"""Offline test doubles for Guided Diagnostics (v4.20.9: moved out of gd_pages.py so live code carries no test-only
classes; the old picker methods pick_manual / entry_pages / toc_pages / fetch_part are gone with the picker)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class StubPageFinder:
    """Offline finder for tests: a fixed library of gd_pages.Page objects. gd_tools.GDLibraryTools.from_finder turns it
    into a gd_tools.StubLibrary (manuals, _pages, _toc, _parts are read there)."""

    def __init__(self, manuals=None, pages=None, toc=None, parts=None):
        self.manuals = manuals or []
        self._pages = pages or []
        self._toc = toc or []
        self._parts = parts or {}
        self.calls = []

    def doc_title(self, doc_id) -> str:
        """Title of a library doc for source lines; the doc id itself when unknown."""
        for m in self.manuals:
            if str(m.get("doc_id")) == str(doc_id) and m.get("title"):
                return m["title"]
        for p in self._pages:
            if str(p.doc_id) == str(doc_id) and p.title:
                return p.title
        return str(doc_id)
