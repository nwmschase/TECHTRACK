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
     again with the results; web searches already ran on xAI's side inside the call. Pages opened with read_pages are
     also sent as page images in one message after the results (page_image_fn; caps MAX_PAGE_IMAGES_*). Repeat until a
     reply comes back with no function call.
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
# never shown to Grok and not in the primer, same pattern as SAFETY_CEILING_CALLS. ON at 30 (Chase 2026-10-24 2:51 PM).
# read_pages / open_web_document hand back at most this many pages in one turn; the rest are left out quietly and logged
# (PAGE_BACKSTOP_HIT). None turns it off.
# Why 30: a library page is about 3,000 characters (six-row check median 3,061), so 30 pages is about 90,000 characters,
# roughly 23,000 input tokens (~4 chars/token), about $0.03 at grok-4.3's $1.25/M input for one call. Pages read are re-sent
# on every later call of the turn and in later turns, so 30 bounds the worst turn near 6 calls x 23k = ~140k input tokens
# (~$0.17 uncached). A normal job reads 2-8 pages; 30 is three full reads at gd_tools.READ_MAX_PAGES (10), with room to
# read past a wrong manual, so a real job never meets it.
MAX_PAGES_READ_PER_TURN = 30
# Page images (Chase 2026-11-27, test1: "the library HALF useless because it thinks its all text"). When Grok opens library
# pages with read_pages, the app also hands it each page as a picture, drawn from the library PDF (the same drawing the
# "Show page" button uses), in one message right after the tool results (xAI docs: images go in a message as input_image
# data URLs; a function_call_output carries text). Pages carrying a picture label go first. App-side caps, logged, not in
# the primer: at most MAX_PAGE_IMAGES_PER_READ images per tool round and MAX_PAGE_IMAGES_PER_TURN per turn. Web pages get
# no image here (Grok's own web search can view and show web images). None turns a cap off; image_fn=None sends none.
MAX_PAGE_IMAGES_PER_READ = 6
MAX_PAGE_IMAGES_PER_TURN = 12
# Turn log (Chase 2026-10-24, "log triggers galore"): one JSON line per turn, app-side, never shown to Grok. run_turn writes
# to log_path; log_path=None (the default) means GD_TURN_LOG from the environment, else this file in the temp dir.
DEFAULT_LOG_PATH = os.environ.get("GD_TURN_LOG") or os.path.join(tempfile.gettempdir(), "techtrack-gd-turns.jsonl")
CASE_LOG_KEEP = 30            # turn records kept in the case (store) for the app's notes / cost review

# Trigger names (each logged as {"trigger": NAME, ...} in the turn record's "triggers" list, as they happen).
T_SAFETY_CEILING = "SAFETY_CEILING_HIT"            # the last allowed call was made with tools off / Grok still asked for tools
T_PAGE_BACKSTOP = "PAGE_BACKSTOP_HIT"              # MAX_PAGES_READ_PER_TURN left pages out (only when it is set)
T_PAGE_RANGE_LIMIT = "PAGE_RANGE_LIMIT_HIT"        # one read_pages request asked for more than gd_tools.READ_MAX_PAGES
T_OTHER_BRAND = "OTHER_BRAND_PAGE_READ"            # Grok opened a page of a doc whose maker is not the maker the tech typed
T_REPEAT = "REPEATED_SEARCH"                       # the same tool with the same arguments ran earlier in this job
T_TOOL_ERROR = "TOOL_ERROR"                        # a library tool returned an error
T_TOOL_EMPTY = "TOOL_EMPTY_RESULT"                 # a library tool returned nothing (no documents, hits or pages)
T_WEB_ERROR = "WEB_SEARCH_ERROR"                   # a server-side web search item came back failed
T_FORUM = "FORUM_SOURCE_USED"                      # a web source on a forum host
T_STATE_MISSING = "STATE_BLOCK_MISSING"
T_STATE_BROKEN = "STATE_BLOCK_BROKEN"
T_STORY = "STORY_WRITTEN"                          # the state block carried a technician story this turn
T_WEB_GATE_OPENED = "WEB_GATE_OPENED"              # v4.20.7: the web tools were offered for the first time in this job
T_CITED_NOT_OPENED = "CITED_NOT_OPENED"            # v4.20.7: Grok cited a library page it never opened (dropped)
T_APP_PICTURE_PAGE = "APP_OPENED_PICTURE_PAGE"     # v4.20.7: a picture was asked for, Grok opened no page, the app opened one

