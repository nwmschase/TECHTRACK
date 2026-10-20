"""One Guided Diagnostics turn (branch fresh-core). Plumbing only.

The code: asks the page-finder for pages, keeps them inside the page budget, builds the prompt, makes the call,
cuts off and stores the brain's state block, and returns the reply. It decides nothing about the repair:
no keyword triggers, no guards, no holds, no appended lines, no rewrites of the brain's reply.

Turn flow
  1. Load the case from the store (or start one).
  2. Pages: the first turn, a changed unit, or a new fault code in the state -> page-finder pick_manual.
     A part named in state.next_part_to_fetch -> fetch_part (cached per part). state.web_lookup -> web_fn if wired.
  3. Budget the pages (newest part pages, entry pages, web pages, supporting pages, older part pages).
  4. Build messages (gd_prompt) and make ONE call.
  5. Cut off the state block and store it (gd_state). If that block asks for a part or web lookup whose pages are not in
     hand yet, fetch them and redo the call once (MAX_FETCH_ROUNDS), so the step can cite the page.
  6. Return the brain's prose unchanged.

Approved rule checks (CHASE-RULE-DECISIONS-2026-10-20; state-based, never a rewrite of the reply):
  R2 web lookup: only pages from maker (OEM) domains are given to the brain (oem_domains.allowed).
  R3 no part order while a test is pending: a state block with order_part while pending_test is open gets ONE re-call
     with a plain note; if it still orders, the order is not recorded and the problem is logged.
  R4 brand lock: the page-finder only hands over pages of the picked maker's manuals (gd_pages.LibraryPageFinder).
  R5 citation check: a cited doc+page the brain was never shown is not recorded as a source; the problem is logged
     and the brain is told on its next turn.
"""
from __future__ import annotations

import json
import time

import gd_prompt
import gd_state
import oem_domains
from gd_pages import Page, Picked, apply_budget, PAGE_BUDGET_PAGES, PAGE_BUDGET_CHARS

REPLY_MAX_TOKENS = 2000           # prose + the state block
FIRST_EFFORT, LATER_EFFORT = "medium", "low"
MAX_FETCH_ROUNDS = 1              # extra calls per turn to bring in pages the brain just asked for
STORE_KEY = "gd_case"


def _picked_to_dict(p: Picked) -> dict:
    return {"manuals": p.manuals, "pages": [x.to_dict() for x in p.pages], "n_entry": len(p.entry),
            "why": p.why, "code": p.code, "raw": p.raw}


def _picked_from_dict(d: dict) -> Picked:
    pages = [Page.from_dict(x) for x in d.get("pages") or []]
    return Picked(manuals=d.get("manuals") or [], entry=pages[:d.get("n_entry", 0)], pages=pages,
                  why=d.get("why") or [], code=d.get("code") or "", raw=d.get("raw") or {})


def new_case(category, model_text, complaint):
    return {"unit": {"category": category or "", "model_text": model_text or ""}, "complaint": complaint or "",
            "picked": None, "picked_code": None, "toc": [], "part_pages": {}, "part_order": [], "web_pages": {},
            "state": gd_state.new_state(), "turns": 0, "problems": [], "shown": [], "notes_next": []}


def _ensure_pages(case, finder, web_fn, notes):
    """Bring the case's pages up to date with the unit and the stored state. Returns the Picked."""
    st = case["state"]
    code = st.get("fault_code") or None
    if case["picked"] is None or case["picked_code"] != code:
        picked = finder.pick_manual(case["unit"]["category"], case["unit"]["model_text"], case["complaint"], code)
        case["picked"], case["picked_code"] = _picked_to_dict(picked), code
        case["toc"] = [p.to_dict() for p in finder.toc_pages(picked)] if picked.found else []
    picked = _picked_from_dict(case["picked"])
    part = (st.get("next_part_to_fetch") or "").strip()
    if part:
        _fetch_part(case, finder, picked, part)
    q = (st.get("web_lookup") or "").strip()
    if q:
        _web(case, web_fn, q, notes)
    return picked


def _fetch_part(case, finder, picked, part) -> bool:
    """Fetch a part's pages once per part name. Returns True when new pages arrived."""
    if part in case["part_pages"]:
        if part in case["part_order"]:
            case["part_order"].remove(part)
        case["part_order"].append(part)
        return False
    got = [p.to_dict() for p in finder.fetch_part(part, picked)]
    case["part_pages"][part] = got
    case["part_order"].append(part)
    return bool(got)


def _web(case, web_fn, query, notes) -> bool:
    if query in case["web_pages"]:
        return False
    if web_fn is None:
        notes.append(f"WEB LOOKUP '{query}': not available in this build. Work from the pages here; where they do not cover a "
                     "step, use labeled [General trade knowledge] and say what the library is missing.")
        case["web_pages"][query] = []
        return False
    brands = [m.get("brand") or "" for m in ((case.get("picked") or {}).get("manuals") or [])]
    raw = list(web_fn(query) or [])
    got = [p.to_dict() for p in raw if oem_domains.allowed(getattr(p, "url", ""), brands)]   # R2
    if len(got) < len(raw):
        notes.append(f"WEB LOOKUP '{query}': {len(raw) - len(got)} result(s) from non-maker sites were left out.")
    case["web_pages"][query] = got
    return bool(got)


def _ordered_pages(case, picked):
    order = list(reversed(case["part_order"]))
    newest = [Page.from_dict(d) for d in case["part_pages"].get(order[0], [])] if order else []
    older = [Page.from_dict(d) for part in order[1:] for d in case["part_pages"].get(part, [])]
    web = [Page.from_dict(d) for q in case["web_pages"] for d in case["web_pages"][q]]
    entry = [p for p in picked.pages if p.kind == "entry"]
    support = [p for p in picked.pages if p.kind != "entry"]
    return newest + entry + web + support + older


