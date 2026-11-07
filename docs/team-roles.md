# ClearPath team roles

Who builds what for the ClearPath Irvine ADU prototype, and how the pieces fit
together by the 2:30 PM submission.

- **Product spec:** [ClearPath backend design](superpowers/specs/2026-11-07-clearpath-backend-design.md)
  (cited below as "spec §N"). Its status is still *proposed*: confirm it as a team before coding.
- **Demo user:** a first-time homeowner adding a detached ADU in Irvine (scenario C01 in
  [`lanes/2-clear-it/scenarios.json`](../lanes/2-clear-it/scenarios.json)).
- **Team size:** 5. Replace "Person 1–5" with names once roles are picked.

| Person | Role | Owns (spec) | Main folder |
|---|---|---|---|
| Person 1 | Frontend | UI on top of spec §9 | `frontend/` |
| Person 2 | Data and regulations researcher | Content for spec §3, §6, §8 | `backend/data/irvine_adu/` |
| Person 3 | Backend A: platform, database, data import | spec §4, §5, §6, §10 | `backend/src/clearpath/ingestion/`, `migrations/`, root config |
| Person 4 | Backend B: location and permit lookup | spec §7, lookup routes in §9 | `backend/src/clearpath/locations/`, `permits/` |
| Person 5 | Backend C: projects and timeline | spec §8, project routes in §9 | `backend/src/clearpath/projects/`, `timelines/` |

---

## Schedule and checkpoints

Times are targets for today. Every checkpoint should leave a version that runs.

| Time | Checkpoint | Done means |
|---|---|---|
| 11:15 | **Kickoff** | Roles confirmed. Spec approved or trimmed. The two contracts below are agreed. |
| 11:45 | **Contracts frozen** | Manifest JSON shape (P2 ↔ P3/P4/P5) and API response examples (P1 ↔ P4/P5) are committed. |
| 12:30 | **Walking skeleton** | `docker compose up` works. Health check passes. One lookup returns fixture data. The frontend shows that data, mocked if needed. |
| 1:30 | **Integrated** | Real Irvine data is seeded. The frontend calls the live API end to end: lookup → create project → update checklist → timeline. |
| 2:00 | **Feature freeze** | Bug fixes only. README filled in. Demo video recorded. |
| 2:20 | **Final checks** | Repo public. No keys and no personal information in the repo or its history. Fresh-clone "Try it" steps work. |
| 2:30 | **Submit** | Form submitted on the event hub. |

**If behind at a checkpoint, cut in this order** (the first item goes first):
1. Live Irvine GIS address lookup. Keep "selected Irvine area" mode only (spec §7).
2. Release rollback (`data activate`) and concurrent-publish handling (spec §6).
3. Assumed finish-date forecast (spec §8). Keep progress, next actions and bottlenecks.
4. The event history route (`GET /projects/{id}/events`).
5. Full API-key and OpenAPI contract tests (spec §11, A12). Keep a basic key check.

Never cut: citations on every requirement, "needs information" for unknowns,
`ASSUMPTION` labels, and the prototype / not-legal-advice notice.

---

## The two contracts everyone depends on

### Contract 1: dataset manifest (Person 2 → Persons 3, 4, 5)

Person 3 owns the final schema. Person 2 fills it in. Agree on the shape by 11:45 so
Person 2 can enter data while the importer is being built. Below is a **draft shape for
discussion**. Every value shown is a placeholder, not a fact.

```json
{
  "schema_version": 1,
  "jurisdiction": "irvine-ca",
  "project_type": "adu",
  "subtype": "detached_adu_existing_dwelling",
  "sources": [
    {
      "key": "IRV-ADU",
      "url": "<official URL>",
      "title": "<page or PDF title>",
      "publisher": "City of Irvine",
      "authority_type": "city_guidance",
      "checked_at": "2026-11-07",
      "sha256": "<computed by fetch command>",
      "verification_depth": "full_text_read | title_only | blocked",
      "terms_note": "<reuse terms or unknown>"
    }
  ],
  "passages": [
    {
      "id": "<uuid>",
      "source_key": "IRV-ADU",
      "locator": "page 2 | #heading-anchor",
      "excerpt": "<exact text copied from the source>"
    }
  ],
  "pathways": [
    { "key": "irvine_adu_standard", "title": "<title>", "applies_if": { "eq": ["project_type", "adu"] }, "citations": ["<passage uuid>"] }
  ],
  "requirements": [
    {
      "key": "<slug>",
      "pathways": ["irvine_adu_standard"],
      "kind": "permit | document | review",
      "title": "<as named by the city>",
      "description": "<plain-language, no invented details>",
      "applies_if": { "all": [{ "eq": ["adu_form", "detached"] }] },
      "required_for_preparation": true,
      "citations": ["<passage uuid>"]
    }
  ],
  "milestones": [
    {
      "key": "application_preparation",
      "title": "<title>",
      "predecessors": [],
      "requirements": ["<requirement key>"],
      "published_clock": null,
      "assumed_days": { "min": null, "max": null, "label": "ASSUMPTION", "rationale": null },
      "citations": ["<passage uuid>"]
    }
  ],
  "conflicts": [
    { "rule_keys": ["<key>"], "sources": ["<key>", "<key>"], "summary": "<what disagrees>" }
  ]
}
```

