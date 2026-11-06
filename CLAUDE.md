# James: AI linking part (Tasnim's workspace)

Read this file first. It is the standing brief for every session in this folder.

## Who and what

- The user is **Tasnim**, a student in the Windesheim minor Digital Transformation & AI. She has **not built or trained an AI before** and wants to understand everything that is built.
- Client: **RVL Asbest / James** (inspections for asbestos, chromium-6, HazMat and IHM on ships and structures). Product owner: Rolf van Leeuwen. Teammate building the app: **Ivan**.
- The folder is a six-week-minor project with a portfolio assessment. Tasnim owns **Chapter 11 (Prompting)**, **Appendix A (prompt iterations)**, and with Ivan Chapter 9 and Appendix J.

## The one chain James supports

`analysis result -> sample -> source/application -> location in the object -> object -> survey location`

The AI proposes each link. A **named inspector approves, corrects or rejects** every link. Nothing is final without that.

## Safety rules (never break these)

1. The system only **proposes**. It never approves a link by itself.
2. When evidence is missing or conflicting, propose **no link** (`sample: null`) with a reason. A wrong link that looks convincing is the worst outcome. The target for wrong links is zero.
3. A proposed sample code must exist in the register. Anything else counts as a wrong link.
4. If a model answer is not valid JSON or breaks the contract, treat every line of it as **no link**. Never guess.
5. Decisions are append-only: a new decision supersedes an old one, the log keeps both.
6. **Fictional data only.** No real RVL reports, names, IMO numbers or locations until Rolf and the coach confirm the approved AI tool and that anonymised reports are allowed.
7. **No secrets in the repo.** API keys come from environment variables, never from files that are committed.

## Teaching mode (important)

Tasnim must be able to explain every piece in her individual interview. So:

- Work in **small chunks** (see `docs/CHUNKS.md`). Finish one chunk, then stop and wait.
- **Before** changing anything, say in plain words what you are about to do and why, in 3 to 6 lines. Avoid jargon; if you must use a term, explain it once.
- **After** each chunk: what changed, which files, what the numbers show, and one question for Tasnim to test her understanding. Do not move on until she has answered or says to continue.
- Prefer the smallest change that works. Do not add frameworks, abstractions or features that were not asked for.
- When something fails, show the real error, say what it means, then fix it.
- Keep a running file `docs/learning-notes.md`: three lines per session (what we did, what was surprising, what is still unclear). It feeds her Chapter 11 reflection. Ask before writing in it.

## Who owns what (do not cross)

| Folder | Owner | Notes |
|---|---|---|
| `ai/` | Tasnim | prompts, linking logic, evaluation, test cases |
| `contract/` | Tasnim and Ivan together | change only when both agree; write the decision in `docs/decisions.md` |
| `app/` | Ivan | screens, API, database, upload, hosting. **Do not edit.** |
| `james/` | shared starting point | earlier backend code. `linker.py`, `evaluate.py`, `demo_data.py` move into `ai/` (Chunk 1). `store.py`, `extract.py`, `schema.sql` are Ivan's to keep, rewrite or drop. Do not change them without asking Tasnim. |

Work on the git branch `tasnim/ai`. Never push to `main`.

## The contract

Input from the app:

```json
{"report_id":"LAB-2026-0412","register":[{"code":"S-01","location":"Engine room, port bulkhead","material":"Insulation wrap","colour":"grey fibrous"}],
 "rows":[{"n":1,"raw_id":"S02","description":"Exhaust pipe lagging, engine room","result":"Asbestos not detected"}]}
```

Output to the app (`sample: null` means no link):

```json
{"proposals":[{"n":1,"sample":"S-02","confidence":"high","reason":"ID S02 matches S-02 and the description matches the exhaust lagging"}]}
```

One proposal per row, same order, same `n`. Schemas and examples live in `contract/`.

## Test data and scoring

- `ai/testcases/cases.json`: registers, and 42 lab lines in four sets: `dev` (12, S-codes), `dev2` (11, typed codes like M01, HM12, PBS03), `dev3` (10, RVL standard notation like MM-1, CR6-1, with older notations), `hold` (9, **hold-out: use once per final version, never tune on it**).
- Every case has an inspector-style reference answer (`truth`, `null` means no link exists).
- Four outcomes: **correct**, **wrong**, **abstained_ok** (no link, and none existed), **abstained_missed** (no link, but one existed). Wrong links count most.
- RVL standard codes (Rolf, 6 Nov 2026): `MM` asbestos bulk, `KM` asbestos dust, `PBS` PCB bulk, `SS` PCB swipe, `OS` PCB oil, `ODS`, `PFOS`, `HBCDD`, `HM` heavy metals, `CR6` chromium-6, `PAH`, `TBT`, `PFAS`, `NORM`, `TPH`, `VOC`, `VI` visual inspection, `DR` document review, `EI` equipment identification; written `MM-1` (dash, no leading zeros). Older notations stay recognisable through the alias table (`CH6` → `CR6`, `PAC` → `PAH`, `M` → `MM`); `ZM` is unknown. The lab's original code is always kept. Two codes that differ only by prefix (for example `MM-12` and `HM-12`) are a real conflict risk.

## Commands

```
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install pdfplumber reportlab pillow
python3 -m unittest discover -s tests -t .             # all tests, should pass before and after each chunk
python3 run_demo.py                                    # walk through the demo flow
```

OCR for scanned PDFs also needs `tesseract` and `poppler-utils`. Tests that need them skip themselves when missing.

## Style

- Python 3, standard library first. Type hints on public functions. Short docstrings that say *why*.
- Every behaviour change comes with a test. Tests use the fictional demo data only.
- Plain English in comments and docs. Dutch terms only when quoting Rolf.

## Known limits (state them honestly in any write-up)

- No real lab report has been used. Real layouts will break `extract.py`.
- The rule-based linker is the baseline. AI value over rules is **not yet shown**. If it adds nothing, that is a valid finding.
- There is no AI/API access yet. The AI step is built against a stand-in until the tool is approved.
- Accuracy on made-up data says nothing about accuracy on real reports.

## Explain like I am new
I have never built or trained an AI and I am confused. From now on:
- Explain every term the first time you use it, in one plain sentence, with an everyday comparison.
- Use one real example line (S02 | Exhaust pipe lagging, engine room | Asbestos not detected) and follow it through the code, so I see what happens to it.
- Never show more than one idea at a time. Keep each explanation under 15 lines, then ask me a question and wait.
- Keep docs/glossary.md up to date with every term you introduce.
- If I say "simpler", start again with a different comparison, not the same words shorter.
