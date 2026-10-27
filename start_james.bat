@echo off
rem Start the James app: data is kept in james.db, the browser opens by itself.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (set PY=.venv\Scripts\python.exe) else (set PY=python)
if not exist "context\IHM 26-.odt" if "%JAMES_IHM_TEMPLATE%"=="" (
  echo Note: RVL's IHM template is not in context\. The app works, but "Download IHM report" will not.
  echo Ask Ivan or Tasnim for the template and put it in the context folder.
  echo.
)
start "" http://127.0.0.1:8000
%PY% app\server.py --db james.db
if errorlevel 1 (
  echo.
  echo The app stopped with an error. Is Python installed and did "pip install pdfplumber reportlab pillow" run?
  pause
)
