# Irvine ADU bundle (stub)

Person 2 fills this reviewed-public stub using checked City of Irvine sources.
Record each source URL, publisher, checked date and verification depth. Copy exact
excerpts into passages with stable UUIDs and a locator; mark `review_status` as
`reviewed` only after checking the text, otherwise `needs_review` or `failed`.
Cite reviewed passages from every pathway and requirement. Do not invent facts,
fees, addresses, deadlines or form names. Label estimated durations `ASSUMPTION`.
Source keys use uppercase letters/digits/underscores/hyphens (e.g. `IRV-ADU`);
rule keys, fact names, jurisdiction and profile keys use lowercase slugs.

Once the CLI lands, validate from the repository root:

```sh
clearpath data import --manifest backend/data/irvine_adu/manifest.json --dry-run
```

Meanwhile run from the repository root:

```sh
cd backend && PYTHONPATH=src uv run --no-project --python 3.12 --with 'pydantic>=2' --with pytest pytest tests/unit -q
```

An empty stub is structurally valid but provides no real rule coverage. This is a
prototype, not legal, financial or lending advice; consult a professional.
