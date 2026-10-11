"""Optional step photos in Guided Diagnostics.

The tech can type the finding. A photo is sent only to xAI vision.
A retired Groq llama-4-scout id is never used. The reply states only what
the model returned. An unclear photo does not become a guessed scene.
"""
from __future__ import annotations

import base64
import contextvars
import json
import re

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.19.46"

# Groq retired this id (HTTP 404). Step photos do not call Groq at all.
DEAD_GROQ_SCOUT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
XAI_VISION_MODELS = ("grok-4.6", "grok-2-vision-1212")
XAI_PROVIDERS = ("xai",)

_REVIEW = contextvars.ContextVar("gd_step_photo_review", default=None)

_SUBJECTS = (
    ("meter", re.compile(r"\b(?:meter|voltage|ohm|ohms|gauge|\d+\s*psi|reading)\b", re.I)),
    ("tag", re.compile(r"\b(?:data plate|rating plate|model tag|nameplate|the tag)\b", re.I)),
    ("connector", re.compile(r"\b(?:connector|connection|clamp|fitting|supply line)\b", re.I)),
    ("leak", re.compile(r"\b(?:leak|leaks|leaking|weep|weeps|weeping|drip)\b", re.I)),
    ("part", re.compile(r"\b(?:part|valve|cartridge|pedal|breaker|seal|retainer)\b", re.I)),
)
_SUBJECT_LABEL = {
    "meter": "meter reading",
    "tag": "tag",
    "connector": "connector",
    "leak": "leak",
    "part": "part",
}
_CONFIRM_WORD_RE = re.compile(
    r"\b(?:photo|picture|sent|attached|yes|done|ok|okay|here)\b",
    re.I,
)


def activate(review):
    return _REVIEW.set(review)


def deactivate(token) -> None:
    _REVIEW.reset(token)


def current():
    return _REVIEW.get()


def photo_subject(text: str) -> str:
    """tag, leak, connector, meter, or part. Empty when a photo does not help."""
    raw = text or ""
    for name, pattern in _SUBJECTS:
        if pattern.search(raw):
            return name
    return ""


def photo_ask_lines(text: str) -> list[str]:
    subject = photo_subject(text)
    label = _SUBJECT_LABEL.get(subject)
    if label:
        first = f"Take a photo of the {label}."
    else:
        first = "Take a photo of this step and send it."
    return [first, "A photo is optional.", "You can type what you see."]


def with_photo_ask(text: str) -> str:
    """Ask for a photo when this check is a tag, leak, connector, meter, or part."""
    raw = text or ""
    if not raw.strip() or "take a photo" in raw.lower():
        return raw
    if not photo_subject(raw):
        return raw
    ask = "\n".join(photo_ask_lines(raw))
    lines = raw.splitlines()
    idx = next((i for i, line in enumerate(lines) if line.startswith("📖")), len(lines))
    lines.insert(idx, ask)
    return "\n".join(lines)


def adjust_latest(latest: str) -> str:
    """Confirm adds what the model saw. A bad photo does not count as the finding."""
    review = current()
    base = latest or ""
    if not review:
        return base
    verdict = (review.get("verdict") or "").strip().lower()
    if verdict == "confirm":
        sees = (review.get("sees") or "").strip()
        if sees and sees not in base:
            return f"{base}\n{sees}".strip()
        return base
    if verdict in ("mismatch", "unclear"):
        return ""
    return base


