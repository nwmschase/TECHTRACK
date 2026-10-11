#!/usr/bin/env python3
"""Score a Bay PDF or a Guided Diagnostics transcript against the established profiles.

Usage: python3 scripts/profile_check.py <pdf-or-transcript.txt>

Prints PASS or FAIL for each rule, the PF-01..PF-33 past-fail lines, then the
v1.2 scorecard. A line a human must judge prints MANUAL. Exit 0 when no rule FAILs.
A PDF is checked for section order, branch subsections, step line order,
banned strings, sentence length, figure width, and figure placement.
A transcript is checked for the chat profile: no label block, no step
counter, a photo only when it helps, no figure without an ask, and no repeats.
"""
from __future__ import annotations

import hashlib
import math
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
        _fastener_sequence(raw),
        _source_doc_quotes(raw),
        _mid_phrase_gap(raw),
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
        rules = rules + grade_pdf(text, rules)
        return rules + grade_past_fails(doc, text)
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


def _token_set(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


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
        if has_bad and "?" in assistant and cites_kit and not _pages_clash(assistant):
            continue
        return True
    return False


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
    bodies = [_assistant_body(turn) for turn in assistants if _assistant_body(turn)]
    repeated = len(bodies) != len(set(bodies)) or _near_duplicate(bodies)
    follow = all("?" in turn for turn in assistants) if assistants else False
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
        return rules + grade_pdf(text, rules) + grade_past_fails(None, text)
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
_FIG_LABEL_RE = re.compile(
    r"(?i)^fig\.?\s*\d+\b|\b(?:42109|34122|34123|42088|CCD-\d+|FACT\d*|FACR)\b"
)
_DOC_ID_RE = re.compile(r"\b(?:42109|34122|34123|42088|CCD-\d+|FACT\d*|FACR-\d+)\b", re.I)
_THETFORD_BRANCHES = (
    ("supply",),
    ("vacuum", "3412"),
    ("42109", "water valve"),
    ("flange",),
)
_CASE_SOURCE_KEYS = {
    "thetford": ("thetford", "42070", "42088", "42109", "34122", "34123", "toilet", "valve", "flange"),
    "furrion": ("furrion", "facr", "ccd-0008666", "ccd-0007990", "rooftop", "freeze", "drain"),
}


def _assistant_turns(text: str) -> list[str]:
    pairs = _pairs(text or "")
    return [turn for _user, turn in pairs]


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
        and "?" in body
    )


def _photo_when_unneeded(text: str) -> bool:
    for user, assistant in _pairs(text or ""):
        if PHOTO_LINE not in assistant.lower():
            continue
        body = re.sub(r"(?i)send a photo of what you see\.?", "", assistant)
        body = re.sub(r"(?i)what do you see\??", "", body)
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


def _figure_caption_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if _PF_FIG_LINE.match(line.strip())]


def _invented_figure(text: str, rules: dict) -> tuple[str, str]:
    if not _ok(rules, "banned_strings"):
        detail = rules["banned_strings"].detail or "invented or off-brand text"
        return "FAIL", detail
    captions = _figure_caption_lines(text)
    blob = "\n".join(captions).lower()
    low = (text or "").lower()
    if "bundled kit sheet" in low or any(phrase in blob for phrase in _CAPTION_BAD):
        return "FAIL", "caption is a sketch or a bundled kit sheet"
    kind = _case_kind(text)
    brand_hit = _off_brand(blob, kind) if kind and blob else ""
    if brand_hit:
        return "FAIL", f"figure caption names {brand_hit}"
    bad = [line for line in captions if not _FIG_LABEL_RE.search(line)]
    if bad:
        return "FAIL", f"invented figure caption: {bad[0][:80]}"
    if captions:
        return "PASS", "figure captions are manual Fig. labels for this case"
    width = rules.get("figure_width")
    drawn = bool(width and "figures," in (width.detail or ""))
    if drawn and _ok(rules, "figure_placement"):
        return "PASS", "drawn figures are captioned under the citing step"
    if drawn:
        return "FAIL", "a drawn figure has no manual Fig. caption"
    return "PASS", "no figure drawn, and no invented caption"


def _safety_status(text: str, rules: dict) -> tuple[str, str]:
    safety = rules.get("safety_once")
    if safety and not safety.ok:
        return "FAIL", safety.detail or "safety note repeated"
    conflicts = [
        step.splitlines()[0][:70]
        for step in _bounded_steps(text or "")
        if _state_conflict(step)
    ]
    if conflicts:
        return "FAIL", conflicts[0]
    if safety and safety.ok:
        return "PASS", "safety is once per section and does not contradict the action"
    return "MANUAL", "human confirms the safety note is correct"


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
    elif assistants and all(_turn_explains_how(turn) for turn in assistants):
        how_status, how_detail = "PASS", "each reply says where, what to look for, good and bad, and what to report"
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
        (5, "PASS" if _ok(named, "no_figure_without_ask") else "FAIL", "figures only after the tech asked"),
        (6, photo_status, photo_detail),
        (7, "PASS" if _gd_web_ok(raw) else "FAIL", "web fallback is labeled, or there is no web content"),
        (8, safety_status, safety_detail),
        (9, reopen_status, reopen_detail),
        (10, "PASS" if _ok(named, "banned_strings") else "FAIL", "no leaked text, filler, or cut-off marker"),
    ]
    return [_card(number, status, GD_SCORECARD[number - 1], detail, GD_AUTO_FAIL) for number, status, detail in rows]


def grade_pdf(text: str, rules: list[Rule]) -> list[Rule]:
    """v1.2 Bay PDF scorecard.

    Lines 7 and 8 PASS when the sheet shows a real caption and a safety note
    that does not contradict the action. They FAIL on an invented figure or a
    contradiction. MANUAL stays when the sheet does not show enough to judge.
    """
    named = _named(rules)
    inspected = _step_inspection(text)
    banned_ok = _ok(named, "banned_strings")
    invented_status, invented_detail = _invented_figure(text, named)
    safety_status, safety_detail = _safety_status(text, named)
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


