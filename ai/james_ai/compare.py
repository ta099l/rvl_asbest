"""Compare rules only, AI only and hybrid on one test set, in one table.

    python3 -m ai.james_ai.compare --set dev --replay ai/replays/dev_v1.json

Every case is one lab line, sent as its own request. The AI answers come from
a replay file (answers pasted from the prompt lab); without one, every AI line
is "no recorded answer" and so no link. To make a replay file to fill in:

    python3 -m ai.james_ai.compare --set dev --export-prompts ai/replays/dev_v1.json

It lists the exact prompt and key per case with "answer": null; answers already
in the file are kept. Paste each model answer into its "answer" field.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .ai_step import DEFAULT_PROMPT, PROMPTS_DIR, ReplayClient, build_prompt, prompt_key, propose
from .evaluate import outcome
from .hybrid import hybrid, rules_response
from .linker import parse_report
from .score import CASES_FILE, HOLD, OUTCOMES, RUNS_DIR, load_cases, save_run

VARIANTS = ("rules", "ai", "hybrid")


def case_request(case: dict, register: List[dict]) -> dict:
    """One test case as a one-line contract request."""
    row = parse_report("---\n" + case["line"])[1][0]
    raw = row.raw_id.strip()
    return {"report_id": case["id"], "register": register,
            "rows": [{"n": 1, "raw_id": None if raw in ("", "-", "—") else raw,
                      "description": row.desc, "result": row.result}]}


def set_requests(data: dict, set_name: str) -> List[tuple]:
    register = data["registers"][data["sets"][set_name]["register"]]
    return [(c, case_request(c, register)) for c in data["cases"] if c["set"] == set_name]


def compare_set(data: dict, set_name: str, client: ReplayClient, version: str = DEFAULT_PROMPT,
                prompts_dir: Path = PROMPTS_DIR) -> dict:
    cases = []
    for c, req in set_requests(data, set_name):
        h = hybrid(req, client, version, prompts_dir)
        a = propose(req, client, version, prompts_dir)
        got = {"rules": rules_response(req)["proposals"][0], "ai": a.response["proposals"][0],
               "hybrid": h.response["proposals"][0]}
        cases.append({"id": c["id"], "tag": c["tag"], "truth": c["truth"],
                      "ai_answered": not (a.answer is None), "sent_to_ai": bool(h.sent),
                      **{v: {"sample": got[v]["sample"], "reason": got[v]["reason"],
                             "outcome": outcome(got[v]["sample"], c["truth"])} for v in VARIANTS}})
    counts = {v: {k: sum(x[v]["outcome"] == k for x in cases) for k in OUTCOMES} for v in VARIANTS}
    return {"set": set_name, "variant": "compare", "prompt": version, "lines": len(cases),
            "ai_answered": sum(x["ai_answered"] for x in cases),
            "sent_to_ai": sum(x["sent_to_ai"] for x in cases), "counts": counts, "cases": cases}


def table(result: dict, details: bool = True) -> str:
    out = [f"Set {result['set']}: {result['lines']} lines, prompt {result['prompt']}, "
           f"AI answers found for {result['ai_answered']} of {result['lines']}, "
           f"hybrid sent {result['sent_to_ai']} to the AI", "",
           f"  {'variant':8}" + "".join(f"{k:>18}" for k in OUTCOMES)]
    for v in VARIANTS:
        out.append(f"  {v:8}" + "".join(f"{result['counts'][v][k]:>18}" for k in OUTCOMES))
    if not details:
        return "\n".join(out)
    short = {"correct": "ok", "wrong": "WRONG", "abstained_ok": "none ok", "abstained_missed": "missed"}
    out += ["", f"  {'case':5}{'reference':11}" + "".join(f"{v:20}" for v in VARIANTS)]
    for x in result["cases"]:
        cells = "".join(f"{(x[v]['sample'] or '-') + ' ' + short[x[v]['outcome']]:20}" for v in VARIANTS)
        out.append(f"  {x['id']:5}{x['truth'] or '-':11}{cells}" + ("" if x["sent_to_ai"] else "(rules only)"))
    return "\n".join(out)


def export_prompts(data: dict, set_name: str, path: Path, version: str = DEFAULT_PROMPT,
                   prompts_dir: Path = PROMPTS_DIR) -> int:
    """Write (or update) a replay file with one empty answer per case. Returns how many are empty."""
    old = json.loads(path.read_text(encoding="utf-8"))["answers"] if path.exists() else {}
    answers = dict(old)
    cases: dict = {}
    for c, req in set_requests(data, set_name):
        text = build_prompt(req, version, prompts_dir)
        key = prompt_key(text)
        cases.setdefault(key, []).append(c["id"])   # identical lines share one prompt
        answers[key] = {"prompt": version, "report_id": ", ".join(cases[key]), "text": text,
                        "answer": old.get(key, {}).get("answer")}
    note = (f"Prompts for set {set_name}, prompt {version}. Paste each model answer into 'answer' "
            "(raw text or JSON). Answers are only used for the exact prompt above them.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"note": note, "answers": answers}, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return sum(a["answer"] is None for a in answers.values())


def main(argv: Optional[List[str]] = None, cases_file: Path = CASES_FILE,
         runs_dir: Path = RUNS_DIR) -> int:
    data = load_cases(cases_file)
    ap = argparse.ArgumentParser(description="Compare rules only, AI only and hybrid on a test set.")
    ap.add_argument("--set", required=True, choices=sorted(data["sets"]), dest="set_name")
    ap.add_argument("--replay", type=Path, help="replay file with recorded AI answers")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT, help="prompt version in ai/prompts/")
    ap.add_argument("--export-prompts", type=Path, metavar="FILE",
                    help="write the prompts of this set to a replay file to fill in, then stop")
    args = ap.parse_args(argv)

    if args.export_prompts:
        if args.set_name == HOLD:
            ap.error("do not export the hold-out set; run it once with a final replay file")
        empty = export_prompts(data, args.set_name, args.export_prompts, args.prompt)
        print(f"Wrote {args.export_prompts}: {empty} prompts still need an answer.")
        return 0

    client = ReplayClient(args.replay)
    result = compare_set(data, args.set_name, client, args.prompt)
    result["replay"] = str(args.replay) if args.replay else None
    if args.set_name == HOLD:
        print("WARNING: hold-out set. Use it once per final version and never tune on it.\n")
        print(table(result, details=False))
        print(f"\nSaved: {save_run(result, runs_dir)}")
    else:
        print(table(result))
        if not args.replay:
            print("\nNo replay file given: the AI column shows what happens when the AI gives no answer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
