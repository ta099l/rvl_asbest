import contextlib
import io
import unittest

import run_demo
from ai.james_ai.ai_step import ReplayClient
from ai.james_ai.hybrid import hybrid


def keyboard(*keys):
    """Stand-in for input(): returns the given keys in order, then acts like Ctrl-D."""
    it = iter(keys)

    def ask(prompt):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    return ask


def run_flow(*keys):
    lines = []
    store = run_demo.flow(keyboard(*keys), out=lambda *a, sep=" ": lines.append(sep.join(map(str, a))))
    return store, "\n".join(lines)


def decisions(store):
    return [(e["idx"] + 1, e["state"], e["sample_code"]) for e in store.audit_log()]


FULL = ("Demo Inspector", "a", "a", "a", "a", "a",
        "c", "S-06", "steering gear room", "r", "not in register", "a", "c", "S-08", "checked photo", "a")


class DemoReplay(unittest.TestCase):
    def test_stand_in_answers_still_match_the_prompt(self):
        run = hybrid(run_demo.ship_request(), ReplayClient(run_demo.DEMO_REPLAY))
        self.assertEqual(run.sent, [2, 3, 4, 8])
        self.assertEqual(run.ai.problems, [])                  # else the demo silently shows rules only
        self.assertEqual(run.source[8], "disagree")


class Flow(unittest.TestCase):
    def test_full_session(self):
        store, text = run_flow(*FULL)
        self.assertEqual(decisions(store), [
            (1, "approved", "S-01"), (2, "approved", "S-02"), (3, "approved", "S-03"),
            (4, "approved", "S-04"), (5, "approved", "S-05"), (6, "corrected", "S-06"),
            (7, "rejected", None), (8, "corrected", "S-08"), (9, "approved", "S-07")])
        self.assertTrue(all(e["decided_by"] == "Demo Inspector" for e in store.audit_log()))
        self.assertIn("Nothing is proposed for this line, so it cannot be approved", text)  # line 8: 'a' refused
        self.assertIn("== 3. Draft report", text)
        self.assertIn("== 4. Audit log", text)

    def test_no_link_line_offers_only_correct_reject_skip(self):
        asked = []
        keys = keyboard("Ann", "a", "a", "a", "a", "a", "r", "no")

        def ask(prompt):
            asked.append(prompt)
            return keys(prompt)
        store = run_demo.flow(ask, out=lambda *a, sep=" ": None)
        self.assertEqual(asked[6], "  [c]orrect  [r]eject  [s]kip > ")   # line 6 has no proposal
        self.assertEqual(decisions(store)[-1], (6, "rejected", None))

    def test_a_name_is_required(self):
        _, text = run_flow("", "  ", "Ann")
        self.assertIn("A name is required", text)

    def test_unknown_code_is_asked_again(self):
        store, text = run_flow("Ann", "c", "S-99", "c", "S-01", "fine")
        self.assertIn("'S-99' is not in the register", text)
        self.assertEqual(decisions(store), [(1, "corrected", "S-01")])

    def test_unknown_key_is_asked_again(self):
        store, text = run_flow("Ann", "x", "a")
        self.assertIn("Type a, c, r or s.", text)
        self.assertEqual(decisions(store), [(1, "approved", "S-01")])

    def test_input_ending_leaves_lines_open_and_still_reports(self):
        store, text = run_flow("Ann", "a", "s")
        self.assertEqual(decisions(store), [(1, "approved", "S-01")])
        self.assertIn("Input ended", text)
        self.assertIn("not yet reviewed", text)                 # open items in the draft report

    def test_without_ai_answers_the_flow_still_works(self):
        lines = []
        store = run_demo.flow(keyboard("Ann", "a"), out=lambda *a, sep=" ": lines.append(sep.join(map(str, a))),
                              replay=None)
        self.assertIn("AI not used", "\n".join(lines))
        self.assertEqual(decisions(store), [(1, "approved", "S-01")])


class Classic(unittest.TestCase):
    def test_scripted_walk_through_still_runs(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_demo.main([])
        self.assertIn("== 5. Audit log", out.getvalue())
        self.assertIn("S-03 v2: Chrysotile 35% (re-analysis)   <- result changed", out.getvalue())


if __name__ == "__main__":
    unittest.main()
