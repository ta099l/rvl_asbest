"""James app: the screen and the small web server around Tasnim's linking code.

Run from the repository root:

    python3 app/server.py            (Windows: python app\\server.py)

then open http://127.0.0.1:8000 in a browser. Only the standard library is used.

What this file does, in one picture:

    browser  <->  server.py  <->  hybrid() (rules first, AI second)  +  Store (SQLite)

The AI part (ai/james_ai) only PROPOSES. This app shows every proposal with its
reason, and only a named inspector can approve, correct or reject a line. Nothing
reaches the draft chapters without that decision.

Replay answers are used by default. A Groq API client can be enabled explicitly
with JAMES_AI_PROVIDER=groq; use fictional data unless RVL has approved more.
"""
import argparse
import types
import base64
import hashlib
import binascii
import json
import os
import re
import sys
import tempfile
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.james_ai.ai_step import ReplayClient            # noqa: E402
from ai.james_ai.contract import ContractError          # noqa: E402
from app import export_odt, photos                      # noqa: E402
from app.auth import COOKIE, LOGIN_PAGE, SESSION_SECONDS, Auth, parse_users  # noqa: E402
from app.demo_data import SHIP                          # noqa: E402
from app.ihm import (GROUPS, PART_I, SECTIONS_2_3, TABLE_LINES, findings, group_for_code,  # noqa: E402
                     group_section, load_thresholds, next_code, part_i, sample_type, section_2_3,
                     sum_quantities, table_line)
from ai.james_ai.hybrid import HybridRun, hybrid        # noqa: E402
from ai.james_ai.linker import Sample                   # noqa: E402
from james.store import EDITABLE, OBJECT_FIELDS, PROJECT_INFO, SOURCE_PHOTO_ACTIONS, Store   # noqa: E402

STATIC = Path(__file__).resolve().parent / "static"
# The condition values of a source, in one place (to confirm with Rolf).
CONDITIONS = json.loads((Path(__file__).resolve().parent / "conditions.json").read_text(encoding="utf-8"))["values"]
DEMO_REPLAY = ROOT / "ai" / "replays" / "demo_ship.json"
PRACTICE_ERRORS = 5          # wrong links seeded into a practice report (test case TC12)
MAX_JSON_BYTES = 25 * 1024 * 1024     # every JSON request; refused BEFORE the body is read
MAX_PDF_BYTES = 18 * 1024 * 1024      # a PDF travels as base64 inside JSON (+33%), so 18 MB fits in 25 MB


