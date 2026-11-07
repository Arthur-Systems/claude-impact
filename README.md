# ClearPath — AI-powered permit navigator

Lane 2 team workspace for Claude Impact Lab: UCI × SoCal Affordable Housing.

Help housing teams manage multiple development projects, understand permit
requirements, prepare documents, and track the steps toward approval. Affordable
housing is the goal; Irvine ADU is the first populated rule dataset.

**Team:** To be confirmed
**Members:** To be confirmed
**Lane:** 2 — Clear it
**Built at:** Claude Impact Lab: UCI × SoCal Affordable Housing, November 7, 2026

## Repository setup

This repository contains the official **Lane 2: Clear it** starter materials:
the lane guide, source list, Orange County city list, timeline, and sample
scenarios. Shared event guides and the license are included. The specific
backend design supports a **portfolio of housing projects**, using Python/FastAPI
and PostgreSQL with pgvector. **Irvine + ADU** is the first curated rule profile;
other housing types can be saved as drafts while their requirements are sourced.
Application implementation awaits design approval.

## Backend design

The first slice covers dataset ingestion, permit lookup, and separate project
checklists/timelines, with a portfolio API for listing and filtering projects.
Frontend development, Claude chat, user document uploads/OCR, and vector search
follow later.

Read the [ClearPath backend design](SPEC.md)
for the proposed data model, API contracts, source verification, failure behavior,
and acceptance checks. Its status is **proposed**, pending review before coding.

The [backend implementation plan](docs/superpowers/plans/2026-11-07-clearpath-backend.md)
breaks the work into six tested tasks. Confirmed order: **Irvine ADU first,
affordable multifamily rules next**, with multiple projects supported from the start.

## Get the repository

```sh
git clone https://github.com/Arthur-Systems/claude-impact.git
cd claude-impact
```

Accept your collaborator invitation before cloning while the repository is
private. See [CONTRIBUTING.md](CONTRIBUTING.md) for the team workflow.

- [Lane 2: Clear it](lanes/2-clear-it/README.md)
- [Lane 2 data sources](lanes/2-clear-it/data/DATA-SOURCES.md)
- [Orange County cities](lanes/2-clear-it/data/oc-cities.json)
- [Timeline](lanes/2-clear-it/data/timeline.json) and [sample scenarios](lanes/2-clear-it/scenarios.json)
- [Getting started](docs/getting-started.md)
- [Challenge background](docs/background.md)
- [Judging](docs/judging.md) and [submission checklist](docs/submission.md)

The repository is currently private. The event requires it to be public by
submission time; the owner must authorize that visibility change separately.
Fill in the project sections below as the team builds.

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

Backend A now runs locally with FastAPI, PostgreSQL 17 + pgvector, Alembic
migrations, API-key protection, request IDs, and sanitized error responses. It
imports a city registry and versioned manifests, stores sources and citations,
and publishes reviewed drafts while retiring the previous release in the same
scope. Synthetic seeding is repeatable. Two real PostgreSQL publishing connections
are tested for serialization and a single active release.

The database includes project, checklist, event, and milestone tables for teammate
work. This Backend A slice does not expose project, portfolio, permit lookup,
location, or timeline APIs. The [backend teammate guide](backend/README.md) lists
commands and extension interfaces. Today's approved scope is the
[Backend A design](docs/superpowers/specs/2026-11-07-backend-a-platform-ingestion-design.md).

Lane 2 source materials and the [ADU demo packet builder](clear_path_checklist_build/README.md)
remain in the repository. That packet is a software-testing sample, not an
official city form or an imported rule dataset.

**Demo video:** Not recorded yet.
**Live demo:** Not deployed yet.

## How Claude is used

Planned: Claude can explain retrieved source material and help answer permitting
questions in a later slice. The first backend's checklists and timeline state
must work without an AI API key. Record actual Claude contributions here as the
team builds.

## Try it

