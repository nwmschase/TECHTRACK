"""Lippert Power Gear pages must not illustrate a Thetford, Dometic, or other Lippert line.

The live library gained Power Gear tip sheets. A missing brand was treated as
a match, so How blocks and figures from those sheets landed on other cases.
The step cursor reads the stored chat text, and that appended How block
changed which Thetford check a real answer closed.
"""
import io
import unittest

from PIL import Image

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import (
    cited_figure_count,
    compile_bay_procedure,
    paint_library_step_figures,
    render_bay_procedure_pdf,
)
from gd_library_coach import avoid_duplicate_reply

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
HOW = (
    "\n\nHow (Tip Sheet #216, page 4): Tools: wrench. "
    "Meter setting: not stated in Tip Sheet #216. "
    "Connector or pin: not stated in Tip Sheet #216. "
    "Expected reading: not stated in Tip Sheet #216. "
    "Order: 1. Remove the pump seal at the closet flange. "
    "2. Replace the motor brake. Step 1 of 14. "
    "Torque or spec: not stated in Tip Sheet #216\n"
    "Power Gear pump replacement / page 2 / Fig. 3 motor brake"
)


def _png() -> bytes:
    image = Image.new("RGB", (32, 32), (20, 40, 80))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


TINY = _png()


def _row(doc_id, title, brand, label, caption, product_line="", category_name="", models=""):
    return {
        "id": doc_id,
        "document_id": doc_id,
        "kind": "figure",
        "title": title,
        "brand": brand,
        "product_line": product_line,
        "category_name": category_name,
        "models": models,
        "page": 1,
        "label": label,
        "caption": caption,
        "png": TINY,
    }


def _library():
    return [
        _row(
            1,
            "Tip Sheet #216",
            "Lippert",
            "Fig. 4 pump seal",
            "Power Gear pump seal",
            product_line="Power Gear",
            category_name="Leveling",
        ),
        _row(
            2,
            "Power Gear motor brake",
            "Power Gear",
            "Fig. 2 motor brake",
            "Motor brake assembly",
            product_line="Power Gear",
            category_name="Leveling",
        ),
        _row(
            3,
            "Power Gear pump replacement",
            "Power Gear",
            "Fig. 1 pump replacement",
            "Hydraulic pump replacement",
            product_line="Power Gear",
            category_name="Leveling",
        ),
        _row(
            4,
            "Thetford Water Valve Kit 42109",
            "Thetford",
            "Fig. 1 PEDAL REMOVED",
            "Water valve kit 42109 pedal",
            category_name="Plumbing / Toilets",
        ),
        _row(
            5,
            "Thetford Vacuum Breaker Kit 34123/34122",
            "Thetford",
            "Fig. 1 vacuum breaker",
            "Vacuum breaker kit 34122",
            category_name="Plumbing / Toilets",
        ),
        _row(
            6,
            "Dometic Brisk II diagnostic 3311071",
            "Dometic",
            "Fig. 2 ceiling thermostat",
            "B57915 ceiling selector",
            category_name="Air Conditioning",
        ),
        _row(
            7,
            "Lippert Level Up Towable Owner's Manual",
            "Lippert",
            "Fig. 1 CARTRIDGE VALVE",
            "Cartridge valve 177094",
            product_line="Level Up",
            category_name="Leveling",
            models="807662",
        ),
        _row(
            8,
            "Lippert PSX1 stabilizer jack",
            "Lippert",
            "Fig. 2 roll pin",
            "PSX1 manual crank roll pin",
            product_line="PSX1",
            category_name="Leveling",
            models="PSX1",
        ),
    ]


def _blob(offers) -> str:
    return " ".join(
        f"{item.get('title') or ''} {item.get('label') or ''} {item.get('caption') or ''}"
        for item in offers
    ).lower()


def _turn(latest, history, draft=""):
    return avoid_duplicate_reply(draft, history, latest, CAT, MODEL)


