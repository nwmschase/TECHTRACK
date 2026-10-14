"""Strict PDF v1.4 reading: the misses Leader found on the rev2 live sheet."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bay_profile_lines as bpl  # noqa: E402
import profile_check as pc  # noqa: E402


def _sheet(branch_body: str, diagnosis: str = "", before: str = "- Turn the RV water off before this work.") -> str:
    diag = diagnosis or (
        "Step 1: Check the hose at the valve\nWhere: Back of the toilet.\nDo this:\n1. Check the hose.\n"
        "Good looks like: The hose is dry.\nNext: Go to the next check.\n"
    )
    return f"DIAGNOSIS\n{diag}REPAIR BRANCH\nPart\nBEFORE YOU START\n{before}\nREMOVAL\n{branch_body}DO NOT\n- Do not rush.\n"


GOOD_BRANCH = (
    "Step 1: Pull the water hose off the water valve\nWhere: At the water valve.\nDo this:\n1. Pull it.\n"
    "Good looks like: The hose is off.\nNext: Push the water hose onto the water valve.\n"
    "INSTALLATION\nStep 2: Push the water hose onto the water valve\nWhere: At the water valve.\nDo this:\n1. Push it.\n"
    "Good looks like: The hose is fully on.\nNext: Tighten the hose clamp.\n"
    "Step 3: Tighten the hose clamp\nWhere: At the water valve.\nDo this:\n1. Tighten.\n"
    "Good looks like: The clamp is tight.\nNext: Confirm the repair is dry.\n"
    "VERIFY\nStep 4: Confirm the repair is dry\nWhere: At the water valve.\nDo this:\n1. Look.\n"
    "Good looks like: The repair is dry.\nNext: This branch is complete.\n"
)


def _named(text):
    return {r.name: r for r in pc._strict_v14(text)}


def test_clean_sheet_passes_every_strict_rule():
    named = _named(_sheet(GOOD_BRANCH))
    assert all(r.ok for r in named.values()), [r for r in named.values() if not r.ok]


def test_missing_where_fails():
    assert not _named(_sheet(GOOD_BRANCH.replace("Where: At the water valve.\nDo this:\n1. Tighten.", "Do this:\n1. Tighten.")))["where_lines"].ok


def test_where_that_is_not_a_place_fails():
    assert not _named(_sheet(GOOD_BRANCH.replace("Where: At the water valve.\nDo this:\n1. Tighten.", "Where: At the seal and.\nDo this:\n1. Tighten.")))["where_lines"].ok


def test_non_profile_label_fails():
    text = _sheet(GOOD_BRANCH.replace("Next: Tighten the hose clamp.", "If it fails: Push again.\nNext: Tighten the hose clamp."))
    assert not _named(text)["profile_labels"].ok


def test_diagnosis_action_step_fails():
    diag = "Step 1: Pull the pedal off\nWhere: At the pedal.\nDo this:\n1. Pull.\nGood looks like: Off.\nNext: Go on.\n"
    assert not _named(_sheet(GOOD_BRANCH, diagnosis=diag))["diagnosis_checks"].ok


def test_before_you_start_contradiction_fails():
    body = GOOD_BRANCH.replace("Pull the water hose off the water valve\n", "Lift the toilet off the floor\n", 1)
    text = _sheet(body, before="- Leave the toilet in place if you have room.")
    assert not _named(text)["before_conflict"].ok


def test_safety_restating_action_twice_fails():
    body = GOOD_BRANCH.replace("Where: At the water valve.\nDo this:\n1. Tighten.",
                               "Safety: Tighten the hose clamp for the test.\nWhere: At the water valve.\nDo this:\n1. Tighten.")
    assert not _named(_sheet(body))["safety_duplicate"].ok


def test_double_removal_fails():
    body = (
        "Step 1: Unhook the cover\nWhere: At the cover.\nDo this:\n1. Unhook.\nGood looks like: The cover is off.\nNext: Pull the cover off.\n"
        "Step 2: Pull the cover off\nWhere: At the cover.\nDo this:\n1. Pull.\nGood looks like: The cover is off.\nNext: Confirm the repair is dry.\n"
        "VERIFY\nStep 3: Confirm the repair is dry\nWhere: At the cover.\nDo this:\n1. Look.\nGood looks like: Dry.\nNext: This branch is complete.\n"
    )
    assert not _named(_sheet(body))["double_removal"].ok


def test_hose_never_secured_fails():
    body = GOOD_BRANCH.replace("Tighten the hose clamp", "Wipe the valve")
    assert not _named(_sheet(body))["secure_after_hose"].ok


def test_next_pointing_past_confirm_fails():
    body = GOOD_BRANCH.replace("Next: Confirm the repair is dry.", "Next: Flush the toilet three times.")
    assert not _named(_sheet(body))["next_chain"].ok


def test_bare_and_duplicate_figure_captions_fail():
    assert not _named(_sheet(GOOD_BRANCH) + "Fig. 1\n")["figure_captions"].ok
    twice = _sheet(GOOD_BRANCH) + "Fig. 1 PEDAL REMOVED\nFig. 1 COVER\n"
    assert not _named(twice)["figure_captions"].ok
    named = _sheet(GOOD_BRANCH) + "Fig. 1 CLAMP, Kit A, page 1\nFig. 2 PEDAL, Kit B, page 1\n"  # v4.19.60: numbered across the sheet
    assert _named(named)["figure_captions"].ok


def test_agreement_and_letter_labels_and_vague_it_fail():
    for bad in ("The pod rings is off.", "The seal and spring is off.", "The new clamp a is on.", "It is back on."):
        body = GOOD_BRANCH.replace("Good looks like: The clamp is tight.", f"Good looks like: {bad}")
        assert not _named(_sheet(body))["grammar"].ok, bad


def test_scorecard_auto_fails_line_eight_on_contradiction():
    body = GOOD_BRANCH.replace("Pull the water hose off the water valve\n", "Lift the toilet off the floor\n", 1)
    text = _sheet(body, before="- Leave the toilet in place if you have room.")
    cards = {r.name: r for r in pc.grade_pdf(text, pc.check_sheet_text(text))}
    line8 = [r for r in cards.values() if r.name.endswith("8") or " 8" in r.name or "08" in r.name]
    assert line8 and not line8[0].ok


def test_builder_lines_conform():
    heading, lines = bpl.conform_lines(
        "Step 4: Take off the pod rings",
        ["Do this:", "1. Take off the pod rings.", "Good looks like: The pod rings is off.", "If it fails: Pull harder.",
         "Next: Flush."],
        previous_where="", previous_object="", next_action="Take off the pod", figure_ref="Fig. 2",
    )
    text = "\n".join(lines)
    assert "If it fails" not in text
    assert "Where: At the pod rings. See Fig. 2." in text
    assert "The pod rings are off." in text
    assert "Next: Take off the pod." in text


def test_builder_helpers():
    assert bpl.fix_agreement("The seal and spring is off.") == "The seal and spring are off."
    assert bpl.fix_agreement("The nuts are tight and the flange is dry.") == "The nuts are tight and the flange is dry."
    assert bpl.where_place("The toilet sits on the floor.") == "On the floor."
    assert bpl.where_from_action("Throw the inlet seal and spring away") in ("At the inlet seal.", "At the inlet seal and spring.")
    assert bpl.resolve_action_it("Tighten it with new clamp C", "the new flush hose") == "Tighten the new flush hose with new clamp C"
    assert bpl.before_conflicts(["Leave the toilet in place if you have room."], ["Lift the toilet off the floor."])
