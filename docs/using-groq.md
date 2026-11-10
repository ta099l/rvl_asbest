# Trying James with Groq

Groq is optional. The app continues to use its saved replay answers by default. The Groq client uses Python's standard library, so it adds no package dependency.

## Before you start

- Use only fictional data from this repository until RVL and the coach approve the provider and data scope.
- Have the project checked out on your computer and open a terminal in the project folder. Use Bash/WSL if your prompt looks like `tasnim@...:~/rvl_asbest$`; use PowerShell if it starts with `PS`.
- The current startup loads the fictional demo report, so selecting Groq may make a model call as the app starts.

## 1. Create your Groq API key

1. Sign in or create an account at [GroqCloud](https://console.groq.com/).
2. Open [API Keys](https://console.groq.com/keys).
3. Select **Create API Key**, name it something like `james-fictional-test`, and create it.
4. Copy the key when Groq displays it. Keep it private; do not paste it into chat, source code, a committed file, or a screenshot.

If Groq only shows the key once, save it in a password manager. You can revoke it and create another if it is exposed.

## Bash / WSL steps

In WSL, go to the project and activate its virtual environment:

```bash
cd ~/rvl_asbest
source .venv/bin/activate
```

If `.venv` does not exist yet, create it first:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pdfplumber reportlab pillow
```

Enter your key without displaying it, then run the fictional test sets against both models:

```bash
read -s -p "Groq API key: " GROQ_API_KEY
printf '\n'
export GROQ_API_KEY
for model in openai/gpt-oss-20b openai/gpt-oss-120b; do
    python3 -m ai.james_ai.compare --provider groq --model "$model" --set dev --pause 8 --save
    python3 -m ai.james_ai.compare --provider groq --model "$model" --set dev2 --pause 8 --save
    python3 -m ai.james_ai.compare --provider groq --model "$model" --set dev3 --pause 8 --save
done
unset GROQ_API_KEY
```

If a command stops early, clear the key with `unset GROQ_API_KEY`. To run the app itself with Groq, enter the key again and use:

```bash
read -s -p "Groq API key: " GROQ_API_KEY
printf '\n'
export GROQ_API_KEY
JAMES_AI_PROVIDER=groq JAMES_GROQ_MODEL=openai/gpt-oss-20b python3 app/server.py --db james-groq.db
unset GROQ_API_KEY
```

Open http://127.0.0.1:8000 and stop the server with Ctrl+C. Startup loads the fictional demo report and may make a Groq call.

## Windows PowerShell alternative

### Prepare the project terminal

In PowerShell, change to the James project folder. If the virtual environment already exists, use its Python directly:

```powershell
$py = ".\.venv\Scripts\python.exe"
```

If it does not exist yet, create it and install the project packages:

```powershell
python -m venv .venv
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install pdfplumber reportlab pillow
```

The Groq client itself uses Python's standard library; this is the app's existing setup.

### Run the model comparison

The following block asks for the key without displaying it, then compares both models on the fictional development sets. Run it from the project folder:

```powershell
$secureKey = Read-Host "Groq API key" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    foreach ($model in @("openai/gpt-oss-20b", "openai/gpt-oss-120b")) {
        & $py -m ai.james_ai.compare --provider groq --model $model --set dev --pause 8 --save
        & $py -m ai.james_ai.compare --provider groq --model $model --set dev2 --pause 8 --save
        & $py -m ai.james_ai.compare --provider groq --model $model --set dev3 --pause 8 --save
    }
} finally {
    Remove-Item Env:GROQ_API_KEY -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
```

The comparison reports correct, wrong, safe-abstention and missed-link counts. Groq usage lines report model, token counts, estimated price and elapsed time. Results are saved in `ai/runs/`. Do not use `--set hold` while tuning models or prompts.

### Optionally run the web app with Groq

To try the app itself, run this in the same PowerShell terminal, enter the key again when prompted, and select the model:

```powershell
$secureKey = Read-Host "Groq API key" -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    $env:JAMES_AI_PROVIDER = "groq"
    $env:JAMES_GROQ_MODEL = "openai/gpt-oss-20b"
    & $py app\server.py --db james-groq.db
} finally {
    Remove-Item Env:GROQ_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:JAMES_AI_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:JAMES_GROQ_MODEL -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
}
```

Open http://127.0.0.1:8000. The console window must stay open while the app runs; stop it with Ctrl+C. Startup loads the fictional demo report and may call Groq. The database is local and Git ignores `james-groq.db`.

The client requests strict JSON Schema output and James validates the response again against its own contract. The output format alone cannot prove a link is factually correct.

## Switch back to replay mode

Close the Groq run and start `start_james.bat` normally. Replay mode is the default unless `JAMES_AI_PROVIDER=groq` is set in the current process environment.

See [Groq model selection](groq-model-selection.md) for the current price comparison and evaluation plan. Listed prices may change.
