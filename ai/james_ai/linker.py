"""Link lab result lines to samples in a register.

The linker only PROPOSES. It never decides: every proposal still needs an
inspector. When evidence is missing or conflicting it proposes nothing and
says why. This is a port of the rules used in the James Workbench prototype.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

STOP = {"the", "of", "at", "on", "in", "and", "a", "an", "with", "near", "side", "to", "for"}
# Prefixes that end in a digit (chromium-6). Without a separator, 'CR601' would
# otherwise read as prefix 'CR' + number 601 instead of 'CR6' + 1.
DIGIT_PREFIXES = ("CR6", "CH6")


@dataclass
class Sample:
    id: str
    source: str
    location: str
    part: str
    material: str
    notes: str = ""
    photo: str = ""
    deck: str = ""                   # deck level, its own column in the IHM report
    status: str = "sampled"          # "sampled" or "not sampled" (inaccessible: a survey limitation)
    restriction: str = ""            # why it was not sampled
    drawing: str = ""                # drawing reference and position, e.g. "GA-01 pos 12"
    quantity: str = ""               # estimated quantity of the source
    unit: str = ""                   # kg, m2, m, pcs, l

    @property
    def text(self) -> str:
        return " ".join([self.location, self.part, self.material, self.notes])


@dataclass
class LabRow:
    index: int
    raw: str
    raw_id: str
    desc: str
    result: str
    extra: Dict[str, str] = field(default_factory=dict)   # certificate, method, quantity, remarks


@dataclass
class Proposal:
    index: int
    row: LabRow
    status: str = "none"            # "propose" or "none"
    sample_id: Optional[str] = None
    confidence: Optional[str] = None  # high / medium / low
    reason: str = ""
    alts: List[Tuple[str, float]] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    scores: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class LinkRun:
    head: Dict[str, str]
    proposals: List[Proposal]
    header_flags: List[str]


def toks(s: str) -> List[str]:
    words = re.sub(r"[^a-z0-9]+", " ", str(s).lower()).split(" ")
    out = []
    for w in words:
        if not w or w in STOP:
            continue
        out.append(w[:-1] if len(w) > 3 and w.endswith("s") else w)
    return out


def score(lab_desc: str, reg_text: str) -> float:
    """Share of the lab description's words found in the register text."""
    a = list(dict.fromkeys(toks(lab_desc)))
    b = toks(reg_text)
    if not a:
        return 0.0
    return sum(1 for w in a if w in b) / len(a)


def code_parts(s: str) -> Optional[Tuple[str, str]]:
    """Split a code into prefix and number: 'PBS 03' -> ('PBS', '3'), 'CH6-05' -> ('CH6', '5').

    The prefix says which test it is (M asbestos, HM heavy metals, ...), the
    number which sample. None when the code does not end in a number (e.g. 'S-O3').
    """
    t = str(s).upper().strip()
    parts = [p for p in re.split(r"[^A-Z0-9]+", t) if p]
    if len(parts) >= 2 and parts[-1].isdigit():
        return "".join(parts[:-1]), parts[-1].lstrip("0") or "0"
    for p in DIGIT_PREFIXES:
        if t.startswith(p) and t[len(p):].isdigit():
            return p, t[len(p):].lstrip("0") or "0"
    m = re.match(r"^([A-Z]+)([0-9]+)$", t)
    if m:
        return m.group(1), m.group(2).lstrip("0") or "0"
    return None


def id_key(s: str) -> str:
    """Compare IDs ignoring case, separators and zero padding."""
    cp = code_parts(s)
    if cp:
        return cp[0] + "|" + cp[1]
    t = str(s).upper().strip()
    parts = [p for p in re.split(r"[^A-Z0-9]+", t) if p]
    if len(parts) >= 2:
        return "".join(parts[:-1]) + "|" + re.sub(r"^0+(?=[0-9])", "", parts[-1])
    return t


def prefix_siblings(code: str, register: List["Sample"]) -> List["Sample"]:
    """Register samples with the same number but another prefix (M12 -> HM12)."""
    cp = code_parts(code)
    if not cp:
        return []
    out = []
    for s in register:
        sp = code_parts(s.id)
        if sp and sp[1] == cp[1] and sp[0] != cp[0]:
            out.append(s)
    return out


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


# Column names a lab may use, mapped to one name. Real IHM lab tables have
# SampleNumber | CertificateNumber | AnalysisMethod | AnalysisResult | Remarks | Quantity.
COLUMN_NAMES = {
    "id": "id", "sample": "id", "sampleid": "id", "samplenumber": "id", "sampleno": "id",
    "description": "description", "materialuse": "description",
    "method": "method", "analysis": "method", "analysismethod": "method", "analysisfor": "method",
    "result": "result", "analysisresult": "result", "analysisresults": "result",
    "certificate": "certificate", "certificatenumber": "certificate", "certificateno": "certificate",
    "quantity": "quantity", "remarks": "remarks",
}
DEFAULT_COLUMNS = ["id", "description", "result"]


