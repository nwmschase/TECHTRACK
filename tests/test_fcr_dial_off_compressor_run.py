"""FCR08/FCR10 dial OFF + compressor still running: thermostat C/T, not fuse-first."""
import unittest

from bay_procedure import compile_bay_procedure, procedure_plain_text, rewrite_bay_search_symptom
from gd_library_coach import (
    DIAL_OFF_RUN_INVERTER_SHOP_LINE,
    DIAL_OFF_RUN_PART_SHOP_LINE,
    DIAL_OFF_RUN_PRODUCT_LOCK,
    DIAL_OFF_RUN_SEARCH_BOOST,
    DIAL_OFF_RUN_SHOP_LINE,
    coach_library_search_boost,
    compact_manual_context,
    complete_chat_with_payload_retry,
    ct_prove_from_turn,
    dial_off_run_reply_needs_guard,
    dial_off_run_search_symptom,
    ensure_fcr_dial_off_compressor_run_path,
    extract_stated_facts,
    is_ai_request_too_large,
    is_fcr_dial_off_compressor_run_context,
    is_fcr_e2_fan_fault_context,
    is_fridge_ice_moisture_context,
    is_fridge_no_power_complaint,
    rank_chunks_for_dial_off_run,
    reply_names_dial_off_ct_prove,
    reply_names_dial_off_inverter_secondary,
    reply_names_spark_free_thermostat_part,
    reply_opens_dial_off_wrong_tree,
    score_dial_off_run_chunk,
    shrink_ai_messages,
    trim_coach_history,
)

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


