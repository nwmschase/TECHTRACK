"""Library tools Grok calls itself during a Guided Diagnostics turn (branch grok-search, Chase 2026-10-22 / 2026-10-24).

Grok picks the manual and the pages. These tools only look things up and hand back what they find; nothing here picks,
locks, boosts or filters for Grok. They run in our code against the local library (the same pagefinder index + app
library DB that gd_pages uses), so they cost nothing per call.

  find_documents(brand?, model?, unit_type?, words?)        documents with doc_id, title, brand, models, kind, revision, pages
  table_of_contents(doc_id)                                 the doc's contents pages plus a page-by-page outline of its labels
  search_pages(words, doc_ids?, brand?, unit_type?, limit?) page hits: doc, printed page, sheet, labels and a short snippet,
                                                            ordered by match only (one score for every page, each hit labeled
                                                            with its own doc and brand; no tier or picked-manual boost)
  read_pages(doc_id, pages?, sheets?)                       whole pages: full text, page topics / picture labels, page notes
                                                            (DOC DEFECT ...), the doc's number, revision and note
  open_web_document(url, words?)                            a document URL Grok found with its web search, fetched over plain
                                                            HTTP (free; PDF text per sheet, with the revision read from it)

The internet search itself is xAI's built-in web_search tool, which runs inside Grok's own call (gd_llm.respond); it is
listed in TOOL_SPECS so the Responses API runs it server-side.

Matching reuses the page-finder's own word normalisation, RV term families, BM25 and (when on) the meaning vectors
(pagefinder/search.py: hybrid, bm25, model_score, covers_unit). Page topics and picture labels are part of each page's
searchable words (search.Library._page_row). Contents and cover pages count 0.3 in search_pages, the same weight the
page-finder gives them, since table_of_contents returns them directly.
"""
from __future__ import annotations

import collections
import json
import re
import sqlite3

from gd_pages import Page

SNIPPET_CHARS = 320
TOC_PAGE_CHARS = 2000
LABEL_CHARS = 240          # page-topic labels shown with a search hit or an outline row (read_pages gives them whole)      # a contents page is titles; a longer one is cut here (read_pages opens it whole)
# One read_pages request opens up to this many pages (Chase 2026-10-24: keep it). Pages asked for past it are not opened;
# the result tells Grok which ones, so it can ask again in another read. The primer states this number.
READ_MAX_PAGES = 10
RANGE_MAX_PAGES = READ_MAX_PAGES   # older name
RANGE_EXPAND_MAX = 2000    # a range is expanded into page labels up to this span (guards '1-999999'); longer is taken as typed
# No tool returns a whole document's text: find_documents / table_of_contents / search_pages return titles, labels and
# short snippets; read_pages and open_web_document return the pages asked for (Chase 2026-10-24).
DEFAULT_HITS = 8
DEFAULT_DOCS = 15

