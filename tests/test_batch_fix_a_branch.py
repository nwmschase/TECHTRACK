"""Batch fix (a): a manual-built sheet gets a repair branch only when the cited page has removal and installation."""
import unittest

from bay_procedure import manual_repair_branch

PAGE = [{"title": "Kit TI", "page": 2, "excerpt": (
    "Remove the two bolts from the motor cover. Disconnect the motor leads. "
    "Install the new brake on the motor shaft. Reconnect the motor leads. Tighten the two bolts."
)}]


class TestManualRepairBranch(unittest.TestCase):
    def test_branch_has_removal_install_verify(self):
        b = manual_repair_branch(PAGE)
        secs = [s["section"] for s in b["steps"]]
        self.assertIn("removal", secs)
        self.assertIn("installation", secs)
        self.assertEqual(secs[-1], "prove")
        self.assertTrue(b["steps"][-1]["text"].startswith("Confirm"))
        self.assertTrue(any("gloves" in x for x in b["before"]))
        texts = " ".join(s["text"] for s in b["steps"])
        self.assertIn("Remove the two bolts from the motor cover", texts)

    def test_no_branch_without_installation(self):
        page = [{"title": "x", "page": 1, "excerpt": "Remove the cover. Check the fuse at the panel."}]
        self.assertIsNone(manual_repair_branch(page))


if __name__ == "__main__":
    unittest.main()
