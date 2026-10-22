"""Your permit miner. You never need to edit this file.

What it does, in order:
  1. Reads everything you set in config.yml
  2. Downloads recent building permits for the area you chose
  3. Throws away the ones that aren't your kind of work
  4. Asks Claude to score what's left against the services you sell
  5. Draws a postcard preview for the best one

Nothing is mailed. You get pictures and a PDF to download.

If anything goes wrong, it prints a plain-English message telling you
exactly what to fix.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta

import requests
import yaml

import postcard

# The Claude model this workshop edition uses. Pinned on purpose so all
# fifty forks behave identically. Maintainer: see MAINTAINERS.md before
# changing this.
CLAUDE_MODEL = "claude-sonnet-5"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
PORTAL_TIMEOUT = 30
OUT_DIR = "output"

# Open-data portals name their columns differently in every area, so the
# miner looks for the first name it recognises out of each list below.
# This is why you only paste two values into config.yml instead of
# filling in a form about your county's spreadsheet.
FIELD_GUESSES = {
    "date": ["issue_date", "issued_date", "date_issued", "permit_issue_date",
             "issueddate", "issued_on", "file_date", "application_date",
             "applied_date", "application_start_date", "status_date"],
    "description": ["work_description", "description", "permit_description",
                    "scope_of_work", "job_description", "work_desc",
                    "proposed_work", "permit_type_desc", "proposed_use"],
    "type": ["permit_type", "permit_type_desc", "permit_class_mapped",
             "permit_class", "permittype", "permit_category", "type"],
    "value": ["reported_cost", "estimated_cost", "total_job_valuation",
              "declared_valuation", "valuation", "total_valuation",
              "construction_cost", "job_value", "estimated_value"],
    "address": ["original_address1", "street_address", "site_address",
                "property_address", "permit_address", "full_address",
                "address_line_1", "location_address", "address"],
    "owner": ["owner_name", "ownername", "owner", "applicant_name",
              "contact_name", "owner_full_name"],
    "city": ["original_city", "property_city", "city", "jurisdiction"],
    "zip": ["original_zip", "zip", "zipcode", "postal_code", "zip_code"],
}

# When an owner's name uses one of these words, it's a company: a
# builder, a landlord or an investor, not a homeowner you can sell to.
# Matched as whole words, so a homeowner called INCANDELA doesn't get
# thrown out for containing "INC".
COMPANY_PATTERNS = [
    "LLC", "INC", "CORP", "CORPORATION", "LP", "LLP", "TRUST", "TRUSTEE",
    "TRUSTEES", "PROPERTIES", "REALTY", "HOLDINGS", "INVESTMENTS",
    "ENTERPRISES", "GROUP", "ASSOCIATES", "PARTNERS", "DEVELOPMENT",
    "CONSTRUCTION", "BUILDERS", "HOMES", "ESTATES", "MANAGEMENT",
    "SERVICES", "SOLUTIONS", "VENTURES", "ESTATE OF",
]


def die(message: str) -> None:
    """Print a fix-it message a non-technical person can act on, then stop."""
    print()
    print("=" * 70)
    print("SOMETHING NEEDS YOUR ATTENTION")
    print("=" * 70)
    print(message)
    print("=" * 70)
    print(f"::error::{message.splitlines()[0]}")
    sys.exit(1)


def stop_politely(message: str) -> None:
    """Finish the run without failing it, and say why in plain words.

    Used when nothing went wrong technically: the area just had no
    permits worth a card. A red X would tell the wrong story.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "NO-POSTCARD-THIS-RUN.txt"), "w",
              encoding="utf-8") as f:
        f.write("No postcard was made this run.\n\n")
        f.write(message + "\n")
    print()
    print("=" * 70)
    print("NOTHING TO PUT ON A POSTCARD THIS RUN")
    print("=" * 70)
    print(message)
    print("=" * 70)
    print("::notice::No postcard this run - see the log for what to change.")
    sys.exit(0)


