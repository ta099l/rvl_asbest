# Handoff for the next Claude session

Written 18 Nov 2026 on branch `tasnim/ai`, after the client meeting of 17 Nov 2026.
Read this after `CLAUDE.md`. CLAUDE.md holds the standing rules. This file holds **where things stand now and what changed**.

---

## 1. Read in this order

1. `CLAUDE.md`: the user, ownership, safety rules, teaching mode, commands. **Its rules win** over anything here.
2. This file.
3. `docs/decisions.md`: every agreed change, newest at the bottom.
4. `docs/what-we-built.md`: features 1–12, three lines each.
5. `docs/questions-rolf-joris.md`: open questions and Rolf's answers of 6 Nov.
6. Only when needed: `docs/iteration-log.md` (prompt results, generated), `docs/groq-model-selection.md`, `docs/hosting.md`, `docs/CHUNKS.md`.

## 2. The project in five sentences

- **James** is a prototype for RVL Asbest. It turns lab certificates (and later intake and fieldwork) into an **IHM report**: an Inventory of Hazardous Materials, mainly for ships.
- The part built so far links each **lab result line to a registered sample**: rules first, then AI (Groq) for the lines the rules can't settle.
- A **named inspector** approves every link.
- Approved results are classified per substance (`app/ihm.py`) and exported into RVL's IHM template (`app/export_odt.py`, .odt).
- This is a six-week student minor (Windesheim, Digital Transformation & AI), graded on a portfolio. The user is **Tasnim**, who owns `ai/` and Chapter 11 (Prompting). **Ivan** owns `app/`.

People:
- **Rolf van Leeuwen**: RVL, product owner, "the client" / opdrachtgever.
- **Rico Magsino**: supervising teacher / coach.
- **Harm**: wrote the test cases (TC..) and KPIs (K..).
- **Joris**: also receives questions (see the questions file).

## 3. Current state (checked 18 Nov)

- **Tests:** `.venv/bin/python -m unittest discover -s tests -t .` gives 153 OK. `python3 -m unittest discover -s app -t .` gives 59 OK.
  - Run inside `.venv`. With the system Python, 3 tests fail on missing `pdfplumber` / `reportlab`. That is setup, not a bug.
- **Last commits:**
  - 33d7fb6 (17 Nov): screen redesign.
  - 2648765 (16 Nov): prompts v2/v3, dev5, model runs, ZM alias, app fixes.
  - b4b99a6 (14 Nov): two-table lab layout, dev4.
- **Uncommitted** (Tasnim's working tree, don't discard):
  - `docs/decisions.md`: entry for the 17 Nov redesign.
  - `docs/iteration-log.md`: regenerated.
  - Untracked: `dev4_lab.pdf`, `dev5_lab.pdf` (fictional test PDFs) and `docs/report/` (portfolio chapters 01–04 as .md + .pdf).
- **AI:** Groq client exists (`ai/james_ai/client_groq.py`), with model `openai/gpt-oss-20b`. The key comes from an environment variable.
- **Prompts:** v1_baseline, v2_rules, v3_rules_order. **v3 has no saved run yet.**
- **Measured so far: the hybrid (rules + AI) is not better than rules alone.**
  - On dev4, rules score 8/1/2/1 (correct/wrong/abstained_ok/abstained_missed).
  - The v2 runs show the AI refusing old notations, which turns correct rule links into "no link". v3 was written to fix this.
  - Per CLAUDE.md, "AI adds nothing" is a valid finding. Don't hide it.
- **Test sets** in `ai/testcases/cases.json`: dev, dev2, dev3, dev4 (and dev5 for the app flow).
  - The `hold` set is used **once per final version**. Never tune on it.
- **Hosting:** `render.yaml` + `docs/hosting.md` are ready (Render, Frankfurt, about $7.25/month, login through `JAMES_USERS`). **Not yet deployed**, as far as the repo shows. Ask Tasnim.
- **App changes made at Tasnim's request in Ivan's `app/`** (16 and 17 Nov) are logged in `docs/decisions.md` as "Ivan: to review".
  - Don't edit `app/` again unless Tasnim explicitly asks.
  - Log any such edit in `docs/decisions.md` the same way.

## 4. What the client meeting of 17 Nov 2026 changed (most important)

Source: "Notulen gesprek opdrachtgever – RVL-asbest" (Rico and the client, about 28 minutes). Tasnim pasted it into the conversation; it is not in the repo. Key points:

**What the client actually wants:**
- A tool that turns **intake + fieldwork + analysis certificates** into a professional IHM report.
- **The bronbladen (source sheets) are the core of that report.**
- A bronblad contains:
  - a fieldwork summary with **photos** (each with a number and description);
  - the sample number (e.g. `M01`);
  - location, application, and condition (damaged, weathered);
  - the **analysis certificate number**.
- **Photo, sample and certificate must be linked correctly.** If they aren't, the report is unusable. The user must be able to check and correct that link.
- Most of the report is **fixed standard text**. Only the intake, the inventory tables and the bronbladen are project-specific. The AI should fill only those.
- His current way of working: he feeds lab reports (PCB, asbestos) into **ChatGPT** with his own work instructions. He builds the report step by step: analyses, then inventory tables (location, application, condition), then bronbladen. It still costs him many evenings.
  - **His ChatGPT chat, instructions and example reports are the real specification.** Ask for them.
- He wants **few clicks and little typing**: upload, process, check.

**His feedback on the version he has (sent before the weekend, so it may predate the 17 Nov redesign):**
- He couldn't really test it. **Clicking a project or a section only makes the page jump to the top.**
  - Cause in the code: the app is one long page. Every action calls `render()`, which replaces `#app.innerHTML` (`app/static/index.html` around lines 421–437), so the scroll position resets.
