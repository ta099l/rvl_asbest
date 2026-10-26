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
