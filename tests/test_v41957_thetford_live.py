"""v4.19.57: the live library path, not the direct kit compile, keeps the Thetford sheet.

Live R2 is not on this machine. tests/fixtures/thetford_live_retrieval.json is the
900/120 chunk windows and figure labels the indexer stores for 42088, 42109, and
34123/34122. PNG bytes are read back from those same PDFs, which is what
attach_pngs does when the object is local.
"""
import json
import unittest
from pathlib import Path

import library_figure_backfill as fb
import manual_figures as mf
from bay_procedure import apply_chunk_figures, compile_bay_procedure, render_bay_procedure_pdf
from gd_library_coach import ensure_thetford_flush_reply

import scripts.profile_check as profile_check

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "thetford_live_retrieval.json"
ROOT = FIXTURE.parent
CONCERN = "Thetford 42070 leaks under the flush lever"
OM = "Thetford Style II OM Permanent RV Toilet 42088"


def _load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _png_index():
    found = {}
    for name in (
        "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf",
        "34123-34122-VacBrkr-1.pdf",
    ):
        indexed = mf.index_pdf_bytes((ROOT / name).read_bytes())
        for fig in indexed["figures"]:
            found[(fig.get("page"), fig.get("label") or "")] = fig.get("png") or b""
    return found


def _live_procedure():
    payload = _load()
    pngs = _png_index()
    chunks = list(payload["chunks"])
    rows = []
    for fig in payload["figures"]:
        row = dict(fig)
        row["png"] = pngs.get((fig.get("page"), fig.get("label") or ""), b"")
        row["category_name"] = "Plumbing / Toilets"
        rows.append(row)
    proc = compile_bay_procedure(
        concern=CONCERN,
        brand="Thetford",
        model="42070",
        category="Plumbing / Toilets",
        chunks=chunks,
    )
    job = f"{proc.category} {proc.brand} {proc.model} {proc.concern}"
    packets = fb.figure_packets(rows, chunks, job)
    for packet in packets:
        packet["figures"] = [fig for fig in packet.get("figures") or [] if fig.get("png")]
    packets = [packet for packet in packets if packet.get("figures")]
    return apply_chunk_figures(proc, packets)


class TestLiveRetrievalFixture(unittest.TestCase):
    def test_fixture_is_the_indexer_window_shape(self):
        payload = _load()
        self.assertIn("42088", payload["note"])
        self.assertGreaterEqual(len(payload["chunks"]), 10)
        self.assertTrue(any(len(chunk["excerpt"]) <= 900 for chunk in payload["chunks"]))
        titles = {chunk["title"] for chunk in payload["chunks"]}
        self.assertTrue(any("42088" in title for title in titles))
        self.assertTrue(any("42109" in title for title in titles))
        self.assertTrue(any("3412" in title for title in titles))
        labels = " ".join(fig["label"] for fig in payload["figures"])
        self.assertIn("Fig. 1", labels)


