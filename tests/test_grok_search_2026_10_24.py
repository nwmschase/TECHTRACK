"""Grok does the looking (Chase 2026-10-22 / 2026-10-24): library tools Grok calls itself, xAI's built-in web search in
Grok's own call, the 6-call safety ceiling, the pages backstop (off by default), the turn log and its triggers.
Offline: scripted fakes and a fake xAI client, no network, no paid call."""
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_llm  # noqa: E402
import gd_prompt  # noqa: E402
import gd_tools  # noqa: E402
import gd_turn  # noqa: E402
from gd_pages import Page  # noqa: E402
from gd_fixtures import StubPageFinder  # noqa: E402
from test_fresh_core import FakeChat, FakeRespond, block, outputs, page, MAN  # noqa: E402

OTHER = {"doc_id": "L9", "title": "Other Maker Fridge Sheet", "brand": "Othermaker", "unit_type": "refrigerator", "doc_type": "tech-sheet"}


def lib_finder():
    return StubPageFinder(
        manuals=MAN + [OTHER],
        pages=[page(sheet=2, kind="toc", text="Contents: Troubleshooting ... 25; Fan ... 29"),
               page(sheet=25, kind="entry", text="TROUBLESHOOTING CHART: E2 = freezer fan fault"),
               page(sheet=29, text="Freezer fan motor test: 12 V at F+ F-, 0.3 A draw"),
               page(sheet=30, text="Thermistor chart 10k ohm at 77F"),
               Page(doc_id="L9", title="Other Maker Fridge Sheet", page="2", sheet=2, text="Othermaker fan motor test 12 V")])


def tmplog():
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    return path


def names(r):
    return [t["trigger"] for t in r["triggers"]]


class XaiShapes:
    """The parts of an xAI Responses API reply (docs.x.ai/developers/tools/advanced-usage) as plain dicts."""

    @staticmethod
    def fcall(cid, name, args):
        return {"type": "function_call", "call_id": cid, "name": name, "arguments": json.dumps(args), "id": "fc_" + cid, "status": "completed"}

    @staticmethod
    def web(query, status="completed"):
        return {"type": "web_search_call", "id": "ws1", "status": status, "action": {"type": "search", "query": query}}

    @staticmethod
    def msg(text, urls=()):
        return {"type": "message", "role": "assistant", "id": "m1", "status": "completed",
                "content": [{"type": "output_text", "text": text,
                             "annotations": [{"type": "url_citation", "url": u, "start_index": 0, "end_index": 0, "title": str(i + 1)}
                                             for i, u in enumerate(urls)]}]}

    @staticmethod
    def resp(*items, usage=None):
        return {"id": "resp_1", "model": "grok-4.3", "output": list(items),
                "usage": usage or {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 800}, "output_tokens": 200,
                                   "output_tokens_details": {"reasoning_tokens": 50}, "num_server_side_tools_used": 0,
                                   "cost_in_usd_ticks": 12_000_000}}


class FakeXai:
    """Stands in for OpenAI(base_url=api.x.ai): client.responses.create(**kw) returns the next scripted reply."""

    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
        outer = self

        class _R:
            def create(self, **kw):
                outer.requests.append(json.loads(json.dumps(kw, default=str)))
                return outer.replies.pop(0)
        self.responses = _R()

    def factory(self, provider, *, api_key, base_url):
        assert provider == gd_llm.PROVIDER_XAI and base_url == gd_llm.DEFAULT_XAI_BASE_URL
        return self


SECRETS = {"XAI_API_KEY": "test-key-not-real", "XAI_MODEL": "grok-4.3"}


