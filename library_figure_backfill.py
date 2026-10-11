"""Page images and figure crops for the case manuals a manager selects.

Backfill covers CCD-0008666, CCD-0007990, and the Thetford Style II docs.
It does not queue the rest of the library.

Rendering uses the same 150 dpi cropper as a single upload. The PNG is stored
in R2 at image_path. The database row keeps that key, the caption, the page,
the box, and chunk_id for the first chunk on that page. A local cache speeds
up the next read. This module does not import Streamlit.
"""
from __future__ import annotations

import gc
import re
import time
from pathlib import Path

from sqlalchemy import text

import manual_figures as mf

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.19.56"

# Measured at 150 dpi from the two kit fixtures (42109 one page, 34123 two
# pages). Mean page PNG 519584 bytes. Mean of five crops 82040 bytes.
# Those sheets are figure-heavy: 5 crops on 3 pages. A text manual has fewer.
PAGE_PNG_BYTES = 519584
CROP_PNG_BYTES = 82040
SAMPLE_PAGES = 3
SAMPLE_CROPS = 5
SAMPLE_NOTE = (
    "150 dpi mean from Thetford kit sheets 42109 (1 page) and 34123/34122 (2 pages)"
)
# Cloudflare bills decimal GB and includes 10 GB-month before $0.015/GB-month.
DECIMAL_GB = 1_000_000_000
R2_USD_PER_GB_MONTH = 0.015
R2_FREE_GB = 10.0

# Read-through cache. The durable copy is the R2 object. This folder is gitignored.
CACHE_DIR = Path("library_pages")
_LOCK_SECONDS = 180
_BATCH = 2
# One Streamlit step renders this many pages, then the next step resumes.
PAGES_PER_STEP = 8

_JOB_DDL = """
CREATE TABLE IF NOT EXISTS figure_backfill_jobs (
    id INTEGER PRIMARY KEY,
    status VARCHAR(20) DEFAULT 'paused',
    created_date VARCHAR(40) DEFAULT '',
    updated_date VARCHAR(40) DEFAULT '',
    lock_until REAL DEFAULT 0,
    batch_size INTEGER DEFAULT 2
)
"""
_ITEM_DDL = """
CREATE TABLE IF NOT EXISTS figure_backfill_items (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    title VARCHAR(250) DEFAULT '',
    file_path VARCHAR(400) DEFAULT '',
    status VARCHAR(20) DEFAULT 'pending',
    error VARCHAR(400) DEFAULT '',
    page_count INTEGER DEFAULT 0,
    figure_count INTEGER DEFAULT 0,
    byte_size INTEGER DEFAULT 0,
    page_cursor INTEGER DEFAULT 0
)
"""

_STOP = {
    "this", "that", "with", "from", "have", "been", "will", "your", "into",
    "onto", "before", "after", "when", "then", "than", "them", "they",
    "page", "manual", "item", "part", "list", "show", "what", "does",
    "figure", "step", "sheet", "kit",
}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _clip(text_value, limit: int) -> str:
    value = "" if text_value is None else str(text_value)
    return value[:limit]


def _all(session, sql, params=None):
    return [dict(row) for row in session.execute(text(sql), params or {}).mappings().all()]


def _one(session, sql, params=None):
    row = session.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None


def ensure_schema(engine) -> None:
    """Create figure columns and the backfill tables. Safe to call more than once."""
    with engine.begin() as conn:
        conn.exec_driver_sql(mf.ASSET_DDL)
        have = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(doc_assets)").fetchall()}
        alters = (
            ("caption", "ALTER TABLE doc_assets ADD COLUMN caption TEXT DEFAULT ''"),
            ("bbox", "ALTER TABLE doc_assets ADD COLUMN bbox VARCHAR(80) DEFAULT ''"),
            ("chunk_id", "ALTER TABLE doc_assets ADD COLUMN chunk_id INTEGER"),
        )
        for name, ddl in alters:
            if name not in have:
                conn.exec_driver_sql(ddl)
        conn.exec_driver_sql(_JOB_DDL)
        conn.exec_driver_sql(_ITEM_DDL)
        item_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(figure_backfill_items)").fetchall()}
        if "page_cursor" not in item_cols:
            conn.exec_driver_sql(
                "ALTER TABLE figure_backfill_items ADD COLUMN page_cursor INTEGER DEFAULT 0"
            )


def _column_names(session, table: str) -> set[str]:
    rows = session.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def ensure_ready(session) -> None:
    """Add figure columns on the session's connection, without a second transaction."""
    session.execute(text(mf.ASSET_DDL))
    have = _column_names(session, "doc_assets")
    alters = (
        ("caption", "ALTER TABLE doc_assets ADD COLUMN caption TEXT DEFAULT ''"),
        ("bbox", "ALTER TABLE doc_assets ADD COLUMN bbox VARCHAR(80) DEFAULT ''"),
        ("chunk_id", "ALTER TABLE doc_assets ADD COLUMN chunk_id INTEGER"),
    )
    for name, ddl in alters:
        if name not in have:
            session.execute(text(ddl))
    if not _column_names(session, "figure_backfill_jobs"):
        session.execute(text(_JOB_DDL))
    if not _column_names(session, "figure_backfill_items"):
        session.execute(text(_ITEM_DDL))
    elif "page_cursor" not in _column_names(session, "figure_backfill_items"):
        session.execute(text(
            "ALTER TABLE figure_backfill_items ADD COLUMN page_cursor INTEGER DEFAULT 0"
        ))


def link_chunk_ids(session, document_id: int) -> None:
    """Point each asset at the first chunk on the same document and page."""
    session.execute(
        text(
            """
            UPDATE doc_assets
            SET chunk_id = (
                SELECT id FROM doc_chunks
                WHERE document_id = doc_assets.document_id
                  AND page = doc_assets.page
                ORDER BY id
                LIMIT 1
            )
            WHERE document_id = :id
            """
        ),
        {"id": int(document_id)},
    )


def _cache_file(image_path: str, cache_root=None):
    """Local path for one R2 key. Rejects absolute paths and parent segments."""
    raw = (image_path or "").replace("\\", "/").lstrip("/")
    if not raw:
        return None
    parts = Path(raw).parts
    if ".." in parts or Path(raw).is_absolute():
        return None
    root = Path(cache_root) if cache_root is not None else CACHE_DIR
    return root / raw


def fetch_png(image_path: str, download=None, cache_root=None) -> bytes:
    """PNG for one library key. Cache first, then R2, then save the cache."""
    dest = _cache_file(image_path, cache_root)
    if dest is not None and dest.is_file():
        try:
            cached = dest.read_bytes()
        except Exception:
            cached = b""
        if cached:
            return cached
    if not download or not image_path:
        return b""
    try:
        data = download(image_path) or b""
    except Exception:
        data = b""
    if data and dest is not None:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        except Exception:
            pass
    return data or b""


def _insert_asset(session, document_id, page, kind, label, path, width, height, caption, bbox) -> None:
    session.execute(
        text(
            """
            INSERT INTO doc_assets (
                document_id, page, kind, label, image_path, width, height,
                png_blob, caption, bbox, chunk_id
            ) VALUES (
                :document_id, :page, :kind, :label, :image_path, :width, :height,
                NULL, :caption, :bbox, NULL
            )
            """
        ),
        {
            "document_id": int(document_id),
            "page": int(page),
            "kind": kind,
            "label": label,
            "image_path": path,
            "width": int(width or 0),
            "height": int(height or 0),
            "caption": caption,
            "bbox": mf.format_bbox(bbox),
        },
    )


def _ship_png(png: bytes, path: str, upload_png, root) -> bool:
    """Upload one PNG. False means R2 refused it, so the caller must not store the key."""
    if root is not None and png and path:
        dest = Path(root) / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(png)
    if upload_png and png and path:
        try:
            uploaded = upload_png(png, path, "image/png")
        except Exception:
            return False
        if uploaded is False:
            return False
    return True


