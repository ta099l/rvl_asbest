# How to test what is built

Run everything from the project folder, in the VS Code terminal (WSL):

```
cd ~/rvl_asbest
source .venv/bin/activate
```

The prompt now starts with `(.venv)`. Do this once per new terminal.

## 1. All automatic tests (do this first, and after every change)

```
python3 -m unittest discover -s tests -t .
```

Expected: `Ran 117 tests ... OK (skipped=1)`. The one skip is the OCR test (needs `tesseract`, not installed). Any `FAIL` or `ERROR` means something broke: read the first lines of the message, they name the test and the line.

One file at a time, with the name of each test (`-v`):

| Command | What it proves |
|---|---|
| `python3 -m unittest tests.test_linker -v` | Rules: IDs, conflicts, typed codes (M12 is not HM12) |
| `python3 -m unittest tests.test_contract -v` | 20 kinds of broken AI answer all become no link |
| `python3 -m unittest tests.test_score -v` | The four outcomes are counted right; hold-out is saved, not shown |
| `python3 -m unittest tests.test_ai_step -v` | Prompt is built right; garbage, errors and missing answers become no link |
| `python3 -m unittest tests.test_hybrid -v` | What goes to the AI, how answers are merged, the guard |
| `python3 -m unittest tests.test_store tests.test_extract -v` | Ivan's starting code still works |

## 2. The demo (whole flow, made-up ship)

```
python3 run_demo.py
```

Look for: row 6 `NO LINK` (ID says S-05, description says S-06), row 7 `NO LINK` (S-09 not in register), row 8 `low` (matched on description only). Every result is a proposal until the inspector step.

## 3. The baseline numbers (rules only)

```
python3 -m ai.james_ai.score --set dev
python3 -m ai.james_ai.score --set dev2
```

Expected now:

| Set | correct | wrong | abstained_ok | abstained_missed |
|---|---|---|---|---|
| dev | 8 | 0 | 2 | 2 |
| dev2 | 8 | 0 | 2 | 1 |

(dev2 was 9 / 2 / 0 / 0 before Chunk 4, and 8 / 0 / 1 / 2 before e11 was set to no link.) Below the numbers you see each line that was not right, with the reason.

**Do not run `--set hold` to check things.** It was run once for rules v1 (6 / 0 / 2 / 1, saved in `ai/runs/`). Run it again only for a final version.

## 4. The three-way comparison

```
python3 -m ai.james_ai.compare --set dev --replay ai/replays/dev_v1.json
```

Without AI answers the AI column is all "no link" and the hybrid equals the rules. That is the honest result, not a bug. `(rules only)` marks lines that never go to the AI.

## 5. Try to break it yourself (good for the interview)

**A broken AI answer.** Look at the prompt for the contract example, then feed a bad answer:

```
python3 -m ai.james_ai.ai_step prompt contract/examples/request.json
python3 -c "
import json
from ai.james_ai.ai_step import propose, FailingClient
req = json.load(open('contract/examples/request.json'))
run = propose(req, FailingClient('[{\"n\":1,\"sample\":\"S-99\"}]'))
print(run.problems)
for p in run.response['proposals']: print(p)
"
```

Expected: every line `sample: None`, reason starts with `AI answer rejected`. Change the answer text and run it again: whatever you break, you never get a link from a broken answer.

**A tricky lab line for the rules.** Change the line and see what the rules do:

```
python3 -c "
from ai.james_ai.score import load_cases, to_samples, link_line
reg = to_samples(load_cases()['registers']['ship_typed_codes'])
p = link_line('M12 | Red-brown paint, cargo hold 1, heavy metals | Pb 640 mg/kg', reg).proposals[0]
print(p.sample_id, p.confidence, p.flags); print(p.reason)
"
```

Try `HM12` instead of `M12`, or `PBS 3 | Cable sheath, main switchboard | PCB 12 mg/kg`.

## 6. Adding real AI answers (prompt lab)

1. Open `ai/replays/dev_v1.json`. Each entry has `text` (the exact prompt) and `"answer": null`.
2. Paste `text` into the prompt lab (only with an approved tool, and only this fictional data).
3. Paste the model's reply into `answer`, exactly as it came (raw text is fine; inside JSON quotes need `\"`, or paste the JSON object itself).
4. Run the comparison of step 4 again. "AI answers found for N of 12" goes up.

If you change the prompt, make a new version (`ai/prompts/v2_....txt`), export again with `--prompt v2_...` into a new file. Old answers are not reused for a new prompt: the key is a fingerprint of the exact text.

## 7. Git: see what changed

```
git log --oneline                # all saved steps
git diff a72511c --stat          # everything changed since the original kit
```

## 8. Iteration log (Appendix A)

```
python3 -m ai.james_ai.score --set dev --save
python3 -m ai.james_ai.compare --set dev --replay ai/replays/dev_v1.json --save
python3 -m ai.james_ai.iteration_log
```

The first two save a run to `ai/runs/` (now kept in git). The last one rebuilds `docs/iteration-log.md` from all saved runs and prompt versions. Check that its tables match what the commands printed. Hold-out runs appear with totals only.

## 9. Interactive demo as an inspector

```
python3 run_demo.py --flow
```

Type your name, then for each line `a` (approve), `c` (correct: type the right code and a note), `r` (reject, with a note) or `s` (skip). At the end you see the draft report and the audit log with your name on every decision. Try `a` on line 8: it is refused, because the rules (S-08) and the stand-in AI (no link) disagree, so nothing is proposed. The AI answers come from `ai/replays/demo_ship.json`: hand-written stand-ins, not model output.

Imported prompt-lab answers: `python3 -m ai.james_ai.import_answers answers.txt` (see the top of `ai/james_ai/import_answers.py` for the file format).
