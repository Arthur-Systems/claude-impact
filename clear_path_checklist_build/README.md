# ADU submittal packet (demo)

Abbreviated, fillable ADU submittal packet for the ClearPath demo (Irvine, ADU).
**Sample for software testing — not an official City of Irvine document.**

| File | What it is |
|---|---|
| `clearpath_adu_packet_blank.pdf` | 7-page fillable PDF: cover checklist + DOC-01 to DOC-06 |
| `clearpath_adu_packet_schema.json` | Every document and field (name, label, type, options, required, completed by) |
| `packet_spec.py` | Source of truth for documents and fields — edit this |
| `build_packet.py` | Regenerates the PDF and schema from the spec |

## Regenerate

```bash
pip install reportlab pypdf
python build_packet.py .
```

## Documents

- **DOC-01** Building Permit Application (based on Irvine Form 65-59 / 41-60)
- **DOC-02** Development Standards Checklist, site plan (Form 67-01)
- **DOC-03** ADU Verification Form (Part B completed by Planning staff)
- **DOC-04** Fire authority (OCFA) plan submittal criteria
- **DOC-05** School facilities + transportation corridor fee determinations (Forms 42-97, 66-92)
- **DOC-06** Owner acknowledgments: C&D waste, pre-approved plan release, e-signature

Separate uploads the app should expect but the packet doesn't recreate (plan set, site plan,
Title 24, covenant, deposit form, take-off sheet, HOA letter) are listed in the schema under
`external_documents`.

## Using the schema

- Field names are stable keys, e.g. `doc01.project_address`, `doc02.std.side_setback_ft.proposed`.
- `completed_by: "City staff"` marks fields the applicant should leave blank — useful for telling
  "applicant missed this" apart from "waiting on the city."
- Fill: write values into the PDF's form fields by name (e.g. pypdf `update_page_form_field_values`).
- Extract: read form fields directly (`PdfReader.get_fields()`); use OCR only for scanned or flattened uploads.

Source requirements: https://cityofirvine.gov/building-permits-and-inspections/project-constructing-accessory-dwelling-unit-adu
