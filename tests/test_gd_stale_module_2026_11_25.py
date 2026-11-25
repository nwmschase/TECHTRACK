"""Live crash 2026-11-25 (SW6DE water heater job): after the 46ecd22 redeploy, answering the end-of-job access question
("switch replaced, everything is working as designed.") raised TypeError at rv_techtrack.py
`_story.record_access_answer(_rec, msg, history)`. Streamlit re-executed the new rv_techtrack.py but kept the previous
gd_story in sys.modules, whose record_access_answer(case, text) took two arguments. The app now drops the plain-imported
GD modules when their files changed, so the next import runs the deployed file."""
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NAMES = ("gd_state", "gd_pages", "gd_prompt", "gd_official", "gd_tools", "gd_turn", "gd_story", "gd_work_orders",
         "_techtrack_src_stamps")
MSG = "switch replaced, everything is working as designed."
HISTORY = [
    {"role": "user", "content": "Suburban SW6DE propane will not light, igniter clicks then lockout"},
    {"role": "assistant", "content": "Re-check the 12 V supply at the water heater during an ignition try."},
]


def _loader_namespace():
    src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
    start = src.index("_GDC_STALE_GUARD_ATTRS")
    end = src.index("_gdc = _load_gd_library_coach()")
    ns = {"__file__": str(ROOT / "rv_techtrack.py"), "Path": Path}
    exec(compile(src[start:end], "loader", "exec"), ns)
    return ns


def _stale_gd_story():
    """The gd_story a process loaded at 34a0cc3: record_access_answer(case, text)."""
    old = types.ModuleType("gd_story")

    def record_access_answer(case, text):
        return case

    old.record_access_answer = record_access_answer
    old.__file__ = str(ROOT / "gd_story.py")
    return old


class TestStaleGdModules(unittest.TestCase):
    def setUp(self):
        self._saved = {n: sys.modules.get(n) for n in NAMES}
        sys.modules.pop("_techtrack_src_stamps", None)

    def tearDown(self):
        for n, m in self._saved.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m

    def test_stale_module_reproduces_the_live_typeerror(self):
        sys.modules["gd_story"] = _stale_gd_story()
        import gd_story as _story
        with self.assertRaises(TypeError):
            _story.record_access_answer({"state": {"access_asked": True}}, MSG, HISTORY)

    def test_redeploy_drops_stale_gd_story_and_access_answer_records(self):
        ns = _loader_namespace()
        stale = _stale_gd_story()
        sys.modules["gd_story"] = stale
        dropped = ns["_drop_changed_gd_modules"]()
        self.assertIn("gd_story", dropped)
        self.assertNotIn("gd_story", sys.modules)
        import gd_story as _story
        self.assertIsNot(_story, stale)
        rec = {"state": {"access_asked": True}}
        _story.record_access_answer(rec, MSG, HISTORY)          # the exact live call: no TypeError
        self.assertEqual(rec["state"]["access_answer"], MSG)
        self.assertTrue(_story.access_logged_reply(rec))

    def test_unchanged_files_keep_the_loaded_modules(self):
        ns = _loader_namespace()
        ns["_drop_changed_gd_modules"]()
        import gd_story
        import gd_turn
        self.assertEqual(ns["_drop_changed_gd_modules"](), [])   # an ordinary rerun reloads nothing
        self.assertIs(sys.modules["gd_story"], gd_story)
        self.assertIs(sys.modules["gd_turn"], gd_turn)

    def test_one_changed_file_drops_the_whole_stack(self):
        ns = _loader_namespace()
        ns["_drop_changed_gd_modules"]()
        import gd_story  # noqa: F401
        import gd_turn  # noqa: F401
        sys.modules["_techtrack_src_stamps"].stamps["gd_story"] = "older-deploy"
        dropped = ns["_drop_changed_gd_modules"]()
        self.assertIn("gd_story", dropped)
        self.assertIn("gd_turn", dropped)
        self.assertNotIn("gd_turn", sys.modules)

    def test_app_runs_the_guard_after_the_module_reload(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("_gdc = _reload_stale_app_modules(APP_VERSION)\n_drop_changed_gd_modules()\n", src)
        for name in NAMES[:-1]:
            self.assertTrue((ROOT / f"{name}.py").is_file(), name)


if __name__ == "__main__":
    unittest.main()
