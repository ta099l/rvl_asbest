# Contract

The agreed JSON between Ivan's app and Tasnim's AI part. Changes only when Tasnim and Ivan both agree; write the decision in `docs/decisions.md`.

| File | What it is |
|---|---|
| `request.schema.json` | What the app sends: `report_id`, the `register` of the object, the lab `rows` |
| `response.schema.json` | What comes back: one `proposals` entry per row, same order, same `n` |
| `examples/request.json`, `examples/response.json` | One valid example of each |

## Rules a schema cannot express (checked in `ai/james_ai/contract.py`)

1. Register codes are unique. Rows are numbered `n = 1, 2, 3 ...` in order.
2. `proposals` has exactly one entry per row, and each `n` equals that row's `n`.
3. `sample` is a register code with the exact spelling, or `null` for no link. A link must have a `confidence` of `high`, `medium` or `low`.
4. No extra fields, and every proposal has a non-blank `reason`.

## What happens when a rule is broken

- **Broken response** (from the model): every row becomes `sample: null` with a reason starting "AI answer rejected ...". It is never repaired or partly used.
- **Broken request** (from the app): `ContractError` is raised. That is a bug to fix, not something to hide as "no link".

A proposal is only a proposal: a named inspector approves, corrects or rejects every one.
