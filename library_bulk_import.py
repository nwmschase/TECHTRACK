"""Manager-only bulk import for the shop Document Library.

A ZIP of PDFs (and an optional manifest) is staged on disk, with a copy under
``imports/bulk/`` in R2 when storage is configured. Each Streamlit run imports
a small batch: sha256 dedupe, R2 upload, document row, and 900-character
chunks with 120 overlap. Progress lives in ``bulk_import_jobs`` and
``bulk_import_items``, so a rerun or a restored database can continue.

This module does not import Streamlit or the page renderer. The Manager Tools
panel is the only caller, and it runs only after that section is selected.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
NEEDS_OCR_NOTE = "needs OCR"
BAD_PDF_NOTE = "bad PDF"
DEFAULT_CATEGORY = "Lippert Unsorted"
DEFAULT_BATCH = 8
MAX_BATCH = 40
LOCK_SECONDS = 600
R2_SUMMARY_PREFIXES = (
    "documents/",
    "certificates/",
    "safety/",
    "backups/",
    "imports/bulk/",
)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_OPEN_STATUSES = ("complete", "abandoned")


def chunk_page_text(page_num: int, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Same windows the library indexer uses: 900 characters, 120 overlap."""
    if len(text) <= chunk_size:
        return [(page_num, text)]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append((page_num, piece))
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def format_elapsed(seconds: float) -> str:
    """Clock time for an import run: ``45s``, ``2m 5s``, or ``1h 1m 1s``."""
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def files_per_minute(files_done: int, elapsed_seconds: float):
    """Files finished divided by minutes. None until the clock has moved."""
    if elapsed_seconds <= 0:
        return None
    return float(files_done) / (float(elapsed_seconds) / 60.0)


def format_import_pace(files_done: int, elapsed_seconds: float) -> str:
    rate = files_per_minute(files_done, elapsed_seconds)
    rate_txt = "—" if rate is None else f"{rate:.1f}"
    return f"Elapsed {format_elapsed(elapsed_seconds)} · {rate_txt} files/minute"


def arm_import_pace(state: dict, done_files: int, now: float, *, reset: bool) -> None:
    """Start the pace clock, or keep the one already running for this ZIP."""
    if reset or not state.get("bulk_pace_started_at") or state.get("bulk_pace_frozen_at"):
        state["bulk_pace_started_at"] = float(now)
        state["bulk_pace_base_done"] = int(done_files)
        state["bulk_pace_frozen_at"] = None


def freeze_import_pace(state: dict, now: float) -> None:
    """Stop the clock when the manager hits Stop or the ZIP finishes."""
    if state.get("bulk_pace_started_at") and not state.get("bulk_pace_frozen_at"):
        state["bulk_pace_frozen_at"] = float(now)


def import_pace_line(state: dict, done_files: int, now: float) -> str:
    started = state.get("bulk_pace_started_at")
    if not started:
        return ""
    frozen = state.get("bulk_pace_frozen_at")
    end = float(frozen) if frozen else float(now)
    elapsed = max(0.0, end - float(started))
    base = int(state.get("bulk_pace_base_done") or 0)
    finished = max(0, int(done_files) - base)
    return format_import_pace(finished, elapsed)


def auto_continue_should_rerun(
    *,
    auto: bool,
    stopped: bool,
    pending: int,
    processed: int,
    status: str,
    error: str = "",
) -> bool:
    """True when Auto-continue should load the next batch.

    Stop, an error, or a finished ZIP ends the chain. A batch that processed
    nothing does not reload, so a stuck ZIP cannot spin.
    """
    if stopped or not auto:
        return False
    if error or status in ("complete", "abandoned", "missing"):
        return False
    return int(pending or 0) > 0 and int(processed or 0) > 0


def format_bytes(num) -> str:
    n = float(num or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} B"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def parse_tier(value) -> int:
    """Lower numbers run first. A blank or non-numeric tier waits until the end."""
    raw = ("" if value is None else str(value)).strip()
    if not raw:
        return 999
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 999


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clip(value, limit: int) -> str:
    return (value or "").strip()[:limit]