- "Everything is mixed together." He wants **separate pages or tabs**, in the order of his workflow: home, dashboard, intake, fieldwork, lab results, bronbladen, report.
- In fieldwork the **substance groups must be separate: asbestos, PCBs, heavy metals.**
  - Now the register is one table (`index.html` around line 570).
  - `app/ihm.py` already maps code prefixes to substances (`PREFIX_HINT`), so this can reuse existing logic.

**Decisions:**
- The IHM report with bronbladen is the main output.
- **Advice** (based on regulations, e.g. "don't sand lead paint") is an optional extra, not a requirement. Park it.
- The tool must go **online**, so the client always has the latest version.
- At handover the **API key must come from the client's own account**.
- Doing the fieldwork inside the tool (photos and notes on site) is a wish for **later**.

**Main risk named by Rico:** the team doesn't yet understand the client's workflow well enough. AI-built tools get to about 70%; the last 30% needs real understanding.

## 5. Gap analysis: meeting vs. code

| Need from the meeting | In the code now | Gap |
|---|---|---|
| Separate tabs, working navigation | One long page, full re-render, scroll resets | **Big**: blocks all client testing |
| Fieldwork split per substance group | One register table | Medium (prefix → substance logic exists in `ihm.py`) |
| Bronbladen with photos, sample, location, application, condition, certificate | Photo is only a text field (`F-012`); no photo upload; no bronblad screen or export | **Biggest content gap** |
| Photo ↔ sample ↔ certificate linkable and checkable | Certificate number per lab line exists (feature 6); sample ↔ result linking exists (the core of `ai/`) | Photo side missing |
| Intake form | "New project" has the template's Project Information (feature 10) | Unclear whether that matches his intake; ask him |
| Desk research incl. drawings | Only a "drawing position" text field | Missing |
| Fixed text + AI-filled parts | Export fills RVL's .odt template (feature 12) | Mostly there; check against his example report |
| Online | Render config ready | Deploy and send the link |
| Cost per report | Groq client logs token usage; illustrative arithmetic in `groq-model-selection.md` | Real per-report number not yet computed |
| API key on the client's account | Key from environment variable | Write the handover steps |

**How to frame Tasnim's linking work:** it is still needed, because it is how a certificate result gets tied to a sample on a bronblad. But it is one step toward the bronblad, not the product itself. Present it that way in docs and the portfolio.

## 6. Agreed priorities (proposed to Tasnim on 17 Nov; confirm before acting)

1. **A version the client can click through:** tabs, no scroll jump, hosted link. *(Ivan / `app/`)*
2. **Bronbladen with photos**, and the photo–sample–certificate link. *(Ivan for screens and export; joint for the contract if AI output changes)*
3. Fieldwork split per substance group; intake; desk research with drawings. *(Ivan)*
4. **Cost per report** from real Groq runs in `ai/runs/` (tokens → euros, at 10–25 reports/month per Rolf). *(Tasnim, `ai/`)*
5. **Handover note:** Groq account and API key in the client's name, Render account, where the key goes. *(Tasnim, with Ivan)*
6. **Run prompt v3** on dev–dev4 and log it. Compare with the client's own ChatGPT instructions once received (good Chapter 11 material). *(Tasnim)*
7. **Parked:** regulatory advice, fieldwork inside the tool.

**Action items for the students from the meeting notes:**
- Record a walkthrough with the client: what goes in, what he does by hand, what comes out. Use the transcript.
- Get his ChatGPT chat, instructions and example reports.
- Fix navigation.
- Restructure into tabs.
- Split fieldwork per substance group.
- Build the bronbladen.
- Add desk research.
- Deploy safely and report to Rico.
- Compute cost per report.
- Prepare the handover.

## 7. Traps

- **Fictional data only** (CLAUDE.md rule 6). The client offers real example reports and his ChatGPT chat. **Don't commit real reports, names, IMO numbers or locations** until Rolf and the coach confirm, or the material is anonymised.
  - Use real reports only to learn the *structure*, as was done for the two-table lab layout on 14 Nov (see `decisions.md`).
- `context/` holds the RVL IHM template (`IHM 26-.odt`) and `real_test.db`. Treat it with care and don't publish it.
- **Never push to `main`.** Commit only when Tasnim asks.
- Don't send anything about the project or the user to outside services. The Groq key is in the environment, never in files.
- The `hold` test set: once per final version only.
- `app/` is Ivan's. Proposals for him go in `docs/decisions.md` or a message, not as silent edits.

## 8. How to work with Tasnim

- Teaching mode from CLAUDE.md applies to every session:
  - small chunks;
  - say what you'll do in 3–6 lines first;
  - explain each new term once, with an everyday comparison;
  - keep each explanation under 15 lines;
  - end with one check question and wait for her answer.
- Keep `docs/glossary.md` up to date with every new term.
- Ask before writing in `docs/learning-notes.md`.
- She has to defend every piece in an individual interview. **Prefer the smallest change she can explain over a clever one.**

## 9. Open questions for the client (add to `docs/questions-rolf-joris.md` when asked)

1. Can we have the ChatGPT chat, its work instructions and two or three (anonymised) example reports?
2. Is "IHM Part 1, hazardous materials" the only part RVL delivers? Who delivers the other parts?
3. An asbestos threshold or percentage was mentioned in the meeting, but the number was inaudible. Which one?
4. Could his own server host the tool, instead of Render?
5. When is the walkthrough with the students? "Half past three" was mentioned; the date is unclear.
6. Word (.docx) or is .odt fine for the export? (Still open from 6 Nov.)
7. What exactly is his intake form? Does "New project" cover it?
8. How are photos numbered and described today, and do drawings come from the shipowner or from the yard?
