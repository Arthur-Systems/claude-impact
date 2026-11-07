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
- `published_clock` is null or `{"text": "...", "citations": ["passage-uuid"]}`:
  display only, never a calculated due date. Pathways require `description`.
- Conflicts accept exactly one of `source_keys` or its alias `sources`; rule and
  source references must resolve to bundle entries. Conflicts currently reference
  pathways/requirements, not milestone keys.
- The content hash covers the raw parsed JSON, including curator notes, before
  defaults and normalization. Formatting/key ordering alone does not change it.

From the repository root:

```sh
uv run --project backend clearpath data import --manifest backend/data/irvine_adu/manifest.json --dry-run
make seed-irvine
```

Dry-run performs file-only validation. Import/publication remain blocked by
schema/reference errors or unreviewed cited evidence; do not bypass these gates.
`manifest.batch1.json` is an earlier draft and is not a seed target.
