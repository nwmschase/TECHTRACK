"""v4.19.55: one HOW action, the cited page, a specific bad look, and real backfill counts."""
import re
import unittest

from sqlalchemy import text

import library_figure_backfill as fb
import manual_figures as mf
from gd_library_coach import strip_leaked_prompt
from tests.test_library_figures import FigureCase
from tests.test_v41943_brand_figure_gate import TINY


def _numbered(step) -> list[str]:
    return [
        line
        for line in mf.step_body_lines(step, show_figure=False)
        if re.match(r"^\d+\. ", line)
    ]


def _assert_one_action(test, step, label):
    actions = mf.step_action_lines(step)
    test.assertEqual(len(actions), 1, (label, actions))
    test.assertEqual(len(step.get("actions") or []), 1, (label, step.get("actions")))
    lines = _numbered(step)
    test.assertEqual(lines, [f"1. {actions[0]}"], (label, lines))
    test.assertFalse(any(line.startswith("2.") for line in lines), (label, lines))
    test.assertNotRegex(lines[0], r"^1\. \d+\.")


class TestOneActionPerHowLine(unittest.TestCase):
    def test_every_thetford_and_s01_step_has_one_action(self):
        groups = (
            ("valve", mf.thetford_kit_layout("valve")["steps"]),
            ("breaker", mf.thetford_kit_layout("breaker")["steps"]),
            ("s01-prove", mf.facr_proving_layout()["steps"]),
            ("s01-rr", mf.facr_rr_layout()["steps"]),
        )
        for name, steps in groups:
            self.assertGreater(len(steps), 1, name)
            for index, step in enumerate(steps, 1):
                _assert_one_action(self, step, f"{name} step {index}")
        grabs = [
            step
            for step in groups[0][1]
            if "grab the front of the pedal" in (step.get("text") or "").lower()
        ]
        pulls = [
            step
            for step in groups[0][1]
            if "pull the pedal up and off" in (step.get("text") or "").lower()
        ]
        self.assertEqual(len(grabs), 1)
        self.assertEqual(len(pulls), 1)
        self.assertIsNone(pulls[0].get("figure"))

    def test_proving_step_1_does_not_start_with_a_stray_number(self):
        for key in ("supply", "vacuum", "valve", "flange"):
            body = mf.thetford_proving_body(key)
            numbered = [line for line in body.splitlines() if re.match(r"^\d+\. ", line)]
            self.assertEqual(len(numbered), 1, (key, numbered))
            self.assertTrue(numbered[0].startswith("1. "), numbered)
            self.assertFalse(numbered[0].startswith("2."))
        heading, lines = mf.lines_from_shop_text(
            "Step 1: Turn off the water Do this: 2. Turn off the water.",
            1,
        )
        self.assertIn("1. Turn off the water.", lines)
        self.assertNotIn("2. Turn off the water.", lines)
        stray = {
            "text": "2. Turn off the water.",
            "actions": ["2. Turn off the water."],
            "fields": {"HOW": "2. Turn off the water.", "GOOD vs BAD": ""},
        }
        self.assertEqual(_numbered(stray), ["1. Turn off the water."])


class TestSpecificBadLooks(unittest.TestCase):
    def test_each_step_names_its_own_bad_sign(self):
        seen = set()
        for name, steps in (
            ("valve", mf.thetford_kit_layout("valve")["steps"]),
            ("breaker", mf.thetford_kit_layout("breaker")["steps"]),
            ("s01-prove", mf.facr_proving_layout()["steps"]),
            ("s01-rr", mf.facr_rr_layout()["steps"]),
        ):
            for index, step in enumerate(steps, 1):
                body = "\n".join(mf.step_body_lines(step, show_figure=False))
                self.assertNotIn("It does not look right", body, (name, index, body))
                good, bad = mf._good_bad_bits((step.get("fields") or {}).get("GOOD vs BAD") or "")
                self.assertTrue(good, (name, index))
                self.assertTrue(bad, (name, index))
                self.assertNotEqual(bad.lower(), good.lower(), (name, index, good, bad))
                self.assertNotIn("it does not look right", bad.lower())
                seen.add(bad.lower())
        self.assertGreater(len(seen), 8)


