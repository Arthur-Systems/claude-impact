# API example responses

These files are **example request/response pairs** for the ClearPath lookup routes
(SPEC.md §7 and §9). They are mocks for the frontend (Person 1), not real data. Every
URL, title, excerpt, hash and form name is a placeholder in `<angle brackets>`, and
numbers such as `floor_area_sqft: 600` are arbitrary test inputs, not Irvine rules. Each
file holds `{"request", "status_code", "response"}`, and every response carries
`"example": true`, which the real API will not send. When the real API needs a different
shape, **update these files first, then the code**, and tell Person 1. Person 5 owns
the project and timeline examples.

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
- `test_only_unreviewed_release`: tests only. Unreviewed data was force-loaded as
  `reviewed_public`. The real API should never send this.

**Error `code`s** (HTTP status): `missing_api_key` (401), `invalid_request`,
`invalid_location_input`, `invalid_project_type`, `invalid_facts`,
`project_type_conflict` and fact-validation codes such as `unknown_fact`,
`invalid_fact_value`, `enum_value_not_allowed` (all 422), `dataset_unavailable` (503).
