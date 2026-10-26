# Learning notes

Three lines per session: what we did, what was surprising, what is still unclear. Feeds the Chapter 11 reflection.

## 2026-10-26, Chunks 0 to 2

- **Did:** set up the kit, the virtual environment and the branch `tasnim/ai`; moved the AI code into `ai/james_ai/` without breaking the 32 tests; wrote the contract with Ivan as JSON Schemas plus a validator.
- **Surprising:** Ivan's `store.py` depended on the linker, so moving a file needed a small forwarder to avoid touching his code. The prompt and the contract disagreed on the answer format (list vs `{"proposals": [...]}`).
- **Still unclear:** (Tasnim to fill in)

## 2026-10-26, Chunks 3 to 9 (build mode)

- **Did:** baseline scores for the rules (dev 8/0/2/2, dev2 9/2/0/0, then 8/0/2/1 after typed codes and the e11 rule), the AI step with stand-in clients, the hybrid, the comparison table, the answer importer, the iteration log, the survey proposal for Ivan, and the interactive demo.
- **Surprising:** the most dangerous mistake was a confident one (M12 linked with high confidence while the text said heavy metals). Two reference answers (e7, e11) contradicted each other, so writing test data is itself a design decision.
- **Still unclear:** (Tasnim to fill in) Whether the AI adds anything over the rules: no AI answers recorded yet.
