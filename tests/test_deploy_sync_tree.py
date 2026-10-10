"""Community Cloud's push sync reads the repo root as UTF-8 text."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDeploySyncTree(unittest.TestCase):
    def test_word_list_is_utf8_text_at_repo_root(self):
        path = ROOT / "bay_words.txt"
        raw = path.read_bytes()
        # 1f 8b is gzip. A root-level gzip file makes the GitHub sync skip redeploy.
        self.assertFalse(raw.startswith(b"\x1f\x8b"))
        text = raw.decode("utf-8")
        self.assertIn("\nwill\n", text)
        self.assertIn("\ngo\n", text)
        self.assertEqual(list(ROOT.glob("*.gz")), [])
        source = (ROOT / "bay_procedure.py").read_text(encoding="utf-8")
        self.assertIn('with_name("bay_words.txt")', source)
        self.assertNotIn("bay_words.txt.gz", source)
        self.assertNotIn("import gzip", source)

    def test_ignore_rules_use_a_dotted_gitignore(self):
        self.assertTrue((ROOT / ".gitignore").is_file())
        self.assertFalse((ROOT / "gitignore").exists())
