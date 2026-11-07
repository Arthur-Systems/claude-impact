"""Render the ClearPath demo ADU packet as a fillable PDF plus a JSON schema.

Usage: python build_packet.py [outdir]
"""
import json
import sys
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent))
from packet_spec import DOCUMENTS, EXTERNAL_DOCUMENTS, PACKET  # noqa: E402

W, H = letter
M = 40                      # page margin
CW = W - 2 * M              # content width
INK = HexColor("#1d2430")
MUTED = HexColor("#5b6472")
ACCENT = HexColor("#1f5f5b")
RULE = HexColor("#c9ced6")
STAFF_BG = HexColor("#eef1f4")
FIELD_BG = HexColor("#fbfcfd")
WARN = HexColor("#9a3b12")

LABEL_PT = 7.2
FIELD_H = 17
AREA_H = 40
GAP = 4


def norm(row_item):
    """Expand a spec tuple into a dict."""
    kind = row_item[0]
    if kind in ("choice", "multi"):
        _, name, label, options, width, *rest = row_item
    else:
        _, name, label, width, *rest = row_item
        options = ["Yes", "No"] if kind == "yesno" else None
    return {"type": kind, "name": name, "label": label, "options": options,
            "width": width, "required": bool(rest and rest[0])}


class Packet:
    def __init__(self, path):
        self.c = canvas.Canvas(str(path), pagesize=letter)
        self.c.setTitle(f"ClearPath Demo - {PACKET['title']}")
        self.c.setAuthor("ClearPath (hackathon demo)")
        self.c.setSubject(PACKET["disclaimer"])
        self.page_no = 0
        self.doc = None
        self.y = 0
        self.schema_fields = []

    # ---------------------------------------------------------------- chrome
    def new_page(self, doc=None, cont=False):
        if self.page_no:
            self.footer()
            self.c.showPage()
        self.page_no += 1
        c = self.c
        # banner
        c.setFillColor(ACCENT)
        c.rect(0, H - 28, W, 28, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(M, H - 18, "CLEARPATH DEMO  |  " + PACKET["title"].upper())
        c.setFont("Helvetica", 8)
        c.drawRightString(W - M, H - 18, "SAMPLE FOR SOFTWARE TESTING - NOT AN OFFICIAL FORM")
        self.y = H - 48
        if doc:
            c.setFillColor(ACCENT)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(M, self.y, doc["id"])
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(M + 48, self.y, doc["title"] + ("  (continued)" if cont else ""))
            self.y -= 14
            if not cont:
                c.setFont("Helvetica", 7.5)
                c.setFillColor(MUTED)
                meta = (f"Based on: {doc['based_on']}   |   Completed by: {doc['completed_by']}"
                        f"   |   When required: {doc['condition']}")
                for line in simpleSplit(meta, "Helvetica", 7.5, CW):
                    c.drawString(M, self.y, line)
                    self.y -= 9
            self.y -= 6
            c.setStrokeColor(RULE)
            c.line(M, self.y, W - M, self.y)
            self.y -= 12

    def footer(self):
        c = self.c
        c.setFont("Helvetica", 6.8)
        c.setFillColor(MUTED)
        lines = simpleSplit(PACKET["disclaimer"], "Helvetica", 6.8, CW - 60)
        y = 28
        for line in lines:
            c.drawString(M, y, line)
            y -= 8
        c.drawRightString(W - M, 28, f"Page {self.page_no}")

    def need(self, h):
        if self.y - h < 42:
            self.new_page(self.doc, cont=True)

    # ---------------------------------------------------------------- fields
    def register(self, doc_id, f, section, staff):
        self.schema_fields.append({
            "document": doc_id,
            "name": f"{doc_id.lower().replace('-', '')}.{f['name']}",
            "label": f["label"],
            "type": f["type"],
            "options": f["options"],
            "required": f["required"],
            "section": section,
            "completed_by": "City staff" if staff else "Applicant",
        })

    def label(self, x, y, text, required):
        c = self.c
        c.setFont("Helvetica", LABEL_PT)
        c.setFillColor(MUTED)
        c.drawString(x, y, text)
        if required:
            c.setFillColor(WARN)
            c.drawString(x + c.stringWidth(text, "Helvetica", LABEL_PT) + 1.5, y, "*")

    def draw_field(self, doc_id, f, x, w, top):
        """Draw one field whose label baseline sits at `top`. Returns height used."""
        c, form = self.c, self.c.acroForm
        fname = f"{doc_id.lower().replace('-', '')}.{f['name']}"
        self.label(x, top, f["label"], f["required"])
        box_top = top - 3
        kind = f["type"]
        if kind in ("text", "sign"):
            y = box_top - FIELD_H
            form.textfield(name=fname, tooltip=f["label"], x=x, y=y, width=w - 6, height=FIELD_H,
                           borderWidth=0.6, borderColor=RULE, fillColor=FIELD_BG,
                           textColor=INK, fontSize=9, fontName="Helvetica")
            if kind == "sign":
                c.setStrokeColor(INK)
                c.setLineWidth(0.8)
                c.line(x, y - 1, x + w - 6, y - 1)
                c.setLineWidth(1)
            return top - y + 2
        if kind == "area":
            y = box_top - AREA_H
            form.textfield(name=fname, tooltip=f["label"], x=x, y=y, width=w - 6, height=AREA_H,
                           borderWidth=0.6, borderColor=RULE, fillColor=FIELD_BG, textColor=INK,
                           fontSize=9, fontName="Helvetica", fieldFlags="multiline")
            return top - y + 2
        # option groups
        opts = f["options"]
        cx = x
        y = box_top - 12
        for o in opts:
            tw = c.stringWidth(o, "Helvetica", 8.5)
            if cx + 14 + tw > x + w - 4:
                cx = x
                y -= 14
            if kind == "multi":
                form.checkbox(name=f"{fname}.{o}", tooltip=f"{f['label']}: {o}", x=cx, y=y,
                              size=10, borderWidth=0.6, borderColor=INK, fillColor=white,
                              buttonStyle="check")
            else:
                form.radio(name=fname, tooltip=f"{f['label']}: {o}", value=o, selected=False,
                           x=cx, y=y, size=10, borderWidth=0.6, borderColor=INK, fillColor=white,
                           buttonStyle="circle")
            c.setFont("Helvetica", 8.5)
            c.setFillColor(INK)
            c.drawString(cx + 13, y + 2, o)
            cx += 13 + tw + 12
        return top - y + 4

    def row_height(self, row):
        hs = []
        for f in row:
            if f["type"] == "area":
                hs.append(AREA_H + 14)
            elif f["type"] in ("choice", "multi", "yesno"):
                hs.append(28)
            else:
                hs.append(FIELD_H + 14)
        return max(hs) + GAP

    def section(self, doc, sec, note=None):
        c = self.c
        rows = [[norm(i) for i in r] for r in sec["rows"]]
        staff = sec.get("staff", False)
        first_h = self.row_height(rows[0]) if rows else 0
        self.need(26 + first_h)
        # heading
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(M, self.y, sec["title"].upper())
        if staff:
            c.setFillColor(WARN)
            c.setFont("Helvetica-Oblique", 7.5)
            c.drawRightString(W - M, self.y, "Completed by City staff - applicant leaves blank")
        self.y -= 5
        c.setStrokeColor(ACCENT if not staff else RULE)
        c.setLineWidth(1.2)
        c.line(M, self.y, W - M, self.y)
        c.setLineWidth(1)
        self.y -= 12
        if note:
            c.setFont("Helvetica-Oblique", 8)
            c.setFillColor(MUTED)
            for line in simpleSplit(note, "Helvetica-Oblique", 8, CW):
                c.drawString(M, self.y, line)
                self.y -= 10
            self.y -= 3
        for row in rows:
            h = self.row_height(row)
            self.need(h)
            if staff:
                c.setFillColor(STAFF_BG)
                c.rect(M - 4, self.y - h + GAP + 2, CW + 8, h, stroke=0, fill=1)
            x = M
            for f in row:
                w = CW * f["width"]
                self.draw_field(doc["id"], f, x, w, self.y)
                self.register(doc["id"], f, sec["title"], staff)
                x += w
            self.y -= h
        self.y -= 6

    def standards_table(self, doc):
        c = self.c
        t = doc["table"]
        widths = [0.24, 0.40, 0.22, 0.14]
        xs = [M]
        for wf in widths[:-1]:
            xs.append(xs[-1] + CW * wf)

        def header():
            c.setFillColor(ACCENT)
            c.rect(M, self.y - 4, CW, 15, stroke=0, fill=1)
            c.setFillColor(white)
            c.setFont("Helvetica-Bold", 8)
            for x, col in zip(xs, t["columns"]):
                c.drawString(x + 4, self.y + 1, col)
            self.y -= 18

        self.need(40)
        header()
        for i, (key, std, req) in enumerate(t["rows"]):
            req_lines = simpleSplit(req, "Helvetica", 7.5, CW * widths[1] - 8) or [""]
            std_lines = simpleSplit(std, "Helvetica-Bold", 8, CW * widths[0] - 8)
            h = max(22, 10 * max(len(req_lines), len(std_lines)) + 8)
            if self.y - h < 42:
                self.new_page(doc, cont=True)
                header()
            if i % 2 == 0:
                c.setFillColor(HexColor("#f5f7f9"))
                c.rect(M, self.y - h + 9, CW, h, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont("Helvetica-Bold", 8)
            ty = self.y
            for line in std_lines:
                c.drawString(xs[0] + 4, ty, line)
                ty -= 10
            c.setFont("Helvetica", 7.5)
            c.setFillColor(MUTED)
            ty = self.y
            for line in req_lines:
                c.drawString(xs[1] + 4, ty, line)
                ty -= 10
            base = f"{doc['id'].lower().replace('-', '')}.std.{key}"
            fy = self.y - 7
            c.acroForm.textfield(name=f"{base}.proposed", tooltip=f"{std}: proposed / shown",
                                 x=xs[2] + 2, y=fy, width=CW * widths[2] - 6, height=15,
                                 borderWidth=0.6, borderColor=RULE, fillColor=white,
                                 textColor=INK, fontSize=8.5)
            c.acroForm.textfield(name=f"{base}.sheet", tooltip=f"{std}: plan sheet",
                                 x=xs[3] + 2, y=fy, width=CW * widths[3] - 6, height=15,
                                 borderWidth=0.6, borderColor=RULE, fillColor=white,
                                 textColor=INK, fontSize=8.5)
            for suffix, lab in (("proposed", "Proposed / shown"), ("sheet", "Plan sheet")):
                self.schema_fields.append({
                    "document": doc["id"], "name": f"{base}.{suffix}", "label": f"{std} - {lab}",
                    "type": "text", "options": None, "required": suffix == "proposed",
                    "section": "Development standards", "completed_by": "Applicant",
                    "requirement": req or None,
                })
            self.y -= h
        self.y -= 10

    # ---------------------------------------------------------------- pages
    def cover(self):
        self.new_page()
        c = self.c
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 20)
        c.drawString(M, self.y - 6, "Abbreviated ADU Submittal Packet")
        self.y -= 26
        c.setFont("Helvetica", 10.5)
        c.setFillColor(MUTED)
        c.drawString(M, self.y, f"Demo jurisdiction: {PACKET['jurisdiction']}   |   Project type: {PACKET['project_type']}")
        self.y -= 22

        c.setFillColor(HexColor("#fdf3ee"))
        box = simpleSplit(PACKET["disclaimer"], "Helvetica", 8.5, CW - 20)
        bh = 14 + 11 * len(box)
        c.rect(M, self.y - bh + 10, CW, bh, stroke=0, fill=1)
        c.setFillColor(WARN)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(M + 10, self.y, "DEMO ONLY")
        c.setFont("Helvetica", 8.5)
        ty = self.y - 11
        for line in box:
            c.drawString(M + 10, ty, line)
            ty -= 11
        self.y -= bh + 12

        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(M, self.y, "SUBMITTAL CHECKLIST")
        self.y -= 6
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.2)
        c.line(M, self.y, W - M, self.y)
        c.setLineWidth(1)
        self.y -= 14
        cols = [("Incl.", 0.06), ("ID", 0.09), ("Document", 0.43), ("Completed by", 0.22), ("Required", 0.20)]
        xs, x = [], M
        for _, wf in cols:
            xs.append(x)
            x += CW * wf
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(MUTED)
        for (name, _), x in zip(cols, xs):
            c.drawString(x + 2, self.y, name)
        self.y -= 14

        entries = [(d["id"], d["title"], d["completed_by"], "Yes" if d["required"] else "Conditional", True)
                   for d in DOCUMENTS]
        entries += [(e["id"], e["title"], e["completed_by"], "Yes" if e["required"] else "Conditional", False)
                    for e in EXTERNAL_DOCUMENTS]
        for i, (did, title, by, req, in_packet) in enumerate(entries):
            tl = simpleSplit(title + ("" if in_packet else "  (separate upload)"), "Helvetica", 8, CW * 0.43 - 6)
            bl = simpleSplit(by, "Helvetica", 7.5, CW * 0.22 - 6)
            h = 10 * max(len(tl), len(bl)) + 8
            if i % 2 == 0:
                c.setFillColor(HexColor("#f5f7f9"))
                c.rect(M, self.y - h + 9, CW, h, stroke=0, fill=1)
            c.acroForm.checkbox(name=f"packet.included.{did}", tooltip=f"{did} included",
                                x=xs[0] + 4, y=self.y - 3, size=10, borderWidth=0.6,
                                borderColor=INK, fillColor=white, buttonStyle="check")
            c.setFillColor(ACCENT if in_packet else MUTED)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(xs[1] + 2, self.y, did)
            c.setFillColor(INK)
            c.setFont("Helvetica", 8)
            ty = self.y
            for line in tl:
                c.drawString(xs[2] + 2, ty, line)
                ty -= 10
            c.setFont("Helvetica", 7.5)
            c.setFillColor(MUTED)
            ty = self.y
            for line in bl:
                c.drawString(xs[3] + 2, ty, line)
                ty -= 10
            c.setFillColor(INK if req == "Yes" else MUTED)
            c.drawString(xs[4] + 2, self.y, req)
            self.y -= h
        self.y -= 12

        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(M, self.y, "HOW THIS PACKET MAPS TO THE REAL PROCESS")
        self.y -= 6
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1.2)
        c.line(M, self.y, W - M, self.y)
        c.setLineWidth(1)
        self.y -= 13
        steps = [
            "1. Request the ADU Verification Form from Planning; staff complete and sign Part B (DOC-03).",
            "2. Complete DOC-01, DOC-02, DOC-04, DOC-05 (applicant parts) and DOC-06.",
            "3. Assemble the plan set (PLAN-01, PLAN-02) and other separate uploads (EXT-01 to EXT-05).",
            "4. Upload everything to the city's online permit portal. Staff check completeness, then invoice plan review fees.",
            "Fields marked * are required. Shaded sections are completed by City staff and should be blank on submittal.",
        ]
        c.setFont("Helvetica", 8.5)
        for s in steps:
            for line in simpleSplit(s, "Helvetica", 8.5, CW):
                c.setFillColor(INK if s[0].isdigit() else MUTED)
                c.drawString(M, self.y, line)
                self.y -= 11
        self.y -= 4

    def build(self):
        self.cover()
        for doc in DOCUMENTS:
            self.doc = doc
            self.new_page(doc)
            if "table" in doc:
                self.standards_table(doc)
            notes = doc.get("notes", {})
            for sec in doc["sections"]:
                self.section(doc, sec, notes.get(sec["title"]))
        self.footer()
        self.c.save()


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    pdf_path = out / "clearpath_adu_packet_blank.pdf"
    p = Packet(pdf_path)
    p.build()

    by_doc = {}
    for f in p.schema_fields:
        by_doc.setdefault(f["document"], []).append({k: v for k, v in f.items() if k != "document"})
    schema = {
        **PACKET,
        "documents": [
            {k: d[k] for k in ("id", "title", "based_on", "completed_by", "required", "condition")}
            | {"fields": by_doc.get(d["id"], [])}
            for d in DOCUMENTS
        ],
        "external_documents": EXTERNAL_DOCUMENTS,
        "packet_fields": [{"name": f"packet.included.{x['id']}", "type": "checkbox"}
                          for x in DOCUMENTS + EXTERNAL_DOCUMENTS],
    }
    (out / "clearpath_adu_packet_schema.json").write_text(json.dumps(schema, indent=2))
    print(pdf_path, p.page_no, "pages,", len(p.schema_fields), "schema fields")


if __name__ == "__main__":
    main()
