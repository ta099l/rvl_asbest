# app/ — James lab-agent prototype (Ivan)

Concept prototype. **All data is fictitious**, no real AI runs (a recorded stand-in answers).
The agent proposes, a named inspector decides.

## Start (Windows)
    python app\server.py
Open http://127.0.0.1:8000. Python 3 only, no extra packages.

## Demo flow
1. Click "Load demo report 1".
2. Type the inspector name (top right). Every decision is signed.
3. Approve / correct / reject each line. Ch. 9 and Ch. 10 fill from approved lines only.
4. "Save approved lines to the history", then "Load follow-up report 2" to see a changed result.

## Files
- server.py — web server and service layer around ai/ and james/ (Tasnim's hybrid pipeline)
- static/index.html — the screen
- test_app.py — tests: `python -m unittest discover -s app -p "test_*.py" -t .`

## Not decided yet
- Sample code conventions (S-01 here), thresholds for Table A: Rolf must confirm.
