"""A Streamlit redeploy must bind the new sibling modules, not the cached ones."""
import re
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_NAMES = (
    "gd_llm",
    "gd_step_photo",
    "manual_figures",
    "gd_library_coach",
    "library_figure_backfill",
)


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

    def test_matching_revision_is_not_replaced(self):
        ns = _loader_namespace()
        current = types.ModuleType("library_figure_backfill")
        current.MODULE_REVISION = "v4.20.2"
        marker = object()
        current.marker = marker
        sys.modules["library_figure_backfill"] = current
        loaded = ns["_reload_app_module"]("library_figure_backfill", "v4.20.2")
        self.assertIs(loaded, current)
        self.assertIs(loaded.marker, marker)

    def tearDown(self):
        for name, mod in self._saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


    def test_redeploy_replaces_a_stale_figure_bank_module(self):
        """Callers reload. The figure bank has to reload with them."""
        ns = _loader_namespace()
        stale = types.ModuleType("library_figure_backfill")
        stale.MODULE_REVISION = "v4.19.6"
        sys.modules["library_figure_backfill"] = stale

        ns["_reload_stale_app_modules"]("v4.20.2")
        loaded = sys.modules["library_figure_backfill"]
        self.assertIsNot(loaded, stale)
        self.assertEqual(loaded.MODULE_REVISION, "v4.20.2")
        self.assertTrue(hasattr(loaded, "fits_case"))
        self.assertTrue(hasattr(loaded, "off_brand_figure"))
        self.assertTrue(hasattr(loaded, "procedure_how"))

    def test_stale_manual_figures_reloads_the_coach_and_logs_revisions(self):
        """The lead-jack coach must not keep a module that was loaded earlier."""
        ns = _loader_namespace()
        stale = types.ModuleType("manual_figures")
        stale.MODULE_REVISION = "v4.19.6"
        sys.modules["manual_figures"] = stale
        with self.assertLogs("techtrack.modules", level="WARNING") as captured:
            ns["_reload_stale_app_modules"]("v4.20.2")
        loaded = sys.modules["manual_figures"]
        self.assertIsNot(loaded, stale)
        self.assertEqual(loaded.MODULE_REVISION, "v4.20.2")
        coach = sys.modules["gd_library_coach"]
        self.assertIs(coach._manual_figures, loaded)
        self.assertEqual(coach.MODULE_REVISION, "v4.20.2")
        text = "\n".join(captured.output)
        for name in APP_NAMES:
            self.assertIn(f"MODULE_REVISION {name}=v4.20.2", text)
        mismatch = types.ModuleType("gd_step_photo")
        mismatch.MODULE_REVISION = "v4.19.6"
        with self.assertLogs("techtrack.modules", level="ERROR") as bad:
            ns["_log_loaded_revision"]("gd_step_photo", mismatch, "v4.20.2")
        self.assertIn("MODULE_REVISION gd_step_photo=v4.19.6 expected v4.20.2", "\n".join(bad.output))


    def test_missing_revision_is_stale(self):
        ns = _loader_namespace()
        stale = types.ModuleType("gd_llm")
        stale.complete_chat = lambda *a, **k: "STALE"
        sys.modules["gd_llm"] = stale
        loaded = ns["_reload_app_module"]("gd_llm", "v4.20.2")
        self.assertIsNot(loaded, stale)
        self.assertEqual(loaded.MODULE_REVISION, "v4.20.2")


    def test_required_revision_matches_the_app_header(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        header = re.search(r"RV TechTrack (v\d+\.\d+\.\d+)", src).group(1)
        required = re.search(r'_GDC_REQUIRED_REVISION = "(v[\d.]+)"', src).group(1)
        self.assertEqual(required, header)
        self.assertEqual(header, "v4.20.2")
        for name in APP_NAMES:
            text = (ROOT / f"{name}.py").read_text(encoding="utf-8")
            self.assertIn(f'MODULE_REVISION = "{header}"' if name != "gd_library_coach" else "MODULE_REVISION = COACH_REVISION", text)
            self.assertIn(header, text)


if __name__ == "__main__":
    unittest.main()


class TestConcurrentSessionsLoadWholeModules(unittest.TestCase):
    """Live 2026-10-20 reboot: "cannot import name 'MAX_FIGURES_PER_SHEET' from 'bay_procedure'" (the Bay PDF module,
    removed 2026-10-24; the check now imports the last name of the figure bank). Two session threads
    loaded the sibling modules at once; one bound the other's half-run module. Reproduced here before the lock (3/3
    rounds failed: MAX_FIGURES_PER_SHEET, manual_figures attrs, KeyError) and clean after it."""

    def setUp(self):
        self._saved = {name: sys.modules.get(name) for name in APP_NAMES}

    def tearDown(self):
        for name, mod in self._saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod

    def test_parallel_first_load_never_binds_a_partial_module(self):
        import threading

        for _ in range(3):
            for name in APP_NAMES:
                sys.modules.pop(name, None)
            ns = _loader_namespace()
            bar, errs = threading.Barrier(6), []

            def worker():
                try:
                    bar.wait()
                    ns["_reload_stale_app_modules"]("v4.20.2")
                    with ns["_app_module_lock"]():
                        from library_figure_backfill import complete_figure_rows  # noqa: F401
                except BaseException as exc:  # noqa: BLE001
                    errs.append(f"{type(exc).__name__}: {exc}")

            threads = [threading.Thread(target=worker) for _ in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errs, [])

    def test_failed_load_leaves_no_half_module(self):
        import tempfile

        ns = _loader_namespace()
        d = Path(tempfile.mkdtemp())
        (d / "tt_broken_mod.py").write_text("MODULE_REVISION = 'v4.20.2'\nraise RuntimeError('boom')\n")
        ns["__file__"] = str(d / "rv_techtrack.py")
        exec(compile("Path = __import__('pathlib').Path", "x", "exec"), ns)
        with self.assertRaises(RuntimeError):
            ns["_reload_app_module"]("tt_broken_mod", "v4.20.2")
        self.assertNotIn("tt_broken_mod", sys.modules)

    def test_sibling_modules_have_no_import_cycle(self):
        import ast

        names = set(APP_NAMES) | {"gd_pages", "gd_turn", "gd_state", "gd_prompt", "gd_story", "legacy_selector",
                                  "library_bulk_import", "oem_domains"}
        graph = {}
        for n in names:
            f = ROOT / f"{n}.py"
            if not f.exists():
                continue
            deps = set()
            for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    deps |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    deps.add(node.module.split(".")[0])
            graph[n] = deps & names - {n}

        def cycle_from(n, path):
            for m in graph.get(n, ()):
                if m in path:
                    return path[path.index(m):] + [m]
                c = cycle_from(m, path + [m])
                if c:
                    return c
            return None

        for n in graph:
            self.assertIsNone(cycle_from(n, [n]), f"import cycle among app modules from {n}")
