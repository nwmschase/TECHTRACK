"""v4.20.5 primer lines (Chase 2026-11-27 t1653u, test7: Grok cited p.11/p.12 it had not opened, sent a web image instead
of opening L6 p.6, and guessed a motor swap instead of finding the harness ohm test in the other Schwintek guides)."""
import os, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestOpenPageLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = open(os.path.join(ROOT, "gd_primer.md"), encoding="utf-8").read()

    def test_open_the_page_line(self):
        self.assertIn("Before giving a test, a reading, or a picture, Grok opens the library page that has it; when the pages "
                      "open so far don't cover it, Grok searches the library again (other manuals for the same unit included) "
                      "before going to the web.", self.p)

    def test_opened_pages_only_line(self):
        self.assertIn("Grok describes only what is on pages it opened in this job; a page seen only in a table of contents "
                      "is not yet read.", self.p)

    def test_both_once_and_web_search_still_offered(self):
        self.assertEqual(self.p.count("Before giving a test, a reading, or a picture"), 1)
        self.assertEqual(self.p.count("Grok describes only what is on pages it opened"), 1)
        self.assertIn("*Web search* (xAI's built-in search)", self.p)


if __name__ == "__main__":
    unittest.main()
