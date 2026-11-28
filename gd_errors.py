"""Guided Diagnostics errors and fallbacks, said plainly and logged (v4.20.9, audit H3 + "no silent fallbacks", Chase t1727u).

  classify(exc)              -> (kind, status)   kind: "timeout" | "xai_error" | "no_key" | "app_bug"
  tech_line(kind, status, exc) -> the short line the tech sees (every one starts with ERROR_PREFIX)
  error_record(exc, where)   -> {type, status, exception, message, traceback} for the GD turn log
  emit(tag, **fields)        -> prints one tagged line to stdout ("GD_ERROR {...}" / "GD_FALLBACK {...}")
  fallback(where, why, exc=None, **fields)
                             -> a quiet fallback: prints GD_FALLBACK and queues it for this run's turn log
  take_fallbacks()           -> the queued fallbacks (the app puts them into the next GD turn log it publishes)
  pending()                  -> True when fallbacks are queued (the app publishes them at once outside a turn)

  TAG_STARTUP -> the tag of the one startup line (fields: gd_turn.startup_fields)

No key values are ever printed: provider messages are already redacted by gd_llm, and redact() masks any secret the app
passes in.
"""
from __future__ import annotations

import json
import threading
import traceback

MODULE_REVISION = "v4.20.9"

ERROR_PREFIX = "Guided Diagnostics did not answer:"
TAG_ERROR = "GD_ERROR"
TAG_FALLBACK = "GD_FALLBACK"
KIND_TIMEOUT, KIND_XAI, KIND_NO_KEY, KIND_BUG = "timeout", "xai_error", "no_key", "app_bug"
_MSG_CAP = 500

_local = threading.local()


def classify(exc) -> tuple:
    """What failed: the AI call timed out, xAI answered with an error (and its status code), no key, or our own code."""
    kind = getattr(exc, "kind", None)
    if kind in (KIND_TIMEOUT, KIND_XAI, KIND_NO_KEY):
        return kind, getattr(exc, "status", None)
    if isinstance(exc, TimeoutError):
        return KIND_TIMEOUT, None
    return KIND_BUG, None


def tech_line(kind: str, status=None, exc=None) -> str:
    if kind == KIND_TIMEOUT:
        return f"{ERROR_PREFIX} the AI took too long and was stopped. Nothing was guessed. Send the same message again."
    if kind == KIND_XAI:
        code = f"xAI error {status}" if status else "xAI error, no status code"
        return f"{ERROR_PREFIX} the AI service sent back an error ({code}). Nothing was guessed. Send the same message again in a minute."
    if kind == KIND_NO_KEY:
        return f"{ERROR_PREFIX} no AI key is set up (XAI_API_KEY). Nothing was guessed. Tell the manager."
    name = type(exc).__name__ if exc is not None else "error"
    return (f"{ERROR_PREFIX} a bug in the app ({name}). Nothing was guessed. It was logged. Send the message again, and "
            f"tell the manager if it happens again.")


def is_error_line(text) -> bool:
    return isinstance(text, str) and text.startswith(ERROR_PREFIX)


def redact(text: str, secrets=()) -> str:
    out = text or ""
    for s in secrets or ():
        if s and len(str(s)) >= 4:
            out = out.replace(str(s), "[redacted]")
    return out


def traceback_summary(exc, frames: int = 4) -> list:
    """The last few frames as 'file:line in function' (no locals, no source text)."""
    tb = traceback.extract_tb(getattr(exc, "__traceback__", None))[-frames:]
    return [f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno} in {f.name}" for f in tb]


def error_record(exc, where: str, secrets=()) -> dict:
    kind, status = classify(exc)
    return {"type": kind, "status": status, "where": where, "exception": type(exc).__name__,
            "message": redact(str(exc), secrets)[:_MSG_CAP], "traceback": traceback_summary(exc)}


def emit(tag: str, **fields) -> str:
    line = f"{tag} " + json.dumps(fields, default=str, sort_keys=True)
    try:
        print(line, flush=True)
    except Exception:   # stdout closed: nothing else can be done, and a log line never breaks the turn
        return ""
    return line


def _queue() -> list:
    q = getattr(_local, "q", None)
    if q is None:
        q = _local.q = []
    return q


def fallback(where: str, why: str, exc=None, secrets=(), **fields) -> dict:
    """A place that carries on without something (no photo read, no picture page, no story...): never quiet."""
    rec = {"where": where, "why": why, **fields}
    if exc is not None:
        rec.update(exception=type(exc).__name__, message=redact(str(exc), secrets)[:_MSG_CAP],
                   traceback=traceback_summary(exc))
    emit(TAG_FALLBACK, **rec)
    _queue().append(rec)
    return rec


def pending() -> bool:
    return bool(_queue())


def take_fallbacks() -> list:
    q = _queue()
    out, q[:] = list(q), []
    return out


TAG_STARTUP = "TT_STARTUP"
