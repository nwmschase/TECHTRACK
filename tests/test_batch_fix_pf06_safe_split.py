from bay_procedure import split_long_action

SRC = ("Turn off power at the breaker, disconnect the battery cable at the battery terminal, "
       "check the fuse in the panel box.")


def _words(text):
    return [w.strip(".,;").lower() for w in text.split()]


def test_safe_split_keeps_words_and_verbs():
    lines = split_long_action(SRC)
    assert len(lines) > 1
    assert _words(" ".join(lines)) == _words(SRC)
    for line in lines:
        assert len(line.split()) <= 15
        assert not line.lower().startswith(("and ", "or "))


def test_no_safe_cut_stays_whole():
    src = "Remove the dump valve assembly and bench test it by applying power and ground to the coil (not polarity sensitive)."
    assert split_long_action(src) == [src]
