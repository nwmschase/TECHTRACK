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
            "FCR_E2_FAN_FAULT_PRODUCT_LOCK",
            "ac_search_symptom",
            "drop_unity_chunks_for_ac",
            "ensure_fcr_e2_fan_rr",
            "fcr_e2_search_symptom",
            "is_air_conditioning_context",
            "is_fcr_e2_fan_fault_context",
            "skip_unity_for_ac",
            "skip_unity_for_water_heater",
            "is_water_heater_context",
            "WATER_HEATER_PRODUCT_LOCK",
            "DEFAULT_LIBRARY_CATEGORIES",
            "AIR_CONDITIONING_CATEGORY",
            "REFRIGERATORS_CATEGORY",
            "WATER_HEATERS_CATEGORY",
            "RANGE_COOKTOPS_CATEGORY",
            "gd_category_select_options",
            "library_category_picker_names",
            "is_cooktop_pan_on_flameout_context",
            "COOKTOP_PRODUCT_LOCK",
            "ensure_cooktop_tip_pan_check",
            "is_stabilizer_override_pin_context",
            "PSX1_PRODUCT_LOCK",
            "ensure_stabilizer_assembly_rr",
            "is_fridge_ice_moisture_context",
            "ICE_MOISTURE_PRODUCT_LOCK",
            "ensure_fridge_ice_moisture_path",
        ):
            self.assertTrue(hasattr(mod, name), name)
        self.assertTrue(
            mod.skip_unity_for_ac("Air Conditioning", "Furrion FACT12SA2", "no cool")
        )
        self.assertTrue(
            mod.is_fcr_e2_fan_fault_context(
                "Refrigerators", "Furrion FCR10DCGTA", "intermittent E2 / 2-flash"
            )
        )

    def test_rv_techtrack_binds_only_existing_coach_names(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        names = _names_assigned_from_gdc(src)
        self.assertIn("skip_unity_for_ac", names)
        self.assertIn("AC_PRODUCT_LOCK", names)
        self.assertIn("is_fcr_e2_fan_fault_context", names)
        self.assertIn("FCR_E2_FAN_FAULT_PRODUCT_LOCK", names)
        self.assertIn("skip_unity_for_water_heater", names)
        self.assertIn("WATER_HEATER_PRODUCT_LOCK", names)
        self.assertIn("DEFAULT_LIBRARY_CATEGORIES", names)
        self.assertIn("AIR_CONDITIONING_CATEGORY", names)
        self.assertIn("REFRIGERATORS_CATEGORY", names)
        self.assertIn("WATER_HEATERS_CATEGORY", names)
        self.assertIn("RANGE_COOKTOPS_CATEGORY", names)
        self.assertIn("gd_category_select_options", names)
        self.assertIn("library_category_picker_names", names)
        self.assertIn("COOKTOP_PRODUCT_LOCK", names)
        self.assertIn("is_cooktop_pan_on_flameout_context", names)
        self.assertIn("PSX1_PRODUCT_LOCK", names)
        self.assertIn("is_stabilizer_override_pin_context", names)
        self.assertIn("ICE_MOISTURE_PRODUCT_LOCK", names)
        self.assertIn("is_fridge_ice_moisture_context", names)
        self.assertIn("ensure_fridge_ice_moisture_path", names)
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
        self.assertEqual(ns["AIR_CONDITIONING_CATEGORY"], "Air Conditioning")
        self.assertEqual(ns["WATER_HEATERS_CATEGORY"], "Water Heaters")
        self.assertEqual(ns["RANGE_COOKTOPS_CATEGORY"], "Range & Cooktops")
        self.assertEqual(ns["REFRIGERATORS_CATEGORY"], "Refrigerators")
        self.assertIn(ns["AIR_CONDITIONING_CATEGORY"], ns["DEFAULT_LIBRARY_CATEGORIES"])
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
        self.assertTrue(hasattr(loaded, "skip_unity_for_ac"))
        self.assertTrue(hasattr(loaded, "is_fcr_e2_fan_fault_context"))
        self.assertTrue(hasattr(loaded, "skip_unity_for_water_heater"))
        self.assertTrue(hasattr(loaded, "is_cooktop_pan_on_flameout_context"))
        self.assertTrue(hasattr(loaded, "is_stabilizer_override_pin_context"))
        self.assertTrue(hasattr(loaded, "is_fridge_ice_moisture_context"))
        self.assertTrue(hasattr(loaded, "AIR_CONDITIONING_CATEGORY"))
        self.assertTrue(hasattr(loaded, "DEFAULT_LIBRARY_CATEGORIES"))
        self.assertEqual(loaded.AIR_CONDITIONING_CATEGORY, "Air Conditioning")
        self.assertTrue(
            loaded.skip_unity_for_ac("Air Conditioning", "Dometic B57915", "no cool")
        )
        self.assertTrue(
            loaded.skip_unity_for_water_heater("", "Girard GSWH-2", "water heater stopped working E8")
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
