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


def _row(
    doc_id,
    title,
    brand,
    label,
    caption,
    product_line="",
    category_name="",
    models="",
    width=0,
    height=0,
):
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
        "width": width,
        "height": height,
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
        _row(
            9,
            "Thetford Plastic Tank",
            "Thetford",
            "Fig. 1 plastic tank",
            "Plastic tank waste",
            category_name="Plumbing / Toilets",
        ),
        _row(
            11,
            "(Discontinued) Atwood Manual Tongue Jack Bevel Gear",
            "Atwood",
            "Fig. 1 bevel gear",
            "SAMPLE watermark",
            product_line="Tongue Jack",
            category_name="Leveling",
        ),
        _row(
            12,
            "Lippert TI-143",
            "Lippert",
            "port header",
            "TI-143 port header strip",
            product_line="Leveling",
            category_name="Leveling",
            width=960,
            height=36,
        ),
        _row(
            13,
            "Lippert TI-489 Titan Electric Bracket",
            "Lippert",
            "Fig. 1 Titan bracket",
            "TI-489 Titan bracket",
            product_line="Titan",
            category_name="Leveling",
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

    def test_library_with_only_power_gear_shows_no_bundled_sheet(self):
        foreign = [row for row in self.rows if "thetford" not in row["title"].lower()]
        offers = fb.offers_for_turn(
            foreign,
            mf.thetford_proving_line("valve"),
            "show me the pedal",
            CAT,
            MODEL,
        )
        self.assertEqual(offers, [])
        self.assertNotIn("bundled kit sheet", _blob(offers))

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
        self.assertIn("**Step 1:", nxt)
        self.assertNotRegex(nxt, r"(?<!\d)Step 2:")
        self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", nxt)
        self.assertNotIn("Tip Sheet", nxt)
        self.assertNotIn("motor brake", nxt.lower())

    def test_real_answers_advance_the_procedure_past_step_1(self):
        first = _turn("No leak while flushing.", self._vacuum_history())
        self.assertIn("**Step 1:", first)
        history = self._vacuum_history() + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": first + HOW},
        ]
        second = _turn("Water is off.", history)
        self.assertIn("**Step 2:", second)
        self.assertNotRegex(second, r"(?<!\d)Step 1:")
        history = history + [
            {"role": "user", "content": "Water is off."},
            {"role": "assistant", "content": second + HOW},
        ]
        third = _turn("The bolt covers are off.", history)
        self.assertIn("**Step 3:", third)
        self.assertNotRegex(third, r"(?<!\d)Step 1:")
        self.assertNotRegex(third, r"(?<!\d)Step 2:")

    def test_not_checked_yet_does_not_harvest_the_tip_sheet(self):
        first = _turn("No leak while flushing.", self._vacuum_history())
        history = self._vacuum_history() + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": first + HOW},
        ]
        held = _turn("Not checked yet.", history)
        self.assertIn("**Step 1:", held)
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
        self.assertIn("**Step 1:", nxt)
        self.assertNotIn("Tip Sheet", nxt)
        history = history + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": nxt + HOW},
        ]
        total = len(mf.thetford_kit_layout("valve")["steps"])
        self.assertGreater(total, 13)
        for number in range(2, total + 1):
            nxt = _turn("Yes.", history)
            self.assertIn(f"**Step {number}:", nxt)
            self.assertNotRegex(nxt, rf"(?<!\d)Step {number - 1}:")
            self.assertNotIn("Tip Sheet", nxt)
            self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", nxt)
            history = history + [
                {"role": "user", "content": "Yes."},
                {"role": "assistant", "content": nxt + HOW},
            ]
        done = _turn("Yes.", history)
        self.assertIn("The repair procedure is done.", done)
        self.assertIn("Look for leaks.", done)
        self.assertNotRegex(done, r"Step \d+:")
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
            self.assertNotIn("Plastic Tank", text)


class TestThetfordKitFiguresOnly(unittest.TestCase):
    def test_valve_and_breaker_offers_are_the_kits(self):
        rows = _library()
        valve = fb.offers_for_turn(
            rows, mf.thetford_proving_line("valve"), "show me the pedal", CAT, MODEL
        )
        breaker = fb.offers_for_turn(
            rows, mf.thetford_proving_line("vacuum"), "show me", CAT, MODEL
        )
        valve_blob = _blob(valve)
        breaker_blob = _blob(breaker)
        self.assertIn("42109", valve_blob)
        self.assertIn("34123", breaker_blob)
        for blob in (valve_blob, breaker_blob):
            self.assertNotIn("plastic tank", blob)
            self.assertNotIn("motor brake", blob)
            self.assertNotIn("tip sheet", blob)
            self.assertNotIn("power gear", blob)
        self.assertNotIn("34123", valve_blob)
        self.assertNotIn("42109", breaker_blob)


