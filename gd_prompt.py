"""Prompt for Guided Diagnostics (branch fresh-core).

The single guidance text Grok gets is gd_primer.md: a plain description of what TechTrack is, who uses it, how the library is
organized and what the tools do. It holds no rules. The one other system block is STATE_FORMAT, the shape of the state block
the app reads back (response-format plumbing).

Message order each turn (stable text first, so the provider can cache it):
  1. system: the primer + the state format                (same every turn)
  2. system: the unit as typed, the picked manual(s), table of contents, the pages found by search and web lookup,
             the case state so far, the running summary
  3. the conversation so far
  4. the tech's new message
"""
from __future__ import annotations

import json
import os

PRIMER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gd_primer.md")
with open(PRIMER_PATH, encoding="utf-8") as _fh:
    PRIMER = _fh.read().strip()

STATE_FORMAT = """**State block (response format).** A reply ends with one state block that the app strips off and stores; the tech does not see it.
<state>{"complaint_verified": "yes|no|not_asked", "complaint_quote": "", "complaint_actual": "",
"facts": [{"item": "", "value": "", "quote": ""}], "fault_code": "", "pending_test": "", "part_working": "",
"next_part_to_fetch": "", "web_lookup": "", "order_part": "", "cause": "",
"repair": {"done": false, "verified": false, "what": "", "quote": ""},
"cited": [{"doc_id": "", "page": ""}], "summary": "", "closed": false}</state>
Every field is optional: a field that is left out keeps its stored value. `summary` and `cited` are stored fresh each turn.
`quote` fields hold the tech's exact words. `next_part_to_fetch` is the text for a library search, `web_lookup` is the text for a
web lookup, `order_part` is a part the reply tells the tech to order or replace this turn, and `cited` lists the document and
page of each source the reply used."""

SYSTEM = "\n\n".join([PRIMER, STATE_FORMAT])


def _doc_line(p) -> str:
    bits = []
    if getattr(p, "url", ""):
        bits.append(f"source {p.url} (host {p.host})")
    if getattr(p, "doc_number", ""):
        bits.append(f"doc no. {p.doc_number}")
    if getattr(p, "revision", ""):
        bits.append(f"revision {p.revision}")
    return ("\nDOC: " + "; ".join(bits)) if bits else ""


def _pages_block(title, pages):
    if not pages:
        return ""
    parts = [f"=== {title} ==="]
    for p in pages:
        note = _doc_line(p)
        if getattr(p, "note", ""):
            note += f"\nPAGE NOTE (reviewed): {p.note}"
        if getattr(p, "topics", ""):
            note += f"\nPAGE TOPICS: {p.topics}"
        parts.append(f"--- [{p.label()}] ({p.kind}{'; ' + p.reason if p.reason else ''}) ---{note}\n{p.text.strip()}")
    return "\n".join(parts)


def context_block(*, category, model_text, picked, toc, pages, state, notes=()):
    lines = [f"UNIT (as the tech typed it): category={category or '-'}; model={model_text or '-'}"]
    if picked is not None and picked.found:
        lines.append("MANUALS PICKED BY THE PAGE FINDER: " + "; ".join(
            f"{m['title']} ({m['doc_id']})" + (f" [note: {m['note']}]" if m.get("note") else "") for m in picked.manuals))
    else:
        lines.append("MANUALS PICKED BY THE PAGE FINDER: none")
    for n in notes:
        lines.append(n)
    body = "\n".join(lines)
    blocks = [body, _pages_block("TABLE OF CONTENTS", toc), _pages_block("SELECTED PAGES", pages)]
    st = {k: v for k, v in (state or {}).items() if k != "summary"}
    blocks.append("CASE STATE SO FAR (from the earlier state blocks):\n" + json.dumps(st, ensure_ascii=False, sort_keys=True))
    if (state or {}).get("summary"):
        blocks.append("RUNNING SUMMARY OF EARLIER TURNS:\n" + state["summary"])
    return "\n\n".join(b for b in blocks if b)


def recent_history(history):
    """The conversation so far, user and assistant messages with text."""
    return [m for m in (history or []) if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()]


def build_messages(*, user_msg, history, category, model_text, picked, toc, pages, state, notes=()):
    return ([{"role": "system", "content": SYSTEM},
             {"role": "system", "content": context_block(category=category, model_text=model_text, picked=picked, toc=toc,
                                                         pages=pages, state=state, notes=notes)}]
            + [{"role": m["role"], "content": m["content"]} for m in recent_history(history)]
            + [{"role": "user", "content": user_msg or ""}])
