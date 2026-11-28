"""v4.20.9 (Chase t1726u "what can u do to prevent it from continuously happening when we change code"): dead-code guard.

Fails when a function, method, class or top-level constant in the live code has no caller left. Live code = the root
*.py modules and pagefinder/*.py. scripts/*.py count as callers (shop tools Chase runs by hand); tests/ do NOT count, so
a path kept alive only by its own test still fails here. The scan repeats until nothing new is found, so a dead cluster
(A calls B, nobody calls A) is caught whole. Replace a path = delete the old one in the same change.

Known limit: names are matched by spelling, so a dead def that shares its name with a live one is not caught.
"""
import ast
import importlib
import pathlib
import py_compile
import sys
import unittest
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Real entry points only. Each line says who calls it. Keep this list SMALL; never add a name just to make this pass.
ALLOWED = {
    # html.parser.HTMLParser calls these by name while parsing a web page (gd_official.fetch_document).
    "gd_official.py:_Text.handle_starttag",
    "gd_official.py:_Text.handle_endtag",
    "gd_official.py:_Text.handle_data",
    # Thinking-level knob, parked by Chase t1729u item 1 ("before we go live"): kept on purpose, not wired yet.
    "gd_llm.py:GD_ASK_MAX_TOKENS",
}


def _live_files():
    return sorted(list(ROOT.glob("*.py")) + list((ROOT / "pagefinder").glob("*.py")))


def _refs(node, skip):
    out, stack = Counter(), [node]
    while stack:
        n = stack.pop()
        if id(n) in skip:
            continue
        if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Store):
            out[n.id] += 1
        elif isinstance(n, ast.Attribute):
            out[n.attr] += 1
        elif isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.isidentifier():
            out[n.value] += 1     # getattr(mod, "name"), __all__, dispatch tables keyed by name
        elif isinstance(n, ast.alias):
            out[n.name.split(".")[-1]] += 1
        stack.extend(ast.iter_child_nodes(n))
    return out


def dead_names():
    live = {p: ast.parse(p.read_text(encoding="utf-8")) for p in _live_files()}
    callers = [ast.parse(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "scripts").glob("*.py"))]
    defs = []   # (label, name, node, own-ref node or None)
    for p, tree in live.items():
        rel = p.relative_to(ROOT).as_posix()
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defs.append((f"{rel}:{n.name}", n.name, n, n))
            if isinstance(n, ast.ClassDef):
                for b in n.body:
                    if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)) and not b.name.startswith("__"):
                        defs.append((f"{rel}:{n.name}.{b.name}", b.name, b, b))
            if isinstance(n, (ast.Assign, ast.AnnAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                for t in targets:
                    if isinstance(t, ast.Name) and not t.id.startswith("__"):
                        defs.append((f"{rel}:{t.id}", t.id, n, None))
    dead = set()
    while True:
        skip = {id(node) for label, _n, node, _o in defs if label in dead and not isinstance(node, (ast.Assign, ast.AnnAssign))}
        total = Counter()
        for tree in list(live.values()) + callers:
            total.update(_refs(tree, skip))
        new = set()
        for label, name, node, own in defs:
            if label in dead:
                continue
            self_refs = _refs(own, set())[name] if own is not None and not isinstance(own, ast.ClassDef) else 0
            if total[name] - self_refs <= 0:
                new.add(label)
        if not new:
            return dead
        dead |= new


class TestNoDeadCode(unittest.TestCase):
    def test_every_live_def_has_a_caller(self):
        found = dead_names() - ALLOWED
        self.assertEqual(sorted(found), [], "no caller left: delete it in this change (tests do not count as callers)")

    def test_allowlist_has_no_stale_lines(self):
        """An allowlist line whose name is gone or now has a caller must be removed."""
        self.assertEqual(sorted(ALLOWED - dead_names()), [])

    def test_allowlist_stays_small(self):
        self.assertLessEqual(len(ALLOWED), 6)


class TestLiveModulesLoad(unittest.TestCase):
    def test_every_live_file_compiles(self):
        for p in _live_files() + sorted((ROOT / "scripts").glob("*.py")):
            py_compile.compile(str(p), doraise=True)

    def test_gd_path_modules_import(self):
        for name in ("gd_errors", "gd_llm", "gd_state", "gd_story", "gd_sends", "gd_turn", "gd_tools", "gd_pages",
                     "gd_page_links", "gd_official", "gd_prompt", "gd_step_photo", "gd_work_orders", "gd_picture",
                     "pagefinder.search", "pagefinder.terms", "pagefinder.doc_fixes"):
            importlib.import_module(name)


if __name__ == "__main__":
    unittest.main()
