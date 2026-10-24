"""Good/Bad wording helpers kept for manual_figures.step_body_lines.

The rest of this module (the Bay PDF step conformance) was removed with the
Bay PDF builder (Chase 2026-10-24). Nothing here knows a brand.
"""
from __future__ import annotations

import re


_NEG_WORDS = {"not", "no", "still", "does", "do", "did", "has", "have", "is", "are", "sits", "isnt", "doesnt",
              "off", "on", "up", "down", "out", "in", "a", "the", "an", "any"}


def _words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def bad_negates_good(good: str, bad: str) -> bool:
    """'The clamp has not moved' only negates 'The clamp has moved'. It says nothing new."""
    g = {_ANTONYM.get(_stem(w), _stem(w)) for w in _words_of(good)} - _NEG_WORDS
    b = {_ANTONYM.get(_stem(w), _stem(w)) for w in _words_of(bad)} - _NEG_WORDS
    if not b:
        return True
    return b <= g


# Opposite words count as the same word: 'loose' only negates 'tight'.
_ANTONYM = {"loose": "tight", "stay": "go", "goe": "go", "closed": "open", "unlocked": "lock",
            "missing": "on", "miss": "hit", "moved": "move", "still": "not", "doe": "not"}


def clamp_bad(action: str) -> str:
    """'Tighten the inlet tube with the new clamp A' fails as 'The inlet tube turns under the clamp.'"""
    m = re.match(r"(?i)^tighten (?:the )?(?:new )?(.+?) with (?:the )?(?:new )?clamp\b", (action or "").strip())
    if not m or m.group(1).strip().lower() in ("it", "them"):
        return ""
    return f"The {m.group(1).strip()} turns under the clamp."