# v4.20.7 web gate (Chase 2026-11-28 t1713u; test8: Grok asked for the library and the web in the same round, xAI ran the web
# search inside that call, and Grok answered from the web before it saw the library list). The web tools are left out of
# the tool list until the job has a library page opened, or the library came back with nothing for the unit (an empty
# document list, a document list that had to be widened past the unit, or a whole-library page search with no hits). On a
# picture request the web tools also wait until the library was looked at in that turn. Decided from the app's own tool
# records, never from Grok's text.
WEB_TOOL_TYPES = ("web_search", "x_search")
WEB_FUNCTION_NAMES = ("open_web_document",)
WEB_GATE_CLOSED_RESULT = {"error": "open_web_document is not available yet: search the library and open a page first"}
LIBRARY_LOOKUPS = ("find_documents", "table_of_contents", "search_pages", "read_pages")
TRIGGERS = (T_SAFETY_CEILING, T_PAGE_BACKSTOP, T_PAGE_RANGE_LIMIT, T_OTHER_BRAND, T_REPEAT, T_TOOL_ERROR, T_TOOL_EMPTY,
            T_WEB_ERROR, T_FORUM, T_STATE_MISSING, T_STATE_BROKEN, T_STORY, T_WEB_GATE_OPENED,
            T_CITED_NOT_OPENED, T_APP_PICTURE_PAGE)
FORUM_HOST_WORDS = ("forum", "irv2", "reddit", "rvforums", "rv.net", "community", "facebook", "groups.", "quora", "boards.")
# xAI usage reports cost_in_usd_ticks (billed cost incl. server-side tools); 1 USD = 1e10 ticks (docs.x.ai/developers/cost-tracking)
USD_PER_TICK = 1e-10

# What the tech picked at the start of the job (app buttons), told to Grok as session context, not as a rule.
HELP_PAGES, HELP_WALKTHROUGH = "pages", "walkthrough"
HELP_MODE_LINES = {
    HELP_PAGES: ("HOW THE TECH WANTS HELP ON THIS JOB: the manual pages. He picked having the right manual pages and diagrams "
                 "found and shown, with a short pointer to what on them fits this unit and complaint, and he works the steps "
                 "himself. A step-by-step walkthrough from where he is is there whenever he asks for help or says he is stuck."),
    HELP_WALKTHROUGH: ("HOW THE TECH WANTS HELP ON THIS JOB: a full walkthrough of the diagnosis and the repair, one step at a time: "
                       "the check to make, the reading to expect, and what each result means."),
}

CEILING_REPLY = "I ran out of lookups for this message. Send it again and I will pick up from what I found."


def _read_limit():
    try:
        import gd_tools
        return gd_tools.READ_MAX_PAGES
    except Exception:
        return None


def new_case(category, model_text, complaint):
    return {"unit": {"category": category or "", "model_text": model_text or ""}, "complaint": complaint or "",
            "read": {}, "read_order": [], "web_sources": [], "searches": [],
            "state": gd_state.new_state(), "turns": 0, "problems": [], "notes_next": [],
            "web_gate": new_web_gate(), "found_docs": []}


def new_web_gate():
    return {"open": False, "why": "", "library_empty": False}


def is_web_tool(spec) -> bool:
    return spec.get("type") in WEB_TOOL_TYPES or (spec.get("type") == "function" and spec.get("name") in WEB_FUNCTION_NAMES)


def offered_tools(tool_specs, web_ok):
    """The tool list for one model round: every library tool, and the web tools only when web_ok."""
    return [t for t in tool_specs if web_ok or not is_web_tool(t)]


