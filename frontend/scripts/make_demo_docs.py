"""Generate fictional sample documents and demo ZIPs for the ClearPath Documents tab.

Every file is a one-page PDF stamped "SAMPLE DOCUMENT". No real person, parcel,
fee or deadline appears in any of them. Standard library only.

    python3 frontend/scripts/make_demo_docs.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "public" / "demo"
FIXED_TIME = (2026, 11, 7, 12, 0, 0)  # stable ZIP timestamps

# (file name, document title, one-line description)
DOCS = [
    ("01_Site_Plan.pdf", "Site plan", "Fictional dashboard sample."),
    ("02_Floor_Plans.pdf", "Floor plans", "Fictional dashboard sample."),
    ("03_Proof_of_Ownership.pdf", "Proof of ownership", "Fictional dashboard sample."),
    ("04_Structural_Calculations.pdf", "Structural calculations", "Fictional dashboard sample."),
    ("Holiday_Photo.pdf", "Holiday photo", "Unmatched fictional dashboard sample."),
    ("05_Energy_Compliance_Report.pdf", "Energy compliance report", "Fictional dashboard sample."),
    ("06_Elevations.pdf", "Elevations", "Fictional dashboard sample."),
]

ZIPS = {
    "clearpath-dashboard-1-plans.zip": DOCS[:2],
    "clearpath-dashboard-2-supporting.zip": DOCS[2:5],
    "clearpath-dashboard-3-final.zip": DOCS[5:],
    "clearpath-dashboard-all.zip": DOCS,
}


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(title: str, description: str) -> bytes:
    lines = [
        ("F2", 11, (0.75, 0.1, 0.1), "SAMPLE DOCUMENT - CLEARPATH DEMO ONLY - NOT A REAL APPLICATION"),
        ("F2", 20 if len(title) <= 30 else 14, (0, 0, 0), title),
        ("F1", 11, (0.2, 0.2, 0.2), "Fictional dashboard demonstration - not a city form"),
        ("F1", 11, (0.2, 0.2, 0.2), description),
        ("F1", 11, (0, 0, 0), ""),
        ("F1", 11, (0, 0, 0), "Project: Fictional dashboard sample"),
        ("F1", 11, (0, 0, 0), "Applicant: Sample Applicant (fictional)"),
        ("F1", 11, (0, 0, 0), "Property: none (no real parcel)"),
        ("F1", 11, (0, 0, 0), "Prepared: November 7, 2026"),
        ("F1", 11, (0, 0, 0), ""),
        ("F1", 10, (0.35, 0.35, 0.35), "This file exists only to show how ClearPath matches uploaded documents"),
        ("F1", 10, (0.35, 0.35, 0.35), "by filename only. Contents are not validated. No city acceptance."),
        ("F1", 10, (0.35, 0.35, 0.35), "Prototype. Not legal advice. Consult a professional for decisions."),
    ]
    parts = ["BT 0.9 0.8 0.8 rg /F2 42 Tf 0.707 0.707 -0.707 0.707 100 250 Tm (SAMPLE DOCUMENT) Tj ET"]
    y = 712
    for font, size, (r, g, b), text in lines:
        if text:
            parts.append(f"BT {r} {g} {b} rg /{font} {size} Tf 72 {y} Td ({_esc(text)}) Tj ET")
        y -= size + 12
    parts.append("0.75 0.1 0.1 RG 2 w 60 60 492 680 re S")  # red border
    stream = "\n".join(parts).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Title (%s) /Producer (ClearPath demo generator) >>" % _esc("SAMPLE: " + title).encode("latin-1"),
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info 7 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pdfs = {name: make_pdf(title, desc) for name, title, desc in DOCS}
    for zip_name, docs in ZIPS.items():
        with zipfile.ZipFile(OUT / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, _, _ in docs:
                info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, pdfs[name])
        print(f"{zip_name}: {', '.join(d[0] for d in docs)}")


if __name__ == "__main__":
    main()
