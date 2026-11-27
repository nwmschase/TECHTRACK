"""Prompt for Guided Diagnostics (branch grok-search).

The single guidance text Grok gets is gd_primer.md: a plain description of what TechTrack is, who uses it, how the library is
organized and what the tools do. It holds no rules. The one other system block is STATE_FORMAT, the shape of the state block
the app reads back (response-format plumbing).

Message order each turn (stable text first, so the provider can cache it):
  1. system: the primer + the state format                (same every turn)
  2. system: the unit as typed, the pages Grok read earlier in this job (whole, with labels and notes), the web sources
             it used, the lookups it ran, the case state so far, the running summary
     (no manual is picked for Grok: it finds the documents and pages itself with the tools in gd_tools)
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
<state>{"facts": [{"item": "", "value": "", "quote": ""}], "fault_code": "", "pending_test": "", "part_working": "",
"next_part_to_fetch": "", "web_lookup": "", "order_part": "", "cause": "",
"repair": {"done": false, "verified": false, "what": "", "quote": ""},
"cited": [{"doc_id": "", "page": ""}], "summary": "", "closed": false, "story": ""}</state>
Every field is optional: a field that is left out keeps its stored value. `summary` and `cited` are stored fresh each turn.
`quote` fields hold the tech's exact words. `story` holds the technician story once the tech has called the repair verified; the app shows it in the shop notes box. `next_part_to_fetch` holds the words of the latest library search and `web_lookup` the words of the
latest internet search (a record for the job; the searches themselves run through the tools), `order_part` is a part the reply
tells the tech to order or replace this turn, and `cited` lists the document and page of each source the reply used (a web
source: its address as the doc_id)."""

SYSTEM = "\n\n".join([PRIMER, STATE_FORMAT])
STATE_REMINDER = "REPLY FORMAT: as always, the reply ends with the <state> block described in the instructions."


def reminder_item():
    """The REPLY FORMAT reminder as the last input item of a model round (v4.20.6, test7b: placed before the history and
    the tool results it was far behind what Grok read last, and both turns came back without the block)."""
    return {"role": "system", "content": STATE_REMINDER}


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


def _searches_block(searches):
    if not searches:
        return ""
    lines = ["LOOKUPS RUN EARLIER IN THIS JOB (tool and words; the pages read are above):"]
    for x in searches:
        args = x.get("args")
        lines.append(f"- {x.get('tool')}: {args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)}")
    return "\n".join(lines)


def _web_block(web_sources):
    if not web_sources:
        return ""
    return "WEB SOURCES USED EARLIER IN THIS JOB:\n" + "\n".join(
        f"- {w.get('url')}" + (f" ({w['title']})" if w.get("title") else "") for w in web_sources)


def context_block(*, category, model_text, pages=(), web_sources=(), searches=(), state=None, notes=()):
    lines = [f"UNIT (as the tech typed it): category={category or '-'}; model={model_text or '-'}"]
    for n in notes:
        lines.append(n)
    body = "\n".join(lines)
    blocks = [body, _pages_block("PAGES READ EARLIER IN THIS JOB", list(pages)), _web_block(list(web_sources)),
              _searches_block(list(searches))]
    st = {k: v for k, v in (state or {}).items() if k != "summary"}
    blocks.append("CASE STATE SO FAR (from the earlier state blocks):\n" + json.dumps(st, ensure_ascii=False, sort_keys=True))
    if (state or {}).get("summary"):
        blocks.append("RUNNING SUMMARY OF EARLIER TURNS:\n" + state["summary"])
    # The REPLY FORMAT reminder (STATE_REMINDER) is no longer here: since v4.20.6 it is the last item of every round's
    # input (reminder_item(), added by gd_turn.run_turn after the tool results).
    return "\n\n".join(b for b in blocks if b)


def recent_history(history):
    """The conversation so far, user and assistant messages with text."""
    return [m for m in (history or []) if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()]


def build_messages(*, user_msg, history, category, model_text, pages=(), web_sources=(), searches=(), state=None, notes=()):
    return ([{"role": "system", "content": SYSTEM},
             {"role": "system", "content": context_block(category=category, model_text=model_text, pages=pages,
                                                         web_sources=web_sources, searches=searches, state=state, notes=notes)}]
            + [{"role": m["role"], "content": m["content"]} for m in recent_history(history)]
            + [{"role": "user", "content": user_msg or ""}])
