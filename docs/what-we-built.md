# What we built

Three lines per item: what it does, why it exists, one example.

## 1. Answer importer (`python3 -m ai.james_ai.import_answers <file>`)
- **What:** reads prompt + answer pairs pasted from the prompt lab and files each answer under the exact prompt in `ai/replays/*.json`; a new prompt wording becomes a new version in `ai/prompts/vN_imported.txt`.
- **Why:** copying answers by hand into JSON is slow and error-prone, and an answer must never end up under the wrong prompt or replace an earlier one unnoticed.
- **Example:** paste `=== PROMPT` + the d2 prompt + `=== ANSWER` + the reply into `answers.txt`; the command prints `FILLED dev_v1.json d2`, and pasting a different reply later prints `CONFLICT ... kept it (use --replace to overwrite)`.

## 2. Rule: an unregistered code gets no link (case e11)
- **What:** dev2 case e11 (`M3`) now has reference "no link", and tests pin that the rules give no link for it and no wrong links on dev and dev2.
- **Why:** e11 and e7 had the same pattern but opposite reference answers; a code that is not in the register must not be hung on another sample just because the text fits.
- **Example:** `M3 | Gasket, boiler door` gives no link with "The register uses M codes, so this looks like a sample that was not registered." The description hint M02 is shown to the inspector, not proposed.

## 3. Proposal: survey location belongs to a survey (Chunk 7, for Ivan)
- **What:** a written proposal in `docs/decisions.md` for a `survey` table (project, site, dates, inspector) that samples and lab reports belong to, with the table changes and the effect on `store.py`, plus four open questions.
- **Why:** one ship can be surveyed in Rotterdam and later in Antwerp; with one site on the object, the second survey overwrites where the first results came from.
- **Example:** MV Demo Star, survey 1 at Quay 12 Demo Harbour in 2026 (S-01..S-08) and survey 2 at a shipyard in 2027: each result keeps the place and date of the survey it came from.

## 4. Iteration log for Appendix A (`python3 -m ai.james_ai.iteration_log`)
- **What:** rebuilds `docs/iteration-log.md` from every saved run in `ai/runs/` and every prompt in `ai/prompts/`: per prompt version the change note, the full prompt, a results table, and the wrong and missed cases with reasons. `score` and `compare` got `--save`, and `ai/runs/` is now kept in git.
- **Why:** graders want visible, reproducible iteration; numbers typed by hand into a report can drift from what was really measured.
- **Example:** the v1_baseline section shows dev2 hybrid 8 / 0 / 2 / 1 with AI answers 0/11 at commit 713da6b, and lists e3 as missed with "M12 and HM12 differ only by prefix".

## 5. Interactive demo (`python3 run_demo.py --flow`)
- **What:** runs the hybrid on the fictional ship with stand-in AI answers, shows each line's proposal, source (rules, both, disagree) and reason, and lets a typed, named inspector approve, correct, reject or skip from the keyboard; then prints the draft report and the audit log. Plain `python3 run_demo.py` is unchanged.
- **Why:** it shows the whole chain and the one rule that matters (nothing is final without a named inspector) in a few minutes, for Rolf, Ivan or the interview.
- **Example:** line 8 (`- | Pump packing, pump room`): rules say S-08, the stand-in AI says no link, so the proposal is NO LINK; `a` is refused, `c` + `S-08` + a note is recorded as "corrected" under the inspector's name.

## 6. Lab tables with extra columns (27 Oct, Ivan, see `docs/decisions.md`)
- **What:** a lab report may start its table with `Columns: Sample No. | Description | Analysis | Result | Certificate`; the linker and the PDF extractor keep certificate number, method, quantity and remarks apart. Without that line nothing changes.
- **Why:** a real IHM report lists certificate number and method per result, and Harm's K1 and K7 measure them.
- **Example:** `HM01 | Railing paint | Heavy metals | Lead 1400 mg/kg |` has an empty certificate, so the app flags "No certificate number on this lab line".

## 7. Places that could not be sampled (27 Oct)
- **What:** a register entry can have status `not sampled` with a reason. It is never offered to the linker, it is not a "missing result", and it goes to section 3 "Survey limitations" as potentially hazardous (PCHM).
- **Why:** test case TC08: an inaccessible place must never be reported as "no hazardous material".
- **Example:** M05, pipe insulation in a void behind a welded panel: a lab line `M05 | ... | Chrysotile 5%` gets no link, and the report says "Treat as potentially containing hazardous materials until sampled".

## 8. IHM reading and the report layout (27 Oct, `app/ihm.py`)
- **What:** each approved result is split per substance and compared with `app/thresholds.json` (to confirm by RVL); the report shows Part I I-1/I-2/I-3, 2.3 per substance, 3 limitations and 5.1 Table A/B, and can be signed once every line is decided.
- **Why:** the app's report must look like what RVL hands to a class society, and Harm's K6 and TC05/TC06 measure it.
- **Example:** `Lead 1000 mg/kg` is exactly on the threshold, so it is listed in Table B and flagged "inspector confirms"; `Lead 1,400 mg/kg` is not guessed (1400 or 1.4?).

## 9. Practice review (27 Oct)
- **What:** loads the demo report with 5 deliberately wrong links that look like normal proposals; when every line is decided it shows how many the reviewer caught.
- **Why:** Harm's TC12 / K10 measures automation bias: a review step only helps when the human really checks.
- **Example:** someone who approves everything scores 0 of 5; someone who compares the lab ID with the proposed sample scores 5 of 5.

## 10. Project and field registration (27 Oct, afternoon)
- **What:** "New project" with the Project Information of the RVL template, and a form to register each source and sample (deck, location, part, material, photo, drawing position, quantity, unit, status). Every change is logged; codes never change.
- **Why:** RVL's first success criterion starts "from project creation and field registration"; the register used to be fixed demo data.
- **Example:** register `HM01 | Railing | Paint layer | 20 m2`, paste a lab line `HM01 | Railing paint | Heavy metals | Lead 250 mg/kg | C-2`, approve and sign: Table 16 shows "B3 Lead – Paint · 20 · m2".

## 11. Evidence kept with every report (27 Oct, afternoon)
- **What:** file name, SHA-256 fingerprint, read method, linker fingerprint and prompt version are stored with each lab report and shown under it.
- **Why:** the onboarding asks to keep "source file reference, extracted fields, match logic, warnings, human corrections, approver and version".
- **Example:** after the linker code changes, an old report shows "older than the current linker", so nobody mistakes old proposals for new ones.

## 12. Export into RVL's IHM template (27 Oct, late afternoon, `app/export_odt.py`)
- **What:** one button fills RVL's IHM template (.odt, opens in Word and LibreOffice) with the approved results: Part I lists, Source Records per source, lab tables, limitations and Table 15/16.
- **Why:** a surveyor delivers a document in RVL's template, not a web page.
- **Example:** the demo report signed by "B. Reviewer" gives `IHM_J-26-014_final.odt` with "A-2 Polychlorinated Biphenyls (PCB) | 35 | kg" and "A-1 Asbestos | to be filled in", because M01 is in metres and M03 in pieces.
