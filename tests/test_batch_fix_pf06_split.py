from bay_procedure import split_long_action

LONG = ("If the catch pawl is damaged or otherwise cannot be pulled up, "
        "proceed to step 10, remove catch pawl, and return to step 6.")


def test_long_action_splits_and_keeps_every_word():
    lines = split_long_action(LONG)
    assert len(lines) > 1
    assert all(len(x.split()) <= 15 for x in lines)
    assert " ".join(lines).split() == LONG.split()


def test_short_or_unmarked_action_stays_whole():
    assert split_long_action("Check the fuse.") == ["Check the fuse."]
    w = " ".join(["word"] * 20)
    assert split_long_action(w) == [w]
