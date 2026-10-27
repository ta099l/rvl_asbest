"""Turn a lab report PDF into the text format the linker reads:

    Report: LAB-2026-0412
    Project: 26-3VK
    ---
    S-01 | Insulation wrap, engine room bulkhead | Chrysotile 15%

Pages with a text layer are read directly. Pages without one (scans, photos)
go through OCR (tesseract). Both paths produce words with positions, and the
same table logic rebuilds the ID / description / result columns from the
header row. This was only tried on simple one-table layouts. Real lab reports
will differ, so treat the layout code as a starting point.
"""
import glob
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pdfplumber


@dataclass
class Word:
    text: str
    x0: float
    top: float
    height: float
    x1: float = 0.0          # right edge; 0 when unknown

    @property
    def right(self) -> float:
        return self.x1 or self.x0 + len(self.text) * 0.5 * self.height

    @property
    def center(self) -> float:
        return self.top + self.height / 2


@dataclass
class Extraction:
    text: str
    method: str                       # "text", "ocr" or "mixed"
    pages: int
    notes: List[str] = field(default_factory=list)


def _group_lines(words: List[Word]) -> List[List[Word]]:
    if not words:
        return []
    # Group by vertical centre, not top edge: a small glyph such as "-" sits lower than
    # tall letters on the same line and would otherwise become a row of its own.
    tol = 0.6 * statistics.median(w.height for w in words)
    lines: List[list] = []                      # [sum of centres, count, words]
    for w in sorted(words, key=lambda w: (w.center, w.x0)):
        if lines and abs(w.center - lines[-1][0] / lines[-1][1]) <= tol:
            lines[-1][0] += w.center
            lines[-1][1] += 1
            lines[-1][2].append(w)
        else:
            lines.append([w.center, 1, [w]])
    return [sorted(ws, key=lambda w: w.x0) for _, _, ws in lines]


# Header words that start a column. Words in one header cell ("Certificate Number")
# are joined first, so "analysisresult" and "analysismethod" stay two columns.
HEADER_NAMES = {
    "id": "id", "sample": "id", "sampleid": "id", "samplenumber": "id", "sampleno": "id",
    "description": "description", "materialuse": "description",
    "method": "method", "analysismethod": "method",
    "result": "result", "results": "result", "analysisresult": "result", "analysisresults": "result",
    "certificate": "certificate", "certificatenumber": "certificate", "certificateno": "certificate",
    "quantity": "quantity", "remarks": "remarks",
}
Columns = List[Tuple[float, str]]          # (left edge x, column name), left to right


def _header_cells(line: List[Word]) -> List[Tuple[float, str]]:
    """Join words that sit close together into one header cell: [(x of first word, joined text)]."""
    cells: List[list] = []                     # [x of first word, joined text, right edge]
    for w in line:
        if cells and w.x0 - cells[-1][2] < 0.6 * w.height:     # about one space apart: same cell
            cells[-1][1] += w.text
            cells[-1][2] = w.right
        else:
            cells.append([w.x0, w.text, w.right])
    return [(x, re.sub(r"[^a-z]", "", t.lower())) for x, t, _ in cells]


def _find_columns(lines: List[List[Word]]) -> Optional[Tuple[int, Columns]]:
    """Return (header line index, columns) from the first line that has a description and a result header."""
    for i, ln in enumerate(lines):
        cols = [(x - 3, HEADER_NAMES[t]) for x, t in _header_cells(ln) if t in HEADER_NAMES]
        names = [n for _, n in cols]
        if "description" in names and "result" in names:
            if names[0] != "id":                    # the first column holds the sample ID, named or not
                cols.insert(0, (float("-inf"), "id"))
            cols[0] = (float("-inf"), "id")
            seen, out = set(), []
            for x, n in cols:
                if n not in seen:
                    seen.add(n)
                    out.append((x, n))
            return i, out
    return None


def _cells(line: List[Word], cols: Columns) -> List[str]:
    edges = [x for x, _ in cols[1:]] + [float("inf")]
    out = []
    for k, (x, _) in enumerate(cols):
        out.append(" ".join(w.text for w in line if (k == 0 or w.x0 >= x) and w.x0 < edges[k]))
    return out


def words_to_lab_lines(words: List[Word], cols: Optional[Columns] = None):
    """Return (header lines 'Key: value', table rows 'id | desc | result', columns).

    With only ID, description and result columns the rows look exactly as before.
    With extra columns (certificate, method, quantity, remarks) a header line
    'Columns: ...' names them, and every row keeps all its cells.
    """
    lines = _group_lines(words)
    start = 0
    head: List[str] = []
    if cols is None:
        found = _find_columns(lines)
        if found is None:
            return [], [], None
        hi, cols = found
        for ln in lines[:hi]:
            t = " ".join(w.text for w in ln)
            if ":" in t:
                head.append(t)
        if [n for _, n in cols] != ["id", "description", "result"]:
            head.append("Columns: " + " | ".join(n for _, n in cols))
        start = hi + 1
    rows: List[str] = []
    for ln in lines[start:]:
        cells = _cells(ln, cols)
        if not any(cells):
            continue
        cells[0] = cells[0] or "-"
        rows.append(" | ".join(cells))
    return head, rows, cols


def _ocr_words(pdf_path: str, page_number: int) -> List[Word]:
    if shutil.which("tesseract") is None or shutil.which("pdftoppm") is None:
        raise RuntimeError("This page has no text layer and OCR is not available "
                           "(install tesseract and poppler-utils).")
    with tempfile.TemporaryDirectory() as tmp:
        prefix = os.path.join(tmp, "page")
        subprocess.run(["pdftoppm", "-r", "200", "-f", str(page_number), "-l", str(page_number),
                        "-png", pdf_path, prefix], check=True, capture_output=True)
        img = sorted(glob.glob(prefix + "*.png"))[0]
        out = subprocess.run(["tesseract", img, "stdout", "--psm", "6", "tsv"],
                             check=True, capture_output=True, text=True).stdout
    words: List[Word] = []
    for ln in out.splitlines()[1:]:
        f = ln.split("\t")
        if len(f) < 12 or f[0] != "5" or not f[11].strip():
            continue
        words.append(Word(f[11].strip(), float(f[6]), float(f[7]), float(f[9]), float(f[6]) + float(f[8])))
    return words


def extract_lab_text(pdf_path: str) -> Extraction:
    methods, notes = [], []
    head: List[str] = []
    rows: List[str] = []
    cols = None
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        for page in pdf.pages:
            ws = page.extract_words()
            if len(ws) >= 5:
                words = [Word(w["text"], w["x0"], w["top"], w["bottom"] - w["top"], w["x1"]) for w in ws]
                methods.append("text")
            else:
                words = _ocr_words(pdf_path, page.page_number)
                methods.append("ocr")
                notes.append(f"Page {page.page_number} was read by OCR. Check it against the original image.")
            h, r, cols = words_to_lab_lines(words, cols)
            if not head:
                head = h
            rows += r
    if cols is None:
        notes.append("No table with 'Description' and 'Result' column headers was found.")
    method = methods[0] if len(set(methods)) == 1 else "mixed"
    text = "\n".join(head + ["---"] + rows)
    return Extraction(text=text, method=method, pages=n, notes=notes)
