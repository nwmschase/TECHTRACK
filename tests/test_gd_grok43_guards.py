"""grok-4.3 Guided Diagnostics regressions: retrieval gaps and two partials."""
import unittest
from pathlib import Path

from bay_procedure import bay_brand_retrieval, rank_bay_chunks
from gd_library_coach import (
    ac_search_symptom,
    COOKTOP_TIP_LOW_REPAIR,
    DOMETIC_CEILING_LINE,
    DOMETIC_NOCOOL_CONFIRM_FAN,
    DOMETIC_NOCOOL_OPEN,
    FURNACE_WALL_TSTAT_LINE,
    GROUND_CONTROL_LEVEL_LINE,
    GROUND_CONTROL_STAY_LINE,
    chunk_matches_asked_brand,
    cooktop_tip_sits_low,
    dometic_bypass_facts,
    ensure_cooktop_tip_pan_check,
    ensure_dometic_ceiling_thermostat,
    ensure_furnace_wall_thermostat,
    ensure_ground_control_level_path,
    filter_chunks_for_unit,
    is_cooktop_pan_on_flameout_context,
    is_dometic_b57915_nocoool_context,
    is_ground_control_context,
    is_level_up_advantage_context,
    is_suburban_furnace_context,
    page_identity_blob,
    page_is_dometic_nocoool_family,
    page_is_ground_control_family,
    rank_chunks_for_dometic_nocoool,
    rank_chunks_for_ground_control,
    reply_loops_furnace_12v,
    reply_names_ground_control_calibration,
)

GC_FILE = (
    "library/Lippert Internal Tech Support – Electric Leveling Systems "
    "(Ground Control TT_2.0_3.0).pdf"
)
GC_PAGE = {
    "title": "scan0042",
    "keywords": "",
    "excerpt": "Manual level, then zero point calibration when one side lifts.",
    "file_path": GC_FILE,
}
LEVEL_UP_PAGE = {
    "title": "Lippert Level Up Advantage 807662",
    "keywords": "hydraulic leveling",
    "excerpt": "Not Ground Control. Hydraulic level up manual mode.",
    "file_path": "level_up_807662.pdf",
}
FILTER_PAGE = {
    "title": "Dometic Brisk B57915 return air filter",
    "keywords": "filter",
    "excerpt": "Clean the filter and retest the rooftop unit.",
    "file_path": "brisk_filter.pdf",
}
DIAG_PAGE = {
    "title": "catalog_page",
    "keywords": "",
    "excerpt": "No cool. Compressor does not start. Check the ceiling selector.",
    "file_path": "Dometic diagnostic service manual 3311071.pdf",
}
S10 = "Lippert Ground Control 343633 auto-level lifts the driver side"
S09_MODEL = "Dometic B57915E711J0EMX"
S09 = "fan runs, no cold"


