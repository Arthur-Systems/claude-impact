# API example responses

These files are **example request/response pairs** for the ClearPath lookup routes
(SPEC.md §7 and §9): `GET /api/v1/jurisdictions`, `POST /api/v1/locations/resolve`,
`POST /api/v1/permit-lookups` and `GET /api/v1/sources/{source_key}`
(`sources_get.json`). They are mocks for the frontend (Person 1), not real data. Every
URL, title, excerpt, hash and form name is a placeholder in `<angle brackets>`, and
numbers such as `floor_area_sqft: 600` are arbitrary test inputs, not Irvine rules. Each
file holds `{"request", "status_code", "response"}`, and every response carries
`"example": true`, which the real API will not send. When the real API needs a different
shape, **update these files first, then the code**, and tell Person 1. Person 5 owns
the project and timeline examples.

Every permit lookup also has `sources_used`: each cited source exactly once, in the
order it is first cited, as `{source_key, title, url, publisher, checked_at,
verification_depth}`. It is `[]` when there is no checklist.

## Possible values

These lists match `backend/src/clearpath/permits/service.py` and
`backend/src/clearpath/locations/service.py`. A test checks that every value used in
these example files appears here.

**Permit lookup `status` (top level)**
- `checklist_ready`: every pathway and requirement has a definite answer.
- `needs_information`: at least one item is not definite (missing fact, source conflict,
  missing evidence or an unreadable rule), or several rule profiles match and
  `profile_key` is needed.
- `rule_coverage_unavailable`: no curated rules for this city and project type. Empty
  checklist. Rules for another housing type are never used instead.
- `location_unresolved`: the location is unresolved or ambiguous. No checklist.

A configured profile whose dataset can't be loaded is not a status. It is an HTTP 503
error with code `dataset_unavailable`.

**Pathway / requirement `status`**: `applies`, `not_applicable`, `needs_information`.
A missing fact never produces `not_applicable`.

**Pathway / requirement `status_reason`**
- `facts_met`: the rule is true for the given facts.
- `facts_not_met`: the rule is false for the given facts.
- `missing_facts`: the rule depends on facts not given (see `missing_fact_keys`).
- `source_conflict`: sources disagree about this item (see `conflict_ids`).
- `insufficient_evidence`: none of its citations could be matched to a source.
- `rule_invalid`: the dataset's rule for this item could not be read.

**Location `status`**: `selected_area`, `confirmed`, `ambiguous`, `unresolved`,
`outside_supported_area`.

**Location `status_reason`**: `null`, `multiple_candidates`, `unknown_jurisdiction`,
`mode_not_implemented`, `fixture_requires_synthetic_mode`, `no_rule_coverage`,
`synthetic_fixture`.

**Location `mode`**: `selected_area`, `point`, `address`, `fixture`. Only `selected_area`
is implemented. `point` and `address` return `unresolved` / `mode_not_implemented`.

**Warning `code`s** (each warning is `{code, message}`, sometimes with extra fields):
- `example_data`: only in these files.
- `synthetic_dataset`: the result comes from synthetic demo data.
- `selected_area_property_not_verified`: area-level result; no property was checked.
- `location_ambiguous`, `location_unresolved`, `location_mode_not_implemented`,
  `synthetic_location_fixture`: about the location.
- `no_rule_coverage`: the city is listed but has no curated rules.
- `rule_coverage_unavailable`: no rules for this project type in this city.
- `registry_not_coverage`: (jurisdictions list) being listed is not coverage.
- `profile_key_required`: several profiles match; extra field `profile_keys`.
- `draft_manifest_defaults`: draft dataset with defaults filled in; extra field `gaps`.
- `unreviewed_extraction`: cited text not yet checked by a person; extra field `source_keys`.
- `citation_unresolved`: a citation could not be matched to a source passage.
- `rule_invalid`: unreadable rules; extra field `rule_keys`.
- `statutory_clock_unverified`: state time limits not checked; no legal due date.
- `source_differs_across_releases`: (sources route) two active releases describe the
  same source differently; the first is shown.
- `test_only_unreviewed_release`: tests only. Unreviewed data was force-loaded as
  `reviewed_public`. The real API should never send this.

**Error `code`s** (HTTP status): `unauthorized` (401, missing or wrong `X-API-Key`),
`source_not_found` (404), `not_found` (404, unknown route; dev server),
`validation_error` (422, body failed the request model: unknown field or wrong type;
`details.fields` lists `{loc, type}`), `invalid_location_input`, `invalid_request`,
`invalid_project_type`, `invalid_facts`, `project_type_conflict` and fact-validation codes
such as `unknown_fact`, `invalid_fact_value`, `enum_value_not_allowed` (all 422),
`internal_error` (500, no details ever), `dataset_unavailable` (503). Every error also
has an `X-Request-ID` header equal to `request_id`.

## Projects and timeline (Person 5)

Files: `project_created.json`, `requirement_patch.json`, `timeline.json`,
`milestone_event_conflict_409.json`. Values match `backend/src/clearpath/projects/` and
`backend/src/clearpath/timelines/`.

**Project `state`**: `draft` (no pinned release) and `active` (after
`POST /api/v1/projects/{id}/activate` pins a release).

**Requirement `status`**: `not_started`, `in_progress`, `ready`. "Ready" is self-reported.
It does not mean the city accepted the document.

**Milestone `state`**: `not_started`, `in_progress`, `completed`. Events: `start`,
`complete`, `reopen`.

**Timeline bottleneck `code`s**: `missing_information`, `missing_documents`,
`awaiting_city`, `source_conflict`, `estimate_exceeded`.

**Project / timeline warning `code`s**:
- `synthetic_dataset`: the result comes from synthetic demo data.
- `selected_area_property_not_verified`: same code as the lookup (see above).
- `self_reported_status`: "ready" means the applicant marked it prepared, not that the
  city accepted it.

**Error `code`s** (HTTP status): `project_not_found`, `requirement_not_found`,
`milestone_not_found` (404); `stale_revision`, `project_not_active`,
`project_already_active`, `project_scope_immutable`, `milestone_transition_conflict`,
`requirement_transition_conflict`, `requirement_not_applicable` (409);
`validation_error`, `invalid_cursor`, `rule_facts_not_accepted` (422);
`dataset_unavailable`, `release_graph_invalid` (503).
