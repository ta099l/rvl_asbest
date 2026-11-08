# James midterm document set

**Status:** working draft, based on repository evidence available 6 November 2026.  
**Purpose:** make the reasoning, design, implementation and validation of the James prototype easy to assess and explain.

These documents connect to one another: the problem analysis motivates the advice; the requirements shape the design; the prototype realizes part of that design; and the validation and control plan identify what is proven and what remains to be checked.

## Documents

1. [Problem analysis and advice](01-analysis-and-advice.md) — current process, problem, scope, options and provisional multi-criteria analysis.
2. [Requirements and user stories](02-requirements-and-user-stories.md) — functional and nonfunctional requirements with acceptance checks and current status.
3. [Solution design](03-solution-design.md) — workflow, data flow, architecture, OCR and AI-linking design.
4. [Realization and validation](04-realization-and-validation.md) — what exists in the repository, evidence, known limits and test plan.
5. [Project management and control](05-management-and-control.md) — staged three-month plan, decisions, risks and review points.
6. [Assessment evidence map](06-assessment-evidence-map.md) — where current evidence supports the midterm and what is still missing.

## PDFs for the coach meeting (3 November 2026)

- [Problem Analysis & Advice (PDF)](01_problem_analysis_and_advice.pdf)
- [Requirements & User Stories (PDF)](02_requirements_and_user_stories.pdf)

## Optional Groq model work

- [Groq setup instructions](../using-groq.md)
- [Model price comparison and evaluation plan](../groq-model-selection.md)

## Evidence sources used

- `README.md`, `docs/context.md`, `docs/decisions.md`, `docs/what-we-built.md`, `docs/iteration-log.md`, `docs/how-to-test.md`
- `app/README.md`, `app/server.py`, `james/extract.py`, `ai/james_ai/`, `contract/`
- `ai/testcases/cases.json` and saved results in `ai/runs/`
- The course rubric and Techradar materials supplied in the three ZIP files

## Important qualifications

- These are **portfolio drafts**, not client-approved requirements or a signed-off implementation plan. Items marked **Confirm** need the team, coach or RVL to validate.
- The course files include material dated earlier in 2026. Confirm with Daan which criteria and dates apply to this cohort.
- Project notes disagree about whether field registration is implemented: an older status table says it was missing, while `docs/what-we-built.md` and the app describe project and sample registration. This set uses the newer implementation description and flags the discrepancy for a live demo check.
- An optional Groq client now exists for fictional-data evaluation; no live model results are recorded yet. Permission to use real reports, production cloud hosting, and production security are not established by the current repository.