Install Docker with Compose and [uv](https://docs.astral.sh/uv/), then start Docker.
From the repository root:

```sh
cp .env.example .env
# Edit .env: choose a local CLEARPATH_API_KEY and keep CLEARPATH_MODE=synthetic.
export COMPOSE_PROJECT_NAME=claude-impact
make backend-up
make backend-migrate
make seed-demo
make run
```

Open `http://127.0.0.1:8000/docs`. Health endpoints need no key;
`/api/v1/_ping` needs the `X-API-Key` header. Keep the key and `.env` out of git.
The synthetic dataset demonstrates ingestion and publication, not city guidance.

```sh
make test-backend TEST_DB=clearpath_test_myname
make smoke
# After reviewing curated source passages, attempt public import/publication:
make seed-irvine
```

`make smoke` uses a throwaway key and temporary API on `127.0.0.1:8765`, verifies
live/ready and ping authentication, then stops only its own API process. It leaves
PostgreSQL running and is safe to repeat. If that port is occupied, select a free
port with `make smoke SMOKE_PORT=18765`. `seed-irvine` stops on validation errors
or cited passages that still need review. See [backend/README.md](backend/README.md)
for environment variables, CLI commands, and teammate ownership rules.

## Sources and assumptions

| Item | Source or assumption | Date checked |
|---|---|---|
| Irvine ADU submittal requirements and next steps | City of Irvine, [Project: Constructing an Accessory Dwelling Unit (ADU)](https://cityofirvine.gov/building-permits-and-inspections/project-constructing-accessory-dwelling-unit-adu) (full text read) | 2026-11-07 |
| Completeness review, approx. 2 business days | City service target, same ADU page ("Next Steps"). Not an approval forecast | 2026-11-07 |
| Plan check fee at submittal; permit fees at issuance | City of Irvine, [Fee Schedule](https://cityofirvine.gov/node/4706). No fee amounts entered | 2026-11-07 |
| Development standards (setbacks, size limits, parking) | City of Irvine Form 67-01, [Pre-Approved ADU Development Standards Checklist](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35890-67-01.pdf). Cites old Gov. Code 65852.2 (flagged as stale) | 2026-11-07 |
| Application package forms | City of Irvine [ADU application package](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-34716-adu-application-package_updated-2025.pdf). Extracted text partly garbled: needs_review | 2026-11-07 |
| Hold Harmless Affidavit (pre-approved plans) | City of Irvine [Form 67-02](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35928-67-02.pdf) (title only read). Scope conflicts with ADU page; not entered as a requirement | 2026-11-07 |
| Pre-approved plan list | City of Irvine [Pre-Approved ADU Plans Program](https://cityofirvine.gov/building-permits-and-inspections/pre-approved-adu-plans-program): list says "Coming soon". No plan catalog seeded | 2026-11-07 |
| 15-business-day completeness, 60-day decision, renumbering to Gov. Code 66310-66342 | California HCD, [ADU Handbook (March 2026)](https://www.hcd.ca.gov/sites/default/files/docs/policy-and-research/ADU-Handbook-Update.pdf), pp. 11, 13, 34-35. Excerpts need hand-check | 2026-11-07 |
| Gov. Code § 66317 statute text | [leginfo](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=66317): **blocked**, not verified. No legal due dates are calculated | 2026-11-07 |
| AB 2234 post-entitlement review periods | City of Irvine, [Building Permit Requirements Under AB 2234](https://cityofirvine.gov/community-development/building-permit-requirements-under-assembly-bill-ab-2234) | 2026-11-07 |
| Milestone durations | None. All null; the tool shows "no estimate". Any future numbers will be labeled ASSUMPTION | n/a |
| Demo packet and example applications | Synthetic test data (fictional names, addresses, APNs). Not official forms | n/a |

Label any assumed numbers as ASSUMPTION here and in the tool.


## What is real and what is mocked

| Part | Status |
|---|---|
| FastAPI foundation, migrations, PostgreSQL storage | Working locally. Health/readiness, protected probes, stable errors, and request IDs are tested. |
| Manifest validation, registry import, release publication | Working locally with real PostgreSQL. Imports are immutable and repeat imports reuse releases; publication checks cited-passage review status. |
| Synthetic demo | Working. Test sources and timing ranges are synthetic; timing values are labeled ASSUMPTION. They are not permitting facts. |
| Curated Irvine source bundle | Present for curation. Import and public publication depend on schema validity and review of every cited passage. No claim of verified approval eligibility. |
| Project, checklist, timeline, and portfolio functionality | Tables exist. Backend A does not implement these HTTP APIs or claim a complete user workflow. |
| Location, permit lookup, source and jurisdiction HTTP routes | Not built in Backend A. These routes belong to Person 4's workstream. |
| `data fetch` with allowlist, rate limiting, and IP checks | Not built. Backend A imports local curated manifests and makes no source-network requests. |
| `data activate` rollback | Not built. Retired releases cannot be republished through the draft-only service; changed content requires a new import. |
| Concurrent publish verification | Implemented beyond the original deferral: two real publishing connections serialize behind the jurisdiction lock and leave one active release. |
| Separate Compose database profiles | Not built. Replaced by release `kind` and `CLEARPATH_MODE` filtering in one database. |
| Source-file hash verification | Not built. Source SHA-256 metadata is optional; excerpt hashes are computed during import. |
| Fully relational associations for every reference | Not built. Passage citations use `citation_links`; other references remain import-validated JSONB. |
| Immutable Compose image digest and backend CI workflow | Not built. The DB uses the `pgvector/pgvector:pg17` tag. |
| Automatic personal-data detection in imports | Not built. Content review is manual, and real personal information must not be entered. |
| Configurable manifest roots | Test-only `allowed_roots` hook exists. The CLI always uses the fixed `backend/data/` and `backend/tests/fixtures/` roots. |
| Chat, embeddings/vector search, and user uploads/OCR | Not built. Installing pgvector does not implement vector search. |

## Where it gets things wrong

What we saw it miss, and what we would not trust it with yet. Where the answer is "unknown", say so.

## Next steps

What it would take for a nonprofit or city to use this next month. What we would do with one more
week.

## Data and privacy

Use only public or provided data. Do not add personal information about real
tenants, buyers, or residents. The prototype must not file applications or
contact any city or person. Document the app's actual data handling here when
it is implemented.

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
