"""Thin, dependency-free LLM wrapper: Microsoft Foundry first, Anthropic as fallback.

Every caller MUST handle `None` — the app has to keep working with zero network
access (see the fallback plan in the project spec), so nothing downstream may
assume an LLM answered. `complete()` returns (text, provider) so callers can
record which provider actually generated a given piece of text.

Environment variables:
  FOUNDRY_ENDPOINT   Full chat-completions URL from the deployment's "Consume"
                     tab in the Microsoft Foundry portal (Azure AI Model
                     Inference API — OpenAI-chat-completions-shaped request/response).
  FOUNDRY_API_KEY    Key for that deployment.
  FOUNDRY_MODEL      Optional — only needed for unified multi-model endpoints
                     that require a "model" field in the request body.

  ANTHROPIC_API_KEY  Falls back to Claude directly if Foundry isn't configured
                     or a Foundry call fails.
"""

import json
import os
import urllib.error
import urllib.request

ANTHROPIC_MODEL = "claude-sonnet-5"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
TIMEOUT_SECONDS = 8


def is_configured() -> bool:
    return bool(
        (os.environ.get("FOUNDRY_ENDPOINT") and os.environ.get("FOUNDRY_API_KEY"))
        or os.environ.get("ANTHROPIC_API_KEY")
    )


def complete(system: str, prompt: str, max_tokens: int = 300) -> tuple[str, str] | None:
    """Return (text, provider) — provider is "foundry" or "anthropic" — or None if
    neither is configured or reachable."""
    for provider, fn in (("foundry", _complete_foundry), ("anthropic", _complete_anthropic)):
        text = fn(system, prompt, max_tokens)
        if text is not None:
            return text, provider
    return None


def _complete_foundry(system: str, prompt: str, max_tokens: int) -> str | None:
    endpoint = os.environ.get("FOUNDRY_ENDPOINT")
    api_key = os.environ.get("FOUNDRY_API_KEY")
    if not endpoint or not api_key:
        return None

    body = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    }
    model = os.environ.get("FOUNDRY_MODEL")
    if model:
        body["model"] = model

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", "api-key": api_key},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
        return payload["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError):
        return None


def _complete_anthropic(system: str, prompt: str, max_tokens: int) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    body = json.dumps(
        {
            "model": ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        ANTHROPIC_API_URL,
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
