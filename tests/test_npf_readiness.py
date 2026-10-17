"""General rule: No Problem Found needs a recorded inspection of the complaint's path, not just operating the unit (RC27 class).
'Operating as designed' after a repair is a close-out and is untouched. Negated condemns are not condemns."""
import gd_official as go

RUN_ONLY = ("Ran it on customer settings with doors closed and gave it a full pull-down: freezer came down first, then the fridge "
            "reached about 38F. Display looked normal with no fault codes; compressor and fans were running as expected.")
INSPECT = "Removed rear interior airflow cover: no ice, debris or blockage in the freezer-to-fridge passage."
NPF = "No Problem Found - operating as designed.\n\nCustomer explanation: the freezer cools first."


def test_npf_without_inspection_is_held():
    assert go.npf_unready(NPF, [RUN_ONLY])
    out = go.hold_npf_inspection(NPF)
    assert "No Problem Found - operating" not in out and "Customer explanation" not in out
    assert out.startswith("Not No Problem Found yet")


def test_npf_after_inspection_is_allowed():
    assert not go.npf_unready(NPF, [RUN_ONLY, INSPECT])


def test_pending_inspection_does_not_count():
    assert go.npf_unready(NPF, [RUN_ONLY, "Haven't pulled the airflow cover yet; that check is still pending."])


def test_as_designed_after_a_repair_is_a_close_out():
    for done in ["Reseat already done: sensor in the coil, no E3 for 30 minutes.", "Probe is in the coil after reseat; ran COOL, no E3.",
                 "Petit tube already aimed away from the wheel, no E8.", "Zero Point Calibration ENTER to set; set it. Auto level OK.",
                 "Fix complete: no part replaced."]:
        assert not go.npf_unready(NPF, [RUN_ONLY, done]), done


def test_npf_held_while_complaint_present_still_wins():
    assert go.npf_blocked(NPF, ["The fridge is still warm after 6 hours; complaint is still present."])


def test_negated_condemn_is_not_a_condemn():
    assert go.condemned_parts("Condemn no parts.\nDo not replace the valve.\nReplace the fuse.") == ["fuse"]
