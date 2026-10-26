"""Database layer: objects, samples, lab reports, inspector decisions, asset versions."""
import os
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .linker import Sample, link

SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql")
STATES = ("approved", "corrected", "rejected")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        exists = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='object'").fetchone()
        if not exists:
            with open(SCHEMA, encoding="utf-8") as f:
                self.db.executescript(f.read())

    # ---------- objects and samples ----------
    def add_object(self, name: str, kind: str, ref: str, site: str, project: str,
                   samples: List[Sample]) -> int:
        with self.db:
            cur = self.db.execute(
                "INSERT INTO object(name,kind,ref,site,project) VALUES (?,?,?,?,?)",
                (name, kind, ref, site, project))
            oid = cur.lastrowid
            self.db.executemany(
                "INSERT INTO sample(object_id,code,source,location,part,material,notes,photo) "
                "VALUES (?,?,?,?,?,?,?,?)",
                [(oid, s.id, s.source, s.location, s.part, s.material, s.notes, s.photo) for s in samples])
        return oid

    def object(self, object_id: int) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM object WHERE id=?", (object_id,)).fetchone()

    def register(self, object_id: int) -> List[Sample]:
        rows = self.db.execute("SELECT * FROM sample WHERE object_id=? ORDER BY rowid", (object_id,))
        return [Sample(r["code"], r["source"], r["location"], r["part"], r["material"],
                       r["notes"], r["photo"]) for r in rows]

    # ---------- lab reports ----------
    def ingest_report(self, object_id: int, label: str, text: str) -> int:
        """Store the report text, run the linker, store every proposal with its reason."""
        obj = self.object(object_id)
        run = link(obj["project"], self.register(object_id), text)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO lab_report(object_id,label,report_ref,lab,header_project,raw_text,ingested_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (object_id, label, run.head.get("report"), run.head.get("lab"),
                 run.head.get("project"), text, _now()))
            rid = cur.lastrowid
            for p in run.proposals:
                self.db.execute(
                    "INSERT INTO lab_row(report_id,idx,raw_line,raw_id,description,result,"
                    "proposed_code,confidence,reason,flags) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (rid, p.index, p.row.raw, p.row.raw_id, p.row.desc, p.row.result,
                     p.sample_id, p.confidence, p.reason, ",".join(p.flags)))
        return rid

    def header_flags(self, report_id: int) -> List[str]:
        rep = self.db.execute("SELECT * FROM lab_report WHERE id=?", (report_id,)).fetchone()
        obj = self.object(rep["object_id"])
        run = link(obj["project"], self.register(rep["object_id"]), rep["raw_text"])
        return run.header_flags

    def rows(self, report_id: int) -> List[sqlite3.Row]:
        return self.db.execute(
            "SELECT * FROM lab_row WHERE report_id=? ORDER BY idx", (report_id,)).fetchall()

    # ---------- decisions ----------
    def decide(self, report_id: int, idx: int, state: str, by: str,
               sample_code: Optional[str] = None, note: str = "") -> None:
        """Record an inspector decision. Never overwrites: a new decision supersedes the old one."""
        if state not in STATES:
            raise ValueError(f"state must be one of {STATES}")
        if not by or not by.strip():
            raise ValueError("a named inspector is required")
        row = self.db.execute("SELECT * FROM lab_row WHERE report_id=? AND idx=?",
                              (report_id, idx)).fetchone()
        if row is None:
            raise ValueError(f"no lab row {idx} in report {report_id}")
        rep = self.db.execute("SELECT object_id FROM lab_report WHERE id=?", (report_id,)).fetchone()
        codes = {s.id for s in self.register(rep["object_id"])}
        if state == "approved":
            if row["proposed_code"] is None:
                raise ValueError("nothing was proposed for this row, so it cannot be approved; "
                                 "use 'corrected' to link it by hand or 'rejected'")
            sample_code = row["proposed_code"]
        elif state == "corrected":
            if sample_code not in codes:
                raise ValueError(f"unknown sample {sample_code!r}")
        else:
            sample_code = None
        with self.db:
            self.db.execute(
                "INSERT INTO decision(lab_row_id,state,sample_code,decided_by,decided_at,note) "
                "VALUES (?,?,?,?,?,?)", (row["id"], state, sample_code, by.strip(), _now(), note))

    def current_decisions(self, report_id: int) -> Dict[int, sqlite3.Row]:
        q = """SELECT d.*, r.idx FROM decision d JOIN lab_row r ON r.id = d.lab_row_id
               WHERE r.report_id=? ORDER BY d.id"""
        out: Dict[int, sqlite3.Row] = {}
        for d in self.db.execute(q, (report_id,)):
            out[d["idx"]] = d          # later decisions replace earlier ones
        return out

    def audit_log(self, report_id: Optional[int] = None) -> List[sqlite3.Row]:
        q = """SELECT d.id, d.decided_at, d.decided_by, d.state, d.sample_code, d.note,
                      r.idx, r.raw_id, r.proposed_code, r.report_id
               FROM decision d JOIN lab_row r ON r.id = d.lab_row_id"""
        if report_id is None:
            return self.db.execute(q + " ORDER BY d.id").fetchall()
        return self.db.execute(q + " WHERE r.report_id=? ORDER BY d.id", (report_id,)).fetchall()

    # ---------- draft report ----------
    def draft_report(self, report_id: int) -> dict:
        rep = self.db.execute("SELECT * FROM lab_report WHERE id=?", (report_id,)).fetchone()
        obj = self.object(rep["object_id"])
        reg = {s.id: s for s in self.register(rep["object_id"])}
        dec = self.current_decisions(report_id)
        linked, open_items = [], []
        linked_codes = set()
        for r in self.rows(report_id):
            d = dec.get(r["idx"])
            if d is not None and d["state"] in ("approved", "corrected"):
                s = reg[d["sample_code"]]
                linked_codes.add(s.id)
                linked.append({"location": s.location, "sample": s.id, "source": s.source,
                               "material": f"{s.material}, {s.notes}", "result": r["result"],
                               "linked_by": d["decided_by"], "via": d["state"]})
            elif d is None:
                open_items.append(f"Lab row {r['idx'] + 1} ({r['raw_id'] or 'no ID'}): not yet reviewed")
            else:
                open_items.append(f"Lab row {r['idx'] + 1} ({r['raw_id'] or 'no ID'}): inspector decided no link")
        for code, s in reg.items():
            if code not in linked_codes:
                open_items.append(f"Sample {code} ({s.location}) has no linked result")
        open_items += self.header_flags(report_id)
        linked.sort(key=lambda x: x["location"])
        return {"object": obj["name"], "site": obj["site"], "project": obj["project"],
                "report": rep["report_ref"], "status": "DRAFT" if open_items else "COMPLETE",
                "linked": linked, "open_items": open_items}

    # ---------- asset file ----------
    def save_asset_version(self, object_id: int, report_id: int, by: str) -> int:
        dec = self.current_decisions(report_id)
        links = {i: d for i, d in dec.items() if d["state"] in ("approved", "corrected")}
        if not links:
            raise ValueError("no approved links to save")
        prev = self.asset(object_id)["samples"]
        with self.db:
            ver = (self.db.execute("SELECT COALESCE(MAX(version),0) m FROM asset_version WHERE object_id=?",
                                   (object_id,)).fetchone()["m"]) + 1
            cur = self.db.execute(
                "INSERT INTO asset_version(object_id,version,created_at,created_by,summary) VALUES (?,?,?,?,?)",
                (object_id, ver, _now(), by, f"{len(links)} link(s) saved from report {report_id}"))
            vid = cur.lastrowid
            for idx, d in sorted(links.items()):
                r = self.db.execute("SELECT * FROM lab_row WHERE report_id=? AND idx=?",
                                    (report_id, idx)).fetchone()
                old = prev.get(d["sample_code"], {}).get("history", [])
                changed = 1 if old and old[-1]["result"] != r["result"] else 0
                self.db.execute(
                    "INSERT INTO asset_entry(version_id,sample_code,lab_row_id,result,approved_by,"
                    "approved_at,via,changed) VALUES (?,?,?,?,?,?,?,?)",
                    (vid, d["sample_code"], r["id"], r["result"], d["decided_by"], d["decided_at"],
                     d["state"], changed))
        return ver

    def asset(self, object_id: int) -> dict:
        obj = self.object(object_id)
        reg = {s.id: s for s in self.register(object_id)}
        q = """SELECT e.*, v.version FROM asset_entry e JOIN asset_version v ON v.id = e.version_id
               WHERE v.object_id=? ORDER BY v.version, e.id"""
        samples: Dict[str, dict] = {}
        for e in self.db.execute(q, (object_id,)):
            s = reg[e["sample_code"]]
            samples.setdefault(e["sample_code"], {"source": s.source, "location": s.location,
                                                  "history": []})["history"].append(
                {"version": e["version"], "result": e["result"], "approved_by": e["approved_by"],
                 "approved_at": e["approved_at"], "via": e["via"], "changed": bool(e["changed"])})
        latest = self.db.execute("SELECT COALESCE(MAX(version),0) m FROM asset_version WHERE object_id=?",
                                 (object_id,)).fetchone()["m"]
        return {"object": obj["name"], "site": obj["site"], "version": latest, "samples": samples}