def load_config() -> dict:
    """Read config.yml and check the handful of things it must contain."""
    try:
        with open("config.yml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        die("config.yml is missing. It should be in the "
            "session-02-permit-miner folder of your repository, next to "
            "this file. If you renamed or moved it, rename it back to "
            "exactly: config.yml")
    except yaml.YAMLError as exc:
        die("config.yml could not be read. This almost always means a "
            "quote, a dash or an indent got lost while editing.\n"
            "The permit_source block has to look exactly like this, with "
            "two spaces in front of each of the last three lines:\n"
            'permit_source:\n'
            '  place: "Austin, Texas"\n'
            '  portal: "data.austintexas.gov"\n'
            '  dataset: "3syk-w9eu"\n'
            f"Technical detail: {exc}")

    if not isinstance(config, dict):
        die("config.yml is empty or isn't laid out the way the miner "
            "expects. Re-copy it from the workshop repository: "
            "github.com/hfscdogg/integrateuworkshops")

    source = config.get("permit_source") or {}
    portal = str(source.get("portal") or "").strip()
    dataset = str(source.get("dataset") or "").strip()
    if not portal or not dataset:
        die("Your permit source isn't set. Open config.yml, find the "
            "permit_source block, and fill in both the portal and the "
            "dataset:\n"
            'permit_source:\n'
            '  place: "Austin, Texas"\n'
            '  portal: "data.austintexas.gov"\n'
            '  dataset: "3syk-w9eu"\n'
            "counties.md in this folder lists areas that are known to work.")

    # People paste the whole web address out of the browser bar, so take
    # the bit that matters and quietly drop the rest.
    portal = portal.replace("https://", "").replace("http://", "")
    portal = portal.strip("/").split("/")[0]

    company = config.get("company") or {}
    if not str(company.get("name") or "").strip():
        die("Your company name isn't set. Open config.yml and fill in the "
            "name under the company block, keeping the quotes:\n"
            'company:\n'
            '  name: "Your Company Name"')

    services = [str(s).strip() for s in (config.get("services") or [])
                if str(s).strip()]
    if not services:
        die("You haven't listed any services. Claude scores every permit "
            "against that list, so it can't rank anything without it. "
            "Open config.yml and put at least one line under services:\n"
            'services:\n'
            '  - "Home theater and media room design"')

    def word_list(key):
        return [str(w).strip().lower()
                for w in (config.get(key) or []) if str(w).strip()]

    config["permit_source"] = {"place": str(source.get("place") or portal).strip(),
                               "portal": portal, "dataset": dataset}
    config["services"] = services
    config["wanted_work"] = word_list("wanted_work")
    config["unwanted_work"] = word_list("unwanted_work")
    config["lookback_days"] = int(config.get("lookback_days") or 30)
    config["max_permits"] = max(1, int(config.get("max_permits") or 25))
    config["minimum_job_value"] = float(config.get("minimum_job_value") or 0)
    config["keep_permits_without_value"] = bool(
        config.get("keep_permits_without_value"))
    config["skip_company_owners"] = config.get("skip_company_owners") is not False
    return config


def pick_field(record: dict, kind: str) -> str:
    """Find which column name this area uses for a thing we care about."""
    for guess in FIELD_GUESSES[kind]:
        if guess in record:
            return guess
    return ""


def build_address(record: dict, address_field: str) -> str:
    """Get a street address out of the record, however the area stores it."""
    if address_field and str(record.get(address_field) or "").strip():
        return str(record[address_field]).strip()
    # Some areas (Chicago, for one) store the address in pieces.
    pieces = [str(record.get(part) or "").strip()
              for part in ("street_number", "street_direction", "street_name",
                           "suffix", "street_suffix", "street_type")]
    return " ".join(p for p in pieces if p).strip()


def parse_money(raw):
    """Turn '$1,250,000.00' or 1250000 into a number. None if unreadable."""
    if raw is None:
        return None
    text = re.sub(r"[^0-9.]", "", str(raw))
    if not text or text == ".":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def mentions(text: str, words: list) -> bool:
    """True when the text uses any of these words.

    Words have to start where a real word starts, which is fussier than
    it sounds and matters a lot. Plain "is this string in there" would
    let "shed" fire on "finished basement" and throw away the best job
    on the list. Endings are still fair game, so "repair" catches
    "repairs" and "roof" catches "roofing".
    """
    return any(re.search(r"\b" + re.escape(word), text) for word in words)


def owner_is_company(owner: str) -> bool:
    """True when the name on the permit belongs to a business."""
    if not owner:
        return False
    cleaned = owner.upper().replace(".", "")
    cleaned = re.sub(r"[^A-Z0-9]+", " ", cleaned)
    return any(f" {p} " in f" {cleaned.strip()} " for p in COMPANY_PATTERNS)