Facts the rule engine accepts (spec §7): `project_type`, `adu_form`, `existing_dwelling`,
`floor_area_sqft`. Operators: `all`, `any`, `not`, `eq`, `in`, `lt`, `lte`, `gt`, `gte`.

### Contract 2: API responses (Persons 4, 5 → Person 1)

The routes are defined in spec §9. By 11:45, Persons 4 and 5 each commit **example JSON
responses** to `backend/tests/fixtures/api_examples/`, one file per route. Person 1 builds
against those files as mocks. When the real API returns something different, the example
files get updated first, then the code.

Example files needed:
`jurisdictions.json`, `locations_resolve_selected_area.json`,
`locations_resolve_ambiguous.json`, `permit_lookup_applies.json`,
`permit_lookup_needs_information.json`, `project_created.json`,
`requirement_patch.json`, `milestone_event_conflict_409.json`, `timeline.json`,
`error_envelope.json`.

---

## Person 1: Frontend

**Goal:** the live demo. A judge should see one user's journey, with sources and
unknowns on screen.

**Stack:** not set by the spec, so the team decides at kickoff. Suggestion: React + Vite +
TypeScript, or one plain HTML/JS page if speed matters more. Pin versions in
`package.json`.

**Screens:**
1. **Start / lookup:** pick "Irvine (selected area)" or enter a structured address (number,
   street name, street type, unit). Then answer the project facts: ADU form, existing
   dwelling yes/no, floor area (optional, may be left unknown).
2. **Results checklist:** candidate pathway; requirements grouped as *applies*,
   *needs information* (show which facts are missing) and *not applicable*. Every item
   gets a citation chip that opens the source title, URL, page/locator, excerpt and
   date checked.
3. **Warnings bar:** location status (`selected_area` = "property not verified"),
   source conflicts, stale or unreviewed sources, and "synthetic demo data" whenever
   demo mode is on.
4. **Project tracker:** create a project, mark documents `not_started / in_progress / ready`,
   and start/complete/reopen milestones. Show a 409 conflict as a readable message
   (e.g. "complete the earlier step first").
5. **Timeline view:** six milestones in dependency order, with progress %, document
   readiness (marked *provisional* when unknowns remain), next actions, bottleneck
   reasons, and a forecast range labeled **ASSUMPTION**, or "no estimate available".
6. **Footer on every page:** "Prototype. Not legal advice. Confirm with the City of Irvine
   or a professional."

**Rules:**
- Never display a number, fee, deadline or statute that did not come from the API.
- Display "unknown" as unknown. Don't hide it or default it.
- API key comes from an env var (`VITE_CLEARPATH_API_KEY` or similar), never hard-coded.
  Add the name to `.env.example`.

**Also owns:** screenshots for the README, and recording the demo video (30 s–2 min) with
the team at 2:00.

**Done when:** the full C01 journey runs against the live local API, and the same build
still works on mock files if the backend breaks.

---

## Person 2: Data and regulations researcher

**Goal:** the correct, cited content the backend serves. This role decides whether the
tool is trustworthy. A confident wrong answer is the worst outcome.

This role can be done mostly in a browser and a text editor. No terminal is needed:
files can be edited and committed on GitHub's web page.

**Tasks:**
1. **Read the Irvine sources** listed in spec §3: ADU construction guide, ADU application
   package, development standards checklist, hold harmless affidavit, pre-approved plan
   page. For each, record the exact URL, title, date checked, and how much was actually read
   (`full_text_read`, `title_only`, `blocked`).
2. **Extract requirements** for a *detached ADU on a lot with an existing dwelling*: every
   form, document, permit and review the city names. For each one: the city's own name
   for it, the page/heading where it appears, an exact copied excerpt, and the condition
   under which it applies, expressed in the four facts above. Mark
   anything that doesn't fit those facts as a gap. Don't stretch a rule to fit.
3. **Handle the garbled PDF text** (spec §3, §6). The application package extracts badly,
   so type a clean, checked excerpt with its page number. Mark anything not checked as
   `needs_review`.
4. **Check state guidance** in the HCD ADU Handbook (March 2026): which sections it cites
   for ADU approval, completeness and decision timing. Record what it says and where.
   If the statute text on leginfo can't be opened, record the gap. Don't fill it in.
