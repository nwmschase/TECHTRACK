"""v4.19.47 live-gate leftovers.

The Thetford bay sheet carries the numbered repair, with a crop on every
step that has one. Empty shop fields stay off the reply. HappiJac, LCD
tables, and TI-324 header strips stay off the wrong sheets. A repeated
Ground Control crop is drawn once. The FACR gate names the repair on the
fifth turn. The Girard hose sentence survives a blower line.
"""
import io
import unittest

from PIL import Image

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import (
    BayFigure,
    compile_bay_procedure,
    layout_problems,
    paint_library_step_figures,
    render_bay_procedure_pdf,
)
from gd_library_coach import avoid_duplicate_reply

HOSE = "Check for integrity and connections of the pressure switch hose."
S01 = [
    "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running, not raining.",
    "Drain is clear, pan is clean and draining, base-pan slope is fine.",
    "Filter is clean.",
    "Evaporator fan spins freely with good airflow.",
    "Freeze sensor reads 2 kΩ at 25°C.",
    "What is the repair?",
]


def _png(width=180, height=140, color=(30, 70, 120)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def _placed(proc) -> str:
    parts = [
        f"{fig.title} {fig.caption}"
        for group in (proc.step_figures or [])
        for fig in group
    ]
    parts.extend(f"{fig.title} {fig.caption}" for fig in (proc.figures or []))
    return " ".join(parts).lower()


def _walk(turns, category, model, draft="Read the freeze sensor."):
    history = []
    replies = []
    for latest in turns:
        reply = avoid_duplicate_reply(draft, history, latest, category, model)
        replies.append(reply or "")
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": reply})
    return replies


class TestThetfordBayRepairProcedure(unittest.TestCase):
    def test_the_numbered_repair_keeps_a_crop_on_every_figured_step(self):
        proc = compile_bay_procedure(
            concern="Thetford 42070 leaks under the flush lever",
            brand="Thetford",
            model="42070",
            category="Plumbing / Toilets",
            chunks=[
                {
                    "title": "Thetford Style II OM Permanent RV Toilet 42088",
                    "page": 3,
                    "excerpt": "Check the water supply line connection.",
                }
            ],
        )
        titles = [procedure.get("title") or "" for procedure in proc.procedures]
        self.assertTrue(any("42109" in title for title in titles))
        self.assertTrue(any("3412" in title for title in titles))
        valve = next(procedure for procedure in proc.procedures if "42109" in (procedure.get("title") or ""))
        breaker = next(procedure for procedure in proc.procedures if "3412" in (procedure.get("title") or ""))
        self.assertEqual(len(valve["steps"]), 14)
        self.assertEqual(len(breaker["steps"]), 13)
        water = valve["steps"][0]
        pedal = valve["steps"][3]
        thumb = next(step for step in valve["steps"] if "thumb" in (step.get("text") or "").lower())
        inlet = next(step for step in valve["steps"] if "inlet seal in" in (step.get("text") or "").lower())
        drive = next(step for step in valve["steps"] if "drive pin" in (step.get("text") or "").lower())
        pivot = next(step for step in valve["steps"] if "pivot" in (step.get("text") or "").lower())
        self.assertIn("turn off the water", (water.get("text") or "").lower())
        self.assertIsNone(water.get("figure"))
        self.assertIn("pull the pedal", (pedal.get("text") or "").lower())
        self.assertIsNone(pedal.get("figure"))
        self.assertIn("PEDAL REMOVED", (thumb.get("figure") or {}).get("label") or "")
        self.assertIn("Fig. 2", (inlet.get("figure") or {}).get("label") or "")
        self.assertIn("Fig. 3", (drive.get("figure") or {}).get("label") or "")
        self.assertIn("Fig. 4", (pivot.get("figure") or {}).get("label") or "")
        self.assertFalse(mf.png_is_blank((thumb.get("figure") or {}).get("png") or b""))
        figured = 0
        for procedure in proc.procedures:
            for step in procedure["steps"]:
                figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
                png = (figure or {}).get("png") or b""
                if png and not mf.png_is_blank(png):
                    figured += 1
                    self.assertTrue(figure.get("label"))
                else:
                    self.assertFalse(figure)
        self.assertGreaterEqual(figured, 5)
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        drawn = [mark for mark in trace if mark.kind == "image"]
        self.assertEqual(len(drawn), figured)
        text = _pdf_text(pdf).lower()
        self.assertIn("repair procedure", text)
        self.assertIn("removal", text)
        self.assertIn("turn off the water", text)
        self.assertIn("pull the pedal", text)
        self.assertNotIn("disconnect rv water supply", text)

    def test_a_library_miss_does_not_paste_the_kit(self):
        proc = compile_bay_procedure(
            concern="leaks under the flush lever when flushing",
            brand="Thetford",
            model="Style II 42070",
            category="(any)",
            chunks=[
                {
                    "title": "Norcold N6xx/N8xx refrigerator manual 619394E",
                    "page": 31,
                    "excerpt": "Propane leak at the burner orifice.",
                }
            ],
        )
        self.assertEqual(proc.procedures, [])
        self.assertNotIn("42109", " ".join(proc.bay_order))


class TestFillerSentenceOnce(unittest.TestCase):
    def test_the_filler_sentence_is_said_at_most_once(self):
        repeated = (
            "Not stated in this sheet. Check the valve. "
            "Not stated in this sheet. Not stated in this sheet."
        )
        cleaned = mf.hide_internal_marker(repeated)
        self.assertEqual(cleaned.lower().count("not stated in this sheet"), 1)
        self.assertIn("Check the valve", cleaned)
        markers = mf.hide_internal_marker("UNCONFIRMED. Do the check. UNCONFIRMED.")
        self.assertEqual(markers.lower().count("not stated in this sheet"), 1)
        self.assertIn("Do the check", markers)


class TestEmptyFieldsStayOffTheReply(unittest.TestCase):
    def test_proving_lines_omit_the_filler_sentence(self):
        for key in ("supply", "vacuum", "valve", "flange"):
            line = mf.thetford_proving_line(key)
            self.assertNotIn("Not stated in this sheet", line)
            self.assertNotIn("UNCONFIRMED", line)
            self.assertIn("HOW:", line)
            self.assertIn("PHOTO:", line)
            self.assertNotIn("SAFETY:", line)
            self.assertNotIn("TOOLS / METER SETTING:", line)
            self.assertIn("📖 Source:", line)

    def test_the_gd_walk_omits_empty_fields(self):
        history = []
        latest = "toilet leaks under the flush lever when flushing"
        for _ in range(4):
            reply = avoid_duplicate_reply(
                "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
                history,
                latest,
                "Plumbing / Toilets",
                "Style II 42070",
            )
            self.assertNotIn("Not stated in this sheet", reply)
            self.assertNotIn("UNCONFIRMED", reply)
            self.assertIn("HOW:", reply)
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})
            latest = "Not checked yet"