class TestCitedPageImage(unittest.TestCase):
    def test_a_cited_page_without_a_figure_shows_that_page(self):
        reply = (
            mf.thetford_proving_line("supply")
            + "\n\nThe cited page has no diagram."
        )
        rows = [
            {
                "id": 1,
                "document_id": 9,
                "kind": "figure",
                "title": "Thetford Style II OM Permanent RV Toilet 42088",
                "brand": "Thetford",
                "page": 7,
                "label": "parts",
                "caption": "Korean parts page",
                "png": TINY,
                "image_path": "docs/9/p7-figure.png",
            },
            {
                "id": 2,
                "document_id": 9,
                "kind": "page",
                "title": "Thetford Style II OM Permanent RV Toilet 42088",
                "brand": "Thetford",
                "page": 3,
                "label": "page",
                "caption": "Thetford Style II OM Permanent RV Toilet 42088, page 3",
                "png": b"",
                "image_path": "docs/9/p3.png",
            },
        ]
        offers = fb.offers_for_turn(
            rows, reply, "show me", "Plumbing / Toilets", "Style II 42070"
        )
        self.assertTrue(offers)
        self.assertTrue(all(int(item["page"]) == 3 for item in offers))
        self.assertEqual(offers[0]["kind"], "page")
        self.assertEqual(offers[0]["image_path"], "docs/9/p3.png")
        cleaned = strip_leaked_prompt(reply)
        self.assertNotIn("no diagram", cleaned.lower())
        self.assertIn("supply", cleaned.lower())

    def test_a_figure_on_the_cited_page_still_wins(self):
        reply = mf.thetford_proving_line("valve")
        rows = [
            {
                "id": 4,
                "document_id": 4,
                "kind": "figure",
                "title": "Thetford Water Valve Kit 42109",
                "brand": "Thetford",
                "page": 1,
                "label": "Fig. 1 PEDAL REMOVED",
                "caption": "Water valve kit 42109 pedal",
                "png": TINY,
                "image_path": "docs/4/fig1.png",
                "category_name": "Plumbing / Toilets",
            },
            {
                "id": 7,
                "document_id": 4,
                "kind": "figure",
                "title": "Thetford Water Valve Kit 42109",
                "brand": "Thetford",
                "page": 7,
                "label": "parts",
                "caption": "other page",
                "png": TINY,
                "image_path": "docs/4/p7.png",
            },
        ]
        offers = fb.offers_for_turn(
            rows, reply, "show me the pedal", "Plumbing / Toilets", "Style II 42070"
        )
        self.assertTrue(offers)
        self.assertTrue(all(int(item["page"]) == 1 for item in offers))
        self.assertIn("pedal", offers[0]["caption"].lower())


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


class TestGenericBadIsOmitted(unittest.TestCase):
    def test_a_generic_bad_line_is_left_off(self):
        generic = {
            "text": "Look at the seal.",
            "fields": {"GOOD vs BAD": "Good: The seal is seated. Bad: It does not look right."},
        }
        lines = mf.step_body_lines(generic, show_figure=False, show_photo=False)
        self.assertTrue(any(line.startswith("Good looks like:") for line in lines))
        self.assertFalse(any("Bad looks like" in line for line in lines))
        self.assertFalse(any("does not look right" in line.lower() for line in lines))
        specific = {
            "text": "Look at the seal.",
            "fields": {"GOOD vs BAD": "Good: The seal is seated. Bad: The seal is folded."},
        }
        shown = mf.step_body_lines(specific, show_figure=False, show_photo=False)
        self.assertTrue(any(line.startswith("Bad looks like: The seal is folded") for line in shown))
        _heading, shop = mf.lines_from_shop_text(
            "Step 2: Look at the seal. Good looks like: The seal is seated. "
            "Bad looks like: It does not look right. Next: Go on.",
            2,
        )
        self.assertFalse(any(line.startswith("Bad looks like") for line in shop))
        self.assertTrue(any(line.startswith("Good looks like") for line in shop))