def store_pdf_figures(
    session,
    document_id: int,
    pdf_bytes: bytes,
    title: str = "",
    upload_png=None,
    root=None,
    start_page: int = 1,
    max_pages: int | None = None,
) -> dict:
    """Render a window of pages, one page at a time, and upload each PNG.

    Does not commit. The row stores the key, caption, page, and box, not the
    image bytes. ``start_page`` and ``max_pages`` let a long manual resume
    without rendering the rest of the file in this step. PNG bytes are dropped
    before the next page is rasterized.
    """
    ensure_ready(session)
    start = max(1, int(start_page or 1))
    if start <= 1:
        session.execute(
            text("DELETE FROM doc_assets WHERE document_id = :id"),
            {"id": int(document_id)},
        )
    else:
        session.execute(
            text("DELETE FROM doc_assets WHERE document_id = :id AND page >= :page"),
            {"id": int(document_id), "page": start},
        )
    pages = []
    figures = []
    stored_bytes = 0
    page_count = 0
    any_text = False
    last_page = start - 1
    for rendered in mf.walk_pdf_pages(pdf_bytes, start_page=start, max_pages=max_pages):
        page_count = int(rendered["page_count"])
        last_page = int(rendered["page"])
        page_text = rendered.get("text") or ""
        if page_text:
            any_text = True
        png = rendered.get("png") or b""
        stored_bytes += len(png)
        path = mf.asset_path(int(document_id), last_page, "page", "page")
        if png and not _ship_png(png, path, upload_png, root):
            raise RuntimeError("could not store the page image in R2")
        label = "page"
        caption = mf.display_caption(title, last_page, label) if title else ""
        width = int(rendered.get("width") or 0)
        height = int(rendered.get("height") or 0)
        _insert_asset(
            session, document_id, last_page, "page", "", path, width, height, caption, ""
        )
        pages.append({"page": last_page, "width": width, "height": height})
        rendered["png"] = b""
        png = b""
        for figure in list(rendered.get("figures") or []):
            fig_png = figure.get("png") or b""
            stored_bytes += len(fig_png)
            fig_label = figure.get("label") or ""
            fig_path = mf.asset_path(int(document_id), last_page, "figure", fig_label or "fig")
            if fig_png and not _ship_png(fig_png, fig_path, upload_png, root):
                raise RuntimeError("could not store the figure image in R2")
            fig_caption = mf.display_caption(title, last_page, fig_label) if title else (fig_label or "")
            _insert_asset(
                session,
                document_id,
                last_page,
                "figure",
                fig_label,
                fig_path,
                int(figure.get("width") or 0),
                int(figure.get("height") or 0),
                fig_caption,
                figure.get("bbox"),
            )
            figures.append({"page": last_page, "label": fig_label})
            figure["png"] = b""
        rendered["figures"] = []
        gc.collect()
    link_chunk_ids(session, int(document_id))
    refresh_document_asset_note(session, int(document_id))
    next_page = last_page + 1 if page_count else 1
    done = page_count == 0 or next_page > page_count
    whole = max_pages is None or (start <= 1 and done)
    return {
        "pages": pages,
        "figures": figures,
        "scanned": (not any_text) if whole else False,
        "stored_bytes": stored_bytes,
        "page_count": page_count,
        "next_page": next_page,
        "done": done,
    }


def _pdf_documents(session) -> list[dict]:
    rows = _all(
        session,
        """
        SELECT id, title, file_path, file_type, brand, clean_title, doc_number, models
        FROM documents ORDER BY id
        """,
    )
    kept = []
    for row in rows:
        kind = (row.get("file_type") or "").lower()
        path = (row.get("file_path") or "").lower()
        if kind == "pdf" or path.endswith(".pdf"):
            kept.append(row)
    return kept


_CASE_CCD_RE = re.compile(r"CCD-?0*8666|CCD-?0*7990|\b0008666\b|\b0007990\b", re.I)
_CASE_PART_RE = re.compile(r"\b(?:42088|42109|42110|42049|34122|34123)\b")
_CASE_STYLE_RE = re.compile(r"style\s*ii", re.I)
_CASE_PARTS_LIST_RE = re.compile(r"parts\s*list", re.I)
_THETFORD_RE = re.compile(r"thetford", re.I)


def case_backfill_document(doc: dict) -> bool:
    """True for the Furrion FACR manuals and the Thetford Style II docs.

    CCD-0008666, CCD-0007990, the Style II owner manual, the 42109 water
    valve kit, the 42110 parts sheet, the 34123/34122 vacuum breaker, and
    a Thetford parts list. Other manuals stay out.
    """
    blob = " ".join(
        str(doc.get(key) or "")
        for key in ("title", "clean_title", "file_path", "brand", "doc_number", "models")
    )
    if _CASE_CCD_RE.search(blob) or _CASE_PART_RE.search(blob):
        return True
    if _CASE_PARTS_LIST_RE.search(blob) and (
        _THETFORD_RE.search(blob) or re.search(r"toilet|aqua-magic|style\s*ii", blob, re.I)
    ):
        return True
    return bool(_THETFORD_RE.search(blob) and _CASE_STYLE_RE.search(blob))


def case_backfill_documents(session) -> list[dict]:
    """PDFs the per-case backfill is allowed to render."""
    return [doc for doc in _pdf_documents(session) if case_backfill_document(doc)]


def document_asset_counts(session) -> dict[int, dict]:
    """Page-image and figure counts stored for each document. Missing docs are absent."""
    ensure_ready(session)
    rows = _all(
        session,
        """
        SELECT document_id,
               SUM(CASE WHEN kind = 'page' THEN 1 ELSE 0 END) AS pages,
               SUM(CASE WHEN kind = 'figure' THEN 1 ELSE 0 END) AS figures
        FROM doc_assets
        GROUP BY document_id
        """,
    )
    return {
        int(row["document_id"]): {
            "pages": int(row["pages"] or 0),
            "figures": int(row["figures"] or 0),
        }
        for row in rows
    }


def index_status_line(title: str, indexed: bool, index_note: str = "", pages: int = 0, figures: int = 0) -> str:
    """Index status includes the stored page-image count and the figure count."""
    note = (index_note or "").strip() or ("indexed" if indexed else "not indexed")
    mark = "OK" if indexed else "MISSING"
    return (
        f"{mark} {title} - {note} - {int(pages)} page images, {int(figures)} figures"
    )


def refresh_document_asset_note(session, document_id: int) -> str:
    """Write the stored page-image and figure counts onto the document."""
    counts = document_asset_counts(session).get(int(document_id), {"pages": 0, "figures": 0})
    note = f"{counts['pages']} page images, {counts['figures']} figures"
    session.execute(
        text("UPDATE documents SET index_note = :note WHERE id = :id"),
        {"note": _clip(note, 250), "id": int(document_id)},
    )
    return note


def backfill_batch_message(result: dict) -> str:
    """Pages stored this click, manuals finished, and what is still queued."""
    return (
        f"This batch: {int((result or {}).get('pages_stored') or 0)} page images stored, "
        f"{int((result or {}).get('done') or 0)} manuals finished, "
        f"{int((result or {}).get('failed') or 0)} failed. "
        f"Remaining {int((result or {}).get('pending') or 0)}."
    )


def estimated_figure_count(pages: int) -> int:
    """Kit-sheet crop count. High for a text manual, which has fewer drawings."""
    pages = max(0, int(pages))
    if not pages:
        return 0
    return int(round(pages * SAMPLE_CROPS / SAMPLE_PAGES))


