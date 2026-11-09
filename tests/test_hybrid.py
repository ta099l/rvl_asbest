import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai.james_ai.ai_step import FailingClient, ReplayClient, build_prompt, prompt_key
from ai.james_ai.compare import case_request, compare_set, export_prompts, main
from ai.james_ai.contract import response_problems
from ai.james_ai.demo_data import SHIP
from ai.james_ai.hybrid import hybrid
from ai.james_ai.linker import link
from ai.james_ai.score import load_cases, score_set
from tests.test_score import DATA as TINY

REGISTER = load_cases()["registers"]["ship_s_codes"]


def row(n, raw_id, description):
    return {"n": n, "raw_id": raw_id, "description": description, "result": "Asbestos not detected"}


# 1 high (stays), 2 medium (sent), 3 Dutch without ID (sent), 4 ID conflict (stays)
REQUEST = {"report_id": "LAB-TEST-1", "register": REGISTER, "rows": [
    row(1, "S-01", "Insulation wrap, engine room bulkhead"),
    row(2, "S02", "Exhaust pipe lagging, engine room"),
    row(3, None, "Pompafdichting, pompruimte"),
    row(4, "S-05", "Flange gasket, steering gear room"),
]}


class AnswerClient:
    """Answers the two sent lines with the given samples, and remembers the prompt."""

    def __init__(self, *samples):
        self.samples, self.prompt = samples, None

    def complete(self, text):
        self.prompt = text
        return json.dumps({"proposals": [
            {"n": i + 1, "sample": s, "confidence": "medium" if s else None, "reason": "test answer"}
            for i, s in enumerate(self.samples)]})


def samples(run):
    return [p["sample"] for p in run.response["proposals"]]


class WhatGoesToTheAI(unittest.TestCase):
    def test_only_unsettled_lines_are_sent(self):
        client = AnswerClient("S-02", "S-08")
        run = hybrid(REQUEST, client)
        self.assertEqual(run.sent, [2, 3])
        lab_lines = client.prompt.split("LAB LINES")[1]
        self.assertIn("1. S02 | Exhaust pipe lagging", lab_lines)
        self.assertIn("2. - | Pompafdichting", lab_lines)
        self.assertNotIn("Insulation wrap", lab_lines)      # high-confidence rule link
        self.assertNotIn("Flange gasket", lab_lines)        # conflicting evidence

    def test_two_equal_candidates_are_not_sent_to_the_ai(self):
        # dev case d11: "Gasket" fits S-03 and S-06 equally. The AI picked S-03 and was wrong.
        req = {"report_id": "LAB-TEST-2", "register": REGISTER, "rows": [row(1, None, "Gasket")]}
        client = AnswerClient("S-03")
        run = hybrid(req, client)
        self.assertEqual(run.sent, [])
        self.assertIsNone(client.prompt)                    # the AI was never asked
        self.assertEqual(samples(run), [None])
        self.assertIn("equally", run.response["proposals"][0]["reason"])

    def test_nothing_to_send_means_no_ai_call(self):
        client = AnswerClient()
        run = hybrid(dict(REQUEST, rows=[REQUEST["rows"][0]]), client)
        self.assertIsNone(client.prompt)
        self.assertEqual(samples(run), ["S-01"])

    def test_unregistered_code_is_never_sent(self):
        p = link("", SHIP["samples"], "---\nS-09 | Hatch coaming seal, hold 2 | X").proposals[0]
        self.assertIn("row:0:unregistered", p.flags)
        client = AnswerClient("S-04")
        run = hybrid(dict(REQUEST, rows=[row(1, "S-09", "Hatch coaming seal, hold 2")]), client)
        self.assertIsNone(client.prompt)
        self.assertEqual(samples(run), [None])


