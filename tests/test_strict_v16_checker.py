"""Leader rev4 page review (rev5): Bad lines that only negate Good, two figure numbers,
captions named after the step, and fragment Do-this items fail on their own."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import profile_check as pc  # noqa: E402
from test_strict_v14_checker import GOOD_BRANCH, _sheet  # noqa: E402
from test_strict_v15_checker import _step  # noqa: E402


def _named(text):
    return {r.name: r for r in pc._strict_v14(text)}


def test_opposite_word_bad_fails():
    for good, bad in (
        ("The clamp is tight.", "The clamp is loose."),
        ("The bowl water goes down.", "The bowl water stays up."),
        ("The tab locks in place.", "The tab does not lock."),
        ("The cover wraps the back.", "The cover does not wrap the back."),
    ):
        named = _named(_sheet(_step(1, "Do the thing", good, bad, "This branch is complete.")))
        assert not named["bad_is_specific"].ok, (good, bad)


def test_symptom_bad_still_passes():
    named = _named(_sheet(_step(1, "Tighten the inlet tube with the new clamp A", "The clamp is tight.",
                                "The inlet tube turns under the clamp.", "This branch is complete.")))
    assert named["bad_is_specific"].ok, named["bad_is_specific"].detail


def test_two_figure_numbers_fail():
    text = _sheet(GOOD_BRANCH) + "Fig. 2 PEDAL REMOVED (kit Fig. 1), Thetford Kit 42109, page 1\n"
    assert not _named(text)["figure_captions"].ok


def test_caption_named_after_the_step_fails():
    body = _step(1, "Slide clamp A down the inlet tube", "The clamp has moved.", nxt="This branch is complete.")
    text = _sheet(body) + "Fig. 1 SLIDE CLAMP A DOWN THE INLET TUBE, Thetford Kit 34122, page 1\n"
    assert not _named(text)["figure_captions"].ok
    text = _sheet(body) + "Fig. 1 COMPONENT LOCATIONS, Thetford Kit 34122, page 1\n"
    assert _named(text)["figure_captions"].ok, _named(text)["figure_captions"].detail


def test_fragment_do_item_fails():
    body = _step(1, "Secure the back of the cover with two rings", "Both rings are on.", nxt="This branch is complete.")
    bad = body.replace("Good looks like", "2. Larger on top and smaller on bottom.\nGood looks like")
    assert not _named(_sheet(bad))["do_item_is_action"].ok
    good = body.replace("Good looks like", "2. Put the larger ring on top and the smaller ring on the bottom.\nGood looks like")
    assert _named(_sheet(good))["do_item_is_action"].ok


def test_builder_caption_uses_the_manual_label_and_one_number():
    import bay_procedure as bp

    text = "4 Refer to Figure 1 for component \nlocations. Style Lite shown."
    assert bp.manual_figure_label("Fig. 1", text) == "Fig. 1 COMPONENT LOCATIONS"
    assert bp.manual_figure_label("Fig. 2", text) == "Fig. 2"
    assert bp.manual_figure_label("FIGURE 1 - PEDAL REMOVED", text) == "FIGURE 1 - PEDAL REMOVED"

    class Body:
        figure_count = 1

    cap = bp._sheet_figure_caption(Body(), "Figure 1 PEDAL REMOVED, Kit 42109, page 1", "Pull the pedal off")
    assert cap == "Fig. 2 PEDAL REMOVED, Kit 42109, page 1"
    assert "PULL THE PEDAL" not in bp._sheet_figure_caption(Body(), "Fig. 1, Kit 34122, page 1", "Pull the pedal off")
