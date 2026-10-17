"""Leader 2026-10-17 05:50 PT rulings O1-O6 (PR #92, branch cursor/selector-root-fix). Locked, verbatim where a transcript exists.

O1  A tech-recorded repair with its own basis counts as the fix; post-repair release/verify checks never trigger the hold.
O2  Condition (1) wins over the S20 card (see tests/test_v41929_levelup_leadjack.py): 'coil tests good' rules the coil out; the
    cartridge call needs a CITED manual elimination path, else HOLD then escalate.
O3  An OEM request is not authorization (a replace needs a recorded go-ahead). Before any OEM / whole-unit request, the cheaper
    decisive upstream tests must be done or recorded as not possible.
O4  The latest result per part wins; no invented readings.
O5  A contact line is name + number only.
O6  No brand words in GD logic; contact name / escalation brand come from the pinned document's metadata.
GD code never sees a case id, a brand list or a doc id; fixtures are byte-for-byte transcript text (tests/fixtures_leader_0550.py)."""
import os
import random
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402
from tests import fixtures_leader_0550 as F  # noqa: E402

NO_MANUAL = "NO Suburban NT-20SEQT MANUAL in the shop library or on an official OEM site. Every step must be tagged [General trade knowledge]."


def _tech(turns, n):
    return [t for t, _ in turns[:n]]


def _hist(turns, n):
    return [m for t, g in turns[:n] for m in ({"role": "user", "content": t}, {"role": "assistant", "content": g})]


class TestO1RecordedRepairIsTheFix(unittest.TestCase):
    """6753d23 RC04 (verbatim): 'drop across the 30A breaker' (T5) is the breaker's own failing result; T6 'Replaced the 30A breaker;
    ... Auto Level completed'; the Ah test 'not done (customer pickup)' first appears in that repair message. 6753d23 held at T6/T7 and
    parked at T8 with 'no fix reached'."""

    def test_rc04_breaker_repair_is_recorded(self):
        rr = go.recorded_repair(_tech(F.RC04_675_TURNS, 6), "", {})
        self.assertIsNotNone(rr)
        self.assertEqual(rr[0], 5)
        self.assertIn("breaker", rr[1])
        self.assertIn("Replaced the 30A breaker", rr[2])

    def test_rc04_post_repair_ah_test_never_holds(self):
        for n in (6, 7, 8):
            pairs = go.session_tests(_hist(F.RC04_675_TURNS, n - 1), F.RC04_675_TURNS[n - 1][0])
            pts = go.pending_tests(pairs, "")
            self.assertTrue([p for p in pts if "Ah test" in p.text], n)  # it IS a pending test ...
            pin = {}
            left = go.drop_post_repair_checks(pts, [a for _, a in pairs], "", pin)
            self.assertFalse([p for p in left if "Ah test" in p.text], n)  # ... but a post-repair check: it never holds
            self.assertIn("Battery amp-draw/Ah test not done (customer pickup).", pin["post_repair_checks"])

    def test_rc04_summary_names_the_repair(self):
        class _T:
            text = "Battery amp-draw/Ah test not done (customer pickup)."
            scope = {"battery", "touchpad"}
        summ = go.escalation_summary([_T()], _tech(F.RC04_675_TURNS, 8), {}, [], True)
        self.assertNotIn("no fix reached", summ)
        self.assertIn("repair recorded", summ)
        self.assertRegex(summ, r"30A breaker|Breaker already replaced")

    def test_repair_without_its_own_basis_is_not_the_fix(self):
        tech = ["Customer says the slide will not move.", "Motor connector looks OK.", "Replaced the slide motor; slide moves now."]
        self.assertIsNone(go.recorded_repair(tech, "", {}))

    def test_complaint_still_present_cancels_the_repair(self):
        tech = ["Customer says the slide will not move.", "The slide motor reads open.", "Replaced the slide motor.",
                "Slide still will not move."]
        self.assertIsNone(go.recorded_repair(tech, "", {}))

    def test_pending_test_before_the_repair_still_holds(self):
        tech = ["Customer says the slide will not move.", "Voltage at the slide motor is still pending.", "The slide motor reads open.",
                "Replaced the slide motor."]
        pt = [go.PendingTest("Voltage at the slide motor is still pending.", [], {"motor"}, set(), 1)]
        self.assertEqual(go.drop_post_repair_checks(pt, tech, "", {}), pt)


