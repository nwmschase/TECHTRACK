from bay_procedure import _label_fallback_steps


def test_every_fallback_line_kept_and_labeled():
    lines = [
        "Pull the catch pawl and extend the stabilizer. If this check fails, stay on it. If it passes, go to the next check.",
        "Record the complaint, the model name, and the first cited check on this sheet.",
        "Retest the complaint after those checks.",
    ]
    out = _label_fallback_steps(lines)
    assert len(out) == len(lines)
    for step in out:
        for label in ("Do this: 1.", "Good looks like:", "Next:"):
            assert label in step
    assert "Pull the catch pawl and extend the stabilizer." in out[0]


def test_fallback_step_line_one_is_not_the_heading():
    out = _label_fallback_steps(["Keep clear and use caution."])
    assert "Where: At the part named in this step." in out[0]