def web_allowed(gate, picture_request=False, library_looked_this_turn=False):
    """Web tools on this round? The job's gate is open, and on a picture request the library was looked at this turn
    (unless the library has nothing for the unit)."""
    if not gate.get("open"):
        return False
    if picture_request and not library_looked_this_turn and not gate.get("library_empty"):
        return False
    return True


def library_empty_reason(name, args, out):
    """Why this library result means the library has nothing for the unit, or "" (it has something)."""
    try:
        d = json.loads(out)
    except (TypeError, ValueError):
        return ""
    if not isinstance(d, dict) or d.get("error"):
        return ""
    if name == "find_documents":
        if not d.get("documents"):
            return "find_documents found no document"
        widened = d.get("filters_widened") or ""
        if "whole library" in widened or "listed by words instead" in widened:
            return f"find_documents: {widened}"
    if name == "search_pages" and not d.get("hits"):
        a = args if isinstance(args, dict) else {}
        if not a.get("doc_ids") and not a.get("brand") and not a.get("unit_type"):
            return "search_pages found no page in the whole library"
    return ""


def _found_doc_ids(out):
    try:
        d = json.loads(out)
    except (TypeError, ValueError):
        return []
    return [x.get("doc_id") for x in (d.get("documents") or []) if isinstance(x, dict) and x.get("doc_id")] if isinstance(d, dict) else []


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


MAX_CITED_FROM_OPENED = 8


def opened_citations(cited, case):
    """(kept, dropped): a library citation stays only when that page was opened in this job; a web citation (an address)
    stays when this job's web search returned it or it was opened."""
    read_keys = set()
    for p in _read_pages(case):
        read_keys.add((str(p.doc_id), str(p.page)))
        read_keys.add((str(p.doc_id), f"sheet {p.sheet}"))
    web = {w.get("url") for w in case.get("web_sources") or [] if w.get("url")}
    kept, dropped = [], []
    for c in cited or []:
        if not isinstance(c, dict):
            continue
        did, page = str(c.get("doc_id") or ""), str(c.get("page") or "")
        if (did, page) in read_keys or (did.startswith(("http://", "https://")) and did in web):
            kept.append({"doc_id": did, "page": page} if not did.startswith("http") else dict(c))
        else:
            dropped.append(dict(c))
    return kept, dropped


def app_open_picture_page(case, library, user_msg):
    """The best picture-labelled page of the manuals found for this unit (pages read in the job, then find_documents
    results; a unit search when neither), opened with read_pages. None when no such page exists."""
    import gd_picture

    docs = [p.doc_id for p in _read_pages(case) if p.source != "web"] + list(case.get("found_docs") or [])
    if not docs:
        unit = case.get("unit") or {}
        a = {k: v for k, v in (("unit_type", unit.get("category")), ("words", unit.get("model_text") or case.get("complaint")))
             if v}
        if a:
            out, _, err = library.call("find_documents", a)
            if not err and not library_empty_reason("find_documents", a, out):
                docs = _found_doc_ids(out)
    docs = list(dict.fromkeys(str(d) for d in docs if d))[:8]
    if not docs:
        return None
    words = " ".join(sorted(gd_picture.subject_words(user_msg))) + " picture diagram photo"
    out, _, err = library.call("search_pages", {"words": words.strip(), "doc_ids": docs, "limit": 12})
    if err:
        return None
    try:
        hits = json.loads(out).get("hits") or []
    except (TypeError, ValueError, AttributeError):
        return None
    pic = [dict(h, text=h.get("snippet") or "") for h in hits
           if gd_picture.has_picture_label(h.get("topics"))]
    if not pic:
        return None
    best = gd_picture.pick_picture_page(user_msg, pic)
    if best is None:
        return None
    _out, pages, err = library.call("read_pages", {"doc_id": best["doc_id"], "sheets": [int(best["sheet"])]}, max_pages=1)
    pages = [p for p in pages or [] if p.source != "web"]
    return pages[0] if pages and not err else None


