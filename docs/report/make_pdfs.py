"""Turn the Markdown documents in docs/report/ into PDFs.

    python3 docs/report/make_pdfs.py

Why: the documents are kept as Markdown (easy to edit and review in git) and handed in as PDF.
Only the Markdown this folder uses is supported: headings, paragraphs, bold, inline code,
bullet and numbered lists, and pipe tables.
"""
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent
BRAND = colors.HexColor("#1f5a43")
TEXT = colors.HexColor("#18201b")
MUTED = colors.HexColor("#56605a")
LINE = colors.HexColor("#d5d9d3")
HEAD_BG = colors.HexColor("#f1f3f0")

BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=TEXT, alignment=TA_LEFT, spaceAfter=5)
STYLES = {
    "h1": ParagraphStyle("h1", parent=BASE, fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=TEXT, spaceAfter=2),
    "sub": ParagraphStyle("sub", parent=BASE, fontSize=9, textColor=MUTED, spaceAfter=12),
    "h2": ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=BRAND, spaceBefore=12, spaceAfter=5),
    "h3": ParagraphStyle("h3", parent=BASE, fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=4),
    "p": BASE,
    "cell": ParagraphStyle("cell", parent=BASE, fontSize=8.3, leading=10.8, spaceAfter=0),
    "headcell": ParagraphStyle("headcell", parent=BASE, fontName="Helvetica-Bold", fontSize=8.3, leading=10.8, spaceAfter=0, textColor=MUTED),
}


def inline(text: str) -> str:
    """Markdown inline marks to reportlab's mini-HTML."""
    t = escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
    return t


def table(rows, width):
    head, body = rows[0], rows[1:]
    n = len(head)
    # Every column is at least as wide as its longest word (so no word is broken letter by letter);
    # the width left over is shared by how much text each column holds.
    cell = lambda r, i: re.sub(r"[*`]", "", r[i]) if i < len(r) else ""
    word = [max((len(w) for r in rows for w in cell(r, i).split()), default=1) for i in range(n)]
    floor = [w * 5.2 + 12 for w in word]
    if sum(floor) > width:                               # very long words: shrink floors proportionally
        floor = [f * width / sum(floor) for f in floor]
    text = [min(max(len(cell(r, i)) for r in rows), 70) for i in range(n)]
    extra = [max(t * 5.2 + 12 - f, 0) for t, f in zip(text, floor)]
    spare = width - sum(floor)
    widths = [f + (spare * e / sum(extra) if sum(extra) else spare / n) for f, e in zip(floor, extra)]
    data = [[Paragraph(inline(c), STYLES["headcell"]) for c in head]]
    data += [[Paragraph(inline(r[i] if i < len(r) else ""), STYLES["cell"]) for i in range(n)] for r in body]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


def flowables(md: str, width: float):
    out, lines, i = [], md.splitlines(), 0
    first_h1 = True
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("# "):
            out.append(Paragraph(inline(ln[2:]), STYLES["h1"]))
            if first_h1 and i + 2 < len(lines) and lines[i + 1].strip() == "" and lines[i + 2].strip() and not lines[i + 2].startswith(("#", "*", "|", "-")):
                out.append(Paragraph(inline(lines[i + 2].strip()), STYLES["sub"]))
                i += 3
                first_h1 = False
                continue
            first_h1 = False
            i += 1
        elif ln.startswith("## "):
            out.append(Paragraph(inline(ln[3:]), STYLES["h2"]))
            i += 1
        elif ln.startswith("### "):
            out.append(Paragraph(inline(ln[4:]), STYLES["h3"]))
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            out.append(table(rows, width))
            out.append(Spacer(1, 7))
        elif re.match(r"^(- |\d+\. )", ln):
            numbered = bool(re.match(r"^\d+\. ", ln))
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                text = re.sub(r"^(- |\d+\. )", "", lines[i]).strip()
                items.append(ListItem(Paragraph(inline(text), STYLES["p"]), leftIndent=12))
                i += 1
            out.append(ListFlowable(items, bulletType="1" if numbered else "bullet", start="1" if numbered else None,
                                    bulletFontSize=8 if not numbered else 9.5, leftIndent=14, bulletColor=MUTED))
            out.append(Spacer(1, 3))
        else:
            para = [ln.strip()]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||- |\d+\. )", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append(Paragraph(inline(" ".join(para)), STYLES["p"]))
    return out


def build(md_path: Path, pdf_path: Path) -> None:
    md = md_path.read_text(encoding="utf-8")
    title = md.splitlines()[0].lstrip("# ").strip()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"James · {title}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=18 * mm, title=title, author="Tasnim (James project team)")
    doc.build(flowables(md, A4[0] - 36 * mm), onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    for md in sorted(HERE.glob("[0-9][0-9]-*.md")):
        pdf = md.with_suffix(".pdf")
        build(md, pdf)
        print(f"Wrote {pdf.relative_to(HERE.parents[1])}")
