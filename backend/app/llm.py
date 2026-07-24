"""Thin, dependency-free Anthropic API wrapper.

Every caller MUST handle `None` — the app has to keep working with zero network
access (see the fallback plan in the project spec), so nothing downstream may
assume the LLM answered.
"""

import json
import os
import urllib.error
import urllib.request

MODEL = "claude-sonnet-5"
API_URL = "https://api.anthropic.com/v1/messages"
TIMEOUT_SECONDS = 8


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def complete(system: str, prompt: str, max_tokens: int = 300) -> str | None:
    """Return a short text completion, or None if the LLM is unavailable/unconfigured/erroring."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    body = json.dumps(
        {
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
        return payload["content"][0]["text"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError):
        return None
