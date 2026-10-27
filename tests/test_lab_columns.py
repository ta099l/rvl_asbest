"""Lab tables with extra columns, register status, duplicate codes and sign-off (fictional data only)."""
import os
import sqlite3
import tempfile
import unittest

from ai.james_ai.linker import Sample, link, parse_report
from james.store import Store

REG = [
    Sample("M01", "B01", "Engine room, exhaust pipe", "Exhaust pipe", "Insulation", "white", "F-012", deck="Deck 2"),
    Sample("M02", "B02", "Accommodation, cabin 3.04", "Floor", "Floor tile", "beige", "F-018", deck="Deck 3"),
    Sample("M05", "B10", "Void space behind panel", "Pipe", "Pipe insulation", "", "",
           deck="Deck 1", status="not sampled", restriction="No access: welded hatch"),
]
TEXT = "\n".join([
    "Report: L-TEST-1", "Project: 26-TST",
    "Columns: Sample No. | Description | AnalysisMethod | AnalysisResult | CertificateNumber",
    "---",
    "M01 | White insulation | NEN 5896 | Chrysotile 10% | C-0001",
    "M02 | Floor tile | NEN 5896 | Not detected |",
])


class ColumnsInText(unittest.TestCase):
    def test_named_columns_keep_extra_fields_apart(self):
        _, rows = parse_report(TEXT)
        self.assertEqual((rows[0].raw_id, rows[0].desc, rows[0].result), ("M01", "White insulation", "Chrysotile 10%"))
        self.assertEqual(rows[0].extra, {"method": "NEN 5896", "certificate": "C-0001"})
        self.assertEqual(rows[1].extra["certificate"], "")

    def test_without_columns_line_nothing_changes(self):
        _, rows = parse_report("---\nM01 | White insulation | Chrysotile 10% | extra")
        self.assertEqual(rows[0].result, "Chrysotile 10% | extra")
        self.assertEqual(rows[0].extra, {})

    def test_links_are_the_same_with_or_without_extra_columns(self):
        plain = "---\nM01 | White insulation | Chrysotile 10%\nM02 | Floor tile | Not detected"
        a = [p.sample_id for p in link("", REG[:2], plain).proposals]
        b = [p.sample_id for p in link("", REG[:2], TEXT).proposals]
        self.assertEqual(a, b)


class StoreFields(unittest.TestCase):
    def setUp(self):
        self.st = Store()
        self.oid = self.st.add_object("Test ship", "Ship", "IMO 0000000", "Test yard", "26-TST", REG)
        self.rid = self.st.ingest_report(self.oid, "Lab 1", TEXT)
        self.addCleanup(self.st.db.close)

    def test_certificate_and_method_are_stored(self):
        r = self.st.rows(self.rid)[0]
        self.assertEqual((r["certificate"], r["method"]), ("C-0001", "NEN 5896"))

    def test_register_keeps_deck_and_status(self):
        reg = {s.id: s for s in self.st.register(self.oid)}
        self.assertEqual(reg["M01"].deck, "Deck 2")
        self.assertEqual(reg["M05"].status, "not sampled")

    def test_not_sampled_place_is_a_limitation_not_a_missing_result(self):
        self.assertEqual([s.id for s in self.st.limitations(self.oid)], ["M05"])
        self.assertNotIn("M05", [s.id for s in self.st.sampled(self.oid)])
        self.st.decide(self.rid, 0, "approved", by="T. Inspector")
        self.st.decide(self.rid, 1, "approved", by="T. Inspector")
        self.assertFalse(any("M05" in i for i in self.st.draft_report(self.rid)["open_items"]))

    def test_a_lab_result_cannot_be_linked_to_a_place_that_was_not_sampled(self):
        rid = self.st.ingest_report(self.oid, "Lab 2", "---\nM05 | Pipe insulation, void space | Chrysotile 5%")
        self.assertIsNone(self.st.rows(rid)[0]["proposed_code"])
        with self.assertRaises(ValueError):
            self.st.decide(rid, 0, "corrected", by="T. Inspector", sample_code="M05")

    def test_duplicate_codes_in_the_register_are_refused(self):
        with self.assertRaises(ValueError) as e:
            self.st.add_object("Ship 2", "Ship", "", "Yard", "26-TST", [REG[0], REG[0]])
        self.assertIn("M01", str(e.exception))

    def test_signing_needs_every_line_decided_and_records_open_items(self):
        with self.assertRaises(ValueError):
            self.st.sign(self.rid, "T. Inspector", [])
        self.st.decide(self.rid, 0, "approved", by="T. Inspector")
        self.st.decide(self.rid, 1, "rejected", by="T. Inspector")
        with self.assertRaises(ValueError):
            self.st.sign(self.rid, " ", [])
        self.st.sign(self.rid, "T. Inspector", ["M02 has no photo"])
        self.assertEqual(self.st.signoff(self.rid)["open_items"], ["M02 has no photo"])


