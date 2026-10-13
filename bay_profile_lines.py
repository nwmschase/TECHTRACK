"""PDF-PROFILE conformance for painted Bay steps (v4.19.59).

Generic rules applied to a step's heading and labeled lines right before
paint. Nothing here knows a brand. Profile labels are Where, Tools, Do this,
Good looks like, Bad looks like, Next (Safety once per section).
"""
from __future__ import annotations

import re

PROFILE_LABELS = ("Where", "Tools", "Do this", "Good looks like", "Bad looks like", "Next", "Safety")
_LABEL_RE = re.compile(r"^([A-Z][A-Za-z /]{1,24}):\s*(.*)$")
_PREP_RE = re.compile(r"\b(?:on|onto|at|under|in|into|to|from|behind)\s+(the\s+[a-z][a-z0-9 -]*)", re.I)
_THE_RE = re.compile(r"\b(the\s+(?:new\s+|old\s+)?[a-z][a-z0-9-]*(?:\s+[a-z][a-z0-9-]*){0,2})", re.I)
_STOP_WORDS = {"off", "on", "away", "back", "up", "down", "out", "in", "one", "a", "until", "with", "while", "to", "time", "times",
               "leaks", "weeps", "drips", "is", "are", "stops", "snaps", "hits", "for", "if", "when", "after", "before", "that", "so"}
CHECK_VERBS = ("check", "look", "listen", "measure", "watch", "test", "confirm", "inspect", "feel")


def _trim_phrase(phrase: str) -> str:
    words = phrase.split()
    out = []
    for index, word in enumerate(words):
        low = word.lower()
        if low in ("and", "or") and out and index + 1 < len(words) and words[index + 1].lower() not in _STOP_WORDS:
            out.append(word)
            continue
        if low in _STOP_WORDS and out:
            break
        out.append(word)
    while out and out[-1].lower() in ("and", "or", "the", "a"):
        out.pop()
    return " ".join(out).strip()


def where_place(where: str) -> str:
    """'The toilet sits on the floor.' -> 'On the floor.' A Where names a place, not a sentence."""
    match = re.match(r"(?i)^the [\w /-]+? (?:sits|is|goes|stays|rests) ((?:on|in|at|under|behind|between) .+)$", (where or "").strip())
    return match.group(1)[:1].upper() + match.group(1)[1:] if match else where


def action_object(action: str) -> str:
    """'Take off the pod rings' -> 'the pod rings'. '' when there is none."""
    text = re.sub(r"[.]+$", "", action or "")
    match = _THE_RE.search(text)
    return _trim_phrase(match.group(1)) if match else ""


def where_from_action(action: str) -> str:
    """A Where line built from the action's own place words."""
    text = re.sub(r"[.]+$", "", action or "")
    places = list(_PREP_RE.finditer(text))
    phrase = _trim_phrase(places[-1].group(1)) if places else action_object(text)
    if not phrase:
        return ""
    return f"At {phrase}."


def _plural(noun_phrase: str) -> bool:
    words = noun_phrase.lower().split()
    if not words:
        return False
    if " and " in f" {noun_phrase.lower()} ":
        return True
    last = words[-1]
    return last.endswith("s") and not last.endswith(("ss", "us", "is"))


def fix_agreement(sentence: str) -> str:
    """'The pod rings is on' -> 'are on'. 'The seal and spring is off' -> 'are off'."""

    def repl(match):
        subject, verb = match.group(1), match.group(2)
        if re.search(r"\b(?:are|is|was|were|has|have)\b", subject):
            return match.group(0)
        if _plural(re.sub(r"^the\s+", "", subject, flags=re.I)):
            return f"{subject} {'are' if verb == 'is' else 'were'}"
        return match.group(0)

    return re.sub(r"\b(The\s+[a-z][a-z -]*?)\s+(is|was)\b", repl, sentence or "")


def fix_letter_labels(sentence: str, action: str) -> str:
    """Keep 'clamp A' as written in the action ('the new clamp a is on' -> 'clamp A')."""
    out = sentence
    for word, letter in re.findall(r"\b([a-z]{3,})\s+([A-Z])\b", action or ""):
        out = re.sub(rf"\b({word})\s+{letter.lower()}\b", rf"\1 {letter}", out)
    return out


def fix_vague_it(sentence: str, subject: str) -> str:
    """'It is back on.' -> 'The bolt covers are back on.'"""
    if not subject or not re.match(r"^It\b", sentence or ""):
        return sentence
    rest = sentence[2:]
    return fix_agreement(subject[:1].upper() + subject[1:] + rest)


