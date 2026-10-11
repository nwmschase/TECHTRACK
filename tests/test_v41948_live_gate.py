"""v4.19.48 live-gate leftovers.

The Thetford sheet keeps each figure with its caption, and it prints only the
confirmed kit. The FACR gate uses the short live turns. The Girard hose sentence
stays on page 23. A Fig. callout is not cut off the source quote.
"""
import unittest

from bay_procedure import (
    MARGIN,
    _best_verbatim_quote,
    _split_sentences,
    clean_source_excerpt,
    compile_bay_procedure,
    layout_problems,
    render_bay_procedure_pdf,
)
from gd_library_coach import avoid_duplicate_reply, ensure_facr_early_pressure_ask
from tests.test_v41947_live_gate import _pdf_text

HOSE = "Check for integrity and connections of the pressure switch hose."


def _walk(turns, draft):
    history = []
    replies = []
    for latest in turns:
        reply = avoid_duplicate_reply(
            draft, history, latest, "Air Conditioning", "FACR08HESA2-PS"
        )
        reply = ensure_facr_early_pressure_ask(
            reply, history, latest, "Air Conditioning", "FACR08HESA2-PS"
        )
        replies.append(reply or "")
        history.append({"role": "user", "content": latest})
        history.append({"role": "assistant", "content": reply})
    return replies


class TestThetfordConfirmedRepair(unittest.TestCase):
    def _sheet(self, concern, history=None):
        return compile_bay_procedure(
            concern=concern,
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
            history=history,
        )

    def test_a_valve_finding_omits_the_breaker_repair(self):
        proc = self._sheet(
            "Thetford 42070 leaks under the flush lever",
            history=[
                {"role": "user", "content": "The water valve weeps at the pedal."},
            ],
        )
        titles = " ".join(procedure.get("title") or "" for procedure in proc.procedures)
        self.assertIn("42109", titles)
        self.assertNotIn("3412", titles)
        self.assertEqual(len(proc.procedures[0]["steps"]), 14)
        pngs = []
        for step in proc.procedures[0]["steps"]:
            png = ((step.get("figure") or {}) if isinstance(step.get("figure"), dict) else {}).get("png") or b""
            if not png:
                continue
            self.assertNotIn(png, pngs)
            pngs.append(png)
        self.assertGreaterEqual(len(pngs), 4)

    def test_a_breaker_finding_omits_the_valve_repair(self):
        proc = self._sheet("The vacuum breaker leaks while flushing. Kit 34123.")
        titles = " ".join(procedure.get("title") or "" for procedure in proc.procedures)
        self.assertIn("3412", titles)
        self.assertNotIn("42109", titles)
        self.assertEqual(len(proc.procedures[0]["steps"]), 13)

    def test_figure_and_caption_stay_together_above_the_floor(self):
        proc = self._sheet("Thetford 42070 leaks under the flush lever")
        trace = []
        pdf = render_bay_procedure_pdf(proc, trace=trace)
        self.assertEqual(layout_problems(trace), [])
        images = [mark for mark in trace if mark.kind == "image"]
        captions = [mark for mark in trace if mark.role == "caption"]
        self.assertGreaterEqual(len(images), 4)
        self.assertGreaterEqual(len(captions), len(images))
        floor = MARGIN + 36
        for image in images:
            self.assertGreaterEqual(image.y0, floor - 1)
            self.assertLessEqual(image.y1, 792)
            lines = [
                cap for cap in captions
                if cap.page == image.page
                and cap.x0 >= image.x0 - 2
                and cap.y1 <= image.y0 + 2
                and cap.y0 >= image.y0 - 36
            ]
            self.assertTrue(lines, image)
            self.assertGreaterEqual(min(cap.y0 for cap in lines), floor - 1)
            words = " ".join(cap.text for cap in lines)
            self.assertRegex(words, r"Fig\.\s*\d+")
            self.assertNotRegex(words, r"(?:^|\s)/\s*Fig")
        joined = " ".join(cap.text for cap in captions)
        self.assertIn("Fig. 2", joined)
        self.assertIn("INSERTING", joined)
        self.assertNotIn("/ Fig.", joined)
        text = _pdf_text(pdf)
        self.assertNotIn("Not stated in this sheet", text)
        self.assertNotIn("That limit is", text)
        self.assertNotIn("Slide clamp A", text)
        self.assertNotIn("Throw the old vacuum breaker", text)
        self.assertEqual(text.lower().count("before you start"), 1)
        self.assertIn("42109", text)


