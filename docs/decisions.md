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