def _decode_csv(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _header_key(header: str) -> str:
    key = (header or "").strip().lower().replace("-", " ")
    return re.sub(r"\s+", "_", key)


def _cell(row, canon, name: str) -> str:
    src = canon.get(name)
    if not src:
        return ""
    return (row.get(src) or "").strip()


def _first_cell(row, canon, *names: str) -> str:
    for name in names:
        value = _cell(row, canon, name)
        if value:
            return value
    return ""


class Manifest:
    """CSV rows keyed by full path and by basename."""

    def __init__(self):
        self.index = {}
        self.rows = []

    def row_for(self, member_name: str) -> dict:
        if not self.index:
            return {}
        norm = (member_name or "").replace("\\", "/").lower()
        base = norm.split("/")[-1]
        return dict(self.index.get(norm) or self.index.get(base) or {})


def parse_manifest(data) -> Manifest:
    """Read manifest metadata. Headers are case-insensitive; spaces become underscores.

    ``doc_number`` and ``ti_number`` fill each other when only one is present.
    ``models`` accepts a ``model`` header. The stored title is the title column,
    then clean_title. The filename is the title only when both are blank.
    """
    if isinstance(data, bytes):
        raw = _decode_csv(data)
    else:
        raw = data or ""
    if not str(raw).strip():
        raise ValueError("Manifest CSV is empty.")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ValueError("Manifest CSV needs a header row.")
    canon = {}
    for header in reader.fieldnames:
        canon[_header_key(header)] = header
    if "filename" not in canon:
        raise ValueError("Manifest CSV needs a filename column.")
    manifest = Manifest()
    for row in reader:
        filename = _cell(row, canon, "filename").replace("\\", "/")
        if not filename:
            continue
        clean_title = _cell(row, canon, "clean_title")
        doc_number = _first_cell(row, canon, "doc_number", "ti_number")
        ti_number = _first_cell(row, canon, "ti_number", "doc_number")
        parsed = {
            "filename": filename,
            "category": _cell(row, canon, "category"),
            "doc_type": _cell(row, canon, "doc_type"),
            "title": _cell(row, canon, "title") or clean_title,
            "clean_title": clean_title,
            "brand": _cell(row, canon, "brand"),
            "product_line": _cell(row, canon, "product_line"),
            "models": _first_cell(row, canon, "models", "model"),
            "doc_number": doc_number,
            "ti_number": ti_number,
            "revision_date": _cell(row, canon, "revision_date"),
            "keywords": _cell(row, canon, "keywords"),
            "tier": parse_tier(_cell(row, canon, "tier")),
        }
        manifest.rows.append(parsed)
        norm = filename.lower()
        base = norm.split("/")[-1]
        manifest.index[norm] = parsed
        # First basename wins when two families share a file name.
        manifest.index.setdefault(base, parsed)
    if not manifest.rows:
        raise ValueError("Manifest CSV has no file rows.")
    return manifest


def split_semicolon_list(value) -> list:
    """Split a manifest cell on semicolons, newlines, or pipes. Blank pieces drop out."""
    raw = "" if value is None else str(value)
    seen = set()
    out = []
    for part in re.split(r"[;\n|]+", raw):
        text = part.strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _compact_alnum(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def listed_models_match(models, query: str) -> bool:
    """True when a listed model is the model the tech typed.

    FCR10 matches FCR10DCGTA-BL. 2111-0001 matches Coleman-Mach 2111-0001.
    FACR13 does not match Furrion FCR10DCGTA-BL. An empty list or query does not match.
    """
    if isinstance(models, (list, tuple)):
        entries = [str(item).strip() for item in models if str(item).strip()]
    else:
        entries = split_semicolon_list(models)
    query = (query or "").strip()
    if not entries or not query:
        return False
    q_low = query.lower()
    q_compact = _compact_alnum(query)
    q_tokens = set(re.findall(r"[a-z0-9]+", q_low))
    for entry in entries:
        text = (entry or "").strip()
        if len(text) < 3:
            continue
        low = text.lower()
        if low in q_low:
            return True
        compact = _compact_alnum(low)
        if compact and q_compact and (compact in q_compact or q_compact in compact):
            return True
        for tok in re.findall(r"[a-z0-9]+", low):
            if len(tok) >= 3 and tok in q_tokens:
                return True
            if len(tok) >= 4 and q_compact and tok in q_compact:
                return True
    return False


def _doc_value(doc, name: str) -> str:
    if isinstance(doc, dict):
        value = doc.get(name)
    else:
        value = getattr(doc, name, "")
    return "" if value is None else str(value)


def library_search_blob(doc) -> str:
    """Title, keywords, models, and the other manifest fields, lowercased."""
    parts = [
        _doc_value(doc, name)
        for name in (
            "title",
            "clean_title",
            "keywords",
            "models",
            "brand",
            "product_line",
            "doc_type",
            "doc_number",
            "ti_number",
            "revision_date",
        )
    ]
    return " ".join(parts).lower()


def library_record_matches(doc, query: str = "", brand: str = "", model: str = "") -> bool:
    """Library search: every word must hit the blob, then optional brand and model filters.

    A stored brand is authoritative. A blank brand still matches title and keywords.
    A stored models list is authoritative for the model box. With no list, the model
    box falls back to the same blob so older titles still match.
    """
    blob = library_search_blob(doc)
    terms = (query or "").lower().split()
    if terms and not all(term in blob for term in terms):
        return False
    wanted = (brand or "").strip()
    if wanted and wanted.lower() not in ("(any)", "any"):
        stored = _doc_value(doc, "brand").strip()
        if stored:
            left = wanted.lower()
            right = stored.lower()
            if left != right and left not in right and right not in left:
                return False
        elif wanted.lower() not in blob:
            return False
    typed = (model or "").strip()
    if typed:
        listed = _doc_value(doc, "models")
        if split_semicolon_list(listed):
            if not listed_models_match(listed, typed):
                return False
        elif typed.lower() not in blob:
            return False
    return True


def safe_filename(name: str) -> str:
    base = (name or "manual.pdf").replace("\\", "/").split("/")[-1]
    base = _SAFE_NAME.sub("_", base).strip("._") or "manual.pdf"
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    if len(base) > 140:
        base = base[:130].rstrip("._") + ".pdf"
    return base


def title_from_filename(name: str) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1]
    if base.lower().endswith(".pdf"):
        base = base[:-4]
    base = re.sub(r"\s+", " ", base.replace("_", " ").replace("-", " ")).strip()
    return (base or "Untitled manual")[:250]


def inspect_pdf_bytes(file_bytes: bytes):
    """Return (kind, pages, error).

    kind is ``text``, ``needs_ocr``, or ``bad``.
    A PDF that opens and has pages but no text is kept and flagged needs OCR.
    Bytes that are not a readable PDF are a bad PDF and are not stored.
    """
    if not file_bytes or b"%PDF" not in file_bytes[:1024]:
        return "bad", [], BAD_PDF_NOTE
    try:
        from pypdf import PdfReader
    except ImportError:
        return "bad", [], "pypdf not installed"
    try:
        reader = PdfReader(io.BytesIO(file_bytes), strict=False)
        if getattr(reader, "is_encrypted", False):
            try:
                if reader.decrypt("") == 0:
                    return "bad", [], BAD_PDF_NOTE
            except Exception:
                return "bad", [], BAD_PDF_NOTE
        if len(reader.pages) <= 0:
            return "bad", [], BAD_PDF_NOTE
        pages = []
        for i, page in enumerate(reader.pages, 1):
            try:
                extracted = page.extract_text() or ""
            except Exception:
                extracted = ""
            if extracted.strip():
                pages.append((i, extracted))
    except Exception:
        return "bad", [], BAD_PDF_NOTE
    if not pages:
        return "needs_ocr", [], ""
    return "text", pages, ""


def _apply_schema(conn) -> None:
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name VARCHAR(150) UNIQUE NOT NULL
        )
        """
    )
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY,
            category_id INTEGER NOT NULL,
            title VARCHAR(250) NOT NULL,
            file_path VARCHAR(400) NOT NULL,
            file_type VARCHAR(20) DEFAULT 'pdf',
            uploaded_by INTEGER,
            created_date DATETIME,
            keywords TEXT DEFAULT '',
            indexed BOOLEAN DEFAULT 0,
            index_note VARCHAR(250) DEFAULT '',
            content_sha256 VARCHAR(64),
            doc_type VARCHAR(80),
            ti_number VARCHAR(80),
            import_tier INTEGER,
            byte_size INTEGER,
            needs_ocr BOOLEAN DEFAULT 0,
            clean_title VARCHAR(250),
            brand VARCHAR(80),
            product_line VARCHAR(150),
            models TEXT,
            doc_number VARCHAR(80),
            revision_date VARCHAR(40)
        )
        """
    )
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS doc_chunks (
            id INTEGER PRIMARY KEY,
            document_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            title VARCHAR(250) DEFAULT '',
            page INTEGER DEFAULT 1,
            chunk_text TEXT NOT NULL,
            keywords TEXT DEFAULT ''
        )
        """
    )
    existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documents)").fetchall()}
    extras = (
        ("content_sha256", "VARCHAR(64)"),
        ("doc_type", "VARCHAR(80)"),
        ("ti_number", "VARCHAR(80)"),
        ("import_tier", "INTEGER"),
        ("byte_size", "INTEGER"),
        ("needs_ocr", "BOOLEAN DEFAULT 0"),
        ("clean_title", "VARCHAR(250)"),
        ("brand", "VARCHAR(80)"),
        ("product_line", "VARCHAR(150)"),
        ("models", "TEXT"),
        ("doc_number", "VARCHAR(80)"),
        ("revision_date", "VARCHAR(40)"),
    )
    for name, ddl in extras:
        if name not in existing:
            conn.exec_driver_sql(f"ALTER TABLE documents ADD COLUMN {name} {ddl}")
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_documents_content_sha256 ON documents(content_sha256)"
    )
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS bulk_import_jobs (
            id INTEGER PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'staged',
            created_by INTEGER,
            created_date VARCHAR(40),
            updated_date VARCHAR(40),
            zip_name VARCHAR(250),
            zip_sha256 VARCHAR(64) NOT NULL,
            zip_r2_key TEXT DEFAULT '',
            zip_local_path TEXT DEFAULT '',
            manifest_name VARCHAR(250) DEFAULT '',
            batch_size INTEGER DEFAULT 8,
            total_files INTEGER DEFAULT 0,
            note VARCHAR(400) DEFAULT '',
            lock_until REAL DEFAULT 0
        )
        """
    )
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS bulk_import_items (
            id INTEGER PRIMARY KEY,
            job_id INTEGER NOT NULL,
            ordinal INTEGER NOT NULL,
            filename TEXT NOT NULL,
            category_name VARCHAR(150) DEFAULT '',
            doc_type VARCHAR(80) DEFAULT '',
            title VARCHAR(250) DEFAULT '',
            ti_number VARCHAR(80) DEFAULT '',
            tier INTEGER DEFAULT 999,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            sha256 VARCHAR(64) DEFAULT '',
            document_id INTEGER,
            byte_size INTEGER,
            index_note VARCHAR(250) DEFAULT '',
            error VARCHAR(400) DEFAULT '',
            clean_title VARCHAR(250) DEFAULT '',
            brand VARCHAR(80) DEFAULT '',
            product_line VARCHAR(150) DEFAULT '',
            models TEXT DEFAULT '',
            doc_number VARCHAR(80) DEFAULT '',
            revision_date VARCHAR(40) DEFAULT '',
            keywords TEXT DEFAULT ''
        )
        """
    )
    job_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(bulk_import_jobs)").fetchall()}
    if "lock_until" not in job_cols:
        conn.exec_driver_sql("ALTER TABLE bulk_import_jobs ADD COLUMN lock_until REAL DEFAULT 0")
    item_cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(bulk_import_items)").fetchall()}
    for name, ddl in (
        ("clean_title", "VARCHAR(250)"),
        ("brand", "VARCHAR(80)"),
        ("product_line", "VARCHAR(150)"),
        ("models", "TEXT"),
        ("doc_number", "VARCHAR(80)"),
        ("revision_date", "VARCHAR(40)"),
        ("keywords", "TEXT"),
    ):
        if name not in item_cols:
            conn.exec_driver_sql(f"ALTER TABLE bulk_import_items ADD COLUMN {name} {ddl}")
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_bulk_jobs_sha ON bulk_import_jobs(zip_sha256, status)"
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_bulk_items_job ON bulk_import_items(job_id, status, tier, ordinal)"
    )


def ensure_schema(engine) -> None:
    """Create bulk-import tables and document columns. Safe to call more than once."""
    with engine.begin() as conn:
        _apply_schema(conn)


def _one(session, sql, params=None):
    row = session.execute(text(sql), params or {}).mappings().first()
    return dict(row) if row else None


def _all(session, sql, params=None):
    return [dict(row) for row in session.execute(text(sql), params or {}).mappings().all()]


def _insert(session, sql, params) -> int:
    row = session.execute(text(sql), params).first()
    return int(row[0])


def storage_summary(session, db_path) -> dict:
    doc_count = int(session.execute(text("SELECT COUNT(*) FROM documents")).scalar() or 0)
    needs = int(
        session.execute(text("SELECT COUNT(*) FROM documents WHERE needs_ocr = 1")).scalar() or 0
    )
    path = Path(db_path)
    db_bytes = path.stat().st_size if path.is_file() else 0
    return {
        "doc_count": doc_count,
        "needs_ocr_count": needs,
        "db_bytes": db_bytes,
        "db_path": str(path),
    }


def summarize_prefix_objects(grouped: dict) -> dict:
    """Sum list-objects results by prefix.

    Folder placeholders (keys ending in ``/``) are skipped. ``bytes_known`` is
    false when the API omitted Size for any counted object.
    """
    out = {}
    for prefix, objects in (grouped or {}).items():
        count = 0
        size = 0
        known = True
        for item in objects or []:
            if not isinstance(item, dict):
                continue
            key = item.get("Key") or ""
            if not key or str(key).endswith("/"):
                continue
            count += 1
            if "Size" not in item or item.get("Size") is None:
                known = False
            else:
                size += int(item["Size"])
        out[prefix] = {
            "count": count,
            "bytes": size,
            "bytes_known": known,
            "truncated": False,
        }
    return out


def storage_summary_lines(local: dict, r2_totals, r2_error: str = "") -> list:
    lines = [
        f"Documents: {int(local.get('doc_count') or 0)}",
        f"Database file: {format_bytes(local.get('db_bytes') or 0)}",
    ]
    needs = local.get("needs_ocr_count")
    if needs is not None:
        lines.append(f"Needs OCR: {int(needs)}")
    if r2_error:
        lines.append(f"R2 totals unavailable: {r2_error}")
        return lines
    if not r2_totals:
        lines.append("R2 totals: not loaded. Refresh to list storage by prefix.")
        return lines
    for prefix, info in r2_totals.items():
        if info.get("bytes_known"):
            byte_txt = format_bytes(info.get("bytes") or 0)
        else:
            byte_txt = "size not reported by the API"
        extra = " (partial list)" if info.get("truncated") else ""
        lines.append(f"{prefix} {int(info.get('count') or 0)} objects, {byte_txt}{extra}")
    return lines


def _pdf_members(data: bytes):
    found = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            name = (info.filename or "").replace("\\", "/")
            if not name or name.endswith("/") or info.is_dir():
                continue
            base = name.split("/")[-1]
            if name.startswith("__MACOSX/") or base.startswith("._") or base.startswith("."):
                continue
            if not base.lower().endswith(".pdf"):
                continue
            found.append((name, int(info.file_size or 0)))
    return found


def _stage_fail(message: str) -> dict:
    return {
        "ok": False,
        "job_id": None,
        "resumed": False,
        "total": 0,
        "warning": "",
        "error": message,
        "zip_sha256": "",
        "zip_r2_key": "",
    }


def is_bulk_staging_key(key: str) -> bool:
    """True for one ``imports/bulk/<file>.zip`` object. Document keys are not staging ZIPs."""
    text = (key or "").strip().replace("\\", "/")
    if not text.startswith("imports/bulk/") or not text.endswith(".zip"):
        return False
    name = text[len("imports/bulk/") :]
    return bool(name) and "/" not in name and ".." not in name


def staging_zip_can_drop(progress: dict) -> bool:
    """The cloud ZIP can go when nothing is left to import and nothing failed.

    A failed file keeps the ZIP so that import can resume. Pending or working
    files keep it too.
    """
    if not progress:
        return False
    return (
        int(progress.get("pending") or 0) == 0
        and int(progress.get("working") or 0) == 0
        and int(progress.get("failed") or 0) == 0
    )


def _clear_staging_key(session, job_id: int, key: str) -> None:
    session.execute(
        text(
            """
            UPDATE bulk_import_jobs
            SET zip_r2_key = '', updated_date = :now
            WHERE id = :id AND zip_r2_key = :key
            """
        ),
        {"now": _now(), "id": int(job_id), "key": key},
    )
    session.commit()
    session.expire_all()


def _staging_key_still_needed(session, key: str, except_job_id: int) -> bool:
    """True when another job still has to read this same cloud ZIP."""
    rows = _all(
        session,
        "SELECT id FROM bulk_import_jobs WHERE zip_r2_key = :key AND id != :id",
        {"key": key, "id": int(except_job_id)},
    )
    for row in rows:
        if not staging_zip_can_drop(job_progress(session, int(row["id"]))):
            return True
    return False


def release_finished_staging_zip(session, job: dict, progress: dict, delete_object) -> dict:
    """Delete ``imports/bulk/<sha>.zip`` when this job no longer needs it.

    The object stays when a file failed or work is still pending. A key outside
    ``imports/bulk/`` is never deleted. If another open job uses the same key,
    this job drops its pointer and the object stays.
    """
    key = (job.get("zip_r2_key") or "").strip()
    if not key:
        return {"deleted": False, "kept": False, "key": "", "error": ""}
    if not staging_zip_can_drop(progress):
        return {"deleted": False, "kept": True, "key": key, "error": ""}
    if not is_bulk_staging_key(key):
        return {
            "deleted": False,
            "kept": True,
            "key": key,
            "error": "Refusing to delete a key outside imports/bulk/.",
        }
    if _staging_key_still_needed(session, key, int(job["id"])):
        _clear_staging_key(session, int(job["id"]), key)
        return {"deleted": False, "kept": False, "key": key, "error": ""}
    if delete_object is None:
        return {"deleted": False, "kept": True, "key": key, "error": ""}
    try:
        ok = bool(delete_object(key))
    except Exception as exc:
        return {"deleted": False, "kept": True, "key": key, "error": str(exc)}
    if not ok:
        return {
            "deleted": False,
            "kept": True,
            "key": key,
            "error": "Could not delete the staging ZIP.",
        }
    _clear_staging_key(session, int(job["id"]), key)
    return {"deleted": True, "kept": False, "key": key, "error": ""}


def cleanup_finished_import_zips(session, delete_object) -> dict:
    """Delete staging ZIPs for finished imports that have no failed files.

    Imports that are still open, or that finished with a failed file, keep
    their ZIP so they can resume.
    """
    jobs = _all(
        session,
        """
        SELECT * FROM bulk_import_jobs
        WHERE zip_r2_key IS NOT NULL AND zip_r2_key != ''
        ORDER BY id ASC
        """,
    )
    deleted, kept, errors = [], [], []
    for job in jobs:
        # A previous row in this pass may already have cleared this key.
        current = _one(session, "SELECT zip_r2_key FROM bulk_import_jobs WHERE id = :id", {"id": job["id"]})
        if not current or not (current.get("zip_r2_key") or "").strip():
            continue
        job = dict(job)
        job["zip_r2_key"] = current["zip_r2_key"]
        result = release_finished_staging_zip(
            session, job, job_progress(session, int(job["id"])), delete_object
        )
        if result["deleted"]:
            deleted.append(result["key"])
        elif result["error"]:
            errors.append({"key": result["key"], "error": result["error"]})
        elif result["kept"]:
            kept.append(result["key"])
    return {"deleted": deleted, "kept": kept, "errors": errors}


def job_progress(session, job_id: int) -> dict:
    rows = session.execute(
        text(
            """
            SELECT status, COUNT(*) AS n
            FROM bulk_import_items
            WHERE job_id = :id
            GROUP BY status
            """
        ),
        {"id": job_id},
    ).all()
    counts = {
        "pending": 0,
        "working": 0,
        "imported": 0,
        "needs_ocr": 0,
        "duplicate": 0,
        "failed": 0,
    }
    for status, n in rows:
        counts[str(status)] = int(n)
    counts["total"] = sum(counts.values())
    counts["done_files"] = counts["total"] - counts["pending"] - counts["working"]
    return counts


def list_open_jobs(session) -> list:
    return _all(
        session,
        """
        SELECT * FROM bulk_import_jobs
        WHERE status NOT IN ('complete', 'abandoned')
        ORDER BY id ASC
        """,
    )


def latest_open_job(session):
    return _one(
        session,
        """
        SELECT * FROM bulk_import_jobs
        WHERE status NOT IN ('complete', 'abandoned')
        ORDER BY id DESC
        LIMIT 1
        """,
    )


def recent_items(session, job_id: int, limit: int = 12) -> list:
    return _all(
        session,
        """
        SELECT filename, status, tier, title, index_note, error
        FROM bulk_import_items
        WHERE job_id = :id AND status != 'pending'
        ORDER BY id DESC
        LIMIT :limit
        """,
        {"id": job_id, "limit": int(limit)},
    )


def abandon_job(session, job_id: int) -> None:
    session.execute(
        text(
            """
            UPDATE bulk_import_jobs
            SET status = 'abandoned', lock_until = 0, updated_date = :now
            WHERE id = :id
            """
        ),
        {"id": job_id, "now": _now()},
    )
    session.commit()
    session.expire_all()


def stage_zip_bytes(
    session,
    zip_bytes: bytes,
    *,
    zip_name: str,
    manifest_bytes: bytes | None = None,
    manifest_name: str = "",
    uploaded_by: int | None = None,
    batch_size: int = DEFAULT_BATCH,
    staging_dir="bulk_imports",
    upload_staging=None,
) -> dict:
    """Write the ZIP locally, record one row per PDF, and keep an open job resumable."""
    if not zip_bytes:
        return _stage_fail("Choose a ZIP of PDFs.")
    sha = hashlib.sha256(zip_bytes).hexdigest()
    try:
        members = _pdf_members(zip_bytes)
    except zipfile.BadZipFile:
        return _stage_fail("That file is not a ZIP archive.")
    manifest = Manifest()
    if manifest_bytes:
        try:
            manifest = parse_manifest(manifest_bytes)
        except ValueError as exc:
            return _stage_fail(str(exc))
    if not members and not manifest.rows:
        return _stage_fail("The ZIP has no PDF files.")
    batch = max(1, min(int(batch_size or DEFAULT_BATCH), MAX_BATCH))
    folder = Path(staging_dir)
    folder.mkdir(parents=True, exist_ok=True)
    local = folder / f"{sha}.zip"
    local.write_bytes(zip_bytes)
    existing = _one(
        session,
        """
        SELECT * FROM bulk_import_jobs
        WHERE zip_sha256 = :sha AND status NOT IN ('complete', 'abandoned')
        ORDER BY id DESC
        LIMIT 1
        """,
        {"sha": sha},
    )
    if existing:
        session.execute(
            text(
                """
                UPDATE bulk_import_jobs
                SET zip_local_path = :path,
                    zip_name = :name,
                    batch_size = :batch,
                    updated_date = :now,
                    lock_until = 0
                WHERE id = :id
                """
            ),
            {
                "path": str(local),
                "name": _clip(zip_name, 250) or "library.zip",
                "batch": batch,
                "now": _now(),
                "id": existing["id"],
            },
        )
        session.commit()
        session.expire_all()
        progress = job_progress(session, int(existing["id"]))
        return {
            "ok": True,
            "job_id": int(existing["id"]),
            "resumed": True,
            "total": progress["total"],
            "warning": "This ZIP is already in progress. Continuing that import.",
            "error": "",
            "zip_sha256": sha,
            "zip_r2_key": existing.get("zip_r2_key") or "",
        }

    present = set()
    planned = []
    for name, _size in members:
        meta = manifest.row_for(name)
        planned.append(
            _planned_item(meta, name, status="pending", error="", title_fallback=title_from_filename(name))
        )
        norm = name.lower()
        present.add(norm)
        present.add(norm.split("/")[-1])
    for row in manifest.rows:
        norm = row["filename"].lower()
        base = norm.split("/")[-1]
        if norm in present or base in present:
            continue
        planned.append(
            _planned_item(
                row,
                row["filename"],
                status="failed",
                error="not in zip",
                title_fallback=title_from_filename(row["filename"]),
            )
        )
    if not planned:
        return _stage_fail("The ZIP has no PDF files.")
    planned.sort(key=lambda item: (item["tier"], item["filename"].lower()))
    try:
        job_id = _insert(
            session,
            """
            INSERT INTO bulk_import_jobs (
                status, created_by, created_date, updated_date, zip_name, zip_sha256,
                zip_r2_key, zip_local_path, manifest_name, batch_size, total_files, note, lock_until
            ) VALUES (
                'staged', :created_by, :now, :now, :zip_name, :sha,
                '', :path, :manifest_name, :batch, :total, '', 0
            )
            RETURNING id
            """,
            {
                "created_by": uploaded_by,
                "now": _now(),
                "zip_name": _clip(zip_name, 250) or "library.zip",
                "sha": sha,
                "path": str(local),
                "manifest_name": _clip(manifest_name, 250),
                "batch": batch,
                "total": len(planned),
            },
        )
        for ordinal, item in enumerate(planned, 1):
            session.execute(
                text(
                    """
                    INSERT INTO bulk_import_items (
                        job_id, ordinal, filename, category_name, doc_type, title,
                        ti_number, tier, status, error,
                        clean_title, brand, product_line, models, doc_number,
                        revision_date, keywords
                    ) VALUES (
                        :job_id, :ordinal, :filename, :category_name, :doc_type, :title,
                        :ti_number, :tier, :status, :error,
                        :clean_title, :brand, :product_line, :models, :doc_number,
                        :revision_date, :keywords
                    )
                    """
                ),
                {"job_id": job_id, "ordinal": ordinal, **item},
            )
        session.commit()
    except Exception as exc:
        session.rollback()
        return _stage_fail(f"Could not save the import: {exc}")

    warning = ""
    r2_key = ""
    if upload_staging is not None:
        r2_key = f"imports/bulk/{sha}.zip"
        try:
            saved = bool(upload_staging(zip_bytes, r2_key, "application/zip"))
        except Exception:
            saved = False
        if saved:
            session.execute(
                text("UPDATE bulk_import_jobs SET zip_r2_key = :key, updated_date = :now WHERE id = :id"),
                {"key": r2_key, "now": _now(), "id": job_id},
            )
            session.commit()
        else:
            r2_key = ""
            warning = (
                "The ZIP is saved on this server, but the cloud copy failed. "
                "Upload the same ZIP again after a reboot to continue."
            )
    session.expire_all()
    return {
        "ok": True,
        "job_id": job_id,
        "resumed": False,
        "total": len(planned),
        "warning": warning,
        "error": "",
        "zip_sha256": sha,
        "zip_r2_key": r2_key,
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_zip(job: dict, download_zip):
    path = Path(job.get("zip_local_path") or "")
    if path.is_file() and path.stat().st_size > 0:
        return path, ""
    key = (job.get("zip_r2_key") or "").strip()
    if key and download_zip is not None:
        try:
            data = download_zip(key)
        except Exception:
            data = None
        if data:
            if hashlib.sha256(data).hexdigest() != (job.get("zip_sha256") or ""):
                return None, "The cloud copy of the ZIP does not match this import."
            if not path:
                path = Path("bulk_imports") / f"{job['zip_sha256']}.zip"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return path, ""
    return None, "The ZIP is not on this server. Upload the same ZIP again to continue."


def _category_id(session, name: str) -> int:
    cleaned = _clip(name, 150) or DEFAULT_CATEGORY
    row = _one(
        session,
        "SELECT id FROM categories WHERE lower(name) = lower(:name) LIMIT 1",
        {"name": cleaned},
    )
    if row:
        return int(row["id"])
    return _insert(
        session,
        "INSERT INTO categories (name) VALUES (:name) RETURNING id",
        {"name": cleaned},
    )


def _key_taken(session, key: str, taken: set) -> bool:
    if key in taken:
        return True
    row = session.execute(
        text("SELECT 1 FROM documents WHERE file_path = :key LIMIT 1"),
        {"key": key},
    ).first()
    return row is not None


def build_document_key(session, category_id: int, filename: str, item_id: int, taken: set) -> str:
    """``documents/{cat_id}_{timestamp}_{filename}``, with the item id if that key is taken."""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    safe = safe_filename(filename)
    key = f"documents/{int(category_id)}_{ts}_{safe}"
    if _key_taken(session, key, taken):
        stem = safe[:-4] if safe.lower().endswith(".pdf") else safe
        key = f"documents/{int(category_id)}_{ts}_{int(item_id)}_{stem}.pdf"
    taken.add(key)
    return key[:400]


def _find_duplicate(session, sha: str):
    if not sha:
        return None
    return _one(
        session,
        """
        SELECT id, title FROM documents
        WHERE content_sha256 = :sha AND content_sha256 IS NOT NULL AND content_sha256 != ''
        LIMIT 1
        """,
        {"sha": sha},
    )


def _planned_item(meta: dict, filename: str, *, status: str, error: str, title_fallback: str) -> dict:
    meta = meta or {}
    title = (meta.get("title") or "").strip() or title_fallback
    return {
        "filename": filename,
        "category_name": _clip(meta.get("category") or DEFAULT_CATEGORY, 150),
        "doc_type": _clip(meta.get("doc_type") or "", 80),
        "title": _clip(title, 250),
        "clean_title": _clip(meta.get("clean_title") or "", 250),
        "brand": _clip(meta.get("brand") or "", 80),
        "product_line": _clip(meta.get("product_line") or "", 150),
        "models": (meta.get("models") or "").strip(),
        "doc_number": _clip(meta.get("doc_number") or "", 80),
        "revision_date": _clip(meta.get("revision_date") or "", 40),
        "keywords": (meta.get("keywords") or "").strip(),
        "ti_number": _clip(meta.get("ti_number") or "", 80),
        "tier": int(meta.get("tier") if meta else 999),
        "status": status,
        "error": error or "",
    }


def _join_unique(parts) -> str:
    out = []
    seen = set()
    for part in parts:
        text = ("" if part is None else str(part)).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return " ".join(out)


def _keywords(item: dict) -> str:
    """Search text copied onto the document and each chunk.

    The columns stay the source of truth for brand and model filters. This
    string is what title/keyword search already scans.
    """
    parts = []
    parts.extend(split_semicolon_list(item.get("keywords") or ""))
    parts.extend(split_semicolon_list(item.get("models") or ""))
    for field in (
        "brand",
        "product_line",
        "doc_number",
        "ti_number",
        "doc_type",
        "category_name",
        "clean_title",
        "revision_date",
    ):
        parts.append(item.get(field) or "")
    return _join_unique(parts)


def _set_item(session, item_id: int, **fields) -> None:
    if not fields:
        return
    clause = ", ".join(f"{name} = :{name}" for name in fields)
    fields["id"] = item_id
    session.execute(text(f"UPDATE bulk_import_items SET {clause} WHERE id = :id"), fields)


def _read_member(zip_path: Path, name: str) -> bytes:
    with zipfile.ZipFile(zip_path) as archive:
        return archive.read(name)


def _import_one(session, item: dict, zip_path: Path, upload_pdf, taken: set, uploaded_by) -> str:
    data = _read_member(zip_path, item["filename"])
    sha = hashlib.sha256(data).hexdigest()
    duplicate = _find_duplicate(session, sha)
    if duplicate:
        _set_item(
            session,
            item["id"],
            status="duplicate",
            sha256=sha,
            document_id=int(duplicate["id"]),
            byte_size=len(data),
            index_note="duplicate",
            error="",
        )
        return "duplicate"
    kind, pages, err = inspect_pdf_bytes(data)
    if kind == "bad":
        _set_item(
            session,
            item["id"],
            status="failed",
            sha256=sha,
            byte_size=len(data),
            index_note="",
            error=_clip(err or BAD_PDF_NOTE, 400),
        )
        return "failed"
    category_id = _category_id(session, item.get("category_name") or DEFAULT_CATEGORY)
    key = build_document_key(session, category_id, item["filename"], int(item["id"]), taken)
    try:
        uploaded = bool(upload_pdf(data, key, "application/pdf")) if upload_pdf else False
    except Exception:
        uploaded = False
    if not uploaded:
        _set_item(
            session,
            item["id"],
            status="failed",
            sha256=sha,
            byte_size=len(data),
            error="upload to storage failed",
        )
        return "failed"
    chunks = []
    needs = kind == "needs_ocr"
    if not needs:
        for page_num, page_text in pages:
            chunks.extend(chunk_page_text(page_num, page_text))
        if not chunks:
            needs = True
    title = _clip(item.get("title") or title_from_filename(item["filename"]), 250)
    keywords = _keywords(item)
    note = NEEDS_OCR_NOTE if needs else f"Indexed {len(chunks)} chunks from {len(pages)} pages"
    doc_id = _insert(
        session,
        """
        INSERT INTO documents (
            category_id, title, file_path, file_type, uploaded_by, created_date,
            keywords, indexed, index_note, content_sha256, doc_type, ti_number,
            import_tier, byte_size, needs_ocr,
            clean_title, brand, product_line, models, doc_number, revision_date
        ) VALUES (
            :category_id, :title, :file_path, 'pdf', :uploaded_by, :created,
            :keywords, :indexed, :index_note, :sha, :doc_type, :ti_number,
            :tier, :byte_size, :needs_ocr,
            :clean_title, :brand, :product_line, :models, :doc_number, :revision_date
        )
        RETURNING id
        """,
        {
            "category_id": category_id,
            "title": title,
            "file_path": key,
            "uploaded_by": uploaded_by,
            "created": _now(),
            "keywords": keywords,
            "indexed": 0 if needs else 1,
            "index_note": _clip(note, 250),
            "sha": sha,
            "doc_type": _clip(item.get("doc_type") or "", 80),
            "ti_number": _clip(item.get("ti_number") or "", 80),
            "tier": int(item.get("tier") if item.get("tier") is not None else 999),
            "byte_size": len(data),
            "needs_ocr": 1 if needs else 0,
            "clean_title": _clip(item.get("clean_title") or "", 250),
            "brand": _clip(item.get("brand") or "", 80),
            "product_line": _clip(item.get("product_line") or "", 150),
            "models": (item.get("models") or "").strip(),
            "doc_number": _clip(item.get("doc_number") or item.get("ti_number") or "", 80),
            "revision_date": _clip(item.get("revision_date") or "", 40),
        },
    )
    for page_num, chunk in chunks:
        session.execute(
            text(
                """
                INSERT INTO doc_chunks (
                    document_id, category_id, title, page, chunk_text, keywords
                ) VALUES (
                    :document_id, :category_id, :title, :page, :chunk_text, :keywords
                )
                """
            ),
            {
                "document_id": doc_id,
                "category_id": category_id,
                "title": title,
                "page": int(page_num),
                "chunk_text": chunk,
                "keywords": keywords,
            },
        )
    _set_item(
        session,
        item["id"],
        status="needs_ocr" if needs else "imported",
        sha256=sha,
        document_id=doc_id,
        byte_size=len(data),
        index_note=_clip(note, 250),
        error="",
    )
    return "needs_ocr" if needs else "imported"


def _empty_result(job_id, status: str, *, error: str = "", busy: bool = False, progress=None) -> dict:
    progress = progress or {
        "pending": 0,
        "working": 0,
        "imported": 0,
        "needs_ocr": 0,
        "duplicate": 0,
        "failed": 0,
        "total": 0,
        "done_files": 0,
    }
    return {
        "ok": not error,
        "job_id": job_id,
        "processed": 0,
        "imported": 0,
        "needs_ocr": 0,
        "duplicate": 0,
        "failed": 0,
        "pending": progress["pending"],
        "total": progress["total"],
        "status": status,
        "backup": None,
        "busy": busy,
        "error": error,
    }


def process_next_batch(
    session,
    job_id: int,
    *,
    upload_pdf,
    download_zip=None,
    backup_db=None,
    delete_zip=None,
    batch_size: int | None = None,
    progress=None,
) -> dict:
    """Import the next N pending files. Commits each file, then asks for a DB backup.

    When the ZIP finishes with nothing pending and nothing failed, ``delete_zip``
    removes the ``imports/bulk/`` copy. A failed file leaves that copy in place.
    """
    job = _one(session, "SELECT * FROM bulk_import_jobs WHERE id = :id", {"id": job_id})
    if not job:
        return _empty_result(job_id, "missing", error="Import job not found.")
    if job["status"] in _OPEN_STATUSES:
        counts = job_progress(session, job_id)
        return _empty_result(job_id, job["status"], progress=counts)
    now = time.time()
    lock_until = float(job.get("lock_until") or 0)
    if lock_until > now:
        counts = job_progress(session, job_id)
        return _empty_result(
            job_id,
            job["status"],
            error="This import is already running.",
            busy=True,
            progress=counts,
        )
    batch = batch_size if batch_size is not None else job.get("batch_size") or DEFAULT_BATCH
    batch = max(1, min(int(batch), MAX_BATCH))
    session.execute(
        text(
            """
            UPDATE bulk_import_jobs
            SET status = 'running', batch_size = :batch, lock_until = :lock, updated_date = :now
            WHERE id = :id
            """
        ),
        {"batch": batch, "lock": now + LOCK_SECONDS, "now": _now(), "id": job_id},
    )
    session.commit()
    imported = needs = duplicates = failed = processed = 0
    zip_error = ""
    try:
        session.execute(
            text(
                """
                UPDATE bulk_import_items
                SET status = 'pending'
                WHERE job_id = :id AND status = 'working'
                """
            ),
            {"id": job_id},
        )
        session.commit()
        path, zip_error = _resolve_zip(job, download_zip)
        if path is not None and _sha256_file(path) != job["zip_sha256"]:
            path = None
            zip_error = "The ZIP on disk does not match this import."
        if path is not None and str(path) != (job.get("zip_local_path") or ""):
            session.execute(
                text("UPDATE bulk_import_jobs SET zip_local_path = :path WHERE id = :id"),
                {"path": str(path), "id": job_id},
            )
            session.commit()
        if path is not None:
            pending_rows = _all(
                session,
                """
                SELECT * FROM bulk_import_items
                WHERE job_id = :id AND status = 'pending'
                ORDER BY tier ASC, ordinal ASC, id ASC
                LIMIT :batch
                """,
                {"id": job_id, "batch": batch},
            )
            for row in pending_rows:
                session.execute(
                    text(
                        """
                        UPDATE bulk_import_items
                        SET status = 'working'
                        WHERE id = :id AND status = 'pending'
                        """
                    ),
                    {"id": row["id"]},
                )
            session.commit()
            working = _all(
                session,
                """
                SELECT * FROM bulk_import_items
                WHERE job_id = :id AND status = 'working'
                ORDER BY tier ASC, ordinal ASC, id ASC
                """,
                {"id": job_id},
            )
            taken = set()
            for index, item in enumerate(working, 1):
                try:
                    status = _import_one(
                        session,
                        item,
                        path,
                        upload_pdf,
                        taken,
                        job.get("created_by"),
                    )
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    _set_item(
                        session,
                        item["id"],
                        status="failed",
                        error=_clip(f"{BAD_PDF_NOTE}: {exc}", 400),
                    )
                    session.commit()
                    status = "failed"
                processed += 1
                if status == "imported":
                    imported += 1
                elif status == "needs_ocr":
                    needs += 1
                elif status == "duplicate":
                    duplicates += 1
                else:
                    failed += 1
                if progress:
                    try:
                        progress(index, len(working), item.get("filename") or "")
                    except Exception:
                        pass
    finally:
        counts = job_progress(session, job_id)
        finished = counts["pending"] == 0 and counts["working"] == 0 and not zip_error
        new_status = "complete" if finished else "paused"
        session.execute(
            text(
                """
                UPDATE bulk_import_jobs
                SET status = :status, lock_until = 0, updated_date = :now
                WHERE id = :id
                """
            ),
            {"status": new_status, "now": _now(), "id": job_id},
        )
        session.commit()
        session.expire_all()
    backup = None
    if backup_db and (processed > 0 or new_status == "complete"):
        try:
            backup = backup_db()
        except Exception as exc:
            backup = (False, str(exc))
    counts = job_progress(session, job_id)
    staging = {"deleted": False, "kept": False, "key": "", "error": ""}
    if new_status == "complete":
        staging = release_finished_staging_zip(session, job, counts, delete_zip)
    return {
        "ok": not zip_error,
        "job_id": job_id,
        "processed": processed,
        "imported": imported,
        "needs_ocr": needs,
        "duplicate": duplicates,
        "failed": failed,
        "pending": counts["pending"],
        "total": counts["total"],
        "status": new_status,
        "backup": backup,
        "busy": False,
        "error": zip_error,
        "staging_zip_deleted": staging["deleted"],
        "staging_zip_kept": staging["kept"],
        "staging_zip_error": staging["error"],
    }


def _status_label(status: str) -> str:
    if status == "needs_ocr":
        return NEEDS_OCR_NOTE
    if status == "duplicate":
        return "duplicate"
    if status == "imported":
        return "imported"
    if status == "failed":
        return "failed"
    return status or ""


def render_manager_bulk_panel(
    st,
    *,
    session,
    db_path,
    user_id,
    upload_bytes,
    download_bytes,
    backup_db,
    r2_prefix_totals,
    r2_ready: bool,
    staging_dir="bulk_imports",
    delete_bytes=None,
) -> None:
    """Draw the Manager Tools bulk-import panel.

    Counting records and reading the database file size are the only work that
    happens on open. PDF parsing, R2 uploads, and the cloud DB backup run when
    the manager starts or continues a batch. The Guided Diagnostics and Bay
    sections do not call this.
    """
    st.caption(
        "Upload a ZIP of PDFs, up to about 180 MB (the upload limit is 200 MB). "
        "Split the Lippert and Furrion library into several ZIPs. "
        "An optional manifest CSV sets filename, clean_title, brand, product_line, models, "
        "category, doc_type, doc_number, revision_date, keywords, and tier. "
        "models and keywords are semicolon lists. doc_number is the CCD or TI number. "
        "Lower tier numbers run first. A category from the manifest is created when it is new."
    )
    st.caption(
        "Each batch imports a few files and then saves the database to cloud storage. "
        "Leave this page whenever you need Guided Diagnostics or a Bay sheet. "
        "Progress stays in the database, so you can continue after a rerun or a reboot. "
        "When a ZIP finishes with no failed files, its cloud copy under imports/bulk/ is removed. "
        "A ZIP with a failed file stays so the import can resume."
    )
    try:
        local = storage_summary(session, db_path)
    except Exception as exc:
        st.error(f"Could not read the library summary: {exc}")
        local = {"doc_count": 0, "needs_ocr_count": 0, "db_bytes": 0}
    cached = st.session_state.get("bulk_r2_totals")
    cached_err = st.session_state.get("bulk_r2_error") or ""
    if st.button("Refresh R2 storage totals", key="bulk_r2_refresh"):
        try:
            cached, cached_err = r2_prefix_totals(R2_SUMMARY_PREFIXES)
        except Exception as exc:
            cached, cached_err = {}, str(exc)
        st.session_state["bulk_r2_totals"] = cached
        st.session_state["bulk_r2_error"] = cached_err
    for line in storage_summary_lines(local, cached, cached_err):
        st.write(line)
    if st.button("Clean up finished import ZIPs", key="bulk_cleanup_zips"):
        if delete_bytes is None or not r2_ready:
            st.error("R2 storage is not configured. Check Streamlit Secrets.")
        else:
            cleaned = cleanup_finished_import_zips(session, delete_bytes)
            st.success(
                f"Removed {len(cleaned['deleted'])} finished staging ZIP(s) from cloud storage."
            )
            if cleaned["kept"]:
                st.info(
                    f"Kept {len(cleaned['kept'])} ZIP(s). "
                    "Those imports still have unfinished or failed files, so they can resume."
                )
            for item in cleaned["errors"]:
                st.warning(f"{item['key']}: {item['error']}")
    if not r2_ready:
        st.error("R2 storage is not configured. Check Streamlit Secrets before starting an import.")

    opens = []
    try:
        opens = list_open_jobs(session)
    except Exception as exc:
        st.error(f"Could not read import progress: {exc}")
    job = None
    if len(opens) == 1:
        job = opens[0]
    elif len(opens) > 1:
        labels = [f"#{row['id']} {row['zip_name']} ({row['status']})" for row in opens]
        pick = st.selectbox("In-progress import", labels, key="bulk_job_pick")
        job = opens[labels.index(pick)]

    if "bulk_batch_size" not in st.session_state:
        st.session_state["bulk_batch_size"] = DEFAULT_BATCH
    batch_size = int(
        st.number_input(
            "Files per batch",
            min_value=1,
            max_value=MAX_BATCH,
            step=1,
            key="bulk_batch_size",
            help="Each run imports this many PDFs, then saves the database.",
        )
    )
    auto = st.checkbox(
        "Auto-continue",
        key="bulk_auto_continue",
        help=(
            "After each batch, start the next one until this ZIP is done. "
            "Each batch still cloud-saves the database. Stop finishes the current batch, then waits."
        ),
    )
    if not auto:
        st.session_state["bulk_run_chain"] = False

    if job:
        counts = job_progress(session, int(job["id"]))
        total = max(int(counts["total"]), 1)
        st.progress(min(1.0, counts["done_files"] / total))
        st.write(
            f"**{counts['done_files']}** of **{counts['total']}** files in {job['zip_name']} "
            f"(tier order, batch of {batch_size})"
        )
        st.write(
            f"Imported {counts['imported']} · needs OCR {counts['needs_ocr']} · "
            f"duplicates {counts['duplicate']} · failed {counts['failed']} · "
            f"remaining {counts['pending']}"
        )
        pace = import_pace_line(st.session_state, counts["done_files"], time.time())
        if pace:
            st.write(pace)
        for item in recent_items(session, int(job["id"])):
            note = item.get("error") or item.get("index_note") or ""
            st.write(
                f"{_status_label(item.get('status') or '')}: {item.get('filename')} "
                f"(tier {item.get('tier')}) {note}".rstrip()
            )
        stop = st.button("Stop", key="bulk_stop")
        go = st.button("Import next batch", type="primary", key="bulk_go")
        abandon = st.button("Abandon this import", key="bulk_abandon")
        if stop:
            st.session_state["bulk_run_chain"] = False
            freeze_import_pace(st.session_state, time.time())
        if abandon:
            st.session_state["bulk_run_chain"] = False
            abandon_job(session, int(job["id"]))
            st.rerun()
        if go:
            st.session_state["bulk_run_chain"] = bool(auto)
        should_run = bool(go) or bool(st.session_state.get("bulk_run_chain"))
        if stop:
            should_run = False
        if should_run and r2_ready:
            _run_batch(
                st,
                session,
                job_id=int(job["id"]),
                upload_bytes=upload_bytes,
                download_bytes=download_bytes,
                backup_db=backup_db,
                batch_size=batch_size,
                auto=auto,
                stopped=False,
                reset_pace=bool(go),
                delete_zip=delete_bytes,
            )
        elif should_run and not r2_ready:
            st.session_state["bulk_run_chain"] = False

    zip_up = st.file_uploader("ZIP of PDFs", type=["zip"], key="bulk_zip")
    manifest = st.file_uploader("Manifest CSV (optional)", type=["csv"], key="bulk_manifest")
    if st.button("Start bulk import", type="primary", key="bulk_start"):
        if not r2_ready:
            st.error("R2 storage is not configured. Check Streamlit Secrets.")
        elif zip_up is None:
            st.warning("Choose a ZIP of PDFs.")
        else:
            staged = stage_zip_bytes(
                session,
                zip_up.getvalue(),
                zip_name=zip_up.name,
                manifest_bytes=manifest.getvalue() if manifest is not None else None,
                manifest_name=manifest.name if manifest is not None else "",
                uploaded_by=user_id,
                batch_size=batch_size,
                staging_dir=staging_dir,
                upload_staging=upload_bytes,
            )
            if not staged["ok"]:
                st.error(staged["error"])
            else:
                if staged.get("warning"):
                    st.warning(staged["warning"])
                st.session_state["bulk_run_chain"] = bool(auto)
                _run_batch(
                    st,
                    session,
                    job_id=int(staged["job_id"]),
                    upload_bytes=upload_bytes,
                    download_bytes=download_bytes,
                    backup_db=backup_db,
                    batch_size=batch_size,
                    auto=auto,
                    stopped=False,
                    reset_pace=True,
                    delete_zip=delete_bytes,
                )


def _run_batch(
    st,
    session,
    *,
    job_id,
    upload_bytes,
    download_bytes,
    backup_db,
    batch_size,
    auto,
    stopped=False,
    reset_pace=False,
    delete_zip=None,
) -> None:
    before = job_progress(session, job_id)
    arm_import_pace(st.session_state, before["done_files"], time.time(), reset=reset_pace)
    holder = {"bar": None}

    def _tick(index, total, filename):
        if holder["bar"] is None:
            holder["bar"] = st.progress(0.0)
        holder["bar"].progress(min(1.0, index / max(total, 1)), text=filename or "Importing")

    try:
        result = process_next_batch(
            session,
            job_id,
            upload_pdf=upload_bytes,
            download_zip=download_bytes,
            backup_db=backup_db,
            delete_zip=delete_zip,
            batch_size=batch_size,
            progress=_tick,
        )
    except Exception as exc:
        st.session_state["bulk_run_chain"] = False
        st.error(f"Bulk import stopped: {exc}")
        return
    if result.get("staging_zip_deleted"):
        st.caption("Removed the finished staging ZIP from cloud storage.")
    elif result.get("staging_zip_error"):
        st.warning(
            "The import finished, but the staging ZIP is still in cloud storage: "
            + result["staging_zip_error"]
        )
    elif result.get("staging_zip_kept") and result.get("status") == "complete":
        st.caption(
            "The staging ZIP stays in cloud storage because a file failed. The import can resume."
        )
    if result.get("error"):
        st.session_state["bulk_run_chain"] = False
        st.error(result["error"])
    elif result.get("busy"):
        st.session_state["bulk_run_chain"] = False
        st.warning(result.get("error") or "This import is already running.")
    else:
        st.write(
            f"This batch: imported {result['imported']}, needs OCR {result['needs_ocr']}, "
            f"duplicates {result['duplicate']}, failed {result['failed']}."
        )
    backup = result.get("backup")
    if isinstance(backup, tuple) and len(backup) == 2:
        ok, note = backup
        if ok:
            st.success(note or "Database saved to cloud storage.")
        elif note:
            st.warning(note)
    now = time.time()
    carry_on = auto_continue_should_rerun(
        auto=bool(auto) and bool(st.session_state.get("bulk_run_chain")),
        stopped=stopped,
        pending=int(result.get("pending") or 0),
        processed=int(result.get("processed") or 0),
        status=result.get("status") or "",
        error=result.get("error") or "",
    )
    if not carry_on:
        freeze_import_pace(st.session_state, now)
    counts = job_progress(session, job_id)
    pace = import_pace_line(st.session_state, counts["done_files"], now)
    if pace:
        st.write(pace)
    if result.get("status") == "complete" and not result.get("error"):
        st.success(
            f"Import finished. {result['total']} file(s) recorded. "
            "Upload the next ZIP when you are ready."
        )
        st.session_state["bulk_run_chain"] = False
        return
    if carry_on:
        st.rerun()
    else:
        st.session_state["bulk_run_chain"] = False
