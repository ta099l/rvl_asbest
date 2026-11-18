# 11. Prompting

James · AI-assisted linking of lab results for RVL Asbest · Draft · 17 November 2026

**Draft written with help from Claude (AI) on the basis of my own measurements in the repository. To rework in my own words before hand-in.** Every number comes from the saved runs in `ai/runs/`; the full prompts, change notes and line-by-line results are in Appendix A (`docs/iteration-log.md`).

## 11.1 The task and why prompting matters here

The AI in James has one narrow job: for a lab-report line that the rules cannot link safely, propose which registered sample it belongs to, or say that no sample can be chosen. A named inspector approves every proposal; the AI never decides.

That makes the prompt a safety instrument, not a style choice. The worst outcome is not a missed link (the inspector links it by hand) but a convincing wrong link: a result placed on the wrong sample that passes review. So the question for every prompt version was not "does it link more lines?" but "does it make fewer wrong links without losing too many correct ones?"

Four design decisions frame the prompt:

- **A fixed answer format.** The prompt asks for JSON in the shape of the contract agreed with Ivan: one proposal per line, a register code or null, a confidence and a reason. The answer is validated; if it breaks the contract, every line becomes "no link". A broken answer is never repaired, because a repaired guess is still a guess.
- **Rules first, AI second.** Clear links and clear conflicts are decided by the rule-based linker and never reach the model. The AI only sees lines the rules are unsure about, and if rules and AI disagree the line gets no link.
- **No self-reported confidence.** An AI-only link is capped at "medium"; "high" is reserved for objective rule checks (exact code, description agrees).
- **Measure, do not judge by eye.** Each prompt version runs on the same fictional test sets with reference answers written before any run, scored as correct, wrong, correct "no link" and missed.

## 11.2 Method

- **Test data:** 45 fictional lab lines in four sets (dev to dev4) covering simple codes, typed codes, RVL's standard notation with older notations, and the two-table lab layout. A hold-out set of 9 lines is not used for tuning.
- **Model:** Groq `openai/gpt-oss-20b`, chosen after comparing it with `openai/gpt-oss-120b` (section 11.3). Fictional data only; RVL has not yet approved a provider for real data.
- **Comparison:** three variants per run: rules only, AI only, and the hybrid that James actually uses.
- **Rule for prompt changes:** every change answers a mistake measured in the previous version, and the rules are written in general terms, without naming test cases, so the prompt is not tuned to the test.

## 11.3 Iterations

**Prompt v1: the baseline.** A plain task description: "For each lab line, say which sample in the register it belongs to", followed by the register and the lines. No examples and no rules about uncertainty.

| 45 lines, dev to dev4 | Correct | Wrong | No link (OK) | Missed |
| --- | --- | --- | --- | --- |
| Rules only | 31 | 1 | 8 | 5 |
| AI only, v1 (20b) | 35 | 7 | 3 | 0 |
| Hybrid, v1 (20b) | 32 | 2 | 7 | 4 |

On its own the model linked almost everything, including 7 wrong links. The reasons it gave showed the pattern: it followed the place description instead of the code. A chromium-6 line `CH6-01` was linked to the heavy-metals sample HM-1 because both were taken from the same wall. It also guessed a sample for codes that are not in the register, and picked one of two equally fitting samples. The hybrid caught most of this, but still ended with 2 wrong links against 1 for the rules alone.

**Model check: is the model the problem?** I ran the same prompt with the six times larger `gpt-oss-120b`. On its own it made 7 wrong links as well; in the hybrid 2, the same as the small model, at twice the price (about $0.012 against $0.006 for 45 lines). A bigger model did not fix the behaviour, so I kept the smaller model and concluded that the instructions had to change.

**Prompt v2: six rules from the measured mistakes.** v2 is v1 plus six rules, each aimed at one observed error:

1. The sample ID is the strongest evidence; the description only confirms it.
2. Spelling does not matter, a different prefix is a different test; older notations count as the same prefix (CH6 = CR6, PAC = PAH, M = MM).
3. A code that is not in the register gives no link.
4. The result must fit the test of the code (lead belongs to HM, Cr(VI) to CR6).
5. Two equally fitting samples give no link.
6. "High" confidence only for an exact code confirmed by the description.

| 45 lines, dev to dev4 | Correct | Wrong | No link (OK) | Missed |
| --- | --- | --- | --- | --- |
| AI only, v2 (20b) | 27 | 2 | 7 | 9 |
| Hybrid, v2 (20b) | 26 | 1 | 8 | 10 |

The AI's own wrong links dropped from 7 to 2, and the one wrong link left in the hybrid comes from the rules, not the AI: the model now correctly refused a heavy-metals result on a chromium-6 code. But the model became too cautious. Its reasons explained why: "Lab code Pac-01 is not present in the register". It applied rule 3 before rule 2, so older notations and spellings (CH6-02, M2, Pac-01, CR603) were refused. In the hybrid the rules linked these lines correctly, the AI said "no", and the disagreement turned five correct links into "no link". It also refused plain codes like S-03 because rule 4 only listed RVL test prefixes.

**Prompt v3: the order of the rules.** v3 changes two sentences. Rule 3 now says: first read the code as in rule 2, and only if it is then still not in the register, answer null. Rule 4 now applies only to codes whose prefix names a test, and lists every RVL test prefix, including the older notation ZM = HM from RVL's code list. v3 has not been measured yet; the expected effect is that the refused older notations become correct links while the wrong links stay at the v2 level.

## 11.4 What I learned about prompting

- **Measure behaviour, then change instructions.** Every useful change in v2 came from reading the model's own reasons on wrong lines. Without the line-by-line results I would not have seen that the model followed the place instead of the code.
- **A bigger model is not a better prompt.** Six times the model size gave the same wrong links. The cheap fix was clearer instructions, not more compute.
- **Rules interact.** Each v2 rule was sensible on its own; together they conflicted because the model applied them in the order it read them. Prompts need the same care as code: the order and the scope of each rule matter.
- **Safety and coverage pull in opposite directions.** v2 removed most wrong links but missed more correct ones. For RVL a missed link costs inspector time and a wrong link can end up in a signed report, so I accept fewer links if they are safer, but not a prompt that refuses correct, well-documented notations.
- **One run is not evidence.** The same prompt answered the same line differently on two days. Prompt versions must be compared over repeated runs.
- **Do not tune on the test.** Rules are written in general terms and never quote a test line, and the hold-out set is used once, on the final version only. One example in rule 2 (`CR601`) also occurs in a dev3 test line, which slightly favours that line; in v3 I replaced a second example (`S-03`) for exactly that reason.

## 11.5 Reflection (to write in my own words)

*Questions to answer here:*

- What surprised me most when I read the model's reasons for its wrong links?
- Why did I choose to keep the smaller model, and would I choose differently if RVL had a larger budget?
- What did I find hard about writing rules for a model, compared with writing rules in code?
- What would I do differently if I started the prompt work again?
- What is still unclear to me about how far the AI can be trusted in this task?

## 11.6 Limits and next steps

- All test lines are fictional and written by the team; 45 lines is a small set (one line moves a score by about 2 points).
- No real lab report has been sent to the model, and none will be until RVL approves a provider and the data that may be used.
- Next: measure v3 three times on all test sets (including dev5), adopt it only if the hybrid makes no more wrong links than the rules and links more lines correctly, then run the hold-out set once on the final version.
- The remaining wrong link of the rules (a result that does not fit the test of the code) should become a rule in code, so safety does not depend on the prompt alone.
