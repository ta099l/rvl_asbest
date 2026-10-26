# Decisions

One entry per decision: date, what, why, who agreed.

## 2026-10-26: Contract v1 for request and response (PROPOSED, waiting for Ivan)

- **What:** the request and response formats in `contract/` (schemas plus examples). The response is an object `{"proposals": [...]}`, not a bare list. Any broken answer turns every row into no link; a broken request raises an error.
- **Why:** an object can get new fields later without breaking the app. All-or-nothing rejection follows safety rule 4: a partly broken answer is not trusted for any line. Strict codes (exact spelling, must be in the register) follow rule 3.
- **Open point:** the v1 prompt (`ai/prompts/_output_format.txt`) still asks the model for a bare list, which this contract rejects. To be settled in Chunk 5 as a recorded prompt change, so v1 stays unchanged as the baseline for Appendix A.
- **Agreed by:** Tasnim (proposed). Ivan: not yet.