def project_r2_storage(pdf_bytes: int, pages: int, figures: int | None = None) -> dict:
    """R2 bytes for the PDFs plus one page PNG and the figure crops.

    ``figures`` left empty uses the kit-sheet rate. The monthly price is
    storage only, after 10 decimal GB free, at $0.015 per GB-month.
    """
    pages = max(0, int(pages))
    pdf_bytes = max(0, int(pdf_bytes))
    estimated = figures is None
    if estimated:
        figures = estimated_figure_count(pages)
    else:
        figures = max(0, int(figures))
    page_bytes = pages * PAGE_PNG_BYTES
    crop_bytes = figures * CROP_PNG_BYTES
    total = pdf_bytes + page_bytes + crop_bytes
    total_gb = total / DECIMAL_GB
    billable_gb = max(0.0, total_gb - R2_FREE_GB)
    return {
        "pdf_bytes": pdf_bytes,
        "pages": pages,
        "figures": figures,
        "figures_estimated": estimated,
        "page_bytes": page_bytes,
        "crop_bytes": crop_bytes,
        "r2_bytes": total,
        "pdf_gb": pdf_bytes / DECIMAL_GB,
        "page_gb": page_bytes / DECIMAL_GB,
        "crop_gb": crop_bytes / DECIMAL_GB,
        "total_gb": total_gb,
        "free_gb": R2_FREE_GB,
        "billable_gb": billable_gb,
        "monthly_usd": billable_gb * R2_USD_PER_GB_MONTH,
        "price_per_gb": R2_USD_PER_GB_MONTH,
        "crops_per_page": (figures / pages) if pages else 0.0,
    }


def format_r2_projection(est: dict) -> str:
    """Plain report: PDF bytes, page images, figure crops, and the monthly bill."""
    rate = (
        "kit-sheet rate, high for a text manual"
        if est.get("figures_estimated")
        else "counted"
    )
    lines = [
        f"PDFs: {est['pdf_gb']:.2f} GB ({int(est['pdf_bytes'])} bytes)",
        f"Pages: {int(est['pages'])}",
        f"Page images: {est['page_gb']:.2f} GB ({int(est['page_bytes'])} bytes)",
        (
            f"Figure crops: {est['crop_gb']:.2f} GB "
            f"({int(est['figures'])} crops, {rate})"
        ),
        f"R2 total: {est['total_gb']:.2f} GB",
        (
            f"Monthly storage: ${est['monthly_usd']:.2f} "
            f"({est['billable_gb']:.2f} GB above {est['free_gb']:.0f} GB free "
            f"at ${est['price_per_gb']:.3f}/GB-month)"
        ),
    ]
    return "\n".join(lines)


def estimate_backfill(session) -> dict:
    """Bytes the per-case backfill would write.

    Only CCD-0008666, CCD-0007990, and the Thetford Style II docs are counted.
    Page images are one PNG per page (the highest chunk page, or 1). Figure
    crops use the kit-sheet rate from the measured sample, which is higher
    than a text manual. The bytes are the R2 objects only.
    """
    ensure_ready(session)
    docs = case_backfill_documents(session)
    pages = 0
    for doc in docs:
        row = _one(
            session,
            "SELECT MAX(page) AS pages FROM doc_chunks WHERE document_id = :id",
            {"id": int(doc["id"])},
        )
        count = int((row or {}).get("pages") or 0)
        pages += count if count > 0 else 1
    figures = estimated_figure_count(pages)
    page_bytes = pages * PAGE_PNG_BYTES
    crop_bytes = figures * CROP_PNG_BYTES
    r2_bytes = page_bytes + crop_bytes
    return {
        "documents": len(docs),
        "pages": pages,
        "figures": figures,
        "page_bytes": page_bytes,
        "crop_bytes": crop_bytes,
        "r2_bytes": r2_bytes,
        "sqlite_bytes": 0,
        "total_bytes": r2_bytes,
        "page_png_bytes": PAGE_PNG_BYTES,
        "crop_png_bytes": CROP_PNG_BYTES,
        "crops_per_page": SAMPLE_CROPS / SAMPLE_PAGES,
        "sample": SAMPLE_NOTE,
    }


def format_bytes(n) -> str:
    size = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} B"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def estimate_caption(est: dict) -> str:
    docs = int(est.get("documents") or 0)
    pages = int(est.get("pages") or 0)
    page_kb = int(est.get("page_png_bytes") or PAGE_PNG_BYTES) / 1024
    crop_kb = int(est.get("crop_png_bytes") or CROP_PNG_BYTES) / 1024
    rate = float(est.get("crops_per_page") or 0)
    if docs == 0 or pages == 0:
        return (
            "No case manual is selected, so the backfill would store 0 bytes in R2. "
            f"A 150 dpi page image is about {page_kb:.0f} KB and a figure crop is about {crop_kb:.0f} KB. "
            "The database stores the key, caption, page, box, and chunk link, not a second copy of the PNG. "
            f"The kit sheets used for that measurement averaged {rate:.1f} crops per page. "
            "A text manual has fewer crops."
        )
    return (
        f"Backfill storage estimate: {docs} manuals, {pages} pages. "
        f"R2 holds the page images {format_bytes(est.get('page_bytes'))} plus about "
        f"{int(est.get('figures') or 0)} figure crops "
        f"({format_bytes(est.get('crop_bytes'))} at the kit-sheet rate of {rate:.1f} per page), "
        f"{format_bytes(est.get('r2_bytes'))} in all. "
        "The database stores the key, caption, page, box, and chunk link, not the PNG. "
        f"Measured page image about {page_kb:.0f} KB, crop about {crop_kb:.0f} KB. "
        "A text manual has fewer crops than those kit sheets. "
        "This count is CCD-0008666, CCD-0007990, and the Thetford Style II docs."
    )


def job_progress(session, job_id: int) -> dict:
    rows = _all(
        session,
        """
        SELECT status, COUNT(*) AS n, COALESCE(SUM(byte_size), 0) AS bytes
        FROM figure_backfill_items
        WHERE job_id = :id
        GROUP BY status
        """,
        {"id": int(job_id)},
    )
    counts = {row["status"]: int(row["n"]) for row in rows}
    done = counts.get("done", 0)
    failed = counts.get("failed", 0)
    pending = counts.get("pending", 0)
    working = counts.get("working", 0)
    total = done + failed + pending + working
    return {
        "done": done,
        "failed": failed,
        "pending": pending + working,
        "working": working,
        "total": total,
        "bytes": sum(int(row["bytes"] or 0) for row in rows),
    }


def open_job(session):
    """The job a manager can continue. A finished job is not open."""
    ensure_ready(session)
    row = _one(
        session,
        """
        SELECT * FROM figure_backfill_jobs
        WHERE status IN ('paused', 'running')
        ORDER BY id DESC
        LIMIT 1
        """,
    )
    if not row:
        return None
    counts = job_progress(session, int(row["id"]))
    if counts["pending"] == 0 and counts["working"] == 0 and row["status"] != "running":
        return None
    return row


def _job_document_ids(session, job_id: int) -> set[int]:
    rows = _all(
        session,
        "SELECT document_id FROM figure_backfill_items WHERE job_id = :id",
        {"id": int(job_id)},
    )
    return {int(row["document_id"]) for row in rows}


def pdf_choices(session) -> list[dict]:
    """Case manuals a manager can backfill. The rest of the library is not listed."""
    return [
        {"id": int(doc["id"]), "title": (doc.get("title") or f"Document {doc['id']}").strip()}
        for doc in case_backfill_documents(session)
    ]


