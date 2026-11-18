"""Sources (bronbladen) and photos in the database, and the upgrade of old database files (fictional data only)."""
import os
import re
import sqlite3
import tempfile
import unittest

from ai.james_ai.linker import Sample
from james.store import SCHEMA, Store

BY = "Test Inspector"


def old_file(sql: str) -> str:
    path = os.path.join(tempfile.mkdtemp(), "old.db")
    db = sqlite3.connect(path)
    db.executescript(sql)
    db.commit()
    db.close()
    return path


def schema_before_sources() -> str:
    """schema.sql as it was before this change: no source and photo tables, no ai_* columns."""
    with open(SCHEMA, encoding="utf-8") as f:
        sql = f.read()
    sql = re.sub(r"\n-- One source \(bron\).*", "\n", sql, flags=re.S)          # drops the source and photo tables
    sql = re.sub(r"\n\s*ai_[a-z_]+\s+[A-Z]+,[^\n]*", "", sql)                  # drops the ai_* columns
    assert "CREATE TABLE source" not in sql and "ai_code" not in sql
    return sql


SAMPLES = """
    INSERT INTO object (id, name, kind, ref, site, project) VALUES (1, 'Old ship (fictitious)', 'Ship', '', 'Yard', '26-OLD');
    INSERT INTO sample (object_id, code, source, location, part, material, notes, photo, quantity, unit) VALUES
        (1, 'MM-1', 'B01', 'Engine room', 'Pipe', 'Insulation', '', 'F-1', '12', 'm'),
        (1, 'MM-2', 'B01', 'Engine room', 'Pipe', 'Insulation', '', '', '99', 'kg'),
        (1, 'HM-1', 'B02', 'Railing', 'Railing', 'Paint', '', 'F-2', '', ''),
        (1, 'PBS-1', '', 'Bridge', 'Window', 'Rubber', '', '', '', '');
"""


class UpgradeYesterdaysFile(unittest.TestCase):
    """A database made by the app before sources and photos existed."""

    def setUp(self):
        self.path = old_file(schema_before_sources() + SAMPLES)

    def test_sources_and_photos_are_made_from_the_old_text_fields(self):
        st = Store(self.path)
        src = st.sources(1)
        self.assertEqual(sorted(src), ["B01", "B02"])              # PBS-1 has no source number
        self.assertEqual((src["B01"]["quantity"], src["B01"]["unit"]), ("12", "m"))   # from the FIRST sample only
        self.assertIsNone(src["B02"]["quantity"])                  # empty stays empty
        photos = {p["photo_no"]: p for p in st.photos(1)}
        self.assertEqual(sorted(photos), ["F-1", "F-2"])
        self.assertEqual((photos["F-1"]["sample_code"], photos["F-1"]["source_no"]), ("MM-1", "B01"))
        self.assertIsNone(photos["F-1"]["stored_name"])            # no file yet: "photo missing"
        self.assertEqual(st.register(1)[0].photo, "F-1")           # nothing deleted from the sample
        st.db.close()

    def test_every_new_row_is_logged_once_and_the_upgrade_is_safe_twice(self):
        st = Store(self.path)
        log = [(e["code"], e["action"], e["changed_by"]) for e in st.register_log(1)]
        self.assertEqual(sorted(log), sorted([("B01", "source added", "James (database upgrade)"),
                                              ("B02", "source added", "James (database upgrade)"),
                                              ("F-1", "photo added", "James (database upgrade)"),
                                              ("F-2", "photo added", "James (database upgrade)")]))
        st.db.close()
        st2 = Store(self.path)                                      # opened again: nothing new
        self.assertEqual(len(st2.register_log(1)), 4)
        self.assertEqual(len(st2.sources(1)), 2)
        self.assertEqual(len(st2.photos(1)), 2)
        st2.db.close()

    def test_lab_rows_get_the_ai_columns(self):
        st = Store(self.path)
        cols = {r["name"] for r in st.db.execute("PRAGMA table_info(lab_row)")}
        self.assertTrue({"ai_code", "ai_confidence", "ai_reason", "ai_source", "ai_prompt_version", "ai_sent"} <= cols)
        st.db.close()

    def test_an_unlinked_photo_is_not_brought_back_by_a_second_upgrade(self):
        st = Store(self.path)
        st.update_sample(1, "MM-1", {"photo": "F-9"}, BY)
        st.db.close()
        st2 = Store(self.path)
        photos = {p["photo_no"]: p["sample_code"] for p in st2.photos(1)}
        self.assertEqual(photos, {"F-1": None, "F-2": "HM-1", "F-9": "MM-1"})    # F-1 kept, unlinked
        st2.db.close()


