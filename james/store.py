"""Database layer: objects, samples, lab reports, inspector decisions, asset versions."""
import json
import os
import sqlite3
from datetime import datetime, timezone
import re
from typing import Callable, Dict, List, Optional

from .linker import Sample, link

SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql")
STATES = ("approved", "corrected", "rejected")
NOT_SAMPLED = "not sampled"

# Columns added after the first version: a database file made before them gets them added.
_NEW_COLUMNS = {
    "object": [("survey_date", "TEXT"), ("info", "TEXT")],
    "sample": [("deck", "TEXT"), ("status", "TEXT NOT NULL DEFAULT 'sampled'"), ("restriction", "TEXT"),
               ("drawing", "TEXT"), ("quantity", "TEXT"), ("unit", "TEXT")],
    "lab_report": [("source_file", "TEXT"), ("source_sha256", "TEXT"), ("read_method", "TEXT"),
                   ("linker_version", "TEXT"), ("prompt_version", "TEXT")],
    "lab_row": [("certificate", "TEXT"), ("method", "TEXT"), ("quantity", "TEXT"), ("remarks", "TEXT"),
                ("ai_code", "TEXT"), ("ai_confidence", "TEXT"), ("ai_reason", "TEXT"), ("ai_source", "TEXT"),
                ("ai_prompt_version", "TEXT"), ("ai_sent", "INTEGER")],
}
# Tables added after the first version; on an old file they are created and filled once (see _upgrade).
_NEW_TABLES = ("source", "photo")
# What an inspector may change on a source (bronblad). The source number itself never changes.
SOURCE_FIELDS = ("substance_group", "description", "condition", "quantity", "unit", "assessment", "conclusion", "drawing")
ASSESSMENTS = ("confirmed", "not hazardous", "PCHM", "not accessible")
# register_log actions about sources and photos start with these words. They do not change what the
# linker reads, so they never mark lab proposals out of date (register_changed_at skips them).
SOURCE_PHOTO_ACTIONS = ("source ", "photo ")
# Fields an inspector may change after registering a sample. The code itself never changes:
# lab results and decisions hang on it.
EDITABLE = ("source", "location", "part", "material", "notes", "photo", "deck", "status", "restriction", "drawing",
            "quantity", "unit")
# Project Information fields of the RVL IHM template, besides name, type, location, project number and date.
PROJECT_INFO = ("client", "client_address", "owner", "owner_address", "surveyor", "technical_responsible",
                "project_coordinator", "survey_period")
# Columns of the object table that the intake page may change.
OBJECT_FIELDS = ("name", "kind", "ref", "site", "project", "survey_date")
# register_log code for a change to the project details (not a sample, so no report goes out of date).
PROJECT_LOG_CODE = "(project)"


def check_sample(s: Sample) -> None:
    """The minimum a field registration needs before a lab result can be linked to it."""
    missing = [n for n, v in (("code", s.id), ("location", s.location), ("material", s.material)) if not (v or "").strip()]
    if missing:
        raise ValueError("a sample needs " + ", ".join(missing))
    if s.status not in ("sampled", NOT_SAMPLED):
        raise ValueError(f"status must be 'sampled' or '{NOT_SAMPLED}'")
    if s.status == NOT_SAMPLED and not (s.restriction or "").strip():
        raise ValueError("a place that was not sampled needs the reason (it goes to the survey limitations)")


