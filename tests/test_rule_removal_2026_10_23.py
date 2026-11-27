"""Chase's direct order (2026-10-23 8:34 AM): no rules. Grok gets one plain primer and the tools; library labels stay.
Offline: scripted fake brain, mocked web, no network, no paid call."""
import json
import os
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_official  # noqa: E402
import gd_pages  # noqa: E402
import gd_prompt  # noqa: E402
import gd_state  # noqa: E402
import gd_turn  # noqa: E402
from gd_pages import Page, StubPageFinder  # noqa: E402
from test_fresh_core import FakeChat, FakeRespond, block, finder, outputs, page, MAN  # noqa: E402

RULE_WORDS = [r"\bRULE \d", r"\bmust\b", r"\bnever\b", r"\bonly\b", r"\balways\b", r"\bdon't\b", r"\bdo not\b", r"\bdo NOT\b",
              r"say so", r"say you don't know", r"no info", r"manufacturer sites only", r"not available in this build",
              r"\bshall\b", r"\bforbid", r"\brequired\b"]


class TestPrimerIsTheOnlyGuidance(unittest.TestCase):
    def test_primer_loads_and_is_about_one_page(self):
        text = (ROOT / "gd_primer.md").read_text(encoding="utf-8")
        self.assertEqual(gd_prompt.PRIMER, text.strip())
        self.assertLess(len(text.split()), 1875)   # 2026-11-24: + "How a diagnosis goes in the trade" (reefer miss); 2026-11-27: + page images / web photos / cited page lines (test1); v4.20.4: + library-first line (test6, Chase t1647u); v4.20.5: + open-the-page and opened-pages-only lines (test7, Chase t1653u)
        for want in ("RV and trailer repair techs", "Page topics", "diagram / drawing / illustration / picture / pic / image / figure",
                     "photo / photograph / picture / pic / image / figure of the actual", "next_part_to_fetch", "web_lookup",
                     "maker's own site first", "forum", "natural first place to look", "does not need to know what is in the library"):
            self.assertIn(want, text)

    def test_system_text_is_primer_plus_state_format_only(self):
        self.assertEqual(gd_prompt.SYSTEM, gd_prompt.PRIMER + "\n\n" + gd_prompt.STATE_FORMAT)
        f = finder()
        msgs = gd_prompt.build_messages(user_msg="hi", history=[], category="Refrigerators", model_text="Acme X1",
                                        pages=f._pages, state=gd_state.new_state())
        self.assertEqual([m["role"] for m in msgs], ["system", "system", "user"])
        self.assertEqual(msgs[0]["content"], gd_prompt.SYSTEM)
        self.assertFalse(hasattr(gd_prompt, "RULES") or hasattr(gd_prompt, "GUIDANCE") or hasattr(gd_prompt, "HISTORY_TURNS"))

    def test_primer_has_no_behavioral_instruction_words(self):
        # v4.20.5: the two sentences Chase approved (t1653u, test7) are exempt by exact text ("only", and a descriptive
        # "don't cover it"); the same words anywhere else still fail.
        approved = ("Grok describes only what is on pages it opened in this job; a page seen only in a table of contents is not yet read.",
                    "when the pages open so far don't cover it,")
        primer = gd_prompt.PRIMER
        for a in approved:
            self.assertIn(a, primer)
            primer = primer.replace(a, "")
        for name, text in (("gd_primer.md", primer), ("STATE_FORMAT", gd_prompt.STATE_FORMAT)):
            for pat in RULE_WORDS:
                self.assertIsNone(re.search(pat, text, re.I if pat.islower() else 0), f"{name}: {pat}")

    def test_whole_conversation_goes_through(self):
        hist = []
        for i in range(10):
            hist += [{"role": "user", "content": f"tech {i}"}, {"role": "assistant", "content": f"gd {i}"}]
        msgs = gd_prompt.build_messages(user_msg="now", history=hist, category="", model_text="", pages=finder()._pages,
                                        state=gd_state.new_state())
        self.assertEqual(len(msgs), 2 + 20 + 1)


