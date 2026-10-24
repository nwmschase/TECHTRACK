"""Leader rev4 page review (rev5): Bad lines that only negate Good, two figure numbers,
captions named after the step, and fragment Do-this items fail on their own."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from test_strict_v14_checker import GOOD_BRANCH, _sheet  # noqa: E402
from test_strict_v15_checker import _step  # noqa: E402


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