def resolve_action_it(action: str, previous_object: str) -> str:
    """'Tighten it with new clamp C' -> 'Tighten the new flush hose with new clamp C'."""
    if not previous_object:
        return action
    return re.sub(r"^(\w+)\s+it\b", lambda m: f"{m.group(1)} {previous_object}", action or "", count=1)


def _sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text[:1].upper() + text[1:] if text else text


def conform_lines(
    heading: str,
    lines: list[str],
    *,
    previous_where: str = "",
    previous_object: str = "",
    next_action: str = "",
    diagnosis: bool = False,
    figure_ref: str = "",
) -> tuple[str, list[str]]:
    """Return (heading, lines) in profile order with only profile labels."""
    head_m = re.match(r"^(Step\s+\d+:\s*)(.*)$", heading or "")
    prefix, action = (head_m.group(1), head_m.group(2)) if head_m else ("", heading or "")
    action = resolve_action_it(action, previous_object)
    subject = action_object(action)
    fields: dict[str, list[str]] = {}
    order: list[str] = []
    do_items: list[str] = []
    fail = ""
    in_do = False
    for line in lines or []:
        if line == "Do this:":
            in_do = True
            continue
        if in_do and re.match(r"^\d+\.\s", line):
            item = re.sub(r"^\d+\.\s*", "", line)
            do_items.append(_sentence(resolve_action_it(item.rstrip("."), previous_object)))
            continue
        in_do = False
        match = _LABEL_RE.match(line)
        if not match:
            continue
        label, value = match.group(1), match.group(2)
        if label == "If it fails":
            fail = value
            continue
        if label not in PROFILE_LABELS:
            continue
        if label == "Safety" and action and value.lower().startswith(action.lower().rstrip(".")[:18].lower()):
            continue  # restating the step's own action is not a safety note
        fields.setdefault(label, []).append(value)
        if label not in order:
            order.append(label)
    where = where_place((fields.get("Where") or [""])[0]) or where_from_action(action) or previous_where
    if figure_ref and figure_ref.lower() not in where.lower():
        where = f"{_sentence(where)} See {figure_ref}." if where else f"See {figure_ref}."
    for key in ("Good looks like", "Bad looks like"):
        if key in fields:
            fields[key] = [
                fix_agreement(fix_vague_it(fix_letter_labels(_sentence(v), action), subject)) for v in fields[key]
            ]
    nxt = (fields.get("Next") or [""])[0]
    if next_action and not diagnosis:
        nxt = _sentence(next_action)
    if diagnosis and fail:
        nxt = f"{_sentence(nxt)} {_sentence(fail)}".strip()
    out: list[str] = []
    if fields.get("Safety"):
        out.append("Safety: " + " ".join(_sentence(v) for v in fields["Safety"]))
    if where:
        out.append(f"Where: {_sentence(where)}")
    if fields.get("Tools"):
        out.append(f"Tools: {_sentence(fields['Tools'][0])}")
    if do_items:
        out.append("Do this:")
        out.extend(f"{i}. {item}" for i, item in enumerate(do_items, 1))
    for key in ("Good looks like", "Bad looks like"):
        for value in fields.get(key) or []:
            out.append(f"{key}: {value}")
    if nxt:
        out.append(f"Next: {_sentence(nxt)}")
    new_heading = f"{prefix}{action[:1].upper() + action[1:] if action else action}"
    return new_heading, out


def end_state(step_lines: list[str]) -> str:
    for line in step_lines:
        if line.startswith("Good looks like:"):
            return re.sub(r"\s+", " ", line.split(":", 1)[1]).strip().lower().rstrip(".")
    return ""


def drop_duplicate_removals(steps: list[dict], good_of) -> list[dict]:
    """Two removal steps that end in the same state ('The cover is off') are one step.

    The earlier, vaguer one goes; the later one carries the how.
    """
    keep = []
    for index, step in enumerate(steps):
        state = good_of(step)
        if state and re.search(r"\bis off\b|\bare off\b", state) and step.get("section") == "removal":
            later = [good_of(other) for other in steps[index + 1:index + 4] if other.get("section") == "removal"]
            if state in later:
                continue
        keep.append(step)
    return keep


def before_conflicts(before: list[str], actions: list[str]) -> list[str]:
    """Before-you-start lines that a later step contradicts (leave X in place vs lift X)."""
    bad = []
    blob = " ".join(a.lower() for a in actions)
    for item in before or []:
        match = re.search(r"\b(?:leave|keep)\s+the\s+([a-z]+)\s+in place|\bskip\s+remov\w*\s+(?:the\s+)?([a-z]+)", item, re.I)
        if not match:
            continue
        noun = (match.group(1) or match.group(2) or "").lower()
        if re.search(rf"\b(?:lift|remove|take off|pull)\b[^.]*\b{noun}\b", blob):
            bad.append(item)
    return bad