class TestNoRuleStringsLeft(unittest.TestCase):
    """The grep check: removed rule markers are gone from the prompt files and the GD core."""
    GD_CORE = ["gd_prompt.py", "gd_turn.py", "gd_pages.py", "gd_state.py", "gd_official.py", "gd_story.py"]

    def test_prompt_files_have_no_rule_strings(self):
        src = (ROOT / "gd_prompt.py").read_text()
        self.assertNotIn("RULE 1", src)
        self.assertNotIn("RULE 2", src)
        self.assertNotIn("[General trade knowledge]", src)
        self.assertNotIn("manufacturer sites only", src.lower())
        self.assertNotIn("none found for this unit", src)
        self.assertNotIn("PAGES FOUND BUT NOT SHOWN", src)

    def test_core_has_no_removed_filters_or_caps(self):
        for f in self.GD_CORE:
            s = (ROOT / f).read_text()
            for pat in (r"import oem_domains", r"oem_domains\.", r"MAX_FETCH_ROUNDS", r"PAGE_BUDGET_PAGES", r"PAGE_BUDGET_CHARS",
                        r"TOC_BUDGET_CHARS", r"REPLY_MAX_TOKENS", r"HISTORY_TURNS", r"_order_while_pending", r"_check_citations",
                        r"not available in this build", r"non-maker sites", r"brand lock"):
                self.assertIsNone(re.search(pat, s), f"{pat} in {f}")
        self.assertFalse((ROOT / "oem_domains.py").exists())


    def test_no_dead_end_and_no_gate_in_the_turn(self):
        # no web tool wired, a lookup asked for: no 'not available' note reaches the brain, and no extra call is made
        f, store = StubPageFinder(), {}
        chat = FakeChat([block(web_lookup="Brinkley Z3100 front jack bracket", summary="a")])
        r = gd_turn.run_turn("front jack", "Leveling", "Brinkley Model Z", [], finder=f, chat_fn=chat, store=store)
        self.assertEqual(r["calls"], 1)
        self.assertNotIn("not available", chat.seen[0][0][1]["content"])
        self.assertEqual(r["mode"], "no_manual")

    def test_order_with_pending_test_is_not_policed(self):
        f, store = finder(), {}
        chat = FakeChat(["Order the fan.\n" + block(pending_test="fan amps", order_part="freezer fan motor", summary="a")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store)
        self.assertEqual(r["calls"], 1)
        self.assertEqual(r["state"]["order_part"], "freezer fan motor")
        self.assertEqual(r["problems"], [])

    def test_any_cited_page_is_recorded(self):
        f, store = finder(), {}
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, store=store, chat_fn=FakeChat(
            ["x\n" + block(cited=[{"doc_id": "L1", "page": "25"}, {"doc_id": "web:irv2.com/t", "page": "1"}], summary="a")]))
        self.assertEqual(len(r["cited"]), 2)
        self.assertEqual(r["problems"], [])


