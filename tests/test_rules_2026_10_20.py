"""Chase's approved rules R2-R5 (CHASE-RULE-DECISIONS-2026-10-20) as state/data checks. Offline, scripted fake brain."""
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_prompt  # noqa: E402
import gd_turn  # noqa: E402
import oem_domains  # noqa: E402
from gd_pages import Page  # noqa: E402
from test_fresh_core import FakeChat, block, finder  # noqa: E402



def web_page(url, text="web text"):
    p = Page(doc_id="W", title="web", page="1", sheet=1, text=text, kind="web")
    p.url = url
    return p


class TestR3NoOrderWhileTestPending(unittest.TestCase):
    def test_order_with_pending_test_gets_one_redo_then_is_not_recorded(self):
        f, store = finder(), {}
        chat = FakeChat(["Order the fan.\n" + block(pending_test="fan amps", order_part="freezer fan motor", summary="a"),
                         "Order it anyway.\n" + block(pending_test="fan amps", order_part="freezer fan motor", summary="b")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store)
        self.assertEqual(r["calls"], 2)
        self.assertIn("still pending", chat.seen[1][0][1]["content"])
        self.assertEqual(r["state"]["order_part"], "")
        self.assertTrue(any(p.startswith("R3:") for p in r["problems"]))

    def test_redo_that_finishes_the_test_first_is_kept(self):
        f, store = finder(), {}
        chat = FakeChat([block(pending_test="fan amps", order_part="freezer fan motor", summary="a"),
                         "Measure fan amps first.\n" + block(pending_test="fan amps", order_part="", summary="b")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store)
        self.assertEqual(r["reply"], "Measure fan amps first.")
        self.assertFalse(any(p.startswith("R3:") for p in r["problems"]))

    def test_order_after_test_cleared_passes_and_does_not_carry_over(self):
        f, store = finder(), {}
        r = gd_turn.run_turn("0 A at the fan with 12 V", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat(["Order a fan.\n" + block(pending_test="", order_part="freezer fan motor", summary="a")]))
        self.assertEqual(r["calls"], 1)
        self.assertEqual(r["state"]["order_part"], "freezer fan motor")
        r = gd_turn.run_turn("ok", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat(["ok\n" + block(summary="b")]))
        self.assertEqual(r["state"]["order_part"], "")


class TestR5CitationCheck(unittest.TestCase):
    def test_cited_page_not_shown_is_dropped_logged_and_told_next_turn(self):
        f, store = finder(), {}
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, store=store, chat_fn=FakeChat(
            ["x\n" + block(cited=[{"doc_id": "L1", "page": "25"}, {"doc_id": "L1", "page": "99"}, {"doc_id": "L1", "page": "2"}], summary="a")]))
        self.assertEqual(r["cited"], [{"doc_id": "L1", "page": "25"}, {"doc_id": "L1", "page": "2"}])  # entry page + TOC page
        self.assertTrue(any(p.startswith("R5:") and "p.99" in p for p in r["problems"]))
        chat = FakeChat(["y\n" + block(summary="b")])
        gd_turn.run_turn("ok", "Refrigerators", "Acme X1", [], finder=f, store=store, chat_fn=chat)
        self.assertIn("L1 p.99, which you were not shown", chat.seen[0][0][1]["content"])

    def test_page_shown_on_an_earlier_turn_counts(self):
        f, store = finder(), {}
        gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, store=store,
                         chat_fn=FakeChat([block(next_part_to_fetch="freezer fan motor", summary="a"), "t\n" + block(summary="a2")]))
        r = gd_turn.run_turn("ok", "Refrigerators", "Acme X1", [], finder=f, store=store,
                             chat_fn=FakeChat(["z\n" + block(cited=[{"doc_id": "L1", "page": "29"}], summary="b")]))
        self.assertEqual(r["cited"], [{"doc_id": "L1", "page": "29"}])
        self.assertFalse(r["problems"])


class TestR2OemWebOnly(unittest.TestCase):
    def test_allowlist(self):
        self.assertTrue(oem_domains.allowed("https://www.lci1.com/support/manual.pdf"))
        self.assertTrue(oem_domains.allowed("https://dometic.com/x"))
        for bad in ("https://www.irv2.com/forums/x", "https://www.etrailer.com/x", "https://notdometic.com/x",
                    "https://dometic.com.evil.net/x", "", "not a url"):
            self.assertFalse(oem_domains.allowed(bad), bad)

    def test_only_maker_pages_reach_the_brain(self):
        f, store = finder(), {}
        web = lambda q: [web_page("https://www.dometic.com/manual.pdf", "MAKER PAGE TEXT"),
                         web_page("https://www.irv2.com/forum/t", "FORUM PAGE TEXT")]
        chat = FakeChat([block(web_lookup="acme fan spec", summary="a"), "ok\n" + block(summary="b")])
        gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store, web_fn=web)
        got = store["gd_case"]["web_pages"]["acme fan spec"]
        self.assertEqual([g["text"] for g in got], ["MAKER PAGE TEXT"])
        self.assertIn("non-maker sites were left out", chat.seen[1][0][1]["content"])


class TestPromptAlignment(unittest.TestCase):
    def test_new_rules_are_in_and_say_you_dont_know_is_out(self):
        sys_txt = gd_prompt.SYSTEM if hasattr(gd_prompt, "SYSTEM") else gd_prompt.build_messages(
            user_msg="x", history=[], category="", model_text="", picked=finder().pick_manual("", "", ""), toc=[], pages=[],
            not_shown=[], state=gd_turn.gd_state.new_state())[0]["content"]
        low = sys_txt.lower()
        self.assertNotIn("say you don't know", low)
        self.assertNotIn("say you do not know", low)
        for want in ("[general trade knowledge]", "order_part", "pending", "authorization", "phone number"):
            self.assertIn(want, low)


if __name__ == "__main__":
    unittest.main()
