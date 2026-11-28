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
"cited": [{"doc_id": "", "page": ""}], "summary": "", "closed": false}</state>
Every field is optional, and so is each part of `repair`: a field (or part) that is left out keeps its stored value, except `cited`, which holds this turn's citations (left out = nothing cited this turn).
`quote` fields hold the tech's exact words. `next_part_to_fetch` holds the words of the latest library search and `web_lookup` the words of the
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


def _app_failure_line(m) -> bool:
    """v4.20.11: an assistant message that is the app's own "did not answer" line (gd_errors), not something Grok said."""
    import gd_errors
    return m.get("role") == "assistant" and gd_errors.is_error_line((m.get("content") or "").strip())


def recent_history(history):
    """The conversation so far, user and assistant messages with text. The app's failed-turn lines stay in the tech's chat
    but are not sent to Grok as if Grok had said them (v4.20.11)."""
    return [m for m in (history or []) if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()
            and not _app_failure_line(m)]


def pages_item(pages):
    """The pages already read in this job as one system message, or None when there are none."""
    txt = _pages_block("PAGES READ EARLIER IN THIS JOB", list(pages))
    return {"role": "system", "content": txt} if txt else None


def build_input(*, user_msg, history, category, model_text, pages=(), web_sources=(), searches=(), state=None, notes=()):
    """The input list of one turn, ordered for xAI's prompt cache (v4.20.10, Chase t1732u; docs.x.ai prompt caching: the
    cache matches the start of the request, so anything that changes turn to turn breaks it from that point on).
    The same text as before, only reordered (the old single context block is split in two):
      1. the primer (constant),
      2. the pages read earlier in this job (the biggest part; only ever grows at the end, in first-read order),
      3. the conversation so far (append-only: each turn adds two messages at the end),
      4. the tech's new message,
      5. the rest of the job context LAST: unit line, notes, web sources, lookups, case state, summary (all of it can
         change every turn).
    Within a turn gd_turn only appends to this list (tool calls, their results, page images) and puts the REPLY FORMAT
    reminder after everything, so each round's request starts with the whole previous round's request. Across turns the
    request starts with the previous turn's primer + pages + history up to the old user message, except where a turn read
    a new page (the pages block then grows and the history after it is sent fresh once). Measured on the 11/27 jobs
    (scripts/cache_share_estimate.py): putting the pages after the history instead would LOSE cache, since the pages are
    most of the tokens, so they stay in front."""
    head = pages_item(pages)
    return ([{"role": "system", "content": SYSTEM}]
            + ([head] if head else [])
            + [{"role": m["role"], "content": m["content"]} for m in recent_history(history)]
            + [{"role": "user", "content": user_msg or ""},
               {"role": "system", "content": context_block(category=category, model_text=model_text, pages=(),
                                                           web_sources=web_sources, searches=searches, state=state, notes=notes)}])
