# ClearPath: cited permit checklists and timelines for housing projects

> For a nonprofit project manager or first-time ADU builder in Orange County: ClearPath turns a city's scattered ADU guidance into one checklist and approval timeline per project, with every requirement linked to the exact source passage, and says "unknown" instead of guessing.

**Team:** ClearPath
**Members:** Arthur, Pranav, Miguel, Youting, John
**Lane:** 2: Clear it
**Built at:** Claude Impact Lab: UCI x SoCal Affordable Housing, November 7, 2026

Irvine detached ADUs are the first reviewed rule set. Other housing types can be saved as draft projects marked "rule coverage unavailable" until their rules are sourced and reviewed.

## Get the repository

```sh
git clone https://github.com/Arthur-Systems/claude-impact.git
cd claude-impact
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the team workflow.

- [Lane 2: Clear it](lanes/2-clear-it/README.md)
- [Lane 2 data sources](lanes/2-clear-it/data/DATA-SOURCES.md)
- [Orange County cities](lanes/2-clear-it/data/oc-cities.json)
- [Timeline](lanes/2-clear-it/data/timeline.json) and [sample scenarios](lanes/2-clear-it/scenarios.json)
- [Getting started](docs/getting-started.md)
- [Challenge background](docs/background.md)
- [Judging](docs/judging.md) and [submission checklist](docs/submission.md)


## The real user

A nonprofit housing project manager or small builder managing several housing
projects needs to know which forms and steps apply to each, what is missing,
and what happens next. A first-time Irvine ADU applicant is the initial demo case.

**Before:** piece together municipal pages, forms, and state guidance across
several projects.
**After:** follow each project's sourced checklist and milestones, with unknown
requirements, unsupported rule coverage, and timeline assumptions shown explicitly.

An affordability goal is a declared project intention. The prototype does not
certify affordability, funding eligibility, or homes built.

## What we built
- **Reviewed Irvine ADU dataset** (Person 2): 9 public sources, 29 hand-checked excerpts, 10 requirements, 6 approval milestones (each marked city or applicant), and 4 recorded source conflicts, in `backend/data/irvine_adu/manifest.json`.
- **Permit lookup** (Person 4): given a location and project facts, returns each requirement as applies, needs information, or not applicable, with the source title, URL, excerpt and date checked. Missing facts stay unknown, never false.
- **Projects and timeline** (Person 5): save several projects, activate one against the published rules, track documents and milestones in order, and see progress, next actions and bottlenecks.
- **Platform and import** (Person 3): FastAPI, PostgreSQL 17, migrations, API-key auth, one error format, and an import command that validates every citation and refuses to publish unreviewed evidence.
- **Frontend** (Person 1): Next.js app in `clearpath/` with Overview, Documents, Navigator, Search, Timeline and Ask the City tabs. The Documents and Timeline tabs show live Irvine data from the API with source chips (title, link, excerpt, date checked) and fall back to labeled demo data when the backend is off.

**Demo video:** [link or "uploaded on the hub"]
**Live demo:** run locally, see Try it.

## How Claude is used

- **Building it:** the backend platform, importer and integration were written by Claude Opus coding agents run from Hermes (earlier foundation tasks also used a GPT-based agent), each change re-tested by a separate reviewer agent on its own database before merging. Teammates used AI assistants for their own parts; each person reviewed and owns their code.
- **Data:** a teammate read every city and state source and hand-checked every excerpt. No rule ships without a cited, reviewed passage.
- **At runtime:** the checklist, citations and timeline do not call an AI model, so every answer traces to a source. The Navigator tab shows labeled demo answers; it is not connected to a model yet.

## Try it
Prerequisites: Docker with Compose, [uv](https://docs.astral.sh/uv/), Node 18.17+.

Backend with the reviewed Irvine data:

```sh
export COMPOSE_PROJECT_NAME=claude-impact
make backend-up backend-migrate seed-cities
cd backend
CLEARPATH_MODE=public uv run clearpath data import --manifest data/irvine_adu/manifest.json
CLEARPATH_MODE=public uv run clearpath data publish --release <release_id printed above> --reviewed
cd ..
CLEARPATH_MODE=public CLEARPATH_API_KEY=change-me CLEARPATH_CORS_ORIGINS=http://localhost:3000 make run
```

API docs: `http://127.0.0.1:8000/docs`. Every `/api/v1` call needs the `X-API-Key` header.

Frontend:

```sh
cd clearpath
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000, NEXT_PUBLIC_API_KEY=change-me
npm install
npm run dev                         # http://localhost:3000
```

Checks: `make test-backend TEST_DB=clearpath_test_yourname` (800+ tests) and `make smoke SMOKE_PORT=8799`. Synthetic test data instead of Irvine: `make seed-demo` with `CLEARPATH_MODE=synthetic`. More detail: [backend/README.md](backend/README.md).

## Sources and assumptions