5. **Flag conflicts and stale citations:** e.g. any Irvine document still citing old
   Gov Code 65852.2 numbers (renumbered to 66310–66342), or two sources that disagree.
   Each becomes a `conflicts` entry.
6. **Milestones:** confirm the six milestones in spec §8 (preparation, submission,
   completeness review, plan review, fee/payment readiness, permit issuance) and their
   order against what the city source actually says. Record any published city service
   target with its exact wording and scope.
7. **Assumed durations (optional):** if the team wants a forecast, propose min/max day
   ranges per milestone, each marked `ASSUMPTION` with a one-line basis. Leaving them
   null is fine; the tool will say "no estimate".
8. **Fill in** Irvine's entry in [`lanes/2-clear-it/data/oc-cities.json`](../lanes/2-clear-it/data/oc-cities.json)
   (permit page, ADU checklist, fee schedule URLs + `checked` date), and the README
   "Sources and assumptions" table.

**Rules:**
- Never invent a section number, fee, deadline, form name or address. If the source
  doesn't say, write "unknown".
- Organizer `VERIFIED` labels in `DATA-SOURCES.md` are leads, not proof. Re-check.
- Only blank public forms. No real applicant or resident information, ever. If you find
  any, stop and tell an organizer.
- Be gentle with city sites: open pages by hand, no bulk downloading.

**Handoff:** a first batch of 3–5 requirements by 12:15 so the backend can test with real
content. The full set by 1:15.

**Done when:** every requirement and milestone in the manifest has at least one checked
passage, and every gap or conflict is written down.

---

## Person 3: Backend A — platform, database, data import

**Goal:** the foundation the other two backend roles build on. **Unblock others first.**

**Tasks, in order:**
1. **Scaffold (by 11:45):** `backend/pyproject.toml` with pinned versions (Python 3.12,
   FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3, HTTPX, Shapely, pytest);
   `compose.yaml` with PostgreSQL 17 + pgvector (pinned image tag, bound to localhost);
   `Makefile`; `.env.example` with `CLEARPATH_API_KEY` and `DATABASE_URL`. Package
   layout `backend/src/clearpath/{api,ingestion,locations,permits,projects,timelines}/`
   with empty modules so Persons 4 and 5 can start in their own folders.
2. **Health + app shell:** FastAPI app, `/health/live`, `/health/ready`, `X-API-Key`
   check, the error envelope `{error: {code, message, details}, request_id}`, rejection of
   unknown fields.
3. **Migrations (spec §5):** Alembic with `CREATE EXTENSION vector`, then the tables.
   Order: `jurisdictions`, `source_snapshots`, `source_passages`, `dataset_releases`,
   `ingestion_runs`, `pathways`, `requirements`, `milestone_templates`, citation association
   tables. The project tables (`projects`, `project_requirements`, `project_milestones`,
   `project_events`) can be written by Person 5 in their own migration.
4. **Manifest schema:** Pydantic models for Contract 1; agree on it with Person 2 by 11:45.
5. **Import CLI (spec §6):** `clearpath data import --manifest PATH [--dry-run]` and
   `clearpath data publish --release UUID --reviewed`. Validate hashes, citations,
   predicates (shared validator with Person 4), and an acyclic milestone graph. Import in
   one transaction; importing the same manifest twice is a no-op. One active release per
   jurisdiction/subtype.
6. **Synthetic fixture bundle** at `backend/tests/fixtures/irvine_adu_synthetic/`, clearly
   labeled synthetic, so everyone can test before Person 2's real data lands.
7. **Make targets:** `backend-up`, `backend-migrate`, `seed-demo`, `seed-irvine`,
   `test-backend`.
8. **Later, if time:** `data fetch` (allowlisted hosts, 1 req/s, 10 s timeout, 10 MiB cap),
   `data activate` rollback, `GET /api/v1/sources/{id}`.

**Spec checks owned:** A1, A2, A3, A4.

**Done when:** a fresh clone runs `make backend-up backend-migrate seed-demo` and the health
check reports the dataset as available.

---

## Person 4: Backend B — location and permit lookup

**Goal:** "Given where and what, which requirements apply, and why?"

**Tasks, in order:**
1. **Predicate evaluator (spec §7):** pure Python, no `eval`, no dynamic SQL. Three-valued
   logic: true / false / unknown. `not unknown` = unknown. `all` = false if any operand is
   false, else unknown if any is unknown. `any` = true if any operand is true, else unknown
   if any is unknown. Missing facts never become false. Unit-test this first. Share the
   validator with Person 3's importer.