def ensure_job(session, document_ids=None) -> int:
    """Open a backfill for the selected case manuals.

    A missing selection does not queue the library. Ids outside CCD-0008666,
    CCD-0007990, and the Thetford Style II docs are dropped. A new selection
    does not resume a job for a different set of manuals.
    """
    catalog = case_backfill_documents(session)
    allowed = {int(doc["id"]) for doc in catalog}
    if not document_ids:
        return 0
    wanted = {int(doc_id) for doc_id in document_ids} & allowed
    if not wanted:
        return 0
    current = open_job(session)
    if current and _job_document_ids(session, int(current["id"])) == wanted:
        return int(current["id"])
    now = _now()
    session.execute(
        text(
            """
            INSERT INTO figure_backfill_jobs
                (status, created_date, updated_date, lock_until, batch_size)
            VALUES ('paused', :now, :now, 0, :batch)
            """
        ),
        {"now": now, "batch": _BATCH},
    )
    session.commit()
    job = _one(session, "SELECT id FROM figure_backfill_jobs ORDER BY id DESC LIMIT 1")
    job_id = int(job["id"])
    for doc in catalog:
        if int(doc["id"]) not in wanted:
            continue
        session.execute(
            text(
                """
                INSERT INTO figure_backfill_items
                    (job_id, document_id, title, file_path, status)
                VALUES (:job_id, :document_id, :title, :file_path, 'pending')
                """
            ),
            {
                "job_id": job_id,
                "document_id": int(doc["id"]),
                "title": _clip(doc.get("title") or "", 250),
                "file_path": _clip(doc.get("file_path") or "", 400),
            },
        )
    session.execute(
        text("UPDATE figure_backfill_jobs SET updated_date = :now WHERE id = :id"),
        {"now": now, "id": job_id},
    )
    session.commit()
    return job_id


def process_backfill_batch(
    session,
    job_id: int,
    *,
    download_pdf,
    upload_png=None,
    batch_size: int | None = None,
    progress=None,
) -> dict:
    """Render the next few manuals. Each manual is committed, including a failure."""
    ensure_ready(session)
    job = _one(session, "SELECT * FROM figure_backfill_jobs WHERE id = :id", {"id": int(job_id)})
    if not job:
        return {
            "ok": False,
            "job_id": job_id,
            "processed": 0,
            "done": 0,
            "failed": 0,
            "pending": 0,
            "total": 0,
            "status": "missing",
            "busy": False,
            "pages_stored": 0,
            "error": "Figure backfill job not found.",
        }
    now_ts = time.time()
    if float(job.get("lock_until") or 0) > now_ts and job.get("status") == "running":
        counts = job_progress(session, int(job_id))
        return {
            "ok": False,
            "job_id": int(job_id),
            "processed": 0,
            "done": 0,
            "failed": 0,
            "pending": counts["pending"],
            "total": counts["total"],
            "status": job["status"],
            "busy": True,
            "pages_stored": 0,
            "error": "This backfill is already running.",
        }
    batch = batch_size if batch_size is not None else job.get("batch_size") or _BATCH
    batch = max(1, min(int(batch), 10))
    session.execute(
        text(
            """
            UPDATE figure_backfill_jobs
            SET status = 'running', lock_until = :lock, updated_date = :now, batch_size = :batch
            WHERE id = :id
            """
        ),
        {"lock": now_ts + _LOCK_SECONDS, "now": _now(), "batch": batch, "id": int(job_id)},
    )
    session.execute(
        text(
            """
            UPDATE figure_backfill_items
            SET status = 'pending'
            WHERE job_id = :id AND status = 'working'
            """
        ),
        {"id": int(job_id)},
    )
    session.commit()
    pending = _all(
        session,
        """
        SELECT * FROM figure_backfill_items
        WHERE job_id = :id AND status = 'pending'
        ORDER BY CASE WHEN COALESCE(page_cursor, 0) > 0 THEN 0 ELSE 1 END, id
        LIMIT :batch
        """,
        {"id": int(job_id), "batch": batch},
    )
    done = failed = processed = pages_stored = 0
    for index, item in enumerate(pending, 1):
        title = item.get("title") or ""
        session.execute(
            text("UPDATE figure_backfill_items SET status = 'working' WHERE id = :id"),
            {"id": item["id"]},
        )
        session.commit()
        try:
            data = download_pdf(item.get("file_path") or "") if download_pdf else None
            if not data:
                raise RuntimeError("could not download the pdf")
            start = int(item.get("page_cursor") or 0) or 1
            indexed = store_pdf_figures(
                session,
                int(item["document_id"]),
                data,
                title=title,
                upload_png=upload_png,
                start_page=start,
                max_pages=PAGES_PER_STEP,
            )
            del data
            gc.collect()
            pages_stored += len(indexed.get("pages") or [])
            page_count = int(indexed.get("page_count") or 0)
            figure_count = int(item.get("figure_count") or 0) + len(indexed.get("figures") or [])
            nbytes = int(item.get("byte_size") or 0) + int(indexed.get("stored_bytes") or 0)
            if indexed.get("done", True):
                session.execute(
                    text(
                        """
                        UPDATE figure_backfill_items
                        SET status = 'done', error = '', page_count = :pages,
                            figure_count = :figures, byte_size = :nbytes, page_cursor = 0
                        WHERE id = :id
                        """
                    ),
                    {
                        "pages": page_count or len(indexed.get("pages") or []),
                        "figures": figure_count,
                        "nbytes": nbytes,
                        "id": item["id"],
                    },
                )
                done += 1
                finished_file = True
            else:
                session.execute(
                    text(
                        """
                        UPDATE figure_backfill_items
                        SET status = 'pending', error = '', page_count = :pages,
                            figure_count = :figures, byte_size = :nbytes, page_cursor = :cursor
                        WHERE id = :id
                        """
                    ),
                    {
                        "pages": page_count,
                        "figures": figure_count,
                        "nbytes": nbytes,
                        "cursor": int(indexed.get("next_page") or 0),
                        "id": item["id"],
                    },
                )
                finished_file = False
            session.commit()
            processed += 1
        except Exception as exc:
            session.rollback()
            session.execute(
                text(
                    """
                    UPDATE figure_backfill_items
                    SET status = 'failed', error = :error
                    WHERE id = :id
                    """
                ),
                {"error": _clip(exc, 400), "id": item["id"]},
            )
            session.commit()
            failed += 1
            processed += 1
            finished_file = True
        if progress:
            try:
                progress(index, len(pending), title)
            except Exception:
                pass
        if not finished_file:
            break
    counts = job_progress(session, int(job_id))
    finished = counts["pending"] == 0 and counts["working"] == 0
    status = "complete" if finished else "paused"
    session.execute(
        text(
            """
            UPDATE figure_backfill_jobs
            SET status = :status, lock_until = 0, updated_date = :now
            WHERE id = :id
            """
        ),
        {"status": status, "now": _now(), "id": int(job_id)},
    )
    session.commit()
    return {
        "ok": True,
        "job_id": int(job_id),
        "processed": processed,
        "done": done,
        "failed": failed,
        "pending": counts["pending"],
        "total": counts["total"],
        "status": status,
        "busy": False,
        "pages_stored": pages_stored,
        "error": "",
    }


def meta_rows(session) -> list[dict]:
    """Figure and page rows. Image bytes stay in R2."""
    ensure_ready(session)
    return _all(
        session,
        """
        SELECT a.id, a.document_id, a.page, a.kind, a.label, a.caption, a.bbox,
               a.chunk_id, a.image_path, a.width, a.height,
               d.title AS title, d.file_path AS file_path, d.brand AS brand,
               d.product_line AS product_line, d.models AS models,
               d.keywords AS keywords, d.clean_title AS clean_title,
               d.doc_number AS doc_number, c.name AS category_name
        FROM doc_assets a
        JOIN documents d ON d.id = a.document_id
        LEFT JOIN categories c ON c.id = d.category_id
        """,
    )


