# Project context (from the team portfolio)

Summary of `RVL Asbest Portfolio.docx` (template + business analysis) and Harm's chapters 2, 12, 13, 14 (version 1, 26 Oct 2026). The source files live in `context/`, which is not committed. Only the team's own writing was used here; the RVL project dossiers and the IHM report in `context/` were **not** read (safety rule 6).

## Team and roles

| Who | Role | Owns |
|---|---|---|
| Ivan | Builder | Prototype front-end, back-end, integrations · Ch. 10 Data & Architecture · Appendix G · Ch. 9 + Appendix J with Tasnim |
| Tasnim | Builder | AI agent and workflow · Ch. 11 Prompting · Appendix A |
| Sydney | Analysis & business case | Ch. 3, 4, 5, 8 · Appendices E, F |
| Chris | Strategy & final editing | Ch. 1, 6, 7, 15 · executive summary |
| Harm | Validation & handover | Ch. 2, 12, 13, 14 · KPI sheet (H), test cases (I), transition document (K) |

Client and product owner: Rolf van Leeuwen. Practice expert (IHM and lab): Joris, validates the gold standard and draft reports. Coach: Rigo Magsino.

## Dates

- 23 Oct 2026: prototype v1 (core flow, first AI extraction, demo for RVL).
- Week of 2 Nov 2026: mid-term evaluation and **test round 1 with Joris** on v1.
- Nov to early Dec: sprints v2 and v3, each with the test set and a user test.
- Mid Dec: prototype frozen, final test round.
- 16 Jan 2027: final deadline (portfolio, report, presentation). No transition document means no assessment.

## Agreed scope

In: one workflow (IHM/HazMat Part I for ships), data model project → object → survey location → source → sample → lab result, lab-report import with AI extraction linked to the right sample, completeness check and inspector review, draft report on the RVL IHM template, test framework, KPI sheet, transition document.

Out: production platform, all survey types at once, replacing the inspector's judgement, real client data without approval, unapproved integrations.

## KPIs the prototype is measured on (Harm, Ch. 12)

| ID | KPI | Target | Prototype today |
|---|---|---|---|
| K1 | Extraction accuracy per field (sample ID, substance, result, unit, detection limit, method, certificate no.) | ≥ 95% | Only ID / description / result are extracted |
| K2 | Correct sample link | ≥ 98%, 0 silent wrong links | Measured by `ai/` scoring (wrong links 0 on dev/dev2) |
| K3 | Completeness check: seeded gaps found / false alarms | ≥ 90% / ≤ 15% | Flags for missing result and missing photo; no certificate-number check |
| K4 | Unclear cases escalated | 100% | No-link with reason; unreadable OCR fields not yet flagged per field |
| K5 | Processing time per lab report | ≥ 50% faster | Not measured; RVL baseline needed |
| K6 | Draft report fields correct (Table A/B, source records) | ≥ 90% | Ch. 9 table; Ch. 10 only "asbestos detected → Table A" |
| K7 | Full chain sample → source → location → photo → certificate | 100% | Chain shown up to photo; certificate number missing |
| K8 | Usability (SUS) | ≥ 68 | User test not done |
| K9 | Calibration: "high confidence" correct | ≥ 98% | Labels come from objective rule checks, as Harm's design asks |
| K10 | Seeded errors found by the reviewing inspector | ≥ 80% | Needs a review mode with seeded errors |

Harm's design rule for K9: never trust a confidence score the model gives itself. "High confidence" only when objective checks pass: ID exists and is unique, value and unit fit the substance, the value is literally in the source, and repeated runs agree.

## Test cases (Harm, Appendix I) and what they ask of the prototype

