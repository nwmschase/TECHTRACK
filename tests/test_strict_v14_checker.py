"""Strict PDF v1.4 reading: the misses Leader found on the rev2 live sheet."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bay_profile_lines as bpl  # noqa: E402


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