class TestO2CartridgeNeedsACitedPath(unittest.TestCase):
    """Condition (1) wins: a pass on the coil never condemns the cartridge; only a cited manual elimination path does."""
    TECH = ["Customer says the front jacks drift when other circuits pressurize.", "Front-left solenoid coil tests good."]

    def test_coil_good_alone_holds_the_cartridge(self):
        out, held = go.condemn_gate("Replace the front-left cartridge valve. [General trade knowledge]", self.TECH, "")
        self.assertTrue(held)
        self.assertNotRegex(out, r"(?m)^Replace the front-left cartridge valve")
        self.assertRegex(out, r"OEM / shop tech line")  # held, then the escalation path

    def test_cited_elimination_path_allows_it(self):
        page = ("[PAGE 15]\nIf the coil tests good and the jack still drifts, the cartridge valve is leaking by. "
                "Replace the cartridge valve.")
        line = "Replace the front-left cartridge valve. [Library: Level Up Towable Owner's Manual p.15]"
        basis = go.condemn_basis(line, "front-left cartridge valve", self.TECH, page, False, line)
        self.assertEqual(basis[0], "elimination", basis)


class TestO3OemRequestAndUpstreamTests(unittest.TestCase):
    OEM_BLOCK = ("OEM AUTHORIZATION FINDINGS\nComplaint verified (how): no cooling.\nRuled out: fans.\n"
                 "Requested authorization: replace complete rooftop unit.")

    def test_request_line_is_not_a_replace_order(self):
        reply = "Document the findings and submit them to the OEM for authorization to replace the rooftop unit.\n" + self.OEM_BLOCK
        out, held = go.condemn_gate(reply, ["Customer says no cooling.", "Fans look normal/OK."], "")
        self.assertFalse(held, out)

    def test_replace_order_without_goahead_is_held(self):
        reply = "Replace the compressor now. [General trade knowledge]\n" + self.OEM_BLOCK
        tech = ["Customer says no cooling.", "Fans look normal/OK.", "Submitted the findings to the OEM; waiting on a reply."]
        out, held = go.condemn_gate(reply, tech, "", {})
        self.assertTrue([h for h in held if "compressor" in h[0]], out)

    def test_recorded_goahead_licenses_the_replace(self):
        reply = "Replace the compressor now; the OEM approved it. [General trade knowledge]\n" + self.OEM_BLOCK
        tech = ["Customer says no cooling.", "Fans look normal/OK.", "The OEM approved the compressor replacement, authorization number 4471."]
        self.assertTrue(go.oem_goahead(tech))
        out, held = go.condemn_gate(reply, tech, "", {})
        self.assertFalse([h for h in held if "compressor" in h[0]], out)

    def test_goahead_from_the_documents_own_brand(self):
        tech = ["Customer says no heat.", "Acme approved the board swap."]
        self.assertFalse(go.oem_goahead(tech))
        self.assertTrue(go.oem_goahead(tech, "acme"))
        self.assertFalse(go.oem_goahead(["Complaint.", "Waiting for Acme to approve it."], "acme"))

    def test_rc13_thermostat_test_before_the_oem_request(self):
        """6753d23 RC13 T8 (verbatim): the OEM block went out with the thermostat named (wall tstat) and never tested; the
        thermostat bypass is the cheaper decisive upstream test."""
        tech, gd = _tech(F.RC13_675_TURNS, 8), F.RC13_675_TURNS[7][1]
        pin = {}
        out, up = go.oem_upstream_gate(gd, tech, NO_MANUAL, pin)
        self.assertEqual(up, ["thermostat"])
        self.assertNotIn("OEM AUTHORIZATION FINDINGS", out)
        self.assertNotIn("Requested authorization", out)
        self.assertIn("no result is recorded for the thermostat", out)
        go.oem_upstream_gate(gd, tech, NO_MANUAL, pin)
        out3, up3 = go.oem_upstream_gate(gd, tech, NO_MANUAL, pin)  # asked twice: the request goes out, test listed as not done
        self.assertEqual(up3, [])
        self.assertIn("Requested authorization", out3)
        self.assertIn("listed as not done", out3)

    def test_recorded_not_possible_releases_the_request(self):
        tech = _tech(F.RC13_675_TURNS, 8) + ["Thermostat bypass at the furnace cannot be done - no access to the wall run."]
        out, up = go.oem_upstream_gate(F.RC13_675_TURNS[7][1], tech, NO_MANUAL, {})
        self.assertEqual(up, [])
        self.assertIn("OEM AUTHORIZATION FINDINGS", out)

    def test_with_a_manual_only_its_own_tests_gate(self):
        sec = "[PAGE 4]\nTest the thermostat with a jumper across R and W."
        tech = ["Customer says no heat.", "Thermostat set to heat.", "Board has 12 V; blower looks normal/OK."]
        out, up = go.oem_upstream_gate(self.OEM_BLOCK, tech, sec, {})
        self.assertEqual(up, ["thermostat"])
        self.assertIn("jumper across R and W", out)
        out, up = go.oem_upstream_gate(self.OEM_BLOCK, ["Customer says no heat.", "Igniter set aside."], sec, {})
        self.assertEqual(up, [])  # the manual gives no igniter test: not a gating upstream test


