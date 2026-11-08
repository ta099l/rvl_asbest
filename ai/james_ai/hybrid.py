"""Rules first, AI second.

The rule-based linker runs on every line. Two kinds of line never go to the AI:
- a link the rules made with high confidence (exact ID, description agrees);
- a no-link the rules made because the evidence conflicts (ID says one sample,
  description another; two lines claim one sample; prefix mismatch). The AI
  cannot make contradicting evidence agree; it can only pick a side.
Every other line (medium or low links, and lines the rules could not link) is
sent to the AI in one request. Then:
- rules and AI agree        -> the link stays;
- rules and AI disagree     -> no link, both reasons shown;
- only the AI links         -> the AI's proposal;
- the AI answer is unusable -> the rules' proposal stays, with the reason.
Guard: a sample may be proposed for one line only. If a line would get a sample
that another line already has, neither line is linked.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .ai_step import DEFAULT_PROMPT, PROMPTS_DIR, AiRun, Client, propose
from .contract import check_request, response_problems
from .linker import LinkRun, Proposal, link
from .score import to_samples

# rule flags that mean "the evidence conflicts": stays no link, never sent to the AI
CONFLICT_FLAGS = ("conflict", "duplicate", "prefix_conflict", "collision", "unregistered")


@dataclass
class HybridRun:
    response: dict                       # follows the contract
    source: Dict[int, str]               # n -> rules, ai, both, disagree, guard, rules (ai unusable)
    sent: List[int] = field(default_factory=list)   # n of the lines sent to the AI
    ai: Optional[AiRun] = None


def _clean(s: Optional[str]) -> str:
    # The rules read "id | description | result" lines; keep each field on one line, one cell.
    return " ".join(str(s or "").replace("|", "/").split())


def rules_run(request: dict) -> LinkRun:
    """Run the rule-based linker on a contract request."""
    text = "---\n" + "\n".join(
        f"{_clean(r['raw_id']) or '-'} | {_clean(r['description'])} | {_clean(r['result'])}"
        for r in request["rows"])
    return link("", to_samples(request["register"]), text)


def rules_response(request: dict) -> dict:
    """The rules' proposals in contract form."""
    check_request(request)
    return {"proposals": [_as_proposal(p, r["n"]) for p, r in
                          zip(rules_run(request).proposals, request["rows"])]}


def _as_proposal(p: Proposal, n: int) -> dict:
    linked = p.status == "propose"
    return {"n": n, "sample": p.sample_id if linked else None,
            "confidence": p.confidence if linked else None, "reason": p.reason.strip()}


def _stays_with_rules(p: Proposal) -> bool:
    if p.status == "propose":
        return p.confidence == "high"
    return any(f.split(":")[-1] in CONFLICT_FLAGS for f in p.flags)


def hybrid(request: dict, client: Client, version: str = DEFAULT_PROMPT,
           prompts_dir=PROMPTS_DIR) -> HybridRun:
    check_request(request)
    rows = request["rows"]
    rule_props = rules_run(request).proposals
    out = {r["n"]: _as_proposal(p, r["n"]) for p, r in zip(rule_props, rows)}
    source = {r["n"]: "rules" for r in rows}
    send = [r for p, r in zip(rule_props, rows) if not _stays_with_rules(p)]
    if not send:
        return HybridRun({"proposals": list(out.values())}, source)

    # The AI sees the full register but only the lines that were not settled, numbered 1..k.
    sub = {"report_id": request["report_id"], "register": request["register"],
           "rows": [dict(r, n=i + 1) for i, r in enumerate(send)]}
    ai = propose(sub, client, version, prompts_dir)
    for r, a in zip(send, ai.response["proposals"]):
        n, mine = r["n"], out[r["n"]]
        if ai.problems:
            mine["reason"] = f"{mine['reason']} AI not used: {ai.problems[0]}."
            source[n] = "rules (ai unusable)"
        elif a["sample"] == mine["sample"]:
            if a["sample"] is None:
                mine["reason"] = f"No link from the rules or the AI. Rules: {mine['reason']} AI: {a['reason']}"
            else:
                mine["reason"] = f"Rules and AI agree on {a['sample']}. Rules: {mine['reason']} AI: {a['reason']}"
            source[n] = "both"
        elif mine["sample"] is None:
            # A model cannot verify its own confidence. Keep an AI-only link below
            # high confidence; only objective rule checks may label a link high.
            confidence = "medium" if a["confidence"] == "high" else a["confidence"]
            reason = f"AI: {a['reason']} (Rules found no safe link: {mine['reason']})"
            if a["confidence"] == "high":
                reason += " The model's high confidence is capped at medium."
            out[n] = {"n": n, "sample": a["sample"], "confidence": confidence,
                      "reason": reason}
            source[n] = "ai"
        else:
            out[n] = {"n": n, "sample": None, "confidence": None,
                      "reason": (f"Rules say {mine['sample']}, the AI says {a['sample'] or 'no link'}. "
                                 f"They disagree, so no link is proposed. Rules: {mine['reason']} "
                                 f"AI: {a['reason']}")}
            source[n] = "disagree"

    _guard_one_line_per_sample(out, source)
    response = {"proposals": [out[r["n"]] for r in rows]}
    problems = response_problems(response, request)
    if problems:  # a bug in this file, never a model problem: fail loudly
        raise RuntimeError(f"hybrid broke the contract: {problems}")
    return HybridRun(response, source, [r["n"] for r in send], ai)


def _guard_one_line_per_sample(out: Dict[int, dict], source: Dict[int, str]) -> None:
    """If the AI brought in a sample that another line also has, unlink all of them."""
    by_sample: Dict[str, List[int]] = {}
    for n, p in out.items():
        if p["sample"] is not None:
            by_sample.setdefault(p["sample"], []).append(n)
    for sample, ns in by_sample.items():
        if len(ns) > 1 and any(source[n] == "ai" for n in ns):
            for n in ns:
                others = ", ".join(str(m) for m in ns if m != n)
                out[n] = {"n": n, "sample": None, "confidence": None,
                          "reason": (f"{sample} is also proposed for line {others}. Two lines cannot "
                                     "share a sample, so neither is linked; the inspector decides.")}
                source[n] = "guard"