def parse_columns(spec: str) -> List[str]:
    """'Sample No. | CertificateNumber | Result' -> ['id', 'certificate', 'result'].

    Unknown names are kept (lowercased) so nothing is silently dropped. Without
    an id, description or result column the default order is used instead.
    """
    cols = [COLUMN_NAMES.get(re.sub(r"[^a-z]", "", c.lower()), c.strip().lower()) for c in spec.split("|")]
    return cols if {"id", "result"} <= set(cols) else list(DEFAULT_COLUMNS)


def parse_report(text: str):
    """Header lines 'Key: value', then '---', then 'ID | description | result'.

    An optional header line 'Columns: id | description | method | result | certificate'
    names the columns, so a lab table with extra columns keeps them apart. Without
    it every line is read as ID | description | result, as before.
    """
    head: Dict[str, str] = {}
    rows: List[LabRow] = []
    in_rows = False
    cols = list(DEFAULT_COLUMNS)
    for ln in str(text).split("\n"):
        if not ln.strip():
            continue
        if ln.strip() == "---":
            in_rows = True
            cols = parse_columns(head["columns"]) if "columns" in head else list(DEFAULT_COLUMNS)
            continue
        if not in_rows:
            if ":" in ln:
                k, v = ln.split(":", 1)
                head[k.strip().lower()] = v.strip()
        elif cols == DEFAULT_COLUMNS:
            p = [x.strip() for x in ln.split("|")]
            p += [""] * (3 - len(p))
            rows.append(LabRow(len(rows), ln, p[0], p[1], " | ".join(p[2:])))
        else:
            p = [x.strip() for x in ln.split("|")]
            p += [""] * (len(cols) - len(p))
            cells = dict(zip(cols, p[:len(cols) - 1] + [" | ".join(p[len(cols) - 1:])]))
            extra = {k: v for k, v in cells.items() if k not in ("id", "description", "result")}
            rows.append(LabRow(len(rows), ln, cells.get("id", ""), cells.get("description", ""),
                               cells.get("result", ""), extra))
    return head, rows


def _has_id(r: LabRow) -> bool:
    t = r.raw_id.strip()
    return bool(t) and t not in ("-", "—")


def _unregistered_code(raw_id: str, best: str, prefixes: set) -> Optional[str]:
    """Why a well-formed but unknown lab code must not be guessed from its description.

    OS02 next to a register with OS01 is most likely a sample nobody registered,
    not a typo for OS01. M12 when the description fits HM12 is another test.
    Malformed codes (S-O3) and codes from another system (GS15) are not caught.
    """
    lab, reg = code_parts(raw_id), code_parts(best)
    if not lab:
        return None
    if reg and lab[1] == reg[1] and lab[0] != reg[0]:
        return f"{best} has the same number but prefix {reg[0]}, and the lab wrote {lab[0]}."
    if lab[0] in prefixes:
        return f"The register uses {lab[0]} codes, so this looks like a sample that was not registered."
    return None


