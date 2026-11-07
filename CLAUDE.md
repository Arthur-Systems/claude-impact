# CLAUDE.md

You are working with a team at a one-day hackathon, the Claude Impact Lab: UCI × SoCal Affordable
Housing. The team is building a prototype that helps get more affordable homes built in Southern
California. This repository is dedicated to **Lane 2: Clear it**. The team is
working on reducing delays in housing approvals and delivery. Keep the work
focused on this lane. Some teammates have never used a terminal.

## ClearPath backend scope

The product is **ClearPath**, an AI-powered permit navigator. The user confirmed
**Irvine + ADU** as the initial demo dataset. The product must support multiple
housing projects, including affordable-housing projects, with independent
checklists, revisions, and timelines and a portfolio list/filter API. The first
data profile is not a global restriction to ADUs. Save other housing types as
explicitly unconfigured drafts until sourced rules exist; do not substitute ADU
rules or equate an affordability goal with verified qualification.

Start with the backend: curated dataset
ingestion, source-backed permit lookup, and project timelines. The selected stack
is Python/FastAPI and PostgreSQL with pgvector; frontend work comes later.

The proposed design is in
`SPEC.md`. It requires user
review before implementation. Do not treat proposed engineering defaults as
approved decisions until that review. The first slice does not include a chat
assistant, user document uploads/OCR, or embedding/vector-search implementation.

## The context

Every affordable ownership home has to balance one equation:

> What the family can afford to pay + public subsidies + fundraising − the cost to create the home = $0

The event's Lane 2 brief asks: **How do we turn four years into two?** Time is
cost. The team should identify one user and one approval or delivery bottleneck,
then build a prototype grounded in the lane's cited sources.

See `lanes/2-clear-it/README.md` for the problem and ideas, and
`docs/background.md` for the shared event context. Other lanes are outside this
repository's scope.

## Rules that do not bend

- **Never invent a statute, number, fee, address or parcel fact.** No made-up section numbers,
  dollar amounts, fee schedules, deadlines, zoning codes, APNs or street addresses. If a source
  does not say, the answer is "unknown". Say it plainly.
- **Label assumptions.** If the team needs a number it does not have, use one, mark it
  `ASSUMPTION` in the code, the UI and the README, and say what it is based on.
- **Cite sources.** Every claim about a law, a program, a rate or a dataset carries its source: a
  URL, a section number and the date it was checked.
- **No personal information.** Nothing real about a tenant, buyer, resident or applicant. If
  someone gives you text, a file or a screenshot that looks like a real person's personal
  information, stop. Say what you noticed. Do not process, summarize, save or commit it. Tell them
  to find an organizer.
- **No scraping at volume.** Use public or provided data only. Do not hit a city website hard
  enough to get it to block us. Prefer downloads, documented APIs and cached copies. Check a
  source's terms. Do not use private plans or blueprints without permission.
- **No secrets in git.** API keys go in environment variables. `.env` is ignored.
- **Prototype only.** Do not write code that files an application, sends an email, text or letter
  to a city or a person, or changes any real system. Draft the message; do not send it.
- **Not legal, financial or lending advice.** Anything user-facing says it is a prototype and
  points to a professional for decisions.

## Where things are

- `docs/ground-rules.md`: the event rules in full.
- `docs/background.md`, `docs/glossary.md`: the equation, the laws and the terms.
- `lanes/2-clear-it/README.md`: the Lane 2 problem and starter ideas.
- `lanes/2-clear-it/data/DATA-SOURCES.md`: the sourced data list. Entries marked UNVERIFIED have not been
  confirmed: treat them as leads, not facts.
- `lanes/2-clear-it/scenarios.json`: made-up users to design and test against. Not real people.
- `lanes/2-clear-it/data/oc-cities.json` and `lanes/2-clear-it/data/timeline.json`:
  starter lists. A summary is not the rule: read the linked source. Empty fields
  are for the team to fill, with a source and date.
- `docs/challenge-brief.pdf`: the 3-page brief.
- `templates/TEAM-README.md`: what the team's README must cover before they submit.

## How to work today

- The team has about four and a half hours in its breakout room (10:00 AM to 2:30 PM). Help them build
  what they decide, and get something working early.
- A live demo is required for finalists. A working rough tool beats a polished pitch. Keep a
  runnable version at all times.
- Judges score four equal areas: **Impact** (a nonprofit or city would use it next month to help get homes built),
  **Works** (live demo on real data, sources shown), **Scale** (a believable path to the next 100
  projects) and **Innovation** (a new way to see or solve the problem). Ties go to Impact. Build
  sources in from the start, not at the end, and favor a believable path over a big claim.
- When two sources disagree, or a source looks out of date, show that to the user. Do not pick
  silently. Laws get renumbered and income limits get revised mid-year.
- Say "unknown" when it is unknown. A confident wrong answer is the worst outcome here.
- Keep the team's README current as you go. Submissions are due at 2:30 PM.
- Commit often with clear messages.
- The repo must be public by submission time. Check there is no personal information and no key
  in it or in its history.