def cited_from_opened(pages, limit=MAX_CITED_FROM_OPENED):
    """[{doc_id, page}] for the library pages opened this turn, in the order read (each once; web pages left out)."""
    out, seen = [], set()
    for p in pages or []:
        if getattr(p, "source", "") == "web":
            continue
        page = str(p.page) if p.page not in (None, "") else f"sheet {p.sheet}"
        key = (str(p.doc_id), page)
        if key in seen:
            continue
        seen.add(key)
        out.append({"doc_id": str(p.doc_id), "page": page})
    return out[:limit] if limit else out


def _has_picture_label(p: Page) -> bool:
    import gd_picture
    return gd_picture.has_picture_label(p.topics)


def page_image_order(pages):
    """Library pages that can get an image, picture-labelled pages first, each (doc_id, sheet) once, read order kept."""
    seen, lib = set(), []
    for p in pages or []:
        if p.source == "web" or not p.doc_id or not p.sheet or (p.doc_id, p.sheet) in seen:
            continue
        seen.add((p.doc_id, p.sheet))
        lib.append(p)
    return [p for p in lib if _has_picture_label(p)] + [p for p in lib if not _has_picture_label(p)]


def page_image_message(pages, image_fn, limit=None):
    """One input message with the page images for library pages just read, or (None, sent, failed).
    image_fn(doc_id, sheet) -> PNG/JPEG bytes or None. sent / failed: page labels."""
    import base64

    msg_parts, sent, failed = [], [], []
    for p in page_image_order(pages):
        if limit is not None and len(sent) >= limit:
            break
        try:
            data = image_fn(p.doc_id, int(p.sheet))
        except Exception:
            data = None
        if not data:
            failed.append(p.label())
            continue
        mime = "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
        msg_parts.append({"type": "input_text", "text": f"Page image: {p.label()} (PDF sheet {p.sheet})"})
        msg_parts.append({"type": "input_image", "image_url": f"data:{mime};base64," + base64.b64encode(data).decode("ascii"),
                          "detail": "high"})
        sent.append(p.label())
    if not sent:
        return None, sent, failed
    head = {"type": "input_text", "text": "The app attached the page images of the library pages just opened with read_pages, "
                                          "drawn from the library PDF, in the same order as labelled below."}
    return {"role": "user", "content": [head] + msg_parts}, sent, failed


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


def _args(arguments):
    try:
        a = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
    except (TypeError, ValueError):
        return {}
    return a if isinstance(a, dict) else {}


def _web_query(action):
    if isinstance(action, dict):
        return action.get("query") or action.get("url") or action.get("pattern") or ""
    return str(action or "")


