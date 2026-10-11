"""Optional GD step photos. Vision is mocked. xAI only, never llama-4-scout."""
import json
import unittest
from pathlib import Path

from gd_library_coach import avoid_duplicate_reply
from gd_step_photo import (
    DEAD_GROQ_SCOUT_MODEL,
    complete_xai_vision,
    history_user_text,
    parse_vision_review,
    photo_subject,
    present_photo_review,
    review_step_photo,
)

CAT = "Plumbing / Toilets"
MODEL = "Style II 42070"
ROOT = Path(__file__).resolve().parents[1]


def _procedure_history():
    return [
        {"role": "user", "content": "toilet leaks under the flush lever"},
        {"role": "assistant", "content": "Back of the toilet: check the water supply line."},
        {"role": "user", "content": "Supply is tight. The water valve weeps at the pedal."},
        {"role": "assistant", "content": "Check whether the vacuum breaker leaks while flushing."},
        {"role": "user", "content": "Vacuum breaker is dry. No leak there."},
        {"role": "assistant", "content": "Step 1 of 40.\nPull the pedal up."},
    ]


def _turn(latest, review, history=None, draft=""):
    return avoid_duplicate_reply(
        draft,
        history if history is not None else _procedure_history(),
        latest,
        CAT,
        MODEL,
        photo_review=review,
    )


class TestPhotoSubjects(unittest.TestCase):
    def test_subjects_are_tag_leak_connector_meter_and_part(self):
        self.assertEqual(photo_subject("Read the model tag on the toilet."), "tag")
        self.assertEqual(photo_subject("Look for a leak under the pedal."), "leak")
        self.assertEqual(photo_subject("Check the supply line connection."), "connector")
        self.assertEqual(photo_subject("Read the meter at the connector."), "meter")
        self.assertEqual(photo_subject("The new valve is the part in the kit."), "part")
        self.assertEqual(photo_subject("Turn off the water to the RV."), "")


class TestVisionParse(unittest.TestCase):
    def test_garbage_and_a_guess_become_unclear(self):
        self.assertEqual(parse_vision_review("not json"), {"verdict": "unclear", "sees": ""})
        self.assertEqual(
            parse_vision_review('{"verdict":"confirm","sees":""}'),
            {"verdict": "unclear", "sees": ""},
        )
        invented = '{"verdict":"unclear","sees":"water pouring from the valve"}'
        parsed = parse_vision_review(invented)
        self.assertEqual(parsed["verdict"], "unclear")
        self.assertEqual(parsed["sees"], "")
        self.assertNotIn("water pouring", present_photo_review("Step 1 of 3.", parsed))

    def test_confirm_keeps_only_the_model_sentence(self):
        raw = '{"verdict":"confirm","sees":"The pedal is off."}'
        self.assertEqual(parse_vision_review(raw), {"verdict": "confirm", "sees": "The pedal is off."})


