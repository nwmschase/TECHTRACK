import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
"""Leader page review 10/14 12:21 (rev2): garbled text, non-action or repeated
headings, and split If/then lines are caught on every sheet."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import sheet_language_check as sl  # noqa: E402
from bay_procedure import compile_bay_procedure, render_bay_procedure_pdf  # noqa: E402

CASES = {
    "S01": ("Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running, not raining; frost/ice on evaporator.", "Furrion", "FACR08HESA2-PS", "Air Conditioning"),
    "S11": ("Intermittent E3; sometimes normal.", "Furrion", "FACT12SA2-PS", "Air Conditioning"),
}

# The 28ff646 page text Leader flagged, as the checker reads it.
OLD_S01_PRIMARY = "Furrion rooftop assembly and condensate path. Chill layout book for the pan and drain."
OLD_S01_END = "Replace the rooftop unit after that assembly prove."
OLD_S11 = [
    "Step 1: On a FACT12 E3", "Do this:", "1. On a FACT12 E3:",
    "2. Measure 12 V at the communication connector and check the data line.",
    "Step 2: Confirm the data connector is seated", "Do this:", "1. Confirm the data connector is seated.",
    "2. If a pin is pushed back or the connector is loose:", "3. Repair it and retest the code.",
]


class TestCheckerCatchesTheOldPages(unittest.TestCase):
    def test_old_s01_garble_is_caught(self):
        got = sl.check_lines([], primary=OLD_S01_PRIMARY, nodes=[OLD_S01_END])
        self.assertTrue(any("Chill layout book" in p for p in got), got)
        self.assertTrue(any("after that assembly prove" in p for p in got), got)

    def test_old_s11_heading_and_split_are_caught(self):
        got = sl.check_lines(OLD_S11)
        self.assertIn("SL-2 heading is not an action: Step 1: On a FACT12 E3", got)
        self.assertIn("SL-2 heading repeats line 1: Step 2: Confirm the data connector is seated", got)
        self.assertIn("SL-3 split If/then: 2. If a pin is pushed back or the connector is loose:", got)


class TestSheetsPassTheLanguageChecks(unittest.TestCase):
    def _pdf(self, name, tmp):
        concern, brand, model, category = CASES[name]
        proc = compile_bay_procedure(concern=concern, brand=brand, model=model, category=category)
        path = Path(tmp) / f"{name}.pdf"
        path.write_bytes(render_bay_procedure_pdf(proc))
        return proc, str(path)

    def test_s01_and_s11_sheets_are_clean(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            for name in CASES:
                proc, path = self._pdf(name, tmp)
                self.assertEqual(sl.check_pdf(path), [], name)
                nodes = [n.text.replace("\n", " ") for n in (proc.flowchart.nodes if proc.flowchart else [])]
                self.assertEqual(sl.check_lines([], primary=proc.primary_cite, nodes=nodes), [], name)

    def test_snapshot_sheets_are_clean(self):
        import test_bay_clean_snapshots as snap
        for name, concern, brand, model, category, chunks in snap.CASES:
            proc = compile_bay_procedure(concern=concern, brand=brand, model=model, category=category,
                                         chunks=chunks or [], created=snap.CREATED)
            text = snap._pdf_text(render_bay_procedure_pdf(proc))
            lines = [l for l in text.splitlines() if l.strip()]
            self.assertEqual(sl.check_lines(lines), [], name)

    def test_s11_steps_carry_the_profile_labels(self):
        import tempfile, subprocess
        with tempfile.TemporaryDirectory() as tmp:
            _proc, path = self._pdf("S11", tmp)
            text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
        for label in ("Where:", "Tools:", "Good looks like:", "Bad looks like:", "Next:"):
            self.assertIn(label, text)


if __name__ == "__main__":
    unittest.main()
