# Problem analysis and advice

James · AI-assisted linking of lab results for RVL Asbest · Version 2 · 17 November 2026

**Status:** working document for the coach and RVL. Based on what is built and measured in the repository up to 17 November 2026. Items marked *to confirm* need RVL. All test data is fictional.

## 1. Summary

RVL inspectors spend a large part of every survey copying lab results into the right place of an IHM report. The lab uses its own sample numbers and layouts, so every result has to be matched by hand to the sample, source and location registered in the field. James supports that step: it reads the lab report, proposes a link for each result, and lets a named inspector approve, correct or reject it before a draft report is filled in RVL's own template.

The prototype now covers the whole flow from project creation to a downloadable IHM report. Measured on 55 fictional test lines, the rule-based linker makes 1 wrong link (40 correct, 10 correct "no link", 4 missed). Adding an AI model (Groq, gpt-oss-20b) has not yet improved on the rules: with the first prompt it made 2 wrong links instead of 1; with the second prompt it made 1 but missed more correct links. **Advice:** keep the rules as the dependable core, keep the AI as a gated assistant for unclear lines only, and fix the one known rule gap (a result that does not fit the type of test in the sample code) before any pilot.

## 2. Context

RVL Asbest is a small certified inspection firm (asbestos, chromium-6, HazMat and IHM) working on ships and structures. Since the Hong Kong Convention entered into force on 26 June 2025, ships of 500 GT and more need an Inventory of Hazardous Materials (IHM); existing ships must have one by 2030. Demand grows while the team stays small, so time per survey and the quality of the data matter.

RVL's own success criteria for the prototype (onboarding, 9 September 2026):

1. A working prototype shows the essential flow from project creation and field registration to linked lab results and a draft report.
2. Sources, samples, photos, drawings and locations stay consistently linked, and missing information is flagged.
3. Inspectors can review, correct and approve AI-supported output; uncertainty and responsibilities are visible.

## 3. Stakeholders

| Stakeholder | Role | Interest |
| --- | --- | --- |
| Rolf van Leeuwen (RVL) | Product owner, decision maker | Faster, reliable reports; control over data and tools |
| Inspectors | Main users | Less copying, clear proposals, final say over every link |
| Technical Responsible Person | Signs the report on behalf of the company | A correct, complete, traceable report |
| Quality reviewer | Checks the work | Evidence of how every result was linked and by whom |
| Laboratory | Supplies analysis reports | No change to its way of working |
| Client / class society | Receives the IHM | A report in the agreed structure |
| Project team (Tasnim, Ivan) | Build and evaluate | A prototype that can be explained and assessed |

## 4. Current process and where it hurts

The process runs: project creation, desk research, planning, fieldwork, synchronisation, laboratory analysis, quality control, report, digital asset record. The step James targets lies between laboratory analysis and report.

| Step | What happens today | Problem |
| --- | --- | --- |
| Lab report arrives | PDF per test type, sometimes a new version replacing an older one | Several reports per project, versions must be tracked |
| Match result to sample | The inspector compares the lab's lines with the field register | The lab uses its own ID; our code sits in a separate overview table |
| Read the code | Codes in older notations (CH6, Pac, ZM, M) and spelling variants (CR601, MM-01) | Easy to mismatch two tests at the same place |
| Read the result | Up to 16 parameters per sample, remark letters with a meaning | A "below 10" with remark C does not mean "absent" |
| Fill the report | Copy into the IHM template by hand | Repetitive, error-prone, little trace of who decided what |

**Root causes:** two numbering systems (lab and RVL) joined only through the lab's overview table; several notations for the same test; manual copying without a record of decisions. These were confirmed by studying the structure of real lab reports; no content of those reports is used in the project.

## 5. Scope

**In scope:** one workflow (IHM / HazMat Part I); project and sample registration; reading lab reports (pasted text, digital PDF, scanned PDF with OCR); link proposals by rules with optional AI; inspector review; a draft report in RVL's template; evidence and audit log; repeatable evaluation on fictional test sets.

**Out of scope:** automatic approval; all survey types at once; production platform and support; real client data or real AI use without RVL's approval.

## 6. What has been built

