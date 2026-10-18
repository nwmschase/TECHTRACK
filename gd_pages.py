"""Page-finder interface for Guided Diagnostics (branch fresh-core).

GD never searches or ranks pages itself. It asks a page-finder for:
  pick_manual(category, model_text, complaint, code) -> Picked   which manual(s), plus the entry pages
  entry_pages(picked)                                -> [Page]    entry page(s) + best supporting pages
  toc_pages(picked)                                  -> [Page]    the picked manuals' table-of-contents pages
  fetch_part(part, picked)                           -> [Page]    pages that test / replace / show one part

The real finder is /workspace/techtrack-fresh/library/search.py (built by another worker; never edited
from here). LibraryPageFinder adapts it. StubPageFinder is for offline tests.

Page budget: only whole pages are sent, at most PAGE_BUDGET_PAGES pages and PAGE_BUDGET_CHARS characters
per turn. Pages that do not fit are NOT silently lost: their doc + page labels are listed to the brain
as "pages not shown", so it can ask for one by name.
"""
from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass, field, asdict

LIBRARY_DIR = os.environ.get("TT_LIBRARY_DIR", "/workspace/techtrack-fresh/library")
PAGE_BUDGET_PAGES = 8
PAGE_BUDGET_CHARS = 40_000
TOC_BUDGET_CHARS = 6_000


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

    @property
    def key(self):
        return (self.doc_id, self.sheet)

    def label(self) -> str:
        return f"{self.title} ({self.doc_id}), p.{self.page}"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Page":
        return Page(**{k: d.get(k) for k in Page.__dataclass_fields__ if k in d})


@dataclass
class Picked:
    manuals: list = field(default_factory=list)   # [{doc_id, title, brand, unit_type, doc_type}]
    entry: list = field(default_factory=list)     # [Page]
    pages: list = field(default_factory=list)     # [Page] entry + supporting
    why: list = field(default_factory=list)       # the finder's own trace, shown in logs only
    code: str = ""
    raw: dict = field(default_factory=dict)       # the finder's native result (needed by fetch_part)

    @property
    def found(self) -> bool:
        return bool(self.manuals)


def apply_budget(pages, max_pages=PAGE_BUDGET_PAGES, max_chars=PAGE_BUDGET_CHARS):
    """Keep pages in the given priority order until the budget is used. Returns (kept, not_shown).
    Exact duplicates (same doc + sheet) are merged; nothing else is dropped without being listed."""
    kept, not_shown, seen, used = [], [], set(), 0
    for p in pages:
        if p.key in seen:
            continue
        seen.add(p.key)
        if len(kept) < max_pages and used + len(p.text or "") <= max_chars:
            kept.append(p)
            used += len(p.text or "")
        else:
            not_shown.append(p)
    return kept, not_shown


class StubPageFinder:
    """Offline finder for tests: a fixed library of Page objects keyed by doc. Records every call."""

    def __init__(self, manuals=None, pages=None, toc=None, parts=None):
        self.manuals = manuals or []
        self._pages = pages or []
        self._toc = toc or []
        self._parts = parts or {}
        self.calls = []

    def pick_manual(self, category, model_text, complaint="", code=None) -> Picked:
        self.calls.append(("pick_manual", category, model_text, complaint, code))
        entry = [p for p in self._pages if p.kind == "entry"]
        return Picked(manuals=list(self.manuals), entry=entry, pages=list(self._pages), code=code or "")

    def entry_pages(self, picked: Picked):
        self.calls.append(("entry_pages",))
        return list(picked.pages)

    def toc_pages(self, picked: Picked):
        self.calls.append(("toc_pages",))
        return list(self._toc)

    def fetch_part(self, part, picked: Picked):
        self.calls.append(("fetch_part", part))
        return list(self._parts.get(part, []))


class LibraryPageFinder:
    """Adapter over the fresh library's search.py (read-only).

    meaning=False runs the library with its meaning (embedding) half switched off, BM25-on-whole-words only.
    That mode exists for offline tests while the library's vectors are not built; it is not a product mode."""

    def __init__(self, library_dir=LIBRARY_DIR, meaning=True):
        if library_dir not in sys.path:
            sys.path.insert(0, library_dir)
        self.search = importlib.import_module("search")
        self.meaning = meaning
        if not meaning:
            self.search.meaning = lambda lib, query, keys: {k: 0.0 for k in keys}

    def _page(self, p: dict, kind: str) -> Page:
        return Page(doc_id=p["doc_id"], title=p["title"], page=str(p.get("printed_page") or p["pdf_sheet"]),
                    sheet=int(p["pdf_sheet"]), text=p.get("text") or "", kind=kind, reason=p.get("reason", ""))

    def pick_manual(self, category, model_text, complaint="", code=None) -> Picked:
        r = self.search.search(unit=category or None, model=model_text or None, complaint=complaint or "", code=code or None)
        n_entry = len(r.get("entry") or [])
        pages = [self._page(p, "entry" if i < n_entry else "support") for i, p in enumerate(r.get("pages") or [])]
        return Picked(manuals=r.get("manuals") or [], entry=pages[:n_entry], pages=pages,
                      why=r.get("why") or [], code=r.get("code") or "", raw={k: v for k, v in r.items() if k != "pages"})

    def entry_pages(self, picked: Picked):
        return list(picked.pages)

    def toc_pages(self, picked: Picked, max_chars=TOC_BUDGET_CHARS):
        lib = self.search._lib()
        out, used = [], 0
        for m in picked.manuals:
            for p in lib.pages(m["doc_id"]):
                if p.get("is_toc") and used + len(p["text"]) <= max_chars:
                    out.append(Page(doc_id=m["doc_id"], title=m["title"], page=str(p.get("printed_page") or p["pdf_sheet"]),
                                    sheet=int(p["pdf_sheet"]), text=p["text"], kind="toc", reason="table of contents"))
                    used += len(p["text"])
        return out

    def fetch_part(self, part, picked: Picked):
        res = self.search.fetch_by_part(part, {"manuals": picked.manuals})
        return [self._page(p, "part") for p in res]