def _schema_table(name: str) -> str:
    """The CREATE TABLE statement for one table, taken from schema.sql, so old files get exactly the same table."""
    with open(SCHEMA, encoding="utf-8") as f:
        sql = re.sub(r"--[^\n]*", "", f.read())
    stmt = next(x for x in sql.split(";") if re.match(rf"\s*CREATE TABLE {name}\s*\(", x))
    return stmt.strip().replace(f"CREATE TABLE {name}", f"CREATE TABLE IF NOT EXISTS {name}", 1)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self, path: str = ":memory:", group_of: Optional[Callable[[str], Optional[str]]] = None):
        """group_of: sample code -> substance group (the app passes app.ihm.group_for_code); None leaves it empty."""
        self.group_of = group_of or (lambda code: None)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        exists = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='object'").fetchone()
        if not exists:
            with open(SCHEMA, encoding="utf-8") as f:
                self.db.executescript(f.read())
        else:
            self._upgrade()

    def _upgrade(self) -> None:
        """Bring a database file from an older schema up to date, without losing data."""
        with self.db:
            for table, cols in _NEW_COLUMNS.items():
                have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
                for name, typ in cols:
                    if name not in have:
                        self.db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
            self.db.execute("CREATE TABLE IF NOT EXISTS register_log (id INTEGER PRIMARY KEY, "
                            "object_id INTEGER NOT NULL REFERENCES object(id), code TEXT NOT NULL, "
                            "action TEXT NOT NULL, detail TEXT NOT NULL, changed_by TEXT NOT NULL, "
                            "changed_at TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS signoff (id INTEGER PRIMARY KEY, "
                            "report_id INTEGER NOT NULL REFERENCES lab_report(id), signed_by TEXT NOT NULL, "
                            "signed_at TEXT NOT NULL, open_items TEXT NOT NULL)")
            have = {r["name"] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing = [t for t in _NEW_TABLES if t not in have]
            for t in missing:                               # the same CREATE TABLE as schema.sql, no copy
                self.db.execute(_schema_table(t))
        if "source" in missing:
            # Filled ONCE, when the tables are new: running the upgrade again changes nothing, and a photo
            # an inspector unlinked later is never recreated from the old text field. Nothing is deleted.
            for o in self.objects():
                for smp in self.register(o["id"]):
                    self._sync_sample(o["id"], smp, "James (database upgrade)")

    # ---------- objects and samples ----------
    def add_object(self, name: str, kind: str, ref: str, site: str, project: str,
                   samples: List[Sample], survey_date: str = "", info: Optional[Dict[str, str]] = None) -> int:
        """Add an object with its sample register.

        A code that appears twice in the register is refused: the linker could
        only guess which of the two a lab result belongs to (test case TC04).
        """
        if not (name or "").strip() or not (project or "").strip() or not (site or "").strip():
            raise ValueError("a project needs a name, a project number and a survey location")
        for s in samples:
            check_sample(s)
        codes = [s.id for s in samples]
        dupes = sorted({c for c in codes if codes.count(c) > 1})
        if dupes:
            raise ValueError("the sample register has duplicate codes: " + ", ".join(dupes) +
                             ". Fix the field registration first; the system will not choose between them.")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO object(name,kind,ref,site,project,survey_date,info) VALUES (?,?,?,?,?,?,?)",
                (name.strip(), kind, ref, site.strip(), project.strip(), survey_date,
                 json.dumps({k: (info or {}).get(k, "") for k in PROJECT_INFO})))
            oid = cur.lastrowid
            self.db.executemany(
                "INSERT INTO sample(object_id,code,source,location,part,material,notes,photo,deck,status,"
                "restriction,drawing,quantity,unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [(oid, s.id, s.source, s.location, s.part, s.material, s.notes, s.photo, s.deck,
                  s.status or "sampled", s.restriction, s.drawing, s.quantity, s.unit) for s in samples])
        for s in samples:
            self._sync_sample(oid, s, "James (project created)")
        return oid

    def object(self, object_id: int) -> sqlite3.Row:
        return self.db.execute("SELECT * FROM object WHERE id=?", (object_id,)).fetchone()

    def register(self, object_id: int) -> List[Sample]:
        rows = self.db.execute("SELECT * FROM sample WHERE object_id=? ORDER BY rowid", (object_id,))
        return [Sample(r["code"], r["source"], r["location"], r["part"], r["material"],
                       r["notes"], r["photo"], r["deck"] or "", r["status"] or "sampled",
                       r["restriction"] or "", r["drawing"] or "", r["quantity"] or "", r["unit"] or "") for r in rows]

    def project_info(self, object_id: int) -> Dict[str, str]:
        raw = self.object(object_id)["info"]
        return {k: "" for k in PROJECT_INFO} | (json.loads(raw) if raw else {})

    def objects(self) -> List[sqlite3.Row]:
        return self.db.execute("SELECT * FROM object ORDER BY id").fetchall()

    def update_object(self, object_id: int, changes: Dict[str, str], by: str) -> None:
        """Change the project details (intake page). Logged old -> new under PROJECT_LOG_CODE, so the
        report keeps a trace of who changed what; it does not mark lab reports out of date."""
        if not (by or "").strip():
            raise ValueError("a named inspector is required")
        row = self.object(object_id)
        if row is None:
            raise ValueError("unknown project")
        bad = set(changes) - set(OBJECT_FIELDS) - set(PROJECT_INFO)
        if bad:
            raise ValueError("these fields cannot be changed: " + ", ".join(sorted(bad)))
        old = {k: row[k] or "" for k in OBJECT_FIELDS} | self.project_info(object_id)
        new = old | {k: (v or "").strip() for k, v in changes.items()}
        if not new["name"] or not new["project"] or not new["site"]:
            raise ValueError("a project needs a name, a project number and a survey location")
        diffs = [f"{k}: {old[k] or '–'} -> {new[k] or '–'}" for k in (*OBJECT_FIELDS, *PROJECT_INFO) if old[k] != new[k]]
        if not diffs:
            return
        with self.db:
            self.db.execute("UPDATE object SET " + ", ".join(f"{k}=?" for k in OBJECT_FIELDS) + ", info=? WHERE id=?",
                            [new[k] for k in OBJECT_FIELDS] + [json.dumps({k: new[k] for k in PROJECT_INFO}), object_id])
            self._log_register(object_id, PROJECT_LOG_CODE, "changed", "; ".join(diffs), by)

    # ---------- field registration ----------
    def add_sample(self, object_id: int, s: Sample, by: str) -> None:
        """Register one sample (or a place that could not be sampled). Logged with name and time."""
        if not (by or "").strip():
            raise ValueError("a named inspector is required")
        s.id = (s.id or "").strip()
        check_sample(s)
        if s.id in {x.id for x in self.register(object_id)}:
            raise ValueError(f"sample code {s.id} is already registered for this object; codes must be unique")
        with self.db:
            self.db.execute(
                "INSERT INTO sample(object_id,code,source,location,part,material,notes,photo,deck,status,"
                "restriction,drawing,quantity,unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (object_id, s.id, s.source, s.location, s.part, s.material, s.notes, s.photo, s.deck,
                 s.status, s.restriction, s.drawing, s.quantity, s.unit))
            self._log_register(object_id, s.id, "added", f"{s.material} at {s.location}"
                               + (f" ({s.status}: {s.restriction})" if s.status == NOT_SAMPLED else ""), by)
        self._sync_sample(object_id, s, by)

    def update_sample(self, object_id: int, code: str, changes: Dict[str, str], by: str) -> None:
        """Change registered fields of a sample. The code never changes; every change is logged old -> new."""
        if not (by or "").strip():
            raise ValueError("a named inspector is required")
        bad = set(changes) - set(EDITABLE)
        if bad:
            raise ValueError("these fields cannot be changed: " + ", ".join(sorted(bad)))
        old = next((x for x in self.register(object_id) if x.id == code), None)
        if old is None:
            raise ValueError(f"unknown sample {code!r}")
        new = Sample(**{**old.__dict__, **{k: (v or "").strip() for k, v in changes.items()}})
        check_sample(new)
        if new.status == NOT_SAMPLED and old.status != NOT_SAMPLED and self._has_links(object_id, code):
            raise ValueError(f"{code} already has a linked lab result, so it cannot become 'not sampled'")
        diffs = [f"{k}: {getattr(old, k) or '–'} -> {getattr(new, k) or '–'}"
                 for k in EDITABLE if getattr(old, k) != getattr(new, k)]
        if not diffs:
            return
        with self.db:
            self.db.execute(
                "UPDATE sample SET " + ", ".join(f"{k}=?" for k in EDITABLE) + " WHERE object_id=? AND code=?",
                [getattr(new, k) for k in EDITABLE] + [object_id, code])
            self._log_register(object_id, code, "changed", "; ".join(diffs), by)
            if old.photo and old.photo != new.photo:         # unlink, never delete: the row and its file stay
                cur = self.db.execute("UPDATE photo SET sample_code=NULL WHERE object_id=? AND photo_no=? AND sample_code=?",
                                      (object_id, old.photo, code))
                if cur.rowcount:
                    self._log_register(object_id, old.photo, "photo unlinked", f"from sample {code}", by)
            if old.source != new.source:
                cur = self.db.execute("UPDATE photo SET source_no=? WHERE object_id=? AND sample_code=?",
                                      (new.source or None, object_id, code))
                if cur.rowcount:
                    self._log_register(object_id, code, "photo changed",
                                       f"photos of sample {code}: source {old.source or '–'} -> {new.source or '–'}", by)
        self._sync_sample(object_id, new, by)

    # ---------- sources (bronbladen) and photos ----------
    def _sync_sample(self, object_id: int, s: Sample, by: str) -> None:
        """Make sure the source and photo a sample names exist as rows. Adds, never overwrites:
        a new source copies quantity and unit from the first sample that names it."""
        with self.db:
            if (s.source or "").strip():
                cur = self.db.execute(
                    "INSERT OR IGNORE INTO source(object_id,source_no,substance_group,quantity,unit,updated_by,updated_at) "
                    "VALUES (?,?,?,?,?,?,?)", (object_id, s.source.strip(), self.group_of(s.id), s.quantity or None,
                                               s.unit or None, by.strip(), _now()))
                if cur.rowcount:
                    self._log_register(object_id, s.source.strip(), "source added", f"from sample {s.id}", by)
            if (s.photo or "").strip():
                no = s.photo.strip()
                row = self.db.execute("SELECT sample_code FROM photo WHERE object_id=? AND photo_no=?", (object_id, no)).fetchone()
                if row is None:
                    n = self.db.execute("SELECT COUNT(*) FROM photo WHERE object_id=?", (object_id,)).fetchone()[0]
                    self.db.execute("INSERT INTO photo(object_id,photo_no,source_no,sample_code,sort_order) VALUES (?,?,?,?,?)",
                                    (object_id, no, (s.source or "").strip() or None, s.id, n + 1))
                    self._log_register(object_id, no, "photo added", f"for sample {s.id}, no file yet", by)
                elif row["sample_code"] is None:
                    self.db.execute("UPDATE photo SET sample_code=?, source_no=? WHERE object_id=? AND photo_no=?",
                                    (s.id, (s.source or "").strip() or None, object_id, no))
                    self._log_register(object_id, no, "photo linked", f"to sample {s.id}", by)

    def sources(self, object_id: int) -> Dict[str, sqlite3.Row]:
        return {r["source_no"]: r for r in
                self.db.execute("SELECT * FROM source WHERE object_id=? ORDER BY source_no", (object_id,))}

    def photos(self, object_id: int) -> List[sqlite3.Row]:
        return self.db.execute("SELECT * FROM photo WHERE object_id=? ORDER BY sort_order, id", (object_id,)).fetchall()

    def update_source(self, object_id: int, source_no: str, changes: Dict[str, str], by: str) -> None:
        """Change the details of a source (bronblad). Logged old -> new; the source number never changes."""
        if not (by or "").strip():
            raise ValueError("a named inspector is required")
        bad = set(changes) - set(SOURCE_FIELDS)
        if bad:
            raise ValueError("these fields cannot be changed: " + ", ".join(sorted(bad)))
        row = self.db.execute("SELECT * FROM source WHERE object_id=? AND source_no=?", (object_id, source_no)).fetchone()
        if row is None:
            raise ValueError(f"unknown source {source_no!r}")
        new = {k: (v or "").strip() or None for k, v in changes.items()}
        if new.get("assessment") and new["assessment"] not in ASSESSMENTS:
            raise ValueError("assessment must be one of: " + ", ".join(ASSESSMENTS))
        diffs = [f"{k}: {row[k] or '–'} -> {v or '–'}" for k, v in new.items() if (row[k] or None) != v]
        if not diffs:
            return
        with self.db:
            self.db.execute("UPDATE source SET " + ", ".join(f"{k}=?" for k in new) + ", updated_by=?, updated_at=? "
                            "WHERE object_id=? AND source_no=?", [*new.values(), by.strip(), _now(), object_id, source_no])
            self._log_register(object_id, source_no, "source changed", "; ".join(diffs), by)

    def _has_links(self, object_id: int, code: str) -> bool:
        q = """SELECT 1 FROM decision d JOIN lab_row r ON r.id = d.lab_row_id JOIN lab_report l ON l.id = r.report_id
               WHERE l.object_id=? AND d.sample_code=? AND d.state IN ('approved','corrected') LIMIT 1"""
        return self.db.execute(q, (object_id, code)).fetchone() is not None

    def _log_register(self, object_id: int, code: str, action: str, detail: str, by: str) -> None:
        self.db.execute("INSERT INTO register_log(object_id,code,action,detail,changed_by,changed_at) "
                        "VALUES (?,?,?,?,?,?)", (object_id, code, action, detail, by.strip(), _now()))

    def register_log(self, object_id: int) -> List[sqlite3.Row]:
        return self.db.execute("SELECT * FROM register_log WHERE object_id=? ORDER BY id", (object_id,)).fetchall()

    def register_changed_at(self, object_id: int) -> Optional[str]:
        r = self.db.execute("SELECT MAX(changed_at) m FROM register_log WHERE object_id=? AND code<>? "
                            "AND action NOT LIKE 'source %' AND action NOT LIKE 'photo %'",
                            (object_id, PROJECT_LOG_CODE)).fetchone()
        return r["m"]

    def sampled(self, object_id: int) -> List[Sample]:
        """The register a lab result may link to: samples that were really taken."""
        return [s for s in self.register(object_id) if s.status != NOT_SAMPLED]

    def limitations(self, object_id: int) -> List[Sample]:
        """Places that could not be sampled: survey limitations, treated as potentially hazardous."""
        return [s for s in self.register(object_id) if s.status == NOT_SAMPLED]

    # ---------- lab reports ----------
    def ingest_report(self, object_id: int, label: str, text: str, evidence: Optional[Dict[str, str]] = None) -> int:
        """Store the report text, run the linker, store every proposal with its reason.

        evidence: where the text came from (source_file, source_sha256, read_method,
        linker_version), kept with the report so every proposal can be traced back.
        """
        ev = evidence or {}
        obj = self.object(object_id)
        run = link(obj["project"], self.sampled(object_id), text)
        with self.db:
            cur = self.db.execute(
                "INSERT INTO lab_report(object_id,label,report_ref,lab,header_project,raw_text,ingested_at,"
                "source_file,source_sha256,read_method,linker_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (object_id, label, run.head.get("report"), run.head.get("lab"),
                 run.head.get("project"), text, _now(), ev.get("source_file"), ev.get("source_sha256"),
                 ev.get("read_method"), ev.get("linker_version")))
            rid = cur.lastrowid
            for p in run.proposals:
                self.db.execute(
                    "INSERT INTO lab_row(report_id,idx,raw_line,raw_id,description,result,certificate,"
                    "method,quantity,remarks,proposed_code,confidence,reason,flags) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, p.index, p.row.raw, p.row.raw_id, p.row.desc, p.row.result,
                     p.row.extra.get("certificate"), p.row.extra.get("method"),
                     p.row.extra.get("quantity"), p.row.extra.get("remarks"),
                     p.sample_id, p.confidence, p.reason, ",".join(p.flags)))
        return rid

    def relink(self, report_id: int) -> None:
        """Run the linker again on a stored report, for example after the field registration changed.

        Only the proposals are refreshed. Inspector decisions stay as they are (append-only).
        """
        rep = self.db.execute("SELECT * FROM lab_report WHERE id=?", (report_id,)).fetchone()
        obj = self.object(rep["object_id"])
        run = link(obj["project"], self.sampled(rep["object_id"]), rep["raw_text"])
        with self.db:
            for p in run.proposals:
                self.db.execute("UPDATE lab_row SET proposed_code=?, confidence=?, reason=?, flags=? "
                                "WHERE report_id=? AND idx=?",
                                (p.sample_id, p.confidence, p.reason, ",".join(p.flags), report_id, p.index))

    def save_ai(self, report_id: int, lines: List[dict], prompt_version: Optional[str]) -> None:
        """Save the agent's proposal per lab line (rules first, AI second), so a restart shows it again
        without a new AI call. lines: {idx, sample, confidence, reason, source, sent}."""
        with self.db:
            self.db.executemany(
                "UPDATE lab_row SET ai_code=?, ai_confidence=?, ai_reason=?, ai_source=?, ai_prompt_version=?, ai_sent=? "
                "WHERE report_id=? AND idx=?",
                [(x["sample"], x["confidence"], x["reason"], x["source"], prompt_version, int(bool(x["sent"])),
                  report_id, x["idx"]) for x in lines])

    def saved_ai(self, report_id: int) -> Optional[List[sqlite3.Row]]:
        """The saved proposals, or None when this report was read before they were saved (read it again)."""
        rows = self.rows(report_id)
        return rows if rows and all(r["ai_source"] is not None for r in rows) else None

    def set_prompt_version(self, report_id: int, version: Optional[str]) -> None:
        """Record which prompt the AI step used for this report (None when the AI was not asked)."""
        with self.db:
            self.db.execute("UPDATE lab_report SET prompt_version=? WHERE id=?", (version, report_id))

    def header_flags(self, report_id: int) -> List[str]:
        rep = self.db.execute("SELECT * FROM lab_report WHERE id=?", (report_id,)).fetchone()
        obj = self.object(rep["object_id"])
        run = link(obj["project"], self.sampled(rep["object_id"]), rep["raw_text"])
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
        codes = {s.id for s in self.sampled(rep["object_id"])}
        if state == "approved":
            if row["proposed_code"] is None:
                raise ValueError("nothing was proposed for this row, so it cannot be approved; "
                                 "use 'corrected' to link it by hand or 'rejected'")
            sample_code = row["proposed_code"]
        elif state == "corrected":
            if sample_code not in codes:
                raise ValueError(f"unknown sample {sample_code!r}, or a place that was not sampled")
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
            if code not in linked_codes and s.status != NOT_SAMPLED:
                open_items.append(f"Sample {code} ({s.location}) has no linked result")
        open_items += self.header_flags(report_id)
        linked.sort(key=lambda x: x["location"])
        return {"object": obj["name"], "site": obj["site"], "project": obj["project"],
                "report": rep["report_ref"], "status": "DRAFT" if open_items else "COMPLETE",
                "linked": linked, "open_items": open_items}

    # ---------- sign-off ----------
    def sign(self, report_id: int, by: str, open_items: List[str]) -> None:
        """Sign the report sections. Every lab row needs a decision first; open items are recorded."""
        if not by or not by.strip():
            raise ValueError("a named inspector is required")
        undecided = len(self.rows(report_id)) - len(self.current_decisions(report_id))
        if undecided:
            raise ValueError(f"{undecided} lab line(s) still need a decision before signing")
        with self.db:
            self.db.execute("INSERT INTO signoff(report_id,signed_by,signed_at,open_items) VALUES (?,?,?,?)",
                            (report_id, by.strip(), _now(), json.dumps(open_items)))

    def signoff(self, report_id: int) -> Optional[dict]:
        """The latest signature for a report, or None."""
        r = self.db.execute("SELECT * FROM signoff WHERE report_id=? ORDER BY id DESC LIMIT 1",
                            (report_id,)).fetchone()
        return None if r is None else {"by": r["signed_by"], "at": r["signed_at"],
                                       "open_items": json.loads(r["open_items"])}

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
