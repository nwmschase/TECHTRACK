"""Air Conditioning library retrieval: prefer Furrion/Dometic rooftop AC over Unity."""
import unittest

from gd_library_coach import (
    AC_SEARCH_BOOST,
    FACR_FREEZE_SEARCH_BOOST,
    is_air_conditioning_context,
    is_facr_rooftop_freeze_context,
)

CHASE_MODEL = "Furrion FACT12SA2 rooftop air conditioner"
CHASE_CONCERN = "No cool. Interior fan runs. Looking for the FACT / rooftop AC procedure."
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN}"
FACR_MODEL = "Furrion FACR08HESA2-PS"
FACR_CONCERN = "rooftop freeze / condensate leak from the base pan, ice and frost on the coil"
FACR_QUERY = f"{FACR_MODEL} {FACR_CONCERN}"

UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
    "page": 4,
}
FACT = {
    "title": "Furrion FACT12SA2 Rooftop Air Conditioner SM",
    "category": "Air Conditioning",
    "excerpt": (
        "Furrion FACT rooftop air conditioner no cool diagnostics. "
        "ADB air distribution box. Compressor and indoor fan."
    ),
    "page": 8,
}
BRISK = {
    "title": "Dometic Brisk B57915 Rooftop AC SM",
    "category": "Air Conditioning",
    "excerpt": "Dometic Brisk II B57915 rooftop AC. E2 E3 fault codes. ADB wiring.",
    "page": 3,
}
ADB = {
    "title": "Dometic ADB air distribution box",
    "category": "Air Conditioning",
    "excerpt": "Air distribution box for rooftop air conditioner. Ceiling assembly.",
    "page": 1,
}
FRIDGE = {
    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
    "category": "Refrigerators",
    "excerpt": "12V refrigerator not cooling. Inoperable compressor section.",
    "page": 34,
}
CCD_7990 = {
    "title": "Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990",
    "category": "Air Conditioning",
    "excerpt": (
        "Furrion rooftop HVAC troubleshooting and service. "
        "Freeze, frost, condensate, base pan, suction icing."
    ),
    "page": 12,
}
CCD_8666 = {
    "title": "Furrion Chill 8K Rooftop Air Conditioner FACR08HESA2 CCD-0008666",
    "category": "Air Conditioning",
    "excerpt": (
        "Furrion Chill FACR08HESA2-PS rooftop air conditioner. "
        "Freeze sensor tripped. Condensate drain and base pan."
    ),
    "page": 18,
}

LIBRARY = [UNITY, FACT, BRISK, ADB, FRIDGE]
FACR_FREEZE_LIBRARY = [UNITY, BRISK, FACT, CCD_8666, CCD_7990, FRIDGE]


class TestAcDetect(unittest.TestCase):


    def test_e2_e3_ac_codes(self):
        self.assertTrue(is_air_conditioning_context("Air Conditioning", "", "E2 on the CCC"))
        self.assertTrue(is_air_conditioning_context("", "Dometic rooftop AC", "E3 code"))


    def test_level_up_is_not_ac(self):
        self.assertFalse(
            is_air_conditioning_context(
                "Leveling",
                "Lippert Level Up Advantage 807662",
                "Manual Mode flashes",
            )
        )


class TestAcRanking(unittest.TestCase):
    pass






class TestFacrFreezeRetrieval(unittest.TestCase):
    def test_facr_freeze_context(self):
        self.assertTrue(
            is_facr_rooftop_freeze_context("Air Conditioning", FACR_MODEL, FACR_CONCERN)
        )
        self.assertTrue(
            is_facr_rooftop_freeze_context("", FACR_MODEL, "base pan ice / melt leak")
        )
        self.assertTrue(
            is_facr_rooftop_freeze_context("", "FACR08HESA2-PS", "suction icing")
        )
        self.assertFalse(
            is_facr_rooftop_freeze_context("Air Conditioning", CHASE_MODEL, CHASE_CONCERN)
        )
        self.assertFalse(
            is_facr_rooftop_freeze_context(
                "Refrigerators", "Furrion FCR10DCGTA", "icing up on rear wall"
            )
        )
        self.assertFalse(
            is_facr_rooftop_freeze_context("Air Conditioning", "Dometic B57915", "no cool")
        )


if __name__ == "__main__":
    unittest.main()