def fetch_permits(config: dict) -> list:
    """Download recent permits for the one area chosen in config.yml."""
    source = config["permit_source"]
    base = f"https://{source['portal']}/resource/{source['dataset']}.json"
    label = source["place"]

    # A free Socrata app token raises the rate limit. Entirely optional:
    # without it the portal still answers, just more stingily.
    headers = {"User-Agent": "Workshop Permit Miner"}
    token = os.environ.get("SOCRATA_APP_TOKEN", "").strip()
    if token:
        headers["X-App-Token"] = token
        print("Using your SOCRATA_APP_TOKEN for a higher rate limit.")

    def get(params):
        return requests.get(base, params=params, timeout=PORTAL_TIMEOUT,
                            headers=headers)

    # First, grab a single record to learn what this area calls its columns.
    try:
        peek = get({"$limit": 1})
    except requests.RequestException as exc:
        die(f"Could not reach {source['portal']}. The portal may be down, "
            f"or the address in config.yml has a typo. Open "
            f"https://{source['portal']} in your browser to check. ({exc})")

    if peek.status_code == 404:
        die(f"{source['portal']} says that dataset doesn't exist. The "
            f"portal address is probably right but the dataset id "
            f"'{source['dataset']}' is wrong.\n"
            f"Open the dataset page in your browser: the id is the last "
            f"chunk of the web address, like ab12-cd34. counties.md in "
            f"this folder lists ids that are known to work.")

    if peek.status_code == 429:
        die("The portal is asking us to slow down (too many requests). "
            "Wait a minute and press Run workflow again. If it keeps "
            "happening, add the free SOCRATA_APP_TOKEN secret: "
            "counties.md explains how.")

    if peek.status_code != 200:
        die(f"{source['portal']} answered with code {peek.status_code} "
            f"instead of data. Check the portal address and dataset id in "
            f"config.yml against the dataset page in your browser.")

    try:
        sample = peek.json()
    except ValueError:
        die(f"{source['portal']} did not return readable data. Check that "
            f"the address in config.yml is an open-data portal: its "
            f"dataset page should have an API button on it.")

    if not sample:
        stop_politely(
            f"{label} published no permits at all in this dataset.\n"
            f"The connection worked, so your settings are fine: this "
            f"dataset is simply empty. Pick another dataset for your area "
            f"from counties.md, or leave the default and run it again.")

    fields = {kind: pick_field(sample[0], kind) for kind in FIELD_GUESSES}

    params = {"$limit": 400}
    if fields["date"]:
        cutoff = (datetime.now() - timedelta(days=config["lookback_days"])
                  ).strftime("%Y-%m-%dT00:00:00.000")
        params["$where"] = f"{fields['date']} > '{cutoff}'"
        params["$order"] = f"{fields['date']} DESC"
    else:
        print(f"NOTE: {label} doesn't publish a date column this miner "
              f"recognises, so it is reading whatever the portal lists "
              f"first rather than the newest permits.")

    try:
        resp = get(params)
    except requests.RequestException as exc:
        die(f"Could not download permits from {label}. This is usually "
            f"temporary: wait a minute and press Run workflow again. ({exc})")

    if resp.status_code != 200:
        die(f"{label} refused the permit request (code {resp.status_code}). "
            f"This usually means its date column works differently from "
            f"most. Try a smaller lookback_days in config.yml, or pick a "
            f"different dataset from counties.md.")

    try:
        rows = resp.json()
    except ValueError:
        die(f"{label} returned data the miner could not read. Try another "
            f"dataset from counties.md.")

    permits = []
    for row in rows:
        where = build_address(row, fields["address"])
        city = str(row.get(fields["city"]) or "").strip() if fields["city"] else ""
        zipcode = str(row.get(fields["zip"]) or "").strip() if fields["zip"] else ""
        permits.append({
            "place": label,
            "address": ", ".join(b for b in (where, city) if b) or where,
            "street": where,
            "city": city,
            "zip": zipcode,
            "type": str(row.get(fields["type"]) or "").strip() if fields["type"] else "",
            "description": str(row.get(fields["description"]) or "").strip() if fields["description"] else "",
            "owner": str(row.get(fields["owner"]) or "").strip() if fields["owner"] else "",
            "value": parse_money(row.get(fields["value"])) if fields["value"] else None,
            "date": str(row.get(fields["date"]) or "")[:10] if fields["date"] else "",
        })

    print(f"OK: {len(permits)} permit(s) published by {label} in the last "
          f"{config['lookback_days']} days.")
    return permits


