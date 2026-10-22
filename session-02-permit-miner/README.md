# Session 02: Your Permit Miner

A building permit is the strongest buying signal your market produces.
It is a public record that a homeowner has already decided to spend the
money and has already been approved to start. The budget exists, the
work is scheduled, and almost nobody in our trade reads them.

In the next hour you will point this at your area, tell it what you
sell, and it will pull recent permits, throw away the ones that aren't
your kind of work, ask Claude to score what's left against your
services, and hand you a **printed-looking postcard preview** for the
best one, with your logo on it.

**Nothing is mailed.** You get a front image, a back image and a PDF
that you download and look at.

**Before class:** you need a GitHub account and an Anthropic account
with an API key and about 5 dollars of credit
(console.anthropic.com). That's it. If you did Session 01 you already
have both, and the same key works here.

---

## Step 1: Get the files

**If you did Session 01** and already have a fork: open your fork on
github.com and press the **Sync fork** button near the top right, then
**Update branch**. Session 02 appears in a new folder. Your Session 01
setup is untouched and keeps working exactly as it did.

**If you're new:** open **github.com/hfscdogg/integrateuworkshops** and
press **Fork** (top right), then **Create fork**. You now have your own
copy.

Either way, make sure the address bar shows YOUR username, not
hfscdogg.

## Step 2: Open the web editor

1. On your fork, press the **period key** ( . ) on your keyboard.
   GitHub opens a full editor in the browser. Nothing installs on your
   computer.
2. In the file list on the left, click the folder
   **session-02-permit-miner**. Everything you touch today is in there.

## Step 3: Fill in config.yml

Click **config.yml**. It is the only file you need to edit, and it is
in six clearly-marked sections. Work down it:

1. **Your company** — name, tagline, phone, website, location. This is
   what gets printed on the card.
2. **What you sell** — the services list. Claude scores every permit
   against these exact words, so be specific. "Lighting" scores worse
   than "tunable white lighting and motorized shades".
3. **Your logo** — leave it for now; Step 4 covers it.
4. **Where the permits come from** — it ships pointed at Austin, Texas
   so your first run works before you change anything. To point it at
   your area, open **counties.md** in the same folder and follow the
   two-minute recipe.
5. **Which permits count** — the money line and the keyword lists. Leave
   these alone for your first run. Step 7 is where they get interesting.
6. **The postcard** — size and your brand colour as a hex code.

## Step 4: Add your logo

1. In the editor's left sidebar, right-click the **brand** folder inside
   session-02-permit-miner and choose **Upload...**
2. Pick your logo file. A PNG with a transparent background looks best.
   Large is fine, it gets scaled down.
3. If your file is not named `logo.png`, update the `logo_path:` line in
   config.yml to match your file name exactly.

Skipping this is fine. A placeholder ships with the repo, and if the
logo file is missing the card prints your company name instead.

## Step 5: Add your secret

In a new browser tab, open your fork on github.com (not the editor) and
go to **Settings > Secrets and variables > Actions > New repository
secret**.

- Name: `ANTHROPIC_API_KEY`
- Value: your key from console.anthropic.com, pasted with no extra
  spaces

Type the name exactly: all caps, underscores, no spaces. **Secrets do
not copy over when you fork**, so even if you saw this in Session 01
you need it in your own fork.

That is the only secret Session 02 needs.

## Step 6: Save and run

1. **Commit (save) your changes.** In the editor, click the Source
   Control icon in the left sidebar (the branching-lines symbol with a
   blue dot), type any short message like `my setup`, and click
   **Commit & Push**.
2. Go back to your fork on github.com and click the **Actions** tab.
   **GitHub switches workflows off on every new fork.** If you see a
   button saying "I understand my workflows, go ahead and enable them",
   click it. Without this, nothing can run.
3. In the left-hand list click **Permit Miner (Session 02)**, then the
   **Run workflow** button on the right. Leave the box that appears
   empty. Click the green **Run workflow** to confirm.
4. Click the run that appears (give it a few seconds), then click
   **miner** to watch it work. It takes about a minute.
5. When it finishes, go back to the run's summary page and scroll to
   the bottom. Under **Artifacts** there is a file called
   **postcard-preview**. Download it, unzip it, and open the PNGs.

