"""Score the rule-based linker on the test cases in ai/testcases/cases.json.

    python3 -m ai.james_ai.score --set dev      (or dev2, hold)

Each case is one lab line, linked on its own against the register of its set,
so cross-line checks (two lines claiming one sample) never fire here. Outcomes
come from evaluate(), so "correct" and "wrong" mean the same everywhere.

The hold-out set is the exam, not practice: use it once per final version.
Its runs are saved to ai/runs/ with a timestamp and only totals are printed,
so its individual lines cannot creep into tuning.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .evaluate import evaluate
from .linker import LinkRun, Sample, link

ROOT = Path(__file__).resolve().parents[2]
CASES_FILE = ROOT / "ai" / "testcases" / "cases.json"
RUNS_DIR = ROOT / "ai" / "runs"
OUTCOMES = ("correct", "wrong", "abstained_ok", "abstained_missed")
HOLD = "hold"


def load_cases(path: Path = CASES_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_samples(register: List[dict]) -> List[Sample]:
    """The test registers have code/location/material/colour; the linker wants Samples."""
    return [Sample(id=r["code"], source="", location=r["location"], part="",
                   material=r["material"], notes=r["colour"]) for r in register]


def link_line(line: str, register: List[Sample]) -> LinkRun:
    """Run the rules on one lab line, as a report with an empty header."""
    return link("", register, "---\n" + line)


def score_case(case: dict, register: List[Sample]) -> dict:
    run = link_line(case["line"], register)
    p = run.proposals[0]
    counts = evaluate(run, {0: case["truth"]})
    return {
        "id": case["id"], "tag": case["tag"], "line": case["line"], "truth": case["truth"],
        "proposed": p.sample_id, "confidence": p.confidence, "reason": p.reason,
        "outcome": next(k for k in OUTCOMES if counts[k]),
    }


def score_set(data: dict, set_name: str) -> dict:
    """Score every case of one set. Raises KeyError for an unknown set."""
    reg_name = data["sets"][set_name]["register"]
    register = to_samples(data["registers"][reg_name])
    cases = [score_case(c, register) for c in data["cases"] if c["set"] == set_name]
    counts = {k: sum(c["outcome"] == k for c in cases) for k in OUTCOMES}
    return {"set": set_name, "register": reg_name, "variant": "rules",
            "lines": len(cases), "counts": counts, "cases": cases}


def git_commit() -> Optional[str]:
    """The commit the run was made on, with '+changes' if files were not committed."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("+changes" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return None


def save_run(result: dict, runs_dir: Path = RUNS_DIR) -> Path:
    now = datetime.now(timezone.utc)
    record = dict(result, run_at=now.isoformat(timespec="seconds"), commit=git_commit())
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{now:%Y%m%dT%H%M%SZ}_{result['set']}_{result['variant']}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def report(result: dict, details: bool = True) -> str:
    c = result["counts"]
    out = [f"Set {result['set']}: {result['lines']} lines, register {result['register']}, "
           f"variant {result['variant']}"]
    out += [f"  {k:17} {c[k]:3}" for k in OUTCOMES]
    if not details:
        return "\n".join(out)
    bad = [x for x in result["cases"] if x["outcome"] in ("wrong", "abstained_missed")]
    bad.sort(key=lambda x: x["outcome"] != "wrong")  # wrong links first, they matter most
    if bad:
        out.append("\nNot right (wrong links first):")
    for x in bad:
        got = f"{x['proposed']} ({x['confidence']})" if x["proposed"] else "no link"
        out += [f"  {x['id']:4} {x['outcome'].upper():16} [{x['tag']}]  {x['line']}",
                f"       proposed {got}, reference {x['truth'] or 'no link'}",
                f"       reason: {x['reason'].strip()}"]
    return "\n".join(out)


def main(argv: Optional[List[str]] = None, cases_file: Path = CASES_FILE,
         runs_dir: Path = RUNS_DIR) -> int:
    data = load_cases(cases_file)
    ap = argparse.ArgumentParser(description="Score the rule-based linker on a test set.")
    ap.add_argument("--set", required=True, choices=sorted(data["sets"]), dest="set_name")
    ap.add_argument("--save", action="store_true",
                    help="also save a dev/dev2 run to ai/runs/ (hold-out runs are always saved)")
    args = ap.parse_args(argv)

    result = score_set(data, args.set_name)
    if args.set_name == HOLD:
        print("WARNING: hold-out set. Use it once per final version and never tune on it.\n"
              "Only totals are shown; the full result is saved for the record.\n")
        print(report(result, details=False))
        print(f"\nSaved: {save_run(result, runs_dir)}")
    else:
        print(report(result))
        if args.save:
            print(f"\nSaved: {save_run(result, runs_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
