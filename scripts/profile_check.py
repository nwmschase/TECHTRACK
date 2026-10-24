#!/usr/bin/env python3
"""Score a Bay PDF or a Guided Diagnostics transcript against the established profiles.

Usage: python3 scripts/profile_check.py <pdf-or-transcript.txt>

Prints PASS or FAIL for each rule, then the
v1.2 scorecard. A line a human must judge prints MANUAL. Exit 0 when no rule FAILs.
A PDF is checked for section order, branch subsections, step line order,
banned strings, sentence length, figure width, and figure placement.
A transcript is checked for the chat profile: no label block, no step
counter, a photo only when it helps, no figure without an ask, and no repeats.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
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


def _quote_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def source_page_rule(text: str, library: list[dict]) -> Rule:
    """rev6 (Leader rev5 item 2): each quoted Sources line cites the page its words are on.

    library rows carry title, page and chunk_text from the shop library (read-only).
    """
    lines = (text or "").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip().startswith("SOURCES (SHOP DOCUMENT LIBRARY)"))
    except StopIteration:
        return _rule("source_pages", True, "no Sources block")
    rows = []
    current = None
    for line in lines[start + 1:]:
        m = re.match(r"^\s*-\s+(.+?)\s+page\s+(\d+)\s*$", line)
        if m:
            current = {"title": m.group(1), "page": int(m.group(2)), "quote": ""}
            rows.append(current)
            continue
        if current is not None and line.strip() and not line.strip().startswith("-"):
            if re.match(r"^(?:BAY PROCEDURE|Tacoma RV Center|Sources)", line.strip()):
                continue
            current["quote"] = (current["quote"] + " " + line.strip()).strip()
    wrong = []
    for row in rows:
        quote = _quote_key(row["quote"])[:60]
        if len(quote) < 20:
            continue
        numbers = set(re.findall(r"\b\d{5}\b", row["title"]))
        pages = sorted({
            int(chunk.get("page") or 0)
            for chunk in library or []
            if (not numbers or numbers & set(re.findall(r"\b\d{5}\b", str(chunk.get("title") or ""))))
            and quote in _quote_key(str(chunk.get("chunk_text") or ""))
        })
        if not pages:
            wrong.append(f"'{row['quote'][:40]}' not found in {row['title'][:40]}")
        elif row["page"] not in pages:
            wrong.append(f"{row['title'][:40]} page {row['page']}: quote is on page {pages[0]}")
    return _rule("source_pages", not wrong, "each quoted source cites the page its words are on" if not wrong else "; ".join(wrong[:3]))


def printed_figure_number_rule(doc) -> Rule:
    """rev6 (Leader rev5 item 3): the tech sees one number per figure.

    A kit's own printed 'FIGURE N' inside the crop must match the sheet caption 'Fig. N'.
    Reads the image with the tesseract CLI when it is installed; without it the rule is skipped.
    """
    import shutil
    import subprocess
    import tempfile

    if not shutil.which("tesseract"):
        return _rule("figure_printed_number", True, "skipped: tesseract not installed")
    wrong = []
    for page_index, page in enumerate(doc):
        captions = re.findall(r"(?m)^\s*Fig\.\s*(\d+)\b", page.get_text())
        images = sorted(page.get_images(full=True), key=lambda img: min((r.y0 for r in page.get_image_rects(img[0])), default=0))
        for slot, img in enumerate(images):
            if slot >= len(captions):
                break
            data = doc.extract_image(img[0]).get("image") or b""
            with tempfile.NamedTemporaryFile(suffix=".png") as handle:
                handle.write(data)
                handle.flush()
                try:
                    seen = subprocess.run(
                        ["tesseract", handle.name, "-", "--psm", "11"], capture_output=True, text=True, timeout=60
                    ).stdout
                except Exception:
                    continue
            printed = re.findall(r"(?i)\bFIGURE\s+(\d+)\b", seen)
            if any(number != captions[slot] for number in printed):
                wrong.append(f"p{page_index + 1} Fig. {captions[slot]} shows printed FIGURE {printed[0]}")
    return _rule("figure_printed_number", not wrong, "one number per figure" if not wrong else "; ".join(wrong[:3]))


def library_from_db(db_path) -> list[dict]:
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT d.title, c.page, c.chunk_text FROM doc_chunks c JOIN documents d ON d.id = c.document_id"
        ).fetchall()
    finally:
        con.close()
    return [{"title": t, "page": p, "chunk_text": x} for t, p, x in rows]


def check_pdf_bytes(data: bytes, library: list[dict] | None = None) -> list[Rule]:
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        text = "\n".join(page.get_text() for page in doc)
        rules = check_sheet_text(text) + _figure_rules(doc)
        if library is not None:
            rules.append(source_page_rule(text, library))
        rules.append(printed_figure_number_rule(doc))
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
_FIG_LABEL_RE = re.compile(
    r"(?i)^fig\.?\s*\d+\b|\b(?:42109|34122|34123|42088|CCD-\d+|FACT\d*|FACR)\b"
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


def _all_ok(named, *names) -> bool:
    return all(_ok(named, name) for name in names if name in named)


def _first_fail(named, names, default: str) -> str:
    for name in names:
        if name in named and not _ok(named, name):
            return named[name].detail
    return default


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
        (1, "PASS" if _ok(named, "section_order") and _ok(named, "branch_subsections") and _all_ok(named, "source_pages") else "FAIL",
         _first_fail(named, ("source_pages",), "header, flowchart, diagnosis, branches, do not, sources")),
        (2, "PASS" if _all_ok(named, "branch_subsections", "next_chain", "double_removal", "secure_after_hose", "reinstalled", "old_part_removed") else "FAIL",
         _first_fail(named, ("next_chain", "double_removal", "secure_after_hose", "reinstalled", "old_part_removed"), "each branch ends on a confirm with a pass and a fail")),
        (3, "PASS" if not inspected["order"] and _all_ok(named, "where_lines", "profile_labels", "diagnosis_checks", "where_single", "next_single_path") else "FAIL",
         _first_fail(named, ("where_lines", "profile_labels", "diagnosis_checks", "where_single", "next_single_path"), "numbered headings and the same label order")),
        (4, "PASS" if _all_ok(named, "sentence_length", "grammar", "good_is_a_look", "do_item_is_action") else "FAIL", _first_fail(named, ("grammar", "good_is_a_look", "do_item_is_action"), "one action per line, about 12 words")),
        (5, "PASS" if not inspected["generic"] and _all_ok(named, "bad_is_specific") else "FAIL", _first_fail(named, ("bad_is_specific",), "Bad looks like is specific, or left off")),
        (6, "PASS" if _all_ok(named, "figure_width", "figure_placement", "figure_captions", "figure_printed_number") else "FAIL",
         _first_fail(named, ("figure_captions", "figure_printed_number"), "figure width, centering, and caption")),
        (7, invented_status, invented_detail),
        (8, safety_status if _all_ok(named, "before_conflict", "safety_duplicate") else "FAIL",
         _first_fail(named, ("before_conflict", "safety_duplicate"), safety_detail)),
        (9, line_nine, "no photo script, unconfirmed, leaked text, or stray number"),
        (10, "PASS" if _ok(named, "web_content") else "FAIL", "web content stays in Outside sources"),
    ]
    return [_card(number, status, PDF_SCORECARD[number - 1], detail, PDF_AUTO_FAIL) for number, status, detail in rows]


_PF_FIG_LINE = re.compile(r"^(?:Figure:|Fig\.)", re.I)
_PF_STATE = (
    (re.compile(r"water off", re.I), re.compile(r"water on", re.I)),
    (re.compile(r"power off", re.I), re.compile(r"power on", re.I)),
    (re.compile(r"propane off", re.I), re.compile(r"propane on", re.I)),
    (re.compile(r"breaker off", re.I), re.compile(r"breaker on", re.I)),
    (re.compile(r"supplies off", re.I), re.compile(r"supplies on", re.I)),
)
_THETFORD_OFF = (
    "norcold", "furrion", "dometic", "suburban", "coleman", "happijac",
    "atwood", "girard", "power gear", "lippert",
)
_FURRION_OFF = (
    "norcold", "thetford", "dometic", "suburban", "coleman", "happijac", "atwood",
)
_CAPTION_BAD = ("bundled kit sheet", "sketch")


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
        if any(re.search(r"\bcover the (?:tank hole|holding tank opening)\b", action) for action in actions) and not any(
            re.search(r"\btake the towel off\b|\buncover the holding tank\b", action) for action in actions
        ):
            problems.append("a towel covers the holding tank opening and is not taken off")
        if "holding tank" in block.lower() and lift_at >= 0:
            hose_off = next(
                (i for i, action in enumerate(actions) if re.search(r"\bwater hose off\b|\bpull the water hose\b", action)),
                -1,
            )
            hose_on = next(
                (
                    i
                    for i, action in enumerate(actions)
                    if re.search(r"\bwater hose onto\b|\bpush the water hose\b", action)
                ),
                -1,
            )
            if hose_off < 0 or hose_off > lift_at:
                problems.append("the flange branch lifts the toilet before the water hose comes off")
            elif hose_on < 0 or hose_on < lift_at:
                problems.append("the flange branch does not put the water hose back on")
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


def _folded_quote(text: str) -> str:
    """Manual text with ligatures, soft hyphens, and line breaks folded out."""
    raw = unicodedata.normalize("NFKC", text or "")
    raw = raw.replace("\u00ad", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    raw = raw.replace("\u2019", "'").replace("\u2018", "'")
    raw = raw.replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", raw).strip().casefold()


_DOC_CORPUS: dict[str, str | None] = {}


def _manual_corpus(doc: str) -> str | None:
    """Folded text of one bundled manual. None when that file is not here."""
    if doc in _DOC_CORPUS:
        return _DOC_CORPUS[doc]
    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    folded = ""
    if doc == "42088":
        path = root / "om42088_pypdf_pages.json"
        if path.is_file():
            pages = json.loads(path.read_text(encoding="utf-8"))
            folded = _folded_quote(" ".join(page.get("text") or "" for page in pages))
    else:
        name = {
            "34123": "34123-34122-VacBrkr-1.pdf",
            "42109": "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf",
        }.get(doc, "")
        path = root / name if name else None
        if path is not None and path.is_file():
            try:
                import pymupdf
            except Exception:
                _DOC_CORPUS[doc] = None
                return None
            pdf = pymupdf.open(path)
            try:
                folded = _folded_quote("\n".join(page.get_text() for page in pdf))
            finally:
                pdf.close()
    _DOC_CORPUS[doc] = folded or None
    return _DOC_CORPUS[doc]


def _source_doc_quotes(text: str) -> Rule:
    """Each Sources quote is a verbatim sentence from that document."""
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
    missing = []
    for doc, quote in found.items():
        corpus = _manual_corpus(doc)
        if not corpus:
            missing.append(doc)
            continue
        if _folded_quote(quote) not in corpus:
            return _rule("source_quotes", False, f"{doc} quote is not a verbatim sentence from that document")
    if missing and len(missing) == len(found):
        return _rule("source_quotes", True, "source text is not in this checkout")
    return _rule("source_quotes", True, "each source quote is a verbatim sentence from that document")


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


def _state_conflict(step: str) -> str:
    for off, on in _PF_STATE:
        if off.search(step) and on.search(step):
            return f"{off.pattern} and {on.pattern}"
    return ""


def _branch_chunks(text: str) -> list[str]:
    starts = [match.start() for match in re.finditer(r"REPAIR BRANCH|REPAIR PROCEDURE", text or "")]
    if not starts:
        return [text or ""]
    ends = starts[1:] + [len(text)]
    return [text[start:end] for start, end in zip(starts, ends)]


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
    args = list(argv[1:])
    db = None
    if "--db" in args:
        at = args.index("--db")
        db = Path(args[at + 1]) if at + 1 < len(args) else None
        del args[at:at + 2]
    if len(args) != 1:
        print("Usage: python3 scripts/profile_check.py <pdf-or-transcript.txt> [--db library.sqlite]", file=sys.stderr)
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"FAIL  file  {path} is not a file")
        return 1
    if db is not None and path.suffix.lower() == ".pdf":
        rules = check_pdf_bytes(path.read_bytes(), library_from_db(db))
    else:
        rules = check_path(path)
    print(format_report(rules))
    return 0 if all(rule.ok for rule in rules) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