You should be looking at the front and back of a postcard aimed at a
real property in your area, with your logo on it.

---

## Step 7 (the actual lesson): argue with the filter

Everything above is plumbing. This is the part worth your hour.

Two numbers in the run log tell you how your business judgment is
doing:

- **"N of M permit(s) survived your filter"** — how much of your
  market you are choosing to ignore, and whether you are ignoring the
  right parts.
- **The scores in "Top of the list"** — how well Claude thinks each
  surviving job matches what you actually sell.

Open **config.yml** and push on it:

- **`minimum_job_value`** is the money line. Raise it to 250000 and you
  get a handful of real projects. Drop it to 25000 and you drown. Find
  your number.
- **`services`** is what Claude scores against. Make it more specific
  and watch the scores and the postcard copy both get sharper.
- **`wanted_work`** is your trade. A pool builder and a lighting
  integrator should have completely different lists.
- **`unwanted_work`** always beats `wanted_work`, on purpose. It is how
  "replace all deck boards" stops pretending to be a deck job.
- **`skip_company_owners`** drops permits pulled by an LLC, which is
  usually a builder or a landlord. Turn it off if you sell to builders.

Change one thing, press Run workflow, read the new numbers. That loop —
not the code — is the skill you are taking home.

Each run costs a fraction of a cent of Anthropic credit. Run it as many
times as you like.

---

## Troubleshooting

**"Your ANTHROPIC_API_KEY secret wasn't found."**
The secret is missing or the name isn't exact. It must be all caps with
underscores. Add it in YOUR fork under Settings > Secrets and variables
> Actions.

**"Claude rejected your API key" or "out of credit."**
The key was pasted incompletely or with spaces, or the account has no
credit. Make a fresh key at console.anthropic.com and update the
secret; add about 5 dollars under Billing.

**"All N permits were filtered out."**
Good news: the run worked, your filter is just too tight. The log lists
what to loosen, in order. The usual culprit is `minimum_job_value` in
an area that leaves the dollar column blank — set
`keep_permits_without_value: true` and run it again.

**"published no permits in the last 30 days."**
Not an error, and the run stays green. That area is quiet or posts in
batches. Raise `lookback_days` to 60 or 90, or pick another area from
counties.md.

**"says that dataset doesn't exist."**
Your portal address is right but the dataset id is wrong. Re-copy the
last chunk of the dataset page's web address. counties.md has the
recipe.

**"config.yml could not be read."**
A quote, a dash or an indent went missing while editing. The message
shows you exactly what the block should look like. The `place`,
`portal` and `dataset` lines each need two spaces in front of them.

**"asking us to slow down."**
Too many requests at once, which happens when a room full of people run
at the same moment. Wait a minute and run it again, or add the free
`SOCRATA_APP_TOKEN` secret described in counties.md.

**There's no Run workflow button.**
Two causes. First: GitHub disables workflows on new forks, so click the
"enable workflows" button on the Actions tab. Second: make sure you
clicked **Permit Miner (Session 02)** in the left-hand list first; the
button lives on that page.

**I can't find the artifact.**
It's at the bottom of the run's summary page, not inside the log view.
Click the run's name in the breadcrumb at the top to get back to the
summary, then scroll down to **Artifacts**.

---

## About that "mail it for real" step

There isn't one, on purpose.

The workflow has an optional hook where a mail house would plug in, and
it is inert: it has no send in it, it does nothing unless you add a
`LOB_API_KEY` secret AND type an exact confirmation phrase into the Run
workflow box, and even then it only prints what a mail house would have
received. Nothing in this repository can spend your money or put paper
in the post.

Wiring up real mail is a decision to make deliberately, after you have
looked at a few dozen of these cards and decided the targeting is
right.

---

## What this is the tip of

This is the workshop edition: one area, one filter, one card, small
enough to read over coffee.

The production version this was carved from doesn't wait for a county
to have an open-data portal. It drives ten county permit systems
directly — Accela, EnerGov, monthly PDF reports, county assessor
lookups for the real assessed value — then enriches each owner with
contact data, mails a printed postcard carrying a personal URL, and
alerts the salesperson the moment somebody scans the QR code on it.
Permits that don't convert get excluded with one click, and those
exclusions become rules that sharpen the next run.

None of that matters until the filter in Step 7 is honest. Start there.
