#!/usr/bin/env python3
"""Score a Bay PDF or a Guided Diagnostics transcript against the established profiles.

Usage: python3 scripts/profile_check.py <pdf-or-transcript.txt>

Prints PASS or FAIL for each rule, then the v1.2 scorecard.
A line a human must judge prints MANUAL. Exit 0 when no rule FAILs.
A PDF is checked for section order, branch subsections, step line order,
banned strings, sentence length, figure width, and figure placement.
A transcript is checked for the chat profile: no label block, no step
counter, a photo only when it helps, no figure without an ask, and no repeats.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


PAGE_W = 612.0
MARGIN = 36.0
CONTENT_W = PAGE_W - 2 * MARGIN
# Profile: about 70-80% of the usable page width. 75% is the sheet width.
FIG_MIN = 0.70 * CONTENT_W - 1.0
FIG_MAX = 0.80 * CONTENT_W + 2.0
# "About 12 words." Locked kit phrases stay under the existing 15-word ceiling.
WORD_LIMIT = 15

LABEL_ORDER = (
    "where:",
    "tools:",
    "do this:",
    "good looks like:",
    "bad looks like:",
    "next:",
    "if it fails:",
)
REQUIRED_LABELS = ("do this:", "good looks like:", "next:")
GENERIC_BAD = re.compile(
    r"^(?:it does not look right|not stated(?: in this sheet)?|unconfirmed|"
    r"do this step again|the step is not finished|not this:.*)\.?$",
    re.I,
)
BANNED = (
    "not stated in this sheet",
    "unconfirmed",
    "photo:",
    "a photo is optional",
    "yes, go to the next step",
    "no, do this step again",
    "will display the shop",
    "absent from the docs",
    "send a photo of what you see",
)
SAFETY_CUE = re.compile(
    r"water off|supplies off|flammable|gloves|flame|hoist|propane|breaker off|keep people",
    re.I,
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


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", text or ""))


def _rule(name: str, ok: bool, detail: str = "") -> Rule:
    return Rule(name, bool(ok), detail)


def check_sheet_text(text: str) -> list[Rule]:
    """PDF-profile rules that can be read from the sheet text."""
    raw = text or ""
    low = raw.lower()
    rules = [
        _section_order(raw),
        _branch_subsections(raw),
        _line_order(raw),
        _banned(low, include_photo=True),
        _sentence_length(raw),
        _safety_once(raw),
        _web_content(raw),
    ]
    return rules


def _section_order(text: str) -> Rule:
    def at(pattern: str) -> int:
        match = re.search(pattern, text)
        return match.start() if match else -1

    marks = {
        "concern": at(r"\bCONCERN\b"),
        "model": at(r"\bMODEL\b"),
        "primary": at(r"\bPRIMARY\b"),
        "diagnosis": at(r"\bDIAGNOSIS\b"),
        "removal": at(r"\bREMOVAL\b"),
        "do not": at(r"\bDO NOT\b"),
        "sources": at(r"\bSOURCES\b"),
    }
    missing = [name for name, pos in marks.items() if pos < 0]
    if missing:
        return _rule("section_order", False, "missing " + ", ".join(missing))
    order = ["concern", "model", "primary", "diagnosis", "removal", "do not", "sources"]
    positions = [marks[name] for name in order]
    if positions != sorted(positions):
        return _rule("section_order", False, "sections are out of order")
    head = text[: marks["diagnosis"]]
    if not re.search(r"\b(?:YES|NO)\b", head):
        return _rule("section_order", False, "no diagnosis flowchart before the checks")
    return _rule("section_order", True, "header, flowchart, diagnosis, branches, do not, sources")


def _blocks(text: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r"REPAIR BRANCH|REPAIR PROCEDURE", text)]
    if not starts:
        return []
    ends = starts[1:] + [len(text)]
    stop = re.search(r"\bDO NOT\b", text)
    blocks = []
    for start, end in zip(starts, ends):
        if stop and start >= stop.start():
            continue
        if stop and end > stop.start() > start:
            end = stop.start()
        blocks.append(text[start:end])
    return blocks


def _branch_subsections(text: str) -> Rule:
    blocks = _blocks(text)
    if not blocks:
        return _rule("branch_subsections", False, "no repair branch")
    problems = []
    for index, block in enumerate(blocks, 1):
        title = " ".join(block.split()[:6])
        if "BEFORE YOU START" not in block:
            problems.append(f"branch {index} ({title}) has no Before you start")
        else:
            before = block.split("REMOVAL", 1)[0]
            if not SAFETY_CUE.search(before):
                problems.append(f"branch {index} safety note is not in Before you start")
        if "REMOVAL" not in block or not re.search(r"Step\s+\d+\s*:", block.split("REMOVAL", 1)[-1][:400]):
            problems.append(f"branch {index} has no numbered Removal steps")
        if "INSTALLATION" not in block:
            problems.append(f"branch {index} has no Installation")
        else:
            after = block.split("INSTALLATION", 1)[-1][:500]
            if not re.search(r"Step\s+\d+\s*:", after):
                problems.append(f"branch {index} Installation is not numbered")
        confirms = list(re.finditer(r"Step\s+\d+\s*:\s*(?:Confirm|Verify)\b", block, re.I))
        confirm = confirms[-1] if confirms else None
        if not confirm:
            problems.append(f"branch {index} has no confirm / verify step")
        else:
            tail = block[confirm.start():]
            if "Good looks like:" not in tail or "Bad looks like:" not in tail:
                problems.append(f"branch {index} verify step has no pass/fail")
    if problems:
        return _rule("branch_subsections", False, "; ".join(problems[:6]))
    return _rule("branch_subsections", True, f"{len(blocks)} branches with removal, installation, verify")


def _step_chunks(text: str) -> list[str]:
    parts = re.split(r"(?=Step\s+\d+\s*:)", text)
    return [part for part in parts if re.match(r"Step\s+\d+\s*:", part)]


def _procedure_text(text: str) -> str:
    """Step-format rules apply to the procedure, not the short diagnosis lead-in."""
    marks = []
    for pattern in ("PROVING CHECKS", "REPAIR BRANCH", "REPAIR PROCEDURE"):
        match = re.search(pattern, text)
        if match:
            marks.append(match.start())
    if not marks:
        return text
    return text[min(marks):]


def _line_order(text: str) -> Rule:
    chunks = _step_chunks(_procedure_text(text))
    if not chunks:
        return _rule("line_order", False, "no numbered steps")
    problems = []
    for chunk in chunks:
        heading = chunk.splitlines()[0][:80]
        labels = []
        for line in chunk.splitlines():
            low = line.strip().lower()
            for name in LABEL_ORDER:
                if low.startswith(name):
                    labels.append(name)
                    break
        if labels != [name for name in LABEL_ORDER if name in labels]:
            problems.append(f"{heading} labels out of order")
        missing = [name for name in REQUIRED_LABELS if name not in labels]
        if missing:
            problems.append(f"{heading} missing {', '.join(missing)}")
        for line in chunk.splitlines():
            if line.strip().lower().startswith("bad looks like:"):
                value = line.split(":", 1)[-1].strip()
                if GENERIC_BAD.match(value):
                    problems.append(f"{heading} generic bad")
            if re.match(r"\s*\d+\.\s+\d+\.", line):
                problems.append(f"{heading} stray number")
        if len(problems) > 8:
            break
    if problems:
        return _rule("line_order", False, "; ".join(problems[:6]))
    return _rule("line_order", True, f"{len(chunks)} steps in Where / Tools / Do this / Good / Bad / Next order")


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


def _sentence_length(text: str) -> Rule:
    longest = 0
    sample = ""
    for chunk in _step_chunks(_procedure_text(text)):
        first = chunk.splitlines()[0]
        title = re.sub(r"^Step\s+\d+\s*:\s*", "", first).strip()
        count = _words(title)
        if count > longest:
            longest, sample = count, title
        in_do = False
        for line in chunk.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("do this:"):
                in_do = True
                continue
            if in_do and re.match(r"\d+\.\s+", stripped):
                action = re.sub(r"^\d+\.\s+", "", stripped)
                count = _words(action)
                if count > longest:
                    longest, sample = count, action
                continue
            if in_do and stripped and not re.match(r"\d+\.\s+", stripped):
                in_do = False
    if longest > WORD_LIMIT:
        return _rule("sentence_length", False, f"{longest} words: {sample}")
    return _rule(
        "sentence_length",
        True,
        f"longest {longest} words (profile about 12; fail above {WORD_LIMIT})",
    )


def _safety_once(text: str) -> Rule:
    """Each branch prints a safety sentence once. The same note may open the next branch."""
    problems = []
    chunks = _blocks(text) or [text]
    proving = re.search(r"PROVING CHECKS[\s\S]*?(?=REPAIR BRANCH|REPAIR PROCEDURE|\bDO NOT\b)", text)
    if proving:
        chunks = [proving.group(0), *chunks]
    for index, block in enumerate(chunks, 1):
        lines = [re.sub(r"\s+", " ", line).strip().lower() for line in re.findall(r"Safety:.*", block)]
        dupes = sorted({line for line in lines if lines.count(line) > 1})
        if dupes:
            problems.append(f"branch {index} repeats {dupes[0][:70]}")
        if "BEFORE YOU START" in block and "REMOVAL" in block:
            before = block.split("BEFORE YOU START", 1)[-1].split("REMOVAL", 1)[0].lower()
            for line in lines:
                sentence = line.split(":", 1)[-1].strip().rstrip(".")
                if sentence and sentence in before:
                    problems.append(f"branch {index} repeats the before-you-start note")
    if problems:
        return _rule("safety_once", False, "; ".join(problems[:4]))
    return _rule("safety_once", True, "each branch gives its safety note once")


def _web_content(text: str) -> Rule:
    if re.search(r"from the web|outside sources", text, re.I):
        if "OUTSIDE SOURCES" not in text and "Outside sources" not in text:
            return _rule("web_content", False, "web content is not in an Outside sources section")
    return _rule("web_content", True, "no web content mixed into the manual steps")


def _figure_rules(doc) -> list[Rule]:
    widths = []
    placement = []
    for page_index, page in enumerate(doc, 1):
        images = page.get_image_info() or []
        words = page.get_text("words") or []
        for info in images:
            box = info.get("bbox") or info.get("bbox")
            if not box:
                continue
            x0, y0, x1, y1 = box
            width = x1 - x0
            widths.append(width)
            if width < FIG_MIN or width > FIG_MAX:
                placement.append(f"page {page_index} width {width:.0f} outside 70-80%")
            center = (x0 + x1) / 2.0
            if abs(center - PAGE_W / 2.0) > 3.0:
                placement.append(f"page {page_index} figure is not centered")
            # words are (x0, y0, x1, y1, text, ...) in the same space as the image box
            step_above = any(
                str(word[4]).startswith("Step") and word[3] <= y0 + 4
                for word in words
            )
            caption_below = any(
                word[1] >= y1 - 2 and word[1] <= y1 + 40
                for word in words
            )
            if not step_above:
                placement.append(f"page {page_index} figure is split from its step")
            if not caption_below:
                placement.append(f"page {page_index} caption is not under the figure")
    if not widths:
        return [
            _rule("figure_width", True, "no figure where the manual has none"),
            _rule("figure_placement", True, "no figure to place"),
        ]
    width_ok = not any("width" in item for item in placement)
    place_ok = not any("width" not in item for item in placement)
    width_detail = (
        f"{len(widths)} figures, {min(widths):.0f}-{max(widths):.0f} pt "
        f"(usable page {CONTENT_W:.0f} pt, 70-80%)"
    )
    return [
        _rule("figure_width", width_ok, width_detail if width_ok else "; ".join(placement[:4])),
        _rule(
            "figure_placement",
            place_ok,
            "caption under the citing step" if place_ok else "; ".join(
                item for item in placement if "width" not in item
            )[:240],
        ),
    ]


def check_pdf_bytes(data: bytes) -> list[Rule]:
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in doc)
        rules = check_sheet_text(text) + _figure_rules(doc)
        return rules + grade_pdf(text, rules)
    finally:
        doc.close()


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
    body = re.sub(r"(?i)^ASSISTANT:\s*", "", body)
    return re.sub(r"\s+", " ", body).strip().lower()


def check_transcript(text: str) -> list[Rule]:
    """GD-profile rules for a USER / ASSISTANT transcript."""
    raw = re.sub(r"<!--.*?-->", "", text or "", flags=re.S)
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
    bodies = [_assistant_body(turn) for turn in assistants if _assistant_body(turn)]
    repeated = len(bodies) != len(set(bodies))
    follow = all("?" in turn for turn in assistants) if assistants else False
    rules = [
        _rule("no_label_block", label_hit is None, "" if label_hit is None else label_hit.group(0).strip()),
        _rule("no_step_counter", counter_hit is None, "" if counter_hit is None else counter_hit.group(0)),
        _banned(low, include_photo=False),
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
    ]
    return rules + grade_gd(raw, rules)


def _looks_like_sheet(text: str) -> bool:
    return "BEFORE YOU START" in text or "\nDIAGNOSIS\n" in text or "Do this:" in text


def check_path(path: Path) -> list[Rule]:
    data = path.read_bytes()
    if data.startswith(b"%PDF") or path.suffix.lower() == ".pdf":
        return check_pdf_bytes(data)
    text = data.decode("utf-8", errors="replace")
    if _looks_like_sheet(text):
        rules = check_sheet_text(text)
        rules.append(_rule("figure_width", False, "text extract has no page images; pass the PDF"))
        rules.append(_rule("figure_placement", False, "text extract has no page images; pass the PDF"))
        return rules + grade_pdf(text, rules)
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
PDF_SCORECARD = (
    "Structure complete: header, flowchart, diagnosis, a branch for every possible repair, Do Not list, sources.",
    "Each branch runs to completion and ends with a confirm step with a clear pass or fail.",
    "Every step has a bold numbered heading and the same labeled lines in the same order.",
    "One action per line; sentences of about 12 words or fewer; plain words.",
    "Bad looks like is specific to the step, or left out.",
    "Real same-brand manual figure, large (about 70-80% width), centered under the step that cites it, with caption; never split from its step.",
    "No figure where the manual has none; nothing invented or off-brand.",
    "Safety stated once per section, and correct (no contradictions).",
    "None of: PHOTO or yes/no lines, UNCONFIRMED tags, disclaimers, leaked app text, cut-off sentences, stray numbers.",
    "Web content only in a separate labeled Outside sources section.",
)
GD_AUTO_FAIL = {1, 8, 10}
PDF_AUTO_FAIL = {2, 7, 8, 9}
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


def _step_inspection(text: str) -> dict:
    """Label order, a generic Bad line, and a stray number, scanned once."""
    chunks = _step_chunks(_procedure_text(text))
    order_problems = []
    generic = []
    stray = []
    if not chunks:
        order_problems.append("no numbered steps")
    for chunk in chunks:
        heading = chunk.splitlines()[0][:80]
        labels = []
        for line in chunk.splitlines():
            low = line.strip().lower()
            for name in LABEL_ORDER:
                if low.startswith(name):
                    labels.append(name)
                    break
            if low.startswith("bad looks like:"):
                value = line.split(":", 1)[-1].strip()
                if GENERIC_BAD.match(value):
                    generic.append(heading)
            if re.match(r"\s*\d+\.\s+\d+\.", line):
                stray.append(heading)
        if labels != [name for name in LABEL_ORDER if name in labels]:
            order_problems.append(f"{heading} labels out of order")
        missing = [name for name in REQUIRED_LABELS if name not in labels]
        if missing:
            order_problems.append(f"{heading} missing {', '.join(missing)}")
    return {"order": order_problems, "generic": generic, "stray": stray}


def _gd_web_ok(text: str) -> bool:
    if re.search(r"from the web|outside sources", text or "", re.I):
        return _GD_WEB_LABEL in (text or "")
    return True


def _reopen_blames(text: str) -> bool:
    for user, assistant in _pairs(text or ""):
        if _REOPEN_PHRASE.search(user) and _BLAME.search(assistant):
            return True
    return False


def grade_gd(text: str, rules: list[Rule]) -> list[Rule]:
    """v1.2 Guided Diagnostics scorecard. Lines 1, 2, 6, 8, and 9 stay MANUAL unless a check can fail them."""
    named = _named(rules)
    photo = named.get("photo_only_when_it_helps")
    cite = "source:" in (text or "").lower()
    if photo and not photo.ok:
        photo_status, photo_detail = "FAIL", photo.detail or "photo on every step"
    else:
        photo_status = "MANUAL"
        photo_detail = photo.detail if photo else "human confirms when a photo helps"
    if _reopen_blames(text):
        reopen_status, reopen_detail = "FAIL", "a reopen reply blames the tech or the program"
    else:
        reopen_status, reopen_detail = "MANUAL", "human confirms a neutral reopen"
    rows = [
        (1, "MANUAL", "shop-manual cite present" if cite else "no Source cite; human confirms the pathway"),
        (2, "MANUAL", "human confirms the how-to detail"),
        (3, "PASS" if _ok(named, "no_repeats") and _ok(named, "follow_up") else "FAIL", "moved forward without a repeated reply"),
        (4, "PASS" if _ok(named, "no_label_block") and _ok(named, "no_step_counter") else "FAIL", "no label block and no step counter"),
        (5, "PASS" if _ok(named, "no_figure_without_ask") else "FAIL", "figures only after the tech asked"),
        (6, photo_status, photo_detail),
        (7, "PASS" if _gd_web_ok(text) else "FAIL", "web fallback is labeled, or there is no web content"),
        (8, "MANUAL", "human confirms the safety warnings"),
        (9, reopen_status, reopen_detail),
        (10, "PASS" if _ok(named, "banned_strings") else "FAIL", "no leaked text, filler, or cut-off marker"),
    ]
    return [_card(number, status, GD_SCORECARD[number - 1], detail, GD_AUTO_FAIL) for number, status, detail in rows]


def grade_pdf(text: str, rules: list[Rule]) -> list[Rule]:
    """v1.2 Bay PDF scorecard. Lines 7 and 8 stay MANUAL unless a check can fail them."""
    named = _named(rules)
    inspected = _step_inspection(text)
    banned_ok = _ok(named, "banned_strings")
    if not banned_ok:
        invented_status, invented_detail = "FAIL", named["banned_strings"].detail or "invented or off-brand text"
    else:
        invented_status, invented_detail = "MANUAL", "human confirms no figure was invented or off-brand"
    safety = named.get("safety_once")
    if safety and not safety.ok:
        safety_status, safety_detail = "FAIL", safety.detail or "safety note repeated"
    else:
        safety_status, safety_detail = "MANUAL", "human confirms the safety note is correct"
    line_nine = "PASS" if banned_ok and not inspected["stray"] else "FAIL"
    rows = [
        (1, "PASS" if _ok(named, "section_order") and _ok(named, "branch_subsections") else "FAIL", "header, flowchart, diagnosis, branches, do not, sources"),
        (2, "PASS" if _ok(named, "branch_subsections") else "FAIL", "each branch ends on a confirm with a pass and a fail"),
        (3, "PASS" if not inspected["order"] else "FAIL", "numbered headings and the same label order"),
        (4, "PASS" if _ok(named, "sentence_length") else "FAIL", "one action per line, about 12 words"),
        (5, "PASS" if not inspected["generic"] else "FAIL", "Bad looks like is specific, or left off"),
        (6, "PASS" if _ok(named, "figure_width") and _ok(named, "figure_placement") else "FAIL", "figure width, centering, and caption"),
        (7, invented_status, invented_detail),
        (8, safety_status, safety_detail),
        (9, line_nine, "no photo script, unconfirmed, leaked text, or stray number"),
        (10, "PASS" if _ok(named, "web_content") else "FAIL", "web content stays in Outside sources"),
    ]
    return [_card(number, status, PDF_SCORECARD[number - 1], detail, PDF_AUTO_FAIL) for number, status, detail in rows]


def gate_summary(rules: list[Rule]) -> str:
    """Markdown block for a gate summary. MANUAL lines are not passes."""
    cards = [rule for rule in rules if rule.scorecard]
    if not cards:
        return ""
    if cards[0].line_text == GD_SCORECARD[0]:
        kind = "Guided Diagnostics"
    else:
        kind = "Bay PDF"
    lines = [f"## {kind} scorecard"]
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
    if len(argv) != 2:
        print("Usage: python3 scripts/profile_check.py <pdf-or-transcript.txt>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    if not path.is_file():
        print(f"FAIL  file  {path} is not a file")
        return 1
    rules = check_path(path)
    print(format_report(rules))
    return 0 if all(rule.ok for rule in rules) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
