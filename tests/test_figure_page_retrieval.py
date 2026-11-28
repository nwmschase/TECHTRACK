"""Figure / terminal page retrieval: prefer real SM diagrams over Quick Notes p.13."""
import unittest

from gd_library_coach import (
    FURRION_FCR_BOARD_FIGURE_PAGES,
)

FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"

# Shop-typical OCR/index text for CCD-0008122 (Chase live miss was p.13).
FURRION_PAGES = [
    {
        "page": 13,
        "title": FURRION,
        "excerpt": (
            "Troubleshooting Instructions\nQuick Notes\n"
            "Nominal voltage: 12 V DC\n"
            "Check supply voltage at the refrigerator.\n"
            "If voltage is below specification, charge the battery.\n"
            "Output of the compressor circuit should be within spec."
        ),
    },
    {
        "page": 11,
        "title": FURRION,
        "excerpt": (
            "Wiring diagram\nFig. 1 Refrigerator wiring schematic\n"
            "12V DC input, compressor, fan connections."
        ),
    },
    {
        "page": 16,
        "title": FURRION,
        "excerpt": (
            "Fig. 2 Inverter PCB\n"
            "Fig. 3 Diagnostic LED terminals D and +\n"
            "Fig. 4 Board layout showing output terminals"
        ),
    },
    {
        "page": 17,
        "title": FURRION,
        "excerpt": (
            "Fig. 4 Inverter board terminal identification\n"
            "D / + diagnostic LED clip-on points on the inverter PCB"
        ),
    },
    {
        "page": 27,
        "title": FURRION,
        "excerpt": (
            "Error Code — Fan Fault Diagnostics\n"
            "Fig. 21 Locate the inverter PCB. "
            "Measure voltage at the F+ and F− terminals."
        ),
    },
    {
        "page": 45,
        "title": FURRION,
        "excerpt": "Fig. 68 Housing labels\nFig. 69 Terminal identification on the refrigerator housing",
    },
    {
        "page": 46,
        "title": FURRION,
        "excerpt": "Fig. 69 Housing labels continued — terminal callouts on the cabinet.",
    },
]

DIAGRAM_PAGES = {11, 16, 17, 27, 45, 46}


class TestBoardFigureAskDetect(unittest.TestCase):
    pass



class TestPageLayoutGuard(unittest.TestCase):
    pass








if __name__ == "__main__":
    unittest.main()
