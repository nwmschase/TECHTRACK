"""Bulk import stays steady (10/20 audit item 3c): the panel works on the newest / chosen import (never snaps to the
oldest), a click that interrupts a batch leaves no half-written document and no stuck lock, and the next batch resumes."""
import unittest

from sqlalchemy import text

import library_bulk_import as bulk
from tests.test_library_bulk_import import BulkCase, _text_pdf


class Interrupt(BaseException):
    """Stands in for Streamlit's RerunException / StopException (both BaseException)."""


class PickActiveJob(unittest.TestCase):
    def test_newest_open_job_by_default(self):
        opens = [{"id": 3}, {"id": 9}, {"id": 5}]
        self.assertEqual(bulk.pick_active_job(opens), 9)

    def test_remembered_job_wins_while_open(self):
        opens = [{"id": 3}, {"id": 9}]
        self.assertEqual(bulk.pick_active_job(opens, 3), 3)
        self.assertEqual(bulk.pick_active_job(opens, "3"), 3)

    def test_finished_remembered_job_falls_back_to_newest(self):
        self.assertEqual(bulk.pick_active_job([{"id": 3}, {"id": 9}], 12), 9)
        self.assertIsNone(bulk.pick_active_job([], 12))


class InterruptedBatch(BulkCase):
    def test_click_mid_batch_rolls_back_and_releases_lock_then_resumes(self):
        files = {f"m{i}.pdf": _text_pdf(f"Manual {i} slide motor error E{i}") for i in range(3)}
        staged = self.stage(files, batch_size=3)
        self.assertTrue(staged["ok"], staged.get("error"))
        job_id = staged["job_id"]
        calls = {"n": 0}

        def upload_then_interrupt(data, key, content_type="application/pdf"):
            calls["n"] += 1
            if calls["n"] == 2:   # second file: the manager clicked again, Streamlit interrupts the run
                raise Interrupt()
            return self.upload_pdf(data, key, content_type)

        with self.assertRaises(Interrupt):
            bulk.process_next_batch(self.session, job_id, upload_pdf=upload_then_interrupt, backup_db=self.backup, batch_size=3)
        row = self.job_row(job_id)
        self.assertEqual(float(row["lock_until"] or 0), 0.0)          # lock released, no 'already running' hang
        self.assertEqual(row["status"], "paused")
        n_docs = self.session.execute(text("SELECT count(*) FROM documents")).scalar()
        self.assertEqual(n_docs, 1)                                     # the interrupted file left nothing behind
        done = self.run_batch(job_id, batch_size=3)                     # next click resumes
        self.assertFalse(done["busy"])
        self.assertEqual(done["status"], "complete")
        self.assertEqual(self.session.execute(text("SELECT count(*) FROM documents")).scalar(), 3)

    def test_live_lock_reports_busy_without_touching_items(self):
        staged = self.stage({"a.pdf": _text_pdf("Awning motor test")}, batch_size=1)
        job_id = staged["job_id"]
        import time
        self.session.execute(text("UPDATE bulk_import_jobs SET lock_until = :t WHERE id = :id"), {"t": time.time() + 60, "id": job_id})
        self.session.commit()
        res = self.run_batch(job_id)
        self.assertTrue(res["busy"])
        self.assertEqual(self.session.execute(text("SELECT count(*) FROM documents")).scalar(), 0)


if __name__ == "__main__":
    unittest.main()