class TestO4LatestResultWins(unittest.TestCase):
    def test_rc12_t5_thermostat_install_is_held(self):
        """6753d23 RC12 T5 (verbatim): the thermostat was never recorded as failed ('isn't recorded as open/short or failed ...; that
        check looks normal/OK'); the case file has no thermostat reading. 6753d23 read the negated sentence as a failure."""
        tech, gd = _tech(F.RC12_675_TURNS, 5), F.RC12_675_TURNS[4][1]
        self.assertEqual(go.own_failing_result({"thermostat"}, tech), "")
        out, held = go.condemn_gate(gd, tech, "", {})
        self.assertTrue([h for h in held if "thermostat" in h[0]])

    def test_negated_failure_list_is_not_a_failure(self):
        self.assertFalse(go._is_failing("Thermostat 2021128850 itself isn\u2019t recorded as open/short or failed in the notes;"))
        self.assertTrue(go._is_failing("Fan does not rotate (shaft locked)."))
        self.assertTrue(go._is_failing("The fuse reads open."))

    def test_later_pass_cancels_earlier_fail(self):
        tech = ["Complaint.", "The relay reads open.", "Reseated it; the relay now tests good."]
        self.assertEqual(go.latest_result({"relay"}, tech)[0], "pass")
        out, held = go.condemn_gate("Replace the relay. [General trade knowledge]", tech, "")
        self.assertTrue(held)

    def test_later_fail_wins_over_earlier_pass(self):
        tech = ["Complaint.", "The relay tests good.", "The relay reads open under load."]
        self.assertEqual(go.latest_result({"relay"}, tech)[0], "fail")

    def test_connector_or_seating_pass_does_not_cancel(self):
        for later in ("Relay plugs look seated and OK.", "Relay wiring looks OK.", "Relay was seated.", "Relay holder fit looks OK."):
            tech = ["Complaint.", "The relay reads open.", later]
            self.assertEqual(go.latest_result({"relay"}, tech)[0], "fail", later)

    def test_not_recorded_is_not_a_pass(self):
        tech = ["Complaint.", "The relay reads open.", "Relay continuity check isn\u2019t in the notes and looks normal/OK."]
        self.assertEqual(go.latest_result({"relay"}, tech)[0], "fail")


class TestO5ContactIsNameAndNumber(unittest.TestCase):
    LINE = ("Shop/OEM tech-line 423-775-2131 ext. 7102 if brown still not 10.5\u201313.5 VDC after board swap. "
            "[Library: Suburban Water Heater Master Service and Training Manual p.3]")  # 6753d23 hold set RC22 T9

    def test_contact_from_doc_brand(self):
        self.assertEqual(go.contact_name_number(self.LINE, {"doc_brand": "suburban"}), "Suburban tech line: 423-775-2131 ext. 7102")

    def test_contact_without_brand_keeps_the_lines_name(self):
        c = go.contact_name_number(self.LINE, {})
        self.assertTrue(c.endswith("423-775-2131 ext. 7102"), c)
        self.assertNotRegex(c, r"brown|board|VDC|if ")

    def test_escalation_summary_contact_line(self):
        class _T:
            text = "Brown-wire voltage during TFI is still pending."
            scope = {"board", "valve"}
        summ = go.escalation_summary([_T()], ["Complaint.", "Brown-wire voltage during TFI is still pending."],
                                     {"doc_brand": "suburban"}, [self.LINE], True)
        line = [ln for ln in summ.splitlines() if "Contact:" in ln][0]
        self.assertRegex(line, r"Contact: Suburban tech line: 423-775-2131 ext\. 7102\.?\s*(?:\[|$)")
        self.assertNotIn("brown still", line)