def _remember_shown(case, pages):
    seen = {tuple(x) for x in case["shown"]}
    for p in list(pages) + [Page.from_dict(d) for d in case.get("toc") or []]:
        for k in ((p.doc_id, str(p.page)), (p.doc_id, str(p.sheet))):
            if k not in seen:
                seen.add(k); case["shown"].append(list(k))


def _check_citations(case, cited):
    """R5: split cited [{doc_id, page}] into (shown, never shown). Page matches the printed page or the PDF sheet."""
    seen = {tuple(x) for x in case["shown"]}
    ok, bad = [], []
    for c in cited:
        key = (str(c.get("doc_id") or ""), str(c.get("page") or "").strip().lstrip("p.").strip())
        (ok if key in seen else bad).append(c)
    return ok, bad


def _order_while_pending(state, update):
    """R3: the pending test (after this update) when the update also orders a part, else ''."""
    order = (update.get("order_part") or "").strip()
    pending = (update["pending_test"] if "pending_test" in update else (state or {}).get("pending_test") or "").strip()
    return pending if order and pending else ""


def run_turn(user_msg, category, model_text, history, *, finder, chat_fn, store, usage_fn=None, web_fn=None,
             log_path="", max_pages=PAGE_BUDGET_PAGES, max_chars=PAGE_BUDGET_CHARS):
    """chat_fn(messages, max_tokens, reasoning_effort) -> str. Returns
    {reply, mode, state, pages_used, not_shown, usage, seconds, context_chars, problems, calls}."""
    t0 = time.time()
    case = store.get(STORE_KEY)
    if case is None:
        case = new_case(category, model_text, user_msg)
    elif (case["unit"]["category"], case["unit"]["model_text"]) != (category or "", model_text or ""):
        # The tech changed the unit fields: new pages for the new unit; what the tech already reported stays.
        case["unit"] = {"category": category or "", "model_text": model_text or ""}
        case["picked"], case["part_pages"], case["part_order"], case["toc"] = None, {}, [], []
    case.setdefault("shown", []); case.setdefault("notes_next", [])
    notes = list(case["notes_next"]); case["notes_next"] = []
    picked = _ensure_pages(case, finder, web_fn, notes)
    effort = FIRST_EFFORT if case["turns"] == 0 else LATER_EFFORT
    calls, usage, problems = 0, {}, []
    while True:
        pages, not_shown = apply_budget(_ordered_pages(case, picked), max_pages, max_chars)
        msgs = gd_prompt.build_messages(user_msg=user_msg, history=history, category=case["unit"]["category"],
                                        model_text=case["unit"]["model_text"], picked=picked,
                                        toc=[Page.from_dict(d) for d in case["toc"]], pages=pages, not_shown=not_shown,
                                        state=case["state"], notes=notes)
        reply = chat_fn(msgs, REPLY_MAX_TOKENS, effort)
        calls += 1
        if usage_fn:
            u = usage_fn() or {}
            usage = {k: usage.get(k, 0) + v if isinstance(v, (int, float)) and not isinstance(v, bool) else v for k, v in u.items()}
        prose, update, probs = gd_state.parse(reply)
        problems += probs
        _remember_shown(case, pages)
        r3 = _order_while_pending(case["state"], update)
        if calls > MAX_FETCH_ROUNDS:
            if r3:
                problems.append(f"R3: order of {update['order_part']!r} while test {r3!r} is pending; order not recorded")
                update = dict(update, order_part="")
            break
        if r3:
            notes.append(f"CHECK: your last draft orders/replaces '{update['order_part']}' while the test '{r3}' is still "
                         "pending. Finish that test or drop it (say why) before any part order. Redo your reply.")
            continue
        part, query = (update.get("next_part_to_fetch") or "").strip(), (update.get("web_lookup") or "").strip()
        new_pages = (bool(part) and _fetch_part(case, finder, picked, part)) | (bool(query) and _web(case, web_fn, query, notes))
        if not new_pages:
            break
    update = dict(update)
    if update:
        update.setdefault("order_part", "")   # per turn: an order is never carried into a later turn
    if "cited" in update:                  # R5
        ok, bad = _check_citations(case, update["cited"])
        update["cited"] = ok
        if bad:
            problems.append("R5: cited page(s) not shown: " + ", ".join(f"{c.get('doc_id')} p.{c.get('page')}" for c in bad))
            case["notes_next"].append("CHECK: your last reply cited " + ", ".join(f"{c.get('doc_id')} p.{c.get('page')}" for c in bad)
                                      + ", which you were not shown. Cite only pages listed under SELECTED PAGES or TABLE OF CONTENTS.")
    case["state"] = gd_state.merge(case["state"], update)
    case["turns"] += 1
    case["problems"] = (case["problems"] + problems)[-50:]
    store[STORE_KEY] = case
    mode = "closed" if case["state"].get("closed") else ("walk" if picked.found else "no_manual")
    ctx = sum(len(m["content"]) for m in msgs)
    rec = {"turn": case["turns"], "mode": mode, "calls": calls, "effort": effort, "context_chars": ctx,
           "pages_used": [p.label() for p in pages], "not_shown": [p.label() for p in not_shown],
           "manuals": [m.get("doc_id") for m in picked.manuals], "problems": problems, "usage": usage,
           "seconds": round(time.time() - t0, 2)}
    if log_path:
        with open(log_path, "a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
    return {"reply": prose, "mode": mode, "state": case["state"], "pages_used": rec["pages_used"],
            "not_shown": rec["not_shown"], "usage": usage, "seconds": rec["seconds"], "context_chars": ctx,
            "problems": problems, "calls": calls, "cited": case["state"].get("cited") or []}
