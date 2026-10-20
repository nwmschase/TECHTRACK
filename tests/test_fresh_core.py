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
import gd_prompt  # noqa: E402
import gd_state  # noqa: E402
import gd_story  # noqa: E402
import gd_turn  # noqa: E402
from gd_pages import Page, StubPageFinder  # noqa: E402

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


class TestPromptAssembly(unittest.TestCase):
    def test_contents_and_order(self):
        st = gd_state.merge(gd_state.new_state(), {"facts": [{"item": "fan volts", "value": "10.4 V", "quote": "10.4 at the fan"}],
                                                   "summary": "E2 on arrival; fan volts taken."})
        hist = []
        for i in range(10):
            hist += [{"role": "user", "content": f"tech {i}"}, {"role": "assistant", "content": f"gd {i}"}]
        f = finder()
        picked = f.pick_manual("Refrigerators", "Acme X1", "freezes")
        msgs = gd_prompt.build_messages(user_msg="now what", history=hist, category="Refrigerators", model_text="Acme X1",
                                        picked=picked, toc=f.toc_pages(picked), pages=picked.pages,
                                        not_shown=[page(sheet=40)], state=st)
        sys_txt, ctx = msgs[0]["content"], msgs[1]["content"]
        self.assertIn("RULE 1 - Library docs first, relevant pages only.", sys_txt)
        self.assertIn("RULE 2 - Verify the complaint with one quick question at the start.", sys_txt)
        for g in ("Don't re-ask a reading", "doc and page on every step", "phone number printed in the manual",
                  "Spell out physical steps", "adjustment, calibration, realign or reset"):
            self.assertIn(g, sys_txt)
        self.assertIn("<state>", sys_txt)
        # context: unit, manual, toc, pages with doc + page labels, not-shown list, state, summary - in that order
        order = ["UNIT (as the tech typed it)", "MANUALS PICKED", "=== TABLE OF CONTENTS ===", "=== SELECTED PAGES ===",
                 "[Acme Fridge Service Manual (L1), p.25]", "PAGES FOUND BUT NOT SHOWN", "CASE STATE SO FAR", "RUNNING SUMMARY"]
        idx = [ctx.index(o) for o in order]
        self.assertEqual(idx, sorted(idx))
        self.assertIn("10.4 V", ctx)
        self.assertIn("E2 on arrival", ctx)
        # last N exchanges only, then the new message
        body = msgs[2:]
        self.assertEqual(len(body), 2 * gd_prompt.HISTORY_TURNS + 1)
        self.assertEqual(body[0]["content"], "tech 4")
        self.assertEqual(body[-1], {"role": "user", "content": "now what"})

    def test_no_manual_is_said_plainly(self):
        ctx = gd_prompt.context_block(category="Leveling", model_text="?", picked=gd_pages.Picked(), toc=[], pages=[],
                                      not_shown=[], state=gd_state.new_state())
        self.assertIn("none found for this unit", ctx)


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
        self.assertNotIn("ask_techtrack_reply", gd, "GD must not fall back to the keyword coach")
        self.assertIsNone(re.search(r"unity_gate\s*=\s*st\.selectbox", src), "Unity selector still in the app")
        self.assertFalse((ROOT / "gd_official.py").exists())

    def test_core_never_regex_reads_prose(self):
        for f in ("gd_turn.py", "gd_state.py", "gd_story.py"):
            self.assertNotIn("import re", (ROOT / f).read_text(), f"{f} imports re")