_PF_FIELD = re.compile(
    r"^(Where|Good looks like|Bad looks like|Next|Safety|If it fails|Caution):\s*(.*)$",
    re.I,
)
_PF_STOP = re.compile(
    r"^(?:Step\s+\d+\s*:|Figure:|Fig\.|BAY PROCEDURE|Tacoma RV Center|"
    r"REPAIR BRANCH|REPAIR PROCEDURE|BEFORE YOU START|REMOVAL|INSTALLATION|"
    r"VERIFY|DO NOT|SOURCES|DIAGNOSIS|VISUAL FLOWCHART|WHAT THIS PATTERN|"
    r"Where:|Tools:|Do this:|Good looks like:|Bad looks like:|Next:|Safety:|"
    r"If it fails:|Caution:|- |(?:CCD|FACT|FACR)-\d+)",
    re.I,
)
_PF_HEADING = re.compile(
    r"^(?:REMOVAL|INSTALLATION|VERIFY|BEFORE YOU START|DO NOT|DIAGNOSIS|"
    r"REPAIR PROCEDURE|REPAIR BRANCH|SOURCES \(SHOP DOCUMENT LIBRARY\)|"
    r"VISUAL FLOWCHART|WHAT THIS PATTERN USUALLY MEANS)$",
    re.I,
)
_PF_PAGE = re.compile(r"\b(?:page\s+\d+|p\.?\s*\d+)\b", re.I)
_PF_GLUED_DOC = re.compile(
    r"(?m)^(?:\d+\s+)?(?:CCD|FACT|FACR)-\d{3,}\s+(?!page\b|p\.?\s*\d)[A-Za-z]"
)
_PF_DOUBLE = re.compile(r"\b([A-Za-z]{2,})[^\S\n]+\1\b", re.I)
_PF_RUNON = re.compile(r"\b[a-z]{3,}\s+[A-Z][a-z]{2,}")
_PF_FIG_LINE = re.compile(r"^(?:Figure:|Fig\.)", re.I)
_PF_FOREIGN = re.compile(
    r"\b(?:le|la|les|des|du|et|el|los|las|del|para|que|una|"
    r"jetez|resserrez|levante|coloque|envuelva|fije|separe|corra|sous|pince)\b",
    re.I,
)
_PF_STATE = (
    (re.compile(r"water off", re.I), re.compile(r"water on", re.I)),
    (re.compile(r"power off", re.I), re.compile(r"power on", re.I)),
    (re.compile(r"propane off", re.I), re.compile(r"propane on", re.I)),
    (re.compile(r"breaker off", re.I), re.compile(r"breaker on", re.I)),
    (re.compile(r"supplies off", re.I), re.compile(r"supplies on", re.I)),
)
_PF_EXPERT = (
    "petit tube in the flame",
    "freeze-sensor seating",
    "e2 or e3 is a freeze",
)
_THETFORD_OFF = (
    "norcold", "furrion", "dometic", "suburban", "coleman", "happijac",
    "atwood", "girard", "power gear", "lippert",
)
_FURRION_OFF = (
    "norcold", "thetford", "dometic", "suburban", "coleman", "happijac", "atwood",
)
_CAPTION_BAD = ("bundled kit sheet", "sketch")


def _pf(number: int, status: str, detail: str) -> Rule:
    return Rule(f"PF-{number:02d}", status != "FAIL", detail, status=status, number=number)


def _case_kind(text: str) -> str:
    head = (text or "")[:1800].lower()
    if "thetford" in head or "42070" in head:
        return "thetford"
    if "furrion" in head or "facr" in head or "ccd-0008666" in head:
        return "furrion"
    return ""


def _bounded_steps(text: str) -> list[str]:
    """A step ends at the next step or at the next section heading."""
    parts = re.split(r"(?=Step\s+\d+\s*:)", _procedure_text(text or ""))
    steps = []
    for part in parts:
        if not re.match(r"Step\s+\d+\s*:", part):
            continue
        cut = re.split(
            r"\n(?=(?:REPAIR BRANCH|REPAIR PROCEDURE|BEFORE YOU START|REMOVAL|"
            r"INSTALLATION|VERIFY|DO NOT|SOURCES|DIAGNOSIS)\b)",
            part,
            maxsplit=1,
        )
        steps.append(cut[0])
    return steps


def _step_actions(step: str) -> list[str]:
    actions = []
    in_do = False
    for line in step.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("do this:"):
            in_do = True
            continue
        if in_do and re.match(r"\d+\.\s+", stripped):
            actions.append(re.sub(r"^\d+\.\s+", "", stripped).strip().rstrip(".").lower())
            continue
        if in_do and stripped:
            in_do = False
    return actions


def _sentence_values(text: str) -> list[str]:
    """Procedure sentences, with a wrapped line joined back onto its field."""
    proc = _procedure_text(text or "")
    proc = re.split(r"\nSOURCES\b", proc, maxsplit=1)[0]
    lines = proc.splitlines()
    values = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        match = _PF_FIELD.match(stripped)
        action = re.match(r"\d+\.\s+(\S.*)$", stripped)
        bullet = stripped.startswith("- ")
        if match:
            value = match.group(2).strip()
            index += 1
            while index < len(lines):
                nxt = lines[index].strip()
                if not nxt or _PF_FIELD.match(nxt) or _PF_STOP.match(nxt) or re.match(r"\d+\.\s+", nxt):
                    break
                value = f"{value} {nxt}".strip()
                index += 1
            if value:
                values.append(value)
            continue
        if action:
            value = action.group(1).strip()
            index += 1
            while index < len(lines):
                nxt = lines[index].strip()
                if not nxt or _PF_FIELD.match(nxt) or _PF_STOP.match(nxt) or re.match(r"\d+\.\s+", nxt):
                    break
                value = f"{value} {nxt}".strip()
                index += 1
            values.append(value)
            continue
        if bullet:
            value = stripped[2:].strip()
            index += 1
            while index < len(lines):
                nxt = lines[index].strip()
                if not nxt or _PF_FIELD.match(nxt) or _PF_STOP.match(nxt) or nxt.startswith("- "):
                    break
                if re.match(r"\d+\.\s+", nxt) or nxt.startswith("Step "):
                    break
                value = f"{value} {nxt}".strip()
                index += 1
            if not _PF_PAGE.search(value):
                values.append(value)
            continue
        index += 1
    return values


def _fastener_sequence(text: str) -> Rule:
    """A toilet is not lifted while it is still bolted down, and a removed part goes back.

    The vacuum-breaker sheet used to pull the hose and then lift the toilet,
    with the bolt covers never taken off and never put back. The flange height
    check belongs in Removal, after the toilet is off the bolts.
    """
    if not re.search(r"\b(42070|42109|34123|34122|thetford)\b", text or "", re.I):
        return _rule("fastener_sequence", True, "this sheet does not lift a toilet")
    problems = []
    for block in _branch_chunks(text or ""):
        actions = []
        for step in _bounded_steps(block):
            actions.extend(_step_actions(step))
        if not actions:
            continue
        lift_at = next((i for i, action in enumerate(actions) if re.search(r"\blift the toilet\b", action)), -1)
        fastener_at = next(
            (
                i
                for i, action in enumerate(actions)
                if re.search(r"\btake (?:off )?the (?:bolt covers|nuts)\b|\btake off the bolt covers\b|\bnuts off\b", action)
            ),
            -1,
        )
        if lift_at >= 0 and (fastener_at < 0 or fastener_at > lift_at):
            problems.append("the toilet is lifted before the nuts or bolt covers come off")
        if any(re.search(r"\btake off the bolt covers\b", action) for action in actions) and not any(
            re.search(r"\bbolt covers back\b|\bput the bolt covers\b", action) for action in actions
        ):
            problems.append("the bolt covers come off and are not put back")
        if any(re.search(r"\btake the nuts off\b|\btake off the nuts\b", action) for action in actions) and not any(
            re.search(r"\btighten the nuts\b|\bput the nuts\b", action) for action in actions
        ):
            problems.append("the nuts come off and are not tightened")
        if lift_at >= 0 and not any(re.search(r"\bset the toilet\b|\bplace the toilet\b", action) for action in actions):
            problems.append("the toilet is lifted and not set back")
        if any(re.search(r"\btake off the old floor seal\b|\btake off the old seal\b", action) for action in actions):
            if not any(re.search(r"\bfloor seal\b|\bflange seal\b", action) and re.search(r"\bput\b", action) for action in actions):
                problems.append("the old seal comes off and no seal is put on")
        if any(re.search(r"\bcover the tank hole\b", action) for action in actions) and not any(
            re.search(r"\btake the towel off\b", action) for action in actions
        ):
            problems.append("a towel covers the tank hole and is not taken off")
        if re.search(r"\bflange\b", block, re.I) and re.search(r"\b7/16\b", block):
            inst = block.upper().find("\nINSTALLATION")
            height = block.lower().find("7/16")
            if inst >= 0 and height > inst:
                problems.append("the flange height check sits under Installation")
    if problems:
        return _rule("fastener_sequence", False, problems[0])
    return _rule("fastener_sequence", True, "fasteners come off before the toilet is lifted, and removed parts go back")