class TestXaiVisionCall(unittest.TestCase):
    def test_photo_goes_to_xai_and_not_the_retired_scout_model(self):
        calls = []

        def fake(messages, **kwargs):
            calls.append({"messages": messages, "kwargs": kwargs})
            return '{"verdict":"confirm","sees":"a brass tag"}'

        complete_xai_vision(
            [{"role": "user", "content": "x"}],
            secret_fn=lambda name: DEAD_GROQ_SCOUT_MODEL if "MODEL" in name else "",
            complete_fn=fake,
        )
        self.assertEqual(calls[0]["kwargs"]["providers"], ["xai"])
        self.assertNotIn("groq", calls[0]["kwargs"])
        models = " ".join(calls[0]["kwargs"]["models"]["xai"])
        self.assertNotIn("llama-4-scout", models)
        self.assertIn("grok-4.6", models)

        sent = []

        def fake_messages(messages):
            sent.extend(messages)
            return '{"verdict":"mismatch","sees":"a dry towel"}'

        review = review_step_photo(b"\xff\xd8\xff", "image/jpeg", "the leak", "it weeps", fake_messages)
        self.assertEqual(review["verdict"], "mismatch")
        self.assertEqual(review["sees"], "a dry towel")
        payload = sent[0]["content"]
        self.assertEqual(payload[1]["type"], "image_url")
        self.assertTrue(payload[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertIn("Do not guess", payload[0]["text"])
        self.assertNotIn("llama-4-scout", json.dumps(sent))


class TestThetfordPhotoTurns(unittest.TestCase):
    def test_confirm_states_what_it_sees_and_moves_on(self):
        reply = _turn(
            "Yes.",
            {"verdict": "confirm", "sees": "The pedal is off."},
        )
        self.assertIn("I see: The pedal is off.", reply)
        self.assertIn("Step 2 of", reply)
        self.assertNotIn("Step 1 of", reply)

    def test_mismatch_asks_for_another_and_stays(self):
        reply = _turn(
            "Yes.",
            {"verdict": "mismatch", "sees": "a dry towel on the floor"},
        )
        self.assertIn("I see: a dry towel on the floor.", reply)
        self.assertIn("This photo does not match the finding.", reply)
        self.assertIn("Send another photo, or type what you see.", reply)
        self.assertIn("Step 1 of", reply)
        self.assertNotIn("Step 2 of", reply)

    def test_unclear_does_not_invent_a_scene(self):
        reply = _turn(
            "Yes.",
            {"verdict": "unclear", "sees": "water pouring from the valve"},
        )
        self.assertNotIn("water pouring from the valve", reply)
        self.assertNotIn("I see:", reply)
        self.assertIn("This photo is not clear enough.", reply)
        self.assertIn("I will not guess what it shows.", reply)
        self.assertIn("Send another photo, or type what you see.", reply)
        self.assertIn("Step 1 of", reply)
        self.assertNotIn("Step 2 of", reply)

    def test_no_photo_typed_yes_still_moves_on(self):
        reply = _turn("Photo sent. Yes.", None)
        self.assertIn("Step 2 of", reply)
        self.assertNotIn("Step 1 of", reply)
        self.assertNotIn("I see:", reply)

    def test_a_mismatched_supply_photo_does_not_skip_to_the_vacuum_breaker(self):
        history = [
            {"role": "user", "content": "toilet leaks under the flush lever"},
            {
                "role": "assistant",
                "content": "Back of the toilet: check the water supply line connection at the water valve.",
            },
        ]
        reply = _turn(
            "Supply connection is tight. No leak there.",
            {"verdict": "mismatch", "sees": "Water is running at the fitting."},
            history,
            draft="📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
        )
        low = reply.lower()
        self.assertIn("I see: Water is running at the fitting.", reply)
        self.assertIn("supply", low)
        self.assertNotIn("vacuum breaker", low)
        self.assertIn("A photo is optional.", reply)

    def test_a_confirming_photo_can_close_the_supply_check(self):
        history = [
            {"role": "user", "content": "toilet leaks under the flush lever"},
            {
                "role": "assistant",
                "content": "Back of the toilet: check the water supply line connection at the water valve.",
            },
        ]
        reply = _turn(
            "",
            {"verdict": "confirm", "sees": "The supply connection is tight."},
            history,
            draft="📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
        )
        self.assertIn("I see: The supply connection is tight.", reply)
        self.assertIn("vacuum breaker", reply.lower())
        self.assertIn("only while flushing", reply.lower())

    def test_history_keeps_a_confirm_and_drops_a_contradicted_finding(self):
        kept = history_user_text("tight", True, {"verdict": "confirm", "sees": "The supply connection is tight."})
        self.assertIn("The supply connection is tight.", kept)
        self.assertIn("Yes.", kept)
        dropped = history_user_text(
            "Supply connection is tight. Yes.",
            True,
            {"verdict": "mismatch", "sees": "Water is running at the fitting."},
        )
        self.assertNotIn("tight", dropped.lower())
        self.assertNotIn("Yes", dropped)
        self.assertEqual(history_user_text("Supply connection is tight.", False, None), "Supply connection is tight.")


class TestGdPhotoUploader(unittest.TestCase):
    def test_the_chat_form_has_an_optional_photo_uploader(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        form = src.split('st.form("gd_send_form"', 1)[1].split("if new_chat:", 1)[0]
        self.assertIn("st.file_uploader(", form)
        self.assertIn("Photo (optional)", form)
        self.assertIn("photo_review=photo_review", src)
        self.assertNotIn("llama-4-scout", form)


if __name__ == "__main__":
    unittest.main()