class TestStateRoundTrip(unittest.TestCase):
    def test_parse_strip_merge(self):
        reply = "Check the fan at F+ F- [Acme, p.29]\n" + block(
            complaint_verified="yes", complaint_quote="yep, E2 and frozen",
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
        self.assertEqual(s["complaint_verified"], "yes")
        back = gd_state.loads(gd_state.dumps(s))
        self.assertEqual(back, s)

    def test_missing_or_bad_block_changes_nothing(self):
        for reply in ("Just prose, the tech said it is fixed and verified.", "x <state>{not json}</state>",
                      block(complaint_verified="maybe", closed="yes", nonsense=1)):
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
            "complaint_verified": "no", "complaint_actual": "not cooling at all", "complaint_quote": "no, it's actually warm",
            "facts": [{"item": "fan volts", "value": "10.4 V", "quote": "10.4"}], "cause": "fan motor [Acme p.29]",
            "repair": {"done": True, "verified": True, "what": "Replaced freezer fan", "quote": "new fan in, cooling"}})
        txt = gd_story.warranty_story(case, [{"role": "user", "content": "freezes, E2"}])
        for want in ("freezes, E2", "not cooling at all", "fan volts: 10.4 V", "fan motor [Acme p.29]", "Replaced freezer fan", "verified working"):
            self.assertIn(want, txt)


class TestTurnFlowAndRetrieval(unittest.TestCase):
    def test_first_turn_picks_pages_and_stores_state(self):
        f, store = finder(), {}
        chat = FakeChat(["Did you see it freeze yourself?\n" + block(complaint_verified="not_asked", summary="start", cited=[])])
        r = gd_turn.run_turn("freezes contents, E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store)
        self.assertEqual(f.calls[0], ("pick_manual", "Refrigerators", "Acme X1", "freezes contents, E2", None))
        self.assertEqual(r["reply"], "Did you see it freeze yourself?")
        self.assertEqual(r["mode"], "walk")
        self.assertEqual(chat.seen[0][2], gd_turn.FIRST_EFFORT)
        self.assertIn("p.25", r["pages_used"][0])
        self.assertEqual(store["gd_case"]["state"]["summary"], "start")

    def test_part_request_fetches_pages_and_redoes_once(self):
        f, store = finder(), {}
        chat = FakeChat([block(next_part_to_fetch="freezer fan motor", summary="a"),
                         "Test the fan at F+ F- [Acme, p.29]\n" + block(next_part_to_fetch="freezer fan motor", summary="b")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store)
        self.assertIn(("fetch_part", "freezer fan motor"), f.calls)
        self.assertEqual(r["calls"], 2)
        second_ctx = chat.seen[1][0][1]["content"]
        self.assertIn("Freezer fan motor test", second_ctx)
        self.assertIn("p.29", r["pages_used"][0])  # newest part pages first
        # next turn: same part is cached, no refetch, one call
        chat2 = FakeChat(["ok\n" + block(summary="c")])
        r2 = gd_turn.run_turn("10.4 V at the fan", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat2, store=store)
        self.assertEqual(r2["calls"], 1)
        self.assertEqual([c for c in f.calls if c[0] == "fetch_part"], [("fetch_part", "freezer fan motor")])

    def test_fault_code_in_state_repicks_pages_with_code(self):
        f, store = finder(), {}
        gd_turn.run_turn("not cooling", "Refrigerators", "Acme X1", [], finder=f, store=store,
                         chat_fn=FakeChat(["?\n" + block(fault_code="E2", summary="x")]))
        gd_turn.run_turn("it shows E2", "Refrigerators", "Acme X1", [], finder=f, store=store,
                         chat_fn=FakeChat(["ok\n" + block(summary="y")]))
        picks = [c for c in f.calls if c[0] == "pick_manual"]
        self.assertEqual([p[4] for p in picks], [None, "E2"])

    def test_no_manual_and_web_not_wired(self):
        f, store = StubPageFinder(), {}
        chat = FakeChat([block(web_lookup="Brinkley Z3100 front jack bracket", summary="a"), "I don't know.\n" + block(summary="b")])
        r = gd_turn.run_turn("front jack", "Leveling", "Brinkley Model Z", [], finder=f, chat_fn=chat, store=store)
        self.assertEqual(r["mode"], "no_manual")
        self.assertEqual(r["calls"], 1)  # nothing new arrived, so no redo
        self.assertIn("none found for this unit", chat.seen[0][0][1]["content"])

    def test_reply_is_returned_unchanged(self):
        f, store = finder(), {}
        text = "Replace the control board [Acme, p.31]. Then run it and tell me what it does."
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat([text + "\n" + block(summary="s")]))
        self.assertEqual(r["reply"], text)

    def test_closed_comes_from_state_only(self):
        f, store = finder(), {}
        r = gd_turn.run_turn("it works now after I re-aimed the sensor", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat(["Run it once more to confirm.\n" + block(summary="s")]))
        self.assertEqual(r["mode"], "walk")  # the code does not read 'it works now'
        r = gd_turn.run_turn("yes it cools", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat(["Job closed.\n" + block(closed=True, repair={"done": True, "verified": True,
                                                                                           "what": "re-aimed sensor", "quote": "yes it cools"}, summary="s")]))
        self.assertEqual(r["mode"], "closed")


class TestPageBudget(unittest.TestCase):
    def test_caps_and_lists_what_was_not_shown(self):
        pages = [page(sheet=i, text="x" * 9000) for i in range(1, 8)] + [page(sheet=1, text="dup")]
        kept, not_shown = gd_pages.apply_budget(pages, max_pages=8, max_chars=40_000)
        self.assertEqual([p.sheet for p in kept], [1, 2, 3, 4])
        self.assertEqual([p.sheet for p in not_shown], [5, 6, 7])
        self.assertLessEqual(sum(len(p.text) for p in kept), 40_000)

    def test_turn_respects_budget(self):
        big = StubPageFinder(manuals=MAN, pages=[page(sheet=i, kind="entry" if i < 3 else "support", text="y" * 12000) for i in range(1, 12)])
        chat = FakeChat(["ok\n" + block(summary="s")])
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=big, chat_fn=chat, store={})
        self.assertEqual(len(r["pages_used"]), 3)
        self.assertEqual(len(r["not_shown"]), 8)
        self.assertLess(r["context_chars"], gd_pages.PAGE_BUDGET_CHARS + 10_000)
        self.assertIn("PAGES FOUND BUT NOT SHOWN", chat.seen[0][0][1]["content"])


INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))
APP_DB = os.environ.get("TT_TEST_APP_DB", "/workspace/techtrack-fresh/migration-test/fresh-start.db")


@unittest.skipUnless(os.path.exists(os.path.join(INDEX, "index.sqlite")) and os.path.exists(APP_DB), "811-doc index / app DB not on this box")
class TestRealLibraryWiring(unittest.TestCase):
    """The shipped page-finder index (built from the 811-doc app library) through the adapter, keyword half only so
    the test needs no model download. Wiring + brand lock, not search quality (the picker sweep measures that)."""

    @classmethod
    def setUpClass(cls):
        cls.f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=APP_DB)

    def check(self, cat, model, complaint, brand, part):
        p = self.f.pick_manual(cat, model, complaint)
        self.assertTrue(p.manuals, model)
        self.assertEqual(p.manuals[0]["brand"].lower(), brand.lower())
        self.assertEqual(p.manuals[0]["unit_type"], cat)
        self.assertTrue(p.entry and all(x.kind == "entry" for x in p.entry))
        self.assertTrue(all(x.text and x.page for x in p.pages))
        parts = self.f.fetch_part(part, p)
        docs = self.f.lib.docs
        picked_brands = {m["brand"].lower() for m in p.manuals}
        self.assertTrue(all(docs[x.doc_id]["brand"].lower() in picked_brands for x in parts), "R4: another maker's page")
        kept, _ = gd_pages.apply_budget(p.pages + parts)
        self.assertLessEqual(sum(len(x.text) for x in kept), gd_pages.PAGE_BUDGET_CHARS)
        return p

    def test_furrion_fcr10(self):
        self.check("Refrigerators", "Furrion FCR10DCGFA", "freezes contents, E2 blinking", "Furrion", "freezer fan motor")

    def test_suburban_water_heater(self):
        self.check("Water Heaters", "Suburban SW6DE water heater", "gas clicks but never lights", "Suburban", "gas valve")

    def test_suburban_furnace_hyphen_case(self):
        p = self.check("Furnaces", "Suburban NT-20SEQT furnace", "furnace won't heat", "Suburban", "thermostat")
        self.assertTrue(self.f.toc_pages(p) is not None)

    def test_brand_known_only_from_data(self):
        p = self.f.pick_manual("Leveling", "DeWald 140-1179", "jacks won't extend")
        self.assertTrue(p.manuals)
        self.assertEqual(p.manuals[0]["brand"].lower(), "dewald")

    def test_model_tag_beats_title_preference(self):
        # 3f: a model listed by two docs goes to the doc made for that control first; the wider tip sheet comes second
        for model, own in (("Power Gear 140-1230", "L370"), ("Power Gear 140-1227", "L555")):
            p = self.f.pick_manual("Leveling", model, "not working")
            self.assertEqual(p.manuals[0]["doc_id"], own, model)

    def test_brand_lock_no_other_makers_manual(self):
        # R4: a maker with no manual in the asked category gets none (never another maker's manual)
        p = self.f.pick_manual("Leveling", "Furrion FACR13LPSA2-PS", "not cooling")
        self.assertEqual(p.manuals, [])

    def test_category_name_never_names_the_maker(self):
        # 'electronics-onecontrol-...' must not make the maker Lippert (product-line words come only from the typed unit)
        p = self.f.pick_manual("electronics-onecontrol-tpms-cameras", "Power Gear 140-1224", "not working")
        self.assertTrue(p.manuals)
        self.assertEqual(p.manuals[0]["brand"], "Power Gear")

    def test_whole_unit_maker_owner_manual(self):
        p = self.f.pick_manual("Air Conditioning", "Brinkley Model Z", "AC not cooling")
        self.assertTrue(p.manuals)
        self.assertEqual({m["brand"] for m in p.manuals}, {"Brinkley"})

    def test_app_library_changes_reach_the_finder_without_restart(self):
        import shutil, sqlite3, tempfile
        from pagefinder import search as pf
        d = tempfile.mkdtemp()
        db = os.path.join(d, "app.db")
        shutil.copy(APP_DB, db)
        saved = pf._L
        try:
            f = gd_pages.LibraryPageFinder(INDEX, meaning=False, app_db=db)
            self.assertEqual(f.pick_manual("Leveling", "Power Gear 140-1230", "x").manuals[0]["doc_id"], "L370")
            c = sqlite3.connect(db)
            c.execute("delete from doc_chunks where document_id=370"); c.execute("delete from documents where id=370"); c.commit(); c.close()
            ids = [m["doc_id"] for m in f.pick_manual("Leveling", "Power Gear 140-1230", "x").manuals]
            self.assertNotIn("L370", ids)
        finally:
            pf._L = saved

    def test_doc_title_for_source_lines(self):
        # cited doc ids become library titles for the warranty story / source ledger (keyed by title)
        self.assertEqual(self.f.doc_title("L370"), self.f.lib.docs["L370"]["title"])
        self.assertEqual(self.f.doc_title("no-such-doc"), "no-such-doc")

    def test_full_turn_on_real_library(self):
        chat = FakeChat(["Did you see it happen?\n" + block(summary="s")])
        r = gd_turn.run_turn("gas clicks but never lights", "Water Heaters", "Suburban SW6DE water heater", [], finder=self.f,
                             chat_fn=chat, store={})
        self.assertEqual(r["mode"], "walk")
        self.assertTrue(r["pages_used"])
        self.assertLessEqual(len(r["pages_used"]), gd_pages.PAGE_BUDGET_PAGES)


if __name__ == "__main__":
    unittest.main()
