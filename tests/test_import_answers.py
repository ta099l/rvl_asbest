import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai.james_ai import import_answers as ia
from ai.james_ai.ai_step import ReplayClient, build_prompt, propose
from ai.james_ai.compare import case_request, export_prompts
from tests.test_score import DATA as TINY

ROOT = Path(__file__).resolve().parents[1]
ANSWER = {"proposals": [{"n": 1, "sample": "A-01", "confidence": "high", "reason": "test"}]}
OTHER = {"proposals": [{"n": 1, "sample": None, "confidence": None, "reason": "other"}]}


class Workspace(unittest.TestCase):
    """Temporary prompts/, replays/ and cases.json, so real files are never touched."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.prompts = self.tmp / "prompts"
        shutil.copytree(ROOT / "ai" / "prompts", self.prompts)
        for f in self.prompts.glob("*.note.md"):
            f.unlink()
        self.replays = self.tmp / "replays"
        self.cases = self.tmp / "cases.json"
        self.cases.write_text(json.dumps(TINY))
        self.replay = self.replays / "dev_v1.json"
        export_prompts(TINY, "dev", self.replay, prompts_dir=self.prompts)

    def prompt(self, case=0, version="v1_baseline"):
        req = case_request(TINY["cases"][case], TINY["registers"]["tiny"])
        return build_prompt(req, version, self.prompts)

    def run_import(self, items, replace=False):
        return ia.import_answers(items, replace, self.prompts, self.replays, self.cases, example=None)

    def stored(self, path=None):
        answers = json.loads((path or self.replay).read_text())["answers"]
        return {a["report_id"]: a["answer"] for a in answers.values()}


class ReadItems(unittest.TestCase):
    def write(self, text, suffix=".txt"):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        p = d / f"answers{suffix}"
        p.write_text(text)
        return p

    def test_text_format_with_windows_line_endings(self):
        p = self.write("=== PROMPT\r\nline one\r\nline two\r\n=== ANSWER\r\n{\"a\": 1}\r\n\r\n"
                       "=== PROMPT\r\nsecond\r\n=== ANSWER\r\nraw text\r\n")
        self.assertEqual(ia.read_items(p), [("line one\nline two", '{"a": 1}'), ("second", "raw text")])

    def test_json_format(self):
        p = self.write(json.dumps([{"prompt": "p", "answer": ANSWER}]), ".json")
        self.assertEqual(ia.read_items(p), [("p", ANSWER)])

    def test_broken_files_are_refused_with_the_line(self):
        for text, msg in (("=== ANSWER\nx", "line 1"), ("=== PROMPT\np", "no ANSWER"),
                          ("hello\n=== PROMPT\np\n=== ANSWER\na", "before the first"),
                          ("=== PROMPT\np\n=== PROMPT\nq\n=== ANSWER\na", "line 3")):
            with self.subTest(text), self.assertRaises(ValueError) as ctx:
                ia.read_items(self.write(text))
            self.assertIn(msg, str(ctx.exception))


class FillReplayFiles(Workspace):
    def test_exact_prompt_fills_the_answer(self):
        r = self.run_import([(self.prompt(0), ANSWER)])
        self.assertEqual([x.status for x in r], ["filled"])
        self.assertEqual(self.stored()["t1"], ANSWER)

    def test_lost_newline_at_the_end_still_matches(self):
        r = self.run_import([(self.prompt(0).strip(), ANSWER)])
        self.assertEqual(r[0].status, "filled")

    def test_never_overwrites_silently(self):
        self.run_import([(self.prompt(0), ANSWER)])
        self.assertEqual(self.run_import([(self.prompt(0), ANSWER)])[0].status, "unchanged")
        r = self.run_import([(self.prompt(0), OTHER)])
        self.assertEqual(r[0].status, "conflict")
        self.assertIn("--replace", r[0].detail)
        self.assertEqual(self.stored()["t1"], ANSWER)                 # kept
        self.assertEqual(self.run_import([(self.prompt(0), OTHER)], replace=True)[0].status, "replaced")
        self.assertEqual(self.stored()["t1"], OTHER)

    def test_unknown_prompt_is_a_mismatch_and_writes_nothing(self):
        before = self.replay.read_text()
        r = self.run_import([("Please summarise this report.", ANSWER)])
        self.assertEqual(r[0].status, "mismatch")
        self.assertEqual(self.replay.read_text(), before)

    def test_empty_answer_is_a_mismatch(self):
        self.assertEqual(self.run_import([(self.prompt(0), "  ")])[0].status, "mismatch")

    def test_imported_answer_is_used_by_the_ai_step(self):
        self.run_import([(self.prompt(0), ANSWER)])
        req = case_request(TINY["cases"][0], TINY["registers"]["tiny"])
        run = propose(req, ReplayClient(self.replay), prompts_dir=self.prompts)
        self.assertEqual((run.problems, run.response["proposals"][0]["sample"]), ([], "A-01"))


class NewPromptVersions(Workspace):
    def reworded(self, case=0):
        return self.prompt(case).replace("say which sample", "name the sample")

    def test_new_wording_becomes_a_new_version(self):
        r = self.run_import([(self.reworded(0), ANSWER)])
        self.assertEqual(r[0].status, "new_version")
        tpl = (self.prompts / "v2_imported.txt").read_text()
        self.assertIn("name the sample", tpl)
        self.assertIn("{{REGISTER}}", tpl)
        self.assertIn("{{LINES}}", tpl)
        self.assertNotIn("A-01 | Engine room", tpl)                  # the filled-in data is taken out
        self.assertIn("TODO", (self.prompts / "v2_imported.note.md").read_text())
        path = self.replays / "dev_v2_imported.json"
        self.assertEqual(self.stored(path)["t1"], ANSWER)
        # end to end: the AI step with v2 finds the answer
        req = case_request(TINY["cases"][0], TINY["registers"]["tiny"])
        run = propose(req, ReplayClient(path), "v2_imported", self.prompts)
        self.assertEqual(run.problems, [])

    def test_same_new_wording_for_another_case_reuses_the_version(self):
        r = self.run_import([(self.reworded(0), ANSWER), (self.reworded(1), OTHER)])
        self.assertEqual([x.status for x in r], ["new_version", "added"])
        self.assertFalse((self.prompts / "v3_imported.txt").exists())

    def test_changed_answer_format_is_not_guessed(self):
        text = self.prompt(0).replace('"confidence" is', "confidence is")
        r = self.run_import([(text, ANSWER)])
        self.assertEqual(r[0].status, "mismatch")
        self.assertFalse((self.prompts / "v2_imported.txt").exists())


class Command(Workspace):
    def test_exit_code_and_summary(self):
        items = self.tmp / "answers.json"
        items.write_text(json.dumps([{"prompt": self.prompt(0), "answer": ANSWER},
                                     {"prompt": "nonsense", "answer": ANSWER}]))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ia.main([str(items)], self.prompts, self.replays, self.cases, None)
        self.assertEqual(code, 1)                                     # a mismatch is not OK
        self.assertIn("Summary: 1 filled, 1 mismatch", out.getvalue())


if __name__ == "__main__":
    unittest.main()