class TestGroundControlRetrieval(unittest.TestCase):
    def test_343633_is_ground_control_not_level_up(self):
        self.assertTrue(is_ground_control_context("Leveling", "343633", S10))
        self.assertFalse(is_level_up_advantage_context("Leveling", "343633", S10))
        self.assertFalse(
            is_ground_control_context(
                "Leveling", "807662", "Level Up hydraulic auto level. Not Ground Control."
            )
        )

    def test_filename_matches_the_bay_brand_lookup(self):
        ident = page_identity_blob(
            GC_PAGE["title"], "", GC_PAGE["excerpt"], GC_PAGE["file_path"]
        )
        self.assertTrue(page_is_ground_control_family(ident))
        self.assertFalse(
            page_is_ground_control_family(
                page_identity_blob(
                    LEVEL_UP_PAGE["title"], "", LEVEL_UP_PAGE["excerpt"], LEVEL_UP_PAGE["file_path"]
                )
            )
        )
        self.assertFalse(
            chunk_matches_asked_brand(
                GC_PAGE["title"], "", GC_PAGE["excerpt"], {"lippert"}
            )
        )
        self.assertTrue(
            chunk_matches_asked_brand(
                GC_PAGE["title"],
                "",
                GC_PAGE["excerpt"],
                {"lippert"},
                file_path=GC_PAGE["file_path"],
            )
        )
        kept, miss = bay_brand_retrieval(
            [LEVEL_UP_PAGE, GC_PAGE], "Leveling", "Lippert 343633", S10
        )
        self.assertFalse(miss)
        titles = {p.get("file_path") for p in kept}
        self.assertIn(GC_FILE, titles)

    def test_shared_rank_prefers_ground_control_over_level_up(self):
        ranked = rank_chunks_for_ground_control([LEVEL_UP_PAGE, GC_PAGE], S10)
        self.assertEqual(ranked[0]["file_path"], GC_FILE)
        self.assertTrue(
            all(page_is_ground_control_family(
                page_identity_blob(p.get("title"), "", p.get("excerpt"), p.get("file_path"))
            ) for p in ranked)
        )
        bay = rank_bay_chunks(
            [LEVEL_UP_PAGE, GC_PAGE], "Leveling", "Lippert Ground Control 343633", S10
        )
        self.assertEqual(bay[0]["file_path"], GC_FILE)
        self.assertNotIn("807662", bay[0]["file_path"])

    def test_library_miss_becomes_manual_level_and_zero_point(self):
        miss = "The library has no Ground Control docs, so there are no steps."
        fixed = ensure_ground_control_level_path(miss)
        self.assertEqual(fixed, GROUND_CONTROL_LEVEL_LINE)
        self.assertTrue(reply_names_ground_control_calibration(fixed))
        low = fixed.lower()
        self.assertIn("manual level", low)
        self.assertIn("zero-point", low)
        self.assertIn("front five", low)
        self.assertIn("rear five", low)
        self.assertIn("enter", low)
        self.assertIn("lippert internal tech support", low)
        self.assertIn("ground control", low)
        self.assertNotIn("library has no", low)
        self.assertNotIn("swap a level sensor.", low)

    def test_harness_swap_becomes_the_sequence_and_later_turns_do_not_repeat_it(self):
        opener = (
            "Run manual level, then zero-point calibration. "
            "Check the wiring harness and swap the level sensor."
        )
        first = ensure_ground_control_level_path(opener)
        self.assertEqual(first, GROUND_CONTROL_LEVEL_LINE)
        self.assertNotIn("swap the level sensor", first.lower())
        self.assertNotIn("check the wiring harness", first.lower())
        self.assertIn("do not replace a harness", first.lower())
        later = ensure_ground_control_level_path(
            opener,
            history=[{"role": "assistant", "content": first}],
        )
        self.assertEqual(later, GROUND_CONTROL_STAY_LINE)
        self.assertNotIn("run manual level, then zero-point calibration", later.lower())
        self.assertNotIn("front five", later.lower())
        progress = ensure_ground_control_level_path(
            "Zero point set successfully. Auto-level again and the driver side stays put.",
            history=[{"role": "assistant", "content": first}],
        )
        self.assertIn("stays put", progress.lower())
        self.assertNotIn("front five", progress.lower())


