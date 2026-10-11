"""Live v4.19.40 misses: figures, the full Bay procedure, an optional photo, the procedure list, and the freeze-sensor shorthand."""
import unittest

from pathlib import Path

import manual_figures as mf
from bay_procedure import compose_sheet, compile_bay_procedure, layout_problems, render_bay_procedure_pdf
from gd_library_coach import avoid_duplicate_reply, facr_proves_from_chat, figure_render_honesty_note

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
CITE = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"


def _procedure_history(first_step):
    return [
        {"role": "user", "content": "toilet leaks under the flush lever"},
        {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
        {"role": "assistant", "content": "Check whether the vacuum breaker leaks while flushing."},
        {"role": "user", "content": "Vacuum breaker is dry. No leak there."},
        {"role": "assistant", "content": first_step},
    ]


def _turn(latest, history, draft=""):
    return avoid_duplicate_reply(draft, history, latest, CAT, MODEL)


class TestBundledThetfordFigures(unittest.TestCase):
    def test_show_me_and_a_physical_step_get_a_real_crop(self):
        show = mf.bundled_thetford_offers(
            "Check the water supply line connection at the water valve.",
            "show me the figure",
            CAT,
            MODEL,
        )
        self.assertTrue(show)
        self.assertTrue(show[0]["png"])
        self.assertFalse(mf.png_is_blank(show[0]["png"]))
        self.assertIn("png", show[0])
        valve = mf.bundled_thetford_offers(
            "Fig. 1 PEDAL REMOVED. Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me",
            CAT,
            MODEL,
        )
        labels = " ".join(item["label"] for item in valve).lower()
        self.assertIn("pedal", labels)
        self.assertTrue(any(item["label"] == "page" for item in valve))
        other = mf.bundled_thetford_offers("Read the freeze sensor.", "show me", "Air Conditioning", "FACR08")
        self.assertEqual(other, [])

    def test_empty_library_labels_the_bundled_page_as_a_last_resort(self):
        import library_figure_backfill as fb

        offers = fb.offers_for_turn(
            [],
            "Pull the pedal off.\n📖 Source: Thetford Water Valve Kit 42109, page 1",
            "show me the figure",
            CAT,
            MODEL,
        )
        self.assertTrue(offers)
        self.assertTrue(offers[0]["bundled"])
        self.assertTrue(offers[0]["png"])
        self.assertFalse(mf.png_is_blank(offers[0]["png"]))
        self.assertTrue(offers[0]["caption"].startswith("Bundled kit sheet, not from the shop library."))
        note = figure_render_honesty_note("Thetford Water Valve Kit 42109", True)
        self.assertIn("could not load", note.lower())
        self.assertNotIn("could not load", offers[0]["caption"].lower())
        miss = fb.offers_for_turn(
            [],
            "No document in the shop library for this unit.",
            "show me",
            CAT,
            MODEL,
        )
        self.assertEqual(miss, [])
        other = fb.offers_for_turn([], "Read the freeze sensor.", "show me", "Air Conditioning", "FACR08")
        self.assertEqual(other, [])
        root = Path(__file__).resolve().parents[1]
        source = root.joinpath("rv_techtrack.py").read_text(encoding="utf-8")
        backfill = root.joinpath("library_figure_backfill.py").read_text(encoding="utf-8")
        self.assertIn("offers_for_turn", source)
        self.assertIn("Backfill page images and figures", source)
        self.assertNotIn('st.button("Backfill page images")', source)
        self.assertIn("st.file_uploader(", source)
        self.assertIn("Photo (optional)", source)
        self.assertIn("bundled_thetford_offers", backfill)
        self.assertIn("Bundled kit sheet, not from the shop library.", backfill)


class TestBayProcedureWithoutLibraryCrops(unittest.TestCase):
    def test_text_only_chunks_do_not_paste_the_bundled_kit(self):
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category=CAT,
            chunks=[
                {"title": "Thetford Style II OM Permanent RV Toilet 42088", "page": 3, "excerpt": "Check the water supply line connection."},
                {"title": "Thetford Water Valve Service Kit 42109", "page": 1, "excerpt": "Disconnect RV water supply from toilet."},
            ],
        )
        self.assertEqual(proc.procedures, [])
        blob = " ".join(proc.bay_order).lower()
        self.assertIn("supply", blob)
        self.assertIn("vacuum", blob)
        pages = compose_sheet(proc)
        images = [image for page in pages for image in page.images]
        self.assertGreaterEqual(len(images), 2)
        shown = " ".join(fig.title for group in proc.step_figures for fig in group)
        self.assertIn("42109", shown)
        self.assertIn("34123", shown)
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc).lower()
        doc.close()
        self.assertNotIn("disconnect rv water supply", text)
        self.assertNotIn("connect rv water supply line to toilet", text)


