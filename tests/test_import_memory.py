"""Bulk import stays inside a memory bound on a long manual.

The old renderer kept every page PNG. On a 136-page PDF whose rendered pages
were 64,784,413 bytes, peak RSS rose by 122,772 KB (about 120 MB), to 227,024 KB.
Rendering one page at a time grew peak RSS by 904 KB on that same PDF.
"""
import gc
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import library_bulk_import as bulk
import library_figure_backfill as fb
import manual_figures as mf

PAGES = 136
# One page pixmap is about 6 MB. Holding every page was about 120 MB above
# the baseline. Streaming has to stay well under that.
GROWTH_LIMIT_KB = 80 * 1024


def _rss_kb() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def _photo_pdf(pages: int) -> bytes:
    import numpy as np
    import fitz
    from PIL import Image

    rng = np.random.default_rng(1)
    doc = fitz.open()
    try:
        for i in range(pages):
            page = doc.new_page(width=612, height=792)
            arr = rng.integers(0, 256, size=(400, 300, 3), dtype=np.uint8)
            image = Image.fromarray(arr, mode="RGB")
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=70)
            page.insert_image(fitz.Rect(36, 36, 576, 756), stream=buf.getvalue())
            page.insert_text((40, 24), f"Page {i + 1}")
        return doc.tobytes()
    finally:
        doc.close()


def _text_pdf(pages: int) -> bytes:
    import fitz

    doc = fitz.open()
    try:
        for i in range(pages):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72), f"Owner manual page {i + 1}")
        return doc.tobytes()
    finally:
        doc.close()


class TestPageRenderMemory(unittest.TestCase):
    def test_a_136_page_pdf_releases_each_page_image(self):
        pdf = _photo_pdf(PAGES)
        gc.collect()
        start = _rss_kb()
        peak = start
        seen = 0
        for rendered in mf.walk_pdf_pages(pdf, start_page=1, max_pages=None):
            self.assertTrue(rendered["png"])
            rendered["png"] = b""
            seen += 1
            peak = max(peak, _rss_kb())
        gc.collect()
        peak = max(peak, _rss_kb())
        self.assertEqual(seen, PAGES)
        growth = peak - start
        self.assertLess(
            growth,
            GROWTH_LIMIT_KB,
            f"peak RSS grew {growth} KB; the old all-pages render grew about 122772 KB",
        )


class TestPageCursor(unittest.TestCase):
    def test_a_long_pdf_splits_across_import_steps(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        engine = create_engine(f"sqlite:///{Path(tmp.name) / 'library.db'}")
        bulk.ensure_schema(engine)
        session = sessionmaker(bind=engine)()
        self.addCleanup(session.close)
        pdf = _text_pdf(20)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("manual.pdf", pdf)
        staged = bulk.stage_zip_source(
            session,
            io.BytesIO(buf.getvalue()),
            zip_name="leveling.zip",
            uploaded_by=1,
            batch_size=2,
            staging_dir=str(Path(tmp.name) / "staging"),
        )
        self.assertTrue(staged["ok"], staged)
        self.assertEqual(bulk.DEFAULT_BATCH, 2)

        def index_figures(document_id, data, title, start_page=1):
            return fb.store_pdf_figures(
                session,
                document_id,
                data,
                title=title,
                start_page=start_page,
                max_pages=fb.PAGES_PER_STEP,
            )

        cursors = []
        for _ in range(6):
            result = bulk.process_next_batch(
                session,
                int(staged["job_id"]),
                upload_pdf=lambda data, key, content_type="application/pdf": True,
                backup_db=lambda: (True, "saved"),
                batch_size=2,
                index_figures=index_figures,
            )
            self.assertEqual(result["failed"], 0)
            row = session.execute(
                text("SELECT status, figure_page, page_count FROM bulk_import_items")
            ).mappings().one()
            cursors.append((row["status"], int(row["figure_page"] or 0), int(row["page_count"] or 0)))
            if row["status"] == "imported":
                break
        self.assertEqual(cursors[0][0], "pending")
        self.assertEqual(cursors[0][1], fb.PAGES_PER_STEP + 1)
        self.assertEqual(cursors[0][2], 20)
        self.assertEqual(cursors[-1][0], "imported")
        pages = session.execute(
            text("SELECT COUNT(*) FROM doc_assets WHERE kind = 'page'")
        ).scalar()
        self.assertEqual(int(pages), 20)
        blobs = session.execute(
            text("SELECT COUNT(*) FROM doc_assets WHERE png_blob IS NOT NULL AND length(png_blob) > 0")
        ).scalar()
        self.assertEqual(int(blobs or 0), 0)


class TestNoPngCache(unittest.TestCase):
    def test_page_png_bytes_are_not_cached_in_session_or_st_cache(self):
        source = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
        self.assertNotIn("st.cache", source)
        self.assertIn("def _figures_for_session", source)
        self.assertEqual(source.count('st.session_state["ask_auto_show"] = _figures_for_session('), 2)
        self.assertNotIn('st.session_state["ask_auto_show"] = _offers', source)
        self.assertNotIn('st.session_state["ask_auto_show"] = pages', source)