def _fingerprint(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


# Which linking code made a proposal: changes whenever the linker or the hybrid pipeline changes.
LINKER_VERSION = _fingerprint(ROOT / "ai" / "james_ai" / "linker.py", ROOT / "ai" / "james_ai" / "hybrid.py")


def _one_letter_apart(a: str, b: str) -> bool:
    """True when two prefixes differ by exactly one letter added, removed or changed (MM/HM, OS/ODS)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def norm(code: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


def minutes_between(a: str, b: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    return round((datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 60, 1)


class Service:
    """All state of one demo session. One lock: the demo has one user at a time."""

    def __init__(self, db_path: str = ":memory:", data_dir: Optional[str] = None):
        # One lock for everything that touches the database. The server runs one thread per request
        # (ThreadingHTTPServer); SQLite gets one shared connection, and this lock lets one request at a
        # time use it. Reading an upload and resizing a photo happen outside the lock.
        self.lock = threading.RLock()
        self.db_path = db_path
        self.data_dir = Path(data_dir) if data_dir else photos.data_dir(db_path)
        self.thresholds = load_thresholds()
        self.reset()

    # ---------- session ----------
    def reset(self) -> None:
        with self.lock:
            if getattr(self, "store", None) is not None:
                self.store.db.close()
            self.store = Store(self.db_path if self.db_path != ":memory:" else ":memory:",
                               group_of=lambda code: group_for_code(code)["key"])
            # A database file (--db) keeps the demo ship between runs: reuse it instead of adding a copy each start.
            known = next((o["id"] for o in self.store.objects()
                          if (o["name"], o["ref"], o["project"]) == (SHIP["name"], SHIP["ref"], SHIP["project"])), None)
            self.object_id = known or self.store.add_object(SHIP["name"], SHIP["kind"], SHIP["ref"], SHIP["site"],
                                                            SHIP["project"], SHIP["samples"], SHIP.get("survey_date", ""),
                                                            SHIP.get("info"))
            if known is None:
                for no, fields in SHIP.get("sources", {}).items():     # the demo ship's bronbladen
                    self.store.update_source(self.object_id, no, fields, "James (demo data)")
            self.demo_object = self.object_id
            self.runs: Dict[int, HybridRun] = {}
            self.read_at: Dict[int, str] = {}                 # report id -> when the agent last read it
            self.agent_log: List[dict] = []
            self.practice: Dict[int, Dict[int, str]] = {}   # report id -> {row idx: seeded wrong sample}
            provider = os.environ.get("JAMES_AI_PROVIDER", "replay").strip().lower()
            if provider == "replay":
                self.client = ReplayClient(DEMO_REPLAY)
            elif provider == "groq":
                from ai.james_ai.client_groq import GroqClient
                self.client = GroqClient()
            else:
                raise RuntimeError("JAMES_AI_PROVIDER must be 'replay' or 'groq'")
            if known is None:
                self.load_demo("b1")

    def oid(self, object_id=None) -> int:
        """The project a request is about. The browser sends it with every request (from its URL), so two
        windows on two projects never affect each other. Without one, the last opened project is used:
        a fallback for old callers and the tests."""
        if object_id in (None, ""):
            return self.object_id
        try:
            oid = int(object_id)
        except (TypeError, ValueError):
            raise ValueError("unknown project")
        if self.store.object(oid) is None:
            raise ValueError("unknown project")
        return oid

    def report_object(self, rid: int) -> int:
        """The project a lab report belongs to: sign, export and history follow the report, not the screen."""
        row = self.store.db.execute("SELECT object_id FROM lab_report WHERE id=?", (rid,)).fetchone()
        if row is None:
            raise ValueError("unknown report")
        return row["object_id"]

    def log(self, report_id: int, text: str) -> None:
        self.agent_log.append({"at": now(), "report_id": report_id, "by": "Agent", "text": text})

    # ---------- reports ----------
    def load_demo(self, key: str, object_id=None) -> int:
        with self.lock:
            if key not in SHIP["reports"]:
                raise ValueError("unknown demo report")
            if self.oid(object_id) != self.demo_object:
                raise ValueError("the demo reports belong to the demo ship; switch to it first, or paste or upload a report")
            rep = SHIP["reports"][key]
            return self.ingest(rep["label"], rep["text"], source_file="demo report (built in)", read_method="demo text",
                               object_id=self.demo_object)

    def ingest(self, label: str, text: str, source_file: str = "pasted text", read_method: str = "pasted text",
               sha256: Optional[str] = None, object_id=None) -> int:
        """Store a lab report with its evidence (where it came from, its fingerprint, how it was read)."""
        with self.lock:
            if not text or not text.strip():
                raise ValueError("the lab report text is empty")
            evidence = {"source_file": source_file, "read_method": read_method, "linker_version": LINKER_VERSION,
                        "source_sha256": sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()}
            rid = self.store.ingest_report(self.oid(object_id), label.strip() or "Lab report", text, evidence)
            if not self.store.rows(rid):
                raise ValueError("no lab lines found: put the lines after a line with ---")
            self.read(rid)
            return rid

    def ingest_pdf(self, label: str, pdf: bytes, object_id=None) -> int:
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
                              sha256=hashlib.sha256(pdf).hexdigest(), object_id=object_id)
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
        self.save_run(rid)
        n = len(req["rows"])
        self.log(rid, f"Read {n} lab lines. {n - len(run.sent)} settled by the rules, {len(run.sent)} sent to the AI step.")
        for i, p in enumerate(run.response["proposals"]):
            if p["sample"] is None:
                self.log(rid, f"Line {i + 1} ({req['rows'][i]['raw_id'] or 'no ID'}): no link found.")

    def save_run(self, rid: int) -> None:
        """Keep the agent's proposals in the database, so a restart does not ask the AI again."""
        run = self.runs[rid]
        pv = run.ai.prompt_version if run.ai else None
        self.store.save_ai(rid, [{"idx": i, "sample": p["sample"], "confidence": p["confidence"], "reason": p["reason"],
                                  "source": run.source.get(i + 1, "rules"), "sent": (i + 1) in run.sent}
                                 for i, p in enumerate(run.response["proposals"])], pv)

    def saved_run(self, rid: int) -> Optional[HybridRun]:
        """Rebuild the agent's run from the saved proposals; None when this report has none saved."""
        rows = self.store.saved_ai(rid)
        if rows is None:
            return None
        props = [{"n": r["idx"] + 1, "sample": r["ai_code"], "confidence": r["ai_confidence"], "reason": r["ai_reason"]}
                 for r in rows]
        sent = [r["idx"] + 1 for r in rows if r["ai_sent"]]
        ai = None
        if sent:   # what the screen needs to explain the AI step: which prompt, and whether the answer was used
            unusable = [r["ai_reason"].split("AI not used: ", 1)[1].rstrip(".") for r in rows
                        if r["ai_source"] == "rules (ai unusable)" and "AI not used: " in (r["ai_reason"] or "")]
            ai = types.SimpleNamespace(prompt_version=rows[0]["ai_prompt_version"], problems=unusable[:1])
        return HybridRun({"proposals": props}, {r["idx"] + 1: r["ai_source"] for r in rows}, sent, ai)

    def is_practice(self, rid: int) -> bool:
        """A practice report is remembered in memory; after a restart its label still marks it."""
        if rid in self.practice:
            return True
        rep = self.store.db.execute("SELECT label FROM lab_report WHERE id=?", (rid,)).fetchone()
        return bool(rep) and rep["label"].startswith("Practice review")

    def run_for(self, rid: int) -> HybridRun:
        """The agent's proposals for a report. They live in memory only, so after a restart of the app
        the report is read again; the inspector's decisions are in the database and stay."""
        if rid not in self.runs:
            saved = self.saved_run(rid)
            if saved is not None:
                self.runs[rid] = saved               # the saved proposals: no new AI call after a restart
            else:
                self.read(rid)
                self.log(rid, "Read again: this report was read before proposals were saved.")
        return self.runs[rid]

    def reread(self, rid: int) -> None:
        """Read a report again with the current field registration (rules and AI)."""
        with self.lock:
            if self.store.signoff(rid):
                raise ValueError("this report is signed; its proposals can no longer change")
            self.store.relink(rid)
            self.read(rid)
            self.log(rid, "Read again with the current field registration.")

    # ---------- projects and field registration ----------
    def new_project(self, f: dict) -> int:
        with self.lock:
            self.object_id = self.store.add_object((f.get("name") or "").strip(), (f.get("kind") or "").strip(),
                                                   (f.get("ref") or "").strip(), (f.get("site") or "").strip(),
                                                   (f.get("project") or "").strip(), [], (f.get("survey_date") or "").strip(),
                                                   {k: (f.get(k) or "").strip() for k in PROJECT_INFO})
            return self.object_id

    def update_project(self, f: dict, by: str, object_id=None) -> None:
        """Save the intake page: the project details, logged old -> new."""
        with self.lock:
            changes = {k: f[k] for k in (*OBJECT_FIELDS, *PROJECT_INFO) if k in f}
            self.store.update_object(self.oid(object_id), changes, by)

    def select_object(self, oid: int) -> None:
        with self.lock:
            if self.store.object(oid) is None:
                raise ValueError("unknown project")
            self.object_id = oid

    def add_sample(self, f: dict, by: str, object_id=None) -> None:
        with self.lock:
            fields = {k: (f.get(k) or "").strip() for k in EDITABLE}
            fields["status"] = fields["status"] or "sampled"
            oid = self.oid(object_id)
            self.check_condition(f, fields["source"])
            self.store.add_sample(oid, Sample(id=(f.get("code") or "").strip(), **fields), by)
            self.save_condition(oid, f, fields["source"], by)

    def update_sample(self, code: str, f: dict, by: str, object_id=None) -> None:
        with self.lock:
            oid = self.oid(object_id)
            current = next((s for s in self.store.register(oid) if s.id == code), None)
            source = (f["source"] if "source" in f else (current.source if current else "")) or ""
            self.check_condition(f, source.strip())
            self.store.update_sample(oid, code, {k: f[k] for k in EDITABLE if k in f}, by)
            self.save_condition(oid, f, source.strip(), by)

    @staticmethod
    def check_condition(f: dict, source: str) -> None:
        """A condition belongs to a source (bronblad), not to a sample."""
        c = (f.get("condition") or "").strip()
        if not c:
            return
        if not source:
            raise ValueError("a condition belongs to a source: enter the source number first")
        if c not in CONDITIONS:
            raise ValueError("condition must be one of: " + ", ".join(CONDITIONS))

    def save_condition(self, oid: int, f: dict, source: str, by: str) -> None:
        if "condition" in f and source:
            self.store.update_source(oid, source, {"condition": f.get("condition") or ""}, by)

    # ---------- practice review (TC12 / K10) ----------
    def load_practice(self, object_id=None) -> int:
        """Load demo report 1 with wrong links seeded in, to measure whether the reviewer really checks.

        The seeded proposals look like any other proposal. The score is shown only
        after every line is decided. A practice report never reaches the history or sign-off.
        """
        with self.lock:
            if self.oid(object_id) != self.demo_object:
                raise ValueError("the practice review uses the demo ship; switch to it first")
            rep = SHIP["reports"]["b1"]
            rid = self.ingest("Practice review (contains deliberate errors)", rep["text"],
                              source_file="demo report (built in)", read_method="demo text", object_id=self.demo_object)
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
            self.save_run(rid)
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
            if self.store.db.execute("SELECT 1 FROM lab_report WHERE id=?", (rid,)).fetchone() is None:
                raise ValueError("unknown report")
            run = self.run_for(rid)
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
            if self.is_practice(rid):
                raise ValueError("a practice report cannot be signed")
            if self.store.signoff(rid):
                raise ValueError("this report is already signed")
            view = self.report_view(rid, self.store.register(self.report_object(rid)))
            self.store.sign(rid, by, view["open_items"])
            self.log(rid, f"Signed by {by.strip()} as Technical Responsible Person. Report status: Final.")

    def export(self, rid: int):
        """The report filled into RVL's IHM template: (bytes, file name). Practice reports are refused."""
        with self.lock:
            if self.store.db.execute("SELECT 1 FROM lab_report WHERE id=?", (rid,)).fetchone() is None:
                raise ValueError("unknown report")
            if self.is_practice(rid):
                raise ValueError("a practice report cannot be exported")
            view = self.report_view(rid, self.store.register(self.report_object(rid)))
            data = export_odt.export(view)
            project = re.sub(r"[^A-Za-z0-9-]+", "_", dict(view["ihm"]["project"])["Project Number"] or "project")
            self.log(rid, f"IHM report exported to the RVL template ({'final' if view['signed'] else 'draft'}).")
            return data, f"IHM_{project}_{'final' if view['signed'] else 'DRAFT'}.odt"

    def save_history(self, rid: int, by: str) -> int:
        with self.lock:
            if not (by or "").strip():
                raise ValueError("enter the inspector name first")
            if self.is_practice(rid):
                raise ValueError("a practice report never goes into the ship's history")
            v = self.store.save_asset_version(self.report_object(rid), rid, by.strip())
            return v

    # ---------- photos ----------
    def upload_photo(self, object_id, name: str, data: bytes, by: str) -> dict:
        """Check, store and number one uploaded photo and propose its link. The slow part (Pillow) runs
        outside the lock. A photo that is already in this project (same sha256) is skipped."""
        if not (by or "").strip():
            raise ValueError("enter the inspector name first: every upload is signed")
        name = Path(name or "photo.jpg").name[:200]
        with self.lock:
            oid = self.oid(object_id)
        sha = photos.sha256(data)
        with self.lock:
            dup = self.store.photo_by_sha(oid, sha)
        if dup:
            return {"skipped": True, "message": f"{name} is already here as photo {dup['photo_no']}: skipped"}
        full, thumb, w, h = photos.process(data)              # refuses anything that is not a real JPG or PNG
        photos.store_files(self.data_dir, oid, sha, full, thumb)
        with self.lock:
            dup = self.store.photo_by_sha(oid, sha)           # another window may have sent the same file meanwhile
            if dup:
                return {"skipped": True, "message": f"{name} is already here as photo {dup['photo_no']}: skipped"}
            f = {"stored_name": sha, "original_name": name, "sha256": sha, "mime": "image/jpeg", "width": w, "height": h}
            rows = self.store.photos(oid)
            fill = next((r for r in rows if r["stored_name"] is None and photos.matches_photo_no(name, r["photo_no"])), None)
            if fill is not None:
                pid = self.store.add_photo_file(oid, f, by, fill_id=fill["id"])
                return {"id": pid, "photo_no": fill["photo_no"], "linked": bool(fill["sample_code"] or fill["source_no"]),
                        "message": f"{name} -> photo {fill['photo_no']} (its number was already registered)"}
            reg = self.store.register(oid)
            sample, source, reason = photos.propose(name, {x.id: x.source for x in reg}, self.store.sources(oid))
            f.update(photo_no=photos.next_photo_no(r["photo_no"] for r in rows),
                     proposed_sample=sample, proposed_source=source, proposal_reason=reason)
            pid = self.store.add_photo_file(oid, f, by)
            return {"id": pid, "photo_no": f["photo_no"], "linked": bool(sample or source),
                    "message": f"{name} -> photo {f['photo_no']}: {reason}"}

    def photo_file(self, object_id, photo_id: int, thumb: bool) -> Path:
        """The file of a photo, only when the photo belongs to the project the request names."""
        if object_id in (None, ""):
            raise ValueError("name the project")
        oid = self.oid(object_id)
        row = self.store.photo(photo_id)
        if row is None or row["object_id"] != oid or not row["stored_name"]:
            raise ValueError("photo not found in this project")
        return photos.photo_path(self.data_dir, oid, row["stored_name"], thumb=thumb)

    def default_description(self, oid: int, sample_code: Optional[str], source_no: Optional[str]) -> str:
        """'<location> - <material/application>' of the photo's sample, or the first sample of its source."""
        reg = self.store.register(oid)
        s = next((x for x in reg if x.id == sample_code), None) or next((x for x in reg if source_no and x.source == source_no), None)
        if s is None:
            return ""
        return f"{s.location} - {', '.join(x for x in (s.material, s.part) if x)}"

    def update_photo(self, object_id, photo_id: int, f: dict, by: str) -> None:
        """Number, description or link of one photo. A link to a sample also sets that sample's source.
        An empty description is filled from the linked source."""
        with self.lock:
            oid = self.oid(object_id)
            row = self.store.photo(photo_id)
            if row is None or row["object_id"] != oid:
                raise ValueError("unknown photo in this project")
            changes = {k: f[k] for k in ("photo_no", "description") if k in f}
            if "link" in f:                                   # "sample:MM-1", "source:B01" or "" (not linked)
                kind, _, value = (f.get("link") or "").partition(":")
                sample = value if kind == "sample" else None
                source = value if kind == "source" else None
                if sample:
                    source = next((x.source for x in self.store.register(oid) if x.id == sample), None) or None
                changes.update(sample_code=sample, source_no=source)
                if (sample or source) and not (changes.get("description") or row["description"]):
                    changes["description"] = self.default_description(oid, sample, source)
            self.store.update_photo(oid, photo_id, changes, by)

    def accept_photo_proposals(self, object_id, by: str) -> int:
        """Accept every proposed link of photos that are not linked yet: one click for the whole batch."""
        with self.lock:
            oid = self.oid(object_id)
            n = 0
            for r in self.store.photos(oid):
                if not (r["sample_code"] or r["source_no"]) and (r["proposed_sample"] or r["proposed_source"]):
                    link = f"sample:{r['proposed_sample']}" if r["proposed_sample"] else f"source:{r['proposed_source']}"
                    self.update_photo(oid, r["id"], {"link": link}, by)
                    n += 1
            return n

    def photos_with_file(self, oid: int, reg) -> Dict[str, List[str]]:
        """Photo numbers with a file, per sample code: its own photos plus those of its source."""
        rows = [r for r in self.store.photos(oid) if r["stored_name"]]
        out = {}
        for s in reg:
            out[s.id] = [r["photo_no"] for r in rows if r["sample_code"] == s.id or (s.source and r["source_no"] == s.source)]
        return out

    def set_certificate(self, rid: int, idx: int, certificate: str, by: str) -> None:
        with self.lock:
            if self.store.signoff(rid):
                raise ValueError("this report is signed: it can no longer change")
            self.store.set_certificate(rid, idx, certificate, by)

    def confirm_check(self, object_id, key: str, by: str) -> None:
        """Mark a link-check warning as checked (only warnings can be confirmed; errors must be fixed)."""
        with self.lock:
            oid = self.oid(object_id)
            issue = next((i for i in self.link_check(oid) if i.get("key") == key), None)
            if issue is None or issue["severity"] != "warning":
                raise ValueError("only an open warning of the link check can be marked as checked")
            self.store.confirm_check(oid, key, issue["text"], by)

    # ---------- link check: one list for the bronbladen page, the export and sign-off ----------
    def link_check(self, oid: int) -> List[dict]:
        """Every broken link between photo, source, sample, lab result and certificate, one line each,
        with where to fix it. Errors first. An empty list means all links are complete."""
        from ai.james_ai.linker import alias_key, code_parts, std_prefix
        reg = self.store.register(oid)
        sources = self.store.sources(oid)
        rows = self.store.photos(oid)
        issues: List[dict] = []

        def add(rule, severity, text, fix, key=None):
            issues.append({"rule": rule, "severity": severity, "text": text, "fix": fix, "key": key})

        group = lambda code: group_for_code(code)["key"]
        for r in rows:
            if not (r["sample_code"] or r["source_no"]):
                add("photo_unlinked", "error", f"Photo {r['photo_no']}" + (f" ({r['original_name']})" if r["original_name"] else " (no file yet)")
                    + " is not linked to a source or sample.", {"page": "fieldwork", "photo": r["id"]})
        by_source = {no: [s.id for s in reg if s.source == no] for no in sources}
        for no, codes in by_source.items():
            n = sum(1 for r in rows if r["stored_name"] and (r["source_no"] == no or r["sample_code"] in codes))
            fix = {"page": "fieldwork", "photos": True, "group": group(codes[0]) if codes else None}
            if n == 0:
                add("source_no_photo", "error", f"Source {no} has no photo yet" + (f" ({', '.join(codes)})." if codes else "."), fix)
            elif n > 4:
                add("source_too_many", "error", f"Source {no} has {n} photos; a bronblad holds at most 4. Unlink the extra ones.", fix)
        for s in reg:
            if not (s.source or "").strip():
                add("sample_no_source", "error", f"Sample {s.id} has no source number.",
                    {"page": "fieldwork", "group": group(s.id), "sample": s.id})
        reports = [r["id"] for r in self.store.db.execute("SELECT id FROM lab_report WHERE object_id=? ORDER BY id", (oid,))
                   if not self.is_practice(r["id"])]
        approved, lines = set(), []
        for rid in reports:
            dec = self.store.current_decisions(rid)
            for r in self.store.rows(rid):
                d = dec.get(r["idx"])
                lines.append((rid, r, d))
                if d and d["state"] in ("approved", "corrected"):
                    approved.add(d["sample_code"])
        keys = {alias_key(s.id): s.id for s in reg}
        for s in reg:
            if s.status != "not sampled" and s.id not in approved:
                line = next(((rid, r) for rid, r, d in lines if d is None and r["ai_code"] == s.id), None)
                fix = ({"page": "lab", "report": line[0], "line": line[1]["idx"]} if line
                       else {"page": "fieldwork", "group": group(s.id), "sample": s.id})
                add("sample_no_result", "error", f"Sample {s.id} has no approved lab result. "
                    + ("Approve its lab line." if line else "Read the lab report with its result, or register it as not sampled with the reason."), fix)
        for rid, r, d in lines:
            raw = (r["raw_id"] or "").strip()
            if d and d["state"] in ("approved", "corrected") and not (r["certificate"] or "").strip():
                add("result_no_certificate", "error", f"Approved result {raw or 'line ' + str(r['idx'] + 1)} → {d['sample_code']} has no certificate number.",
                    {"page": "lab", "report": rid, "line": r["idx"]})
            if raw and raw != "-" and d is None and alias_key(raw) not in keys:
                add("code_not_in_register", "error", f"Lab line {r['idx'] + 1}: code {raw} is not in the register.",
                    {"page": "lab", "report": rid, "line": r["idx"]})
        seen = {}
        for s in reg:                                        # the same sample written twice (M-3 and MM-3)
            k = alias_key(s.id)
            if k and k in seen:
                add("same_sample_twice", "error", f"{seen[k]} and {s.id} are the same sample in two notations.",
                    {"page": "fieldwork", "group": group(s.id), "sample": s.id})
            elif k:
                seen[k] = s.id
        confirmed = self.store.confirmed_checks(oid)
        parts = [(s.id, code_parts(s.id)) for s in reg]
        for i, (a, pa) in enumerate(parts):                  # MM-12 and HM-12: one letter apart, same number
            for b, pb in parts[i + 1:]:
                if pa and pb and pa[1] == pb[1] and _one_letter_apart(std_prefix(pa[0]), std_prefix(pb[0])):
                    key = f"{a}/{b}"
                    if key not in confirmed:
                        add("prefix_only", "warning", f"Check: {a} and {b} differ only by prefix. A lab could mix them up.",
                            {"confirm": key}, key)
        issues.sort(key=lambda i: i["severity"] != "error")
        return issues

    # ---------- view for the screen ----------
    def view(self, rid: Optional[int] = None, object_id=None) -> dict:
        """Everything the screen shows for one project. A report of another project is never shown in it."""
        with self.lock:
            oid = self.oid(object_id)
            reports = [dict(r) for r in self.store.db.execute(
                "SELECT id,label,report_ref,lab,ingested_at FROM lab_report WHERE object_id=? ORDER BY id",
                (oid,))]
            for r in reports:
                r["practice"] = self.is_practice(r["id"])
            obj = dict(self.store.object(oid))
            obj["demo"] = oid == self.demo_object
            obj["info"] = self.store.project_info(oid)
            reg = self.store.register(oid)
            sources = self.store.sources(oid)
            shots = self.photos_with_file(oid, reg)
            # lab lines without a decision, over every report of this project (badge on the Lab results tab)
            open_lines = self.store.db.execute(
                "SELECT COUNT(*) FROM lab_row r JOIN lab_report l ON l.id = r.report_id WHERE l.object_id=? "
                "AND NOT EXISTS (SELECT 1 FROM decision d WHERE d.lab_row_id = r.id)", (oid,)).fetchone()[0]
            out = {"object": obj,
                   "objects": [{"id": o["id"], "name": o["name"], "project": o["project"]} for o in self.store.objects()],
                   "register": [{"code": s.id, "source": s.source, "location": s.location, "part": s.part,
                                 "material": s.material, "notes": s.notes, "photo": ", ".join(shots[s.id]), "deck": s.deck,
                                 "photos": len(shots[s.id]),
                                 "status": s.status, "restriction": s.restriction, "drawing": s.drawing,
                                 "quantity": s.quantity, "unit": s.unit, "group": group_for_code(s.id),
                                 "condition": (sources[s.source]["condition"] or "") if s.source in sources else "",
                                 "missing": [n for n, v in (("source", s.source), ("deck", s.deck), ("photo", shots[s.id]),
                                                            ("drawing", s.drawing)) if not v and s.status == "sampled"]}
                                for s in reg],
                   "register_log": [{"at": e["changed_at"], "by": e["changed_by"], "code": e["code"],
                                     "action": e["action"], "detail": e["detail"]}
                                    for e in self.store.register_log(oid)
                                    if not e["action"].startswith(SOURCE_PHOTO_ACTIONS)],   # those show on the bronbladen
                   "photos": [{"id": r["id"], "photo_no": r["photo_no"], "file": bool(r["stored_name"]),
                               "original_name": r["original_name"] or "", "description": r["description"] or "",
                               "sample": r["sample_code"], "source": r["source_no"],
                               "proposed_sample": r["proposed_sample"], "proposed_source": r["proposed_source"],
                               "proposal_reason": r["proposal_reason"] or ""} for r in self.store.photos(oid)],
                   "sources": sorted(sources),
                   "link_check": self.link_check(oid),
                   "photo_max_mb": photos.max_photo_bytes() // (1024 * 1024),
                   "conditions": CONDITIONS,
                   "reports": reports, "report": None, "open_lines": open_lines,
                   "groups": self.groups_view(reg),
                   "asset": self.store.asset(oid),
                   "thresholds_note": "Thresholds: to confirm by RVL (app/thresholds.json)."}
            if not reports:
                return out
            rid = rid if rid in [r["id"] for r in reports] else reports[-1]["id"]
            out["report"] = self.report_view(rid, reg)
            return out

    @staticmethod
    def groups_view(reg) -> List[dict]:
        """The fieldwork tabs: every substance group with its report section, how many samples it
        holds, and the next free code. The screen keeps no copy of this mapping."""
        codes = [s.id for s in reg]
        out = []
        for key, label, main, always in GROUPS:
            mine = [c for c in codes if group_for_code(c)["key"] == key]
            out.append({"key": key, "label": label, "section": group_section(key), "always": always,
                        "count": len(mine), "unknown": sum(group_for_code(c)["unknown"] for c in mine),
                        "next_code": next_code(codes, key)})
        return out

    def report_view(self, rid: int, reg) -> dict:
        run = self.run_for(rid)
        shots = self.photos_with_file(self.report_object(rid), reg)
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
                    {"ok": bool(shots[sample.id]), "text": f"Photo {', '.join(shots[sample.id])}" if shots[sample.id] else "Photo missing"},
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
                                                      "photo": ", ".join(shots[sample.id]), "ship": ship},
                "checks": checks,
                "decision": None if d is None else {"state": d["state"], "sample": d["sample_code"], "by": d["decided_by"],
                                                    "at": d["decided_at"], "note": d["note"]},
            })
        flags = self.flags(rid, rows, reg, shots)
        report = self.ihm_sections(rid, rows, reg_by, shots)
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
                "practice": self.is_practice(rid), "practice_score": self.practice_score(rid),
                "rows": rows, "counts": counts, "flags": flags, "ai_note": ai_note,
                "ihm": report, "open_items": open_items, "signed": signed, "timing": timing, "audit": audit}

    def ihm_sections(self, rid: int, rows: List[dict], reg_by: dict, shots: Optional[Dict[str, List[str]]] = None) -> dict:
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
        sources = self.store.sources(oid)
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
                # The bronblad reads the source table first and falls back to the sample, as before.
                src = sources.get(s.source) if s.source else None
                pick = lambda k: (src[k] or "").strip() if src is not None and src[k] else ""
                src_qty = " ".join(x for x in (pick("quantity"), pick("unit")) if x)
                sec["records"].append({"source": s.source or "–",
                                       "description": pick("description") or ", ".join(x for x in (s.part, s.material) if x),
                                       "sample": s.id, "certificate": r["certificate"], "location": where,
                                       "material": s.material, "result": f["text"], "quantity": src_qty or qty,
                                       "condition": pick("condition"),
                                       "conclusion": pick("conclusion") or conclusion,
                                       "photo": ", ".join((shots or {}).get(s.id, [])), "drawing": s.drawing,
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
        for i in self.link_check(self.report_object(rid)):          # the same list as the bronbladen page
            out.append(f"Link check ({i['severity']}): {i['text']}")
        for t in ("table_a", "table_b"):
            for x in ihm[t]:
                if x["found"] and x["quantity"] is None:
                    out.append(f"{x['line']} (Table {x['table']}): quantity and unit to be filled in by the inspector "
                               f"(not every source of {', '.join(x['samples'])} has a quantity in the same unit).")
        return out

    def flags(self, rid: int, rows: List[dict], reg, shots: Dict[str, List[str]]) -> List[dict]:
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
            elif not shots.get(s.id):
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


AUTH = Auth({})      # replaced in main(): no users = no login (own laptop)


class Handler(BaseHTTPRequestHandler):
    server_version = "James/0.1"

    # --- login helpers ---------------------------------------------------------------
    def client_address_text(self) -> str:
        forwarded = (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
        return forwarded or self.client_address[0]

    def current_user(self) -> Optional[str]:
        """The logged-in name; "" when login is switched off; None when login is needed."""
        if not AUTH.enabled:
            return ""
        return AUTH.user_from_cookie_header(self.headers.get("Cookie"))

    def secure_cookie(self) -> str:
        return "; Secure" if (self.headers.get("X-Forwarded-Proto") or "").lower() == "https" else ""

    def send_html(self, text: str, status: int = 200) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, where: str) -> None:
        self.send_response(302)
        self.send_header("Location", where)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_view(self, rid, user: str, object_id=None) -> None:
        out = SERVICE.view(rid, object_id)
        out["me"] = user
        out["login"] = AUTH.enabled
        self.send_json(out)

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
        user = self.current_user()
        if path == "/login" and AUTH.enabled:
            return self.redirect("/") if user else self.send_html(LOGIN_PAGE)
        if path == "/healthz":
            return self.send_json({"ok": True})
        if user is None:                                     # login needed
            if path.startswith("/api/"):
                return self.send_json({"error": "login required"}, 401)
            return self.redirect("/login")
        m = re.fullmatch(r"/api/photo/(\d+)(/thumb)?", path)
        if m:
            return self.get_photo(int(m.group(1)), bool(m.group(2)))
        if path in ("/", "/index.html"):
            self.send_html((STATIC / "index.html").read_text(encoding="utf-8"))
        elif path == "/api/export":
            q = dict(kv.split("=", 1) for kv in self.path.partition("?")[2].split("&") if "=" in kv)
            try:
                rid = int(q.get("report", ""))
                with SERVICE.lock:
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
            try:
                with SERVICE.lock:
                    self.send_view(rid, user, q.get("object") or None)
            except ValueError as e:
                self.send_json({"error": str(e)}, 400)
        else:
            self.send_json({"error": "not found"}, 404)

    def get_photo(self, photo_id: int, thumb: bool) -> None:
        """GET /api/photo/<id>[/thumb]?object=<id>. The photo's project is looked up in the database and must
        be the project the request names; the file path is built only from the generated stored name."""
        q = parse_qs(urlsplit(self.path).query)
        try:
            with SERVICE.lock:
                path = SERVICE.photo_file(q.get("object", [None])[0], photo_id, thumb)
            data = path.read_bytes()
        except (ValueError, FileNotFoundError):
            return self.send_json({"error": "photo not found in this project"}, 404)
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "private, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def body_length(self, limit: int) -> Optional[int]:
        """The size the browser announces. Missing or too large: refused before one byte of the body is read,
        so a 40 MB upload never fills the server's memory."""
        raw = self.headers.get("Content-Length")
        if raw is None or not raw.strip().isdigit():
            self.send_json({"error": "the request has no Content-Length"}, 411)
            return None
        if int(raw) > limit:
            self.close_connection = True
            self.send_json({"error": f"the upload is larger than {limit // (1024 * 1024)} MB"}, 413)
            return None
        return int(raw)

    def post_photo(self) -> None:
        """POST /api/photo?object=<id>&name=<file name>, the raw image as body (no base64)."""
        length = self.body_length(photos.max_photo_bytes())
        if length is None:
            return
        user = self.current_user()
        if user is None:
            self.close_connection = True
            return self.send_json({"error": "login required"}, 401)
        q = parse_qs(urlsplit(self.path).query)
        name = (q.get("name") or ["photo.jpg"])[0]
        data = self.rfile.read(length)                       # outside the lock: other windows keep working
        if len(data) != length:                              # the browser stopped sending (closed, cancelled)
            self.close_connection = True
            return
        try:
            # with login on, the logged-in name; on your own laptop, the inspector name typed at the top
            by = user or unquote(self.headers.get("X-Inspector", ""))
            out = SERVICE.upload_photo(q.get("object", [None])[0], name, data, by)
        except (ValueError, KeyError, TypeError) as e:
            return self.send_json({"error": f"{name}: {e}"}, 400)
        self.send_json(out)

    def do_POST(self):
        if urlsplit(self.path).path == "/api/photo":
            return self.post_photo()
        length = self.body_length(MAX_JSON_BYTES)
        if length is None:
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            path = self.path.split("?")[0]
            if path == "/api/login" and AUTH.enabled:
                who = AUTH.check(body.get("name", ""), body.get("password", ""), self.client_address_text())
                if who is None:
                    if AUTH.blocked(self.client_address_text()):
                        return self.send_json({"error": "Too many tries. Wait a minute."}, 429)
                    return self.send_json({"error": "Wrong name or password."}, 401)
                data = json.dumps({"ok": True, "me": who}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Set-Cookie", f"{COOKIE}={AUTH.make_token(who)}; Path=/; HttpOnly; SameSite=Lax; "
                                               f"Max-Age={SESSION_SECONDS}{self.secure_cookie()}")
                self.end_headers()
                self.wfile.write(data)
                return
            if path == "/api/logout":
                data = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Set-Cookie", f"{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{self.secure_cookie()}")
                self.end_headers()
                self.wfile.write(data)
                return
            user = self.current_user()
            if user is None:
                return self.send_json({"error": "login required"}, 401)
            if user:
                body["by"] = user          # with login, the signature is always the logged-in name
            with SERVICE.lock:             # one request at a time inside the database (see Service.lock)
                return self.dispatch_post(path, body, user)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error) as e:
            self.send_json({"error": str(e)}, 400)

    def dispatch_post(self, path: str, body: dict, user: str) -> None:
        try:
            oid = body.get("object")                 # the project this browser tab shows (from its URL)
            if path == "/api/reset":
                SERVICE.reset()
                rid, oid = None, SERVICE.demo_object
            elif path == "/api/demo":
                rid = SERVICE.load_demo(body.get("which", "b1"), oid)
            elif path == "/api/report":
                rid = SERVICE.ingest(body.get("label", ""), body.get("text", ""), object_id=oid)
            elif path == "/api/reread":
                rid = int(body["report_id"])
                SERVICE.reread(rid)
                oid = SERVICE.report_object(rid)
            elif path == "/api/project":
                oid = SERVICE.new_project(body)
                rid = None
            elif path == "/api/project-update":
                SERVICE.update_project(body, body.get("by", ""), oid)
                rid = body.get("report_id")
            elif path == "/api/select-project":          # old callers: the screen now keeps the project in its URL
                SERVICE.select_object(int(body["object_id"]))
                rid, oid = None, int(body["object_id"])
            elif path == "/api/sample":
                SERVICE.add_sample(body, body.get("by", ""), oid)
                rid = body.get("report_id")
            elif path == "/api/sample-update":
                SERVICE.update_sample(body.get("code", ""), body, body.get("by", ""), oid)
                rid = body.get("report_id")
            elif path == "/api/decide":
                rid = int(body["report_id"])
                SERVICE.decide(rid, int(body["idx"]), body.get("action", ""), body.get("by", ""),
                               body.get("sample"), (body.get("note") or "").strip())
                oid = SERVICE.report_object(rid)
            elif path == "/api/save-history":
                rid = int(body["report_id"])
                SERVICE.save_history(rid, body.get("by", ""))
                oid = SERVICE.report_object(rid)
            elif path == "/api/sign":
                rid = int(body["report_id"])
                SERVICE.sign(rid, body.get("by", ""))
                oid = SERVICE.report_object(rid)
            elif path == "/api/practice":
                rid = SERVICE.load_practice(oid)
            elif path == "/api/upload-pdf":
                data = base64.b64decode(body.get("pdf_base64", ""), validate=True)
                if len(data) > MAX_PDF_BYTES:
                    raise ValueError("the PDF is larger than 18 MB")
                rid = SERVICE.ingest_pdf(body.get("label", ""), data, oid)
            elif path == "/api/photo-update":
                SERVICE.update_photo(oid, int(body["id"]), body, body.get("by", ""))
                rid = body.get("report_id")
            elif path == "/api/photo-accept":
                SERVICE.accept_photo_proposals(oid, body.get("by", ""))
                rid = body.get("report_id")
            elif path == "/api/certificate":
                rid = int(body["report_id"])
                SERVICE.set_certificate(rid, int(body["idx"]), body.get("certificate", ""), body.get("by", ""))
                oid = SERVICE.report_object(rid)
            elif path == "/api/check-confirm":
                SERVICE.confirm_check(oid, body.get("key", ""), body.get("by", ""))
                rid = body.get("report_id")
            else:
                return self.send_json({"error": "not found"}, 404)
            self.send_view(rid, user, oid)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, binascii.Error) as e:
            self.send_json({"error": str(e)}, 400)


def main(argv: Optional[List[str]] = None) -> int:
    global SERVICE
    ap = argparse.ArgumentParser(description="James app (fictitious data, no real AI).")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT") or 8000))
    ap.add_argument("--host", default=None, help="default 127.0.0.1; on a host that sets PORT: 0.0.0.0")
    ap.add_argument("--db", default=os.environ.get("JAMES_DB", ":memory:"),
                    help="a file name keeps the data between runs (or set JAMES_DB)")
    args = ap.parse_args(argv)
    global AUTH
    AUTH = Auth(parse_users(os.environ.get("JAMES_USERS")), os.environ.get("JAMES_SECRET"))
    args.host = args.host or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    if args.host not in ("127.0.0.1", "localhost") and not AUTH.enabled:
        if os.environ.get("PORT"):
            print("Refusing to start on a hosting service without a login: set JAMES_USERS.")
            return 2
        print("WARNING: no login. Anyone who can reach this address can use the app. "
              "Set JAMES_USERS to switch the login on.")
    SERVICE = Service(args.db)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)      # one slow upload no longer blocks others
    srv.daemon_threads = True
    print(f"James is running: http://{args.host}:{args.port}   (stop with Ctrl+C)"
          + ("   [login on]" if AUTH.enabled else ""))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
