"""Library page images and figure crops for every brand, including Lippert."""
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import library_bulk_import as bulk
import library_figure_backfill as fb
import manual_figures as mf

ROOT = Path(__file__).resolve().parents[1]
VALVE_PDF = ROOT / "tests" / "fixtures" / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf"
LIPPERT_TITLE = "Lippert Level Up Towable Owner's Manual"
THETFORD_TITLE = "Thetford Water Valve Kit 42109"


class MemoryR2:
    def __init__(self):
        self.objects = {}

    def upload(self, data, key, content_type="image/png"):
        self.objects[key] = data
        return True

    def download(self, key):
        return self.objects.get(key)


def _lippert_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.draw_rect(fitz.Rect(72, 80, 320, 240), color=(0, 0, 0), fill=(0.15, 0.15, 0.15), width=2)
    page.insert_text((72, 262), "Fig. 1 CARTRIDGE VALVE")
    data = doc.tobytes()
    doc.close()
    return data


class FigureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.tmp.name) / 'library.db'}")
        bulk.ensure_schema(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        fb.ensure_ready(self.session)
        self.session.commit()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def add_document(self, title, brand, file_path, page_text="Cartridge Valve, item F, part 177094."):
        self.session.execute(
            text("INSERT INTO categories (name) VALUES (:name)"),
            {"name": f"cat-{title[:20]}"},
        )
        self.session.commit()
        category_id = self.session.execute(text("SELECT id FROM categories ORDER BY id DESC LIMIT 1")).scalar()
        doc_id = self.session.execute(
            text(
                """
                INSERT INTO documents (
                    category_id, title, file_path, file_type, keywords, indexed, brand
                ) VALUES (
                    :category_id, :title, :file_path, 'pdf', :keywords, 1, :brand
                )
                RETURNING id
                """
            ),
            {
                "category_id": category_id,
                "title": title,
                "file_path": file_path,
                "keywords": brand,
                "brand": brand,
            },
        ).scalar()
        self.session.execute(
            text(
                """
                INSERT INTO doc_chunks (
                    document_id, category_id, title, page, chunk_text, keywords
                ) VALUES (
                    :document_id, :category_id, :title, 1, :chunk_text, :keywords
                )
                """
            ),
            {
                "document_id": doc_id,
                "category_id": category_id,
                "title": title,
                "chunk_text": page_text,
                "keywords": brand,
            },
        )
        self.session.commit()
        return int(doc_id)


class TestBackfillJob(FigureCase):
    def test_backfill_is_resumable_and_estimates_storage(self):
        good = Path(self.tmp.name) / "level-up.pdf"
        good.write_bytes(_lippert_pdf())
        missing = "library/missing.pdf"
        self.add_document("Furrion Chill FACR CCD-0008666", "Furrion", str(good))
        self.add_document(
            "Furrion Rooftop HVAC CCD-0007990", "Furrion", missing, page_text="Page two only."
        )
        self.add_document(LIPPERT_TITLE, "Lippert", "library/level-up.pdf")
        self.session.execute(
            text("UPDATE doc_chunks SET page = 4 WHERE title = 'Furrion Rooftop HVAC CCD-0007990'")
        )
        self.session.commit()
        estimate = fb.estimate_backfill(self.session)
        self.assertEqual(estimate["documents"], 2)
        self.assertEqual(estimate["pages"], 5)
        self.assertEqual(
            estimate["figures"],
            int(round(estimate["pages"] * fb.SAMPLE_CROPS / fb.SAMPLE_PAGES)),
        )
        self.assertEqual(
            estimate["r2_bytes"],
            estimate["pages"] * fb.PAGE_PNG_BYTES + estimate["figures"] * fb.CROP_PNG_BYTES,
        )
        self.assertEqual(estimate["sqlite_bytes"], 0)
        self.assertEqual(estimate["total_bytes"], estimate["r2_bytes"])
        self.assertEqual(fb.PAGE_PNG_BYTES, 519584)
        self.assertEqual(fb.CROP_PNG_BYTES, 82040)
        caption = fb.estimate_caption(estimate)
        self.assertIn("2 manuals", caption)
        self.assertIn("R2", caption)
        self.assertNotIn("again", caption.lower())
        self.assertIn("not the PNG", caption)
        empty = fb.estimate_caption(
            {
                "documents": 0,
                "pages": 0,
                "page_png_bytes": fb.PAGE_PNG_BYTES,
                "crop_png_bytes": fb.CROP_PNG_BYTES,
                "crops_per_page": fb.SAMPLE_CROPS / fb.SAMPLE_PAGES,
            }
        )
        self.assertIn("0 bytes", empty)

        def download(path):
            local = Path(path)
            if local.is_file():
                return local.read_bytes()
            return None

        self.assertEqual(fb.ensure_job(self.session), 0)
        choices = fb.pdf_choices(self.session)
        self.assertEqual(
            {row["title"] for row in choices},
            {"Furrion Chill FACR CCD-0008666", "Furrion Rooftop HVAC CCD-0007990"},
        )
        job_id = fb.ensure_job(self.session, [row["id"] for row in choices])
        ticks = []
        first = fb.process_backfill_batch(
            self.session,
            job_id,
            download_pdf=download,
            batch_size=1,
            progress=lambda index, total, title: ticks.append((index, total, title)),
        )
        self.assertEqual(first["processed"], 1)
        self.assertEqual(first["done"], 1)
        self.assertEqual(first["status"], "paused")
        self.assertEqual(first["pending"], 1)
        self.assertTrue(ticks)
        progress = fb.job_progress(self.session, job_id)
        self.assertEqual(progress["done"], 1)
        self.assertEqual(progress["pending"], 1)
        assets = self.session.execute(
            text("SELECT kind, bbox FROM doc_assets WHERE kind = 'figure'")
        ).fetchall()
        self.assertTrue(assets)
        self.assertTrue(assets[0][1])
        second = fb.process_backfill_batch(
            self.session,
            job_id,
            download_pdf=download,
            batch_size=1,
        )
        self.assertEqual(second["failed"], 1)
        self.assertEqual(second["status"], "complete")
        failed = self.session.execute(
            text("SELECT status, error FROM figure_backfill_items WHERE status = 'failed'")
        ).mappings().first()
        self.assertIn("download", (failed["error"] or "").lower())
        again = fb.process_backfill_batch(
            self.session,
            job_id,
            download_pdf=download,
            batch_size=2,
        )
        self.assertEqual(again["processed"], 0)
        self.assertEqual(
            self.session.execute(
                text("SELECT COUNT(*) FROM figure_backfill_items WHERE status = 'failed'")
            ).scalar(),
            1,
        )
        module = (ROOT / "library_figure_backfill.py").read_text(encoding="utf-8")
        self.assertNotIn("import streamlit", module)
        app = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("Backfill selected manuals", app)
        self.assertIn("pdf_choices", app)
        self.assertNotIn("Backfill page images and figures", app)
        self.assertIn("case_backfill_document", module)

    def test_selected_manuals_do_not_queue_the_whole_library(self):
        first = self.add_document("Furrion Chill FACR CCD-0008666", "Furrion", "library/8666.pdf")
        second = self.add_document(
            "Furrion Rooftop HVAC CCD-0007990", "Furrion", "library/7990.pdf"
        )
        third = self.add_document("Thetford Style II OM Permanent RV Toilet 42088", "Thetford", "library/om.pdf")
        valve = self.add_document("Thetford Water Valve Kit 42109", "Thetford", "library/valve.pdf")
        breaker = self.add_document(
            "Thetford Vacuum Breaker Kit 34123/34122", "Thetford", "library/breaker.pdf"
        )
        other = self.add_document(LIPPERT_TITLE, "Lippert", "library/level-up.pdf")
        tank = self.add_document("Thetford Plastic Tank", "Thetford", "library/tank.pdf")
        self.assertEqual(fb.ensure_job(self.session), 0)
        self.assertFalse(fb.case_backfill_document({"title": LIPPERT_TITLE, "brand": "Lippert"}))
        self.assertFalse(fb.case_backfill_document({"title": "Thetford Plastic Tank", "brand": "Thetford"}))
        choices = {int(row["id"]) for row in fb.pdf_choices(self.session)}
        self.assertEqual(choices, {first, second, third, valve, breaker})
        refused = fb.ensure_job(self.session, [other, tank])
        self.assertEqual(refused, 0)
        picked = fb.ensure_job(self.session, [first, second, other])
        self.assertEqual(fb._job_document_ids(self.session, picked), {first, second})
        again = fb.ensure_job(self.session, [first, second])
        self.assertEqual(again, picked)
        both = fb.ensure_job(self.session, [first, second, third, valve, breaker, other, tank])
        self.assertNotEqual(both, picked)
        self.assertEqual(fb._job_document_ids(self.session, both), {first, second, third, valve, breaker})


class TestBulkImportFigures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "library.db")
        self.staging = str(Path(self.tmp.name) / "staging")
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        bulk.ensure_schema(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def test_import_writes_figures_and_a_failure_does_not_drop_the_pdf(self):
        import io
        import zipfile

        files = {
            "level-up.pdf": _lippert_pdf(),
            "blank.pdf": _blank_pdf(),
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        staged = bulk.stage_zip_source(
            self.session,
            buf.getvalue(),
            zip_name="lippert.zip",
            manifest_bytes=(
                "filename,clean_title,brand,product_line,models\n"
                "level-up.pdf,Lippert Level Up Towable Owner's Manual,Lippert,Level Up,807662\n"
                "blank.pdf,Lippert scanned sheet,Lippert,Level Up,807662\n"
            ).encode("utf-8"),
            manifest_name="manifest.csv",
            uploaded_by=3,
            batch_size=4,
            staging_dir=self.staging,
        )
        self.assertTrue(staged["ok"], staged)
        calls = []

        def index_figures(document_id, data, title):
            calls.append(title)
            indexed = fb.store_pdf_figures(self.session, document_id, data, title=title)
            return f"{len(indexed.get('pages') or [])} page images, {len(indexed.get('figures') or [])} figures"

        result = bulk.process_next_batch(
            self.session,
            int(staged["job_id"]),
            upload_pdf=lambda data, key, content_type="application/pdf": True,
            backup_db=lambda: (True, "saved"),
            batch_size=4,
            index_figures=index_figures,
        )
        self.assertEqual(result["failed"], 0)
        self.assertGreaterEqual(result["imported"] + result["needs_ocr"], 2)
        self.assertEqual(len(calls), 2)
        rows = self.session.execute(
            text(
                """
                SELECT d.title, a.kind, a.chunk_id, a.bbox
                FROM doc_assets a
                JOIN documents d ON d.id = a.document_id
                ORDER BY d.id, a.kind
                """
            )
        ).fetchall()
        kinds = {}
        for title, kind, chunk_id, bbox in rows:
            kinds.setdefault(title, set()).add(kind)
            if "Level Up" in title and kind == "figure":
                self.assertTrue(chunk_id)
                self.assertIn(",", bbox or "")
        self.assertIn("figure", kinds[LIPPERT_TITLE])
        self.assertIn("page", kinds[LIPPERT_TITLE])
        scanned = [title for title in kinds if "scanned" in title.lower()]
        self.assertTrue(scanned)
        self.assertIn("page", kinds[scanned[0]])
        self.assertNotIn("figure", kinds[scanned[0]])
        blobs = self.session.execute(
            text("SELECT COUNT(*) FROM doc_assets WHERE png_blob IS NOT NULL AND length(png_blob) > 0")
        ).scalar()
        self.assertEqual(int(blobs or 0), 0)

        def boom(document_id, data, title):
            raise RuntimeError("crop failed")

        fresh = io.BytesIO()
        with zipfile.ZipFile(fresh, "w") as archive:
            archive.writestr("other.pdf", _other_pdf())
        staged_bad = bulk.stage_zip_source(
            self.session,
            fresh.getvalue(),
            zip_name="other.zip",
            uploaded_by=3,
            batch_size=4,
            staging_dir=self.staging,
        )
        self.assertTrue(staged_bad["ok"], staged_bad)
        failed_crop = bulk.process_next_batch(
            self.session,
            int(staged_bad["job_id"]),
            upload_pdf=lambda data, key, content_type="application/pdf": True,
            backup_db=lambda: (True, "saved"),
            batch_size=4,
            index_figures=boom,
        )
        self.assertEqual(failed_crop["failed"], 0)
        self.assertEqual(failed_crop["imported"] + failed_crop["needs_ocr"], 1)


def _other_pdf() -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "Lippert hose diagram for a different file.")
    data = doc.tobytes()
    doc.close()
    return data


def _blank_pdf() -> bytes:
    from pypdf import PdfWriter
    import io

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


class TestLippertR2Projection(unittest.TestCase):
    def test_cost_is_r2_only_above_ten_gb(self):
        pdf_bytes = 10_240_000_000
        pages = 1000
        est = fb.project_r2_storage(pdf_bytes, pages)
        figures = int(round(pages * fb.SAMPLE_CROPS / fb.SAMPLE_PAGES))
        page_bytes = pages * fb.PAGE_PNG_BYTES
        crop_bytes = figures * fb.CROP_PNG_BYTES
        total = pdf_bytes + page_bytes + crop_bytes
        self.assertEqual(est["pdf_bytes"], pdf_bytes)
        self.assertEqual(est["page_bytes"], page_bytes)
        self.assertEqual(est["crop_bytes"], crop_bytes)
        self.assertEqual(est["figures"], figures)
        self.assertTrue(est["figures_estimated"])
        self.assertEqual(est["r2_bytes"], total)
        self.assertEqual(est["sqlite_bytes"] if "sqlite_bytes" in est else 0, 0)
        self.assertAlmostEqual(est["pdf_gb"], 10.24)
        self.assertAlmostEqual(est["total_gb"], total / fb.DECIMAL_GB)
        self.assertAlmostEqual(est["billable_gb"], est["total_gb"] - 10)
        self.assertAlmostEqual(est["monthly_usd"], est["billable_gb"] * 0.015)
        under = fb.project_r2_storage(9_000_000_000, 0, figures=0)
        self.assertEqual(under["monthly_usd"], 0)
        self.assertFalse(under["figures_estimated"])

    def test_script_counts_pages_in_a_manifest(self):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "lippert_r2_projection",
            ROOT / "scripts" / "lippert_r2_projection.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        tmp = tempfile.TemporaryDirectory()
        try:
            root = Path(tmp.name)
            pdf = root / "level-up.pdf"
            from pypdf import PdfWriter
            import io

            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            writer.add_blank_page(width=612, height=792)
            buf = io.BytesIO()
            writer.write(buf)
            pdf.write_bytes(buf.getvalue())
            manifest = root / "LOAD-MANIFEST.csv"
            manifest.write_text("filename,bytes\nlevel-up.pdf,1\n", encoding="utf-8")
            rows = mod.read_manifest_rows(manifest)
            tally = mod.tally_manifest(rows, root, root)
            self.assertEqual(tally["files"], 1)
            self.assertEqual(tally["opened"], 1)
            self.assertEqual(tally["pages"], 2)
            self.assertEqual(tally["pdf_bytes"], pdf.stat().st_size)
            import contextlib
            import io as _io

            with contextlib.redirect_stderr(_io.StringIO()):
                missing = mod.main([str(root / "missing.csv")])
            self.assertEqual(missing, 2)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