def _source_quote_rows(text: str) -> list[tuple[str, str]]:
    match = re.search(r"SOURCES \(SHOP DOCUMENT LIBRARY\)(.*)\Z", text or "", re.S)
    if not match:
        return []
    rows = []
    title = ""
    quote: list[str] = []

    def flush():
        if title:
            rows.append((title, " ".join(quote).strip()))

    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or re.match(r"^(?:UNIT ID|Brand:|Model:|Serial:)", stripped):
            continue
        if stripped.startswith("-") and re.search(r"\bpage\s+\d+\b", stripped, re.I):
            flush()
            title = stripped
            quote = []
            continue
        if title:
            quote.append(stripped)
    flush()
    return rows


def _source_doc_quotes(text: str) -> Rule:
    """Each Sources quote comes from that document, not from a neighbor's line."""
    if not re.search(r"\b42109\b", text or ""):
        return _rule("source_quotes", True, "no kit source quote on this sheet")
    found = {}
    titled = set()
    for title, quote in _source_quote_rows(text):
        doc = ""
        if "42109" in title:
            doc = "42109"
        elif re.search(r"\b3412[23]\b", title):
            doc = "34123"
        elif "42088" in title:
            doc = "42088"
        if not doc:
            continue
        titled.add(doc)
        if quote:
            found[doc] = quote
    if "42109" not in found:
        if "42109" in titled:
            return _rule("source_quotes", False, "42109 has no quote from the water valve kit")
        return _rule("source_quotes", True, "the water-valve source has no separate quote")
    valve = found["42109"].lower()
    owner = (found.get("42088") or "").lower()
    if owner and valve == owner:
        return _rule("source_quotes", False, "42109 repeats the 42088 quote")
    if re.search(r"supply line|supply connection", valve):
        return _rule("source_quotes", False, "42109 quote is the owner-manual supply line")
    if not re.search(r"water valve|pedal|inlet|retainer", valve):
        return _rule("source_quotes", False, "42109 quote does not come from the water valve kit")
    return _rule("source_quotes", True, "each source quote comes from that document")


def _kit_source_sentences() -> list[str]:
    """English lines from the bundled kit sheets, for the mid-phrase check."""
    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    paths = (
        root / "34123-34122-VacBrkr-1.pdf",
        root / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf",
    )
    sentences = []
    try:
        import pymupdf
    except Exception:
        return []
    for path in paths:
        if not path.is_file():
            continue
        doc = pymupdf.open(path)
        try:
            raw = "\n".join(page.get_text() for page in doc)
        finally:
            doc.close()
        raw = raw.replace("\u00ad", "").replace("\u2013", "-").replace("\u2014", "-")
        # A kit sentence wraps across lines. "Secure back of Shroud" continues
        # as "with two O-rings - larger" and "on top and smaller on bottom."
        buf = ""
        for line in raw.splitlines():
            line = re.sub(r"\s+", " ", line).strip()
            if not line:
                continue
            starts = bool(re.match(r"^(?:\d+[\.\)]|[a-c]\.)\s+\S", line))
            if buf and starts:
                if len(buf) >= 12:
                    sentences.append(buf)
                buf = line
            elif buf:
                buf = f"{buf} {line}"
            else:
                buf = line
            if re.search(r"[.!?]$", buf):
                if len(buf) >= 12:
                    sentences.append(buf)
                buf = ""
        if len(buf) >= 12:
            sentences.append(buf)
    return sentences


def _word_tokens(text: str) -> list[str]:
    text = (text or "").lower().replace("shroud", "cover").replace("o-ring", "ring")
    text = text.replace("-", " ")
    return re.findall(r"[a-z0-9]+", text)


def _find_seq(words: list[str], seq: list[str], start: int = 0) -> int:
    if not seq:
        return -1
    limit = len(words) - len(seq) + 1
    for index in range(start, max(start, limit)):
        if words[index : index + len(seq)] == seq:
            return index
    return -1


def _mid_phrase_gap(text: str) -> Rule:
    """A step that keeps the start and the end of a source sentence, and drops the middle."""
    if not re.search(r"\b(34123|42109)\b", text or ""):
        return _rule("mid_phrase", True, "no kit sentence to compare")
    sentences = _kit_source_sentences()
    if not sentences:
        return _rule("mid_phrase", True, "kit source text is not in this checkout")
    skip = {"the", "a", "of", "and", "on", "to", "in"}
    for step in _bounded_steps(text or ""):
        actions = _step_actions(step)
        if not actions:
            heading = re.sub(r"^Step\s+\d+\s*:\s*", "", step.splitlines()[0], flags=re.I)
            actions = [heading]
        for action in actions:
            words = _word_tokens(action)
            if len(words) < 6:
                continue
            head, tail = words[:3], words[-3:]
            for sentence in sentences:
                source = _word_tokens(sentence)
                head_at = _find_seq(source, head)
                if head_at < 0:
                    continue
                tail_at = _find_seq(source, tail, head_at + 3)
                if tail_at < 0:
                    continue
                have = set(words)
                missing = [word for word in source[head_at + 3 : tail_at] if word not in have and word not in skip]
                if len(missing) >= 3:
                    return _rule("mid_phrase", False, f"quote drops {' '.join(missing[:6])} from: {action[:70]}")
    return _rule("mid_phrase", True, "kit quotes keep the source phrase")


def _valve_start_bare(pairs: list[tuple[str, str]]) -> bool:
    """The water-valve repair turn names a place and a tool in plain words."""
    for user, assistant in pairs:
        if "42109" not in (assistant or ""):
            continue
        if not re.search(r"water valve|weeps at the pedal|no leak while flushing", user or "", re.I):
            continue
        low = assistant.lower()
        has_place = bool(re.search(r"\bgo to the water valve\b|\bat the water valve\b|\bat the pedal\b", low))
        has_tool = bool(re.search(r"\b(wrench|plier|screwdriver|towel)\b", low))
        if has_place and has_tool:
            continue
        return True
    return False


