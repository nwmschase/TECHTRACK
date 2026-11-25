"""Chase 2026-11-25 'clean it up' (GD-4 fallback story, offline, no Grok call). Not new story rules: the numbered fallback
log built from the tech's messages
(a) carried his misspellings ('Thermstat', 'cieling', 'fanmotor', 'doesnt', 'pwoerr') -> matched against the words the
    session itself spells; real English words and anything the session never spells stay as he typed;
(b) logged the same 1.91 A / 122 V reading twice (his recap repeats the test) -> one step, the fuller wording, at the place
    the test was first reported, every reading kept;
(c) logged 'I have peacemaker tool ... that I can plug into the control board.' as a step on its own, with the result as the
    next step -> one step describing the test and its result.
Then (Chase 11/25 t1585u-t1587u): "REWRITE THE WORDS INTO THE BEST POSSIBLE STORY", reasonable inferences are fine, and "A
STORY IS A WELL WRITTEN CONCERN CAUSE AND CORRECTION ... NOT A ... BULLETPOINT LIST": the fallback is three paragraphs in
professional past tense, no first person, restated steps told once, his conclusion folded into the cause, the repair told
once in CORRECTION; every reading stays."""
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


def cause(s):
    return gd_story.parse_story(s)["CAUSE"]


def wo_story():
    refs = gd_story.procedure_references(a.case_156231(), a.HIST, a.CITED, page_lookup=a.lookup)
    return gd_story.write_warranty_story(a.case_156231(), a.HIST, "NT-20SEQT", references=refs)


def m1066_story():
    return gd_story.write_warranty_story(m.M1066_CASE, m.M1066, "FCR16DCASA-SS", chat_fn=None)


class TestASpelling(unittest.TestCase):
    def test_gd4_misspellings_take_the_session_spelling(self):
        s = cause(gd4_story())
        for bad in ("Thermstat", "cieling", "fanmotor", " i ", "Its the", "thats", "peacemaker", "12 v "):
            self.assertNotIn(bad, s)
        for good in ("confirmed 12 V at the thermostat", "control box ceiling assembly", "Peacemaker"):
            self.assertIn(good, s)

    def test_real_words_stay(self):
        self.assertIn("the unit was not in low power mode", m1066_story())   # 'pwoerr' fixed, 'low' not made 'Low'
        self.assertIn("filter-drier", m1066_story())
        self.assertIn("did not ignite at all", wo_story())

    def test_unit_words(self):
        vocab = gd_story._session_vocab(["Check the ceiling assembly and the thermostat. Use the Peacemaker tool."])
        self.assertEqual(gd_story._tidy("thermstat at the cieling", vocab), "thermostat at the ceiling")
        self.assertEqual(gd_story._tidy("I measured 12 v at the board", vocab), "Measured 12 V at the board")
        self.assertEqual(gd_story._tidy("though it was working", vocab), "though it was working")
        self.assertEqual(gd_story._tidy("the xqzzy part", vocab), "the xqzzy part")   # nothing near it: left alone


class TestBRepeatedReading(unittest.TestCase):
    def test_191_told_once_with_every_reading(self):
        s = gd4_story()
        self.assertEqual(s.count("1.91 A at 122 V"), 1, s)
        self.assertIn("The fan motor drew about 1.91 A at 122 V, and its shaft was locked.", s)
        self.assertEqual(cause(s).count("122 VAC"), 1)
        self.assertIn("At the control box, I measured 122 VAC input.", s)
        self.assertEqual(gd_story.missing_readings(s, g4.HIST), [])

    def test_order_kept(self):
        c = cause(gd4_story())
        self.assertLess(c.index("plugged into the control board"), c.index("1.91 A"))
        self.assertLess(c.index("1.91 A"), c.index("15.11"))
        self.assertLess(c.index("thermostat"), c.index("trim"))

    def test_different_readings_both_stay(self):
        out = gd_story._drop_repeated_readings(["Battery 12.6 V.", "Battery 12.4 V after load.", "Board 12.6 V at J1."])
        self.assertEqual(out, ["Battery 12.6 V.", "Battery 12.4 V after load."])
        out2 = gd_story._drop_repeated_readings(["It draws 1.91 A at 122 V.", "Fan check.", "It draws 1.91 A at 122 V, shaft locked."])
        self.assertEqual(out2, ["It draws 1.91 A at 122 V, shaft locked.", "Fan check."])