class PdfWithExtraColumns(unittest.TestCase):
    """A lab table laid out like the real IHM lab tables: the extractor keeps every column."""

    def test_extra_columns_come_out_named(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from james.extract import extract_lab_text
        path = os.path.join(tempfile.mkdtemp(), "lab.pdf")
        c = canvas.Canvas(path, pagesize=A4)
        c.setFont("Helvetica", 11)
        c.drawString(40, 800, "Report: L-TEST-2")
        xs = [40, 110, 230, 330, 440]
        c.setFont("Helvetica-Bold", 10)
        for x, h in zip(xs, ["Sample No.", "Description", "Analysis Method", "Result", "Certificate Number"]):
            c.drawString(x, 760, h)
        c.setFont("Helvetica", 10)
        for y, cells in [(740, ["M01", "White insulation", "NEN 5896", "Chrysotile 10%", "C-0001"]),
                         (722, ["M02", "Floor tile", "NEN 5896", "Not detected", "C-0002"])]:
            for x, t in zip(xs, cells):
                c.drawString(x, y, t)
        c.save()
        text = extract_lab_text(path).text
        self.assertIn("Columns: id | description | method | result | certificate", text)
        _, rows = parse_report(text)
        self.assertEqual([(r.raw_id, r.result, r.extra["certificate"]) for r in rows],
                         [("M01", "Chrysotile 10%", "C-0001"), ("M02", "Not detected", "C-0002")])


class OldDatabaseFile(unittest.TestCase):
    def test_a_database_from_before_the_new_columns_is_upgraded(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "old.db")
        db = sqlite3.connect(path)
        db.executescript("""
            CREATE TABLE object (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, ref TEXT,
                                 site TEXT NOT NULL, project TEXT NOT NULL);
            CREATE TABLE sample (object_id INTEGER NOT NULL, code TEXT NOT NULL, source TEXT, location TEXT NOT NULL,
                                 part TEXT, material TEXT, notes TEXT, photo TEXT, PRIMARY KEY (object_id, code));
            CREATE TABLE lab_report (id INTEGER PRIMARY KEY, object_id INTEGER NOT NULL, label TEXT NOT NULL,
                                     report_ref TEXT, lab TEXT, header_project TEXT, raw_text TEXT NOT NULL,
                                     ingested_at TEXT NOT NULL);
            CREATE TABLE lab_row (id INTEGER PRIMARY KEY, report_id INTEGER NOT NULL, idx INTEGER NOT NULL,
                                  raw_line TEXT NOT NULL, raw_id TEXT, description TEXT, result TEXT,
                                  proposed_code TEXT, confidence TEXT, reason TEXT NOT NULL, flags TEXT NOT NULL);
            INSERT INTO object VALUES (1, 'Old ship', 'Ship', '', 'Yard', '26-OLD');
            INSERT INTO sample VALUES (1, 'M01', 'B01', 'Engine room', '', 'Insulation', '', '');
        """)
        db.commit()
        db.close()
        st = Store(path)
        self.assertEqual(st.register(1)[0].status, "sampled")
        rid = st.ingest_report(1, "Lab", TEXT)
        self.assertEqual(st.rows(rid)[0]["certificate"], "C-0001")
        st.db.close()


if __name__ == "__main__":
    unittest.main()