def attach_pngs(session, offers, read_local: bool = False, download=None, cache_root=None) -> list:
    """Load PNG bytes for the chosen rows from the cache or from R2.

    ``session`` is unused. The database does not hold the image.
    """
    del session
    for offer in offers or []:
        if offer.get("png"):
            continue
        path = offer.get("image_path") or ""
        if not path:
            continue
        png = b""
        if read_local:
            local = Path(path)
            if not local.is_absolute() and local.is_file():
                try:
                    png = local.read_bytes()
                except Exception:
                    png = b""
        if not png:
            png = fetch_png(path, download=download, cache_root=cache_root)
        offer["png"] = png or b""
    return offers


def _words(value: str) -> set[str]:
    import re

    return {
        word
        for word in re.findall(r"[a-z0-9]+", (value or "").lower())
        if len(word) > 3 and word not in _STOP
    }


def _row_part_topic(row: dict) -> str:
    blob = f"{row.get('title') or ''} {row.get('label') or ''} {row.get('caption') or ''}"
    return mf.part_topic(blob)


# Product lines are narrower than the maker. Power Gear is not Level Up,
# and a pump-seal tip sheet is not a toilet kit or a rooftop air conditioner.
_LINE_RES = (
    ("power_gear", re.compile(
        r"power\s*gear|tip\s*sheet\s*#?\s*216|\bmotor\s*brake\b|\bpump\s*seal\b|\bpump\s+replacement\b",
        re.I,
    )),
    ("level_up", re.compile(r"level[\s-]*up|\b807662\b", re.I)),
    ("ground_control", re.compile(r"ground\s*control|\b343633\b", re.I)),
    ("psx1", re.compile(r"\bpsx1\b", re.I)),
    ("schwintek", re.compile(r"\bschwintek\b", re.I)),
    # Same maker is not the same system. A tongue jack is not a PSX1 stabilizer,
    # and a Titan bracket is not Level Up.
    ("tongue_jack", re.compile(r"tongue\s*jack|bevel\s*gear", re.I)),
    ("titan", re.compile(r"\btitan\b|\bti[\s-]*489\b", re.I)),
    ("happijac", re.compile(r"happi\s*jac", re.I)),
    ("ac", re.compile(r"air\s*condition|\brooftop\b|\bhvac\b|\bb57915\b|\bbrisk\b", re.I)),
    ("plastic_tank", re.compile(r"plastic\s+tank", re.I)),
    ("toilet", re.compile(
        r"\b(?:toilet|thetford|42070|42109|42049|34122|34123|flush\s+lever)\b",
        re.I,
    )),
)


def _without_how(text: str) -> str:
    """Shop text only. An appended How block is not the case identity.

    The cut is the How marker itself. A title with a closing parenthesis
    used to leave the rest of that block in the shop text.
    """
    return re.split(r"\bHow\s*\(", text or "", maxsplit=1, flags=re.I)[0]


def _product_lines(text: str) -> set[str]:
    blob = text or ""
    return {name for name, pattern in _LINE_RES if pattern.search(blob)}


def _category_family(text: str) -> str:
    low = text or ""
    if re.search(r"air\s*condition", low, re.I):
        return "ac"
    if re.search(r"toilet", low, re.I):
        return "toilet"
    if re.search(r"\bleveling\b", low, re.I):
        return "leveling"
    if re.search(r"\bfurnace", low, re.I):
        return "furnace"
    if re.search(r"water\s*heat", low, re.I):
        return "water"
    if re.search(r"refrigerat", low, re.I):
        return "fridge"
    return ""


def _part_ids(text: str) -> set[str]:
    return set(re.findall(r"\b\d{4,}\b", text or ""))


_BRAND_WORDS = {
    "lippert", "dometic", "thetford", "furrion", "atwood", "coleman",
    "girard", "suburban", "norcold", "happijac",
}
# Shared family words are not a topic. "Level" does not make a slide motor
# relevant to a Manual Mode flash, and it does not make a HappiJac crop a PSX1.
_GENERIC_TOPIC = {
    "level", "mode", "auto", "home", "manual", "advantage", "system",
    "repair", "check", "unit", "model", "works", "still", "flash",
    "flashes", "dumps", "back", "page", "figure",
}


def figure_on_topic(row, reply="", user_msg="", model="") -> bool:
    """A same-family crop still has to share the step's topic or part.

    A bare Fig. label on a document that already passed the brand gate stays.
    A table, a header strip, or a crop about a different part does not.
    """
    if junk_figure(row):
        return False
    identity = _figure_identity(row)
    step_blob = " ".join(part for part in (reply, user_msg, model) if part)
    if mf.brands_conflict(step_blob, identity):
        return False
    step = _without_how(" ".join(part for part in (reply, user_msg, model) if part))
    step_words = _words(step) - _BRAND_WORDS - _GENERIC_TOPIC
    row_words = _words(identity) - _BRAND_WORDS - _GENERIC_TOPIC
    ids_step = _part_ids(step)
    ids_row = _part_ids(identity)
    if ids_row and ids_step:
        return not ids_row.isdisjoint(ids_step)
    if step_words & row_words:
        return True
    return not row_words


def _row_text(row: dict) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in (
            "title",
            "brand",
            "product_line",
            "models",
            "keywords",
            "clean_title",
            "doc_number",
            "file_path",
            "label",
            "caption",
            "category",
            "category_name",
        )
    )


def _case_job(category="", model="", user_msg="", reply="", job_text="") -> str:
    return _without_how(
        " ".join(
            part
            for part in (category, model, user_msg, reply, job_text)
            if part
        )
    )


def _asked_brands(category, model, job, user_msg="", reply="", job_text="") -> set:
    import gd_library_coach as gdc

    symptom = _without_how(f"{user_msg or ''} {reply or ''} {job_text or ''}")
    asked = set(gdc.asked_brands_for_lookup(category or "", model or "", symptom))
    # S09 often types the rooftop code and not the word Dometic.
    if re.search(r"\bb57915\b", job or "", re.I):
        asked.add("dometic")
    return asked


def _figure_identity(row: dict) -> str:
    """The words that name this crop. Keywords on the parent document do not."""
    return " ".join(
        str((row or {}).get(key) or "")
        for key in ("title", "label", "caption", "clean_title", "doc_number", "product_line")
    )


def junk_figure(row) -> bool:
    """A sample page, a watermark, or a port-header strip is not a shop figure.

    Width and height are the stored crop. A short wide strip is a running
    header. A normal page crop is left for the system gate.
    """
    blob = _figure_identity(row or {})
    if re.search(r"\bsample\b|watermark|\(discontinued\)", blob, re.I):
        return True
    if re.search(r"port[-\s]*header|running header|header strip", blob, re.I):
        return True
    if re.search(r"\b(?:lcd|spec(?:ification)?\s+table|data\s+table)\b|\btable\b", blob, re.I):
        return True
    if re.search(r"\bti[\s-]*143\b", blob, re.I) and not re.search(r"\bpsx1\b|roll\s*pin", blob, re.I):
        return True
    if re.search(r"\bti[\s-]*324\b", blob, re.I):
        return True
    try:
        width = int((row or {}).get("width") or 0)
        height = int((row or {}).get("height") or 0)
    except (TypeError, ValueError):
        width = height = 0
    if width >= 320 and height > 0 and height <= 80 and width / height >= 6:
        return True
    return False