class Merging(unittest.TestCase):
    def test_agree_and_fill_in(self):
        run = hybrid(REQUEST, AnswerClient("S-02", "S-08"))
        self.assertEqual(samples(run), ["S-01", "S-02", "S-08", None])
        self.assertEqual(run.source, {1: "rules", 2: "both", 3: "ai", 4: "rules"})
        self.assertIn("Rules and AI agree on S-02", run.response["proposals"][1]["reason"])

    def test_disagreement_gives_no_link(self):
        run = hybrid(REQUEST, AnswerClient("S-03", None))
        self.assertEqual(samples(run), ["S-01", None, None, None])
        self.assertEqual(run.source[2], "disagree")
        self.assertIn("Rules say S-02, the AI says S-03", run.response["proposals"][1]["reason"])

    def test_unusable_ai_answer_keeps_the_rules(self):
        run = hybrid(REQUEST, FailingClient())
        self.assertEqual(samples(run), ["S-01", "S-02", None, None])
        self.assertIn("AI not used: not valid JSON", run.response["proposals"][1]["reason"])

    def test_response_always_follows_the_contract(self):
        for client in (AnswerClient("S-02", "S-08"), AnswerClient("S-03", "S-01"), FailingClient()):
            self.assertEqual(response_problems(hybrid(REQUEST, client).response, REQUEST), [])


class Guard(unittest.TestCase):
    def test_ai_sample_already_linked_by_rules_unlinks_both(self):
        run = hybrid(REQUEST, AnswerClient("S-02", "S-01"))   # S-01 is line 1's
        self.assertEqual(samples(run), [None, "S-02", None, None])
        self.assertEqual((run.source[1], run.source[3]), ("guard", "guard"))
        self.assertIn("also proposed for line 3", run.response["proposals"][0]["reason"])

    def test_two_ai_lines_with_one_sample_unlink_both(self):
        req = dict(REQUEST, rows=[row(1, None, "Pompafdichting, pompruimte"),
                                  row(2, None, "Pakking pomp, pompruimte")])
        run = hybrid(req, AnswerClient("S-08", "S-08"))
        self.assertEqual(samples(run), [None, None])


class Pacing(unittest.TestCase):
    def test_waits_between_real_calls_but_not_for_repeated_prompts(self):
        from unittest import mock
        from ai.james_ai import compare
        client = compare.MemoizedClient(compare.PacedClient(AnswerClient("S-02"), 8))
        with mock.patch.object(compare.time, "sleep") as sleep:
            client.complete("prompt A")       # first call: no wait
            client.complete("prompt A")       # same prompt: answered from memory, no wait
            client.complete("prompt B")       # second real call: waits
        sleep.assert_called_once_with(8)


class Compare(unittest.TestCase):
    def test_without_answers_rules_and_hybrid_match_the_rules_score(self):
        data = load_cases()
        for name in ("dev", "dev2", "dev3"):
            r = compare_set(data, name, ReplayClient())
            self.assertEqual(r["counts"]["rules"], score_set(data, name)["counts"])
            self.assertEqual(r["counts"]["hybrid"], r["counts"]["rules"])
            self.assertEqual((r["counts"]["ai"]["correct"], r["counts"]["ai"]["wrong"]), (0, 0))
            self.assertEqual(r["ai_answered"], 0)

    def test_export_then_fill_in_then_compare(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "dev.json"
            # 4 cases but 3 prompts: t3 and t4 have the same line, so the same question
            self.assertEqual(export_prompts(TINY, "dev", path), 3)
            replay = json.loads(path.read_text())
            self.assertIn("t3, t4", [a["report_id"] for a in replay["answers"].values()])
            # keys are the fingerprints of the exact prompts the AI step will send
            req = case_request(TINY["cases"][3], TINY["registers"]["tiny"])
            key = prompt_key(build_prompt(req))
            self.assertIn(key, replay["answers"])
            # paste an answer for case t4, export again: the answer is kept
            replay["answers"][key]["answer"] = {"proposals": [
                {"n": 1, "sample": "A-02", "confidence": "low", "reason": "test"}]}
            path.write_text(json.dumps(replay))
            self.assertEqual(export_prompts(TINY, "dev", path), 2)
            r = compare_set(TINY, "dev", ReplayClient(path))
            self.assertEqual(r["ai_answered"], 2)                 # t3 and t4
            t4 = next(x for x in r["cases"] if x["id"] == "t4")
            self.assertEqual(t4["ai"]["outcome"], "correct")

    def test_hold_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["--set", "hold", "--export-prompts", str(Path(d) / "x.json")])


if __name__ == "__main__":
    unittest.main()
