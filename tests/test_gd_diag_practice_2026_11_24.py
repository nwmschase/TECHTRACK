"""2026-11-24 live v4.20 smoke miss: FCR16DCASA-SS 'not getting cold' at 40F outside. GD read L284 p11 (working range 50-110F),
blamed the cold weather and told the tech no other troubleshooting was needed; the real fault was a dead evaporator fan.
Fix (no rules, per Chase 10/23): the primer describes how a diagnosis goes in the trade. Offline only."""
import pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import gd_prompt  # noqa: E402
from test_rule_removal_2026_10_23 import RULE_WORDS  # noqa: E402

PARA = gd_prompt.PRIMER.split("**How a diagnosis goes in the trade.**", 1)


class TestDiagnosisPractice(unittest.TestCase):
    def test_paragraph_is_in_the_system_text(self):
        self.assertEqual(len(PARA), 2)
        self.assertIn("**How a diagnosis goes in the trade.**", gd_prompt.SYSTEM)

    def para(self):
        return PARA[1].split("**The library.**", 1)[0]

    def test_ranked_list_and_next_check(self):
        p = self.para()
        for want in ("short list of likely causes, ranked", "next check", "stays open until a test rules it out"):
            self.assertIn(want, p)

    def test_operating_range_is_a_limit_not_a_cause(self):
        p = self.para()
        self.assertIn("working temperature range is a limit", p)
        self.assertIn("in the direction that produces that symptom", p)
        self.assertIn("cold weather keeps a refrigerator box cold", p)

    def test_not_cooling_list_covers_the_real_causes(self):
        p = self.para().lower()
        for part in ("evaporator fan", "frost on the coil", "condenser fan", "airflow", "voltage", "door seals",
                     "temperature sensors", "control board", "compressor", "sealed system"):
            self.assertIn(part, p)

    def test_no_rule_words(self):
        p = self.para()
        for pat in RULE_WORDS:
            self.assertIsNone(re.search(pat, p, re.I if pat.islower() else 0), pat)


# Reefer case for the next paid real-Grok check (not run offline):
REEFER_CASE = dict(category="Refrigerators", model="FCR16DCASA-SS",
                   complaint="CUSTOMER STATES THAT THE REFER IS NOT GETTING COLD. CUSTOMER WAS OUT IN 40 DEGREE WEATHER AND THE "
                             "REFER WOULD NOT GET BELOW 42 DEGREES.",
                   bad=["outside its design range", "No other troubleshooting"], want_any=["evaporator fan", "fan"])

if __name__ == "__main__":
    unittest.main()