def fits_case(row, category="", model="", user_msg="", reply="", job_text="") -> bool:
    """True only when this document is the case brand, model, and system.

    Every case uses this gate, not only Thetford. A named system has to be
    on the document. A document that names a different system does not
    illustrate the case. No match means no figure and no How block.
    """
    import gd_library_coach as gdc

    if junk_figure(row):
        return False
    job = _case_job(category, model, user_msg, reply, job_text)
    row_text = _row_text(row or {})
    job_lines = _product_lines(job)
    row_lines = _product_lines(row_text)
    # The case named a system. The document has to share it, and it cannot
    # name an extra system. A Thetford plastic-tank sheet is not kit 42109
    # or kit 34123.
    if job_lines and not (job_lines & row_lines):
        return False
    if job_lines and (row_lines - job_lines):
        return False
    asked = _asked_brands(category, model, job, user_msg, reply, job_text)
    job_family = _category_family(category) or _category_family(job)
    # The document named a system the case did not. That is a different product.
    if row_lines and not job_lines and (asked or job_family):
        return False
    if not gdc.chunk_matches_asked_brand(
        (row or {}).get("title") or "",
        (row or {}).get("keywords") or "",
        "",
        asked,
        coleman_job=gdc.is_coleman_2111_context(category or "", model or "", job),
        file_path=(row or {}).get("file_path") or "",
        brand=(row or {}).get("brand") or "",
        models=(row or {}).get("models") or "",
        clean_title=(row or {}).get("clean_title") or "",
        product_line=(row or {}).get("product_line") or "",
        doc_number=(row or {}).get("doc_number") or "",
    ):
        return False
    if not gdc.model_list_allows((row or {}).get("models") or "", model or ""):
        return False
    row_family = _category_family(
        (row or {}).get("category") or (row or {}).get("category_name") or ""
    )
    if job_family and row_family and job_family != row_family:
        return False
    return True


def off_brand_figure(row, category="", model="", user_msg="", reply="", job_text="") -> bool:
    """True when this figure names a different brand, model, or system.

    A shop seed that names no other product stays. A Tip Sheet, a Power Gear
    page, or another maker does not.
    """
    import gd_library_coach as gdc

    if junk_figure(row):
        return True
    job = _case_job(category, model, user_msg, reply, job_text)
    row_text = _row_text(row or {})
    job_lines = _product_lines(job)
    row_lines = _product_lines(row_text)
    if job_lines and row_lines and job_lines.isdisjoint(row_lines):
        return True
    if job_lines and (row_lines - job_lines):
        return True
    if row_lines and not job_lines:
        return True
    asked = _asked_brands(category, model, job, user_msg, reply, job_text)
    declared = gdc.canonical_shop_brands((row or {}).get("brand") or "")
    if not declared:
        declared = gdc.canonical_shop_brands(
            (row or {}).get("title") or "",
            (row or {}).get("product_line") or "",
            (row or {}).get("clean_title") or "",
        )
    if asked and declared and asked.isdisjoint(declared):
        return True
    if not gdc.model_list_allows((row or {}).get("models") or "", model or ""):
        return True
    job_family = _category_family(category) or _category_family(job)
    row_family = _category_family(
        (row or {}).get("category") or (row or {}).get("category_name") or ""
    )
    if job_family and row_family and job_family != row_family:
        return True
    return False


def procedure_how(row, text, doc_title, page, category="", model="", user_msg="", reply="", job_text="") -> str:
    """The How block for this document, or nothing when it is not this case."""
    identity = dict(row or {})
    if doc_title and not identity.get("title"):
        identity["title"] = doc_title
    if not fits_case(identity, category, model, user_msg, reply, job_text):
        return ""
    return mf.procedure_detail(text or "", doc_title, page)


def select_library_figures(rows, reply: str, user_msg: str, category: str, model: str) -> list[dict]:
    """Pick figure crops for this case. Zero means no brand, model, or topic match.

    A document has to be the same brand and product line as the case. A figure
    then has to match the step's topic and part number. Nothing else is shown.
    """
    import re

    job = " ".join(part for part in (category, model, user_msg, reply) if part)
    figures = [
        row
        for row in rows or []
        if (row.get("kind") or "figure") == "figure"
        and fits_case(row, category, model, user_msg, reply)
        and figure_on_topic(row, reply, user_msg, model)
    ]
    topic = mf.part_topic(_without_how(reply))
    if topic:
        figures = [
            row
            for row in figures
            if not _row_part_topic(row) or _row_part_topic(row) == topic
        ]
    if not figures:
        return []
    named = mf._numbers_named(reply or "") or mf._numbers_named(user_msg or "")
    reply_words = _words(reply or "")
    ask_words = reply_words or _words(user_msg or "")
    model_words = _words(f"{model or ''} {category or ''}")
    by_doc: dict[int, dict] = {}
    for row in figures:
        title = row.get("title") or ""
        brand = row.get("brand") or ""
        identity = f"{title} {brand}"
        if mf.brands_conflict(job, identity):
            continue
        doc_id = int(row.get("document_id") or 0)
        bucket = by_doc.setdefault(
            doc_id,
            {"score": 0, "title": title, "brand": brand_name_of(identity), "rows": []},
        )
        bucket["rows"].append(row)
        title_words = _words(identity)
        label_words = _words(f"{row.get('label') or ''} {row.get('caption') or ''}")
        overlap = len(title_words & model_words) + len(title_words & ask_words)
        overlap += len(label_words & reply_words) * 3
        overlap += len(label_words & ask_words)
        if brand and mf.brand_name(job) == mf.brand_name(identity):
            overlap += 4
        if overlap > bucket["score"]:
            bucket["score"] = overlap
    winners = [bucket for bucket in by_doc.values() if bucket["score"] > 0]
    if not winners:
        return []
    winners.sort(key=lambda bucket: bucket["score"], reverse=True)
    best_brand = winners[0]["brand"]
    if best_brand:
        winners = [bucket for bucket in winners if not bucket["brand"] or bucket["brand"] == best_brand]
    chosen = []
    for bucket in winners:
        for row in bucket["rows"]:
            label = f"{row.get('label') or ''} {row.get('caption') or ''}"
            if mf.brands_conflict(job, f"{row.get('title') or ''} {row.get('brand') or ''}"):
                continue
            nums = mf._figure_numbers(label)
            if named and not any(number in named for number in nums):
                continue
            label_words = _words(label)
            figure_score = len(label_words & reply_words) * 3 + len(label_words & ask_words)
            if topic and _row_part_topic(row) == topic:
                figure_score += 6
            if named and any(number in named for number in nums):
                figure_score += 8
            step_ids = _part_ids(reply or "") or _part_ids(user_msg or "")
            row_ids = _part_ids(f"{row.get('title') or ''} {label}")
            if row_ids and step_ids and row_ids.isdisjoint(step_ids):
                continue
            if row_ids and step_ids & row_ids:
                figure_score += 8
            chosen.append((figure_score, bucket["score"], row))
    if not chosen:
        return []
    pool = [item for item in chosen if item[0] > 0]
    if not pool:
        return []
    pool.sort(key=lambda item: (item[0], item[1]), reverse=True)
    offers = []
    seen = set()
    for figure_score, _doc_score, row in pool:
        key = (row.get("document_id"), row.get("page"), row.get("label"), row.get("id"))
        if key in seen:
            continue
        seen.add(key)
        label = row.get("label") or ""
        caption = row.get("caption") or mf.display_caption(row.get("title") or "", row.get("page"), label)
        offers.append(
            {
                "id": row.get("id"),
                "title": row.get("title") or "",
                "page": row.get("page"),
                "label": label,
                "caption": caption,
                "bbox": row.get("bbox") or "",
                "png": row.get("png") or b"",
                "file_path": row.get("file_path") or "",
                "document_id": row.get("document_id") or 0,
                "chunk_id": row.get("chunk_id"),
                "kind": "figure",
                "image_path": row.get("image_path") or "",
                "bundled": False,
                "brand": row.get("brand") or "",
                "product_line": row.get("product_line") or "",
                "models": row.get("models") or "",
                "keywords": row.get("keywords") or "",
                "category_name": row.get("category_name") or "",
                "clean_title": row.get("clean_title") or "",
                "doc_number": row.get("doc_number") or "",
            }
        )
        if figure_score <= 0 and len(offers) >= 3:
            break
    asked = mf.wants_manual_image(user_msg) or bool(re.search(r"\bshow\b", user_msg or "", re.I))
    if asked and offers:
        page_rows = [
            row
            for row in rows or []
            if row.get("kind") == "page"
            and row.get("document_id") == offers[0]["document_id"]
            and row.get("page") == offers[0]["page"]
        ]
        if page_rows:
            page = page_rows[0]
            offers.append(
                {
                    "id": page.get("id"),
                    "title": page.get("title") or offers[0]["title"],
                    "page": page.get("page"),
                    "label": "page",
                    "caption": page.get("caption")
                    or mf.display_caption(page.get("title") or "", page.get("page"), "page"),
                    "bbox": "",
                    "png": page.get("png") or b"",
                    "file_path": page.get("file_path") or "",
                    "document_id": page.get("document_id") or 0,
                    "chunk_id": page.get("chunk_id"),
                    "kind": "page",
                    "image_path": page.get("image_path") or "",
                    "bundled": False,
                    "brand": page.get("brand") or "",
                }
            )
    return offers


