# app/ — James lab-agent prototype (Ivan)

Concept prototype. **All data is fictitious**, no real AI runs (a recorded stand-in answers).
The agent proposes, a named inspector decides.

## Start (Windows)
    python app\server.py
Open http://127.0.0.1:8000. Python 3 and `pdfplumber` (for PDF upload) only.

## Your own (fictitious) project
1. "New project": the Project Information fields of the RVL IHM template.
2. "Sources and samples": register every sample with deck, location, part, material, photo, drawing position,
   quantity and unit. A place that could not be sampled gets status "not sampled" and a reason.
3. Paste or upload the lab report. Decide every line, then sign as Technical Responsible Person.
   The report is laid out like the RVL IHM template; Table A/B quantities come from the registration.
4. "Download IHM report (.odt)" fills RVL's IHM template. The template is not in the repository: put it at
   `context/IHM 26-.odt` or set `JAMES_IHM_TEMPLATE` to its path.

## Demo flow
1. Type the inspector name (top right). Every decision is signed.
2. Demo report L-26-4471 is loaded (MV Noorderlicht, the same data as the demo artifact).
   "Needs your attention" shows M-03 (notation differs) and M09 (unregistered code) first.
3. Approve / correct / reject each line. Only approved lines reach the report.
4. The report follows the layout of an RVL IHM report: Part I lists I-1/I-2/I-3, 2.3 results per
   substance, 3 survey limitations, 5.1 Table A and B. "Sign as definitive" locks the decisions.
5. "Save approved lines to the history", then load "Follow-up L-26-4590" to see a changed result.
6. "Practice review" loads the report with 5 deliberately wrong links and scores the reviewer (TC12).
7. "Upload lab PDF" reads a fictitious lab PDF with `james/extract.py`. "Paste a lab report" takes text.

## Files
- `server.py` — web server and service layer around `ai/` and `james/`
- `ihm.py` — reads a lab result into substance, threshold status, Table A/B and Part I list
- `thresholds.json` — the thresholds, **to confirm by RVL**
- `export_odt.py` — fills RVL's IHM template (.odt) with the approved results
- `demo_data.py` — the fictitious ship and its two lab reports
- `static/index.html` — the screen
- `demo/james-lab-agent.html` — the standalone demo published as an artifact
- `test_app.py`, `test_export.py` — tests: `python -m unittest discover -s app -p "test_*.py" -t .`

## What each test case from Harm's Appendix I touches
| TC | Where |
|---|---|
| TC01, TC07 | certificate and method columns; completeness flags |
| TC03 | unregistered code → no link (linker) |
| TC04 | duplicate code in the register is refused (`store.add_object`) |
| TC05, TC06 | `ihm.py` + `thresholds.json`; exactly-on-threshold is flagged |
| TC08 | register status `not sampled` → survey limitations, PCHM |
| TC09 | processing time on the report card |
| TC12 | practice review |

## Not decided yet
- Sample code notation (`M01` or `MM01`), thresholds, report template: see `docs/questions-rolf-joris.md`.