def _source_lines(text: str) -> list[str] | None:
    match = re.search(r"SOURCES \(SHOP DOCUMENT LIBRARY\)(.*)\Z", text or "", re.S)
    if not match:
        match = re.search(r"(?m)^SOURCES\b(.*)\Z", text or "", re.S)
    if not match:
        return None
    return [line.strip() for line in match.group(1).splitlines() if line.strip().startswith("-")]


def _page_views(doc) -> list[dict]:
    if doc is None:
        return []
    views = []
    for page in doc:
        lines = [line.strip() for line in page.get_text().splitlines() if line.strip()]
        views.append({
            "lines": lines,
            "images": len(page.get_images() or []),
            "rect": page.rect,
            "words": page.get_text("words") or [],
            "drawings": page.get_drawings() or [],
        })
    return views


def _body_lines(lines: list[str]) -> list[str]:
    body = []
    for line in lines:
        low = line.lower()
        if low == "bay procedure" or low.startswith("tacoma rv center"):
            continue
        body.append(line)
    return body


def _image_rows(doc) -> list[dict]:
    if doc is None:
        return []
    rows = []
    for index, page in enumerate(doc, 1):
        infos = page.get_image_info() or []
        xrefs = [item[0] for item in (page.get_images(full=True) or [])]
        words = page.get_text("words") or []
        for slot, info in enumerate(infos):
            box = info.get("bbox")
            xref = xrefs[slot] if slot < len(xrefs) else info.get("xref")
            digest = ""
            if xref:
                try:
                    raw = doc.extract_image(xref)
                    digest = hashlib.md5(raw["image"]).hexdigest()
                except Exception:
                    digest = str(xref)
            rows.append({
                "page": index,
                "bbox": box,
                "md5": digest or str(xref or slot),
                "words": words,
                "rect": page.rect,
            })
    return rows


def _off_brand(text: str, kind: str) -> str:
    low = (text or "").lower()
    banned = _THETFORD_OFF if kind == "thetford" else _FURRION_OFF if kind == "furrion" else ()
    for token in banned:
        if token in low:
            return token
    return ""


def _state_conflict(step: str) -> str:
    for off, on in _PF_STATE:
        if off.search(step) and on.search(step):
            return f"{off.pattern} and {on.pattern}"
    return ""


def _branch_titles(text: str) -> list[str]:
    titles = []
    lines = (text or "").splitlines()
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped != "REPAIR BRANCH" and not stripped.startswith("REPAIR PROCEDURE"):
            continue
        for nxt in lines[index + 1:]:
            if nxt.strip():
                titles.append(nxt.strip())
                break
    return titles


def _thetford_title_gap(titles: list[str]) -> tuple[list[str], set[int]]:
    extra = []
    matched: set[int] = set()
    for title in titles:
        low = title.lower()
        hit = None
        for index, keys in enumerate(_THETFORD_BRANCHES):
            if any(key in low for key in keys):
                hit = index
                break
        if hit is None:
            extra.append(title)
        else:
            matched.add(hit)
    return extra, matched


def _captions_tied_to_manual(text: str) -> bool:
    blocks = _blocks(text or "")
    saw = False
    for block in blocks:
        if not _figure_caption_lines(block):
            continue
        saw = True
        if not _DOC_ID_RE.search(block):
            return False
    if saw:
        return True
    return bool(_DOC_ID_RE.search(text or ""))


def _segment_hits_rect(seg, x0: float, y0: float, x1: float, y1: float) -> bool:
    """True when a connector segment crosses the YES or NO word box."""
    ax, ay, bx, by = seg
    inside, left, right, bottom, top = 0, 1, 2, 4, 8

    def code(x: float, y: float) -> int:
        bits = inside
        if x < x0:
            bits |= left
        elif x > x1:
            bits |= right
        if y < y0:
            bits |= bottom
        elif y > y1:
            bits |= top
        return bits

    c1, c2 = code(ax, ay), code(bx, by)
    for _ in range(12):
        if not (c1 | c2):
            return True
        if c1 & c2:
            return False
        bits = c1 or c2
        if bits & top:
            ax, ay, bx, by, c1, c2 = _clip(ax, ay, bx, by, c1, c2, y1, horizontal=False)
        elif bits & bottom:
            ax, ay, bx, by, c1, c2 = _clip(ax, ay, bx, by, c1, c2, y0, horizontal=False)
        elif bits & right:
            ax, ay, bx, by, c1, c2 = _clip(ax, ay, bx, by, c1, c2, x1, horizontal=True)
        else:
            ax, ay, bx, by, c1, c2 = _clip(ax, ay, bx, by, c1, c2, x0, horizontal=True)
        c1, c2 = code(ax, ay), code(bx, by)
    return False


def _clip(ax, ay, bx, by, c1, c2, edge: float, *, horizontal: bool):
    if c1:
        if horizontal:
            if bx != ax:
                ay = ay + (by - ay) * (edge - ax) / (bx - ax)
            ax = edge
        else:
            if by != ay:
                ax = ax + (bx - ax) * (edge - ay) / (by - ay)
            ay = edge
    else:
        if horizontal:
            if bx != ax:
                by = ay + (by - ay) * (edge - ax) / (bx - ax)
            bx = edge
        else:
            if by != ay:
                bx = ax + (bx - ax) * (edge - ay) / (by - ay)
            by = edge
    return ax, ay, bx, by, c1, c2


def _yes_no_stroke_hits(doc) -> list[str]:
    problems = []
    for index, page in enumerate(doc, 1):
        words = [
            word for word in (page.get_text("words") or [])
            if str(word[4]).strip().upper() in {"YES", "NO"}
        ]
        segments = []
        for drawing in page.get_drawings() or []:
            for item in drawing.get("items") or []:
                if not item or item[0] != "l":
                    continue
                p1, p2 = item[1], item[2]
                segments.append((float(p1.x), float(p1.y), float(p2.x), float(p2.y)))
        for word in words:
            if any(_segment_hits_rect(seg, word[0], word[1], word[2], word[3]) for seg in segments):
                problems.append(f"page {index} {word[4]} overlaps a connector")
    return problems


def _branch_chunks(text: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r"REPAIR BRANCH|REPAIR PROCEDURE", text or "")]
    if not starts:
        return [text or ""]
    ends = starts[1:] + [len(text)]
    return [text[start:end] for start, end in zip(starts, ends)]


def _actions_repeated_in_a_branch(text: str) -> str:
    for block in _branch_chunks(text):
        seen = []
        for step in _bounded_steps(block):
            for action in _step_actions(step):
                if not action or action.startswith("confirm "):
                    continue
                if action in seen:
                    return action
                seen.append(action)
    return ""