class TestS01ShortGate(unittest.TestCase):
    def test_freeze_sensor_draft_still_closes_on_the_fifth_turn(self):
        replies = _walk(
            ["drain", "pan", "fan", "pressures", "freeze sensor"],
            "Read the freeze sensor.",
        )
        self.assertLess(
            sum("pressure" in reply.lower() for reply in replies[1:3]),
            2,
            replies[1:3],
        )
        fifth = replies[4].lower()
        self.assertIn("authorize rooftop assembly", fifth)
        self.assertIn("ccd-0007990", fifth)
        self.assertNotIn("read the freeze sensor", fifth)
        self.assertNotIn("authorize rooftop assembly", replies[3].lower())


class TestS13HoseWithoutTheChunk(unittest.TestCase):
    def test_page_23_is_quoted_when_the_chunk_omits_the_hose(self):
        proc = compile_bay_procedure(
            "Girard GSWH-2 gives E8 error code.",
            "Girard",
            "GSWH-2",
            "Water Heaters",
            chunks=[
                {
                    "title": "Girard Tankless Water Heater GSWH-2 Troubleshooting and Service Manual CCD-0009390",
                    "page": 12,
                    "excerpt": "The blower runs when the control calls for heat.",
                }
            ],
        )
        hay = " ".join(
            f"{src.get('title') or ''} {src.get('excerpt') or ''} {src.get('page') or ''}"
            for src in proc.sources
        )
        self.assertIn(HOSE, hay)
        self.assertIn("23", hay)
        text = _pdf_text(render_bay_procedure_pdf(proc))
        self.assertIn(HOSE, text)
        self.assertIn("page 23", text.lower())


class TestS04FigureCallout(unittest.TestCase):
    def test_fig_12_stays_in_the_source_quote(self):
        raw = "Open flag terminals C (blue) and T (black) with no jumper as shown in Fig . 12."
        parts = _split_sentences(raw)
        self.assertTrue(any("Fig. 12" in part for part in parts))
        self.assertFalse(any(part.rstrip().endswith("Fig.") or part.rstrip().endswith("Fig .") for part in parts))
        quote = _best_verbatim_quote(raw, "dial_off", "thermostat compressor dial jumper")
        self.assertIn("Fig. 12", quote)
        self.assertNotRegex(quote, r"Fig\s*\.?\s*$")
        proc = compile_bay_procedure(
            "Temperature dial is OFF and the compressor is still running.",
            "Furrion",
            "FCR10DCGTA-BL",
            "Refrigerators",
            chunks=[
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 31,
                    "excerpt": raw,
                }
            ],
        )
        excerpts = " ".join(src.get("excerpt") or "" for src in proc.sources)
        self.assertIn("Fig. 12", excerpts)
        self.assertNotRegex(excerpts, r"Fig\s*\.\s*(?:$|\n)")
        text = _pdf_text(render_bay_procedure_pdf(proc))
        self.assertIn("Fig. 12", text)
        self.assertNotIn("Fig .", text)

    def test_a_quote_cut_at_fig_is_not_published(self):
        cut = "Open flag terminals C (blue) and T (black) with no jumper as shown in Fig ."
        cleaned = clean_source_excerpt(cut)
        self.assertIn("flag terminals", cleaned.lower())
        self.assertNotIn("Fig .", cleaned)
        self.assertNotRegex(cleaned, r"Fig\s*\.?\s*$")
        quote = _best_verbatim_quote(cut, "dial_off", "thermostat compressor dial jumper")
        self.assertNotIn("Fig .", quote)
        self.assertNotRegex(quote, r"Fig\s*\.?\s*$")
        longer = (
            "Leave the dial fully OFF. "
            "Open flag terminals C (blue) and T (black) with no jumper as shown in Fig . 12."
        )
        kept = _best_verbatim_quote(longer, "dial_off", "thermostat compressor dial jumper")
        self.assertIn("Fig. 12", kept)
        self.assertNotIn("Fig .", kept)
        padded = (
            "Open flag terminals C (blue) and T (black) with no jumper "
            + ("and the compressor is still running past the detent " * 4)
            + "as shown in Fig . 12."
        )
        clipped = clean_source_excerpt(padded)
        self.assertIn("Fig. 12", clipped)
        self.assertNotRegex(clipped, r"Fig\s*\.?\s*$")


if __name__ == "__main__":
    unittest.main()
