"""xAI primary, Groq fallback. Clients are mocks - no live network."""
import os
import unittest

import gd_llm
from gd_library_coach import is_ai_request_too_large


XAI_KEY = "xai-test-key-not-real"
GROQ_KEY = "groq-test-key-not-real"
MESSAGES = [
    {"role": "system", "content": "Cite the shop manual only."},
    {"role": "user", "content": "FACR08 still freezing after the drain prove."},
]


class HTTPError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status_code = status


class APITimeoutError(Exception):
    pass


class APIConnectionError(Exception):
    pass


def _response(content):
    message = type("M", (), {"content": content})()
    choice = type("C", (), {"message": message})()
    return type("R", (), {"choices": [choice]})()


def _factory(outcomes, record):
    """outcomes[provider] is a list of str or Exception, consumed in order."""

    def factory(provider, *, api_key, base_url):
        record.append(
            {
                "event": "client",
                "provider": provider,
                "api_key": api_key,
                "base_url": base_url,
            }
        )

        class Completions:
            def create(self, **kwargs):
                record.append(
                    {
                        "event": "call",
                        "provider": provider,
                        "api_key": api_key,
                        "base_url": base_url,
                        "kwargs": kwargs,
                    }
                )
                outcome = outcomes[provider].pop(0)
                if isinstance(outcome, Exception):
                    raise outcome
                return _response(outcome)

        class Chat:
            completions = Completions()

        class Client:
            chat = Chat()

        return Client()

    return factory


def _calls(record, provider=None):
    calls = [row for row in record if row["event"] == "call"]
    if provider is None:
        return calls
    return [row for row in calls if row["provider"] == provider]