class TestNoCaps(unittest.TestCase):
    def test_all_pages_pass_with_no_cap(self):
        pages = [page(sheet=i, text="x" * 9000) for i in range(1, 30)] + [page(sheet=1, text="dup")]
        kept, not_shown = gd_pages.apply_budget(pages)
        self.assertEqual(len(kept), 29)          # the duplicate (same doc + sheet) is merged, nothing else dropped
        self.assertEqual(not_shown, [])
        self.assertEqual(sum(len(p.text) for p in kept), 29 * 9000)

    def test_a_caller_can_still_set_a_budget(self):
        pages = [page(sheet=i, text="x" * 9000) for i in range(1, 8)]
        kept, not_shown = gd_pages.apply_budget(pages, max_pages=8, max_chars=40_000)
        self.assertEqual([p.sheet for p in kept], [1, 2, 3, 4])
        self.assertEqual(len(not_shown), 3)

    def test_turn_sends_every_page_and_no_token_or_effort_limit(self):
        big = StubPageFinder(manuals=MAN, pages=[page(sheet=i, kind="entry" if i < 3 else "support", text="y" * 12000) for i in range(1, 12)])
        chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": [str(i) for i in range(1, 11)]})],
                            [("read_pages", {"doc_id": "L1", "pages": ["11"]})], "ok\n" + block(summary="s")])
        r = gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=big, respond_fn=chat, store={}, log_path="")
        self.assertEqual(len(r["pages_used"]), 11)
        self.assertEqual(r["not_shown"], [])
        self.assertEqual([s[2] for s in chat.seen], [None, None, None])   # no tool_choice set; no token or effort setting exists
        import inspect, gd_llm
        src = inspect.getsource(gd_llm.respond)
        self.assertNotIn("max_output_tokens", src)
        self.assertNotIn("reasoning", src.split("kwargs = ")[1].split("\n")[0])

    def test_rounds_repeat_until_nothing_new_is_asked(self):
        f, store = finder(), {}
        f._parts["wiring"] = [page(sheet=31, kind="part", text="wiring page")]
        chat = FakeRespond([[("search_pages", {"words": "freezer fan motor"})], [("read_pages", {"doc_id": "L1", "pages": ["31"]})],
                            "Done\n" + block(next_part_to_fetch="wiring", summary="c")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store=store, log_path="")
        self.assertEqual(r["calls"], 3)       # more than the old single extra round
        self.assertIn("wiring page", outputs(chat.seen[2][0])[1]["pages"][0]["text"])


class TestSafetyCeiling(unittest.TestCase):
    def test_turn_stops_at_the_ceiling_when_every_round_asks_for_something_new(self):
        f, store = finder(), {}
        for i in range(10):
            f._parts[f"part{i}"] = [page(sheet=40 + i, kind="part", text=f"page {i}")]
        chat = FakeRespond([[("search_pages", {"words": f"page {i}"})] for i in range(10)])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store=store, log_path="")
        self.assertEqual(r["calls"], gd_turn.SAFETY_CEILING_CALLS)
        self.assertTrue(any("safety ceiling" in p for p in r["problems"]))
        self.assertEqual([s[2] for s in chat.seen][-1], "none")   # the last allowed call goes out with tools off
        for items, *_ in chat.seen:                              # the brain never sees the ceiling
            self.assertNotIn("ceiling", json.dumps(items))


class FakeResp:
    def __init__(self, content=b"", text="", url="", headers=None):
        self.content, self.text, self.url, self.headers = content, text, url, headers or {}


class FakeHttp:
    """Stands in for httpx: get(url) -> FakeResp. No network."""
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, **kw):
        self.calls.append(url)
        r = self.routes[url]
        r.url = r.url or url
        return r


def _pdf_bytes(pages):
    from reportlab.pdfgen import canvas
    import io
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for t in pages:
        for i, line in enumerate(t.split("\n")):
            c.drawString(72, 760 - 16 * i, line)
        c.showPage()
    c.save()
    return buf.getvalue()


