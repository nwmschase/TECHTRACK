"""Leader rev5 page review (rev6): Where fixes that still apply to the manual figure steps.

The Bay PDF sheet checks in this file were removed with the Bay PDF builder (Chase 2026-10-24).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_trash_bag_where_is_a_place():
    import manual_figures as mf

    assert mf._where_field("Remove toilet from floor and place on plastic trash bag.").startswith("On the trash bag")
