"""Chase 2026-11-25 (t1596/t1600): the manual pages GD cites become a compact clickable row under the reply:
📄 Open PDF (short-lived presigned R2 link, inline, #page=<PDF sheet>) and 🖼 Show page (drawn only when tapped).
Nothing when nothing was cited; at most 4 rows (Aug 20: no always-on source forest). Offline: no paid Grok, no R2."""
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_page_links as gl  # noqa: E402

ROWS = [{"pdf_sheet": 1, "printed_page": ""}, {"pdf_sheet": 2, "printed_page": "i"},
        {"pdf_sheet": 21, "printed_page": "19"}, {"pdf_sheet": 22, "printed_page": "20"}]


class FakeS3:
    def __init__(self, keys=()):
        self.keys, self.signed = set(keys), []

    def generate_presigned_url(self, op, Params, ExpiresIn):
        self.signed.append((op, dict(Params), ExpiresIn))
        return f"https://r2.example/{Params['Bucket']}/{Params['Key']}?X-Amz-Signature=fake"

    def head_object(self, Bucket, Key):
        if Key not in self.keys:
            raise RuntimeError("404")
        return {"ContentLength": 1}


class TestSheetLookup(unittest.TestCase):
    def test_printed_label_maps_to_pdf_sheet(self):
        self.assertEqual(gl.sheet_for("19", ROWS), 21)
        self.assertEqual(gl.sheet_for("i", ROWS), 2)
        self.assertEqual(gl.sheet_for("sheet 7", ROWS), 7)      # gd_turn labels an unprinted page "sheet N"
        self.assertEqual(gl.sheet_for("1", ROWS), 1)            # no printed page: the label is the sheet
        self.assertIsNone(gl.sheet_for("99", ROWS))
        self.assertIsNone(gl.sheet_for("", ROWS))

    def test_opened_page_keeps_its_sheet_and_unopened_page_is_looked_up(self):
        calls = []
        def pages_fn(d):
            calls.append(d)
            return ROWS
        refs = gl.page_refs([{"doc_id": "L5", "page": "19", "title": "Furrion FCR16 Service Manual", "sheet": 21},
                             {"doc_id": "L5", "page": "20"}],
                            pages_fn=pages_fn, file_fn=lambda d: "documents/5_x.pdf", title_fn=lambda d: "Furrion FCR16 Service Manual")
        self.assertEqual([r["sheet"] for r in refs], [21, 22])
        self.assertEqual(calls, ["L5"])                          # only the page Grok did not open is looked up
        self.assertEqual(refs[0]["label"], "Furrion FCR16 Service Manual · p.19")
        self.assertEqual(refs[1]["title"], "Furrion FCR16 Service Manual")
        self.assertEqual(refs[0]["file_path"], "documents/5_x.pdf")

    def test_unknown_label_has_no_sheet(self):
        refs = gl.page_refs([{"doc_id": "L5", "page": "404"}], pages_fn=lambda d: ROWS, file_fn=lambda d: "k")
        self.assertIsNone(refs[0]["sheet"])
        self.assertEqual(refs[0]["page"], "404")


class TestRows(unittest.TestCase):
    def test_nothing_cited_no_rows(self):
        self.assertEqual(gl.page_refs([]), [])
        self.assertEqual(gl.page_refs(None), [])
        self.assertEqual(gl.page_refs([{"doc_id": "", "page": "3"}, "junk"]), [])

    def test_cap_and_dedupe(self):
        cited = [{"doc_id": "L1", "page": str(n), "sheet": n} for n in (3, 3, 4, 5, 6, 7, 8)]
        refs = gl.page_refs(cited, file_fn=lambda d: "k")
        self.assertEqual(len(refs), gl.MAX_PAGE_LINKS)
        self.assertEqual(gl.MAX_PAGE_LINKS, 4)
        self.assertEqual([r["sheet"] for r in refs], [3, 4, 5, 6])

    def test_web_source_uses_its_url(self):
        url = "https://www.furrion.com/docs/ccd-0008122.pdf"
        refs = gl.page_refs([{"doc_id": url, "page": "3"}, {"doc_id": url, "page": "4"}])
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["kind"], "web")
        self.assertEqual(refs[0]["url"], url)
        self.assertEqual(refs[0]["label"], "furrion.com · p.3")

    def test_long_titles_are_shortened(self):
        refs = gl.page_refs([{"doc_id": "L1", "page": "2", "sheet": 2, "title": "X" * 80}])
        self.assertLessEqual(len(refs[0]["label"].split(" · ")[0]), gl.TITLE_CHARS)


