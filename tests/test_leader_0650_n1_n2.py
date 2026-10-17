"""Leader 2026-10-17 06:50 PT rulings N1, N2 (+ the O3 cite confirmation). Locked, verbatim where a transcript exists.

N1  GD sends a structured CLOSE only after a verified, recorded repair; the harness ends on CLOSE. No CLOSE without a recorded
    repair (O1: the repaired part had its own basis before the repair) AND the tech's verify pass after it.
N2  A contact label is the company the SOURCE LINE names for that number; else the pinned manual's brand (doc metadata); if that is
    ambiguous, no company: 'tech line per <doc> p.<n>'. A brand is never put on a number it does not own.
O3  The upstream test asked before an OEM / whole-unit request, with a manual pinned, is the manual's own test and cites doc + page;
    without a citable page there is no gate.
GD code never sees a case id; fixtures are byte-for-byte transcript / library text (tests/fixtures_leader_0550.py)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go  # noqa: E402
from tests import fixtures_leader_0550 as F  # noqa: E402

RC20_DOC = "Level Up Advantage 807662 Manual Mode Flash Home \u2014 Shop Writeup"


def _tech(turns, n=None):
    return [t for t, _ in (turns if n is None else turns[:n])]


class TestN1Close(unittest.TestCase):
    def test_rc04_verified_repair_closes(self):
        """6753d23 RC04 T6 (verbatim): 'Replaced the 30A breaker; after charge, batteries at full voltage and Auto Level completed …'
        after the breaker's own drop-across result (T5)."""
        close = go.verified_close(_tech(F.RC04_675_TURNS, 6), "", {})
        self.assertIsNotNone(close)
        self.assertIn("30A breaker", close[0])
        self.assertRegex(close[1], r"Auto Level completed")
        out = go.close_reply(close, {"post_repair_checks": ["Battery amp-draw/Ah test not done (customer pickup)."]})
        self.assertTrue(out.splitlines()[0].startswith(go.CLOSE_HEAD + ":"))
        self.assertIn("Not done (release note, not a blocker): Battery amp-draw/Ah test not done", out)
        self.assertNotIn("VERIFY: run the function again", out)

    def test_no_close_before_the_repair(self):
        self.assertIsNone(go.verified_close(_tech(F.RC04_675_TURNS, 5), "", {}))

    def test_no_close_without_a_recorded_repair_rc20(self):
        """db2e601 RC20 (verbatim): no parts replaced, ESCALATION SUMMARY; never a CLOSE."""
        for n in range(1, len(F.RC20_DB2_TURNS) + 1):
            self.assertIsNone(go.verified_close(_tech(F.RC20_DB2_TURNS, n), "", {}), n)

    def test_no_close_without_a_verify_pass_rc08(self):
        """db2e601 RC08 (verbatim): the panel was replaced on its own good-in/bad-out result, but every later message says
        'Post-repair verify isn't in the notes … I can't report whether the jack runs' - no verify pass, no CLOSE."""
        tech = _tech(F.RC08_DB2_TURNS)
        pin = {"directed_repairs": ["panel"]}  # live: condemn_gate recorded the panel condemn on its own result
        self.assertIsNotNone(go.recorded_repair(tech, "", pin))
        self.assertIsNone(go.verified_close(tech, "", pin))

    def test_no_close_shapes(self):
        base = ["Customer says the vent fan is dead.", "The fuse reads open."]
        for tail in ("Replaced the fuse.", "Replaced the fuse; fan still dead.", "Replaced the fuse; verify not done yet.",
                     "Replaced the fuse; I can't tell whether it works.", "Replaced the fuse; bypass at the switch works."):
            self.assertIsNone(go.verified_close(base + [tail], "", {}), tail)
        self.assertIsNone(go.verified_close(["Customer says the vent fan is dead.", "Fuse holder looks OK.",
                                             "Replaced the fuse; fan works and the complaint is gone."], "", {}))  # no basis
        self.assertIsNotNone(go.verified_close(base + ["Replaced the fuse; fan works and the complaint is gone."], "", {}))
        self.assertIsNone(go.verified_close(base + ["Replaced the fuse; fan works.", "Next day the fan is still dead."], "", {}))

    def test_harness_ends_on_close(self):
        src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "gd_rc_sim.py")).read()
        self.assertIn('ln.startswith(go.CLOSE_HEAD + ":")', src)

    def test_property_close_iff_basis_repair_and_verify(self):
        rnd = random.Random(650)
        parts = ["fuse", "relay", "breaker", "thermostat", "switch"]
        for _ in range(300):
            p = rnd.choice(parts)
            basis, repair, verify, still = (rnd.random() < 0.6 for _ in range(4))
            tech = ["Customer says it does not work."]
            tech.append(f"The {p} reads open." if basis else f"The {p} holder looks OK.")
            if repair:
                tech.append(f"Replaced the {p}" + ("; it works and the complaint is gone." if verify else "."))
                if still:
                    tech.append("Complaint is still present.")
            want = basis and repair and verify and not still
            self.assertEqual(go.verified_close(tech, "", {}) is not None, want, tech)


