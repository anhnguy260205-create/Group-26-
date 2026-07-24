"""Thin, dependency-free LLM wrapper.

Provider order, chosen at call time from the environment:

1. Microsoft Foundry (OpenAI-compatible chat-completions surface) — the primary
   provider, used whenever ``AZURE_AI_ENDPOINT`` + ``AZURE_AI_API_KEY`` are set.
2. Anthropic direct (native Messages API) — fallback if only ``ANTHROPIC_API_KEY``
   is set, so the app still runs without an Azure resource.
3. None — nothing configured, or the network/provider errored.

Every caller MUST handle `None` — the app has to keep working with zero network
access (see the fallback plan in the project spec), so nothing downstream may
assume the LLM answered.
"""

import json
import os
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 8

# --- Microsoft Foundry ---------------------------------------------------------
# AZURE_AI_ENDPOINT may be either the resource base (e.g.
# "https://<resource>.services.ai.azure.com") or a full chat-completions URL; we
# normalise below. AZURE_AI_MODEL is the model / deployment name served by your
# Foundry resource (Claude, GPT, Phi, etc.).
FOUNDRY_DEFAULT_MODEL = "claude-sonnet-4-5"

# --- Anthropic direct (fallback) ----------------------------------------------
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-5"


def _foundry_configured() -> bool:
    return bool(os.environ.get("AZURE_AI_ENDPOINT") and os.environ.get("AZURE_AI_API_KEY"))


def _anthropic_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def is_configured() -> bool:
    """True if any LLM provider is configured. Callers still handle None regardless."""
    return _foundry_configured() or _anthropic_configured()


def active_provider() -> str:
    """Which provider a call would use right now — handy for logging/health checks."""
    if _foundry_configured():
        return "foundry"
    if _anthropic_configured():
        return "anthropic"
    return "none"


def _foundry_url() -> str:
    endpoint = os.environ["AZURE_AI_ENDPOINT"].rstrip("/")
    # Allow passing a fully-formed completions URL through untouched.
    if "chat/completions" in endpoint:
        url = endpoint
    else:
        url = f"{endpoint}/openai/v1/chat/completions"
    # Classic Azure OpenAI deployments want an api-version query param; harmless
    # on the newer v1 surface, so include it when the caller provides one.
    api_version = os.environ.get("AZURE_AI_API_VERSION")
    if api_version and "api-version=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}api-version={api_version}"
    return url


def _post(url: str, headers: dict, body: dict) -> dict | None:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def _complete_foundry(system: str, prompt: str, max_tokens: int) -> str | None:
    key = os.environ["AZURE_AI_API_KEY"]
    model = os.environ.get("AZURE_AI_MODEL", FOUNDRY_DEFAULT_MODEL)
    payload = _post(
        _foundry_url(),
        # Send both auth headers: the classic Azure OpenAI surface reads `api-key`,
        # the newer OpenAI-compatible v1 surface reads the Bearer token. Extra one
        # is ignored, so this works against either without extra config.
        headers={"api-key": key, "authorization": f"Bearer {key}"},
        body={
            "model": model,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
    )
    if not payload:
        return None
    try:
        return payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return None


def _complete_anthropic(system: str, prompt: str, max_tokens: int) -> str | None:
    payload = _post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
        },
        body={
            "model": os.environ.get("ANTHROPIC_MODEL", ANTHROPIC_DEFAULT_MODEL),
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    if not payload:
        return None
    try:
        return payload["content"][0]["text"].strip()
    except (KeyError, IndexError, TypeError):
        return None


def complete(system: str, prompt: str, max_tokens: int = 300) -> str | None:
    """Return a short text completion, or None if no provider is available/erroring.

    Tries Microsoft Foundry first, then Anthropic direct. Never raises — a flaky
    network must never break the intervention flow, only fall back to templated text.
    """
    if _foundry_configured():
        text = _complete_foundry(system, prompt, max_tokens)
        if text:
            return text
        # Foundry configured but unreachable/errored: try Anthropic if we also have it.
    if _anthropic_configured():
        return _complete_anthropic(system, prompt, max_tokens)
    return None