class TestWebTool(unittest.TestCase):
    def test_app_side_web_search_is_retired_from_the_gd_path(self):
        # Grok searches the web itself (xAI built-in web_search in its own call, Chase 2026-10-24); gd_official's fetch
        # stays for open_web_document, its make_web_fn / xai_search are no longer wired into GD.
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertNotIn("_gd_web_tool()", src)
        self.assertNotIn("gd_official.make_web_fn(secret_fn=_secret)", src)
        import gd_tools
        self.assertIn({"type": "web_search", "enable_image_search": True, "enable_image_understanding": True},
                      gd_tools.TOOL_SPECS)   # 2026-11-27: image search on (test1)
        self.assertTrue(callable(gd_official.fetch_pages))

    def test_html_page_from_any_host_comes_back_with_url_host_and_revision(self):
        http = FakeHttp({"https://www.irv2.com/forums/t1": FakeResp(
            text="<html><title>Fridge thermistor</title><body><p>Revised: 03/04/2022</p><p>" + "thermistor 10k ohm at 77F " * 80 + "</p></body></html>",
            headers={"content-type": "text/html", "last-modified": "Tue, 01 Mar 2022 10:00:00 GMT"})})
        web = gd_official.make_web_fn(http=http, search_fn=lambda q: [{"url": "https://www.irv2.com/forums/t1", "title": "t"}])
        pages = web("fridge thermistor resistance")
        self.assertEqual(len(pages), 1)
        p = pages[0]
        self.assertEqual((p.kind, p.source, p.host, p.url), ("web", "web", "www.irv2.com", "https://www.irv2.com/forums/t1"))
        self.assertIn("03/04/2022", p.revision)
        self.assertIn("thermistor", p.text)
        self.assertEqual(web.last_errors, [])

    def test_pdf_pages_are_ranked_by_the_words_and_carry_revision(self):
        import shutil
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not installed")
        pdf = _pdf_bytes(["TROUBLESHOOTING GUIDE\nRev: 02/17/25", "Sail switch test\nmeasure 12 V at the sail switch", "Warranty terms and phone numbers"])
        url = "https://lci-support-doc.s3.amazonaws.com/manuals/x/ccd-1.pdf"
        http = FakeHttp({url: FakeResp(content=pdf, headers={"content-type": "application/pdf", "last-modified": "Mon, 17 Feb 2025 16:56:37 GMT"})})
        web = gd_official.make_web_fn(http=http)
        pages = web(url + " sail switch")
        self.assertEqual(pages[0].page, "2")                       # best-matching page first
        self.assertEqual({p.revision for p in pages}, {"Rev 02/17/25"})
        self.assertEqual(pages[0].host, "lci-support-doc.s3.amazonaws.com")
        self.assertEqual(len(http.calls), 1)
        web(url + " sail switch")                                  # same URL and words: served from the tool's cache
        self.assertEqual(len(http.calls), 1)

    def test_xai_search_is_used_when_a_key_exists_and_is_mocked_here(self):
        calls = []

        class Http(FakeHttp):
            def post(self, url, json=None, **kw):
                calls.append((url, json))
                body = {"output": [{"content": [{"type": "output_text", "text": '{"sources": [{"url": "https://www.dometic.com/a", "title": "A", "kind": "maker"}]}'}]}]}

                class R:
                    def json(_):
                        return body
                return R()
        http = Http({"https://www.dometic.com/a": FakeResp(text="<html><title>A</title><body>" + "service " * 400 + "</body></html>",
                                                           headers={"content-type": "text/html"})})
        web = gd_official.make_web_fn(secret_fn=lambda k: "KEY" if k == "XAI_API_KEY" else None, http=http)
        pages = web("dometic furnace sail switch")
        self.assertEqual(calls[0][0], gd_official.XAI_RESPONSES_URL)
        self.assertEqual(calls[0][1]["tools"], [{"type": "web_search"}])        # no allowed_domains filter
        self.assertEqual(pages[0].host, "www.dometic.com")

    def test_web_documents_from_any_site_come_back_with_source_lines(self):
        f, store = finder(), {}
        web_pages = [Page(doc_id="web:irv2.com/t", title="forum thread", page="1", sheet=1, text="FORUM TEXT", kind="web", source="web",
                          url="https://www.irv2.com/forum/t", revision="Last-Modified 2022"),
                     Page(doc_id="web:dometic.com/m.pdf", title="m.pdf", page="3", sheet=3, text="MAKER TEXT", kind="web", source="web",
                          url="https://www.dometic.com/m.pdf", revision="Rev 04/12/23")]
        calls = []

        def fetch(url, words):
            calls.append((url, words))
            return web_pages
        chat = FakeRespond([[("open_web_document", {"url": "https://www.dometic.com/m.pdf", "words": "fan spec"})],
                            "ok [forum]\n" + block(summary="b")])
        r = gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store=store, web_fetch=fetch, log_path="")
        out = outputs(chat.seen[1][0])[0]
        self.assertEqual(calls, [("https://www.dometic.com/m.pdf", "fan spec")])
        self.assertEqual([p["text"] for p in out["pages"]], ["FORUM TEXT", "MAKER TEXT"])
        self.assertEqual(out["pages"][0]["host"], "www.irv2.com")
        self.assertEqual(out["pages"][1]["revision"], "Rev 04/12/23")
        self.assertEqual(r["calls"], 2)
        # next turn: the web pages read come along with their source lines
        chat2 = FakeChat(["ok\n" + block(summary="c")])
        gd_turn.run_turn("next", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat2, store=store, log_path="")
        ctx = chat2.seen[0][0][1]["content"]
        self.assertIn("source https://www.irv2.com/forum/t (host www.irv2.com)", ctx)
        self.assertIn("revision Rev 04/12/23", ctx)

    def test_web_error_and_empty_result_are_reported_as_facts_not_rules(self):
        f, store = finder(), {}

        def boom(q):
            raise RuntimeError("timeout")
        chat = FakeChat([block(web_lookup="x", summary="a"), "ok\n" + block(summary="b")])
        gd_turn.run_turn("E2", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat, store=store, web_fn=boom)
        self.assertEqual(len(chat.seen), 1)   # nothing new arrived, so no redo
        chat2 = FakeChat(["ok\n" + block(summary="c")])
        gd_turn.run_turn("again", "Refrigerators", "Acme X1", [], finder=f, chat_fn=chat2, store=store, web_fn=boom)
        self.assertEqual(len(chat2.seen), 1)


