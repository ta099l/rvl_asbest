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


def _find_columns(lines: List[List[Word]]) -> Optional[Tuple[int, float, float]]:
    """Return (header line index, description x, result x) from the header row."""
    for i, ln in enumerate(lines):
        low = {w.text.lower().strip(":"): w for w in ln}
        if "description" in low and "result" in low:
            return i, low["description"].x0 - 3, low["result"].x0 - 3
    return None


def words_to_lab_lines(words: List[Word], cols: Optional[Tuple[float, float]] = None):
    """Return (header lines 'Key: value', table rows 'id | desc | result', columns)."""
    lines = _group_lines(words)
    start = 0
    head: List[str] = []
    if cols is None:
        found = _find_columns(lines)
        if found is None:
            return [], [], None
        hi, dx, rx = found
        for ln in lines[:hi]:
            t = " ".join(w.text for w in ln)
            if ":" in t:
                head.append(t)
        cols, start = (dx, rx), hi + 1
    dx, rx = cols
    rows: List[str] = []
    for ln in lines[start:]:
        idc = " ".join(w.text for w in ln if w.x0 < dx)
        dsc = " ".join(w.text for w in ln if dx <= w.x0 < rx)
        res = " ".join(w.text for w in ln if w.x0 >= rx)
        if not (idc or dsc or res):
            continue
        rows.append(f"{idc or '-'} | {dsc} | {res}")
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
        words.append(Word(f[11].strip(), float(f[6]), float(f[7]), float(f[9])))
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
                words = [Word(w["text"], w["x0"], w["top"], w["bottom"] - w["top"]) for w in ws]
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
