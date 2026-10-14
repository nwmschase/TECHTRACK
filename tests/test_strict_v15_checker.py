"""Leader rev3 page review (v4.19.60): misses that must fail on their own, and the builder repairs."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import bay_profile_lines as bpl  # noqa: E402
import profile_check as pc  # noqa: E402
from test_strict_v14_checker import GOOD_BRANCH, _sheet  # noqa: E402


def _named(text):
    return {r.name: r for r in pc._strict_v14(text)}


def _step(n, action, good, bad="", nxt="", where="At the toilet."):
    lines = [f"Step {n}: {action}", f"Where: {where}", "Do this:", f"1. {action}.", f"Good looks like: {good}"]
    if bad:
        lines.append(f"Bad looks like: {bad}")
    lines.append(f"Next: {nxt or 'Go on.'}")
    return "\n".join(lines) + "\n"


def test_clean_branch_still_passes_every_rule():
    named = _named(_sheet(GOOD_BRANCH))
    assert all(r.ok for r in named.values()), [r for r in named.values() if not r.ok]


def test_hose_on_tight_is_not_a_clamp_regression():
    # rev3 Step 34 / Step 38: Good "The hose is on tight", then the water went back on. That passed before.
    body = (
        _step(1, "Pull the water hose off the toilet", "The hose is off.", nxt="Push the water hose onto the toilet.")
        + "INSTALLATION\n"
        + _step(2, "Push the water hose onto the toilet", "The hose is on tight.", "The hose sits crooked.", "Turn the RV water on.")
        + _step(3, "Turn the RV water on", "No drip at the toilet.", nxt="Tighten the hose clamp on the toilet.")
        + _step(4, "Tighten the hose clamp on the toilet", "The clamp is tight on the hose.", nxt="Confirm the repair is dry.")
        + "VERIFY\n" + _step(5, "Confirm the repair is dry", "The repair is dry.", "A drip shows.", "This branch is complete.")
    )
    assert not _named(_sheet(body))["secure_after_hose"].ok


def test_figure_number_repeated_across_the_sheet_fails_even_with_documents():
    text = _sheet(GOOD_BRANCH) + "Fig. 1 CLAMP, Kit A, page 1\nFig. 1 PEDAL REMOVED, Kit B, page 1\n"
    assert not _named(text)["figure_captions"].ok
    assert _named(_sheet(GOOD_BRANCH) + "Fig. 1 CLAMP, Kit A, page 1\nFig. 2 PEDAL, Kit B, page 1\n")["figure_captions"].ok


def test_part_removed_but_not_reinstalled_fails():
    body = (
        _step(1, "Pull the inlet seal and spring off the inlet hole", "The inlet seal and spring are off.", nxt="Throw the inlet seal and spring away.")
        + _step(2, "Throw the inlet seal and spring away", "They are in the trash.", nxt="Put the inlet seal in the inlet hole.")
        + "INSTALLATION\n" + _step(3, "Put the inlet seal in the inlet hole", "The seal is in the hole.", nxt="Confirm the repair is dry.")
        + "VERIFY\n" + _step(4, "Confirm the repair is dry", "The repair is dry.", "A drip shows.", "This branch is complete.")
    )
    assert not _named(_sheet(body))["reinstalled"].ok
    fixed = body.replace("Put the inlet seal in the inlet hole", "Put the inlet seal and spring in the inlet hole")
    assert _named(_sheet(fixed))["reinstalled"].ok


def test_new_part_without_old_one_off_fails():
    body = (
        _step(1, "Take off the vacuum breaker", "The vacuum breaker is off.", nxt="Put the new flush hose on the nozzle.")
        + "INSTALLATION\n" + _step(2, "Put the new flush hose on the nozzle", "The hose is on.", nxt="Confirm the repair is dry.")
        + "VERIFY\n" + _step(3, "Confirm the repair is dry", "The repair is dry.", "A drip shows.", "This branch is complete.")
    )
    assert not _named(_sheet(body))["old_part_removed"].ok


def test_two_orders_in_one_next_fail():
    diag = _step(1, "Check the hose at the valve", "The hose is dry.", nxt="Go to the next check. Fix or tighten the supply connection.")
    assert not _named(_sheet(GOOD_BRANCH, diagnosis=diag))["next_single_path"].ok
    diag_ok = _step(1, "Check the hose at the valve", "The hose is dry.",
                    nxt="If it is good, go to the next check. If it is bad, fix or tighten the supply connection.")
    assert _named(_sheet(GOOD_BRANCH, diagnosis=diag_ok))["next_single_path"].ok


def test_doubled_where_fails():
    body = GOOD_BRANCH.replace("Where: At the water valve.\nDo this:\n1. Tighten.", "Where: On the flush hose. On the nozzle.\nDo this:\n1. Tighten.")
    assert not _named(_sheet(body))["where_single"].ok


def test_action_in_good_fails():
    body = GOOD_BRANCH.replace("Good looks like: The clamp is tight.", "Good looks like: Flush 3 times. Dry at the valve.")
    assert not _named(_sheet(body))["good_is_a_look"].ok


def test_bad_that_only_negates_good_fails():
    body = GOOD_BRANCH.replace("Good looks like: The clamp is tight.", "Good looks like: The clamp has moved.\nBad looks like: The clamp has not moved.")
    assert not _named(_sheet(body))["bad_is_specific"].ok


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
