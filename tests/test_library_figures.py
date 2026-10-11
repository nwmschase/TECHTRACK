"""Library page images and figure crops for every brand, including Lippert."""
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import library_bulk_import as bulk
import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import compose_sheet, compile_bay_procedure, layout_problems, render_bay_procedure_pdf

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


class TestLippertLibraryFigures(FigureCase):
    def test_level_up_returns_the_library_crop_not_thetford(self):
        lippert_id = self.add_document(LIPPERT_TITLE, "Lippert", "library/level-up.pdf")
        thetford_id = self.add_document(
            THETFORD_TITLE,
            "Thetford",
            "library/valve.pdf",
            page_text="Fig. 1 PEDAL REMOVED",
        )
        r2 = MemoryR2()
        cache = Path(self.tmp.name) / "cache"
        fb.store_pdf_figures(
            self.session, lippert_id, _lippert_pdf(), title=LIPPERT_TITLE, upload_png=r2.upload
        )
        fb.store_pdf_figures(
            self.session, thetford_id, VALVE_PDF.read_bytes(), title=THETFORD_TITLE, upload_png=r2.upload
        )
        self.session.commit()
        stored = [
            row[0]
            for row in self.session.execute(
                text("SELECT png_blob FROM doc_assets WHERE document_id = :id"),
                {"id": lippert_id},
            ).fetchall()
        ]
        self.assertTrue(stored)
        self.assertTrue(all(not blob for blob in stored))
        self.assertTrue(r2.objects)
        linked = self.session.execute(
            text(
                """
                SELECT chunk_id, bbox, caption, label
                FROM doc_assets
                WHERE document_id = :id AND kind = 'figure'
                """
            ),
            {"id": lippert_id},
        ).mappings().first()
        self.assertIsNotNone(linked)
        self.assertTrue(linked["chunk_id"])
        self.assertIn(",", linked["bbox"])
        self.assertIn("CARTRIDGE", linked["label"].upper())
        self.assertIn("Lippert", linked["caption"])
        rows = fb.meta_rows(self.session)
        self.assertTrue(all("png_blob" not in row for row in rows))
        offers = fb.offers_for_turn(
            rows,
            "",
            "show me the cartridge",
            "Leveling",
            "Level Up Advantage 807662",
        )
        fb.attach_pngs(self.session, offers, download=r2.download, cache_root=cache)
        cached = list(cache.rglob("*.png"))
        self.assertTrue(cached)
        r2.objects.clear()
        from_cache = fb.fetch_png(offers[0]["image_path"], download=r2.download, cache_root=cache)
        self.assertTrue(from_cache)
        self.assertFalse(mf.png_is_blank(from_cache))
        figures = [offer for offer in offers if offer.get("kind") == "figure"]
        self.assertTrue(figures)
        crop = figures[0]
        self.assertEqual(crop["document_id"], lippert_id)
        self.assertIn("CARTRIDGE", crop["label"].upper())
        self.assertTrue(crop["bbox"])
        self.assertIn("Lippert", crop["caption"])
        self.assertFalse(crop["bundled"])
        self.assertTrue(crop["png"])
        self.assertFalse(mf.png_is_blank(crop["png"]))
        blob = " ".join(f"{offer.get('title')} {offer.get('label')}" for offer in offers).lower()
        self.assertNotIn("thetford", blob)
        self.assertNotIn("pedal", blob)
        self.assertNotIn("bundled kit sheet", crop["caption"].lower())

    def test_bay_pdf_paints_the_lippert_library_figure(self):
        lippert_id = self.add_document(LIPPERT_TITLE, "Lippert", "library/level-up.pdf")
        self.add_document(THETFORD_TITLE, "Thetford", "library/valve.pdf", page_text="Fig. 1 PEDAL REMOVED")
        r2 = MemoryR2()
        fb.store_pdf_figures(
            self.session, lippert_id, _lippert_pdf(), title=LIPPERT_TITLE, upload_png=r2.upload
        )
        self.session.commit()
        rows = fb.meta_rows(self.session)
        fb.attach_pngs(
            self.session, rows, download=r2.download, cache_root=Path(self.tmp.name) / "bay-cache"
        )
        chunks = [
            {
                "document_id": lippert_id,
                "title": LIPPERT_TITLE,
                "page": 1,
                "excerpt": "Cartridge Valve, item F, part 177094.",
            }
        ]
        packets = fb.figure_packets(
            rows,
            chunks,
            "Lippert Level Up Advantage 807662 cartridge",
        )
        self.assertEqual(len(packets), 1)
        self.assertIn("Lippert", packets[0]["title"])
        proc = compile_bay_procedure(
            concern="Level Up front jacks drift. Loose cartridge valve.",
            brand="Lippert",
            model="Level Up Advantage 807662",
            category="Leveling",
            chunks=[{**chunks[0], "figures": packets[0]["figures"]}],
        )
        pictured = [
            (index, group)
            for index, group in enumerate(proc.step_figures or [])
            if group
        ]
        self.assertTrue(pictured)
        slot, group = pictured[0]
        self.assertIn("177094", proc.bay_order[slot])
        self.assertIn("CARTRIDGE", (group[0].caption or "").upper())
        pages = compose_sheet(proc)
        images = [image for page in pages for image in page.images]
        self.assertTrue(images)
        self.assertFalse(mf.png_is_blank(images[0].png))
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        self.assertIn("177094", text)
        self.assertIn("CARTRIDGE", text.upper())
        self.assertNotIn("PEDAL REMOVED", text.upper())


class TestBackfillJob(FigureCase):
    def test_backfill_is_resumable_and_estimates_storage(self):
        good = Path(self.tmp.name) / "level-up.pdf"
        good.write_bytes(_lippert_pdf())
        missing = "library/missing.pdf"
        self.add_document(LIPPERT_TITLE, "Lippert", str(good))
        self.add_document("Lippert second manual", "Lippert", missing, page_text="Page two only.")
        self.session.execute(
            text("UPDATE doc_chunks SET page = 4 WHERE title = 'Lippert second manual'")
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

        job_id = fb.ensure_job(self.session)
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
        staged = bulk.stage_zip_bytes(
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
        staged_bad = bulk.stage_zip_bytes(
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
