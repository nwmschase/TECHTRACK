"""Web lookup tool for Guided Diagnostics (branch fresh-core).

Ported from the live official-manual fetcher (gd_official.py at origin/main b1e363d / v4.19.64, which fresh-core commit
339697a deleted): the same plain-HTTP PDF download + pdftotext, and the same xAI web_search call that finds a document URL.
Chase's design is that Grok can go to the internet on its own, so this is a TOOL: no gate by the library, by the tech
asking, or by domain. The maker's own site is the usual first stop, then other reliable sources, then forums; that order
is described to Grok in gd_primer.md, it is not enforced here.

web_lookup(query) -> [gd_pages.Page]  (kind "web", source "web"), each page carrying:
    url / host        where it came from
    revision          the document's own revision text or date when one can be read, else the server's Last-Modified
    doc_id / title / page / sheet / text
The query can hold a URL (fetched directly, plain HTTP, free), words (a search finds sources first), or both (the words
rank the pages of that URL).

Search backends, in order: xAI web_search (needs XAI_API_KEY; this is the call the live app already made), then a plain
HTTP search page. Both are injectable (search_fn / http) so tests run with a mock and no network.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin, quote_plus

from gd_pages import Page

XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"
DEFAULT_SEARCH_MODEL = "grok-4.3"     # same default as gd_llm.DEFAULT_XAI_MODEL; overridden by XAI_MODEL
PAGES_PER_DOCUMENT = 8                # pages returned per web document, best-matching first (a search result size, as the library search returns 3)
TIMEOUT = 60.0
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+", re.I)
_REV_RES = (
    re.compile(r"\b(?:rev(?:ision)?|revised)\b\.?\s*[:#\-]?\s*((?:[A-Z]?\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})|(?:[A-Z][a-z]{2,8}\.?\s+\d{1,2},?\s+\d{4})|(?:[A-Z][a-z]{2,8}\.?\s+\d{4})|(?:[A-Z0-9][\w.\-]{0,10}))", re.I),
    re.compile(r"\b((?:19|20)\d{2}[-/]\d{2}[-/]\d{2})\b"),
)


def host_of(url: str) -> str:
    try:
        return (urlparse(url or "").hostname or "").lower()
    except Exception:
        return ""


def _pdf_text(data: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(data)
        f.flush()
        try:
            out = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, timeout=120)
            return out.stdout.decode("utf-8", "ignore")
        except Exception:
            return ""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self._in_title, self._skip, self.links = [], "", False, 0, []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        elif tag in ("p", "br", "li", "tr", "h1", "h2", "h3", "h4", "div"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str):
    p = _Text()
    try:
        p.feed(html or "")
    except Exception:
        pass
    text = re.sub(r"[ \t]+", " ", "".join(p.parts))
    return re.sub(r"\n\s*\n+", "\n\n", text).strip(), p.title.strip(), p.links


def find_revision(text: str, last_modified: str = "") -> str:
    """The document's own revision text when its first pages show one, else the server's Last-Modified."""
    head = text[:6000]
    for rx in _REV_RES:
        m = rx.search(head)
        if m:
            return (("Rev " if rx is _REV_RES[0] else "dated ") + m.group(1)).strip()
    return f"Last-Modified {last_modified}" if last_modified else ""


def _words(text: str) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2]


def _rank(pages: list, query_words: list) -> list:
    """Best-matching pages first (plain word counts); with no words the document's own order."""
    if not query_words:
        return list(pages)
    qs = set(query_words)

    def score(p):
        ws = _words(p.text)
        return sum(1 for w in ws if w in qs) / (len(ws) ** 0.5 + 1)
    return sorted(pages, key=lambda p: -score(p))


def fetch_pages(url: str, *, http=None, query: str = "", timeout: float = TIMEOUT, per_doc: int = PAGES_PER_DOCUMENT) -> list:
    """Download one URL (plain HTTP) and return its pages as Page objects. A PDF becomes one Page per sheet; an HTML page
    becomes one Page, and a PDF it links to is followed once when the page itself has little text."""
    import httpx

    http = http or httpx
    r = http.get(url, timeout=timeout, follow_redirects=True)
    final = str(getattr(r, "url", url) or url)
    headers = getattr(r, "headers", {}) or {}
    ctype = str(headers.get("content-type", headers.get("Content-Type", ""))).lower()
    last_mod = str(headers.get("last-modified", headers.get("Last-Modified", "")))
    content = getattr(r, "content", b"") or b""
    is_pdf = "pdf" in ctype or content[:5] == b"%PDF-" or final.lower().split("?")[0].endswith(".pdf")
    host = host_of(final)
    base = final.rstrip("/").rsplit("/", 1)[-1] or host
    did = f"web:{host}/{base}"[:120]
    qwords = _words(query)
    if is_pdf:
        sheets = [(i + 1, t) for i, t in enumerate(_pdf_text(content).split("\f")) if t.strip()]
        full = "\n".join(t for _, t in sheets[:3])
        rev = find_revision(full, last_mod)
        title = base
        pages = [Page(doc_id=did, title=title, page=str(n), sheet=n, text=t, kind="web", reason=f"web lookup: {host}",
                      source="web", url=final, revision=rev) for n, t in sheets]
        return _rank(pages, qwords)[:per_doc] if per_doc else pages
    text, title, links = html_to_text(getattr(r, "text", "") or content.decode("utf-8", "ignore"))
    rev = find_revision(text, last_mod)
    pages = []
    if text:
        pages.append(Page(doc_id=did, title=title or base, page="1", sheet=1, text=text, kind="web", reason=f"web lookup: {host}",
                          source="web", url=final, revision=rev))
    if len(text) < 1500:   # a document landing page: follow its first PDF link once
        pdfs = [urljoin(final, h) for h in links if h.lower().split("?")[0].endswith(".pdf")]
        if pdfs:
            try:
                return pages + fetch_pages(pdfs[0], http=http, query=query, timeout=timeout, per_doc=per_doc)
            except Exception:
                pass
    return pages


