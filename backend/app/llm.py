"""Thin, dependency-free LLM wrapper.

Provider order, chosen at call time from the environment:

1. Microsoft Foundry (OpenAI-compatible chat-completions surface) — the primary
   provider, used whenever ``AZURE_AI_ENDPOINT`` + ``AZURE_AI_API_KEY`` are set.
2. Anthropic direct (native Messages API) — fallback if only ``ANTHROPIC_API_KEY``
   is set, so the app still runs without an Azure resource.
3. None — nothing configured, or the network/provider errored.

Every caller MUST handle `None` — the app has to keep working with zero network
access (see the fallback plan in the project spec), so nothing downstream may
assume an LLM answered. `complete()` returns (text, provider) so callers can
record which provider actually generated a given piece of text — not just which
one was configured, since a configured-but-failing Foundry call still falls
through to Anthropic underneath.

Environment variables:
  AZURE_AI_ENDPOINT     Resource base (e.g. "https://<resource>.services.ai.azure.com")
                        or a full chat-completions URL — normalised below either way.
  AZURE_AI_API_KEY      Key for that Foundry resource.
  AZURE_AI_MODEL        Model / deployment served by your resource for the "deep" tier --
                        reasoning-heavy calls like the capacity forecast.
                        (default: claude-sonnet-4-5). Examples: claude-sonnet-4-5, gpt-4o.
  AZURE_AI_MODEL_FAST   Model / deployment for the "fast" tier -- short conversational text
                        like the Companion's opening line, where latency matters more than
                        depth. (default: claude-haiku-4-5). Optional; falls back to the deep
                        model if unset, so a single-deployment resource still works.
  AZURE_AI_API_VERSION  Only needed for classic Azure OpenAI deployment endpoints
                        (e.g. 2024-10-21). Leave unset on the newer /openai/v1 surface.

  ANTHROPIC_API_KEY     Falls back to Claude directly if Foundry isn't configured
                        or a Foundry call fails.
  ANTHROPIC_MODEL       Optional override (default: claude-sonnet-5).
"""

import json
import os
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 8

# --- Microsoft Foundry ---------------------------------------------------------
# Model routing. Both tiers hit the SAME Foundry endpoint and key -- only the model name
# changes -- so short interactive text can be served by a small fast model while the
# reasoning-heavy forecast goes to a larger one, without a second provider or second
# integration. Callers pick a tier; nothing else about the call changes.
FOUNDRY_DEFAULT_MODEL = "claude-sonnet-4-5"
FOUNDRY_FAST_MODEL = "claude-haiku-4-5"
DEEP_TIER = "deep"
FAST_TIER = "fast"

# --- Anthropic direct (fallback) ------------------------------------------------
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
    """Which provider a call would attempt first right now — handy for a health check.
    Not a guarantee of which provider will actually answer; complete()'s returned
    provider label is the source of truth for that."""
    if _foundry_configured():
        return "foundry"
    if _anthropic_configured():
        return "anthropic"
    return "none"


def _foundry_model(tier: str) -> str:
    """Resolve a tier to a concrete deployment name.

    The fast tier deliberately falls back to the deep model when AZURE_AI_MODEL_FAST isn't
    set, so a resource with only one deployment keeps working -- routing is an optimisation,
    never a requirement.
    """
    deep = os.environ.get("AZURE_AI_MODEL", FOUNDRY_DEFAULT_MODEL)
    if tier == FAST_TIER:
        return os.environ.get("AZURE_AI_MODEL_FAST") or deep
    return deep


def routing() -> dict:
    """What a call would use right now, per tier. Exposed on /health for debugging."""
    if not _foundry_configured():
        return {"provider": active_provider(), "fast": None, "deep": None}
    return {
        "provider": "foundry",
        "fast": _foundry_model(FAST_TIER),
        "deep": _foundry_model(DEEP_TIER),
    }


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


def _complete_foundry(system: str, prompt: str, max_tokens: int, tier: str) -> str | None:
    key = os.environ["AZURE_AI_API_KEY"]
    model = _foundry_model(tier)
    payload = _post(
        _foundry_url(),
        # Send both auth headers: the classic Azure OpenAI surface reads `api-key`,
        # the newer OpenAI-compatible v1 surface reads the Bearer token. The extra
        # one is ignored, so this works against either without extra config.
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


def complete(
    system: str, prompt: str, max_tokens: int = 300, tier: str = DEEP_TIER
) -> tuple[str, str] | None:
    """Return (text, provider) — provider is "foundry" or "anthropic" — or None if
    no provider is configured/reachable. Never raises — a flaky network must never
    break the intervention flow, only fall back to templated text.

    `tier` is "fast" for short interactive text or "deep" for reasoning-heavy calls. It
    selects the Foundry deployment; the Anthropic fallback ignores it.
    """
    if _foundry_configured():
        text = _complete_foundry(system, prompt, max_tokens, tier)
        if text:
            return text, "foundry"
        # Foundry configured but unreachable/errored: try Anthropic if we also have it.
    if _anthropic_configured():
        text = _complete_anthropic(system, prompt, max_tokens)
        if text:
            return text, "anthropic"
    return None
