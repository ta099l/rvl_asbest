# James — lab agent prototype (RVL Asbest, minor DT&AI)

A concept prototype for RVL's IHM surveys: register sources and samples, read a lab report, let the agent propose a link per result, let a named surveyor decide, and fill RVL's IHM template with the approved results. **All data is fictitious. Replay answers are the default; an optional Groq client is available for controlled evaluation with fictional data.**

The agent only proposes. A named person approves, corrects or rejects every link. Nothing is final without that.

## Get started (Windows, about 15 minutes)

1. Install **Python 3** (python.org, tick "Add python.exe to PATH") and **Git**.
2. Get the code:
   ```
   git clone https://github.com/ta099l/rvl_asbest.git
   cd rvl_asbest
   git checkout ivan/app
   ```
3. Install the three packages:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install pdfplumber reportlab pillow
   ```
4. Copy RVL's documents into a folder `context\` in the project (ask Ivan or Tasnim; they are shared through the team folder, **never through GitHub**). The app needs `context\IHM 26-.odt` for the Word download; everything else works without it.
5. Start: double-click **`start_james.bat`**, or type `python app\server.py --db james.db`. The browser opens http://127.0.0.1:8000. Keep the black window open; close it (or press Ctrl+C) to stop.

To opt in to Groq, follow `docs/using-groq.md`. Use fictional data until RVL and the coach approve any broader data use.

## Use it

- Type your name at the top: every action is signed with it.
- **Demo:** MV Noorderlicht with lab report L-26-4471 is loaded. "Needs your attention" shows the two lines the agent is unsure about.
- **Own (fictitious) project:** New project → register sources and samples → paste or upload a lab report → decide every line → sign as Technical Responsible Person → **Download IHM report (.odt)**, which opens in Word.
- **Practice review:** a report with five hidden mistakes, to test whether the reviewer really checks (Harm's TC12).
- Your projects are kept in `james.db` in the project folder (not in git). Delete it to start clean.

Without installing anything, the flow can be seen in the demo artifact (ask Ivan for the link).

## Who works where

| Folder | Owner | Branch |
|---|---|---|
| `app/` — screen, server, report, Word export | Ivan | `ivan/app` |
| `ai/` — linker rules, prompts, scoring, test cases | Tasnim | `tasnim/ai` |
| `contract/` — what the app and the AI part send each other | Tasnim and Ivan together | change only when both agree |
| `james/`, `schema.sql` — PDF reading and database | Ivan, ask Tasnim first | `ivan/app` |
| `docs/` — decisions, context, questions for RVL, glossary | everyone | your own branch |
| Test rounds (Appendix I, KPI sheet) | Harm | `harm/tests` |

## Team rules

1. **Work on your own branch.** Never commit to `main` or to someone else's branch.
2. **Merge through a pull request** on GitHub, reviewed by one other team member.
3. **Tests green before every push:**
   ```
   python -m unittest discover -s tests -t .
   python -m unittest discover -s app -p "test_*.py" -t .
   ```
4. **Fictitious data only.** No real RVL reports, client names, ship names, IMO numbers or locations until Rolf and the coach approve it.
5. **No secrets in the repo.** API keys come from environment variables, never from files that are committed.
6. **RVL's documents stay out of git.** The folder `context/` is ignored on purpose.

## Where to read more

| File | What |
|---|---|
| `app/README.md` | the app in detail, and which test case each feature serves |
| `docs/context.md` | what we know from RVL's documents (template, work process, onboarding, Lloyd's checklist) |
| `docs/decisions.md` | every decision, why, and who agreed |
| `docs/questions-rolf-joris.md` | open questions for RVL, each linked to the test it blocks |
| `docs/what-we-built.md` | each piece in three lines: what, why, example |
| `docs/glossary.md` | every term in one plain sentence |
| `docs/using-groq.md` | optional setup for testing the AI step with Groq and fictional data |
| `docs/groq-model-selection.md` | current Groq prices and the proposed quality/cost comparison |
| `CLAUDE.md` | the standing brief for Claude Code sessions in this folder |