def qualify(permit: dict, config: dict) -> bool:
    """Decide whether one permit is worth Claude's attention.

    The order matters, and it is the whole lesson of this session:
      1. a company on the deed is somebody else's job
      2. the killer words win over the wanted words, always
      3. the work has to be something you actually sell
      4. the job has to be big enough to be worth a stamp
    """
    text = f"{permit['type']} {permit['description']}".lower()

    if config["skip_company_owners"] and owner_is_company(permit["owner"]):
        return False
    if mentions(text, config["unwanted_work"]):
        return False
    if config["wanted_work"] and not mentions(text, config["wanted_work"]):
        return False
    if permit["value"] is None:
        return config["keep_permits_without_value"]
    return permit["value"] >= config["minimum_job_value"]


def call_claude(api_key: str, message: str) -> str:
    """One call to Claude. Returns the text it wrote."""
    try:
        resp = requests.post(
            ANTHROPIC_URL, timeout=120,
            headers={"x-api-key": api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": CLAUDE_MODEL, "max_tokens": 2000,
                  "messages": [{"role": "user", "content": message}]},
        )
    except requests.RequestException as exc:
        die(f"Could not reach Claude's servers. This is usually temporary: "
            f"wait one minute and press Run workflow again. ({exc})")

    if resp.status_code == 401:
        die("Claude rejected your API key. The ANTHROPIC_API_KEY secret "
            "exists but its value is wrong. Common causes: extra spaces "
            "pasted around the key, or an incomplete copy. Create a fresh "
            "key at console.anthropic.com > API keys, then update the "
            "secret under Settings > Secrets and variables > Actions.")
    if resp.status_code == 400 and "credit" in resp.text.lower():
        die("Your Anthropic account is out of credit, so Claude cannot "
            "answer. Go to console.anthropic.com > Billing and add credit "
            "(5 dollars is plenty for a whole workshop), then press Run "
            "workflow again.")
    if resp.status_code == 429:
        die("Claude is rate limiting requests right now. Wait one minute "
            "and press Run workflow again.")
    if resp.status_code != 200:
        die(f"Claude answered with an unexpected error (code "
            f"{resp.status_code}). Wait a minute and press Run workflow "
            f"again. If it keeps happening, ask for help and share this: "
            f"{resp.text[:300]}")

    return "".join(b.get("text", "") for b in resp.json().get("content", [])
                   ).strip()


def extract_json(text: str):
    """Pull the JSON list out of whatever Claude wrote around it."""
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


def score_permits(permits: list, config: dict) -> list:
    """Ask Claude to score each permit against what you sell."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        die("Your ANTHROPIC_API_KEY secret wasn't found. Check the name is "
            "exact: all caps, underscores, no spaces. Add it under "
            "Settings > Secrets and variables > Actions > New repository "
            "secret, in YOUR fork (not the original repository).")

    company = config["company"]
    listed = "\n".join(f"- {s}" for s in config["services"])
    rows = []
    for n, p in enumerate(permits):
        value = f"${p['value']:,.0f}" if p["value"] is not None else "not stated"
        rows.append(
            f"{n}. {p['address'] or 'address not stated'}\n"
            f"   Filed: {p['date'] or 'not stated'}   Declared value: {value}\n"
            f"   Permit type: {p['type'] or 'not stated'}\n"
            f"   Work: {p['description'] or 'not stated'}")

    message = f"""You are the head of business development at {company.get('name')}, a custom integration company in {company.get('location') or 'the area'}.

These are the services you sell:
{listed}

Below are real building permits recently pulled in {config['permit_source']['place']}. Each one is a homeowner who has already decided to spend money and already been approved to start.

Score every permit on how well it fits what you sell, then write the copy for a postcard aimed at the best ones.

Respond with ONLY a JSON array, no other words, no markdown fence. One object per permit, in the same order as the list, each with exactly these keys:

