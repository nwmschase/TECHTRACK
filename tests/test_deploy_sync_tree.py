"""Community Cloud's push sync reads the repo root as UTF-8 text."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDeploySyncTree(unittest.TestCase):

    def test_ignore_rules_use_a_dotted_gitignore(self):
        self.assertTrue((ROOT / ".gitignore").is_file())
        self.assertFalse((ROOT / "gitignore").exists())