def xai_search(query: str, api_key: str, *, model: str = DEFAULT_SEARCH_MODEL, http=None, timeout: float = 120.0) -> list:
    """The live app's web_search call (xAI Responses API). Returns [{url, title}]. Paid per call; tests pass a mock http."""
    import httpx

    http = http or httpx
    prompt = (
        f"Find the best web sources for this RV repair lookup: {query}. "
        "Start with the maker's own site (manual PDF, bulletin, spec chart, support page); then other reliable published sources; "
        "forum posts when nothing better exists. Reply with JSON only: "
        "{\"sources\": [{\"url\": \"<direct url>\", \"title\": \"<title>\", \"kind\": \"maker|other|forum\"}]}. Up to 5 sources."
    )
    body = {"model": model, "input": [{"role": "user", "content": prompt}], "tools": [{"type": "web_search"}]}
    r = http.post(XAI_RESPONSES_URL, json=body, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"})
    data = r.json()
    text = ""
    for item in data.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                text += c.get("text", "")
    m = re.search(r"\{.*\}", text, re.S)
    try:
        found = json.loads(m.group(0)) if m else {}
    except Exception:
        found = {}
    return [{"url": s.get("url", ""), "title": s.get("title", ""), "kind": s.get("kind", "")}
            for s in (found.get("sources") or []) if isinstance(s, dict) and s.get("url")]


def http_search(query: str, *, http=None, timeout: float = TIMEOUT) -> list:
    """Plain-HTTP search page (no key, no cost). Returns [{url, title}]."""
    import httpx

    http = http or httpx
    r = http.get("https://html.duckduckgo.com/html/?q=" + quote_plus(query), timeout=timeout, follow_redirects=True,
                 headers={"User-Agent": "Mozilla/5.0 (TechTrack web lookup)"})
    out = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', getattr(r, "text", "") or "", re.S):
        href = m.group(1)
        q = re.search(r"uddg=([^&]+)", href)
        if q:
            from urllib.parse import unquote
            href = unquote(q.group(1))
        out.append({"url": href, "title": re.sub(r"<[^>]+>", "", m.group(2)).strip()})
    return out


def make_web_fn(*, secret_fn=None, http=None, search_fn=None):
    """Build the web_fn(query) -> [Page] that gd_turn.run_turn calls. search_fn(query) -> [{url, title}] replaces the
    built-in search (tests); http replaces httpx (tests). Fetched documents are cached for the life of the function.
    web_fn.last_errors lists what went wrong on the latest call, so the turn can tell Grok what the tool returned."""
    cache: dict = {}
    secret_fn = secret_fn or os.environ.get

    def web_fn(query: str) -> list:
        web_fn.last_errors = []
        query = (query or "").strip()
        urls = _URL_RE.findall(query)
        words = _URL_RE.sub(" ", query).strip()
        cands = [{"url": u.rstrip(".,;")} for u in urls]
        if not cands:
            try:
                if search_fn is not None:
                    cands = list(search_fn(query) or [])
                else:
                    key = secret_fn("XAI_API_KEY")
                    cands = []
                    if key:
                        try:
                            cands = xai_search(query, key, model=secret_fn("XAI_MODEL") or DEFAULT_SEARCH_MODEL, http=http)
                        except Exception as exc:
                            web_fn.last_errors.append(f"xAI web search failed: {exc}")
                    if not cands:
                        cands = http_search(query, http=http)
            except Exception as exc:
                web_fn.last_errors.append(f"search failed: {exc}")
        pages = []
        for c in cands:
            url = c.get("url") or ""
            if not url:
                continue
            key = (url, words)
            if key not in cache:
                try:
                    cache[key] = fetch_pages(url, http=http, query=words or query)
                except Exception as exc:
                    web_fn.last_errors.append(f"could not fetch {url}: {exc}")
                    cache[key] = []
            pages += cache[key]
        return pages

    web_fn.last_errors = []
    return web_fn