class TestO6NoBrandWordsInLogic(unittest.TestCase):
    def test_no_known_brand_in_gate_regexes(self):
        for rx in (go.ESCALATED_RE, go.GOAHEAD_RE, go.GOAHEAD_SOURCE_RE, go.OEM_PATH_RE, go.OEM_REQUEST_LINE_RE, go.WHOLE_UNIT_REQ_RE):
            for b in go.KNOWN_BRANDS:
                self.assertNotRegex(rx.pattern.lower(), r"(?<![a-z])" + re.escape(b.lower()) + r"(?![a-z])", (rx.pattern[:60], b))

    def test_escalation_brand_comes_from_doc_metadata(self):
        msg = "Already called Lippert/Brinkley with those findings. Plumbing check at the front-left hoses is still pending; no parts replaced."
        self.assertFalse(go.escalated(msg, {}))
        self.assertTrue(go.escalated(msg, {"doc_brand": "lippert"}))
        self.assertTrue(go.escalated("Already called the tech line with the same findings.", {}))

    def test_pin_brand_is_the_documents(self):
        self.assertEqual(go._doc_brand({"title": "Suburban Water Heater Master Service and Training Manual", "brand": ""}), "suburban")
        self.assertEqual(go._doc_brand({"title": "Electric Leveling System User Manual (Travel Trailer)", "brand": ""}), "")


class TestPropertyO1toO4(unittest.TestCase):
    """Random sessions over generic parts: (a) the LATEST own result decides the condemn; (b) a post-repair check never holds;
    (c) an OEM block with a named, untested upstream part is withheld until tested / recorded as not possible (NO MANUAL mode)."""
    PARTS = ["relay", "fuse", "breaker", "valve", "board", "thermostat", "switch"]
    FAIL = ["The {p} reads open.", "The {p} is shorted to ground.", "The {p} failed the continuity test."]
    PASS = ["The {p} tests good.", "The {p} reads normal/OK.", "The {p} checked good."]

    def test_property_latest_result_decides(self):
        rnd = random.Random(550)
        for _ in range(300):
            p = rnd.choice(self.PARTS)
            seq = [rnd.choice(["f", "p"]) for _ in range(rnd.randint(1, 4))]
            tech = ["Customer says it does not work."] + [rnd.choice(self.FAIL if k == "f" else self.PASS).format(p=p) for k in seq]
            self.assertEqual(go.latest_result({p}, tech)[0], "fail" if seq[-1] == "f" else "pass", tech)
            out, held = go.condemn_gate(f"Replace the {p}. [General trade knowledge]", tech, "")
            self.assertEqual(bool(held), seq[-1] == "p", (tech, out))

    def test_property_post_repair_check_never_holds(self):
        rnd = random.Random(551)
        for _ in range(200):
            p = rnd.choice(self.PARTS)
            check = f"{rnd.choice(['Load', 'Amp-draw', 'Leak-down'])} test on the {rnd.choice(self.PARTS)} not done (customer pickup)."
            tech = ["Customer says it does not work.", rnd.choice(self.FAIL).format(p=p), f"Replaced the {p}; it works now. {check}"]
            pts = [go.PendingTest(check, [], {p}, set(), 2)]
            self.assertEqual(go.drop_post_repair_checks(pts, tech, "", {}), [], tech)

    def test_property_upstream_before_oem(self):
        rnd = random.Random(552)
        block = "OEM AUTHORIZATION FINDINGS\nComplaint verified: dead.\nRequested authorization: replace complete unit."
        for _ in range(200):
            up, other = rnd.sample(["relay", "fuse", "breaker", "thermostat", "switch"], 2)
            base = ["Customer says it is dead.", f"Checked around the {up} and the {other}.", rnd.choice(self.PASS).format(p=other)]
            out, held = go.oem_upstream_gate(block, base, "NO MANUAL", {})
            self.assertEqual(held, [up], base)
            self.assertNotIn("Requested authorization", out)
            done = base + [rnd.choice(self.FAIL + self.PASS + ["The {p} test cannot be done here."]).format(p=up)]
            out, held = go.oem_upstream_gate(block, done, "NO MANUAL", {})
            self.assertEqual(held, [], done)
            self.assertIn("Requested authorization", out)


if __name__ == "__main__":
    unittest.main()
