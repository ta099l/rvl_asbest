# Decisions

One entry per decision: date, what, why, who agreed.

## 2026-10-26: Contract v1 for request and response (PROPOSED, waiting for Ivan)

- **What:** the request and response formats in `contract/` (schemas plus examples). The response is an object `{"proposals": [...]}`, not a bare list. Any broken answer turns every row into no link; a broken request raises an error.
- **Why:** an object can get new fields later without breaking the app. All-or-nothing rejection follows safety rule 4: a partly broken answer is not trusted for any line. Strict codes (exact spelling, must be in the register) follow rule 3.
- **Open point:** the v1 prompt (`ai/prompts/_output_format.txt`) still asks the model for a bare list, which this contract rejects. To be settled in Chunk 5 as a recorded prompt change, so v1 stays unchanged as the baseline for Appendix A.
- **Agreed by:** Tasnim (proposed). Ivan: not yet.

## 2026-10-26: Typed codes in the rule-based linker

- **What:** codes are read as prefix + number (`PBS 03` = `PBS3` = `PBS03`; `M12` is not `HM12`). Two new no-link rules: (A) the ID exists but a same-number, other-prefix sample fits the description better (`M12` vs `HM12`); (B) an unknown but well-formed code of a prefix family the register uses (`OS02` next to `OS01`), or one whose description points to a same-number, other-prefix sample, is not guessed from the description.
- **Why:** safety rule 2. A prefix marks a different test, so a prefix mismatch is conflicting evidence. dev2 went from 2 wrong links to 0.
- **Cost:** dev2 case e11 (`M3`, reference `M02`) is now a missed link instead of correct. Its reference answer contradicts e7 (`OS02`, reference no link), which has the same pattern. Ask Rolf which is right for real reports.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-10-26: Answer format follows the contract; replay answers are tied to the exact prompt

- **What:** `ai/prompts/_output_format.txt` now asks for `{"proposals": [...]}` instead of a bare list. Only the shape changed, not the wording; `v1_baseline.txt` is unchanged. Replayed answers are stored under a key computed from the exact prompt text (`python3 -m ai.james_ai.ai_step prompt <request.json>` shows it).
- **Why:** with the old format every v1 answer broke the contract and became no link. The key makes sure an answer recorded for one prompt version is never reused for another, so each result in Appendix A belongs to the prompt that produced it.
- **Note:** prompt-lab answers recorded in the old list format before this change would be rejected; record them again with the new format.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-10-26: Hybrid pipeline, rules first and AI second

- **What:** high-confidence rule links and rule no-links caused by conflicting evidence (conflict, duplicate, prefix conflict, collision, unregistered code) never go to the AI. All other lines go to the AI in one request. Rules and AI agree: link stays. They disagree: no link. Only the AI links: the AI's proposal. AI answer unusable: the rules' proposal stays. Guard: a sample proposed for two lines unlinks both.
- **Why:** the AI should only work where the rules are unsure, and two sources that disagree are conflicting evidence (safety rule 2). The AI cannot make contradicting evidence agree.
- **Also:** an unknown code of a prefix family the register uses (S-09 next to S-01..S-08) is now always flagged `unregistered`, so the AI never links it either.
- **Status:** no recorded AI answers yet, so the AI and hybrid numbers are not yet meaningful. Fill `ai/replays/dev_v1.json` and `dev2_v1.json` from the prompt lab.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-10-26: An unregistered code gets no link, even if the description matches (e11 changed)

