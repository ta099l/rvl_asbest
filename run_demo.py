"""Walk through the whole flow on the fictional ship case:
lab report -> proposals with reasons -> inspector decisions -> draft report -> asset file.

    python3 run_demo.py          the scripted walk-through (rules only)
    python3 run_demo.py --flow   hybrid proposals; you decide each line from the keyboard

The --flow answers come from ai/replays/demo_ship.json: hand-written stand-in
answers to show the flow, not model output. Never use them for scoring.
"""
import argparse
import sys
import textwrap
from pathlib import Path
from typing import Callable, List, Optional

from ai.james_ai.ai_step import ReplayClient
from ai.james_ai.demo_data import SHIP
from ai.james_ai.hybrid import hybrid
from ai.james_ai.linker import parse_report
from james.store import Store

DEMO_REPLAY = Path(__file__).resolve().parent / "ai" / "replays" / "demo_ship.json"
REPORT_ID = "LAB-2026-0412"


def print_draft_and_audit(s: Store, rid: int, out: Callable = print) -> None:
    out("\n== 3. Draft report")
    d = s.draft_report(rid)
    out(f"  {d['object']} at {d['site']} [{d['status']}]")
    for x in d["linked"]:
        out(f"  {x['sample']} {x['location']:36} {x['result']}")
    out("  Open items:", *d["open_items"], sep="\n   - ")
    out("\n== 4. Audit log")
    for e in s.audit_log():
        out(f"  {e['decided_at']}  {e['decided_by']}: row {e['idx'] + 1} {e['state']}"
            f" {e['sample_code'] or ''} {('(' + e['note'] + ')') if e['note'] else ''}")


def classic() -> None:
    s = Store()  # in memory; pass a file path to keep the data
    oid = s.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"], SHIP["project"], SHIP["samples"])

    print("== 1. Lab report 1 arrives; the linker proposes")
    rid = s.ingest_report(oid, "Lab report 1", SHIP["reports"]["b1"]["text"])
    for r in s.rows(rid):
        print(f"  row {r['idx'] + 1}: {r['raw_id'] or '-':6} -> {r['proposed_code'] or 'NO LINK':8} {r['confidence'] or '':7} {r['reason'][:90]}")

    print("\n== 2. The inspector decides (nothing is final until this step)")
    INSPECTOR = "Inspector (demo)"
    for r in s.rows(rid):
        if r["proposed_code"]:
            s.decide(rid, r["idx"], "approved", by=INSPECTOR)
    s.decide(rid, 5, "corrected", by=INSPECTOR, sample_code="S-06", note="description matches the steering gear room")
    s.decide(rid, 6, "rejected", by=INSPECTOR, note="S-09 is not in the register, ask the lab")

    print("\n== 3. Draft report")
    d = s.draft_report(rid)
    print(f"  {d['object']} at {d['site']} [{d['status']}]")
    for x in d["linked"]:
        print(f"  {x['sample']} {x['location']:36} {x['result']}")
    print("  Open items:", *d["open_items"], sep="\n   - ")

    print("\n== 4. Save to the asset file, then a follow-up report arrives")
    s.save_asset_version(oid, rid, INSPECTOR)
    r2 = s.ingest_report(oid, "Lab report 2", SHIP["reports"]["b2"]["text"])
    s.decide(r2, 0, "approved", by=INSPECTOR)
    s.decide(r2, 1, "approved", by=INSPECTOR)
    s.save_asset_version(oid, r2, INSPECTOR)
    a = s.asset(oid)
    print(f"  asset file is at version {a['version']}")
    for h in a["samples"]["S-03"]["history"]:
        print(f"  S-03 v{h['version']}: {h['result']}" + ("   <- result changed" if h["changed"] else ""))

    print("\n== 5. Audit log")
    for e in s.audit_log():
        print(f"  {e['decided_at']}  {e['decided_by']}: row {e['idx'] + 1} {e['state']}"
              f" {e['sample_code'] or ''} {('(' + e['note'] + ')') if e['note'] else ''}")