def _cited_doc_pages(text: str) -> set[tuple[str, str]]:
    body = re.split(r"SOURCES \(SHOP DOCUMENT LIBRARY\)", text or "", maxsplit=1)[0]
    found = set()
    for match in re.finditer(r"\b(42088|34122|34123|42109)\b", body):
        window = body[max(0, match.start() - 80) : match.end() + 80]
        for page in re.findall(r"\bpage\s+(\d+)\b", window, re.I):
            doc = "34123" if match.group(1) in {"34122", "34123"} else match.group(1)
            found.add((doc, page))
    return found


def _sources_miss_cites(text: str) -> str:
    sources = _source_lines(text)
    if sources is None:
        return ""
    blob = "\n".join(sources)
    missing = []
    for doc, page in sorted(_cited_doc_pages(text)):
        doc_ok = doc in blob or (doc == "34123" and "34122" in blob)
        if not doc_ok or not re.search(rf"\bpage\s+{page}\b", blob, re.I):
            missing.append(f"{doc} p{page}")
    return ", ".join(missing)


def _before_blocks(text: str) -> list[str]:
    return re.findall(
        r"BEFORE YOU START\s*(.*?)(?=\n(?:REMOVAL|INSTALLATION|VERIFY|Step\s+\d+))",
        text or "",
        re.S,
    )


def _before_owner_lines(text: str) -> str:
    for block in _before_blocks(text):
        low = block.lower()
        if "drain the holding tank" in low or "add the tank deodorant" in low:
            return "before you start has an owner-manual chore"
        if re.search(r"rinse the toilet|wash the toilet", low):
            return "before you start has an owner-manual chore"
        if re.search(r"water on", low) and re.search(r"water off", low):
            return "before you start says water on and water off"
    return ""


def _bad_repeats_itself(text: str) -> str:
    for step in _bounded_steps(text):
        for line in step.splitlines():
            if not line.strip().lower().startswith("bad looks like:"):
                continue
            value = line.split(":", 1)[-1].strip()
            parts = [part.strip().lower().rstrip(".") for part in re.split(r"[.!?]", value) if part.strip()]
            if len(parts) >= 2 and len(set(parts)) < len(parts):
                return value[:80]
            if len(parts) >= 2:
                left, right = _token_set(parts[0]), _token_set(parts[1])
                short = left if len(left) <= len(right) else right
                if len(short) >= 3 and len(left & right) / len(short) >= 0.6:
                    return value[:80]
    return ""


def _fail_copies_bad(text: str) -> str:
    for step in _bounded_steps(text):
        bad = ""
        fail = ""
        for line in step.splitlines():
            low = line.strip().lower()
            if low.startswith("bad looks like:"):
                bad = low.split(":", 1)[-1].strip().rstrip(".")
            elif low.startswith("if it fails:"):
                fail = low.split(":", 1)[-1].strip().rstrip(".")
        if bad and fail and bad == fail:
            return bad[:80]
    return ""


def _identical_tool_lists(text: str) -> str:
    for block in _branch_chunks(text):
        tools = []
        steps = _bounded_steps(block)
        for step in steps:
            line = ""
            for raw in step.splitlines():
                if raw.strip().lower().startswith("tools:"):
                    line = raw.strip().lower()
                    break
            tools.append(line)
        filled = [line for line in tools if line]
        if len(steps) >= 6 and len(filled) == len(steps) and len(set(filled)) == 1:
            if filled[0].count(",") >= 2:
                return filled[0][:80]
    return ""


def _stub_removal(text: str) -> str:
    for block in _branch_chunks(text):
        removal = []
        in_removal = False
        for line in block.splitlines():
            stripped = line.strip()
            if stripped == "REMOVAL":
                in_removal = True
                continue
            if stripped in {"INSTALLATION", "VERIFY"}:
                in_removal = False
            if in_removal and re.match(r"Step\s+\d+\s*:", stripped):
                removal.append(stripped)
        if len(removal) == 1 and re.match(r"Step\s+\d+\s*:\s*Check\b", removal[0], re.I):
            return removal[0][:80]
    return ""


def _pedal_figure_step(text: str) -> str:
    for step in _bounded_steps(text):
        if not re.search(r"PEDAL REMOVED", step, re.I):
            continue
        head = step.splitlines()[0]
        if not re.search(r"pedal", head, re.I) or not re.search(r"\boff\b", head, re.I):
            return head[:80]
    return ""


def _yes_no_label_faults(doc) -> list[str]:
    problems = []
    for index, page in enumerate(doc, 1):
        words = page.get_text("words") or []
        labels = [word for word in words if str(word[4]).strip().upper() in {"YES", "NO"}]
        segments = []
        for drawing in page.get_drawings() or []:
            for item in drawing.get("items") or []:
                if not item or item[0] != "l":
                    continue
                p1, p2 = item[1], item[2]
                segments.append((float(p1.x), float(p1.y), float(p2.x), float(p2.y)))
        for word in labels:
            height = float(word[3]) - float(word[1])
            if height < 7.0:
                problems.append(f"page {index} {word[4]} is {height:.1f}pt")
                continue
            cx = (float(word[0]) + float(word[2])) / 2.0
            cy = (float(word[1]) + float(word[3])) / 2.0
            best = None
            best_d = 1e9
            for x1, y1, x2, y2 in segments:
                if abs(y2 - y1) > 10 or abs(x2 - x1) < 18:
                    continue
                dist = math.hypot(cx - x1, cy - y1)
                if dist < best_d:
                    best_d = dist
                    best = (x1, x2)
            if not best or best_d > 70:
                continue
            x1, x2 = best
            if x2 < x1 - 8 and cx > x1 + 10:
                problems.append(f"page {index} {word[4]} is right of a left arrow")
            elif x1 < x2 - 8 and cx < x1 - 10:
                problems.append(f"page {index} {word[4]} is left of a right arrow")
    return problems


def _soft_or_cut_figures(doc) -> list[str]:
    problems = []
    if doc is None:
        return problems
    for index, page in enumerate(doc, 1):
        for line in page.get_text().splitlines():
            if re.fullmatch(r"Fig\.?\s*3\s+WATER", line.strip(), re.I):
                problems.append(f"page {index} Fig. 3 caption is cut off at WATER")
        for info in page.get_image_info() or []:
            bbox = info.get("bbox") or ()
            width = int(info.get("width") or 0)
            if len(bbox) < 4 or width <= 0:
                continue
            shown = float(bbox[2]) - float(bbox[0])
            if width < 220 and shown > 280:
                problems.append(f"page {index} figure is {width}px drawn at {shown:.0f}pt")
            height = int(info.get("height") or 0)
            if width >= 220 and height > width * 1.35 and shown > 280:
                problems.append(
                    f"page {index} figure is {width}x{height}px, so its caption fills the page"
                )
    return problems


