"""v4.19.63: GD finds the Thetford manual with no Category, no Model, and Unity 'Not sure'.

Live v4.19.62 (Oct 14 10:29 PT): the GD default Unity gate 'Not sure' turned on the
Unity context, so search_manual_chunks with no Category looked only in Electrical /
Reference. The Thetford manual is in Plumbing / Toilets, the brand filter kept
nothing, and GD replied 'No Thetford document in the shop library for this unit.'
The Bay path passes no Unity gate, so the Bay PDF found the same manual.

Does not import rv_techtrack: the search function and its ORM models are loaded
from the source into an in-memory SQLite library.
"""
import ast
import json
import math
import os
import re
import unittest
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

import gd_library_coach

ROOT = Path(__file__).resolve().parents[1]
MSG = "Thetford Aqua-Magic toilet leaks water at the pedal when flushing."


def _load_search():
    tree = ast.parse((ROOT / "rv_techtrack.py").read_text(encoding="utf-8"))
    byname = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            byname[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    byname[target.id] = node
    ns = {"__name__": "rv_slice", "Base": declarative_base(), "_gdc": gd_library_coach,
          "relationship": relationship, "datetime": datetime, "re": re, "json": json,
          "math": math, "os": os}
    for name in dir(sa):
        ns.setdefault(name, getattr(sa, name))

    def run(names):
        exec(compile(ast.Module(body=[byname[n] for n in names], type_ignores=[]), "rv_slice", "exec"), ns)

    run(["User", "Category", "Document", "DocChunk", "search_manual_chunks"])
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id.endswith("_CATEGORY") for t in node.targets
        ):
            exec(compile(ast.Module(body=[node], type_ignores=[]), "rv_slice", "exec"), ns)
    engine = sa.create_engine("sqlite://")
    ns["Base"].metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    ns["session"] = session
    cat, doc, chunk = ns["Category"], ns["Document"], ns["DocChunk"]
    elec, toilets = cat(name="Electrical"), cat(name="Plumbing / Toilets")
    session.add_all([elec, toilets])
    session.flush()
    unity = doc(category_id=elec.id, title="Lippert OneControl Unity Electrical SM",
                file_path="documents/unity.pdf", keywords="Lippert, Unity")
    thetford = doc(category_id=toilets.id, title="Thetford Style II OM Permanent RV Toilet 42088",
                   file_path="documents/42088.pdf", keywords="Thetford, Style II, Plumbing / Toilets, 42088")
    session.add_all([unity, thetford])
    session.flush()
    session.add_all([
        chunk(document_id=unity.id, category_id=elec.id, title=unity.title, page=3,
              chunk_text="Unity board relay outputs and the water pump circuit."),
        chunk(document_id=thetford.id, category_id=toilets.id, title=thetford.title, page=3,
              chunk_text="Water leaking at the pedal when flushing: check the water valve and the supply connection."),
    ])
    session.commit()

    def search(**kwargs):
        for _ in range(100):
            try:
                return ns["search_manual_chunks"](None, "", MSG, limit=8, **kwargs)
            except NameError as exc:
                name = str(exc).split("'")[1]
                if hasattr(gd_library_coach, name):
                    ns[name] = getattr(gd_library_coach, name)
                elif name in byname:
                    run([name])
                else:
                    raise
        raise AssertionError("search_manual_chunks did not load")

    return search


class TestGdThetfordUnityNotSure(unittest.TestCase):
    def test_unity_not_sure_still_finds_the_thetford_manual_with_no_category(self):
        search = _load_search()
        hits = search(unity_context=True)
        titles = [c.title for c in hits]
        self.assertIn("Thetford Style II OM Permanent RV Toilet 42088", titles)
        self.assertNotIn("Lippert OneControl Unity Electrical SM", titles)

    def test_without_unity_the_result_is_the_same_manual(self):
        search = _load_search()
        hits = search(unity_context=False)
        self.assertEqual([c.title for c in hits], ["Thetford Style II OM Permanent RV Toilet 42088"])


if __name__ == "__main__":
    unittest.main()