| TC | Case | Needs in the prototype |
|---|---|---|
| TC01 | Clean digital certificate, 10 asbestos samples | Extraction of all fields + links |
| TC02 | Low-quality scan, 2 values unreadable | Per-field "check needed", never guessed |
| TC03 | Sample ID on certificate not in project | No link + escalation (works) |
| TC04 | Same sample ID twice in the project | Duplicate flagged, no automatic choice |
| TC05 | Lead exactly on the threshold | Exact value, no rounding, Table B |
| TC06 | PCB, ODS and Cr(VI) on one certificate | Each in the right IHM category |
| TC07 | Source without photo and without certificate no. | Completeness warning on both |
| TC08 | Inaccessible area, not sampled | Registered as PCHM / limitation, not "absent" |
| TC09 | Manual vs James processing time | Stopwatch test |
| TC10 | Full synthetic project → draft IHM report | ≥ 90% fields, full chain |
| TC11 | Same input three times | Same output; differences flagged |
| TC12 | Draft with 5 seeded errors | Inspector finds ≥ 4 |
| TC13 | Think-aloud + SUS | Usability |

## Open point: sample code format

Harm's chapters use `MM00` for asbestos and `CR600` for chromium-6. `CLAUDE.md` and the test cases in `ai/` use `M`, `KM` and `CH6-nn`, as does the demo artifact (`M01`). Ask Rolf or Joris which notation is real before test round 1.

## Structure of a real RVL IHM report (headings and table columns only)

Taken from a skeleton of one real IHM report (headings and table header rows only, identifiers removed, checked before reading). No content was read.

- **Front:** project number, a project information table (about 17 fields), technical responsible person.
- **Summary of identified hazardous materials**, three tables in the IHM Part I layout, each `No. | Name | Location | Materials | Parts where used | Approximate quantity | Remarks`: I-1 paints and coatings, I-2 equipment and machinery, I-3 structure and hull.
- **1.2 Hazardous materials:** asbestos, PCB, ODS, organotin (TBT), PFOS. Terminology table.
- **2 Investigation and results:** 2.1 method (consultation table: name and rank), 2.2 desk research, 2.3 visual inspection and sample results:
  - a **sample identification key**: `Sample Code | Description` (about 10 codes) plus additional codes (about 7);
  - per substance (2.3.1 ... 2.3.7, including ODS and radioactive materials) the same three tables:
    1. samples: `Sample No. | Deck Level | Location | Material / Use | Sample Type | Analysis Results`;
    2. a `Description | Details` block per sample;
    3. lab results: `SampleNumber | CertificateNumber | AnalysisMethod | AnalysisResult | Remarks | Quantity (±)`.
- **3 Survey limitations:** general, inaccessible construction, locations not inspected: `No. | Deck Level / Area | Location / Equipment | Restriction / Reason | Recommended follow-up`. This is where TC08 (not sampled, PCHM) lands.
- **4 Safety and health.**
- **5 Conclusions:** Table A and Table B, `Hazardous Material | Quantity | Unit | IHM Table`; 5.2 recommendations.
- **Appendices:** A locations of sources, B lab certificates, C desk research, D accreditation, E Visual Sampling and Check Plan (`Zone | System | Component | Material to Check | Document Reference | Check Procedure | Analysis / Source Reference | Result | Notes`).

What this means for the prototype:
- The real report has no "Ch. 9 / Ch. 10". Results go in **2.3** (per substance), the Materials List is the **Part I summary (I-1/I-2/I-3)** and **5.1 Table A/B**. Check with Rolf which template is leading.
- Each lab result carries a **certificate number, analysis method and quantity**. These belong in the contract and the extraction (K1, K7, TC07).
- **Deck level** is its own field next to location.
- The sample code key is part of the report itself, so the code families (`M` or `MM`) can be read from it once someone checks a real key.

## Structure of a real RVL project dossier, hazardous substances (headings and table columns only)

1 project data (`Onderdeel | Gegevens`, 14 rows) · 2 scope and preliminary sample plan (`Voorgestelde codes | Onderdeel | Aantal`) · 3 desk research and sampling · 4 safety and access · 5 contract review and delivery · 6–7 **sample register** (`Code | Gepland onderdeel | Exacte locatie kleur lagen | Foto / tekening analyse`) · 8 **survey location sheet** (`Veld | Registratie`) · handover to lab · deviation and decision · 9 paint layer build-up (`Laag | Waargenomen kleur | Omschrijving en waarneming`).

The sample register is the field registration the linker matches against. The separate survey location sheet supports the survey-table proposal in `docs/decisions.md`. The asbestos dossier is one large form table and gave no usable skeleton.