class TestDometicNoCoolRetrieval(unittest.TestCase):
    def test_fan_no_cold_is_3311071_not_a_brisk_e3_filter_job(self):
        self.assertTrue(
            is_dometic_b57915_nocoool_context("Air Conditioning", S09_MODEL, S09)
        )
        self.assertFalse(
            is_dometic_b57915_nocoool_context(
                "Air Conditioning", "Dometic B57915", "Brisk no cool E3"
            )
        )
        ident = page_identity_blob(
            DIAG_PAGE["title"], "", DIAG_PAGE["excerpt"], DIAG_PAGE["file_path"]
        )
        self.assertTrue(page_is_dometic_nocoool_family(ident))
        self.assertFalse(
            page_is_dometic_nocoool_family(
                page_identity_blob(
                    FILTER_PAGE["title"], "", FILTER_PAGE["excerpt"], FILTER_PAGE["file_path"]
                )
            )
        )

    def test_shared_rank_prefers_3311071_over_the_filter_page(self):
        query = f"{S09_MODEL} {S09}"
        kept = filter_chunks_for_unit(
            [FILTER_PAGE, DIAG_PAGE], "Air Conditioning", S09_MODEL, S09
        )
        self.assertEqual(len(kept), 1)
        self.assertIn("3311071", kept[0]["file_path"])
        ranked = rank_chunks_for_dometic_nocoool([FILTER_PAGE, DIAG_PAGE], query)
        self.assertIn("3311071", ranked[0]["file_path"])
        bay = rank_bay_chunks(
            [FILTER_PAGE, DIAG_PAGE], "Air Conditioning", S09_MODEL, S09
        )
        self.assertIn("3311071", bay[0]["file_path"])

    def test_both_bypasses_cool_replaces_the_ceiling_thermostat(self):
        history = [
            {
                "role": "user",
                "content": (
                    "Dometic B57915E711J0EMX fan runs, no cold. "
                    "Peacemaker bypass at the unit cools."
                ),
            }
        ]
        latest = "Bypassing the ceiling selector/thermostat cools. What is the repair?"
        facts = dometic_bypass_facts(history, latest)
        self.assertEqual(facts.get("dometic_unit_bypass"), "cools")
        self.assertEqual(facts.get("dometic_ceiling_bypass"), "cools")
        loop = "Clean the filter again and retest. The filter is the next check."
        fixed = ensure_dometic_ceiling_thermostat(loop, facts)
        self.assertEqual(fixed, DOMETIC_CEILING_LINE)
        low = fixed.lower()
        self.assertIn("replace the ceiling thermostat/selector", low)
        self.assertNotIn("filter", low)
        self.assertIn("3311071", fixed)
        steered = ensure_dometic_ceiling_thermostat(loop, {})
        self.assertEqual(steered, DOMETIC_NOCOOL_CONFIRM_FAN)
        self.assertIn("3311071", steered)
        self.assertIn("confirm the fan runs", steered.lower())
        self.assertIn("peacemaker", steered.lower())
        self.assertIn("ceiling selector", steered.lower())
        self.assertLess(steered.lower().index("peacemaker"), steered.lower().index("filter"))
        self.assertNotIn("clean the filter", steered.lower())
        self.assertNotIn("library has no", steered.lower())
        opening = (
            "The library has no no-cool steps for this Dometic. "
            "Start with the filter check."
        )
        turn1 = ensure_dometic_ceiling_thermostat(opening, {})
        self.assertEqual(turn1, DOMETIC_NOCOOL_CONFIRM_FAN)
        self.assertNotIn("library has no", turn1.lower())
        fan_facts = dometic_bypass_facts([], "Dometic B57915 fan runs, no cold")
        self.assertEqual(fan_facts.get("dometic_fan"), "runs")
        fan_open = ensure_dometic_ceiling_thermostat(opening, fan_facts)
        self.assertEqual(fan_open, DOMETIC_NOCOOL_OPEN)

    def test_turns_on_will_not_blow_cold_confirms_fan_then_peacemaker(self):
        complaint = (
            "Dometic rooftop AC B57915E711J0EMX turns on but will not blow cold."
        )
        self.assertTrue(is_dometic_b57915_nocoool_context("", "", complaint))
        self.assertTrue(
            is_dometic_b57915_nocoool_context(
                "Air Conditioning", "B57915E711J0EMX", complaint
            )
        )
        self.assertFalse(
            is_dometic_b57915_nocoool_context(
                "Air Conditioning", "Dometic B57915", "Brisk no cool E3"
            )
        )
        boosted = ac_search_symptom(
            "Air Conditioning", "B57915E711J0EMX", complaint
        )
        self.assertTrue(
            is_dometic_b57915_nocoool_context(
                "Air Conditioning", "B57915E711J0EMX", boosted
            )
        )
        brisk_boosted = ac_search_symptom(
            "Air Conditioning", "Dometic B57915", "Brisk no cool E3"
        )
        self.assertNotEqual(brisk_boosted, "Brisk no cool E3")
        self.assertFalse(
            is_dometic_b57915_nocoool_context(
                "Air Conditioning", "Dometic B57915", brisk_boosted
            )
        )
        opening = (
            "The library has no no-cool steps for this Dometic. "
            "Start with the filter check."
        )
        turn1 = ensure_dometic_ceiling_thermostat(opening, {})
        self.assertEqual(turn1, DOMETIC_NOCOOL_CONFIRM_FAN)
        low = turn1.lower()
        self.assertIn("confirm the fan runs", low)
        self.assertIn("peacemaker", low)
        self.assertIn("3311071", turn1)
        self.assertNotIn("library has no", low)
        self.assertLess(low.index("peacemaker"), low.index("filter"))
        self.assertNotIn("clean the filter", low)
        self.assertNotIn("channel", low)
        kept = filter_chunks_for_unit(
            [FILTER_PAGE, DIAG_PAGE], "Air Conditioning", "B57915E711J0EMX", complaint
        )
        self.assertEqual(len(kept), 1)
        self.assertIn("3311071", kept[0]["file_path"])
        bay = rank_bay_chunks(
            [FILTER_PAGE, DIAG_PAGE], "Air Conditioning", "B57915E711J0EMX", complaint
        )
        self.assertIn("3311071", bay[0]["file_path"])
        follow = ensure_dometic_ceiling_thermostat(
            "Fan runs. Peacemaker is next once you confirm it cools.",
            {"dometic_fan": "runs"},
            history=[{"role": "assistant", "content": turn1}],
        )
        self.assertIn("peacemaker is next", follow.lower())
        restart = ensure_dometic_ceiling_thermostat(
            "The library does not cover this. Clean the filter.",
            {},
            history=[{"role": "assistant", "content": turn1}],
        )
        self.assertEqual(restart, DOMETIC_NOCOOL_CONFIRM_FAN)
        live = (
            "The shop Document Library excerpts for the B57915 Brisk II cover "
            "install, wiring, dimensions, and basic filter cleaning only. "
            'No diagnostic steps for "turns on but no cold air" are in those pages. '
            "Does the fan run at all, and have you checked the return air filter?"
        )
        from gd_library_coach import claims_library_missing_steps

        self.assertTrue(claims_library_missing_steps(live))

    def test_send_path_rewrites_the_live_turn1_reply(self):
        """Same function the Send button calls, with the live grok-4.3 draft."""
        src = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
        cut = src.split("# ---------------- LOGIN ----------------", 1)[0]
        ns = {
            "__name__": "rv_techtrack_send_path",
            "__file__": str(Path(__file__).resolve().parents[1] / "rv_techtrack.py"),
        }
        exec(compile(cut, "rv_techtrack.py", "exec"), ns)
        live = (
            "The shop Document Library excerpts for the B57915 Brisk II cover "
            "install, wiring, dimensions, and basic filter cleaning only. "
            'No diagnostic steps for "turns on but no cold air" are in those pages. '
            "Does the fan run at all, and have you checked the return air filter?"
        )
        ns["ai_available"] = lambda: True
        ns["ai_chat"] = lambda *args, **kwargs: live
        complaint = "Dometic rooftop AC B57915E711J0EMX turns on but will not blow cold."
        reply, flow = ns["guided_diagnostics_reply"](
            complaint,
            "Air Conditioning",
            "B57915E711J0EMX",
            [],
            unity_gate="Not sure",
        )
        self.assertIsNone(flow)
        self.assertEqual(reply, DOMETIC_NOCOOL_CONFIRM_FAN)
        low = reply.lower()
        self.assertIn("confirm the fan runs", low)
        self.assertIn("peacemaker", low)
        self.assertIn("3311071", reply)
        self.assertNotIn("return air filter", low)
        self.assertNotIn("no diagnostic steps", low)
        self.assertNotIn("channel", low)


