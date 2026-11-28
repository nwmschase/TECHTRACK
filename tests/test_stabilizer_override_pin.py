"""Front stabilizer / PSX1 seized override pin: complete jack assembly, not coupler-only."""
import unittest

from gd_library_coach import (
    is_stabilizer_override_pin_context,
)

WO_MODEL = "Lippert PSX1 front stabilizer"
WO_COMPLAINT = (
    "Power extend/retract works; manual crank/override will not engage. "
    "Roll pin seized at the override coupler."
)

PSX1_OVERRIDE_USAGE = {
    "title": "Lippert PSX1 CCD-0007345",
    "category": "Leveling",
    "page": 7,
    "excerpt": (
        "Override usage. How to use the manual override crank. "
        "Coupler engagement for temporary override. Not an assembly R&R page."
    ),
}
PSX1_ASSEMBLY = {
    "title": "Lippert PSX1 CCD-0007345",
    "category": "Leveling",
    "page": 4,
    "excerpt": (
        "Front stabilizer jack. Replace the complete jack assembly. "
        "Reconnect mount and electrical. Retest power and manual."
    ),
}
COUPLER_ONLY = {
    "title": "Lippert PSX1 CCD-0007345",
    "category": "Leveling",
    "page": 9,
    "excerpt": "Replace the override coupler only. Coupler-only repair. No complete assembly.",
}
REAR_OWNER = {
    "title": "rear stabilizer owner",
    "category": "ID & Reference",
    "page": 1,
    "excerpt": "Rear stabilizer owner identification. Stabilizer jack location.",
}
LEVEL_UP = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "page": 2,
    "excerpt": "Level-Up hydraulic leveling controller 807662 Manual Mode. OCTP.",
}

LIBRARY = [PSX1_OVERRIDE_USAGE, COUPLER_ONLY, LEVEL_UP, REAR_OWNER, PSX1_ASSEMBLY]


class TestStabilizerDetect(unittest.TestCase):
    def test_seized_roll_pin_is_psx1_path(self):
        self.assertTrue(
            is_stabilizer_override_pin_context("Leveling", WO_MODEL, WO_COMPLAINT)
        )
        self.assertTrue(
            is_stabilizer_override_pin_context(
                "",
                "PSX1",
                "manual override will not engage, override pin broken, not field serviceable",
            )
        )


    def test_power_only_without_manual_fail_is_not_pin_path(self):
        self.assertFalse(
            is_stabilizer_override_pin_context(
                "Leveling", "front stabilizer jack", "power extend works"
            )
        )


if __name__ == "__main__":
    unittest.main()
