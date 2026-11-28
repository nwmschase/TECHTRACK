"""v4.20.6 (Chase go pt1664u, test7b): one picture from the pages Grok opened, cited pages when the state block is missing,
the old fallback note replaced."""
import os, subprocess, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gd_picture, gd_turn, gd_prompt
from gd_pages import Page

SRC = open(os.path.join(ROOT, "rv_techtrack.py"), encoding="utf-8").read()

REPLY = """Here are the exact diagrams and photos from the Lippert manual (CCD-0001769).
C2 Controller Overview (Page 6) – shows the exact controller you have under the bed, with the two LEDs, Mode button, Motor 1 & Motor 2 connectors. Also includes the motor harness connector detail (Fig. 7).
B Version Controller (Page 5) – very similar layout for reference.
Motors & Harnesses photo (Page 8) – actual photo of the motor and harness connection (Fig. 17).
Full wiring diagram & color codes (Page 13) – complete schematic showing both motor harnesses, controller connections, switch, power, and the exact wire colors."""


def _p(page, text="", topics=""):
    return Page(doc_id="L6", title="In-Wall Slide-Out Manual", page=str(page), sheet=int(page), text=text, topics=topics)


PAGES = [_p(5, "B version controller LED mode", "diagram / drawing: B version controller"),
         _p(6, "C2 controller LED mode button motor connector", "diagram / drawing: C2 controller overview"),
         _p(8, "motor harness connector ribs notch", "photo / photograph of the actual component: motor and harness connector"),
         _p(13, "wiring diagram colors black red brown green blue", "wiring diagram: color codes, motor harnesses")]


class TestPickPicture(unittest.TestCase):
    def test_one_page_for_the_item_asked(self):
        # v4.20.7: chosen from the page labels and text (no page numbers read out of the reply text)
        pick = lambda q: gd_picture.pick_picture_page(q, PAGES).page
        self.assertEqual(pick("can you show me a picture of the C2 controller"), "6")
        self.assertEqual(pick("send a photo of the motor and harness"), "8")
        self.assertEqual(pick("picture of the wiring diagram"), "13")

    def test_label_and_text_when_reply_names_no_page(self):
        pages = [_p(3, "slide room overview"), _p(9, "", topics="motor wiring diagram")]
        self.assertEqual(gd_picture.pick_picture_page("pic of the wiring", pages).page, "9")

    def test_nothing_opened_is_none_and_web_pages_skipped(self):
        self.assertIsNone(gd_picture.pick_picture_page("photo of the controller", []))
        web = Page(doc_id="https://x", title="x", page="1", sheet=1, text="controller", source="web")
        self.assertIsNone(gd_picture.pick_picture_page("photo of the controller", [web]))

    def test_dict_pages_work(self):
        d = [{"doc_id": "L6", "page": "8", "sheet": 8, "title": "t"}, {"doc_id": "L6", "page": "13", "sheet": 13}]
        self.assertEqual(gd_picture.pick_picture_page("wiring colors", d, cited=[{"doc_id": "L6", "page": "13"}])["page"], "13")

    def test_reply_text_page_regex_is_gone(self):
        self.assertFalse(hasattr(gd_picture, "_PAGE_REF"))
        self.assertFalse(hasattr(gd_picture, "_reply_scores"))


class TestCitedWhenStateMissing(unittest.TestCase):
    def _run(self, final):
        calls = []

        def respond(items, tools, tool_choice=None):
            calls.append(1)
            if len(calls) == 1:
                return {"text": "", "calls": [{"call_id": "c1", "name": "read_pages", "arguments": "{}"}], "output": []}
            return final

        class Lib:
            last_dropped, last_read = [], {}
            def call(self, name, args, max_pages=None): return "{}", [PAGES[1], PAGES[3], PAGES[1]], None
            def unit_brands(self, t): return set()
            def doc_brand(self, d): return ""
            def doc_brand_names(self, d): return set()

        return gd_turn.run_turn("show me the controller", "", "Schwintek", [], store={}, library=Lib(), respond_fn=respond,
                                log_path="")

    def test_opened_pages_fill_cited(self):
        r = self._run("Here is the controller page.")
        self.assertEqual([(c["doc_id"], c["page"]) for c in r["cited"]], [("L6", "6"), ("L6", "13")])
        self.assertTrue(all(c.get("read") and c.get("sheet") for c in r["cited"]))
        self.assertEqual([p.page for p in r["turn_pages"]], ["6", "13", "6"])

    def test_state_block_cited_wins(self):
        r = self._run('ok <state>{"cited": [{"doc_id": "L6", "page": "13"}]}</state>')
        self.assertEqual([(c["doc_id"], c["page"]) for c in r["cited"]], [("L6", "13")])


class TestFallbackNote(unittest.TestCase):
    def test_plain_note_and_old_boilerplate_gone(self):
        import gd_library_coach
        self.assertFalse(hasattr(gd_library_coach, "figure_render_honesty_note"))   # v4.20.7: retired
        src = open(gd_library_coach.__file__, encoding="utf-8").read()
        self.assertNotIn("could not load a matching shop-library PDF page", src + SRC)
        self.assertNotIn("TechTrack could not render that page image this turn", src)
        self.assertEqual(gd_picture.FAIL_NOTE, "That page didn't load; tap Open PDF.")

    def test_send_path_has_no_old_lookups(self):
        i = SRC.index('_send_key = gd_send_key(f"user:{_send_user}"')
        block = SRC[i:SRC.index("st.rerun()", i)]
        for old in ("resolve_requested_library_pages", "gd_figures_under_step", "_stored_figure_matches",
                    "figure_render_honesty_note"):
            self.assertNotIn(old, block)
        self.assertIn("_render_gd_picture(m.get(\"picture\")", SRC)
        body = SRC[SRC.index("def _render_gd_picture("):SRC.index("def _gd_commit_send(")]
        self.assertIn("gd_picture.FAIL_NOTE", body)
        self.assertIn("Open PDF", body)


if __name__ == "__main__":
    unittest.main()


class TestTurnPicture(unittest.TestCase):
    def _fn(self):
        import ast
        tree = ast.parse(SRC)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_gd_turn_picture")
        ns = {"_gd_doc_file_path": lambda d: f"library/{d}.pdf", "_gd_cited_page_refs": lambda c: [dict(x) for x in c or []]}
        exec(compile(ast.Module([node], []), "rv_techtrack.py", "exec"), ns)
        return ns["_gd_turn_picture"]

    def test_one_page_ref_from_the_opened_pages(self):
        pic = self._fn()("can you show me a picture of the C2 controller", REPLY,
                         {"turn_pages": PAGES, "cited": [], "drawn_keys": [("L6", 6), ("L6", 13)]})
        self.assertEqual((pic["ref"]["doc_id"], pic["ref"]["sheet"], pic["ref"]["file_path"]), ("L6", 6, "library/L6.pdf"))
        self.assertTrue(pic["drawn_for_grok"])
        self.assertNotIn("png", pic)

    def test_no_page_opened_this_turn_shows_nothing(self):
        # v4.20.7: no fallback to pages cited in earlier turns (an unrelated earlier page is not a picture of the ask)
        f = self._fn()
        self.assertIsNone(f("photo of the wiring", REPLY, {"turn_pages": [], "cited": [{"doc_id": "L6", "page": "13",
                                                                                         "sheet": 13}]}))