class TestFurnaceWallThermostat(unittest.TestCase):
    def test_rw_jumper_commits_to_wall_thermostat(self):
        history = [
            {
                "role": "user",
                "content": (
                    "Suburban NT-20SEQT furnace. Jumped R/W at the furnace. "
                    "It lights and runs."
                ),
            }
        ]
        latest = "What is the repair?"
        loop = "Check 12 VDC at the furnace board again before you decide."
        self.assertTrue(reply_loops_furnace_12v(loop))
        self.assertTrue(
            is_suburban_furnace_context("Furnaces", "Suburban NT-20SEQT", history[0]["content"])
        )
        fixed = ensure_furnace_wall_thermostat(
            loop, history, latest, "Furnaces", "Suburban NT-20SEQT"
        )
        self.assertEqual(fixed, FURNACE_WALL_TSTAT_LINE)
        low = fixed.lower()
        self.assertIn("replace the wall thermostat", low)
        self.assertIn("wire run", low)
        self.assertIn("voltage is missing", low)
        self.assertFalse(reply_loops_furnace_12v(fixed))
        self.assertNotIn("12 v", low)
        early = ensure_furnace_wall_thermostat(
            loop, history, "Still looking.", "Furnaces", "Suburban NT-20SEQT"
        )
        self.assertEqual(early, loop)

    def test_library_cover_line_is_said_at_most_once(self):
        cover = "The library does not cover this."
        repair = (
            "Replace the wall thermostat. If voltage is missing, check the wire run. "
            + cover
        )
        history = [
            {
                "role": "user",
                "content": (
                    "Suburban NT-20SEQT furnace. Jumped R/W at the furnace. "
                    "It lights and runs."
                ),
            }
        ]
        first = ensure_furnace_wall_thermostat(
            repair, history, "What is the repair?", "Furnaces", "Suburban NT-20SEQT"
        )
        self.assertEqual(first.lower().count("does not cover"), 1)
        self.assertIn("replace the wall thermostat", first.lower())
        again = ensure_furnace_wall_thermostat(
            repair,
            history + [{"role": "assistant", "content": first}],
            "What is the repair?",
            "Furnaces",
            "Suburban NT-20SEQT",
        )
        self.assertNotIn("does not cover", again.lower())
        self.assertIn("replace the wall thermostat", again.lower())
        self.assertIn("wire run", again.lower())

    def test_coleman_and_cooktop_are_not_this_furnace_commit(self):
        reply = "Check 12 VDC at the wall thermostat."
        self.assertEqual(
            ensure_furnace_wall_thermostat(
                reply, [], "What is the repair?", "Air Conditioning", "Coleman-Mach 2111-0001"
            ),
            reply,
        )