class TestN2ContactLabel(unittest.TestCase):
    PIN = {"doc_brand": "lippert", "doc_title": RC20_DOC, "section_text": "[PAGE 3]\n" + F.RC20_DOC_P3_CONTACTS}

    def test_rc20_shows_firefly_574_825_4600(self):
        """db2e601 RC20 printed 'Contact: Lippert tech line: 574-825-4600' - the number is the Firefly line on p.3 of the pinned
        writeup ('- Firefly Tech Support: 574-825-4600 / support@fireflyint.com')."""
        class _T:
            text = "Plumbing check on the front-jack path is still pending."
            scope = {"hose", "jack"}
        summ = go.escalation_summary([_T()], _tech(F.RC20_DB2_TURNS), dict(self.PIN), [], True)
        line = [ln for ln in summ.splitlines() if "Contact:" in ln][0]
        self.assertIn("Contact: Firefly tech line: 574-825-4600", line)
        self.assertNotIn("Lippert", line)

    def test_each_number_keeps_its_own_company(self):
        lines = F.RC20_DOC_P3_CONTACTS.splitlines()
        self.assertEqual(go.contact_name_number(lines[1], self.PIN), "Firefly tech line: 574-825-4600")
        self.assertEqual(go.contact_name_number(lines[2], self.PIN), "Brinkley tech line: 888-502-3460")

    def test_no_company_named_uses_the_doc_brand(self):
        line = "Shop/OEM tech-line 423-775-2131 ext. 7102 if brown still not 10.5\u201313.5 VDC after board swap."
        self.assertEqual(go.contact_name_number(line, {"doc_brand": "suburban"}), "Suburban tech line: 423-775-2131 ext. 7102")

    def test_ambiguous_gives_doc_and_page_only(self):
        line = "Call Firefly or Lippert at 574-825-4600. [Library: Level Up Advantage 807662 Manual Mode Flash Home p.3]"
        self.assertEqual(go.contact_name_number(line, self.PIN),
                         "tech line per Level Up Advantage 807662 Manual Mode Flash Home p.3: 574-825-4600")
        self.assertEqual(go.contact_name_number("Shop/OEM tech-line 423-775-2131.", {"doc_title": "Some Manual",
                                                "section_text": "[PAGE 9]\nShop/OEM tech-line 423-775-2131."}),
                         "tech line per Some Manual p.9: 423-775-2131")

    def test_property_never_a_foreign_brand_on_a_number(self):
        rnd = random.Random(651)
        names = ["Acme", "Zenith", "Northwind", "Contoso", "Fabrikam"]
        for _ in range(300):
            co, brand = rnd.sample(names, 2)
            num = f"{rnd.randint(200, 989)}-{rnd.randint(200, 989)}-{rnd.randint(1000, 9999)}"
            line = rnd.choice(["- {c} Tech Support: {n}", "Call {c} at {n}.", "Shop/OEM tech-line: {c} {n} / help@x.com",
                               "{c} Care: {n} or 555-555-5555"]).format(c=co, n=num)
            label = go.contact_name_number(line, {"doc_brand": brand.lower()})
            self.assertTrue(label.startswith(co + " "), (line, label))
            self.assertNotIn(brand, label)


class TestO3UpstreamCite(unittest.TestCase):
    BLOCK = "OEM AUTHORIZATION FINDINGS\nComplaint verified: dead.\nRequested authorization: replace complete unit."

    def test_ask_cites_doc_and_page(self):
        sec = "[PAGE 3]\nIntro.\n\n[PAGE 4]\nTest the controller with the CAN cable unplugged and the terminator in."
        tech = ["Customer says the jacks drift.", "Checked around the controller."]
        out, up = go.oem_upstream_gate(self.BLOCK, tech, sec,
                                       {"source_label": "Library: Shop Writeup", "doc_title": "Shop Writeup"})
        self.assertEqual(up, ["controller"])
        self.assertIn("[Library: Shop Writeup p.4]", out)
        self.assertNotIn("Requested authorization", out)

    def test_no_citable_page_no_gate(self):
        sec = "Test the controller with the CAN cable unplugged."  # manual text with no page marker: nothing to cite
        out, up = go.oem_upstream_gate(self.BLOCK, ["Customer says dead.", "Checked around the controller."], sec, {})
        self.assertEqual(up, [])
        self.assertIn("Requested authorization", out)


if __name__ == "__main__":
    unittest.main()
