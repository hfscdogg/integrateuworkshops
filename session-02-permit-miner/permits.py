"""Your permit miner pipeline. You never need to edit this file.

What it does, in order:
  1. Reads your settings from config.yml and your instructions from prompt.txt
  2. Downloads recent building permits from the open-data portals you chose
  3. Throws away the ones that aren't your kind of work
  4. Sends the survivors plus your instructions to Claude
  5. Emails you the call list Claude wrote

If anything goes wrong, it prints a plain-English message telling you
exactly what to fix.
"""

import os
import re
import sys
from datetime import datetime, timedelta

import requests
import yaml

# The Claude model this workshop edition uses. Pinned on purpose so all
# fifty forks behave identically. Maintainer: see MAINTAINERS.md before
# changing this.
CLAUDE_MODEL = "claude-sonnet-5"

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
RESEND_URL = "https://api.resend.com/emails"
PORTAL_TIMEOUT = 30      # seconds per portal download

# Open-data portals name their columns differently from city to city, so
# the miner looks for the first name it recognises out of each list
# below. This is why you only have to paste an address in config.yml
# instead of filling in a form about your city's spreadsheet.
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
}

# When an owner's name contains one of these words, it's a company: a
# builder, a landlord or an investor, not a homeowner you can sell to.
# These are matched as whole words, so a homeowner called INCANDELA
# doesn't get thrown out for containing "INC".
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
    # The ::error:: line makes GitHub show the first sentence in red at
    # the top of the run page.
    print(f"::error::{message.splitlines()[0]}")
    sys.exit(1)


