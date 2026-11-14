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


# ---------------------------------------------------------------------------
# Dutch two-table layout: an overview table that ties the
# lab's own ID to our sample code ("Uw referentie"), and one or more results
# tables keyed by the lab's ID only. Ruled tables, read with pdfplumber's
# table finder. Only the table structure is used here; tests use invented data.
# ---------------------------------------------------------------------------

def _norm(cell) -> str:
    """Cell text with line breaks kept, pipes made safe for the 'a | b | c' row format."""
    return (cell or "").replace("|", "/").strip()


def _flat(cell) -> str:
    return re.sub(r"\s+", " ", _norm(cell)).strip()


def _key(cell) -> str:
    """Lab ID as a join key. 'X-AB-8 015', 'X-AB-8\\n015' and 'X-AB-8 15' are one ID:
    the lab sometimes drops leading zeros in one table but not the other."""
    parts = _norm(cell).upper().split()
    if len(parts) > 1 and parts[-1].isdigit():      # series, then the number on its own
        return f"{''.join(parts[:-1])}#{int(parts[-1])}"
    return "".join(parts)


def _header(row) -> List[str]:
    return [re.sub(r"[^a-z]", "", (c or "").lower()) for c in row]


def _find(hdr: List[str], test) -> Optional[int]:
    return next((i for i, h in enumerate(hdr) if test(h)), None)


def _summary(test: str, names: List[str], values: List[str], units: List[str]) -> Tuple[str, bool]:
    """One readable result text per sample, and whether the values could be paired safely."""
    if not values:
        return "", True
    if len(units) != len(values):
        units = [units[0]] * len(values) if len(set(units)) == 1 else [""] * len(values)
    vals = [f"{v} {u}".strip() for v, u in zip(values, units)]
    if not names:
        return (f"{test}: " if test else "") + "; ".join(vals), True
    if len(names) != len(values):           # never guess which value belongs to which parameter
        return f"{test}: {len(values)} values for {len(names)} parameters, see the report", False
    if len(vals) > 1 and len(set(vals)) == 1:
        return f"{test}: all {len(vals)} parameters {vals[0]}", True
    return f"{test}: " + "; ".join(f"{n} {v}" for n, v in zip(names, vals)), True


def _two_table_layout(pdf) -> Optional[Tuple[List[str], List[str], List[str]]]:
    """Return (header lines, rows, notes), or None when the report does not have this layout."""
    overview: List[Tuple[str, str, str, str]] = []      # (lab key, lab id, reference cell, method)
    results: dict = {}                                  # lab key -> [result texts]
    shown: dict = {}                                    # lab key -> lab ID as the lab wrote it
    notes: List[str] = []
    kind, idx, width = None, {}, 0
    for page in pdf.pages:
        for table in page.extract_tables():
            if not table or not table[0]:
                continue
            hdr = _header(table[0])
            body = table[1:]
            ref = _find(hdr, lambda h: "uwreferentie" in h)
            res = _find(hdr, lambda h: h.startswith("resultaat"))
            if ref is not None:
                kind, width = "overview", len(hdr)
                idx = {"ref": ref, "method": _find(hdr, lambda h: "analysemethode" in h)}
            elif res is not None:
                kind, width = "results", len(hdr)
                unit = re.search(r"\(([^)]+)\)", table[0][res] or "")
                idx = {"res": res, "param": _find(hdr, lambda h: "parameter" in h),
                       "unit": _find(hdr, lambda h: h.startswith("eenheid")),
                       "remark": _find(hdr, lambda h: h.startswith("opm")),
                       "unit_text": unit.group(1) if unit else ""}
            elif kind and len(hdr) == width:            # a table that runs on from the previous page
                body = table
            else:
                kind = None                             # a legend or remarks table: not ours
                continue
            for row in body:
                if not row or not _flat(row[0]):
                    continue
                if kind == "overview":
                    m = idx["method"]
                    method = ", ".join(ln.strip() for ln in _norm(row[m] if m is not None else "").split("\n")
                                       if ln.strip() and not re.match(r"^\d{2}-\d{2}-\d{4}", ln.strip()))
                    overview.append((_key(row[0]), _flat(row[0]), _norm(row[idx["ref"]]), method))
                else:
                    p = idx["param"]
                    lines = [ln.strip() for ln in _norm(row[p]).split("\n") if ln.strip()] if p is not None else []
                    test = next((ln for ln in lines if not ln.startswith("-")), "")
                    names = [ln.lstrip("- ").strip() for ln in lines if ln.startswith("-")]
                    values = [v.strip() for v in _norm(row[idx["res"]]).split("\n") if v.strip()]
                    u = idx["unit"]
                    units = ([x.strip() for x in _norm(row[u]).split("\n") if x.strip()] if u is not None
                             else [idx["unit_text"]] * len(values))
                    text, paired = _summary(test, names, values, units)
                    r = idx["remark"]
                    mark = _flat(row[r]) if r is not None else ""
                    if mark and mark not in ("-", "--"):
                        text += f" (lab remark {mark})"
                        notes.append(f"Lab ID {_flat(row[0])} has remark {mark}: read the lab's explanation "
                                     "before treating a '<' value as 'not present'.")
                    if not paired:
                        notes.append(f"Lab ID {_flat(row[0])}: values and parameters do not line up, check the report.")
                    results.setdefault(_key(row[0]), []).append(text)
                    shown.setdefault(_key(row[0]), _flat(row[0]))
    if not overview:
        return None

    full = "\n".join(page.extract_text() or "" for page in pdf.pages)
    head: List[str] = []
    m = re.search(r"Analyserapport:\s*(.+)", full)
    if m:
        head.append("Report: " + re.sub(r"\s*/\s*", "/", m.group(1).strip()))
    m = re.search(r"Uw referentie\s*:\s*Project\s+(\S+)", full)
    if m:
        head.append("Project: " + m.group(1))
    m = re.search(r"Datum rapportage\s*:\s*(.+)", full)
    if m:
        head.append("Date: " + m.group(1).strip())
    m = re.search(r"vervangt document\s+([^,]+?)\s*,", full)
    if m:
        old = re.sub(r"\s*/\s*", "/", m.group(1).strip())
        head.append("Replaces: " + old)
        notes.append(f"This report replaces {old}. Results read from the older version are superseded.")
    head.append("Columns: id | description | result | method | remarks")

    rows: List[str] = []
    used = set()
    for key, lab_id, ref, method in overview:
        words = ref.split()
        code = words[0] if words else "-"
        desc = re.sub(r"^Locatie\s*:?\s*", "", " ".join(words[1:]), flags=re.I)
        found = results.get(key, [])
        if found:
            used.add(key)
        else:
            notes.append(f"No result found for {code} (lab ID {lab_id}).")
        rows.append(" | ".join([code, desc, "; ".join(found), method, f"lab ID {lab_id}"]))
    for key, found in results.items():
        if key not in used:                 # a result we cannot tie to a sample code: never guess one
            notes.append(f"A result has a lab ID that is not in the overview table ({shown[key]}). Link it by hand.")
            rows.append(" | ".join(["-", "", "; ".join(found), "", f"lab ID {shown[key]}, not in overview"]))
    return head, rows, notes


def extract_lab_text(pdf_path: str) -> Extraction:
    methods, notes = [], []
    head: List[str] = []
    rows: List[str] = []
    cols = None
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        if all(len(p.extract_words()) >= 5 for p in pdf.pages):
            found = _two_table_layout(pdf)
            if found is not None:
                head, rows, notes = found
                return Extraction(text="\n".join(head + ["---"] + rows), method="text", pages=n, notes=notes)
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
