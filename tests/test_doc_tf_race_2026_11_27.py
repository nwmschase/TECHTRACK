"""v4.20.5: Library.doc_tf race (test7 2026-11-27: find_documents failed with KeyError 'L166').

Two GD turns ran at once on a cold library; one read the word-count cache while the other was still filling it.
The cache is now built whole and published under the lock, so a second caller waits and gets the full dict."""
import collections, os, sys, threading, time, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pagefinder import search as s
import gd_tools


def slow_library(n=40, delay=0.01):
    lib = s.Library.__new__(s.Library)          # no index file needed: only docs + pages are used by doc_tf
    lib.docs = {f"L{i}": {"doc_id": f"L{i}"} for i in range(n)}
    lib._doc_tf = None
    pages = {k: [{"tf": collections.Counter({"motor": 1, k.lower(): 2})}] for k in lib.docs}
    def _pages(doc_id):
        time.sleep(delay)                        # a cold library reads each doc's pages from sqlite
        return pages[doc_id]
    lib.pages = _pages
    return lib


class TestDocTfRace(unittest.TestCase):
    def test_second_caller_never_sees_a_half_built_cache(self):
        lib = slow_library()
        first = threading.Thread(target=lib.doc_tf)
        first.start()
        time.sleep(0.05)                         # the first build is under way
        got = lib.doc_tf()
        keys_at_return = set(got)                # snapshot now: the old code handed back the dict still being filled
        first.join()
        self.assertEqual(keys_at_return, set(lib.docs))
        self.assertEqual(got["L39"][1], 3)

    def test_find_documents_during_a_cold_build(self):
        lib = slow_library()
        for d in lib.docs.values():
            d.update(title=f"Schwintek controller {d['doc_id']}", brand="Lippert", unit_type="Slideouts", models="[]")
        tools = gd_tools.LibraryTools(lib)
        first = threading.Thread(target=lib.doc_tf)
        first.start()
        time.sleep(0.05)
        r = tools.find_documents(brand="Lippert", unit_type="Slide-outs", words="controller motor", limit=5)
        first.join()
        self.assertNotIn("error", r)
        self.assertTrue(r["documents"])

    def test_stub_and_label_caches_published_whole(self):
        import re
        for f in ("gd_tools.py", os.path.join("pagefinder", "search.py")):
            src = open(os.path.join(ROOT, f)).read()
            bad = re.findall(r"^\s*self\._(?:doc_tf|label_tf) = \{\}\s*$", src, re.M)   # empty cache published, then filled
            self.assertEqual(bad, [], f)


if __name__ == "__main__":
    unittest.main()