class TestLiveFigureAttachKeepsEveryBranch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = _live_procedure()
        cls.pdf = render_bay_procedure_pdf(cls.proc)

    def test_every_flowchart_outcome_keeps_a_branch(self):
        titles = " ".join(item.get("title") or "" for item in self.proc.procedures)
        self.assertIn("Supply", titles)
        self.assertRegex(titles, r"3412")
        self.assertIn("42109", titles)
        self.assertIn("Flange", titles)
        self.assertGreaterEqual(len(self.proc.procedures), 4)
        for procedure in self.proc.procedures:
            sections = {step.get("section") for step in procedure.get("steps") or []}
            self.assertIn("removal", sections, procedure.get("title"))
            self.assertIn("installation", sections, procedure.get("title"))
            for number, step in enumerate(procedure.get("steps") or [], 1):
                lines = mf.step_body_lines(step, show_figure=False)
                self.assertTrue(
                    any(line.startswith("Next:") for line in lines),
                    mf.step_heading(step, number),
                )
                heading = mf.step_heading(step, number)
                self.assertNotIn("Put the vot", heading)
                self.assertNotRegex(heading, r"\bwl\b")

    def test_tools_bad_do_not_and_flush_line(self):
        valve = next(item for item in self.proc.procedures if "42109" in (item.get("title") or ""))
        tool_blob = " ".join(
            [(step.get("fields") or {}).get("TOOLS / METER SETTING") or "" for step in valve.get("steps") or []]
            + list(valve.get("before") or [])
        )
        self.assertIn("wrench", tool_blob.lower())
        self.assertIn("plier", tool_blob.lower())
        self.assertNotRegex(tool_blob, r"(?i)^Tools: a towel\.?$")
        sheet = []
        for procedure in self.proc.procedures:
            for number, step in enumerate(procedure.get("steps") or [], 1):
                sheet.append(mf.step_heading(step, number))
                sheet.extend(mf.step_body_lines(step, show_figure=False))
        blob = "\n".join(sheet)
        self.assertNotIn("Flush 3 times. dry", blob)
        self.assertNotIn("tank hole in the floor", blob.lower())
        self.assertIn("holding tank opening at the closet flange", blob.lower())
        for kind in ("breaker", "valve"):
            actions = [
                step.get("text") or ""
                for step in (mf.thetford_kit_layout(kind).get("steps") or [])
            ]
            self.assertIn(
                "Uncover the holding tank opening at the closet flange.",
                actions,
                kind,
            )
        self.assertNotIn("Put the vot", blob)
        for line in blob.splitlines():
            if not line.startswith("Bad looks like:"):
                continue
            self.assertTrue(mf._bad_worth_printing(line.split(":", 1)[1]), line)
        do_not = " ".join(self.proc.do_not).lower()
        self.assertNotIn("antifreeze", do_not)
        self.assertNotIn("ice", do_not)
        self.assertNotIn("scouring", do_not)
        self.assertFalse(any("How (" in line for line in self.proc.bay_order))

    def test_review_sequence_quotes_and_figure_crop(self):
        breaker = next(item for item in self.proc.procedures if "3412" in (item.get("title") or ""))
        actions = [step.get("text") or "" for step in breaker.get("steps") or []]
        lift = next(i for i, action in enumerate(actions) if "Lift the toilet" in action)
        covers = next(i for i, action in enumerate(actions) if "bolt covers" in action and "Take off" in action)
        back = next(i for i, action in enumerate(actions) if "bolt covers back" in action)
        self.assertLess(covers, lift)
        self.assertLess(lift, back)
        self.assertTrue(any("two rings" in action and "larger" in action for action in actions))
        flange = next(item for item in self.proc.procedures if "Flange" in (item.get("title") or ""))
        flange_actions = [
            (step.get("section"), (step.get("text") or "").rstrip("."))
            for step in flange.get("steps") or []
        ]
        self.assertIn(("removal", "Lift the toilet off the floor"), flange_actions)
        self.assertIn(("removal", "Take off the old floor seal"), flange_actions)
        self.assertIn(("removal", "Pull the water hose off the toilet"), flange_actions)
        self.assertIn(("removal", "Cover the holding tank opening at the closet flange with a towel"), flange_actions)
        self.assertIn(("installation", "Uncover the holding tank opening at the closet flange"), flange_actions)
        height_step = next(step for step in flange.get("steps") or [] if "7/16" in (step.get("text") or ""))
        uncover_step = next(
            step for step in flange.get("steps") or [] if (step.get("text") or "").startswith("Uncover")
        )
        self.assertIn("Uncover the holding tank opening", (height_step.get("fields") or {}).get("NEXT") or "")
        self.assertNotIn("02125", (height_step.get("fields") or {}).get("NEXT") or "")
        self.assertIn("holding tank opening is clear", (uncover_step.get("fields") or {}).get("GOOD vs BAD") or "")
        self.assertNotIn("The opening is open", (uncover_step.get("fields") or {}).get("GOOD vs BAD") or "")
        self.assertIn(("installation", "Push the water hose onto the toilet"), flange_actions)
        hose_off = next(i for i, (section, action) in enumerate(flange_actions) if action == "Pull the water hose off the toilet")
        self.assertLess(hose_off, next(i for i, (_section, action) in enumerate(flange_actions) if action == "Lift the toilet off the floor"))
        hose_on = next(i for i, (section, action) in enumerate(flange_actions) if action == "Push the water hose onto the toilet")
        self.assertLess(next(i for i, (_section, action) in enumerate(flange_actions) if action == "Lift the toilet off the floor"), hose_on)
        height = next(i for i, (section, action) in enumerate(flange_actions) if "7/16" in action)
        install = next(i for i, (section, _action) in enumerate(flange_actions) if section == "installation")
        self.assertLess(height, install)
        quotes = {src.get("title") or "": src.get("excerpt") or "" for src in self.proc.sources}
        valve_quote = next(quote for title, quote in quotes.items() if "42109" in title)
        owner_quote = next(quote for title, quote in quotes.items() if "42088" in title)
        self.assertNotEqual(valve_quote, owner_quote)
        self.assertNotIn("supply line", valve_quote.lower())
        self.assertRegex(valve_quote.lower(), r"water valve|pedal|inlet|retainer")
        import io

        from PIL import Image

        indexed = mf.index_pdf_bytes((ROOT / "42109_SK_WaterValve_StyleII_Res_42049C-1.pdf").read_bytes())
        fig3 = next(fig for fig in indexed["figures"] if (fig.get("label") or "").startswith("Fig. 3"))
        self.assertIn("WATER VALVE CLOSED POSITION", fig3["label"])
        image = Image.open(io.BytesIO(fig3["png"]))
        try:
            self.assertLessEqual(image.size[1], image.size[0] * 1.35, image.size)
            with Image.open(ROOT / "thetford_live_library" / "cache" / "library" / "doc1-p1-4.png") as cached:
                self.assertEqual(cached.size, image.size)
        finally:
            image.close()

    def test_profile_check_has_no_fail(self):
        rules = profile_check.check_pdf_bytes(self.pdf)
        failed = [rule for rule in rules if rule.status == "FAIL"]
        self.assertEqual(failed, [], failed)
        named = {rule.name: rule for rule in rules}
        self.assertEqual(named["PF-10"].status, "PASS")
        self.assertEqual(named["PF-15"].status, "PASS")
        self.assertIn("Result: 10/10.", profile_check.gate_summary(rules))
        manual = [rule.name for rule in rules if rule.name.startswith("PF-") and rule.status == "MANUAL"]
        self.assertEqual(manual, ["PF-32"])


