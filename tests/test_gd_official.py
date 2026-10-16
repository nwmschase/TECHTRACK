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
        self.assertIn("will not use another brand", r["reply"])

    def test_official_domains_only(self):
        self.assertTrue(go.url_is_official("https://www.lci1.com/x.pdf", "lippert"))
        self.assertTrue(go.url_is_official("https://corporate.lippert.com/a.pdf", "lippert"))
        self.assertFalse(go.url_is_official("https://www.manualslib.com/a.pdf", "lippert"))
        self.assertFalse(go.url_is_official("https://lci1.com.evil.net/a.pdf", "lippert"))


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

    def test_cost(self):
        self.assertAlmostEqual(go.turn_cost({"prompt_tokens": 1_000_000, "cached_tokens": 0, "completion_tokens": 0}), 2.0)


if __name__ == "__main__":
    unittest.main()
