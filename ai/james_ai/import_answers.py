"""Import answers from the prompt lab into the replay files.

    python3 -m ai.james_ai.import_answers answers.txt [--replace]

The input pairs the exact prompt you pasted with the answer you got back.
Plain text (easiest to paste):

    === PROMPT
    You link lab result lines to samples. ...
    === ANSWER
    {"proposals": [...]}
    === PROMPT
    ...

or JSON: [{"prompt": "...", "answer": "..."}, ...].

For each pair:
- the prompt is found in ai/replays/*.json by its exact text (only line endings
  and whitespace at the very ends are ignored) and the answer is filled in;
- an answer that is already there is never overwritten silently: a different
  one is reported as a conflict and kept, unless --replace is given;
- a prompt that matches no replay entry is matched to a dev, dev2 or dev3 test case.
  If its wording is a new prompt version, the template is written to
  ai/prompts/vN_imported.txt (with a note to fill in) and the answer goes to
  ai/replays/<set>_<version>.json. A new version is only written if rebuilding
  the prompt from it gives exactly the pasted text;
- anything else is reported as a mismatch and nothing is written for it.
The hold-out set is never matched: its answers are not collected this way.
"""
import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ai_step import OUTPUT_FORMAT, PROMPTS_DIR, build_prompt, load_template, prompt_key
from .compare import set_requests
from .score import CASES_FILE, ROOT, load_cases

REPLAYS_DIR = ROOT / "ai" / "replays"
EXAMPLE_REQUEST = ROOT / "contract" / "examples" / "request.json"
MATCH_SETS = ("dev", "dev2", "dev3")


@dataclass
class Result:
    status: str      # filled, unchanged, conflict, replaced, new_version, added, mismatch
    item: int        # 1-based position in the input file
    detail: str


def read_items(path: Path) -> List[Tuple[str, Any]]:
    """Read (prompt, answer) pairs from a .json or a plain-text file."""
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if path.suffix.lower() == ".json":
        items = json.loads(text)
        if not isinstance(items, list) or not all(isinstance(i, dict) and {"prompt", "answer"} <= i.keys()
                                                  for i in items):
            raise ValueError("a JSON file must be a list of {\"prompt\": ..., \"answer\": ...}")
        return [(i["prompt"], i["answer"]) for i in items]
    pairs, prompt, answer, part = [], [], [], None
    for no, line in enumerate(text.split("\n"), 1):
        mark = line.strip()
        if mark == "=== PROMPT":
            if part == "answer":
                pairs.append(("\n".join(prompt), "\n".join(answer).strip()))
            elif part == "prompt":
                raise ValueError(f"line {no}: a new PROMPT before the ANSWER of the previous one")
            prompt, answer, part = [], [], "prompt"
        elif mark == "=== ANSWER":
            if part != "prompt":
                raise ValueError(f"line {no}: ANSWER without a PROMPT before it")
            part = "answer"
        elif part == "prompt":
            prompt.append(line)
        elif part == "answer":
            answer.append(line)
        elif mark:
            raise ValueError(f"line {no}: text before the first '=== PROMPT'")
    if part == "prompt":
        raise ValueError("the last PROMPT has no ANSWER")
    if part == "answer":
        pairs.append(("\n".join(prompt), "\n".join(answer).strip()))
    return pairs


def _key_variants(prompt: str) -> List[str]:
    """Keys to try: as pasted, and with the ends trimmed (pasting often drops a newline)."""
    p = prompt.replace("\r\n", "\n")
    return list(dict.fromkeys(prompt_key(t) for t in (p, p.strip() + "\n", p.strip())))


def _same(a: Any, b: Any) -> bool:
    norm = lambda x: x.strip() if isinstance(x, str) else json.dumps(x, sort_keys=True)
    return norm(a) == norm(b)


def _load_replays(replays_dir: Path) -> Dict[Path, dict]:
    return {p: json.loads(p.read_text(encoding="utf-8")) for p in sorted(replays_dir.glob("*.json"))}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _known_requests(data: dict, example: Optional[Path]) -> List[Tuple[str, str, dict]]:
    """(set, case ids, request) for every dev, dev2 or dev3 case, plus the contract example."""
    out = [(s, c["id"], req) for s in MATCH_SETS if s in data["sets"] for c, req in set_requests(data, s)]
    if example is not None and example.exists():
        req = json.loads(example.read_text(encoding="utf-8"))
        out.append(("example", req["report_id"], req))
    return out


def _versions(prompts_dir: Path) -> List[str]:
    return sorted(p.stem for p in prompts_dir.glob("*.txt") if not p.name.startswith("_"))


def _template_from(prompt: str, request: dict, prompts_dir: Path) -> Optional[str]:
    """Undo the filling-in: put the slots back where this request's register and lines are."""
    register = "\n".join(f"{s['code']} | {s['location']} | {s['material']} | {s['colour']}"
                         for s in request["register"])
    lines = "\n".join(f"{r['n']}. {r['raw_id'] or '-'} | {r['description']} | {r['result']}"
                      for r in request["rows"])
    fmt = (prompts_dir / OUTPUT_FORMAT).read_text(encoding="utf-8").strip()
    text = prompt.replace("\r\n", "\n").strip()
    if text.count(register) != 1 or text.count(lines) != 1 or not text.endswith(fmt):
        return None
    body = text[: -len(fmt)].rstrip().replace(register, "{{REGISTER}}").replace(lines, "{{LINES}}")
    return body + "\n"


