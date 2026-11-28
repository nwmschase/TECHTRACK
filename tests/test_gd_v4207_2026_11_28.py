"""v4.20.7 (Chase t1713u, audit 2026-11-28): web gate, photo request opens the manual page, cited = opened pages of this
turn, GD answer temperature 0.7, and the retired picture paths stay gone. No paid calls."""
import inspect
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_llm  # noqa: E402
import gd_picture  # noqa: E402
import gd_turn  # noqa: E402
from gd_pages import Page, StubPageFinder  # noqa: E402
from test_fresh_core import FakeRespond, block, page, MAN  # noqa: E402

PIC = Page(doc_id="L1", title="Acme Fridge Service Manual", page="31", sheet=31, text="Fan motor and harness connector",
           topics="photo / photograph of the actual component: freezer fan motor and harness connector")


def finder(pages=None):
    return StubPageFinder(manuals=MAN, pages=pages if pages is not None else [
        page(sheet=25, kind="entry", text="TROUBLESHOOTING CHART: E2 = freezer fan fault"),
        page(sheet=29, text="Freezer fan motor test: 12 V at F+ F-, 0.3 A draw"), PIC])


def web_names(tools):
    return sorted(t.get("name") or t.get("type") for t in tools if gd_turn.is_web_tool(t))


def turn(script, store=None, msg="E2 on the freezer", **kw):
    chat = FakeRespond(script)
    r = gd_turn.run_turn(msg, "Refrigerators", "Acme X1", [], finder=kw.pop("finder", finder()), respond_fn=chat,
                         store={} if store is None else store, log_path="", web_fetch=lambda u, w: [], **kw)
    return r, chat


class TestWebGate(unittest.TestCase):
    def test_no_web_tools_until_a_library_page_is_opened(self):
        store = {}
        r, chat = turn([[("search_pages", {"words": "E2"})], [("read_pages", {"doc_id": "L1", "pages": ["29"]})],
                        "ok\n" + block(summary="s")], store=store)
        offered = [web_names(tools) for _items, tools, _c in chat.seen]
        self.assertEqual(offered[0], [])
        self.assertEqual(offered[1], [])
        self.assertTrue(offered[2])                         # after the page read
        self.assertTrue(store["gd_case"]["web_gate"]["open"])

    def test_gate_stays_open_for_the_job(self):
        store = {}
        turn([[("read_pages", {"doc_id": "L1", "pages": ["29"]})], "ok\n" + block(summary="s")], store=store)
        _r, chat = turn(["ok\n" + block(summary="s")], store=store, msg="fan has 12 V")
        self.assertTrue(web_names(chat.seen[0][1]))

    def test_empty_library_opens_the_gate(self):
        _r, chat = turn([[("search_pages", {"words": "zzzz qqqq"})], "ok\n" + block(summary="s")], finder=finder([]))
        self.assertTrue(web_names(chat.seen[-1][1]))

    def test_web_document_before_the_library_is_refused(self):
        fetched = []
        chat = FakeRespond([[("open_web_document", {"url": "https://x.example/a.pdf"})], "ok\n" + block(summary="s")])
        gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=finder(), respond_fn=chat, store={}, log_path="",
                         web_fetch=lambda u, w: fetched.append(u) or [])
        self.assertEqual(fetched, [])

    def test_log_only_trigger_is_gone(self):
        self.assertFalse(hasattr(gd_turn, "T_WEB_BEFORE_LIBRARY"))
        self.assertIn(gd_turn.T_WEB_GATE_OPENED, gd_turn.TRIGGERS)


