"""Shared LLM provider for Guided Diagnostics chat, warranty story, and plate photos.

Guided Diagnostics turns use ``respond`` (xAI Responses API, xAI only, no Groq fallback, 240 s a round).
The story and plate photos use ``complete_chat``: xAI first, Groq one automatic fallback with the same
messages. No OEM / FACR / Coleman text lives here.

Secrets (Streamlit ``st.secrets`` or environment; never log the values):

- ``XAI_API_KEY`` - primary key
- ``GROQ_API_KEY`` - story / plate fallback key
- The model is set in code only: ``DEFAULT_XAI_MODEL`` (grok-4.3). v4.20.9: the ``XAI_MODEL`` secret is no longer read.
- ``XAI_BASE_URL`` - default ``https://api.x.ai/v1``
- ``GD_LLM_PRIMARY`` - ``xai`` (default) or ``groq``
"""
from __future__ import annotations

import os
import re
import threading

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.20.13"

# Guided Diagnostics ask turns: no token cap and no reasoning-effort setting (None = the provider's own defaults).
GD_ASK_MAX_TOKENS = None
GD_ASK_REASONING_EFFORT = None

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

DEFAULT_XAI_MODEL = "grok-4.3"  # Chase: Grok 4.3 at go-live (readiness #34). v4.20.9: the ONE source of the model; the
# XAI_MODEL secret is not read (live GD turn logs 11/27 all show grok-4.3, so nothing changes). Printed in TT_STARTUP.
DEFAULT_XAI_BASE_URL = "https://api.x.ai/v1"
# Live Groq chat model. Vision plate reads pass their own Groq vision ids.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

# Healthy GD turns on this app finish in about 21–100s. The OpenAI SDK
# default is 600s with 2 retries (about 30 minutes) and Groq's default is 60s
# with 2 retries. A stuck socket then never reaches the fallback, and the
# Streamlit script stays on "Running" / Stop until the tech reloads.
# One bounded attempt per provider; the provider loop is the only retry.
REQUEST_TIMEOUT_SEC = 150.0
CONNECT_TIMEOUT_SEC = 10.0
# Wall clock sits just past the HTTP read timeout so a working socket timeout
# surfaces as the SDK error. If the SDK timeout does not fire, the wall clock
# still unblocks the Streamlit run.
DEADLINE_SLACK_SEC = 5.0

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


class LLMProviderError(RuntimeError):
    """User-facing provider failure. ``str(exc)`` is already prefixed and redacted.
    v4.20.9: ``kind`` ("timeout" / "xai_error" / "no_key") and ``status`` (the HTTP status code or None) say what failed,
    so the app can tell the tech the real reason (gd_errors)."""

    def __init__(self, message="", kind="xai_error", status=None):
        super().__init__(message)
        self.kind = kind
        self.status = status


class LLMTimeoutError(TimeoutError):
    """The provider did not answer within ``REQUEST_TIMEOUT_SEC``."""


TIMEOUT_RETRY_SENTENCE = (
    "The AI took too long and was stopped. Send the same message again."
)


_last_usage: dict = {}


def _record_usage(response, model: str = "") -> None:
    """Keep token counts from the last completion for GD cost logging."""
    global _last_usage
    try:
        u = getattr(response, "usage", None)
        details = getattr(u, "prompt_tokens_details", None)
        out_details = getattr(u, "completion_tokens_details", None)
        _last_usage = {
            "model": model or "",
            "prompt_tokens": int(getattr(u, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(u, "completion_tokens", 0) or 0),
            "cached_tokens": int(getattr(details, "cached_tokens", 0) or 0) if details else 0,
            "reasoning_tokens": int(getattr(out_details, "reasoning_tokens", 0) or 0) if out_details else 0,
        }
    except Exception:
        _last_usage = {"model": model or ""}


def last_usage() -> dict:
    """Token usage from the last successful completion (may be empty)."""
    return dict(_last_usage)




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
        return [DEFAULT_XAI_MODEL]     # v4.20.9: the code is the one source of the model (no XAI_MODEL secret)
    return [DEFAULT_GROQ_MODEL]


def _client_timeout(provider: str):
    """Read budget for one attempt. Connect fails faster than a reasoning turn."""
    read = float(REQUEST_TIMEOUT_SEC)
    connect = float(CONNECT_TIMEOUT_SEC)
    if provider == PROVIDER_XAI:
        try:
            import httpx2

            return httpx2.Timeout(read, connect=connect)
        except Exception:
            return read
    try:
        import httpx

        return httpx.Timeout(read, connect=connect)
    except Exception:
        return read


def default_client_factory(provider: str, *, api_key: str, base_url: str):
    timeout = _client_timeout(provider)
    if provider == PROVIDER_XAI:
        from openai import OpenAI

        return OpenAI(
            api_key=api_key,
            base_url=base_url or DEFAULT_XAI_BASE_URL,
            timeout=timeout,
            max_retries=0,
        )
    if provider == PROVIDER_GROQ:
        from groq import Groq

        return Groq(api_key=api_key, timeout=timeout, max_retries=0)
    raise LLMProviderError(f"Unknown LLM provider: {provider}")


def _deadline_sec() -> float:
    return float(REQUEST_TIMEOUT_SEC) + float(DEADLINE_SLACK_SEC)


def _timeout_phrase() -> str:
    seconds = float(REQUEST_TIMEOUT_SEC)
    shown = str(int(seconds)) if seconds >= 10 else f"{seconds:.1f}"
    return f"timed out after {shown}s"


def _run_with_deadline(fn, timeout_sec: float):
    """Run ``fn`` on a daemon thread so a stuck SDK call cannot block forever.

    ``ThreadPoolExecutor.shutdown(wait=True)`` would wait out the hung call and
    undo the deadline. The thread is a daemon; the HTTP timeout should still
    end it. Streamlit APIs are not called from the thread.
    """
    box: dict = {}

    def runner():
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=runner, name="gd-llm", daemon=True)
    thread.start()
    thread.join(timeout_sec)
    if thread.is_alive():
        raise LLMTimeoutError(_timeout_phrase())
    if "error" in box:
        raise box["error"]
    return box.get("value")


