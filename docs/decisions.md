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