def parse_vision_review(raw: str) -> dict:
    """Only a real confirm or mismatch keeps the model's sees text.

    Anything else is unclear with an empty sees string. This function never
    writes a scene of its own.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except Exception:
        return {"verdict": "unclear", "sees": ""}
    if not isinstance(data, dict):
        return {"verdict": "unclear", "sees": ""}
    verdict = str(data.get("verdict") or "").strip().lower()
    sees = str(data.get("sees") or "").strip()
    if verdict not in ("confirm", "mismatch", "unclear"):
        return {"verdict": "unclear", "sees": ""}
    if verdict == "unclear" or not sees:
        return {"verdict": "unclear", "sees": ""}
    if sees not in (raw or ""):
        return {"verdict": "unclear", "sees": ""}
    return {"verdict": verdict, "sees": sees}


def vision_prompt(asked: str, typed: str) -> str:
    return (
        "You are checking one shop photo for an RV tech. "
        f"The step asked for this: {(asked or '').strip() or '(no step)'}. "
        f"The tech typed: {(typed or '').strip() or '(nothing)'}. "
        "Return ONLY JSON with keys verdict and sees. "
        "verdict is confirm, mismatch, or unclear. "
        "sees is one short sentence of only what is visible in the photo. "
        "If the photo is blurry, dark, cut off, or you cannot tell, "
        "verdict is unclear and sees is an empty string. "
        "Do not guess. Do not describe anything you cannot see. "
        "confirm means the photo shows the asked step and agrees with the typed finding. "
        "mismatch means the photo shows something else, or it disagrees with the typed finding. "
        "On mismatch, sees must still be only what is visible."
    )


def vision_messages(image_bytes: bytes, mime: str, asked: str, typed: str) -> list:
    mime = (mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    encoded = base64.b64encode(image_bytes or b"").decode("ascii")
    data_url = f"data:{mime};base64,{encoded}"
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": vision_prompt(asked, typed)},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]


def vision_model_ids(secret_fn=None) -> list[str]:
    """xAI vision ids only. llama-4-scout is dropped even if a secret names it."""
    out = []

    def _add(name: str) -> None:
        cleaned = (name or "").strip()
        if not cleaned or DEAD_GROQ_SCOUT_MODEL in cleaned or "llama-4-scout" in cleaned.lower():
            return
        if cleaned not in out:
            out.append(cleaned)

    lookup = secret_fn or (lambda _name: "")
    for key in ("XAI_VISION_MODEL", "XAI_MODEL"):
        try:
            _add(str(lookup(key) or ""))
        except Exception:
            continue
    for model in XAI_VISION_MODELS:
        _add(model)
    return out


def complete_xai_vision(messages, secret_fn=None, complete_fn=None) -> str:
    """One xAI vision call. Groq is not a fallback for this photo."""
    import gd_llm

    fn = complete_fn or gd_llm.complete_chat
    return fn(
        messages,
        temperature=0.0,
        max_tokens=300,
        secret_fn=secret_fn,
        models={"xai": vision_model_ids(secret_fn)},
        empty_is_failure=True,
        providers=list(XAI_PROVIDERS),
    )


def review_step_photo(image_bytes, mime, asked, typed, complete_fn=None) -> dict | None:
    """None when there is no photo. Otherwise confirm, mismatch, or unclear."""
    if not image_bytes:
        return None
    fn = complete_fn or complete_xai_vision
    try:
        raw = fn(vision_messages(image_bytes, mime, asked, typed))
    except Exception:
        return {"verdict": "unclear", "sees": ""}
    return parse_vision_review(raw or "")


def latest_confirms_step(text: str, review) -> bool | None:
    """True or False when a photo decides. None when the text rules apply."""
    if not review:
        return None
    verdict = (review.get("verdict") or "").strip().lower()
    if verdict == "confirm" and (review.get("sees") or "").strip():
        return True
    if verdict in ("mismatch", "unclear"):
        return False
    return None


def present_photo_review(reply: str, review) -> str:
    """State the model sees text, or say the photo cannot be used. Never invent a scene."""
    if not review:
        return reply or ""
    verdict = (review.get("verdict") or "").strip().lower()
    sees = (review.get("sees") or "").strip()
    body = (reply or "").strip()
    if body.startswith("I see:") or body.startswith("This photo is not clear enough.") or body.startswith(
        "I cannot tell what this photo shows."
    ):
        return body
    if verdict == "confirm" and sees:
        sentence = sees if sees.endswith((".", "!", "?")) else f"{sees}."
        return f"I see: {sentence}\n{body}".strip()
    if verdict == "mismatch":
        if sees:
            sentence = sees if sees.endswith((".", "!", "?")) else f"{sees}."
            seen = f"I see: {sentence}"
        else:
            seen = "I cannot tell what this photo shows."
        return (
            f"{seen}\n"
            "This photo does not match the finding.\n"
            "Send another photo, or type what you see.\n"
            f"{body}"
        ).strip()
    return (
        "This photo is not clear enough.\n"
        "I will not guess what it shows.\n"
        "Send another photo, or type what you see.\n"
        f"{body}"
    ).strip()


def history_user_text(typed: str, had_photo: bool, review) -> str:
    """What the next turn may treat as a typed finding."""
    text = (typed or "").strip()
    if not had_photo or not review:
        return text
    verdict = (review.get("verdict") or "").strip().lower()
    if verdict == "confirm" and (review.get("sees") or "").strip():
        sees = review["sees"].strip()
        parts = [part for part in (text, sees, "Yes.") if part]
        kept = []
        for part in parts:
            if part not in kept:
                kept.append(part)
        return "\n".join(kept)
    return "The file did not count."
