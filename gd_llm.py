"""Shared LLM provider for Guided Diagnostics chat, warranty story, and plate photos.

Primary is xAI (OpenAI-compatible). Groq is one automatic fallback with the same
messages. No OEM / FACR / Coleman text lives here.

Secrets (Streamlit ``st.secrets`` or environment; never log the values):

- ``XAI_API_KEY`` - primary key
- ``GROQ_API_KEY`` - fallback key
- ``XAI_MODEL`` - default ``grok-4.6``
- ``XAI_BASE_URL`` - default ``https://api.x.ai/v1``
- ``GD_LLM_PRIMARY`` - ``xai`` (default) or ``groq``
"""
from __future__ import annotations

import os
import re

PROVIDER_XAI = "xai"
PROVIDER_GROQ = "groq"
PROVIDER_LABEL = {
    PROVIDER_XAI: "xAI",
    PROVIDER_GROQ: "Groq",
}
KEY_NAME = {
    PROVIDER_XAI: "XAI_API_KEY",
    PROVIDER_GROQ: "GROQ_API_KEY",
}
SDK_MODULE = {
    PROVIDER_XAI: "openai",
    PROVIDER_GROQ: "groq",
}

DEFAULT_XAI_MODEL = "grok-4.6"
DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
# Live Groq chat model. Vision plate reads pass their own Groq vision ids.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

NO_KEY_MESSAGE = (
    "No AI key configured. Add XAI_API_KEY (preferred) or GROQ_API_KEY in Streamlit secrets."
)

# 413 / context overflow must surface so the caller can shrink and retry.
# Do not spend the fallback provider on a payload that is too large for both.
_PAYLOAD_TOO_LARGE_RE = re.compile(
    r"("
    r"\b413\b|"
    r"request too large|"
    r"payload too large|"
    r"request entity too large|"
    r"context[_ ]length|"
    r"maximum context|"
    r"too many tokens|"
    r"token limit|"
    r"reduce the length"
    r")",
    re.I,
)
_NOT_FOUND_RE = re.compile(r"\b404\b|model_not_found|model not found", re.I)
# IndexError is not included: an empty choices list is a bad provider response
# and should fall through to the other provider.
_LOCAL_BUGS = (TypeError, ValueError, KeyError, UnicodeEncodeError, UnicodeDecodeError)

# Set on a successful completion. Not shown to the bay tech.
_last_provider = ""


class LLMProviderError(RuntimeError):
    """User-facing provider failure. ``str(exc)`` is already prefixed and redacted."""


def last_provider() -> str:
    """``xai`` or ``groq`` after the last successful completion; empty before that."""
    return _last_provider


def _clean(val) -> str:
    if val is None:
        return ""
    return str(val).strip()


def default_secret(name: str):
    """Streamlit secret, then environment. Same order as the app's ``_secret``."""
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def _lookup(name: str, secret_fn) -> str:
    fn = secret_fn or default_secret
    try:
        return _clean(fn(name))
    except Exception:
        return ""


def _sdk_installed(module: str) -> bool:
    try:
        __import__(module)
    except ImportError:
        return False
    return True


def provider_order(secret_fn=None) -> list[str]:
    """Primary then fallback. Unknown ``GD_LLM_PRIMARY`` stays on xAI."""
    primary = _lookup("GD_LLM_PRIMARY", secret_fn).lower()
    if primary == PROVIDER_GROQ:
        return [PROVIDER_GROQ, PROVIDER_XAI]
    return [PROVIDER_XAI, PROVIDER_GROQ]


def ai_configured(secret_fn=None) -> bool:
    """True when chat can be attempted.

    An xAI key counts even if the OpenAI SDK failed to import (the call then
    falls through to Groq). A Groq key counts only when the groq package imports,
    matching the v4.17 offline check.
    """
    if _lookup("XAI_API_KEY", secret_fn):
        return True
    if _lookup("GROQ_API_KEY", secret_fn) and _sdk_installed("groq"):
        return True
    return False


def _status_code(exc) -> int | None:
    for obj in (exc, getattr(exc, "response", None)):
        if obj is None:
            continue
        for attr in ("status_code", "status"):
            val = getattr(obj, attr, None)
            if isinstance(val, int):
                return val
    return None


def is_payload_too_large(exc) -> bool:
    if _status_code(exc) == 413:
        return True
    return bool(_PAYLOAD_TOO_LARGE_RE.search(str(exc or "")))


