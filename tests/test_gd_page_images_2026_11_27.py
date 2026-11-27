"""Page images to Grok, image search on, primer corrected (Chase 2026-11-27, test1 Schwintek: "the library HALF useless
because it thinks its all text"). Offline: scripted fakes, no network, no paid call."""
import base64
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_prompt  # noqa: E402
import gd_tools  # noqa: E402
import gd_turn  # noqa: E402
from gd_pages import Page, StubPageFinder  # noqa: E402
from test_fresh_core import FakeRespond, MAN, block, page  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40


def pic(sheet, text="figure page"):
    p = page(sheet=sheet, text=text)
    p.topics = "diagram / drawing / illustration / picture / pic / image / figure: wiring diagram"
    return p


def finder(n_plain=3, n_pic=2):
    pages = [page(sheet=10 + i, text=f"plain text page {i}") for i in range(n_plain)]
    pages += [pic(20 + i) for i in range(n_pic)]
    return StubPageFinder(manuals=MAN, pages=pages)


def image_msgs(items):
    return [i for i in items if isinstance(i, dict) and i.get("role") == "user" and isinstance(i.get("content"), list)
            and any(c.get("type") == "input_image" for c in i["content"])]


class TestPageImagesReachGrok(unittest.TestCase):
    def run_turn(self, sheets, image_fn, script_tail=None, f=None):
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": [str(s) for s in sheets]})]]
                           + (script_tail or ["ok " + block(summary="s")]))
        calls = []

        def fn(doc_id, sheet):
            calls.append((doc_id, sheet))
            return image_fn(doc_id, sheet)
        r = gd_turn.run_turn("show me the wiring", "Refrigerators", "Acme X1", [], finder=f or finder(), respond_fn=chat,
                             store={}, log_path="", page_image_fn=fn)
        return r, chat, calls

    def test_images_follow_the_tool_results_as_data_urls(self):
        r, chat, calls = self.run_turn([10, 20], lambda d, s: PNG)
        second = chat.seen[1][0]
        msgs = image_msgs(second)
        self.assertEqual(len(msgs), 1)
        # after every function_call_output of that round
        idx_img = second.index(msgs[0])
        idx_out = max(i for i, x in enumerate(second) if isinstance(x, dict) and x.get("type") == "function_call_output")
        self.assertGreater(idx_img, idx_out)
        imgs = [c for c in msgs[0]["content"] if c.get("type") == "input_image"]
        self.assertEqual(len(imgs), 2)
        self.assertTrue(imgs[0]["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(imgs[0]["image_url"].split(",", 1)[1]), PNG)
        # picture-labelled page first
        self.assertEqual(calls[0], ("L1", 20))
        self.assertEqual(r["usage"]["page_images_sent"], 2)
        self.assertEqual(len(r["page_images"]["sent"]), 2)
        self.assertEqual(r["log"]["page_images"]["sent"], r["page_images"]["sent"])

    def test_cap_per_read_and_picture_pages_first(self):
        f = finder(n_plain=6, n_pic=3)
        sheets = [10, 11, 12, 13, 14, 15, 20, 21, 22]
        r, chat, calls = self.run_turn(sheets, lambda d, s: PNG, f=f)
        self.assertEqual(r["usage"]["page_images_sent"], gd_turn.MAX_PAGE_IMAGES_PER_READ)
        self.assertEqual([s for _, s in calls[:3]], [20, 21, 22])
        self.assertEqual(r["usage"]["page_images_skipped"], len(sheets) - gd_turn.MAX_PAGE_IMAGES_PER_READ)

    def test_turn_cap(self):
        f = finder(n_plain=0, n_pic=15)
        reads = [[str(20 + i) for i in range(0, 6)], [str(20 + i) for i in range(6, 12)], [str(20 + i) for i in range(12, 15)]]
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": r})] for r in reads] + ["ok " + block(summary="s")])
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store={}, log_path="",
                             page_image_fn=lambda d, s: PNG)
        self.assertEqual(r["usage"]["page_images_sent"], gd_turn.MAX_PAGE_IMAGES_PER_TURN)
        self.assertEqual(r["usage"]["page_images_skipped"], 3)
        self.assertEqual(image_msgs(chat.seen[3][0]).__len__(), 2)   # third read got no image message

    def test_failed_drawing_is_logged_and_text_still_goes(self):
        r, chat, calls = self.run_turn([10, 20], lambda d, s: None)
        self.assertEqual(image_msgs(chat.seen[1][0]), [])
        self.assertEqual(r["usage"]["page_images_failed"], 2)
        self.assertTrue(any("page images not drawn" in p for p in r["problems"]))

    def test_no_image_fn_sends_no_images(self):
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": ["20"]})], "ok " + block(summary="s")])
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=finder(), respond_fn=chat, store={}, log_path="")
        self.assertEqual(image_msgs(chat.seen[1][0]), [])
        self.assertEqual(r["usage"]["page_images_sent"], 0)

    def test_search_pages_gets_no_images(self):
        chat = FakeRespond([[("search_pages", {"words": "wiring"})], "ok " + block(summary="s")])
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=finder(), respond_fn=chat, store={}, log_path="",
                             page_image_fn=lambda d, s: PNG)
        self.assertEqual(image_msgs(chat.seen[1][0]), [])

    def test_jpeg_mime(self):
        msg, sent, failed = gd_turn.page_image_message([pic(20)], lambda d, s: b"\xff\xd8\xff" + b"y" * 20)
        img = [c for c in msg["content"] if c.get("type") == "input_image"][0]
        self.assertTrue(img["image_url"].startswith("data:image/jpeg;base64,"))

    def test_web_pages_are_not_drawn(self):
        w = Page(doc_id="https://x.com/a.pdf", title="a", page="1", sheet=1, text="t", source="web", url="https://x.com/a.pdf")
        self.assertEqual(gd_turn.page_image_order([w]), [])


class TestImageSearchAndPrimer(unittest.TestCase):
    def test_web_search_has_image_options(self):
        self.assertEqual(gd_tools.WEB_SEARCH_SPEC,
                         {"type": "web_search", "enable_image_search": True, "enable_image_understanding": True})
        self.assertIn(gd_tools.WEB_SEARCH_SPEC, gd_tools.TOOL_SPECS)

    def test_primer_no_longer_says_text_only(self):
        p = gd_prompt.PRIMER
        self.assertNotIn("The text of a page is what can be read here", p)
        self.assertIn("read_pages also sends each page's image", p)
        self.assertIn("a web photo may be a different model, and the library pages are the trusted source", p)
        self.assertIn("A cited library page shows the tech that exact page.", p)   # v4.20.2: web-address half removed (test2)

    def test_read_pages_spec_mentions_images(self):
        spec = next(t for t in gd_tools.FUNCTION_SPECS if t["name"] == "read_pages")
        self.assertIn("page images", spec["description"])


class TestAppWiring(unittest.TestCase):
    def test_app_passes_page_image_fn_and_show_page_shares_the_drawing(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("page_image_fn = _gd_page_image_fn()", src)
        self.assertIn("page_image_fn=page_image_fn,", src)
        self.assertIn("def _gd_sheet_png(", src)
        self.assertIn("png = _gd_sheet_png(doc_id, sheet, file_path)", src)


if __name__ == "__main__":
    unittest.main()