class TestFullTurnLibraryThenWeb(unittest.TestCase):
    """One whole turn through gd_llm.respond and a fake xAI client: library tools first, then the built-in web search
    and a web document, then the final reply; every request carries both kinds of tool."""

    def run_case(self, replies, finder=None, log=None):
        x = FakeXai(replies)
        fetched = []

        def fetch(url, words):
            fetched.append(url)
            return [Page(doc_id="web:acme.com/fan.pdf", title="fan.pdf", page="4", sheet=4, text="Acme fan spec 0.3 A", kind="web",
                         source="web", url=url, revision="Rev 2024")]

        def respond_fn(items, tools, tool_choice=None):
            return gd_llm.respond(items, tools, tool_choice=tool_choice, secret_fn=SECRETS.get, client_factory=x.factory)
        store = {}
        r = gd_turn.run_turn("E2 and the freezer is warm", "Refrigerators", "Acme X1", [], finder=finder or lib_finder(),
                             respond_fn=respond_fn, store=store, web_fetch=fetch, log_path=log or "")
        return r, x, fetched, store

    def test_library_then_web_then_answer(self):
        X = XaiShapes
        replies = [X.resp(X.fcall("a", "find_documents", {"brand": "Acme", "unit_type": "refrigerator"}),
                          X.fcall("b", "search_pages", {"words": "E2 freezer fan", "doc_ids": ["L1"]})),
                   X.resp(X.fcall("c", "read_pages", {"doc_id": "L1", "pages": ["25", "29"]})),
                   X.resp(X.web("Acme X1 freezer fan amp draw spec"),
                          X.fcall("d", "open_web_document", {"url": "https://www.acme.com/fan.pdf", "words": "amp"})),
                   X.resp(X.msg("The fan should draw about 0.3 A [Acme Fridge Service Manual].\n"
                                + block(cited=[{"doc_id": "L1", "page": "29"}], summary="E2; fan test", web_lookup="Acme X1 fan amp"),
                                urls=["https://www.acme.com/fan.pdf"]))]
        log = tmplog()
        r, x, fetched, store = self.run_case(replies, log=log)
        self.assertEqual(r["calls"], 4)
        self.assertTrue(r["reply"].startswith("The fan should draw about 0.3 A"))
        # v4.20.7 web gate: the library tools only until a library page is open (round 3 on), then + the web tools
        for i, req in enumerate(x.requests):
            kinds = [t.get("name") or t["type"] for t in req["tools"]]
            if i < 2:
                self.assertEqual(kinds, ["find_documents", "table_of_contents", "search_pages", "read_pages"])
            else:
                self.assertEqual(kinds, list(gd_tools.FUNCTION_NAMES) + ["web_search"])
            self.assertIn("no_inline_citations", req["include"])
            self.assertEqual(req["model"], "grok-4.3")
            self.assertNotIn("max_output_tokens", req)
        # the function results went back in as function_call_output items with the right call ids
        sent = x.requests[1]["input"]
        outs = {i["call_id"]: json.loads(i["output"]) for i in sent if i.get("type") == "function_call_output"}
        self.assertEqual(outs["a"]["documents"][0]["doc_id"], "L1")
        self.assertEqual(outs["b"]["hits"][0]["page"], "25")
        self.assertIn("function_call", [i.get("type") for i in sent])   # Grok's own call items sent back first
        last = x.requests[3]["input"]
        self.assertIn("web_search_call", [i.get("type") for i in last])
        self.assertEqual(fetched, ["https://www.acme.com/fan.pdf"])
        # what the app gets back
        self.assertEqual(r["cited"], [{"doc_id": "L1", "page": "29", "title": "Acme Fridge Service Manual", "sheet": 29, "read": True}])
        self.assertEqual([p["page"] for p in r["pages_read"]], ["25", "29", "4"])
        self.assertEqual(r["web_sources"], [{"url": "https://www.acme.com/fan.pdf", "title": "1"}])
        self.assertEqual(r["mode"], "walk")
        self.assertEqual(r["usage"]["model_calls"], 4)
        self.assertEqual(r["usage"]["prompt_tokens"], 4000)
        self.assertEqual(r["usage"]["tool_calls"], 4)
        self.assertEqual(r["usage"]["web_search_calls"], 1)
        self.assertEqual(r["usage"]["pages_opened"], 3)
        self.assertAlmostEqual(r["usage"]["cost_usd"], 4 * 12_000_000 * gd_turn.USD_PER_TICK)
        self.assertIn("WEB_GATE_OPENED", names(r))   # v4.20.7: the web tools opened after the page read
        self.assertIn(gd_turn.T_MEANING_OFF, names(r))  # v4.20.8: meaning search is off by default
        # the JSON-lines turn log
        rec = json.loads(open(log).read().strip().splitlines()[-1])
        for k in ("model_calls", "rounds", "tool_calls", "pages_opened", "web", "triggers", "tokens_in", "tokens_out", "cost_usd", "seconds"):
            self.assertIn(k, rec)
        self.assertEqual(rec["web"][0]["query"], "Acme X1 freezer fan amp draw spec")
        self.assertEqual(rec["web"][1]["sources"], ["https://www.acme.com/fan.pdf"])
        t = rec["tool_calls"][0]
        self.assertEqual((t["tool"], t["call"]), ("find_documents", 1))
        self.assertGreater(t["chars"], 0)
        self.assertIn("seconds", t)
        self.assertEqual([(p["doc_id"], p["page"], p["brand"]) for p in rec["pages_opened"]][:2], [("L1", "25", "Acme"), ("L1", "29", "Acme")])
        self.assertEqual(len(store["gd_case"]["log"]), 1)

    def test_ceiling_still_enforced_with_tools(self):
        X = XaiShapes
        replies = [X.resp(X.fcall(f"c{i}", "search_pages", {"words": f"fan {i}"})) for i in range(5)]
        replies.append(X.resp(X.msg("Here is where we are.\n" + block(summary="s"))))
        r, x, _, _ = self.run_case(replies)
        self.assertEqual(r["calls"], gd_turn.SAFETY_CEILING_CALLS)
        self.assertEqual([q.get("tool_choice") for q in x.requests], [None] * 5 + ["none"])
        self.assertIn(gd_turn.T_SAFETY_CEILING, names(r))
        self.assertEqual(r["reply"], "Here is where we are.")
        for q in x.requests:
            self.assertNotIn("ceiling", json.dumps(q["input"]).lower())

    def test_grok_still_asking_on_the_last_call_gets_a_plain_reply(self):
        X = XaiShapes
        replies = [X.resp(X.fcall(f"c{i}", "search_pages", {"words": f"fan {i}"})) for i in range(6)]
        r, x, _, _ = self.run_case(replies)
        self.assertEqual(r["calls"], 6)
        self.assertEqual(r["reply"], gd_turn.CEILING_REPLY)
        self.assertTrue(any("still asking for tools" in p for p in r["problems"]))