class TestFigureUnderTheStep(unittest.TestCase):
    def _assert_figures(self, proc, name):
        from bay_procedure import (
            MARGIN,
            _CONTENT_W,
            _FIGURE_WIDTH,
            layout_problems,
            render_bay_procedure_pdf,
        )

        trace = []
        render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [], name)
        images = [mark for mark in trace if mark.kind == "image"]
        self.assertGreaterEqual(len(images), 1, name)
        center = MARGIN + _CONTENT_W / 2.0
        widths = []
        for image in images:
            width = image.x1 - image.x0
            widths.append(width)
            self.assertGreaterEqual(width, _FIGURE_WIDTH - 1.0, (name, width))
            self.assertLess(image.x0, MARGIN + _CONTENT_W * 0.5, name)
            self.assertAlmostEqual((image.x0 + image.x1) / 2.0, center, delta=2.0, msg=name)
            captions = [
                cap
                for cap in trace
                if cap.role == "caption"
                and cap.page == image.page
                and cap.x0 >= image.x0 - 2
                and cap.y1 <= image.y0 + 2
                and cap.y0 >= image.y0 - 36
            ]
            self.assertTrue(captions, (name, image.page))
            above = [
                text
                for text in trace
                if text.kind == "text"
                and text.page == image.page
                and text.y0 >= image.y1 - 2
                and text.text.startswith("Step ")
            ]
            self.assertTrue(above, (name, image.page))
        self.assertAlmostEqual(min(widths), max(widths), delta=1.0, msg=name)

    def test_thetford_and_s01_use_one_large_centered_width(self):
        from tests.test_s01_facr_standard import _sheet
        from tests.test_step_format import _thetford

        self._assert_figures(_thetford(), "thetford")
        self._assert_figures(_sheet(), "s01")

    def test_a_short_page_keeps_the_step_with_its_figure(self):
        import io

        from PIL import Image

        from bay_procedure import MARGIN, _CONTENT_W, _FIGURE_WIDTH, _SheetFlow, _paint_repair_procedure

        image = Image.new("RGB", (400, 280), (20, 40, 80))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        pages = []
        flow = _SheetFlow(pages, "Repair procedure")
        flow.y = flow.floor + 70
        _paint_repair_procedure(
            flow,
            {
                "heading": "REPAIR PROCEDURE",
                "title": "Pedal",
                "steps": [
                    {
                        "text": "Pull the pedal off.",
                        "section": "removal",
                        "fields": {
                            "WHERE": "At the pedal.",
                            "HOW": "Pull the pedal off.",
                            "GOOD vs BAD": "Good: The pedal is off. Bad: The pedal stays on.",
                            "NEXT": "On good: Install the new seal.",
                        },
                        "figure": {
                            "png": buf.getvalue(),
                            "label": "Fig. 1 PEDAL REMOVED",
                            "title": "42109",
                            "page": 1,
                        },
                    }
                ],
            },
        )
        self.assertGreater(len(pages), 1)
        self.assertFalse(pages[0].images)
        later = pages[-1]
        self.assertEqual(len(later.images), 1)
        drawn = later.images[0]
        headings = [item for item in later.texts if str(item.text).startswith("Step ")]
        self.assertTrue(headings)
        self.assertGreater(headings[0].y, drawn.y + drawn.h)
        self.assertGreaterEqual(drawn.w, _FIGURE_WIDTH - 1.0)
        self.assertAlmostEqual(drawn.x + drawn.w / 2.0, MARGIN + _CONTENT_W / 2.0, delta=2.0)
        captions = [item for item in later.texts if item.role == "caption"]
        self.assertTrue(captions)
        self.assertLess(captions[0].y, drawn.y)


if __name__ == "__main__":
    unittest.main()
