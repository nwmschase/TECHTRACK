"""One process, every live case, the same Send path the app uses.

UPDATED 2026-10-16 for the GD official method. Edit authorized by Leader (1:51 PM PT,
cursor/gd-official-method). The model call is an offline stand-in, so this replay asserts what
the code controls: safety line first, verify-first rule, every reported finding reaches the
model on the repair ask, and nothing leaks between cases. Reaching each job's real fix with the
live model is checked by the real-case reruns (RC07, RC08, RC12-RC19).

The v4.19.23 conditional layer classified a job from loose words, so a furnace
sentence survived into the next case. This walks guided_diagnostics_reply in
order, in one loaded app, with a poisoned draft on every turn.
"""
import re
import unittest
from pathlib import Path

POISON = (
    "If the sail switch has power in and power out while the blower runs, replace the wall thermostat.\n"
    "Take the next check on this job and write the reading down. "
    "If that check fails, replace the part that check names.\n"
    "If the pin or coupler or seized, replace the complete front stabilizer jack assembly.\n"
    "1. 2. Turn touch pad off. 3. 4. Press ENTER.\n"
    "If those pressures are in range and the interior leak , replace the rooftop assembly."
)

CASES = (
    (
        "S01",
        "Air Conditioning",
        "FACR08HESA2-PS",
        [
            "Furrion FACR08HESA2-PS rooftop AC; water leaking from forward AC inside while running, not raining.",
            "Drain is clear, pan is clean and draining, base-pan slope is fine.",
            "Filter is clean.",
            "Evaporator fan spins freely with good airflow.",
            "Freeze sensor reads 2 kΩ at 25°C.",
            "What is the repair?",
        ],
        ("sail switch", "wall thermostat", "front stabilizer"),
    ),
    (
        "S02",
        "Air Conditioning",
        "Coleman-Mach 2111-0001",
        [
            "Coleman-Mach rooftop A/C model 2111-0001; ran about 2 minutes then dead.",
            "122 VAC at the control box. Fan High is dead.",
            "Peacemaker bypass: compressor runs, fan does not rotate. About 1.91 A, shaft locked.",
            "What is the repair?",
        ],
        ("sail switch", "replace the wall thermostat", "front stabilizer"),
    ),
    (
        "S03",
        "Electrical",
        "BAL Soft-Touch SS 5.1",
        [
            "BAL Soft-Touch SS 5.1 electric tongue jack dead only; other stabilizers and panel lights work.",
            "I measured 0 V at the soft-touch panel tongue channel while commanding extend.",
            "Motor runs on direct 12V. Manual override turns the jack; coupler OK.",
            "What is the repair?",
        ],
        ("sail switch", "front stabilizer jack", "wall thermostat"),
    ),
    (
        "S04",
        "Refrigerators",
        "FCR10DCGTA-BL",
        [
            "Temperature dial is OFF and the compressor is still running. Freezer is frozen solid.",
            "Compressor stopped with C and T open.",
            "What is the repair?",
        ],
        ("sail switch", "front stabilizer", "wall thermostat"),
    ),
    (
        "S05",
        "Refrigerators",
        "FCR10DCGTA-BL",
        [
            "Furrion FCR10 fridge; icing up on the rear wall about halfway from the top.",
            "Door gasket is sealing properly.",
            "What is the repair?",
        ],
        ("sail switch", "rear drain", "wall thermostat"),
    ),
    (
        "S06",
        "Leveling",
        "Lippert Level Up Advantage 807662",
        [
            "Level Up Advantage 807662 Manual Mode flashes then dumps back to home. Auto Level still works.",
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ],
        ("sail switch", "front stabilizer", "wall thermostat", "take the next check"),
    ),
    (
        "S07",
        "Refrigerators",
        "FCR10DCGTA-BG-PWH",
        [
            "Freezes contents; intermittent blinking 2 / E2; temp control intermittent.",
            "Fan voltage cycles 14.28–10.37 V on about a 40 s cycle.",
            "What is the repair?",
        ],
        ("sail switch", "take the next check", "front stabilizer"),
    ),
    (
        "S08",
        "Furnaces",
        "Suburban NT-20SEQT",
        [
            "Suburban furnace. Will not blow warm; fan turns on then shuts off.",
            "Thermostat bypassed at the furnace: the furnace operates.",
            "What is the repair?",
        ],
        ("front stabilizer", "ceiling thermostat", "take the next check"),
    ),
    (
        "S09",
        "Air Conditioning",
        "B57915E711J0EMX",
        [
            "AC turns on but will not blow cold.",
            "Peacemaker bypass at the rooftop unit cools.",
            "Bypassing the ceiling controls also cools.",
            "What is the repair?",
        ],
        ("sail switch", "wall thermostat", "front stabilizer"),
    ),
    (
        "S10",
        "Leveling",
        "Lippert Ground Control 343633",
        [
            "Auto-level lifts driver-side tires though nearly level.",
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ],
        ("sail switch", "1. 2.", "front stabilizer"),
    ),
    (
        "S11",
        "Air Conditioning",
        "FACT12SA2-PS",
        [
            "E3 error code on the FACT12 rooftop.",
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ],
        ("sail switch", "and e2 ,", "front stabilizer"),
    ),
    (
        "S12",
        "Air Conditioning",
        "FACT12SA2-PS",
        [
            "E2 error code; sometimes normal.",
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ],
        ("sail switch", "and e2 ,", "and the code ,"),
    ),
    (
        "S13",
        "Water Heaters",
        "Girard GSWH-2",
        [
            "Girard GSWH-2 gives E8 error code.",
            "Tubing is clear.",
            "What is the repair?",
        ],
        ("sail switch", "wall thermostat", "front stabilizer"),
    ),
    (
        "S14",
        "Leveling",
        "Lippert PSX1",
        [
            "Front stabilizer jack. Power works. The manual crank will not operate. The roll pin is broken.",
            "What is the repair?",
        ],
        ("sail switch", "pin or coupler or seized", "20300427"),
    ),
    (
        "S15",
        "Range & Cooktops",
        "Suburban SDN2U",
        [
            "When using stove, it will shut off as soon as a pan is put on it — either burner.",
            "Not checked yet — what do you recommend next?",
            "What is the repair?",
        ],
        ("sail switch", "wall thermostat", "front stabilizer"),
    ),
)