class TestValveFindingDoesNotReturnToVacuum(unittest.TestCase):
    def _on_step_1(self):
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
        step1 = _turn("No leak while flushing.", history)
        self.assertIn("**Step 1:", step1)
        history = history + [
            {"role": "user", "content": "No leak while flushing."},
            {"role": "assistant", "content": step1 + HOW},
        ]
        return history

    def test_a_leak_after_the_valve_finding_stays_on_the_valve_kit(self):
        history = self._on_step_1()
        for answer in ("It still leaks.", "Leak at the pedal.", "The water valve still weeps."):
            nxt = _turn(answer, history)
            self.assertIn("**Step 2:", nxt, answer)
            self.assertNotIn("34123", nxt, answer)
            self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", nxt, answer)
            self.assertIn("42109", nxt, answer)


class TestBayPdfShowsKitCrops(unittest.TestCase):
    def test_steps_get_real_crops_not_a_text_only_figure_line(self):
        import pymupdf
        from PIL import Image as PilImage

        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category=CAT,
            chunks=[
                {
                    "title": "Thetford Style II OM Permanent RV Toilet 42088",
                    "page": 3,
                    "excerpt": "Check the water supply line connection.",
                }
            ],
        )
        self.assertGreaterEqual(len(proc.procedures), 1)
        self.assertFalse(any("3412" in (procedure.get("title") or "") for procedure in proc.procedures))
        vacuum = next(i for i, step in enumerate(proc.bay_order) if "vacuum breaker" in step.lower())
        valve = next(i for i, step in enumerate(proc.bay_order) if "42109" in step)
        for index, needle in ((vacuum, "34123"), (valve, "42109")):
            self.assertTrue(proc.step_figures[index], needle)
            fig = proc.step_figures[index][0]
            self.assertIn(needle, fig.title)
            self.assertFalse(mf.png_is_blank(fig.image_png))
            image = PilImage.open(io.BytesIO(fig.image_png))
            self.assertGreater(image.size[0], 80, needle)
            self.assertGreater(image.size[1], 80, needle)
        doc = pymupdf.open(stream=render_bay_procedure_pdf(proc), filetype="pdf")
        widths = []
        for page in doc:
            for info in page.get_images():
                extracted = doc.extract_image(info[0])
                widths.append(extracted["width"])
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        self.assertGreaterEqual(len(widths), 2)
        self.assertTrue(all(width > 80 for width in widths))
        self.assertNotIn("Tip Sheet", text)
        self.assertNotIn("Power Gear", text)
        self.assertNotIn("Plastic Tank", text)
        self.assertNotIn("motor brake", text.lower())


class TestS09Turn2StaysClean(unittest.TestCase):
    def test_peacemaker_bypass_reply_has_no_off_brand_block(self):
        history = [
            {"role": "user", "content": "AC turns on but will not blow cold."},
            {
                "role": "assistant",
                "content": (
                    "Confirm the fan runs, then do the Peacemaker bypass at the rooftop unit "
                    "and report whether it cools."
                ),
            },
        ]
        latest = "Peacemaker bypass at the rooftop unit cools."
        reply = avoid_duplicate_reply(
            "Do the Peacemaker bypass at the rooftop unit Check the ceiling selector.",
            history,
            latest,
            "Air Conditioning",
            "B57915E711J0EMX",
        )
        low = reply.lower()
        self.assertIn("ceiling", low)
        for banned in ("tip sheet", "power gear", "motor brake", "pump seal", "plastic tank", "thetford", "42109", "34123"):
            self.assertNotIn(banned, low, banned)
        self.assertNotIn("How (Tip Sheet", reply)
        offers = fb.offers_for_turn(
            _library(),
            reply,
            latest,
            "Air Conditioning",
            "B57915E711J0EMX",
        )
        blob = _blob(offers)
        for banned in ("tip sheet", "power gear", "motor brake", "pump seal", "plastic tank", "thetford", "42109", "34123"):
            self.assertNotIn(banned, blob, banned)
        if offers:
            self.assertIn("dometic", blob)


def _stored_live_step(step: str, how: str, figure: str) -> str:
    """One stored turn: flattened eight fields, the live How block, then the caption.

    Live joins the shop lines onto one line and appends How (title): plus
    "Title / page N / Fig. ...". The title's ")" must not hide the step number.
    """
    return (
        " ".join(step.splitlines())
        + how
        + f" Thetford Water Valve Kit 42109 / page 1 / {figure}"
    )


def _live_how(title="(Discontinued) Atwood Manual Tongue Jack Bevel Gear"):
    """The block live appends: a How title that contains ")", then a caption."""
    return (
        f"\n\nHow ({title}, page 1): Tools: wrench. "
        "Meter setting: not stated in the manual. "
        "Order: 1. Remove the pump seal at the closet flange. "
        "Step 1 of 14. "
        f"{title} / page 1 / Fig. 1 bevel gear"
    )


