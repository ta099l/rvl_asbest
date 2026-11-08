"""Groq API client for the existing proposal-only AI interface.

The API key is read from the process environment. Request content is never
written to the usage log; only operational metadata and token-based cost are.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional


API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "proposals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "sample": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "confidence": {"anyOf": [
                        {"type": "string", "enum": ["high", "medium", "low"]},
                        {"type": "null"},
                    ]},
                    "reason": {"type": "string"},
                },
                "required": ["n", "sample", "confidence", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["proposals"],
    "additionalProperties": False,
}
PRICES_PER_MILLION = {
    # GroqCloud listed prices checked 2026-11-06. Update if Groq changes them.
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
}

_log = logging.getLogger("james.groq")
if not _log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("Groq usage %(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.INFO)
    _log.propagate = False


class GroqClient:
    """Call Groq chat completions and return the model's raw text response."""

    def __init__(self, model: Optional[str] = None, timeout: Optional[float] = None,
                 prompt_version: Optional[str] = None):
        self.api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY is not set in the environment")
        self.model = model or os.environ.get("JAMES_GROQ_MODEL", DEFAULT_MODEL).strip()
        self.timeout = timeout if timeout is not None else float(os.environ.get("JAMES_GROQ_TIMEOUT", "45"))
        self.prompt_version = prompt_version or os.environ.get("JAMES_GROQ_PROMPT_VERSION", "v1_baseline")
        self.max_completion_tokens = int(os.environ.get("JAMES_GROQ_MAX_COMPLETION_TOKENS", "4096"))

    def complete(self, text: str) -> str:
        """Send one prompt; failures are raised for ai_step to turn into no-link results."""
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "james_link_proposals",
                    "strict": True,
                    "schema": RESPONSE_SCHEMA,
                },
            },
            "max_completion_tokens": self.max_completion_tokens,
        }).encode("utf-8")
        request = urllib.request.Request(
            API_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Do not include the response body: provider errors can echo request details.
            raise RuntimeError(f"Groq returned HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Groq request failed ({type(exc.reason).__name__})") from None

        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("Groq response contained no choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise RuntimeError("Groq response did not contain text")

        usage = payload.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        prices = PRICES_PER_MILLION.get(self.model)
        estimated_cost = None
        if prices and isinstance(input_tokens, int) and isinstance(output_tokens, int):
            estimated_cost = round((input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000, 8)
        record = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provider": "groq",
            "model": self.model,
            "prompt_version": self.prompt_version,
            "prompt_fingerprint": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
            "prompt_characters": len(text),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost_usd": estimated_cost,
            "elapsed_seconds": round(time.monotonic() - start, 3),
        }
        _log.info(json.dumps(record, sort_keys=True))
        return content