_BANNED = (
    "take the next check on this job",
    "check the first step on this job",
    "measure the open check",
    "write the open reading",
    "write reading ",
    "replace the part that check names",
    "replace the failed part",
    "pin or coupler or seized",
    "interior leak ,",
    "1. 2.",
)


def _load_send_path():
    src = Path(__file__).resolve().parents[1].joinpath("rv_techtrack.py").read_text()
    cut = src.split("# ---------------- LOGIN ----------------", 1)[0]
    ns = {
        "__name__": "rv_techtrack_session_replay",
        "__file__": str(Path(__file__).resolve().parents[1] / "rv_techtrack.py"),
    }
    exec(compile(cut, "rv_techtrack.py", "exec"), ns)
    ns["ai_available"] = lambda: True
    ns["ai_chat"] = lambda *args, **kwargs: POISON
    ns["_gd_official_web"] = lambda unit: {}
    ns["_gd_official_chat"] = _scripted_model
    return ns


SENT = []


def _scripted_model(messages, max_tokens, effort):
    SENT.append(messages)
    unit = re.search(r"UNIT: ([^\n]*)", messages[0]["content"])
    return f"1. Verify the complaint on {unit.group(1) if unit else 'this unit'} and report what it does."


class TestOneSessionReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = _load_send_path()

    def test_fifteen_cases_in_one_process_do_not_leak(self):
        reply_fn = self.ns["guided_diagnostics_reply"]
        previous_model = None
        for name, category, model, turns, banned in CASES:
            history, store = [], {}
            for i, latest in enumerate(turns):
                reply, flow = reply_fn(latest, category, model, history, unity_gate="No", pin_store=store)
                self.assertIsNone(flow, name)
                text = (reply or "").strip()
                self.assertTrue(text, name)
                low = text.lower()
                for phrase in _BANNED:
                    self.assertNotIn(phrase, low, name)
                for phrase in banned:
                    self.assertNotIn(phrase, low, name)
                if i == 0:
                    self.assertIn("Safety first", text, name)
                if previous_model and previous_model != model:
                    self.assertNotIn(previous_model, SENT[-1][0]["content"], name)
                history.append({"role": "user", "content": latest})
                history.append({"role": "assistant", "content": text})
            sent = "\n".join(m["content"] for m in SENT[-1])
            for latest in turns:
                self.assertIn(latest[:40], sent, (name, latest))
            previous_model = model
