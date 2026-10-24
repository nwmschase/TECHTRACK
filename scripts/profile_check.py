#!/usr/bin/env python3
"""Score a Guided Diagnostics transcript against the established profile.

Usage: python3 scripts/profile_check.py <transcript.txt>

Prints PASS or FAIL for each rule, then the v1.2 GD scorecard. A line a human
must judge prints MANUAL. Exit 0 when no rule FAILs. A transcript is checked
for the chat profile: no label block, no step counter, a photo only when it
helps, no figure without an ask, and no repeats.
(The Bay PDF checks were removed with the Bay PDF builder, Chase 2026-10-24.)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


BANNED = (
    "not stated in this sheet",
    "not stated",
    "unconfirmed",
    "photo:",
    "a photo is optional",
    "yes, go to the next step",
    "no, do this step again",
    "will display the shop",
    "absent from the docs",
    "send a photo of what you see",
    "<!--",
    "gd-step:",
    "scouring",
)
ASK_RE = re.compile(
    r"show me|show the|where is it|where it is|what does it look like|"
    r"what it looks like|what do they look like",
    re.I,
)
FIGURE_RE = re.compile(r"(?m)^\[figure\]|^Figure:\s|!\[[^\]]*\]\(", re.I)
LABEL_RE = re.compile(
    r"(?m)^(Where|Tools|Do this|Good looks like|Bad looks like|Next):\s",
)
COUNTER_RE = re.compile(r"Step\s+\d+\s+of\s+\d+|\*\*Step\s+\d+:", re.I)
PHOTO_LINE = "send a photo of what you see"


class Rule:
    def __init__(self, name: str, ok: bool, detail: str = "", **marks):
        self.name = name
        self.ok = ok
        self.detail = detail
        self.status = marks.get("status") or ("PASS" if ok else "FAIL")
        self.number = marks.get("number") or 0
        self.line_text = marks.get("line_text") or ""
        self.scorecard = bool(marks.get("scorecard"))
        self.auto_fail = bool(marks.get("auto_fail"))

    def __repr__(self) -> str:
        return f"{self.status}  {self.name}  {self.detail}".rstrip()


def _rule(name: str, ok: bool, detail: str = "") -> Rule:
    return Rule(name, bool(ok), detail)


def _banned(low: str, *, include_photo: bool) -> Rule:
    hits = []
    for phrase in BANNED:
        if phrase == "send a photo of what you see" and not include_photo:
            continue
        if phrase in low:
            hits.append(phrase)
    if hits:
        return _rule("banned_strings", False, ", ".join(hits))
    return _rule("banned_strings", True, "no photo script, unconfirmed, or leaked app text")


def _pairs(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?=^(?:USER|ASSISTANT):)", text or "", flags=re.M)
    pending = ""
    pairs = []
    for part in parts:
        if part.startswith("USER:"):
            pending = part
        elif part.startswith("ASSISTANT:"):
            pairs.append((pending, part))
    return pairs


def _assistant_body(text: str) -> str:
    body = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
    body = re.sub(r"📖.*", "", body)
    body = re.sub(r"(?i)send a photo of what you see\.?", "", body)
    body = re.sub(r"(?i)what do you see\??", "", body)
    body = re.sub(r"(?i)tell me what you see\.?", "", body)
    body = re.sub(r"(?i)report what you see\??", "", body)
    body = re.sub(r"(?i)^ASSISTANT:\s*", "", body)
    return re.sub(r"\s+", " ", body).strip().lower()


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _show_me_repeat_exempt(user: str, assistant: str) -> bool:
    """A show-me may repeat the location when it shows the picture or says there is none.

    Any other show-me still has to add new content.
    """
    if not ASK_RE.search(user or ""):
        return False
    raw = assistant or ""
    if FIGURE_RE.search(raw) or _FIGURE_ATTACHED_RE.search(raw):
        return True
    return bool(re.search(r"\bno picture\b", raw, re.I))


def _near_duplicate(bodies: list[str]) -> bool:
    """One extra sentence on a copied turn is still the same reply."""
    tokens = [_token_set(body) for body in bodies if body]
    for index, left in enumerate(tokens):
        for right in tokens[index + 1 :]:
            if len(left) < 8 or len(right) < 8:
                continue
            union = left | right
            if union and len(left & right) / len(union) >= 0.72:
                return True
            short, long = (left, right) if len(left) <= len(right) else (right, left)
            if len(short) >= 12 and len(short & long) / len(short) >= 0.85:
                return True
    return False


def _pages_clash(turn: str) -> bool:
    parts = (turn or "").split("📖")
    body = parts[0]
    source = " ".join(parts[1:])
    body_pages = set(re.findall(r"\bpage\s+(\d+)\b", body, re.I))
    source_pages = set(re.findall(r"\bpage\s+(\d+)\b", source, re.I))
    return bool(body_pages and source_pages and body_pages.isdisjoint(source_pages))


def _bare_vacuum_turn(pairs: list[tuple[str, str]]) -> bool:
    """T3 after a dry supply, with no bad line, no question, or owner manual 42088 instead of kit 34123."""
    for user, assistant in pairs:
        if not re.search(r"supply connection is dry", user or "", re.I):
            continue
        low = assistant.lower()
        has_bad = bool(re.search(r"\bbad result\b|\bbad looks like\b", low))
        cites_kit = bool(re.search(r"\b3412[23]\b", low))
        if has_bad and _asks_follow_up(assistant) and cites_kit and not _pages_clash(assistant):
            continue
        return True
    return False


_GOOD_LABEL_RE = re.compile(r"\b(?:a )?good result\b|\bgood looks like\b", re.I)
_BAD_LABEL_RE = re.compile(r"\b(?:a )?bad result\b|\bbad looks like\b", re.I)
_REPORT_BACK_RE = re.compile(
    r"\b(?:report what you (?:see|find|hear)|what do you see|tell me what you see)\b",
    re.I,
)
_ACTION_TURN_RE = re.compile(
    r"\b(check|replace|remove|install|flush|go to|use a|use the|turn the|pull the|seat)\b",
    re.I,
)
_WEEP_REASK_RE = re.compile(r"cartridge for a weep|\bcheck\b.{0,60}\bweep\b", re.I)


def _repeats_established_finding(pairs: list[tuple[str, str]]) -> str:
    """A later reply must not ask the tech to prove a result they already reported."""
    for user, assistant in pairs:
        body = assistant or ""
        if re.search(r"weeps at the pedal", user or "", re.I) and _WEEP_REASK_RE.search(body):
            if not re.search(r"\b(replace|remove|install|seat|pull the pedal)\b", body, re.I):
                return "asks to check for a weep the tech already reported"
        if re.search(r"no leak while flushing", user or "", re.I):
            low = body.lower()
            if (
                "vacuum breaker" in low
                and re.search(r"\b(check|watch|flush)\b", low)
                and not re.search(r"\b(42109|replace|remove|install|water off)\b", low)
            ):
                return "asks the vacuum-breaker check again after it passed"
        if re.search(r"supply connection is dry", user or "", re.I):
            if (
                re.search(r"\bcheck\b", body, re.I)
                and re.search(r"supply connection", body, re.I)
                and not re.search(r"vacuum breaker|34123", body, re.I)
            ):
                return "asks the supply check again after it was dry"
    return ""


def _labeled_good_bad(text: str, pairs: list[tuple[str, str]]) -> str:
    """A Thetford check names a good result and a bad result in the sentences.

    A show-me answers where the part is. It is not a new test, so it does not
    need those lines.
    """
    if _case_kind(text) != "thetford":
        return ""
    for index, (user, assistant) in enumerate(pairs, 1):
        if ASK_RE.search(user or ""):
            continue
        raw = assistant or ""
        if not _ACTION_TURN_RE.search(raw):
            continue
        if _GOOD_LABEL_RE.search(raw) and _BAD_LABEL_RE.search(raw):
            continue
        return f"turn {index} does not label both a good result and a bad result"
    return ""


def _asks_follow_up(text: str) -> bool:
    """A question, or the report-back line. The period form still counts."""
    raw = text or ""
    return "?" in raw or bool(_REPORT_BACK_RE.search(raw))


def _report_back_gap(pairs: list[tuple[str, str]]) -> str:
    """Every reply ends by saying what the tech should report."""
    for index, (_user, assistant) in enumerate(pairs, 1):
        if not _REPORT_BACK_RE.search(assistant or ""):
            return f"turn {index} does not say what to report back"
    return ""


_OBSERVATION_TOOL_RE = re.compile(r"\b(wrench|pliers?|screwdriver)\b", re.I)
_HANDS_ON_TOOL_RE = re.compile(
    r"\b(slide clamp|remove the inlet|pull the inlet|replace the vacuum|"
    r"remove|install|tighten|seat|pull the pedal|take the toilet off)\b",
    re.I,
)
_FIGURE_ATTACH_RE = re.compile(
    r"(?m)^(?:T\d+\s+)?Figure:\s|^\[figure\]|!\[[^\]]*\]\(|^(?:T\d+\s+)?Fig(?:ure)?\.?\s+\d+\b",
    re.I,
)


def _tools_fit_the_action(pairs: list[tuple[str, str]]) -> str:
    """An observation-only flush-and-watch names no wrench, pliers, or screwdriver.

    A later 'if it is good, flush' confirm is not that check.
    """
    for _user, assistant in pairs:
        raw = _action_without_next(assistant or "")
        if not _OBSERVATION_TOOL_RE.search(raw) or not re.search(r"\b(flush|watch)\b", raw, re.I):
            continue
        if _HANDS_ON_TOOL_RE.search(raw):
            continue
        return "an observation-only check names a wrench, pliers, or a screwdriver"
    return ""


def _figures_only_when_asked(pairs: list[tuple[str, str]]) -> str:
    """A figure line is attached only after the tech asked to see one."""
    for user, assistant in pairs:
        if _FIGURE_ATTACH_RE.search(assistant or "") and not ASK_RE.search(user or ""):
            return "figure attached before the tech asked to see it"
    return ""


_FIGURE_MENTION_RE = re.compile(
    r"\bfigure\s+\d+\b|\bas shown in\s+fig(?:ure)?\.?\s*\d+\b|\bfig\.\s*\d+\b",
    re.I,
)
_SCRIPTED_FIG_CITE_RE = re.compile(r"the manual shows fig\.\s*\d+\b[^.]*\.", re.I)
_FIGURE_ATTACHED_RE = re.compile(
    r"(?m)^(?:T\d+\s+)?Figure:\s|^\[figure\]|!\[[^\]]*\]\(",
    re.I,
)


def _figure_named_without_attachment(pairs: list[tuple[str, str]]) -> str:
    """'Figure 1' or 'as shown in Figure N' needs the figure on this reply.

    The scripted sentence 'The manual shows Fig. N.' is the cite, not this miss.
    """
    for index, (_user, assistant) in enumerate(pairs, 1):
        raw = assistant or ""
        if _FIGURE_ATTACHED_RE.search(raw):
            continue
        body = _SCRIPTED_FIG_CITE_RE.sub("", raw)
        if _FIGURE_MENTION_RE.search(body):
            return f"turn {index} names a figure that is not attached"
    return ""


def check_transcript(text: str) -> list[Rule]:
    """GD-profile rules for a USER / ASSISTANT transcript."""
    original = text or ""
    raw = re.sub(r"<!--.*?-->", "", original, flags=re.S)
    pairs = _pairs(raw)
    assistants = [pair[1] for pair in pairs] or [raw]
    low = raw.lower()
    label_hit = LABEL_RE.search(raw)
    counter_hit = COUNTER_RE.search(raw)
    photo_hits = [turn for turn in assistants if PHOTO_LINE in turn.lower()]
    photo_every = len(assistants) >= 2 and len(photo_hits) == len(assistants)
    figure_problems = []
    for user, assistant in pairs:
        if FIGURE_RE.search(assistant) and not ASK_RE.search(user):
            figure_problems.append("figure shown before the tech asked")
    bodies = []
    comparable = []
    if pairs:
        for user, assistant in pairs:
            body = _assistant_body(assistant)
            if not body:
                continue
            bodies.append(body)
            if not _show_me_repeat_exempt(user, assistant):
                comparable.append(body)
    else:
        bodies = [_assistant_body(raw)] if _assistant_body(raw) else []
        comparable = list(bodies)
    repeated = len(bodies) != len(set(bodies)) or _near_duplicate(comparable)
    follow = all(_asks_follow_up(turn) for turn in assistants) if assistants else False
    rules = [
        _rule("no_label_block", label_hit is None, "" if label_hit is None else label_hit.group(0).strip()),
        _rule("no_step_counter", counter_hit is None, "" if counter_hit is None else counter_hit.group(0)),
        _banned(original.lower(), include_photo=False),
        _rule(
            "photo_only_when_it_helps",
            not photo_every,
            "photo on every step" if photo_every else f"photo on {len(photo_hits)} of {len(assistants)} replies",
        ),
        _rule(
            "no_figure_without_ask",
            not figure_problems,
            figure_problems[0] if figure_problems else "figures only after show me / where is it / what does it look like",
        ),
        _rule("no_repeats", not repeated, "a reply repeated" if repeated else f"{len(bodies)} distinct replies"),
        _rule("follow_up", follow, "each reply asks what the tech sees" if follow else "a reply has no follow-up question"),
        _rule(
            "repeats_established_finding",
            not _repeats_established_finding(pairs),
            _repeats_established_finding(pairs) or "later replies move past reported findings",
        ),
        _rule(
            "labeled_good_bad",
            not _labeled_good_bad(raw, pairs),
            _labeled_good_bad(raw, pairs) or "each check labels a good result and a bad result",
        ),
        _rule(
            "report_back",
            not _report_back_gap(pairs),
            _report_back_gap(pairs) or "each reply says what to report back",
        ),
        _rule(
            "tools_fit_the_action",
            not _tools_fit_the_action(pairs),
            _tools_fit_the_action(pairs) or "tools match the action",
        ),
        _rule(
            "figures_only_when_asked",
            not _figures_only_when_asked(pairs),
            _figures_only_when_asked(pairs) or "figures only after the tech asked",
        ),
        _rule(
            "figure_named_only_when_attached",
            not _figure_named_without_attachment(pairs),
            _figure_named_without_attachment(pairs) or "a named figure is attached",
        ),
    ]
    return rules + grade_gd(raw, rules)


def check_path(path: Path) -> list[Rule]:
    text = path.read_bytes().decode("utf-8", errors="replace")
    return check_transcript(text)


GD_SCORECARD = (
    "Stayed on the shop manual pathways and cited them; no invented parts, specs, or steps.",
    "Every test request explained HOW: where, tool and setting, what to look or listen for, what good and bad mean, what to report.",
    "Followed the tech's answers; moved forward on reported results; no repeats or loops.",
    "Natural, conversational sentences; no rigid label blocks or step counter.",
    "Figures only when asked; same brand and model; none if the manual has none.",
    "Asked for a photo when it would really help, and did NOT ask when it wasn't needed.",
    "Web fallback only when the manuals fell short AND the tech asked; labeled, with sources.",
    "Safety warnings given where they apply.",
    "Reopen handled neutrally: re-checked earlier steps and readings, then the next likely cause.",
    "None of: leaked app text, off-brand content, filler, cut-off sentences.",
)
GD_AUTO_FAIL = {1, 8, 10}
_REOPEN_PHRASE = re.compile(
    r"wasn['\u2019]?t the fix|not the(?: actual)? fix|\bcame back\b|\bnot fixed\b",
    re.I,
)
_BLAME = re.compile(r"your fault|you did it wrong|our mistake", re.I)
_GD_WEB_LABEL = "Not in the shop manuals, from the web:"


def _named(rules: list[Rule]) -> dict:
    return {rule.name: rule for rule in rules}


def _ok(rules: dict, name: str) -> bool:
    rule = rules.get(name)
    return bool(rule and rule.ok)


def _card(number: int, status: str, line_text: str, detail: str, auto_numbers: set[int]) -> Rule:
    return Rule(
        f"score-{number}",
        status != "FAIL",
        detail,
        status=status,
        number=number,
        line_text=line_text,
        scorecard=True,
        auto_fail=number in auto_numbers,
    )


def _gd_web_ok(text: str) -> bool:
    return True   # retired 2026-10-23 (Chase order); was the web-label check


def _reopen_blames(text: str) -> bool:
    for user, assistant in _pairs(text or ""):
        if _REOPEN_PHRASE.search(user) and _BLAME.search(assistant):
            return True
    return False


_HOW_LEAK = re.compile(r"\bhow\s*\(|\bnot stated\b", re.I)
_CITE_RE = re.compile(r"source:|📖", re.I)
_WHERE_RE = re.compile(
    r"\b(at the|on the|back of|go to|water valve|pedal|vacuum breaker|flange|water off|water to the)\b",
    re.I,
)
_GOODBAD_RE = re.compile(r"\b(good result|bad result)\b", re.I)
_LOOK_RE = re.compile(r"\b(check|look|leak|weep|dry|comes out|flush)\b", re.I)
_HANDS_RE = re.compile(r"\b(remove the|install the|loosen the|reinstall the|put the new)\b", re.I)
_IF_TAIL_RE = re.compile(r"(?i)^if it is (?:good|bad)\b")
_SAFETY_GD = re.compile(
    r"water off|gloves|glasses|supplies off|propane|breaker off|keep people|flame",
    re.I,
)
_VISUAL_RE = re.compile(
    r"\b(leak|weep|look|see|connection|pedal|dry|wet|crack|flush|valve|breaker)\b",
    re.I,
)


def _assistant_turns(text: str) -> list[str]:
    pairs = _pairs(text or "")
    return [turn for _user, turn in pairs]


def _checks_explain_how(pairs: list[tuple[str, str]], assistants: list[str]) -> bool:
    """Each test explains the how. A show-me only answers where, so it is skipped."""
    if pairs:
        checks = [(user, assistant) for user, assistant in pairs if not ASK_RE.search(user or "")]
        return bool(checks) and all(_turn_explains_how(assistant) for _user, assistant in checks)
    return bool(assistants) and all(_turn_explains_how(turn) for turn in assistants)


def _turn_explains_how(turn: str) -> bool:
    """Plain sentences cover where, what to look for, good and bad, and the report.

    A tool is required only when the reply names one. Printing 'not stated'
    is a leak, handled before this check. The label block is a different line.
    """
    body = turn or ""
    return bool(
        _WHERE_RE.search(body)
        and _GOODBAD_RE.search(body)
        and _LOOK_RE.search(body)
        and _asks_follow_up(body)
    )


def _photo_when_unneeded(text: str) -> bool:
    for user, assistant in _pairs(text or ""):
        if PHOTO_LINE not in assistant.lower():
            continue
        body = re.sub(r"(?i)send a photo of what you see\.?", "", assistant)
        body = re.sub(r"(?i)what do you see\??", "", body)
        body = re.sub(r"(?i)tell me what you see\.?", "", body)
        body = re.sub(r"(?i)report what you see\??", "", body)
        if ASK_RE.search(user) or _VISUAL_RE.search(user) or _VISUAL_RE.search(body):
            continue
        return True
    return False


def _action_without_next(turn: str) -> str:
    kept = []
    for line in (turn or "").splitlines():
        if _IF_TAIL_RE.match(line.strip()):
            continue
        kept.append(line)
    return "\n".join(kept)


def _safety_missing(text: str) -> bool:
    """A hands-on repair with no safety note yet. A check, or an if-bad next step, is not one."""
    seen = False
    for turn in _assistant_turns(text):
        if _SAFETY_GD.search(turn):
            seen = True
        action = _action_without_next(turn)
        if _HANDS_RE.search(action) and not seen:
            return True
    return False


def _reopen_neutral(text: str) -> bool:
    for user, assistant in _pairs(text or ""):
        if not _REOPEN_PHRASE.search(user):
            continue
        if _BLAME.search(assistant):
            return False
        if not re.search(r"\b(check|reading|again|next)\b", assistant, re.I):
            return False
    return True


def grade_gd(text: str, rules: list[Rule]) -> list[Rule]:
    """v1.2 Guided Diagnostics scorecard.

    A line PASSes when this transcript shows it and FAILs when it breaks.
    MANUAL stays only when the turns do not show enough to judge.
    """
    named = _named(rules)
    raw = text or ""
    assistants = _assistant_turns(raw)
    photo = named.get("photo_only_when_it_helps")
    if _HOW_LEAK.search(raw) or not _ok(named, "banned_strings"):
        cite_status, cite_detail = "FAIL", "invented filler or a leaked How block"
    elif any(_pages_clash(turn) for turn in assistants):
        cite_status, cite_detail = "FAIL", "a reply names a page its Source line does not"
    elif assistants and all(_CITE_RE.search(turn) for turn in assistants):
        kind = _case_kind(raw)
        brand_hit = _off_brand(raw, kind) if kind else ""
        if brand_hit:
            cite_status, cite_detail = "FAIL", f"off-brand {brand_hit}"
        else:
            cite_status, cite_detail = "PASS", "each reply cites a shop manual"
    else:
        cite_status = "MANUAL"
        cite_detail = (
            "shop-manual cite present"
            if "source:" in raw.lower()
            else "no Source cite; human confirms the pathway"
        )
    if _HOW_LEAK.search(raw):
        how_status, how_detail = "FAIL", "How block or 'not stated' is not a shop sentence"
    elif _bare_vacuum_turn(_pairs(raw)):
        how_status, how_detail = "FAIL", "the vacuum-breaker turn has no bad line, no question, or cites 42088 instead of kit 34123"
    elif _valve_start_bare(_pairs(raw)):
        how_status, how_detail = "FAIL", "the water-valve turn names no place and no tool"
    elif _checks_explain_how(_pairs(raw), assistants):
        how_status, how_detail = "PASS", "each check says where, what to look for, good and bad, and what to report"
    else:
        how_status, how_detail = "MANUAL", "human confirms the how-to detail"
    if photo and not photo.ok:
        photo_status, photo_detail = "FAIL", photo.detail or "photo on every step"
    elif _photo_when_unneeded(raw):
        photo_status, photo_detail = "FAIL", "photo asked on a step that is not visual"
    elif assistants:
        photo_status = "PASS"
        photo_detail = photo.detail if photo else "photo only on a visual step"
    else:
        photo_status, photo_detail = "MANUAL", "human confirms when a photo helps"
    if _safety_missing(raw):
        safety_status, safety_detail = "FAIL", "a repair step has no safety warning"
    elif assistants:
        safety_status, safety_detail = "PASS", "safety is on the step where the work starts, or the turn is only a check"
    else:
        safety_status, safety_detail = "MANUAL", "human confirms the safety warnings"
    if _reopen_blames(raw):
        reopen_status, reopen_detail = "FAIL", "a reopen reply blames the tech or the program"
    elif _REOPEN_PHRASE.search(raw) and not _reopen_neutral(raw):
        reopen_status, reopen_detail = "MANUAL", "human confirms a neutral reopen"
    elif assistants:
        reopen_status = "PASS"
        reopen_detail = "reopen re-checks without blame" if _REOPEN_PHRASE.search(raw) else "no reopen in this session"
    else:
        reopen_status, reopen_detail = "MANUAL", "human confirms a neutral reopen"
    rows = [
        (1, cite_status, cite_detail),
        (2, how_status, how_detail),
        (3, "PASS" if _ok(named, "no_repeats") and _ok(named, "follow_up") else "FAIL", "moved forward without a repeated reply"),
        (4, "PASS" if _ok(named, "no_label_block") and _ok(named, "no_step_counter") else "FAIL", "no label block and no step counter"),
        (
            5,
            "PASS"
            if _ok(named, "no_figure_without_ask") and _ok(named, "figure_named_only_when_attached")
            else "FAIL",
            "figures only after the tech asked, and a named figure is attached",
        ),
        (6, photo_status, photo_detail),
        (7, "PASS", "retired 2026-10-23: no web rule (Chase order)"),
        (8, safety_status, safety_detail),
        (9, reopen_status, reopen_detail),
        (10, "PASS" if _ok(named, "banned_strings") else "FAIL", "no leaked text, filler, or cut-off marker"),
    ]
    return [_card(number, status, GD_SCORECARD[number - 1], detail, GD_AUTO_FAIL) for number, status, detail in rows]


_CHECK_VERBS = ("check", "look", "listen", "measure", "watch", "test", "confirm", "inspect", "feel")


_THETFORD_OFF = (
    "norcold", "furrion", "dometic", "suburban", "coleman", "happijac",
    "atwood", "girard", "power gear", "lippert",
)
_FURRION_OFF = (
    "norcold", "thetford", "dometic", "suburban", "coleman", "happijac", "atwood",
)


def _case_kind(text: str) -> str:
    head = (text or "")[:1800].lower()
    if "thetford" in head or "42070" in head:
        return "thetford"
    if "furrion" in head or "facr" in head or "ccd-0008666" in head:
        return "furrion"
    return ""


_DOC_CORPUS: dict[str, str | None] = {}


def _valve_start_bare(pairs: list[tuple[str, str]]) -> bool:
    """The water-valve repair turn names a place and a tool in plain words."""
    for user, assistant in pairs:
        if "42109" not in (assistant or ""):
            continue
        if not re.search(r"water valve|weeps at the pedal|no leak while flushing", user or "", re.I):
            continue
        low = assistant.lower()
        has_place = bool(re.search(r"\bgo to the water valve\b|\bat the water valve\b|\bat the pedal\b", low))
        has_tool = bool(re.search(r"\b(wrench|pliers?|screwdriver|towel)\b", low))
        if has_place and has_tool:
            continue
        return True
    return False


def _off_brand(text: str, kind: str) -> str:
    low = (text or "").lower()
    banned = _THETFORD_OFF if kind == "thetford" else _FURRION_OFF if kind == "furrion" else ()
    for token in banned:
        if token in low:
            return token
    return ""


def gate_summary(rules: list[Rule]) -> str:
    """Markdown block for a gate summary. MANUAL lines are not passes."""
    cards = [rule for rule in rules if rule.scorecard]
    if not cards:
        return ""
    lines = ["## Guided Diagnostics scorecard"]
    passed = 0
    auto = []
    for rule in cards:
        note = f" ({rule.detail})" if rule.detail else ""
        lines.append(f"{rule.number}. {rule.status} — {rule.line_text}{note}")
        if rule.status == "PASS":
            passed += 1
        if rule.status == "FAIL" and rule.auto_fail:
            auto.append(str(rule.number))
    verdict = "yes" if auto else "no"
    extra = f" Lines {', '.join(auto)}." if auto else ""
    lines.append(f"Result: {passed}/10. Automatic FAIL: {verdict}.{extra}")
    return "\n".join(lines)


def format_report(rules: list[Rule]) -> str:
    lines = []
    for rule in rules:
        if rule.scorecard:
            continue
        lines.append(f"{'PASS' if rule.ok else 'FAIL'}  {rule.name}" + (f"  {rule.detail}" if rule.detail else ""))
    summary = gate_summary(rules)
    if summary:
        lines.append(summary)
    failed = [rule for rule in rules if not rule.ok]
    lines.append("PASS" if not failed else f"FAIL  {len(failed)} rule(s)")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    args = list(argv[1:])
    if len(args) != 1:
        print("Usage: python3 scripts/profile_check.py <transcript.txt>", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"FAIL  file  {path} is not a file")
        return 1
    rules = check_path(path)
    print(format_report(rules))
    return 0 if all(rule.ok for rule in rules) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
