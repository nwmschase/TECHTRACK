"""Shop wording: tech-facing GD and Bay PDF output must not say channel."""
import re
import unittest
from pathlib import Path

from bay_procedure import (
    apply_shop_channel_wording,
    compile_bay_procedure,
    pdf_content_operators,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
)
from gd_library_coach import (
    BAL_TONGUE_PANEL_SHOP_LINE,
    BAL_TONGUE_PIGTAIL_SHOP_LINE,
    BAL_TONGUE_PRODUCT_LOCK,
    BAL_TONGUE_PROVE_SHOP_LINE,
    OPEN_LIBRARY_COACH_RULE,
    SHOP_LANGUAGE_RULE,
    WATER_HEATER_PRODUCT_LOCK,
    ensure_bal_tongue_only_path,
    ensure_coleman_motor_board_auth,
    ensure_facr_freeze_assembly_rr,
    ensure_fcr_dial_off_compressor_run_path,
    ensure_fcr_e2_fan_rr,
    ensure_fridge_ice_moisture_path,
    ensure_level_up_manual_can_path,
    extract_stated_facts,
    facr_freeze_proves_from_text,
    format_stated_facts_rule,
    rewrite_shop_channel_words,
)

ROOT = Path(__file__).resolve().parents[1]
CHANNEL_RE = re.compile(r"\bchannels?\b", re.I)

BAL_WO = (
    "BAL Soft-Touch SS 5.1 electric tongue jack dead. "
    "Other stabilizers and panel lights work. Motor OK on direct 12V. Coupler OK."
)


def _pdf_text(pdf: bytes) -> str:
    try:
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return pdf_content_operators(pdf)


def _without_channel_ban(text: str) -> str:
    """Drop the prompt line that names the banned jargon."""
    kept = []
    for line in (text or "").splitlines():
        low = line.lower()
        if "channel" in low and any(
            k in low for k in ("do not", "don't", "avoid", "never say", "jargon", "shop words")
        ):
            continue
        kept.append(line)
    return "\n".join(kept)


def _assert_no_channel(testcase, text, label):
    match = CHANNEL_RE.search(text or "")
    testcase.assertIsNone(
        match,
        f"{label} still says {match.group(0)!r}" if match else label,
    )


class TestShopChannelFilter(unittest.TestCase):
    def test_user_example_and_plural_and_case(self):
        raw = "Prove 12V at the soft-touch panel tongue channel while you command extend"
        out = rewrite_shop_channel_words(raw)
        self.assertIn("tongue jack output wire at the panel", out.lower())
        _assert_no_channel(self, out, "example")
        self.assertEqual(
            rewrite_shop_channel_words("The stabilizer channels are live."),
            "The stabilizer circuits are live.",
        )
        self.assertEqual(rewrite_shop_channel_words("CHANNEL"), "WIRE")
        self.assertEqual(rewrite_shop_channel_words("Channels"), "Circuits")

    def test_marked_oem_source_quote_stays_verbatim(self):
        raw = (
            "Prove 12V at the soft-touch panel tongue channel.\n"
            "📖 Source: BAL SS 5.1 Stabilizing System INS.STA.001\n"
            '"tongue channel voltage at the panel connector"'
        )
        out = rewrite_shop_channel_words(raw)
        before, _sep, quote = out.partition("📖 Source:")
        _assert_no_channel(self, before, "prose before source")
        self.assertIn("tongue channel voltage at the panel connector", quote)
        self.assertIn("20300427", rewrite_shop_channel_words("Replace panel 20300427 on that channel."))
        kept = rewrite_shop_channel_words('OEM source quote: "check the tongue channel"')
        self.assertIn("tongue channel", kept)

    def test_bal_climax_meaning_and_part_number(self):
        self.assertIn(
            "Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel.",
            BAL_TONGUE_PROVE_SHOP_LINE,
        )
        self.assertIn("20300427", BAL_TONGUE_PANEL_SHOP_LINE)
        self.assertIn("replace the soft-touch user panel", BAL_TONGUE_PANEL_SHOP_LINE.lower())
        self.assertIn("repair the local tongue pigtail", BAL_TONGUE_PIGTAIL_SHOP_LINE.lower())
        self.assertIn("INS.STA.001", BAL_TONGUE_PROVE_SHOP_LINE)
        missing = extract_stated_facts(BAL_WO + " No 12V on the tongue jack output wire at the panel.")
        present = extract_stated_facts(
            BAL_WO + " 12V is present on the tongue jack output wire at the panel."
        )
        self.assertEqual(missing.get("tongue_channel_volts"), "missing")
        self.assertEqual(present.get("tongue_channel_volts"), "present")
        panel = rewrite_shop_channel_words(
            ensure_bal_tongue_only_path("Replace the coupler.", missing)
        )
        pigtail = rewrite_shop_channel_words(
            ensure_bal_tongue_only_path("Replace the coupler.", present)
        )
        self.assertIn("20300427", panel)
        self.assertIn("pigtail", pigtail.lower())
        self.assertIn("repair", pigtail.lower())
        _assert_no_channel(self, panel, "panel guard")
        _assert_no_channel(self, pigtail, "pigtail guard")