class TestRespondAdapter(unittest.TestCase):
    def test_parse_response(self):
        X = XaiShapes
        got = gd_llm.parse_response(X.resp(X.web("q1"), X.fcall("z", "read_pages", {"doc_id": "L1"}), X.msg("hi", ["https://a.example/x"])))
        self.assertEqual(got["calls"][0]["name"], "read_pages")
        self.assertEqual(got["server_tools"][0]["action"]["query"], "q1")
        self.assertEqual(got["web_sources"], [{"url": "https://a.example/x", "title": "1"}])
        self.assertEqual(got["usage"]["cached_tokens"], 800)
        self.assertEqual(got["usage"]["cost_in_usd_ticks"], 12_000_000)

    def test_no_key_raises_the_offline_line(self):
        with self.assertRaises(gd_llm.LLMProviderError):
            gd_llm.respond([], gd_tools.TOOL_SPECS, secret_fn=lambda k: None)

    def test_app_uses_respond_with_tools(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        a = src.index("def _gd_official_reply(")
        body = src[a:src.index("\ndef guided_diagnostics_reply(", a)]
        self.assertIn("gd_llm.respond(items, tools, tool_choice=tool_choice, secret_fn=_secret,", body)
        self.assertNotIn("web_fn=", body)


class TestToolsReturnPagesNotManuals(unittest.TestCase):
    def setUp(self):
        self.t = gd_tools.LibraryTools.for_finder(lib_finder())

    def test_snippets_are_short_and_ranked_plainly(self):
        r = self.t.search_pages("fan motor test")
        self.assertTrue(all(len(h["snippet"]) <= gd_tools.SNIPPET_CHARS + 10 for h in r["hits"]))
        self.assertEqual({h["doc_id"] for h in r["hits"][:2]}, {"L1", "L9"})   # both makers, each labeled with its own doc
        self.assertEqual([h["score"] for h in r["hits"]], sorted([h["score"] for h in r["hits"]], reverse=True))
        self.assertTrue(all("text" not in h for h in r["hits"]))

    def test_table_of_contents_gives_labels_not_the_manual(self):
        long = StubPageFinder(manuals=MAN, pages=[page(sheet=1, kind="toc", text="x " * 5000)] +
                              [page(sheet=i, text="body " * 800) for i in range(2, 20)])
        toc = gd_tools.LibraryTools.for_finder(long).table_of_contents("L1")
        self.assertLessEqual(len(toc["contents_pages"][0]["text"]), gd_tools.TOC_PAGE_CHARS)
        self.assertTrue(all(len(r["first_line"]) <= 70 and "text" not in r for r in toc["outline"]))
        self.assertLess(len(json.dumps(toc)), 6000)

    def test_read_pages_returns_the_pages_asked_for(self):
        res, pages = self.t.read_pages("L1", pages=["29"])
        self.assertEqual([p["page"] for p in res["pages"]], ["29"])
        res, pages = self.t.read_pages("L1", pages=["1-999999"])  # a silly range is taken as typed, not expanded
        self.assertEqual(pages, [])
        self.assertEqual(res["not_found"], ["page 1-999999"])
        res, pages = self.t.read_pages("L1", pages=["29-30"])
        self.assertEqual([p.page for p in pages], ["29", "30"])

    def test_tool_errors_come_back_as_results(self):
        out, pages, err = self.t.call("read_pages", '{"doc_id": "L404"}')
        self.assertIn("no document L404", json.loads(out)["error"])
        out, pages, err = self.t.call("read_pages", "{not json")
        self.assertTrue(err)
        out, pages, err = self.t.call("drop_table", "{}")
        self.assertIn("unknown tool", err)


class TestPagesBackstop(unittest.TestCase):
    def setUp(self):
        self.was = gd_turn.MAX_PAGES_READ_PER_TURN

    def tearDown(self):
        gd_turn.MAX_PAGES_READ_PER_TURN = self.was

    def test_on_at_30_and_quiet(self):
        """Chase 2026-10-24 2:51 PM: backstop ON; about 3,000 chars a page -> 30 pages ~ 90k chars a turn. Not in the
        primer, the state format or any tool description."""
        self.assertEqual(gd_turn.MAX_PAGES_READ_PER_TURN, 30)
        shown = gd_prompt.SYSTEM + json.dumps(gd_tools.TOOL_SPECS)
        self.assertNotIn("30 pages", shown)
        self.assertNotIn("backstop", shown.lower())
        self.assertNotIn("per turn", shown.lower())

    def test_backstop_cuts_quietly_at_30_and_logs_requested_vs_served(self):
        big = StubPageFinder(manuals=MAN, pages=[page(sheet=i, text=f"page {i} " * 50) for i in range(1, 41)])
        script = [[("read_pages", {"doc_id": "L1", "sheets": list(range(k, k + 10))})] for k in (1, 11, 21, 31)]
        chat = FakeRespond(script + ["ok\n" + block(summary="s")])
        log = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=big, respond_fn=chat, store={}, log_path=log)
        self.assertEqual(r["usage"]["pages_opened"], 30)
        self.assertEqual(r["usage"]["pages_requested"], 40)
        self.assertEqual(r["usage"]["pages_served"], 30)
        self.assertEqual(r["usage"]["pages_backstop_left_out"], 10)
        self.assertEqual(outputs(chat.seen[4][0])[3]["pages"], [])
        self.assertNotIn("limit", outputs(chat.seen[4][0])[3])          # the backstop says nothing to Grok
        self.assertIn(gd_turn.T_PAGE_BACKSTOP, names(r))
        self.assertNotIn(gd_turn.T_PAGE_RANGE_LIMIT, names(r))
        rec = json.loads(open(log).read().splitlines()[-1])
        self.assertEqual((rec["pages_requested"], rec["pages_served"], rec["pages_backstop"]), (40, 30, 30))
        self.assertEqual([t["pages_requested"] for t in rec["tool_calls"]], [10, 10, 10, 10])
        self.assertEqual([t["pages_served"] for t in rec["tool_calls"]], [10, 10, 10, 0])

    def test_when_set_pages_past_it_are_left_out_logged_and_not_shown(self):
        gd_turn.MAX_PAGES_READ_PER_TURN = 2
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": ["25", "29"]})],
                            [("read_pages", {"doc_id": "L1", "pages": ["30"]}), ("read_pages", {"doc_id": "L9", "pages": ["2"]})],
                            "ok\n" + block(summary="s")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=lib_finder(), respond_fn=chat, store={}, log_path="")
        self.assertEqual(r["usage"]["pages_opened"], 2)
        later = outputs(chat.seen[2][0])[1:]
        self.assertEqual([o["pages"] for o in later], [[], []])
        self.assertIn(gd_turn.T_PAGE_BACKSTOP, names(r))
        self.assertTrue(any("pages backstop" in p for p in r["problems"]))
        self.assertNotIn("backstop", json.dumps(chat.seen[2][0]).lower())