# ---------------------------------------------------------------- tool specs (xAI Responses API shapes)
# Function tools: {"type": "function", "name", "description", "parameters"} - docs.x.ai/developers/tools/function-calling
# Built-in web search: {"type": "web_search"} - docs.x.ai/developers/tools/web-search
_STR = {"type": "string"}
FUNCTION_SPECS = [
    {"type": "function", "name": "find_documents",
     "description": "List library documents that match a maker, a model, a unit type and/or words (title, keywords, page "
                    "text). Each result has doc_id, title, brand, other brand names, unit type, kind (doc type and source "
                    "type), models, document number, revision date, page count and why it matched.",
     "parameters": {"type": "object", "properties": {
         "brand": {"type": "string", "description": "Maker name as the tech or the plate gives it, e.g. Suburban, Furrion, Atwood"},
         "model": {"type": "string", "description": "Model number or model words, e.g. NT-20SEQT, FCR08DCGTA, GC10A-4E"},
         "unit_type": {"type": "string", "description": "Library category, e.g. Furnaces, Refrigerators, Water Heaters, Air Conditioning"},
         "words": {"type": "string", "description": "Any words: a part, a symptom, a code, a document title"},
         "limit": {"type": "integer", "description": "How many documents to list (default 15)"}}}},
    {"type": "function", "name": "table_of_contents",
     "description": "One document's contents pages (whole text) and an outline of every page: printed page, sheet, page "
                    "marks and page-topic / picture labels.",
     "parameters": {"type": "object", "properties": {"doc_id": {"type": "string"}}, "required": ["doc_id"]}},
    {"type": "function", "name": "search_pages",
     "description": "Search library pages by words (part names, fault codes, symptoms, page-topic or picture-label words). "
                    "Optional doc_ids, brand and unit_type narrow the pages searched. Hits come back ordered by how well "
                    "the page matches the words, each with its own doc_id, title, brand, printed page, sheet, labels, "
                    "page note and a short snippet.",
     "parameters": {"type": "object", "properties": {
         "words": {"type": "string"},
         "doc_ids": {"type": "array", "items": {"type": "string"}},
         "brand": _STR, "unit_type": _STR,
         "limit": {"type": "integer", "description": "How many hits (default 8)"}}, "required": ["words"]}},
    {"type": "function", "name": "read_pages",
     "description": "Open whole pages of one document: full text, page topics and picture labels, page notes (DOC DEFECT, "
                    "MISPRINTED PAGE, NEEDS OCR), the document number, revision and document note. The app also sends the "
                    "opened pages as page images (drawn from the PDF) in a message right after the result, picture-labelled "
                    "pages first. pages are printed page "
                    "numbers as the manual prints them; sheets are PDF sheet numbers. One read opens up to 10 pages; when more are "
                    "asked for, the result names the pages left for another read.",
     "parameters": {"type": "object", "properties": {
         "doc_id": {"type": "string"},
         "pages": {"type": "array", "items": {"type": "string"}, "description": "Printed pages, e.g. [\"27\", \"29-31\"]"},
         "sheets": {"type": "array", "items": {"type": "integer"}}}, "required": ["doc_id"]}},
    {"type": "function", "name": "open_web_document",
     "description": "Fetch one web document by URL (for example a maker's PDF manual found with the web search) and return "
                    "its pages best matching the words first, each with its source address, host and the revision read "
                    "from the document.",
     "parameters": {"type": "object", "properties": {"url": _STR, "words": _STR}, "required": ["url"]}},
]
# Image search and image understanding on (Chase 2026-11-27, test1): Grok can find a real photo and put it in the reply as
# a Markdown image (docs.x.ai web-search: enable_image_search), and look at images on the pages it browses
# (enable_image_understanding, view_image: billed as image tokens). Image search is billed as a normal web search.
WEB_SEARCH_SPEC = {"type": "web_search", "enable_image_search": True, "enable_image_understanding": True}
TOOL_SPECS = FUNCTION_SPECS + [WEB_SEARCH_SPEC]
FUNCTION_NAMES = tuple(t["name"] for t in FUNCTION_SPECS)


# ---------------------------------------------------------------- helpers
def _phrase(text):
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _unit_key(text):
    """A unit type / category compared without spaces, dashes, case or a plural s: Slide-outs = Slide Outs = Slideouts."""
    return _phrase(text).replace(" ", "").rstrip("s")


def _marks(p):
    return [m[3:] for m in ("is_toc", "is_cover", "is_safety", "is_parts", "is_fault_codes", "is_troubleshooting", "is_wiring")
            if p.get(m)]


def _models(d):
    try:
        return list(json.loads(d.get("models") or "[]"))
    except (TypeError, ValueError):
        return []