| Item | Source or assumption | Date checked |
|---|---|---|
| Irvine ADU submittal requirements and next steps | City of Irvine, [Project: Constructing an Accessory Dwelling Unit (ADU)](https://cityofirvine.gov/building-permits-and-inspections/project-constructing-accessory-dwelling-unit-adu) (full text read) | 2026-11-07 |
| Completeness review, approx. 2 business days | City service target, same ADU page ("Next Steps"). Not an approval forecast | 2026-11-07 |
| Plan check fee at submittal; permit fees at issuance | City of Irvine, [Fee Schedule](https://cityofirvine.gov/node/4706). No fee amounts entered | 2026-11-07 |
| Development standards (setbacks, size limits, parking) | City of Irvine Form 67-01, [Pre-Approved ADU Development Standards Checklist](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35890-67-01.pdf). Cites old Gov. Code 65852.2 (flagged as stale) | 2026-11-07 |
| Application package forms | City of Irvine [ADU application package](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-34716-adu-application-package_updated-2025.pdf). Extracted text partly garbled; excerpts hand-checked against the PDF | 2026-11-07 |
| Hold Harmless Affidavit (pre-approved plans) | City of Irvine [Form 67-02](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35928-67-02.pdf) (title only read). Scope conflicts with ADU page; not entered as a requirement | 2026-11-07 |
| Pre-approved plan list | City of Irvine [Pre-Approved ADU Plans Program](https://cityofirvine.gov/building-permits-and-inspections/pre-approved-adu-plans-program): list says "Coming soon". No plan catalog seeded | 2026-11-07 |
| 15-business-day completeness, 60-day decision, renumbering to Gov. Code 66310-66342 | California HCD, [ADU Handbook (March 2026)](https://www.hcd.ca.gov/sites/default/files/docs/policy-and-research/ADU-Handbook-Update.pdf), pp. 11, 13, 34-35. Excerpts hand-checked | 2026-11-07 |
| Gov. Code § 66317 statute text | [leginfo](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=66317): **blocked**, not verified. No legal due dates are calculated | 2026-11-07 |
| AB 2234 post-entitlement review periods | City of Irvine, [Building Permit Requirements Under AB 2234](https://cityofirvine.gov/community-development/building-permit-requirements-under-assembly-bill-ab-2234) | 2026-11-07 |
| Milestone durations | None. All null; the tool shows "no estimate". Any future numbers will be labeled ASSUMPTION | n/a |
| Demo packet and example applications | Synthetic test data (fictional names, addresses, APNs). Not official forms | n/a |

Label any assumed numbers as ASSUMPTION here and in the tool.


## What is real and what is mocked
| Part | Status |
|---|---|
| Irvine ADU requirements, citations, conflicts | Working. Reviewed public sources, served from the database |
| Permit lookup (applies / needs information / not applicable) | Working over the API |
| Projects, checklist status, milestone order, timeline | Working over the API |
| Frontend Documents checklist and Timeline | Working against the live API; a banner says whether the page shows live or demo data |
| Frontend document upload matching | Demo filename-only PDF/image/ZIP matching, no OCR or content validation. Live receipt status persists on the shared Documents/Timeline API project; API failures are labeled browser-only. Received is not city acceptance and does not resolve Unknown source conflicts. Fictional staged ZIPs are linked in Documents |
| Navigator answers | Mocked: labeled demo answers, no model call |
| Finish-date forecast | Not available: no reviewed durations, so the tool shows none |
| Legal due dates | Not calculated: statute text for Gov. Code 66317 could not be opened |
| Parcel eligibility (zoning, lot size, easements) | Not checked. Selected-area lookups say "property not verified" |
| Other cities and housing types | Not covered yet. Saved as drafts with "rule coverage unavailable" |
| Source refresh, release rollback, CI | Not built |

## Where it gets things wrong
- It knows only what was read from Irvine's public pages on November 7, 2026. If the city changes a form, the checklist is stale until someone re-checks the source and publishes a new release.
- Floor area does not change the checklist yet: none of the reviewed rules depend on it.
- Where sources disagree (for example the order of fee payment and plan review, or whether the Hold Harmless Affidavit applies), it shows the conflict and does not pick a side.
- It does not check a real parcel, and it does not calculate legal deadlines.
- Prototype. Not legal advice. Confirm with the City of Irvine or a professional.

## Next steps
- **Next month:** a nonprofit can use the Irvine ADU rules as they are; a city permit tech can use the cited view to check a form against state guidance.
- **Next 100 projects:** projects are cheap once a city and housing type has a reviewed rule file. Each new city or type is one manifest (sources, excerpts, rules, steps) checked by a person and published with one command; no code change.
- **With one more week:** SB 9 two-unit and lot-split rules for Irvine, two more OC cities to compare (scenario C02), HCD Annual Progress Report data for real approval times with its limits stated, and a Navigator that answers only from cited passages.

## Data and privacy
This project uses only public sources. It stores no personal information about tenants, buyers, residents or applicants; projects have a label, not an owner. It does not file applications or contact any city or person: "Ask the City" opens a draft email for the user to send.

## License

Code: MIT. Event challenge materials: CC0 1.0. Third-party sources retain their
own terms. See [LICENSE](LICENSE).

## Starter provenance

Lane 2 and shared event materials were copied from
[travcjohnson/claude-impact-lab-uci](https://github.com/travcjohnson/claude-impact-lab-uci)
at commit [`45a05a5`](https://github.com/travcjohnson/claude-impact-lab-uci/commit/45a05a5c65ba5e3ae7b15e991c8fedf3a29d3ebf).
The team README outline is in [templates/TEAM-README.md](templates/TEAM-README.md).
These are imported event materials; check the [live event hub](https://claudesocal.com/uci-impact-lab)
for current schedules and announcements.
