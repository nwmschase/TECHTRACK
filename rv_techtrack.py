# Grok — paste with FULL current rv_techtrack.py from GitHub main (whatever is live now — v4.8.5 or latest)

Rewrite the ENTIRE file. Return COMPLETE rv_techtrack.py only. No patch, no explanations.

## Version
- Docstring first line: `RV TechTrack v4.8.6`
- Keep v4.8.4–v4.8.5 behavior that still matters:
  - brand-lock never empty, model prefixes, fridge synonyms, fridge OEM, warranty pass-bind
  - flowchart: 1–2 tests per chat turn, wait for results
  - warranty story cites 📖 Source on performed steps
  - coach attributes excerpts to shop Document Library (never “you uploaded”)
- Add:
  - v4.8.6: Guided Diagnostics does NOT dump source-page UI every turn
  - v4.8.6: show library text/illustration pages ONLY when the tech asks
  - v4.8.6: still record cited sources silently for warranty story

## Shop bug (proven after v4.8.5)
Source-page rendering went too far. Guided Diagnostics now cites every source and expands dropdown menus (view illustration / download PDF) so the chat is hard to scroll and continue testing. Chase wants TechTrack to show source text/illustration **only when asked**. It must still keep a record of which source pages were cited for the warranty story. Do not throw the full source chrome out for every step.

## Required changes

### A) Silent source ledger (always)
On every Guided Diagnostics search/turn that finds chunks:
- Build `build_sources_payload(chunks)` (or equivalent).
- Store in `st.session_state` (and optionally AskChat) a quiet ledger: document_id, title, page, file_path, excerpt, plus any pages parsed from assistant `📖 Source` lines.
- Clear ledger on Start new chat.
- Warranty story / `ask_chat_to_warranty_story` / `improve_tech_story` MUST still be able to attach `📖 Source: [title] — page [N]` to performed steps from this ledger + coach citations.
- Do **not** require the tech to open a dropdown for the ledger to work.

### B) No always-on Source pages expander in Guided Diagnostics chat
Remove or default-hide the large **📷 Source pages** expander / per-step illustration-download chrome from the Guided Diagnostics chat UI so it does not appear under every reply or every step.
- Do not list every linked page in the main scroll path every turn.
- Do not add “Open Source pages dropdown → choose this title” spam on every coach step (Jobs WO plan can keep lighter wording or drop it).
- Inline coach citations stay short: one line `📖 Source: [title] — page [N]` is enough.

### C) On-demand only — when the tech asks
When the user message asks to see the source / illustration / figure / diagram / drawing / “show that page” / “associated illustrations” / Fig. N:
1. Resolve pages from the last assistant citations and/or the silent ledger.
2. Then show **only those** pages: `st.image` via `render_pdf_page_png` after R2 download, and/or a short text excerpt for that page.
3. Optional: a single compact download button for that one PDF — not a menu of every source from the whole chat.
4. If nothing matches, say so in one sentence and offer Download of the one best matching library PDF if known.
5. Coach reply: pages are shown below from the shop library. Never “you uploaded.”

### D) Diagnostic Jobs
Keep the existing Jobs **📷 Source pages** panel if it is useful for WO work, but do not make Guided Diagnostics chat mirror that always-open bulk UI. Prefer on-demand there too if the Jobs panel became equally noisy — Guided Diagnostics chat is the mandatory fix.

### E) Flowchart + warranty (keep)
- Chat: max one clarifying question OR 1–2 next tests; wait; branch; no Step 3/4/5 dumps.
- Warranty: cite 📖 Source on tech-performed steps that had citations; no invented pages.

### F) Do not
- Do not remove pymupdf page render capability — only stop forcing it into every turn’s UI.
- Do not remove Unity/fridge/furnace OEM, brand-lock, sidebar, cookie, R2.
- Login columns stay centered.

## Done when
Guided Diagnostics chat is readable again (no source dropdown forest every step). Asking “show the illustration / that page” still shows the real library page. Warranty story still gets silent source records / citations for steps the tech actually ran.

Return the complete rewritten rv_techtrack.py only.
