"""Optional GD step photos. Vision is mocked. xAI only, never llama-4-scout."""
import json
import unittest
from pathlib import Path

import manual_figures as mf
from gd_step_photo import (
    DEAD_GROQ_SCOUT_MODEL,
    complete_xai_vision,
    history_user_text,
    parse_vision_review,
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
        self.assertIn("verdict", payload[0]["text"])
        self.assertNotIn("llama-4-scout", json.dumps(sent))


class TestThetfordPhotoTurns(unittest.TestCase):


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