class TestOffBrandFiguresStayOff(unittest.TestCase):
    def setUp(self):
        self.rows = _library()

    def test_dometic_ac_does_not_take_the_pump_seal_sheet(self):
        offers = fb.offers_for_turn(
            self.rows,
            "Replace the ceiling thermostat.",
            "The fan runs and the air is not cold. Show me the figure.",
            "Air Conditioning",
            "Dometic B57915E711J0EMX",
        )
        blob = _blob(offers)
        self.assertIn("dometic", blob)
        self.assertIn("thermostat", blob)
        bare = fb.offers_for_turn(
            self.rows,
            "Replace the ceiling thermostat.",
            "The fan runs and the air is not cold.",
            "Air Conditioning",
            "B57915E711J0EMX",
        )
        bare_blob = _blob(bare)
        self.assertIn("dometic", bare_blob)
        self.assertNotIn("tip sheet", bare_blob)
        self.assertNotIn("power gear", bare_blob)
        self.assertNotIn("tip sheet", blob)
        self.assertNotIn("216", blob)
        self.assertNotIn("power gear", blob)
        self.assertNotIn("pump seal", blob)
        self.assertNotIn("thetford", blob)

    def test_thetford_show_me_is_the_pedal_not_power_gear(self):
        reply = mf.thetford_proving_line("valve")
        offers = fb.offers_for_turn(self.rows, reply, "show me the pedal", CAT, MODEL)
        self.assertTrue(offers)
        blob = _blob(offers)
        self.assertIn("42109", blob)
        self.assertIn("pedal", blob)
        self.assertNotIn("tip sheet", blob)
        self.assertNotIn("power gear", blob)
        self.assertNotIn("motor brake", blob)
        self.assertNotIn("3412", blob)
        self.assertFalse(offers[0].get("bundled"))

    def test_vacuum_step_figure_is_the_breaker_kit(self):
        reply = mf.thetford_proving_line("vacuum")
        offers = fb.offers_for_turn(self.rows, reply, "show me", CAT, MODEL)
        self.assertTrue(offers)
        blob = _blob(offers)
        self.assertIn("3412", blob)
        self.assertNotIn("42109", blob)
        self.assertNotIn("power gear", blob)
        self.assertNotIn("tip sheet", blob)

    def test_library_with_only_power_gear_falls_back_to_the_thetford_kit(self):
        foreign = [row for row in self.rows if "thetford" not in row["title"].lower()]
        offers = fb.offers_for_turn(
            foreign,
            mf.thetford_proving_line("valve"),
            "show me the pedal",
            CAT,
            MODEL,
        )
        self.assertTrue(offers)
        blob = _blob(offers)
        self.assertIn("pedal", blob)
        self.assertTrue(offers[0].get("bundled"))
        self.assertNotIn("tip sheet", blob)
        self.assertNotIn("power gear", blob)

    def test_level_up_ground_control_and_psx1_do_not_share_power_gear_figures(self):
        cases = (
            (
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes then dumps back to home. Loose cartridge 177094.",
                "177094",
            ),
            (
                "Leveling",
                "Lippert Ground Control 343633",
                "Auto-level lifts the driver side. Zero-point calibration is the repair.",
                "",
            ),
            (
                "Leveling",
                "Lippert PSX1",
                "Front stabilizer jack. The roll pin is broken.",
                "roll pin",
            ),
        )
        for category, model, reply, expect in cases:
            offers = fb.offers_for_turn(self.rows, reply, "show me the figure", category, model)
            blob = _blob(offers)
            self.assertNotIn("tip sheet", blob, model)
            self.assertNotIn("power gear", blob, model)
            self.assertNotIn("motor brake", blob, model)
            self.assertNotIn("pump seal", blob, model)
            self.assertNotIn("thetford", blob, model)
            if expect:
                self.assertIn(expect, blob, model)

    def test_packets_keep_the_case_document_only(self):
        chunks = [
            {"document_id": 1, "title": "Tip Sheet #216", "page": 1, "excerpt": "Remove the pump seal."},
            {"document_id": 4, "title": "Thetford Water Valve Kit 42109", "page": 1, "excerpt": "Pull the pedal."},
            {"document_id": 2, "title": "Power Gear motor brake", "page": 1, "excerpt": "Release the motor brake."},
        ]
        packets = fb.figure_packets(
            self.rows,
            chunks,
            "Plumbing / Toilets Thetford Style II 42070 pedal 42109",
        )
        titles = " ".join(packet["title"] for packet in packets).lower()
        self.assertIn("42109", titles)
        self.assertNotIn("tip sheet", titles)
        self.assertNotIn("power gear", titles)
        self.assertNotIn("motor brake", titles)


