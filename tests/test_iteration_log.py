import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai.james_ai.ai_step import FailingClient, ReplayClient
from ai.james_ai.compare import compare_set
from ai.james_ai.iteration_log import build, main
from ai.james_ai.score import save_run, score_set
from tests.test_score import DATA as TINY

ROOT = Path(__file__).resolve().parents[1]


class IterationLog(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.runs = self.tmp / "runs"
        self.prompts = self.tmp / "prompts"
        shutil.copytree(ROOT / "ai" / "prompts", self.prompts)
        (self.prompts / "v1_baseline.note.md").write_text("Test note: baseline.")
        save_run(score_set(TINY, "dev"), self.runs)
        save_run(dict(compare_set(TINY, "dev", ReplayClient(), prompts_dir=self.prompts),
                      replay=None), self.runs)
        save_run(dict(compare_set(TINY, "hold", FailingClient(), prompts_dir=self.prompts),
                      replay=None), self.runs)
        self.log = build(self.runs, self.prompts)

    def test_has_note_full_prompt_and_tables(self):
        self.assertIn("## Baseline: rules only", self.log)
        self.assertIn("## Prompt v1_baseline", self.log)
        self.assertIn("Test note: baseline.", self.log)
        self.assertIn("LAB LINES (sample ID as written by the lab", self.log)
        self.assertIn('{"proposals":', self.log)                      # the answer format is part of it
        self.assertIn("| dev | rules | - | 1 | 1 | 1 | 1 |", self.log)

    def test_wrong_and_missed_cases_with_reasons(self):
        self.assertIn("- **wrong** t2 [planted]", self.log)
        self.assertIn("- **abstained_missed** t4", self.log)
        self.assertLess(self.log.index("- **wrong** t2"), self.log.index("- **abstained_missed** t4"))
        self.assertIn("Reason: ID matches register exactly.", self.log)

    def test_hold_out_shows_totals_only(self):
        self.assertIn("| hold | hybrid |", self.log)
        self.assertIn("Its lines are not shown on purpose", self.log)
        hold_line = next(c["line"] for c in TINY["cases"] if c["set"] == "hold")
        hold_part = self.log.split("#### hold run")[1]
        self.assertNotIn(hold_line, hold_part)

    def test_same_files_give_the_same_log(self):
        self.assertEqual(build(self.runs, self.prompts), self.log)

    def test_missing_note_and_no_runs_are_said_plainly(self):
        (self.prompts / "v1_baseline.note.md").unlink()
        log = build(self.tmp / "empty", self.prompts)
        self.assertIn("No change note yet.", log)
        self.assertIn("No saved runs yet.", log)

    def test_command_writes_the_file(self):
        out_file = self.tmp / "iteration-log.md"
        with contextlib.redirect_stdout(io.StringIO()):
            main([], self.runs, self.prompts, out_file)
        self.assertEqual(out_file.read_text(), self.log)


if __name__ == "__main__":
    unittest.main()
