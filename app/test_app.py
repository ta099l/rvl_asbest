"""Tests for the app service layer (fictional demo data only)."""
import unittest
from app.server import Service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.s = Service()
        self.s.load_demo("b1")

    def rep(self):
        v = self.s.view(None)
        return v["report"], v["report"]["id"]

    def test_labels(self):
        r, _ = self.rep()
        labels = [x["proposal"]["label"] for x in r["rows"]]
        self.assertEqual(labels.count("certain"), 3)
        self.assertEqual(labels.count("none"), 3)

    def test_decision_needs_name(self):
        _, rid = self.rep()
        with self.assertRaises(Exception):
            self.s.decide(rid, 0, "approve", "", None, "")

    def test_approve_fills_chapter9(self):
        _, rid = self.rep()
        self.s.decide(rid, 0, "approve", "Test Inspector", None, "")
        r, _ = self.rep()
        self.assertEqual(len(r["ch9"]), 1)

    def test_no_link_cannot_be_approved(self):
        r, rid = self.rep()
        idx = next(x["idx"] for x in r["rows"] if x["proposal"]["label"] == "none")
        with self.assertRaises(Exception):
            self.s.decide(rid, idx, "approve", "Test Inspector", None, "")


if __name__ == "__main__":
    unittest.main()
