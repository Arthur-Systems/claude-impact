# ClearPath — AI-powered permit navigator

Lane 2 team workspace for Claude Impact Lab: UCI × SoCal Affordable Housing.

Help an Irvine ADU applicant understand permit requirements, prepare documents,
and track the steps toward approval.

**Team:** To be confirmed
**Members:** To be confirmed
**Lane:** 2 — Clear it
**Built at:** Claude Impact Lab: UCI × SoCal Affordable Housing, November 7, 2026

## Repository setup

This repository contains the official **Lane 2: Clear it** starter materials:
the lane guide, source list, Orange County city list, timeline, and sample
scenarios. Shared event guides and the license are included. The specific
backend design is being specified for **Irvine + ADU**, using Python/FastAPI and
PostgreSQL with pgvector. Application implementation awaits design approval.

## Backend design

The first slice covers dataset ingestion, permit lookup, and project timelines.
Frontend development, Claude chat, user document uploads/OCR, and vector search
follow later.

Read the [ClearPath backend design](docs/superpowers/specs/2026-11-07-clearpath-backend-design.md)
for the proposed data model, API contracts, source verification, failure behavior,
and acceptance checks. Its status is **proposed**, pending review before coding.

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

A first-time applicant preparing an ADU project in Irvine needs to know which
forms and steps apply, what is missing, and what happens next.

**Before:** piece together municipal pages, forms, and state guidance.
**After:** follow a sourced checklist and track project milestones, with unknown
requirements and timeline assumptions shown explicitly.

## What we built

The repository currently contains Lane 2 source materials and the proposed
backend specification. No application code has been added yet.

**Demo video:** Not recorded yet.
**Live demo:** Not deployed yet.

## How Claude is used

Planned: Claude can explain retrieved source material and help answer permitting
questions in a later slice. The first backend's checklists and timeline state
must work without an AI API key. Record actual Claude contributions here as the
team builds.

## Try it

There is no runnable application yet. The clone commands above provide the event
materials. Add exact install and run commands, prerequisites, and environment
variable names here when application code is added. Keep keys out of the repo.

## Sources and assumptions

| Item | Source or assumption | Date checked |
|---|---|---|
| | law, dataset, program or ASSUMPTION | |

Label any assumed numbers as ASSUMPTION here and in the tool.

## What is real and what is mocked

| Part | Status |
|---|---|
| | working / partly working / mocked |

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
