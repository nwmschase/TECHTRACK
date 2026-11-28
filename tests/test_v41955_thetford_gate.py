"""v4.19.55: one HOW action, the cited page, a specific bad look, and real backfill counts."""
import re
import unittest

from sqlalchemy import text

import library_figure_backfill as fb
import manual_figures as mf
from tests.test_library_figures import FigureCase
from tests.test_v41943_brand_figure_gate import TINY


def _pdf(pages: int) -> bytes:
    import fitz

    doc = fitz.open()
    try:
        for index in range(pages):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72), f"Thetford page {index + 1}")
        return doc.tobytes()
    finally:
        doc.close()


class TestBackfillCountsMatchStorage(FigureCase):
    def test_case_list_includes_42110_and_a_thetford_parts_list(self):
        self.assertTrue(fb.case_backfill_document({"title": "Thetford 42110", "brand": "Thetford"}))
        self.assertTrue(fb.case_backfill_document({"title": "Parts List", "brand": "Thetford"}))
        self.assertTrue(fb.case_backfill_document({"title": "CCD-0008666", "brand": "Furrion"}))
        self.assertTrue(fb.case_backfill_document({"title": "CCD-0007990", "brand": "Furrion"}))
        self.assertFalse(fb.case_backfill_document({"title": "Parts List", "brand": "Lippert"}))
        app = __import__("pathlib").Path(__file__).resolve().parents[1].joinpath(
            "rv_techtrack.py"
        ).read_text(encoding="utf-8")
        self.assertIn("document_asset_counts", app)
        self.assertIn("index_status_line", app)
        self.assertIn("backfill_batch_message", app)

    def test_a_failed_upload_does_not_leave_a_stored_key(self):
        doc_id = self.add_document("Thetford Style II OM 42088", "Thetford", "library/42088.pdf")
        job = fb.ensure_job(self.session, [doc_id])

        def refuse(data, key, content_type="image/png"):
            return False

        result = fb.process_backfill_batch(
            self.session,
            job,
            download_pdf=lambda path: _pdf(1),
            upload_png=refuse,
            batch_size=1,
        )
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["pages_stored"], 0)
        stored = self.session.execute(text("SELECT COUNT(*) FROM doc_assets")).scalar()
        self.assertEqual(stored, 0)
        self.assertIn("0 page images stored", fb.backfill_batch_message(result))
        self.assertIn("1 failed", fb.backfill_batch_message(result))

    def test_a_page_window_reports_stored_pages_and_index_counts(self):
        doc_id = self.add_document("Thetford 42110", "Thetford", "library/42110.pdf")
        other = self.add_document("CCD-0008666", "Furrion", "library/8666.pdf")
        original = fb.PAGES_PER_STEP
        fb.PAGES_PER_STEP = 1
        try:
            job = fb.ensure_job(self.session, [doc_id, other])
            uploaded = []
            result = fb.process_backfill_batch(
                self.session,
                job,
                download_pdf=lambda path: _pdf(2),
                upload_png=lambda data, key, content_type="image/png": uploaded.append(
                    (data, key, content_type)
                ) or True,
                batch_size=1,
            )
        finally:
            fb.PAGES_PER_STEP = original
        self.assertEqual(result["done"], 0)
        self.assertGreaterEqual(result["pages_stored"], 1)
        self.assertGreaterEqual(len(uploaded), 1)
        for data, key, content_type in uploaded:
            self.assertTrue(data.startswith(b"\x89PNG"), key)
            self.assertGreater(len(data), 8)
            self.assertTrue(key)
            self.assertEqual(content_type, "image/png")
        self.assertGreaterEqual(result["pending"], 1)
        message = fb.backfill_batch_message(result)
        self.assertIn("page images stored", message)
        self.assertNotIn("0 rendered", message)
        note = self.session.execute(
            text("SELECT index_note FROM documents WHERE id = :id"),
            {"id": doc_id},
        ).scalar()
        self.assertIn("page images", note or "")
        counts = fb.document_asset_counts(self.session)
        self.assertGreaterEqual(counts[doc_id]["pages"], 1)
        self.assertNotIn(other, counts)
        zero = fb.index_status_line("CCD-0008666", True, "", 0, 0)
        self.assertIn("0 page images, 0 figures", zero)
        shown = fb.index_status_line(
            "Thetford 42110",
            True,
            note or "",
            counts[doc_id]["pages"],
            counts[doc_id]["figures"],
        )
        self.assertIn(f"{counts[doc_id]['pages']} page images", shown)
        self.assertIn(f"{counts[doc_id]['figures']} figures", shown)


_LABEL_ORDER = (
    "Safety:",
    "Where:",
    "Tools:",
    "Do this:",
    "Good looks like:",
    "Bad looks like:",
    "Next:",
    "Figure:",
)


class TestGdStepLayout(unittest.TestCase):


    def test_the_chat_draws_one_picture_from_opened_pages(self):
        # v4.20.7: the old figure path (step figures, kit figure renderer, regex picture asks) is retired
        source = __import__("pathlib").Path(__file__).resolve().parents[1].joinpath(
            "rv_techtrack.py"
        ).read_text(encoding="utf-8")
        loop = source.split("for index, m in enumerate(history):", 1)[1].split("Describe the symptom", 1)[0]
        self.assertIn("_render_gd_picture(", loop)
        import ast
        tree = ast.parse(source)
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        used |= {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for gone in ("_render_gd_figures_under_step", "gd_figures_under_step", "render_library_page_image",
                     "tech_asked_for_manual_figure", "wants_library_page_shown", "render_on_demand_library_pages",
                     "resolve_requested_library_pages", "_stored_figure_matches", "_figures_for_session",
                     "figure_render_honesty_note", "offers_for_turn"):
            self.assertNotIn(gone, used)
        self.assertIn('picture = _gd_turn_picture(msg, reply, entry) if entry.get("asked_image") and not _gd_reply_is_failure(reply) else None', source)
        self.assertFalse(hasattr(mf, "tech_asked_for_manual_figure"))


def _gd_row(doc_id, title, brand, page, label, *, kind="figure", models="", category="Plumbing / Toilets"):
    return {
        "id": doc_id * 10 + page,
        "document_id": doc_id,
        "kind": kind,
        "title": title,
        "brand": brand,
        "page": page,
        "label": label,
        "caption": f"{title} {label}",
        "png": TINY,
        "image_path": f"docs/{doc_id}/p{page}.png",
        "category_name": category,
        "models": models,
    }


if __name__ == "__main__":
    unittest.main()
