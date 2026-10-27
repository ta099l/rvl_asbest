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
import base64
import hashlib
import binascii
import json
import re
import sys
import tempfile
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
from app import export_odt                              # noqa: E402
from app.demo_data import SHIP                          # noqa: E402
from app.ihm import (PART_I, SECTIONS_2_3, TABLE_LINES, findings, load_thresholds,  # noqa: E402
                     part_i, sample_type, section_2_3, sum_quantities, table_line)
from ai.james_ai.hybrid import HybridRun, hybrid        # noqa: E402
from ai.james_ai.linker import Sample                   # noqa: E402
from james.store import EDITABLE, PROJECT_INFO, Store   # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
DEMO_REPLAY = ROOT / "ai" / "replays" / "demo_ship.json"
PRACTICE_ERRORS = 5          # wrong links seeded into a practice report (test case TC12)


def _fingerprint(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


# Which linking code made a proposal: changes whenever the linker or the hybrid pipeline changes.
LINKER_VERSION = _fingerprint(ROOT / "ai" / "james_ai" / "linker.py", ROOT / "ai" / "james_ai" / "hybrid.py")


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def norm(code: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


def minutes_between(a: str, b: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    return round((datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 60, 1)


class Service:
    """All state of one demo session. One lock: the demo has one user at a time."""

    def __init__(self, db_path: str = ":memory:"):
        self.lock = threading.RLock()
        self.db_path = db_path
        self.thresholds = load_thresholds()
        self.reset()

    # ---------- session ----------
    def reset(self) -> None:
        with self.lock:
            if getattr(self, "store", None) is not None:
                self.store.db.close()
            self.store = Store(self.db_path if self.db_path != ":memory:" else ":memory:")
            self.object_id = self.store.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"],
                                                   SHIP["project"], SHIP["samples"], SHIP.get("survey_date", ""),
                                                   SHIP.get("info"))
            self.demo_object = self.object_id
            self.runs: Dict[int, HybridRun] = {}
            self.read_at: Dict[int, str] = {}                 # report id -> when the agent last read it
            self.agent_log: List[dict] = []
            self.practice: Dict[int, Dict[int, str]] = {}   # report id -> {row idx: seeded wrong sample}
            self.client = ReplayClient(DEMO_REPLAY)
            self.load_demo("b1")

    def log(self, report_id: int, text: str) -> None:
        self.agent_log.append({"at": now(), "report_id": report_id, "by": "Agent", "text": text})

    # ---------- reports ----------
    def load_demo(self, key: str) -> int:
        with self.lock:
            if key not in SHIP["reports"]:
                raise ValueError("unknown demo report")
            if self.object_id != self.demo_object:
                raise ValueError("the demo reports belong to the demo ship; switch to it first, or paste or upload a report")
            rep = SHIP["reports"][key]
            return self.ingest(rep["label"], rep["text"], source_file="demo report (built in)", read_method="demo text")

    def ingest(self, label: str, text: str, source_file: str = "pasted text", read_method: str = "pasted text",
               sha256: Optional[str] = None) -> int:
        """Store a lab report with its evidence (where it came from, its fingerprint, how it was read)."""
        with self.lock:
            if not text or not text.strip():
                raise ValueError("the lab report text is empty")
            evidence = {"source_file": source_file, "read_method": read_method, "linker_version": LINKER_VERSION,
                        "source_sha256": sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()}
            rid = self.store.ingest_report(self.object_id, label.strip() or "Lab report", text, evidence)
            if not self.store.rows(rid):
                raise ValueError("no lab lines found: put the lines after a line with ---")
            self.read(rid)
            return rid

    def ingest_pdf(self, label: str, pdf: bytes) -> int:
        """Read a lab report PDF with the extractor, then handle it like pasted text."""
        from james.extract import extract_lab_text
        with self.lock, tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.pdf"
            path.write_bytes(pdf)
            try:
                ex = extract_lab_text(str(path))
            except Exception as e:                       # a broken or unreadable PDF is the user's to fix
                raise ValueError(f"the PDF could not be read: {e}")
            if "---\n" not in ex.text or not ex.text.split("---\n", 1)[1].strip():
                raise ValueError("no lab table found in the PDF. " + " ".join(ex.notes))
            rid = self.ingest(label or "Uploaded PDF", ex.text, source_file=label or "uploaded.pdf",
                              read_method={"text": "PDF text layer", "ocr": "PDF via OCR", "mixed": "PDF, text layer and OCR"}.get(ex.method, ex.method),
                              sha256=hashlib.sha256(pdf).hexdigest())
            for n in ex.notes:
                self.log(rid, n)
            self.log(rid, f"PDF read ({ex.pages} page(s), method: {ex.method}).")
            return rid

    def request_for(self, rid: int) -> dict:
        rep = self.store.db.execute("SELECT * FROM lab_report WHERE id=?", (rid,)).fetchone()
        register = [{"code": s.id, "location": s.location, "material": s.material, "colour": s.notes}
                    for s in self.store.sampled(rep["object_id"])]
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
        self.read_at[rid] = now()
        self.store.set_prompt_version(rid, run.ai.prompt_version if run.ai else None)
        n = len(req["rows"])
        self.log(rid, f"Read {n} lab lines. {n - len(run.sent)} settled by the rules, {len(run.sent)} sent to the AI step.")
        for i, p in enumerate(run.response["proposals"]):
            if p["sample"] is None:
                self.log(rid, f"Line {i + 1} ({req['rows'][i]['raw_id'] or 'no ID'}): no link found.")

    def reread(self, rid: int) -> None:
        """Read a report again with the current field registration (rules and AI)."""
        with self.lock:
            if self.store.signoff(rid):
                raise ValueError("this report is signed; its proposals can no longer change")
            self.store.relink(rid)
            self.read(rid)
            self.log(rid, "Read again with the current field registration.")

    # ---------- projects and field registration ----------
    def new_project(self, f: dict) -> None:
        with self.lock:
            self.object_id = self.store.add_object((f.get("name") or "").strip(), (f.get("kind") or "").strip(),
                                                   (f.get("ref") or "").strip(), (f.get("site") or "").strip(),
                                                   (f.get("project") or "").strip(), [], (f.get("survey_date") or "").strip(),
                                                   {k: (f.get(k) or "").strip() for k in PROJECT_INFO})

    def select_object(self, oid: int) -> None:
        with self.lock:
            if self.store.object(oid) is None:
                raise ValueError("unknown project")
            self.object_id = oid

    def add_sample(self, f: dict, by: str) -> None:
        with self.lock:
            fields = {k: (f.get(k) or "").strip() for k in EDITABLE}
            fields["status"] = fields["status"] or "sampled"
            self.store.add_sample(self.object_id, Sample(id=(f.get("code") or "").strip(), **fields), by)

    def update_sample(self, code: str, f: dict, by: str) -> None:
        with self.lock:
            self.store.update_sample(self.object_id, code, {k: f[k] for k in EDITABLE if k in f}, by)

    # ---------- practice review (TC12 / K10) ----------
    def load_practice(self) -> int:
        """Load demo report 1 with wrong links seeded in, to measure whether the reviewer really checks.

        The seeded proposals look like any other proposal. The score is shown only
        after every line is decided. A practice report never reaches the history or sign-off.
        """
        with self.lock:
            if self.object_id != self.demo_object:
                raise ValueError("the practice review uses the demo ship; switch to it first")
            rep = SHIP["reports"]["b1"]
            rid = self.ingest("Practice review (contains deliberate errors)", rep["text"],
                              source_file="demo report (built in)", read_method="demo text")
            props = self.runs[rid].response["proposals"]
            chosen = [i for i, p in enumerate(props) if p["sample"]][:PRACTICE_ERRORS]
            if len(chosen) < 2:
                raise ValueError("the demo report has too few links to build a practice review")
            # each chosen line gets the sample of the next chosen line: every one is wrong, none is used twice
            seeded = {i: props[chosen[(k + 1) % len(chosen)]]["sample"] for k, i in enumerate(chosen)}
            for i, wrong in seeded.items():
                props[i] = {**props[i], "sample": wrong, "confidence": "high",
                            "reason": "ID matches register exactly. Description agrees (100%)."}
                self.runs[rid].source[i + 1] = "rules"
            self.practice[rid] = seeded
            self.agent_log = [e for e in self.agent_log if e["report_id"] != rid]
            self.log(rid, "Practice review loaded. Some proposals are deliberately wrong; the score shows when every line is decided.")
            return rid

    def practice_score(self, rid: int) -> Optional[dict]:
        seeded = self.practice.get(rid)
        if seeded is None:
            return None
        dec = self.store.current_decisions(rid)
        if len(dec) < len(self.store.rows(rid)):
            return {"done": False, "seeded": len(seeded)}
        found, missed = [], []
        for i, wrong in sorted(seeded.items()):
            d = dec[i]
            caught = d["state"] == "rejected" or d["sample_code"] != wrong
            (found if caught else missed).append({"line": i + 1, "seeded": wrong,
                                                  "raw_id": self.store.rows(rid)[i]["raw_id"]})
        return {"done": True, "seeded": len(seeded), "found": len(found), "missed": missed,
                "target": "at least 80% (K10)", "passed": len(found) >= 0.8 * len(seeded)}

    # ---------- decisions ----------
    def decide(self, rid: int, idx: int, action: str, by: str, sample: Optional[str], note: str) -> None:
        with self.lock:
            by = (by or "").strip()
            if not by:
                raise ValueError("enter the inspector name first: every decision is signed")
            run = self.runs.get(rid)
            if run is None:
                raise ValueError("unknown report")
            if self.store.signoff(rid):
                raise ValueError("this report is signed: decisions can no longer change")
            prop = run.response["proposals"][idx]
            row = self.store.rows(rid)[idx]
            if action == "approve":
                if prop["sample"] is None:
                    raise ValueError("nothing is proposed for this line, so it cannot be approved: link it yourself or reject")
                if prop["sample"] == row["proposed_code"]:
                    self.store.decide(rid, idx, "approved", by=by, note=note)
                elif idx in self.practice.get(rid, {}):     # a seeded line: the note must not give it away
                    self.store.decide(rid, idx, "corrected", by=by, sample_code=prop["sample"], note=note)
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
            score = self.practice_score(rid)
            if score and score["done"]:
                self.log(rid, f"Practice result: {score['found']} of {score['seeded']} deliberate errors found.")

    def sign(self, rid: int, by: str) -> None:
        with self.lock:
            if rid in self.practice:
                raise ValueError("a practice report cannot be signed")
            if self.store.signoff(rid):
                raise ValueError("this report is already signed")
            view = self.report_view(rid, self.store.register(self.object_id))
            self.store.sign(rid, by, view["open_items"])
            self.log(rid, f"Signed by {by.strip()} as Technical Responsible Person. Report status: Final.")

    def export(self, rid: int):
        """The report filled into RVL's IHM template: (bytes, file name). Practice reports are refused."""
        with self.lock:
            if rid not in self.runs:
                raise ValueError("unknown report")
            if rid in self.practice:
                raise ValueError("a practice report cannot be exported")
            view = self.report_view(rid, self.store.register(self.object_id))
            data = export_odt.export(view)
            project = re.sub(r"[^A-Za-z0-9-]+", "_", dict(view["ihm"]["project"])["Project Number"] or "project")
            self.log(rid, f"IHM report exported to the RVL template ({'final' if view['signed'] else 'draft'}).")
            return data, f"IHM_{project}_{'final' if view['signed'] else 'DRAFT'}.odt"

    def save_history(self, rid: int, by: str) -> int:
        with self.lock:
            if not (by or "").strip():
                raise ValueError("enter the inspector name first")
            if rid in self.practice:
                raise ValueError("a practice report never goes into the ship's history")
            v = self.store.save_asset_version(self.object_id, rid, by.strip())
            return v

    # ---------- view for the screen ----------
    def view(self, rid: Optional[int] = None) -> dict:
        with self.lock:
            reports = [dict(r) for r in self.store.db.execute(
                "SELECT id,label,report_ref,lab,ingested_at FROM lab_report WHERE object_id=? ORDER BY id",
                (self.object_id,))]
            for r in reports:
                r["practice"] = r["id"] in self.practice
            obj = dict(self.store.object(self.object_id))
            obj["demo"] = self.object_id == self.demo_object
            reg = self.store.register(self.object_id)
            out = {"object": obj,
                   "objects": [{"id": o["id"], "name": o["name"], "project": o["project"]} for o in self.store.objects()],
                   "register": [{"code": s.id, "source": s.source, "location": s.location, "part": s.part,
                                 "material": s.material, "notes": s.notes, "photo": s.photo, "deck": s.deck,
                                 "status": s.status, "restriction": s.restriction, "drawing": s.drawing,
                                 "missing": [n for n, v in (("source", s.source), ("deck", s.deck), ("photo", s.photo),
                                                            ("drawing", s.drawing)) if not v and s.status == "sampled"]}
                                for s in reg],
                   "register_log": [{"at": e["changed_at"], "by": e["changed_by"], "code": e["code"],
                                     "action": e["action"], "detail": e["detail"]}
                                    for e in self.store.register_log(self.object_id)],
                   "reports": reports, "report": None,
                   "asset": self.store.asset(self.object_id),
                   "thresholds_note": "Thresholds: to confirm by RVL (app/thresholds.json)."}
            if not reports:
                return out
            rid = rid if rid in self.runs and rid in [r["id"] for r in reports] else reports[-1]["id"]
            out["report"] = self.report_view(rid, reg)
            return out

    def report_view(self, rid: int, reg) -> dict:
        run = self.runs[rid]
        reg_by = {s.id: s for s in reg}
        rep = self.store.db.execute("SELECT * FROM lab_report WHERE id=?", (rid,)).fetchone()
        decisions = self.store.current_decisions(rid)
        ship = self.store.object(rep["object_id"])["name"]
        rows = []
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
                    {"ok": bool(r["certificate"]), "text": "Certificate number on the lab line" if r["certificate"]
                     else "No certificate number"},
                ]
            d = decisions.get(r["idx"])
            rows.append({
                "n": n, "idx": r["idx"], "raw_line": r["raw_line"], "raw_id": raw, "description": r["description"],
                "result": r["result"], "method": r["method"] or "", "certificate": r["certificate"] or "",
                "quantity": r["quantity"] or "", "remarks": r["remarks"] or "",
                "findings": findings(r["result"], r["method"] or "", raw, self.thresholds),
                "proposal": {"sample": p["sample"], "confidence": p["confidence"], "label": label,
                             "reason": p["reason"], "source": src, "sent_to_ai": n in run.sent},
                "chain": None if sample is None else {"sample": sample.id, "source": sample.source, "deck": sample.deck,
                                                      "location": sample.location, "material": f"{sample.material}, {sample.notes}".strip(", "),
                                                      "photo": sample.photo, "ship": ship},
                "checks": checks,
                "decision": None if d is None else {"state": d["state"], "sample": d["sample_code"], "by": d["decided_by"],
                                                    "at": d["decided_at"], "note": d["note"]},
            })
        flags = self.flags(rid, rows, reg)
        report = self.ihm_sections(rid, rows, reg_by)
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
        signed = self.store.signoff(rid)
        if signed:
            audit.append({"at": signed["at"], "by": signed["by"],
                          "text": f"signed the report sections ({len(signed['open_items'])} open item(s) recorded)"})
        audit.sort(key=lambda e: e["at"])
        last = max((e["decided_at"] for e in self.store.audit_log(rid)), default=None)
        timing = {"started": rep["ingested_at"], "finished": last if counts["decided"] == total else None}
        timing["minutes"] = minutes_between(timing["started"], timing["finished"]) if timing["finished"] else None
        open_items = self.open_items(rid, rows, flags, report)
        changed = self.store.register_changed_at(rep["object_id"])
        evidence = {"source_file": rep["source_file"], "sha256": rep["source_sha256"], "read_method": rep["read_method"],
                    "linker_version": rep["linker_version"], "prompt_version": rep["prompt_version"],
                    "current_linker": LINKER_VERSION}
        return {"id": rid, "label": rep["label"], "ref": rep["report_ref"], "lab": rep["lab"],
                "evidence": evidence,
                "stale": bool(changed and changed > self.read_at.get(rid, rep["ingested_at"])) and not signed,
                "practice": rid in self.practice, "practice_score": self.practice_score(rid),
                "rows": rows, "counts": counts, "flags": flags, "ai_note": ai_note,
                "ihm": report, "open_items": open_items, "signed": signed, "timing": timing, "audit": audit}

    def ihm_sections(self, rid: int, rows: List[dict], reg_by: dict) -> dict:
        """The report sections in the layout of the RVL IHM template, from approved lines only.

        Project Information, Part I lists I-1 / I-2 / I-3 (each with its own columns),
        2.3.1-2.3.7 with a Source Record per source, 3 survey limitations and the fixed
        lines of Table A and Table B. Classification and list choice are proposals.
        """
        oid = self.store.db.execute("SELECT object_id FROM lab_report WHERE id=?", (rid,)).fetchone()["object_id"]
        obj, info = self.store.object(oid), self.store.project_info(oid)
        signed = self.store.signoff(rid)
        versions = self.store.db.execute("SELECT COUNT(*) n FROM signoff WHERE report_id=?", (rid,)).fetchone()["n"]
        project = [("Project Number", obj["project"]), ("Survey Location", obj["site"]), ("Vessel Name", obj["name"]),
                   ("Vessel Type", obj["kind"]), ("Client", info["client"]), ("Client Address", info["client_address"]),
                   ("Owner", info["owner"]), ("Owner Address", info["owner_address"]), ("Contractor", "James"),
                   ("Survey Period", info["survey_period"] or obj["survey_date"] or ""),
                   ("Survey Conducted By", info["surveyor"]), ("Technical Responsible Person", info["technical_responsible"]),
                   ("Project Coordinator", info["project_coordinator"]),
                   ("Report Status", "Final" if signed else "Draft"), ("Report Version", str(versions or 0)),
                   ("Report Valid Until", "")]
        sections = {no: {"no": no, "title": title, "samples": [], "records": [], "lab": []} for no, title, _ in SECTIONS_2_3}
        part1 = {k: [] for k in PART_I}
        lines: Dict[str, dict] = {}
        manual = []
        for r in rows:
            d = r["decision"]
            if not d or d["state"] == "rejected":
                continue
            s = reg_by[d["sample"]]
            qty = f"{s.quantity} {s.unit}".strip()
            where = " › ".join(x for x in (s.deck, s.location) if x)
            for f in r["findings"]:
                sec = sections[section_2_3(f["key"])]
                listed = f["status"] in ("above", "at")
                conclusion = (f"This concerns {f['name']}: {f['note']}." if listed or f["status"] == "below"
                              else f"{f['name']}: {f['note']}")
                sec["samples"].append({"sample": s.id, "deck": s.deck, "location": s.location,
                                       "material": ", ".join(x for x in (s.material, s.notes) if x),
                                       "type": sample_type(s.id), "result": f["text"]})
                sec["records"].append({"source": s.source or "–", "description": ", ".join(x for x in (s.part, s.material) if x),
                                       "sample": s.id, "certificate": r["certificate"], "location": where,
                                       "material": s.material, "result": f["text"], "quantity": qty,
                                       "conclusion": conclusion, "photo": s.photo, "drawing": s.drawing,
                                       "listed": listed})
                sec["lab"].append({"sample": s.id, "certificate": r["certificate"], "method": r["method"],
                                   "result": f["text"], "remarks": r["remarks"], "quantity": r["quantity"] or qty})
                if listed:
                    lst = part_i(s.material, s.part, s.location)
                    part1[lst].append({"sample": s.id, "part": s.part, "material": s.material, "location": where,
                                       "materials": f["name"], "quantity": qty, "remarks": f["note"],
                                       "table": f["table"], "at_threshold": f["status"] == "at"})
                    label = table_line(f["key"], s.material, s.part)
                    if label is None:
                        manual.append({"sample": s.id, "result": f["text"],
                                       "note": f"{f['name']} has no line in Table A or B of the template: the inspector decides where it goes"})
                    else:
                        ln = lines.setdefault(label, {"samples": [], "quantities": []})
                        ln["samples"].append(s.id)
                        ln["quantities"].append((s.quantity, s.unit))
                elif f["status"] == "unknown":
                    manual.append({"sample": s.id, "result": f["text"], "note": f["note"]})
        for k in part1:
            for i, x in enumerate(part1[k]):
                x["no"] = i + 1
        limitations = [{"no": i + 1, "sample": s.id, "deck": s.deck, "location": s.location, "material": s.material,
                        "restriction": s.restriction or "Not sampled",
                        "follow_up": "Treat as potentially containing hazardous materials (PCHM) until sampled"}
                       for i, s in enumerate(self.store.limitations(oid))]
        tables = {"A": [], "B": []}
        for label, t, _, _ in TABLE_LINES:
            ln = lines.get(label)
            total, unit = sum_quantities(ln["quantities"]) if ln else (None, "")
            tables[t].append({"line": label, "table": t, "samples": ln["samples"] if ln else [],
                              "quantity": total, "unit": unit, "found": bool(ln)})
        return {"project": project, "sections": list(sections.values()), "part1": part1, "part1_titles": PART_I,
                "limitations": limitations, "table_a": tables["A"], "table_b": tables["B"], "manual": manual}

    def open_items(self, rid: int, rows: List[dict], flags: List[dict], ihm: dict) -> List[str]:
        out = []
        undecided = sum(r["decision"] is None for r in rows)
        if undecided:
            out.append(f"{undecided} lab line(s) still need an inspector decision.")
        for f in flags:
            if f["kind"] in ("missing", "completeness"):
                out.append(f"{f['ref']}: {f['text']}")
        for m in ihm["manual"]:
            out.append(f"{m['sample']}: {m['note']}")
        for t in ("table_a", "table_b"):
            for x in ihm[t]:
                if x["found"] and x["quantity"] is None:
                    out.append(f"{x['line']} (Table {x['table']}): quantity and unit to be filled in by the inspector "
                               f"(not every source of {', '.join(x['samples'])} has a quantity in the same unit).")
        return out

    def flags(self, rid: int, rows: List[dict], reg) -> List[dict]:
        out = []
        linked = {r["proposal"]["sample"] for r in rows if r["proposal"]["sample"]}
        decided = {r["decision"]["sample"] for r in rows if r["decision"] and r["decision"]["sample"]}
        sampled = [s for s in reg if s.status != "not sampled"]
        for r in rows:
            p = r["proposal"]
            if p["sample"] and r["raw_id"] and r["raw_id"] != p["sample"]:
                out.append({"kind": "notation", "ref": r["raw_id"], "line": r["n"],
                            "text": f"Sample ID “{r['raw_id']}” differs from the field notation {p['sample']}."})
            if p["sample"] is None and r["raw_id"]:
                if norm(r["raw_id"]) in {norm(s.id) for s in sampled}:
                    out.append({"kind": "conflict", "ref": r["raw_id"], "line": r["n"],
                                "text": f"Line {r['n']}: the ID {r['raw_id']} and the description point to different samples. The inspector decides."})
                else:
                    out.append({"kind": "unknown", "ref": r["raw_id"], "line": r["n"],
                                "text": f"Lab result {r['raw_id']} does not belong to any known sample."})
            if p["sample"] is None and not r["raw_id"]:
                out.append({"kind": "unknown", "ref": f"line {r['n']}", "line": r["n"],
                            "text": "Lab line has no sample ID and no safe match."})
            if p["sample"] and not r["certificate"]:
                out.append({"kind": "completeness", "ref": r["raw_id"] or f"line {r['n']}", "line": r["n"],
                            "text": "No certificate number on this lab line. Needed for the full chain sample → certificate."})
        for s in sampled:
            if s.id not in linked and s.id not in decided:
                out.append({"kind": "missing", "ref": s.id, "line": None,
                            "text": f"Sample {s.id} ({s.material.lower()}, {s.location}) has no lab result."})
            elif not s.photo:
                out.append({"kind": "completeness", "ref": s.id, "line": None,
                            "text": f"No photo ID for {s.id}. Required for the Materials List (photo + location for every hazardous material)."})
            if s.id in linked | decided and not s.drawing:
                out.append({"kind": "completeness", "ref": s.id, "line": None,
                            "text": f"No drawing position for {s.id}. Needed to find the source back on the ship."})
        for s in reg:
            if s.status == "not sampled":
                out.append({"kind": "limitation", "ref": s.id, "line": None,
                            "text": f"{s.location} was not sampled ({s.restriction or 'no reason given'}). Listed under survey limitations as potentially hazardous."})
        for h in self.store.header_flags(rid):
            out.append({"kind": "header", "ref": "header", "line": None, "text": str(h)})
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
        elif path == "/api/export":
            q = dict(kv.split("=", 1) for kv in self.path.partition("?")[2].split("&") if "=" in kv)
            try:
                rid = int(q.get("report", ""))
                data, name = SERVICE.export(rid)
            except (ValueError, KeyError, FileNotFoundError) as e:
                return self.send_json({"error": str(e)}, 400)
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.oasis.opendocument.text")
            self.send_header("Content-Disposition", f'attachment; filename="{name}"')
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
                SERVICE.reread(rid)
            elif path == "/api/project":
                SERVICE.new_project(body)
                rid = None
            elif path == "/api/select-project":
                SERVICE.select_object(int(body["object_id"]))
                rid = None
            elif path == "/api/sample":
                SERVICE.add_sample(body, body.get("by", ""))
                rid = body.get("report_id")
            elif path == "/api/sample-update":
                SERVICE.update_sample(body.get("code", ""), body, body.get("by", ""))
                rid = body.get("report_id")
            elif path == "/api/decide":
                rid = int(body["report_id"])
                SERVICE.decide(rid, int(body["idx"]), body.get("action", ""), body.get("by", ""),
                               body.get("sample"), (body.get("note") or "").strip())
            elif path == "/api/save-history":
                rid = int(body["report_id"])
                SERVICE.save_history(rid, body.get("by", ""))
            elif path == "/api/sign":
                rid = int(body["report_id"])
                SERVICE.sign(rid, body.get("by", ""))
            elif path == "/api/practice":
                rid = SERVICE.load_practice()
            elif path == "/api/upload-pdf":
                data = base64.b64decode(body.get("pdf_base64", ""), validate=True)
                if len(data) > 20 * 1024 * 1024:
                    raise ValueError("the PDF is larger than 20 MB")
                rid = SERVICE.ingest_pdf(body.get("label", ""), data)
            else:
                return self.send_json({"error": "not found"}, 404)
            self.send_json(SERVICE.view(rid))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error) as e:
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
