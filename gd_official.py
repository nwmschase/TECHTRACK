"""Web document fetch for Guided Diagnostics: open_web_document (gd_tools) opens a URL Grok found.

fetch_pages(url, query) -> [gd_pages.Page] (kind "web", source "web"): plain-HTTP download (HTML, or a PDF read with
pdftotext), split into pages, the best-matching pages first, each carrying url / host, the document's own revision text
(or the server's Last-Modified), doc_id / title / page / sheet / text.

v4.20.9 (Chase t1729u "delete"): the old app-side web search (make_web_fn / xai_search / http_search) is deleted. Grok
searches the web itself with xAI's built-in web_search inside its own call (since 2026-10-24); this file only fetches.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from html.parser import HTMLParser
from urllib.parse import urlparse, urljoin

from gd_pages import Page

PAGES_PER_DOCUMENT = 8                # pages returned per web document, best-matching first (a search result size, as the library search returns 3)
TIMEOUT = 60.0
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
        except Exception as e:
            import gd_errors
            gd_errors.fallback("web_pdf_text", "pdftotext failed on a web PDF; no text from it", exc=e)
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
    except Exception as e:   # the text read up to the broken markup is kept
        import gd_errors
        gd_errors.fallback("web_html", "a web page's HTML broke the parser; text up to that point is used", exc=e)
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
            except Exception as e:
                import gd_errors
                gd_errors.fallback("web_pdf_follow", "the landing page's PDF link was not opened", exc=e, url=pdfs[0])
    return pages