class TestThetfordCursorIgnoresAppendedHow(unittest.TestCase):
    def _vacuum_history(self):
        history = [
            {"role": "user", "content": "toilet leaks under the flush lever"},
            {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        ]
        vacuum = _turn(
            "Supply is tight. The water valve weeps at the pedal.",
            history,
            "Check whether the vacuum breaker leaks while flushing.",
        )
        history = history + [
            {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
            {"role": "assistant", "content": vacuum + HOW},
        ]
        return history

    def test_a_real_answer_closes_the_vacuum_check_when_how_says_flange(self):
        nxt = _turn("No leak while flushing.", self._vacuum_history())
        self.assertIn("Step 1 of", nxt)
        self.assertNotIn("Step 2 of", nxt)
        self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", nxt)
        self.assertNotIn("Tip Sheet", nxt)
        self.assertNotIn("motor brake", nxt.lower())

    def test_real_answers_advance_the_procedure_past_step_1(self):
        first = _turn("No leak while flushing.", self._vacuum_history())
        self.assertIn("Step 1 of 14", first)
        history = self._vacuum_history() + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": first + HOW},
        ]
        second = _turn("Water is off.", history)
        self.assertIn("Step 2 of", second)
        self.assertNotIn("Step 1 of", second)
        history = history + [
            {"role": "user", "content": "Water is off."},
            {"role": "assistant", "content": second + HOW},
        ]
        third = _turn("The bolt covers are off.", history)
        self.assertIn("Step 3 of", third)
        self.assertNotIn("Step 1 of", third)
        self.assertNotIn("Step 2 of", third)

    def test_not_checked_yet_does_not_harvest_the_tip_sheet(self):
        first = _turn("No leak while flushing.", self._vacuum_history())
        history = self._vacuum_history() + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": first + HOW},
        ]
        held = _turn("Not checked yet.", history)
        self.assertIn("Step 1 of", held)
        self.assertNotIn("motor brake", held.lower())
        self.assertNotIn("Tip Sheet", held)
        self.assertNotIn("pump seal", held.lower())


