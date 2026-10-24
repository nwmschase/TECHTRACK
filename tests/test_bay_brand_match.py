"""Bay PDF cites the named brand. Coleman 2111-0001 is not a Furrion Chill manual."""
import unittest

from bay_procedure import (
    COLEMAN_BAY_PRIMARY_CITE,
    bay_brand_retrieval,
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
    rewrite_bay_search_symptom,
)
from gd_library_coach import (
    AC_SEARCH_BOOST,
    asked_brands_for_lookup,
    is_coleman_2111_context,
)

CONCERN = (
    "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead / no response."
)

WALL = {
    "title": "Coleman-Mach 12VDC wall-thermostat rooftop service manual",
    "page": 2,
    "excerpt": (
        "Fig. 4 9-pin wall thermostat. 12 VDC present and 115 VAC missing at the "
        "9-pin means the printed circuit board."
    ),
}
PINS = {
    "title": "Coleman-Mach 1976-536 and 1976-603",
    "page": 1,
    "excerpt": "Pin 5 BLK is Fan High. Pin 9 WHT is fan common.",
}
PEACE = {
    "title": "SkillAbove Peacemaker",
    "page": 3,
    "excerpt": (
        "Peacemaker bypass of the thermostat and control box. Compressor runs. Record amperage."
    ),
}
MECH = {
    "title": "Coleman-Mach mechanical-controls service manual 1976-695",
    "page": 6,
    "excerpt": (
        "Fig. 8 capacitor. The run capacitor is good and the motor will not start: replace the motor."
    ),
}
FURRION_CHILL = {
    "title": "Furrion FACT12SA2-PS 8K Electronic Control IM CCD-0008666",
    "page": 1,
    "excerpt": "Fig. 1 Furrion Chill rooftop air conditioner electronic control.",
}
FURRION_PAGES = [
    {**FURRION_CHILL, "page": page}
    for page in (1, 6, 13, 18, 19, 20)
]


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


class TestColemanBayBrandLock(unittest.TestCase):
    def test_search_boost_does_not_make_furrion_the_asked_brand(self):
        self.assertTrue(
            is_coleman_2111_context("Air Conditioning", "Coleman-Mach 2111-0001", CONCERN)
        )
        boosted = f"{CONCERN} {AC_SEARCH_BOOST}"
        self.assertEqual(
            asked_brands_for_lookup("Air Conditioning", "Coleman-Mach 2111-0001", boosted),
            {"coleman"},
        )
        q = rewrite_bay_search_symptom(
            "Air Conditioning", "Coleman-Mach 2111-0001", CONCERN
        ).lower()
        self.assertIn("1976-536", q)
        self.assertIn("peacemaker", q)
        self.assertIn("1976-695", q)
        self.assertNotIn("fact12sa2", q)
        self.assertNotIn("ccd-0008666", q)

    def test_mixed_library_keeps_coleman_and_drops_furrion(self):
        kept, miss = bay_brand_retrieval(
            [FURRION_CHILL, WALL, PINS, PEACE, MECH],
            "Air Conditioning",
            "Coleman-Mach 2111-0001",
            CONCERN,
        )
        self.assertFalse(miss)
        titles = " ".join(ch["title"] for ch in kept).lower()
        self.assertIn("coleman", titles)
        self.assertIn("peacemaker", titles)
        self.assertNotIn("furrion", titles)
        self.assertNotIn("ccd-0008666", titles)


    def test_furrion_only_library_does_not_become_the_coleman_primary(self):
        proc = compile_bay_procedure(
            concern=CONCERN,
            brand="Coleman-Mach",
            model="2111-0001",
            category="Air Conditioning",
            chunks=FURRION_PAGES,
        )
        blob = procedure_plain_text(proc).lower()
        self.assertIn("coleman-mach", proc.primary_cite.lower())
        self.assertIn("1976-536", blob)
        self.assertIn("peacemaker", blob)
        self.assertIn("1976-695", blob)
        self.assertNotIn("furrion", blob)
        self.assertNotIn("ccd-0008666", blob)
        self.assertNotIn("fact12", blob)
        for fig in proc.figures:
            self.assertNotIn("furrion", f"{fig.title} {fig.caption}".lower())


class TestBrandMismatchGuard(unittest.TestCase):
    def test_known_brand_without_its_manual_does_not_cite_the_other_brand(self):
        proc = compile_bay_procedure(
            concern="Rooftop air conditioner will not cool.",
            brand="Dometic",
            model="B57915",
            category="Air Conditioning",
            chunks=FURRION_PAGES,
        )
        low = procedure_plain_text(proc).lower()
        self.assertIn("dometic: general shop safety sheet", proc.primary_cite.lower())
        self.assertIn("general shop safety, not an oem procedure", low)
        self.assertNotIn("add the dometic oem manual", low)
        self.assertNotIn("furrion", proc.primary_cite.lower())
        self.assertNotIn("ccd-0008666", low)
        self.assertNotIn("fact12", low)
        self.assertNotIn("furrion", low)
        self.assertNotIn("yes:", low)
        self.assertNotIn("no:", low)
        for src in proc.sources:
            self.assertNotIn("furrion", (src.get("title") or "").lower())
        for fig in proc.figures:
            self.assertNotIn("furrion", f"{fig.title} {fig.caption}".lower())

    def test_same_brand_manual_is_still_the_primary(self):
        proc = compile_bay_procedure(
            concern="Rooftop air conditioner will not cool.",
            brand="Furrion",
            model="FACT12SA2",
            category="Air Conditioning",
            chunks=[FURRION_CHILL, WALL],
        )
        self.assertIn("furrion", proc.primary_cite.lower())
        self.assertIn("ccd-0008666", proc.primary_cite.lower())
        titles = " ".join(s.get("title") or "" for s in proc.sources).lower()
        self.assertIn("furrion", titles)
        self.assertNotIn("coleman", titles)

    def test_locked_facr_sheet_stays_on_7990_when_a_coleman_page_is_also_retrieved(self):
        proc = compile_bay_procedure(
            concern="FACR08 freeze up interior leak condensate",
            brand="Furrion",
            model="FACR08HESA2-PS",
            category="Air Conditioning",
            chunks=[WALL, PEACE],
        )
        low = procedure_plain_text(proc).lower()
        self.assertIn("ccd-0007990", low)
        self.assertIn("rooftop", proc.primary_cite.lower())
        titles = " ".join(s.get("title") or "" for s in proc.sources).lower()
        self.assertIn("ccd-0007990", titles)
        self.assertNotIn("coleman", titles)
        self.assertNotIn("peacemaker", titles)


if __name__ == "__main__":
    unittest.main()
