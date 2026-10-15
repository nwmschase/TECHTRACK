from bay_procedure import _action_heading


def test_condition_heading_becomes_action():
    assert _action_heading("If the fuse is open, replace the fuse") == "Replace the fuse"
    assert not _action_heading("If fully retracted, it is advisable to use the hand").lower().startswith("if")
    assert _action_heading("Check the fuse") == "Check the fuse"
