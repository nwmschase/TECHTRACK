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
``report.txt``, and 90 dpi page PNGs under ``--out``. The report includes
profile_check for the PDF and for the transcript. Exit 0 when the sheet and
the transcript pass, including 10/10 on both scorecards. Exit 1 when a check
fails. Exit 2 when the database, the cache, or (with ``--live-llm``) the
xAI key cannot be used.
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
            (step.get("fields") or {}).get("TOOLS / METER SETTING") or ""
            for step in valve.get("steps") or []
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
    if "scouring" not in do_not:
        problems.append("Do Not list dropped the cleaner line")
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
    """Headless stand-in for the stored-figure offer that runs after the coach."""
    physical = bool(re.search(
        r"\b(check|tighten|replace|inspect|remove|install|measure|read the)\b",
        reply or "",
        re.I,
    ))
    asked = mf.wants_manual_image(user_msg) or mf.tech_asked_for_manual_figure(user_msg)
    if not physical and not asked:
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


def _live_draft(message: str, history: list, chunks) -> str:
    import gd_llm

    excerpts = []
    for chunk in (chunks or [])[:8]:
        excerpts.append(
            f"Manual: {chunk.get('title') or 'manual'} Page: {chunk.get('page')}\n"
            f"{(chunk.get('excerpt') or '')[:500]}"
        )
    system = (
        "You are the shop Guided Diagnostics coach. Use only the manual excerpts. "
        "Cite a manual as a Source line with its page. Write plain sentences. "
        "Do not use Where, Do this, Good, Bad, or Next labels. "
        "Do not print a How (...) block and do not print the words not stated. "
        "If the manual does not give a tool or a setting, leave it out. "
        "Say where the part is, what to look for, what good and bad look like, "
        "and ask what the tech sees.\n\n"
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
    cards = [rule for rule in rules if rule.scorecard]
    passed = sum(1 for rule in cards if rule.status == "PASS")
    problems = []
    if len(cards) == 10 and passed < 10:
        missed = [f"{rule.number} {rule.status}" for rule in cards if rule.status != "PASS"]
        problems.append(f"{label} scorecard {passed}/10 ({', '.join(missed)})")
    for rule in rules:
        if rule.status == "FAIL":
            problems.append(f"profile_check {rule.name} FAIL: {rule.detail}")
        elif rule.name.startswith("PF-") and rule.status != "PASS" and rule.name != "PF-32":
            problems.append(f"profile_check {rule.name} {rule.status}: {rule.detail}")
    return problems


def _render_pages(pdf: bytes, out: Path) -> None:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    try:
        for index, page in enumerate(doc, 1):
            page.get_pixmap(dpi=90).save(out / f"thetford-bay-p{index:02d}.png")
    finally:
        doc.close()


def _play(rows, chunks, *, live: bool) -> tuple[str, str, list[str]]:
    from gd_library_coach import avoid_duplicate_reply, ensure_thetford_flush_reply

    history = []
    lines = []
    pairs = []
    problems = []
    for label, message in TURNS:
        if live:
            try:
                draft = _live_draft(message, history, chunks)
            except Exception as exc:
                problems.append(f"{label} model call failed: {exc}")
                draft = ""
            reply = avoid_duplicate_reply(
                draft, history, message, CATEGORY, f"{BRAND} {MODEL}"
            )
            reply = _append_figure_detail(reply, message, rows, chunks)
        else:
            reply = ensure_thetford_flush_reply(
                "", history, message, CATEGORY, f"{BRAND} {MODEL}"
            )
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
            if "back of the toilet" not in reply.lower() or "water valve" not in reply.lower():
                problems.append("T2 does not say where the supply connection is")
            blob = " ".join(captions).lower()
            if "page 7" in blob or re.search(r"\bstep\s+1\b", blob):
                problems.append("T2 figure caption is page 7 / Step 1")
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        pairs.append((message, reply))
    return "\n".join(lines).strip() + "\n", _profile_text(pairs), problems


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
        chunks = _thetford_chunks(session)
        if not chunks:
            print("no Thetford chunks in this database", file=sys.stderr)
            return 2
        doc_ids = {int(chunk["document_id"]) for chunk in chunks if chunk.get("document_id")}
        rows = _asset_rows(session, doc_ids)
    finally:
        session.close()
    fb.attach_pngs(None, rows, read_local=False, download=None, cache_root=cache)
    loaded = sum(1 for row in rows if row.get("png"))
    proc = compile_bay_procedure(
        concern=CONCERN,
        brand=BRAND,
        model=MODEL,
        category=CATEGORY,
        chunks=chunks,
    )
    job = f"{CATEGORY} {BRAND} {MODEL} {CONCERN}"
    packets = fb.figure_packets(rows, chunks, job)
    for packet in packets:
        packet["figures"] = [fig for fig in packet.get("figures") or [] if fig.get("png")]
    packets = [packet for packet in packets if packet.get("figures")]
    if packets:
        proc = apply_chunk_figures(proc, packets)
    pdf = render_bay_procedure_pdf(proc)
    transcript, profile, gd_problems = _play(rows, chunks, live=live)
    pdf_rules = profile_check.check_pdf_bytes(pdf)
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
    report = [
        f"chunks {len(chunks)}",
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
    if problems:
        report.append("FAIL")
        report.extend(f"- {item}" for item in problems)
    else:
        report.append("PASS")
    text_out = "\n".join(report) + "\n"
    (out / "report.txt").write_text(text_out, encoding="utf-8")
    print(text_out, end="")
    return 1 if problems else 0


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