def load_config() -> dict:
    """Read config.yml and check the things it must contain."""
    try:
        with open("config.yml", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        die("config.yml is missing. It should be in the "
            "session-02-permit-miner folder of your repository, next to "
            "this file. If you renamed or moved it, rename it back to "
            "exactly: config.yml")
    except yaml.YAMLError as exc:
        die("config.yml could not be read. This usually means a quote, a "
            "dash or an indent got deleted while editing.\n"
            "Open config.yml and check that every source block looks "
            "exactly like:\n"
            '  - name: "Austin, TX"\n'
            '    portal: "data.austintexas.gov"\n'
            '    dataset: "3syk-w9eu"\n'
            f"Technical detail: {exc}")

    sources = []
    for entry in (config.get("sources") or []):
        if not isinstance(entry, dict):
            continue
        portal = str(entry.get("portal") or "").strip()
        dataset = str(entry.get("dataset") or "").strip()
        if not portal or not dataset:
            continue
        # People paste the whole web address out of the browser bar, so
        # take the bit that matters and quietly drop the rest.
        portal = portal.replace("https://", "").replace("http://", "").strip("/")
        portal = portal.split("/")[0]
        sources.append({
            "name": str(entry.get("name") or portal).strip(),
            "portal": portal,
            "dataset": dataset,
        })

    if not sources:
        die("No permit sources found in config.yml. Add at least one block "
            'under "sources:" that looks exactly like:\n'
            '  - name: "Austin, TX"\n'
            '    portal: "data.austintexas.gov"\n'
            '    dataset: "3syk-w9eu"')

    email = str(config.get("email") or "").strip()
    if not email or "@" not in email or email == "you@example.com":
        die("Your email address is not set yet. Open config.yml and replace "
            'you@example.com with your real address, keeping the quotes:\n'
            '  email: "yourname@gmail.com"\n'
            "Use the SAME address you signed up to Resend with.")

    def word_list(key: str) -> list[str]:
        return [str(w).strip().lower()
                for w in (config.get(key) or []) if str(w).strip()]

    return {
        "sources": sources,
        "email": email,
        "lookback_days": int(config.get("lookback_days") or 30),
        "max_permits": int(config.get("max_permits") or 40),
        "minimum_job_value": float(config.get("minimum_job_value") or 0),
        "keep_permits_without_value": bool(
            config.get("keep_permits_without_value")),
        "wanted_work": word_list("wanted_work"),
        "unwanted_work": word_list("unwanted_work"),
        "skip_company_owners": config.get("skip_company_owners") is not False,
    }


def load_prompt() -> str:
    """Read prompt.txt, dropping the # comment lines meant for humans."""
    try:
        with open("prompt.txt", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        die("prompt.txt is missing. It should be in the "
            "session-02-permit-miner folder of your repository. If you "
            "renamed or moved it, rename it back to exactly: prompt.txt")

    prompt = "\n".join(
        line for line in lines if not line.lstrip().startswith("#")).strip()
    if not prompt:
        die("prompt.txt is empty (or only contains # comment lines). Put the "
            "instructions back, or re-copy the file from the workshop "
            "repository: github.com/hfscdogg/integrateuworkshops")
    return prompt


def pick_field(record: dict, kind: str) -> str:
    """Find which column name this city uses for a thing we care about."""
    for guess in FIELD_GUESSES[kind]:
        if guess in record:
            return guess
    return ""


def build_address(record: dict, address_field: str) -> str:
    """Get a street address out of the record, however the city stores it."""
    if address_field and str(record.get(address_field) or "").strip():
        return str(record[address_field]).strip()

    # Some cities (Chicago, for one) store the address in pieces.
    pieces = [
        str(record.get(part) or "").strip()
        for part in ("street_number", "street_direction", "street_name",
                     "suffix", "street_suffix", "street_type")
    ]
    return " ".join(p for p in pieces if p).strip()


def parse_money(raw) -> float | None:
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


def fetch_permits(source: dict, lookback_days: int, max_permits: int) -> list[dict]:
    """Download recent permits from one open-data portal.

    Returns a list of tidied-up permit dicts. Problems are printed as
    warnings; the run continues with the other sources.
    """
    base = f"https://{source['portal']}/resource/{source['dataset']}.json"
    label = source["name"]

    def get(params: dict):
        return requests.get(base, params=params, timeout=PORTAL_TIMEOUT,
                            headers={"User-Agent": "Workshop Permit Miner"})

    # First, grab a single record to learn what this city calls its columns.
    try:
        peek = get({"$limit": 1})
    except requests.RequestException as exc:
        print(f"WARNING: could not reach the portal for {label} "
              f"({source['portal']}). The portal may be down, or the "
              f"address has a typo. Open https://{source['portal']} in "
              f"your browser to check. ({exc})")
        return []

    if peek.status_code == 404:
        print(f"WARNING: {label} answered 'not found'. The portal address "
              f"is probably right but the dataset id "
              f"'{source['dataset']}' is wrong. Open the dataset page in "
              f"your browser: the id is the last chunk of the web "
              f"address, like ab12-cd34.")
        return []

    if peek.status_code == 429:
        print(f"WARNING: {label} is asking us to slow down (too many "
              f"requests). Wait a minute and press Run workflow again.")
        return []

    if peek.status_code != 200:
        print(f"WARNING: {label} answered with code {peek.status_code} "
              f"instead of data. Check the portal address and dataset id "
              f"in config.yml against the dataset page in your browser.")
        return []

    try:
        sample = peek.json()
    except ValueError:
        print(f"WARNING: {label} did not return readable data. Check that "
              f"the portal address in config.yml is an open-data portal "
              f"(the page should offer an 'API' button).")
        return []

    if not sample:
        print(f"WARNING: {label} returned no permits at all. The dataset "
              f"exists but is empty.")
        return []

    record = sample[0]
    fields = {kind: pick_field(record, kind) for kind in FIELD_GUESSES}

    # Now ask for the recent ones. If we couldn't work out which column
    # holds the date, we just take whatever the portal gives us first.
    params = {"$limit": 400}
    if fields["date"]:
        cutoff = (datetime.now() - timedelta(days=lookback_days)).strftime(
            "%Y-%m-%dT00:00:00.000")
        params["$where"] = f"{fields['date']} > '{cutoff}'"
        params["$order"] = f"{fields['date']} DESC"
    else:
        print(f"NOTE: {label} doesn't publish a date column this miner "
              f"recognises, so it is reading the most recent permits the "
              f"portal happens to list first.")

    try:
        resp = get(params)
    except requests.RequestException as exc:
        print(f"WARNING: could not download permits for {label}. ({exc})")
        return []

    if resp.status_code != 200:
        print(f"WARNING: {label} refused the permit request (code "
              f"{resp.status_code}). This usually means its date column "
              f"works differently. Try a smaller lookback_days in "
              f"config.yml, or pick another dataset.")
        return []

    try:
        rows = resp.json()
    except ValueError:
        print(f"WARNING: {label} returned data the miner could not read.")
        return []

    permits = []
    for row in rows[:max_permits * 10]:
        permits.append({
            "source": label,
            "address": build_address(row, fields["address"]),
            "city": str(row.get(fields["city"]) or "").strip() if fields["city"] else "",
            "type": str(row.get(fields["type"]) or "").strip() if fields["type"] else "",
            "description": str(row.get(fields["description"]) or "").strip() if fields["description"] else "",
            "owner": str(row.get(fields["owner"]) or "").strip() if fields["owner"] else "",
            "value": parse_money(row.get(fields["value"])) if fields["value"] else None,
            "date": str(row.get(fields["date"]) or "")[:10] if fields["date"] else "",
        })

    print(f"OK: {len(permits)} permit(s) from {label}")
    return permits


def mentions(text: str, words: list[str]) -> bool:
    """True when the text uses any of these words.

    Words have to start where a real word starts, which is fussier than
    it sounds and matters a lot. Plain "is this string in there" would
    let "shed" fire on "finished basement" and throw away the best job
    on the list. Endings are still fair game, so "repair" catches
    "repairs" and "roof" catches "roofing".
    """
    return any(re.search(r"\b" + re.escape(word), text) for word in words)


def owner_is_company(owner: str) -> bool:
    """True when the name on the permit belongs to a business.

    Whole words only. "L.L.C." and "LLC" both count, but a homeowner
    named INCANDELA or PHILIP is left alone.
    """
    if not owner:
        return False
    # Drop the dots so L.L.C becomes LLC, then turn every other bit of
    # punctuation into a space so we can compare whole words.
    cleaned = owner.upper().replace(".", "")
    cleaned = re.sub(r"[^A-Z0-9]+", " ", cleaned)
    padded = f" {cleaned.strip()} "
    return any(f" {pattern} " in padded for pattern in COMPANY_PATTERNS)


def qualify(permit: dict, config: dict) -> bool:
    """Decide whether one permit is worth putting in front of Claude.

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


def ask_claude(prompt: str, permits: list[dict]) -> str:
    """Send the permits plus your instructions to Claude, return the list."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        die("Your ANTHROPIC_API_KEY secret wasn't found. Check the name is "
            "exact: all caps, underscores, no spaces. Add it under "
            "Settings > Secrets and variables > Actions > New repository "
            "secret, in YOUR fork (not the original repository).")

    lines = []
    for n, p in enumerate(permits, 1):
        value = f"${p['value']:,.0f}" if p["value"] is not None else "not stated"
        where = ", ".join(bit for bit in (p["address"], p["city"]) if bit)
        lines.append(
            f"{n}. {where or 'address not stated'}\n"
            f"   Filed: {p['date'] or 'date not stated'}   "
            f"Declared value: {value}\n"
            f"   Permit type: {p['type'] or 'not stated'}\n"
            f"   Work: {p['description'] or 'not stated'}\n"
            f"   Owner: {p['owner'] or 'not stated'}   ({p['source']})"
        )
    message = f"{prompt}\n\nHere are the permits that passed your filter:\n\n" \
              + "\n".join(lines)

    try:
        resp = requests.post(
            ANTHROPIC_URL,
            timeout=120,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 1200,
                "messages": [{"role": "user", "content": message}],
            },
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
            "(5 dollars is plenty for months of call lists), then press "
            "Run workflow again.")

    if resp.status_code == 429:
        die("Claude is rate limiting requests right now. Wait one minute "
            "and press Run workflow again.")

    if resp.status_code != 200:
        die(f"Claude answered with an unexpected error (code "
            f"{resp.status_code}). Wait a minute and press Run workflow "
            f"again. If it keeps happening, ask for help and share this: "
            f"{resp.text[:300]}")

    call_list = "".join(
        block.get("text", "")
        for block in resp.json().get("content", [])
    ).strip()
    if not call_list:
        die("Claude answered but the call list came back empty. Press Run "
            "workflow to try again.")
    return call_list


