"""Clickable manual pages under a Guided Diagnostics reply (Chase 2026-11-25: "the program should pull the pages for the
tech to click and open in pdf or whatever"; plan approved "love it build it").

Each reply's state block carries the pages Grok cited ({doc_id, page}, gd_turn adds title / sheet / url for pages it
opened). This module turns that list into at most MAX_PAGE_LINKS compact rows: one per cited page, labelled like
"Furrion FCR16 · p.19". The app draws each row with an "Open PDF" link (a short-lived presigned R2 link that opens the
PDF inline at #page=<sheet>) and a "Show page" button that draws the page image only when tapped. Nothing is shown when
nothing was cited (Aug 20 decision: no always-on source forest, no expanders, no images unless asked).

Links always use the PDF sheet (1-based page index in the file), never the printed page label. When Grok cited a page
it did not open, the printed label is looked up in the library's page rows. Pure functions: no Streamlit, no network
except through the client passed in.
"""
from __future__ import annotations

import re

MAX_PAGE_LINKS = 4
LINK_EXPIRES_SEC = 3600
TITLE_CHARS = 40
_SHEET_RE = re.compile(r"^\s*sheet\s*(\d+)\s*$", re.I)


def _is_web(c: dict) -> bool:
    """A web source: its doc_id is its address (gd_prompt), or it carries a url and is not a library doc (L<id>)."""
    did = str(c.get("doc_id") or "").strip()
    if re.match(r"^L\d+$", did):
        return False
    return did.lower().startswith(("http://", "https://")) or bool(c.get("url"))


def sheet_for(cited_page, rows) -> int | None:
    """PDF sheet for a cited page label. 'sheet N' is the sheet itself; otherwise the label is matched against each page
    row's printed page (or its sheet when the manual prints none), the same label every library tool shows Grok.
    None when the label matches no page."""
    s = str(cited_page or "").strip()
    if not s:
        return None
    m = _SHEET_RE.match(s)
    if m:
        return int(m.group(1))
    for r in rows or []:
        label = str(r.get("printed_page") or r.get("pdf_sheet") or "").strip()
        if label and label.lower() == s.lower():
            try:
                return int(r["pdf_sheet"])
            except (KeyError, TypeError, ValueError):
                return None
    return None


def short_title(title: str, limit: int = TITLE_CHARS) -> str:
    t = re.sub(r"\s+", " ", str(title or "")).strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def page_refs(cited, *, pages_fn=None, file_fn=None, title_fn=None, limit: int = MAX_PAGE_LINKS) -> list:
    """Rows to draw for one reply's cited list, in Grok's order, deduplicated, capped at `limit`.

    pages_fn(doc_id) -> page rows ({pdf_sheet, printed_page}); file_fn(doc_id) -> the PDF's storage key (R2) or "";
    title_fn(doc_id) -> library title. Each row: {kind: library|web, doc_id, title, page, sheet, file_path, url, label}.
    Stored on the chat message; no links are stored (they expire), they are built when the row is drawn."""
    out, seen = [], set()
    for c in cited or []:
        if len(out) >= limit:
            break
        if not isinstance(c, dict):
            continue
        did = str(c.get("doc_id") or "").strip()
        page = str(c.get("page") or "").strip()
        if _is_web(c):
            url = str(c.get("url") or did)
            if url in seen:
                continue
            seen.add(url)
            title = short_title(c.get("title") or re.sub(r"^https?://(www\.)?", "", url).split("/")[0])
            out.append({"kind": "web", "doc_id": did, "title": title, "page": page, "sheet": None, "file_path": "",
                        "url": url, "label": f"{title} · p.{page}" if page else title})
            continue
        if not did:
            continue
        sheet = c.get("sheet")
        try:
            sheet = int(sheet) if sheet not in (None, "") else None
        except (TypeError, ValueError):
            sheet = None
        if sheet is None and pages_fn is not None:
            try:
                sheet = sheet_for(page, pages_fn(did))
            except Exception:
                sheet = None
        key = (did, sheet if sheet is not None else page)
        if key in seen:
            continue
        seen.add(key)
        title = c.get("title") or ""
        if (not title or title == did) and title_fn is not None:
            try:
                title = title_fn(did) or title
            except Exception:
                pass
        try:
            fpath = (file_fn(did) if file_fn is not None else "") or ""
        except Exception:
            fpath = ""
        shown_page = page or (str(sheet) if sheet is not None else "")
        if _SHEET_RE.match(shown_page or ""):
            shown_page = str(sheet)
        t = short_title(title or did)
        out.append({"kind": "library", "doc_id": did, "title": title or did, "page": shown_page, "sheet": sheet,
                    "file_path": fpath, "url": "", "label": f"{t} · p.{shown_page}" if shown_page else t})
    return out


def pdf_link(client, bucket: str, key: str, sheet=None, expires: int = LINK_EXPIRES_SEC) -> str:
    """Presigned GET for the PDF, served inline (opens in the browser, not a download), at #page=<sheet> when known.
    Signed locally by the client; "" when there is no client, bucket or key, or signing fails."""
    if client is None or not bucket or not key:
        return ""
    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key, "ResponseContentDisposition": "inline",
                    "ResponseContentType": "application/pdf"},
            ExpiresIn=int(expires),
        )
    except Exception:
        return ""
    if not url:
        return ""
    return f"{url}#page={int(sheet)}" if sheet else url


def object_exists(client, bucket: str, key: str) -> bool:
    """HEAD the object: False when it is not in storage (or storage cannot be reached)."""
    if client is None or not bucket or not key:
        return False
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


_EXISTS_CACHE: dict = {}
EXISTS_TTL_SEC = 600


def object_exists_cached(client_fn, bucket: str, key: str, ttl: int = EXISTS_TTL_SEC, now=None) -> bool:
    """object_exists, remembered per key for `ttl` seconds in this process (a yes/no only, never file bytes), so a chat
    rerun does not HEAD every cited PDF again. client_fn is called only on a miss."""
    import time

    t = time.time() if now is None else now
    hit = _EXISTS_CACHE.get((bucket, key))
    if hit is not None and t - hit[1] < ttl:
        return hit[0]
    try:
        client = client_fn() if callable(client_fn) else client_fn
    except Exception:
        client = None
    ok = object_exists(client, bucket, key)
    if client is not None:
        _EXISTS_CACHE[(bucket, key)] = (ok, t)
    return ok
