"""v4.20.8 (Chase t1725u, 2026-11-28): an empty page search opens the web gate; word-match scores are not halved.
v4.20.13: the meaning (smart) search was deleted, so the switch / model / log tests of this file went with it (the guard
tests/test_gd_v42013_2026_11_28.py fails if it comes back). No paid calls."""
import json
import os
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import gd_pages  # noqa: E402
import gd_tools  # noqa: E402
import gd_turn  # noqa: E402
from test_fresh_core import block  # noqa: E402
from test_gd_v4207_2026_11_28 import finder, turn, web_names  # noqa: E402

INDEX = os.environ.get("TT_PAGEFINDER_DIR", str(ROOT / "pagefinder" / "index"))


class TestEmptySearchOpensTheWebGate(unittest.TestCase):
    def test_nonsense_query_on_pages_returns_empty(self):
        T = gd_tools.LibraryTools.for_finder(finder())
        r = T.search_pages("zzqxv flurble wompus")
        self.assertEqual(r.get("hits"), [])
        self.assertEqual(r.get("matching_pages"), 0)
        why = gd_turn.library_empty_reason("search_pages", {"words": "zzqxv flurble wompus"}, json.dumps(r))
        self.assertTrue(why)

    def test_nonsense_query_on_real_library_returns_empty(self):
        f = gd_pages.LibraryPageFinder(INDEX)
        T = gd_tools.LibraryTools.for_finder(f)
        r = T.search_pages("zzqxv flurble wompus")
        self.assertEqual(r.get("hits"), [])
        self.assertEqual(r.get("matching_pages"), 0)

    def test_empty_library_search_opens_the_web_gate(self):
        r, chat = turn([[("search_pages", {"words": "zzqxv flurble wompus"})], "ok\n" + block(summary="s")])
        self.assertTrue(web_names(chat.seen[-1][1]))
        self.assertIn(gd_turn.T_WEB_GATE_OPENED, [t["trigger"] for t in r["triggers"]])

    def test_picture_lookup_still_finds_a_labelled_page(self):
        store = {}
        turn([[("find_documents", {"unit_type": "refrigerator"})], "ok\n" + block(summary="s")], store=store)
        r, _chat = turn(["Here is the fan.\n" + block(summary="s")], store=store, msg="send me a photo of the fan motor",
                        picture_request=True)
        self.assertIn(gd_turn.T_APP_PICTURE_PAGE, [t["trigger"] for t in r["triggers"]])
        self.assertIn(("L1", "31"), [(c["doc_id"], c["page"]) for c in r["cited"]])

    def test_lone_word_match_is_not_halved(self):
        """A 0.5 blend toward zeros would cap a lone word-match at 0.5 and could hide a hit behind score>0."""
        T = gd_tools.LibraryTools.for_finder(finder())
        r = T.search_pages("E2 freezer fan")
        self.assertTrue(r.get("hits"))
        top = r["hits"][0]["score"]
        self.assertGreater(top, 0.5)
        self.assertLessEqual(top, 1.0)


if __name__ == "__main__":
    unittest.main()