class TestGdLlmProvider(unittest.TestCase):
    def setUp(self):
        gd_llm._last_provider = ""

    def _secrets(self, **extra):
        data = {
            "XAI_API_KEY": XAI_KEY,
            "GROQ_API_KEY": GROQ_KEY,
        }
        data.update(extra)

        def secret(name):
            return data.get(name, "")

        return secret

    def test_primary_xai_success_does_not_call_groq(self):
        record = []
        outcomes = {"xai": ["next prove is rooftop assembly"], "groq": ["should-not-run"]}
        text = gd_llm.complete_chat(
            MESSAGES,
            temperature=0.2,
            max_tokens=900,
            secret_fn=self._secrets(),
            client_factory=_factory(outcomes, record),
        )
        self.assertEqual(text, "next prove is rooftop assembly")
        self.assertEqual(gd_llm.last_provider(), "xai")
        self.assertEqual(len(_calls(record)), 1)
        call = _calls(record, "xai")[0]
        self.assertEqual(call["kwargs"]["model"], "grok-4.6")
        self.assertEqual(call["kwargs"]["messages"], MESSAGES)
        self.assertIs(call["kwargs"]["messages"], MESSAGES)
        self.assertEqual(call["base_url"], "https://api.x.ai/v1")
        self.assertEqual(call["api_key"], XAI_KEY)
        self.assertEqual(_calls(record, "groq"), [])
        self.assertNotIn(XAI_KEY, text)

    def test_primary_429_falls_back_to_groq_with_same_messages(self):
        record = []
        outcomes = {
            "xai": [HTTPError(429, f"rate_limit_exceeded key={XAI_KEY}")],
            "groq": ["groq kept the prove moving"],
        }
        text = gd_llm.complete_chat(
            MESSAGES,
            secret_fn=self._secrets(),
            client_factory=_factory(outcomes, record),
        )
        self.assertEqual(text, "groq kept the prove moving")
        self.assertEqual(gd_llm.last_provider(), "groq")
        self.assertEqual([row["provider"] for row in _calls(record)], ["xai", "groq"])
        groq = _calls(record, "groq")[0]
        self.assertEqual(groq["kwargs"]["model"], "openai/gpt-oss-120b")
        self.assertIs(groq["kwargs"]["messages"], MESSAGES)
        self.assertEqual(groq["kwargs"]["temperature"], 0.2)
        self.assertEqual(groq["kwargs"]["max_tokens"], 1400)
        self.assertEqual(groq["api_key"], GROQ_KEY)
        self.assertEqual(groq["base_url"], "")

    def test_auth_timeout_transport_and_5xx_also_fall_back(self):
        cases = (
            HTTPError(400, "bad request"),
            HTTPError(401, "unauthorized"),
            HTTPError(403, "forbidden"),
            HTTPError(500, "internal"),
            HTTPError(503, "unavailable"),
            APITimeoutError("Request timed out"),
            APIConnectionError("connection reset by peer"),
        )
        for exc in cases:
            with self.subTest(exc=type(exc).__name__ + " " + str(exc)):
                record = []
                outcomes = {"xai": [exc], "groq": ["fallback ok"]}
                text = gd_llm.complete_chat(
                    MESSAGES,
                    secret_fn=self._secrets(),
                    client_factory=_factory(outcomes, record),
                )
                self.assertEqual(text, "fallback ok")
                self.assertEqual([row["provider"] for row in _calls(record)], ["xai", "groq"])

    def test_both_providers_fail_prefixes_names_and_hides_keys(self):
        record = []
        outcomes = {
            "xai": [HTTPError(429, f"rate_limit_exceeded {XAI_KEY}")],
            "groq": [HTTPError(429, f"rate_limit_exceeded {GROQ_KEY}")],
        }
        with self.assertRaises(gd_llm.LLMProviderError) as caught:
            gd_llm.complete_chat(
                MESSAGES,
                secret_fn=self._secrets(),
                client_factory=_factory(outcomes, record),
            )
        message = str(caught.exception)
        self.assertIn("xAI:", message)
        self.assertIn("Groq:", message)
        self.assertIn("429", message)
        self.assertNotIn(XAI_KEY, message)
        self.assertNotIn(GROQ_KEY, message)
        self.assertIn("[redacted]", message)
        self.assertEqual([row["provider"] for row in _calls(record)], ["xai", "groq"])

    def test_missing_xai_key_uses_groq(self):
        record = []
        outcomes = {"xai": ["should-not-run"], "groq": ["groq only"]}
        text = gd_llm.complete_chat(
            MESSAGES,
            secret_fn=self._secrets(XAI_API_KEY=""),
            client_factory=_factory(outcomes, record),
        )
        self.assertEqual(text, "groq only")
        self.assertEqual([row["provider"] for row in _calls(record)], ["groq"])
        self.assertEqual(gd_llm.last_provider(), "groq")

    def test_missing_both_keys_is_a_clear_error_without_a_client(self):
        record = []
        with self.assertRaises(gd_llm.LLMProviderError) as caught:
            gd_llm.complete_chat(
                MESSAGES,
                secret_fn=self._secrets(XAI_API_KEY="", GROQ_API_KEY="  "),
                client_factory=_factory({"xai": [], "groq": []}, record),
            )
        message = str(caught.exception)
        self.assertIn("No AI key configured", message)
        self.assertIn("XAI_API_KEY", message)
        self.assertIn("GROQ_API_KEY", message)
        self.assertEqual(record, [])

    def test_primary_groq_override_and_xai_model_base_url(self):
        record = []
        outcomes = {"groq": ["groq primary"], "xai": ["should-not-run"]}
        text = gd_llm.complete_chat(
            MESSAGES,
            secret_fn=self._secrets(
                GD_LLM_PRIMARY="groq",
                XAI_MODEL="grok-shop",
                XAI_BASE_URL="https://example.test/v1",
            ),
            client_factory=_factory(outcomes, record),
        )
        self.assertEqual(text, "groq primary")
        self.assertEqual([row["provider"] for row in _calls(record)], ["groq"])

        record = []
        outcomes = {"xai": ["custom model"], "groq": ["should-not-run"]}
        text = gd_llm.complete_chat(
            MESSAGES,
            secret_fn=self._secrets(
                GD_LLM_PRIMARY="XAI",
                XAI_MODEL="grok-shop",
                XAI_BASE_URL="https://example.test/v1",
            ),
            client_factory=_factory(outcomes, record),
        )
        self.assertEqual(text, "custom model")
        call = _calls(record, "xai")[0]
        self.assertEqual(call["kwargs"]["model"], "grok-shop")
        self.assertEqual(call["base_url"], "https://example.test/v1")

    def test_unknown_primary_stays_on_xai(self):
        self.assertEqual(
            gd_llm.provider_order(self._secrets(GD_LLM_PRIMARY="claude")),
            ["xai", "groq"],
        )

    def test_payload_too_large_does_not_call_fallback(self):
        record = []
        outcomes = {
            "xai": [HTTPError(413, "request too large")],
            "groq": ["should-not-run"],
        }
        with self.assertRaises(gd_llm.LLMProviderError) as caught:
            gd_llm.complete_chat(
                MESSAGES,
                secret_fn=self._secrets(),
                client_factory=_factory(outcomes, record),
            )
        self.assertTrue(is_ai_request_too_large(caught.exception))
        self.assertIn("xAI:", str(caught.exception))
        self.assertNotIn("Groq:", str(caught.exception))
        self.assertEqual([row["provider"] for row in _calls(record)], ["xai"])

    def test_ai_configured_follows_keys(self):
        self.assertTrue(gd_llm.ai_configured(self._secrets()))
        self.assertTrue(gd_llm.ai_configured(self._secrets(GROQ_API_KEY="")))
        self.assertFalse(
            gd_llm.ai_configured(self._secrets(XAI_API_KEY="", GROQ_API_KEY=""))
        )

    def test_rate_limit_skips_remaining_models_on_that_provider(self):
        record = []
        outcomes = {
            "xai": [HTTPError(429, "rate_limit_exceeded")],
            "groq": ["ok"],
        }
        text = gd_llm.complete_chat(
            MESSAGES,
            secret_fn=self._secrets(),
            client_factory=_factory(outcomes, record),
            models={
                "xai": ["grok-4.6", "grok-2-vision-1212"],
                "groq": ["openai/gpt-oss-120b"],
            },
        )
        self.assertEqual(text, "ok")
        self.assertEqual(
            [row["kwargs"]["model"] for row in _calls(record)],
            ["grok-4.6", "openai/gpt-oss-120b"],
        )

    def test_vision_404_tries_next_model_then_groq(self):
        record = []
        outcomes = {
            "xai": [
                HTTPError(404, "model_not_found"),
                HTTPError(404, "model_not_found"),
            ],
            "groq": ['{"brand":"Furrion","model":"FACR08"}'],
        }
        text = gd_llm.complete_chat(
            MESSAGES,
            temperature=0.0,
            max_tokens=400,
            secret_fn=self._secrets(),
            client_factory=_factory(outcomes, record),
            models={
                "xai": ["grok-4.6", "grok-2-vision-1212"],
                "groq": ["qwen/qwen3.6-27b"],
            },
            empty_is_failure=True,
        )
        self.assertIn("FACR08", text)
        models = [row["kwargs"]["model"] for row in _calls(record)]
        self.assertEqual(models, ["grok-4.6", "grok-2-vision-1212", "qwen/qwen3.6-27b"])

    def test_env_secrets_when_no_secret_fn(self):
        record = []
        keys = ("XAI_API_KEY", "GROQ_API_KEY", "XAI_MODEL", "XAI_BASE_URL", "GD_LLM_PRIMARY")
        saved = {name: os.environ.get(name) for name in keys}
        os.environ["XAI_API_KEY"] = XAI_KEY
        os.environ["GROQ_API_KEY"] = GROQ_KEY
        os.environ["XAI_MODEL"] = "grok-from-env"
        os.environ["XAI_BASE_URL"] = "https://env.example/v1"
        os.environ["GD_LLM_PRIMARY"] = "xai"
        try:
            text = gd_llm.complete_chat(
                MESSAGES,
                client_factory=_factory({"xai": ["from env"], "groq": ["no"]}, record),
            )
        finally:
            for name, old in saved.items():
                if old is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = old
        self.assertEqual(text, "from env")
        call = _calls(record, "xai")[0]
        self.assertEqual(call["kwargs"]["model"], "grok-from-env")
        self.assertEqual(call["base_url"], "https://env.example/v1")
        self.assertNotIn(XAI_KEY, text)

    def test_live_modules_do_not_construct_clients(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app = open(os.path.join(root, "rv_techtrack.py"), encoding="utf-8").read()
        coach = open(os.path.join(root, "gd_library_coach.py"), encoding="utf-8").read()
        helper = open(os.path.join(root, "gd_llm.py"), encoding="utf-8").read()
        self.assertIn("gd_llm.complete_chat", app)
        self.assertNotIn("Groq(", app)
        self.assertNotIn("OpenAI(", app)
        self.assertNotIn("openai/gpt-oss-120b", app)
        self.assertNotIn("Groq(", coach)
        self.assertNotIn("OpenAI(", coach)
        self.assertIn("openai/gpt-oss-120b", helper)
        self.assertIn("https://api.x.ai/v1", helper)
        self.assertIn('DEFAULT_XAI_MODEL = "grok-4.6"', helper)


if __name__ == "__main__":
    unittest.main()
