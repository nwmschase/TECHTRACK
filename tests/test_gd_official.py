import re
"""GD official method: unit gate, wrong-brand refusal, section read, step hold, labels, verify.

Does not import rv_techtrack. No network.
"""
import unittest

import gd_official as go


class FakeLib:
    def __init__(self, docs, chunks):
        self._d, self._c = docs, chunks

    def documents(self):
        return self._d

    def chunks(self, doc_id):
        return self._c.get(doc_id, [])


def _doc(i, title, brand="", models="", keywords=""):
    return {"id": i, "title": title, "brand": brand, "models": models, "product_line": "",
            "clean_title": "", "doc_number": "", "keywords": keywords, "revision_date": ""}


GC_PAGES = [
    {"page": 1, "text": "Introduction and safety."},
    {"page": 2, "text": "Troubleshooting. Fault codes are shown on the touch pad. Symptom: auto level fails. " * 10},
    {"page": 3, "text": "Zero point calibration. Retract all jacks. Press FRONT 5 times, REAR 5 times, ENTER. Troubleshooting continues. " * 8},
    {"page": 4, "text": "Parts list."},
]
LIB = FakeLib(
    [_doc(1, "Lippert Ground Control 3.0 Auto Level Troubleshooting Guide", "Lippert"),
     _doc(2, "Dometic Ground Control 3.0 803280 Troubleshooting", "Dometic", "803280"),
     _doc(3, "Lippert Ground Control 2.0 Owner's Manual", "Lippert")],
    {1: GC_PAGES, 2: [{"page": 1, "text": "wrong brand " * 300}], 3: GC_PAGES},
)
GC = "Lippert OneControl Ground Control GC 3.0 803280"


def _chat(reply):
    calls = []

    def fn(messages, max_tokens, effort):
        calls.append((messages, max_tokens, effort))
        return reply
    fn.calls = calls
    return fn


class TestUnitGate(unittest.TestCase):
    def test_no_steps_before_unit_identified(self):
        chat = _chat("1. Check plugs")
        r = go.official_turn("auto level fails", "Leveling", "", [], library=LIB, chat_fn=chat, pin_store={})
        self.assertEqual(r["mode"], "identify")
        self.assertIn("Safety", r["reply"])
        self.assertEqual(chat.calls, [])

    def test_brand_and_model_identify(self):
        u = go.identify_unit([], "", "", GC)
        self.assertTrue(u["identified"])
        self.assertEqual(u["brand"], "lippert")


class TestPin(unittest.TestCase):
    def test_wrong_brand_never_pinned(self):
        u = go.identify_unit([], "", "", GC)
        self.assertEqual(go.pin_document(LIB, u)["id"], 1)
        self.assertTrue(go.brand_conflict(u, LIB.documents()[1]))

    def test_no_model_match_triggers_web(self):
        u = go.identify_unit([], "", "", "Lippert OneControl Unity X270D")
        self.assertIsNone(go.pin_document(LIB, u))
        seen = []
        r = go.official_turn("slides dead", "", "Lippert OneControl Unity X270D", [], library=LIB,
                             chat_fn=_chat("x"), pin_store={}, web_fetch_fn=lambda unit: seen.append(unit) or {})
        self.assertEqual(len(seen), 1)
        self.assertEqual(r["mode"], "no_manual")
        self.assertIn("general trade knowledge", r["reply"])

    def test_official_domains_only(self):
        self.assertTrue(go.url_is_official("https://www.lci1.com/x.pdf", "lippert"))
        self.assertTrue(go.url_is_official("https://corporate.lippert.com/a.pdf", "lippert"))
        self.assertFalse(go.url_is_official("https://www.manualslib.com/a.pdf", "lippert"))
        self.assertFalse(go.url_is_official("https://lci1.com.evil.net/a.pdf", "lippert"))
        self.assertTrue(go.url_is_official(go.LIPPERT_UNITY_REF_URL, "lippert"))
        self.assertFalse(go.url_is_official("https://other-bucket.s3.amazonaws.com/a.pdf", "lippert"))