class TestS14HappiJacStaysOff(unittest.TestCase):
    def test_an_aftermarket_happijac_figure_is_not_the_psx1_sheet(self):
        row = {
            "title": "HappiJac aftermarket stabilizer",
            "brand": "HappiJac",
            "product_line": "HappiJac",
            "label": "Fig. 2 aftermarket jack",
            "caption": "HappiJac aftermarket electric jack",
            "png": _png(),
        }
        self.assertTrue(
            fb.off_brand_figure(
                row,
                "Leveling",
                "Lippert PSX1",
                "Front stabilizer jack. Roll pin broken.",
                "",
            )
        )
        self.assertFalse(
            fb.figure_on_topic(
                row,
                "Replace the broken roll pin.",
                "Front stabilizer roll pin broken.",
                "Lippert PSX1",
            )
        )
        proc = compile_bay_procedure(
            concern="Front stabilizer jack. Power works. Manual crank will not operate. Roll pin broken.",
            brand="Lippert",
            model="PSX1",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert PSX1 stabilizer jack",
                    "brand": "Lippert",
                    "product_line": "PSX1",
                    "page": 1,
                    "excerpt": "Replace the roll pin on the manual crank.",
                },
                {
                    "title": "HappiJac aftermarket stabilizer",
                    "brand": "HappiJac",
                    "product_line": "HappiJac",
                    "page": 2,
                    "excerpt": "HappiJac aftermarket electric jack installation. " * 8,
                    "figures": [
                        {
                            "png": _png(color=(180, 40, 40)),
                            "label": "Fig. 2 aftermarket jack",
                            "caption": "HappiJac aftermarket electric jack",
                            "title": "HappiJac aftermarket stabilizer",
                            "page": 2,
                        }
                    ],
                }
            ],
        )
        library = [
            {
                "id": 8,
                "document_id": 8,
                "kind": "figure",
                "title": "Lippert PSX1 stabilizer jack",
                "brand": "Lippert",
                "product_line": "PSX1",
                "category_name": "Leveling",
                "models": "PSX1",
                "page": 1,
                "label": "Fig. 2 roll pin",
                "caption": "PSX1 manual crank roll pin",
                "png": _png(color=(20, 90, 40)),
            },
            {
                "id": 14,
                "document_id": 14,
                "kind": "figure",
                "title": "HappiJac aftermarket stabilizer",
                "brand": "HappiJac",
                "product_line": "HappiJac",
                "category_name": "Leveling",
                "page": 2,
                "label": "Fig. 2 aftermarket jack",
                "caption": "HappiJac aftermarket electric jack",
                "png": _png(color=(180, 40, 40)),
            },
        ]
        proc = paint_library_step_figures(proc, library)
        placed = _placed(proc)
        self.assertNotIn("happijac", placed)
        self.assertNotIn("happi jac", placed)
        self.assertNotIn("aftermarket", placed)
        pin = next(i for i, step in enumerate(proc.bay_order) if "roll pin" in step.lower())
        self.assertTrue(proc.step_figures[pin])
        self.assertIn("PSX1", proc.step_figures[pin][0].title)
        text = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        self.assertNotIn("happijac", text)
        self.assertNotIn("aftermarket", text)