class TestOptionalPhotoAndProcedureList(unittest.TestCase):
    def setUp(self):
        first = _turn("Vacuum breaker is dry. No leak there.", [
            {"role": "user", "content": "toilet leaks under the flush lever"},
            {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
            {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
            {"role": "assistant", "content": "Check whether the vacuum breaker leaks while flushing."},
        ])
        self.first = first
        self.history = _procedure_history(first)

    def test_typed_yes_no_and_a_short_answer_advance_once(self):
        self.assertIn("Step 1 of", self.first)
        self.assertIn("Yes, go to the next step.", self.first)
        self.assertIn("No, do this step again.", self.first)
        self.assertLess(int(self.first.split("Step 1 of ", 1)[1].split(".", 1)[0]), 20)
        for answer in ("Yes.", "No.", "Water is off."):
            reply = _turn(answer, self.history)
            self.assertIn("Step 2 of", reply, answer)
            self.assertNotIn("Send the photo before the next step.", reply, answer)
        held = _turn("Not yet.", self.history)
        self.assertIn("Step 1 of", held)
        self.assertIn("Send the photo before the next step.", held)
        self.assertEqual(held.count("Send the photo before the next step."), 1)
        again = _turn("Not yet.", self.history + [
            {"role": "user", "content": "Not yet."},
            {"role": "assistant", "content": held},
        ])
        self.assertIn("Step 2 of", again)
        self.assertNotIn("Send the photo before the next step.", again)
        shown = _turn("show me the figure", self.history)
        self.assertIn("Step 1 of", shown)
        self.assertNotIn("Step 2 of", shown)

    def test_repair_procedure_is_the_numbered_list(self):
        reply = _turn("What is the repair procedure?", self.history)
        self.assertIn("REMOVAL", reply)
        self.assertIn("INSTALLATION", reply)
        self.assertIn("\n1.", reply)
        self.assertNotIn("Step 1 of", reply)
        self.assertLess(reply.lower().find("removal"), reply.lower().find("installation"))
        low = reply.lower()
        self.assertIn("pedal", low)
        self.assertIn("retainer", low)


class TestFreezeSensorShorthand(unittest.TestCase):
    def test_2k_at_25c_authorizes_on_the_fifth_turn(self):
        turns = [
            "Furrion FACR08HESA2-PS rooftop AC. Water leaking inside while running.",
            "Drain is clear. Pan is clean and draining. Base-pan slope is fine.",
            "Filter is clean. Fan spins freely.",
            "Suction line is not iced. 68/235 psi.",
            "Freeze sensor 2k at 25C.",
        ]
        history = []
        replies = []
        for latest in turns:
            reply = avoid_duplicate_reply(
                "Read the freeze sensor.",
                history,
                latest,
                "Air Conditioning",
                "FACR08HESA2-PS",
            )
            replies.append(reply)
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        self.assertIn("Read the freeze sensor.", replies[3])
        self.assertNotIn("replace the rooftop assembly", replies[3].lower())
        last = replies[4].lower()
        self.assertIn("authorize rooftop assembly", last)
        self.assertIn("replace the rooftop assembly", last)
        self.assertIn("ccd-0007990", last)
        prior = [
            {
                "role": "user",
                "content": "Furrion FACR08HESA2-PS rooftop AC. Water leaking inside while running. Frost on the evaporator.",
            },
            {"role": "assistant", "content": "Read the freeze sensor."},
        ]
        facts = facr_proves_from_chat(prior, "Freeze sensor 2k at 25C.")
        self.assertEqual(facts.get("facr_sensor_reading"), "reported")
        for sample in ("sensor is 2.0 kohms", "freeze sensor 2000 ohms", "It reads 2k"):
            parsed = facr_proves_from_chat(prior, sample)
            self.assertEqual(parsed.get("facr_sensor_reading"), "reported", sample)

    def test_pressures_alone_and_a_no_pressure_walk_do_not_authorize(self):
        alone = avoid_duplicate_reply(
            "Read the freeze sensor.",
            [],
            "68/235 psi.",
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        self.assertNotIn("replace the rooftop assembly", alone.lower())
        history = []
        reply = ""
        for latest in (
            "Furrion FACR08 rooftop AC. Water leaking inside.",
            "Drain is clear. Pan is clean and draining. Base-pan slope is fine.",
            "Filter is clean. Fan spins freely.",
            "Freeze sensor 2k at 25C.",
        ):
            reply = avoid_duplicate_reply(
                "Read the freeze sensor.",
                history,
                latest,
                "Air Conditioning",
                "FACR08HESA2-PS",
            )
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
        self.assertNotIn("replace the rooftop assembly", reply.lower())
        self.assertNotIn("authorize rooftop assembly", reply.lower())


if __name__ == "__main__":
    unittest.main()
