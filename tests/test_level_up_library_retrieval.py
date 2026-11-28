"""Level Up Advantage / 807662 library retrieval: prefer Level-Up/OCTP/TI over Unity."""
import unittest


CHASE_MODEL = (
    "Lippert Level Up Advantage Leveling Controller w/ Slide Output, label 807662 / 25499"
)
CHASE_CONCERN = (
    "Manual Mode flashes then returns to home/first screen. "
    "Connectors: Touch Pad, Remote Sensor, Pump, CAN, Slide Output, Power."
)
CHASE_QUERY = f"{CHASE_MODEL} {CHASE_CONCERN} LCD wiring"

UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
    "page": 4,
}
TI005 = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "excerpt": (
        "Level-Up hydraulic leveling controller Manual Mode. "
        "Touch pad LCD returns to home screen. Pump and slide output."
    ),
    "page": 2,
}
QR092 = {
    "title": "QR-092 Level-Up OCTP wiring",
    "category": "Leveling",
    "excerpt": "Level-Up OCTP touch pad LCD wiring diagram. Controller harness.",
    "page": 1,
}
QR059 = {
    "title": "QR-059 ID guide",
    "category": "ID & Reference",
    "excerpt": "Identify Level-Up leveling controller 807662 vs other Lippert boards.",
    "page": 1,
}
TI170 = {
    "title": "TI-170",
    "category": "Leveling",
    "excerpt": "Level-Up leveling notes and controller identification.",
    "page": 1,
}
GROUND = {
    "title": "Ground Control LCD SM",
    "category": "Leveling",
    "excerpt": "Ground Control electric leveling LCD. Not hydraulic Level Up 807662.",
    "page": 3,
}

LIBRARY = [UNITY, TI005, QR092, QR059, TI170, GROUND]


class TestLevelUpDetect(unittest.TestCase):
    pass





class TestLevelUpRanking(unittest.TestCase):
    pass






if __name__ == "__main__":
    unittest.main()
