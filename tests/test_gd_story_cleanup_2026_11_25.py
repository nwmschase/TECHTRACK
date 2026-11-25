"""Chase 2026-11-25 'clean it up' (GD-4 fallback story, offline, no Grok call). Not new story rules: the numbered fallback
log built from the tech's messages
(a) carried his misspellings ('Thermstat', 'cieling', 'fanmotor', 'doesnt', 'pwoerr') -> matched against the words the
    session itself spells; real English words and anything the session never spells stay as he typed;
(b) logged the same 1.91 A / 122 V reading twice (his recap repeats the test) -> one step, the fuller wording, at the place
    the test was first reported, every reading kept;
(c) logged 'I have peacemaker tool ... that I can plug into the control board.' as a step on its own, with the result as the
    next step -> one step describing the test and its result."""
import pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "tests"))
import gd_story  # noqa: E402
import test_gd_story_gd4_2026_11_24 as g4  # noqa: E402
import test_gd_story_access_2026_11_24 as a  # noqa: E402
import test_gd_story_complaint_2026_11_24 as m  # noqa: E402


def gd4_story():
    c = gd_story.record_access_answer(g4.case_gd4(), g4.ANSWER, g4.HIST)
    return gd_story.write_warranty_story(c, g4.HIST + [g4.CHAT[g4.ACCESS_Q_AT + 1]], "")


def log(s):
    return s.split("2. CAUSE - DIAGNOSTIC TEST LOG", 1)[1].split("Confirmed cause:", 1)[0]


class TestASpelling(unittest.TestCase):
    def test_gd4_misspellings_take_the_session_spelling(self):
        s = log(gd4_story())
        for bad in ("Thermstat", "cieling", "fanmotor", " i found", "Its the", "thats", "peacemaker", "12 v "):
            self.assertNotIn(bad, s)
        for good in ("1. Thermostat 12 V confirmed.", "control box ceiling assembly", "Replaced fan motor and control board",
                     "I found no voltage", "It's the fan motor that's running", "Peacemaker"):
            self.assertIn(good, s)

    def test_real_words_and_tech_wording_stay(self):
        s = log(gd4_story())
        self.assertIn("all working as designed", s)             # 'working' is a word: never 'wiring'
        m1066 = gd_story.write_warranty_story(m.M1066_CASE, m.M1066, "FCR16DCASA-SS", chat_fn=None)
        self.assertIn("not in low power mode, seals are all good", m1066)   # 'pwoerr' fixed, 'low' not made 'Low'
        self.assertIn("filter-drier", m1066)

    def test_other_jobs(self):
        refs = gd_story.procedure_references(a.case_156231(), a.HIST, a.CITED, page_lookup=a.lookup)
        s = gd_story.write_warranty_story(a.case_156231(), a.HIST, "NT-20SEQT", references=refs)
        self.assertIn("doesn't ignite at all", s)

    def test_unit_words(self):
        vocab = gd_story._session_vocab(["Check the ceiling assembly and the thermostat. Use the Peacemaker tool."])
        self.assertEqual(gd_story._tidy("thermstat at the cieling", vocab), "thermostat at the ceiling")
        self.assertEqual(gd_story._tidy("I measured 12 v at the board", vocab), "Measured 12 V at the board")
        self.assertEqual(gd_story._tidy("though it was working", vocab), "though it was working")
        self.assertEqual(gd_story._tidy("the xqzzy part", vocab), "the xqzzy part")   # nothing near it: left alone


class TestBRepeatedReading(unittest.TestCase):
    def test_191_logged_once_with_every_reading(self):
        s = gd4_story()
        self.assertEqual(s.count("1.91 A at 122 V"), 1, s)
        self.assertIn("It draws about 1.91 A at 122 V, and the shaft is locked.", s)
        self.assertEqual(log(s).count("122 VAC"), 1)
        self.assertEqual(gd_story.missing_readings(s, g4.HIST), [])

    def test_order_kept_at_first_report(self):
        steps = [l for l in log(gd4_story()).split("\n") if l[:1].isdigit()]
        i_peace = next(n for n, l in enumerate(steps) if "plugged into the control board" in l)
        i_draw = next(n for n, l in enumerate(steps) if "1.91 A" in l)
        i_cap = next(n for n, l in enumerate(steps) if "15.11" in l)
        self.assertLess(i_peace, i_draw)
        self.assertLess(i_draw, i_cap)

    def test_different_readings_both_stay(self):
        out = gd_story._drop_repeated_readings(["Battery 12.6 V.", "Battery 12.4 V after load.", "Board 12.6 V at J1."])
        self.assertEqual(out, ["Battery 12.6 V.", "Battery 12.4 V after load."])   # 12.6 V repeated: logged once
        out2 = gd_story._drop_repeated_readings(["It draws 1.91 A at 122 V.", "Fan check.", "It draws 1.91 A at 122 V, shaft locked."])
        self.assertEqual(out2, ["It draws 1.91 A at 122 V, shaft locked.", "Fan check."])


class TestCSetupAndResult(unittest.TestCase):
    def test_tool_sentence_joins_its_result(self):
        s = log(gd4_story())
        self.assertNotIn("I have peacemaker tool", s)
        self.assertNotIn("I have Peacemaker tool", s)
        self.assertIn("With the Peacemaker tool plugged into the control board, the compressor will kick on when commanded "
                      "but the fans do not turn on.", s)

    def test_setup_without_a_known_verb_is_left(self):
        self.assertEqual(gd_story._setup_sentence("I have a meter that I can borrow"), "")
        self.assertEqual(gd_story._join_setups(["I have a jumper that I can clip to R and W.", "Fan came on."]),
                         ["With the jumper clipped to R and W, fan came on."])


if __name__ == "__main__":
    unittest.main()
