"""Offline tests for the fresh GD core. No LLM call: chat_fn is a scripted fake."""
import json
import os
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gd_pages  # noqa: E402
from pagefinder import search as _pf_search  # noqa: E402

_REAL_MEANING = _pf_search.meaning   # keep before any test swaps in a keyword-only stub
import gd_prompt  # noqa: E402
import gd_state  # noqa: E402
import gd_story  # noqa: E402
import gd_turn  # noqa: E402
from gd_pages import Page  # noqa: E402
from gd_fixtures import StubPageFinder  # noqa: E402

MAN = [{"doc_id": "L1", "title": "Acme Fridge Service Manual", "brand": "Acme", "unit_type": "refrigerator", "doc_type": "service-manual"}]


def page(doc="L1", sheet=1, kind="support", text=None, title="Acme Fridge Service Manual"):
    return Page(doc_id=doc, title=title, page=str(sheet), sheet=sheet, text=text if text is not None else f"page {sheet} text", kind=kind)


def finder():
    return StubPageFinder(
        manuals=MAN,
        pages=[page(sheet=25, kind="entry", text="TROUBLESHOOTING CHART: E2 = freezer fan fault"), page(sheet=18, text="fan wiring")],
        toc=[page(sheet=2, kind="toc", text="Contents: Troubleshooting ... 25")],
        parts={"freezer fan motor": [page(sheet=29, kind="part", text="Freezer fan motor test: 12 V at F+ F-")]},
    )


def block(**kw):
    return "<state>" + json.dumps(kw) + "</state>"


class FakeChat:
    def __init__(self, replies):
        self.replies, self.seen = list(replies), []

    def __call__(self, messages, max_tokens, effort):
        self.seen.append((messages, max_tokens, effort))
        return self.replies.pop(0)


class FakeRespond:
    """Scripted Grok on the tool path: each script entry is a reply string (final) or a list of (tool name, args)
    function calls. Records every input list it was sent."""
    def __init__(self, script):
        self.script, self.seen, self.n = list(script), [], 0

    def __call__(self, items, tools, tool_choice=None):
        self.seen.append((list(items), tools, tool_choice))
        step = self.script.pop(0)
        if isinstance(step, str):
            return {"text": step}
        calls = []
        for name, args in step:
            self.n += 1
            calls.append({"call_id": f"c{self.n}", "name": name, "arguments": json.dumps(args)})
        return {"text": "", "calls": calls}


def outputs(items):
    return [json.loads(i["output"]) for i in items if isinstance(i, dict) and i.get("type") == "function_call_output"]


class TestPromptAssembly(unittest.TestCase):
    def test_contents_and_order(self):
        st = gd_state.merge(gd_state.new_state(), {"facts": [{"item": "fan volts", "value": "10.4 V", "quote": "10.4 at the fan"}],
                                                   "summary": "E2 on arrival; fan volts taken."})
        hist = []
        for i in range(10):
            hist += [{"role": "user", "content": f"tech {i}"}, {"role": "assistant", "content": f"gd {i}"}]
        f = finder()
        msgs = gd_prompt.build_input(user_msg="now what", history=hist, category="Refrigerators", model_text="Acme X1",
                                        pages=f._pages, web_sources=[{"url": "https://www.acme.com/m.pdf"}],
                                        searches=[{"tool": "search_pages", "args": '{"words": "E2"}'}], state=st)
        # v4.20.10: [primer, pages read, history..., new message, rest of the job context]
        sys_txt, ctx = msgs[0]["content"], msgs[1]["content"] + "\n\n" + msgs[-1]["content"]
        # system text = the primer + the state-block format, nothing else
        self.assertEqual(sys_txt, gd_prompt.PRIMER + "\n\n" + gd_prompt.STATE_FORMAT)
        self.assertNotIn("RULE 1", sys_txt)
        self.assertIn("<state>", sys_txt)
        # context: pages with doc + page labels (first), then unit, web sources, lookups, state, summary - in that order
        order = ["=== PAGES READ EARLIER IN THIS JOB ===", "[Acme Fridge Service Manual (L1), p.25]", "UNIT (as the tech typed it)",
                 "WEB SOURCES USED EARLIER", "LOOKUPS RUN EARLIER", "CASE STATE SO FAR", "RUNNING SUMMARY"]
        idx = [ctx.index(o) for o in order]
        self.assertEqual(idx, sorted(idx))
        self.assertIn("10.4 V", ctx)
        self.assertIn("E2 on arrival", ctx)
        # the whole conversation, then the new message
        body = msgs[2:-1]
        self.assertEqual(len(body), 2 * 10 + 1)
        self.assertEqual(body[0]["content"], "tech 0")
        self.assertEqual(body[-1], {"role": "user", "content": "now what"})

    def test_no_manual_is_picked_for_grok(self):
        ctx = gd_prompt.context_block(category="Leveling", model_text="?", pages=[], state=gd_state.new_state())
        self.assertNotIn("MANUALS PICKED", ctx)
        self.assertNotIn("none found for this unit", ctx)
        self.assertNotIn("PAGES READ EARLIER", ctx)   # nothing read yet: no empty block


