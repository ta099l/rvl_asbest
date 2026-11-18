"""Read lab results into IHM terms: which substance, above or below the threshold, Table A or B.

Everything here is a PROPOSAL for the inspector. The thresholds live in
thresholds.json and are marked "to confirm by RVL". When a result cannot be
read with certainty, the finding says so instead of guessing.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

THRESHOLDS = Path(__file__).resolve().parent / "thresholds.json"

# How each substance is written in a lab result or analysis name.
NAMES = {
    "asbestos": r"asbest|chrysotil|amosit|crocidolit|tremolit|actinolit|anthophyllit",
    "pcb": r"\bPCBs?\b",
    "ods": r"\bODS\b|\bH?CFC|halon",
    "tbt": r"\bTBT\b|organotin|tributyltin",
    "pfos": r"\bPFOS\b",
    "cd": r"\bCd\b|cadmium",
    "cr6": r"Cr\s*\(?VI\)?|CrVI|Cr6|chroo?m\w*[- ]?6|hexavalent",          # Dutch: Chroom-6
    "pb": r"\bPb\b|\blead\b|\blood\b",                       # Dutch: lood
    "hg": r"\bHg\b|mercury|\bkwik\b",                      # Dutch: kwik
    "hbcdd": r"HBCDD?",
    "radio": r"radioactiv",
    "pah": r"\bPAH\b|\bPAK\b|poly-?\s?aromati|polycyclic aromatic",   # not an IHM substance: no table
}
# Sample code prefixes RVL uses, as a hint when the result itself names no substance.
PREFIX_HINT = {"M": "asbestos", "MM": "asbestos", "KM": "asbestos", "PBS": "pcb", "SS": "pcb", "OS": "pcb",
               "ODS": "ods", "PFOS": "pfos", "HBCDD": "hbcdd", "CH6": "cr6", "CR6": "cr6"}
# A result that names its own substance, e.g. "Zink (Zn) 18000 mg/kg". When that substance is not in
# NAMES, it must not be guessed from the method or the sample code: zinc is not chromium-6.
NAMED_SUBSTANCE = re.compile(r"[A-Za-z]{3,}\s*\([A-Z][a-z]?\)")
NOT_DETECTED = re.compile(r"not\s+detected|n\.?d\.?\b|none\s+detected|absent", re.I)
DETECTED = re.compile(r"detected|present|positive", re.I)
VALUE = re.compile(r"(<|≤|>|≥)?\s*(\d[\d.,]*)(?:\s*[–-]\s*(\d[\d.,]*))?\s*(%|mg/kg|ppm)", re.I)

# Sections 2.3.x of the RVL IHM template, in their fixed order, and which substances go in each.
SECTIONS_2_3 = [
    ("2.3.1", "Asbestos", ["asbestos"]),
    ("2.3.2", "PCB's", ["pcb"]),
    ("2.3.3", "Ozone Depleting Substances (ODS)", ["ods"]),
    ("2.3.4", "PFOS", ["pfos"]),
    ("2.3.5", "HBCDD", ["hbcdd"]),
    ("2.3.6", "Heavy metals (Lead - Pb + Chromium - Cr + Cadmium - Cd)", ["pb", "cr6", "cd", "hg"]),
    ("2.3.7", "Radioactive Materials", ["radio"]),
    ("2.3.x", "Other substances (not a section in the template)", ["tbt", "pah", None]),
]
# The fixed lines of Table A (Table 15) and Table B (Table 16) in the RVL IHM template.
# (label, table, substance keys, extra test on the source: None, "paint" or "battery")
TABLE_LINES = [
    ("A-1 Asbestos", "A", ["asbestos"], None),
    ("A-2 Polychlorinated Biphenyls (PCB)", "A", ["pcb"], None),
    ("A-3 Ozone Depleting Substances (ODS)", "A", ["ods"], None),
    ("A-4 Anti-fouling Systems Containing Organotin Compounds", "A", ["tbt"], None),
    ("B1 Hexavalent Chromium, B2 Cadmium", "B", ["cr6", "cd"], None),
    ("B3 Lead – Paint", "B", ["pb"], "paint"),
    ("B3 Lead – Batteries", "B", ["pb"], "battery"),
    ("HBCDD", "B", ["hbcdd"], None),
    ("Radioactive Materials", "B", ["radio"], None),
    ("Mercury", "B", ["hg"], None),
]
BATTERY = re.compile(r"batter", re.I)

# ---------- Substance groups for the fieldwork tabs ----------
# The ONE mapping from a sample code to its group. Each prefix (in RVL's standard notation, after the
# linker's ALIASES: M -> MM, ZM -> HM, PAC -> PAH, CH6 -> CR6) names a substance key, and the section
# comes from section_2_3, the same function the export uses, so a tab and the report never disagree.
# prefix: (group, substance key or None, meaning)
PREFIX_GROUP = {
    "MM": ("asbestos", "asbestos", "asbestos, bulk sample"),
    "KM": ("asbestos", "asbestos", "asbestos, dust sample"),
    "PBS": ("pcb", "pcb", "PCB, bulk sample"),
    "SS": ("pcb", "pcb", "PCB, swipe sample"),
    "OS": ("pcb", "pcb", "PCB, oil sample"),
    "ODS": ("ods", "ods", "ozone depleting substances"),
    "PFOS": ("pfos", "pfos", "PFOS"),
    "PFAS": ("pfos", "pfos", "PFAS: reported under 2.3.4 PFOS until Rolf decides (question 17)"),
    "HBCDD": ("hbcdd", "hbcdd", "HBCDD"),
    "HM": ("metals", "pb", "heavy metals (zware metalen; older notation ZM)"),
    "CR6": ("metals", "cr6", "chromium-6 (older notation CH6)"),
    "NORM": ("radio", "radio", "naturally occurring radioactive material"),
    "PAH": ("other", "pah", "PAH (Dutch PAK; older notation PAC)"),
    "TBT": ("other", "tbt", "organotin, anti-fouling (Table A-4)"),
    "TPH": ("other", None, "total petroleum hydrocarbons"),
    "VOC": ("other", None, "volatile organic compounds"),
    "VI": ("other", None, "visual inspection, no lab sample"),
    "V": ("other", None, "visual registration, no lab sample (older notation, to check: Rolf question 14)"),
    "DR": ("other", None, "document review, no lab sample"),
    "EI": ("other", None, "equipment identification, no lab sample"),
}
# The tabs, in order: (group, label, main prefix for a new sample, always shown)
GROUPS = [
    ("asbestos", "Asbestos", "MM", True),
    ("pcb", "PCB", "PBS", True),
    ("metals", "Heavy metals", "HM", True),
    ("ods", "ODS", "ODS", False),
    ("pfos", "PFOS / PFAS", "PFOS", False),
    ("hbcdd", "HBCDD", "HBCDD", False),
    ("radio", "Radioactive", "NORM", False),
    ("other", "Other", None, False),
]
GROUP_LABEL = {g: label for g, label, _, _ in GROUPS}


def _std_parts(code: str):
    """(prefix as written, standard prefix, number) or None. Parsing and aliases are the linker's own."""
    from ai.james_ai.linker import code_parts, std_prefix
    cp = code_parts(code or "")
    return (cp[0], std_prefix(cp[0]), int(cp[1])) if cp else None