class TestLinks(unittest.TestCase):
    def test_presigned_inline_link_at_the_sheet(self):
        s3 = FakeS3()
        url = gl.pdf_link(s3, "techtrack-files", "documents/5_x.pdf", 21)
        self.assertTrue(url.endswith("#page=21"))
        op, params, exp = s3.signed[0]
        self.assertEqual(op, "get_object")
        self.assertEqual(params["ResponseContentDisposition"], "inline")
        self.assertEqual(params["ResponseContentType"], "application/pdf")
        self.assertEqual(params["Key"], "documents/5_x.pdf")
        self.assertLessEqual(exp, 3600)

    def test_no_sheet_no_fragment_and_missing_inputs(self):
        self.assertNotIn("#page", gl.pdf_link(FakeS3(), "b", "k", None))
        self.assertEqual(gl.pdf_link(None, "b", "k", 3), "")
        self.assertEqual(gl.pdf_link(FakeS3(), "b", "", 3), "")

    def test_object_exists(self):
        s3 = FakeS3(keys={"documents/a.pdf"})
        self.assertTrue(gl.object_exists(s3, "b", "documents/a.pdf"))
        self.assertFalse(gl.object_exists(s3, "b", "documents/missing.pdf"))
        self.assertFalse(gl.object_exists(None, "b", "documents/a.pdf"))

    def test_storage_check_is_remembered_briefly(self):
        gl._EXISTS_CACHE.clear()
        made = []
        def client_fn():
            made.append(1)
            return FakeS3(keys={"documents/a.pdf"})
        self.assertTrue(gl.object_exists_cached(client_fn, "b", "documents/a.pdf", now=1000))
        self.assertTrue(gl.object_exists_cached(client_fn, "b", "documents/a.pdf", now=1300))
        self.assertEqual(len(made), 1)
        self.assertTrue(gl.object_exists_cached(client_fn, "b", "documents/a.pdf", now=1000 + gl.EXISTS_TTL_SEC + 1))
        self.assertEqual(len(made), 2)
        self.assertFalse(gl.object_exists_cached(lambda: None, "b", "documents/x.pdf", now=1))
        self.assertNotIn(("b", "documents/x.pdf"), gl._EXISTS_CACHE)   # no storage client: not remembered


def _slice(src, start, end):
    a = src.index(start)
    return src[a:src.index(end, a + len(start))]