def brand_name_of(text_value: str) -> str:
    return mf.brand_name(text_value)


def figures_beside_steps(rows, steps, category: str = "", model: str = "") -> list[list[dict]]:
    """The same library crops Guided Diagnostics would show, one group per bay step."""
    groups = []
    for step in steps or []:
        offers = select_library_figures(rows, step or "", "", category, model)
        groups.append(offers[:1])
    return groups


def _om_page_caption(item: dict) -> bool:
    """The Style II owner manual page caption is not a kit figure label."""
    blob = f"{item.get('title') or ''} {item.get('caption') or ''} {item.get('label') or ''}"
    if re.search(r"\b42088\b", blob) and re.search(r"/\s*page\b", item.get("caption") or "", re.I):
        return True
    return (item.get("label") or "") == "page" and bool(re.search(r"\b42088\b", blob))


_DOC_TOKEN_RE = re.compile(
    r"CCD-0*(\d{4,})|\b(42088|42109|42110|42049|34122|34123)\b",
    re.I,
)


def _doc_tokens(text: str) -> set[str]:
    found = set()
    for match in _DOC_TOKEN_RE.finditer(text or ""):
        found.add((match.group(1) or match.group(2) or "").lstrip("0").lower() or "0")
    return found


def _cited_doc_pages(reply: str) -> dict[str, set[int]]:
    """Pages this reply names for a manual. Another page of that manual is not a substitute."""
    found: dict[str, set[int]] = {}
    blob = reply or ""
    for match in re.finditer(
        r"(CCD-0*\d{4,}|\b(?:42088|42109|42110|42049|34122|34123)\b)([^\n]{0,160})",
        blob,
        re.I,
    ):
        pages = {int(number) for number in re.findall(r"\bpage\s*(\d+)", match.group(2), flags=re.I)}
        if not pages:
            continue
        for token in _doc_tokens(match.group(1)):
            found.setdefault(token, set()).update(pages)
    return found


def _offer_from_asset(row: dict) -> dict:
    kind = row.get("kind") or "figure"
    label = row.get("label") or ("page" if kind == "page" else "")
    return {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "page": row.get("page"),
        "label": label,
        "caption": row.get("caption")
        or mf.display_caption(row.get("title") or "", row.get("page"), label),
        "bbox": row.get("bbox") or "",
        "png": row.get("png") or b"",
        "file_path": row.get("file_path") or "",
        "document_id": row.get("document_id") or 0,
        "chunk_id": row.get("chunk_id"),
        "kind": kind,
        "image_path": row.get("image_path") or "",
        "bundled": False,
        "brand": row.get("brand") or "",
        "product_line": row.get("product_line") or "",
        "models": row.get("models") or "",
        "keywords": row.get("keywords") or "",
        "category_name": row.get("category_name") or "",
        "clean_title": row.get("clean_title") or "",
        "doc_number": row.get("doc_number") or "",
    }


def _offers_for_cited_pages(rows, cites: dict[str, set[int]]) -> list[dict]:
    """The cited page's figure, or that same page's image when the page has no figure."""
    by_key: dict[tuple, list] = {}
    for row in rows or []:
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("title", "clean_title", "file_path", "doc_number", "caption", "label")
        )
        tokens = _doc_tokens(blob) & set(cites)
        if not tokens:
            continue
        try:
            page = int(row.get("page") or 0)
        except (TypeError, ValueError):
            continue
        if not any(page in cites[token] for token in tokens):
            continue
        if not (row.get("png") or row.get("image_path")):
            continue
        by_key.setdefault((int(row.get("document_id") or 0), page), []).append(row)
    offers = []
    for grouped in by_key.values():
        figures = [row for row in grouped if (row.get("kind") or "figure") == "figure"]
        pages = [row for row in grouped if row.get("kind") == "page"]
        chosen = figures[:1] or pages[:1]
        offers.extend(_offer_from_asset(row) for row in chosen)
    return offers


def _offer_matches_cited_page(item: dict, cites: dict[str, set[int]]) -> bool:
    """A cited manual may only show a page the reply named."""
    blob = " ".join(
        str(item.get(key) or "")
        for key in ("title", "caption", "label", "doc_number", "clean_title", "file_path")
    )
    tokens = _doc_tokens(blob) & set(cites)
    if not tokens:
        return True
    try:
        page = int(item.get("page") or 0)
    except (TypeError, ValueError):
        return False
    return any(page in cites[token] for token in tokens)


def gd_figure_caption(item: dict) -> str:
    """Caption under a Guided Diagnostics figure: the document and the page."""
    item = item or {}
    title = str(item.get("title") or "Manual").strip() or "Manual"
    try:
        page = int(item.get("page") or 0)
    except (TypeError, ValueError):
        page = 0
    label = str(item.get("label") or "").strip()
    try:
        if page:
            return mf.display_caption(title, page, label)
        return title
    except Exception:
        if page:
            return f"{title}, page {page}"
        return title


def _source_cites(reply: str) -> list[tuple[str, int]]:
    """'Source: <manual>, page N' lines. The page number is part of the cite."""
    found = []
    for match in re.finditer(r"Source:\s*([^,\n]{3,160}),\s*page\s+(\d+)", reply or "", re.I):
        title = re.sub(r"^[\s📖*]+", "", match.group(1)).strip()
        if title:
            found.append((title, int(match.group(2))))
    return found


def _row_on_source(row: dict, title: str, page: int) -> bool:
    try:
        row_page = int(row.get("page") or 0)
    except (TypeError, ValueError):
        return False
    if row_page != int(page):
        return False
    row_title = (row.get("title") or "").strip().lower()
    want = (title or "").strip().lower()
    if not row_title or not want:
        return False
    if want in row_title or row_title in want:
        return True
    return bool(_doc_tokens(want) & _doc_tokens(row_title))


def _gd_same_case(item: dict, category: str, model: str, user_msg: str, reply: str) -> bool:
    """Same brand and model as this case. A bad row is skipped, not raised."""
    try:
        if off_brand_figure(item, category, model, user_msg, reply):
            return False
        return bool(fits_case(item, category, model, user_msg, reply))
    except Exception:
        return False


def _offer_is_cited(item: dict, cites: dict[str, set[int]], sources: list[tuple[str, int]]) -> bool:
    """True when this offer is one of the manuals and pages the reply named."""
    if cites and _offer_matches_cited_page(item, cites):
        blob = " ".join(
            str(item.get(key) or "")
            for key in ("title", "caption", "label", "doc_number", "clean_title", "file_path")
        )
        if _doc_tokens(blob) & set(cites):
            return True
    for title, page in sources or []:
        if _row_on_source(item, title, page):
            return True
    return False


