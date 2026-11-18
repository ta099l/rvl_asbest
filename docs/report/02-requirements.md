# Functional and non-functional requirements

James · AI-assisted linking of lab results for RVL Asbest · Version 2 · 17 November 2026

**Status:** requirements as built and tested on 17 November 2026. Sources: RVL onboarding (9 September 2026), the KPI sheet (K1 to K10), test cases TC01 to TC12, RVL's sample code list (6 November 2026) and decisions in `docs/decisions.md`. Client acceptance is still required. Priorities use MoSCoW: **M**ust, **S**hould, **C**ould, **W**on't (this time).

**Status labels:** **Done** = built and covered by automated tests on fictional data. **Partial** = built for part of the requirement. **Open** = not built yet. "Done" does not mean validated on real RVL reports.

## 1. Functional requirements

### 1.1 Project and field registration

| ID | Requirement | Prio | Acceptance check | Status |
| --- | --- | --- | --- | --- |
| FR-01 | A user can create a project with the Project Information fields of the RVL IHM template (object, project number, survey location, period, client, owner, people). | M | Creating a project without name, project number or location is refused; a created project can be selected. | Done |
| FR-02 | A user can register a sample with code, source, deck, location, part, material, colour, photo, drawing position, quantity and unit. | M | The sample appears in the register and is offered to the linker. A registered code cannot change; every change is logged with name and time. | Done |
| FR-03 | A user can register a place that could not be sampled, with a reason. | M | It is never offered to the linker, never counts as a missing result, and appears as a survey limitation (PCHM) in the report (TC08). | Done |
| FR-04 | A user can switch between projects; data is kept when the application restarts. | M | After a restart every project and decision is still there and every report can be opened. | Done |

### 1.2 Reading lab reports

| ID | Requirement | Prio | Acceptance check | Status |
| --- | --- | --- | --- | --- |
| FR-05 | A user can paste a lab report as text or upload a PDF. | M | Pasted text and a digital PDF show their lab lines; a scanned PDF is read by OCR and says so. | Done |
| FR-06 | The system reads the two-table lab layout: an overview table (lab ID to RVL code and place) and results tables keyed by the lab ID. | M | Each result is joined to the RVL code; the lab ID is kept; a result whose lab ID is not in the overview gets no code and a warning. | Done (fictional layouts) |
| FR-07 | The system keeps lab remark letters with the result and warns about them. | M | "<10 mg/kg (lab remark C)" stays visible; a warning says a "<" value with a remark is not "absent". | Done |
| FR-08 | The system recognises a report that replaces an older version. | S | The header shows "Replaces: ..." and a note says older results are superseded. | Done |
| FR-09 | The system summarises multi-parameter results without losing values. | S | 16 equal values become "all 16 parameters <0,1 mg/Kg"; different values are listed per parameter; values that cannot be paired with parameters are not guessed. | Done |
| FR-10 | Each extracted field (sample ID, substance, result, unit, detection limit, method, certificate) is available separately (K1). | S | Field-level accuracy can be measured per field. | Partial: unit and limit stay inside the result text |

### 1.3 Linking

| ID | Requirement | Prio | Acceptance check | Status |
| --- | --- | --- | --- | --- |
| FR-11 | The system proposes a link only to a registered sample. | M | A proposed code that is not in the register never appears. | Done |
| FR-12 | The system reads RVL codes with spelling variants and older notations (CH6 = CR6, PAC = PAH, M = MM, ZM = HM). | M | CR601, CR6 01 and CR6-1 are one code; a link through an older notation is at most "medium" and says so. | Done |
| FR-13 | The system proposes no link, with a reason, when evidence is missing or conflicts. | M | Unknown code of a known family, prefix conflict (M12 vs HM12), code and place pointing to different samples, two equal candidates, one sample proposed for two lines: all give "no link" with a reason. | Done |
| FR-14 | The system checks that the result fits the test of the sample code. | M | A heavy-metals result on a CR6 code gives "no link". | Open (in prompt v3 only; dev4 case g9 is the one remaining wrong link) |
| FR-15 | The AI step is used only for lines the rules cannot settle safely. | S | Certain links and conflicts never go to the AI; rules and AI disagreeing gives "no link"; an invalid AI answer turns every line into "no link"; AI-only links are at most "medium". | Done |
| FR-16 | The prompt version can be chosen and is recorded with every report. | S | JAMES_PROMPT selects the version; the report evidence shows it. | Done |

### 1.4 Review and sign-off

| ID | Requirement | Prio | Acceptance check | Status |
| --- | --- | --- | --- | --- |
| FR-17 | A named inspector approves, corrects (links to another sample) or rejects every line. | M | Each decision stores name, time and note; a decision cannot be made without a name. | Done |
| FR-18 | A decision can be changed; the old decision stays in the log. | M | "Change decision" reopens the line; both decisions are in the audit log. | Done |
| FR-19 | Lines that need a human are shown first, with the chain sample, source, location, object, photo and certificate. | M | "Needs your attention" lists check and no-link lines above certain links. | Done |
| FR-20 | Missing information is flagged: sample without result, missing photo, drawing or certificate number. | S | A seeded gap appears as a flag (K3). | Done |
| FR-21 | The Technical Responsible Person signs when every line is decided; signing locks the decisions and records open items. | M | Signing is refused while lines are open; after signing no decision can change. | Done |
| FR-22 | A practice review loads a report with deliberately wrong links and scores the reviewer (K10). | S | Approving everything scores 0 of 5; a practice report can never be signed or exported. | Done |

