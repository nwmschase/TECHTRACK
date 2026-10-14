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
               "leaks", "weeps", "drips", "is", "are", "stops", "snaps", "hits", "for", "if", "when", "after", "before", "that", "so",
               "into", "open", "closed", "around", "over", "across", "through", "place"}
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
    dash_note = ""
    if " - " in action:
        # 'Secure X with two rings - larger on top' : the action, then the detail as its own line.
        action, dash_note = [part.strip() for part in action.split(" - ", 1)]
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
            if dash_note and " - " in item:
                item = item.split(" - ", 1)[0]
                do_items.append(_sentence(item.rstrip(".")))
                do_items.append(_sentence(note_as_action(dash_note, action).rstrip(".")))
                continue
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
    where = first_where(where_place((fields.get("Where") or [""])[0])) or where_from_action(action) or previous_where
    if "Good looks like" in fields:
        moved, rest = split_good_actions(fields["Good looks like"][0])
        if moved:
            do_items.extend(_sentence(m) for m in moved)
            fields["Good looks like"] = [rest] if rest else []
    if fields.get("Good looks like") and fields.get("Bad looks like"):
        good0 = fields["Good looks like"][0]
        fields["Bad looks like"] = [
            b for b in fields["Bad looks like"] if not generic_bad(b) and not bad_negates_good(good0, b)
        ] if not re.match(r"(?i)^confirm\b", action) else fields["Bad looks like"]
    if figure_ref and figure_ref.lower() not in where.lower():
        where = f"{_sentence(where)} See {figure_ref}." if where else f"See {figure_ref}."
    for key in ("Good looks like", "Bad looks like"):
        if key in fields:
            fields[key] = [
                fix_agreement(fix_vague_it(fix_letter_labels(_sentence(v), action), subject)) for v in fields[key]
            ]
    if fields.get("Good looks like") and not fields.get("Bad looks like") and do_items and clamp_bad(do_items[0]):
        fields["Bad looks like"] = [clamp_bad(do_items[0])]
    nxt = (fields.get("Next") or [""])[0]
    if next_action and not diagnosis:
        nxt = _sentence(next_action.split(" - ", 1)[0])
    if diagnosis and (fail or nxt):
        nxt = diagnosis_next(nxt, fail)
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


# ---- v4.19.60: branch-level repairs (Leader rev3 page review) ---------------
_IMPERATIVE = ("flush", "turn", "push", "pull", "press", "run", "open", "close", "tighten", "put", "set", "remove")
_GENERIC_BAD = {"the leak continues", "the leak is still there", "the leak persists", "it still leaks", "it fails"}
_NEG_WORDS = {"not", "no", "still", "does", "do", "did", "has", "have", "is", "are", "sits", "isnt", "doesnt",
              "off", "on", "up", "down", "out", "in", "a", "the", "an", "any"}
_REMOVE_RE = re.compile(r"\b(?:off|remove|removed|take|took|pull|pulled|unhook|out)\b", re.I)
_THROW_RE = re.compile(r"^(?:throw|discard)\b", re.I)
_ARTICLE_BLOCK = {"no", "the", "a", "an", "new", "old", "your", "its", "this", "that", "each", "both", "two", "one", "all", "any", "every"}
_ARTICLE_AFTER = {"over", "to", "of", "into", "onto", "on", "until", "around", "in", "with", "under", "from", "behind", "at"}
_ARTICLE_SKIP_NOUNS = {"two", "three", "four", "one", "place", "top", "bottom", "position", "closed", "open", "floor"}


def _words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def first_where(where: str) -> str:
    """'On the inlet tube. At the vacuum breaker.' -> 'On the inlet tube.' A Where names one place."""
    text = re.sub(r"\s+", " ", where or "").strip()
    fig = re.search(r"\s*See Fig\.?\s*\d+\.?$", text)
    tail = fig.group(0).strip() if fig else ""
    body = text[: fig.start()] if fig else text
    parts = [p for p in re.split(r"(?<=\.)\s+(?=[A-Z])", body) if p.strip()]
    first = parts[0] if parts else body
    return f"{first} {tail}".strip()


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


def note_as_action(note: str, action: str) -> str:
    """'Larger on top and smaller on bottom' after 'with two rings' is
    'Put the larger ring on top and the smaller ring on the bottom.' A Do-this item is an action."""
    text = re.sub(r"\s+", " ", note or "").strip().rstrip(".")
    m = re.match(r"(?i)^(\w+er) on (?:the )?(\w+) and (\w+er) on (?:the )?(\w+)$", text)
    noun = re.search(r"(?i)\bwith (?:the )?(?:two|both|2) (\w+?)s\b", action or "")
    if not m or not noun:
        return text
    a, p1, b, p2 = (g.lower() for g in m.groups())
    n = noun.group(1).lower()
    place = lambda w: w if w in ("top",) else f"the {w}"
    return f"Put the {a} {n} on {place(p1)} and the {b} {n} on {place(p2)}"


