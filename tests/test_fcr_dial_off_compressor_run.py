"""FCR08/FCR10 dial OFF + compressor still running: thermostat C/T, not fuse-first."""
import unittest
from pathlib import Path

from gd_library_coach import (
    compact_manual_context,
    complete_chat_with_payload_retry,
    is_ai_request_too_large,
    is_fcr_e2_fan_fault_context,
    shrink_ai_messages,
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


class TestPayload413(unittest.TestCase):
    def test_413_request_too_large_is_detected(self):
        self.assertTrue(is_ai_request_too_large(RuntimeError("Groq: 413 request too large")))
        self.assertTrue(is_ai_request_too_large("payload too large"))
        self.assertFalse(is_ai_request_too_large(RuntimeError("401 invalid api key")))


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
