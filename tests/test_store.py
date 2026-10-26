import unittest

from ai.james_ai.demo_data import SHIP
from james.store import Store


def new_store():
    s = Store()
    oid = s.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"], SHIP["project"], SHIP["samples"])
    return s, oid


class Review(unittest.TestCase):
    def setUp(self):
        self.s, self.oid = new_store()
        self.rid = self.s.ingest_report(self.oid, "Lab report 1", SHIP["reports"]["b1"]["text"])

    def test_ingest_stores_proposals_and_reasons(self):
        rows = self.s.rows(self.rid)
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[2]["proposed_code"], "S-03")
        self.assertIsNone(rows[5]["proposed_code"])
        self.assertTrue(all(r["reason"] for r in rows))

    def test_cannot_approve_without_a_proposal(self):
        with self.assertRaises(ValueError):
            self.s.decide(self.rid, 5, "approved", by="Inspector A")

    def test_decision_needs_a_named_inspector(self):
        with self.assertRaises(ValueError):
            self.s.decide(self.rid, 0, "approved", by="  ")

    def test_correct_needs_a_real_sample(self):
        with self.assertRaises(ValueError):
            self.s.decide(self.rid, 5, "corrected", by="Inspector A", sample_code="S-99")

    def test_unknown_row_and_state(self):
        with self.assertRaises(ValueError):
            self.s.decide(self.rid, 99, "rejected", by="Inspector A")
        with self.assertRaises(ValueError):
            self.s.decide(self.rid, 0, "maybe", by="Inspector A")

    def test_newer_decision_replaces_older_but_log_keeps_both(self):
        self.s.decide(self.rid, 0, "approved", by="Inspector A")
        self.s.decide(self.rid, 0, "rejected", by="Inspector B", note="checked photo, wrong")
        cur = self.s.current_decisions(self.rid)[0]
        self.assertEqual((cur["state"], cur["decided_by"]), ("rejected", "Inspector B"))
        self.assertEqual(len(self.s.audit_log(self.rid)), 2)

    def test_draft_report_only_contains_approved_links(self):
        self.s.decide(self.rid, 0, "approved", by="Inspector A")
        self.s.decide(self.rid, 5, "corrected", by="Inspector A", sample_code="S-06", note="photo IMG_0133")
        d = self.s.draft_report(self.rid)
        self.assertEqual({x["sample"] for x in d["linked"]}, {"S-01", "S-06"})
        self.assertEqual(d["status"], "DRAFT")
        self.assertIn("Lab row 2 (S02): not yet reviewed", d["open_items"])
        self.assertIn("Sample S-02 (Engine room, main engine exhaust) has no linked result", d["open_items"])

    def test_report_is_complete_only_when_everything_is_resolved(self):
        for i, r in enumerate(self.s.rows(self.rid)):
            if r["proposed_code"]:
                self.s.decide(self.rid, i, "approved", by="Inspector A")
            elif i == 5:
                self.s.decide(self.rid, i, "corrected", by="Inspector A", sample_code="S-06")
            else:
                self.s.decide(self.rid, i, "rejected", by="Inspector A", note="S-09 is not in the register")
        d = self.s.draft_report(self.rid)
        # lab row 7 (S-09) stays an open item because the inspector decided no link
        self.assertEqual(d["status"], "DRAFT")
        self.assertEqual(d["open_items"], ["Lab row 7 (S-09): inspector decided no link"])
        self.assertEqual(len(d["linked"]), 8)


class AssetFile(unittest.TestCase):
    def test_versions_keep_history_and_flag_changes(self):
        s, oid = new_store()
        r1 = s.ingest_report(oid, "Lab report 1", SHIP["reports"]["b1"]["text"])
        s.decide(r1, 2, "approved", by="Inspector A")          # S-03, Chrysotile 40%
        self.assertEqual(s.save_asset_version(oid, r1, "Inspector A"), 1)

        r2 = s.ingest_report(oid, "Lab report 2", SHIP["reports"]["b2"]["text"])
        s.decide(r2, 0, "approved", by="Inspector A")          # S-06 new
        s.decide(r2, 1, "approved", by="Inspector A")          # S-03 re-analysis, 35%
        self.assertEqual(s.save_asset_version(oid, r2, "Inspector A"), 2)

        a = s.asset(oid)
        self.assertEqual(a["version"], 2)
        h = a["samples"]["S-03"]["history"]
        self.assertEqual([x["version"] for x in h], [1, 2])
        self.assertEqual([x["changed"] for x in h], [False, True])
        self.assertIn("40%", h[0]["result"])
        self.assertIn("35%", h[1]["result"])
        self.assertEqual(len(a["samples"]["S-06"]["history"]), 1)

    def test_cannot_save_empty_version(self):
        s, oid = new_store()
        r1 = s.ingest_report(oid, "Lab report 1", SHIP["reports"]["b1"]["text"])
        with self.assertRaises(ValueError):
            s.save_asset_version(oid, r1, "Inspector A")


if __name__ == "__main__":
    unittest.main()
