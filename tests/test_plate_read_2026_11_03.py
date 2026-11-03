"""Data-plate photo read on the Guided Diagnostics page (memory test 2026-11-03).

The bug: "Read plate into Model" read the photo, then wrote st.session_state['ask_model'] after the Model text box
had already been drawn in that run, and Streamlit raised StreamlitWidgetAlreadyInstantiatedError, so the GD page
crashed. The fix parks the read value and puts it in the box on the next run, before the box is drawn.

These tests run the app's real helper functions (pulled from rv_techtrack.py by name, so the whole app is not
imported) inside a small page with the same layout as the GD page: Model box first, plate expander after it.
No AI is called: the plate reader is a stub.
"""
import ast
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rv_techtrack.py"
HELPERS = (
    "_restore_widget",
    "_remember_widget",
    "apply_plate_read_to_model_key",
    "_plate_pending_key",
    "apply_pending_plate_read",
    "show_plate_read_note",
)


def _helper_source() -> str:
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    src = APP.read_text(encoding="utf-8")
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS and node.name not in found:
            found[node.name] = ast.get_source_segment(src, node)
    missing = [h for h in HELPERS if h not in found]
    assert not missing, f"helpers missing from rv_techtrack.py: {missing}"
    return "\n\n".join(found[h] for h in HELPERS)


def _page(helpers: str, reply: str) -> str:
    # Same order as the GD page: pending value -> restore -> Model box -> note -> plate expander -> remember.
    return f'''
import streamlit as st

def read_data_plate_from_image(raw, mime="image/jpeg"):
    return {reply}

{helpers}

apply_pending_plate_read("ask_model", "gd_model_memory")
_restore_widget("ask_model", "gd_model_memory")
st.text_input("Model / System (optional)", key="ask_model")
show_plate_read_note("ask_model")
plate_img = st.file_uploader("Or upload plate photo", type=["jpg", "jpeg", "png", "webp"], key="ask_plate_upload")
if plate_img is not None:
    apply_plate_read_to_model_key("ask_model", plate_img, "ask_plate_read_btn")
_remember_widget("ask_model", "gd_model_memory")
'''


OK_READ = '{"ok": True, "error": "", "brand": "Dometic", "model": "B57915", "raw": ""}'
BAD_READ = '{"ok": False, "error": "Could not read a model from that photo.", "brand": "", "model": "", "raw": ""}'


class TestPlateReadFillsModel(unittest.TestCase):
    def _run(self, reply: str) -> AppTest:
        at = AppTest.from_string(_page(_helper_source(), reply), default_timeout=30)
        at.run()
        at.text_input(key="ask_model").set_value("typed first").run()
        at.file_uploader(key="ask_plate_upload").upload("plate.jpg", b"\xff\xd8fake-jpeg", "image/jpeg")
        at.run()
        at.button(key="ask_plate_read_btn").click().run()
        return at

    def test_read_plate_fills_the_model_box_without_crashing(self):
        at = self._run(OK_READ)
        self.assertFalse(list(at.exception), [e.value for e in at.exception])
        self.assertEqual(at.text_input(key="ask_model").value, "Dometic B57915")
        self.assertEqual(at.session_state["gd_model_memory"], "Dometic B57915")
        self.assertIn("Model set to: Dometic B57915", [s.value for s in at.success])

    def test_a_failed_read_warns_and_keeps_what_the_tech_typed(self):
        at = self._run(BAD_READ)
        self.assertFalse(list(at.exception))
        self.assertEqual(at.text_input(key="ask_model").value, "typed first")
        self.assertTrue(any("Could not read" in w.value for w in at.warning))

    def test_tech_can_still_edit_the_model_after_a_read(self):
        at = self._run(OK_READ)
        at.text_input(key="ask_model").set_value("B57915.301").run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.text_input(key="ask_model").value, "B57915.301")
        self.assertEqual(at.session_state["gd_model_memory"], "B57915.301")


class TestGdPageOrder(unittest.TestCase):
    def test_pending_read_is_applied_before_the_model_box_is_drawn(self):
        src = APP.read_text(encoding="utf-8")
        pending = src.index('apply_pending_plate_read("ask_model", "gd_model_memory")')
        box = src.index('key="ask_model"')
        button = src.index('apply_plate_read_to_model_key("ask_model", plate_img, "ask_plate_read_btn")')
        self.assertLess(pending, box)
        self.assertLess(box, button)

    def test_reader_never_writes_the_widget_key_directly(self):
        seg = ast.get_source_segment(
            APP.read_text(encoding="utf-8"),
            next(n for n in ast.parse(APP.read_text(encoding="utf-8")).body
                 if isinstance(n, ast.FunctionDef) and n.name == "apply_plate_read_to_model_key"),
        )
        self.assertNotIn("st.session_state[model_key] =", seg)


if __name__ == "__main__":
    unittest.main()
