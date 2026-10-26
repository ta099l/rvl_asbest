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
        t = truth.get(p.index)
        if p.status == "propose":
            out["correct" if p.sample_id == t else "wrong"] += 1
        elif t is None:
            out["abstained_ok"] += 1
        else:
            out["abstained_missed"] += 1
    return out
