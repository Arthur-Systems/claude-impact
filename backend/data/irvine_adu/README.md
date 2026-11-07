# Irvine ADU curated bundle

Person 2 owns `manifest.json`. Preserve checked source text, citations, conditions,
and stated gaps; do not invent facts, fees, addresses, deadlines, or form names.
This is a prototype, not legal, financial, or lending advice.

## Accepted format

- `schema_version` is `1`; `profile_key` is a required lowercase slug, never derived.
  `kind` defaults to `reviewed_public`, `curator_label` to `""`; `subtype` is optional.
- `fact_schema` maps fact names to `string`, `boolean`, or `number`, matching
  Person 4's `permits/predicates.py`. If omitted for `project_type: adu`, it defaults
  to `project_type: string`, `adu_form: string`, `existing_dwelling: boolean`, and
  `floor_area_sqft: number`. Other project types require an explicit schema.
- Keys starting with `_` are curator notes at any depth. They are ignored for
  persistence and never echoed in validation diagnostics. A passage without an
  explicit `review_status` becomes `needs_review` when `_review_note` is non-empty,
  otherwise `reviewed`. An explicit status always wins. Check the text before
  marking it reviewed; publication rejects citations to unreviewed passages.
- Source keys are uppercase (`^[A-Z0-9][A-Z0-9_-]{0,79}$`); fact names,
  jurisdiction/profile keys, and pathway/requirement/milestone keys are lowercase
  slugs. Every pathway and requirement needs citations in a public bundle.
- `assumed_days` is null or an object with nullable `min`/`max` and mandatory
  `label: ASSUMPTION`. A non-empty `rationale` is required if either bound is set;
  it may be null or omitted only when both bounds are null.
- Pathway `description` is optional and defaults to `""`.
- `published_clock` is null or a timing object: `kind` (`city_service_target`,
  `statutory_clock`, `observed`, `assumption`), finite numeric/null `value`, text
  `unit`, non-empty `scope`, optional nullable `qualifier`/`verification`, and
  optional passage UUID `citation` and/or UUID list `citations` (default `[]`).
  City targets and statutory clocks require at least one citation. Both citation
  forms must resolve and are linked to the milestone. Display only; never calculate due dates.
- Conflicts accept exactly one of `source_keys` or its alias `sources`, with at
  least one non-empty rule string, one non-empty source string, and a non-empty
  summary. These are informational, not checked references: unentered rules,
  milestone keys and pseudo-sources such as `SPEC-8` are valid. They persist unchanged.
- The content hash covers the raw parsed JSON, including curator notes, before
  defaults and normalization. Formatting/key ordering alone does not change it.

From the repository root:

```sh
uv run --project backend clearpath data import --manifest backend/data/irvine_adu/manifest.json --dry-run
make seed-irvine
```

Dry-run performs file-only validation; it does not confirm evidence review. Import
accepts the curated format, but public publication rejects unreviewed cited evidence
with `unreviewed_evidence` and the affected pathway/requirement/milestone keys, including
clock citations. To clear the gate, Person 2 must hand-check **each `_review_note` passage**
against its source, then remove the note or set `"review_status": "reviewed"`. If an
explicit `needs_review`/`failed` status remains, change it only after that check.
Reimport the edited manifest as a new draft, then publish with `--reviewed`.
Do not bypass the gate or alter source evidence just to make publication succeed.
`manifest.batch1.json` is an earlier draft and is not a seed target.
