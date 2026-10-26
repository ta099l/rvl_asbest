import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai.james_ai.score import OUTCOMES, load_cases, main, report, score_set

# Tiny made-up set: one line per outcome. The real hold-out set is never used in tests.
REGISTER = [
    {"code": "A-01", "location": "Engine room", "material": "Gasket", "colour": "black"},
    {"code": "A-02", "location": "Pump room", "material": "Pump packing", "colour": "grey"},
]
DATA = {
    "registers": {"tiny": REGISTER},
    "sets": {"dev": {"register": "tiny"}, "hold": {"register": "tiny"}},
    "cases": [
        {"id": "t1", "set": "dev", "tag": "clean", "line": "A-01 | Gasket, engine room | x", "truth": "A-01"},
        {"id": "t2", "set": "dev", "tag": "planted", "line": "A-02 | Pump packing, pump room | x", "truth": "A-01"},
        {"id": "t3", "set": "dev", "tag": "unknown ID", "line": "A-09 | Hatch seal | x", "truth": None},
        {"id": "t4", "set": "dev", "tag": "missed", "line": "A-09 | Hatch seal | x", "truth": "A-02"},
        {"id": "h1", "set": "hold", "tag": "clean", "line": "A-02 | Pump packing, pump room | x", "truth": "A-02"},
    ],
}


class ScoreSet(unittest.TestCase):
    def test_each_outcome_is_counted(self):
        r = score_set(DATA, "dev")
        self.assertEqual(r["counts"], {k: 1 for k in OUTCOMES})
        self.assertEqual([c["outcome"] for c in r["cases"]],
                         ["correct", "wrong", "abstained_ok", "abstained_missed"])

    def test_only_cases_of_the_set_are_used(self):
        self.assertEqual(score_set(DATA, "dev")["lines"], 4)
        self.assertEqual(score_set(DATA, "hold")["lines"], 1)

    def test_report_lists_wrong_links_first(self):
        text = report(score_set(DATA, "dev"))
        self.assertLess(text.index("t2"), text.index("t4"))
        self.assertNotIn("t1 ", text.split("Not right")[1])   # correct lines are not listed
        self.assertNotIn("t3 ", text.split("Not right")[1])   # nor correct abstentions

    def test_real_cases_file_loads_with_every_set(self):
        data = load_cases()
        for name in ("dev", "dev2"):
            r = score_set(data, name)
            self.assertEqual(sum(r["counts"].values()), r["lines"])
        self.assertEqual(set(data["sets"]), {"dev", "dev2", "hold"})


class DevSetsStaySafe(unittest.TestCase):
    """Regression guard on the real dev sets (never hold): the rules make no wrong links."""

    def test_no_wrong_links_on_dev_and_dev2(self):
        data = load_cases()
        for name in ("dev", "dev2"):
            self.assertEqual(score_set(data, name)["counts"]["wrong"], 0, name)

    def test_unregistered_code_gets_no_link_even_if_the_description_matches(self):
        # e11: M3 is not in the register, which uses M codes; the description fits M02.
        data = load_cases()
        e11 = next(c for c in data["cases"] if c["id"] == "e11")
        self.assertIsNone(e11["truth"])
        case = next(c for c in score_set(data, "dev2")["cases"] if c["id"] == "e11")
        self.assertEqual((case["proposed"], case["outcome"]), (None, "abstained_ok"))
        self.assertIn("not registered", case["reason"])


class Command(unittest.TestCase):
    def run_main(self, argv):
        with tempfile.TemporaryDirectory() as d:
            cases = Path(d) / "cases.json"
            cases.write_text(json.dumps(DATA))
            runs = Path(d) / "runs"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(argv, cases_file=cases, runs_dir=runs)
            saved = [json.loads(p.read_text()) for p in sorted(runs.glob("*.json"))] if runs.exists() else []
            return code, out.getvalue(), saved

    def test_dev_prints_details_and_saves_nothing(self):
        code, out, saved = self.run_main(["--set", "dev"])
        self.assertEqual(code, 0)
        self.assertIn("Not right", out)
        self.assertEqual(saved, [])

    def test_hold_warns_shows_totals_only_and_saves_the_run(self):
        code, out, saved = self.run_main(["--set", "hold"])
        self.assertEqual(code, 0)
        self.assertIn("WARNING: hold-out set", out)
        self.assertNotIn("Pump packing", out)              # no line details on screen
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["set"], "hold")
        self.assertEqual(saved[0]["counts"]["correct"], 1)
        self.assertIn("run_at", saved[0])
        self.assertIn("commit", saved[0])

    def test_unknown_set_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_main(["--set", "nope"])


if __name__ == "__main__":
    unittest.main()