class TestCitedPagesReachHistory(unittest.TestCase):
    """_gd_official_reply keeps the turn's cited list; the history message stores it as page rows."""

    def test_official_reply_keeps_cited_and_refs_are_built(self):
        from test_fresh_core import FakeRespond, block, finder
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        code = _slice(src, "def _gd_official_reply(", "\ndef guided_diagnostics_reply(")
        code += _slice(src, "def _gd_cited_page_refs(", "\ndef _gd_pdf_in_storage(")
        fake_st = types.SimpleNamespace(session_state={"gd_last_cited": [{"doc_id": "OLD", "page": "1"}]})
        stub = finder()
        stub.lib = types.SimpleNamespace(pages=lambda d: ROWS)
        respond = FakeRespond(["Check the fan wiring on page 19. " + block(cited=[{"doc_id": "L1", "page": "19"}])])
        ns = {"st": fake_st, "_gd_official_respond": respond, "_gd_official_chat": None, "_gd_page_finder": lambda: stub,
              "GD_USAGE_LOG": "", "GD_UNAVAILABLE_LINE": "unavailable", "record_cited_pages": lambda line: None,
              "gd_llm": None, "_secret": lambda k: None, "_gd_doc_file_path": lambda d: f"documents/{d}.pdf"}
        exec(compile(code, "rv_slice", "exec"), ns)
        reply = ns["_gd_official_reply"]("fridge fan not running", "Refrigerators", "Acme X1", [], {})
        self.assertIn("page 19", reply)
        # v4.20.7: page 19 was cited but never opened in this job, so it is not kept (no button that leads nowhere)
        self.assertEqual(fake_st.session_state["gd_last_cited"], [])
        refs = ns["_gd_cited_page_refs"]([{"doc_id": "L1", "page": "19"}])
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["sheet"], 21)                       # printed p.19 is PDF sheet 21
        self.assertEqual(refs[0]["file_path"], "documents/L1.pdf")
        self.assertEqual(refs[0]["label"], "Acme Fridge Service Manual · p.19")

    def test_failed_turn_clears_the_previous_turns_pages(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        code = _slice(src, "def _gd_official_reply(", "\ndef guided_diagnostics_reply(")
        fake_st = types.SimpleNamespace(session_state={"gd_last_cited": [{"doc_id": "L1", "page": "1"}]})
        import index_fetch
        def boom():
            raise index_fetch.IndexLoading("loading")
        ns = {"st": fake_st, "_gd_official_respond": None, "_gd_official_chat": None, "_gd_page_finder": boom,
              "GD_USAGE_LOG": "", "GD_UNAVAILABLE_LINE": "x", "record_cited_pages": lambda l: None, "gd_llm": None,
              "_secret": lambda k: None}
        exec(compile(code, "rv_slice", "exec"), ns)
        ns["_gd_official_reply"]("hi", "Refrigerators", "X", [], {})
        self.assertNotIn("gd_last_cited", fake_st.session_state)

    def test_history_message_stores_pages_and_each_reply_draws_its_row(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn('"pages": _gd_cited_page_refs(entry.get("cited")),', src)   # v4.20.6: the send's kept cited pages
        self.assertIn('cited=list(st.session_state.pop("gd_last_cited", None) or [])', src)
        self.assertIn('_render_gd_page_links((m.get("pages") or []) if isinstance(m, dict) else [], f"gd_pages_{index}")', src)
        self.assertIn('"gd_page_links", "gd_picture", "gd_sends")', src)                       # reloaded with the GD stack on a redeploy
        row = _slice(src, "def _render_gd_page_links(", "\ndef clear_ask_source_state(")
        self.assertNotIn("st.expander", row)                          # Aug 20: no dropdowns
        self.assertIn("gd_page_links.pdf_link(get_r2_client(), st.secrets[\"R2_BUCKET_NAME\"], key, sheet)", row)
        self.assertIn('"📄 Open PDF"', row)
        self.assertIn('"🖼 Show page"', row)


def _count_images(node):
    n = 1 if type(node).__name__ == "Image" else 0
    kids = getattr(node, "children", None)
    return n + (sum(_count_images(c) for c in kids.values()) if isinstance(kids, dict) else 0)


class TestAppRow(unittest.TestCase):
    """The tech's view (AppTest, offline, no keys): a reply with a cited page shows its row; the page draws only on tap;
    a reply with no pages shows no row; a PDF not in storage shows a plain note."""

    def setUp(self):
        keys = ("XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
        p = mock.patch.dict(os.environ, {k: v for k, v in os.environ.items() if k not in keys}, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def test_row_and_show_page(self):
        from test_gd_nav_and_send import APP
        from streamlit.testing.v1 import AppTest
        pdf = str(ROOT / "tests" / "fixtures" / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf")
        at = AppTest.from_file(str(APP), default_timeout=90)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        at.radio[0].set_value("💬 Guided Diagnostics").run()
        at.session_state["ask_chat"] = [
            {"role": "user", "content": "toilet leaks at the valve"},
            {"role": "assistant", "content": "See the water valve kit sheet.", "figures": [],
             "pages": [{"kind": "library", "doc_id": "L999998", "title": "Thetford Water Valve Kit 42109", "page": "1",
                        "sheet": 1, "file_path": pdf, "url": "", "label": "Thetford Water Valve Kit 42109 · p.1"},
                       {"kind": "library", "doc_id": "L999997", "title": "Gone Manual", "page": "3", "sheet": 3,
                        "file_path": "documents/not-there.pdf", "url": "", "label": "Gone Manual · p.3"}]},
            {"role": "user", "content": "ok"},
            {"role": "assistant", "content": "Next, check the supply.", "figures": []},
        ]
        at.run()
        self.assertFalse(list(at.exception))
        captions = [c.value for c in at.caption]
        self.assertIn("📖 Thetford Water Valve Kit 42109 · p.1", captions)
        self.assertTrue(any("Gone Manual · p.3" in c and "not in the shop library storage" in c for c in captions))
        show = at.button(key="gd_pages_1_show_0_btn")
        self.assertEqual(show.label, "🖼 Show page")
        n_img = _count_images(at._tree)
        with self.assertRaises(KeyError):
            at.button(key="gd_pages_3_show_0_btn")                  # the reply with no pages has no row
        show.click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.button(key="gd_pages_1_show_0_btn").label, "✖ Hide page")
        self.assertNotIn("Couldn't draw that page here. Use Open PDF.", [c.value for c in at.caption])
        self.assertEqual(_count_images(at._tree), n_img + 1)               # the cited page is drawn only after the tap
        at.button(key="gd_pages_1_show_0_btn").click().run()                # tap again: hidden
        self.assertEqual(_count_images(at._tree), n_img)


if __name__ == "__main__":
    unittest.main()