class TestPhotoOpensTheManualFirst(unittest.TestCase):
    def test_picture_request_with_no_page_opened_opens_the_picture_page(self):
        store = {}
        turn([[("find_documents", {"unit_type": "refrigerator"})], "ok\n" + block(summary="s")], store=store)
        r, _chat = turn(["Here is the fan.\n" + block(summary="s")], store=store, msg="send me a photo of the fan motor",
                        picture_request=True)
        self.assertIn(gd_turn.T_APP_PICTURE_PAGE, [t["trigger"] for t in r["triggers"]])
        self.assertIn(("L1", "31"), [(c["doc_id"], c["page"]) for c in r["cited"]])

    def test_detector(self):
        for m in ("can you show me a picture of the controller", "do you have diagrams", "photo of the harness",
                  "what does it look like"):
            self.assertTrue(gd_picture.is_picture_request(m), m)
        for m in ("fan reads 12.4 V", "Not checked yet", "fuse blown and replaced"):
            self.assertFalse(gd_picture.is_picture_request(m), m)


class TestCitedIsThisTurnsOpenedPages(unittest.TestCase):
    def test_unopened_page_is_dropped(self):
        r, _ = turn([[("read_pages", {"doc_id": "L1", "pages": ["29"]})],
                     "ok\n" + block(summary="s", cited=[{"doc_id": "L1", "page": "29"}, {"doc_id": "L1", "page": "25"}])])
        self.assertEqual([(c["doc_id"], c["page"]) for c in r["cited"]], [("L1", "29")])
        self.assertIn(gd_turn.T_CITED_NOT_OPENED, [t["trigger"] for t in r["triggers"]])

    def test_block_without_cited_clears_last_turns_list(self):
        store = {}
        r1, _ = turn([[("read_pages", {"doc_id": "L1", "pages": ["29"]})],
                      "ok\n" + block(summary="s", cited=[{"doc_id": "L1", "page": "29"}])], store=store)
        self.assertTrue(r1["cited"])
        r2, _ = turn(["next step\n" + block(summary="s2")], store=store, msg="12 V there")
        self.assertEqual(r2["cited"], [])
        self.assertEqual(store["gd_case"]["state"]["cited"], [])


class TestTemperature(unittest.TestCase):
    def test_only_the_gd_answer_call_moved(self):
        self.assertEqual(gd_llm.GD_RESPOND_TEMPERATURE, 0.7)
        self.assertEqual(inspect.signature(gd_llm.respond).parameters["temperature"].default, 0.7)
        self.assertEqual(inspect.signature(gd_llm.complete_chat).parameters["temperature"].default, 0.2)
        self.assertIn("temperature=0.0", (ROOT / "gd_step_photo.py").read_text(encoding="utf-8").replace(" ", ""))

    def test_respond_sends_it(self):
        sent = {}

        class Client:
            class responses:
                @staticmethod
                def create(**kw):
                    sent.update(kw)
                    return {"output": [], "usage": {}}

        try:
            gd_llm.respond([{"role": "user", "content": "x"}], [], secret_fn=lambda k, d="": "key" if k == "XAI_API_KEY" else "",
                           client_factory=lambda *a, **k: Client())
        except gd_llm.LLMProviderError:
            pass
        self.assertEqual(sent.get("temperature"), 0.7)


class TestRetiredPicturePaths(unittest.TestCase):
    def test_gone(self):
        import gd_library_coach
        import library_figure_backfill
        import manual_figures
        for mod, name in ((gd_library_coach, "wants_library_page_shown"), (gd_library_coach, "pick_diagram_page_numbers"),
                          (gd_library_coach, "figure_render_honesty_note"), (manual_figures, "tech_asked_for_manual_figure"),
                          (manual_figures, "bundled_thetford_offers"), (library_figure_backfill, "offers_for_turn"),
                          (library_figure_backfill, "select_library_figures"), (gd_picture, "_PAGE_REF")):
            self.assertFalse(hasattr(mod, name), name)

    def test_primer_lines(self):
        p = (ROOT / "gd_primer.md").read_text(encoding="utf-8")
        self.assertNotIn("Web search can also show photos", p)
        self.assertNotIn("Several lookups in one round cost less", p)


if __name__ == "__main__":
    unittest.main()