class TestS06TopicAndPart(unittest.TestCase):
    def test_lcd_tables_and_header_strips_are_not_figures(self):
        table = {
            "title": "Lippert Level Up Advantage LCD specification table",
            "label": "Fig. 2 LCD spec table",
            "caption": "LCD specification table",
            "product_line": "Level Up",
        }
        again = {
            "title": "Lippert Level Up data table",
            "label": "Fig. 4",
            "caption": "specification table",
            "product_line": "Level Up",
        }
        header = {
            "title": "Lippert TI-324",
            "label": "header strip",
            "caption": "TI-324 header strip",
            "product_line": "Level Up",
            "width": 960,
            "height": 36,
        }
        slide = {
            "title": "Lippert Level Up slide-out motor",
            "label": "Fig. 3 slide motor",
            "caption": "bedroom slide motor",
            "product_line": "Level Up",
        }
        for row in (table, again, header):
            self.assertTrue(fb.junk_figure(row), row["title"])
            self.assertFalse(
                fb.figure_on_topic(
                    row,
                    "Manual Mode flashes then dumps back to home.",
                    "Auto Level still works.",
                    "Level Up Advantage 807662",
                )
            )
        self.assertFalse(
            fb.figure_on_topic(
                slide,
                "Manual Mode flashes then dumps back to home. Auto Level still works.",
                "",
                "Level Up Advantage 807662",
            )
        )
        png = _png()
        proc = compile_bay_procedure(
            concern="Manual Mode flashes then dumps back to home. Auto Level still works.",
            brand="Lippert",
            model="Level Up Advantage 807662",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert Level Up Advantage LCD specification table",
                    "brand": "Lippert",
                    "product_line": "Level Up",
                    "page": 4,
                    "excerpt": "LCD specification table for the display. " * 8,
                    "figures": [
                        {**table, "png": png, "page": 4},
                        {**again, "png": png, "page": 5},
                    ],
                },
                {
                    "title": "Lippert TI-324",
                    "brand": "Lippert",
                    "product_line": "Level Up",
                    "page": 2,
                    "excerpt": "TI-324 header strip. " * 12,
                    "figures": [{**header, "png": _png(960, 36), "page": 2}],
                },
                {
                    "title": "Lippert Level Up slide-out motor",
                    "brand": "Lippert",
                    "product_line": "Level Up",
                    "page": 6,
                    "excerpt": "Bedroom slide motor. " * 8,
                    "figures": [{**slide, "png": _png(color=(10, 10, 10)), "page": 6}],
                },
            ],
        )
        placed = _placed(proc)
        for banned in ("lcd", "table", "ti-324", "ti324", "header", "slide"):
            self.assertNotIn(banned, placed, banned)
        text = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        self.assertNotIn("lcd", text)
        self.assertNotIn("ti-324", text)
        self.assertNotIn("header strip", text)


