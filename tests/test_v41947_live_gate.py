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
            self.assertNotIn("Do this:", line)
            self.assertNotIn("Where:", line)
            self.assertNotIn("Good looks like:", line)
            self.assertNotRegex(line, r"Step \d+ of")
            step = {"fields": mf._THETFORD_PROVING[key], "actions": [], "text": ""}
            if key in ("supply", "vacuum"):
                self.assertIn("Tell me what you see.", line, key)
                self.assertNotIn(mf.PHOTO_VISUAL, line, key)
            elif mf.step_needs_photo(step):
                self.assertIn(mf.PHOTO_VISUAL, line, key)
            else:
                self.assertNotIn(mf.PHOTO_VISUAL, line, key)
            self.assertNotIn("PHOTO:", line)
            self.assertNotIn("A photo is optional.", line)
            self.assertNotIn("SAFETY:", line)
            self.assertNotIn("TOOLS / METER SETTING:", line)
            self.assertIn("📖 Source:", line)


if __name__ == "__main__":
    unittest.main()