class TestKnownCaseTechText(unittest.TestCase):
    def _guard_and_pdf(self):
        facr_facts = facr_freeze_proves_from_text(
            "Drain is clear. Fan-filter OK. Freeze sensor good. Interior leak is still there."
        )
        bal_facts = extract_stated_facts(BAL_WO)
        level_facts = extract_stated_facts(
            "Manual Mode flashes then dumps back to home on the Level Up pad. Auto Level still works."
        )
        coleman_facts = {
            "coleman_2111": "climax",
            "coleman_fan_high": "dead",
            "coleman_compressor": "ok",
            "coleman_fan_motor": "locked",
            "coleman_stall_amps": "reported",
            "coleman_cap": "ok",
        }
        e2_facts = {"fan_fault": "e2", "fan_volts": "reported", "fan_amps": "reported"}
        guards = {
            "FACR08": ensure_facr_freeze_assembly_rr("Searching the manuals.", facr_facts),
            "BAL SS 5.1": ensure_bal_tongue_only_path("Replace the coupler.", bal_facts),
            "FCR10 OFF": ensure_fcr_dial_off_compressor_run_path(
                "Check the 15A fuse in the front vent cavity, then confirm 12V continuity."
            ),
            "FCR10 ice": ensure_fridge_ice_moisture_path(
                "Check the 15A fuse in the front vent cavity.\n📖 Source: Fuse location"
            ),
            "Level Up 807662": ensure_level_up_manual_can_path(
                "Swap another 807662 controller and the LCD next.",
                level_facts,
            ),
            "Coleman 2111-0001": ensure_coleman_motor_board_auth(
                "Replace the complete 2111-0001 rooftop assembly.",
                coleman_facts,
            ),
            "FCR10 E2": ensure_fcr_e2_fan_rr(
                "CCD-0008122 does not list a separate freezer evaporator fan. "
                "E2 repair is board only.",
                e2_facts,
            ),
            "Suburban NT-20SEQT": WATER_HEATER_PRODUCT_LOCK,
        }
        sheets = {
            "FACR08": dict(
                concern=(
                    "Furrion FACR08HESA2-PS rooftop AC. Water leaking from the forward AC "
                    "inside while running. Frost/ice on the evaporator."
                ),
                brand="Furrion",
                model="FACR08HESA2-PS",
                category="Air Conditioning",
            ),
            "BAL SS 5.1": dict(
                concern=BAL_WO,
                brand="BAL",
                model="Soft-Touch SS 5.1",
                category="Leveling",
            ),
            "FCR10 OFF": dict(
                concern=(
                    "temperature dial OFF but compressor still running, "
                    "freezer frozen solid, overcooling"
                ),
                brand="Furrion",
                model="FCR10DCGTA-BG-PWH",
                category="Refrigerators",
            ),
            "FCR10 ice": dict(
                concern="icing up on rear wall — only about half from the top down",
                brand="Furrion",
                model="FCR10DCGTA-BG-PWH",
                category="Refrigerators",
            ),
            "Level Up 807662": dict(
                concern=(
                    "Manual Mode flashes then dumps back to home on the Level Up pad. "
                    "Auto Level still works."
                ),
                brand="Lippert",
                model="Level Up Advantage 807662",
                category="Leveling",
            ),
            "Coleman 2111-0001": dict(
                concern="Coleman-Mach rooftop A/C model 2111-0001. Ran about 2 minutes then dead.",
                brand="Coleman-Mach",
                model="2111-0001",
                category="Air Conditioning",
            ),
            "FCR10 E2": dict(
                concern="Freezes contents; intermittent blinking 2 / E2; temp control intermittent",
                brand="Furrion",
                model="FCR10DCGTA-BG-PWH",
                category="Refrigerators",
            ),
            "Suburban NT-20SEQT": dict(
                concern="Suburban NT-20SEQT water heater no hot water",
                brand="Suburban",
                model="NT-20SEQT",
                category="Water Heaters",
            ),
        }
        return guards, sheets

    def test_guard_text_and_bay_pdfs_omit_channel(self):
        guards, sheets = self._guard_and_pdf()
        self.assertEqual(set(guards), set(sheets))
        for name, guard in guards.items():
            shipped = rewrite_shop_channel_words(guard)
            self.assertTrue(shipped.strip(), name)
            _assert_no_channel(self, shipped, f"GD {name}")
        self.assertNotIn("20300427", guards["BAL SS 5.1"])
        self.assertIn("12v", guards["BAL SS 5.1"].lower())
        self.assertIn("INS.STA.001", guards["BAL SS 5.1"])
        self.assertIn("CCD-0007990", guards["FACR08"])
        self.assertIn("compressor stops", guards["FCR10 OFF"].lower())
        self.assertNotIn("2021128850", guards["FCR10 OFF"])
        self.assertIn("page 36", guards["FCR10 ice"].lower())
        self.assertIn("rubber boot", guards["Level Up 807662"].lower())
        self.assertIn("firefly", guards["Level Up 807662"].lower())
        self.assertIn("2111-0001", guards["Coleman 2111-0001"])
        self.assertIn("control board", guards["Coleman 2111-0001"].lower())
        self.assertIn("freezer evaporator fan", guards["FCR10 E2"].lower())
        for name, kwargs in sheets.items():
            proc = compile_bay_procedure(**kwargs)
            blob = "\n".join(
                [
                    procedure_plain_text(proc),
                    procedure_body_text(proc),
                    "\n".join(proc.notes),
                    "\n".join(fig.caption or "" for fig in proc.figures),
                    "\n".join(fig.excerpt or "" for fig in proc.figures),
                ]
            )
            _assert_no_channel(self, blob, f"sheet {name}")
            pdf = _pdf_text(render_bay_procedure_pdf(proc))
            self.assertGreater(len(pdf), 80, name)
            _assert_no_channel(self, pdf, f"PDF {name}")

    def test_sheet_filter_rewrites_unmarked_excerpt_and_keeps_quote(self):
        proc = compile_bay_procedure(
            concern="Customer states the air conditioner is not cooling.",
            brand="Furrion",
            model="FACT12SA2",
            category="Air Conditioning",
            chunks=[
                {
                    "title": "Shop service excerpt",
                    "page": 4,
                    "excerpt": (
                        "Check the control channel before the swap.\n"
                        "📖 Source: OEM book - page 4\n"
                        '"leave the control channel quote"'
                    ),
                }
            ],
        )
        excerpt = proc.sources[0]["excerpt"]
        # Source polish keeps the whole sentence and drops the marker line.
        # The shop pass then rewrites the unmarked sentence.
        self.assertEqual(excerpt, "Check the control wire before the swap.")
        _assert_no_channel(self, excerpt, "compiled excerpt")
        self.assertEqual(proc.sources[0]["title"], "Shop service excerpt")
        proc.sources[0]["excerpt"] = (
            "Check the control channel before the swap.\n"
            "📖 Source: OEM book - page 4\n"
            '"leave the control channel quote"'
        )
        again = apply_shop_channel_wording(proc)
        kept = again.sources[0]["excerpt"]
        prose, _sep, quoted = kept.partition("📖 Source:")
        _assert_no_channel(self, prose, "excerpt prose")
        self.assertIn("control wire", prose)
        self.assertIn("control channel", quoted)
        twice = apply_shop_channel_wording(again)
        self.assertEqual(twice.sources[0]["excerpt"], kept)


