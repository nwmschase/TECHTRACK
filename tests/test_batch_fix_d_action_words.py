from bay_procedure import _fit_action_words


def test_long_action_splits_at_its_own_clause_marks():
    out = _fit_action_words([
        "If fully retracted, it is advisable to use the hand crank to turn each jack a few turns before engaging the motors"
    ])
    assert out and all(len(a.split()) <= 15 for a in out)


def test_short_action_unchanged():
    assert _fit_action_words(["Check the fuse."]) == ["Check the fuse."]


def test_unsplittable_long_action_drops():
    long = " ".join(["word"] * 20)
    assert _fit_action_words([long]) == []