def failure_action(exc) -> str:
    """How to treat one failed provider call.

    ``payload`` - raise now (shrink-and-retry owns HTTP 413).
    ``fatal`` - local programming error; do not call the other provider.
    ``next_model`` - this model id is dead (404); try the next id on the same provider.
    ``switch_provider`` - missing-key is handled by the caller; 401/403, 429,
    other 4xx, 5xx, timeout, and transport switch to the fallback provider.
    Unclassified client errors also switch so a new SDK wording cannot kill a prove path.
    """
    if isinstance(exc, _LOCAL_BUGS) and _status_code(exc) is None and not is_payload_too_large(exc):
        if not _NOT_FOUND_RE.search(str(exc or "")):
            return "fatal"
    if is_payload_too_large(exc):
        return "payload"
    code = _status_code(exc)
    if code == 404 or (code is None and _NOT_FOUND_RE.search(f"{type(exc).__name__} {exc}")):
        return "next_model"
    return "switch_provider"


def _detail(exc) -> str:
    text = str(exc or "").strip() or type(exc).__name__
    code = _status_code(exc)
    if code is not None and str(code) not in text:
        return f"{code} {text}"
    return text


def _redact(text: str, secrets: list[str]) -> str:
    out = text or ""
    for secret in secrets:
        if secret and len(secret) >= 4 and secret in out:
            out = out.replace(secret, "[redacted]")
    return out


def _models_for(provider: str, models: dict | None, secret_fn) -> list[str]:
    supplied = []
    if models and models.get(provider):
        supplied = [_clean(m) for m in models[provider] if _clean(m)]
    if supplied:
        return supplied
    if provider == PROVIDER_XAI:
        return [_lookup("XAI_MODEL", secret_fn) or DEFAULT_XAI_MODEL]
    return [DEFAULT_GROQ_MODEL]


def default_client_factory(provider: str, *, api_key: str, base_url: str):
    if provider == PROVIDER_XAI:
        from openai import OpenAI

        return OpenAI(api_key=api_key, base_url=base_url or DEFAULT_XAI_BASE_URL)
    if provider == PROVIDER_GROQ:
        from groq import Groq

        return Groq(api_key=api_key)
    raise LLMProviderError(f"Unknown LLM provider: {provider}")


def _completion_text(client, *, model: str, messages, temperature: float, max_tokens: int) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def complete_chat(
    messages,
    temperature: float = 0.2,
    max_tokens: int = 1400,
    *,
    secret_fn=None,
    client_factory=None,
    models: dict | None = None,
    empty_is_failure: bool = False,
) -> str:
    """Chat completion. Try the primary provider, then the other one once.

    ``models`` replaces the single default model for a provider (vision plate
    reads pass xAI grok-4.6 first, then the current Groq vision ids). A 404
    tries the next model on that provider. Rate limit, auth, 5xx, timeout, and
    transport skip the rest of that provider and retry the same messages on
    the fallback. The bay sees an error only when both providers fail.
    """
    global _last_provider

    order = provider_order(secret_fn)
    redact = [
        _lookup("XAI_API_KEY", secret_fn),
        _lookup("GROQ_API_KEY", secret_fn),
    ]
    base_url = _lookup("XAI_BASE_URL", secret_fn) or DEFAULT_XAI_BASE_URL
    factory = client_factory or default_client_factory
    errors: list[str] = []

    for provider in order:
        label = PROVIDER_LABEL[provider]
        key = _lookup(KEY_NAME[provider], secret_fn)
        if not key:
            errors.append(f"{label}: missing {KEY_NAME[provider]}")
            continue
        if client_factory is None and not _sdk_installed(SDK_MODULE[provider]):
            errors.append(f"{label}: {SDK_MODULE[provider]} package is not installed")
            continue
        model_ids = _models_for(provider, models, secret_fn)
        if not model_ids:
            errors.append(f"{label}: no model configured")
            continue
        try:
            client = factory(
                provider,
                api_key=key,
                base_url=base_url if provider == PROVIDER_XAI else "",
            )
        except Exception as exc:
            action = failure_action(exc)
            detail = _redact(_detail(exc), redact)
            if action in ("payload", "fatal"):
                raise LLMProviderError(f"{label}: {detail}") from None
            errors.append(f"{label}: {detail}")
            continue

        notes: list[str] = []
        for model in model_ids:
            try:
                text = _completion_text(
                    client,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                action = failure_action(exc)
                detail = _redact(_detail(exc), redact)
                if action == "payload":
                    raise LLMProviderError(f"{label}: {detail}") from None
                if action == "fatal":
                    raise LLMProviderError(f"{label}: {detail}") from None
                if action == "next_model":
                    notes.append(f"{model}: {detail}")
                    continue
                notes.append(detail if len(model_ids) == 1 else f"{model}: {detail}")
                break
            if empty_is_failure and not text:
                notes.append(f"{model}: empty vision response")
                continue
            _last_provider = provider
            return text
        if notes:
            errors.append(f"{label}: " + "; ".join(notes))

    if errors and all(err.startswith("xAI: missing ") or err.startswith("Groq: missing ") for err in errors):
        if len(errors) == len(order):
            raise LLMProviderError(NO_KEY_MESSAGE) from None
    if not errors:
        raise LLMProviderError(NO_KEY_MESSAGE) from None
    raise LLMProviderError(" | ".join(errors)) from None
