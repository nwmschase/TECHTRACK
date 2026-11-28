"""v4.20.12 candidate (second audit, 2026-11-28): TT_STARTUP prints again when the version or commit changes (hot reload
after a push), once per change, never on a plain rerun."""
import ast
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_PATH = os.path.join(ROOT, "rv_techtrack.py")
HOLDER = "_techtrack_startup_printed"


def _load_funcs(names):
    src = open(APP_PATH, encoding="utf-8").read()
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in keep} == set(names), "startup functions missing from rv_techtrack.py"
    return ast.Module(body=keep, type_ignores=[])


class StartupLineTests(unittest.TestCase):
    def setUp(self):
        self.saved = sys.modules.pop(HOLDER, None)
        self.lines = []
        fake_errors = types.SimpleNamespace(TAG_STARTUP="TT_STARTUP",
                                            emit=lambda tag, **f: self.lines.append((tag, f["version"], f["commit"])))
        fake_turn = types.SimpleNamespace(startup_fields=lambda v, c: {"version": v, "commit": c or "unknown"})
        self.mods = {"gd_errors": fake_errors, "gd_turn": fake_turn}
        self.saved_mods = {k: sys.modules.get(k) for k in self.mods}
        sys.modules.update(self.mods)
        self.ns = {"os": os, "sys": sys, "__file__": APP_PATH, "APP_VERSION": "v1", "_git_commit": lambda: ""}
        exec(compile(_load_funcs(["_print_startup_line", "_git_commit_cheap"]), APP_PATH, "exec"), self.ns)
        self.commit = "aaaaaaa"
        self.ns["_git_commit_cheap"] = lambda: self.commit

    def tearDown(self):
        sys.modules.pop(HOLDER, None)
        if self.saved is not None:
            sys.modules[HOLDER] = self.saved
        for k, v in self.saved_mods.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def test_one_line_per_version_or_commit_change(self):
        run = self.ns["_print_startup_line"]
        run(); run(); run()                      # first start + two plain reruns
        self.assertEqual(self.lines, [("TT_STARTUP", "v1", "aaaaaaa")])
        self.ns["APP_VERSION"] = "v2"; self.commit = "bbbbbbb"   # hot reload after a push
        run(); run()
        self.assertEqual(self.lines[-1], ("TT_STARTUP", "v2", "bbbbbbb"))
        self.assertEqual(len(self.lines), 2)
        self.commit = "ccccccc"                  # new commit, same version
        run()
        self.assertEqual(len(self.lines), 3)
        self.assertEqual(self.lines[-1][2], "ccccccc")

    def test_cheap_commit_reads_this_repo(self):
        ns = {"os": os, "__file__": APP_PATH}
        exec(compile(_load_funcs(["_git_commit_cheap"]), APP_PATH, "exec"), ns)
        got = ns["_git_commit_cheap"]()
        if not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("no .git folder in this copy")
        import subprocess
        want = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()[:7]
        self.assertEqual(got, want)


class StaleTestReferenceGuard(unittest.TestCase):
    """A skipped test still has to point at real code (the TT_LIVE_PUBLIC_FETCH test called gd_official.make_web_fn for
    weeks after v4.20.9 deleted it, and the skip hid it). Every gd_X.name a test reads must exist in gd_X."""

    def test_every_gd_module_attribute_read_in_tests_exists(self):
        import glob
        import importlib
        sys.path.insert(0, ROOT)
        mods, bad = {}, []
        for f in sorted(glob.glob(os.path.join(ROOT, "tests", "*.py"))):
            tree = ast.parse(open(f, encoding="utf-8").read())
            for n in ast.walk(tree):
                if (isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and isinstance(n.value, ast.Name)
                        and n.value.id.startswith("gd_") and os.path.exists(os.path.join(ROOT, n.value.id + ".py"))):
                    m = mods.get(n.value.id) or importlib.import_module(n.value.id)
                    mods[n.value.id] = m
                    if not hasattr(m, n.attr):
                        bad.append(f"{os.path.basename(f)}:{n.lineno} {n.value.id}.{n.attr}")
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