class TestShowMeReply(unittest.TestCase):
    def test_supply_show_me_names_the_connection_and_page_3(self):
        supply = mf.thetford_proving_line("supply")
        self.assertIn("back of the toilet, on the water valve", supply)
        self.assertIn("page 3", supply)
        history = [
            {"role": "user", "content": CONCERN},
            {"role": "assistant", "content": supply},
        ]
        reply = ensure_thetford_flush_reply(
            "How (Thetford, page 7): Tools: not stated. Meter setting: not stated.",
            history,
            "show me",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertIn("back of the toilet, on the water valve", reply)
        self.assertNotIn("How (", reply)
        self.assertNotIn("Meter setting: not stated", reply)
        page7 = {
            "id": 7,
            "document_id": 9,
            "kind": "figure",
            "title": OM,
            "brand": "Thetford",
            "page": 7,
            "label": "Step 1",
            "png": b"\x89PNG\r\n\x1a\npage7",
            "category_name": "Plumbing / Toilets",
        }
        page3 = {
            "id": 3,
            "document_id": 9,
            "kind": "page",
            "title": OM,
            "brand": "Thetford",
            "page": 3,
            "label": "page",
            "png": b"\x89PNG\r\n\x1a\npage3",
            "category_name": "Plumbing / Toilets",
        }
        offers = fb.offers_for_turn(
            [page7, page3], supply, "it leaks under the lever", "Plumbing / Toilets", "Thetford 42070"
        )
        self.assertEqual(len(offers), 1)
        self.assertEqual(int(offers[0]["page"]), 3)
        caption = fb.gd_figure_caption(offers[0])
        self.assertIn("page 3", caption)
        self.assertNotIn("page 7", caption)
        self.assertNotIn("Step 1", caption)

    def test_the_valve_turn_names_the_place_and_the_tools(self):
        history = [
            {"role": "user", "content": CONCERN},
            {"role": "assistant", "content": "Check the supply connection."},
            {"role": "user", "content": "The supply connection is dry."},
            {"role": "assistant", "content": "Check the vacuum breaker."},
        ]
        reply = ensure_thetford_flush_reply(
            "",
            history,
            "No leak while flushing. The water valve weeps at the pedal.",
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        self.assertIn("Go to the water valve.", reply)
        self.assertIn("Use a 1/2-inch wrench and pliers.", reply)
        self.assertNotIn("Where:", reply)
        self.assertNotIn("Tools:", reply)


class TestBayTabCopy(unittest.TestCase):
    def test_the_form_describes_branches(self):
        source = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text(encoding="utf-8")
        self.assertIn("Repair branches:", source)
        self.assertNotIn("Bay-order steps:", source)
        self.assertIn("one numbered branch", source)


class TestReviewDefectsFail(unittest.TestCase):
    """The pre-merge misses stay failures. A clean sheet is not a weaker check."""

    def test_bare_vacuum_near_copy_marker_and_page_clash_fail(self):
        bare = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\n"
            "Check the vacuum breaker on page 3.\n"
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(bare)}
        self.assertEqual(named["score-2"].status, "FAIL")
        clash = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\n"
            "Bad result: it leaks while flushing. What do you see? Owner manual page 1 shows the kit.\n"
            "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(clash)}
        self.assertEqual(named["score-1"].status, "FAIL")
        copied = (
            "The water supply connection is at the back of the toilet on the water valve "
            "and the fitting should be dry before you open a kit."
        )
        dup = (
            f"USER: one\nASSISTANT:\n{copied}\n\n"
            f"USER: two\nASSISTANT:\n{copied} The cited manual page shows that connection.\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(dup)}
        self.assertEqual(named["no_repeats"].status, "FAIL")
        leaked = "USER: one\nASSISTANT:\nPull the pedal up and off.\n<!--gd-step:1-->\n"
        banned = [rule for rule in profile_check.check_transcript(leaked) if rule.name == "banned_strings"]
        self.assertEqual(banned[0].status, "FAIL")

    def test_duplicate_pod_and_scouring_fail(self):
        pod = (
            "Thetford 42070\n"
            "REPAIR BRANCH\nVacuum breaker 34123\n"
            "REMOVAL\n"
            "Step 12: Take off the pod\nDo this:\n1. Take off the pod.\n"
            "Step 14: Take off the pod\nDo this:\n1. Take off the pod.\n"
        )
        named = {rule.name: rule for rule in profile_check.grade_past_fails(None, pod)}
        self.assertEqual(named["PF-09"].status, "FAIL")
        banned = [
            rule
            for rule in profile_check.check_transcript(
                "USER: x\nASSISTANT:\nDo not use scouring powders.\n"
            )
            if rule.name == "banned_strings"
        ]
        self.assertEqual(banned[0].status, "FAIL")

    def test_lift_before_fasteners_and_a_cut_quote_fail(self):
        lifted = (
            "Thetford 34123\nREPAIR BRANCH\nVacuum breaker\nREMOVAL\n"
            "Step 7: Pull the water hose off the toilet\nDo this:\n"
            "1. Pull the water hose off the toilet.\n"
            "Step 8: Lift the toilet off the floor\nDo this:\n"
            "1. Lift the toilet off the floor.\n"
        )
        rule = profile_check._fastener_sequence(lifted)
        self.assertFalse(rule.ok, rule.detail)
        self.assertIn("lifted", rule.detail)
        bare_flange = (
            "Thetford 42070\nREPAIR BRANCH\nFlange and seal\nREMOVAL\n"
            "Step 1: Take the nuts off the floor bolts\nDo this:\n"
            "1. Take the nuts off the floor bolts.\n"
            "Step 2: Lift the toilet off the floor\nDo this:\n"
            "1. Lift the toilet off the floor.\n"
            "Step 3: Cover the holding tank opening at the closet flange with a towel\nDo this:\n"
            "1. Cover the holding tank opening at the closet flange with a towel.\n"
            "INSTALLATION\n"
            "Step 4: Uncover the holding tank opening at the closet flange\nDo this:\n"
            "1. Uncover the holding tank opening at the closet flange.\n"
            "Step 5: Set the toilet on the floor bolts\nDo this:\n"
            "1. Set the toilet on the floor bolts.\n"
            "Step 6: Tighten the nuts until the toilet does not rock\nDo this:\n"
            "1. Tighten the nuts until the toilet does not rock.\n"
        )
        rule = profile_check._fastener_sequence(bare_flange)
        self.assertFalse(rule.ok, rule.detail)
        self.assertIn("water hose", rule.detail)
        high = (
            "Thetford 42070\nREPAIR BRANCH\nFlange\nREMOVAL\n"
            "Step 1: Take the nuts off the floor bolts\nDo this:\n"
            "1. Take the nuts off the floor bolts.\n"
            "INSTALLATION\n"
            "Step 2: Tighten the nuts until the toilet does not rock\nDo this:\n"
            "1. Tighten the nuts until the toilet does not rock.\n"
            "Step 3: Check the flange is 7/16 inch above the floor\nDo this:\n"
            "1. Check the flange is 7/16 inch above the floor.\n"
        )
        rule = profile_check._fastener_sequence(high)
        self.assertFalse(rule.ok, rule.detail)
        self.assertIn("Installation", rule.detail)
        cut = (
            "Thetford 34123\n"
            "Step 39: Secure back of cover on top and smaller on bottom\n"
            "Do this:\n1. Secure back of cover on top and smaller on bottom.\n"
        )
        rule = profile_check._mid_phrase_gap(cut)
        self.assertFalse(rule.ok, rule.detail)
        kept = (
            "Thetford 34123\n"
            "Step 42: Secure back of cover with two rings - larger on top and smaller on bottom\n"
            "Do this:\n"
            "1. Secure back of cover with two rings - larger on top and smaller on bottom.\n"
        )
        rule = profile_check._mid_phrase_gap(kept)
        self.assertTrue(rule.ok, rule.detail)

    def test_a_copied_or_missing_valve_quote_fails(self):
        copied = (
            "42109\nSOURCES (SHOP DOCUMENT LIBRARY)\n"
            "- Thetford Style II OM Permanent RV Toilet 42088 page 3\n"
            "Check the water supply line connection at the water valve.\n"
            "- Thetford Water Valve Kit 42109 page 1\n"
            "Check the water supply line connection at the water valve.\n"
        )
        rule = profile_check._source_doc_quotes(copied)
        self.assertFalse(rule.ok, rule.detail)
        missing = (
            "42109\nSOURCES (SHOP DOCUMENT LIBRARY)\n"
            "- Thetford Water Valve Kit 42109 page 1\n"
        )
        rule = profile_check._source_doc_quotes(missing)
        self.assertFalse(rule.ok, rule.detail)
        own = (
            "42109\nSOURCES (SHOP DOCUMENT LIBRARY)\n"
            "- Thetford Style II OM Permanent RV Toilet 42088 page 3\n"
            "Back of toilet: check water supply line connection at water valve.\n"
            "- Thetford Vacuum Breaker Kit 34123/34122 page 1\n"
            "With pliers, slide clamp A down inlet tube, then remove inlet tube from vacuum breaker.\n"
            "- Thetford Water Valve Kit 42109 page 1\n"
            "Insert new Water Valve Cartridge Assembly until fully seated.\n"
        )
        rule = profile_check._source_doc_quotes(own)
        self.assertTrue(rule.ok, rule.detail)
        paraphrase = (
            "42109\nSOURCES (SHOP DOCUMENT LIBRARY)\n"
            "- Thetford Style II OM Permanent RV Toilet 42088 page 3\n"
            "Check the water supply line connection at the water valve.\n"
            "- Thetford Vacuum Breaker Kit 34123/34122 page 1\n"
            "Slide clamp A down the inlet tube.\n"
            "- Thetford Water Valve Kit 42109 page 1\n"
            "Lay the toilet on its side with the pedal up.\n"
        )
        rule = profile_check._source_doc_quotes(paraphrase)
        self.assertFalse(rule.ok, rule.detail)
        self.assertIn("verbatim", rule.detail)

    def test_a_bare_valve_start_fails_and_a_tall_crop_fails(self):
        bare = (
            "USER: No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\nTurn off the water to the RV.\nWhat do you see?\n"
            "📖 Source: Thetford Water Valve Kit 42109, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(bare)}
        self.assertEqual(named["score-2"].status, "FAIL")
        named_place = (
            "USER: No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\nGo to the water valve.\nUse a 1/2-inch wrench and pliers.\n"
            "Turn off the water to the RV.\nA bad result is water still comes out.\n"
            "What do you see?\n"
            "📖 Source: Thetford Water Valve Kit 42109, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(named_place)}
        self.assertNotEqual(named["score-2"].status, "FAIL")

    def test_a_repeated_finding_unlabeled_result_and_pliers_fail(self):
        weep = (
            "USER: Thetford 42070 leaks under the flush lever\n"
            "ASSISTANT:\n"
            "Go to the water valve. A good result is it stays tight. "
            "A bad result is water comes out. Report what you see?\n"
            "📖 Source: 42088, page 3\n\n"
            "USER: No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\n"
            "Check the cartridge for a weep. A good result is a dry pedal. "
            "A bad result is a weep at the pedal. Report what you see?\n"
            "📖 Source: 42109, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(weep)}
        self.assertFalse(named["repeats_established_finding"].ok)
        plain = (
            "USER: Thetford 42070 leaks under the flush lever\n"
            "ASSISTANT:\n"
            "Go to the water valve. It stays tight. Water comes out. What do you see?\n"
            "📖 Source: 42088, page 3\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(plain)}
        self.assertFalse(named["labeled_good_bad"].ok)
        self.assertTrue(named["report_back"].ok)
        silent = (
            "USER: Thetford 42070 leaks under the flush lever\n"
            "ASSISTANT:\n"
            "Go to the water valve. A good result is it stays tight. "
            "A bad result is water comes out.\n"
            "📖 Source: 42088, page 3\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(silent)}
        self.assertFalse(named["report_back"].ok)
        pliers = (
            "USER: The supply connection is dry.\n"
            "ASSISTANT:\n"
            "Go to the vacuum breaker. Use pliers. You flush and watch it. "
            "A good result is no leak. A bad result is it leaks. Report what you see?\n"
            "📖 Source: 34123, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(pliers)}
        self.assertFalse(named["tools_fit_the_action"].ok)
        repair = (
            "USER: Thetford 42070. No leak while flushing. The water valve weeps at the pedal.\n"
            "ASSISTANT:\n"
            "Turn the RV water off. Go to the water valve at the pedal. "
            "Use a 1/2-inch wrench and pliers. Seat the new cartridge. "
            "A good result is the new cartridge is seated. "
            "A bad result is the old cartridge is still in. Report what you see?\n"
            "📖 Source: 42109, page 1\n"
        )
        named = {rule.name: rule for rule in profile_check.check_transcript(repair)}
        self.assertTrue(named["repeats_established_finding"].ok)
        self.assertTrue(named["labeled_good_bad"].ok)
        self.assertTrue(named["report_back"].ok)
        self.assertTrue(named["tools_fit_the_action"].ok)
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 700), 0)
        pix.clear_with(255)
        page.insert_image(pymupdf.Rect(36, 80, 441, 700), pixmap=pix)
        problems = profile_check._soft_or_cut_figures(doc)
        self.assertTrue(any("caption fills" in item for item in problems), problems)
        doc.close()
