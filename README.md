# RV TechTrack

Shop app for Tacoma RV Center (`streamlit run rv_techtrack.py`). Guided Diagnostics chat, the warranty-story writer, and the data-plate photo reader share one LLM helper (`gd_llm.py`).

## Guided Diagnostics LLM (v4.18.0)

xAI is called first. If that call cannot be made or the provider fails, the same messages are sent once to Groq. The bay sees an error only when both fail. The error is prefixed with the provider name (`xAI: ...` / `Groq: ...`). API keys are never written into that error.

Put these in Streamlit Cloud secrets (or the process environment). Names only - do not commit values. A template is in [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example).

| Name | Required | Default | Purpose |
| --- | --- | --- | --- |
| `XAI_API_KEY` | Primary | | xAI API key |
| `GROQ_API_KEY` | Fallback | | Existing Groq key. Chat fallback model stays `openai/gpt-oss-120b` |
| `XAI_MODEL` | No | `grok-4.6` | Chat model. Also the data-plate model unless `XAI_VISION_MODEL` is set |
| `XAI_BASE_URL` | No | `https://api.x.ai/v1` | OpenAI-compatible base URL |
| `GD_LLM_PRIMARY` | No | `xai` | `xai` or `groq` - which provider is tried first |
| `XAI_VISION_MODEL` | No | | Optional plate-photo model id. `grok-4.6` already accepts images |
| `GROQ_VISION_MODEL` | No | `qwen/qwen3.6-27b` | Optional Groq plate-photo model. `meta-llama/llama-4-scout-17b-16e-instruct` stays off the default list (Groq 404) |

Fallback covers a missing primary key, HTTP 401/403, 429, other request rejects except payload-too-large, 5xx, timeouts, and transport errors. HTTP 413 still shrinks the Guided Diagnostics payload and retries. A dead vision model id (HTTP 404) tries the next id on that provider, then the other provider.

`GD_LLM_PRIMARY=groq` flips the order without a code change. Groq is not removed.

## Other secrets

`AUTH_COOKIE_SECRET` and the `R2_*` storage keys are unchanged. See `DEPLOY.txt`.
