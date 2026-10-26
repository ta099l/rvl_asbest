# Concept demo for the coach (about 10 minutes)

Goal: show the concept works end to end on made-up data, that it is safe by design, and what you need from the coach to take the next step.

## Before you start (5 minutes earlier)

```
cd ~/rvl_asbest
source .venv/bin/activate
python3 -m unittest discover -s tests -t .      # must say OK (skipped=1)
```

Open the slides, and make the terminal font big (Ctrl and + in VS Code).

## 1. The problem (1 minute, slides)

"RVL inspectors take samples on ships. The lab sends back results, but the lab writes the codes its own way: `S02` instead of `S-02`, typos, Dutch text, no code at all. Today someone matches every line to the right sample by hand. A wrong match means a result ends up on the wrong spot in the ship's records, and that can be a safety problem."

## 2. The concept (1 minute, slides)

"The system **proposes** each link with a reason. A **named inspector** approves, corrects or rejects every one. When the evidence is unclear, it proposes **no link**. A wrong link that looks convincing is the worst outcome, so our target is zero wrong links."

"It works in two steps: fixed **rules** first, and only the lines the rules can't settle go to the **AI**. If the rules and the AI disagree, the result is no link."

## 3. Live: follow one line (2 minutes)

The line: `S02 | Exhaust pipe lagging, engine room | Asbestos not detected`

```
python3 run_demo.py --flow
```

Type a name, then press `a` on lines 1 to 5 and stop at line 2 to explain:

- The lab wrote `S02`; the register has `S-02`. The rules tidy both to the same code, so this is a **medium** match: the code needed tidying, but the description fits 100%.
- Medium means "not certain", so the line went to the AI as well. The AI agreed: **from: both**.
- You press `a`, and it's recorded under your name.

Then show **line 8** (`- | Pump packing, pump room`): the rules guess S-08 from the text alone, but the AI says the evidence isn't enough. They disagree, so **no link** is proposed. Pressing `a` is refused. Press `c`, type `S-08` and a note.

Finish the run (`r` on line 7 with a note, `a` on the rest). Show the **draft report** and the **audit log**: every decision has a name and a time.

Say: "The AI answers here are stand-ins I wrote to show the flow. We don't have an approved AI tool yet."

## 4. Live: the trap it avoids (1 minute)

```
python3 -c "
from ai.james_ai.score import load_cases, to_samples, link_line
reg = to_samples(load_cases()['registers']['ship_typed_codes'])
p = link_line('M12 | Red-brown paint, cargo hold 1, heavy metals | Pb 640 mg/kg', reg).proposals[0]
print(p.sample_id, p.confidence); print(p.reason)"
```

"The lab wrote M12, the asbestos test. But the text says heavy metals, which is HM12. My first version linked this with **high** confidence: wrong, and it looked convincing. Now it says no link and tells the inspector to ask the lab."

## 5. Live: broken AI output (30 seconds)

```
python3 -c "
import json
from ai.james_ai.ai_step import propose, FailingClient
req = json.load(open('contract/examples/request.json'))
run = propose(req, FailingClient('Sure! Line 1 is S-02.'))
for p in run.response['proposals']: print(p['sample'], '|', p['reason'][:70])"
```

"If the AI answers with anything that breaks the agreed format, every line becomes no link. We never try to repair the answer."

## 6. The numbers (1 minute, slides)

Rules only, on made-up test lines:

| Set | correct | wrong | no link, correct | no link, missed |
|---|---|---|---|---|
| dev (12 lines) | 8 | **0** | 2 | 2 |
| dev2 (11 lines, typed codes) | 8 | **0** | 2 | 1 |
| hold-out (9, run once) | 6 | **0** | 2 | 1 |

"dev2 started with **2 wrong links**. I fixed them by teaching the rules that a prefix is part of the code. The hold-out set is like an exam: I ran it once and never tuned on it."

## 7. Honest limits (1 minute)

- All data is made up. These numbers say nothing about real reports.
- There's no approved AI tool yet, so **whether the AI adds anything over the rules is not shown yet**. If it adds nothing, that is a valid finding.
- Real lab report layouts will need work on the PDF reading (Ivan's part).

## 8. What I need (1 minute)

1. Which AI tool is approved (Rolf and the coach), and what data may be sent to it.
2. Whether anonymised real reports may be used.
3. Feedback: is the "rules first, AI second, the inspector always decides" concept the right direction for the portfolio?

## Questions the coach may ask

- **"Why not just let the AI do it?"** An AI can be confidently wrong, and a wrong link is the worst outcome. The rules are predictable and explainable; the AI is only used where the rules are unsure, and disagreement means no link.
- **"How do you know it works?"** 32 test lines with an inspector-style answer, scored in four outcomes, plus 118 automatic tests. The hold-out set was run once.
- **"What did you learn about prompting?"** The prompt and the answer format are versioned. Every answer is tied to the exact prompt by a fingerprint, so results can't get mixed up between versions. The iteration log (`docs/iteration-log.md`) is the evidence for Appendix A.
- **"What's Ivan's part and what's yours?"** Ivan: the app, the database, upload, hosting. Me: the linking logic, the prompts, the evaluation and the test cases. The agreed format between the two parts is in `contract/`.
- **"What if the inspector is in a hurry?"** Nothing is final without a named decision, and a no-link proposal can't be approved with one key press.

## If something breaks during the demo

Run `python3 run_demo.py` (no flag): the scripted walk-through needs no typing. Or show `docs/iteration-log.md` and the test output.