def send_email(call_list: str, recipient: str) -> None:
    """Deliver the call list to your inbox through Resend."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        die("Your RESEND_API_KEY secret wasn't found. Check the name is "
            "exact: all caps, underscores, no spaces. Get the key from "
            "resend.com > API Keys, then add it under Settings > Secrets "
            "and variables > Actions > New repository secret in YOUR fork.")

    today = datetime.now().strftime("%B %d, %Y")
    try:
        resp = requests.post(
            RESEND_URL,
            timeout=30,
            headers={"Authorization": f"Bearer {api_key}",
                     "Content-Type": "application/json"},
            json={
                "from": "Permit Miner <onboarding@resend.dev>",
                "to": [recipient],
                "subject": f"Your Permit Call List for {today}",
                "text": call_list,
            },
        )
    except requests.RequestException as exc:
        die(f"Could not reach the email service. This is usually temporary: "
            f"wait one minute and press Run workflow again. ({exc})")

    if resp.status_code in (401, 403) and "testing" not in resp.text.lower():
        die("The email service rejected your RESEND_API_KEY. Create a fresh "
            "key at resend.com > API Keys and update the secret under "
            "Settings > Secrets and variables > Actions.")

    if resp.status_code != 200:
        body = resp.text.lower()
        if "testing" in body or "own email" in body or "verify" in body:
            die(f"Resend refused to deliver to {recipient}. On the free "
                f"plan, Resend only delivers to the email address you "
                f"signed up with. Open config.yml and set the email line "
                f"to the exact address on your Resend account.")
        die(f"The email service answered with an unexpected error (code "
            f"{resp.status_code}). Wait a minute and press Run workflow "
            f"again. If it keeps happening, ask for help and share this: "
            f"{resp.text[:300]}")

    print(f"OK: call list emailed to {recipient}")


def main() -> None:
    print("Step 1 of 5: reading your settings...")
    config = load_config()
    prompt = load_prompt()

    print(f"Step 2 of 5: downloading permits from the last "
          f"{config['lookback_days']} days...")
    permits = []
    for source in config["sources"]:
        permits.extend(fetch_permits(
            source, config["lookback_days"], config["max_permits"]))

    if not permits:
        die("None of your permit sources returned anything, so there is "
            "nothing to mine. Open each portal address from config.yml in "
            "your browser and check the dataset id still matches the one "
            "in the web address. If your city's portal is down today, put "
            "back one of the three defaults and run it again.")
    print(f"Collected {len(permits)} permit(s) total.")

    print("Step 3 of 5: throwing away the ones that aren't your work...")
    kept = [p for p in permits if qualify(p, config)]
    kept = kept[:config["max_permits"]]
    print(f"{len(kept)} of {len(permits)} permit(s) survived your filter.")

    if not kept:
        die("Every permit was filtered out, so there is nothing to send to "
            "Claude. This is almost always the filter being too tight, not "
            "a broken run. In config.yml try, in this order:\n"
            "  1. lower minimum_job_value (many cities under-report value)\n"
            "  2. set keep_permits_without_value to true\n"
            "  3. take a word out of unwanted_work\n"
            "  4. raise lookback_days to look further back")

    print("Step 4 of 5: asking Claude which ones to call...")
    call_list = ask_claude(prompt, kept)
    print()
    print("-" * 70)
    print(call_list)
    print("-" * 70)
    print()

    print("Step 5 of 5: emailing it to you...")
    send_email(call_list, config["email"])
    print()
    print("All done. Check your inbox (and the spam folder, the first time).")


if __name__ == "__main__":
    main()