BANNED = [
    ("forced plug line", r"plug/connector seating check|include one plug"),
    ("VERIFY appender", r"def ensure_verify|VERIFY: run the function again"),
    ("Unity selector", r"OneControl / Unity board on this coach|unity_gate\s*=\s*st\.selectbox|UNITY_PATH_RULES|apply_unity_path"),
    ("fixed safety line", r"Safety first: chock the wheels|SAFETY_LINE"),
    ("keyword guards", r"NOT_DONE_RE|PENDING_TEST_WORD_RE|CONDEMN_RE|cap_repeats|structural_reply|condemn_gate|drop_reasks|record_facts"),
    ("shop hint", r"_gd_legacy_hint|SHOP HINT"),
    ("hard-coded pages", r"_PAGES\s*=\s*\(\d"),
]
NEW_CORE = ["gd_pages.py", "gd_state.py", "gd_prompt.py", "gd_turn.py", "gd_story.py"]


class TestCitedTitles(unittest.TestCase):
    def test_stub_doc_title(self):
        f = finder()
        self.assertEqual(f.doc_title("L1"), "Acme Fridge Service Manual")
        self.assertEqual(f.doc_title("X9"), "X9")

    def test_app_records_cited_pages_by_title(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        a = src.index("def _gd_official_reply(")
        body = src[a:src.index("\ndef ", a + 10)]
        self.assertIn("doc_title(c.get('doc_id'))", body)
        self.assertNotIn(".lib.docs", body, "app must use the finder interface, not LibraryPageFinder internals")


class TestNoBannedLeftovers(unittest.TestCase):
    def test_new_core_is_clean(self):
        for f in NEW_CORE:
            src = (ROOT / f).read_text()
            for name, pat in BANNED:
                self.assertIsNone(re.search(pat, src), f"{name} found in {f}")

    def test_gd_path_in_app_is_clean(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        a, b = src.index("def _gd_page_finder("), src.index("# ---------------- END GUIDED FLOW ENGINE")
        gd = src[a:b]
        for name, pat in BANNED:
            self.assertIsNone(re.search(pat, gd), f"{name} found in the app's GD path")
        self.assertIsNone(re.search(r"unity_gate\s*=\s*st\.selectbox", src), "Unity selector still in the app")
        self.assertIn("gd_llm.respond(", gd)        # Grok's own call carries the library tools + built-in web search
        self.assertNotIn("_gd_web_tool()", gd)      # the app-side web search is retired from the GD path
        # the Bay PDF path is gone (cleanup 2026-10-24): the backburnered finder has no caller anywhere in the app
        for name in ("pick_manual", "fetch_part", "entry_pages", "toc_pages"):
            self.assertIsNone(re.search(rf"\b{name}\s*\(", src), f"{name} called from the app")
            self.assertFalse(hasattr(gd_pages.LibraryPageFinder, name), f"{name} is back (v4.20.9 deleted it)")

    def test_core_never_regex_reads_prose(self):
        for f in ("gd_turn.py", "gd_state.py", "gd_story.py"):
            self.assertNotIn("import re", (ROOT / f).read_text(), f"{f} imports re")


class TestStateRoundTrip(unittest.TestCase):
    def test_parse_strip_merge(self):
        reply = "Check the fan at F+ F- [Acme, p.29]\n" + block(
            facts=[{"item": "fan volts", "value": "10.4 V", "quote": "10.4"}], pending_test="fan amps",
            part_working="freezer fan", next_part_to_fetch="", cited=[{"doc_id": "L1", "page": "29"}], summary="s1")
        prose, upd, probs = gd_state.parse(reply)
        self.assertEqual(prose, "Check the fan at F+ F- [Acme, p.29]")
        self.assertEqual(probs, [])
        s = gd_state.merge(gd_state.new_state(), upd)
        s = gd_state.merge(s, {"facts": [{"item": "fan volts", "value": "12.1 V", "quote": "12.1 now"},
                                         {"item": "fan amps", "value": "0.4 A", "quote": ".4"}],
                               "repair": {"done": True, "verified": True, "what": "replaced fan", "quote": "new fan, cools"},
                               "closed": True})
        self.assertEqual([f["value"] for f in s["facts"]], ["12.1 V", "0.4 A"])
        back = gd_state.loads(gd_state.dumps(s))
        self.assertEqual(back, s)

    def test_missing_or_bad_block_changes_nothing(self):
        for reply in ("Just prose, the tech said it is fixed and verified.", "x <state>{not json}</state>",
                      block(closed="yes", nonsense=1)):
            prose, upd, probs = gd_state.parse(reply)
            self.assertEqual(upd, {})
            self.assertTrue(probs)
            self.assertNotIn("<state>", prose)

    def test_fenced_json_inside_block(self):
        prose, upd, _ = gd_state.parse('ok\n<state>```json\n{"closed": true, "summary": "done"}\n```</state>')
        self.assertEqual(upd, {"closed": True, "summary": "done"})

    def test_story_from_state_only(self):
        case = gd_turn.new_case("Refrigerators", "Acme X1", "freezes, E2")
        case["state"] = gd_state.merge(case["state"], {
            "facts": [{"item": "fan volts", "value": "10.4 V", "quote": "10.4"}], "cause": "fan motor [Acme p.29]",
            "repair": {"done": True, "verified": True, "what": "Replaced freezer fan", "quote": "new fan in, cooling"}})
        txt = gd_story.warranty_story(case, [{"role": "user", "content": "freezes, E2"}])
        for want in ("freezes, E2", "fan volts of 10.4 V", "fan motor [Acme p.29]", "I replaced the freezer fan", "verified it was working"):
            self.assertIn(want, txt)


class TestTurnFlowAndRetrieval(unittest.TestCase):
    def test_first_turn_no_pick_grok_searches_and_state_is_stored(self):
        f, store = finder(), {}
        chat = FakeRespond([[("search_pages", {"words": "E2 freezer fan"})], "Did you see it freeze yourself?\n" + block(summary="start", cited=[])])
        r = gd_turn.run_turn("freezes contents, E2", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store=store, log_path="")
        self.assertEqual(f.calls, [])                  # the app's finder picks nothing
        self.assertEqual(r["reply"], "Did you see it freeze yourself?")
        self.assertEqual(r["calls"], 2)
        hits = outputs(chat.seen[1][0])[0]["hits"]
        self.assertEqual(hits[0]["page"], "25")        # the E2 chart page matches best
        self.assertEqual(store["gd_case"]["state"]["summary"], "start")
        self.assertEqual(r["mode"], "no_manual")       # searched, nothing opened yet

    def test_pages_read_carry_to_later_turns_and_cited_get_titles(self):
        f, store = finder(), {}
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": ["29"]})],
                            "Test the fan at F+ F-\n" + block(cited=[{"doc_id": "L1", "page": "29"}], summary="b")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store=store, log_path="")
        self.assertEqual(r["mode"], "walk")
        self.assertEqual(r["cited"][0]["title"], "Acme Fridge Service Manual")
        self.assertEqual(r["cited"][0]["sheet"], 29)
        self.assertIn("p.29", r["pages_used"][0])
        chat2 = FakeChat(["ok\n" + block(summary="c")])
        r2 = gd_turn.run_turn("10.4 V at the fan", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat2, store=store, log_path="")
        self.assertEqual(r2["calls"], 1)
        self.assertIn("Freezer fan motor test", chat2.seen[0][0][1]["content"])   # page read last turn comes along (the pages item, right after the primer)

    def test_unit_change_clears_pages_read(self):
        f, store = finder(), {}
        gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, store=store, log_path="",
                         respond_fn=FakeRespond([[("read_pages", {"doc_id": "L1", "pages": ["29"]})], "ok\n" + block(summary="a")]))
        chat = FakeChat(["ok\n" + block(summary="b")])
        gd_turn.run_turn("E2", "Refrigerators", "Acme X2", [], finder=f, store=store, chat_fn=chat, log_path="")
        self.assertNotIn("Freezer fan motor test", chat.seen[0][0][-2]["content"])

    def test_no_library_hits_and_no_web(self):
        f, store = StubPageFinder(), {}
        chat = FakeChat(["I don't know.\n" + block(web_lookup="Brinkley Z3100 front jack bracket", summary="b")])
        r = gd_turn.run_turn("front jack", "Leveling", "Brinkley Model Z", [], finder=f, chat_fn=chat, store=store, log_path="")
        self.assertEqual(r["mode"], "no_manual")
        self.assertEqual(r["calls"], 1)   # the web_lookup field is a record; the app runs no search for it

    def test_reply_is_returned_unchanged(self):
        f, store = finder(), {}
        text = "Replace the control board [Acme, p.31]. Then run it and tell me what it does."
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=f, store=store, log_path="",
                             chat_fn=FakeChat([text + "\n" + block(summary="s")]))
        self.assertEqual(r["reply"], text)

    def test_closed_comes_from_state_only(self):
        f, store = finder(), {}
        r = gd_turn.run_turn("it works now after I re-aimed the sensor", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat(["Run it once more to confirm.\n" + block(summary="s")]), log_path="")
        self.assertNotEqual(r["mode"], "closed")  # the code does not read 'it works now'
        r = gd_turn.run_turn("yes it cools", "Refrigerators", "Acme X1", [], finder=f, store=store, log_path="",
                             chat_fn=FakeChat(["Job closed.\n" + block(closed=True, repair={"done": True, "verified": True,
                                                                                           "what": "re-aimed sensor", "quote": "yes it cools"}, summary="s")]))
        self.assertEqual(r["mode"], "closed")