class TestThetfordBayFigures(unittest.TestCase):
    def test_matching_kit_figures_sit_beside_the_steps(self):
        excerpt = (
            "Needed: wrench. Remove the pump seal. Install the motor brake. "
            "Figure 4 shows the pump seal on the Power Gear motor. "
        ) * 4
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category=CAT,
            chunks=[
                {
                    "title": "Tip Sheet #216",
                    "brand": "Lippert",
                    "product_line": "Power Gear",
                    "page": 4,
                    "excerpt": excerpt,
                    "figures": [
                        {
                            "png": TINY,
                            "label": "Fig. 4 pump seal",
                            "title": "Tip Sheet #216",
                            "page": 4,
                        }
                    ],
                },
                {
                    "title": "Thetford Style II OM Permanent RV Toilet 42088",
                    "brand": "Thetford",
                    "page": 3,
                    "excerpt": "Check the water supply line connection.",
                },
            ],
        )
        self.assertNotIn("How (Tip Sheet", " ".join(proc.bay_order))
        self.assertNotIn("pump seal", " ".join(proc.bay_order).lower())
        proc = paint_library_step_figures(proc, _library())
        vacuum = next(i for i, step in enumerate(proc.bay_order) if "vacuum breaker" in step.lower())
        valve = next(i for i, step in enumerate(proc.bay_order) if "42109" in step)
        self.assertIn("3412", proc.step_figures[vacuum][0].title)
        self.assertIn("42109", proc.step_figures[valve][0].title)
        placed = " ".join(
            fig.title
            for group in proc.step_figures
            for fig in group
        ).lower()
        self.assertNotIn("tip sheet", placed)
        self.assertNotIn("power gear", placed)
        self.assertNotIn("motor brake", placed)
        self.assertGreater(cited_figure_count(proc), 0)
        import pymupdf

        doc = pymupdf.open(stream=render_bay_procedure_pdf(proc), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        images = sum(len(page.get_images()) for page in doc)
        doc.close()
        self.assertGreater(images, 0)
        self.assertNotIn("Tip Sheet", text)
        self.assertNotIn("Power Gear", text)
        self.assertNotIn("motor brake", text.lower())


def _tip_chunk():
    excerpt = (
        "Needed: wrench. Remove the pump seal. Install the motor brake. "
        "Figure 4 shows the pump seal on the Power Gear motor. "
    ) * 4
    return {
        "title": "Tip Sheet #216",
        "brand": "Lippert",
        "product_line": "Power Gear",
        "category_name": "Leveling",
        "page": 4,
        "excerpt": excerpt,
        "figures": [
            {
                "png": TINY,
                "label": "Fig. 4 pump seal",
                "caption": "Power Gear pump seal",
                "title": "Tip Sheet #216",
                "page": 4,
            }
        ],
    }


_OFF_BRAND = ("tip sheet", "power gear", "pump seal", "motor brake", "216")


def _assert_clean(case, proc):
    sheet = " ".join(proc.bay_order)
    lowered = sheet.lower()
    case.assertNotIn("How (Tip Sheet", sheet)
    for banned in _OFF_BRAND:
        case.assertNotIn(banned, lowered, proc.model)
    placed = " ".join(
        f"{fig.title} {fig.caption}"
        for group in (proc.step_figures or [])
        for fig in group
    )
    placed += " " + " ".join(
        f"{fig.title} {fig.caption}" for fig in (proc.figures or [])
    )
    for banned in _OFF_BRAND:
        case.assertNotIn(banned, placed.lower(), proc.model)


class TestEveryCaseBlocksOffBrand(unittest.TestCase):
    def test_a_document_with_no_system_does_not_fill_a_named_system(self):
        blank = _row(9, "Lippert service bulletin", "Lippert", "Fig. 1", "hydraulic pump")
        self.assertFalse(
            fb.fits_case(
                blank,
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes then dumps home.",
                "",
            )
        )
        self.assertFalse(
            fb.fits_case(
                blank,
                "Air Conditioning",
                "B57915E711J0EMX",
                "The air is not cold.",
                "Replace the ceiling thermostat.",
            )
        )

    def test_how_block_stays_off_every_case(self):
        cases = (
            ("Air Conditioning", "B57915E711J0EMX", "Replace the ceiling thermostat."),
            ("Leveling", "Lippert Level Up Advantage 807662", "Manual Mode flashes then dumps home."),
            ("Leveling", "Lippert PSX1", "The roll pin is broken."),
            ("Leveling", "Lippert Level Up Advantage 807662", "Replace cartridge valve 177094."),
            (CAT, MODEL, mf.thetford_proving_line("valve")),
        )
        tip = _tip_chunk()
        for category, model, reply in cases:
            how = fb.procedure_how(
                tip,
                tip["excerpt"],
                tip["title"],
                tip["page"],
                category,
                model,
                "show me",
                reply,
            )
            self.assertEqual(how, "", model)


class TestThetfordCursorWalksAllFourteen(unittest.TestCase):
    def test_yes_advances_step_1_through_14_with_the_how_block_stored(self):
        history = [
            {"role": "user", "content": "toilet leaks under the flush lever"},
            {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        ]
        vacuum = _turn(
            "Supply is tight. The water valve weeps at the pedal.",
            history,
            "Check whether the vacuum breaker leaks while flushing.",
        )
        history = history + [
            {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
            {"role": "assistant", "content": vacuum + HOW},
        ]
        nxt = _turn("No leak while flushing.", history)
        self.assertIn("Step 1 of 14", nxt)
        self.assertNotIn("Tip Sheet", nxt)
        history = history + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": nxt + HOW},
        ]
        for number in range(2, 15):
            nxt = _turn("Yes.", history)
            self.assertIn(f"Step {number} of 14", nxt)
            self.assertNotRegex(nxt, rf"Step {number - 1} of 14")
            self.assertNotIn("Tip Sheet", nxt)
            self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", nxt)
            history = history + [
                {"role": "user", "content": "Yes."},
                {"role": "assistant", "content": nxt + HOW},
            ]
        done = _turn("Yes.", history)
        self.assertIn("The repair procedure is done.", done)
        self.assertNotIn("Step 1 of", done)
        self.assertNotIn("Step 14 of", done)
        self.assertNotIn("Tip Sheet", done)


class TestBayFiguresComeFromTheMatchingDoc(unittest.TestCase):
    def _sheet(self, concern, brand, model, category, extra_chunks=None):
        chunks = [_tip_chunk()]
        chunks.extend(extra_chunks or [])
        proc = compile_bay_procedure(
            concern=concern,
            brand=brand,
            model=model,
            category=category,
            chunks=chunks,
        )
        proc = paint_library_step_figures(proc, _library())
        return proc

    def test_s09_s06_s14_s20_and_thetford_stay_on_their_own_documents(self):
        import pymupdf

        s09 = self._sheet(
            "AC turns on but will not blow cold. Peacemaker bypass cools. Ceiling bypass cools.",
            "Dometic",
            "B57915E711J0EMX",
            "Air Conditioning",
            extra_chunks=[
                {
                    "title": "Dometic Brisk II",
                    "brand": "Dometic",
                    "page": 23,
                    "excerpt": "Ceiling thermostat selector.",
                }
            ],
        )
        _assert_clean(self, s09)
        ceiling = next(i for i, step in enumerate(s09.bay_order) if "ceiling thermostat" in step.lower())
        self.assertTrue(s09.step_figures[ceiling])
        self.assertIn("Dometic", s09.step_figures[ceiling][0].title)
        self.assertIn("b57915", s09.step_figures[ceiling][0].caption.lower())

        s06 = self._sheet(
            "Manual Mode flashes then dumps back to home. Auto Level still works.",
            "Lippert",
            "Level Up Advantage 807662",
            "Leveling",
        )
        _assert_clean(self, s06)
        for group in s06.step_figures or []:
            for fig in group:
                self.assertRegex(fig.title.lower(), r"level[\s-]*up|807662")

        s14 = self._sheet(
            "Front stabilizer jack. Power works. Manual crank will not operate. Roll pin broken.",
            "Lippert",
            "PSX1",
            "Leveling",
        )
        _assert_clean(self, s14)
        pin = next(i for i, step in enumerate(s14.bay_order) if "roll pin" in step.lower())
        self.assertTrue(s14.step_figures[pin])
        self.assertIn("PSX1", s14.step_figures[pin][0].title)
        self.assertIn("roll pin", s14.step_figures[pin][0].caption.lower())

        s20 = self._sheet(
            "Level Up front jacks drift. Loose cartridge valve 177094.",
            "Lippert",
            "Level Up Advantage 807662",
            "Leveling",
        )
        _assert_clean(self, s20)
        cartridge = next(i for i, step in enumerate(s20.bay_order) if "177094" in step)
        self.assertTrue(s20.step_figures[cartridge])
        self.assertIn("Level Up", s20.step_figures[cartridge][0].title)
        self.assertIn("177094", s20.step_figures[cartridge][0].caption)

        thetford = self._sheet(
            "Thetford 42070 leaks under the flush lever",
            "Thetford",
            "42070",
            CAT,
            extra_chunks=[
                {
                    "title": "Thetford Style II OM Permanent RV Toilet 42088",
                    "brand": "Thetford",
                    "page": 3,
                    "excerpt": "Check the water supply line connection.",
                }
            ],
        )
        _assert_clean(self, thetford)
        valve = next(i for i, step in enumerate(thetford.bay_order) if "42109" in step)
        self.assertTrue(thetford.step_figures[valve])
        self.assertIn("42109", thetford.step_figures[valve][0].title)

        for proc in (s09, s06, s14, s20, thetford):
            doc = pymupdf.open(stream=render_bay_procedure_pdf(proc), filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            self.assertNotIn("Tip Sheet", text)
            self.assertNotIn("Power Gear", text)
            self.assertNotIn("pump seal", text.lower())
            self.assertNotIn("motor brake", text.lower())