class UpgradeVeryOldFile(unittest.TestCase):
    """The oldest layout (same pattern as tests/test_lab_columns.py): no quantity, no register_log."""

    def test_opens_and_gets_sources_and_photos(self):
        path = old_file("""
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
            INSERT INTO sample VALUES (1, 'M01', 'B01', 'Engine room', '', 'Insulation', '', 'F-001');
        """)
        st = Store(path)
        self.assertEqual(list(st.sources(1)), ["B01"])
        self.assertEqual([p["photo_no"] for p in st.photos(1)], ["F-001"])
        st.db.close()


class SourcesInUse(unittest.TestCase):
    def setUp(self):
        self.st = Store(group_of=lambda code: "asbestos" if code.startswith("MM") else None)
        self.oid = self.st.add_object("MV Test (fictitious)", "Ship", "", "Yard", "J-1", [
            Sample("MM-1", "B01", "Engine room", "Pipe", "Insulation", photo="F-1", quantity="12", unit="m")])

    def test_new_project_gets_its_sources_and_photos(self):
        self.assertEqual(self.st.sources(self.oid)["B01"]["substance_group"], "asbestos")
        self.assertEqual([p["photo_no"] for p in self.st.photos(self.oid)], ["F-1"])

    def test_source_changes_are_checked_and_logged(self):
        self.st.update_source(self.oid, "B01", {"condition": "Damaged", "assessment": "PCHM"}, BY)
        e = self.st.register_log(self.oid)[-1]
        self.assertEqual((e["code"], e["action"], e["changed_by"]), ("B01", "source changed", BY))
        self.assertIn("condition: – -> Damaged", e["detail"])
        with self.assertRaises(ValueError):
            self.st.update_source(self.oid, "B01", {"assessment": "probably fine"}, BY)
        with self.assertRaises(ValueError):
            self.st.update_source(self.oid, "B01", {"source_no": "B02"}, BY)        # the number never changes
        with self.assertRaises(ValueError):
            self.st.update_source(self.oid, "B01", {"condition": "Good"}, "")        # signed
        with self.assertRaises(ValueError):
            self.st.update_source(self.oid, "B99", {"condition": "Good"}, BY)

    def test_new_source_and_photo_from_a_registered_sample(self):
        self.st.add_sample(self.oid, Sample("MM-2", "B02", "Bridge", "Window", "Kit", photo="F-2"), BY)
        self.assertIn("B02", self.st.sources(self.oid))
        actions = [(e["code"], e["action"]) for e in self.st.register_log(self.oid)]
        self.assertIn(("B02", "source added"), actions)
        self.assertIn(("F-2", "photo added"), actions)

    def test_what_marks_lab_proposals_out_of_date(self):
        """Changing a sample's own source number or location still marks proposals out of date;
        a condition or photo change does not (the linker never reads them)."""
        old = "2000-01-01 00:00:00"
        self.assertIsNone(self.st.register_changed_at(self.oid))            # only source/photo lines so far
        self.st.update_source(self.oid, "B01", {"condition": "Damaged"}, BY)
        self.assertIsNone(self.st.register_changed_at(self.oid))            # a condition does not count
        self.st.update_sample(self.oid, "MM-1", {"source": "B05"}, BY)
        self.assertIsNotNone(self.st.register_changed_at(self.oid))         # the sample's source number does
        self.st.db.execute("UPDATE register_log SET changed_at=?", (old,))
        self.st.update_sample(self.oid, "MM-1", {"location": "Engine room, port side"}, BY)
        self.assertNotEqual(self.st.register_changed_at(self.oid), old)     # and so does its location

    def test_a_photo_change_alone_does_not_count(self):
        self.st.db.execute("DELETE FROM register_log")
        self.st.update_source(self.oid, "B01", {"condition": "Weathered"}, BY)
        self.st._sync_sample(self.oid, Sample("MM-1", "B01", "Engine room", "Pipe", "Insulation", photo="F-3"), BY)
        self.assertIsNone(self.st.register_changed_at(self.oid))


class SavedAiProposals(unittest.TestCase):
    def test_saved_only_when_every_line_has_one(self):
        st = Store()
        oid = st.add_object("MV Test (fictitious)", "Ship", "", "Yard", "J-1",
                            [Sample("MM-1", "B01", "Engine room", "Pipe", "Insulation")])
        rid = st.ingest_report(oid, "Lab", "---\nMM-1 | Pipe insulation | Chrysotile 5%\nMM-2 | Tile | none")
        self.assertIsNone(st.saved_ai(rid))                                # read before saving: read again
        st.save_ai(rid, [{"idx": 0, "sample": "MM-1", "confidence": "high", "reason": "r", "source": "rules", "sent": False},
                         {"idx": 1, "sample": None, "confidence": "low", "reason": "r2", "source": "ai", "sent": True}], "v3")
        rows = st.saved_ai(rid)
        self.assertEqual([(r["ai_code"], r["ai_source"], r["ai_sent"], r["ai_prompt_version"]) for r in rows],
                         [("MM-1", "rules", 0, "v3"), (None, "ai", 1, "v3")])


if __name__ == "__main__":
    unittest.main()
