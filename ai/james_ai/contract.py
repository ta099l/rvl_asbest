"""Check AI answers against the James contract (contract/*.schema.json).

A model can return text that looks fine but breaks the contract: a code that
is not in the register, a missing line, lines in the wrong order. A wrong link
that looks convincing is the worst outcome, so this module never repairs an
answer. If anything is wrong, every row becomes "no link" with the reason, and
the inspector links those rows by hand (CLAUDE.md, safety rule 4).

The checks here mirror the schema files and add the rules a schema cannot
express on its own (codes unique, n in order, sample must be in the register).
"""
import json
from typing import Any, Dict, List, Optional, Tuple

CONFIDENCE = ("high", "medium", "low")
REGISTER_KEYS = {"code", "location", "material", "colour"}
ROW_KEYS = {"n", "raw_id", "description", "result"}
PROPOSAL_KEYS = {"n", "sample", "confidence", "reason"}


class ContractError(ValueError):
    """The request is broken. That is a bug in the app, not a model problem."""


def _is_int(x: Any) -> bool:
    # In Python True is also an int; the contract wants real numbers only.
    return isinstance(x, int) and not isinstance(x, bool)


def _keys_problem(obj: dict, expected: set, where: str) -> Optional[str]:
    missing, extra = expected - obj.keys(), obj.keys() - expected
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(sorted(missing)))
        if extra:
            parts.append("unexpected " + ", ".join(sorted(extra)))
        return f"{where}: {'; '.join(parts)}"
    return None


def request_problems(request: Any) -> List[str]:
    """List everything wrong with a request. Empty list means valid."""
    if not isinstance(request, dict):
        return ["request is not a JSON object"]
    p = _keys_problem(request, {"report_id", "register", "rows"}, "request")
    if p:
        return [p]
    out: List[str] = []
    if not isinstance(request["report_id"], str) or not request["report_id"].strip():
        out.append("report_id must be a non-empty string")

    reg = request["register"]
    if not isinstance(reg, list) or not reg:
        out.append("register must be a non-empty list")
    else:
        seen = set()
        for i, s in enumerate(reg):
            where = f"register[{i}]"
            if not isinstance(s, dict):
                out.append(f"{where} is not an object")
                continue
            p = _keys_problem(s, REGISTER_KEYS, where)
            if p:
                out.append(p)
                continue
            if not all(isinstance(s[k], str) for k in REGISTER_KEYS):
                out.append(f"{where}: all fields must be strings")
                continue
            if not s["code"].strip():
                out.append(f"{where}: code is empty")
            elif s["code"] in seen:
                out.append(f"{where}: code {s['code']} appears twice")
            seen.add(s["code"])

    rows = request["rows"]
    if not isinstance(rows, list) or not rows:
        out.append("rows must be a non-empty list")
    else:
        for i, r in enumerate(rows):
            where = f"rows[{i}]"
            if not isinstance(r, dict):
                out.append(f"{where} is not an object")
                continue
            p = _keys_problem(r, ROW_KEYS, where)
            if p:
                out.append(p)
                continue
            if not _is_int(r["n"]) or r["n"] != i + 1:
                out.append(f"{where}: n must be {i + 1}")
            if not (r["raw_id"] is None or isinstance(r["raw_id"], str)):
                out.append(f"{where}: raw_id must be a string or null")
            if not isinstance(r["description"], str) or not isinstance(r["result"], str):
                out.append(f"{where}: description and result must be strings")
    return out


def check_request(request: Any) -> None:
    """Raise ContractError if the request breaks the contract."""
    problems = request_problems(request)
    if problems:
        raise ContractError("; ".join(problems))


def response_problems(response: Any, request: dict) -> List[str]:
    """List everything wrong with a response to a (valid) request."""
    if not isinstance(response, dict):
        return ["answer is not a JSON object with a 'proposals' list"]
    p = _keys_problem(response, {"proposals"}, "answer")
    if p:
        return [p]
    props = response["proposals"]
    if not isinstance(props, list):
        return ["proposals is not a list"]
    rows = request["rows"]
    if len(props) != len(rows):
        return [f"{len(props)} proposals for {len(rows)} lab lines"]

    codes = {s["code"] for s in request["register"]}
    out: List[str] = []
    for i, (pr, row) in enumerate(zip(props, rows)):
        where = f"proposal {i + 1}"
        if not isinstance(pr, dict):
            out.append(f"{where} is not an object")
            continue
        p = _keys_problem(pr, PROPOSAL_KEYS, where)
        if p:
            out.append(p)
            continue
        if not _is_int(pr["n"]) or pr["n"] != row["n"]:
            out.append(f"{where}: n is {pr['n']!r}, expected {row['n']}")
        sample = pr["sample"]
        if sample is not None and (not isinstance(sample, str) or sample not in codes):
            out.append(f"{where}: sample {sample!r} is not a code in the register")
        conf = pr["confidence"]
        if sample is None:
            if conf is not None and conf not in CONFIDENCE:
                out.append(f"{where}: confidence {conf!r} is not high, medium, low or null")
        elif conf not in CONFIDENCE:
            out.append(f"{where}: confidence {conf!r} is not high, medium or low")
        if not isinstance(pr["reason"], str) or not pr["reason"].strip():
            out.append(f"{where}: reason is missing")
    return out


def no_links(request: dict, why: str) -> Dict[str, list]:
    """A response that proposes nothing for every row, with the same reason."""
    return {"proposals": [{"n": r["n"], "sample": None, "confidence": None, "reason": why}
                          for r in request["rows"]]}


def validate_response(answer: Any, request: dict) -> Tuple[Dict[str, list], List[str]]:
    """Turn a model answer into a response that is always safe to show.

    answer is the raw text from the model, or already-parsed JSON.
    Returns (response, problems). If problems is empty, response is the answer
    itself. Otherwise response is "no link" for every row and problems says why.
    """
    check_request(request)
    if isinstance(answer, (str, bytes)):
        try:
            answer = json.loads(answer)
        except json.JSONDecodeError as e:
            problems = [f"not valid JSON ({e.msg} at line {e.lineno}, column {e.colno})"]
            return no_links(request, _rejected(problems)), problems
    problems = response_problems(answer, request)
    if problems:
        return no_links(request, _rejected(problems)), problems
    return {"proposals": [dict(p) for p in answer["proposals"]]}, []


def _rejected(problems: List[str]) -> str:
    shown = "; ".join(problems[:3]) + (f" (and {len(problems) - 3} more)" if len(problems) > 3 else "")
    return f"AI answer rejected because it breaks the contract: {shown}. No link proposed; link by hand."
