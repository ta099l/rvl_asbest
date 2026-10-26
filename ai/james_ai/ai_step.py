"""The AI step: prompt in, checked proposals out.

    request -> prompt (template from ai/prompts/) -> client.complete(text) -> answer
            -> contract check -> proposals

The model is hidden behind a client with one method, complete(text) -> str, so
no vendor is built in. Until the AI tool is approved, ReplayClient plays back
answers pasted from the prompt lab. When it is approved, only a new client is
written; nothing here changes.

Whatever goes wrong (garbage, an error, no recorded answer), every row becomes
no link with the reason. The step only proposes; an inspector decides.

To get the exact prompt for the prompt lab, with its key for the replay file:
    python3 -m ai.james_ai.ai_step prompt contract/examples/request.json
"""
import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

from .contract import check_request, no_links, validate_response

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = ROOT / "ai" / "prompts"
OUTPUT_FORMAT = "_output_format.txt"
DEFAULT_PROMPT = "v1_baseline"


class Client(Protocol):
    def complete(self, text: str) -> str: ...


@dataclass
class AiRun:
    response: dict              # always follows the contract
    problems: List[str]         # empty when the model's answer was used as is
    prompt_version: str
    prompt_key: str             # fingerprint of the exact prompt text
    answer: Optional[str]       # raw model text, None if no answer came back


def load_template(version: str = DEFAULT_PROMPT, prompts_dir: Path = PROMPTS_DIR) -> str:
    """A prompt version is <version>.txt followed by the shared answer format."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", version):
        raise ValueError(f"not a prompt version name: {version!r}")
    body = (prompts_dir / f"{version}.txt").read_text(encoding="utf-8")
    fmt = (prompts_dir / OUTPUT_FORMAT).read_text(encoding="utf-8")
    for slot in ("{{REGISTER}}", "{{LINES}}"):
        if slot not in body:
            raise ValueError(f"prompt {version} has no {slot}")
    return body.rstrip("\n") + "\n\n" + fmt


def build_prompt(request: dict, version: str = DEFAULT_PROMPT, prompts_dir: Path = PROMPTS_DIR) -> str:
    """Fill the template with the register and the numbered lab lines."""
    check_request(request)
    register = "\n".join(f"{s['code']} | {s['location']} | {s['material']} | {s['colour']}"
                         for s in request["register"])
    lines = "\n".join(f"{r['n']}. {r['raw_id'] or '-'} | {r['description']} | {r['result']}"
                      for r in request["rows"])
    return (load_template(version, prompts_dir)
            .replace("{{REGISTER}}", register).replace("{{LINES}}", lines))


def prompt_key(text: str) -> str:
    """Short fingerprint of a prompt: one changed character gives another key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def propose(request: dict, client: Client, version: str = DEFAULT_PROMPT,
            prompts_dir: Path = PROMPTS_DIR) -> AiRun:
    """Ask the model for proposals and return only what passes the contract."""
    text = build_prompt(request, version, prompts_dir)   # a broken request raises here
    key = prompt_key(text)
    try:
        answer = client.complete(text)
    except Exception as e:  # any client failure must end as no link, never crash the app
        problems = [f"AI call failed ({type(e).__name__}: {e})"]
        why = f"{problems[0]}. No link proposed; link by hand."
        return AiRun(no_links(request, why), problems, version, key, None)
    if not isinstance(answer, str):
        problems = [f"client returned {type(answer).__name__}, not text"]
        why = f"AI answer rejected: {problems[0]}. No link proposed; link by hand."
        return AiRun(no_links(request, why), problems, version, key, None)
    response, problems = validate_response(answer, request)
    return AiRun(response, problems, version, key, answer)


class NoRecordedAnswer(LookupError):
    """The replay file has no answer for this exact prompt."""


class ReplayClient:
    """Plays back answers recorded in the prompt lab, matched on the prompt's key.

    File format (an answer is the model's raw text, or JSON pasted as is):
        {"answers": {"<prompt key>": {"prompt": "v1_baseline", "report_id": "...", "answer": ...}}}
    An answer is only used for the exact prompt it was recorded for, so an old
    answer cannot be replayed for a changed prompt by accident.
    """

    def __init__(self, path: Path):
        with open(path, encoding="utf-8") as f:
            self.answers = json.load(f)["answers"]
        self.prompts: List[str] = []     # what was asked, for checking afterwards

    def complete(self, text: str) -> str:
        self.prompts.append(text)
        key = prompt_key(text)
        if key not in self.answers:
            raise NoRecordedAnswer(f"no recorded answer for prompt {key}")
        answer = self.answers[key]["answer"]
        return answer if isinstance(answer, str) else json.dumps(answer)


class FailingClient:
    """Returns garbage, to show that bad output becomes no link for every row."""

    def __init__(self, answer: str = "Sure! Line 1 is probably S-02, the rest I am not sure about."):
        self.answer = answer

    def complete(self, text: str) -> str:
        return self.answer


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Show the exact prompt for a request, with its replay key.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompt", help="print the filled prompt and its key")
    p.add_argument("request", type=Path, help="a request JSON file, e.g. contract/examples/request.json")
    p.add_argument("--prompt", default=DEFAULT_PROMPT, help="prompt version in ai/prompts/")
    args = ap.parse_args(argv)

    request = json.loads(args.request.read_text(encoding="utf-8"))
    text = build_prompt(request, args.prompt)
    print(text)
    print(f"\n--- prompt {args.prompt}, report {request['report_id']}, key {prompt_key(text)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
