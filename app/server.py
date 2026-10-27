"""James app: the screen and the small web server around Tasnim's linking code.

Run from the repository root:

    python3 app/server.py            (Windows: python app\\server.py)

then open http://127.0.0.1:8000 in a browser. Only the standard library is used.

What this file does, in one picture:

    browser  <->  server.py  <->  hybrid() (rules first, AI second)  +  Store (SQLite)

The AI part (ai/james_ai) only PROPOSES. This app shows every proposal with its
reason, and only a named inspector can approve, correct or reject a line. Nothing
reaches the draft chapters without that decision.

Data is fictitious. There is no real AI behind this yet: the AI answers for demo
report 1 are hand-written stand-ins (ai/replays/demo_ship.json).
"""
import argparse
import json
import re
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.james_ai.ai_step import ReplayClient            # noqa: E402
from ai.james_ai.contract import ContractError          # noqa: E402
from ai.james_ai.demo_data import SHIP                  # noqa: E402
from ai.james_ai.hybrid import HybridRun, hybrid        # noqa: E402
from james.store import Store                           # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
DEMO_REPLAY = ROOT / "ai" / "replays" / "demo_ship.json"

ASBESTOS = re.compile(r"chrysotile|amosite|crocidolite|tremolite|actinolite|anthophyllite|asbestos", re.I)
NOT_DETECTED = re.compile(r"not\s+detected|<\s*\d|below|none", re.I)


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def norm(code: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


def classify(result: str) -> Optional[dict]:
    """Materials List class for one approved result, or None when it is not automated.

    Only 'asbestos detected' is decided here. Other substances (PCB, lead, ODS ...)
    need thresholds that RVL still has to confirm, so they go to the inspector.
    """
    r = result or ""
    if ASBESTOS.search(r):
        if re.search(r"not\s+detected", r, re.I):
            return {"table": None, "substance": "Asbestos", "note": "not detected"}
        return {"table": "A", "substance": "Asbestos", "note": "detected: proposed for Table A"}
    return {"table": "?", "substance": "other", "note": "classification not automated; thresholds to be confirmed by RVL"}


class Service:
    """All state of one demo session. One lock: the demo has one user at a time."""

    def __init__(self, db_path: str = ":memory:"):
        self.lock = threading.RLock()
        self.db_path = db_path
        self.reset()

    # ---------- session ----------
    def reset(self) -> None:
        with self.lock:
            self.store = Store(self.db_path if self.db_path != ":memory:" else ":memory:")
            self.object_id = self.store.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"],
                                                   SHIP["project"], SHIP["samples"])
            self.runs: Dict[int, HybridRun] = {}
            self.agent_log: List[dict] = []
            self.client = ReplayClient(DEMO_REPLAY)
            self.load_demo("b1")

    def log(self, report_id: int, text: str) -> None:
        self.agent_log.append({"at": now(), "report_id": report_id, "by": "Agent", "text": text})

    # ---------- reports ----------
    def load_demo(self, key: str) -> int:
        with self.lock:
            if key not in SHIP["reports"]:
                raise ValueError("unknown demo report")
            label = {"b1": "Lab report 1", "b2": "Lab report 2 (follow-up)"}.get(key, key)
            return self.ingest(label, SHIP["reports"][key]["text"])

    def ingest(self, label: str, text: str) -> int:
        with self.lock:
            if not text or not text.strip():
                raise ValueError("the lab report text is empty")
            rid = self.store.ingest_report(self.object_id, label.strip() or "Lab report", text)
            if not self.store.rows(rid):
                raise ValueError("no lab lines found: put the lines after a line with ---")
            self.read(rid)
            return rid

    def request_for(self, rid: int) -> dict:
        rep = self.store.db.execute("SELECT * FROM lab_report WHERE id=?", (rid,)).fetchone()
        register = [{"code": s.id, "location": s.location, "material": s.material, "colour": s.notes}
                    for s in self.store.register(rep["object_id"])]
        rows = []
        for r in self.store.rows(rid):
            raw = (r["raw_id"] or "").strip()
            rows.append({"n": r["idx"] + 1, "raw_id": None if raw in ("", "-") else raw,
                         "description": r["description"] or "", "result": r["result"] or ""})
        return {"report_id": rep["report_ref"] or f"report-{rid}", "register": register, "rows": rows}

    def read(self, rid: int) -> None:
        """Run the agent (rules first, AI second) and remember its proposals."""
        req = self.request_for(rid)
        try:
            run = hybrid(req, self.client)
        except ContractError as e:
            raise ValueError(f"the lab report could not be read: {e}")
        self.runs[rid] = run
        n = len(req["rows"])
        self.log(rid, f"Read {n} lab lines. {n - len(run.sent)} settled by the rules, {len(run.sent)} sent to the AI step.")
        for i, p in enumerate(run.response["proposals"]):
            if p["sample"] is None:
                self.log(rid, f"Line {i + 1} ({req['rows'][i]['raw_id'] or 'no ID'}): no link found.")

    # ---------- decisions ----------
    def decide(self, rid: int, idx: int, action: str, by: str, sample: Optional[str], note: str) -> None:
        with self.lock:
            by = (by or "").strip()
            if not by:
                raise ValueError("enter the inspector name first: every decision is signed")
            run = self.runs.get(rid)
            if run is None:
                raise ValueError("unknown report")
            prop = run.response["proposals"][idx]
            row = self.store.rows(rid)[idx]
            if action == "approve":
                if prop["sample"] is None:
                    raise ValueError("nothing is proposed for this line, so it cannot be approved: link it yourself or reject")
                if prop["sample"] == row["proposed_code"]:
                    self.store.decide(rid, idx, "approved", by=by, note=note)
                else:      # the rules did not propose this sample (the AI did); store.py records it as corrected
                    self.store.decide(rid, idx, "corrected", by=by, sample_code=prop["sample"],
                                      note=(note + " " if note else "") +
                                      f"approved the {run.source[idx + 1]} proposal; rules alone proposed {row['proposed_code'] or 'no link'}")
            elif action == "correct":
                self.store.decide(rid, idx, "corrected", by=by, sample_code=sample, note=note)
            elif action == "reject":
                self.store.decide(rid, idx, "rejected", by=by, note=note)
            else:
                raise ValueError("unknown action")

    def save_history(self, rid: int, by: str) -> int:
        with self.lock:
            if not (by or "").strip():
                raise ValueError("enter the inspector name first")
            v = self.store.save_asset_version(self.object_id, rid, by.strip())
            return v

    # ---------- view for the screen ----------
    def view(self, rid: Optional[int] = None) -> dict:
        with self.lock:
            reports = [dict(r) for r in self.store.db.execute(
                "SELECT id,label,report_ref,lab,ingested_at FROM lab_report WHERE object_id=? ORDER BY id",
                (self.object_id,))]
            obj = dict(self.store.object(self.object_id))
            reg = self.store.register(self.object_id)
            out = {"object": obj,
                   "register": [{"code": s.id, "source": s.source, "location": s.location, "material": s.material,
                                 "notes": s.notes, "photo": s.photo} for s in reg],
                   "reports": reports, "report": None,
                   "asset": self.store.asset(self.object_id)}
            if not reports:
                return out
            rid = rid if rid in self.runs else reports[-1]["id"]
            out["report"] = self.report_view(rid, reg)
            return out

    def report_view(self, rid: int, reg) -> dict:
        run = self.runs[rid]
        reg_by = {s.id: s for s in reg}
        rep = self.store.db.execute("SELECT * FROM lab_report WHERE id=?", (rid,)).fetchone()
        decisions = self.store.current_decisions(rid)
        rows, used = [], {}
        for r, p in zip(self.store.rows(rid), run.response["proposals"]):
            n = r["idx"] + 1
            src = run.source.get(n, "rules")
            sample = reg_by.get(p["sample"]) if p["sample"] else None
            if sample is None:
                label = "none"
            elif p["confidence"] == "high" and src in ("rules", "both"):
                label = "certain"
            else:
                label = "check"
            raw = (r["raw_id"] or "").strip()
            raw = "" if raw == "-" else raw
            checks = []
            if sample is not None:
                checks = [
                    {"ok": raw == sample.id, "text": "ID written exactly as in the field registration" if raw == sample.id
                     else f"ID written “{raw or 'none'}”, registration says {sample.id}"},
                    {"ok": True, "text": "Sample exists in the register"},
                    {"ok": bool(sample.photo), "text": "Photo on file" if sample.photo else "Photo missing"},
                ]
                used.setdefault(sample.id, []).append(n)
            d = decisions.get(r["idx"])
            rows.append({
                "n": n, "idx": r["idx"], "raw_line": r["raw_line"], "raw_id": raw, "description": r["description"],
                "result": r["result"],
                "proposal": {"sample": p["sample"], "confidence": p["confidence"], "label": label,
                             "reason": p["reason"], "source": src, "sent_to_ai": n in run.sent},
                "chain": None if sample is None else {"sample": sample.id, "source": sample.source,
                                                      "location": sample.location, "material": f"{sample.material}, {sample.notes}",
                                                      "photo": sample.photo, "ship": self.store.object(rep["object_id"])["name"]},
                "checks": checks,
                "decision": None if d is None else {"state": d["state"], "sample": d["sample_code"], "by": d["decided_by"],
                                                    "at": d["decided_at"], "note": d["note"]},
            })
        flags = self.flags(rid, rows, reg)
        draft = self.store.draft_report(rid)
        ch9, ch10, manual = [], [], []
        photo_of = {s.id: s.photo for s in reg}
        for x in draft["linked"]:
            ch9.append({**x, "photo": photo_of.get(x["sample"], "")})
            c = classify(x["result"])
            if c and c["table"] == "A":
                ch10.append({"sample": x["sample"], "location": x["location"], "material": x["material"],
                             "substance": c["substance"], "table": "A", "photo": photo_of.get(x["sample"], ""),
                             "result": x["result"]})
            elif c and c["table"] == "?":
                manual.append({"sample": x["sample"], "result": x["result"], "note": c["note"]})
        total = len(rows)
        counts = {"total": total,
                  "certain": sum(r["proposal"]["label"] == "certain" for r in rows),
                  "check": sum(r["proposal"]["label"] == "check" for r in rows),
                  "none": sum(r["proposal"]["label"] == "none" for r in rows),
                  "decided": sum(r["decision"] is not None for r in rows),
                  "linked": sum(bool(r["decision"]) and r["decision"]["state"] in ("approved", "corrected") for r in rows)}
        ai = run.ai
        if ai is None:
            ai_note = "Every line was settled by the rules; the AI step was not needed."
        elif ai.problems:
            p0 = ai.problems[0]
            ai_note = ("No recorded stand-in answer for this report, so the rules' proposals are used." if "NoRecordedAnswer" in p0
                       else f"AI answer not used: {p0}. The rules' proposals are used.")
        else:
            ai_note = f"{len(run.sent)} of {total} lines went to the AI step (hand-written stand-in answers, no real AI yet)."
        audit = [{"at": e["decided_at"], "by": e["decided_by"],
                  "text": f"line {e['idx'] + 1} {e['state']}" + (f" → {e['sample_code']}" if e["sample_code"] else " (no link)") +
                          (f" · {e['note']}" if e["note"] else "")}
                 for e in self.store.audit_log(rid)]
        audit += [{"at": e["at"], "by": e["by"], "text": e["text"]} for e in self.agent_log if e["report_id"] == rid]
        audit.sort(key=lambda e: e["at"])
        return {"id": rid, "label": rep["label"], "ref": rep["report_ref"], "lab": rep["lab"],
                "rows": rows, "counts": counts, "flags": flags, "ai_note": ai_note,
                "draft_status": draft["status"], "ch9": ch9, "ch10": ch10, "ch10_manual": manual,
                "open_items": draft["open_items"], "audit": audit}

    def flags(self, rid: int, rows: List[dict], reg) -> List[dict]:
        out = []
        linked = {r["proposal"]["sample"] for r in rows if r["proposal"]["sample"]}
        for r in rows:
            p = r["proposal"]
            if p["sample"] and r["raw_id"] and r["raw_id"] != p["sample"]:
                out.append({"ref": r["raw_id"], "text": f"Sample ID “{r['raw_id']}” differs from the field notation {p['sample']}."})
            if p["sample"] is None and r["raw_id"]:
                if norm(r["raw_id"]) in {norm(s.id) for s in reg}:
                    out.append({"ref": r["raw_id"], "text": f"Line {r['n']}: the ID {r['raw_id']} and the description point to different samples. The inspector decides."})
                else:
                    out.append({"ref": r["raw_id"], "text": f"Lab result {r['raw_id']} does not belong to any known sample."})
            if p["sample"] is None and not r["raw_id"]:
                out.append({"ref": f"line {r['n']}", "text": "Lab line has no sample ID and no safe match."})
        for s in reg:
            if s.id not in linked:
                out.append({"ref": s.id, "text": f"Sample {s.id} ({s.location}) has no lab result."})
            elif not s.photo:
                out.append({"ref": s.id, "text": f"No photo ID for {s.id}. Required for the Materials List (photo + location for every hazardous material)."})
        for h in self.store.header_flags(rid):
            out.append({"ref": "header", "text": str(h)})
        return out