"index": the number shown next to the permit
"score": 0-100, how well this project fits the services above
"fit": one short sentence naming which of your services this project needs and why
"headline": under 9 words, for the front of a postcard, speaking to the homeowner about their project. Never mention the word permit.
"front_message": under 30 words, for the front of the card, warm and specific to what they are building
"back_headline": under 8 words, the pitch headline
"back_message": 40-70 words for the back of the card. Speak to the homeowner as someone building this exact thing. Say what you would do for them and why the timing matters right now. No pressure, no gimmicks, no fake urgency.

Scoring guidance: a new build or a whole-home renovation scores highest because every system is still on the table. A single-room project scores mid. Anything where your services barely apply scores low. Be honest with low scores.

The permits:

{chr(10).join(rows)}"""

    print(f"Asking Claude to score {len(permits)} permit(s) against your "
          f"{len(config['services'])} service line(s)...")
    scored = extract_json(call_claude(api_key, message))

    if scored is None:
        print("NOTE: Claude's first answer wasn't clean JSON. Asking once more.")
        scored = extract_json(call_claude(
            api_key, message + "\n\nReturn ONLY the JSON array. "
                               "Start your reply with [ and end it with ]."))

    if scored is None:
        print("WARNING: Claude did not return readable scores twice in a "
              "row, so the miner is falling back to the biggest declared "
              "job and generic postcard copy. Everything else still works. "
              "Press Run workflow to try again for tailored copy.")
        return []
    return scored


def attach_scores(permits: list, scored: list) -> list:
    """Match Claude's scores back onto the permits, best first."""
    if not scored:
        # Fallback: biggest declared job wins, with plain copy.
        ranked = sorted(permits, key=lambda p: p["value"] or 0, reverse=True)
        for p in ranked:
            p["pick"] = {
                "score": None,
                "fit": "Scored by job size only (Claude's ranking was "
                       "unavailable this run).",
                "headline": "Building something great?",
                "front_message": "We help homeowners get the technology "
                                 "right while the walls are still open.",
                "back_headline": "Let's talk before drywall",
                "back_message": (
                    "We work with homeowners during construction, when "
                    "wiring, lighting and network decisions are still easy "
                    "and inexpensive to make. If you are early in this "
                    "project, a short conversation now can save a lot of "
                    "retrofitting later. We would be glad to walk your "
                    "plans with you."),
            }
        return ranked

    by_index = {}
    for item in scored:
        if not isinstance(item, dict):
            continue
        try:
            by_index[int(item.get("index"))] = item
        except (TypeError, ValueError):
            continue

    ranked = []
    for n, permit in enumerate(permits):
        item = by_index.get(n)
        if not item:
            continue
        try:
            score = float(item.get("score"))
        except (TypeError, ValueError):
            score = 0.0
        permit["pick"] = {
            "score": score,
            "fit": str(item.get("fit") or "").strip(),
            "headline": str(item.get("headline") or "Building something great?").strip(),
            "front_message": str(item.get("front_message") or "").strip(),
            "back_headline": str(item.get("back_headline") or "Let's talk").strip(),
            "back_message": str(item.get("back_message") or "").strip(),
        }
        ranked.append(permit)

    ranked.sort(key=lambda p: p["pick"]["score"] or 0, reverse=True)
    return ranked


