"""Page images and figure crops for every document in the shop library.

Rendering uses the same 150 dpi cropper as a single upload. The PNG is stored
in R2 at image_path. The database row keeps that key, the caption, the page,
the box, and chunk_id for the first chunk on that page. A local cache speeds
up the next read. This module does not import Streamlit.
"""
from __future__ import annotations

import gc
import time
from pathlib import Path

from sqlalchemy import text

import manual_figures as mf

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

BUNDLED_NOTE = "Bundled kit sheet, not from the shop library."
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


def _ship_png(png: bytes, path: str, upload_png, root) -> None:
    """Upload one PNG, optionally cache it, then the caller drops the bytes."""
    if root is not None and png and path:
        dest = Path(root) / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(png)
    if upload_png and png and path:
        try:
            upload_png(png, path, "image/png")
        except Exception:
            pass


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
        _ship_png(png, path, upload_png, root)
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
            _ship_png(fig_png, fig_path, upload_png, root)
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
        "SELECT id, title, file_path, file_type FROM documents ORDER BY id",
    )
    kept = []
    for row in rows:
        kind = (row.get("file_type") or "").lower()
        path = (row.get("file_path") or "").lower()
        if kind == "pdf" or path.endswith(".pdf"):
            kept.append(row)
    return kept


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
    """Bytes the backfill would write for the PDFs already in this database.

    Page images are one PNG per page (the highest chunk page, or 1). Figure
    crops use the kit-sheet rate from the measured sample, which is higher
    than a text manual. The bytes are the R2 objects only.
    """
    ensure_ready(session)
    docs = _pdf_documents(session)
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
            "No manuals are in this database, so the backfill would store 0 bytes in R2. "
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
        "This count is the manuals in this database."
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


def ensure_job(session) -> int:
    """Open a backfill for every PDF, or return the job that still has work."""
    current = open_job(session)
    if current:
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
    for doc in _pdf_documents(session):
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
    done = failed = processed = 0
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
               d.title AS title, d.file_path AS file_path, d.brand AS brand
        FROM doc_assets a
        JOIN documents d ON d.id = a.document_id
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


def _library_miss(*parts) -> bool:
    blob = " ".join(str(part or "") for part in parts).lower()
    return "document in the shop library for this unit" in blob


def select_library_figures(rows, reply: str, user_msg: str, category: str, model: str) -> list[dict]:
    """Pick figure crops for this job from any brand. Zero means no library match.

    A document scores on its title and brand. A figure scores on its caption.
    Another brand's crop is left out once the winning brand is known.
    """
    import re

    job = " ".join(part for part in (category, model, user_msg, reply) if part)
    figures = [row for row in rows or [] if (row.get("kind") or "figure") == "figure"]
    if not figures:
        return []
    named = mf._numbers_named(user_msg or "") or mf._numbers_named(reply or "")
    ask_words = _words(f"{user_msg or ''} {reply or ''}")
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
            figure_score = len(_words(label) & ask_words)
            if named and any(number in named for number in nums):
                figure_score += 8
            chosen.append((figure_score, bucket["score"], row))
    if not chosen:
        return []
    positive = [item for item in chosen if item[0] > 0]
    pool = positive or chosen
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


def offers_for_turn(rows, reply: str, user_msg: str, category: str, model: str) -> list[dict]:
    """Library figures for any brand. A bundled Thetford sheet is the last resort.

    The last resort is labeled, and a library-miss reply does not get one.
    """
    chosen = select_library_figures(rows, reply, user_msg, category, model)
    if chosen:
        return chosen
    if _library_miss(reply, user_msg, category, model):
        return []
    fallback = mf.bundled_thetford_offers(reply, user_msg, category, model)
    labeled = []
    for item in fallback:
        caption = item.get("caption") or ""
        if not caption.startswith(BUNDLED_NOTE):
            caption = f"{BUNDLED_NOTE} {caption}".strip()
        labeled.append({**item, "caption": caption, "bundled": True, "bbox": item.get("bbox") or ""})
    return labeled


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
    """Figure packets for the retrieved chunks. Any brand. No bundled kit."""
    bits = [_chunk_dict(chunk) for chunk in chunks or []]
    doc_ids = {int(bit["document_id"]) for bit in bits if bit.get("document_id")}
    titles = [(bit.get("title") or "").strip().lower() for bit in bits if bit.get("title")]
    grouped: dict[int, dict] = {}
    for row in rows or []:
        if (row.get("kind") or "figure") != "figure":
            continue
        title = row.get("title") or ""
        if mf.brands_conflict(job_text, f"{title} {row.get('brand') or ''}"):
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
            {"title": title, "page": row.get("page"), "excerpt": "", "figures": [], "document_id": doc_id},
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