class TestCSetupAndResult(unittest.TestCase):
    def test_tool_sentence_joins_its_result(self):
        s = cause(gd4_story())
        self.assertNotIn("I have", s)
        self.assertIn("With the Peacemaker tool plugged into the control board, the compressor kicked on when commanded but "
                      "the fans did not turn on.", s)
        self.assertNotIn("Peacemaker bypass", s)         # his recap of the same test is told once

    def test_setup_without_a_known_verb_is_left(self):
        self.assertEqual(gd_story._setup_sentence("I have a meter that I can borrow"), "")
        self.assertEqual(gd_story._join_setups(["I have a jumper that I can clip to R and W.", "Fan came on."]),
                         ["With the jumper clipped to R and W, fan came on."])


class TestProseStory(unittest.TestCase):
    def test_three_paragraphs_no_list(self):
        for s in (gd4_story(), wo_story(), m1066_story()):
            sec = gd_story.parse_story(s)
            self.assertEqual(sorted(sec), ["CAUSE", "CONCERN", "CORRECTION"], s)
            for k, v in sec.items():
                self.assertEqual(len([l for l in v.split("\n") if l.strip()]), 1, (k, v))   # one paragraph each
                self.assertEqual(m.numbered(v), [])
                self.assertFalse(v.lstrip().startswith(("- ", "* ", "• ")))

    def test_first_person_past_tense_varied(self):
        # Chase 11/25: "It needs to be first person. its the technicians story not a narration by a third party"
        for s in (gd4_story(), wo_story(), m1066_story()):
            c = " " + cause(s) + " "
            self.assertNotIn("technician", s.lower())
            self.assertIn(" I ", c)
            for bad in (" I'm ", " will ", " doesn't ", " won't ", " draws ", " reads ", " is locked", " am getting"):
                self.assertNotIn(bad, c)
            starts = [x.split(" ", 1)[0] for x in gd_story._sentences(cause(s))]
            run = max((len(list(g)) for k, g in __import__("itertools").groupby(starts) if k == "I"), default=0)
            self.assertLessEqual(run, 2, starts)                    # no I / I / I monotony
        c = cause(gd4_story())
        self.assertIn("I first confirmed 12 V at the thermostat. Next, I removed the trim", c)
        self.assertIn("I had power at the board, but the board was not commanding the fans", c)
        self.assertTrue(gd_story.parse_story(gd4_story())["CORRECTION"].startswith("I replaced"))

    def test_conclusion_folded_and_repair_told_once(self):
        s = gd4_story()
        self.assertNotIn("that's running that bad voltage", s)
        self.assertIn("These results confirmed that the ceiling control/relay board had failed and was not commanding the "
                      "fans, and the fan motor was seized (locked shaft, 1.91 A draw).", s)
        self.assertNotIn("Replaced", cause(s))
        self.assertTrue(gd_story.parse_story(s)["CORRECTION"].startswith("I replaced the ceiling control/relay board and fan motor."))

    def test_every_reading_and_the_checks_pass(self):
        c = gd_story.record_access_answer(g4.case_gd4(), g4.ANSWER, g4.HIST)
        s = gd4_story()
        self.assertEqual(gd_story.story_problems(s, c, g4.HIST), [])
        self.assertEqual(gd_story.missing_readings(m1066_story(), m.M1066), [])
        self.assertEqual(gd_story.story_problems(wo_story(), a.case_156231(), a.HIST), [])

    def test_references_named_in_the_cause(self):
        self.assertIn("My testing followed the Suburban Furnace Service and Training Manual (", cause(wo_story()))
        self.assertIn("I referenced manufacturer documents CCD-0009616", cause(m1066_story()))


if __name__ == "__main__":
    unittest.main()
