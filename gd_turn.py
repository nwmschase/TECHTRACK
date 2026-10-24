"""One Guided Diagnostics turn (branch grok-search). Plumbing only.

Grok does the looking (Chase 2026-10-22 / 2026-10-24): it searches the library itself with the library tools (gd_tools:
find_documents, table_of_contents, search_pages, read_pages, open_web_document) and the internet with xAI's built-in
web search inside its own call. Grok decides which manual and which pages fit the unit and the complaint. The app picks
nothing, ranks nothing for Grok, and adds no rules: it runs the tool calls Grok makes, hands back what they return, and
stores the state block. No keyword triggers, no guards, no rewrites of the reply, no limits on pages, characters, history
or tokens.

Turn flow
  1. Load the case from the store (or start one). A changed unit clears the pages read for the old unit.
  2. Build messages (gd_prompt): the primer, the unit as typed, the pages Grok read earlier in this job, the web sources
     it used, the searches it ran, the case state, the conversation and the tech's message.
  3. Call Grok with the tools. When the reply holds function calls, run each one here (free, local library) and call
     again with the results; web searches already ran on xAI's side inside the call. Repeat until a reply comes back
     with no function call.
  4. Cut off the state block and store it (gd_state). Pages Grok read are kept in the case for later turns, and the
     pages it cites are matched to the pages it read (title, sheet) for the app's source lines and figures.
  5. Return Grok's prose unchanged.

SAFETY_CEILING_CALLS (Chase 2026-10-24) is an app-side backstop on model calls per turn, tool rounds included. It is not in
the prompt. The last allowed call is made with tool_choice "none", so the turn ends with a reply, and the stop is logged.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from urllib.parse import urlparse

import gd_prompt
import gd_state
import gd_tools
from gd_pages import Page

STORE_KEY = "gd_case"

# Backstop on model calls in one turn (Chase 2026-10-24, "lets try it"). A normal job never reaches it; it only keeps a
# turn that asks for a new, different search every round from running up cost. Not part of the prompt.
SAFETY_CEILING_CALLS = 6
# Pages-per-turn backstop (Chase 2026-10-24 concern: Grok reading a whole manual and running up cost). App-side, logged,
# never shown to Grok, same pattern as SAFETY_CEILING_CALLS. None = off: Chase has not approved a number yet.
# When set, read_pages / open_web_document hand back at most this many pages in one turn; the rest are left out and logged.
MAX_PAGES_READ_PER_TURN = None
# Turn log (Chase 2026-10-24, "log triggers galore"): one JSON line per turn, app-side, never shown to Grok. run_turn writes
# to log_path; log_path=None (the default) means GD_TURN_LOG from the environment, else this file in the temp dir.
DEFAULT_LOG_PATH = os.environ.get("GD_TURN_LOG") or os.path.join(tempfile.gettempdir(), "techtrack-gd-turns.jsonl")
CASE_LOG_KEEP = 30            # turn records kept in the case (store) for the app's notes / cost review

# Trigger names (each logged as {"trigger": NAME, ...} in the turn record's "triggers" list, as they happen).
T_SAFETY_CEILING = "SAFETY_CEILING_HIT"            # the last allowed call was made with tools off / Grok still asked for tools
T_PAGE_BACKSTOP = "PAGE_BACKSTOP_HIT"              # MAX_PAGES_READ_PER_TURN left pages out (only when it is set)
T_OTHER_BRAND = "OTHER_BRAND_PAGE_READ"            # Grok opened a page of a doc whose maker is not the maker the tech typed
T_WEB_BEFORE_LIBRARY = "WEB_BEFORE_LIBRARY_SEARCH"  # a web search / web document this turn before any library tool this turn
T_REPEAT = "REPEATED_SEARCH"                       # the same tool with the same arguments ran earlier in this job
T_TOOL_ERROR = "TOOL_ERROR"                        # a library tool returned an error
T_TOOL_EMPTY = "TOOL_EMPTY_RESULT"                 # a library tool returned nothing (no documents, hits or pages)
T_WEB_ERROR = "WEB_SEARCH_ERROR"                   # a server-side web search item came back failed
T_FORUM = "FORUM_SOURCE_USED"                      # a web source on a forum host
T_STATE_MISSING = "STATE_BLOCK_MISSING"
T_STATE_BROKEN = "STATE_BLOCK_BROKEN"
T_STORY = "STORY_WRITTEN"                          # the state block carried a technician story this turn
TRIGGERS = (T_SAFETY_CEILING, T_PAGE_BACKSTOP, T_OTHER_BRAND, T_WEB_BEFORE_LIBRARY, T_REPEAT, T_TOOL_ERROR, T_TOOL_EMPTY,
            T_WEB_ERROR, T_FORUM, T_STATE_MISSING, T_STATE_BROKEN, T_STORY)
FORUM_HOST_WORDS = ("forum", "irv2", "reddit", "rvforums", "rv.net", "community", "facebook", "groups.", "quora", "boards.")
# xAI usage reports cost_in_usd_ticks (billed cost incl. server-side tools); 1 USD = 1e10 ticks (docs.x.ai/developers/cost-tracking)
USD_PER_TICK = 1e-10

CEILING_REPLY = "I ran out of lookups for this message. Send it again and I will pick up from what I found."


def new_case(category, model_text, complaint):
    return {"unit": {"category": category or "", "model_text": model_text or ""}, "complaint": complaint or "",
            "read": {}, "read_order": [], "web_sources": [], "searches": [],
            "state": gd_state.new_state(), "turns": 0, "problems": [], "notes_next": []}


def _key(p: Page) -> str:
    return f"{p.doc_id}#{p.sheet}"


def _remember_pages(case, pages):
    for p in pages:
        k = _key(p)
        case["read"][k] = p.to_dict()
        if k in case["read_order"]:
            case["read_order"].remove(k)
        case["read_order"].append(k)


def _read_pages(case):
    return [Page.from_dict(case["read"][k]) for k in case["read_order"] if k in case["read"]]


def _legacy_respond(chat_fn):
    """A plain chat_fn(messages, max_tokens, effort) -> str (offline fakes, older callers) as a respond_fn. Its reply is
    final: it has no tool calls."""
    def respond(items, tools, tool_choice=None):
        return chat_fn(items, None, None)
    return respond


def _as_result(got) -> dict:
    if isinstance(got, str):
        return {"text": got, "calls": [], "output": [], "web_sources": [], "server_tools": [], "usage": {}}
    got = dict(got or {})
    for k, v in (("text", ""), ("calls", []), ("output", []), ("web_sources", []), ("server_tools", []), ("usage", {})):
        got.setdefault(k, v)
    return got


def _add_usage(total, u):
    for k, v in (u or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            total[k] = total.get(k, 0) + v
        else:
            total[k] = v
    return total


def _cited_with_pages(cited, case):
    """Each cited {doc_id, page} with the title and sheet of the page Grok read, when it read it."""
    by_doc_page = {}
    for p in _read_pages(case):
        by_doc_page.setdefault((str(p.doc_id), str(p.page)), p)
        by_doc_page.setdefault((str(p.doc_id), f"sheet {p.sheet}"), p)
    out = []
    for c in cited or []:
        c = dict(c)
        p = by_doc_page.get((str(c.get("doc_id")), str(c.get("page") or "")))
        if p is not None:
            c.setdefault("title", p.title)
            c.setdefault("sheet", p.sheet)
            c["read"] = True
            if p.url:
                c.setdefault("url", p.url)
        out.append(c)
    return out


def _is_forum(url):
    u = (url or "").lower()
    host = (urlparse(u).hostname or "")
    return any(w in host for w in FORUM_HOST_WORDS) or "/forum" in u or "/threads/" in u


def _empty(name, out):
    try:
        d = json.loads(out)
    except ValueError:
        return False
    if not isinstance(d, dict) or d.get("error"):
        return False
    for k in ("documents", "hits", "pages", "outline"):
        if k in d:
            return not d[k]
    return False


def _web_query(action):
    if isinstance(action, dict):
        return action.get("query") or action.get("url") or action.get("pattern") or ""
    return str(action or "")


def run_turn(user_msg, category, model_text, history, *, store, finder=None, library=None, chat_fn=None, respond_fn=None,
             usage_fn=None, web_fetch=None, log_path=None, tools=None, **_old):
    """One turn. library: a gd_tools.LibraryTools (default: built over finder's library). respond_fn(items, tools,
    tool_choice) -> gd_llm.respond()-shaped dict or a plain reply string; chat_fn(messages, max_tokens, effort) -> str is the
    older text-only form (no tool calls). log_path: JSON-lines turn log ("" = off, None = DEFAULT_LOG_PATH).
    Returns {reply, mode, state, pages_used, not_shown, usage, seconds, context_chars, problems, calls, cited, tool_calls,
    web_sources, pages_read, triggers, log}."""
    t0 = time.time()
    if respond_fn is None:
        if chat_fn is None:
            raise TypeError("run_turn needs respond_fn or chat_fn")
        respond_fn = _legacy_respond(chat_fn)
    if library is None:
        library = gd_tools.LibraryTools.for_finder(finder, web_fetch=web_fetch) if finder is not None else None
    tool_specs = list(gd_tools.TOOL_SPECS if tools is None else tools)
    case = store.get(STORE_KEY)
    if case is None or "read" not in case:
        case = new_case(category, model_text, user_msg) if case is None else {**new_case(category, model_text, case.get("complaint")),
                                                                                "state": case.get("state") or gd_state.new_state()}
    elif (case["unit"]["category"], case["unit"]["model_text"]) != (category or "", model_text or ""):
        # The tech changed the unit fields: the pages read for the old unit go; what the tech already reported stays.
        case["unit"] = {"category": category or "", "model_text": model_text or ""}
        case["read"], case["read_order"], case["web_sources"], case["searches"] = {}, [], [], []
    case.setdefault("notes_next", []); case.setdefault("log", [])
    notes = list(case["notes_next"]); case["notes_next"] = []
    msgs = gd_prompt.build_messages(user_msg=user_msg, history=history, category=case["unit"]["category"],
                                    model_text=case["unit"]["model_text"], pages=_read_pages(case),
                                    web_sources=case["web_sources"], searches=case["searches"], state=case["state"], notes=notes)
    items = list(msgs)
    unit_brands = library.unit_brands(case["unit"]["model_text"]) if library is not None and hasattr(library, "unit_brands") else set()
    seen_searches = {json.dumps([x.get("tool"), x.get("args")], sort_keys=True, default=str) for x in case["searches"]}
    calls, usage, problems, tool_log, turn_pages, triggers = 0, {}, [], [], [], []
    rounds, web_log, opened = [], [], []
    library_used_this_turn = False
    text = ""

    def trig(name, **info):
        triggers.append({"trigger": name, "at_call": calls, **info})

    while True:
        last = calls + 1 >= SAFETY_CEILING_CALLS
        tc = time.time()
        got = _as_result(respond_fn(items, tool_specs, "none" if last else None))
        calls += 1
        if usage_fn and not got["usage"]:
            got["usage"] = usage_fn() or {}
        usage = _add_usage(usage, got["usage"])
        rounds.append({"call": calls, "seconds": round(time.time() - tc, 3), "tools_off": last,
                       "function_calls": [c["name"] for c in got["calls"]], "server_tools": len(got["server_tools"]),
                       "usage": got["usage"], "text_chars": len(got["text"] or "")})
        text = got["text"] or text
        # web: what Grok searched inside its call (server side) and the sources that came back
        for s in got["server_tools"]:
            q = _web_query(s.get("action"))
            ent = {"call": calls, "type": s.get("type"), "query": q, "action": s.get("action") or {}}
            act = s.get("action") if isinstance(s.get("action"), dict) else {}
            status = s.get("status") or act.get("status") or ""
            if str(status).lower() in ("failed", "error", "incomplete"):
                ent["error"] = status
                trig(T_WEB_ERROR, query=q, status=status)
            web_log.append(ent)
            tool_log.append({"tool": s.get("type"), "args": s.get("action") or {}, "side": "xai", "call": calls})
            if not library_used_this_turn:
                trig(T_WEB_BEFORE_LIBRARY, tool=s.get("type"), query=q)
        new_urls = []
        for w in got["web_sources"]:
            if w.get("url") and w["url"] not in {x["url"] for x in case["web_sources"]}:
                case["web_sources"].append({"url": w["url"], "title": w.get("title") or ""})
            if w.get("url"):
                new_urls.append(w["url"])
                if _is_forum(w["url"]):
                    trig(T_FORUM, url=w["url"])
        if new_urls:
            web_log.append({"call": calls, "type": "sources", "sources": new_urls})
        if not got["calls"]:
            break
        items += got["output"] or [{"type": "function_call", "call_id": c["call_id"], "name": c["name"],
                                    "arguments": c["arguments"]} for c in got["calls"]]
        for c in got["calls"]:
            room = None if MAX_PAGES_READ_PER_TURN is None else max(0, MAX_PAGES_READ_PER_TURN - len(turn_pages))
            sig = json.dumps([c["name"], c["arguments"]], sort_keys=True, default=str)
            if sig in seen_searches:
                trig(T_REPEAT, tool=c["name"], args=c["arguments"])
            seen_searches.add(sig)
            if c["name"] == "open_web_document":
                if not library_used_this_turn:
                    trig(T_WEB_BEFORE_LIBRARY, tool=c["name"], args=c["arguments"])
            else:
                library_used_this_turn = True
            dropped, tt = [], time.time()
            if library is None:
                out, pages, err = json.dumps({"error": "the library is not loaded"}), [], "no library"
            else:
                out, pages, err = library.call(c["name"], c["arguments"], max_pages=room)
                dropped = list(getattr(library, "last_dropped", []) or [])
            secs = round(time.time() - tt, 3)
            if dropped:
                # App-side backstop only: never shown to Grok; logged for the cost review.
                problems.append(f"pages backstop: {len(dropped)} page(s) left out after {MAX_PAGES_READ_PER_TURN} this turn: "
                                + ", ".join(dropped[:20]))
                trig(T_PAGE_BACKSTOP, tool=c["name"], left_out=dropped, limit=MAX_PAGES_READ_PER_TURN)
            if err:
                trig(T_TOOL_ERROR, tool=c["name"], args=c["arguments"], error=err)
            elif _empty(c["name"], out):
                trig(T_TOOL_EMPTY, tool=c["name"], args=c["arguments"])
            items.append({"type": "function_call_output", "call_id": c["call_id"], "output": out})
            _remember_pages(case, pages)
            turn_pages += pages
            for p in pages:
                brand = library.doc_brand(p.doc_id) if library is not None and p.source != "web" else ""
                o = {"doc_id": p.doc_id, "title": p.title, "page": p.page, "sheet": p.sheet, "brand": brand,
                     "chars": len(p.text or ""), "url": p.url, "call": calls}
                opened.append(o)
                if p.source == "web":
                    if _is_forum(p.url):
                        trig(T_FORUM, url=p.url)
                elif unit_brands and library is not None and not (library.doc_brand_names(p.doc_id) & unit_brands):
                    trig(T_OTHER_BRAND, doc_id=p.doc_id, page=p.page, doc_brand=brand, unit_brands=sorted(unit_brands))
            rec = {"tool": c["name"], "args": c["arguments"], "call": calls, "seconds": secs, "chars": len(out),
                   "pages": len(pages), "page_chars": sum(len(p.text or "") for p in pages), "opened": [p.label() for p in pages]}
            if dropped:
                rec["left_out"] = dropped
            if err:
                rec["error"] = err
            tool_log.append(rec)
            case["searches"].append({"tool": c["name"], "args": c["arguments"]})
        if last:
            # App-side backstop only (Chase 2026-10-24): never shown to Grok. Grok still asked for tools on the call made
            # with tool_choice "none"; the turn ends here and is logged.
            problems.append(f"safety ceiling: turn stopped after {calls} calls while still asking for tools")
            break
    if calls >= SAFETY_CEILING_CALLS:
        if not any("safety ceiling" in p for p in problems):
            problems.append(f"safety ceiling: the last of {calls} calls was made with tools off")
        trig(T_SAFETY_CEILING, calls=calls)
    if not text.strip():
        text = CEILING_REPLY
    prose, update, probs = gd_state.parse(text)
    problems += probs
    if any(p == "no <state> block in reply" for p in probs):
        trig(T_STATE_MISSING)
    elif probs:
        trig(T_STATE_BROKEN, problems=probs)
    if (update.get("story") or "").strip():
        trig(T_STORY, chars=len(update["story"]))
    update = dict(update)
    if update:
        update.setdefault("order_part", "")   # per turn field: an order is not carried into a later turn
    case["state"] = gd_state.merge(case["state"], update)
    case["turns"] += 1
    case["problems"] = (case["problems"] + problems)[-50:]
    case["searches"] = case["searches"][-40:]
    lib_calls = [t for t in tool_log if t.get("side") != "xai"]
    usage["model_calls"] = calls
    usage["tool_calls"] = len(lib_calls)
    usage["tool_calls_by_name"] = {n: sum(1 for t in lib_calls if t["tool"] == n) for n in sorted({t["tool"] for t in lib_calls})}
    usage["tool_chars_returned"] = sum(t.get("chars", 0) for t in lib_calls)
    usage["pages_opened"] = len(turn_pages)
    usage["page_chars_opened"] = sum(len(p.text or "") for p in turn_pages)
    usage["web_search_calls"] = sum(1 for t in tool_log if t.get("side") == "xai")
    if usage.get("cost_in_usd_ticks"):
        usage["cost_usd"] = round(usage["cost_in_usd_ticks"] * USD_PER_TICK, 6)
    cited = _cited_with_pages(case["state"].get("cited") or [], case)
    lib_read = [p for p in _read_pages(case) if p.source != "web"]
    mode = "closed" if case["state"].get("closed") else ("walk" if lib_read else ("web" if case["web_sources"] else "no_manual"))
    ctx = sum(len(m.get("content") or "") for m in msgs)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "turn": case["turns"], "unit": dict(case["unit"]), "mode": mode,
           "model_calls": calls, "rounds": rounds, "context_chars": ctx, "tool_calls": tool_log, "pages_opened": opened,
           "web": web_log, "triggers": triggers, "problems": problems, "usage": usage,
           "tokens_in": usage.get("prompt_tokens", 0), "tokens_out": usage.get("completion_tokens", 0),
           "cost_usd": usage.get("cost_usd"), "cited": cited, "pages_used": [p.label() for p in _read_pages(case)],
           "web_sources": [w["url"] for w in case["web_sources"]], "seconds": round(time.time() - t0, 3)}
    case["log"] = (case["log"] + [{k: rec[k] for k in ("ts", "turn", "model_calls", "triggers", "usage", "seconds")}])[-CASE_LOG_KEEP:]
    store[STORE_KEY] = case
    path = DEFAULT_LOG_PATH if log_path is None else log_path
    if path:
        try:
            with open(path, "a") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
        except OSError as exc:
            problems.append(f"turn log not written: {exc}")
    return {"reply": prose, "mode": mode, "state": case["state"], "pages_used": rec["pages_used"], "not_shown": [],
            "usage": usage, "seconds": rec["seconds"], "context_chars": ctx, "problems": problems, "calls": calls,
            "cited": cited, "tool_calls": tool_log, "web_sources": list(case["web_sources"]), "pages_read": opened,
            "triggers": triggers, "log": rec}
