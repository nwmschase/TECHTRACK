"""Page type and the library page-finder adapter for Guided Diagnostics.

Page: one library or web page as Grok's tools hand it over (doc number, revision and page notes included).
LibraryPageFinder: the adapter over pagefinder/search.py and its index built from the app library. The app uses only
LibraryPageFinder(...).lib (Grok searches and reads with gd_tools over it) and doc_title().

v4.20.9 (Chase t1729u "delete"): the old manual picker (pick_manual / entry_pages / toc_pages / fetch_part, Picked,
apply_budget, and search.search / search.pick_manual / search.fetch_by_part) had no live caller since grok-search and is
deleted, with scripts/picker_sweep.py. The offline test finder (StubPageFinder) lives in tests/gd_fixtures.py.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict


@dataclass
class Page:
    doc_id: str
    title: str
    page: str            # printed page label when the manual prints one, else the PDF sheet number
    sheet: int
    text: str
    kind: str = "support"  # entry | support | part | toc | web
    reason: str = ""
    source: str = "library"  # library | web
    url: str = ""
    note: str = ""           # reviewed page note (pagefinder/doc_fixes.tsv), e.g. a misprinted page; shown with the page
    topics: str = ""         # reviewed page-topic labels (doc_fixes page_topics), e.g. 'cable sizing and voltage drop'
    doc_number: str = ""     # the library doc's number (library pages)
    revision: str = ""       # the doc's revision date (library pages) or the revision / Last-Modified read from the web document

    @property
    def host(self) -> str:
        from urllib.parse import urlparse
        try:
            return (urlparse(self.url or "").hostname or "").lower()
        except Exception:
            return ""

    @property
    def key(self):
        return (self.doc_id, self.sheet)

    def label(self) -> str:
        return f"{self.title} ({self.doc_id}), p.{self.page}"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Page":
        return Page(**{k: d[k] for k in Page.__dataclass_fields__ if k in d and d[k] is not None})




class LibraryPageFinder:
    """Adapter over the in-repo page-finder (pagefinder/search.py) and its index built from the app library.

    index_dir: pagefinder/index (index.sqlite) unless TT_PAGEFINDER_DIR says otherwise.
    app_db: the app's library DB; its documents table is the single source of truth for titles, brands, categories
            and models (docs deleted in the app leave the finder; docs added after the index build are read from the
            app's own page chunks). Default: TT_APP_DB.
    Word-match (BM25) search only: the meaning/embedding search was deleted in v4.20.13."""

    def __init__(self, index_dir=None, app_db=None):
        from pagefinder import search as _search
        self.search = _search
        if index_dir or app_db is not None:
            d = index_dir or _search.INDEX_DIR
            _search.use_library(os.path.join(d, "index.sqlite"), app_db)

    @property
    def lib(self):
        return self.search._lib()


    def doc_title(self, doc_id) -> str:
        """Title of a library doc for source lines; the doc id itself when unknown."""
        d = self.lib.docs.get(str(doc_id)) or {}
        return self.search.shown_title(d) if d.get("title") else str(doc_id)
