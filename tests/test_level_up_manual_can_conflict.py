"""Level Up Manual Mode dump + Auto works: Firefly/OneControl CAN isolate."""
import unittest

from gd_library_coach import (
    LEVEL_UP_CAN_PRODUCT_LOCK,
    LEVEL_UP_CAN_SEARCH_BOOST,
    coach_library_search_boost,
    is_level_up_advantage_context,
    is_level_up_manual_can_conflict_context,
    is_level_up_manual_dump_context,
    is_stabilizer_override_pin_context,
    level_up_search_symptom,
    rank_chunks_for_level_up_can,
    score_level_up_can_chunk,
)

WO_MODEL = "Lippert Level Up Advantage 807662"
WO_COMPLAINT = (
    "Manual Mode flashes then dumps back to home on the Level Up pad. "
    "Auto Level still works."
)
WO_CAN_STAYS = (
    f"{WO_COMPLAINT} Power good, no brownout, no error text. "
    "Unplugged wired coach CAN, terminator left in: Manual Mode stays."
)
WO_CAN_DUMPS = (
    f"{WO_COMPLAINT} Power good, no brownout, no error text. "
    "Unplugged wired coach CAN, terminator left in: Manual Mode still dumps."
)

SHOP_WRITEUP = {
    "title": "shop writeup — Level Up Advantage 807662 Manual Mode flash-home / Firefly CAN",
    "category": "Leveling",
    "page": 1,
    "excerpt": (
        "Manual Mode flashes home. Auto Level works. Leave rubber-boot terminator "
        "plugged in. Unplug only wired coach CAN (Firefly/OneControl). "
        "If Manual stays: Firefly USB firmware. If Manual still dumps: Lippert path."
    ),
}
BOARD_SWAP = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "page": 8,
    "excerpt": "Replace the 807662 controller and LCD. Board swap. No CAN isolate.",
}
TI005 = {
    "title": "TI-005 Electronic Leveling Troubleshooting Guide",
    "category": "Leveling",
    "page": 2,
    "excerpt": (
        "Level-Up hydraulic leveling controller Manual Mode. "
        "Touch pad LCD returns to home screen. Pump and slide output."
    ),
}
UNITY = {
    "title": "Lippert OneControl M Series Unity Board SM",
    "category": "Electrical",
    "page": 4,
    "excerpt": (
        "OneControl Unity M-Series reversing output for awning and slide. "
        "BAT1 BAT2 X270 hold EXTEND RETRACT polarity reverse."
    ),
}

LIBRARY = [BOARD_SWAP, UNITY, TI005, SHOP_WRITEUP]

LIVE_BOARD_FIRST = (
    "Manual Mode will not stay. Swap another 807662 controller and the LCD next."
)
LIVE_FIREFLY_WITHOUT_PROVE = (
    "This is Firefly. Call Firefly 574-825-4600 and do a USB firmware update now."
)
LIVE_FIREFLY_AFTER_STILL_DUMP = (
    "CAN is unplugged and Manual still dumps. Push a Firefly USB firmware update "
    "and swap another 807662 for the Firefly conflict."
)


class TestLevelUpCanDetect(unittest.TestCase):
    def test_manual_dump_auto_works_is_can_path(self):
        self.assertTrue(is_level_up_advantage_context("Leveling", WO_MODEL, WO_COMPLAINT))
        self.assertTrue(is_level_up_manual_dump_context("Leveling", WO_MODEL, WO_COMPLAINT))
        self.assertTrue(
            is_level_up_manual_can_conflict_context("Leveling", WO_MODEL, WO_COMPLAINT)
        )

    def test_other_pad_functions_count_as_auto_works(self):
        self.assertTrue(
            is_level_up_manual_can_conflict_context(
                "Leveling",
                WO_MODEL,
                "Manual Mode won't stay / flashes home; other pad functions work",
            )
        )

    def test_manual_dump_without_auto_is_not_can_conflict_yet(self):
        dump_only = "Manual Mode flashes then returns to home/first screen."
        self.assertTrue(is_level_up_manual_dump_context("Leveling", WO_MODEL, dump_only))
        self.assertFalse(
            is_level_up_manual_can_conflict_context("Leveling", WO_MODEL, dump_only)
        )

    def test_auto_fail_is_not_can_conflict(self):
        self.assertFalse(
            is_level_up_manual_can_conflict_context(
                "Leveling",
                WO_MODEL,
                "Manual Mode flashes home and Auto Level does not work",
            )
        )

    def test_stabilizer_and_fridge_lose(self):
        self.assertFalse(
            is_level_up_manual_can_conflict_context(
                "Leveling",
                "Lippert PSX1 front stabilizer",
                "manual override will not engage, roll pin seized",
            )
        )
        self.assertTrue(
            is_stabilizer_override_pin_context(
                "Leveling",
                "Lippert PSX1 front stabilizer",
                "manual override will not engage, roll pin seized",
            )
        )
        self.assertFalse(
            is_level_up_manual_dump_context(
                "Refrigerators", "Furrion FCR10", "not cooling"
            )
        )


class TestLevelUpCanQueryRewrite(unittest.TestCase):
    def test_boost_adds_can_isolate_when_auto_works(self):
        q = level_up_search_symptom("Leveling", WO_MODEL, WO_COMPLAINT)
        low = q.lower()
        self.assertIn("terminator", low)
        self.assertIn("firefly", low)
        self.assertIn("807662", low)
        self.assertIn("firefly cable", LEVEL_UP_CAN_SEARCH_BOOST.lower())
        self.assertIn("rubber boot", LEVEL_UP_CAN_SEARCH_BOOST.lower())
        self.assertNotIn("wired coach can", LEVEL_UP_CAN_SEARCH_BOOST.lower())
        self.assertNotIn("unity", low)
        self.assertNotIn("awning", low)

    def test_dump_without_auto_does_not_add_can_boost(self):
        raw = "Manual Mode flashes then returns to home/first screen."
        q = level_up_search_symptom("Leveling", WO_MODEL, raw)
        low = q.lower()
        self.assertIn("ti-005", low)
        self.assertNotIn("firefly", low)
        self.assertNotIn("terminator", low)


class TestLevelUpCanRanking(unittest.TestCase):
    def test_can_writeup_outranks_board_swap_and_unity(self):
        query = f"{WO_MODEL} {WO_COMPLAINT}"
        ranked = rank_chunks_for_level_up_can(LIBRARY, query, limit=4)
        titles = [r["title"] for r in ranked]
        self.assertEqual(titles[0], SHOP_WRITEUP["title"])
        self.assertNotIn(UNITY["title"], titles)
        self.assertGreater(
            score_level_up_can_chunk(SHOP_WRITEUP, query),
            score_level_up_can_chunk(BOARD_SWAP, query),
        )
        self.assertGreater(
            score_level_up_can_chunk(SHOP_WRITEUP, query),
            score_level_up_can_chunk(UNITY, query),
        )


if __name__ == "__main__":
    unittest.main()
