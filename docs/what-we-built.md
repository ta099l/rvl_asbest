# What we built

Three lines per item: what it does, why it exists, one example.

## 1. Answer importer (`python3 -m ai.james_ai.import_answers <file>`)
- **What:** reads prompt + answer pairs pasted from the prompt lab and files each answer under the exact prompt in `ai/replays/*.json`; a new prompt wording becomes a new version in `ai/prompts/vN_imported.txt`.
- **Why:** copying answers by hand into JSON is slow and error-prone, and an answer must never end up under the wrong prompt or replace an earlier one unnoticed.
- **Example:** paste `=== PROMPT` + the d2 prompt + `=== ANSWER` + the reply into `answers.txt`; the command prints `FILLED dev_v1.json d2`, and pasting a different reply later prints `CONFLICT ... kept it (use --replace to overwrite)`.