- **What:** the reference answer of dev2 case e11 (`M3 | Gasket, boiler door`) is now `null` instead of `M02`. Rule: a lab code that reads as a proper code (prefix + number) of a prefix family the register uses, but is not in the register, gets no link, even when the description fits a registered sample.
- **Why:** M3 next to M01 and M02 most likely is a sample nobody registered, not a typo for M02. Linking it would hang a result on the wrong sample (safety rule 2). e7 (`OS02`) already had this reference, so the two cases now agree. Supersedes the "Cost" note of the typed-codes entry above.
- **Exception, on purpose:** codes from another numbering system (a lab's own `GS15`, `XY7`) and malformed codes (`S-O3`) can still be matched on the description, at low confidence, because they say nothing about our register.
- **Effect:** dev2 rules 8 / 0 / 2 / 1 (correct / wrong / abstained_ok / abstained_missed), was 8 / 0 / 1 / 2.
- **Agreed by:** Tasnim. Still worth confirming with Rolf for real reports.

## 2026-10-26: Survey location belongs to a survey, not to the object (PROPOSAL for Ivan)

**Status:** proposed by Tasnim, waiting for Ivan. Nothing in `schema.sql` or `store.py` is changed until he agrees.

### The problem
Today `object.site` and `object.project` hold one port and one project per ship. But one ship can be surveyed in Rotterdam in 2026 and in Antwerp in 2027, under two RVL projects, with two sets of samples and lab reports. With one `site` on the object, the second survey overwrites where the first one happened, and the last link of the chain (`... -> object -> survey location`) points to the wrong place for old results.

### The proposal
A new table `survey`: one visit to one object, at one place, in one period, under one project. Samples and lab reports belong to a survey; the object only says *what* it is.

```sql
CREATE TABLE survey (
    id          INTEGER PRIMARY KEY,
    object_id   INTEGER NOT NULL REFERENCES object(id),
    project     TEXT NOT NULL,            -- RVL project code (moves here from object)
    site        TEXT NOT NULL,            -- port, shipyard, quay, road km (moves here from object)
    started_on  TEXT NOT NULL,            -- ISO date of the first survey day
    ended_on    TEXT,                     -- NULL while the survey is open
    inspector   TEXT NOT NULL             -- lead inspector, by name
);

-- object: drop site and project
CREATE TABLE object (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL,
    kind  TEXT NOT NULL,
    ref   TEXT                            -- IMO number, object code
);

-- sample: belongs to a survey; a code is unique within its survey
CREATE TABLE sample (
    survey_id INTEGER NOT NULL REFERENCES survey(id),
    code      TEXT NOT NULL,
    source    TEXT, location TEXT NOT NULL, part TEXT, material TEXT, notes TEXT, photo TEXT,
    PRIMARY KEY (survey_id, code)
);

-- lab_report: belongs to the survey whose samples it analyses
--   object_id INTEGER NOT NULL REFERENCES object(id)   becomes
--   survey_id INTEGER NOT NULL REFERENCES survey(id)
```

`lab_row`, `decision`, `asset_version` and `asset_entry` stay as they are; `asset_version.object_id` stays, because the asset file is the object's history over all surveys. The chain becomes `result -> lab_row -> sample -> survey -> object`, and the survey location is `survey.site` on `survey.started_on`.

### What changes in `store.py` (for Ivan to decide how)
- `add_object(name, kind, ref, site, project, samples)` splits into `add_object(name, kind, ref)` and `add_survey(object_id, project, site, started_on, inspector, samples)`.
- `ingest_report` takes a `survey_id`; the project check in the report header compares with `survey.project`.
- `register(...)` returns the samples of one survey; `draft_report` shows the survey's site and date.
- Existing data: one survey per object, filled from the old `object.site` and `object.project`.

### Questions for Ivan (and Rolf)
1. **Do sample codes restart per survey?** If S-01 in Antwerp 2027 is a new sticker, the key must be `(survey_id, code)` as above, and the asset history cannot follow a sample by code alone across surveys. It would then follow the *place in the object* (source/location) instead. Is that how RVL compares results over time?
2. Can one survey span two places (start in port, finish at the shipyard)? If yes, `site` needs its own small table.
3. Is the RVL project always one survey, or can one project cover several visits?
4. Who is the "inspector" of a survey: the lead only, or everyone who took samples?

### Effect on the AI part (Tasnim)
None on the contract: the app already sends one register per request, which will simply be the register of one survey.

## 2026-10-27: Ivan builds across `ai/`, `james/` and `app/` today (permission from Tasnim)

- **What:** Ivan said Tasnim gave him permission to build her part of the concept on 27 October. Changes outside `app/` were kept small and are listed below, so Tasnim can review and explain them. **Tasnim: please confirm or undo.**
- **Not changed:** the linking rules, the hybrid pipeline, the prompts, the contract (`contract/`), and the scoring. Linking results on `dev`, `dev2` and `hold` are the same as before.
- **Changed in `ai/james_ai/linker.py`:** `Sample` got three optional fields (`deck`, `status`, `restriction`); `LabRow` got `extra`; `parse_report` reads an optional header line `Columns: ...` so a lab table with certificate, method, quantity and remarks keeps them apart. Without that line every report is read exactly as before.
- **Changed in `james/` and `schema.sql`:** the extractor recognises extra column headers and writes the `Columns:` line; `sample` has `deck`, `status`, `restriction`; `lab_row` has `certificate`, `method`, `quantity`, `remarks`; a new append-only `signoff` table. An older database file is upgraded in place. A register with a duplicate code is refused (TC04). A place with status `not sampled` is never offered to the linker and never counts as "missing result"; it is a survey limitation.
- **Changed in `tests/`:** `test_import_answers.py` writes exact bytes, so the Windows line-ending test also passes on Windows. New `tests/test_lab_columns.py`.
- **Agreed by:** Ivan (27 Oct). Tasnim: to confirm.

## 2026-10-27: The app's report follows the layout of a real RVL IHM report

- **What:** the draft sections are now Part I summary (I-1 paints, I-2 equipment, I-3 structure), 2.3 results per substance (sample table + lab table with certificate number and method), 3 survey limitations, 5.1 Table A and Table B, and a sign-off. This replaces "Ch. 9 / Ch. 10", which do not exist in the real report.
- **Why:** the structure was taken from the headings and table columns of one real RVL IHM report (no content read, see `docs/context.md`). Harm's tests (K6, K7, TC05–TC08) measure against that layout.
- **Proposals, not facts:** the Table A/B classification uses `app/thresholds.json`, marked "to confirm by RVL". The Part I list (I-1/I-2/I-3) is chosen from the part and material and is shown as a proposal. A value exactly on a threshold is listed and flagged. A number like "1,400" (thousands or decimals?) is never guessed.
- **Sign-off:** only when every lab line is decided; open items are recorded with the signature; after signing, decisions are locked. A practice report can never be signed or saved to the history.
- **Agreed by:** Ivan (owner of `app/`). Thresholds and the report layout: Rolf or Joris to confirm.

## 2026-10-27 (afternoon): Project and field registration, evidence per report, report on the RVL template

- **What:** the app now starts where RVL's process starts: **create a project** (the Project Information fields of the RVL IHM template) and **register sources and samples** (code, source, deck, location, part, material, colour, photo, drawing position, quantity, unit, status, reason). The code of a registered sample never changes; every addition and change is logged with name and time (`register_log`, append-only). A sample that already has a linked result cannot become "not sampled".
- **Evidence per report:** source file name, SHA-256 fingerprint, how it was read (PDF text layer, OCR, pasted), a fingerprint of the linker code and the prompt version used by the AI step. When the field registration changes after a report was read, the report says it is out of date until "Let the agent read again".
- **Report layout:** follows RVL's empty IHM template (`docs/context.md`): Project Information, Part I lists with their own columns, 2.3.1–2.3.7 with a Source Record per source, 3 limitations, Table 15 (A) and Table 16 (B) with the template's fixed lines. Quantities per line are added up from the field registration only when every source has a number in the same unit; otherwise the inspector fills them in. Signing is done as Technical Responsible Person and sets Report Status to Final.
- **Thresholds changed to follow the template:** lead 100 mg/kg (was 1000), HBCDD in Table B, PFOS without a table ("?", inspector decides). Still to confirm by RVL.
- **Not changed:** the contract, the linking rules, the AI step. The survey location and date stay on the object for now; the survey-table proposal is still open.
- **Agreed by:** Ivan (27 Oct). Tasnim: the changes in `ai/james_ai/linker.py` are only extra optional fields on `Sample`.

## 2026-10-27 (late afternoon): Export into RVL's IHM template

- **What:** "Download IHM report (.odt)" fills RVL's own IHM template with the approved lines of one lab report: Project Information, Part I lists (a row per item), 2.3.1–2.3.7 (sample table, a Source Record per source, lab table, photo references), survey limitations, and the fixed lines of Table 15/16 with quantity and unit. Every placeholder is filled; what the app does not know becomes "–". An unsigned report says Draft; a practice report cannot be exported.
- **Why:** RVL delivers a document in its own template. Copying tables by hand was the biggest gap for a surveyor.
- **The template is not in the repository.** It is RVL's property (onboarding: templates only with permission). The app reads it from `context/IHM 26-.odt` or from the path in the environment variable `JAMES_IHM_TEMPLATE`. The tests use a small home-made template with the same patterns, plus one test on the real template when it is present.
- **Not filled by the app:** consultation (2.2), desk research, the VSCP (appendix E) and the photos themselves. Those stay for the surveyor.
- **Agreed by:** Ivan (27 Oct).

## 2026-11-02: Chromium-6 codes keep the 6 in their prefix

- **What:** `code_parts` in `ai/james_ai/linker.py` checks a short list of prefixes that end in a digit (`CR6`, `CH6`) before the general "letters, then digits" rule. `CR601`, `CR6-01` and `CR6 01` now all read as prefix `CR6`, number 1. `CR601` and `CH601` stay different codes.
- **Why:** the IHM template writes chromium-6 codes as `CR600`, without a separator. The old rule read `CR601` as prefix `CR` + number 601, so a register entry `CR6-01` and a lab line `CR601` were seen as two different codes: a missed link, not a wrong one. Found while checking the sample code list for Rolf.
- **Effect:** `dev` and `dev2` scores unchanged (no test case uses a code without a separator yet). 130 tests pass. Reports read before this change show "older than the current linker" in the app until read again.
- **Still open:** which notation RVL really uses (`CR600` or `CH6-nn`, `MM00` or `M00`): question 1 for Rolf. Test cases with `CR6` and `TBT` codes follow after his answer.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-11-06: RVL's standard sample codes, with an alias table for older notations

- **What:** James uses the IHM abbreviations as standard prefixes, written like `MM-1` and `CR6-1` (Rolf, 6 Nov 2026). The linker already treats `MM-1`, `MM01` and `MM1` as one code. New: an alias table in `ai/james_ai/linker.py` maps older notations to the standard prefix: `CH6` → `CR6`, `PAC` → `PAH`, `M` → `MM`. A link found only through an alias gets at most **medium** confidence, and the reason names the older notation ("CH6 is an older notation for CR6"). The rule that an unregistered code is never guessed also reads aliases, so `M3` next to `MM-1`, `MM-2` gets no link.
- **Why:** Rolf asked that existing codes stay recognisable. Without the alias table `CH6-01` and `CR6-1` were seen as different codes: a missed link that costs the inspector time. Medium, not high, because a different notation is weaker evidence than an exact code.
- **Not mapped:** `ZM` (meaning unknown, question 15). Aliases never join different tests: `M` (asbestos) never becomes `HM` (heavy metals).
- **Supersedes:** the 2 Nov test that `CR601` and `CH601` are different keys still holds for `id_key`; the alias match is a separate, weaker step.
- **New test set `dev3`:** 10 lines on a register in the standard notation (no separator, old notation, unregistered TBT-2, a CR6/HM prefix conflict, a lab's own code, no ID). Reference answers were written before running the rules. Rules: 8 correct, 0 wrong, 2 abstained OK, 0 missed. `dev` and `dev2` unchanged.
- **Agreed by:** Tasnim (owner of `ai/`). Code standard: Rolf.

## 2026-11-06: Optional Groq client for fictional-data evaluation

- **What:** added `ai/james_ai/client_groq.py` implementing the existing `complete(text) -> str` client interface. `JAMES_AI_PROVIDER=groq` opts the app into Groq; replay remains the default. The key is read from `GROQ_API_KEY`, never a project file. The client requests strict structured JSON, validates it through the existing contract after return, uses a timeout, and logs model/prompt fingerprint/token usage/estimated cost without logging prompt text. AI-only links cannot claim high confidence; the hybrid caps these at medium.
- **Why:** connect the existing proposal workflow to a live model in a controlled way and compare two current Groq models on the same fictional cases before choosing by quality/cost.
- **Model plan:** `openai/gpt-oss-20b` is the lower-cost starting candidate; `openai/gpt-oss-120b` is the quality challenger. Groq's listed rates and the task-specific evaluation plan are in `docs/groq-model-selection.md`.
- **Safety/status:** fictional data only until RVL and the coach approve provider and data scope. No Groq call or model result has yet been recorded in this repository. Rolf's approval of the sample-code conventions does not imply approval to send reports to Groq.
- **Agreed by:** Tasnim (requested the integration). Real-report data approval: not recorded.

## 2026-11-09: Two equal candidates never go to the AI; Groq retries once on a rate limit

- **What:** in `ai/james_ai/hybrid.py`, `ambiguous` (two register samples fit the description equally) joins the conflict flags: the line stays "no link" and is not sent to the AI. In `ai/james_ai/client_groq.py`, an HTTP 429 (tokens per minute used up) waits as long as Groq's `retry-after` says, at most 30 seconds, and tries once more.
- **Why:** the first working Groq run (dev, `openai/gpt-oss-20b`, prompt v1) linked case d11 `- | Gasket` to S-03 while S-03 and S-06 fit equally; the hybrid passed it on as a wrong link (hybrid 9 correct, 1 wrong). Two equal candidates is conflicting evidence (safety rule 2): the model can only guess a side. Case d12 in the same run got no AI answer because of the free-tier limit (8,000 tokens per minute).
- **Effect:** with the same AI answers, d11 becomes "no link" (abstained OK), so the hybrid would be 9 correct, 0 wrong on dev. To confirm with a new run. The run of 8 Nov stays in `ai/runs/` as the evidence for this change.
- **Also:** the Groq organisation ID in provider error messages is now redacted like the key, so it never ends up in saved runs.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-11-14: Two-table lab layout in the extractor; test set dev4

- **What:** `james/extract.py` reads the Dutch two-table lab layout (overview table: lab ID → our code and place; results tables: lab ID → values), joined on the lab ID. Output: `code | place | result | method | remarks`, with the lab ID in remarks. A result whose lab ID is not in the overview gets no code; a lab remark letter (such as C) stays with the result; a report that replaces an older version says so. Without this layout the old reader runs unchanged. Tasnim agreed to the change in Ivan's file.
- **Data:** only the table structure is used; all codes, places and values in the code, tests and test data are invented.
- **New set `dev4`:** 12 invented lines on an invented structure in that layout; `python3 -m ai.james_ai.make_lab_pdf --set dev4 --out dev4_lab.pdf` builds a PDF of it for the app. Reference answers written before running.
- **Provisional answers:** g5 (`ZM-03`) and g6 (`PCB-01`) are "no link" until Rolf says what `ZM` and `PCB` map to. Change them only with a new entry here.
- **Effect:** dev4 rules 7 / 1 / 3 / 1. The wrong link is g9: code `CR6-2` exists and the place fits, but the result is a heavy-metals panel; the rules do not read the result.
- **First AI run (14 Nov, Groq `openai/gpt-oss-20b`, prompt v1):** AI only 7 / 4 / 1 / 0, hybrid 6 / 2 / 2 / 2, worse than the rules alone. The hybrid's extra wrong link is g6 (`PCB-01` → SS-1, only the AI proposed it); g2 became no link because rules and AI disagreed. The AI did solve g12 by reading the result, but the hybrid keeps that line from the AI. Two of the AI's four wrong links (g5, g6) depend on the provisional answers above.
- **Agreed by:** Tasnim (owner of `ai/`).

## 2026-11-16: ZM is the older notation for HM; full RVL code list in prompt v3

- **What:** the alias table in `ai/james_ai/linker.py` maps `ZM` → `HM` (like `CH6` → `CR6`, `PAC` → `PAH`, `M` → `MM`): a match through it is at most medium confidence and the reason names the older notation. dev4 case g5 (`ZM-03`) now has reference HM-3 instead of the provisional "no link". Prompt v3 (not yet measured) gets `ZM = HM` and the full list of RVL test prefixes.
- **Why:** RVL's sample code list (IHM template and Rolf's note) says existing codes such as CH6-01, ZM-01 and Pac-01 must remain recognisable; ZM stands for *zware metalen* (heavy metals). The full code list: MM, KM, PBS, SS, OS, ODS, PFOS, HBCDD, HM (template key) and TBT, PAH, PFAS, CR6, NORM, TPH, VOC (additional codes), plus VI, DR, EI for observations without a lab sample.
- **Effect:** dev4 rules 8 / 1 / 2 / 1 (was 7 / 1 / 3 / 1 with the old reference for g5).
- **Still open (Rolf):** `PCB-01` on a lab line is not an RVL code (PCB is PBS, SS or OS); g6 stays "no link". `M00` and `V00` are "to check" in RVL's list (`M` is already read as `MM`; `V` is not mapped).
- **Agreed by:** Tasnim (owner of `ai/`), based on Rolf's code list.

## 2026-11-16: Fixes in `app/` (made at Tasnim's request, for Ivan to review)

Found while testing the full flow with the fictional set dev5 (upload, approve, export).
- **Decided lines fold away** (`app/static/index.html`): after Approve, Link here or Reject the buttons disappear and the card shows who decided what. "Change decision" brings them back; the new decision is added to the log, the old one stays (append-only).
- **Cover page filled** (`app/export_odt.py`): the cover table had labels with empty cells and no placeholders; project number, location, survey period, client and internal authorisation ("Draft: not yet authorised" until signed) are now written in.
- **Header and footer filled**: `<26>`, `<Vessel>` and `<Type>` sit in `styles.xml`, which was not filled before.
- **Section 2.3.8 "Other substances"**: the template has no section for PAH, TBT and other substances outside 2.3.1–2.3.7, so approved PAH results disappeared from the report. When such results exist, section 2.3.7 is copied once as 2.3.8 (bookmarks dropped, table names made unique). Question for Rolf: where should PAH go in an RVL report?
- **Zinc is no longer reported as chromium-6** (`app/ihm.py`): a result that names its own substance with a symbol ("Zink (Zn)") that James does not know becomes "Unknown substance, inspector classifies", instead of taking the substance from the sample code. Dutch names Lood, Chroom-6 and Kwik are recognised.
- **Not changed, for RVL:** the template's placeholder cover photo, the PCB health text that stops at "include damage to", and the ship wording ("Vessel", "on board") for structures. These are in RVL's template, not in the code.
- **Restart with a database file** (`app/server.py`): with `--db`, every start added another copy of the demo ship, and switching to a project whose report was read before the restart crashed (proposals are kept in memory only). Now the existing demo ship is reused, and a report without proposals in memory is read again when opened (`run_for`); the inspector's decisions are in the database and stay. A practice report is also recognised by its label after a restart, so it can still never be signed, exported or saved to the history.
- **Project summary** (`app/export_odt.py`): a paragraph under 'Summary' and the 'Survey Findings' line are written from the project's own data: object, project number, survey location and period, how many lab lines were approved, rejected or still open, and per substance which samples were above, below or still to classify. Only facts from the app; RVL's standard summary text follows unchanged.
- **PAH (PAK) recognised** (`app/ihm.py`, `app/thresholds.json`): read from the result instead of 'Unknown substance', reported in 2.3.8. PAH is not in IHM Table A or B, so the app never lists it in Part I or the tables: below the detection limit is reported as such, a measured value is left to the inspector. To confirm by RVL.
- **Tests:** app 59 (was 55), tests 153; all pass.
- **Agreed by:** Tasnim (asked for the changes). Ivan: to review.

## 2026-11-17: Redesign of the app's screens (made at Tasnim's request, for Ivan to review)

- **What:** `app/static/index.html` and the login page in `app/auth.py` get one design system: colour, type, spacing and radius tokens (with a dark mode), one font family, a fixed top bar (product, project switcher, inspector), a page header, a compact stepper, panels with a single title, a clear button order (primary, secondary, ghost, danger), labelled form fields, visible keyboard focus, a progress bar while the server works, toasts, and empty and error states (including "James could not be reached").
- **Wording:** "IMO number", "Ship type · flag" and "Ship" became "Object code", "Type" and "Object" (structures too); the banner "no real AI is running yet" (no longer true with Groq) became "Concept prototype · fictitious data only · the agent proposes, the inspector decides".
- **Not changed:** every API call, element ID and data attribute the script uses, so no behaviour changed. Fixed on the way: the New-project buttons were wired twice; a function named `history` clashed with the browser's `window.history`.
- **Checked:** the page was driven end to end against the running app (new project, register sample, upload dev5, approve, change decision, switch project, dialogs, export): 15 of 15 checks pass, no script errors. Not checked by eye in a real browser yet.
- **Agreed by:** Tasnim (asked for it). Ivan: to review.

## 2026-11-18: Separate pages, and the open project kept per browser tab (made at Tasnim's request, for Ivan to review)

- **Why:** client feedback of 17 Nov: "Clicking a project or a section only makes the page jump to the top" and "Everything is mixed together; I want separate pages or tabs."
- **What, screen** (`app/static/index.html`):
  - A hash router in plain JavaScript, no dependency. The address is `#/projects` or `#/p/<project>/<page>`, with `/<report>` added on `lab` and `report`. An unknown address goes to `#/projects`.
  - Pages in the order of Rolf's work: Dashboard, Upload, Intake, Desk research, Fieldwork, Lab results, Bronbladen, Report.
    - Upload, Desk research and Bronbladen are placeholders.
    - The Dashboard has one status card per step, with the object history and audit log folded.
    - Intake is the New-project fields, editable as a page; the dialog stays for creating a project.
  - A fixed top bar and tab bar. The Lab results tab has a badge with the undecided lines over all reports of the project.
  - Changing page scrolls to the top on purpose. An action on a page redraws only that page (and the tabs). It keeps the scroll position (a decided line stays where it was), the focused field, and unsent form text, also across tab switches.
  - The existing builders (`registration`, `screen`, `reportCard`, `prop`, `historyTable`) moved, not rewritten. `screen` no longer holds the report card, history and audit log.
- **What, server** (`app/server.py`):
  - `GET /api/state` takes `?object=&report=`. Every POST reads `object` from its body.
  - `Service` methods take the project id; `Service.object_id` stays only as a fallback for old callers and the tests.
  - Sign, export, save-history, decide and reread take the project from the report itself.
  - `view` never shows a report of another project, and adds `open_lines` and `object.info`.
  - New `POST /api/project-update`. `/api/select-project` still works but the screen no longer uses it.
- **What, store** (`james/store.py`, Ivan's to keep; Tasnim agreed):
  - New `update_object`, which changes the project details and logs old -> new in `register_log` under the code `(project)`.
  - `register_changed_at` skips that code, so a project-detail change does not mark lab reports out of date.
- **Demo page:** `app/demo/mock_api.js` follows the same parameters. `app/demo/james-lab-agent.html` was **not** rebuilt; run `python3 app/demo/build_artifact.py` to rebuild it.
- **Tests:** `app/test_app.py` gets `PerProjectState` (7) and `TwoWindowsOverHttp` (1). The browser checks in `docs/manual-tests.md` were run by script in local headless Chrome on 18 Nov (demo data only): 36 of 36 pass. Look and feel, the real download and login mode are left for a person.
- **Fixed on the way:** at 768 px the Fieldwork page scrolled sideways, because the hidden "Missing" and "Edit" column labels (`.sr-only`, absolutely positioned) escaped the table's scroll box. The fix is `.tscroll { position: relative }` in `app/static/index.html`. The bug was already in the old single page.
- **Agreed by:** Tasnim (asked for it). Ivan: to review.

## 2026-11-18: Fieldwork split into substance-group tabs, one mapping for tool and report (made at Tasnim's request, for Ivan to review)

- **Why:** client feedback of 17 Nov: "In fieldwork the substance groups must be separate: asbestos, PCBs, heavy metals."
- **One mapping** (`app/ihm.py`):
  - `PREFIX_GROUP` maps each standard prefix to a group, a substance key and its meaning. `GROUPS` gives the tab order, label and main prefix.
  - `group_for_code()` parses the code with the linker's own `code_parts` and `std_prefix`, so ZM→HM, M→MM, PAC→PAH and CH6→CR6 come from the one alias table.
  - The section comes from `section_2_3()`, the same function the export uses. A test proves that every demo sample's tab section equals the section it is exported under.
  - `PREFIX_HINT` and `_code_hint` are unchanged: an HM code still never makes `findings()` guess lead from a result without a substance name.
- **Groups:**

  | Tab | Section | Codes |
  |---|---|---|
  | Asbestos | 2.3.1 | MM, KM, M |
  | PCB | 2.3.2 | PBS, SS, OS |
  | Heavy metals | 2.3.6 | HM, ZM, CR6, CH6 |
  | ODS | 2.3.3 | ODS |
  | PFOS / PFAS | 2.3.4 | PFOS, PFAS |
  | HBCDD | 2.3.5 | HBCDD |
  | Radioactive | 2.3.7 | NORM |
  | Other | 2.3.x | PAH, PAC, TBT, TPH, VOC; and VI, V, DR, EI (assessments without a lab sample) |

- **Rule for Other:**
  - A code listed with a known meaning goes to Other without a warning.
  - A code that is **not** recognised (for example the typo MI02) goes to Other **with** an "unknown code" warning. The warning shows on every Fieldwork tab and on the Dashboard, so a typo cannot silently disappear from its substance group.
- **PFAS** shares the PFOS tab, labelled "PFOS / PFAS", so nobody reads a PFAS result as PFOS. It is exported under 2.3.4, the only section the template has, and the record keeps the code PFAS-x. This is a one-line change in `PREFIX_GROUP`. Question 17 for Rolf.
- **View** (`app/server.py`): each register entry gets `group`. The view gets `groups` with section, count, unknown count and `next_code`, in the project's own style (M03 after M02, MM-6 after MM-5; an empty group starts with RVL's `MM-1`).
- **Screen** (`app/static/index.html`):
  - Group tabs with counts. Asbestos, PCB and Heavy metals are always shown; the others show when they hold samples or are opened with "Add group" (this browser tab only, nothing saved).
  - "Add sample" pre-fills the next code. After saving, the tab of the saved sample opens.
  - One register underneath; the tabs are only views. No migration.
- **Demo page:** `app/demo/mock_api.js` has a copy of the table, because it stands in for the server, marked "keep in step with ihm.PREFIX_GROUP". The screen keeps no copy.
- **Tests:** new `app/test_groups.py` (14). Browser checks in local headless Chrome, demo data and fictional codes only: 11 of 11 pass (see `docs/manual-tests.md`).
- **Open (Rolf):** question 17 (PFAS under 2.3.4?) and 18 (M00 or MM00 for new samples; both are supported).
- **Agreed by:** Tasnim (asked for it). Ivan: to review.

## 2026-11-18: Bronbladen get their own data (sources, photos, condition) and AI proposals are saved (made at Tasnim's request, for Ivan to review)

- **Why:** a bronblad ties together source, samples, certificate, location, material, condition, results, quantity, conclusion and photos. Rolf: if photo, sample and certificate are not linked correctly, the report is unusable. The AI proposals also lived only in memory, so a restart called Groq again.
- **Database** (`schema.sql` for new files, `Store._upgrade` for old ones; additive only, nothing deleted):
  - New table `source`: one row per source number. The link stays `sample.source = source.source_no`. Fields: substance group, description, condition, quantity, unit, assessment (confirmed / not hazardous / PCHM / not accessible), conclusion, drawing, updated_by and updated_at.
  - New table `photo`: one row per photo number, with file fields that stay empty until P4 (`stored_name` NULL means "photo missing"). Unique per project by `photo_no` and by `sha256`.
  - `lab_row` gets `ai_code`, `ai_confidence`, `ai_reason`, `ai_source`, `ai_prompt_version` and `ai_sent`. `ai_sent` was added on top of the request, so "sent to the AI" and the AI note stay right after a restart.
- **Upgrade of an old file:**
  - Old files get the same `CREATE TABLE` text, read from `schema.sql`, not a copy.
  - The source and photo rows are filled **once**, when the tables are first created: one source per distinct `sample.source`, with quantity and unit from its first sample; one file-less photo row per non-empty `sample.photo`.
  - Opening the file again changes nothing, and a photo unlinked later is never recreated.
  - Deck stays on the sample (agreed).
  - Checked: a file made by the previous version opens, upgrades, keeps its decisions, and every page of both projects renders (22 browser checks).
- **Logging (rule 5):** every source and photo add, change, link and unlink goes into `register_log` with who and when, with an action starting `source ` or `photo `. They are kept out of the Fieldwork log on screen (they belong on the bronbladen page) and stay in the database.
- **Out of date:** `register_changed_at` skips source and photo actions, so a condition or photo row change does not mark lab proposals out of date. **Confirmed by test:** changing a sample's own source number or location still marks them out of date, exactly as before.
- **AI proposals:** `Service.read` saves the hybrid result per line. After a restart, `run_for` rebuilds the run from the database without calling the AI (test with a client that fails when called). Reports read before this change are read once more, then saved. `/api/reread` still forces a fresh run. The practice review saves its seeded proposals.
- **Condition:**
  - The values live in `app/conditions.json`: Good, Damaged, Weathered, Unknown, marked "to confirm with Rolf".
  - Condition is stored on the source, not the sample.
  - In the register form it is disabled until a source number is filled in, with the hint "Enter a source number first". The server refuses it too ("a condition belongs to a source: enter the source number first").
- **Export and view:** the Source Record reads description, condition, quantity and conclusion from the source table first, and falls back to the sample-based values as before. The export copies the template's "Source Description" row once as a "Condition" row.
  - Test: the demo export with sources equals the old fallback export apart from the Condition rows.
  - Not checked against RVL's real template: if its label cell is formatted differently, the copied row may keep the label "Source Description".
- **Demo:** MV Noorderlicht has 10 sources (B01–B10) over asbestos, PCB, ODS and heavy metals, with conditions. B10 (MM-5, no access behind a welded panel) is assessment PCHM. The descriptions are the old fallback text, so the demo report only gains the Condition line.
- **Not done (agreed):** deleting a sample. It is not needed now.
- **For P4 (photo upload):** P4 retires the `sample.photo` text field as the place where photos are recorded. An uploaded file is matched to an existing file-less photo row by `photo_no` (and refused as a duplicate by `sha256`), so the upgrade's rows are filled in rather than duplicated.
- **Demo page:** `app/demo/mock_api.js` accepts a condition per source. Its built-in demo has no conditions until `app/demo/build_artifact.py` is run again.
- **Tests:** new `tests/test_sources.py` (11); `app/test_app.py` +5 (saved proposals, condition); `app/test_export.py` +1 (Condition only).
- **Agreed by:** Tasnim (asked for it). Ivan: to review.

## 2026-11-19: Photo upload, numbering, proposed links and the link check (made at Tasnim's request, for Ivan to review)

- **Why:** Rolf: "Photos must get a number and description and correspond to the right sample and analysis certificate. The user must be able to check and correct that."
- **Server** (`app/server.py`):
  - `ThreadingHTTPServer`: one slow upload no longer blocks other windows.
  - SQLite keeps **one shared connection** (`check_same_thread=False`), with **one lock** (`Service.lock`) around every database call. Reading an upload and resizing a photo happen outside the lock.
  - Not one connection per request, because an in-memory database would be empty on every new connection, and the proposals cache lives in `Service`.
- **Limits:** every POST is refused **before the body is read** when `Content-Length` is missing (411) or too large (413).
  - JSON: 25 MB.
  - Photo: `JAMES_MAX_PHOTO_MB`, default 15.
  - The PDF limit went from 20 to **18 MB**, because a PDF travels as base64 inside JSON (+33%).
- **Storage** (`app/photos.py`):
  - Files go under `JAMES_DATA_DIR` (default: the folder of the database file; `./data` when the database is in memory), in `photos/<object>/<sha256>.jpg` with `thumbs/`.
  - Never under `app/static`. The name is generated from the sha256, never taken from the user. `/data/` and `/photos/` are in `.gitignore`.
- **Upload:** `POST /api/photo?object=&name=` with the raw image as body (no base64).
  - Magic bytes (JPEG, PNG) are checked first. HEIC and other types get "please export it as JPG".
  - The image is opened with Pillow, turned upright from EXIF orientation, and saved as a **new JPEG** with a 400 px thumbnail.
  - **Re-encoding removes all EXIF data, including the GPS position phones store in photos.**
  - Very large pixel counts ("decompression bombs") are refused.
  - The same file twice in one project (same sha256) is skipped with a message.
  - The browser sends files one at a time, with "7 of 20" progress.
- **Serving:** `GET /api/photo/<id>[/thumb]?object=` needs a login when login is on. The photo's project is looked up in the database and must equal the `object` in the request; otherwise 404.
- **Numbering:** new numbers continue the project's own format, in one function (`photos.next_photo_no`): F-013 after F-012, or 1, 2, 3 for a project without numbers.
  - An upload whose file name carries the number of a row without a file (e.g. "MM-1 F-012 pipe.jpg") fills that row, so there are no duplicates (the P3 promise).
  - Numbers are editable and stay unique per project.
- **Proposed link:** rules only, no AI. A sample code (`M01`, `PBS-03`, `hm12_2`) or source code (`B4`) in the file name, read with the linker's own `alias_key` (the same code reader as P2).
  - Two different samples in one name: no proposal, and the reason says so.
  - Proposals are stored separately (`photo.proposed_sample`, `proposed_source`, `proposal_reason`). "Accept all proposals" applies them in one click.
  - Linking fills an empty description with "<location> - <material, part>".
- **`sample.photo` retired** (as planned in P3): the Photo text field left the register form. Photo columns, checks, the chain and the export use photos with a file from the `photo` table. The database column stays (no migration).
- **Link check** (`Service.link_check`, in the view JSON as `link_check`): one list for the Bronbladen page, the sign-off open items and the export. Every line has a Fix target that opens the exact place.

  | Rule | Kind |
  |---|---|
  | Photo not linked | error |
  | Source without photo | error |
  | Source with more than 4 photos | error |
  | Sample without source | error |
  | Sample without approved lab result | error |
  | Approved result without certificate number | error |
  | Lab line code not in the register | error |
  | Same sample twice (M-3 and MM-3) | error |
  | Codes that differ by one prefix letter with the same number (MM-12/HM-12, OS-1/ODS-1) | warning |

  - The prefix warning can be **marked as checked** (logged with name and time), because codes never change. It only fires for prefixes one letter apart, since RVL numbers every prefix from 1.
  - **Added to make two fixes possible:**
    - A certificate number can be typed on a lab line that has **none** (logged; the lab's own number is never overwritten).
    - Registering `M-3` next to `MM-3` is now refused.
  - An existing M-3/MM-3 pair from older data can only be resolved with a merge or delete, which is parked.
  - All "photo", "check" and "lab certificate" log lines are kept out of the Fieldwork log and never mark lab proposals out of date.
- **Other:**
  - `requirements.txt` (pdfplumber, pillow, jsonschema, pinned) and `requirements-dev.txt` (+ reportlab for tests). `start_james.bat` installs from `requirements.txt` and carries on when offline.
  - New `app/demo/make_demo_photos.py` makes 19 fictional images; 17 link automatically. They include one sideways image with an EXIF rotate tag, one PNG and the typo MI02.
  - `mock_api.js` answers the photo routes with "needs the app".
  - The Upload placeholder now points to Fieldwork for photos.
- **Hosting:** the repo still describes Render (`docs/hosting.md`); Scaleway (H1) is not in the repo yet. Set `JAMES_DATA_DIR` on the data volume there.
- **Tests:** new `app/test_photos.py` (23) and `app/test_linkcheck.py` (11).
  - The photo tests include: 40 MB refused before reading, a missing Content-Length, a stalled upload not blocking another window, and the serve route refusing a wrong project and a missing login.
  - The link-check tests produce every rule and check it disappears after its fix.
  - Browser checks in local headless Chrome, demo data only: 13 of 13.
- **Agreed by:** Tasnim (asked for it). Ivan: to review.