class TestSectionAndWalk(unittest.TestCase):
    def test_full_section_read_before_first_reply(self):
        s = go.load_section(GC_PAGES, "auto level fails")
        self.assertEqual(s["mode"], "section")
        self.assertEqual(s["pages"], [2, 3])
        chat = _chat("1. Read the fault code on the touch pad [Library: X p.2]")
        store = {}
        go.official_turn("auto level fails", "Leveling", GC, [], library=LIB, chat_fn=chat, pin_store=store)
        msgs, max_tokens, effort = chat.calls[0]
        self.assertIn("Zero point calibration", msgs[0]["content"])
        self.assertEqual(max_tokens, go.REPLY_MAX_TOKENS)
        self.assertEqual(effort, "medium")
        go.official_turn("ok", "Leveling", GC, [{"role": "user", "content": "a"}, {"role": "assistant", "content": "1. b"}],
                         library=LIB, chat_fn=chat, pin_store=store)
        self.assertEqual(chat.calls[1][2], "low")

    def test_whole_manual_when_no_section(self):
        s = go.load_section([{"page": 1, "text": "a"}, {"page": 2, "text": "b"}])
        self.assertEqual(s["mode"], "whole_manual")

    def test_not_checked_holds_step(self):
        store = {}
        chat = _chat("1. Confirm controller, jack and touch pad plugs are seated. [Library: X p.2]")
        go.official_turn("auto level fails", "Leveling", GC, [], library=LIB, chat_fn=chat, pin_store=store)
        hist = [{"role": "user", "content": "auto level fails"},
                {"role": "assistant", "content": "1. Confirm controller, jack and touch pad plugs are seated. [Library: X p.2]"}]
        go.official_turn("not checked", "Leveling", GC, hist, library=LIB, chat_fn=chat, pin_store=store)
        self.assertIn("HELD STEP", chat.calls[1][0][0]["content"])
        self.assertIn("plugs are seated", chat.calls[1][0][0]["content"])

    def test_labels_and_honest_pages(self):
        pin = {"pages": [2, 3]}
        out = go.enforce_labels("1. Do a thing\n2. Other [Library: GC p.9]\n3. Ok [Library: GC p.3]", pin)
        lines = out.splitlines()
        self.assertIn("[General trade knowledge]", lines[0])
        self.assertIn("[General trade knowledge]", lines[1])
        self.assertIn("[Library: GC p.3]", lines[2])

    def test_verify_after_repair(self):
        self.assertIn("VERIFY", go.ensure_verify("1. Perform zero point calibration."))
        self.assertEqual(go.ensure_verify("1. Verify it levels."), "1. Verify it levels.")

    def test_unity_selector_drives_path(self):
        lib = FakeLib(LIB.documents() + [_doc(9, "PRIMARY Lippert OneControl Unity Board Diagnostic", "", "", "X270D")],
                      {**LIB._c, 9: [{"page": 1, "text": "Troubleshooting. BAT1 BAT2 30A. Output polarity diagnose. " * 20}]})
        chat = _chat("1. Read the controller label [General trade knowledge]")
        store = {}
        go.official_turn("awning will not extend", "Awnings", GC, [], library=lib, chat_fn=chat, pin_store=store, unity_gate="Yes")
        sysmsg = chat.calls[0][0][0]["content"]
        self.assertIn("ONECONTROL / UNITY PATH", sysmsg)
        self.assertIn("polarity", sysmsg)
        self.assertIn("PRIMARY Lippert OneControl Unity Board Diagnostic", sysmsg)
        store2, chat2 = {}, _chat("x")
        go.official_turn("awning will not extend", "Awnings", GC, [], library=lib, chat_fn=chat2, pin_store=store2, unity_gate="No")
        self.assertNotIn("ONECONTROL / UNITY PATH", chat2.calls[0][0][0]["content"])

    def test_charge_path_handoff_and_no_tag_unit(self):
        u = go.identify_unit([], "", "", "BAL touchscreen leveling (no model tag found)")
        self.assertTrue(u["identified"])
        self.assertTrue(u["model_unknown"])
        lib = FakeLib([_doc(5, "BAL Electric Leveling System Touch Screen Diagnostic Form", "BAL")],
                      {5: [{"page": 1, "text": "Troubleshooting touch screen diagnostic. " * 60}]})
        chat, store = _chat("1. Map the charge path [General trade knowledge]"), {}
        model = "BAL touchscreen leveling (no model tag found)"
        go.official_turn("leveling intermittent", "Leveling", model, [], library=lib, chat_fn=chat, pin_store=store)
        self.assertNotIn("12V CHARGING-PATH WALK", chat.calls[0][0][0]["content"])
        hist = [{"role": "user", "content": "leveling intermittent"}, {"role": "assistant", "content": "1. Check comms"}]
        go.official_turn("Battery voltage dropped heavily under load.", "Leveling", model, hist, library=lib, chat_fn=chat, pin_store=store)
        sysmsg = chat.calls[1][0][0]["content"]
        self.assertIn("12V CHARGING-PATH WALK", sysmsg)
        self.assertIn("battery capacity test", sysmsg)
        self.assertIn("MODEL UNKNOWN", sysmsg)

    def test_verify_first_and_npf_rule(self):
        chat, store = _chat("1. Run the fridge 2 hours and measure both compartments [General trade knowledge]"), {}
        m = "Furrion FCR fridge (model unknown)"
        lib = FakeLib([], {})
        go.official_turn("fridge not cold, freezer ok", "Refrigerators", m, [], library=lib, chat_fn=chat, pin_store=store)
        self.assertIn("VERIFY THE CUSTOMER COMPLAINT", chat.calls[0][0][0]["content"])
        hist = [{"role": "user", "content": "fridge not cold"}, {"role": "assistant", "content": "1. Run it"}]
        go.official_turn("Ran it 3 hours, fridge reached 38F, freezer 0F", "Refrigerators", m, hist, library=lib, chat_fn=chat, pin_store=store)
        sysmsg = chat.calls[1][0][0]["content"]
        self.assertIn("No Problem Found", sysmsg)
        self.assertIn("complaint_verified", sysmsg)

    def test_reported_fact_is_never_asked_again(self):
        pin = {"facts": {"lcd_text": "LCD shows motor fault", "plugs": "plugs seated"}}
        out = go.drop_reasks("1. Read the LCD text and report it\n2. Check plugs are seated\n3. Retract all jacks", pin)
        self.assertNotIn("LCD", out)
        self.assertNotIn("plugs", out)
        self.assertIn("Retract", out)

    def test_unity_not_sure_identifies_board_first(self):
        chat, store = _chat("1. Find the controller label [General trade knowledge]"), {}
        go.official_turn("slides will not move", "Slide-Outs", GC, [], library=LIB, chat_fn=chat, pin_store=store, unity_gate="Not sure")
        self.assertIn("NOT SURE", chat.calls[0][0][0]["content"])
        hist = [{"role": "user", "content": "slides will not move"}, {"role": "assistant", "content": "1. Find label"}]
        go.official_turn("Label says Unity X270D IDS part# 123", "Slide-Outs", GC, hist, library=LIB, chat_fn=chat, pin_store=store, unity_gate="Not sure")
        self.assertEqual(store["gd_pin"]["unity_mode"], "yes")
        self.assertIn("ONECONTROL / UNITY PATH", chat.calls[1][0][0]["content"])

    def test_rule9_warranty_shop_voice_and_findings(self):
        out = go.shop_voice("Compressor is sealed. Contact an authorized service agent for repair.")
        self.assertNotIn("service agent", out.lower())
        self.assertIn("submit them to the OEM for authorization", out)
        chat, store = _chat("1. Verify the noise [General trade knowledge]"), {}
        go.official_turn("AC grinding noise", "Air Conditioning", "Furrion FACR13LPSA2-PS", [], library=FakeLib([], {}), chat_fn=chat, pin_store=store)
        self.assertIn("OEM AUTHORIZATION FINDINGS", chat.calls[0][0][0]["content"])

    def _story(self):
        hist = [
            {"role": "user", "content": "AC makes grinding noise"},
            {"role": "assistant", "content": "1. Run it and listen [General trade knowledge]"},
            {"role": "user", "content": "Verified: ran it, grinding noise from the rooftop unit"},
            {"role": "assistant", "content": "2. Measure compressor amps [Library: FACR13 Service Manual p.12]"},
            {"role": "user", "content": "Compressor 7.27 A at 117 VAC, noise from inside compressor"},
            {"role": "assistant", "content": "OEM AUTHORIZATION FINDINGS\nRequest: replace complete unit"},
            {"role": "user", "content": "Replaced the complete rooftop unit, tested, works"},
        ]
        pin = {"facts": {"complaint_verified": hist[2]["content"]}, "unit": {"model": "Furrion FACR13LPSA2-PS"}}
        return go.warranty_story(pin, hist), hist

    def test_rule10_story_has_no_invented_readings(self):
        story, hist = self._story()
        typed = " ".join(m["content"] for m in hist)
        for num in re.findall(r"\d+(?:\.\d+)?\s*(?:A|VAC|V|F|kOhm)\b", story):
            self.assertIn(num, typed)
        self.assertNotIn("delta", story.lower())

    def test_rule10_three_sections_separate(self):
        story, _ = self._story()
        a, b, c = story.index("1. CUSTOMER COMPLAINT"), story.index("2. ON-ARRIVAL FINDINGS"), story.index("3. TESTS AND READINGS")
        self.assertLess(a, b); self.assertLess(b, c)
        self.assertIn("AC makes grinding noise", story[a:b])
        self.assertIn("Verified: ran it", story[b:c])
        self.assertNotIn("7.27", story[a:c])

    def test_rule10_every_test_cited(self):
        story, _ = self._story()
        tests = story.split("3. TESTS AND READINGS")[1].split("4. CAUSE")[0]
        self.assertIn("7.27 A at 117 VAC", tests)
        self.assertIn("Library: FACR13 Service Manual p.12", tests)
        self.assertIn("OEM AUTHORIZATION", story)
        self.assertIn("Replaced the complete rooftop unit", story.split("5. CORRECTION")[1])

    def test_rule10_reseat_test_is_not_the_correction(self):
        hist = [{"role": "user", "content": "AC noise"}, {"role": "assistant", "content": "1. Reseat plugs [General trade knowledge]"},
                {"role": "user", "content": "Reseated all plugs, all were tight"},
                {"role": "assistant", "content": "OEM AUTHORIZATION FINDINGS"}]
        story = go.warranty_story({"facts": {}}, hist)
        self.assertIn("OPEN - pending OEM authorization", story.split("5. CORRECTION")[1])

    def test_rc30_exact_model_beats_same_brand_12v_fan(self):
        lib = FakeLib([{"id": 283, "title": 'Furrion 14" 12V Vent Fan (V2.0) with Lid Troubleshooting and Service Manual', "models": "FVF14D90A2"},
                       {"id": 186, "title": "Furrion FCR08 FCR10 12V Refrigerator Troubleshooting and Service Manual CCD-0008122"},
                       {"id": 298, "title": "Furrion Arctic 8 & 10 cu.ft. Refrigerator Troubleshooting and Service Manual", "models": "FCR08DCGTA;FCR10DCGTA"}], {})
        unit = go.identify_unit([], "fridge has no power, 12V", "Refrigerators", "Furrion FCR08DCGTA 12V DC refrigerator")
        self.assertIn(go.pin_document(lib, unit)["id"], (186, 298))

    def test_rc30_never_borrows_another_product(self):
        lib = FakeLib([{"id": 283, "title": 'Furrion 14" 12V Vent Fan Troubleshooting and Service Manual', "models": "FVF14D90A2"}], {})
        unit = go.identify_unit([], "fridge no power 12V", "Refrigerators", "Furrion FCR08DCGTA 12V DC refrigerator")
        self.assertIsNone(go.pin_document(lib, unit))
        self.assertNotIn("12v", go.model_tokens("Furrion FCR08DCGTA 12V"))

    def test_rc30_label_diagram_is_used(self):
        pin = {"facts": {}, "turns": 1}
        go.record_facts(pin, "Label/photo shows: wiring diagram, 15A inline fuse on the red lead")
        self.assertIn("label_diagram", pin["facts"])
        chat, store = _chat("1. Check the inline fuse [General trade knowledge]"), {"gd_pin": None}
        go.official_turn("Label shows a 15A fuse on the red lead", "Refrigerators", "Furrion FCR08DCGTA", [], library=FakeLib([], {}), chat_fn=chat, pin_store=store)
        self.assertIn("UNIT LABEL / DIAGRAM", chat.calls[0][0][0]["content"])

    def test_rc30_story_captures_final_correction(self):
        hist = [{"role": "user", "content": "no power"}, {"role": "assistant", "content": "1. Check fuse [Library: CCD-0008122 p.20]"},
                {"role": "user", "content": "15A inline fuse open"}, {"role": "assistant", "content": "Replace the fuse, verify."},
                {"role": "user", "content": "Replaced the 15A inline fuse under the front; fridge powers up and is cooling."}]
        story = go.warranty_story({"facts": {}}, hist)
        self.assertIn("Replaced the 15A inline fuse", story.split("5. CORRECTION")[1])

    def test_cost(self):
        self.assertAlmostEqual(go.turn_cost({"prompt_tokens": 1_000_000, "cached_tokens": 0, "completion_tokens": 0}), 2.0)


if __name__ == "__main__":
    unittest.main()
