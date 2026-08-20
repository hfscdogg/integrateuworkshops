# Maintainer Notes (Henry)

Attendees never need this file. It covers keeping the workshop repo
healthy and the morning-of checklist.

## Updating the pinned Claude model

The model string lives in a `CLAUDE_MODEL` constant near the top of the
pipeline file, and there is now ONE PER SESSION. Both currently read
`claude-sonnet-5`; change them together:

- Session 01: `brief.py`
- Session 02: `session-02-permit-miner/permit_miner.py`

To update:

1. Check the current model list at docs.anthropic.com (Models page).
2. Change both constants to the new id.
3. Run the end-to-end tests below from a fresh fork before class.
4. Rough cost check: a session 01 run sends ~36 headlines (~4-6k input
   tokens) and gets back <1k output tokens. A session 02 run sends at
   most 25 permits (~2-4k input tokens) and gets back <2k, since Claude
   writes the postcard copy as well as the scores. Fifty attendees
   running each several times during class is still well under a dollar
   total on any current model, but confirm the new model's pricing
   hasn't changed that math.

Also pinned, and worth a glance once a quarter: the actions in EACH
workflow. Both use `actions/checkout@v4.2.2` and
`actions/setup-python@v5.3.0`; `permits.yml` additionally pins
`actions/upload-artifact@v4.4.3`. Session 02 adds `Pillow` to its
`requirements.txt` for the postcard rendering. Bump deliberately, test,
commit.

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

5. Follow `session-02-permit-miner/README.md`. Only `config.yml` and an
   uploaded logo change; the ANTHROPIC_API_KEY secret is already there
   from session 01. Confirm the run goes green, the log prints "N of M
   permit(s) survived your filter" with N > 0, and the
   **postcard-preview** artifact downloads with a front PNG, a back PNG,
   a PDF and scoreboard.txt in it.
6. Open the PNGs. Check the logo scaled sensibly and no text is cut off.
7. Break it on purpose, three times:
   - set `minimum_job_value` to 99999999. Expect a GREEN run, the
     "All N permit(s) were filtered out" note, and a
     NO-POSTCARD-THIS-RUN.txt in the artifact. A red X here is a bug.
   - set the dataset id to garbage. Expect a red run with the "says that
     dataset doesn't exist" message naming the id.
   - point `logo_path` at a file that isn't there. Expect a green run
     whose card prints the company name in the colour band instead.

## Sync test (do this before every session 02 class)

Session 01 attendees pick session 02 up with the Sync fork button, so
that path has to be clean:

1. Make a fork pinned at the session 01 commit, and commit an edit to
   the root `config.yml` and `prompt.txt` the way an attendee would.
2. Press Sync fork > Update branch on that fork.
3. Confirm: no conflict, their root config.yml and prompt.txt edits
   survive untouched, Morning Brief still appears and still runs green.

Session 02 only ADDS files (a new folder and a new workflow) and edits
`README.md` and `MAINTAINERS.md`, which attendees never touch. That is
what keeps the sync clean. If you ever need to move session 01's files
into a folder of their own, understand that it breaks this: every
existing fork gets a conflict, and their README instructions stop
matching what they see.

## Pre-class health checklist (morning of)

Run this before people arrive; it takes about ten minutes.

- [ ] Verify the three default feeds are alive: open each URL from
      config.yml in a browser and confirm raw XML with recent dates.
      (nahbnow.com/feed, constructiondive.com/feeds/news,
      housingwire.com/feed). If one is dead, replace it in config.yml
      and push BEFORE anyone forks.
- [ ] Verify the session 02 default permit dataset is alive and
      returning recent rows. Paste this in a browser:
      data.austintexas.gov/resource/3syk-w9eu.json?$limit=1
      You want a block of JSON back with a recent issued_date. Open-data
      portals retire and renumber datasets without warning, and a dead
      default is the fastest way to lose the room. Spot-check the
      alternates in `session-02-permit-miner/counties.md` the same way.
      If the default is dead, replace the permit_source block in
      `session-02-permit-miner/config.yml` and push BEFORE anyone forks.
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

- Session 02 has NO schedule and NO email. It is Run-workflow-only and
  the output is a downloadable artifact. Attendees who did session 01
  will wait for an inbox that never dings; say out loud that this one
  ends at the Actions page.
- The artifact lives at the BOTTOM of the run SUMMARY page, not in the
  log view they were just watching. This is the single most likely
  "where is it" moment of the hour. Show it on the projector.
- Both workflows share `.github/workflows/` while session 02's code sits
  in a subfolder, which is why `permits.yml` sets
  `working-directory: session-02-permit-miner` and the artifact path is
  repo-relative (`session-02-permit-miner/output/`). Those two disagree
  on purpose: `defaults.run` only applies to `run:` steps, not to the
  upload action's `path:`. If you move the folder, both lines move.
- An area with no permits, or a filter that rejects everything, exits
  GREEN with a note file, not red. That is deliberate: a quiet county is
  not a broken run, and a red X teaches the wrong lesson.
- Open-data portals name their columns differently everywhere, so
  `permit_miner.py` guesses from `FIELD_GUESSES`. An area that names its
  value column something exotic shows no dollar figure, and then the
  money line filters everything out. That is the most likely live
  failure; the fix is `keep_permits_without_value: true`. Know it cold.
- Attendees in small or rural counties may find their area has no portal
  at all. That is a real finding, not a failure. The README tells them
  to run the Austin default and watch the logic. Have a line ready,
  because it WILL come up.
- Claude is asked for JSON. If it answers in prose twice, the miner
  falls back to ranking by declared job value with generic postcard copy
  and says so loudly. The run still produces a card. If you see that
  warning on several forks at once, the model id is probably wrong.
- Keyword matching is word-aware (`mentions()`). Plain substring
  matching let "shed" fire on "finished basement" and threw away the
  best permit on the list. Company detection is whole-word for the same
  reason: "INC" was matching a homeowner named INCANDELA. If you extend
  either list, keep entries lowercase and let the matcher handle plurals
  and -ing endings.
- There is no live mail send anywhere in session 02, by design. The
  optional hook needs a LOB_API_KEY secret AND an exact typed phrase,
  and even then only prints a payload. If someone asks to really mail
  one, that is a conversation for after class, not a config change.