def grade_past_fails(doc, text: str) -> list[Rule]:
    """PF-01..PF-33. FAIL only on a definite hit. MANUAL keeps a human remainder."""
    raw = text or ""
    low = raw.lower()
    kind = _case_kind(raw)
    steps = _bounded_steps(raw)
    sentences = _sentence_values(raw)
    pages = _page_views(doc)
    images = _image_rows(doc)
    rules = []

    cut = [value for value in sentences if re.search(r"\(Fig\s*\.", value) or re.search(r"\b(?:is|the|and)\s*$", value, re.I)]
    if re.search(r"\(Fig\s*\.", raw) or cut:
        sample = cut[0] if cut else "(Fig ."
        rules.append(_pf(1, "FAIL", f"cut-off sentence: {sample[:80]}"))
    else:
        rules.append(_pf(1, "PASS", "no cut-off ending on a procedure sentence"))

    bare = []
    runon = []
    for value in sentences:
        if _words(value) >= 3 and not re.search(r"[.!?]$", value):
            bare.append(value)
        if _PF_RUNON.search(value):
            runon.append(value)
    if bare or runon:
        sample = (bare or runon)[0]
        rules.append(_pf(2, "FAIL", f"missing stop or run-on: {sample[:80]}"))
    else:
        rules.append(_pf(2, "PASS", "procedure sentences end with a stop"))

    fillers = [phrase for phrase in ("unconfirmed", "not stated in this sheet", "see doc.") if phrase in low]
    rules.append(_pf(3, "FAIL" if fillers else "PASS", ", ".join(fillers) if fillers else "no placeholder tokens"))

    foreign = []
    letters = [ch for ch in raw if ch.isalpha()]
    odd = sum(1 for ch in letters if ord(ch) > 127)
    ratio = (odd / len(letters)) if letters else 0
    for line in raw.splitlines():
        if len(_PF_FOREIGN.findall(line)) >= 2:
            foreign.append(line.strip())
    if foreign or ratio > 0.02:
        rules.append(_pf(4, "FAIL", (foreign[0][:80] if foreign else f"non-English letters {ratio:.1%}")))
    else:
        rules.append(_pf(4, "PASS", "steps and quotes stay in plain English"))

    glued = _PF_GLUED_DOC.search(raw)
    rules.append(_pf(
        5,
        "FAIL" if glued else "PASS",
        glued.group(0)[:80] if glued else "no doc id glued to the front of a quote",
    ))

    length = _sentence_length(raw)
    rules.append(_pf(6, "PASS" if length.ok else "FAIL", length.detail))

    doubled = []
    for line in raw.splitlines():
        match = _PF_DOUBLE.search(line)
        if match and match.group(1).lower() not in {"yes", "no"}:
            doubled.append(match.group(0))
    rules.append(_pf(7, "FAIL" if doubled else "PASS", doubled[0] if doubled else "no doubled word"))

    if not steps:
        rules.append(_pf(8, "FAIL", "flowchart only; no numbered repair steps"))
    elif kind == "thetford":
        full = len(steps) >= 14 and "REMOVAL" in raw and "INSTALLATION" in raw
        rules.append(_pf(
            8,
            "PASS" if full else "FAIL",
            f"{len(steps)} numbered steps include removal and installation"
            if full else
            f"{len(steps)} steps; the Thetford repair is the full kit, not a short check sheet",
        ))
    else:
        rules.append(_pf(8, "MANUAL", f"{len(steps)} numbered steps; the expected count is a human compare"))

    flat = []
    for step in steps:
        flat.extend(_step_actions(step))
    dupes = [flat[i] for i in range(1, len(flat)) if flat[i] and flat[i] == flat[i - 1]]
    again = _actions_repeated_in_a_branch(raw)
    stub = _stub_removal(raw) if kind == "thetford" else ""
    if dupes or again or stub:
        detail = (
            f"repeated action: {(dupes or [again])[0][:80]}"
            if dupes or again else
            f"removal is only a check: {stub}"
        )
        rules.append(_pf(9, "FAIL", detail))
    elif kind == "thetford":
        titles = _branch_titles(raw)
        extra, matched = _thetford_title_gap(titles)
        if extra or len(matched) < 4 or len(titles) != 4:
            sample = extra[0] if extra else f"{len(titles)} branch titles"
            rules.append(_pf(9, "FAIL", f"procedure title is not one of the four asked-for repairs: {sample[:80]}"))
        else:
            rules.append(_pf(9, "PASS", "four asked-for branches and no repeated action"))
    else:
        rules.append(_pf(9, "MANUAL", "no adjacent action is repeated; an extra procedure title still needs the asked-for part"))

    missing = []
    conflicts = []
    for step in steps:
        labels = []
        for line in step.splitlines():
            stripped = line.strip().lower()
            for name in LABEL_ORDER:
                if stripped.startswith(name):
                    labels.append(name)
                    break
        absent = [name[:-1] for name in REQUIRED_LABELS if name not in labels]
        if absent:
            missing.append(step.splitlines()[0][:60] + " missing " + ", ".join(absent))
        conflict = _state_conflict(step)
        if conflict:
            conflicts.append(step.splitlines()[0][:60] + " " + conflict)
    bad_repeat = _bad_repeats_itself(raw)
    copied_fail = _fail_copies_bad(raw)
    same_tools = _identical_tool_lists(raw) if kind == "thetford" else ""
    extra = []
    if bad_repeat:
        extra.append(f"bad line repeats itself: {bad_repeat}")
    if copied_fail:
        extra.append(f"if it fails repeats the bad line: {copied_fail}")
    if same_tools:
        extra.append(f"every step lists the same tools: {same_tools}")
    if missing or conflicts or extra:
        rules.append(_pf(10, "FAIL", (missing or conflicts or extra)[0]))
    else:
        rules.append(_pf(
            10,
            "PASS",
            "Do this, Good looks like, and Next are on every step; Bad looks like is specific or omitted; safety stays once per section",
        ))

    yes_lines = [line.strip() for line in raw.splitlines() if line.strip().upper() in {"YES", "NO"}]
    doubled_label = [line for line in raw.splitlines() if re.search(r"\bYES\s+YES\b|\bNO\s+NO\b", line)]
    has_yes = any(line == "YES" for line in yes_lines)
    has_no = any(line == "NO" for line in yes_lines)
    yes_count = yes_lines.count("YES")
    no_count = yes_lines.count("NO")
    if doubled_label or not has_yes or not has_no:
        detail = doubled_label[0].strip() if doubled_label else "flowchart is missing YES or NO"
        rules.append(_pf(11, "FAIL", detail[:80]))
    elif yes_count != no_count:
        rules.append(_pf(11, "FAIL", f"YES {yes_count} and NO {no_count} do not pair"))
    elif doc is not None:
        rules.append(_pf(11, "PASS", f"YES {yes_count} and NO {no_count}, one pair per diamond"))
    else:
        rules.append(_pf(11, "MANUAL", f"YES {yes_count} and NO {no_count}; the diamond graph still needs the PDF"))

    if kind == "thetford":
        tokens_ok = ("42109" in raw or "water valve" in low) and ("vacuum breaker" in low or "34122" in raw or "34123" in raw)
        if "norcold" in low or not tokens_ok:
            rules.append(_pf(12, "FAIL", "Thetford sheet is missing the valve or vacuum-breaker repair"))
        else:
            rules.append(_pf(12, "PASS", "repair names the water valve and the vacuum breaker"))
    elif kind == "furrion":
        tokens_ok = "rooftop" in low or "ccd-0007990" in low or "freeze" in low
        if "norcold" in low or not tokens_ok:
            rules.append(_pf(12, "FAIL", "rooftop sheet is missing the freeze or drain repair"))
        else:
            rules.append(_pf(12, "PASS", "repair stays on the rooftop freeze and drain path"))
    else:
        rules.append(_pf(12, "MANUAL", "no pinned repair phrase for this case"))

    sources = _source_lines(raw)
    missed_cites = _sources_miss_cites(raw) if kind == "thetford" else ""
    if sources is None:
        rules.append(_pf(13, "FAIL", "Sources section is missing"))
    elif not sources or any(not _PF_PAGE.search(line) for line in sources):
        rules.append(_pf(13, "FAIL", "a source line has no page"))
    elif missed_cites:
        rules.append(_pf(13, "FAIL", f"Sources is missing {missed_cites}"))
    else:
        rules.append(_pf(13, "PASS", f"{len(sources)} sources, each with a page"))

    if kind == "thetford":
        needed = [token for token in ("42109", "34122", "42088") if token not in raw and not (token == "34122" and "34123" in raw)]
        rules.append(_pf(14, "FAIL" if needed else "PASS", ", ".join(needed) if needed else "42109, 34122/34123, and 42088 are still cited"))
    elif kind == "furrion":
        needed = [token for token in ("CCD-0008666", "CCD-0007990") if token not in raw]
        rules.append(_pf(14, "FAIL" if needed else "PASS", ", ".join(needed) if needed else "CCD-0008666 and CCD-0007990 are still cited"))
    else:
        rules.append(_pf(14, "MANUAL", "no known-good cite set for this case"))

    cite_lines = []
    orphans = 0
    if pages:
        for view in pages:
            hits = [line for line in view["lines"] if _PF_FIG_LINE.match(line)]
            cite_lines.extend(hits)
            if not view["images"]:
                orphans += len(hits)
        image_count = len(images)
        if cite_lines and image_count == 0:
            rules.append(_pf(15, "FAIL", f"{len(cite_lines)} figure cites and no embedded image"))
        elif orphans > image_count:
            rules.append(_pf(15, "FAIL", f"{orphans} figure cites are not drawn ({image_count} images)"))
        else:
            misplaced = _pedal_figure_step(raw)
            if misplaced:
                rules.append(_pf(15, "FAIL", f"PEDAL REMOVED is under {misplaced}"))
            else:
                rules.append(_pf(15, "PASS", f"{image_count} images cover the figure cites"))
    elif cite_lines or re.search(r"(?m)^(Figure:|Fig\.)", raw):
        rules.append(_pf(15, "MANUAL", "figure cites need the PDF images"))
    else:
        rules.append(_pf(15, "PASS", "no figure cite in the text extract"))

    if doc is None:
        rules.append(_pf(16, "MANUAL", "clipping needs the PDF image boxes"))
    elif not images:
        rules.append(_pf(16, "PASS", "no figure to clip"))
    else:
        clipped = []
        for image in images:
            box = image["bbox"]
            rect = image["rect"]
            if not box:
                clipped.append(f"page {image['page']} image has no box")
                continue
            x0, y0, x1, y1 = box
            if x0 < 12 or y0 < 12 or x1 > rect.width - 12 or y1 > rect.height - 12:
                clipped.append(f"page {image['page']} figure meets the page edge")
            caption = any(
                word[1] >= y1 - 2 and word[1] <= y1 + 48 and word[3] < rect.height - 4
                for word in image["words"]
            )
            if not caption:
                clipped.append(f"page {image['page']} caption is off the page")
        rules.append(_pf(16, "FAIL" if clipped else "PASS", clipped[0] if clipped else "figures sit inset with the caption on the page"))

    if doc is None:
        rules.append(_pf(17, "MANUAL", "image dedupe needs the PDF"))
    elif not images:
        rules.append(_pf(17, "PASS", "no repeated figure"))
    else:
        groups: dict[str, list] = {}
        for image in images:
            groups.setdefault(image["md5"], []).append(image)
        problems = []
        for group in groups.values():
            page_nums = sorted(image["page"] for image in group)
            if len(page_nums) >= 4:
                problems.append(f"same figure on pages {page_nums}")
            elif any(right == left + 1 for left, right in zip(page_nums, page_nums[1:])):
                problems.append(f"same figure on consecutive pages {page_nums}")
            else:
                for image in group:
                    y0 = image["bbox"][1] if image["bbox"] else 0
                    under_step = any(
                        str(word[4]).startswith("Step") and word[3] <= y0 + 4
                        for word in image["words"]
                    )
                    if len(group) > 1 and not under_step:
                        problems.append(f"page {image['page']} repeat is not under its step")
        if problems:
            rules.append(_pf(17, "FAIL", problems[0]))
        elif any(len(group) > 1 for group in groups.values()):
            rules.append(_pf(17, "PASS", "a repeated manual page sits under each step that cites it"))
        else:
            rules.append(_pf(17, "PASS", f"{len(images)} figures, each used once"))

    caption_text = "\n".join(
        line for line in raw.splitlines()
        if _PF_FIG_LINE.match(line.strip()) or re.match(r"(?:CCD|FACT|FACR)-\d+", line.strip())
    ).lower()
    if "bundled kit sheet" in low or any(phrase in caption_text for phrase in _CAPTION_BAD):
        rules.append(_pf(18, "FAIL", "caption is a sketch or a bundled kit sheet"))
    else:
        captions = _figure_caption_lines(raw)
        loose = [line for line in captions if not _FIG_LABEL_RE.search(line)]
        if loose:
            rules.append(_pf(18, "FAIL", f"caption is not a manual figure id: {loose[0][:80]}"))
        elif captions and not _captions_tied_to_manual(raw):
            rules.append(_pf(18, "FAIL", "a Fig. caption sits in a branch that does not cite the manual"))
        else:
            soft = _soft_or_cut_figures(doc) if kind == "thetford" else []
            if soft:
                rules.append(_pf(18, "FAIL", soft[0]))
            elif captions or not re.search(r"(?m)^(Figure:|Fig\.)", raw):
                rules.append(_pf(18, "PASS", "each Fig. caption is a manual label in a branch that cites the manual"))
            else:
                rules.append(_pf(18, "MANUAL", "no sketch caption; the manual id on the caption is a human check"))

    if not kind:
        rules.append(_pf(19, "MANUAL", "figure brand needs a known case"))
    else:
        brand_hit = _off_brand(caption_text, kind)
        rules.append(_pf(
            19,
            "FAIL" if brand_hit else "PASS",
            f"caption names {brand_hit}" if brand_hit else "figure captions match the case brand",
        ))

    if doc is None:
        rules.append(_pf(20, "MANUAL", "YES and NO spacing against the arrows is a 90 dpi check"))
    else:
        crowded = _yes_no_stroke_hits(doc) + _yes_no_label_faults(doc)
        rules.append(_pf(
            20,
            "FAIL" if crowded else "PASS",
            crowded[0] if crowded else "YES and NO labels do not sit on a connector",
        ))

    if doc is None:
        rules.append(_pf(21, "MANUAL", "bar overlap needs the PDF"))
    else:
        covered = []
        for index, view in enumerate(pages, 1):
            for drawing in view["drawings"]:
                rect = drawing.get("rect")
                if not rect or rect.width < 400 or not (8 < rect.height < 28):
                    continue
                inside = []
                for word in view["words"]:
                    cx = (word[0] + word[2]) / 2
                    cy = (word[1] + word[3]) / 2
                    if rect.x0 - 1 <= cx <= rect.x1 + 1 and rect.y0 - 0.5 <= cy <= rect.y1 + 0.5:
                        inside.append(str(word[4]))
                blob = " ".join(inside).lower()
                if any(token in blob for token in ("step", "do this", "good looks", "where:")):
                    covered.append(f"page {index} bar covers step text")
        rules.append(_pf(21, "FAIL" if covered else "PASS", covered[0] if covered else "section bars hold their own headings"))

    if not pages:
        rules.append(_pf(22, "MANUAL", "orphan headings need the PDF pages"))
        rules.append(_pf(23, "MANUAL", "page splits need the PDF pages"))
        rules.append(_pf(24, "MANUAL", "page count needs the PDF"))
    else:
        orphans_h = []
        repeats = []
        empty = []
        for index, view in enumerate(pages):
            body = _body_lines(view["lines"])
            if body and _PF_HEADING.match(body[-1]):
                orphans_h.append(f"page {index + 1} ends on {body[-1]}")
            if index + 1 < len(pages):
                nxt = _body_lines(pages[index + 1]["lines"])
                if body and nxt and _PF_HEADING.match(body[-1]) and body[-1].lower() == nxt[0].lower():
                    repeats.append(f"{body[-1]} repeats onto page {index + 2}")
            if view["images"] == 0 and len(body) <= 3 and not any(line.startswith("Step ") for line in body):
                empty.append(f"page {index + 1} is nearly empty")
        rules.append(_pf(22, "FAIL" if orphans_h else "PASS", orphans_h[0] if orphans_h else "no heading is stranded at the bottom of a page"))
        if repeats or empty:
            rules.append(_pf(23, "FAIL", (repeats or empty)[0]))
        else:
            rules.append(_pf(23, "PASS", f"{len(pages)} pages, no repeated heading and no empty trailing page"))
        count = len(pages)
        if kind == "thetford":
            limit = 24
        elif kind == "furrion":
            limit = 18
        else:
            limit = 0
        if not limit:
            rules.append(_pf(24, "MANUAL", f"{count} pages; no baseline for this case"))
        elif count > limit:
            rules.append(_pf(24, "FAIL", f"{count} pages over the {limit}-page ceiling"))
        else:
            rules.append(_pf(24, "PASS", f"{count} pages within the {limit}-page ceiling"))

    meta = []
    for line in raw.splitlines():
        line_low = line.lower()
        if "closest reference" in line_low or "excerpt" in line_low:
            meta.append(line.strip())
        elif re.search(r"\blibrary\b", line_low) and "document library" not in line_low:
            meta.append(line.strip())
    rules.append(_pf(25, "FAIL" if meta else "PASS", meta[0][:80] if meta else "no internal note on the sheet"))

    if sources is None:
        rules.append(_pf(26, "MANUAL", "no Sources section to compare"))
    elif kind and any(_off_brand(line, kind) for line in sources):
        hit = next(line for line in sources if _off_brand(line, kind))
        rules.append(_pf(26, "FAIL", f"off-brand source: {hit[:80]}"))
    elif kind:
        keys = _CASE_SOURCE_KEYS.get(kind) or ()
        off_topic = [line for line in sources if not any(key in line.lower() for key in keys)]
        if off_topic:
            rules.append(_pf(26, "FAIL", f"source line does not overlap this case: {off_topic[0][:80]}"))
        else:
            rules.append(_pf(26, "PASS", "each source line overlaps this case"))
    else:
        rules.append(_pf(26, "MANUAL", "off-topic snippets need the case brand"))

    jargon = []
    if re.search(r"\bchannel\b", low):
        jargon.append("channel")
    if ".pdf" in low:
        jargon.append(".pdf")
    rules.append(_pf(27, "FAIL" if jargon else "PASS", ", ".join(jargon) if jargon else "no channel or raw filename"))

    stray = re.search(r"(?m)^\s*\d+\.\s+\d+\.", raw)
    field_stray = [value for value in sentences if re.match(r"\d+\.\s+\d+\.", value)]
    if stray or field_stray:
        rules.append(_pf(28, "FAIL", (stray.group(0) if stray else field_stray[0])[:80]))
    else:
        rules.append(_pf(28, "PASS", "no stray numbering"))

    concern = ""
    concern_match = re.search(r"(?m)^CONCERN\s*$\n\s*(.+)", raw)
    if concern_match:
        concern = concern_match.group(1).strip()
    if concern.lower() in {"", "-", "concern", "n/a", "none", "unknown", "todo"}:
        rules.append(_pf(29, "FAIL", "CONCERN is blank"))
    else:
        rules.append(_pf(29, "PASS", "CONCERN names this case"))

    if not kind:
        rules.append(_pf(30, "MANUAL", "cite brand needs a known case"))
    else:
        brand_hit = _off_brand(raw, kind)
        rules.append(_pf(
            30,
            "FAIL" if brand_hit else "PASS",
            f"sheet names {brand_hit}" if brand_hit else "cites stay on this case's brand",
        ))

    model = ""
    model_match = re.search(r"(?m)^MODEL\s*$\n\s*(.+)", raw)
    if model_match:
        model = model_match.group(1).strip()
    if model.lower() in {"", "-", "model", "n/a", "none"}:
        rules.append(_pf(31, "FAIL", "MODEL is blank"))
    elif kind == "thetford" and "42070" in low and "42070" not in model:
        rules.append(_pf(31, "FAIL", "MODEL does not include 42070"))
    elif kind == "furrion" and "facr08" in low and "facr08" not in model.lower():
        rules.append(_pf(31, "FAIL", "MODEL does not include FACR08"))
    else:
        rules.append(_pf(31, "PASS", model[:80]))

    expert = [phrase for phrase in _PF_EXPERT if phrase in low]
    if expert:
        rules.append(_pf(32, "FAIL", expert[0]))
    else:
        rules.append(_pf(32, "MANUAL", "banned phrases are absent; technical correctness still needs expert review"))

    step_conflicts = [step.splitlines()[0][:70] for step in steps if _state_conflict(step)]
    owner = _before_owner_lines(raw) if kind == "thetford" else ""
    if step_conflicts or owner:
        rules.append(_pf(33, "FAIL", step_conflicts[0] if step_conflicts else owner))
    else:
        rules.append(_pf(33, "PASS", "no step pairs water, power, or propane off with on"))

    return rules


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
        if rule.name.startswith("PF-"):
            lines.append(f"{rule.name} {rule.status}" + (f"  {rule.detail}" if rule.detail else ""))
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