2. **Permit lookup service:** read the active release, evaluate pathways and requirements,
   return `applies / not_applicable / needs_information` plus missing fact keys, citations
   (URL, title, locator, snapshot hash, date checked), conflicts, and warnings.
3. **Location resolve, selected-area mode first:** `selected_area` returns an area-level,
   clearly qualified result. An unsupported area returns general links only, with no
   property-specific checklist.
4. **Routes:** `GET /api/v1/jurisdictions`, `POST /api/v1/locations/resolve`,
   `POST /api/v1/permit-lookups`. Commit example responses for Person 1 by 11:45.
5. **Coordinates mode:** point-in-polygon against the city boundary with Shapely. Offline
   tests use the synthetic polygon. Points on the boundary are `ambiguous`.
6. **Live address adapter (cut first if behind):** Irvine GIS address table 19 and building
   layer 1 (spec §7): exact normalized matching, escaped fixed query, at most 5 candidates,
   `outSR=4326`, 10 s timeout. Outage → typed 503 result, never synthetic data. Fetch only
   technical address fields, never owner or resident data.

**Spec checks owned:** A5, A6, A10 (display side).

**Done when:** the C01 facts with `selected_area` return a cited checklist, and leaving
`floor_area_sqft` blank produces `needs_information` wherever it matters.

---

## Person 5: Backend C — projects and timeline

**Goal:** "I've started. What's done, what's next, and what's holding me up?"

**Tasks, in order:**
1. **Project tables migration:** `projects`, `project_requirements`, `project_milestones`,
   `project_events` (spec §5). No applicant name, contact or uploads, ever.
2. **Create / read project:** `POST /api/v1/projects` re-runs Person 4's lookup on the
   server, pins the release, and requires a supported pathway (422 with missing keys
   otherwise). `GET /api/v1/projects/{id}`. Until Person 4's lookup is ready, call a stub
   that returns a fixture.
3. **Requirement status:** `PATCH .../requirements/{key}` with `expected_revision`. Lock the
   row, check the revision (409 if stale), write the audit event in the same transaction.
4. **Milestone state machine (spec §8 table):** `start`, `complete`, `reopen`; predecessors
   and required items must be satisfied; reopening needs dependents reopened first; no
   future timestamps; completion can't come before start. Everything else is a 409.
5. **Timeline calculation:** `GET .../timeline?as_of=YYYY-MM-DD`: progress
   (completed/total, one decimal place, null for an empty graph), document readiness with
   provisional unknown count, next actions in template order, bottleneck codes
   (`missing_information`, `missing_documents`, `awaiting_city`, `source_conflict`,
   `estimate_exceeded`). Commit `timeline.json` example for Person 1 by 11:45.
6. **Forecast (cut if behind):** assumed range via earliest-finish propagation through the
   milestone graph (max of parallel predecessors, not a sum). Any unknown required duration
   → null with `missing_stage_estimates`. Always labeled ASSUMPTION. Never a legal due date.
   Tests pass `as_of` explicitly and never use the wall clock.
7. **Events list (cut if behind):** `GET .../events`, cursor-paginated, default 50, max 100.

**Spec checks owned:** A7, A8, A9.

**Done when:** the demo script can create a project, get a 409 on a premature completion,
update a checklist item, and read a timeline showing progress and the next action.

---

## Shared responsibilities

| Task | Owner | Backup |
|---|---|---|
| Keep `README.md` current (user, what it does, Try it, sources, real vs mocked) | Person 2 | Person 3 |
| "Try it" commands tested on a fresh clone | Person 3 | Person 1 |
| Demo script (the C01 walkthrough judges will see) | Person 1 | Person 5 |
| Demo video | Person 1 | everyone |
| Final privacy and secrets check of repo and history | Person 3 | Person 2 |
| Submission form | Person 2 | anyone |

## How we work in git

- Pull before you start, and again after each break.
- One branch per person (`p1-frontend`, `p2-data`, `p3-platform`, `p4-lookup`,
  `p5-timeline`). Merge to `main` in small pieces, at least once per checkpoint.
- Stay inside your own folders (table at the top). Shared files (`pyproject.toml`,
  `compose.yaml`, `Makefile`, the `api` router list) are edited by Person 3. Ask them
  rather than editing directly.
- Commit messages say what changed, e.g. `lookup: three-valued predicate evaluator`.
- No `.env`, keys or personal information in any commit. `main` must always run.

## Definition of done for the team

- [ ] Live demo of the C01 journey on real, cited Irvine data
- [ ] Every requirement shows its source and date checked; unknowns say "unknown"
- [ ] Every assumed number labeled ASSUMPTION in the code, UI and README
- [ ] Prototype / not-legal-advice notice visible
- [ ] README follows `templates/TEAM-README.md`; repo public; no secrets or personal info
- [ ] Video uploaded and form submitted by 2:30 PM