class TestPageBudget(unittest.TestCase):
    """The old 8-page / 40k-char cap (R6) is gone; v4.20.9 deleted apply_budget (no caller left)."""

    def test_budget_helper_is_deleted(self):
        self.assertFalse(hasattr(gd_pages, "apply_budget"))

    def test_turn_sends_every_page_read(self):
        big = StubPageFinder(manuals=MAN, pages=[page(sheet=i, kind="entry" if i < 3 else "support", text="y" * 12000) for i in range(1, 12)])
        # one read opens up to gd_tools.READ_MAX_PAGES (10); Grok asks for the 11th in a second read
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "sheets": list(range(1, 12))})],
                            [("read_pages", {"doc_id": "L1", "sheets": [11]})], "ok\n" + block(summary="s")])
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=big, respond_fn=chat, store={}, log_path="")
        self.assertEqual(len(r["pages_used"]), 11)
        self.assertEqual(r["not_shown"], [])
        first = outputs(chat.seen[1][0])[0]
        self.assertEqual(len(first["pages"]), 10)
        self.assertEqual(first["not_opened_yet"], ["11"])
        self.assertEqual(len(outputs(chat.seen[2][0])[1]["pages"]), 1)   # 11 pages is well under MAX_PAGES_READ_PER_TURN (30)


INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
APP_DB = os.environ.get("TT_TEST_APP_DB", "/workspace/techtrack-fresh/migration-test/fresh-start.db")


@unittest.skipUnless(os.path.exists(os.path.join(INDEX, "index.sqlite")) and os.path.exists(APP_DB), "811-doc index / app DB not on this box")
class TestRealLibraryWiring(unittest.TestCase):
    """The shipped page-finder index (built from the 811-doc app library) through the adapter, keyword half only so
    the test needs no model download. Wiring, not search quality (the picker sweep measures that)."""

    @classmethod
    def setUpClass(cls):
        cls.f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)

    # v4.20.9: the old picker (pick_manual / fetch_part / toc_pages / apply_budget) is deleted. The wiring is checked
    # through the tools Grok uses: Grok names the maker, find_documents lists that maker's manuals for the unit.
    def tools(self, f=None):
        import gd_tools
        return gd_tools.LibraryTools.for_finder(f or self.f)

    def docs(self, unit, model, words, brand=None, f=None):
        args = {"model": model, "unit_type": unit, "words": words}
        if brand:
            args["brand"] = brand
        return json.loads(self.tools(f).call("find_documents", args)[0]).get("documents", [])

    def check(self, cat, model, complaint, brand, part):
        docs = self.docs(cat, model, complaint, brand=brand)
        self.assertTrue(docs, model)
        self.assertEqual(docs[0]["brand"].lower(), brand.lower())
        self.assertEqual(docs[0]["unit_type"], cat)
        hits = json.loads(self.tools().call("search_pages", {"words": part, "doc_ids": [d["doc_id"] for d in docs]})[0])["hits"]
        self.assertTrue(hits, part)
        out, pages, err = self.tools().call("read_pages", {"doc_id": hits[0]["doc_id"], "sheets": [hits[0]["sheet"]]})
        self.assertFalse(err)
        self.assertTrue(pages and all(x.text and x.page for x in pages))
        return docs

    def test_furrion_fcr10(self):
        self.check("Refrigerators", "FCR10DCGFA", "freezes contents, E2 blinking", "Furrion", "freezer fan motor")

    def test_suburban_water_heater(self):
        self.check("Water Heaters", "SW6DE water heater", "gas clicks but never lights", "Suburban", "gas valve")

    def test_suburban_furnace_hyphen_case(self):
        docs = self.check("Furnaces", "NT-20SEQT furnace", "furnace won't heat", "Suburban", "thermostat")
        self.assertEqual(docs[0]["doc_id"], "L120")
        self.assertIn("contents_pages", self.tools().table_of_contents("L120"))

    def test_brand_known_only_from_data(self):
        docs = self.docs("Leveling", "DeWald 140-1179", "jacks won't extend")
        self.assertTrue(docs)
        self.assertEqual(docs[0]["brand"].lower(), "dewald")

    def test_model_tag_beats_title_preference(self):
        # a model listed by two docs goes to the doc made for that control first
        self.assertEqual(self.docs("Leveling", "Power Gear 140-1230", "not working")[0]["doc_id"], "L370")
        self.assertEqual(sorted(d["doc_id"] for d in self.docs("Leveling", "140-1227", "not working", brand="Power Gear")[:2]),
                         ["L555", "L802"])

    def test_brand_lock_no_other_makers_manual(self):
        # Grok names the maker: a widened search (no Furrion leveling manual) still never lists another maker's manual
        docs = self.docs("Leveling", "FACR13LPSA2-PS", "not cooling", brand="Furrion")
        self.assertEqual({d["brand"] for d in docs}, {"Furrion"})
        self.assertNotIn("Leveling", {d["unit_type"] for d in docs})

    def test_category_name_never_names_the_maker(self):
        docs = self.docs("electronics-onecontrol-tpms-cameras", "FOS7HTASM", "no picture", brand="Furrion")
        self.assertTrue(docs)
        self.assertEqual({d["brand"] for d in docs}, {"Furrion"})

    def test_whole_unit_maker_owner_manual(self):
        docs = self.docs("Air Conditioning", "Model Z", "AC not cooling", brand="Brinkley")
        self.assertTrue(docs)
        self.assertEqual({d["brand"] for d in docs}, {"Brinkley"})

    def test_app_library_changes_reach_the_finder_without_restart(self):
        import shutil, sqlite3, tempfile
        from pagefinder import search as pf
        d = tempfile.mkdtemp()
        db = os.path.join(d, "app.db")
        shutil.copy(APP_DB, db)
        saved = pf._L
        try:
            f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=db)
            self.assertEqual(self.docs("Leveling", "Power Gear 140-1230", "x", f=f)[0]["doc_id"], "L370")
            c = sqlite3.connect(db)
            c.execute("delete from doc_chunks where document_id=370"); c.execute("delete from documents where id=370"); c.commit(); c.close()
            self.assertNotIn("L370", [x["doc_id"] for x in self.docs("Leveling", "Power Gear 140-1230", "x", f=f)])
        finally:
            pf._L = saved

    def test_doc_title_for_source_lines(self):
        # cited doc ids become library titles for the warranty story / source ledger (keyed by title)
        self.assertEqual(self.f.doc_title("L370"), self.f.lib.docs["L370"]["title"])
        self.assertEqual(self.f.doc_title("no-such-doc"), "no-such-doc")

    def test_one_library_and_model_per_process_across_reruns(self):
        # the app builds a finder on every script rerun; the Library (and its model/vectors) must be reused, not rebuilt
        from pagefinder import search as pf
        saved = pf._L
        try:
            a = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)
            b = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)
            self.assertIs(a.lib, b.lib)
            self.assertIs(pf.shared_base_vectors(INDEX), pf.shared_base_vectors(INDEX))
            self.assertFalse(pf.shared_base_vectors(INDEX)[0].flags.writeable)
        finally:
            pf._L = saved

    def test_model_that_cannot_load_falls_back_to_whole_words_and_retries_later(self):
        from unittest import mock
        from pagefinder import search as pf
        saved_l, saved_fail, saved_models, saved_meaning = pf._L, dict(pf._MODEL_FAIL), dict(pf._MODELS), pf.meaning
        saved_on = pf.MEANING_ON
        calls = []
        try:
            pf.MEANING_ON = True
            pf._MODELS.clear(); pf._MODEL_FAIL.clear()
            lib = pf.Library(os.path.join(INDEX, "index.sqlite"), INDEX, app_db=APP_DB)
            def boom(*a, **k):
                calls.append(1); raise OSError("no network")
            with mock.patch.object(pf, "embedding_model", boom):
                keys = [("L370", 1)]
                out = _REAL_MEANING(lib, "jacks will not extend", keys)
                self.assertEqual(out, {("L370", 1): 0.0})
                self.assertIn("no network", lib.meaning_error)
                _REAL_MEANING(lib, "again", keys)
                self.assertEqual(len(calls), 1, "a failed model load is not retried on every click")
        finally:
            pf._L = saved_l; pf._MODEL_FAIL.clear(); pf._MODEL_FAIL.update(saved_fail)
            pf._MODELS.clear(); pf._MODELS.update(saved_models); pf.meaning = saved_meaning; pf.MEANING_ON = saved_on

    def test_meaning_off_never_loads_the_model(self):
        from unittest import mock
        from pagefinder import search as pf
        saved_on = pf.MEANING_ON
        try:
            pf.MEANING_ON = False
            lib = pf.Library(os.path.join(INDEX, "index.sqlite"), INDEX, app_db=APP_DB)
            with mock.patch.object(pf, "shared_embedding_model", side_effect=AssertionError("model loaded")), \
                 mock.patch.object(pf, "shared_base_vectors", side_effect=AssertionError("vectors loaded")):
                self.assertEqual(_REAL_MEANING(lib, "q", [("L370", 1)]), {("L370", 1): 0.0})
                import gd_tools
                self.assertTrue(gd_tools.LibraryTools(lib).search_pages("jacks will not extend", brand="Power Gear")["hits"])
        finally:
            pf.MEANING_ON = saved_on

    def test_app_does_not_read_the_meaning_switch_from_secrets(self):
        # v4.20.8: default is off in code; an old Streamlit secret must not turn it back on.
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertNotIn('_secret("TT_PAGEFINDER_MEANING")', src)
        self.assertNotIn('_secret(\'TT_PAGEFINDER_MEANING\')', src)

    def test_added_docs_are_embedded_in_small_batches(self):
        from pagefinder import search as pf
        self.assertLessEqual(pf.EMBED_BATCH, 4)
        self.assertIn("batch_size=EMBED_BATCH", (ROOT / "pagefinder" / "search.py").read_text())

    def test_full_turn_on_real_library(self):
        chat = FakeRespond([[("find_documents", {"brand": "Suburban", "model": "SW6DE", "unit_type": "Water Heaters"})],
                            [("search_pages", {"words": "gas valve", "brand": "Suburban", "unit_type": "Water Heaters"})],
                            "Did you see it happen?\n" + block(summary="s")])
        r = gd_turn.run_turn("gas clicks but never lights", "Water Heaters", "Suburban SW6DE water heater", [], finder=self.f,
                             respond_fn=chat, store={}, log_path="")
        docs = outputs(chat.seen[1][0])[0]["documents"]
        self.assertTrue(docs and all(d["brand"] == "Suburban" for d in docs))
        hits = outputs(chat.seen[2][0])[1]["hits"]
        self.assertTrue(hits and all(h["brand"] == "Suburban" for h in hits))
        self.assertEqual(r["calls"], 3)


if __name__ == "__main__":
    unittest.main()


class TestGrokWrittenStory(unittest.TestCase):
    def test_story_field_is_stored_and_returned(self):
        case = gd_turn.new_case("Refrigerators", "Acme X1", "freezes, E2")
        case["state"] = gd_state.merge(case["state"], {"story": "Complaint: ... Cause: ... Correction: ...",
                                                       "repair": {"done": True, "verified": True, "what": "x", "quote": "y"}})
        # v4.20.9: the state block has no story field; parse drops one Grok still sends
        self.assertNotIn("story", gd_state.parse('x <state>{"story": "Complaint: ..."}</state>')[1])
        # GD-4 (11/24): the story comes from the Write warranty story button, built from the whole chat, not GD's text
        self.assertNotEqual(gd_story.warranty_story(case, []), "Complaint: ... Cause: ... Correction: ...")