def group_for_code(code: str) -> dict:
    """Which fieldwork tab and report section a sample code belongs to.

    A code whose prefix is not in PREFIX_GROUP goes to Other WITH a warning ('unknown'): a typo such
    as MI02 must not silently disappear from the asbestos tab. VI, DR, EI and V are known codes for an
    assessment without a lab sample, so they go to Other without a warning.
    """
    parts = _std_parts(code)
    known = parts and parts[1] in PREFIX_GROUP
    group, key, meaning = PREFIX_GROUP[parts[1]] if known else ("other", None, "")
    return {"key": group, "label": GROUP_LABEL[group], "section": section_2_3(key),
            "prefix": parts[1] if parts else "", "meaning": meaning, "unknown": not known}


def group_section(group: str) -> str:
    """The report section of a group, from its main prefix (Other: 2.3.x)."""
    main = next(m for g, _, m, _ in GROUPS if g == group)
    return section_2_3(PREFIX_GROUP[main][1] if main else None)


def next_code(codes: List[str], group: str) -> Optional[str]:
    """The next free code for a new sample in a group, in the style the project already uses:
    M03 after M02, PBS04 after PBS03, MM-6 after MM-5. An empty group starts with RVL's standard
    form (MM-1). Other has no main prefix, so the inspector types the code."""
    main = next(m for g, _, m, _ in GROUPS if g == group)
    if not main:
        return None
    same = [(p[2], c.strip()) for c in codes for p in [_std_parts(c)] if p and p[1] == main]
    if not same:
        return f"{main}-1"
    n, last = max(same)
    m = re.match(r"^(.*?)(\d+)$", last)
    digits = m.group(2)
    width = len(digits) if digits.startswith("0") and len(digits) > 1 else 1
    return m.group(1) + str(n + 1).zfill(width)