| Part | What it does |
| --- | --- |
| Field registration | Project information as in the RVL template; samples with code, source, location, material, photo, drawing, quantity; places that could not be sampled with a reason |
| Lab report reading | Simple one-table reports and the two-table layout labs use (overview table plus results tables, joined on the lab's own ID); scanned pages via local OCR |
| Linking | Rules first: exact codes, spelling variants, older notations, conflicts and unregistered codes; AI only for lines the rules cannot settle; disagreement means no link |
| Review | The inspector approves, corrects or rejects each line under their name; decisions are append-only and can be changed |
| Report | RVL's IHM template filled from approved lines only, with a project-specific summary; signing locks the report |
| Evidence | File fingerprint, read method, linker and prompt version, audit log, object history |
| Hosting | Optional shared copy with login on Render, data on a persistent disk |

## 7. Evidence: what the measurements show

The linker is scored on fictional test sets with reference answers written before each run. Four outcomes: correct, wrong, no link where none existed (correct), and no link where one existed (missed). A wrong link counts most, because a convincing wrong link can pass review.

**Rules only, current code (17 November):**

| Test set | Lines | Correct | Wrong | No link (OK) | Missed |
| --- | --- | --- | --- | --- | --- |
| dev (simple codes) | 12 | 8 | 0 | 2 | 2 |
| dev2 (typed codes) | 11 | 8 | 0 | 2 | 1 |
| dev3 (RVL notation) | 10 | 8 | 0 | 2 | 0 |
| dev4 (two-table layout, structure) | 12 | 8 | 1 | 2 | 1 |
| dev5 (PAH report style) | 10 | 8 | 0 | 2 | 0 |
| **Total** | **55** | **40** | **1** | **10** | **4** |

The one wrong link (dev4, g9): the code exists and the place fits, but the result is a heavy-metals result on a chromium-6 sample. The rules do not yet check that the result fits the test.

**Rules plus AI (hybrid), 45 lines of dev to dev4, runs of 16 November, re-scored against today's reference answers:**

| Variant | Correct | Wrong | No link (OK) | Missed | Cost for 45 lines |
| --- | --- | --- | --- | --- | --- |
| Rules only | 31 | 1 | 8 | 5 | free |
| Hybrid, gpt-oss-20b, prompt v1 | 32 | 2 | 7 | 4 | about $0.006 |
| Hybrid, gpt-oss-120b, prompt v1 | 31 | 2 | 7 | 5 | about $0.012 |
| Hybrid, gpt-oss-20b, prompt v2 | 26 | 1 | 8 | 10 | about $0.01 |

**What this means:** a model six times larger was not safer, so the smaller model was kept. The first prompt let the model follow the place description instead of the code. The second prompt removed most AI mistakes but made the model refuse older notations; prompt v3 fixes the order of its rules and has not been measured yet. The same prompt gave a different answer on the same line on two days, so single runs are not enough evidence.

**Limits:** all lines are fictional and written by the team; 55 lines is small (one line moves a score by about 2 points); the hold-out set was last run on 26 October (rules: 6 correct, 0 wrong, 2 OK, 1 missed); no real lab report has been scored.

## 8. Options and multi-criteria analysis

Team assessment, to confirm with RVL. Scores 1 (weak) to 5 (strong); for cost and risk a higher score means lower cost or risk.

| Criterion | Weight | A. Manual with templates | B. Digital workflow + rules | C. B plus AI for unclear lines |
| --- | --- | --- | --- | --- |
| Process value | 25% | 2 | 3 | 4 |
| Safety and control | 25% | 5 | 5 | 3 |
| Feasibility now | 20% | 5 | 5 | 4 |
| Traceability | 15% | 2 | 4 | 5 |
| Cost, privacy, dependency | 15% | 5 | 5 | 2 |
| **Weighted score (of 5)** | 100% | **3.80** | **4.35** | **3.60** |

Option B scores highest: it delivers structure, traceability and the report without sending data to an outside service. Option C has more potential for messy lines (the AI correctly read "lead" to choose a heavy-metals sample where the rules could not), but it has not yet shown fewer wrong links and it needs RVL's approval of the provider and data.

## 9. Risks

| Risk | Effect | Measure |
| --- | --- | --- |
| Convincing wrong link passes review | Result on the wrong place in the report | Conflicts become "no link"; practice review with seeded errors; rule "result must fit the test" (to build) |
| Real lab layouts differ from test data | Lines not read or mixed up | Count-only check on real PDFs locally; unmatched lab IDs are shown, never guessed |
| Real data sent to an outside AI | Breach of RVL's rule and client trust | Fictional data only; AI off by default; key only in the environment |
| AI answers change between runs | Unstable proposals | Repeat runs; AI never decides alone; inspector approves every line |
| Thresholds or report layout wrong | Wrong classification in Table A/B | Thresholds marked "to confirm by RVL"; unknown substances go to the inspector |
| Hosted copy loses data | Rework | Paid plan with disk; backups still to arrange |

## 10. Advice and next steps

1. Keep option B as the core and build the missing rule: a result must fit the test of the sample code.
2. Measure prompt v3 three times on all test sets; adopt AI help only if the hybrid makes no more wrong links than the rules and links more lines correctly.
3. Run the extractor on real lab reports locally, without AI, and record only counts (lines read, lines linked).
4. Ask RVL to decide: approved AI provider and data scope; where PAH results go in the report; whether a lab code "PCB-01" means PBS, SS or OS; the threshold values.
5. Measure the time per report with and without James on a few surveys (K5) and run a short usability test (K8).
6. Run the hold-out set once, on the final version only.
