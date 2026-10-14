"""Headless Thetford check against a copy of the live library.

Does not import the Streamlit app. It reads the shop SQLite file, loads figure
PNGs from an R2 cache directory, then runs the same compile and figure-attach
steps Bay procedure PDF uses. It also plays Guided Diagnostics turns T1-T4
with no model call. ``--live-llm`` sends each turn to grok-4.6 first
(XAI_API_KEY from the environment), then through the same shop guards.
That is the path that can still paste a How block. No-model mode never
builds one, so it cannot catch that leak.

From the repo root:

    python3 scripts/thetford_live_gate.py \\
        --db tests/fixtures/thetford_live_library/library.sqlite \\
        --cache tests/fixtures/thetford_live_library/cache \\
        --out /tmp/thetford-gate

    python3 scripts/thetford_live_gate.py --live-llm \\
        --db /path/to/rv_techtrack_v4.db \\
        --cache /path/to/r2-cache \\
        --out /tmp/thetford-gate

``--cache`` is the directory that mirrors R2 keys. A row whose image_path is
``library/figures/42088-p3.png`` is read from ``{cache}/library/figures/42088-p3.png``.
The database is opened read-only.

Writes ``thetford-bay.pdf``, ``transcript.txt``, ``transcript-profile.txt``,
``report.txt``, and 90 dpi page PNGs under ``--out``. ``--live-llm`` also
writes ``transcript-raw.txt``, the model's reply before the shop guards, and
the report says how many turns the guards rewrote and which guard fired on
each turn. The report includes profile_check for the PDF, the guarded
transcript, and the raw transcript.
Exit 0 when the sheet, the guarded transcript, and (with ``--live-llm``) the
raw reply pass, including 10/10 on the scorecards. A raw FAIL is a failed
check. Exit 1 when a check fails. Exit 2 when the database, the cache, or
(with ``--live-llm``) the xAI key cannot be used.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import (
    apply_chunk_figures,
    compile_bay_procedure,
    render_bay_procedure_pdf,
)
import scripts.profile_check as profile_check

CONCERN = "Thetford 42070 leaks under the flush lever"
CATEGORY = "Plumbing / Toilets"
BRAND = "Thetford"
MODEL = "42070"
TURNS = (
    ("T1", "Thetford 42070 leaks under the flush lever"),
    ("T2", "Show me where that connection is"),
    ("T3", "The supply connection is dry."),
    ("T4", "No leak while flushing. The water valve weeps at the pedal."),
)
_NEEDLES = (
    "%thetford%",
    "%42088%",
    "%42109%",
    "%42110%",
    "%34122%",
    "%34123%",
    "%42070%",
    "%42049%",
)
_TEMPLATE = re.compile(r"\bhow\s*\(|\bnot stated\b", re.I)


def _connect(db: Path):
    uri = "sqlite:///file:" + db.resolve().as_posix() + "?mode=ro&uri=true"
    engine = create_engine(uri)
    return sessionmaker(bind=engine)()


def _english_enough(text: str) -> bool:
    """An English procedure window. A translation column does not count.

    The cut is the language header, so a French tail on an English window
    stays in. A window that is already French or Spanish does not.
    """
    raw = mf._english_prefix(text or "")
    if len(raw) < 80:
        return False
    letters = [ch for ch in raw if ch.isalpha()]
    if letters and sum(1 for ch in letters if ord(ch) > 127) / len(letters) > 0.08:
        return False
    foreign = re.findall(
        r"\b(?:le|la|les|des|du|jetez|el|los|las|para|que|boîtier|crampon)\b",
        raw,
        re.I,
    )
    return len(foreign) < 2


def _rank_chunks(chunks: list[dict], limit: int = 12) -> list[dict]:
    """The live ask returns about 12 chunks. English procedure windows rank first."""

    def score(chunk: dict) -> int:
        text = chunk.get("excerpt") or ""
        title = (chunk.get("title") or "").lower()
        page = int(chunk.get("page") or 0)
        value = 0
        if "42109" in title:
            value += 80
        elif "3412" in title or "vacuum" in title:
            value += 70
        elif "42088" in title and page == 3:
            # One troubleshooting page is useful. It must not outrank a kit window.
            value += 40
        elif "42088" in title:
            value += 10
        if not _english_enough(text):
            value -= 300
        if re.search(r"\b(remove|install|pedal|vacuum breaker|flange|leak)\b", text, re.I):
            value += 15
        return value

    return sorted(chunks, key=score, reverse=True)[:limit]


def _thetford_chunks(session) -> list[dict]:
    blob = (
        "lower("
        "coalesce(d.title, '') || ' ' || coalesce(d.brand, '') || ' ' || "
        "coalesce(d.keywords, '') || ' ' || coalesce(d.clean_title, '') || ' ' || "
        "coalesce(d.doc_number, '') || ' ' || coalesce(d.product_line, '') || ' ' || "
        "coalesce(c.title, '') || ' ' || coalesce(c.keywords, '')"
        ")"
    )
    needle_sql = " OR ".join(f"{blob} LIKE :n{index}" for index in range(len(_NEEDLES)))
    params = {f"n{index}": needle for index, needle in enumerate(_NEEDLES)}
    rows = session.execute(
        text(
            f"""
            SELECT
                c.document_id AS document_id,
                coalesce(c.title, d.title) AS title,
                c.page AS page,
                c.chunk_text AS excerpt,
                c.keywords AS keywords,
                d.file_path AS file_path,
                d.brand AS brand,
                d.models AS models,
                d.clean_title AS clean_title,
                d.product_line AS product_line,
                d.doc_number AS doc_number,
                cat.name AS category
            FROM doc_chunks c
            JOIN documents d ON d.id = c.document_id
            LEFT JOIN categories cat ON cat.id = d.category_id
            WHERE {needle_sql}
            """
        ),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def _asset_rows(session, document_ids: set[int]) -> list[dict]:
    if not document_ids:
        return []
    marks = ", ".join(str(int(item)) for item in sorted(document_ids))
    rows = session.execute(
        text(
            f"""
            SELECT a.id, a.document_id, a.page, a.kind, a.label, a.caption, a.bbox,
                   a.chunk_id, a.image_path, a.width, a.height,
                   d.title AS title, d.file_path AS file_path, d.brand AS brand,
                   d.product_line AS product_line, d.models AS models,
                   d.keywords AS keywords, d.clean_title AS clean_title,
                   d.doc_number AS doc_number, c.name AS category_name
            FROM doc_assets a
            JOIN documents d ON d.id = a.document_id
            LEFT JOIN categories c ON c.id = d.category_id
            WHERE a.document_id IN ({marks})
            """
        )
    ).mappings().all()
    return [dict(row) for row in rows]


def _page_chunks(session, document_ids: set[int]) -> list[dict]:
    """Every chunk of the cited documents. Figure captions can sit outside the ranked windows."""
    if not document_ids:
        return []
    marks = ", ".join(str(int(item)) for item in sorted(document_ids))
    rows = session.execute(
        text(f"SELECT document_id, page, chunk_text FROM doc_chunks WHERE document_id IN ({marks})")
    ).mappings().all()
    return [dict(row) for row in rows]


def _pdf_text(data: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=data, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def _branch_blocks(text: str) -> list[str]:
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


def _sheet_problems(proc, pdf: bytes) -> list[str]:
    problems = []
    titles = " ".join((item.get("title") or "") for item in proc.procedures or [])
    for needle, label in (
        ("supply", "supply connection"),
        ("3412", "vacuum breaker"),
        ("42109", "water valve"),
        ("flange", "flange/seal"),
    ):
        if needle not in titles.lower():
            problems.append(f"missing branch: {label}")
    text = _pdf_text(pdf)
    blocks = _branch_blocks(text)
    if len(blocks) < 4:
        problems.append(f"PDF printed {len(blocks)} repair branches, expected 4")
    for index, block in enumerate(blocks, 1):
        has_removal = "REMOVAL" in block or "Removal: none" in block
        if not has_removal:
            problems.append(f"branch {index} has no Removal")
        if "INSTALLATION" not in block:
            problems.append(f"branch {index} has no Installation")
        if not re.search(r"Step\s+\d+\s*:\s*Confirm\b", block, re.I):
            problems.append(f"branch {index} has no Confirm step")
        confirm = re.search(r"Step\s+\d+\s*:\s*Confirm\b", block, re.I)
        if confirm:
            tail = block[confirm.start():]
            if "Good looks like:" not in tail or "Bad looks like:" not in tail:
                problems.append(f"branch {index} Confirm has no pass/fail")
    valve = next((item for item in proc.procedures or [] if "42109" in (item.get("title") or "")), None)
    if valve:
        tools = " ".join(
            [
                " ".join(valve.get("before") or []),
                " ".join(
                    (step.get("fields") or {}).get("TOOLS / METER SETTING") or ""
                    for step in valve.get("steps") or []
                ),
            ]
        ).lower()
        if "wrench" not in tools and "plier" not in tools:
            problems.append("water valve tools are not the kit Needed list")
        if re.fullmatch(r"tools:\s*a towel\.?", tools.strip(), re.I):
            problems.append("water valve tools are only a towel")
    for procedure in proc.procedures or []:
        for number, step in enumerate(procedure.get("steps") or [], 1):
            for line in mf.step_body_lines(step, show_figure=False):
                if line.startswith("Bad looks like:") and not mf._bad_worth_printing(line.split(":", 1)[1]):
                    problems.append(f"{procedure.get('title')} step {number} Bad line is not specific")
    do_not = " ".join(proc.do_not or []).lower()
    if "antifreeze" in do_not or re.search(r"\bice\b", do_not):
        problems.append("Do Not list has a winterizing item")
    if "scouring" in do_not:
        problems.append("Do Not list has a generic cleaner line")
    return problems


def _keep_figure_detail(detail: str, reply: str) -> str:
    """The shop figure offer. A How block or a 'not stated' filler stays off the reply."""
    text = (detail or "").strip()
    if not text or text in (reply or ""):
        return ""
    if re.match(r"how\s*\(", text, re.I) or re.search(r"\bnot stated\b", text, re.I):
        return ""
    return text


def _append_figure_detail(reply: str, user_msg: str, rows, chunks) -> str:
    """Headless stand-in for the stored-figure offer that runs after the coach.

    A reply that already names the tool and cites the manual is left alone.
    The figure line is only for a turn that asked and still has no procedure.
    """
    asked = mf.wants_manual_image(user_msg) or mf.tech_asked_for_manual_figure(user_msg)
    if not asked:
        return reply
    if "📖" in (reply or "") and re.search(r"\b(wrench|pliers?|flashlight)\b", reply or "", re.I):
        return reply
    chosen = fb.select_library_figures(rows, reply, user_msg, CATEGORY, f"{BRAND} {MODEL}") or []
    if not chosen:
        return reply
    first = chosen[0]
    page = int(first.get("page") or 0)
    doc_id = int(first.get("document_id") or 0)
    page_text = "\n".join(
        (chunk.get("excerpt") or "")
        for chunk in chunks or []
        if int(chunk.get("document_id") or 0) == doc_id and int(chunk.get("page") or 0) == page
    )
    detail = _keep_figure_detail(
        fb.procedure_how(
            first,
            page_text,
            first.get("title") or "",
            first.get("page"),
            CATEGORY,
            f"{BRAND} {MODEL}",
            user_msg,
            reply,
        ),
        reply,
    )
    if not detail:
        return reply
    return ((reply or "").rstrip() + "\n\n" + detail).strip()


def _user_facts(history: list, message: str) -> str:
    """Facts the technician already reported. Later turns must move past them."""
    said = []
    for item in history or []:
        if (item.get("role") or "") == "user":
            said.append(item.get("content") or "")
    said.append(message or "")
    blob = " ".join(said)
    facts = []
    if re.search(r"supply connection is dry", blob, re.I):
        facts.append("The supply connection is dry. Do not repeat that check.")
    if re.search(r"no leak while flushing", blob, re.I):
        facts.append("There is no leak while flushing. The vacuum breaker passed. Do not repeat that check.")
    if re.search(r"weeps at the pedal", blob, re.I):
        facts.append("The water valve weeps at the pedal. The next step is the water valve cartridge.")
    if re.search(r"\bshow me\b", message or "", re.I):
        facts.append("This turn asks where the supply connection is.")
    if not facts:
        facts.append("The leak is under the flush lever. No check is finished yet.")
    return "\n".join(f"- {fact}" for fact in facts)


def _page_has_art(rows, token: str, page: int) -> bool:
    """True when this manual page has a stored page image or figure."""
    for row in rows or []:
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("title", "caption", "label", "doc_number", "file_path", "clean_title")
        )
        if token not in blob:
            continue
        try:
            if int(row.get("page") or 0) != int(page):
                continue
        except (TypeError, ValueError):
            continue
        if row.get("png") or row.get("image_path"):
            return True
    return False


def _turn_plan(history: list, message: str, rows=None) -> dict:
    """The one check this turn is allowed to ask, in the 42088 order."""
    said = " ".join(
        (item.get("content") or "")
        for item in history or []
        if (item.get("role") or "") == "user"
    )
    blob = f"{said} {message or ''}"
    show = bool(re.search(r"\bshow me\b", message or "", re.I))
    if re.search(r"weeps at the pedal", message or "", re.I):
        focus = "valve"
    elif re.search(r"supply connection is dry", blob, re.I):
        focus = "vacuum"
    else:
        focus = "supply"
    cite_42088 = "Thetford Style II OM Permanent RV Toilet 42088, page 3"
    cite_34123 = "Thetford Vacuum Breaker Kit 34123/34122, page 1"
    cite_42109 = "Thetford Water Valve Kit 42109, page 1"
    if focus == "valve":
        plan = {
            "focus": focus,
            "cite": cite_42109,
            "where": "the closet bolts at the floor, on the closet flange",
            "tool": "a 1/2-inch wrench",
            "look": "Take the toilet off the closet bolts",
            "good": "the toilet is off the closet bolts and the water is off",
            "bad": "the toilet is still on the closet bolts, or water still comes out",
            "safety": "",
            "advance": (
                "The tech already reported the weep at the pedal. "
                "Do not check for that weep again. Do not seat the cartridge on this turn. "
                "Say this is the water valve kit 42109 job. The valve is at the pedal. "
                "The first step is one sentence, said once: Turn the RV water off. "
                "Do not repeat that sentence. "
                "The closet bolts that hold the toilet are at the floor, on the closet flange. "
                "Write this as its own sentence: Take the toilet off the closet bolts. "
                "Name the 1/2-inch wrench in the next sentence. "
                "Do not start the bolt sentence with Check. "
                "Do not name pliers. "
                "The good result and the bad result describe that same bolt step, "
                "not seating a cartridge. "
                "Offer to walk the rest one step at a time. "
                "Say the Bay PDF has the full list."
            ),
        }
    elif focus == "vacuum":
        plan = {
            "focus": focus,
            "cite": cite_34123,
            "where": "the vacuum breaker on the flush hose",
            "tool": "none",
            "look": "the vacuum breaker while you flush",
            "good": "no leak while flushing",
            "bad": "it leaks only while flushing",
            "safety": "",
            "advance": (
                "The supply connection is already dry. Flush and watch. "
                "Do not name pliers. Do not cite kit 42109 on this turn."
            ),
        }
    elif show:
        has_art = _page_has_art(rows, "42088", 3)
        if has_art:
            plan = {
                "focus": focus,
                "cite": cite_42088,
                "where": "the back of the toilet, on the attached page image",
                "tool": "none",
                "look": "the water supply line connection at the water valve on that image",
                "good": "none",
                "bad": "none",
                "safety": "",
                "picture": "a page image of 42088 page 3 is attached",
                "advance": (
                    "A page image of this spot is attached to this reply. "
                    "This turn answers where it is. It is not a new test. "
                    "Do not repeat the supply check. Do not name a tool. "
                    "Do not write a good result or a bad result. "
                    "Give one short pointer to where to look on that image, "
                    "using only these manual words: back of the toilet, "
                    "water supply line connection, water valve. "
                    "Start that pointer with 'On this page'. "
                    "End with the exact sentence 'Then do that check and tell me what you see.' "
                    "Do not invent a side or a shape. Do not name a figure number. "
                    "Do not cite kit 42109."
                ),
            }
        else:
            plan = {
                "focus": focus,
                "cite": cite_42088,
                "where": "the back of the toilet",
                "tool": "none",
                "look": "the water supply line connection at the water valve",
                "good": "none",
                "bad": "none",
                "safety": "",
                "picture": "none. The manual has no picture of this spot",
                "advance": (
                    "The manual has no picture of this spot. Say that plainly and briefly. "
                    "Restate the location in one short line: the water supply line connection "
                    "is at the back of the toilet, on the water valve. "
                    "You may ask the tech for a photo of that spot. "
                    "This turn answers where it is. It is not a new test. "
                    "Do not name a tool. Do not write a good result or a bad result. "
                    "End with the exact sentence 'Then do that check and tell me what you see.' "
                    "Do not invent a side or a shape. Do not name a figure. "
                    "Do not cite kit 42109."
                ),
            }
    else:
        plan = {
            "focus": focus,
            "cite": cite_42088,
            "where": "the water valve for the supply connection",
            "tool": "a flashlight",
            "look": "the supply connection at the water valve",
            "good": "the supply connection stays dry",
            "bad": "water comes out of the supply connection",
            "safety": "",
            "advance": "Start with owner manual 42088. Do not cite kit 42109 on this turn.",
        }
    return plan


def _ordered_excerpts(chunks, focus: str) -> list[str]:
    """Owner-manual troubleshooting first, then the kit for this step.

    The ranked Bay list leads with the water-valve kit. This selection does
    not. Page 3 of 42088 stays in front even when it is outside those 12.
    """

    def title_of(chunk) -> str:
        return chunk.get("title") or ""

    def is_trouble(chunk) -> bool:
        page = int(chunk.get("page") or 0)
        text = chunk.get("excerpt") or ""
        return (
            "42088" in title_of(chunk)
            and page == 3
            and bool(re.search(r"water supply line|vacuum breaker", text, re.I))
        )

    def is_focus(chunk) -> bool:
        title = title_of(chunk).lower()
        if focus == "vacuum":
            return bool(re.search(r"3412|vacuum", title))
        if focus == "valve":
            return "42109" in title
        return "42088" in title

    trouble = [chunk for chunk in chunks or [] if is_trouble(chunk)][:2]
    focused = [chunk for chunk in chunks or [] if is_focus(chunk) and chunk not in trouble][:2]
    breaker = [chunk for chunk in chunks or [] if re.search(r"3412", title_of(chunk))][:1]
    valve = [chunk for chunk in chunks or [] if "42109" in title_of(chunk)][:1]
    ordered = []
    for group in (trouble, focused, breaker, valve):
        for chunk in group:
            if chunk not in ordered:
                ordered.append(chunk)
    lines = []
    for chunk in ordered[:6]:
        lines.append(
            f"Manual: {title_of(chunk) or 'manual'} Page: {chunk.get('page')}\n"
            f"{(chunk.get('excerpt') or '')[:700]}"
        )
    return lines


def _live_draft(message: str, history: list, chunks, rows=None) -> str:
    import gd_llm

    plan = _turn_plan(history, message, rows)
    excerpts = _ordered_excerpts(chunks, plan["focus"])
    picture_line = f"Picture: {plan['picture']}\n" if plan.get("picture") else ""
    system = (
        "You are the shop Guided Diagnostics coach for one Thetford 42070 flush-lever leak. "
        "Address the technician as you. "
        "Use only the manual excerpts. Write plain sentences. "
        "Do not use Where, Do this, Good, Bad, or Next labels. "
        "Do not print a How (...) block and do not print the words not stated. "
        "Do not print a step counter. Do not put a page number in the sentences. "
        "Put the page only on the Source line. "
        "A check reply says where to go, what to check, the words 'A good result is', "
        "the words 'A bad result is', and ends with the exact line 'Tell me what you see.' "
        "Name a tool only when THIS TURN gives one. If Tool is none, do not name a tool. "
        "If Good is none, do not write a good result. If Bad is none, do not write a bad result. "
        "A flush-and-watch check does not name a wrench, pliers, or a screwdriver. "
        "An observation-only check is complete with where, what to look for, "
        "a good result, a bad result, and 'Tell me what you see.' It does not need a tool.\n"
        "When the tech asks where something is, that reply answers where it is. "
        "It is not a new test. Do not repeat the previous good result or bad result. "
        "Do not name a tool. "
        "If Picture says a page image is attached, give one short pointer to where to look on that image, "
        "using only the manual's words, and start it with 'On this page'. "
        "Do not name a figure number. The image is attached for you. "
        "If Picture says the manual has no picture, say that plainly and briefly, "
        "restate the location in one short line, and offer a useful next move. "
        "You may ask for a photo of that spot. "
        "End with the exact sentence 'Then do that check and tell me what you see.' "
        "Do not invent a side, a shape, or a part the excerpt does not name. "
        "Never reference a figure unless one is attached to this reply.\n"
        "When THIS TURN is kit 42109, write a conversation. "
        "Say this is the water valve kit 42109 job. The valve is at the pedal. "
        "The first step is one sentence, said once: Turn the RV water off. "
        "Do not say that sentence again. "
        "The closet bolts that hold the toilet are at the floor, on the closet flange. "
        "Write this as its own sentence: Take the toilet off the closet bolts. "
        "Name the 1/2-inch wrench in the next sentence. "
        "Do not start the bolt sentence with Check. "
        "Do not name pliers on this step. "
        "Do not tell them to seat the cartridge on this turn. "
        "The good result and the bad result match that bolt step. "
        "The bad result names what is still wrong, such as the toilet still on the closet bolts "
        "or water still coming out. "
        "Offer to walk the rest one step at a time, and say the Bay PDF has the full list. "
        "Do not put the whole replacement into one Check clause.\n\n"
        "DIAGNOSIS ORDER from owner manual 42088 page 3. Follow this order. Do not skip ahead.\n"
        "1. Supply connection at the water valve. Cite 42088 page 3. The manual names no tool "
        "for this look, so use a flashlight.\n"
        "2. Vacuum breaker while flushing. Cite 34123/34122 page 1. "
        "Flush and watch. Do not name pliers. Pliers are for the later repair.\n"
        "3. Once the tech reports a weep at the pedal, do not ask them to check for that weep. "
        "Start the water valve kit 42109 job. The valve is at the pedal. Cite 42109 page 1. "
        "Say Turn the RV water off once. "
        "The closet bolts are at the floor, on the closet flange. "
        "Write this as its own sentence: Take the toilet off the closet bolts. "
        "Name the 1/2-inch wrench in the next sentence. "
        "Do not start the bolt sentence with Check. "
        "Do not name pliers. Do not seat the cartridge on this turn. "
        "The result matches that bolt step. "
        "Offer to walk the rest one step at a time. The Bay PDF has the full list.\n"
        "4. Closet flange only after those three.\n\n"
        "ESTABLISHED FACTS\n"
        f"{_user_facts(history, message)}\n\n"
        "THIS TURN\n"
        f"Cite: {plan['cite']}\n"
        f"Where: {plan['where']}\n"
        f"Tool: {plan['tool']}\n"
        f"Look: {plan['look']}\n"
        f"Good: {plan['good']}\n"
        f"Bad: {plan['bad']}\n"
        f"Safety: {plan['safety']}\n"
        f"{picture_line}"
        f"Advance: {plan['advance']}\n\n"
        "Write the reply from THIS TURN. Cite only the Cite line. "
        "Move on once an established finding is in. Do not ask that check again. "
        "If Safety is not empty, say that sentence once, before the work. "
        "Do not repeat a sentence that is already a step.\n\n"
        "MANUAL EXCERPTS:\n" + "\n\n".join(excerpts)
    )
    messages = [{"role": "system", "content": system}]
    for item in history or []:
        messages.append({
            "role": item.get("role") or "user",
            "content": item.get("content") or "",
        })
    messages.append({"role": "user", "content": message})
    return gd_llm.complete_chat(
        messages,
        temperature=0.2,
        max_tokens=gd_llm.GD_ASK_MAX_TOKENS,
        reasoning_effort=gd_llm.GD_ASK_REASONING_EFFORT,
        providers=["xai"],
        models={"xai": ["grok-4.6"]},
    )


def _profile_text(pairs: list[tuple[str, str]]) -> str:
    return "\n\n".join(
        f"USER: {user}\nASSISTANT:\n{assistant}" for user, assistant in pairs
    ) + "\n"


def _score_gap(rules, label: str) -> list[str]:
    """PASS and MANUAL do not fail the exit. FAIL, ERROR, and UNKNOWN do."""
    problems = []
    for rule in rules:
        status = (getattr(rule, "status", "") or "").upper()
        if status in ("PASS", "MANUAL"):
            continue
        detail = rule.detail or status or "not PASS"
        shown = status or "FAIL"
        if rule.scorecard:
            problems.append(f"{label} scorecard line {rule.number} {shown}: {detail}")
        else:
            problems.append(f"profile_check {rule.name} {shown}: {detail}")
    return problems


def _raw_manual_problems(raw_profile: str) -> list[str]:
    """The human read of the raw reply. profile_check does not cover these."""
    pairs = profile_check._pairs(raw_profile)
    problems = []
    if len(pairs) < len(TURNS):
        problems.append("RAW transcript does not have 4 turns")
        return problems
    for index, (user, assistant) in enumerate(pairs, 1):
        low = assistant.lower()
        if "the tech" in low:
            problems.append(f"RAW T{index} says the tech")
        if not re.search(r"\byou\b", low):
            problems.append(f"RAW T{index} does not address you")
        # A show-me answers where it is. It does not introduce a new test.
        show = bool(profile_check.ASK_RE.search(user or ""))
        if show:
            pass
        elif index == 3:
            if re.search(r"\b(wrench|pliers?|screwdriver)\b", low) and re.search(r"\b(flush|watch)\b", low):
                if not re.search(
                    r"\b(slide clamp|remove the inlet|pull the inlet|replace the vacuum|remove|install)\b",
                    low,
                ):
                    problems.append("RAW T3 names a tool on a flush-and-watch check")
        elif not re.search(r"\b(wrench|pliers?|flashlight)\b", low):
            problems.append(f"RAW T{index} names no tool")
    turns = [pair[1] for pair in pairs[: len(TURNS)]]
    t1, _t2, t3, t4 = turns
    if "42088" not in t1 or "42109" in t1:
        problems.append("RAW T1 does not cite 42088 ahead of the water valve kit")
    t3_low = t3.lower()
    if "34123" not in t3 or "vacuum breaker" not in t3_low or "42109" in t3:
        problems.append("RAW T3 skips the vacuum breaker")
    t4_low = t4.lower()
    if not re.search(r"\bdry\b", t1.lower()):
        problems.append("RAW T1 good line does not say dry")
    if "42109" not in t4 or not re.search(r"\bwrench\b", t4_low) or "water off" not in t4_low:
        problems.append("RAW T4 misses the water-valve step or the wrench")
    if re.search(r"\bpliers?\b", t4_low):
        problems.append("RAW T4 names pliers for the bolts")
    if len(re.findall(r"turn the rv water off", t4_low)) != 1:
        problems.append("RAW T4 does not say turn the RV water off once")
    if re.search(r"\bseat the new\b|\bseat the cartridge\b", t4_low):
        problems.append("RAW T4 seats the cartridge while the result is the bolts")
    if re.search(r"cartridge for a weep", t4_low):
        problems.append("RAW T4 repeats the weep instead of starting the 42109 repair")
    if not re.search(r"\bbolt", t4_low) or "bay pdf" not in t4_low:
        problems.append("RAW T4 does not walk the 42109 job")
    t2_low = turns[1].lower()
    if re.search(r"inlet side|small collar", t2_low):
        problems.append("RAW T2 invents a place the manual does not name")
    if "water supply line" not in t2_low or "back of the toilet" not in t2_low:
        problems.append("RAW T2 show-me does not use the manual's location words")
    if re.search(r"\bgood result\b|\bbad result\b", t2_low):
        problems.append("RAW T2 repeats a good or bad result")
    if "then do that check and tell me what you see" not in t2_low:
        problems.append("RAW T2 does not point back to the pending check")
    if not re.search(r"no picture|on this page|on that image|page image", t2_low):
        problems.append("RAW T2 does not point at the page image or say there is no picture")
    if "take the toilet off the closet bolts" not in t4_low:
        problems.append("RAW T4 does not say take the toilet off the closet bolts")
    if re.search(r"check the toilet coming off", t4_low):
        problems.append("RAW T4 checks the toilet coming off instead of taking it off")
    for sentence in re.split(r"[.\n]", t4):
        bit = sentence.lower()
        if re.search(r"\bbolt", bit) and re.search(r"water valve|\bpedal\b", bit):
            problems.append("RAW T4 puts the bolts at the water valve or the pedal")
            break
    if re.search(r"\bbolt", t4_low) and not re.search(r"closet flange|\bfloor\b", t4_low):
        problems.append("RAW T4 does not put the bolts at the floor or the closet flange")
    if not re.search(r"one step at a time|step by step", t4_low):
        problems.append("RAW T4 does not offer to go step by step")
    if profile_check._assistant_body(t4) == profile_check._assistant_body(t3):
        problems.append("RAW T4 restates T3")
    return problems


_REPORT_FAIL_RE = re.compile(r"^(?:FAIL\b|\d+\. FAIL\b|PF-\d+ FAIL\b)")


def _report_has_fail(text: str) -> bool:
    """A real FAIL line. 'Automatic FAIL: no.' is not one."""
    return any(_REPORT_FAIL_RE.match(line.strip()) for line in (text or "").splitlines())


def _render_pages(pdf: bytes, out: Path) -> None:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        for index, page in enumerate(doc, 1):
            page.get_pixmap(dpi=90).save(out / f"thetford-bay-p{index:02d}.png")
    finally:
        doc.close()


def _same_reply(left: str, right: str) -> bool:
    def norm(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    return norm(left) == norm(right)


def _play(rows, chunks, *, live: bool, library=None) -> tuple[str, str, list[str], str, int, list[str]]:
    from gd_library_coach import (
        avoid_duplicate_reply,
        ensure_thetford_flush_reply,
        last_guard_name,
        note_supply_page_art,
        reset_supply_page_art,
    )

    art_token = note_supply_page_art(_page_has_art(rows, "42088", 3))
    try:
        history = []
        lines = []
        pairs = []
        raw_pairs = []
        problems = []
        rewrites = 0
        guards = []
        for label, message in TURNS:
            if live:
                try:
                    draft = _live_draft(
                        message, history, library if library is not None else chunks, rows
                    )
                except Exception as exc:
                    problems.append(f"{label} model call failed: {exc}")
                    draft = ""
                guarded = avoid_duplicate_reply(
                    draft,
                    history,
                    message,
                    CATEGORY,
                    f"{BRAND} {MODEL}",
                    chunks=library if library is not None else chunks,
                )
                name = last_guard_name()
                if _same_reply(draft, guarded):
                    name = "none"
                elif not name:
                    name = "shop polish"
                reply = _append_figure_detail(guarded, message, rows, chunks)
                if name == "none" and not _same_reply(guarded, reply):
                    name = "figure detail"
                if not _same_reply(draft, reply):
                    rewrites += 1
                guards.append(f"{label} guard: {name}")
                raw_pairs.append((message, draft or ""))
            else:
                reply = ensure_thetford_flush_reply(
                    "", history, message, CATEGORY, f"{BRAND} {MODEL}"
                )
            asked_figure = mf.wants_manual_image(message) or mf.tech_asked_for_manual_figure(message)
            offers = []
            if asked_figure:
                offers = fb.offers_for_turn(rows, reply, message, CATEGORY, f"{BRAND} {MODEL}") or []
            captions = []
            for offer in offers:
                caption = (offer.get("caption") or offer.get("gd_caption") or "").strip()
                if not caption:
                    caption = fb.gd_figure_caption(offer)
                if caption and caption not in captions:
                    captions.append(caption)
            block = [f"{label} Tech: {message}", f"{label} Guided Diagnostics: {reply}"]
            if captions:
                block.append(f"{label} Figure: " + " | ".join(captions))
            lines.extend(block)
            lines.append("")
            spoken = reply + "\n" + "\n".join(captions)
            if _TEMPLATE.search(spoken):
                problems.append(f"{label} leaks template text")
            if label == "T2":
                low_reply = reply.lower()
                if "back of the toilet" not in low_reply or "water valve" not in low_reply:
                    problems.append("T2 does not say where the supply connection is")
                if re.search(r"inlet side|small collar", low_reply):
                    problems.append("T2 invents a place the manual does not name")
                if "water supply line" not in low_reply or "back of the toilet" not in low_reply:
                    problems.append("T2 show-me does not use the manual's location words")
                if re.search(r"\bgood result\b|\bbad result\b", low_reply):
                    problems.append("T2 repeats a good or bad result")
                if "then do that check and tell me what you see" not in low_reply:
                    problems.append("T2 does not point back to the pending check")
                if captions:
                    if "no picture" in low_reply:
                        problems.append("T2 says there is no picture when a page image is attached")
                    if "on this page" not in low_reply and "on that image" not in low_reply:
                        problems.append("T2 does not point at the attached page image")
                elif "no picture" not in low_reply:
                    problems.append("T2 does not say the manual has no picture")
                elif "photo" not in low_reply:
                    problems.append("T2 does not offer a photo when the manual has no picture")
                blob = " ".join(captions).lower()
                if "page 7" in blob or re.search(r"\bstep\s+1\b", blob):
                    problems.append("T2 figure caption is page 7 / Step 1")
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": reply})
            scored = reply
            if captions:
                figure_block = "\n".join(f"Figure: {caption}" for caption in captions)
                scored = reply.rstrip() + "\n" + figure_block
                # The attachment is part of the reply, not a guard rewrite.
                if live and raw_pairs:
                    user, draft_text = raw_pairs[-1]
                    raw_pairs[-1] = (user, (draft_text or "").rstrip() + "\n" + figure_block)
            pairs.append((message, scored))
        raw_text = _profile_text(raw_pairs) if raw_pairs else ""
        return "\n".join(lines).strip() + "\n", _profile_text(pairs), problems, raw_text, rewrites, guards
    finally:
        reset_supply_page_art(art_token)


def run(db: Path, cache: Path, out: Path, *, live: bool = False) -> int:
    if live and not (os.environ.get("XAI_API_KEY") or "").strip():
        print("XAI_API_KEY is not set. --live-llm needs it for grok-4.6.", file=sys.stderr)
        return 2
    if not db.is_file():
        print(f"database not found: {db}", file=sys.stderr)
        return 2
    if not cache.is_dir():
        print(f"cache directory not found: {cache}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    session = _connect(db)
    try:
        found = _thetford_chunks(session)
        if not found:
            print("no Thetford chunks in this database", file=sys.stderr)
            return 2
        chunks = _rank_chunks(found, 12)
        chunks = sorted(
            chunks,
            key=lambda chunk: (
                int(chunk.get("document_id") or 0),
                int(chunk.get("page") or 0),
            ),
        )
        doc_ids = {int(chunk["document_id"]) for chunk in chunks if chunk.get("document_id")}
        rows = _asset_rows(session, doc_ids)
        page_chunks = _page_chunks(session, doc_ids)
    finally:
        session.close()
    fb.attach_pngs(None, rows, read_local=False, download=None, cache_root=cache)
    fb.complete_figure_rows(rows, page_chunks, download=None, cache_root=cache)
    loaded = sum(1 for row in rows if row.get("png"))
    job = f"{CATEGORY} {BRAND} {MODEL} {CONCERN}"
    figures_by_doc: dict[int, list] = {}
    for row in rows:
        png = row.get("png") or b""
        if not png or (row.get("kind") or "figure") != "figure":
            continue
        doc_id = int(row.get("document_id") or 0)
        figures_by_doc.setdefault(doc_id, []).append(
            {
                "png": png,
                "label": row.get("label") or "",
                "caption": row.get("caption") or "",
                "bbox": row.get("bbox") or "",
                "page": row.get("page"),
                "title": row.get("title") or "",
            }
        )
    # The live ask is these ranked windows, cut at 4000 inside kit_excerpt.
    # The collapsed figure packet keeps only the figure's page, so page 2
    # of the vacuum breaker never reaches the sheet. Crops ride along.
    compile_chunks = []
    for chunk in chunks:
        copied = dict(chunk)
        copied["figures"] = list(figures_by_doc.get(int(chunk.get("document_id") or 0), []))
        compile_chunks.append(copied)
    proc = compile_bay_procedure(
        concern=CONCERN,
        brand=BRAND,
        model=MODEL,
        category=CATEGORY,
        chunks=compile_chunks,
    )
    packets = fb.figure_packets(rows, chunks, job)
    for packet in packets:
        packet["figures"] = [fig for fig in packet.get("figures") or [] if fig.get("png")]
    packets = [packet for packet in packets if packet.get("figures")]
    if packets:
        proc = apply_chunk_figures(proc, packets)
    pdf = render_bay_procedure_pdf(proc)
    transcript, profile, gd_problems, raw_profile, rewrites, guards = _play(
        rows, chunks, live=live, library=found
    )
    pdf_rules = profile_check.check_pdf_bytes(pdf, profile_check.library_from_db(db))
    gd_rules = profile_check.check_transcript(profile)
    problems = (
        _sheet_problems(proc, pdf)
        + gd_problems
        + _score_gap(pdf_rules, "PDF")
        + _score_gap(gd_rules, "GD")
    )
    _render_pages(pdf, out)
    (out / "thetford-bay.pdf").write_bytes(pdf)
    (out / "transcript.txt").write_text(transcript, encoding="utf-8")
    (out / "transcript-profile.txt").write_text(profile, encoding="utf-8")
    raw_rules = []
    if live:
        (out / "transcript-raw.txt").write_text(raw_profile, encoding="utf-8")
        raw_rules = profile_check.check_transcript(raw_profile)
    report = [
        f"chunks {len(chunks)} ranked of {len(found)}",
        f"documents {len(doc_ids)}",
        f"asset rows {len(rows)}",
        f"pngs from cache {loaded}",
        f"branches {len(proc.procedures or [])}",
        f"pdf bytes {len(pdf)}",
        "live-llm grok-4.6" if live else "no-model",
        "",
        profile_check.format_report(pdf_rules),
        "",
        profile_check.format_report(gd_rules),
    ]
    if live:
        problems.extend(_score_gap(raw_rules, "RAW"))
        problems.extend(_raw_manual_problems(raw_profile))
        if rewrites > 1:
            problems.append(f"guards rewrote {rewrites} of {len(TURNS)} turns")
        report.extend([
            "",
            f"guards rewrote {rewrites} of {len(TURNS)} turns",
            *guards,
            "RAW model reply, before the shop guards:",
            profile_check.format_report(raw_rules),
        ])
    if problems:
        report.append("FAIL")
        report.extend(f"- {item}" for item in problems)
    else:
        report.append("PASS")
    text_out = "\n".join(report) + "\n"
    (out / "report.txt").write_text(text_out, encoding="utf-8")
    print(text_out, end="")
    return 1 if problems or _report_has_fail(text_out) else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Thetford Bay PDF and GD T1-T4 from a library database.")
    parser.add_argument("--db", required=True, type=Path, help="Shop SQLite database (read-only)")
    parser.add_argument("--cache", required=True, type=Path, help="Directory of R2 object keys")
    parser.add_argument("--out", required=True, type=Path, help="Directory for the PDF, transcript, and report")
    parser.add_argument(
        "--live-llm",
        action="store_true",
        help="Run T1-T4 through grok-4.6 using XAI_API_KEY, then the shop guards",
    )
    args = parser.parse_args(argv)
    return run(args.db, args.cache, args.out, live=args.live_llm)


if __name__ == "__main__":
    raise SystemExit(main())
