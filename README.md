# RV TechTrack

Shop app for Tacoma RV Center (`streamlit run rv_techtrack.py`). Guided Diagnostics chat, the warranty-story writer, and the data-plate photo reader share one LLM helper (`gd_llm.py`).

## Live app version

The sidebar caption starts with the version on the first line of `rv_techtrack.py` (currently `v4.20.9`). After a push to `main`, that caption should show the new version within a few minutes. That is the check that Community Cloud followed the commit. The shop word list has to stay plain text (`bay_words.txt`) in the repo root. A root-level `.gz` makes the GitHub sync skip the redeploy until someone reboots the app from the dashboard.

## Startup line (v4.20.9)

Each app process prints one line to the Streamlit log when it starts:

`TT_STARTUP {"version": ..., "commit": ..., "model": ..., "gd_temperature": ..., "reasoning_effort": ..., "smart_search": ..., "web_gate": "on", "round_limit": ...}`

That line is the check for what is actually running. No key value is ever printed.

## Model (set in code only)

The model is `grok-4.3`, set in one place: `DEFAULT_XAI_MODEL` in `gd_llm.py`. The `XAI_MODEL` secret is no longer read (v4.20.9); changing the model is a code change, and the startup line prints it.

## Guided Diagnostics (GD) calls

GD turns use the xAI Responses API with the library tools (`gd_llm.respond`). There is no Groq fallback on the GD path. Each round waits at most 240 seconds; a turn runs at most 6 rounds. The double-send guard (`gd_sends.py`) holds a repeated press for the whole turn, so the same message is never sent twice.

When a GD turn fails, the tech sees one line that names the kind of failure (took too long / xAI error with its status code / a bug in the app / no AI key), the turn log gets an `error` record with a short traceback, and the Streamlit log gets a `GD_ERROR` line. Any step that falls back to a quieter path (photo read, plate read, story, state block, picture not drawn, page links) writes a `GD_FALLBACK` line and is listed under `fallbacks` in that turn's log.

The wrap-up (story) and the access question come only at a real end of job: the "✅ Diagnosis complete" / "✅ Repair complete" buttons, Grok marking the repair verified or the job closed, or the tech plainly saying so ("diag complete", "I recommend replacing the board", "repair complete"). Questions and "not working now" never trigger it.

New chat and Open clear the whole GD job record (`gd_state.clear_job_session`).

## Warranty story and plate photos

These use Chat Completions (`gd_llm.complete_chat`). xAI is called first; if that call cannot be made or fails, the same messages are sent once to Groq. Each attempt waits at most 150 seconds with no SDK retries.

| Secret | Required | Default | Notes |
|--------|----------|---------|-------|
| `XAI_API_KEY` | Primary | | xAI API key |
| `GROQ_API_KEY` | Fallback | | Story / plate fallback only. Chat fallback model `openai/gpt-oss-120b` |
| `XAI_BASE_URL` | No | `https://api.x.ai/v1` | OpenAI-compatible base URL |
| `GD_LLM_PRIMARY` | No | `xai` | `xai` or `groq` - which provider the story / plate reader tries first |
| `XAI_VISION_MODEL` | No | | Optional plate-photo model id, tried before the code's list |
| `GROQ_VISION_MODEL` | No | `qwen/qwen3.6-27b` | Optional Groq plate-photo model |

`XAI_MODEL` is not read any more. If it is still in the Streamlit secrets it does nothing.

## Dead-code guard

`tests/test_dead_code_guard.py` fails when a function, class or constant in the live modules has no caller left (scripts count as callers, tests do not). Delete the old path in the same change that replaces it. The allowlist in that test is for real entry points only.

## Other secrets

`AUTH_COOKIE_SECRET` and the `R2_*` storage keys are unchanged. See `DEPLOY.txt`.
