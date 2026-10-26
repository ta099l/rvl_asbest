import os
from difflib import SequenceMatcher
import shutil
import tempfile
import unittest

from ai.james_ai.demo_data import SHIP
from ai.james_ai.evaluate import evaluate
from james.extract import extract_lab_text
from ai.james_ai.linker import link, parse_report
from tests.helpers import make_scan_pdf, make_text_pdf

TEXT = SHIP["reports"]["b1"]["text"]
TRUTH = SHIP["reports"]["b1"]["truth"]


class PdfWithTextLayer(unittest.TestCase):
    def test_same_rows_as_the_source_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lab.pdf")
            make_text_pdf(path, TEXT)
            ex = extract_lab_text(path)
        self.assertEqual(ex.method, "text")
        head, rows = parse_report(ex.text)
        _, want = parse_report(TEXT)
        self.assertEqual(head["project"], "26-3VK")
        self.assertEqual([(r.raw_id, r.desc, r.result) for r in rows],
                         [(r.raw_id, r.desc, r.result) for r in want])

    def test_links_match_text_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lab.pdf")
            make_text_pdf(path, TEXT)
            ex = extract_lab_text(path)
        a = link(SHIP["project"], SHIP["samples"], ex.text)
        b = link(SHIP["project"], SHIP["samples"], TEXT)
        self.assertEqual([p.sample_id for p in a.proposals], [p.sample_id for p in b.proposals])


@unittest.skipUnless(shutil.which("tesseract"), "tesseract not installed")
class ScannedPdf(unittest.TestCase):
    """A scan has no text layer. OCR can misread characters; the safety rule is that a
    misread must never turn into a WRONG link (a missing link is acceptable)."""

    def test_scan_goes_through_ocr_and_never_yields_a_wrong_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "scan.pdf")
            make_scan_pdf(path, TEXT)
            ex = extract_lab_text(path)
        self.assertEqual(ex.method, "ocr")
        self.assertTrue(any("OCR" in n for n in ex.notes))
        run = link(SHIP["project"], SHIP["samples"], ex.text)
        # OCR can add, drop or merge rows, so match each OCR row to its source row by
        # description instead of by position. A row that matches nothing has no right answer.
        src = [r for r in parse_report(TEXT)[1]]
        truth = {}
        for p in run.proposals:
            best = max(src, key=lambda r: SequenceMatcher(None, p.row.desc.lower(), r.desc.lower()).ratio())
            ok = SequenceMatcher(None, p.row.desc.lower(), best.desc.lower()).ratio() >= 0.7
            truth[p.index] = TRUTH[best.index] if ok else None
        res = evaluate(run, truth)
        print("\n[scan test] OCR result vs reference:", res)
        print(ex.text)
        self.assertEqual(res["wrong"], 0)


if __name__ == "__main__":
    unittest.main()