def clamp_bad(action: str) -> str:
    """'Tighten the inlet tube with the new clamp A' fails as 'The inlet tube turns under the clamp.'"""
    m = re.match(r"(?i)^tighten (?:the )?(?:new )?(.+?) with (?:the )?(?:new )?clamp\b", (action or "").strip())
    if not m or m.group(1).strip().lower() in ("it", "them"):
        return ""
    return f"The {m.group(1).strip()} turns under the clamp."


def generic_bad(bad: str) -> bool:
    return re.sub(r"[^a-z ]", "", (bad or "").lower()).strip() in _GENERIC_BAD


def split_good_actions(good: str) -> tuple[list[str], str]:
    """'Flush 3 times. Dry at the pedal.' -> (['Flush 3 times.'], 'No drip at the pedal.')."""
    sentences = [s.strip() for s in re.split(r"(?<=\.)\s+", (good or "").strip()) if s.strip()]
    actions = [s for s in sentences if s.split()[0].lower() in _IMPERATIVE]
    rest = [s for s in sentences if s not in actions]
    rest = [re.sub(r"^Dry at (.+)$", r"No drip at \1", s) for s in rest]
    return actions, " ".join(rest)


def diagnosis_next(good_next: str, fail: str) -> str:
    """One Next with the good path and the bad path named, never two bare orders."""
    good_next = re.sub(r"\s+", " ", good_next or "").strip().rstrip(".")
    fail = re.sub(r"\s+", " ", fail or "").strip()
    out = []
    if good_next:
        out.append(f"If it is good, {good_next[:1].lower() + good_next[1:]}.")
    if fail:
        if re.match(r"(?i)^if\b", fail):
            out.append(_sentence(fail))
        else:
            out.append(f"If it is bad, {fail[:1].lower() + fail[1:]}")
            out[-1] = _sentence(out[-1])
    return " ".join(out)


def noun_vocab(texts: list[str]) -> set[str]:
    vocab = set()
    for text in texts:
        for match in re.finditer(r"\bthe ([a-z]+)", (text or "").lower()):
            if match.group(1) not in _STOP_WORDS and match.group(1) not in _ARTICLE_SKIP_NOUNS:
                vocab.add(match.group(1))
    return vocab


def add_articles(sentence: str, vocab: set[str], *, imperative: bool) -> str:
    """'Push pedal down' -> 'Push the pedal down'. 'Tab locks in place' -> 'The tab locks in place'."""
    words = (sentence or "").split(" ")
    out: list[str] = []
    for index, word in enumerate(words):
        bare = re.sub(r"[^a-z]", "", word.lower())
        prev = re.sub(r"[^a-z]", "", out[-1].lower()) if out else ""
        prev2 = re.sub(r"[^a-z]", "", out[-2].lower()) if len(out) > 1 else ""
        nxt_word = re.sub(r"[^a-z]", "", words[index + 1].lower()) if index + 1 < len(words) else ""
        noun = bare in vocab or (bare in ("back", "front") and nxt_word == "of")
        infinitive = prev2 == "to" and prev in ("engage", "reach", "lock", "hold", "cover") and bare not in _ARTICLE_BLOCK
        letter_label = bool(re.fullmatch(r"[A-H][.,]?", words[index + 1])) if index + 1 < len(words) else False
        wants = (noun or infinitive) and not letter_label and (not out or (prev not in _ARTICLE_BLOCK and out[-1] != "-"))
        if wants:
            if not out and not imperative:
                out.append("The")
                word = word[:1].lower() + word[1:]
            elif out and (prev in _ARTICLE_AFTER or (index == 1 and imperative) or infinitive):
                out.append("the")
        out.append(word)
    return " ".join(out)


def fix_list_comma(sentence: str) -> str:
    """'Throw the old vacuum breaker, and clamps A, B, and C away' loses the first comma."""
    return re.sub(r"^(\w+ the [^,]+?), and (\w+ [A-Z],)", r"\1 and \2", sentence or "")


def _rewrite(step: dict, fn) -> None:
    for key in ("text", "source"):
        if isinstance(step.get(key), str):
            step[key] = fn(step[key])
    if isinstance(step.get("actions"), list):
        step["actions"] = [fn(a) if isinstance(a, str) else a for a in step["actions"]]
    fields = step.get("fields") or {}
    for key in ("HOW", "GOOD vs BAD", "NEXT"):
        if isinstance(fields.get(key), str):
            fields[key] = fn(fields[key])


def _phrase_after_the(text: str, verb_re: str) -> str:
    m = re.search(verb_re + r"\s+the\s+(?:new\s+|old\s+)?([a-z ]+?)(?:\s+(?:on|onto|in|into|off|out|back|from|with|away|until)\b|[.]?$)", text, re.I)
    return m.group(1).strip() if m else ""


