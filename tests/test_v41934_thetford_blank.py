"""v4.19.34: a Thetford flush-lever turn cannot ship as a source line alone."""
import unittest

from gd_library_coach import (
    avoid_duplicate_reply,
    guard_blank_shop_reply,
    polish_shop_reply,
    reply_is_source_only_or_empty,
)

SOURCE = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
CONCERN = "toilet leaks under the flush lever when flushing"
MODEL = "Style II 42070"
CATEGORY = "Plumbing / Toilets"


def _turn(draft, latest, history, model=MODEL):
    return avoid_duplicate_reply(draft, history, latest, CATEGORY, model)


class TestThetfordBlankReply(unittest.TestCase):
    def test_source_only_turn_asks_for_the_supply_connection(self):
        reply = _turn(SOURCE, CONCERN, [])
        low = reply.lower()
        self.assertIn("supply", low)
        self.assertIn("water valve", low)
        self.assertIn("42088", reply)
        self.assertIn("📖", reply)
        self.assertNotEqual(reply.strip(), SOURCE)
        self.assertGreater(len(reply.splitlines()), 1)
        self.assertNotIn("rooftop assembly", low)

    def test_supply_tight_asks_the_valve_and_keeps_a_cite(self):
        history = [
            {"role": "user", "content": CONCERN},
            {
                "role": "assistant",
                "content": (
                    "Back of the toilet: check the water supply line connection at the water valve. "
                    "Secure or tighten it as necessary.\n"
                    + SOURCE
                ),
            },
        ]
        reply = _turn(SOURCE, "Supply connection is tight. No leak there.", history)
        low = reply.lower()
        self.assertIn("water valve", low)
        self.assertIn("weep", low)
        self.assertIn("📖", reply)
        self.assertNotEqual(reply.strip(), SOURCE)
        self.assertNotIn("rooftop", low)

    def test_water_leaking_under_the_lever_is_not_a_rooftop_job(self):
        reply = _turn(
            "If those pressures are in range, replace the rooftop assembly.\n"
            "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990",
            "water leaking under the flush lever when flushing",
            [],
            model="Thetford Style II 42070",
        )
        low = reply.lower()
        self.assertNotIn("rooftop", low)
        self.assertNotIn("pressures", low)
        self.assertTrue(
            "supply" in low or "no thetford document" in low,
            reply,
        )

    def test_a_real_shop_body_is_kept(self):
        body = (
            "Back of the toilet: check the water supply line connection at the water valve. "
            "Secure or tighten it as necessary.\n"
            + SOURCE
        )
        reply = _turn(body, CONCERN, [])
        self.assertIn("supply", reply.lower())
        self.assertIn("42088", reply)
        self.assertNotIn("rooftop", reply.lower())

    def test_source_only_or_empty_falls_back_to_the_next_cited_check(self):
        history = [
            {"role": "user", "content": CONCERN},
            {
                "role": "assistant",
                "content": (
                    "Back of the toilet: check the water supply line connection at the water valve. "
                    "Secure or tighten it as necessary.\n"
                    + SOURCE
                ),
            },
        ]
        latest = "Supply connection is tight. No leak there."
        drafts = ("", SOURCE, "📖 Source: Other Manual, page 9", "Source: page 3")
        for draft in drafts:
            self.assertTrue(reply_is_source_only_or_empty(draft), draft)
            guarded = guard_blank_shop_reply(draft, history, latest, CATEGORY, MODEL)
            self.assertFalse(reply_is_source_only_or_empty(guarded), guarded)
            self.assertIn("weep", guarded.lower())
            self.assertIn("📖", guarded)
            reply = _turn(draft, latest, history)
            self.assertFalse(reply_is_source_only_or_empty(reply), reply)
            self.assertIn("water valve", reply.lower())
            self.assertIn("weep", reply.lower())
            self.assertIn("📖", reply)
            self.assertNotEqual((reply or "").strip(), (draft or "").strip())

    def test_no_library_miss_line_still_ships_without_a_cite(self):
        filler = "Check the reading on this unit and write it down."
        reply = polish_shop_reply(filler, [], CONCERN, "", "Thetford Style II 42070")
        low = reply.lower()
        self.assertIn("no thetford document in the shop library for this unit", low)
        self.assertNotIn("📖", reply)
        self.assertNotIn("supply connection", low)
        self.assertNotIn("rooftop", low)


if __name__ == "__main__":
    unittest.main()