class TestLabelsAndHelpersKept(unittest.TestCase):
    def test_picture_labels_still_in_the_library_data(self):
        tsv = (ROOT / "pagefinder" / "doc_fixes.tsv").read_text(encoding="utf-8")
        self.assertGreaterEqual(tsv.count("diagram / drawing / illustration / picture / pic / image / figure"), 3000)
        self.assertGreaterEqual(tsv.count("photo / photograph / picture / pic / image / figure of the actual component or procedure step"), 900)

    def test_library_page_carries_topics_note_doc_number_and_revision(self):
        p = Page(doc_id="L1", title="Acme Manual", page="5", sheet=5, text="body", topics="diagram / drawing: wiring",
                 note="DOC DEFECT: value is 12 V", doc_number="CCD-1", revision="2024-01-01")
        txt = gd_prompt._pages_block("SELECTED PAGES", [p])
        for want in ("PAGE TOPICS: diagram / drawing: wiring", "PAGE NOTE (reviewed): DOC DEFECT: value is 12 V", "doc no. CCD-1", "revision 2024-01-01"):
            self.assertIn(want, txt)

    def test_search_pages_are_not_filtered_by_maker(self):
        # search_pages hands back every matching page, each labeled with its own doc (no R4 filter, no tier boost)
        other = Page(doc_id="L9", title="Other Maker Service Sheet", page="2", sheet=2, text="OTHER MAKER fan test", kind="part")
        f = StubPageFinder(manuals=MAN, pages=[page(sheet=25, kind="entry", text="fan chart")], parts={"fan": [other]})
        chat = FakeRespond([[("search_pages", {"words": "fan"})], "ok\n" + block(summary="b")])
        gd_turn.run_turn("x", "Refrigerators", "Acme X1", [], finder=f, respond_fn=chat, store={}, log_path="")
        self.assertIn("L9", [h["doc_id"] for h in outputs(chat.seen[1][0])[0]["hits"]])


@unittest.skipUnless(os.environ.get("TT_LIVE_PUBLIC_FETCH") == "1", "set TT_LIVE_PUBLIC_FETCH=1 for the one real public-PDF fetch (plain HTTP, free)")
class TestRealPublicFetch(unittest.TestCase):
    def test_lippert_public_pdf(self):
        web = gd_official.make_web_fn(secret_fn=lambda k: None)
        pages = web("https://lci-support-doc.s3.amazonaws.com/manuals/electronics/onecontrol/ccd-0002117.pdf troubleshooting")
        self.assertTrue(pages)
        self.assertEqual(pages[0].host, "lci-support-doc.s3.amazonaws.com")
        self.assertTrue(pages[0].revision)


if __name__ == "__main__":
    unittest.main()
