# Start here

This folder is a starting kit for working on the AI part of James with Claude Code in VS Code.

## Set up (about 15 minutes)

1. Unzip this folder somewhere simple, for example `Documents/james`.
2. Open VS Code, choose **File > Open Folder**, and pick this folder.
3. Install the **Claude Code** extension and sign in. (If your team shares one Claude login, read the shared-account rules on your plan page first, and keep one chat per task.)
4. Open a terminal in VS Code and run:
   ```
   python3 -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install pdfplumber reportlab pillow
   python3 -m unittest discover -s tests -t .
   ```
   You should see `OK`. A few tests skip themselves if OCR tools are missing; that is fine.
5. Open the Claude Code panel and paste the prompt for **Chunk 0** from `docs/CHUNKS.md`.

## What is in the folder

| Path | What it is |
|---|---|
| `CLAUDE.md` | The standing brief Claude Code reads every session (rules, ownership, teaching mode) |
| `docs/CHUNKS.md` | The ordered prompts, one chunk per session |
| `ai/testcases/cases.json` | Registers and 32 test lines with reference answers (fictional) |
| `ai/prompts/` | The baseline prompt and the fixed answer format |
| `contract/` | Filled in during Chunk 2, shared with Ivan |
| `app/` | Ivan's. Leave empty or put his code here, do not edit |
| `james/`, `tests/`, `schema.sql`, `run_demo.py` | The backend starting point (made-up data, 32 passing tests) |

Do not put real RVL reports anywhere in this folder until Rolf and your coach have approved a tool and said what may be shared.
