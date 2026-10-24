"""FCR08/FCR10 dial OFF + compressor still running: thermostat C/T, not fuse-first."""
import unittest
from pathlib import Path

from gd_library_coach import (
    DIAL_OFF_RUN_PRODUCT_LOCK,
    DIAL_OFF_RUN_SEARCH_BOOST,
    OPEN_LIBRARY_COACH_RULE,
    coach_library_search_boost,
    compact_manual_context,
    complete_chat_with_payload_retry,
    is_ai_request_too_large,
    is_fcr_e2_fan_fault_context,
    rank_chunks_for_dial_off_run,
    score_dial_off_run_chunk,
    shrink_ai_messages,
    trim_coach_history,
)

ROOT = Path(__file__).resolve().parents[1]


FURRION = "Furrion FCR08/FCR10 SM CCD-0008122"
WO_MODEL = "Furrion FCR10DCGTA-BG-PWH"
WO_COMPLAINT = (
    "temperature dial OFF but compressor still running, freezer frozen solid, overcooling"
)

P31 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 31,
    "excerpt": (
        "Intermittent Thermostat Operation. Bypass the thermostat by disconnecting "
        "the flag terminals C (blue) and T (black) (Fig. 24A). Create a jumper "
        "connection (Fig. 25). If operating, replace the thermostat."
    ),
}
P43 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 43,
    "excerpt": (
        "Repair Section 2 Thermostat Replacement. NOTE: Refer to Part G in the "
        "Replaceable Parts List. Spark-Free Thermostat 2021128850. Confirm the probe "
        "is completely installed and seated (Figs. 59-60). Figs. 57-67."
    ),
}
P45 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 45,
    "excerpt": (
        "Reconnect wires (Fig. 67). Compressor Inverter PCB. C and T connections "
        "may be reversed (Fig. 70A) and that does not affect product performance."
    ),
}
FUSE_P19 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 19,
    "excerpt": (
        "Section 1 Fuse. Locate the fuse in the front vent cavity. "
        "15A ATC blade / cartridge. Fuse location."
    ),
}
CONT_P20 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 20,
    "excerpt": (
        "Power continuity. Measure voltage at the appliance connection. "
        "12V continuity between 12V and 15V."
    ),
}
LED_P18 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 18,
    "excerpt": (
        "Diagnostic LED flash codes. Clip a 10 mA LED. Inverter control voltage "
        "on the rear inverter."
    ),
}
P34 = {
    "title": FURRION,
    "category": "Refrigerators",
    "page": 34,
    "excerpt": (
        "Not Cooling. Is the compressor running constantly? Yes. Likely a coolant "
        "leak. Replace unit. Replace the thermostat to recalibrate. Thermostat Replacement."
    ),
}

LIBRARY = [FUSE_P19, CONT_P20, LED_P18, P34, P31, P43, P45]

LIVE_FUSE_MISS = (
    "Check the 15A fuse in the front vent cavity, then confirm 12V continuity "
    "at the appliance connection.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 19\n"
    "Next, count the diagnostic LED flashes and measure inverter control voltage.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 18"
)


class TestDialOffRunQueryAndRank(unittest.TestCase):

    def test_thermostat_pages_outrank_fuse_continuity_led_and_p34(self):
        query = f"{WO_MODEL} {WO_COMPLAINT}"
        ranked = rank_chunks_for_dial_off_run(LIBRARY, query, limit=4)
        pages = [r["page"] for r in ranked]
        self.assertIn(pages[0], (31, 43, 45))
        self.assertNotIn(19, pages)
        self.assertNotIn(20, pages)
        self.assertNotIn(18, pages)
        self.assertNotIn(34, pages)
        self.assertGreater(score_dial_off_run_chunk(P43, query), score_dial_off_run_chunk(FUSE_P19, query))
        self.assertGreater(score_dial_off_run_chunk(P31, query), score_dial_off_run_chunk(CONT_P20, query))
        self.assertGreater(score_dial_off_run_chunk(P31, query), score_dial_off_run_chunk(LED_P18, query))
        self.assertGreater(score_dial_off_run_chunk(P43, query), score_dial_off_run_chunk(P34, query))


class TestPayload413(unittest.TestCase):
    def test_413_request_too_large_is_detected(self):
        self.assertTrue(is_ai_request_too_large(RuntimeError("Groq: 413 request too large")))
        self.assertTrue(is_ai_request_too_large("payload too large"))
        self.assertFalse(is_ai_request_too_large(RuntimeError("401 invalid api key")))

    def test_history_and_excerpts_shrink(self):
        history = []
        for i in range(12):
            history.append({"role": "user", "content": f"turn {i} dial still off " + ("x" * 400)})
            history.append(
                {
                    "role": "assistant",
                    "content": ("Check the fuse.\n" * 40) + "\n📖 Source: Furrion SM - page 19",
                }
            )
        trimmed = trim_coach_history(history, max_messages=8, assistant_cap=200)
        self.assertLessEqual(len(trimmed), 8)
        self.assertLess(sum(len(m["content"]) for m in trimmed), sum(len(m["content"]) for m in history))
        self.assertTrue(any("page 19" in m["content"] or "Source" in m["content"] for m in trimmed))
        big_context = "\n\n".join(
            f"[EXCERPT {n} | PROCEDURE] Manual: {FURRION} | Page: {n}\n" + ("fuse path " * 400)
            for n in range(1, 9)
        )
        compact = compact_manual_context(big_context, excerpt_cap=300, total_cap=2000)
        self.assertLess(len(compact), len(big_context))
        self.assertIn("[EXCERPT", compact)

    def test_retry_on_413_uses_smaller_payload(self):
        messages = [
            {"role": "system", "content": "RULES " + ("manual excerpts\n" + ("chunk " * 500))},
            {"role": "user", "content": "dial off compressor running"},
            {"role": "assistant", "content": "Check fuse page 19. " * 80},
            {"role": "user", "content": "still running"},
            {"role": "assistant", "content": "Check 12V continuity page 20. " * 80},
            {"role": "user", "content": "opened C and T"},
        ]
        sizes = []

        def call(payload, temperature, max_tokens):
            size = sum(len(m.get("content") or "") for m in payload if isinstance(m.get("content"), str))
            sizes.append(size)
            if len(sizes) == 1:
                raise RuntimeError("413 request too large")
            return "thermostat C/T part 2021128850"

        reply = complete_chat_with_payload_retry(call, messages, max_tokens=900)
        self.assertIn("2021128850", reply)
        self.assertGreaterEqual(len(sizes), 2)
        self.assertLess(sizes[1], sizes[0])
        smaller = shrink_ai_messages(messages, level=2)
        self.assertLess(
            sum(len(m.get("content") or "") for m in smaller if isinstance(m.get("content"), str)),
            sizes[0],
        )


if __name__ == "__main__":
    unittest.main()