def _cited_page_offers(rows, cites: dict[str, set[int]], sources: list[tuple[str, int]]) -> list[dict]:
    """Every figure on a cited page. The page image is used only when that page has no figure."""
    grouped: dict[tuple, list] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        hit = False
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("title", "clean_title", "file_path", "doc_number", "caption", "label")
        )
        tokens = _doc_tokens(blob) & set(cites or {})
        try:
            page = int(row.get("page") or 0)
        except (TypeError, ValueError):
            continue
        if tokens and any(page in (cites or {}).get(token, ()) for token in tokens):
            hit = True
        if any(_row_on_source(row, title, want) for title, want in sources or []):
            hit = True
        if not hit:
            continue
        if not (row.get("png") or row.get("image_path") or row.get("file_path")):
            continue
        grouped.setdefault((int(row.get("document_id") or 0), page, (row.get("title") or "")), []).append(row)
    offers = []
    for bucket in grouped.values():
        figures = [row for row in bucket if (row.get("kind") or "figure") == "figure"]
        pages = [row for row in bucket if row.get("kind") == "page"]
        picked = figures or pages[:1]
        offers.extend(_offer_from_asset(row) for row in picked)
    return offers


def gd_figures_under_step(rows, reply: str, user_msg: str, category: str, model: str) -> list[dict]:
    """Figures for one Guided Diagnostics step. Empty when this case has none.

    Cited document and page win. Another brand, another model, or another page
    is left out. A missing crop returns nothing instead of raising.
    """
    try:
        reply = reply or ""
        user_msg = user_msg or ""
        category = category or ""
        model = model or ""
        safe_rows = [row for row in (rows or []) if isinstance(row, dict)]
        cites = _cited_doc_pages(reply)
        sources = _source_cites(reply)
        if cites or sources:
            chosen = [
                item
                for item in _cited_page_offers(safe_rows, cites, sources)
                if _gd_same_case(item, category, model, user_msg, reply)
            ]
            named = mf._numbers_named(reply)
            if named and chosen:
                matched = [
                    item
                    for item in chosen
                    if any(number in mf._figure_numbers(item.get("label") or "") for number in named)
                ]
                if matched:
                    chosen = matched
                else:
                    chosen = [item for item in chosen if (item.get("kind") or "") == "page"][:1]
            if not chosen:
                fallback = offers_for_turn(safe_rows, reply, user_msg, category, model)
                chosen = [
                    item
                    for item in fallback or []
                    if isinstance(item, dict)
                    and _offer_is_cited(item, cites, sources)
                    and _gd_same_case(item, category, model, user_msg, reply)
                ]
        else:
            chosen = [
                item
                for item in offers_for_turn(safe_rows, reply, user_msg, category, model) or []
                if isinstance(item, dict) and _gd_same_case(item, category, model, user_msg, reply)
            ]
        out = []
        seen = set()
        for item in chosen:
            if not (item.get("png") or item.get("image_path") or item.get("file_path")):
                continue
            key = (
                item.get("document_id"),
                item.get("page"),
                item.get("label") or "",
                item.get("image_path") or "",
            )
            if key in seen:
                continue
            seen.add(key)
            shown = dict(item)
            shown["gd_caption"] = gd_figure_caption(shown)
            out.append(shown)
        return out
    except Exception:
        return []


def offers_for_turn(rows, reply: str, user_msg: str, category: str, model: str) -> list[dict]:
    """Library figures for this turn. A missing library figure shows nothing.

    A bundled kit sheet is not a caption the tech sees. A numbered valve step
    shows the kit label, not the owner-manual page caption. A cited page with
    no figure shows that page image, not a figure from another page.
    """
    asked = mf.wants_manual_image(user_msg) or bool(re.search(r"\bshow\b", user_msg or "", re.I))
    cites = _cited_doc_pages(reply) if asked else {}
    cited = _offers_for_cited_pages(rows, cites) if cites else []
    if cited:
        chosen = cited
    else:
        chosen = select_library_figures(rows, reply, user_msg, category, model)
        if cites:
            chosen = [item for item in chosen or [] if _offer_matches_cited_page(item, cites)]
    kit_caption = mf.thetford_procedure_show_caption(reply)
    visible = []
    for item in chosen or []:
        if item.get("bundled"):
            continue
        caption = item.get("caption") or ""
        if re.search(r"bundled kit sheet", caption, re.I):
            continue
        if kit_caption and (_om_page_caption(item) or (item.get("label") or "") == "page"):
            continue
        if kit_caption and "42109" not in f"{item.get('title') or ''} {caption} {item.get('label') or ''}":
            continue
        if kit_caption:
            item = dict(item)
            item["caption"] = kit_caption
            item["label"] = kit_caption
        visible.append(item)
    if kit_caption and not visible:
        offer = mf.thetford_procedure_show_offer(reply)
        if offer:
            visible = [offer]
    asked = mf.wants_manual_image(user_msg) or bool(re.search(r"\bshow\b", user_msg or "", re.I))
    has_art = any((row or {}).get("png") for row in (rows or []))
    if not visible and asked and not has_art:
        offer = mf.thetford_show_offer(reply, user_msg)
        if offer and offer.get("png"):
            visible = [offer]
    return visible


def _chunk_dict(chunk) -> dict:
    if isinstance(chunk, dict):
        excerpt = chunk.get("excerpt") or chunk.get("chunk_text") or ""
        return {
            "document_id": chunk.get("document_id"),
            "title": chunk.get("title") or "",
            "page": chunk.get("page"),
            "excerpt": excerpt,
        }
    return {
        "document_id": getattr(chunk, "document_id", None),
        "title": getattr(chunk, "title", "") or "",
        "page": getattr(chunk, "page", None),
        "excerpt": getattr(chunk, "chunk_text", "") or getattr(chunk, "excerpt", "") or "",
    }


def figure_packets(rows, chunks, job_text: str) -> list[dict]:
    """Figure packets for retrieved chunks that are this case. No bundled kit."""
    bits = [_chunk_dict(chunk) for chunk in chunks or []]
    doc_ids = {int(bit["document_id"]) for bit in bits if bit.get("document_id")}
    titles = [(bit.get("title") or "").strip().lower() for bit in bits if bit.get("title")]
    grouped: dict[int, dict] = {}
    for row in rows or []:
        if (row.get("kind") or "figure") != "figure":
            continue
        title = row.get("title") or ""
        if not fits_case(row, job_text=job_text):
            continue
        doc_id = int(row.get("document_id") or 0)
        title_l = title.lower()
        linked = doc_id in doc_ids or any(
            title_l and (title_l in other or other in title_l) for other in titles
        )
        if not linked:
            continue
        png = row.get("png") or b""
        if png and mf.png_is_blank(png):
            continue
        bucket = grouped.setdefault(
            doc_id,
            {
                "title": title,
                "page": row.get("page"),
                "excerpt": "",
                "figures": [],
                "document_id": doc_id,
                "brand": row.get("brand") or "",
                "product_line": row.get("product_line") or "",
                "models": row.get("models") or "",
                "keywords": row.get("keywords") or "",
                "file_path": row.get("file_path") or "",
                "category_name": row.get("category_name") or "",
            },
        )
        bucket["figures"].append(
            {
                "png": png,
                "label": row.get("label") or "",
                "caption": row.get("caption") or "",
                "bbox": row.get("bbox") or "",
                "page": row.get("page"),
                "title": title,
            }
        )
    packets = []
    for doc_id, bucket in grouped.items():
        if not bucket["figures"]:
            continue
        pages = {fig.get("page") for fig in bucket["figures"]}
        texts = []
        for bit in bits:
            same_doc = bit.get("document_id") and int(bit["document_id"]) == doc_id
            same_title = (bit.get("title") or "").strip().lower() == (bucket["title"] or "").lower()
            if not same_doc and not same_title:
                continue
            if bit.get("page") in pages or not bit.get("page"):
                if bit.get("excerpt"):
                    texts.append(bit["excerpt"])
        bucket["excerpt"] = "\n".join(texts)[:4000]
        if bucket["figures"]:
            bucket["page"] = bucket["figures"][0].get("page")
        packets.append(bucket)
    return packets
