"""v4.19.28: a Thetford toilet does not inherit a Norcold refrigerator manual."""
import unittest

from bay_procedure import (
    bay_brand_retrieval,
    compile_bay_procedure,
    procedure_plain_text,
    render_bay_procedure_pdf,
    sheet_standard_violations,
    procedure_body_text,
)
from gd_library_coach import (
    PLUMBING_TOILETS_CATEGORY,
    library_miss_shop_line,
    polish_shop_reply,
    without_reading_filler,
)

CONCERN = "leaks under the flush lever when flushing"
MODEL = "Thetford Style II 42070"

NORCOLD = [
    {
        "title": "Norcold N6xx/N8xx refrigerator manual 619394E",
        "page": page,
        "excerpt": (
            "Propane leak at the burner orifice. Check the door gasket. "
            "/G6e NO YES"
        ),
    }
    for page in (31, 43, 22, 37)
]
THETFORD = {
    "title": "Thetford Style II 42070 service manual",
    "page": 8,
    "excerpt": "Inspect the flush-lever seal and the water valve.",
}


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


class TestThetfordLibraryMiss(unittest.TestCase):
    def test_norcold_pages_are_not_the_thetford_sheet(self):
        kept, miss = bay_brand_retrieval(
            NORCOLD, "", MODEL, CONCERN
        )
        self.assertTrue(miss)
        self.assertEqual(kept, [])
        proc = compile_bay_procedure(
            concern=CONCERN,
            brand="Thetford",
            model="Style II 42070",
            category="(any)",
            chunks=NORCOLD,
        )
        text = procedure_plain_text(proc)
        low = text.lower()
        self.assertIn("no thetford document in the shop library for this unit", low)
        self.assertIn("general shop safety, not an oem procedure", low)
        self.assertIn("add the thetford oem manual", low)
        self.assertNotIn("norcold", low)
        self.assertNotIn("619394", low)
        self.assertNotIn("propane", low)
        self.assertNotIn("/g6e", low)
        self.assertNotIn("gasket", low)
        self.assertNotIn("yes:", low)
        self.assertNotIn("no:", low)
        self.assertEqual(sheet_standard_violations(procedure_body_text(proc)), [])
        pdf = _pdf_text(render_bay_procedure_pdf(proc)).lower()
        self.assertIn("no thetford document in the shop library for this unit", pdf)
        self.assertNotIn("norcold", pdf)
        self.assertNotIn("619394", pdf)
        self.assertNotIn("/g6e", pdf)
        self.assertNotIn("propane", pdf)

    def test_plumbing_category_still_refuses_the_refrigerator_manual(self):
        proc = compile_bay_procedure(
            concern=CONCERN,
            brand="",
            model=MODEL,
            category=PLUMBING_TOILETS_CATEGORY,
            chunks=NORCOLD,
        )
        low = procedure_plain_text(proc).lower()
        self.assertIn("no thetford document in the shop library for this unit", low)
        self.assertNotIn("norcold", low)

    def test_a_real_thetford_page_is_kept(self):
        kept, miss = bay_brand_retrieval([*NORCOLD, THETFORD], "", MODEL, CONCERN)
        self.assertFalse(miss)
        titles = " ".join(page["title"] for page in kept).lower()
        self.assertIn("thetford", titles)
        self.assertNotIn("norcold", titles)

    def test_reading_filler_cannot_ship_without_a_job_lock(self):
        filler = "Check the reading on this unit and write it down."
        bare = without_reading_filler(filler, [], "hello", "", "")
        self.assertNotIn("check the reading on this unit", bare.lower())
        history = []
        for latest in (
            CONCERN,
            "It only drips while flushing.",
            "What is the repair?",
        ):
            reply = polish_shop_reply(
                filler, history, latest, "", MODEL
            )
            low = reply.lower()
            self.assertIn("no thetford document in the shop library for this unit", low)
            self.assertIn("what do you observe", low)
            self.assertNotIn("check the reading on this unit", low)
            self.assertEqual(reply, library_miss_shop_line("Thetford"))
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    unittest.main()
