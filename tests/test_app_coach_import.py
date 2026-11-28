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
            "is_air_conditioning_context",
            "is_fcr_e2_fan_fault_context",
            "is_water_heater_context",
            "DEFAULT_LIBRARY_CATEGORIES",
            "AIR_CONDITIONING_CATEGORY",
            "REFRIGERATORS_CATEGORY",
            "WATER_HEATERS_CATEGORY",
            "RANGE_COOKTOPS_CATEGORY",
            "gd_category_select_options",
            "library_category_picker_names",
            "is_cooktop_pan_on_flameout_context",
            "is_stabilizer_override_pin_context",
            "complete_chat_with_payload_retry",
            "is_facr_rooftop_freeze_context",
            "FACR_FREEZE_SEARCH_BOOST",
            "is_bal_soft_touch_tongue_only_context",
            "is_coleman_2111_context",
        ):
            self.assertTrue(hasattr(mod, name), name)
        self.assertTrue(
            mod.is_fcr_e2_fan_fault_context(
                "Refrigerators", "Furrion FCR10DCGTA", "intermittent E2 / 2-flash"
            )
        )

    def test_rv_techtrack_binds_only_existing_coach_names(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        names = _names_assigned_from_gdc(src)
        # 2026-10-24: unused aliases were dropped; these are the ones rv still reads.
        for name in (
            "DEFAULT_LIBRARY_CATEGORIES",
            "gd_category_select_options",
            "library_category_picker_names",
            "complete_chat_with_payload_retry",
        ):
            self.assertIn(name, names)
        # v4.20.7: the old figure path that read these is retired, so they are no longer bound
        for name in ("pick_diagram_page_numbers", "is_water_heater_context", "figure_render_honesty_note",
                     "wants_library_page_shown"):
            self.assertNotIn(name, names)
        spec = importlib.util.spec_from_file_location(
            "gd_library_coach_check", ROOT / "gd_library_coach.py"
        )
        coach = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(coach)
        missing = [n for n in names if not hasattr(coach, n)]
        self.assertEqual(missing, [])

    def test_reexport_block_binds_category_attrs(self):
        """Execute the rv_techtrack _gdc re-export block so a missing attr fails CI."""
        src = (ROOT / "rv_techtrack.py").read_text()
        names = _names_assigned_from_gdc(src)
        spec = importlib.util.spec_from_file_location(
            "gd_library_coach_reexport", ROOT / "gd_library_coach.py"
        )
        coach = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(coach)
        lines = []
        for name in names:
            lines.append(f"{name} = _gdc.{name}")
        ns = {"_gdc": coach}
        exec(compile("\n".join(lines), "reexport", "exec"), ns)
        self.assertEqual(coach.AIR_CONDITIONING_CATEGORY, "Air Conditioning")
        self.assertEqual(coach.WATER_HEATERS_CATEGORY, "Water Heaters")
        self.assertEqual(coach.RANGE_COOKTOPS_CATEGORY, "Range & Cooktops")
        self.assertEqual(coach.REFRIGERATORS_CATEGORY, "Refrigerators")
        self.assertIn(coach.AIR_CONDITIONING_CATEGORY, ns["DEFAULT_LIBRARY_CATEGORIES"])
        self.assertTrue(callable(ns["gd_category_select_options"]))
        self.assertTrue(callable(ns["library_category_picker_names"]))

    def test_loader_replaces_stale_cached_module(self):
        """Mirrors Streamlit Cloud keeping a pre-4.13.7 gd_library_coach in sys.modules."""
        stale = types.ModuleType("gd_library_coach")
        stale.OPEN_LIBRARY_COACH_RULE = "old"
        stale.skip_unity_for_ac = lambda *a, **k: True
        stale.is_fcr_e2_fan_fault_context = lambda *a, **k: False
        stale.skip_unity_for_water_heater = lambda *a, **k: True
        stale.is_cooktop_pan_on_flameout_context = lambda *a, **k: False
        stale.is_stabilizer_override_pin_context = lambda *a, **k: False
        # Live crash: PR #14 attrs present, PR #13 category constants absent.
        sys.modules["gd_library_coach"] = stale
        self.addCleanup(lambda: sys.modules.pop("gd_library_coach", None))
        src = (ROOT / "rv_techtrack.py").read_text()
        ns = {"__file__": str(ROOT / "rv_techtrack.py"), "Path": Path}
        start = src.index("_GDC_STALE_GUARD_ATTRS")
        end = src.index("_gdc = _load_gd_library_coach()")
        exec(compile(src[start:end] + "_gdc = _load_gd_library_coach()\n", "loader", "exec"), ns)
        loaded = ns["_gdc"]
        self.assertTrue(hasattr(loaded, "is_fcr_e2_fan_fault_context"))
        self.assertTrue(hasattr(loaded, "is_cooktop_pan_on_flameout_context"))
        self.assertTrue(hasattr(loaded, "is_stabilizer_override_pin_context"))
        self.assertTrue(hasattr(loaded, "is_facr_rooftop_freeze_context"))
        self.assertTrue(hasattr(loaded, "AIR_CONDITIONING_CATEGORY"))
        self.assertTrue(hasattr(loaded, "DEFAULT_LIBRARY_CATEGORIES"))
        self.assertEqual(loaded.AIR_CONDITIONING_CATEGORY, "Air Conditioning")
        self.assertEqual(loaded.COACH_REVISION, "v4.20.8")

    def test_loader_reloads_when_revision_is_old_even_if_names_exist(self):
        """v4.19.4 kept the v4.19.3 coach: every old name existed, so the fan-only detector stayed."""
        src = (ROOT / "rv_techtrack.py").read_text()
        start = src.index("_GDC_STALE_GUARD_ATTRS")
        end = src.index("_gdc = _load_gd_library_coach()")
        ns = {"__file__": str(ROOT / "rv_techtrack.py"), "Path": Path}
        exec(compile(src[start:end], "attrs", "exec"), ns)
        stale = types.ModuleType("gd_library_coach")
        for name in ns["_GDC_STALE_GUARD_ATTRS"]:
            setattr(stale, name, lambda *a, **k: False)
        stale.COACH_REVISION = "v4.19.3"
        stale.is_fcr_e2_fan_fault_context = lambda *a, **k: False
        sys.modules["gd_library_coach"] = stale
        self.addCleanup(lambda: sys.modules.pop("gd_library_coach", None))
        exec(
            compile(src[start:end] + "_gdc = _load_gd_library_coach()\n", "loader", "exec"),
            ns,
        )
        loaded = ns["_gdc"]
        self.assertEqual(loaded.COACH_REVISION, "v4.20.8")
        self.assertIsNot(loaded, stale)
        self.assertTrue(
            loaded.is_fcr_e2_fan_fault_context(
                "Refrigerators", "Furrion FCR10DCGTA", "intermittent E2 / 2-flash"
            )
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
        # rv_techtrackpr4 is an archived v4.12.0 copy that nothing runs. Its old
        # imports (OPEN_LIBRARY_COACH_RULE, hard_tree_yields_to_coach,
        # pick_working_vision_model, tech_wants_open_coach) were dead code and
        # were removed from the coach on 2026-10-24.
        retired = {
            "OPEN_LIBRARY_COACH_RULE",
            "hard_tree_yields_to_coach",
            "pick_working_vision_model",
            "tech_wants_open_coach",
            "wants_library_figures",   # v4.20.7: old regex figure ask, retired with the old figure path
        }
        missing = [n for n in imported if not hasattr(coach, n) and n not in retired]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