class TestTriggers(unittest.TestCase):
    def turn(self, script, model="Acme X1", **kw):
        chat = FakeRespond(script) if not isinstance(script, FakeChat) else None
        r = gd_turn.run_turn("E2", "Refrigerators", model, [], finder=lib_finder(), store=kw.pop("store", {}), log_path="",
                             **({"respond_fn": chat} if chat else {"chat_fn": script}), **kw)
        return r

    def test_names_are_clear_and_unique(self):
        self.assertEqual(len(set(gd_turn.TRIGGERS)), len(gd_turn.TRIGGERS))
        self.assertTrue(all(re.fullmatch(r"[A-Z_]+", t) for t in gd_turn.TRIGGERS))

    def test_other_brand_page_read(self):
        r = self.turn([[("read_pages", {"doc_id": "L9", "pages": ["2"]})], "ok\n" + block(summary="s")])
        t = [x for x in r["triggers"] if x["trigger"] == gd_turn.T_OTHER_BRAND]
        self.assertEqual((t[0]["doc_id"], t[0]["doc_brand"], t[0]["unit_brands"]), ("L9", "Othermaker", ["acme"]))
        r = self.turn([[("read_pages", {"doc_id": "L1", "pages": ["29"]})], "ok\n" + block(summary="s")])
        self.assertNotIn(gd_turn.T_OTHER_BRAND, names(r))

    def test_web_gate_replaced_the_log_only_trigger(self):
        # v4.20.7: WEB_BEFORE_LIBRARY_SEARCH only logged; the gate stops it instead (it must not come back)
        self.assertFalse(hasattr(gd_turn, "T_WEB_BEFORE_LIBRARY"))
        self.assertNotIn("WEB_BEFORE_LIBRARY_SEARCH", open(gd_turn.__file__, encoding="utf-8").read())
        fetched = []
        r = self.turn([[("open_web_document", {"url": "https://x.example/a.pdf"})], "ok\n" + block(summary="s")],
                      web_fetch=lambda u, w: fetched.append(u) or [])
        self.assertEqual(fetched, [])                       # asked for before the library: never run
        self.assertIn(gd_turn.T_TOOL_ERROR, names(r))

    def test_repeated_search_in_the_turn_and_across_turns(self):
        store = {}
        r = self.turn([[("search_pages", {"words": "fan"})], [("search_pages", {"words": "fan"})], "ok\n" + block(summary="s")], store=store)
        self.assertEqual(names(r).count(gd_turn.T_REPEAT), 1)
        r = self.turn([[("search_pages", {"words": "fan"})], "ok\n" + block(summary="s")], store=store)
        self.assertIn(gd_turn.T_REPEAT, names(r))

    def test_tool_error_and_empty_result(self):
        r = self.turn([[("read_pages", {"doc_id": "L404", "pages": ["1"]}), ("search_pages", {"words": "zzqx"})], "ok\n" + block(summary="s")])
        self.assertIn(gd_turn.T_TOOL_ERROR, names(r))
        self.assertIn(gd_turn.T_TOOL_EMPTY, names(r))

    def test_web_search_error_and_forum_source(self):
        def respond(items, tools, tool_choice=None):
            return {"text": "ok\n" + block(summary="s"), "server_tools": [{"type": "web_search_call", "status": "failed", "action": {"query": "q"}}],
                    "web_sources": [{"url": "https://www.irv2.com/forums/threads/123"}, {"url": "https://www.acme.com/m.pdf"}]}
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=lib_finder(), respond_fn=respond, store={}, log_path="")
        self.assertIn(gd_turn.T_WEB_ERROR, names(r))
        forum = [t for t in r["triggers"] if t["trigger"] == gd_turn.T_FORUM]
        self.assertEqual([t["url"] for t in forum], ["https://www.irv2.com/forums/threads/123"])

    def test_state_block_missing_and_broken(self):
        self.assertIn(gd_turn.T_STATE_MISSING, names(self.turn(FakeChat(["no block here"]))))
        self.assertIn(gd_turn.T_STATE_BROKEN, names(self.turn(FakeChat(["x <state>{not json}</state>"]))))
        # v4.20.9: the story field and its STORY_WRITTEN trigger are deleted; a stray story is ignored, never stored
        self.assertFalse(hasattr(gd_turn, "T_STORY"))
        r = self.turn(FakeChat(["Done.\n" + block(story="Complaint: E2. Cause: fan. Correction: replaced fan.", summary="s")]))
        self.assertNotIn("story", r["state"])

    def test_safety_ceiling_trigger(self):
        r = self.turn([[("search_pages", {"words": f"w{i}"})] for i in range(6)])
        self.assertIn(gd_turn.T_SAFETY_CEILING, names(r))

    def test_triggers_are_never_shown_to_grok(self):
        store = {}
        self.turn([[("read_pages", {"doc_id": "L9", "pages": ["2"]})], "ok"], store=store)
        chat = FakeChat(["ok\n" + block(summary="s")])
        self.turn(chat, store=store)
        sent = json.dumps(chat.seen[0][0])
        for t in gd_turn.TRIGGERS:
            self.assertNotIn(t, sent)


INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
# The 840-doc library copy that holds the Atwood DSI manuals (L892-L894) used by F35 (copied from /tmp/fq2/app.db).
APP_DB = next((p for p in (os.environ.get("TT_TEST_GROK_APP_DB", ""), "/workspace/techtrack-fresh/runs/grok-search-2026-10-24/app.db",
                           "/tmp/fq2/app.db") if p and os.path.exists(p)), "")


@unittest.skipUnless(os.path.exists(os.path.join(INDEX, "index.sqlite")) and bool(APP_DB), "index / 840-doc app DB not on this box")
class TestSixFollowUpsOnTheRealLibrary(unittest.TestCase):
    """F08 F09 F15 F27 F31 F35 (runs/priority-2026-10-22/harness/fq.py) with the arguments Grok would send: the maker's
    own documents come back, labeled with their maker; no other maker outranks them (the old flat 0.50 flaw)."""

    @classmethod
    def setUpClass(cls):
        import gd_pages
        sys.path.insert(0, str(ROOT / "scripts"))
        import grok_tool_check
        cls.rows, cls.sizes = grok_tool_check.run(gd_tools.LibraryTools.for_finder(gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)))

    def test_find_documents_lists_the_units_manual(self):
        for r in self.rows:
            self.assertTrue(r["find_ok"], r["id"])

    def test_search_hits_are_the_units_maker_and_hold_the_gold_doc(self):
        want = {"F08": "Suburban", "F09": "Suburban", "F15": "Furrion", "F27": "Furrion", "F31": "Furrion", "F35": "Atwood"}
        for r in self.rows:
            self.assertEqual(r["hit_brands"], [want[r["id"]]], r["id"])
            self.assertGreater(r["gold_in_hits"], 0, r["id"])

    def test_the_page_opened_answers_the_follow_up(self):
        for r in self.rows:
            if r["id"] == "F15":      # no page of the FACT12SA2 docs gives sensor ohms: the library has no value (a web case)
                continue
            self.assertTrue(r["read_matches"], r["id"])

    def test_return_sizes_stay_small(self):
        self.assertLess(self.sizes["search_pages"]["max"], 12000)
        self.assertLess(self.sizes["find_documents"]["max"], 6000)
        self.assertLess(self.sizes["read_pages"]["max"], 15000)


