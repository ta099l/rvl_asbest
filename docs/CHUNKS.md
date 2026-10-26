# Work in chunks

Do one chunk per session. Paste the **Prompt** into Claude Code. When Claude stops, answer its question, tick the **Done when**, and only then start the next chunk. Chunks 0 to 5 need no AI access. Chunk 7 is blocked until the tool is approved.

Time per chunk: 1 to 2 hours. If a chunk runs long, stop at a natural point and say "continue next time".

---

## Chunk 0: Look around (no changes)

**Prompt**
> Read CLAUDE.md and docs/CHUNKS.md. Then explain the project to me in plain words: what James does, what the folders are, and what I own. Run the tests and show me the result. Do not change any file. At the end ask me one question to check I understood.

**You learn:** what a repo, a test and a virtual environment are; the whole picture before any code.
**Done when:** tests pass, and you can say in two sentences what the linker does.

---

## Chunk 1: Set up the folders and git

**Prompt**
> Create the git repo if there is none, make branch `tasnim/ai`, and add a `.gitignore` for Python and `.env`. Move `james/linker.py`, `james/evaluate.py` and `james/demo_data.py` into a package `ai/james_ai/`, fix the imports, and keep every test green. Do not touch `app/`, `store.py`, `extract.py` or `schema.sql`. Explain each step before you do it and show me the git log at the end.

**You learn:** branches, commits, why folders have owners.
**Done when:** tests pass, one clean commit exists, you can explain why `app/` is off limits.
**Check yourself:** what would go wrong if you and Ivan edited the same file?

---

## Chunk 2: Contract and a scoring script

**Prompt**
> Turn the contract in CLAUDE.md into two JSON Schema files in `contract/` (request and response) plus one example of each. Write `ai/james_ai/contract.py` with a function that validates a response against the register (one proposal per row, same `n`, `sample` is a register code or null, confidence is high/medium/low) and treats anything invalid as no link. Add tests, including a broken response. Explain what a schema is before you write one.

**You learn:** what a contract is and why Ivan and you need one; validating machine output.
**Done when:** a deliberately broken answer is rejected in a test.
**Check yourself:** why should invalid model output become "no link" instead of being repaired?

---

## Chunk 3: Test cases as data and the baseline score

**Prompt**
> Write a command `python3 -m james_ai.score --set dev` that loads `ai/testcases/cases.json`, runs the existing rule-based linker on every case, and prints correct, wrong, abstained_ok and abstained_missed, plus the lines it got wrong with the reason. Support `--set dev2` and `--set hold`. For `hold`, print a warning that it should be used once per final version, and write each hold-out run to `ai/runs/` with a timestamp. Adapt the rule-based linker input to the cases (each case is one line; the register comes from the set). Show me the numbers for all three sets and explain what they mean.

**You learn:** baseline, reference answers, evaluation outcomes, why a hold-out set exists.
**Done when:** you have a baseline number for dev and dev2 from the rules alone, written in your notes.
**Check yourself:** why do we count a wrong link as worse than a missed link?

---

## Chunk 4: Typed codes in the rules

**Prompt**
> Dev set 2 uses typed codes (M01, HM12, PBS03, ODS01). Show me which dev2 cases the rule-based linker fails and why. Then extend the linker so it understands a code prefix and number separately (for example PBS1, PBS 03 and PBS03 are the same code, but M12 and HM12 are different). A prefix mismatch with a matching description must produce no link and say why. Add tests for each case. Show before and after numbers on dev2. Do not use the hold-out set.

**You learn:** why real codes make matching harder; fixing one failure at a time and measuring.
**Done when:** wrong links on dev2 are zero, or you can explain each remaining one.
**Check yourself:** what does the linker do when the ID says M12 but the text describes the heavy metals paint?

---

## Chunk 5: The AI step, built against a stand-in

**Prompt**
> Build `ai/james_ai/ai_step.py` that follows the contract. It must: read a prompt version from `ai/prompts/` (start with `v1_baseline.txt` plus `_output_format.txt`), fill in the register and the lab lines, send the text to a **client object with one method `complete(text) -> str`**, parse the JSON answer, validate it with the contract code, and return proposals. Provide two clients: `ReplayClient`, which returns recorded answers from a JSON file (so I can paste answers I got in the prompt lab), and `FailingClient`, which returns garbage, to test that bad output becomes no link. Do not write a real network client yet. Add tests. Explain what a client object is and why we separate it.

**You learn:** how an app talks to a model without being tied to one vendor; structured output; failing safely.
**Done when:** tests show a valid answer is used, and garbage becomes no link for every row.
**Check yourself:** what has to change when the approved tool arrives? (Answer: only the client.)

---

## Chunk 6: Rules first, AI second

**Prompt**
> Build the hybrid pipeline: run the rule-based linker first. Lines it links with high confidence stay as they are. Only the lines it cannot link safely go to the AI step. Add a guard: if the AI proposes a sample that the rules already linked to another row, both get no link. Add a command to compare three variants on a set: rules only, AI only (from a replay file), and hybrid. Print one table. Use the replay file format from Chunk 5. Explain the table.

**You learn:** designing a system where AI is used only where it adds value; guards against false confidence.
**Done when:** you can say, with numbers, whether the AI adds anything over rules. Either answer is valid.
**Check yourself:** which lines should never go to the AI?

---

## Chunk 7: Survey location in the data model (agree with Ivan first)

**Prompt**
> Before writing code, draft a short proposal in `docs/decisions.md`: a survey location (port, shipyard, quay, date) belongs to a **survey**, not to the object, because one ship can be surveyed in Rotterdam and later in Antwerp. Show how the tables in `schema.sql` would change. Do not edit `schema.sql` or `store.py`. I will send the proposal to Ivan.

**You learn:** why data models follow the real process; writing a decision down.
**Done when:** Ivan has read the proposal and said yes or no.

---

## Chunk 8: Real model client (blocked until approved)

Start only after Rolf and Rico have named the approved tool and said what data may be sent.

**Prompt**
> Write `ai/james_ai/client_real.py` implementing the same `complete(text) -> str` for the approved tool. The key comes from an environment variable and is never written to a file. Add a request log (time, prompt version, length, cost if known; **not** the content), a timeout, and a rate limit. Run the dev set once and compare with the replay results from the prompt lab.

**You learn:** what an API call really is: key, request, response, cost, limits, where data goes.

---

## Chunk 9: Evidence for the portfolio

**Prompt**
> Write a script that reads every run in `ai/runs/` and `ai/prompts/` and produces `docs/iteration-log.md` for Appendix A: for each prompt version the change note, the full prompt, a results table, and the wrong or missed cases with reasons. Then help me outline Chapter 11.1 and 11.2 from it, using my own notes. Do not write the chapter for me; ask me questions and let me draft.

**You learn:** turning experiments into evidence; what graders look for (iteration visible, systematic improvement, reproducible).
**Done when:** the log builds with one command and matches the numbers you saw.

---

## If you get stuck

Say: "Explain what just happened in simpler words." Or: "Stop. What is the smallest next step?" Claude should then re-explain and not touch any file.
