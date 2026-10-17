"""General rule: a condemn given in the same reply as an unconditional upstream 'first' correction waits for that correction's result."""
import gd_official as go

FIRST = "Correct the 12 V supply first so it holds 10.5-13.5 VDC under load. [Library: M p.10]"


def test_condemn_alongside_first_fix_becomes_conditional():
    out = go.sequence_condemns(FIRST + "\nReplace the control module board. [Library: M p.17]")
    lines = out.splitlines()
    assert lines[0] == FIRST
    assert lines[1].startswith("Only if the complaint remains after that first correction")
    assert "replace the control module board" in lines[1]


def test_negated_and_conditional_lines_untouched():
    r = FIRST + "\nCoil is in spec; do not replace the valve. [Library: M p.22]\nIf the drop remains, replace the board. [Library: M p.17]"
    assert go.sequence_condemns(r) == r


def test_no_first_fix_leaves_reply_alone():
    r = "Replace the 15A fuse in the front holder. [Library: M p.19]\nVERIFY: power up and confirm the light."
    assert go.sequence_condemns(r) == r


def test_conditional_first_fix_does_not_trigger():
    r = "If the supply is low, correct it first. [Library: M p.10]\nReplace the board. [Library: M p.17]"
    assert go.sequence_condemns(r) == r


def test_verify_line_not_rewritten():
    r = FIRST + "\nVERIFY after you replace nothing else: run 3 cycles."
    assert go.sequence_condemns(r) == r