def ship_request(key: str = "b1") -> dict:
    """The fictional ship's register and lab report as a contract request."""
    register = [{"code": s.id, "location": s.location, "material": s.material, "colour": s.notes}
                for s in SHIP["samples"]]
    rows = [{"n": r.index + 1, "raw_id": None if r.raw_id.strip() in ("", "-") else r.raw_id.strip(),
             "description": r.desc, "result": r.result}
            for r in parse_report(SHIP["reports"][key]["text"])[1]]
    return {"report_id": REPORT_ID, "register": register, "rows": rows}


def flow(ask: Callable[[str], str] = input, out: Callable = print,
         replay: Optional[Path] = DEMO_REPLAY) -> Store:
    """Hybrid proposals, then a named inspector approves, corrects, rejects or skips each line.

    store.py keeps the rules' proposals. Approving a hybrid proposal that the rules
    did not make is therefore recorded as 'corrected', with a note saying so.
    """
    s = Store()
    oid = s.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"], SHIP["project"], SHIP["samples"])
    rid = s.ingest_report(oid, "Lab report 1", SHIP["reports"]["b1"]["text"])
    codes = {x.id for x in SHIP["samples"]}
    run = hybrid(ship_request(), ReplayClient(replay))

    out(f"== 1. Lab report {REPORT_ID} for {SHIP['name']}: rules first, AI second")
    out(f"  {len(run.sent)} of {len(run.response['proposals'])} lines went to the AI (stand-in answers"
        f" from {replay.name if replay else 'nowhere'})" + (f"; AI not used: {run.ai.problems[0]}" if run.ai and run.ai.problems else ""))
    out("  Nothing is final until a named inspector decides each line.\n")
    try:
        name = ""
        while not name:
            name = ask("Inspector name: ").strip()
            if not name:
                out("  A name is required: every decision is signed.")

        out("\n== 2. Decide each line")
        for r, p in zip(s.rows(rid), run.response["proposals"]):
            n = r["idx"] + 1
            out(f"\nLine {n}: {r['raw_line']}")
            got = f"{p['sample']} ({p['confidence']})" if p["sample"] else "NO LINK"
            out(f"  Proposal: {got}   from: {run.source[n]}")
            out(textwrap.fill(p["reason"], 100, initial_indent="  Reason: ", subsequent_indent="          "))
            while True:
                choice = ask("  [a]pprove  [c]orrect  [r]eject  [s]kip > ").strip().lower()[:1]
                try:
                    if choice == "a":
                        if p["sample"] is None:
                            out("  Nothing is proposed for this line: correct it or reject it.")
                            continue
                        if p["sample"] == r["proposed_code"]:
                            s.decide(rid, r["idx"], "approved", by=name)
                        else:
                            s.decide(rid, r["idx"], "corrected", by=name, sample_code=p["sample"],
                                     note=f"approved the {run.source[n]} proposal; rules alone proposed "
                                          f"{r['proposed_code'] or 'no link'}")
                        out(f"  -> approved {p['sample']}")
                    elif choice == "c":
                        code = ask(f"  Correct sample code ({', '.join(sorted(codes))}): ").strip()
                        if code not in codes:
                            out(f"  {code!r} is not in the register.")
                            continue
                        s.decide(rid, r["idx"], "corrected", by=name, sample_code=code,
                                 note=ask("  Note (why): ").strip())
                        out(f"  -> corrected to {code}")
                    elif choice == "r":
                        s.decide(rid, r["idx"], "rejected", by=name, note=ask("  Note (why): ").strip())
                        out("  -> rejected, no link")
                    elif choice == "s":
                        out("  -> skipped, stays open")
                    else:
                        out("  Type a, c, r or s.")
                        continue
                except ValueError as e:      # the store refuses an invalid decision
                    out(f"  Not recorded: {e}")
                    continue
                break
    except EOFError:
        out("\n  Input ended: the remaining lines stay open.")
    print_draft_and_audit(s, rid, out)
    return s


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Demo of James on the fictional ship.")
    ap.add_argument("--flow", action="store_true", help="hybrid proposals with keyboard decisions")
    args = ap.parse_args(argv)
    flow() if args.flow else classic()
    return 0


if __name__ == "__main__":
    sys.exit(main())
