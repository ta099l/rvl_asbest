"""Compare proposed links with reference links verified by an inspector."""
from typing import Dict, Optional

from .linker import LinkRun


def evaluate(run: LinkRun, truth: Dict[int, Optional[str]]) -> dict:
    """truth maps lab row index -> correct sample code, or None if no sample is correct.

    correct          proposal matches the reference
    wrong            proposal differs from the reference (the failure that matters most)
    abstained_ok     no proposal, and no sample was right
    abstained_missed no proposal although a right answer existed (inspector must link by hand)
    """
    out = {"correct": 0, "wrong": 0, "abstained_ok": 0, "abstained_missed": 0, "rows": len(run.proposals)}
    for p in run.proposals:
        out[outcome(p.sample_id if p.status == "propose" else None, truth.get(p.index))] += 1
    return out


def outcome(proposed: Optional[str], truth: Optional[str]) -> str:
    """One line's outcome; None means no link (proposed) or no right sample (truth)."""
    if proposed is not None:
        return "correct" if proposed == truth else "wrong"
    return "abstained_ok" if truth is None else "abstained_missed"
