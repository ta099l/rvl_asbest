-- James data model (SQLite). One object (ship or structure) has samples,
-- lab reports, links and a versioned asset file. Decisions are append-only,
-- so the table doubles as the audit log: who decided what, and when.

PRAGMA foreign_keys = ON;

CREATE TABLE object (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    kind      TEXT NOT NULL,            -- ship, civil structure, ...
    ref       TEXT,                     -- IMO number, object code
    site      TEXT NOT NULL,            -- port, shipyard, quay, road km
    project   TEXT NOT NULL,            -- RVL project code
    survey_date TEXT,                   -- moves to a survey table if that proposal is accepted
    info      TEXT                      -- JSON: the other Project Information fields of the IHM template
);

CREATE TABLE sample (
    object_id INTEGER NOT NULL REFERENCES object(id),
    code      TEXT NOT NULL,            -- code on the sample sticker
    source    TEXT,                     -- source number
    location  TEXT NOT NULL,            -- location in the object
    part      TEXT,
    material  TEXT,
    notes     TEXT,
    photo     TEXT,
    drawing   TEXT,                     -- drawing reference and position, e.g. GA-01 pos 12
    quantity  TEXT,                     -- estimated quantity of the source (IHM: Approximate Quantity)
    unit      TEXT,                     -- kg, m2, m, pcs, l
    deck      TEXT,                     -- deck level (own column in the IHM report)
    status    TEXT NOT NULL DEFAULT 'sampled',  -- 'sampled' or 'not sampled' (inaccessible)
    restriction TEXT,                   -- why it was not sampled: goes to the survey limitations
    PRIMARY KEY (object_id, code)
);

CREATE TABLE lab_report (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES object(id),
    label       TEXT NOT NULL,
    report_ref  TEXT,
    lab         TEXT,
    header_project TEXT,                -- project code as the lab wrote it
    raw_text    TEXT NOT NULL,          -- the extracted text, kept as received
    ingested_at TEXT NOT NULL,
    source_file TEXT,                   -- evidence: file name as received, or 'pasted text'
    source_sha256 TEXT,                 -- evidence: fingerprint of the exact file or text
    read_method TEXT,                   -- evidence: text layer, OCR, mixed, or pasted
    linker_version TEXT,                -- evidence: fingerprint of the linker code that proposed
    prompt_version TEXT                 -- evidence: prompt used by the AI step, if any
);

CREATE TABLE lab_row (
    id          INTEGER PRIMARY KEY,
    report_id   INTEGER NOT NULL REFERENCES lab_report(id),
    idx         INTEGER NOT NULL,       -- position in the report, 0-based
    raw_line    TEXT NOT NULL,
    raw_id      TEXT,
    description TEXT,
    result      TEXT,
    certificate TEXT,                   -- lab certificate number, needed for the full chain
    method      TEXT,                   -- analysis method, e.g. NEN 5896
    quantity    TEXT,
    remarks     TEXT,
    proposed_code TEXT,                 -- NULL = no link proposed
    confidence  TEXT,                   -- high / medium / low
    reason      TEXT NOT NULL,
    flags       TEXT NOT NULL,          -- comma separated, e.g. row:5:conflict
    UNIQUE (report_id, idx)
);

CREATE TABLE decision (                 -- append-only audit log
    id          INTEGER PRIMARY KEY,
    lab_row_id  INTEGER NOT NULL REFERENCES lab_row(id),
    state       TEXT NOT NULL CHECK (state IN ('approved','corrected','rejected')),
    sample_code TEXT,                   -- NULL for 'rejected' (no link)
    decided_by  TEXT NOT NULL,
    decided_at  TEXT NOT NULL,
    note        TEXT
);

CREATE TABLE asset_version (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES object(id),
    version     INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    created_by  TEXT NOT NULL,
    summary     TEXT NOT NULL,
    UNIQUE (object_id, version)
);

CREATE TABLE asset_entry (              -- one approved result in one version
    id          INTEGER PRIMARY KEY,
    version_id  INTEGER NOT NULL REFERENCES asset_version(id),
    sample_code TEXT NOT NULL,
    lab_row_id  INTEGER NOT NULL REFERENCES lab_row(id),
    result      TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    via         TEXT NOT NULL,          -- approved or corrected
    changed     INTEGER NOT NULL        -- 1 if it differs from the previous result
);

CREATE TABLE signoff (                  -- append-only: an inspector signs the report sections
    id          INTEGER PRIMARY KEY,
    report_id   INTEGER NOT NULL REFERENCES lab_report(id),
    signed_by   TEXT NOT NULL,
    signed_at   TEXT NOT NULL,
    open_items  TEXT NOT NULL           -- JSON list, recorded as they were at signing
);

CREATE TABLE register_log (             -- append-only: every change to the field registration
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES object(id),
    code        TEXT NOT NULL,
    action      TEXT NOT NULL,          -- added or changed
    detail      TEXT NOT NULL,          -- what changed, old -> new
    changed_by  TEXT NOT NULL,
    changed_at  TEXT NOT NULL
);