class TestLiveThetfordTranscript(unittest.TestCase):
    def test_the_drive_arm_weep_enters_the_valve_kit_and_the_steps_advance(self):
        how = _live_how()
        history = [
            {"role": "user", "content": "Style II 42070 leaks under the flush lever"},
            {"role": "assistant", "content": mf.thetford_proving_line("supply") + how},
            {"role": "user", "content": "Supply is tight. No leak at the connection."},
            {"role": "assistant", "content": mf.thetford_proving_line("vacuum") + how},
        ]
        step = _turn("water valve body weeps at the drive arm", history)
        self.assertIn("**Step 1:", step)
        self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", step)
        self.assertNotRegex(step, r"(?<!\d)Step 2:")
        seen = [1]
        history = history + [
            {"role": "user", "content": "water valve body weeps at the drive arm"},
            {"role": "assistant", "content": _stored_live_step(step, how, "Fig. 3 WATER")},
        ]
        # Each real answer leaves the step that already shipped and opens the next one.
        total = len(mf.thetford_kit_layout("valve")["steps"])
        self.assertGreater(total, 13)
        for number in range(2, total + 1):
            answer = "Yes."
            step = _turn(answer, history)
            self.assertIn(f"**Step {number}:", step, answer)
            self.assertNotRegex(step, rf"(?<!\d)Step {number - 1}:", answer)
            self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", step, answer)
            self.assertNotIn("34123", step, answer)
            seen.append(number)
            history = history + [
                {"role": "user", "content": answer},
                {"role": "assistant", "content": _stored_live_step(step, how, "Fig. 1")},
            ]
        self.assertEqual(seen, list(range(1, total + 1)))
        done = _turn("The water is on.", history)
        self.assertIn("The repair procedure is done.", done)
        self.assertIn("Look for leaks.", done)
        self.assertNotRegex(done, r"Step \d+:")
        self.assertNotIn("Check whether the vacuum breaker leaks while flushing.", done)


class TestMissingStorageUsesTheBundledCrop(unittest.TestCase):
    def test_a_thetford_offer_without_an_r2_object_still_has_a_crop(self):
        png = mf.png_for_library_offer(
            {
                "title": "Thetford Water Valve Kit 42109",
                "label": "Fig. 1 PEDAL REMOVED",
                "caption": "Thetford Water Valve Kit 42109 / page 1 / Fig. 1 PEDAL REMOVED",
                "page": 1,
                "file_path": "documents/9_missing_thetford.pdf",
                "image_path": "library-pages/9/p1-fig-1.png",
                "bundled": True,
            }
        )
        self.assertTrue(png)
        self.assertFalse(mf.png_is_blank(png))
        other = mf.png_for_library_offer(
            {
                "title": "Dometic Brisk II",
                "label": "Fig. 2 ceiling thermostat",
                "file_path": "documents/missing.pdf",
                "image_path": "library-pages/6/p1-fig.png",
            }
        )
        self.assertEqual(other, b"")