def run_turn(user_msg, category, model_text, history, *, store, finder=None, library=None, chat_fn=None, respond_fn=None,
             usage_fn=None, web_fetch=None, log_path=None, tools=None, help_mode=None, page_image_fn=None,
             picture_request=False, **_old):
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
        case["web_gate"], case["found_docs"] = new_web_gate(), []
    case.setdefault("notes_next", []); case.setdefault("log", [])
    case.setdefault("web_gate", new_web_gate()); case.setdefault("found_docs", [])
    gate = case["web_gate"]
    if not gate["open"] and any(p.source != "web" for p in _read_pages(case)):
        gate.update(open=True, why="a library page was opened earlier in this job")
    if library is None and not gate["open"]:
        gate.update(open=True, why="the library is not loaded", library_empty=True)
    notes = list(case["notes_next"]); case["notes_next"] = []
    # The tech's up-front choice (Chase 2026-11-24): manual pages or a walkthrough. Stored in the job state and passed as
    # one plain line of session context; the primer is unchanged. A later choice (e.g. "Walk me through it") replaces it.
    if help_mode in HELP_MODE_LINES:
        case["state"]["help_mode"] = help_mode
    if case["state"].get("help_mode") in HELP_MODE_LINES:
        notes = [HELP_MODE_LINES[case["state"]["help_mode"]]] + notes
    msgs = gd_prompt.build_messages(user_msg=user_msg, history=history, category=case["unit"]["category"],
                                    model_text=case["unit"]["model_text"], pages=_read_pages(case),
                                    web_sources=case["web_sources"], searches=case["searches"], state=case["state"], notes=notes)
    items = list(msgs)
    unit_brands = library.unit_brands(case["unit"]["model_text"]) if library is not None and hasattr(library, "unit_brands") else set()
    seen_searches = {json.dumps([x.get("tool"), x.get("args")], sort_keys=True, default=str) for x in case["searches"]}
    calls, usage, problems, tool_log, turn_pages, triggers = 0, {}, [], [], [], []
    rounds, web_log, opened = [], [], []
    library_used_this_turn = False
    images_sent, images_failed, images_skipped = [], [], []
    text = ""

    def trig(name, **info):
        triggers.append({"trigger": name, "at_call": calls, **info})

    while True:
        last = calls + 1 >= SAFETY_CEILING_CALLS
        tc = time.time()
        web_ok = web_allowed(gate, picture_request, library_used_this_turn)
        round_specs = offered_tools(tool_specs, web_ok)
        got = _as_result(respond_fn(items + [gd_prompt.reminder_item()], round_specs, "none" if last else None))
        calls += 1
        if usage_fn and not got["usage"]:
            got["usage"] = usage_fn() or {}
        usage = _add_usage(usage, got["usage"])
        rounds.append({"call": calls, "seconds": round(time.time() - tc, 3), "tools_off": last, "web_offered": web_ok,
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
        round_lib_pages = []
        for c in got["calls"]:
            room = None if MAX_PAGES_READ_PER_TURN is None else max(0, MAX_PAGES_READ_PER_TURN - len(turn_pages))
            sig = json.dumps([c["name"], c["arguments"]], sort_keys=True, default=str)
            if sig in seen_searches:
                trig(T_REPEAT, tool=c["name"], args=c["arguments"])
            seen_searches.add(sig)
            if c["name"] not in WEB_FUNCTION_NAMES:
                library_used_this_turn = True
            dropped, tt = [], time.time()
            if c["name"] in WEB_FUNCTION_NAMES and not web_ok:
                # not offered this round (web gate): never run, whatever Grok asked for
                out, pages, err = json.dumps(WEB_GATE_CLOSED_RESULT), [], "web gate closed"
            elif library is None:
                out, pages, err = json.dumps({"error": "the library is not loaded"}), [], "no library"
            else:
                out, pages, err = library.call(c["name"], c["arguments"], max_pages=room)
                dropped = list(getattr(library, "last_dropped", []) or [])
            read_info = dict(getattr(library, "last_read", {}) or {}) if library is not None else {}
            if read_info.get("range_cut"):
                # Grok is told in the tool result which pages are left for another read; logged here.
                trig(T_PAGE_RANGE_LIMIT, tool=c["name"], requested=read_info.get("requested"),
                     limit=_read_limit(), not_opened=read_info["range_cut"])
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
            if c["name"] == "find_documents" and not err:
                case["found_docs"] = list(dict.fromkeys(_found_doc_ids(out) + case["found_docs"]))[:12]
            if not gate["open"] and not err:
                if c["name"] == "read_pages" and any(p.source != "web" for p in pages):
                    gate.update(open=True, why="a library page was opened")
                    trig(T_WEB_GATE_OPENED, why=gate["why"])
                else:
                    empty_why = library_empty_reason(c["name"], c["arguments"] if isinstance(c["arguments"], dict)
                                                     else _args(c["arguments"]), out)
                    if empty_why:
                        gate.update(open=True, why=empty_why, library_empty=True)
                        trig(T_WEB_GATE_OPENED, why=empty_why)
            _remember_pages(case, pages)
            turn_pages += pages
            if c["name"] == "read_pages":
                round_lib_pages += [p for p in pages if p.source != "web"]
            for p in pages:
                brand = library.doc_brand(p.doc_id) if library is not None and p.source != "web" else ""
                o = {"doc_id": p.doc_id, "title": p.title, "page": p.page, "sheet": p.sheet, "brand": brand,
                     "chars": len(p.text or ""), "url": p.url, "call": calls, "topics": p.topics or ""}
                opened.append(o)
                if p.source == "web":
                    if _is_forum(p.url):
                        trig(T_FORUM, url=p.url)
                elif unit_brands and library is not None and not (library.doc_brand_names(p.doc_id) & unit_brands):
                    trig(T_OTHER_BRAND, doc_id=p.doc_id, page=p.page, doc_brand=brand, unit_brands=sorted(unit_brands))
            rec = {"tool": c["name"], "args": c["arguments"], "call": calls, "seconds": secs, "chars": len(out),
                   "pages": len(pages), "page_chars": sum(len(p.text or "") for p in pages), "opened": [p.label() for p in pages]}
            if read_info:
                rec["pages_requested"] = read_info.get("requested", 0)
                rec["pages_served"] = len(pages)
                if read_info.get("range_cut"):
                    rec["range_cut"] = read_info["range_cut"]
                if read_info.get("not_found"):
                    rec["pages_not_found"] = read_info["not_found"]
            if dropped:
                rec["left_out"] = dropped
            if err:
                rec["error"] = err
            tool_log.append(rec)
            case["searches"].append({"tool": c["name"], "args": c["arguments"]})
        if page_image_fn is not None and round_lib_pages and not last:
            left = None if MAX_PAGE_IMAGES_PER_TURN is None else max(0, MAX_PAGE_IMAGES_PER_TURN - len(images_sent))
            caps = [x for x in (MAX_PAGE_IMAGES_PER_READ, left) if x is not None]
            cap = min(caps) if caps else None
            ordered = page_image_order(round_lib_pages)
            if cap == 0:
                images_skipped += [p.label() for p in ordered]
            else:
                msg, sent, failed = page_image_message(round_lib_pages, page_image_fn, limit=cap)
                if msg is not None:
                    items.append(msg)
                images_sent += sent
                images_failed += failed
                if cap is not None:
                    images_skipped += [p.label() for p in ordered if p.label() not in sent and p.label() not in failed]
            if images_failed:
                problems.append(f"page images not drawn: {', '.join(images_failed[:10])}")
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
    app_page = None
    if picture_request and library is not None and not any(p.source != "web" for p in turn_pages):
        # v4.20.7 (Chase t1713u): a picture was asked for and Grok opened no library page: the app opens the best
        # picture-labelled page of the manuals already found for the unit. None (no library picture) leaves Grok's reply.
        try:
            app_page = app_open_picture_page(case, library, user_msg)
        except Exception as exc:
            problems.append(f"app picture page failed: {exc}")
            app_page = None
        if app_page is not None:
            _remember_pages(case, [app_page])
            turn_pages.append(app_page)
            opened.append({"doc_id": app_page.doc_id, "title": app_page.title, "page": app_page.page, "sheet": app_page.sheet,
                           "brand": library.doc_brand(app_page.doc_id), "chars": len(app_page.text or ""), "url": "",
                           "call": calls, "topics": app_page.topics or "", "opened_by": "app"})
            tool_log.append({"tool": "read_pages", "side": "app", "args": {"doc_id": app_page.doc_id, "sheets": [app_page.sheet]},
                             "call": calls, "opened": [app_page.label()]})
            trig(T_APP_PICTURE_PAGE, doc_id=app_page.doc_id, page=app_page.page, sheet=app_page.sheet)
            if not gate["open"]:
                gate.update(open=True, why="a library page was opened (picture)")
                trig(T_WEB_GATE_OPENED, why=gate["why"])
    prose, update, probs = gd_state.parse(text)
    problems += probs
    state_missing = any(p == "no <state> block in reply" for p in probs)
    if state_missing:
        trig(T_STATE_MISSING)
    elif probs:
        trig(T_STATE_BROKEN, problems=probs)
    if (update.get("story") or "").strip():
        trig(T_STORY, chars=len(update["story"]))
    update = dict(update)
    if state_missing:
        # v4.20.6 (test7b): no block, so no cited list from Grok. The library pages Grok opened this turn stand in, so the
        # page buttons, the picture and the story's sources still have them.
        opened_cited = cited_from_opened(turn_pages)
        if opened_cited:
            update["cited"] = opened_cited
            problems.append(f"cited filled from {len(opened_cited)} page(s) opened this turn (no <state> block)")
    # v4.20.7 (audit M2): cited is this turn's list only; a block that leaves it out clears it (gd_state.merge keeps any
    # field left out, which carried the previous turn's pages). The opened-pages filter below runs on this list.
    update.setdefault("cited", [])
    if app_page is not None:
        ref = {"doc_id": str(app_page.doc_id), "page": str(app_page.page)}
        base = update.get("cited") if "cited" in update else []
        update["cited"] = [c for c in (base or []) if c != ref] + [ref]
    if update:
        update.setdefault("order_part", "")   # per turn field: an order is not carried into a later turn
    case["state"] = gd_state.merge(case["state"], update)
    # v4.20.7 (test8: "L6 error code chart" cited, never opened): only pages opened in this job stay cited; a web source
    # stays when it came back from this job's web search or was opened.
    kept, not_opened = opened_citations(case["state"].get("cited") or [], case)
    if not_opened:
        trig(T_CITED_NOT_OPENED, cited=not_opened)
        problems.append(f"cited but never opened (dropped): {', '.join(str(c.get('doc_id')) + ' ' + str(c.get('page')) for c in not_opened)}")
    case["state"]["cited"] = kept
    case["turns"] += 1
    case["problems"] = (case["problems"] + problems)[-50:]
    case["searches"] = case["searches"][-40:]
    lib_calls = [t for t in tool_log if t.get("side") not in ("xai", "app")]
    usage["model_calls"] = calls
    usage["tool_calls"] = len(lib_calls)
    usage["tool_calls_by_name"] = {n: sum(1 for t in lib_calls if t["tool"] == n) for n in sorted({t["tool"] for t in lib_calls})}
    usage["tool_chars_returned"] = sum(t.get("chars", 0) for t in lib_calls)
    usage["pages_opened"] = len(turn_pages)
    reads = [t for t in lib_calls if "pages_requested" in t]
    usage["pages_requested"] = sum(t["pages_requested"] for t in reads)
    usage["pages_served"] = sum(t["pages_served"] for t in reads)
    usage["pages_range_cut"] = sum(len(t.get("range_cut") or []) for t in reads)
    usage["pages_backstop_left_out"] = sum(len(t.get("left_out") or []) for t in lib_calls)
    usage["pages_backstop"] = MAX_PAGES_READ_PER_TURN
    usage["page_chars_opened"] = sum(len(p.text or "") for p in turn_pages)
    usage["web_search_calls"] = sum(1 for t in tool_log if t.get("side") == "xai")
    usage["page_images_sent"] = len(images_sent)
    usage["page_images_failed"] = len(images_failed)
    usage["page_images_skipped"] = len(images_skipped)
    if usage.get("cost_in_usd_ticks"):
        usage["cost_usd"] = round(usage["cost_in_usd_ticks"] * USD_PER_TICK, 6)
    cited = _cited_with_pages(case["state"].get("cited") or [], case)
    lib_read = [p for p in _read_pages(case) if p.source != "web"]
    mode = "closed" if case["state"].get("closed") else ("walk" if lib_read else ("web" if case["web_sources"] else "no_manual"))
    ctx = sum(len(m.get("content") or "") for m in msgs)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "turn": case["turns"], "unit": dict(case["unit"]), "mode": mode,
           "model_calls": calls, "rounds": rounds, "pages_requested": usage["pages_requested"],
           "pages_served": usage["pages_served"], "pages_backstop": MAX_PAGES_READ_PER_TURN, "context_chars": ctx, "tool_calls": tool_log, "pages_opened": opened,
           "web": web_log, "triggers": triggers, "problems": problems, "usage": usage,
           "page_images": {"sent": images_sent, "failed": images_failed, "skipped": images_skipped},
           "web_gate": dict(gate), "picture_request": bool(picture_request),
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
            "triggers": triggers, "page_images": rec["page_images"], "log": rec,
            "turn_pages": [p for p in turn_pages if p.source != "web"]}   # this turn's opened library pages (not logged)