def repair_branch(steps: list[dict], action_of, good_bad_of, make_step, secure_step: dict | None = None) -> list[dict]:
    """Generic repairs on one branch, before it is painted.

    - a new part goes on only after the old one came off;
    - every part that came off in a pair goes back in with its mate;
    - a reconnected hose is clamped before the water goes back on;
    - missing articles and the stray list comma are fixed.
    """
    steps = [dict(step, fields=dict(step.get("fields") or {})) for step in steps]
    vocab = noun_vocab([action_of(s) for s in steps] + [" ".join(good_bad_of(s)) for s in steps])

    def wording(text: str) -> str:
        parts = re.split(r"(?<=[.:])\s+", text)
        fixed = []
        imperative = True
        for part in parts:
            if re.fullmatch(r"(?:On good|On bad):", part):
                imperative = True
                fixed.append(part)
                continue
            if re.fullmatch(r"(?:Good|Bad):", part):
                imperative = False
                fixed.append(part)
                continue
            fixed.append(fix_list_comma(add_articles(part, vocab, imperative=imperative)))
        return " ".join(fixed)

    for step in steps:
        _rewrite(step, wording)
    # 1. an old part comes off before its new one goes on
    out: list[dict] = []
    for step in steps:
        action = action_of(step)
        m = re.match(r"(?i)^(?:put|install|push|fit|set) the new ([a-z ]+?) (on|onto|in|into) the ([a-z ]+?)\.?$", action)
        if m:
            part, target = m.group(1).strip(), m.group(3).strip()
            part_re = r"\b" + r"\s+".join(re.escape(_stem(w.lower())) + "s?" for w in part.split()) + r"\b"
            earlier = [action_of(s).lower() for s in out]
            if not any((_REMOVE_RE.search(a) or _THROW_RE.match(a)) and re.search(part_re, a, re.I) for a in earlier):
                where = (step.get("fields") or {}).get("WHERE") or ""
                new = make_step(
                    f"Pull the old {part} off the {target}.", where,
                    f"The old {part} is off the {target}.", "", f"Put the new {part} on the {target}.",
                    section=(out[-1].get("section") if out else "removal") or "removal",
                )
                out.append(new)
        out.append(step)
    steps = out
    # 2. a part that came off with its mate goes back with it
    for i, step in enumerate(steps):
        action = action_of(step)
        pair = re.search(r"(?i)\bthe ([a-z]+(?: [a-z]+)?) and (?:the )?([a-z]+)\b", action)
        if not pair or not _REMOVE_RE.search(action) or _THROW_RE.match(action):
            continue
        first, mate = pair.group(1).lower(), pair.group(2).lower()
        if mate in {"off", "on", "up", "down", "out", "away", "back", "in", "over"}:
            continue
        later = steps[i + 1:]
        mate_re = re.compile(rf"\b{re.escape(mate)}\b(?=\s+(?:is|are|in|into|on|onto|back|until|with|to|and|off)\b|[.,]|$)", re.I)
        if any(mate_re.search(action_of(s)) for s in later if not _THROW_RE.match(action_of(s))):
            continue
        for s in later:
            text = action_of(s)
            if _THROW_RE.match(text) or _REMOVE_RE.search(text):
                continue
            if re.search(rf"(?i)\bthe {re.escape(first)}\b", text) and (s.get("section") or "") != "removal":
                _rewrite(s, lambda t, f=first, m=mate: re.sub(rf"(?i)\bthe {re.escape(f)}\b(?! and)", f"the {f} and {m}", t, count=2))
                break
    # 3. a reconnected hose is clamped before the water goes on
    out = []
    for i, step in enumerate(steps):
        out.append(step)
        action = action_of(step)
        if not re.search(r"(?i)\b(?:push|put|connect|install)\b.*\b(?:hose|supply line)\b.*\b(?:on|onto|to)\b", action):
            continue
        if re.search(r"(?i)\b(?:tighten|secure|clamp)\b", action):
            continue
        rest = []
        for s in steps[i + 1:]:
            if re.search(r"(?i)\bwater on\b|\bturn on\b", action_of(s)):
                break
            rest.append(action_of(s))
        if any(re.search(r"(?i)\b(?:tighten|secure)\b", a) and re.search(r"(?i)\b(?:hose|clamp|connection|line)\b", a) for a in rest):
            continue
        if secure_step is None:
            continue  # the manual shows no securing step on this sheet: invent no clamp
        good, bad = good_bad_of(step)
        if "tight" in (good or "").lower():
            step["fields"]["GOOD vs BAD"] = "Good: The hose is fully on the fitting. Bad: The hose sits crooked on the fitting."
        added = dict(secure_step, fields=dict(secure_step.get("fields") or {}))
        added["section"] = step.get("section") or "installation"
        out.append(added)
    return out