### 1.5 Report and records

| ID | Requirement | Prio | Acceptance check | Status |
| --- | --- | --- | --- | --- |
| FR-23 | Each approved result is classified per substance against thresholds (Table A or B). | S | "Lead 100 mg/kg" is listed and flagged "inspector confirms"; an unknown substance is never classified from the sample code. | Done (thresholds to confirm by RVL) |
| FR-24 | The system fills RVL's IHM template (.odt) from approved lines only. | M | Cover, header and footer, Project Information, Part I lists, sections 2.3.1 to 2.3.7, survey limitations, Table 15 and 16 are filled; nothing is left as a placeholder. | Done |
| FR-25 | Results without a section in the template (for example PAH) appear in a section 2.3.8 "Other substances". | S | Approved PAH results are listed there and never in Table A or B. | Done (to confirm by RVL) |
| FR-26 | The report summary is written from the project's own data. | S | It names the object, project, location, period, approved/rejected/open lines and per substance the samples above or below the threshold. | Done |
| FR-27 | Evidence is kept with every report: file name, SHA-256 fingerprint, read method, linker version, prompt version. | M | The evidence is visible; a report read before the register changed is marked out of date. | Done |
| FR-28 | Every action of the agent and the inspector is logged with a time. | M | The audit log shows reading, proposals, decisions and sign-off. | Done |
| FR-29 | Approved results are saved per version in the object history. | S | A changed result at the next survey is marked. | Done |
| FR-30 | Photos can be uploaded and placed in the report. | C | — | Open (a photo reference is stored) |

### 1.6 Access

| ID | Requirement | Prio | Acceptance check | Status |
| --- | --- | --- | --- | --- |
| FR-31 | A shared copy requires a login; the name that signs a decision is the logged-in name. | M | Without JAMES_USERS a hosted copy refuses to start; the browser cannot sign as someone else. | Done |

## 2. Non-functional requirements

| ID | Quality | Requirement and measure | Target | Current status |
| --- | --- | --- | --- | --- |
| NFR-01 | Safety | The system only proposes; nothing is final without a named inspector. | 100% of report lines decided by a person | Done: export uses approved lines only; signing needs every line decided |
| NFR-02 | Safety | Wrong links on the evaluation sets. | 0 | 1 of 55 fictional lines (FR-14 open) |
| NFR-03 | Correctness | Correct links (K2). | at least 98% of linkable lines | Rules: 40 of 44 linkable lines correct (91%) on fictional data |
| NFR-04 | Correctness | Field extraction accuracy per field (K1). | at least 95% | Not measured; no labelled real reports |
| NFR-05 | Calibration | Lines marked "high" confidence are correct (K9). | at least 98% | High only for exact codes confirmed by the description; AI-only links capped at medium; not measured separately |
| NFR-06 | Safe failure | Invalid AI output, a failed AI call or a wrong key never creates a link. | 100% | Done: tested; a run with a wrong key gave no AI links, only the rules' proposals |
| NFR-07 | Traceability | Every link can be traced to source file, version, rule or AI reason and person. | 100% | Done: evidence, audit log, append-only decisions |
| NFR-08 | Privacy | No real client, location or personal data in an unapproved AI service. | 0 exceptions | Fictional data only; AI off by default; RVL approval not yet given |
| NFR-09 | Security | Secrets never in the repository; hosted access only with login; signed session cookie; slow-down after failed logins. | 0 secrets in git | Done; passwords are kept in the hosting environment, not yet hashed |
| NFR-10 | Performance | Time per lab report compared with today's manual work (K5). | at least 50% faster | Not measured; RVL baseline needed |
| NFR-11 | Responsiveness | The AI step answers per request within seconds; screen actions feel immediate. | AI under 5 s per request | Mostly met: 0.4 to 9 s per request on Groq, most under 2 s |
| NFR-12 | Usability | System Usability Scale with inspectors (K8). | at least 68 | Not measured |
| NFR-13 | Accessibility | Labelled form fields, visible keyboard focus, readable contrast, works on phone width. | WCAG 2.1 AA basics | Built 17 November; not audited |
| NFR-14 | Compatibility | Output follows RVL's IHM template and terminology; opens in Word and LibreOffice. | Accepted by RVL reviewer | Export built; RVL review pending; template text gaps reported |
| NFR-15 | Maintainability | Automated tests run before and after every change; decisions recorded. | All tests pass | 212 automated tests pass (153 linking, 59 app) |
| NFR-16 | Portability | Runs on Windows and Linux with Python 3 and one PDF library; OCR optional. | Runs on both | Done |
| NFR-17 | Cost | AI cost per report and hosting cost stay small. | Under €0.10 per report; under €10 per month hosting | About $0.006 per 45 lines (gpt-oss-20b); about $7.25 per month hosting |
| NFR-18 | Availability | A shared copy keeps its data and can be restored. | No data loss | Persistent disk on Render; backups not yet arranged |

## 3. Constraints

- RVL's rules: AI output is a proposal; an authorised inspector stays responsible; no company, client, location or personal data in unapproved AI tools.
- The IHM template is RVL's property and is not stored in the repository.
- Thresholds in `app/thresholds.json` are proposals until RVL confirms them.

## 4. Open questions for RVL

1. Which AI provider and which data may be used outside test data?
2. Where do PAH results belong in an RVL report?
3. Is a lab code "PCB-01" an RVL SS, PBS or OS sample?
4. Are M00 and V00 still in use, and what do they mean?
5. Which threshold values apply?
6. Does every lab line carry its own certificate number?