def _next_version(prompts_dir: Path) -> str:
    nums = [int(m.group(1)) for v in _versions(prompts_dir) for m in [re.match(r"v(\d+)", v)] if m]
    return f"v{max(nums, default=0) + 1}_imported"


def import_answers(items: List[Tuple[str, Any]], replace: bool = False,
                   prompts_dir: Path = PROMPTS_DIR, replays_dir: Path = REPLAYS_DIR,
                   cases_file: Path = CASES_FILE, example: Optional[Path] = EXAMPLE_REQUEST) -> List[Result]:
    replays = _load_replays(replays_dir)
    known = None                      # built only when a prompt is not in any replay file
    results: List[Result] = []
    changed = set()

    for i, (prompt, answer) in enumerate(items, 1):
        if answer is None or (isinstance(answer, str) and not answer.strip()):
            results.append(Result("mismatch", i, "empty answer, nothing imported"))
            continue
        hit = next(((path, k) for k in _key_variants(prompt) for path, d in replays.items()
                    if k in d["answers"]), None)
        if hit:
            path, key = hit
            entry = replays[path]["answers"][key]
            where = f"{path.name} {entry.get('report_id', '')} (key {key})"
            old = entry.get("answer")
            if old is None:
                entry["answer"], status = answer, "filled"
            elif _same(old, answer):
                status = "unchanged"
            elif replace:
                entry["answer"], status = answer, "replaced"
            else:
                results.append(Result("conflict", i, f"{where}: a different answer is already there; "
                                                     "kept it (use --replace to overwrite)"))
                continue
            if status != "unchanged":
                changed.add(path)
            results.append(Result(status, i, where))
            continue

        # Not in any replay file: find the test case, then the prompt version.
        if known is None:
            known = _known_requests(load_cases(cases_file), example)
        found = []
        for set_name, ids, req in known:
            tpl = _template_from(prompt, req, prompts_dir)
            if tpl is not None:
                found.append((set_name, ids, req, tpl))
        if len(found) != 1:
            first = prompt.strip().split("\n")[0][:60]
            why = "matches no replay entry and no dev, dev2 or dev3 test case" if not found else \
                  f"matches {len(found)} test cases, cannot tell which"
            results.append(Result("mismatch", i, f"prompt starting '{first}' {why}; nothing written"))
            continue
        set_name, ids, req, tpl = found[0]
        version = next((v for v in _versions(prompts_dir)
                        if (prompts_dir / f"{v}.txt").read_text(encoding="utf-8").strip() == tpl.strip()), None)
        new = version is None
        if new:
            version = _next_version(prompts_dir)
            (prompts_dir / f"{version}.txt").write_text(tpl, encoding="utf-8")
        text = build_prompt(req, version, prompts_dir)
        if prompt_key(text) not in _key_variants(prompt):     # must rebuild to the exact text
            if new:
                (prompts_dir / f"{version}.txt").unlink()
            results.append(Result("mismatch", i, f"case {ids}: rebuilding the prompt does not give the "
                                                 "pasted text; nothing written"))
            continue
        if new:
            (prompts_dir / f"{version}.note.md").write_text(
                f"Imported from the prompt lab on {date.today().isoformat()}.\n"
                "TODO: say what changed compared with the previous version, and why.\n", encoding="utf-8")
        path = replays_dir / f"{set_name}_{version}.json"
        data = replays.setdefault(path, {"note": f"Answers for set {set_name}, prompt {version}, "
                                                 "imported from the prompt lab.", "answers": {}})
        data["answers"][prompt_key(text)] = {"prompt": version, "report_id": ids, "text": text,
                                             "answer": answer}
        changed.add(path)
        results.append(Result("new_version" if new else "added", i,
                              (f"new prompt version {version} written to ai/prompts/{version}.txt; " if new else "")
                              + f"answer for {ids} added to {path.name}"))

    for path in changed:
        _save(path, replays[path])
    return results


def main(argv: Optional[List[str]] = None, prompts_dir: Path = PROMPTS_DIR,
         replays_dir: Path = REPLAYS_DIR, cases_file: Path = CASES_FILE,
         example: Optional[Path] = EXAMPLE_REQUEST) -> int:
    ap = argparse.ArgumentParser(description="Import prompt-lab answers into ai/replays/.")
    ap.add_argument("file", type=Path, help="a .txt (=== PROMPT / === ANSWER) or .json file")
    ap.add_argument("--replace", action="store_true", help="overwrite answers that differ (reported)")
    args = ap.parse_args(argv)

    try:
        items = read_items(args.file)
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Cannot read {args.file}: {e}")
        return 1
    results = import_answers(items, args.replace, prompts_dir, replays_dir, cases_file, example)
    for r in results:
        print(f"  item {r.item:<3} {r.status.upper():12} {r.detail}")
    counts = {s: sum(r.status == s for r in results) for s in
              ("filled", "added", "new_version", "replaced", "unchanged", "conflict", "mismatch")}
    print("Summary: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n) if results else "Nothing to import.")
    if counts["new_version"]:
        print("Write the change note in ai/prompts/<version>.note.md for each new version.")
    return 1 if counts["conflict"] or counts["mismatch"] else 0


if __name__ == "__main__":
    sys.exit(main())
