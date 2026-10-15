from bay_procedure import _fix_title_case_runon


def test_title_case_word_lowered_words_kept():
    src = "Measure at the controller Power input on the Furrion unit."
    out = _fix_title_case_runon(src)
    assert out == "Measure at the controller power input on the Furrion unit."
    assert out.lower() == src.lower()