def write_summary(ranked: list, config: dict, made: list) -> None:
    """Leave a plain-text scoreboard next to the postcards."""
    path = os.path.join(OUT_DIR, "scoreboard.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"PERMIT MINER - {config['permit_source']['place']}\n")
        f.write(f"Run on {datetime.now().strftime('%B %d, %Y at %H:%M')}\n")
        f.write(f"Company: {config['company'].get('name')}\n")
        f.write("=" * 68 + "\n\n")
        if made:
            f.write("Postcards made this run:\n")
            for name in made:
                f.write(f"  - {name}\n")
            f.write("\n")
        f.write("Every permit that passed your filter, best first:\n\n")
        for i, p in enumerate(ranked, 1):
            pick = p.get("pick", {})
            score = pick.get("score")
            value = f"${p['value']:,.0f}" if p["value"] is not None else "not stated"
            f.write(f"{i}. [{'%3d' % score if score is not None else ' --'}] "
                    f"{p['address'] or 'address not stated'}\n")
            f.write(f"      Filed {p['date'] or 'not stated'}   "
                    f"Declared value {value}\n")
            f.write(f"      {p['description'] or 'no description'}\n")
            if pick.get("fit"):
                f.write(f"      Fit: {pick['fit']}\n")
            f.write("\n")
    print(f"OK: scoreboard written to {path}")


def offer_optional_mail(made: list) -> None:
    """The mail step. Deliberately does NOT send anything.

    Two locks have to be open before this even prints a payload: the
    optional LOB_API_KEY secret has to exist, and you have to type an
    exact confirmation phrase into the Run workflow box. Even then it
    only shows you what a mail house would receive. Sending for real is
    a deliberate change you make after the workshop, on purpose, with
    your eyes open.
    """
    has_key = bool(os.environ.get("LOB_API_KEY", "").strip())
    typed = os.environ.get("MAIL_CONFIRMATION", "").strip()
    if not has_key:
        return
    if typed != "PREVIEW THE MAIL PAYLOAD":
        print("\nOptional mail step: LOB_API_KEY is present but the "
              "confirmation phrase was not typed, so nothing was prepared. "
              "This is the safe default.")
        return
    print("\n" + "=" * 70)
    print("OPTIONAL MAIL STEP - DRY RUN ONLY, NOTHING WAS SENT")
    print("=" * 70)
    print("A mail house would receive one job per card below. This build "
          "does not contain a live send, on purpose: nothing here can "
          "spend your money or post anything.")
    for name in made:
        print(f"  would submit: {name} (front + back, print ready)")
    print("=" * 70)


def main() -> None:
    print("Step 1 of 5: reading your settings...")
    config = load_config()
    source = config["permit_source"]
    print(f"Area: {source['place']}  |  Company: "
          f"{config['company'].get('name')}")

    print(f"\nStep 2 of 5: downloading permits for {source['place']}...")
    permits = fetch_permits(config)
    if not permits:
        stop_politely(
            f"{source['place']} published no permits in the last "
            f"{config['lookback_days']} days.\n"
            f"Nothing is broken: this area is just quiet, or it posts in "
            f"batches. Raise lookback_days in config.yml to 60 or 90 and "
            f"run it again, or try another area from counties.md.")

    print("\nStep 3 of 5: throwing away the ones that aren't your work...")
    kept = [p for p in permits if qualify(p, config)]
    print(f"{len(kept)} of {len(permits)} permit(s) survived your filter.")
    if not kept:
        stop_politely(
            f"All {len(permits)} permit(s) from {source['place']} were "
            f"filtered out, so there was nothing to score.\n"
            f"This is almost always the filter being too tight, not a "
            f"broken run. In config.yml try, in this order:\n"
            f"  1. lower minimum_job_value (many areas under-report value)\n"
            f"  2. set keep_permits_without_value to true\n"
            f"  3. take a word out of unwanted_work\n"
            f"  4. raise lookback_days to look further back")

    kept = kept[:config["max_permits"]]

    print("\nStep 4 of 5: scoring them against what you sell...")
    ranked = attach_scores(kept, score_permits(kept, config))
    if not ranked:
        stop_politely("Claude returned scores but none of them lined up "
                      "with your permits. Press Run workflow to try again.")

    print("\nTop of the list:")
    for p in ranked[:5]:
        score = p["pick"].get("score")
        print(f"  [{'%3d' % score if score is not None else ' --'}] "
              f"{p['address']}")
        if p["pick"].get("fit"):
            print(f"        {p['pick']['fit']}")

    print("\nStep 5 of 5: drawing your postcard preview...")
    how_many = max(1, int((config.get("postcard") or {}).get("render_top") or 1))
    made = []
    for i, permit in enumerate(ranked[:how_many], 1):
        stem = f"postcard-{i:02d}"
        front, back, pdf = postcard.render(permit["pick"], permit, config,
                                           OUT_DIR, stem)
        made.extend(os.path.basename(p) for p in (front, back, pdf))
        print(f"  made {os.path.basename(front)}, "
              f"{os.path.basename(back)} and {os.path.basename(pdf)}")
        print(f"       for {permit['address']}")

    write_summary(ranked, config, made)
    offer_optional_mail(made)

    print()
    print("All done. Nothing was mailed.")
    print("Go to the Actions tab, open this run, and download the "
          "'postcard-preview' artifact at the bottom of the page.")


if __name__ == "__main__":
    main()