class TestPromptAndTemplateGrep(unittest.TestCase):
    def test_prompt_constants_and_bay_templates(self):
        import gd_library_coach as coach

        self.assertIn("wire, plug, terminal, circuit, connector", SHOP_LANGUAGE_RULE)
        self.assertIn(SHOP_LANGUAGE_RULE, OPEN_LIBRARY_COACH_RULE)
        self.assertIn(SHOP_LANGUAGE_RULE, BAL_TONGUE_PRODUCT_LOCK + OPEN_LIBRARY_COACH_RULE)
        scanned = []
        for name in dir(coach):
            if name.startswith("_") or "SEARCH" in name:
                continue
            val = getattr(coach, name)
            if not isinstance(val, str):
                continue
            if any(k in name for k in ("LOCK", "SHOP_LINE", "RULE", "HONESTY", "PROVE", "_LINE")):
                scanned.append(name)
                _assert_no_channel(self, _without_channel_ban(val), name)
        self.assertIn("OPEN_LIBRARY_COACH_RULE", scanned)
        self.assertIn("BAL_TONGUE_PRODUCT_LOCK", scanned)
        self.assertIn("SHOP_LANGUAGE_RULE", scanned)
        for label, facts_text in (
            ("prove", BAL_WO),
            ("panel", BAL_WO + " No 12V on the tongue jack output wire at the panel."),
            ("pigtail", BAL_WO + " 12V is present on the tongue jack output wire at the panel."),
        ):
            rule = format_stated_facts_rule(extract_stated_facts(facts_text))
            _assert_no_channel(self, _without_channel_ban(rule), f"facts {label}")
        bay_src = (ROOT / "bay_procedure.py").read_text()
        app_src = (ROOT / "rv_techtrack.py").read_text()
        # The climax needle still matches OEM pages that use the old phrase.
        # It is not printed; the shop filter rewrites any excerpt that carries it.
        oem_needle = '"tongue channel"'
        self.assertEqual(bay_src.count(oem_needle), 1)
        self.assertIn("_PATH_CLIMAX", bay_src)
        bay_facing = bay_src.replace(oem_needle, '"tongue output"', 1)
        _assert_no_channel(self, bay_facing, "bay_procedure.py")
        _assert_no_channel(self, app_src, "rv_techtrack.py")
        self.assertIn("rewrite_shop_channel_words(reply)", app_src)
        self.assertIn("apply_shop_channel_wording", bay_src)
        self.assertIn("25. \"\"\" + SHOP_LANGUAGE_RULE", app_src)


if __name__ == "__main__":
    unittest.main()
