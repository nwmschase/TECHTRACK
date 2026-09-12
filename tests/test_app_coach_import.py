"""Streamlit entry must load gd_library_coach without a missing-name ImportError."""
import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _names_assigned_from_gdc(src: str) -> list:
    """Names bound as NAME = _gdc.NAME in rv_techtrack.py."""
    tree = ast.parse(src)
    out = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        val = node.value
        if (
            isinstance(val, ast.Attribute)
            and isinstance(val.value, ast.Name)
            and val.value.id == "_gdc"
        ):
            out.append(target.id)
    return out


class TestCoachModuleLoads(unittest.TestCase):
    def test_gd_library_coach_has_ac_unity_skip(self):
        spec = importlib.util.spec_from_file_location(
            "gd_library_coach_fresh", ROOT / "gd_library_coach.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in (
            "AC_HINT_TITLES",
            "AC_PRODUCT_LOCK",
            "ac_search_symptom",
            "drop_unity_chunks_for_ac",
            "is_air_conditioning_context",
            "skip_unity_for_ac",
        ):
            self.assertTrue(hasattr(mod, name), name)
        self.assertTrue(
            mod.skip_unity_for_ac("Air Conditioning", "Furrion FACT12SA2", "no cool")
        )

    def test_rv_techtrack_binds_only_existing_coach_names(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        names = _names_assigned_from_gdc(src)
        self.assertIn("skip_unity_for_ac", names)
        self.assertIn("AC_PRODUCT_LOCK", names)
        spec = importlib.util.spec_from_file_location(
            "gd_library_coach_check", ROOT / "gd_library_coach.py"
        )
        coach = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(coach)
        missing = [n for n in names if not hasattr(coach, n)]
        self.assertEqual(missing, [])

    def test_loader_replaces_stale_cached_module(self):
        """Mirrors Streamlit Cloud keeping a pre-4.13.3 gd_library_coach in sys.modules."""
        stale = types.ModuleType("gd_library_coach")
        stale.OPEN_LIBRARY_COACH_RULE = "old"
        sys.modules["gd_library_coach"] = stale
        self.addCleanup(lambda: sys.modules.pop("gd_library_coach", None))
        spec = importlib.util.spec_from_file_location(
            "rv_techtrack_loader_probe", ROOT / "rv_techtrack.py"
        )
        # Only exec through the loader by importing the helper from source.
        src = (ROOT / "rv_techtrack.py").read_text()
        ns = {"__file__": str(ROOT / "rv_techtrack.py"), "Path": Path}
        # Run just enough of the file to define and call the loader.
        start = src.index("def _load_gd_library_coach")
        end = src.index("_gdc = _load_gd_library_coach()")
        exec(compile(src[start:end] + "_gdc = _load_gd_library_coach()\n", "loader", "exec"), ns)
        loaded = ns["_gdc"]
        self.assertTrue(hasattr(loaded, "skip_unity_for_ac"))
        self.assertTrue(
            loaded.skip_unity_for_ac("Air Conditioning", "Dometic B57915", "no cool")
        )

    def test_legacy_pr4_does_not_import_removed_hint(self):
        src = (ROOT / "rv_techtrackpr4").read_text()
        tree = ast.parse(src)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "gd_library_coach":
                imported.extend(a.name for a in node.names)
        self.assertNotIn("format_procedure_library_hint", imported)
        spec = importlib.util.spec_from_file_location(
            "gd_library_coach_pr4", ROOT / "gd_library_coach.py"
        )
        coach = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(coach)
        missing = [n for n in imported if not hasattr(coach, n)]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
