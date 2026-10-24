"""Leader rev3 page review (v4.19.60): misses that must fail on their own, and the builder repairs."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bay_profile_lines as bpl  # noqa: E402
from test_strict_v14_checker import GOOD_BRANCH, _sheet  # noqa: E402


def _step(n, action, good, bad="", nxt="", where="At the toilet."):
    lines = [f"Step {n}: {action}", f"Where: {where}", "Do this:", f"1. {action}.", f"Good looks like: {good}"]
    if bad:
        lines.append(f"Bad looks like: {bad}")
    lines.append(f"Next: {nxt or 'Go on.'}")
    return "\n".join(lines) + "\n"


# ---- builder ---------------------------------------------------------------

def _mk(how, where, good, bad, nxt, section="removal", fail="", tools=""):
    return {"section": section, "text": how.rstrip("."), "actions": [how], "fields": {
        "WHERE": where, "HOW": how.rstrip("."), "GOOD vs BAD": f"Good: {good} Bad: {bad}", "NEXT": f"On good: {nxt}"}}


def _action(step):
    return step["fields"]["HOW"]


def _gb(step):
    text = step["fields"]["GOOD vs BAD"]
    good, _, bad = text.partition(" Bad: ")
    return good.replace("Good: ", ""), bad


def test_repair_branch_adds_clamp_old_part_and_mate():
    steps = [
        _mk("Pull the inlet seal and spring off the inlet hole.", "In the hole.", "They are off.", "", ""),
        _mk("Throw the inlet seal and spring away.", "At the bag.", "In the trash.", "", ""),
        _mk("Take off the vacuum breaker.", "At the breaker.", "Off.", "", ""),
        _mk("Put the new flush hose on the nozzle.", "On the nozzle.", "On.", "", "", section="installation"),
        _mk("Put the inlet seal in the inlet hole.", "In the hole.", "The inlet seal is in.", "", "", section="installation"),
        _mk("Push the water hose onto the toilet.", "At the toilet.", "The hose is on tight.", "", "", section="installation"),
        _mk("Turn the RV water on.", "At the toilet.", "Dry.", "", "", section="installation"),
    ]
    secure = _mk("Secure or tighten the supply line connection at the water valve.", "At the valve.", "Snug and dry.", "", "")
    assert [_action(s) for s in bpl.repair_branch(steps, _action, _gb, _mk)].count(_action(secure)) == 0  # no manual step: no invented clamp
    out = bpl.repair_branch(steps, _action, _gb, _mk, secure_step=secure)
    actions = [_action(s) for s in out]
    assert "Pull the old flush hose off the nozzle" in actions
    assert actions.index("Pull the old flush hose off the nozzle") < actions.index("Put the new flush hose on the nozzle")
    assert "Put the inlet seal and spring in the inlet hole" in actions
    i = actions.index("Push the water hose onto the toilet")
    assert actions[i + 1] == "Secure or tighten the supply line connection at the water valve"


def test_builder_wording_helpers():
    vocab = bpl.noun_vocab(["the pedal", "the cover", "the tab", "the toilet"])
    assert bpl.add_articles("Push pedal down", vocab, imperative=True) == "Push the pedal down"
    assert bpl.add_articles("Tab locks in place.", vocab, imperative=False) == "The tab locks in place."
    assert bpl.add_articles("Slide clamp A down", vocab | {"clamp"}, imperative=True) == "Slide clamp A down"
    assert bpl.fix_list_comma("Throw the old vacuum breaker, and clamps A, B, and C away") == \
        "Throw the old vacuum breaker and clamps A, B, and C away"
    assert bpl.first_where("On the flush hose. On the nozzle. See Fig. 2.") == "On the flush hose. See Fig. 2."
    assert bpl.split_good_actions("Flush 3 times. Dry at the pedal.") == (["Flush 3 times."], "No drip at the pedal.")
    assert bpl.bad_negates_good("The clamp has moved.", "The clamp has not moved.")
    # rev5 (Leader rev4 item 1): "stays up" is only the opposite of "goes down".
    assert bpl.bad_negates_good("The bowl water goes down.", "The bowl water stays up.")
    assert bpl.bad_negates_good("The clamp is tight.", "The clamp is loose.")
    assert bpl.bad_negates_good("The tab locks in place.", "The tab does not lock.")
    assert not bpl.bad_negates_good("The hose is fully on the fitting.", "The hose sits crooked on the fitting.")
    assert bpl.clamp_bad("Tighten the inlet tube with the new clamp A") == "The inlet tube turns under the clamp."
    assert bpl.note_as_action("Larger on top and smaller on bottom.", "Secure the back of the cover with two rings") == "Put the larger ring on top and the smaller ring on the bottom"
    assert bpl.diagnosis_next("Go to the next check", "Fix the supply connection.") == \
        "If it is good, go to the next check. If it is bad, fix the supply connection."
