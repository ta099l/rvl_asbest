import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from ai.james_ai.ai_step import (FailingClient, ReplayClient, build_prompt, load_template, main,
                                 prompt_key, propose)
from ai.james_ai.contract import ContractError, response_problems

ROOT = Path(__file__).resolve().parents[1]
REQUEST = json.loads((ROOT / "contract" / "examples" / "request.json").read_text())
GOOD = json.loads((ROOT / "contract" / "examples" / "response.json").read_text())
EXAMPLE_REPLAY = ROOT / "ai" / "replays" / "example.json"


class FixedClient:
    """Returns one given answer and remembers the prompt."""

    def __init__(self, answer):
        self.answer, self.prompt = answer, None

    def complete(self, text):
        self.prompt = text
        return self.answer


class BrokenClient:
    def complete(self, text):
        raise TimeoutError("no answer within 30 s")


def assert_all_no_link(test, run, fragment):
    test.assertTrue(run.problems)
    test.assertEqual([p["n"] for p in run.response["proposals"]], [1, 2, 3])
    for p in run.response["proposals"]:
        test.assertIsNone(p["sample"])
        test.assertIn(fragment, p["reason"])
    test.assertEqual(response_problems(run.response, REQUEST), [])


class Prompt(unittest.TestCase):
    def test_v1_template_has_both_slots_and_the_answer_format(self):
        t = load_template("v1_baseline")
        self.assertIn("{{REGISTER}}", t)
        self.assertIn('{"proposals":', t)

    def test_prompt_is_filled(self):
        text = build_prompt(REQUEST)
        self.assertNotIn("{{", text)
        self.assertIn("S-02 | Engine room, main engine exhaust | Pipe lagging | white", text)
        self.assertIn("1. S02 | Exhaust pipe lagging, engine room | Asbestos not detected", text)
        self.assertIn("3. - | Sealant, unknown location", text)   # no ID written as -

    def test_key_changes_with_one_character(self):
        text = build_prompt(REQUEST)
        self.assertEqual(prompt_key(text), prompt_key(build_prompt(REQUEST)))
        self.assertNotEqual(prompt_key(text), prompt_key(text + " "))

    def test_unknown_or_unsafe_version_is_refused(self):
        with self.assertRaises(FileNotFoundError):
            load_template("v99_missing")
        with self.assertRaises(ValueError):
            load_template("../contract/README")

    def test_broken_request_stops_loudly(self):
        req = copy.deepcopy(REQUEST)
        req["rows"][0]["n"] = 7
        with self.assertRaises(ContractError):
            propose(req, FixedClient(json.dumps(GOOD)))

    def test_command_prints_prompt_and_key(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            main(["prompt", str(ROOT / "contract" / "examples" / "request.json")])
        self.assertIn(f"key {prompt_key(build_prompt(REQUEST))}", out.getvalue())


class ValidAnswerIsUsed(unittest.TestCase):
    def test_valid_answer_passes_through(self):
        client = FixedClient(json.dumps(GOOD))
        run = propose(REQUEST, client)
        self.assertEqual(run.problems, [])
        self.assertEqual(run.response, GOOD)
        self.assertEqual(client.prompt, build_prompt(REQUEST))   # the model got the real prompt
        self.assertEqual((run.prompt_version, run.answer), ("v1_baseline", json.dumps(GOOD)))

    def test_example_replay_file_works(self):
        client = ReplayClient(EXAMPLE_REPLAY)
        run = propose(REQUEST, client)
        self.assertEqual(run.problems, [])
        self.assertEqual([p["sample"] for p in run.response["proposals"]], ["S-02", "S-01", None])
        self.assertEqual(len(client.prompts), 1)


class BadOutputBecomesNoLink(unittest.TestCase):
    def test_garbage(self):
        assert_all_no_link(self, propose(REQUEST, FailingClient()), "not valid JSON")

    def test_old_bare_list_format(self):
        run = propose(REQUEST, FailingClient(json.dumps(GOOD["proposals"])))
        assert_all_no_link(self, run, "AI answer rejected")

    def test_invented_code(self):
        bad = copy.deepcopy(GOOD)
        bad["proposals"][2]["sample"] = "S-04"
        bad["proposals"][2]["confidence"] = "low"
        assert_all_no_link(self, propose(REQUEST, FixedClient(json.dumps(bad))), "S-04")

    def test_client_error(self):
        run = propose(REQUEST, BrokenClient())
        assert_all_no_link(self, run, "AI call failed (TimeoutError")
        self.assertIsNone(run.answer)

    def test_client_returns_no_text(self):
        assert_all_no_link(self, propose(REQUEST, FixedClient(GOOD)), "not text")

    def test_no_recorded_answer(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "replay.json"
            path.write_text(json.dumps({"answers": {}}))
            assert_all_no_link(self, propose(REQUEST, ReplayClient(path)), "no recorded answer")

    def test_answer_recorded_for_another_prompt_is_not_used(self):
        # Same request, but a prompt version with one word changed: the old answer must not apply.
        with tempfile.TemporaryDirectory() as d:
            prompts = Path(d)
            v1 = (ROOT / "ai" / "prompts" / "v1_baseline.txt").read_text()
            (prompts / "v2_test.txt").write_text(v1.replace("say which", "tell which"))
            (prompts / "_output_format.txt").write_text(
                (ROOT / "ai" / "prompts" / "_output_format.txt").read_text())
            run = propose(REQUEST, ReplayClient(EXAMPLE_REPLAY), "v2_test", prompts)
            assert_all_no_link(self, run, "no recorded answer")


if __name__ == "__main__":
    unittest.main()