class TestWrongSystemFiguresStayOff(unittest.TestCase):
    def test_s14_drops_the_atwood_sample_and_the_ti143_header(self):
        proc = compile_bay_procedure(
            concern="Front stabilizer jack. Power works. Manual crank will not operate. Roll pin broken.",
            brand="Lippert",
            model="PSX1",
            category="Leveling",
            chunks=[
                {
                    "title": "(Discontinued) Atwood Manual Tongue Jack Bevel Gear",
                    "brand": "Atwood",
                    "product_line": "Tongue Jack",
                    "page": 1,
                    "excerpt": "SAMPLE watermark. Bevel gear for the manual tongue jack. " * 8,
                    "figures": [
                        {
                            "png": TINY,
                            "label": "Fig. 1 bevel gear",
                            "caption": "SAMPLE watermark",
                            "title": "(Discontinued) Atwood Manual Tongue Jack Bevel Gear",
                            "page": 1,
                        }
                    ],
                },
                {
                    "title": "Lippert TI-143",
                    "brand": "Lippert",
                    "page": 2,
                    "excerpt": "TI-143 port header strip. " * 12,
                    "figures": [
                        {
                            "png": TINY,
                            "label": "port header",
                            "caption": "TI-143 port header strip",
                            "title": "Lippert TI-143",
                            "page": 2,
                            "width": 960,
                            "height": 36,
                        }
                    ],
                },
            ],
        )
        proc = paint_library_step_figures(proc, _library())
        placed = " ".join(
            f"{fig.title} {fig.caption}"
            for group in (proc.step_figures or [])
            for fig in group
        )
        placed += " " + " ".join(f"{fig.title} {fig.caption}" for fig in (proc.figures or []))
        low = placed.lower()
        self.assertNotIn("atwood", low)
        self.assertNotIn("bevel", low)
        self.assertNotIn("sample", low)
        self.assertNotIn("ti-143", low)
        self.assertNotIn("ti143", low.replace("-", ""))
        self.assertNotIn("header", low)
        pin = next(i for i, step in enumerate(proc.bay_order) if "roll pin" in step.lower())
        self.assertTrue(proc.step_figures[pin])
        self.assertIn("PSX1", proc.step_figures[pin][0].title)

    def test_s06_drops_the_titan_bracket(self):
        offers = fb.offers_for_turn(
            _library(),
            "Manual Mode flashes then dumps back to home. Auto Level still works.",
            "show me the figure",
            "Leveling",
            "Lippert Level Up Advantage 807662",
        )
        blob = _blob(offers)
        self.assertNotIn("titan", blob)
        self.assertNotIn("489", blob)
        self.assertNotIn("ti-143", blob)
        self.assertNotIn("atwood", blob)
        self.assertNotIn("sample", blob)
        proc = compile_bay_procedure(
            concern="Manual Mode flashes then dumps back to home. Auto Level still works.",
            brand="Lippert",
            model="Level Up Advantage 807662",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert TI-489 Titan Electric Bracket",
                    "brand": "Lippert",
                    "product_line": "Titan",
                    "page": 1,
                    "excerpt": "Titan bracket TI-489. " * 12,
                    "figures": [
                        {
                            "png": TINY,
                            "label": "Fig. 1 Titan bracket",
                            "caption": "TI-489 Titan bracket",
                            "title": "Lippert TI-489 Titan Electric Bracket",
                            "page": 1,
                        }
                    ],
                }
            ],
        )
        proc = paint_library_step_figures(proc, _library())
        placed = " ".join(
            f"{fig.title} {fig.caption}"
            for group in (proc.step_figures or [])
            for fig in group
        )
        placed += " " + " ".join(f"{fig.title} {fig.caption}" for fig in (proc.figures or []))
        low = placed.lower()
        self.assertNotIn("titan", low)
        self.assertNotIn("489", low)
        for group in proc.step_figures or []:
            for fig in group:
                self.assertRegex(fig.title.lower(), r"level[\s-]*up|807662")


class TestThetfordProcedureStepsOneAndFour(unittest.TestCase):
    def test_a_crop_sits_only_on_the_step_the_manual_illustrates(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
        valve = root / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf"
        breaker = root / "34123-34122-VacBrkr-1.pdf"
        indexed = mf.index_pdf_bytes(valve.read_bytes())
        figures = [
            {"title": "Thetford Water Valve Kit 42109", "page": fig["page"], "label": fig["label"], "png": fig["png"]}
            for fig in indexed["figures"]
        ]
        text = "\n".join(page["text"] for page in indexed["pages"])
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category=CAT,
            chunks=[
                {
                    "title": "Thetford Water Valve Kit 42109",
                    "page": 1,
                    "excerpt": text,
                    "figures": figures,
                },
                {
                    "title": "Thetford Vacuum Breaker Kit 34123/34122",
                    "page": 1,
                    "excerpt": "\n".join(
                        page["text"] for page in mf.index_pdf_bytes(breaker.read_bytes())["pages"]
                    ),
                },
            ],
        )
        steps = []
        for procedure in proc.procedures:
            if "42109" in (procedure.get("title") or "") or "water valve" in (procedure.get("title") or "").lower():
                steps = procedure["steps"]
        self.assertTrue(steps)
        water = next(step for step in steps if "turn off the water" in (step.get("text") or "").lower())
        pedal = next(
            step for step in steps
            if "pull the pedal" in " ".join(step.get("actions") or [step.get("text") or ""]).lower()
        )
        thumb = next(step for step in steps if "thumb" in (step.get("text") or "").lower())
        inlet = next(step for step in steps if "inlet seal in" in (step.get("text") or "").lower())
        drive = next(step for step in steps if "drive pin" in (step.get("text") or "").lower())
        pivot = next(step for step in steps if "pivot" in (step.get("text") or "").lower())
        self.assertIsNone(water.get("figure"))
        self.assertIsNone(pedal.get("figure"))
        self.assertIn("PEDAL REMOVED", (thumb.get("figure") or {}).get("label") or "")
        self.assertFalse(mf.png_is_blank((thumb.get("figure") or {}).get("png") or b""))
        self.assertIn("Fig. 2", (inlet.get("figure") or {}).get("label") or "")
        self.assertIn("Fig. 3", (drive.get("figure") or {}).get("label") or "")
        self.assertIn("Fig. 4", (pivot.get("figure") or {}).get("label") or "")
        self.assertEqual(steps.index(water), 0)
        self.assertLess(steps.index(pedal), steps.index(thumb))