## Business context in one paragraph

RVL is a small, certified inspection firm (asbestos, chromium-6, HazMat/IHM) in Kalenberg. Since the Hong Kong Convention entered into force (26 Jun 2025), ships of 500 GT and more need an IHM, existing ships by 2030, so demand grows while the team stays small. James should save time per survey, improve data quality and traceability, cut omissions, and reuse object history. Switching costs are low for a one-off report but high once the IHM record is maintained in James.

## RVL company onboarding (v1.0, 9 Sep 2026): what RVL asks for

Source: `context/RVL_Onboarding_English (1).docx` (team document from RVL, no client data). Contact details left out here.

**Success criteria (RVL's own words):**
1. A working prototype demonstrates the essential flow **from project creation and field registration** to linked laboratory results and a draft report.
2. Sources, samples, photos, **drawings** and locations stay consistently linked, and missing required information is flagged.
3. Inspectors can review, correct and approve AI-supported output; uncertainty and responsibilities are visible.

**Process:** project creation → desk research → planning → fieldwork → synchronisation → laboratory analysis → quality control → report → digital asset record. Start: client request. End: inspector-approved report plus structured data in the object dossier.

**First AI task:** extract structured sample results from a lab report and link them to the correct sample, source and location, with completeness checks. Augmentation only.
- Stop automatic processing when an identifier is absent, multiple matches exist, the document is unreadable, or values fall outside defined rules. Never silently guess.
- Keep as evidence: source file reference, extracted fields, match logic, warnings, human corrections, approver, version or timestamp.

**Users:** inspectors first; office and quality staff early in research and testing. Decision maker for the prototype: Rolf, plus an authorised inspector or **quality reviewer** for professional acceptance.

**Non-negotiable:** no company, client, location or personal data in unapproved AI tools; access only with permission from Rolf; AI output is a proposal; record uncertainty and corrections; an authorised inspector stays responsible for the final assessment and approval.

**Priority:** a credible end-to-end prototype and data model for James. Depth and reliability in a limited workflow over a broad interface with untested functions.

### Where the prototype stands against this (27 Oct 2026)

| RVL asks | Status |
|---|---|
| Project creation and field registration | **Missing.** The register is fixed demo data. |
| Lab-result extraction and linking with completeness checks | Built (rules + AI stand-in, flags, no-link on conflict). |
| Drawings linked | **Missing.** Only photo IDs. |
| Stop on absent ID / multiple matches / unreadable / out of rules | Absent ID and conflicts: yes. Ambiguous numbers: yes. Unreadable OCR fields: only a page-level note. |
| Evidence: source file reference, match logic, corrections, approver, version | Match reason, corrections, approver, time: yes. **Source file reference and linker/prompt version: missing.** |
| Quality control step | One person decides and signs. Whether a second reviewer is needed: ask Rolf. |
| Inspector-approved report + object dossier | Sign-off and asset history: yes (draft sections only). |

## RVL's own documents (added 27 Oct 2026, afternoon)

All in `context/` (not committed). None holds client data: the IHM file is RVL's **empty template** with placeholders.

### IHM template (`IHM 26-.odt`): the leading report layout
- **Title page / Project Information:** Project Number, Survey Location, Vessel Name, Vessel Type, Client, Client Address, Owner, Owner Address, Contractor (James), Survey Period, Survey Conducted By, **Technical Responsible Person**, Project Coordinator, Report Status, Report Version, Report Valid Until. Signed "On behalf of James" by the Technical Responsible Person (date, signature).
- **Summary of Identified Hazardous Materials**, each list with its own columns:
  - I-1 Paints and Coating Systems: No. | Application of Paint | Name of Paints | Location | Materials | Approximate Quantity | Remarks
  - I-2 Equipment and Machinery: No. | Name of Equipment and Machinery | Location | Materials | Parts Where Used | Approximate Quantity | Remarks
  - I-3 Structure and Hull: No. | Structural Component | Location | Materials | Parts Where Used | Approximate Quantity | Remarks
- **14 standard remarks** (estimated quantities, PCHM, thresholds, XRF does not show Cr(VI), paint quantities in m², ...).
- **2.3 per substance:** 2.3.1 Asbestos, 2.3.2 PCB's, 2.3.3 ODS, 2.3.4 PFOS, 2.3.5 HBCDD, 2.3.6 Heavy metals (Pb + Cr + Cd), 2.3.7 Radioactive. Each: a sample table (Sample No. | Deck Level | Location | Material / Use | Sample Type | Analysis Results), a **Source Record per source** (Source Description, Sample Number, Laboratory Certificate, Location, Material, Analysis Results, Quantity, Conclusions and/or Recommendations "This concerns ..."), a lab table (Sample Number | Certificate Number | Analysis Method | Analysis Result | Remarks | Quantity (±)) and four photos.
- **Assessment methods** besides lab analysis: Visual Observation, Material Identification / Marking, Document Reference. What cannot be settled is PCHM.
- **Sample Identification Key:** MM00 asbestos, KM00 asbestos dust, PBS00 PCB bulk, SS00 PCB wipe, OS00 PCB oil, ODS00, PFOS00, HBCDD00, HM00; additional TBT00, PAH00, PFAS00, CR600, NORM00, TPH00, VOC00.
- **3 Survey Limitations:** No. | Deck Level / Area | Location / Equipment | Restriction / Reason | Recommended Follow-up.
- **5.1 Table 15 (A):** A-1 Asbestos, A-2 PCB, A-3 ODS, A-4 Anti-fouling (organotin). **Table 16 (B):** B1 Cr(VI) + B2 Cadmium, B3 Lead (100 mg/kg) – Paint, B3 Lead – Batteries, HBCDD, Radioactive Materials, Mercury. Columns: Hazardous Material | Quantity | Unit | IHM Table.
- **Appendices:** A source locations on deck plans, B lab certificates, C desk research, D accreditation, E VSCP (Zone | System | Component | Material to Check | Document Reference | Check Procedure | Analysis / Source Reference | Result | Notes).

### Work process (`V1 James uitleg AI studenten.docx`, Dutch)
- Chain: **Opdracht → Project → Object → Onderzoekslocatie → Vooronderzoek → Inspectie → Locatie in object → Bron/Toepassing → Foto → Monster → Analyse → Tekening → Resultaat → Rapport → Historie.**
- The survey location is recorded **separately from the object** (port, yard, terminal, quay, dock, country, dates): supports the survey-table proposal in `docs/decisions.md`.
- Location in a ship: **ship → deck → zone → room → installation/equipment**.
- A **source (bron)** is registered with: number, location, room/zone, application, material, part/installation, **quantity, unit**, attachment, accessibility, condition, damage, notes, sampling, photos, drawing position. A sample belongs to a source.
- Code list in this document: **M00** asbestos (the template says MM00), KM00, PBS00, SS00, OS00, ODS00, PFOS00, HBCDD00, HM00, **V00 visual registration**.
- Limitations are recorded with location and reason (closed rooms, live electrical installations, behind fixed finishes, tanks).

### Lloyd's checklist (`Inhoud hazmat - ihm part 1.docx`)
What a class society checks: cover with IMO number, ship name, survey date and location, approved service supplier; limitations; methodology and surveyors; SDoC/MD analysis; location codes matching the GA plan; per zone the sample IDs with a reference to lab result and photo; lab reports with sample ID, description, analysis, **detection limit**, lab signature; Materials List per item with material, **estimated weight, location, photo ID, document ID**; every HM labelled with photo and location. It proposes a 13-chapter layout (9 Sampling & Laboratory Results, 10 Materials List): that is where "Ch. 9 / Ch. 10" came from. RVL's own template is used as the leading layout.

### Process pictures (`Huidig bedrijfsproces.png`, `Uiteindelijk bedrijfsproces.png`)
As-is: the manual steps are reading GA drawings, processing results and linking them by hand, compiling the report by hand, and checking it against all sources. To-be: the agent prepares fieldwork from the GA drawings, receives results and links them, drafts the report and checks it for gaps; the inspector reviews and sends. A refit or 5-year renewal reuses the earlier data.