class TestS10FigureDedupe(unittest.TestCase):
    def test_one_ground_control_crop_is_drawn_once(self):
        png = _png(color=(40, 80, 160))
        proc = compile_bay_procedure(
            concern="Auto-level lifts the driver-side tires though the coach is nearly level.",
            brand="Lippert",
            model="Ground Control 343633",
            category="Leveling",
            chunks=[
                {
                    "title": "Lippert Ground Control 343633",
                    "page": 4,
                    "excerpt": "Zero-point calibration is the repair.",
                }
            ],
        )
        self.assertGreaterEqual(len(proc.bay_order), 1)
        marker = "GC-DEDUPE-MARKER"
        fig = BayFigure(
            title="Lippert Ground Control 343633",
            page=4,
            caption=marker,
            image_png=png,
        )
        proc.step_figures = [[fig] for _ in proc.bay_order]
        proc.figures = [fig, fig, fig]
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        drawn = [mark for mark in trace if mark.kind == "image"]
        self.assertEqual(len(drawn), 1)
        self.assertEqual(_pdf_text(pdf).count(marker), 1)
        self.assertIn("343633", _pdf_text(pdf))


class TestS01RepairByTurnFive(unittest.TestCase):
    def test_the_gate_replay_authorizes_on_the_fifth_turn(self):
        replies = _walk(S01, "Air Conditioning", "FACR08HESA2-PS")
        for reply in replies[:4]:
            low = reply.lower()
            self.assertNotIn("replace the rooftop assembly", low)
            self.assertNotIn("authorize rooftop assembly", low)
            self.assertNotIn("sail switch", low)
            self.assertNotIn("stay on the facr", low)
            self.assertNotIn("next check on the", low)
        fifth = replies[4].lower()
        self.assertIn("authorize rooftop assembly", fifth)
        self.assertIn("replace the rooftop assembly", fifth)
        self.assertIn("ccd-0007990", fifth)
        self.assertNotIn("read the freeze sensor", fifth)
        sixth = replies[5].lower()
        self.assertIn("authorize rooftop assembly", sixth)
        self.assertIn("replace the rooftop assembly", sixth)

    def test_four_turns_without_pressures_do_not_authorize(self):
        replies = _walk(
            [
                "Furrion FACR08 rooftop AC. Water leaking inside.",
                "Drain is clear. Pan is clean and draining. Base-pan slope is fine.",
                "Filter is clean. Fan spins freely.",
                "Freeze sensor 2k at 25C.",
            ],
            "Air Conditioning",
            "FACR08HESA2-PS",
        )
        last = replies[-1].lower()
        self.assertNotIn("replace the rooftop assembly", last)
        self.assertNotIn("authorize rooftop assembly", last)


class TestS20BleedReply(unittest.TestCase):
    def test_the_bleed_reply_is_a_yes_no_without_the_cartridge_clause(self):
        from gd_library_coach import LEADJACK_VERIFY_BODY, LEADJACK_VERIFY_WAIT

        for body in (LEADJACK_VERIFY_BODY, LEADJACK_VERIFY_WAIT):
            self.assertIn("Yes, go to the next step.", body)
            self.assertIn("No, do this step again.", body)
            self.assertNotIn("Part 177094 is the cartridge valve", body)
            self.assertNotIn("177094", body)


class TestS13HoseQuote(unittest.TestCase):
    def test_the_blower_line_keeps_the_hose_sentence(self):
        proc = compile_bay_procedure(
            "Girard GSWH-2 gives E8 error code.",
            "Girard",
            "GSWH-2",
            "Water Heaters",
            chunks=[
                {
                    "title": "Girard Tankless Water Heater GSWH-2 Troubleshooting and Service Manual CCD-0009390",
                    "page": 23,
                    "excerpt": (
                        "Check for integrity and connections of the pressure switch hose at the blower."
                    ),
                }
            ],
        )
        hay = " ".join(src.get("excerpt") or "" for src in proc.sources)
        self.assertIn(HOSE, hay)
        text = _pdf_text(render_bay_procedure_pdf(proc))
        self.assertIn(HOSE, text)


if __name__ == "__main__":
    unittest.main()
