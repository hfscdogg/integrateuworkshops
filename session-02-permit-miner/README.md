# Session 02: Your Permit Miner

A building permit is the strongest buying signal your market produces:
a homeowner has already decided to spend the money and has already been
approved to start. Thousands of US cities publish theirs for free, the
day they're issued, and almost nobody in our trade reads them.

This repository reads your city's permits, throws away the ones that
aren't your kind of work, asks Claude (an AI) to rank what's left, and
emails you a short call list. You are about to make your own copy and
turn it on. Total editing required: two files, two secrets, one button.

**Before class (from the prep video):** you need three free accounts:
a GitHub account, an Anthropic account with an API key and about 5
dollars of credit (console.anthropic.com), and a Resend account with an
API key (resend.com). Keep both keys somewhere you can copy from.

**Did Session 01?** Same two secrets, same button. If you already have
the Intel Scout running in this fork, your secrets are already set and
you can skip Step 3, part 1.

---

## Step 1: Open your fork in the web editor

1. Make sure you are looking at YOUR copy of this repository (the fork
   you created; the address bar should show your username, not
   hfscdogg).
2. Press the **period key** ( . ) on your keyboard. GitHub opens the
   web editor: it looks like a programmer's tool, but you will only
   touch two files. Nothing installs on your computer.
3. In the file list on the left, click the folder called
   **session-02-permit-miner**. Everything you need is inside it.

## Step 2: Point it at your city

1. In that folder, click **config.yml**.
2. You'll see three `sources:` blocks, pre-loaded with three real,
   large city permit datasets, so the miner works even if you change
   nothing.
3. To make it yours, open a new tab and Google
   **"your city open data building permits"**. You're looking for a
   page on a government site with an **API** button on it.
4. The dataset address looks like
   `https://data.yourcity.gov/Housing/Building-Permits/ab12-cd34`.
   Two pieces matter:
   - the **portal**: `data.yourcity.gov` (between `https://` and the
     next slash)
   - the **dataset**: `ab12-cd34` (the very last chunk, letters and
     numbers with a dash)
5. Replace one of the three blocks with yours, keeping the dashes,
   indents and quotes exactly as they are.

**If your city isn't there yet**, leave the defaults. Everything below
still works, and you'll see exactly how the miner thinks using another
city's permits. Plenty of counties are still on paper; that's worth
knowing too.

## Step 3: Give it a brain

1. **Add your two secrets.** In a new browser tab, open your fork on
   github.com (not the editor) and go to **Settings > Secrets and
   variables > Actions > New repository secret**. Add these two, names
   typed exactly, values pasted with no extra spaces:
   - Name: `ANTHROPIC_API_KEY` -- Value: your key from console.anthropic.com
   - Name: `RESEND_API_KEY` -- Value: your key from resend.com
2. **Teach it your business.** Back in the web editor, click
   **prompt.txt**. Find the loud comment that says EDIT THIS LINE.
   Replace `[YOUR CITY]` and `[YOUR NICHE]` with your real city and
   what you sell. That one line is the only thing you need to change.

## Step 4: Ship it

1. In the web editor, click **config.yml** one more time and replace
   `you@example.com` with your real email address: the SAME address you
   signed up to Resend with (the free plan only delivers to that one).
2. **Commit (save) your changes:** click the Source Control icon in the
   left sidebar (the branching-lines symbol with a blue dot), type any
   short message like `my setup`, and click **Commit & Push**.
3. Go back to your fork on github.com and click the **Actions** tab.
   **GitHub switches workflows off on every new fork.** You'll see a
   button that says something like "I understand my workflows, go ahead
   and enable them": click it. Without this, nothing can run.
4. In the left list click **Permit Miner**, then the **Run workflow**
   button on the right, then the green **Run workflow** confirm button.
5. Click the run that appears (give it a few seconds), then click
   **miner** to watch it work. In about a minute you'll see
   "All done. Check your inbox."
6. Check your inbox. First time, also check spam and mark it "not
   spam" so the next one lands where it should.

**This one waits for you.** Unlike Session 01, the miner runs when you
press Run workflow, not on a timer. Permits move weekly, not hourly, so
pressing the button on Monday morning is the honest cadence. When you
want it automatic, open `.github/workflows/permits.yml` and follow the
two-line note at the top.

---

## Step 5 (the actual lesson): tune the filter

Everything above is plumbing. This is the part worth your hour.

Scroll through the run log and look at the line that says
**"N of M permit(s) survived your filter."** That ratio is your
business judgment, written down. Now open **config.yml** and argue with
it:

- **`minimum_job_value`** is the money line. Raise it to 250000 and
  you'll get a handful of real projects. Drop it to 25000 and you'll
  drown. Find your number.
- **`wanted_work`** is your trade. A pool builder and a lighting
  integrator should have completely different lists. Delete what isn't
  yours; add the words your customers actually use.
- **`unwanted_work`** always wins over `wanted_work`, on purpose. It's
  how "replace all deck boards" stops pretending to be a deck job.
- **`skip_company_owners`** drops permits pulled by an LLC. Usually
  that's a builder or a landlord. Turn it off if you sell to builders.

Change one thing, press Run workflow, read the new number. That loop --
not the code -- is the skill.

---

## Troubleshooting

**"Your ANTHROPIC_API_KEY secret wasn't found."**
The secret is missing or the name isn't exact. It must be all caps with
underscores: `ANTHROPIC_API_KEY`. Add it in YOUR fork under Settings >
Secrets and variables > Actions (secrets do not copy over when you
fork).

**"Claude rejected your API key" or "out of credit."**
Your key was pasted incompletely or with spaces, or your Anthropic
account has no credit. Create a fresh key at console.anthropic.com and
update the secret; add about 5 dollars of credit under Billing.

**"Resend refused to deliver" or no email arrives.**
The free Resend plan only delivers to the exact email you signed up
with. Make sure the `email:` line in config.yml matches your Resend
account address. If the log says the email sent, check your spam
folder.

**"Every permit was filtered out."**
Good news: the run worked, your filter is just too tight. The log tells
you what to loosen, in order. The usual culprit is `minimum_job_value`
on a city that leaves the dollar column blank -- set
`keep_permits_without_value: true` and run it again.

**"answered 'not found'" for one of your sources.**
The portal address is right but the dataset id is wrong. Open the
dataset page in your browser and re-copy the last chunk of the web
address (the `ab12-cd34` part).

**"None of your permit sources returned anything."**
Every source failed. Open each portal address from config.yml in your
browser. If your city's portal is down today, put back one of the three
defaults and run it again.

**There's no Run workflow button in the Actions tab.**
Two causes. First: GitHub disables workflows on new forks, so click the
"enable workflows" button on the Actions tab if you see one. Second:
make sure you clicked **Permit Miner** in the left-hand list first;
the button lives on that page.

---

## What this is the tip of

This is the workshop edition: one file of pipeline, small enough to
read over coffee, reading whatever your city happens to publish.

The production version this was carved from doesn't wait for a city to
have an open-data portal. It drives ten county permit portals directly
-- Accela, EnerGov, monthly PDF reports, county assessor lookups for
the real property value -- then enriches each owner with contact data,
mails a printed postcard with a personalized URL on it, and tells the
salesperson the moment somebody scans the QR code. Permits that don't
convert get excluded with one click, and the exclusion rules learn.

None of that matters until the filter in Step 5 is honest. Start there.
