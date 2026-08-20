# Maintainer Notes (Henry)

Attendees never need this file. It covers keeping the workshop repo
healthy and the morning-of checklist.

## Updating the pinned Claude model

The model string lives in a `CLAUDE_MODEL` constant near the top of the
pipeline file, and there is now ONE PER SESSION. Both currently read
`claude-sonnet-5`; change them together:

- Session 01: `brief.py`
- Session 02: `session-02-permit-miner/permits.py`

To update:

1. Check the current model list at docs.anthropic.com (Models page).
2. Change both constants to the new id.
3. Run the end-to-end tests below from a fresh fork before class.
4. Rough cost check: a session 01 run sends ~36 headlines (~4-6k input
   tokens) and gets back <1k output tokens. A session 02 run sends at
   most 40 permits (~3-5k input tokens) and gets back <1.2k. Fifty
   attendees running each twice during class is well under a dollar
   total on any current model, but confirm the new model's pricing
   hasn't changed that math.

Also pinned, and worth a glance once a quarter: the two actions in EACH
workflow (`.github/workflows/brief.yml` and
`.github/workflows/permits.yml` both use `actions/checkout@v4.2.2` and
`actions/setup-python@v5.3.0`) and the libraries in each session's
`requirements.txt`. Bump deliberately, test, commit.

## End-to-end test from a fresh fork

This is the same journey an attendee takes; do it with a throwaway
GitHub account if you want the full first-timer experience.

1. Fork github.com/hfscdogg/integrateuworkshops to a test account.
2. Follow README Steps 1-4 exactly as written, using a real Anthropic
   key (with credit) and a real Resend key for an inbox you control.
3. Confirm: Actions tab required the "enable workflows" click; the run
   goes green in under ~2 minutes; the log shows all four steps and the
   brief text; the email lands (check spam).
4. Break it on purpose, twice, to confirm the error messages hold up:
   delete the ANTHROPIC_API_KEY secret and run (expect the exact
   "wasn't found" message); set a garbage feed URL and run (expect the
   per-feed WARNING and a successful brief from the other two feeds).

For session 02, from the same fork:

5. Follow `session-02-permit-miner/README.md` Steps 1-4. Same two
   secrets, so only config.yml and prompt.txt change. Confirm the run
   goes green, the log prints "N of M permit(s) survived your filter"
   with N > 0, and the call list email lands.
6. Break it on purpose, twice: set `minimum_job_value` to 99999999 (expect
   the "Every permit was filtered out" message with the four numbered
   fixes, NOT a crash); set one dataset id to garbage (expect the
   per-source "answered 'not found'" WARNING and a successful call list
   from the remaining sources).

## Pre-class health checklist (morning of)

Run this before people arrive; it takes about ten minutes.

- [ ] Verify the three default feeds are alive: open each URL from
      config.yml in a browser and confirm raw XML with recent dates.
      (nahbnow.com/feed, constructiondive.com/feeds/news,
      housingwire.com/feed). If one is dead, replace it in config.yml
      and push BEFORE anyone forks.
- [ ] Verify the three default session 02 permit datasets are alive and
      still returning recent rows. Open each in a browser:
      data.cityofchicago.org/resource/ydr8-5enu.json?$limit=1
      data.austintexas.gov/resource/3syk-w9eu.json?$limit=1
      data.lacity.org/resource/nbyu-2ha9.json?$limit=1
      You want a JSON record back with a recent issue date. Open-data
      portals retire and renumber datasets without warning, and a dead
      default is the fastest way to lose the room. If one is dead, find
      the city's current permit dataset, replace the block in
      `session-02-permit-miner/config.yml`, and push BEFORE anyone forks.
- [ ] Trigger Run workflow on BOTH workflows on your own fork; confirm
      green runs + both emails delivered end to end. This also confirms
      the pinned model id is still live and the Anthropic API is up.
- [ ] Confirm the Anthropic console and resend.com are reachable and
      their signup flows haven't changed since the prep video.
- [ ] Skim the Actions log output on the test run: the four numbered
      steps should read cleanly on a projector.
- [ ] Have one spare Anthropic key with credit and one spare Resend key
      ready for attendees whose pre-flight failed.

## Things that bite

- Secrets do NOT copy into forks; everyone must add both secrets to
  their own fork. This is the number one support question.
- Workflows are disabled on new forks until the attendee clicks enable
  on the Actions tab. README Step 4 and Troubleshooting both cover it;
  say it out loud anyway.
- Resend's free tier only delivers to the account owner's address. If
  someone insists on a different recipient, they need to verify a
  domain in Resend; that's out of scope for the hour.
- The cron fires at 11:00 UTC. During EDT that's 7 AM; after the
  November time change it becomes 6 AM Eastern.

Session 02 specifically:

- Session 02 has NO schedule: it is Run-workflow-only, and its README
  says so plainly. The commented-out weekly cron in
  `.github/workflows/permits.yml` is there for attendees who want it.
- Both workflows live in the SAME `.github/workflows/` folder while
  session 02's code sits in a subfolder. That's why `permits.yml` sets
  `working-directory: session-02-permit-miner`. If you ever move the
  session folder, that line moves with it.
- Open-data portals name their columns differently in every city, so
  `permits.py` guesses from a list of known column names
  (`FIELD_GUESSES`). A city that calls its value column something
  exotic will simply show no dollar figure, and every permit gets
  filtered out unless `keep_permits_without_value` is true. That's the
  single most likely live failure; the error message walks them through
  it, but know the answer cold.
- Attendees in small/rural counties may find their city has no portal
  at all. That is a real and useful finding, not a failure: the README
  tells them to run the defaults and watch the logic. Have a line ready
  for it, because it WILL come up.
- Keyword matching is word-aware on purpose (`mentions()` in
  `permits.py`). Plain substring matching let "shed" fire on "finished
  basement" and threw away the best permit on the list. If you extend
  the keyword lists, keep them lowercase and let the matcher handle
  plurals and -ing endings.
