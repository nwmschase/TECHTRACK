"""Neutral follow-up when a finished Guided Diagnostics job was not the fix.

The reply rechecks the reading that was supposed to fix the job, then names
the next likely cause. It does not blame the tech or the program, and it does
not ask a check again when that check already passed.
"""
from __future__ import annotations

import re

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.19.56"

BUTTON_MESSAGE = "This wasn't the actual fix."

_REOPEN_RE = re.compile(
    r"wasn['\u2019]?t the(?: actual)? fix"
    r"|not the(?: actual)? fix"
    r"|\bit came back\b"
    r"|\bcame back\b"
    r"|leak came back"
    r"|\bnot fixed\b",
    re.I,
)

_THETFORD_RE = re.compile(r"\bthetford\b|\b42070\b|vacuum breaker|flush lever", re.I)
_SUPPLY_ASK = "check the water supply line connection"


def is_reopen_phrase(text: str) -> bool:
    return bool(_REOPEN_RE.search(text or ""))


def _user_text(history, latest: str) -> str:
    parts = []
    for message in history or []:
        if not isinstance(message, dict):
            continue
        if (message.get("role") or "") == "user":
            parts.append(message.get("content") or "")
    parts.append(latest or "")
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _job_flags(history, latest: str):
    blob = _user_text(history, latest)
    low = blob.lower()
    try:
        from gd_library_coach import _thetford_supply_ok, _thetford_vacuum_bad, _user_blob

        user = _user_blob(history, latest)
        supply_ok = bool(_thetford_supply_ok(user))
        vacuum_bad = bool(_thetford_vacuum_bad(user))
    except Exception:
        supply_ok = bool(re.search(r"supply.{0,48}\b(?:tight|dry|good|ok|okay)\b", low))
        vacuum_bad = bool(re.search(r"vacuum breaker.{0,40}\bleaks?\b", low))
    return low, supply_ok, vacuum_bad


def _is_thetford(history, latest: str, category: str, model: str) -> bool:
    blob = f"{category or ''} {model or ''} {_user_text(history, latest)}"
    return bool(_THETFORD_RE.search(blob))


def _thetford_reply(history, latest: str) -> str:
    """Recheck the vacuum breaker, then the pedal weep on kit 42109.

    A supply connection that already passed is stated and not asked again.
    """
    _low, supply_ok, vacuum_bad = _job_flags(history, latest)
    named_breaker = "vacuum breaker" in _low
    lines = []
    if supply_ok:
        lines.append("Earlier, the supply connection was dry.")
    if named_breaker or vacuum_bad:
        lines.append("Flush once and watch the vacuum breaker.")
        lines.append("A good result is no leak while flushing.")
        lines.append("A bad result is it still leaks while flushing.")
        lines.append("If it is dry, check the pedal for a weep.")
        lines.append("Water valve kit 42109 is the next likely cause.")
    else:
        lines.append("Recheck the last reading you already took.")
        lines.append("Then move to the next likely cause.")
    lines.append("What do you see?")
    if named_breaker or vacuum_bad:
        lines.append("Send a photo of what you see.")
        lines.append("📖 Source: Thetford Water Valve Kit 42109, page 1")
    reply = "\n".join(lines)
    if supply_ok and _SUPPLY_ASK in reply.lower():
        reply = re.sub(re.escape(_SUPPLY_ASK), "the pedal weep", reply, flags=re.I)
    return reply


def _generic_reply() -> str:
    return "\n".join(
        [
            "The earlier result did not hold.",
            "Recheck the last reading before moving on.",
            "Then go to the next likely cause.",
            "What do you see?",
        ]
    )


def neutral_reopen_reply(
    history,
    latest: str,
    category: str = "",
    model: str = "",
) -> str:
    if _is_thetford(history, latest, category, model):
        return _thetford_reply(history, latest)
    return _generic_reply()


def concern_with_finding(concern: str, reason: str) -> str:
    concern = re.sub(r"\s+", " ", (concern or "").strip())
    reason = re.sub(r"\s+", " ", (reason or "").strip())
    if not reason:
        return concern
    if reason.lower() in concern.lower():
        return concern
    if concern:
        return f"{concern} Follow-up: {reason}"
    return reason


def _seed_chunks(category: str, brand: str, model: str, concern: str):
    blob = f"{category} {brand} {model} {concern}"
    if not _THETFORD_RE.search(blob):
        return []
    return [
        {
            "title": "Thetford Style II OM Permanent RV Toilet 42088",
            "brand": "Thetford",
            "keywords": "Thetford 42070 flush lever leak",
            "excerpt": (
                "If the leak persists from the water valve, "
                "the vacuum breaker leaks while flushing."
            ),
            "page": 3,
        }
    ]


def regenerate_bay_pdf(case: dict, history=None, reason: str = "", chunks=None) -> bytes:
    """Build the Bay PDF again with the reopen finding and the repair branches."""
    import bay_procedure as bp

    case = case or {}
    concern = concern_with_finding(case.get("concern") or "", reason)
    brand = case.get("brand") or ""
    model = case.get("model") or ""
    category = case.get("category") or ""
    use_chunks = list(chunks) if chunks is not None else _seed_chunks(category, brand, model, concern)
    proc = bp.compile_bay_procedure(
        concern=concern,
        brand=brand,
        model=model,
        category=category,
        history=history,
        chunks=use_chunks,
    )
    return bp.render_bay_procedure_pdf(proc)
