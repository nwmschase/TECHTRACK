"""Sidebar deploy caption follows the module docstring header, not a frozen literal."""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rv_techtrack.py"
CAPTION = (
    "st.sidebar.caption(f\"{APP_VERSION} \u2022 Tacoma RV Center "
    "\u2022 Open library coach \u2022 Auto DB backup\")"
)


def _load_product_version_fn():
    """Exec only product_version_from_doc. Do not import rv_techtrack (set_page_config)."""
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "product_version_from_doc"
    )
    ns = {"re": re}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(APP), "exec"), ns)
    return ns["product_version_from_doc"], ast.get_docstring(tree)


class TestSidebarVersion(unittest.TestCase):
    def test_docstring_header_is_current_release(self):
        version_of, doc = _load_product_version_fn()
        self.assertTrue(doc.startswith("RV TechTrack v"))
        self.assertEqual(version_of(doc), "v4.18.0")

    def test_header_wins_over_later_changelog_versions(self):
        version_of, _doc = _load_product_version_fn()
        sample = "RV TechTrack v9.9.9\n- v1.0.0: older bullet\n- v4.13.0: coach\n"
        self.assertEqual(version_of(sample), "v9.9.9")
        self.assertEqual(version_of(""), "unknown")
        self.assertEqual(version_of(None), "unknown")

    def test_caption_uses_app_version_constant(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn("APP_VERSION = product_version_from_doc(__doc__)", src)
        self.assertIn(CAPTION, src)
        self.assertNotIn('st.sidebar.caption("v', src)