def _completion_text(
    client,
    *,
    model: str,
    messages,
    temperature: float,
    max_tokens: int | None,
    extra_body: dict | None = None,
) -> str:
    def _call():
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if extra_body:
            kwargs["extra_body"] = extra_body
        response = client.chat.completions.create(**kwargs)
        _record_usage(response, model)
        content = response.choices[0].message.content
        return (content or "").strip()

    text = _run_with_deadline(_call, _deadline_sec())
    return (text or "").strip()


def _raise_provider_errors(errors: list[str]) -> None:
    text = " | ".join(errors)
    if any("timed out" in err.lower() for err in errors):
        text = text.rstrip(".") + ". " + TIMEOUT_RETRY_SENTENCE
    raise LLMProviderError(text)


def complete_chat(
    messages,
    temperature: float = 0.2,
    max_tokens: int | None = 1400,
    *,
    secret_fn=None,
    client_factory=None,
    models: dict | None = None,
    empty_is_failure: bool = False,
    reasoning_effort: str | None = None,
    providers: list | None = None,
) -> str:
    """Chat completion. Try the primary provider, then the other one once.

    ``models`` replaces the single default model for a provider (vision plate
    reads pass the xAI vision ids first, then the current Groq vision ids). A 404
    tries the next model on that provider. Rate limit, auth, 5xx, timeout, and
    transport skip the rest of that provider and retry the same messages on
    the fallback. ``providers`` limits the attempt list. Step photos pass
    ``["xai"]`` so Groq, including the retired llama-4-scout id, is not called.
    Each attempt is bounded by ``REQUEST_TIMEOUT_SEC`` with SDK
    retries off, so a stuck call falls through or raises instead of hanging
    the Streamlit run. The bay sees an error only when both providers fail.
    """

    order = list(providers) if providers else provider_order(secret_fn)
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
                extra_body = None
                if reasoning_effort and provider == PROVIDER_XAI:
                    extra_body = {"reasoning_effort": reasoning_effort}
                text = _completion_text(
                    client,
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_body=extra_body,
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
            return text
        if notes:
            errors.append(f"{label}: " + "; ".join(notes))

    if errors and all(err.startswith("xAI: missing ") or err.startswith("Groq: missing ") for err in errors):
        if len(errors) == len(order):
            raise LLMProviderError(NO_KEY_MESSAGE) from None
    if not errors:
        raise LLMProviderError(NO_KEY_MESSAGE) from None
    _raise_provider_errors(errors)


# ---------------- Guided Diagnostics with tools (branch grok-search, Chase 2026-10-24) ----------------
# Grok gets our client-side library tools (function tools, run in gd_tools) and xAI's built-in web search (server-side,
# runs inside the same call) in ONE request, on the xAI Responses API. Shapes from the official docs (read 2026-10-24):
#   https://docs.x.ai/developers/tools/advanced-usage   "Mixing Server-Side and Client-Side Tools"
#   https://docs.x.ai/developers/tools/function-calling  function tool shape, function_call / function_call_output items
#   https://docs.x.ai/developers/tools/web-search        {"type": "web_search"}
#   https://docs.x.ai/developers/tools/citations         url_citation annotations; include=["no_inline_citations"]
#   https://docs.x.ai/developers/rest-api-reference/inference/responses   usage fields (cost_in_usd_ticks, ...)
# Built-in web search runs on xAI's servers inside the call; a function call pauses the call and comes back here. The
# turn loop (gd_turn) runs the function, appends a function_call_output item and calls again with the whole input list
# (the "encrypted content" pattern: include reasoning.encrypted_content and send response.output back in).
# Chat Completions (complete_chat above) stays for the story, the plate photos and the Groq fallback.

# A call with server-side web searches can run longer than a plain chat call; one bounded attempt, no retries.
TOOL_REQUEST_TIMEOUT_SEC = 240.0
# Inline [[N]](url) links are left out of the reply text so they cannot land inside the JSON state block; the sources
# still come back as url_citation annotations (docs: citations page).
RESPONSES_INCLUDE = ["reasoning.encrypted_content", "no_inline_citations"]


def _dump(item) -> dict:
    if isinstance(item, dict):
        return dict(item)
    for name in ("model_dump", "dict"):
        fn = getattr(item, name, None)
        if callable(fn):
            try:
                return fn(exclude_none=True)
            except TypeError:
                return fn()
    return dict(getattr(item, "__dict__", {}) or {})


def parse_response(response) -> dict:
    """Responses API result -> {text, calls, output, web_sources, server_tools, usage, id}.
    calls: [{call_id, name, arguments}] (client-side function calls to run here)
    output: the response's output items as dicts, to send back in the next call's input
    web_sources: [{url, title}] from url_citation annotations
    server_tools: [{type, action}] for the server-side web_search_call items (what Grok searched)."""
    data = _dump(response)
    out = [_dump(i) for i in (data.get("output") or [])]
    text, calls, web, server = "", [], [], []
    for item in out:
        t = item.get("type")
        if t == "function_call":
            calls.append({"call_id": item.get("call_id") or item.get("id") or "", "name": item.get("name") or "",
                          "arguments": item.get("arguments") or "{}"})
        elif t == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text"):
                    text += c.get("text") or ""
                for a in c.get("annotations") or []:
                    if a.get("type") == "url_citation" and a.get("url"):
                        web.append({"url": a["url"], "title": a.get("title") or ""})
        elif t and t.endswith("_call"):
            server.append({"type": t, "action": item.get("action") or {}, "status": item.get("status") or ""})
    u = data.get("usage") or {}
    ind, outd = u.get("input_tokens_details") or {}, u.get("output_tokens_details") or {}
    usage = {"model": data.get("model") or "", "prompt_tokens": int(u.get("input_tokens") or 0),
             "completion_tokens": int(u.get("output_tokens") or 0), "cached_tokens": int(ind.get("cached_tokens") or 0),
             "reasoning_tokens": int(outd.get("reasoning_tokens") or 0),
             "server_side_tools": int(u.get("num_server_side_tools_used") or 0), "sources": int(u.get("num_sources_used") or 0)}
    if u.get("cost_in_usd_ticks") is not None:
        usage["cost_in_usd_ticks"] = int(u.get("cost_in_usd_ticks") or 0)
    seen = set()
    web = [w for w in web if not (w["url"] in seen or seen.add(w["url"]))]
    return {"text": text.strip(), "calls": calls, "output": out, "web_sources": web, "server_tools": server, "usage": usage,
            "id": data.get("id") or ""}


# v4.20.7 (Chase 2026-11-28 t1713u): the Guided Diagnostics answer call runs at xAI's recommended temperature (0.7; xAI's
# best-practices page says quality usually drops far from it). Reasoning effort is still the provider default (not set).
GD_RESPOND_TEMPERATURE = 0.7


def respond(input_items, tools, *, tool_choice=None, secret_fn=None, client_factory=None, model=None,
            temperature: float = GD_RESPOND_TEMPERATURE, cache_key: str | None = None) -> dict:
    """One Grok call on the xAI Responses API with our function tools + built-in web search. Returns parse_response().
    No token cap and no reasoning-effort setting (the provider's defaults). xAI only: Groq has no built-in web search."""
    global _last_usage
    key = _lookup("XAI_API_KEY", secret_fn)
    if not key:
        raise LLMProviderError(NO_KEY_MESSAGE, kind="no_key")
    redact = [key]
    base_url = _lookup("XAI_BASE_URL", secret_fn) or DEFAULT_XAI_BASE_URL
    model = model or DEFAULT_XAI_MODEL     # v4.20.9: the code is the one source of the model (no XAI_MODEL secret)
    factory = client_factory or default_client_factory
    try:
        client = factory(PROVIDER_XAI, api_key=key, base_url=base_url)
    except Exception as exc:
        raise LLMProviderError(f"xAI: {_redact(_detail(exc), redact)}", status=_status_code(exc)) from None
    kwargs = {"model": model, "input": list(input_items), "tools": list(tools or []), "temperature": temperature,
              "include": list(RESPONSES_INCLUDE)}
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    if cache_key:
        # v4.20.10: xAI prompt_cache_key (docs.x.ai prompt caching): same key = same server = the cached prefix is found.
        # A random per-job id, never a secret; sent through extra_body so older SDK versions accept it.
        kwargs["extra_body"] = {"prompt_cache_key": str(cache_key)}

    def _call():
        return client.responses.create(**kwargs)
    try:
        response = _run_with_deadline(_call, float(TOOL_REQUEST_TIMEOUT_SEC) + float(DEADLINE_SLACK_SEC))
    except LLMTimeoutError:
        raise LLMProviderError(f"xAI: timed out after {int(TOOL_REQUEST_TIMEOUT_SEC)}s. " + TIMEOUT_RETRY_SENTENCE,
                               kind="timeout") from None
    except Exception as exc:
        kind = "timeout" if "timeout" in type(exc).__name__.lower() else "xai_error"
        raise LLMProviderError(f"xAI: {_redact(_detail(exc), redact)}", kind=kind, status=_status_code(exc)) from None
    got = parse_response(response)
    _last_usage = dict(got["usage"])
    return got
