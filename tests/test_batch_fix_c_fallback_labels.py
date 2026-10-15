from bay_procedure import _label_fallback_steps


def test_fallback_steps_carry_required_labels():
    out = _label_fallback_steps([
        "Pull the catch pawl and continue to extend the stabilizer until it is halfway extended. If this check fails, stay on it.",
        "Keep clear and use caution.",
    ])
    assert len(out) == 2
    for step in out:
        assert "Do this: 1." in step
        assert "Good looks like:" in step
        assert "Next:" in step
    assert "stay on it." not in out[0].split("Do this:")[1].split("Good")[0]


def test_fallback_empty_when_nothing_usable():
    assert _label_fallback_steps(["NOTE", "WARNING: risk of injury."]) == []
