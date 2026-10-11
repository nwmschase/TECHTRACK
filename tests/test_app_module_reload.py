"""A Streamlit redeploy must bind the new Bay PDF module, not the cached one."""
import re
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAMES = ("gd_library_coach", "gd_llm", "library_figure_backfill", "bay_procedure")


def _loader_namespace():
    """Exec the reload guard the way the coach-import tests do.

    The slice stops before the production call, which names APP_VERSION.
    That name is not in this namespace.
    """
    src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
    start = src.index("_GDC_STALE_GUARD_ATTRS")
    end = src.index("_gdc = _load_gd_library_coach()")
    ns = {"__file__": str(ROOT / "rv_techtrack.py"), "Path": Path}
    exec(compile(src[start:end], "loader", "exec"), ns)
    return ns


class TestAppModuleReload(unittest.TestCase):
    def setUp(self):
        self._saved = {name: sys.modules.get(name) for name in APP_NAMES}

    def tearDown(self):
        for name, mod in self._saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    def test_redeploy_replaces_stale_bay_procedure_that_still_has_names(self):
        """Old function names are not enough. The previous sheet must not run."""
        ns = _loader_namespace()
        stale = types.ModuleType("bay_procedure")
        stale.MODULE_REVISION = "v4.19.6"
        stale.BAY_PROCEDURE_LABEL = "old"
        stale.MAX_FIGURES_PER_SHEET = 2
        stale.compile_bay_procedure = lambda *a, **k: "STALE"
        stale.render_bay_procedure_pdf = lambda *a, **k: b"STALE"
        stale.crop_page_png_to_figure = lambda *a, **k: b""
        stale.rewrite_bay_search_symptom = lambda *a, **k: ""
        stale.suggested_pdf_filename = lambda *a, **k: "old.pdf"
        sys.modules["bay_procedure"] = stale

        ns["_reload_stale_app_modules"]("v4.19.45")
        loaded = sys.modules["bay_procedure"]
        self.assertIsNot(loaded, stale)
        self.assertEqual(loaded.MODULE_REVISION, "v4.19.45")
        # A second pass sees the matching stamp and keeps this module object.
        again = ns["_reload_app_module"]("bay_procedure", "v4.19.45")
        self.assertIs(again, loaded)

        proc = loaded.compile_bay_procedure(
            concern="Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
            brand="Suburban",
            model="NT-20SEQT",
            category="Furnaces",
            chunks=[],
        )
        self.assertNotEqual(proc, "STALE")
        nodes = " ".join(node.text for node in proc.flowchart.nodes).lower()
        self.assertIn("limit switch", nodes)
        self.assertIn("module board", nodes)
        self.assertNotIn("sail passed", nodes)

    def test_redeploy_replaces_a_stale_figure_bank_module(self):
        """Callers reload. The figure bank has to reload with them."""
        ns = _loader_namespace()
        stale = types.ModuleType("library_figure_backfill")
        stale.MODULE_REVISION = "v4.19.6"
        sys.modules["library_figure_backfill"] = stale

        ns["_reload_stale_app_modules"]("v4.19.45")
        loaded = sys.modules["library_figure_backfill"]
        self.assertIsNot(loaded, stale)
        self.assertEqual(loaded.MODULE_REVISION, "v4.19.45")
        self.assertTrue(hasattr(loaded, "fits_case"))
        self.assertTrue(hasattr(loaded, "off_brand_figure"))
        self.assertTrue(hasattr(loaded, "procedure_how"))

    def test_stale_figure_bank_shows_no_figure_instead_of_crashing(self):
        """The live crash: a reloaded caller bound the old module object."""
        import bay_procedure as bp

        stale = types.ModuleType("library_figure_backfill")
        sys.modules["library_figure_backfill"] = stale
        proc = bp.compile_bay_procedure(
            concern="AC turns on but will not blow cold",
            brand="Dometic",
            model="B57915E711J0EMX",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Tip Sheet #216",
                    "excerpt": "Remove the pump seal at the closet flange.",
                    "page": 4,
                    "figures": [
                        {
                            "png": b"\x89PNG\r\n\x1a\nstale",
                            "label": "Fig. 4 pump seal",
                            "caption": "Power Gear pump seal",
                            "page": 4,
                            "title": "Tip Sheet #216",
                        }
                    ],
                }
            ],
        )
        titles = " ".join(
            [
                *(fig.title for fig in proc.figures or []),
                *(fig.title for group in proc.step_figures or [] for fig in group),
            ]
        ).lower()
        self.assertNotIn("tip sheet", titles)
        self.assertNotIn("power gear", titles)
        self.assertEqual(bp.cited_figure_count(proc), 0)

        proc.figures = [
            bp.BayFigure(
                title="Tip Sheet #216",
                caption="Fig. 4 pump seal",
                excerpt="Power Gear pump seal",
                image_png=b"\x89PNG\r\n\x1a\nstale",
            )
        ]
        bp._drop_off_brand_sheet_figures(proc, "Dometic B57915 AC will not blow cold")
        self.assertEqual(proc.figures, [])

    def test_missing_revision_is_stale(self):
        ns = _loader_namespace()
        stale = types.ModuleType("gd_llm")
        stale.complete_chat = lambda *a, **k: "STALE"
        sys.modules["gd_llm"] = stale
        loaded = ns["_reload_app_module"]("gd_llm", "v4.19.45")
        self.assertIsNot(loaded, stale)
        self.assertEqual(loaded.MODULE_REVISION, "v4.19.45")

    def test_matching_revision_is_not_replaced(self):
        ns = _loader_namespace()
        current = types.ModuleType("bay_procedure")
        current.MODULE_REVISION = "v4.19.45"
        marker = object()
        current.marker = marker
        sys.modules["bay_procedure"] = current
        loaded = ns["_reload_app_module"]("bay_procedure", "v4.19.45")
        self.assertIs(loaded, current)
        self.assertIs(loaded.marker, marker)

    def test_required_revision_matches_the_app_header(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        header = re.search(r"RV TechTrack (v\d+\.\d+\.\d+)", src).group(1)
        required = re.search(r'_GDC_REQUIRED_REVISION = "(v[\d.]+)"', src).group(1)
        self.assertEqual(required, header)
        self.assertEqual(header, "v4.19.45")
        for name in APP_NAMES:
            text = (ROOT / f"{name}.py").read_text(encoding="utf-8")
            self.assertIn(f'MODULE_REVISION = "{header}"' if name != "gd_library_coach" else "MODULE_REVISION = COACH_REVISION", text)
            self.assertIn(header, text)

    def test_header_date_is_the_pacific_calendar_day(self):
        """UTC 2026-10-10 05:30 is still 2026-10-09 in Pacific (PDT, UTC-7)."""
        import bay_procedure as bp

        utc = datetime(2026, 10, 10, 5, 30, tzinfo=timezone.utc)

        class _Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                if tz is None:
                    return utc.replace(tzinfo=None)
                return utc.astimezone(tz)

        original = bp.datetime
        bp.datetime = _Clock
        try:
            self.assertEqual(bp.sheet_local_now().strftime("%Y-%m-%d"), "2026-10-09")
            proc = bp.compile_bay_procedure(
                concern="Suburban NT-20SEQT furnace fan comes on then shuts off, no heat",
                brand="Suburban",
                model="NT-20SEQT",
                category="Furnaces",
                chunks=[],
            )
            self.assertEqual(proc.created.strftime("%Y-%m-%d"), "2026-10-09")
            self.assertIn("Date: 2026-10-09", bp.procedure_plain_text(proc))
            pages = bp.compose_sheet(proc)
            header = " ".join(item.text for item in pages[0].texts if item.role == "header")
            self.assertIn("2026-10-09", header)
            self.assertNotIn("2026-10-10", header)
        finally:
            bp.datetime = original


if __name__ == "__main__":
    unittest.main()