SERVICE: Service


class Handler(BaseHTTPRequestHandler):
    server_version = "James/0.1"

    def log_message(self, fmt, *args):      # keep the console quiet
        pass

    def send_json(self, obj, status=200):
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            data = (STATIC / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/state":
            q = dict(kv.split("=", 1) for kv in self.path.partition("?")[2].split("&") if "=" in kv)
            rid = int(q["report"]) if q.get("report", "").isdigit() else None
            self.send_json(SERVICE.view(rid))
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            path = self.path.split("?")[0]
            if path == "/api/reset":
                SERVICE.reset()
                rid = None
            elif path == "/api/demo":
                rid = SERVICE.load_demo(body.get("which", "b1"))
            elif path == "/api/report":
                rid = SERVICE.ingest(body.get("label", ""), body.get("text", ""))
            elif path == "/api/reread":
                rid = int(body["report_id"])
                SERVICE.read(rid)
            elif path == "/api/decide":
                rid = int(body["report_id"])
                SERVICE.decide(rid, int(body["idx"]), body.get("action", ""), body.get("by", ""),
                               body.get("sample"), (body.get("note") or "").strip())
            elif path == "/api/save-history":
                rid = int(body["report_id"])
                SERVICE.save_history(rid, body.get("by", ""))
            else:
                return self.send_json({"error": "not found"}, 404)
            self.send_json(SERVICE.view(rid))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            self.send_json({"error": str(e)}, 400)


def main(argv: Optional[List[str]] = None) -> int:
    global SERVICE
    ap = argparse.ArgumentParser(description="James app (fictitious data, no real AI).")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 only on a network you trust")
    ap.add_argument("--db", default=":memory:", help="a file name keeps the data between runs")
    args = ap.parse_args(argv)
    SERVICE = Service(args.db)
    srv = HTTPServer((args.host, args.port), Handler)
    print(f"James is running: http://{args.host}:{args.port}   (stop with Ctrl+C)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