def _snippet(text, words, n=SNIPPET_CHARS):
    """The stretch of the page text that holds the most of the search words (plain word hits)."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= n:
        return text
    ws = [w for w in re.findall(r"[a-z0-9]+", (words or "").lower()) if len(w) > 1]
    if not ws:
        return text[:n]
    low = text.lower()
    best, at = -1, 0
    for i in range(0, max(1, len(text) - n // 2), max(40, n // 4)):
        win = low[i:i + n]
        s = sum(win.count(w) for w in ws)
        if s > best:
            best, at = s, i
    return ("..." if at else "") + text[at:at + n].strip() + ("..." if at + n < len(text) else "")


def _cut(text, n):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + " ..."


def _spans(labels):
    """['1','2','3','7','A-1'] -> '1-3, 7, A-1' (runs of whole numbers joined)."""
    out, run = [], []
    def flush():
        if run:
            out.append(run[0] if len(run) == 1 else f"{run[0]}-{run[-1]}")
            run.clear()
    for x in labels:
        if run and x.isdigit() and run[-1].isdigit() and int(x) == int(run[-1]) + 1:
            run.append(x)
        else:
            flush()
            run.append(x)
    flush()
    return ", ".join(out)


def _page_list(spec):
    """['27', '29-31', 5] -> ['27', '29', '30', '31', '5'] (as strings)."""
    out = []
    for x in spec or []:
        s = str(x).strip()
        m = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", s)
        if m and 0 <= int(m.group(2)) - int(m.group(1)) < RANGE_EXPAND_MAX:
            out += [str(i) for i in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif s:
            out += [t for t in re.split(r"\s*,\s*", s) if t]
    return out


# ---------------------------------------------------------------- the tools
class LibraryTools:
    """The library tools over one pagefinder Library (lib.docs + lib.pages(doc_id)).

    lib: pagefinder.search.Library (or StubLibrary in tests). keywords: {doc_id: keyword text} from the app DB's
    documents.keywords (read once, read-only); title_fn(doc) -> the title as GD shows it (shop sheets labeled)."""

    def __init__(self, lib, keywords=None, web_fetch=None):
        from pagefinder import search as _s
        self.s = _s
        self.lib = lib
        self.keywords = dict(keywords or {})
        self.web_fetch = web_fetch            # (url, words) -> [Page]; default gd_official.fetch_pages (plain HTTP)
        self.last_read = {}
        self._label_tf = None
        self.last_dropped = []
        self.last_search_pages = False

    @classmethod
    def for_finder(cls, finder, web_fetch=None):
        """Tools over the same library a gd_pages finder uses (LibraryPageFinder.lib, or a StubPageFinder's pages)."""
        if hasattr(finder, "search") and hasattr(finder, "lib"):
            lib = finder.lib
            return cls(lib, keywords=_app_keywords(getattr(lib, "app_db", "")), web_fetch=web_fetch)
        return cls(StubLibrary.from_finder(finder), web_fetch=web_fetch)

    # -- doc helpers (also used by the turn log)
    def doc_brand(self, doc_id):
        d = self.lib.docs.get(str(doc_id)) or {}
        return d.get("brand") or ""

    def doc_brand_names(self, doc_id):
        d = self.lib.docs.get(str(doc_id)) or {}
        return {_phrase(d.get("brand"))} | {_phrase(x) for x in (d.get("also_brands_l") or ())} - {""}

    def unit_brands(self, model_text):
        """Maker names from the library's own brand list that appear as whole words in what the tech typed (log only)."""
        t = " " + _phrase(model_text) + " "
        names = set()
        for d in self.lib.docs.values():
            for n in {_phrase(d.get("brand"))} | {_phrase(x) for x in (d.get("also_brands_l") or ())}:
                if n and f" {n} " in t:
                    names.add(n)
        return names

    def _title(self, d):
        try:
            return self.s.shown_title(d)
        except Exception:
            return d.get("title") or d["doc_id"]

    def _doc_card(self, d, why=""):
        models = _models(d)
        card = {"doc_id": d["doc_id"], "title": self._title(d), "brand": d.get("brand") or "",
                "other_brand_names": sorted(d.get("also_brands_l") or []), "unit_type": d.get("unit_type") or "",
                "kind": d.get("doc_type") or "", "source_type": d.get("source_type") or "oem",
                "models": models, "doc_number": d.get("doc_number") or "", "revision": d.get("revision_date") or "",
                "pages": int(d.get("n_pages") or len(self.lib.pages(d["doc_id"])) or 0)}
        if d.get("doc_note"):
            card["doc_note"] = d["doc_note"]
        if why:
            card["matched"] = why
        return card

    def _brand_ok(self, d, brand):
        b = _phrase(brand)
        if not b:
            return True
        names = {_phrase(d.get("brand"))} | {_phrase(x) for x in (d.get("also_brands_l") or ())}
        if b in names or b.replace(" ", "") in {n.replace(" ", "") for n in names}:
            return True
        pl = _phrase(d.get("product_line"))
        return bool(pl) and (pl == b)

    def _unit_ok(self, d, unit_type):
        # Spaces, dashes, case and a plural s are ignored, as _brand_ok does for brands (Chase 2026-11-27, test3: Grok sent
        # "Slide-outs" and the library category is "Slideouts", so every slide-out manual was filtered out).
        u = _unit_key(unit_type)
        if not u:
            return True
        uts = [d.get("unit_type") or ""] + [x.strip() for x in str(d.get("also_unit_types") or "").split(",") if x.strip()]
        uts += sorted(d.get("title_units") or [])
        return any(_unit_key(x) == u for x in uts)

    def _docs(self, brand=None, unit_type=None, doc_ids=None):
        out = []
        ids = {str(x) for x in doc_ids} if doc_ids else None
        for d in self.lib.docs.values():
            if ids is not None and d["doc_id"] not in ids:
                continue
            if self._brand_ok(d, brand) and self._unit_ok(d, unit_type):
                out.append(d)
        return out

    def _labels(self):
        """Per doc: the searchable label words (title, alt titles, brand, product line, models, doc number, keywords)."""
        if self._label_tf is None:   # built whole, then published, so a half-built dict is never seen
            built = {}
            for k, d in list(self.lib.docs.items()):
                txt = " ".join([d.get("title") or "", " ".join(json.loads(d.get("alt_titles") or "[]") if d.get("alt_titles") else []),
                                d.get("brand") or "", d.get("product_line") or "", " ".join(_models(d)),
                                d.get("doc_number") or "", self.keywords.get(k, "")])
                tf = collections.Counter(self.s.tokens(txt))
                built[k] = (tf, sum(tf.values()))
            self._label_tf = built
        return self._label_tf

    # -- find_documents
    def find_documents(self, brand=None, model=None, unit_type=None, words=None, limit=None):
        limit = int(limit or DEFAULT_DOCS)
        cand = self._docs(brand=brand, unit_type=unit_type)
        widened = ""
        # Filters that leave nothing never return an empty list: drop the unit type (keep the maker), then both, and score
        # the model / words across what is left (Chase 2026-11-27, test3: an empty result read as "the library has nothing").
        if not cand and unit_type:
            cand = self._docs(brand=brand)
            widened = f"no document has unit type {unit_type!r}" + ("; listed by maker and words instead" if brand else "; listed by words instead")
        if not cand and brand:
            cand = self._docs()
            widened = (widened + "; " if widened else "") + f"no document matches maker {brand!r}; listed across the whole library"
        ms = {}
        if model:
            q_models = list(dict.fromkeys(n for n in (self.s.nmodel(t) for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-/\.]*", model))
                                          if len(n) >= 3 and re.search(r"\d", n)))
            qwords = self.s.mwords(model)
            for d in cand:
                try:
                    ms[d["doc_id"]] = self.s.model_score(d, q_models, qwords)
                except Exception:
                    ms[d["doc_id"]] = (0, 0)
        ws = {}
        if words:
            q = self.s.query_terms(words)
            lab = self._labels()
            a = self.s.bm25(q, [(d["doc_id"], lab[d["doc_id"]][0], lab[d["doc_id"]][1]) for d in cand])
            dtf = self.lib.doc_tf()
            b = self.s.bm25(q, [(d["doc_id"], dtf[d["doc_id"]][0], dtf[d["doc_id"]][1]) for d in cand], b=0.3)
            amax, bmax = max(a.values() or [0]) or 1.0, max(b.values() or [0]) or 1.0
            ws = {k: 0.5 * a.get(k, 0) / amax + 0.5 * b.get(k, 0) / bmax for k in a}
        if model:
            hit = [d for d in cand if ms.get(d["doc_id"], (0, 0)) != (0, 0)]
            cand = hit or cand
        if words and not model:
            cand = [d for d in cand if ws.get(d["doc_id"], 0) > 0] or cand
        cand.sort(key=lambda d: (-ms.get(d["doc_id"], (0, 0))[0], -ms.get(d["doc_id"], (0, 0))[1], -ws.get(d["doc_id"], 0), d["doc_id"]))

        def why(d):
            bits = []
            t, tw = ms.get(d["doc_id"], (0, 0))
            if t >= 1000:
                bits.append("model tag")
            elif t >= 500:
                bits.append("model printed in the page text")
            elif t:
                bits.append("model tag shares the model's start")
            if tw:
                bits.append(f"{tw} model word(s) in the title")
            if ws.get(d["doc_id"]):
                bits.append(f"words {ws[d['doc_id']]:.2f}")
            return "; ".join(bits)
        out = {"documents": [self._doc_card(d, why(d)) for d in cand[:limit]], "total": len(cand),
               "filters": {k: v for k, v in (("brand", brand), ("model", model), ("unit_type", unit_type), ("words", words)) if v}}
        if widened:
            out["filters_widened"] = widened
        return out

    # -- table_of_contents
    def table_of_contents(self, doc_id):
        d = self.lib.docs.get(str(doc_id))
        if not d:
            return {"error": f"no document {doc_id} in the library"}
        pages = self.lib.pages(d["doc_id"])
        toc = []
        for p in pages:
            if p.get("is_toc"):
                t = re.sub(r"[ \t]+", " ", p.get("text") or "").strip()
                row = {"page": str(p.get("printed_page") or p["pdf_sheet"]), "sheet": int(p["pdf_sheet"]), "text": t[:TOC_PAGE_CHARS]}
                if len(t) > TOC_PAGE_CHARS:
                    row["text_cut"] = f"first {TOC_PAGE_CHARS} of {len(t)} characters; read_pages opens the whole page"
                toc.append(row)
        outline = []
        for p in pages:
            row = {"page": str(p.get("printed_page") or p["pdf_sheet"]), "sheet": int(p["pdf_sheet"])}
            if _marks(p):
                row["marks"] = _marks(p)
            if p.get("topics"):
                row["topics"] = _cut(p["topics"], LABEL_CHARS)
            first = next((ln.strip() for ln in (p.get("text") or "").splitlines() if len(ln.strip()) > 3), "")
            row["first_line"] = first[:70]
            outline.append(row)
        return {"document": self._doc_card(d), "contents_pages": toc, "outline": outline}

    # -- search_pages
    def search_pages(self, words, doc_ids=None, brand=None, unit_type=None, limit=None):
        self.last_search_pages = True
        limit = int(limit or DEFAULT_HITS)
        words = (words or "").strip()
        if not words:
            return {"error": "search_pages needs words"}
        docs = self._docs(brand=brand, unit_type=unit_type, doc_ids=doc_ids)
        pages = [p for d in docs for p in self.lib.pages(d["doc_id"]) if p.get("len")]
        if not pages:
            return {"hits": [], "pages_searched": 0, "documents_searched": len(docs)}
        hs = self.s.hybrid(self.lib, words, pages)
        key = lambda p: (p["doc_id"], p["pdf_sheet"])
        kw = self.s.kind_weights(docs)   # v4.20.0: diagnosis docs ahead of user / install / spec sheets of the same unit
        sc = {key(p): hs.get(key(p), 0.0) * (0.3 if p.get("is_toc") or p.get("is_cover") else 1.0) * kw.get(p["doc_id"], 1.0)
              for p in pages}
        ranked = sorted((p for p in pages if sc[key(p)] > 0), key=lambda p: (-sc[key(p)], p["doc_id"], p["pdf_sheet"]))
        hits = []
        for p in ranked[:limit]:
            d = self.lib.docs[p["doc_id"]]
            h = {"doc_id": p["doc_id"], "title": self._title(d), "brand": d.get("brand") or "", "unit_type": d.get("unit_type") or "",
                 "kind": d.get("doc_type") or "", "page": str(p.get("printed_page") or p["pdf_sheet"]), "sheet": int(p["pdf_sheet"]),
                 "score": round(sc[key(p)], 3), "snippet": _snippet(p.get("text"), words)}
            if _marks(p):
                h["marks"] = _marks(p)
            if p.get("topics"):
                h["topics"] = _cut(p["topics"], LABEL_CHARS)
            note = self._page_note(d, p)
            if note:
                h["page_note"] = note
            hits.append(h)
        return {"hits": hits, "matching_pages": len(ranked), "pages_searched": len(pages), "documents_searched": len(docs)}

    def _page_note(self, d, p):
        try:
            from pagefinder import doc_fixes
            return doc_fixes.page_fix(d["doc_id"], d.get("file_path"), p["pdf_sheet"]).get("page_note", "") or ""
        except Exception:
            return p.get("note") or ""

    # -- read_pages
    def read_pages(self, doc_id, pages=None, sheets=None, max_pages=None):
        """Returns (result dict for Grok, [gd_pages.Page] read).
        One request opens up to READ_MAX_PAGES pages, in the order asked; the result says plainly which pages were left for
        another read ("limit"). max_pages: the app-side backstop (gd_turn MAX_PAGES_READ_PER_TURN, never shown to Grok);
        pages past it are left out quietly and listed in self.last_dropped. self.last_read records requested / served."""
        d = self.lib.docs.get(str(doc_id))
        if not d:
            return {"error": f"no document {doc_id} in the library"}, []
        rows = self.lib.pages(d["doc_id"])
        by_sheet = {int(p["pdf_sheet"]): p for p in rows}
        by_label = collections.defaultdict(list)   # the page label every tool shows: printed page, else the sheet
        for p in rows:
            by_label[str(p.get("printed_page") or p["pdf_sheet"])].append(p)
        want, missing = [], []
        for x in _page_list(pages):
            got = by_label.get(x, [])
            if got:
                want += got
            else:
                missing.append(f"page {x}")
        for s in sheets or []:
            try:
                want.append(by_sheet[int(s)])
            except (KeyError, ValueError, TypeError):
                missing.append(f"sheet {s}")
        seen, uniq, out, objs = set(), [], [], []
        for p in want:
            if p["pdf_sheet"] not in seen:
                seen.add(p["pdf_sheet"])
                uniq.append(p)
        lab = lambda p: str(p.get("printed_page") or p["pdf_sheet"])
        cut = uniq[READ_MAX_PAGES:]
        uniq = uniq[:READ_MAX_PAGES]
        self.last_read = {"requested": len(uniq) + len(cut), "served": 0, "range_cut": [lab(p) for p in cut],
                          "not_found": len(missing)}
        for p in uniq:
            if max_pages is not None and len(out) >= max_pages:
                self.last_dropped.append(f"{d['doc_id']} sheet {p['pdf_sheet']}")
                continue
            note = self._page_note(d, p)
            r = {"page": str(p.get("printed_page") or p["pdf_sheet"]), "sheet": int(p["pdf_sheet"]), "text": p.get("text") or ""}
            if _marks(p):
                r["marks"] = _marks(p)
            if p.get("topics"):
                r["topics"] = p["topics"]
            if note:
                r["page_note"] = note
            out.append(r)
            objs.append(Page(doc_id=d["doc_id"], title=self._title(d), page=r["page"], sheet=r["sheet"], text=r["text"], kind="read",
                             reason="read by Grok", note=note, topics=p.get("topics") or "", doc_number=d.get("doc_number") or "",
                             revision=d.get("revision_date") or ""))
        self.last_read["served"] = len(out)
        res = {"document": self._doc_card(d), "pages": out}
        if cut:
            n = len(uniq) + len(cut)
            res["limit"] = (f"pages {_spans([lab(p) for p in uniq])} of the {n} requested are here; one read opens up to "
                            f"{READ_MAX_PAGES} pages. Ask again for the rest: {_spans([lab(p) for p in cut])}")
            res["not_opened_yet"] = [lab(p) for p in cut]
        if missing:
            printed = sorted({str(p.get("printed_page")) for p in rows if p.get("printed_page") not in (None, "")}, key=lambda v: (len(v), v))
            res["not_found"] = missing
            res["document_has"] = {"sheets": f"1-{max(by_sheet) if by_sheet else 0}",
                                   "printed_pages": (printed[0] + "-" + printed[-1]) if printed else "none printed"}
        return res, objs

    # -- open_web_document
    def open_web_document(self, url, words=None, max_pages=None):
        url = (url or "").strip()
        if not re.match(r"https?://", url, re.I):
            return {"error": "open_web_document needs a full http(s) URL"}, []
        fetch = self.web_fetch
        if fetch is None:
            import gd_official
            fetch = lambda u, w: gd_official.fetch_pages(u, query=w or "")
        try:
            got = list(fetch(url, words or "") or [])
        except Exception as exc:
            return {"error": f"could not fetch {url}: {exc}"}, []
        self.last_read = {"requested": len(got), "served": min(len(got), max_pages) if max_pages is not None else len(got),
                          "range_cut": [], "not_found": 0}
        if max_pages is not None and len(got) > max_pages:
            self.last_dropped += [f"{url} page {p.page}" for p in got[max_pages:]]
            got = got[:max_pages]
        res = {"url": url, "pages": [{"page": p.page, "sheet": p.sheet, "title": p.title, "host": p.host, "url": p.url,
                                      "revision": p.revision, "text": p.text} for p in got]}
        if not got:
            res["note"] = "the document came back with no readable text"
        return res, got

    # -- dispatcher
    def call(self, name, arguments, max_pages=None):
        """Run one function call. Returns (output text for Grok, [Page] read, error or ''). max_pages: pages this call may
        still return under the app-side backstop (None = off); what it left out is in self.last_dropped."""
        self.last_dropped = []
        self.last_read = {}
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
            if not isinstance(args, dict):
                raise ValueError("arguments are not a JSON object")
        except ValueError as exc:
            return json.dumps({"error": f"bad arguments: {exc}"}), [], f"bad arguments for {name}"
        pages = []
        try:
            if name == "find_documents":
                res = self.find_documents(**_only(args, "brand", "model", "unit_type", "words", "limit"))
            elif name == "table_of_contents":
                res = self.table_of_contents(args.get("doc_id"))
            elif name == "search_pages":
                res = self.search_pages(**_only(args, "words", "doc_ids", "brand", "unit_type", "limit"))
            elif name == "read_pages":
                res, pages = self.read_pages(**_only(args, "doc_id", "pages", "sheets"), max_pages=max_pages)
            elif name == "open_web_document":
                res, pages = self.open_web_document(**_only(args, "url", "words"), max_pages=max_pages)
            else:
                return json.dumps({"error": f"unknown tool {name}"}), [], f"unknown tool {name}"
        except Exception as exc:   # a tool fault is reported to Grok as what came back, never raised into the turn
            return json.dumps({"error": f"{type(exc).__name__}: {exc}"}), [], f"{name} failed: {exc}"
        return json.dumps(res, ensure_ascii=False, default=str), pages, (res.get("error", "") if isinstance(res, dict) else "")


def _only(args, *names):
    return {k: args[k] for k in names if k in args and args[k] not in (None, "")}


def _app_keywords(app_db):
    """{'L<id>': keywords} from the app library's documents table (read-only). Empty when there is no app DB."""
    if not app_db:
        return {}
    try:
        c = sqlite3.connect(f"file:{app_db}?mode=ro", uri=True)
        try:
            return {f"L{i}": k or "" for i, k in c.execute("select id, keywords from documents")}
        finally:
            c.close()
    except sqlite3.Error:
        return {}


# ---------------------------------------------------------------- offline stand-in for tests
class StubLibrary:
    """A tiny Library built from gd_pages Page objects (offline tests): .docs, .pages(doc_id), .doc_tf()."""

    def __init__(self, docs, pages):
        from pagefinder import search as _s
        self.docs, self._pages, self._doc_tf = {}, collections.defaultdict(list), None
        for m in docs:
            d = {"doc_id": str(m["doc_id"]), "title": m.get("title") or str(m["doc_id"]), "brand": m.get("brand") or "",
                 "unit_type": m.get("unit_type") or "", "doc_type": m.get("doc_type") or "", "models": json.dumps(m.get("models") or []),
                 "doc_number": m.get("doc_number") or "", "revision_date": m.get("revision") or "", "source_type": m.get("source_type") or "oem",
                 "doc_note": m.get("note") or "", "also_brands_l": {b.lower() for b in m.get("also_brands") or []},
                 "product_line": "", "alt_titles": "[]", "page_models_n": set(), "file_path": ""}
            d["models_n"] = [_s.nmodel(x) for x in m.get("models") or [] if len(_s.nmodel(x)) >= 3]
            self.docs[d["doc_id"]] = d
        for p in pages:
            if p.doc_id not in self.docs:
                self.docs[p.doc_id] = {"doc_id": p.doc_id, "title": p.title, "brand": "", "unit_type": "", "doc_type": "", "models": "[]",
                                       "doc_number": p.doc_number, "revision_date": p.revision, "source_type": "oem", "doc_note": "",
                                       "also_brands_l": set(), "product_line": "", "alt_titles": "[]", "page_models_n": set(),
                                       "models_n": [], "file_path": ""}
            if any(r["pdf_sheet"] == p.sheet for r in self._pages[p.doc_id]):
                continue
            self._pages[p.doc_id].append(_s.Library._page_row({
                "doc_id": p.doc_id, "pdf_sheet": p.sheet, "printed_page": p.page, "text": p.text, "topics": p.topics, "note": p.note,
                "codes": [], "is_toc": int(p.kind == "toc"), "is_cover": 0, "is_safety": 0, "is_parts": 0, "is_fault_codes": 0,
                "is_troubleshooting": int(p.kind == "entry"), "is_wiring": 0}))
        for k in self._pages:
            self._pages[k].sort(key=lambda r: r["pdf_sheet"])
            self.docs[k]["n_pages"] = len(self._pages[k])

    @classmethod
    def from_finder(cls, f):
        pages = list(getattr(f, "_pages", []) or []) + list(getattr(f, "_toc", []) or [])
        for v in (getattr(f, "_parts", {}) or {}).values():
            pages += list(v)
        return cls(list(getattr(f, "manuals", []) or []), pages)

    def pages(self, doc_id):
        return self._pages.get(doc_id, [])

    def doc_tf(self):
        if self._doc_tf is None:   # built whole, then published (same as pagefinder Library.doc_tf)
            built = {}
            for k in list(self.docs):
                tf = collections.Counter()
                for p in self.pages(k):
                    tf.update(p["tf"])
                built[k] = (tf, sum(tf.values()))
            self._doc_tf = built
        return self._doc_tf
