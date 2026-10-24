"""Furrion FCR E2 / Fan Fault Current: Fan Replacement must outrank board-only R&R."""
import unittest

from gd_library_coach import (
    is_air_conditioning_context,
    is_fcr_e2_fan_fault_context,
)

FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"
WO_MODEL = "Furrion FCR10DCGTA-BG-PWH"
WO_COMPLAINT = (
    "Freezes contents; intermittent blinking 2 / E2; temp control intermittent"
)
WO_READINGS = (
    "fan V 14.28-10.37 V; fan amps 0.383-0.442 A; supply 13.37 V shore / "
    "12.70 V battery; E2 returned about 1.5 hr after thaw"
)

# Shop-typical CCD-0008122 index text already used in this repo (p.27 fixture + leftover tree).
FAN_FAULT_DIAG = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 27,
    "excerpt": (
        "Error Code — Fan Fault Diagnostics\n"
        "Fig. 21 Locate the inverter PCB. "
        "Measure voltage at the F+ and F− terminals.\n"
        "If the error code remains after checking connections, "
        "replace the inverter PCB and fan. Fan Replacement in Repair Section 2."
    ),
}
FAN_REPLACEMENT = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 33,
    "excerpt": (
        "Potential air blockage or bad fan. Proceed to Fan Replacement in "
        "Repair Section 2 for further information."
    ),
}
FAN_FAULT_CURRENT_SPEC = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 18,
    "excerpt": (
        "Fan Fault Current 1 A peak. Inverter-board fan driver overcurrent spec."
    ),
}
BOARD_ONLY_RR = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 48,
    "excerpt": (
        "Compressor Inverter PCB Replacement. Replace the driver board / "
        "rear inverter. No fan procedure on this page."
    ),
}
AC_E2 = {
    "title": "Furrion FACT12SA2 Rooftop Air Conditioner SM",
    "category": "Air Conditioning",
    "page": 15,
    "excerpt": "E2 freeze / evaporator sensor on the rooftop AC. Not a fridge fan code.",
}

LIBRARY = [FAN_FAULT_CURRENT_SPEC, BOARD_ONLY_RR, FAN_FAULT_DIAG, FAN_REPLACEMENT, AC_E2]


class TestFcrE2Detect(unittest.TestCase):
    def test_wo_complaint_is_fridge_e2_not_ac(self):
        self.assertTrue(
            is_fcr_e2_fan_fault_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_air_conditioning_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )

    def test_fan_readings_keep_the_path(self):
        self.assertTrue(
            is_fcr_e2_fan_fault_context(
                "Refrigerators", WO_MODEL, f"{WO_COMPLAINT} {WO_READINGS}"
            )
        )

    def test_ac_e2_is_not_fridge_fan_fault(self):
        self.assertFalse(
            is_fcr_e2_fan_fault_context("Air Conditioning", "Furrion FACT12SA2", "E2 on the CCC")
        )
        self.assertTrue(
            is_air_conditioning_context("Air Conditioning", "Furrion FACT12SA2", "E2 on the CCC")
        )

    def test_powered_not_cooling_without_e2_is_not_fan_fault(self):
        self.assertFalse(
            is_fcr_e2_fan_fault_context(
                "Refrigerators",
                "Furrion FCR10",
                "found fuse blown and replaced, fridge light comes on, fridge is not cooling",
            )
        )


if __name__ == "__main__":
    unittest.main()