class TestDialOffRunDetect(unittest.TestCase):
    def test_live_off_and_running_is_thermostat_not_fuse_or_ice(self):
        self.assertTrue(
            is_fcr_dial_off_compressor_run_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_fridge_no_power_complaint("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_fridge_ice_moisture_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )
        self.assertFalse(
            is_fcr_e2_fan_fault_context("Refrigerators", WO_MODEL, WO_COMPLAINT)
        )

    def test_natural_complaints_match_fcr_family(self):
        samples = (
            "won't shut off",
            "runs when Off",
            "overcooling with dial Off",
            "freezer frozen solid with control Off",
            "compressor keeps running with the knob off",
            "control set to off and the compressor is still running",
        )
        for complaint in samples:
            self.assertTrue(
                is_fcr_dial_off_compressor_run_context("Refrigerators", WO_MODEL, complaint),
                complaint,
            )

    def test_arctic_family_matches(self):
        self.assertTrue(
            is_fcr_dial_off_compressor_run_context(
                "Refrigerators",
                "Furrion Arctic",
                "dial off, compressor still running, too cold",
            )
        )

    def test_opposite_and_other_paths_do_not_match(self):
        self.assertFalse(
            is_fcr_dial_off_compressor_run_context(
                "Refrigerators",
                WO_MODEL,
                "dial is off and the fridge is not cooling",
            )
        )
        self.assertFalse(
            is_fcr_dial_off_compressor_run_context(
                "Refrigerators",
                WO_MODEL,
                "not cooling, compressor running constantly, coolant leak",
            )
        )
        self.assertFalse(
            is_fcr_dial_off_compressor_run_context(
                "Refrigerators",
                "Norcold N611",
                "dial off but compressor still running",
            )
        )
        self.assertFalse(
            is_fcr_dial_off_compressor_run_context(
                "Refrigerators",
                WO_MODEL,
                "freezes contents, intermittent blinking 2 / E2",
            )
        )
        self.assertTrue(
            is_fridge_ice_moisture_context(
                "Refrigerators",
                WO_MODEL,
                "icing up on rear wall — only about half from the top down",
            )
        )
        self.assertFalse(
            is_fcr_dial_off_compressor_run_context(
                "Refrigerators",
                WO_MODEL,
                "icing up on rear wall — only about half from the top down",
            )
        )

    def test_wont_turn_off_is_not_no_power(self):
        complaint = "FCR10 won't turn off, compressor still running"
        self.assertFalse(is_fridge_no_power_complaint("Refrigerators", WO_MODEL, complaint))
        self.assertTrue(
            is_fcr_dial_off_compressor_run_context("Refrigerators", WO_MODEL, complaint)
        )


class TestDialOffRunQueryAndRank(unittest.TestCase):
    def test_boost_is_thermostat_not_fuse(self):
        q = dial_off_run_search_symptom("Refrigerators", WO_MODEL, WO_COMPLAINT)
        low = q.lower()
        self.assertIn("2021128850", q)
        self.assertIn("thermostat", low)
        self.assertIn("no jumper", DIAL_OFF_RUN_PRODUCT_LOCK.lower())
        self.assertNotIn("fuse", DIAL_OFF_RUN_SEARCH_BOOST.lower())
        self.assertNotIn("no power", DIAL_OFF_RUN_SEARCH_BOOST.lower())
        facts = extract_stated_facts(f"{WO_MODEL} {WO_COMPLAINT}")
        self.assertEqual(facts.get("dial_off_run"), "overcool")
        boost = coach_library_search_boost(facts).lower()
        self.assertIn("2021128850", boost)
        self.assertNotIn("no power", boost)
        self.assertNotIn("ice and moisture", boost)

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


class TestDialOffRunGuard(unittest.TestCase):
    def test_fuse_first_reply_becomes_ct_prove_and_names_part(self):
        self.assertTrue(reply_opens_dial_off_wrong_tree(LIVE_FUSE_MISS))
        self.assertTrue(dial_off_run_reply_needs_guard(LIVE_FUSE_MISS))
        fixed = ensure_fcr_dial_off_compressor_run_path(LIVE_FUSE_MISS)
        low = fixed.lower()
        self.assertTrue(reply_names_dial_off_ct_prove(fixed))
        self.assertTrue(reply_names_spark_free_thermostat_part(fixed))
        self.assertIn("2021128850", fixed)
        self.assertIn("c-fcr10dcgta-007", low)
        self.assertIn("no jumper", low)
        self.assertIn("page 31", low)
        self.assertIn("page 43", low)
        self.assertIn("c (blue)", low)
        self.assertIn("t (black)", low)
        self.assertFalse(reply_opens_dial_off_wrong_tree(fixed))
        self.assertNotIn("page 19", low)
        self.assertNotIn("page 18", low)
        self.assertIn("coolant", low)
        self.assertNotIn("running constantly", DIAL_OFF_RUN_PRODUCT_LOCK.lower().split("do not cite")[0])

    def test_ct_open_stopped_is_part_climax(self):
        facts = extract_stated_facts(
            "Opened flag terminals C and T, no jumper, compressor stopped"
        )
        self.assertEqual(facts.get("ct_prove"), "stopped")
        fixed = ensure_fcr_dial_off_compressor_run_path(LIVE_FUSE_MISS, facts)
        low = fixed.lower()
        self.assertIn("2021128850", fixed)
        self.assertIn("c-fcr10dcgta-007", low)
        self.assertIn("page 43", low)
        self.assertIn(DIAL_OFF_RUN_PART_SHOP_LINE.split("\n")[0][:40], fixed)
        self.assertFalse(reply_opens_dial_off_wrong_tree(fixed))
        self.assertNotIn("15a", low)

    def test_short_followup_stopped_reaches_part_climax(self):
        self.assertEqual(ct_prove_from_turn("compressor stopped"), "stopped")
        self.assertEqual(ct_prove_from_turn(WO_COMPLAINT), "")
        fixed = ensure_fcr_dial_off_compressor_run_path(
            "",
            {"dial_off_run": "overcool", "ct_prove": ct_prove_from_turn("it stopped")},
        )
        self.assertIn("2021128850", fixed)
        self.assertIn("page 43", fixed.lower())

    def test_ct_open_still_running_is_inverter_harness_not_fuse(self):
        facts = extract_stated_facts(
            "C/T open, no jumper, compressor keeps running"
        )
        self.assertEqual(facts.get("ct_prove"), "still_running")
        fixed = ensure_fcr_dial_off_compressor_run_path(
            "Replace the thermostat because it is running constantly. Check the 15A fuse.",
            facts,
        )
        low = fixed.lower()
        self.assertTrue(reply_names_dial_off_inverter_secondary(fixed))
        self.assertIn("inverter", low)
        self.assertIn("harness", low)
        self.assertIn("page 45", low)
        self.assertNotIn("2021128850", fixed)
        self.assertNotIn("c-fcr10dcgta-007", low)
        self.assertFalse(reply_opens_dial_off_wrong_tree(fixed))
        self.assertNotIn("15a", low)
        self.assertIn(DIAL_OFF_RUN_INVERTER_SHOP_LINE.split("\n")[0][:32], fixed)

    def test_shop_lines_do_not_look_like_the_wrong_tree(self):
        for line in (
            DIAL_OFF_RUN_SHOP_LINE,
            DIAL_OFF_RUN_PART_SHOP_LINE,
            DIAL_OFF_RUN_INVERTER_SHOP_LINE,
            DIAL_OFF_RUN_PRODUCT_LOCK,
        ):
            self.assertFalse(reply_opens_dial_off_wrong_tree(line), line[:80])


class TestDialOffRunBayProcedure(unittest.TestCase):
    def test_bay_pdf_leads_with_thermostat_not_fuse(self):
        q = rewrite_bay_search_symptom("Refrigerators", WO_MODEL, WO_COMPLAINT)
        self.assertIn("2021128850", q)
        self.assertNotIn("no power", DIAL_OFF_RUN_SEARCH_BOOST.lower())
        proc = compile_bay_procedure(
            concern=WO_COMPLAINT,
            brand="Furrion",
            model=WO_MODEL,
            category="Refrigerators",
            chunks=[FUSE_P19, LED_P18, P34, P31, P43],
        )
        text = procedure_plain_text(proc).lower()
        self.assertIn("2021128850", text)
        self.assertIn("c-fcr10dcgta-007", text)
        self.assertIn("no jumper", text)
        self.assertIn("page 31", text)
        self.assertIn("page 43", text)
        self.assertIn("inverter", text)
        self.assertIn("harness", text)
        pages = [c.source_page for c in proc.checks]
        self.assertNotIn(19, pages)
        self.assertNotIn(18, pages)
        self.assertNotIn(34, pages)


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
