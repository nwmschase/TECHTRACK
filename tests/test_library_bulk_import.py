"""Bulk Document Library import: dedupe, resume, bad PDF, and scanned flag.

Uses a temporary SQLite file and a fake R2 upload. Does not import rv_techtrack.
"""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from pypdf import PdfWriter
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import library_bulk_import as bulk

ROOT = Path(__file__).resolve().parents[1]


def _text_pdf(message: str) -> bytes:
    import fitz

    doc = fitz.open()
    height = 792 if len(message) < 400 else 2000
    page = doc.new_page(width=612, height=height)
    if len(message) < 400:
        page.insert_text((72, 72), message)
    else:
        page.insert_textbox(fitz.Rect(36, 36, 576, height - 36), message, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buf.getvalue()


class BulkCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "library.db")
        self.staging = str(Path(self.tmp.name) / "staging")
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        bulk.ensure_schema(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.uploads = []
        self.backup_calls = 0
        self.staging_puts = {}

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def upload_pdf(self, data, key, content_type="application/pdf"):
        self.uploads.append({"key": key, "n": len(data), "type": content_type})
        return True

    def upload_staging(self, data, key, content_type="application/zip"):
        self.staging_puts[key] = data
        return True

    def download_staging(self, key):
        return self.staging_puts.get(key)

    def backup(self):
        self.backup_calls += 1
        return True, f"saved {self.backup_calls}"

    def reopen(self):
        self.session.close()
        self.engine.dispose()
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.session = sessionmaker(bind=self.engine)()

    def stage(self, files, manifest=None, batch_size=8, name="lippert.zip", staging_upload=False):
        blob = _zip_bytes(files)
        manifest_bytes = None
        if isinstance(manifest, str):
            manifest_bytes = manifest.encode("utf-8")
        return bulk.stage_zip_bytes(
            self.session,
            blob,
            zip_name=name,
            manifest_bytes=manifest_bytes,
            manifest_name="manifest.csv" if manifest_bytes else "",
            uploaded_by=7,
            batch_size=batch_size,
            staging_dir=self.staging,
            upload_staging=self.upload_staging if staging_upload else None,
        )

    def run_batch(self, job_id, batch_size=None, download=False, delete_zip=None):
        return bulk.process_next_batch(
            self.session,
            job_id,
            upload_pdf=self.upload_pdf,
            download_zip=self.download_staging if download else None,
            backup_db=self.backup,
            delete_zip=delete_zip,
            batch_size=batch_size,
        )

    def job_row(self, job_id):
        return dict(
            self.session.execute(
                text("SELECT * FROM bulk_import_jobs WHERE id = :id"),
                {"id": job_id},
            ).mappings().one()
        )

    def documents(self):
        return [
            dict(row)
            for row in self.session.execute(text("SELECT * FROM documents ORDER BY id")).mappings()
        ]

    def chunks_for(self, document_id):
        return [
            dict(row)
            for row in self.session.execute(
                text(
                    "SELECT page, chunk_text FROM doc_chunks WHERE document_id = :id ORDER BY id"
                ),
                {"id": document_id},
            ).mappings()
        ]


class TestAutoContinue(unittest.TestCase):
    def test_stop_ends_the_chain_and_freezes_the_clock(self):
        self.assertTrue(
            bulk.auto_continue_should_rerun(
                auto=True,
                stopped=False,
                pending=40,
                processed=8,
                status="paused",
            )
        )
        self.assertFalse(
            bulk.auto_continue_should_rerun(
                auto=True,
                stopped=True,
                pending=40,
                processed=8,
                status="paused",
            )
        )
        self.assertFalse(
            bulk.auto_continue_should_rerun(
                auto=False,
                stopped=False,
                pending=40,
                processed=8,
                status="paused",
            )
        )
        self.assertFalse(
            bulk.auto_continue_should_rerun(
                auto=True,
                stopped=False,
                pending=0,
                processed=8,
                status="complete",
            )
        )
        state = {}
        bulk.arm_import_pace(state, 0, now=1000.0, reset=True)
        running = bulk.import_pace_line(state, 16, now=1120.0)
        self.assertEqual(running, "Elapsed 2m 0s · 8.0 files/minute")
        bulk.freeze_import_pace(state, 1120.0)
        self.assertEqual(bulk.import_pace_line(state, 16, now=5000.0), running)
        panel = (ROOT / "library_bulk_import.py").read_text(encoding="utf-8")
        self.assertIn('st.checkbox(\n        "Auto-continue"', panel)
        self.assertIn('st.button("Stop", key="bulk_stop")', panel)


class TestStagingZipCleanup(BulkCase):
    def test_a_finished_zip_with_no_failures_is_deleted(self):
        staged = self.stage(
            {"a.pdf": _text_pdf("Alpha manual."), "b.pdf": _text_pdf("Beta manual.")},
            batch_size=10,
            staging_upload=True,
        )
        deleted = []

        def delete_zip(key):
            deleted.append(key)
            self.staging_puts.pop(key, None)
            return True

        done = self.run_batch(staged["job_id"], batch_size=10, delete_zip=delete_zip)
        self.assertEqual(done["status"], "complete")
        self.assertEqual(done["failed"], 0)
        self.assertEqual(done["pending"], 0)
        self.assertTrue(done["staging_zip_deleted"])
        self.assertEqual(deleted, [staged["zip_r2_key"]])
        self.assertTrue(staged["zip_r2_key"].startswith("imports/bulk/"))
        self.assertEqual(self.job_row(staged["job_id"])["zip_r2_key"], "")
        self.assertEqual(len(self.documents()), 2)
        again = bulk.cleanup_finished_import_zips(self.session, delete_zip)
        self.assertEqual(again["deleted"], [])

    def test_a_failed_file_keeps_the_zip_so_the_import_can_resume(self):
        staged = self.stage(
            {"good.pdf": _text_pdf("Keep this page."), "bad.pdf": b"not a pdf"},
            batch_size=10,
            staging_upload=True,
        )
        deleted = []
        done = self.run_batch(
            staged["job_id"],
            batch_size=10,
            delete_zip=lambda key: deleted.append(key) or True,
        )
        self.assertEqual(done["status"], "complete")
        self.assertGreater(done["failed"], 0)
        self.assertEqual(done["pending"], 0)
        self.assertEqual(deleted, [])
        self.assertTrue(done["staging_zip_kept"])
        self.assertFalse(done["staging_zip_deleted"])
        self.assertEqual(self.job_row(staged["job_id"])["zip_r2_key"], staged["zip_r2_key"])
        self.assertEqual(len(self.documents()), 1)

    def test_an_unfinished_batch_does_not_delete_the_zip(self):
        staged = self.stage(
            {"one.pdf": _text_pdf("First."), "two.pdf": _text_pdf("Second.")},
            batch_size=1,
            staging_upload=True,
        )
        deleted = []
        step = self.run_batch(
            staged["job_id"],
            batch_size=1,
            delete_zip=lambda key: deleted.append(key) or True,
        )
        self.assertEqual(step["status"], "paused")
        self.assertEqual(step["pending"], 1)
        self.assertEqual(deleted, [])
        self.assertEqual(self.job_row(staged["job_id"])["zip_r2_key"], staged["zip_r2_key"])

    def test_a_scanned_pdf_still_drops_the_staging_zip(self):
        staged = self.stage({"scan.pdf": _blank_pdf()}, batch_size=4, staging_upload=True)
        deleted = []
        done = self.run_batch(
            staged["job_id"],
            batch_size=4,
            delete_zip=lambda key: deleted.append(key) or True,
        )
        self.assertEqual(done["needs_ocr"], 1)
        self.assertEqual(done["failed"], 0)
        self.assertEqual(deleted, [staged["zip_r2_key"]])
        self.assertEqual(self.job_row(staged["job_id"])["zip_r2_key"], "")

    def test_cleanup_skips_failed_and_open_zips_and_retries_a_delete_error(self):
        clean = self.stage(
            {"clean.pdf": _text_pdf("Done.")},
            batch_size=4,
            staging_upload=True,
            name="clean.zip",
        )
        self.run_batch(clean["job_id"], batch_size=4)
        failed = self.stage(
            {"good.pdf": _text_pdf("Stored."), "bad.pdf": b"not a pdf"},
            batch_size=4,
            staging_upload=True,
            name="failed.zip",
        )
        self.run_batch(failed["job_id"], batch_size=4)
        paused = self.stage(
            {"one.pdf": _text_pdf("One."), "two.pdf": _text_pdf("Two.")},
            batch_size=1,
            staging_upload=True,
            name="open.zip",
        )
        self.run_batch(paused["job_id"], batch_size=1)
        self.assertNotEqual(clean["zip_r2_key"], failed["zip_r2_key"])
        self.assertNotEqual(clean["zip_r2_key"], paused["zip_r2_key"])

        blocked = bulk.cleanup_finished_import_zips(self.session, lambda key: False)
        self.assertEqual(blocked["deleted"], [])
        self.assertIn(clean["zip_r2_key"], [item["key"] for item in blocked["errors"]])
        self.assertEqual(self.job_row(clean["job_id"])["zip_r2_key"], clean["zip_r2_key"])

        deleted = []
        cleaned = bulk.cleanup_finished_import_zips(
            self.session, lambda key: deleted.append(key) or True
        )
        self.assertEqual(deleted, [clean["zip_r2_key"]])
        self.assertEqual(cleaned["deleted"], [clean["zip_r2_key"]])
        self.assertIn(failed["zip_r2_key"], cleaned["kept"])
        self.assertIn(paused["zip_r2_key"], cleaned["kept"])
        self.assertEqual(self.job_row(clean["job_id"])["zip_r2_key"], "")
        self.assertEqual(self.job_row(failed["job_id"])["zip_r2_key"], failed["zip_r2_key"])
        self.assertEqual(self.job_row(paused["job_id"])["zip_r2_key"], paused["zip_r2_key"])

    def test_cleanup_does_not_delete_a_zip_another_open_job_still_needs(self):
        files = {"shared.pdf": _text_pdf("Shared manual.")}
        first = self.stage(files, batch_size=4, staging_upload=True, name="first.zip")
        self.run_batch(first["job_id"], batch_size=4)
        second = self.stage(files, batch_size=4, staging_upload=True, name="second.zip")
        self.assertNotEqual(second["job_id"], first["job_id"])
        self.assertEqual(second["zip_r2_key"], first["zip_r2_key"])
        deleted = []
        cleaned = bulk.cleanup_finished_import_zips(
            self.session, lambda key: deleted.append(key) or True
        )
        self.assertEqual(deleted, [])
        self.assertEqual(cleaned["deleted"], [])
        self.assertEqual(self.job_row(first["job_id"])["zip_r2_key"], "")
        self.assertEqual(self.job_row(second["job_id"])["zip_r2_key"], first["zip_r2_key"])

    def test_cleanup_refuses_a_key_outside_imports_bulk(self):
        staged = self.stage(
            {"a.pdf": _text_pdf("Stored.")},
            batch_size=4,
            staging_upload=True,
        )
        self.run_batch(staged["job_id"], batch_size=4)
        self.session.execute(
            text("UPDATE bulk_import_jobs SET zip_r2_key = :key WHERE id = :id"),
            {"key": "documents/secret.pdf", "id": staged["job_id"]},
        )
        self.session.commit()
        deleted = []
        cleaned = bulk.cleanup_finished_import_zips(
            self.session, lambda key: deleted.append(key) or True
        )
        self.assertEqual(deleted, [])
        self.assertEqual(cleaned["deleted"], [])
        self.assertEqual(cleaned["errors"][0]["key"], "documents/secret.pdf")
        self.assertEqual(self.job_row(staged["job_id"])["zip_r2_key"], "documents/secret.pdf")
        self.assertFalse(bulk.is_bulk_staging_key("documents/secret.pdf"))
        self.assertFalse(bulk.is_bulk_staging_key("imports/bulk/"))
        self.assertTrue(bulk.is_bulk_staging_key(staged["zip_r2_key"]))
        panel = (ROOT / "library_bulk_import.py").read_text(encoding="utf-8")
        self.assertIn('st.button("Clean up finished import ZIPs", key="bulk_cleanup_zips")', panel)
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("delete_bytes=r2_delete_object", src)
        self.assertNotIn("process_next_batch", src)


class TestChunkWindows(unittest.TestCase):
    def test_overlap_is_120_inside_900_character_windows(self):
        self.assertEqual(bulk.CHUNK_SIZE, 900)
        self.assertEqual(bulk.CHUNK_OVERLAP, 120)
        text = "".join(f"{i:04d}" for i in range(250))
        self.assertEqual(len(text), 1000)
        chunks = bulk.chunk_page_text(3, text)
        self.assertEqual(chunks[0], (3, text[:900]))
        self.assertEqual(chunks[1][1], text[780:])
        self.assertEqual(chunks[0][1][-120:], chunks[1][1][:120])


class TestManifestAndSummary(unittest.TestCase):
    def test_manifest_headers_are_case_insensitive(self):
        manifest = bulk.parse_manifest(
            "Filename,Category,Doc_Type,Title,TI_Number,Tier\n"
            "a.pdf,Lippert Slide-Outs,Owner Manual,Slide Book,TI-100,1\n"
        )
        row = manifest.row_for("folder/a.pdf")
        self.assertEqual(row["category"], "Lippert Slide-Outs")
        self.assertEqual(row["doc_type"], "Owner Manual")
        self.assertEqual(row["title"], "Slide Book")
        self.assertEqual(row["ti_number"], "TI-100")
        self.assertEqual(row["tier"], 1)
        self.assertEqual(bulk.parse_tier(""), 999)
        self.assertEqual(bulk.parse_tier("nope"), 999)

    def test_manifest_reads_metadata_columns_and_aliases(self):
        manifest = bulk.parse_manifest(
            "filename,Clean Title,Brand,Product Line,Model,Category,Doc Type,"
            "Doc Number,Revision Date,Keywords,Tier\n"
            "slide.pdf,Schwintek In-Wall,Lippert,In-Wall Slide-Out,PSX1; Schwintek,"
            "Lippert Slide-Outs,Service Manual,CCD-0001750,2024-03-01,"
            "slide motor; E2; 1234567,3\n"
        )
        row = manifest.row_for("SLIDE.PDF")
        self.assertEqual(row["clean_title"], "Schwintek In-Wall")
        self.assertEqual(row["title"], "Schwintek In-Wall")
        self.assertEqual(row["brand"], "Lippert")
        self.assertEqual(row["product_line"], "In-Wall Slide-Out")
        self.assertEqual(row["models"], "PSX1; Schwintek")
        self.assertEqual(row["doc_number"], "CCD-0001750")
        self.assertEqual(row["ti_number"], "CCD-0001750")
        self.assertEqual(row["revision_date"], "2024-03-01")
        self.assertEqual(row["keywords"], "slide motor; E2; 1234567")
        self.assertEqual(row["tier"], 3)
        aliased = bulk.parse_manifest(
            "filename,ti_number\n"
            "only-ti.pdf,TI-100\n"
        )
        ti = aliased.row_for("only-ti.pdf")
        self.assertEqual(ti["ti_number"], "TI-100")
        self.assertEqual(ti["doc_number"], "TI-100")

    def test_manifest_requires_filename(self):
        with self.assertRaises(ValueError):
            bulk.parse_manifest("title,tier\nBook,1\n")

    def test_storage_lines_keep_doc_count_when_r2_size_is_missing(self):
        grouped = {
            "documents/": [
                {"Key": "documents/a.pdf", "Size": 10},
                {"Key": "documents/b.pdf", "Size": 15},
                {"Key": "documents/", "Size": 0},
            ],
            "certificates/": [{"Key": "certificates/c.pdf"}],
            "backups/": [{"Key": "backups/rv.db", "Size": 100}],
        }
        totals = bulk.summarize_prefix_objects(grouped)
        self.assertEqual(totals["documents/"]["count"], 2)
        self.assertEqual(totals["documents/"]["bytes"], 25)
        self.assertTrue(totals["documents/"]["bytes_known"])
        self.assertEqual(totals["certificates/"]["count"], 1)
        self.assertFalse(totals["certificates/"]["bytes_known"])
        self.assertEqual(totals["backups/"]["bytes"], 100)
        local = {"doc_count": 4, "db_bytes": 2048, "needs_ocr_count": 1}
        lines = bulk.storage_summary_lines(local, totals, "")
        self.assertIn("Documents: 4", lines)
        self.assertIn("Database file: 2.0 KB", lines)
        self.assertIn("Needs OCR: 1", lines)
        self.assertTrue(any(line.startswith("documents/") and "25 B" in line for line in lines))
        self.assertTrue(any("size not reported by the API" in line for line in lines))
        failed = bulk.storage_summary_lines(local, {}, "Could not list storage: denied")
        self.assertIn("Documents: 4", failed)
        self.assertIn("Database file: 2.0 KB", failed)
        self.assertTrue(any(line.startswith("R2 totals unavailable:") for line in failed))


class TestSchemaUpgrade(unittest.TestCase):
    def test_existing_documents_table_gains_checksum_and_ocr_flag(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = str(Path(tmp.name) / "old.db")
        engine = create_engine(f"sqlite:///{path}")
        with engine.begin() as conn:
            conn.exec_driver_sql(
                """
                CREATE TABLE documents (
                    id INTEGER PRIMARY KEY,
                    category_id INTEGER NOT NULL,
                    title VARCHAR(250) NOT NULL,
                    file_path VARCHAR(400) NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                "INSERT INTO documents (category_id, title, file_path) "
                "VALUES (1, 'Older manual', 'documents/old.pdf')"
            )
        bulk.ensure_schema(engine)
        bulk.ensure_schema(engine)
        with engine.connect() as conn:
            info = {
                row[1]: row
                for row in conn.exec_driver_sql("PRAGMA table_info(documents)").fetchall()
            }
            kept = conn.exec_driver_sql(
                "SELECT title, brand, models, doc_number FROM documents"
            ).fetchone()
        self.assertIn("content_sha256", info)
        self.assertIn("needs_ocr", info)
        self.assertIn("byte_size", info)
        for name in (
            "clean_title",
            "brand",
            "product_line",
            "models",
            "doc_number",
            "revision_date",
        ):
            self.assertIn(name, info)
            self.assertEqual(info[name][3], 0)
        self.assertEqual(kept[0], "Older manual")
        self.assertIsNone(kept[1])
        self.assertIsNone(kept[2])
        self.assertIsNone(kept[3])
        engine.dispose()


class TestBulkImport(BulkCase):
    def test_dedupe_skips_the_same_sha256(self):
        body = _text_pdf("Slide motor thermal breaker is open.")
        files = {
            "notes.txt": b"not a manual",
            "first.pdf": body,
            "copy-of-first.pdf": body,
            "other.pdf": _text_pdf("Awning motor runs only while the switch is held."),
        }
        staged = self.stage(files, batch_size=10)
        self.assertTrue(staged["ok"], staged["error"])
        again = self.stage(files, batch_size=10)
        self.assertTrue(again["resumed"])
        self.assertEqual(again["job_id"], staged["job_id"])
        self.assertEqual(bulk.job_progress(self.session, staged["job_id"])["total"], 3)

        done = self.run_batch(staged["job_id"], batch_size=10)
        self.assertEqual(done["status"], "complete")
        self.assertEqual(done["imported"], 2)
        self.assertEqual(done["duplicate"], 1)
        self.assertEqual(len(self.uploads), 2)
        self.assertEqual(len(self.documents()), 2)
        for upload in self.uploads:
            self.assertRegex(upload["key"], r"^documents/\d+_\d{14}_.+\.pdf$")
            self.assertEqual(upload["type"], "application/pdf")

        upload_count = len(self.uploads)
        doc_count = len(self.documents())
        second = self.stage(files, batch_size=10)
        self.assertFalse(second["resumed"])
        self.assertNotEqual(second["job_id"], staged["job_id"])
        replay = self.run_batch(second["job_id"], batch_size=10)
        self.assertEqual(replay["duplicate"], 3)
        self.assertEqual(replay["imported"], 0)
        self.assertEqual(len(self.uploads), upload_count)
        self.assertEqual(len(self.documents()), doc_count)
        self.assertGreaterEqual(self.backup_calls, 2)

    def test_resume_across_a_new_session_and_a_missing_zip(self):
        files = {
            "one.pdf": _text_pdf("First Lippert manual page."),
            "two.pdf": _text_pdf("Second Lippert manual page."),
            "three.pdf": _text_pdf("Third Lippert manual page."),
        }
        staged = self.stage(files, batch_size=1, staging_upload=True)
        self.assertTrue(staged["zip_r2_key"].startswith("imports/bulk/"))
        first = self.run_batch(staged["job_id"], batch_size=1)
        self.assertEqual(first["processed"], 1)
        self.assertEqual(first["pending"], 2)
        self.assertEqual(first["status"], "paused")
        self.assertEqual(self.backup_calls, 1)

        local = Path(self.staging) / f"{staged['zip_sha256']}.zip"
        self.assertTrue(local.is_file())
        local.unlink()
        self.reopen()
        missing = self.run_batch(staged["job_id"], batch_size=1, download=False)
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["processed"], 0)
        self.assertEqual(self.backup_calls, 1)
        self.assertIn("ZIP", missing["error"])

        restored = self.run_batch(staged["job_id"], batch_size=1, download=True)
        self.assertTrue(restored["ok"], restored["error"])
        self.assertEqual(restored["processed"], 1)
        self.assertTrue(local.is_file())
        self.reopen()
        while True:
            step = self.run_batch(staged["job_id"], batch_size=1, download=True)
            if step["status"] == "complete":
                break
            self.assertGreater(step["processed"], 0)
        progress = bulk.job_progress(self.session, staged["job_id"])
        self.assertEqual(progress["imported"], 3)
        self.assertEqual(progress["pending"], 0)
        self.assertEqual(len(self.documents()), 3)
        self.assertGreaterEqual(self.backup_calls, 3)
        idle = self.run_batch(staged["job_id"], batch_size=1, download=True)
        self.assertEqual(idle["processed"], 0)
        self.assertEqual(idle["status"], "complete")

    def test_bad_pdf_is_dropped_and_a_scanned_pdf_is_kept(self):
        good = _text_pdf("The thermal breaker sits on the slide control board.")
        scanned = _blank_pdf()
        files = {
            "good.pdf": good,
            "scan.pdf": scanned,
            "bad.pdf": b"this is not a pdf",
        }
        manifest = (
            "filename,category,doc_type,title,ti_number,tier\n"
            "good.pdf,Lippert Slide-Outs,Service Manual,Slide Control,TI-100,2\n"
            "scan.pdf,Lippert Awnings,Owner Manual,Awning Scan,TI-300,1\n"
            "bad.pdf,Lippert Awnings,Owner Manual,Broken File,TI-400,9\n"
            "missing.pdf,Lippert Axles,TI,Missing Sheet,TI-500,8\n"
        )
        staged = self.stage(files, manifest=manifest, batch_size=10)
        self.assertTrue(staged["ok"], staged["error"])
        # Tier 1 is the scan, then the text manual, then the missing row, then the bad PDF.
        first = self.run_batch(staged["job_id"], batch_size=1)
        self.assertEqual(first["needs_ocr"], 1)
        self.assertEqual(first["imported"], 0)
        result = self.run_batch(staged["job_id"], batch_size=10)
        self.assertEqual(result["status"], "complete")
        progress = bulk.job_progress(self.session, staged["job_id"])
        self.assertEqual(progress["imported"], 1)
        self.assertEqual(progress["needs_ocr"], 1)
        self.assertEqual(progress["failed"], 2)

        docs = self.documents()
        self.assertEqual(len(docs), 2)
        by_title = {row["title"]: row for row in docs}
        self.assertIn("Slide Control", by_title)
        self.assertIn("Awning Scan", by_title)
        self.assertNotIn("Broken File", by_title)
        scan = by_title["Awning Scan"]
        self.assertEqual(scan["needs_ocr"], 1)
        self.assertEqual(scan["indexed"], 0)
        self.assertEqual(scan["index_note"], "needs OCR")
        self.assertEqual(scan["ti_number"], "TI-300")
        self.assertEqual(self.chunks_for(scan["id"]), [])
        good_row = by_title["Slide Control"]
        self.assertEqual(good_row["indexed"], 1)
        self.assertEqual(good_row["needs_ocr"], 0)
        self.assertIn("TI-100", good_row["keywords"])
        self.assertTrue(self.chunks_for(good_row["id"]))
        uploaded_names = " ".join(item["key"] for item in self.uploads)
        self.assertNotIn("bad", uploaded_names)
        self.assertEqual(len(self.uploads), 2)

        categories = [
            row[0]
            for row in self.session.execute(text("SELECT name FROM categories ORDER BY name")).all()
        ]
        self.assertIn("Lippert Slide-Outs", categories)
        self.assertIn("Lippert Awnings", categories)
        self.assertNotIn("Lippert Axles", categories)

        items = [
            dict(row)
            for row in self.session.execute(
                text("SELECT filename, status, error FROM bulk_import_items ORDER BY ordinal")
            ).mappings()
        ]
        by_name = {row["filename"]: row for row in items}
        self.assertEqual(by_name["bad.pdf"]["status"], "failed")
        self.assertEqual(by_name["bad.pdf"]["error"], "bad PDF")
        self.assertEqual(by_name["missing.pdf"]["error"], "not in zip")
        self.assertEqual(by_name["scan.pdf"]["status"], "needs_ocr")

    def test_manifest_metadata_is_stored_on_the_document(self):
        files = {"slide.pdf": _text_pdf("The in-wall motor stops on error E2.")}
        manifest = (
            "filename,clean_title,brand,product_line,models,category,doc_type,"
            "doc_number,revision_date,keywords,tier\n"
            "slide.pdf,Schwintek In-Wall,Lippert,In-Wall Slide-Out,PSX1; Schwintek,"
            "Lippert Slide-Outs,Service Manual,CCD-0001750,2024-03-01,"
            "slide motor; E2; 1234567,1\n"
        )
        staged = self.stage(files, manifest=manifest, batch_size=4)
        self.assertTrue(staged["ok"], staged["error"])
        done = self.run_batch(staged["job_id"], batch_size=4)
        self.assertEqual(done["imported"], 1)
        row = self.documents()[0]
        self.assertEqual(row["title"], "Schwintek In-Wall")
        self.assertEqual(row["clean_title"], "Schwintek In-Wall")
        self.assertEqual(row["brand"], "Lippert")
        self.assertEqual(row["product_line"], "In-Wall Slide-Out")
        self.assertEqual(row["models"], "PSX1; Schwintek")
        self.assertEqual(row["doc_type"], "Service Manual")
        self.assertEqual(row["doc_number"], "CCD-0001750")
        self.assertEqual(row["ti_number"], "CCD-0001750")
        self.assertEqual(row["revision_date"], "2024-03-01")
        for needle in ("E2", "1234567", "PSX1", "Schwintek", "Lippert", "CCD-0001750"):
            self.assertIn(needle, row["keywords"])
        chunks = self.chunks_for(row["id"])
        self.assertTrue(chunks)
        self.assertIn("E2", chunks[0]["chunk_text"])
        stored_keywords = self.session.execute(
            text("SELECT keywords FROM doc_chunks WHERE document_id = :id"),
            {"id": row["id"]},
        ).scalar()
        self.assertIn("1234567", stored_keywords)
        self.assertTrue(bulk.library_record_matches(row, query="e2 1234567"))
        self.assertTrue(bulk.library_record_matches(row, query="psx1"))
        self.assertFalse(bulk.library_record_matches(row, brand="Furrion"))

    def test_tier_order_and_existing_category_case(self):
        self.session.execute(text("INSERT INTO categories (name) VALUES ('Leveling')"))
        self.session.commit()
        files = {
            "later.pdf": _text_pdf("Later axle note."),
            "first.pdf": _text_pdf("First leveling note."),
        }
        manifest = (
            "filename,category,doc_type,title,ti_number,tier\n"
            "later.pdf,Lippert Axles,Service Manual,Later Axle,TI-200,5\n"
            "first.pdf,leveling,Owner Manual,First Level,TI-010,1\n"
        )
        staged = self.stage(files, manifest=manifest, batch_size=1)
        step = self.run_batch(staged["job_id"], batch_size=1)
        self.assertEqual(step["imported"], 1)
        docs = self.documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["title"], "First Level")
        names = [
            row[0]
            for row in self.session.execute(text("SELECT name FROM categories")).all()
        ]
        self.assertIn("Leveling", names)
        self.assertNotIn("leveling", names)
        self.run_batch(staged["job_id"], batch_size=1)
        titles = [row["title"] for row in self.documents()]
        self.assertEqual(titles, ["First Level", "Later Axle"])
        self.assertIn("Lippert Axles", [
            row[0] for row in self.session.execute(text("SELECT name FROM categories")).all()
        ])

    def test_long_manual_uses_the_same_chunk_windows(self):
        message = (
            "The Lippert slide-out motor requires a thermal reset before the room is run. " * 30
        ).strip()
        pdf = _text_pdf(message)
        kind, pages, err = bulk.inspect_pdf_bytes(pdf)
        self.assertEqual(kind, "text", err)
        page_text = pages[0][1]
        expected = []
        for page_num, extracted in pages:
            expected.extend(bulk.chunk_page_text(page_num, extracted))
        self.assertGreater(len(expected), 1)
        self.assertEqual(expected[0][1], page_text[:900].strip())
        self.assertEqual(expected[1][1], page_text[780 : 780 + 900].strip())
        staged = self.stage({"long.pdf": pdf}, batch_size=5)
        done = self.run_batch(staged["job_id"], batch_size=5)
        self.assertEqual(done["imported"], 1)
        doc = self.documents()[0]
        stored = [(row["page"], row["chunk_text"]) for row in self.chunks_for(doc["id"])]
        self.assertEqual(stored, expected)
        self.assertIn("Indexed", doc["index_note"])
        self.assertIn(str(len(expected)), doc["index_note"])

    def test_each_batch_asks_for_a_database_backup(self):
        files = {
            "a.pdf": _text_pdf("Alpha manual."),
            "b.pdf": _text_pdf("Beta manual."),
        }
        staged = self.stage(files, batch_size=1)
        self.run_batch(staged["job_id"], batch_size=1)
        self.assertEqual(self.backup_calls, 1)
        self.run_batch(staged["job_id"], batch_size=1)
        self.assertEqual(self.backup_calls, 2)
        summary = bulk.storage_summary(self.session, self.db_path)
        self.assertEqual(summary["doc_count"], 2)
        self.assertGreater(summary["db_bytes"], 0)

    def test_abandon_keeps_imported_files_and_allows_a_new_job(self):
        files = {"a.pdf": _text_pdf("Keep this manual.")}
        staged = self.stage(files, batch_size=1)
        self.run_batch(staged["job_id"], batch_size=1)
        bulk.abandon_job(self.session, staged["job_id"])
        idle = self.run_batch(staged["job_id"], batch_size=1)
        self.assertEqual(idle["status"], "abandoned")
        self.assertEqual(idle["processed"], 0)
        self.assertEqual(len(self.documents()), 1)
        fresh = self.stage(files, batch_size=1)
        self.assertNotEqual(fresh["job_id"], staged["job_id"])
        replay = self.run_batch(fresh["job_id"], batch_size=1)
        self.assertEqual(replay["duplicate"], 1)
        self.assertEqual(len(self.uploads), 1)

    def test_a_file_that_is_not_a_zip_is_refused(self):
        result = bulk.stage_zip_bytes(
            self.session,
            b"hello",
            zip_name="nope.zip",
            staging_dir=self.staging,
        )
        self.assertFalse(result["ok"])
        self.assertIsNone(result["job_id"])


class TestManagerPanelRenders(unittest.TestCase):
    """The panel is manager-only and must come up without touching Guided Diagnostics."""

    def test_manager_sees_bulk_import_and_guided_diagnostics_does_not(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(ROOT / "rv_techtrack.py"), default_timeout=90)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        self.assertFalse(list(at.exception))

        gd = "💬 Guided Diagnostics"
        at.radio[0].set_value(gd).run()
        self.assertFalse(list(at.exception))
        gd_text = "\n".join(
            (getattr(el, "value", None) or getattr(el, "body", None) or "")
            for el in list(at.markdown) + list(at.caption) + list(at.info)
        )
        self.assertNotIn("ZIP of PDFs", gd_text)

        at.radio[0].set_value("🛠️ Manager Tools").run()
        self.assertFalse(list(at.exception))
        mgr_text = "\n".join(
            (getattr(el, "value", None) or "")
            for el in list(at.caption) + list(at.markdown) + list(at.error)
        )
        self.assertIn("ZIP of PDFs", mgr_text)
        self.assertIn(
            "filename, clean_title, brand, product_line, models, "
            "category, doc_type, doc_number, revision_date, keywords, and tier",
            mgr_text,
        )


class TestManagerPanelWiring(unittest.TestCase):
    def test_bulk_import_is_only_inside_manager_tools(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        module = (ROOT / "library_bulk_import.py").read_text(encoding="utf-8")
        self.assertNotIn("import streamlit", module)
        self.assertNotIn("import rv_techtrack", module)
        self.assertNotIn("render_pdf_page", module)
        self.assertIn("def render_pdf_page_png(", src)
        head, mgr = src.split("# MANAGER TOOLS", 1)
        self.assertNotIn("render_manager_bulk_panel", head)
        self.assertNotIn("process_next_batch", src)
        self.assertEqual(mgr.count("render_manager_bulk_panel"), 1)
        self.assertLess(mgr.index("_enter_panel(tab_mgr)"), mgr.index("render_manager_bulk_panel"))
        self.assertIn("library_bulk_import.ensure_schema(engine)", src)
        self.assertIn('backup_db=lambda: maybe_backup_db_to_r2(force=True)', src)
        self.assertIn("maxUploadSize = 200", (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