def link(project: str, register: List[Sample], text: str) -> LinkRun:
    head, rows = parse_report(text)
    props: List[Proposal] = []
    for r in rows:
        sc = sorted(((s.id, score(r.desc, s.text)) for s in register), key=lambda x: -x[1])
        props.append(Proposal(index=r.index, row=r, scores=sc,
                              alts=[x for x in sc[:2] if x[1] >= 0.4]))
    by_id = {s.id: s for s in register}

    # pass 1: lines that carry an ID
    for p in props:
        r = p.row
        if not _has_id(r):
            continue
        exact = by_id.get(r.raw_id.strip())
        norm = next((s for s in register if id_key(s.id) == id_key(r.raw_id)), None)
        s = exact or norm
        if s is None:
            p.reason = f'ID "{r.raw_id}" is not in the sample register. '
            p.flags.append(f"row:{p.index}:unknown")
            continue
        mine = dict(p.scores)[s.id]
        best = p.scores[0]
        if mine < 0.5 and best[0] != s.id and best[1] >= 0.6:
            p.reason = (f"ID says {s.id} but the description matches {best[0]} ({pct(best[1])}) "
                        f"and {s.id} only {pct(mine)}. Conflicting evidence, so no link is proposed.")
            p.alts = [(s.id, mine), best]
            p.flags.append(f"row:{p.index}:conflict")
            continue
        # M12 and HM12 are different tests on the same spot: a better fit for the
        # sibling means the ID and the description disagree.
        sib = max(((t.id, dict(p.scores)[t.id]) for t in prefix_siblings(s.id, register)),
                  key=lambda x: x[1], default=None)
        if sib and sib[1] > mine:
            p.reason = (f"ID says {s.id} but the description fits {sib[0]} better ({pct(sib[1])} "
                        f"against {pct(mine)}). {s.id} and {sib[0]} differ only by prefix, which "
                        "marks a different test, so no link is proposed. Ask the lab which test this is.")
            p.alts = [(s.id, mine), sib]
            p.flags.append(f"row:{p.index}:prefix_conflict")
            continue
        p.status, p.sample_id = "propose", s.id
        if exact:
            p.confidence = "high" if mine >= 0.5 else "low"
            p.reason = ("ID matches register exactly. " +
                        (f"Description agrees ({pct(mine)})." if mine >= 0.5
                         else f"Description only partly agrees ({pct(mine)}), please check."))
        else:
            p.confidence = "medium" if mine >= 0.5 else "low"
            p.reason = (f'ID "{r.raw_id}" normalised to {s.id} (case, spaces, zero padding). ' +
                        (f"Description agrees ({pct(mine)})." if mine >= 0.5
                         else f"Description only partly agrees ({pct(mine)})."))

    # pass 1.5: several lines proposing the same sample
    groups: Dict[str, List[Proposal]] = {}
    for p in props:
        if p.status == "propose":
            groups.setdefault(p.sample_id, []).append(p)
    for sid, grp in groups.items():
        if len(grp) > 1:
            for p in grp:
                p.reason = (f"Several lab rows point to {sid}. No link is proposed until the "
                            "inspector decides which one is right.")
                p.status, p.sample_id, p.confidence = "none", None, None
                p.flags.append(f"row:{p.index}:duplicate")

    claimed = {p.sample_id: p.index for p in props if p.status == "propose"}
    prefixes = {cp[0] for cp in (code_parts(s.id) for s in register) if cp}

    # pass 2: description only (no ID, or unknown ID)
    for p in props:
        if p.status != "none" or any(f.split(":")[-1] in ("conflict", "duplicate", "prefix_conflict")
                                     for f in p.flags):
            continue
        r = p.row
        best, second = p.scores[0], (p.scores[1] if len(p.scores) > 1 else ("", 0.0))
        pre = p.reason if _has_id(r) else "No ID on this lab line. "
        if best[1] >= 0.7 and best[1] - second[1] >= 0.25:
            if best[0] in claimed:
                p.reason = (f"{pre}The description matches {best[0]} ({pct(best[1])}), but that sample "
                            f"is already linked by ID to row {claimed[best[0]] + 1}. No link proposed.")
                p.flags.append(f"row:{p.index}:collision")
                continue
            why = _unregistered_code(r.raw_id, best[0], prefixes) if _has_id(r) else None
            if why:
                p.reason = (f"{pre}{why} The description fits {best[0]} ({pct(best[1])}), but the ID "
                            "and the description disagree, so no link is proposed.")
                p.alts = [best]
                p.flags.append(f"row:{p.index}:unregistered")
                continue
            p.status, p.sample_id, p.confidence = "propose", best[0], "low"
            p.reason = (f"{pre}Matched on description only: {best[0]} ({pct(best[1])}, next best "
                        f"{pct(second[1])}). Low confidence, inspector must confirm.")
            claimed[best[0]] = p.index
        elif best[1] >= 0.7:
            p.reason = (f"{pre}Two or more samples fit the description equally "
                        f"({' and '.join(x[0] for x in p.scores[:2])}). No link proposed.")
            p.alts = p.scores[:2]
            p.flags.append(f"row:{p.index}:ambiguous")
        else:
            p.reason = f"{pre}No sample in the register fits the description well enough. No link proposed."
        # same rule B as above, also when the description did not point anywhere,
        # so a later step (the AI) cannot link an unregistered code either
        lab = code_parts(r.raw_id) if p.status == "none" and _has_id(r) else None
        if lab and lab[0] in prefixes:
            p.reason += f" The register uses {lab[0]} codes, so this looks like a sample that was not registered."
            p.flags.append(f"row:{p.index}:unregistered")

    header_flags: List[str] = []
    hp = head.get("project")
    if hp and hp != project:
        swapped = sorted(hp) == sorted(project)
        header_flags.append(f"Report header says project {hp}, the case is {project}." +
                            (" Looks like swapped characters." if swapped else ""))
    return LinkRun(head=head, proposals=props, header_flags=header_flags)


def samples_without_proposal(register: List[Sample], run: LinkRun) -> List[Sample]:
    linked = {p.sample_id for p in run.proposals if p.status == "propose"}
    return [s for s in register if s.id not in linked]