if __name__ == "__main__":
    unittest.main()


class TestReadLimitPerRequest(unittest.TestCase):
    """Chase 2026-10-24 2:51 PM: keep the 10-pages-per-read limit; Grok is told plainly what was left for another read."""

    def setUp(self):
        self.big = StubPageFinder(manuals=MAN, pages=[page(sheet=i, text=f"page {i}") for i in range(1, 31)])
        self.t = gd_tools.LibraryTools.for_finder(self.big)

    def test_number_in_code_matches_primer(self):
        self.assertEqual(gd_tools.READ_MAX_PAGES, 10)
        self.assertIn(f"One read opens up to {gd_tools.READ_MAX_PAGES} pages.", gd_prompt.PRIMER)
        self.assertIn("up to 10 pages", [t for t in gd_tools.FUNCTION_SPECS if t["name"] == "read_pages"][0]["description"])

    def test_cut_to_the_limit_says_so(self):
        res, pages = self.t.read_pages("L1", sheets=list(range(1, 26)))
        self.assertEqual([p.sheet for p in pages], list(range(1, 11)))
        self.assertEqual(res["limit"], "pages 1-10 of the 25 requested are here; one read opens up to 10 pages. "
                                       "Ask again for the rest: 11-25")
        self.assertEqual(res["not_opened_yet"], [str(i) for i in range(11, 26)])
        self.assertEqual(self.t.last_read, {"requested": 25, "served": 10, "range_cut": [str(i) for i in range(11, 26)],
                                            "not_found": 0})

    def test_a_range_is_expanded_and_cut(self):
        res, pages = self.t.read_pages("L1", pages=["1-25"])
        self.assertEqual(len(pages), 10)
        self.assertIn("Ask again for the rest: 11-25", res["limit"])

    def test_ten_or_fewer_has_no_note(self):
        res, pages = self.t.read_pages("L1", pages=["1-10"])
        self.assertEqual(len(pages), 10)
        self.assertNotIn("limit", res)

    def test_trigger_and_log(self):
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": ["1-25"]})],
                            [("read_pages", {"doc_id": "L1", "pages": ["11-20"]})], "ok\n" + block(summary="s")])
        log = os.path.join(tempfile.mkdtemp(), "t.jsonl")
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=self.big, respond_fn=chat, store={}, log_path=log)
        hits = [t for t in r["triggers"] if t["trigger"] == gd_turn.T_PAGE_RANGE_LIMIT]
        self.assertEqual(len(hits), 1)
        self.assertEqual((hits[0]["requested"], hits[0]["limit"], len(hits[0]["not_opened"])), (25, 10, 15))
        self.assertIn("Ask again for the rest", outputs(chat.seen[1][0])[0]["limit"])
        rec = json.loads(open(log).read().splitlines()[-1])
        self.assertEqual(rec["tool_calls"][0]["pages_requested"], 25)
        self.assertEqual(rec["tool_calls"][0]["pages_served"], 10)
        self.assertEqual(len(rec["tool_calls"][0]["range_cut"]), 15)
        self.assertEqual((rec["pages_requested"], rec["pages_served"]), (35, 20))
        self.assertEqual(r["usage"]["pages_range_cut"], 15)
        self.assertNotIn("PAGE_RANGE_LIMIT", json.dumps(chat.seen[-1][0]))   # the trigger name is log-only
