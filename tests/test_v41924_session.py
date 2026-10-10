"""One process, every live case, the same Send path the app uses.

The v4.19.23 conditional layer classified a job from loose words, so a furnace
sentence survived into the next case. This walks guided_diagnostics_reply in
order, in one loaded app, with a poisoned draft on every turn.
"""
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
    return ns


class TestOneSessionReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ns = _load_send_path()

    def test_fifteen_cases_in_one_process_do_not_leak(self):
        reply_fn = self.ns["guided_diagnostics_reply"]
        carried = []
        for name, category, model, turns, banned in CASES:
            history = []
            replies = []
            for latest in turns:
                reply, flow = reply_fn(latest, category, model, history, unity_gate="Not sure")
                self.assertIsNone(flow, name)
                text = (reply or "").strip()
                self.assertTrue(text, name)
                low = text.lower()
                for phrase in _BANNED:
                    self.assertNotIn(phrase, low, name)
                for phrase in banned:
                    self.assertNotIn(phrase, low, name)
                self.assertIn("📖", text, name)
                replies.append(text)
                history.append({"role": "user", "content": latest})
                history.append({"role": "assistant", "content": text})
            # A firm repair, once said, is the repair on the last ask.
            firm = ""
            for message in history:
                if message["role"] != "assistant":
                    continue
                for sentence in message["content"].split(". "):
                    low = sentence.lower()
                    if low.startswith("if "):
                        continue
                    if "replace" in low or "reseat" in low or "reposition" in low:
                        firm = sentence
            if firm and turns[-1].lower().startswith("what is the repair"):
                last = replies[-1].lower()
                self.assertNotIn("sail switch", last) if name != "S08" else None
                if name in ("S03", "S07", "S09"):
                    self.assertTrue(
                        any(token in last for token in ("20300427", "inverter", "ceiling")),
                        (name, replies[-1]),
                    )
            carried.append((name, category, model, history))

        # Same process, next case starts clean. Then one mixed history on purpose.
        s08 = next(item for item in carried if item[0] == "S08")
        mixed = list(s08[3])
        reply, _flow = reply_fn(
            "AC turns on but will not blow cold.",
            "Air Conditioning",
            "B57915E711J0EMX",
            mixed,
            unity_gate="Not sure",
        )
        low = (reply or "").lower()
        self.assertNotIn("sail switch", low)
        self.assertNotIn("wall thermostat", low)
        self.assertNotIn("take the next check", low)
        self.assertTrue(reply.strip())

        # The attached v4.19.26 histories, still in this process.
        def turn(latest, category, model, history):
            answer, flow = reply_fn(latest, category, model, history, unity_gate="Not sure")
            self.assertIsNone(flow)
            text = (answer or "").strip()
            self.assertTrue(text)
            self.assertIn("📖", text)
            self.assertNotIn("check the reading on this unit", text.lower())
            history.append({"role": "user", "content": latest})
            history.append({"role": "assistant", "content": text})
            return text

        s04 = []
        turn(
            "Furrion FCR10; dial OFF but compressor still running; fridge ice-cold / overcooling after weeks parked plugged in.",
            "Refrigerators",
            "Furrion FCR10",
            s04,
        )
        s04[-1]["content"] = (
            "Replace the Spark-Free Thermostat, part G 2021128850 (retail C-FCR10DCGTA-007). "
            "Follow the steps on pages 43–45: remove housing, seat probe straight, align clocking pin, "
            "tighten lock nut, reconnect wires.\n"
            "📖 Source: CCD-0008122 - pages 31, 43, 45"
        )
        s04.append(
            {
                "role": "user",
                "content": "Opened C (blue) and T (black) at the thermostat, no jumper, left apart: compressor stopped.",
            }
        )
        repair = turn("What is the repair?", "Refrigerators", "Furrion FCR10", s04)
        self.assertIn("spark-free thermostat", repair.lower())
        self.assertIn("the repair is to replace", repair.lower())
        self.assertNotIn("the repair is to follow", repair.lower())

        s06 = [
            {
                "role": "user",
                "content": (
                    "Level Up Advantage 807662 Manual Mode flashes then dumps back to home. "
                    "Auto Level and other pad functions still work."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Confirm Auto Level still works. Leave the rubber-boot terminator in, "
                    "unplug only the Firefly cable, and report whether Manual Mode holds.\n"
                    "📖 Source: Lippert TI-005 Electronic Leveling Troubleshooting Guide, page 1"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Unplugged the wired Firefly coach CAN cable, rubber-boot terminator left in: "
                    "Manual Mode stays."
                ),
            },
            {
                "role": "assistant",
                "content": (
                    "Real fix is Firefly USB firmware update: read GUI + CCM from Settings, "
                    "call Firefly 574-825-4600, use USB stick 4 GB or smaller.\n"
                    "📖 Source: Lippert TI-005 Electronic Leveling Troubleshooting Guide, page 1"
                ),
            },
        ]
        firefly = turn(
            "What is the repair?",
            "Leveling",
            "Lippert Level Up Advantage 807662",
            s06,
        )
        self.assertIn("update the firefly firmware", firefly.lower())
        self.assertNotIn("unplug only", firefly.lower())
        self.assertFalse(firefly.lower().startswith("if "))

        s08 = [
            {"role": "user", "content": "Will not blow warm; fan turns on then shuts off."},
            {
                "role": "assistant",
                "content": (
                    "Prove the sail switch with the blower running. "
                    "Report power in and power out before any thermostat replacement.\n"
                    "📖 Source: Suburban Furnace Service and Training Manual"
                ),
            },
            {
                "role": "user",
                "content": "Thermostat bypassed at the furnace: the furnace operates.",
            },
        ]
        sail = turn("Sail switch continuity OK", "Furnaces", "Suburban NT-20SEQT", s08)
        self.assertIn("replace the wall thermostat", sail.lower())
        self.assertNotIn("measure power", sail.lower())
        later = turn("What is the repair?", "Furnaces", "Suburban NT-20SEQT", s08)
        self.assertIn("wall thermostat", later.lower())
        self.assertNotIn("measure power", later.lower())
        self.assertNotIn("if the sail", later.lower())

        s09 = [
            {"role": "user", "content": "AC turns on but will not blow cold."},
            {
                "role": "assistant",
                "content": (
                    "Bypass the ceiling selector and report whether it cools. "
                    "If both bypasses cool, replace the ceiling thermostat/selector.\n"
                    "📖 Source: Dometic Brisk II, page 23"
                ),
            },
            {"role": "user", "content": "Peacemaker bypass at the rooftop unit cools."},
        ]
        both = turn(
            "Bypassing the ceiling controls also cools.",
            "Air Conditioning",
            "B57915E711J0EMX",
            s09,
        )
        self.assertIn("replace the ceiling thermostat", both.lower())
        self.assertNotIn("check the reading on this unit", both.lower())
        self.assertNotIn("bypass the ceiling selector and report", both.lower())
        again = turn("What is the repair?", "Air Conditioning", "B57915E711J0EMX", s09)
        self.assertIn("ceiling thermostat", again.lower())
        self.assertNotEqual(again.strip(), s09[1]["content"].strip())
        self.assertNotIn("bypass the ceiling selector and report", again.lower())


if __name__ == "__main__":
    unittest.main()
