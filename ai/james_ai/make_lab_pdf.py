"""Build a lab-report PDF from a test set, in the Dutch two-table layout of our lab.

    python3 -m ai.james_ai.make_lab_pdf --set dev4 --out dev4_lab.pdf

Why: to try a test set in the app the same way a real report arrives (upload a PDF),
without using a real report. Everything in the PDF comes from ai/testcases/cases.json,
which holds fictional data only. Lab IDs are made up ("T-DEV4 001", ...).
"""
import argparse
import textwrap
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ai.james_ai.score import load_cases

GRID = TableStyle([("GRID", (0, 0), (-1, -1), 0.5, "black"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                   ("FONTSIZE", (0, 0), (-1, -1), 8)])


def _wrap(text: str, width: int) -> str:
    """Break long cell text over lines; the extractor joins them back with spaces."""
    return "\n".join(textwrap.wrap(text, width)) or text


def make_lab_pdf(path: str, lines: List[str], project: str, report: str) -> None:
    """One overview table (lab ID -> our code + place) and one results table (lab ID -> result)."""
    st = getSampleStyleSheet()["Normal"]
    overview = [["ID", "Uw referentie", "Ontvangst\nMonstername", "Analysemethode(s)\nDatum analyse - analist"]]
    results = [["ID", "Test/parameter", "Resultaat", "Eenheid"]]
    for n, line in enumerate(lines, start=1):
        code, desc, result = [p.strip() for p in line.split("|", 2)]
        lab_id = f"T-DEV4\n{n:03d}"
        overview.append([lab_id, code + "\n" + _wrap("Locatie: " + desc, 48),
                         "01-01-2099\nOpdrachtgever", "Visueel\nTEST-METHOD\n02-01-2099 - XX"])
        test, _, value = result.rpartition(": ")
        results.append([lab_id, test, _wrap(value, 46), ""])
    SimpleDocTemplate(path, pagesize=A4).build([
        Paragraph(f"Analyserapport: {report}", st),
        Paragraph("Datum rapportage : 01 januari 2099", st),
        Paragraph(f"Uw referentie : Project {project} | fictional test report", st),
        Spacer(1, 12),
        Table(overview, style=GRID, colWidths=[55, 220, 75, 120], repeatRows=1),
        PageBreak(),
        Table(results, style=GRID, colWidths=[55, 130, 250, 35], repeatRows=1),
    ])


def main() -> None:
    data = load_cases()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--set", required=True, choices=sorted(data["sets"]), dest="set_name")
    ap.add_argument("--out", required=True)
    ap.add_argument("--project", default="DEV-4")
    a = ap.parse_args()
    lines = [c["line"] for c in data["cases"] if c["set"] == a.set_name]
    make_lab_pdf(a.out, lines, a.project, f"TEST/{a.set_name.upper()}/v1.0")
    print(f"Wrote {a.out}: {len(lines)} lab lines from set {a.set_name}, project {a.project}.")


if __name__ == "__main__":
    main()
