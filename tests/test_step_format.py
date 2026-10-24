"""Every Bay PDF and every GD step uses the same heading and labels.

The canned photo script stays out of the PDF. Safety is printed once per
section, and again only when that step's safety text changes.
"""
import unittest

import manual_figures as mf

_PHOTO_BLOCK = (
    "a photo is optional",
    "you can type what you see",
    "yes, go to the next step",
    "no, do this step again",
    "take a photo of this step",
    "photo:",
)


def _emitted_safety(steps) -> list[str]:
    return [
        mf.step_safety_text(step)
        for index, step in enumerate(steps, 1)
        if mf.show_safety_for(steps, index)
    ]


class TestSharedStepStructure(unittest.TestCase):


    def test_gd_uses_the_same_markdown_structure(self):
        valve = mf.thetford_kit_layout("valve")["steps"]
        shown = mf.format_one_step(valve[3], 4, len(valve), show_safety=mf.show_safety_for(valve, 4))
        self.assertIn("Here is the repair procedure.", shown)
        self.assertRegex(shown, r"\*\*Step 4: .+\*\*")
        self.assertIn("\n\nDo this:\n1. ", shown)
        located = next(
            step for step in valve
            if any(line.startswith("Where:") for line in mf.step_body_lines(step))
        )
        self.assertIn("Where:", mf.format_one_step(located, 1, len(valve)))
        self.assertNotIn("Yes, go to the next step.", shown)
        self.assertNotIn("A photo is optional.", shown)
        self.assertNotIn("PHOTO:", shown)
        off = mf.facr_rr_layout()["steps"][0]
        quiet = mf.format_one_step(off, 1, 20, show_safety=True)
        self.assertIn("**Step 1: Turn the 115VAC breaker off**", quiet)
        self.assertIn("Safety:", quiet)
        self.assertNotIn(mf.PHOTO_VISUAL, quiet)
        look = next(
            step
            for step in mf.facr_proving_layout()["steps"]
            if step["text"].lower().startswith("look for drip")
        )
        visual = mf.format_one_step(look, 4, 32)
        self.assertEqual(visual.count(mf.PHOTO_VISUAL), 1)
        self.assertIn("\n\nDo this:\n1. Look for drip on the coil.", visual)
        first = valve[0]
        shown_first = mf.format_one_step(first, 1, len(valve), show_safety=True)
        self.assertIn("Good looks like:", shown_first)
        # rev5 (Leader rev4 item 1): 'Water still comes out' only negates 'No water comes out', so it is left off.
        self.assertNotIn("Bad looks like:", shown_first)
        self.assertEqual(shown_first.count("\n1. "), 1)
        self.assertNotIn("\n2. ", shown_first)
        vacuum = mf.thetford_proving_line("vacuum")
        import library_figure_backfill as fb
        offers = fb.offers_for_turn([], vacuum, "show me", "Plumbing / Toilets", "Thetford 42070")
        self.assertTrue(offers and offers[0].get("png"))


if __name__ == "__main__":
    unittest.main()