def section_2_3(key: Optional[str]) -> str:
    return next(no for no, _, keys in SECTIONS_2_3 if key in keys)


def table_line(key: str, material: str, part: str) -> Optional[str]:
    """The Table A/B line a finding counts towards, or None when the template has no line for it."""
    for label, _, keys, test in TABLE_LINES:
        if key not in keys:
            continue
        if test == "paint" and not PAINT.search(material or ""):
            continue
        if test == "battery" and not BATTERY.search(f"{material} {part}"):
            continue
        return label
    return None


# Part I lists of the IHM: I-1 paints and coatings, I-2 equipment and machinery, I-3 structure and hull.
PAINT = re.compile(r"paint|coating|primer|varnish|lacquer", re.I)
EQUIPMENT = re.compile(r"pump|transformer|cable|engine|motor|generator|compressor|valve|switchboard|"
                       r"boiler|cold room|refrigerat|freezer|air.?condition|radar|battery|fan", re.I)
PART_I = {"I-1": "Paints and Coating Systems", "I-2": "Equipment and Machinery", "I-3": "Structure and Hull"}


def load_thresholds(path: Path = THRESHOLDS) -> Dict[str, dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {s["key"]: s for s in data["substances"]}


AMBIGUOUS = re.compile(r"^\d{1,3}[.,]\d{3}$")       # 1,400 is 1400 in English and 1.4 in Dutch


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _code_hint(code: str) -> Optional[str]:
    m = re.match(r"^([A-Za-z]+\d?)[\s-]*\d", (code or "").strip())
    if not m:
        return None
    p = m.group(1).upper()
    return PREFIX_HINT.get(p) or PREFIX_HINT.get(re.sub(r"\d$", "", p))


def findings(result: str, method: str = "", code: str = "", table: Optional[Dict[str, dict]] = None) -> List[dict]:
    """Split one lab result into findings, one per substance.

    'Cr(VI) 8 mg/kg; Pb 1,200 mg/kg' gives two findings. A result without a
    substance name ('85 mg/kg') takes it from the analysis method, then from the
    sample code prefix. Each finding has status above / at / below / unknown.
    """
    table = table or load_thresholds()
    out: List[dict] = []
    for seg in [x.strip() for x in re.split(r";", result or "") if x.strip()]:
        keys = [k for k, rx in NAMES.items() if re.search(rx, seg, re.I)]
        if not keys and not NAMED_SUBSTANCE.search(seg):
            keys = [k for k, rx in NAMES.items() if re.search(rx, method or "", re.I)][:1]
        if not keys and _code_hint(code) and not NAMED_SUBSTANCE.search(seg):
            keys = [_code_hint(code)]
        if not keys:
            out.append({"key": None, "name": "Unknown substance", "table": None, "status": "unknown",
                        "value": None, "unit": "", "text": seg,
                        "note": "The substance could not be read from the result. The inspector classifies it."})
            continue
        for k in keys[:1]:
            out.append(_judge(k, seg, table[k]))
    return out


def _judge(key: str, seg: str, t: dict) -> dict:
    f = {"key": key, "name": t["name"], "table": t["table"], "value": None, "unit": t["unit"], "text": seg,
         "threshold": t["threshold"], "status": "unknown", "note": ""}
    if NOT_DETECTED.search(seg):
        f.update(status="below", note="not detected")
        return f
    m = VALUE.search(seg)
    if m:
        sign, lo, hi, unit = m.group(1), m.group(2), m.group(3), m.group(4).lower().replace("ppm", "mg/kg")
        if AMBIGUOUS.match(hi or lo):
            f.update(unit=unit, note=f"“{hi or lo}” can be read as thousands or as decimals: the inspector reads the certificate")
            return f
        value = _num(hi or lo)
        f.update(value=value, unit=unit)
        if sign in ("<", "≤"):
            f.update(status="below", note=f"below the detection limit ({seg})")
        elif t["table"] is None:            # not in IHM Table A or B (e.g. PAH): never listed by the app
            f.update(note="not in IHM Table A or B: the inspector decides how it is reported")
        elif t["threshold"] is None:
            f.update(status="above", note="no threshold: any detection is listed")
        elif unit != t["unit"]:
            f.update(note=f"unit {unit} differs from the threshold unit {t['unit']}: the inspector compares")
        elif value > t["threshold"]:
            f.update(status="above", note=f"above {t['threshold']:g} {t['unit']}")
        elif value == t["threshold"]:
            f.update(status="at", note=f"exactly on the threshold of {t['threshold']:g} {t['unit']}: inspector confirms")
        else:
            f.update(status="below", note=f"below {t['threshold']:g} {t['unit']}")
        return f
    if DETECTED.search(seg) or key == "asbestos":
        if t["detected_counts"]:
            f.update(status="above", note="detected")
        else:
            f.update(note="detected, but no value to compare with the threshold: the inspector decides")
    return f


def part_i(material: str, part: str, location: str = "") -> str:
    """Which Part I list a material goes on. A proposal: the inspector checks it.

    Only the part and the material count, not the room: board on an engine room
    bulkhead is structure, not machinery.
    """
    if PAINT.search(material or ""):
        return "I-1"
    if EQUIPMENT.search(" ".join([part or "", material or ""])):
        return "I-2"
    return "I-3"


# Sample type from the code family in the RVL Sample Identification Key.
SAMPLE_TYPES = {"KM": "Asbestos dust sample", "SS": "PCB surface wipe sample", "OS": "PCB oil sample",
                "V": "Visual registration"}


def sample_type(code: str) -> str:
    m = re.match(r"^([A-Za-z]+)", (code or "").strip())
    return SAMPLE_TYPES.get(m.group(1).upper(), "Bulk material sample") if m else "Bulk material sample"


def sum_quantities(qs: List[tuple]):
    """Add up source quantities for one Table A/B line. Only when every source has a number in the same unit.

    Returns (total, unit), or (None, "") when the inspector has to fill it in.
    """
    units = {(u or "").strip().lower() for _, u in qs}
    try:
        nums = [float(str(q).replace(",", ".")) for q, _ in qs]
    except ValueError:
        return None, ""
    if len(units) != 1 or "" in units:
        return None, ""
    total = sum(nums)
    return (int(total) if total == int(total) else round(total, 2)), units.pop()