class TestCooktopTipLow(unittest.TestCase):
    def test_sdn2u_tip_low_states_the_repair_without_a_library_miss(self):
        complaint = (
            "Suburban SDN2U cooktop. Burner goes out with a pan on. "
            "The thermocouple tip sits low and gets pushed."
        )
        self.assertTrue(cooktop_tip_sits_low(complaint))
        self.assertTrue(
            is_cooktop_pan_on_flameout_context("Range & Cooktops", "Suburban SDN2U", complaint)
        )
        self.assertFalse(
            is_suburban_furnace_context("Range & Cooktops", "Suburban SDN2U", complaint)
        )
        miss = (
            "The library has no steps for this burner. "
            "The library has no procedure in the manual."
        )
        fixed = ensure_cooktop_tip_pan_check(miss, complaint)
        self.assertEqual(fixed, COOKTOP_TIP_LOW_REPAIR)
        low = fixed.lower()
        self.assertIn("reposition", low)
        self.assertIn("thermocouple tip", low)
        self.assertIn("pan", low)
        self.assertNotIn("library has no", low)
        self.assertNotIn("no steps", low)
        already = (
            "Reposition the thermocouple tip in the burner flame with the pan on."
        )
        cited = ensure_cooktop_tip_pan_check(already, complaint)
        self.assertIn("reposition", cited.lower())
        self.assertIn("page 4", cited.lower())
        self.assertIn("figs. 3-4", cited.lower())
        self.assertNotIn("does not cover", cited.lower())

    def test_library_cover_line_is_said_at_most_once(self):
        complaint = (
            "Suburban SDN2U cooktop. Burner goes out with a pan on. "
            "The thermocouple tip sits low and gets pushed."
        )
        reply = (
            "Reposition the thermocouple tip in the burner flame with the pan on. "
            "The library does not cover this. The library does not cover this."
        )
        first = ensure_cooktop_tip_pan_check(reply, complaint)
        self.assertNotIn("does not cover", first.lower())
        self.assertIn("reposition", first.lower())
        self.assertIn("page 4", first.lower())
        self.assertIn("figs. 3-4", first.lower())
        second = ensure_cooktop_tip_pan_check(
            reply,
            complaint,
            history=[{"role": "assistant", "content": first}],
        )
        self.assertNotIn("does not cover", second.lower())
        self.assertIn("page 4", second.lower())
        self.assertNotIn("library", second.lower())
        self.assertIn("reposition", second.lower())


if __name__ == "__main__":
    unittest.main()
