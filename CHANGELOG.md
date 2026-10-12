# TechTrack — Living Version History

**Owner:** Chase Molloy / Tacoma RV Center  
**App:** https://techtrack-37lks9ceccfqe8a3k3prpy.streamlit.app/  
**Repo:** https://github.com/nwmschase/TECHTRACK (`rv_techtrack.py`)  
**Spine coverage:** inception through current main **v4.19.56** (`0d57348`); pre-v4.7.1 filled from git **2026-09-16**; v4.18.1–v4.19.54 backfilled from git/PRs/tags **2026-10-11**  
**Known-good tags:** `known-good-v41954` → `a76c68f` (v4.19.54 + docs, pre-v4.19.55); `known-good-v41952` → `8acbcbf` (v4.19.52, latest); `known-good-v41950` → `e7b2bad`; `known-good-v41949` → `cd04634`; `known-good-v41948` → `4dd6f68`; `known-good-v41947` → `b546299`; `known-good-v41942` → `f25ec8a`; `known-good-v41941-pre74` → `69d30e7`; `known-good-v41940` → `1dd8c6d`; `known-good-v4.19.39-importer` → `1a34c92`; `known-good-v4.19.39` → `d646e40`; `known-good-v4.19.38` → `110c4b8`; `known-good-v4.19.36` → `d45710a`; `known-good-v4.19.34` → `9933fe7`; `known-good-v4.19.29` → `7d11571`. Current main v4.19.54 is `known-good-v41952` shop code plus a version stamp (10 files, stamp-only) and carries no known-good tag of its own.  
**Profiles:** GD-PROFILE v1.1 and PDF-PROFILE v1.1 (Chase, 2026-10-11), at `/workspace/techtrack-validation/profiles/`.  
**Rule:** Append an entry on every merge, deploy, or revert in the same commit cycle; mirrored in repo as CHANGELOG.md.  
**Maintainers:** Tech Track + Leader (co-maintain)

---

## 1) Purpose & how to keep updating

This is the shop’s living changelog for TechTrack features and fixes — **short per version, deep across versions**. It is not marketing copy.

**On every merge/deploy:**

1. Append a new `### vX.Y.Z` section (or dated era block if version string unknown).
2. Add 2–6 bullets: features/fixes only (no fluff).
3. Update the PR ledger one-liner + merge SHA if known.
4. Bump “current main” in the header.
5. Mark gaps **UNKNOWN** — never invent dates, versions, or features.
6. Prefer evidence order: live sidebar / module docstring → GitHub PR title/body → Tech Track dump → local patch briefs → agent transcripts. **Pre-v4.7.1 fill (2026-09-16):** anonymous `git clone` → `/tmp/TECHTRACK` when `gh` unauth.

**Stack constants (corroborated):** Streamlit Cloud; Groq `openai/gpt-oss-120b`; PDFs in Cloudflare R2 (free tier — watch size); SQLite metadata (Cloud can wipe — Manager Tools DB backup / R2 auto-backup).

---

## 2) Timeline eras

| Era | Approx window | What shipped (summary) |
|-----|---------------|------------------------|
| **Pre-version / early Streamlit** | Repo created **2026-07-21**; **v3.0→v4.7.1** (git SHAs) | **Filled 2026-09-16** from anonymous git clone. Quizzes/certs → Login/Categories/Safety/Story → R2/Groq → WO Jobs / Guided Diagnostics / source viewer. **v4.3 never appears** (jump 4.2→4.4). Streamlit Cloud first deploy date **UNKNOWN**. |
| **Library / R2** | By ~2026-08 (present in v4.7.x snapshots) | Cloudflare R2 permanent PDFs; R2 re-link; catalog export; auto SQLite backup/restore to R2 (`backups/rv_techtrack_v4.db`); manager wipe warning. |
| **Certs / training / safety** | Pre–4.8 core | Certificate Hub; Safety / Compliance + Meeting Acknowledgements; Team Overview (certs + safety progress). |
| **Jobs (WO plans)** | Pre–4.8 core; kept through open-coach pivot | Diagnostic Jobs (WO #) + interactive findings + warranty story; INDEX charts → OEM procedure order; source page viewer in Jobs panel. **Jobs remain the structured plan feature** — not replaced by GD chat. |
| **Guided Diagnostics (chat quality)** | v4.7.x → v4.10.x | Ask TechTrack / GD chat over manuals + Groq; brand-lock; TSB/Recall with system category; Unity gate; fridge fuse-first; figure pipeline; then hard flowchart **ENGINE** (later rejected as GD UX). |
| **Open library coach** | ~2026-09-09 (v4.12 → **v4.13.0** land) | Complaint → cited shop Document Library; questions / clarification / figures on ask; soft-disable hard-tree “path complete” cage; no-reask stated facts; `gd_library_coach.py` at repo root. |
| **Live validation / retrieval locks** | 2026-09-12 → 2026-09-15 (v4.13.1–**v4.13.6**) | Real WO scoreboard method locked; Level-Up vs Unity; AC vs Unity; FCR E2 fan+board; GSWH-2 E8 Water Heaters retrieval. |

**Grok technician-training thread (early build):** **CONTENTS MINED 2026-09-16** — https://grok.com/c/4a4dd5bd-91f2-4c2f-b7ce-017ef27edd06 (title *Tacoma RV Technician Training Program*). Notes: `/workspace/techtrack-validation/grok-technician-training-thread-notes-2026-09-16.md`. **Sister thread not yet mined:** *Streamlit Training Program Code Review* — https://grok.com/c/4a6a6bca-6137-4b44-b841-8cf6bcb9a1f2. **Product intent (thread narrative):** started as custom training modules; reframed because OEM platforms (Lippert, Airxcel/RVTI) already train — TechTrack tracks certs/progress, centralizes shop manuals, guides diagnostics from the library, supports safety/compliance, and improves warranty CCC write-ups (formal OEM training stays outside). **Rewrite era:** thread is narrative for product intent + **v4.7.8–v4.8.6** (many full-file `rv_techtrack.py` rewrite prompts); git SHAs remain authority for v3–v4.7.1 land dates. Memory-limited prior notes still valid: ~Aug 2026 public TT complaint→fix validation; v4.7.8 session snaps → live browser ban until session holds.

---

## 3) Version sections

> Dates are **known ship/observation dates** only. “unknown” = not corroborated on disk. Bullets are features/fixes only.

### Repo inception — **2026-07-21**
- Repo created **2026-07-21T14:24:51Z**.
- First commit `8b77dac080` **2026-07-21 ~07:28 PT** — Add files via upload.
- Tags/releases: **0**. Streamlit Cloud first deploy date **UNKNOWN**.

### v3.0 — **2026-07-21** ~07:28 PT (`8b77dac080`)
- Quizzes + Demonstrated Gate + Full Manager Quiz Builder.

### v3.1 — **2026-07-21** ~08:38 PT (`8fc6f24f75`)
- Certificates + Mobile + DB Backup.

### v4.0 — **2026-07-23** ~13:38 PT (`c001add3a6`)
- Login · Categories · Safety · Story Improver.

### v4.1 — **2026-07-23** ~14:36 PT (`c1c1103812`)
- Login · Categories · Safety · Groq Story Improver.

### v4.2 — **2026-07-24** ~13:47 PT (`4baaf3cd7e`)
- R2 Storage · Groq · Safety.
- Hold at v4.2 through `0457fcb474` (**2026-07-27**) until v4.4.
- **Grok thread narrative:** later described as an older snapshot missing Diagnostic Jobs, manual-guided tests, per-step source cites, source-page viewer, index expansion, and R2 re-link (those land in later git SHAs).

### v4.3 — **never appears**
- Jump **4.2 → 4.4** in git history (no v4.3 land SHA).

### v4.4 — **2026-07-31** ~09:11 PT (`380f1f2e31`)
- WO Jobs · Guided Diagnostics · Story · R2 · Groq.

### v4.5 — **2026-07-31** ~10:43 PT (`3bc5573504`)
- R2 Re-link · WO Jobs · Backup Protect · Groq.

### v4.6 — **2026-07-31** ~13:46 PT (`85f29510d0`)
- Source page viewer · WO Jobs · R2 · Groq.

### v4.7 — **2026-08-05** ~16:10 PT (`d61f175cef`)
- Index→Procedure tests · Source pages · WO Jobs · Groq.

### v4.7.1 — **2026-08-06** ~07:24 PT (`a33e5b5ab5`)
- OEM-order tests · Source viewer · WO Jobs · Groq.
- Early patch-era snapshot also seen later as `rv_live.py` / `branded_rv_techtrack.py` / `view.html` headers.
- **Grok thread (~v4.7.x app shape):** Streamlit Cloud build with login/roles, certificates + team overview, categorized Document Library (R2 PDFs + SQLite chunks), safety meetings/acks, WO Diagnostic Jobs + Groq warranty story, source-page viewer, manager re-index / R2 re-link / backup. (Land dates for earlier pieces remain git SHAs above.)
- **Groq model transition (thread):** `llama-3.3-70b-versatile` notice decommission **2026-08-16**; `openai/gpt-oss-120b` suggested replacement; thread status as of **Aug 18–19, 2026**.

### v4.7.2 — date unknown
- Sidebar: Per-step source cites • OEM order • Source viewer • Groq (`APPLY.md`).

### v4.7.3 — date unknown
- Adds **Ask TechTrack** chat tab (manuals + Groq `openai/gpt-oss-120b`).
- Warranty story from chat transcript (`APPLY.md`).

### v4.7.4 — date unknown
- Tacoma RV Center branding (logo + shop colors `#038944` / `#DF1F26` / `#01147C`).
- Hide default-password login banner (`APPLY_BRAND.md`).

### v4.7.5 — **UNKNOWN**
- No corroborated local bullet list between v4.7.4 and v4.7.6.

### v4.7.6 — date unknown
- Guided Diagnostics • Honest warranty notes • Auto DB backup (sidebar in `view.html` / `STORY_REGEN.md` baseline).

### v4.7.7 — ~**2026-08-20** (commit `1995f1e` on main)
- Write warranty story remounts copy box each click (fixes stale Streamlit widget key).
- `_notes_say_incomplete` uses **last occurrence** so later recorded fix beats earlier “no repair yet” (`STORY_REGEN.md`).

### v4.7.8 — ~**2026-08-21** (commit `2cb39ba`)
- Guided Diagnostics refuses wrong-brand manuals (“No wrong-brand steps”).
- TSB / Recall searched with the system category.
- Write warranty story includes unsent box text.
- Live session-snap era began (~2026-08-21 PT); Leader banned live browser/desktop passes until session holds.
- **Grok thread:** GitHub `rv_techtrack.py` still v4.7.8 (same SHA as Aug 21); live app still using thin checklist warranty prompt — start of **v4.7.8–v4.8.6 rewrite era** (full-file rewrite prompts in thread).

### v4.7.9 — observed live **2026-09-02** (~3:51 PT)
- Live sidebar showed v4.7.9 during Ground Control LCD Cheat Sheet upload (Leveling; ~4 chunks).
- Transcript note: add OpenAI client for xAI Grok path (exact ship contents beyond that **thin**).
- **Grok thread rewrite ask:** stronger warranty writer — no invented tests/readings/parts/repairs; preserve every recorded reading; interpretation only from tech notes; professional CCC/handoff; `max_tokens` → 1600; xAI Grok (`grok-4.6`) routing with Groq fallback; manual RAG/R2/indexing unchanged. Thread notes GitHub/live may not yet have received that file.

### v4.8.0 — date unknown
- 10-hour signed login cookie (`extra-streamlit-components` + `itsdangerous`; `AUTH_COOKIE_SECRET` for Streamlit Cloud) — evidenced in cloud-agent / deploy notes.
- Addresses dropped-websocket forced re-login (session-snap class of failures).
- **Grok thread:** signed 10-hour `tt_auth` cookie; restore/recheck SQLite user; sliding refresh; logout deletion; patch still needed to land in `rv_techtrack.py` before live would use it.

### v4.8.1 — observed live (pre–v4.8.2 prompts)
- Layout fills screen / max-width CSS present, but Streamlit Cloud side gutters still large (`grok-prompt-v482-*`).
- Exact additional bullets beyond layout **UNKNOWN**.
- **Grok thread:** remove 1200px content cap / large gutters while keeping centered login columns; sidebar caption to show Tacoma RV Center + 10-hour cookie.

### v4.8.2 — date unknown
- Harden Streamlit CSS so side gutters stay dead on Streamlit Cloud.
- Unity / OneControl CAN multiplex gate + OEM test order + Electrical cross-search.
- **Grok thread:** same features named (Unity/OneControl CAN-multiplex gate, OEM test order, Electrical/Reference cross-search, stronger gutter CSS).

### v4.8.3 — date unknown
- Collapsed sidebar must not reserve ~220px left gap.
- **Grok thread:** CSS scoped to expanded vs collapsed sidebar state.

### v4.8.4 — date unknown
- Never brand-lock to empty; fridge synonyms + FCR model prefix match.
- Fridge no-power OEM order (accessible fuse before teardown).
- Warranty story binds vague tech “pass/good” to coach’s last recommended test.
- **Grok thread:** model-prefix terms (e.g. FCR10 from FCR10DCGTA); fridge synonyms/topic injection; pass-bind for vague confirmations such as “voltage good.”

### v4.8.5 — date unknown
- Coach attributes excerpts to shop Document Library (never “the text you uploaded”).
- GD as branching flowchart — 1–2 tests per turn, wait for results.
- Warranty story cites 📖 Source (manual + page) on each tech-performed step.
- GD chat can show real library PDF pages when techs ask for figures (prompt era).
- **Grok thread:** one clarifying question or 1–2 next tests per turn; warranty cites manual/page when the coach cited one.

### v4.8.6 — date unknown
- GD does **not** dump source-page UI every turn.
- Show library text/illustration pages **only when the tech asks**.
- Silent source ledger still records cited pages for warranty story.
- **Grok thread:** quiet/silent source ledger retained; no always-on source-page/dropdown forest; on-demand pages only when asked. Final v4.8.6 fix prompted by SyntaxError from raw version bullets/Unicode dashes outside the module docstring — request was a valid complete Python file. End of this thread’s **v4.7.8–v4.8.6 rewrite era** narrative span.

### v4.8.7 — date unknown
- Never invent built-in fault/blink LEDs; Furrion FCR flash codes need SM clip-on diagnostic LED (or skip that gate).

### v4.8.8 — date unknown
- Figure/page requests lock to the cited manual only — never cross-book Fig./page matches.

### v4.8.9 — date unknown
- Never emit markdown/fake images; 📖 Source page must match the claim; only R2 renderer shows photos.

### v4.9.0 — date unknown
- Data-plate photo fills Model/System (camera or upload; shop AI key).

### v4.9.1 — date unknown
- Fix library page miss — Source en-dash cites + page-of-manual + DB title fallback for figures.

### v4.9.2 — date unknown
- Rebuild GD page pipeline — detect → parse → resolve Document/page → R2 + pymupdf render.

### v4.10.0 — date unknown
- Guided Testing flowchart **ENGINE** — hard procedure trees; tech reports, tree edges decide next gate.
- Furrion FCR CCD-0008122 tree (fuse → dial/battery → paper → operating?/Not Cooling); no invented fan volts after paper.
- **Product note (later):** hard-tree quiz rejected as GD chat UX (Jobs keep plans).

### v4.10.1 — date unknown
- Fix Yes/No gate buttons (no `ask_input` write after widget); map not-operating tech language on operating diamond.

### v4.10.2 — date unknown (snapshot in `/workspace/tt-incoming/rv_techtrack.py`)
- Operating gate = listen/feel compressor **or** optional >1A clamp at appliance 12V feed (Fig. 8–9 p.20), not compressor pins.

### v4.11.0 — date unknown (PR #2/#3 recipe/flowchart era; **not** live GD product path)
- Flowchart trees load from `procedures/*.json`; engine pins brand/model/concern.
- Pass/Fail/reading gates + silent source ledger on the job pin (warranty).
- Data-driven GD engine (Furrion tree stays live) — evidenced in cloud-agent transcripts for cage/recipe work.
- **Chase/Leader:** recipe-engine cage **paused** as GD product UX (`GD-BRIEF-2026-09-09.md`).

### v4.12.0 — ~**2026-09-09** (PR #4 branch)
- GD chat is an **OPEN LIBRARY COACH** (cite shop manuals; answer questions; show figures on ask).
- Soft-disable hard-tree “path complete / start a new chat” cage in GD chat (Jobs WO plan unchanged).
- Plate photo uses working Groq vision (`qwen/qwen3.6-27b`) after xAI; `llama-4-scout` 404 retired.
- Superseded as final land by v4.13.0 simple coach (PR #6).

### v4.13.0 — **2026-09-09** (PR #6 merge; PR #5 draft superseded)
- GD chat is a **SIMPLE** open library coach (cite manuals; questions; figures; pivots).
- Hard-tree / Yes-No gate quiz does **not** drive GD chat; never re-ask facts the tech already stated.
- Plate vision: working Groq vision after xAI; scout 404 retired.
- Live caption observed: `v4.13.0 • Tacoma RV Center • Open library coach • Auto DB backup`.

### v4.13.1 — **2026-09-09** (PR #7, merge `fd0b663…`)
- Figure/terminal asks retrieve real SM diagram pages (not wrong Quick Notes p.13).

### v4.13.2 — **2026-09-09** (PR #8, merge `171c02a…`)
- Level Up Advantage / 807662 library search prefers Level-Up / OCTP / TI over Unity board SM.

### v4.13.3 — **2026-09-12** (PR #9, merge `202c45d…`)
- Air Conditioning GD search skips Unity board SM unless the tech names OneControl / Unity / CAN.

### v4.13.4 — **2026-09-12** (PR #10, merge `bf0299c…`)
- Streamlit loads `gd_library_coach` from this file’s folder (no stale/missing-module ImportError after #9).

### v4.13.5 — **2026-09-15** (PR #11, merge `0d2f13c`)
- Furrion FCR E2 / Fan Fault Current can reach freezer evaporator fan R&R (and board+fan) via `ensure_fcr_e2_fan_rr`.
- Live WO 155578-2 retest **PASS** (fan + inverter PCB; off-path 0; CCD-0008122 p.27).

### v4.13.6 — **2026-09-15** (PR #12, merge `bd563d4`) — **current main**
- Water Heaters / Girard GSWH-2 E8 GD search skips Unity and keeps E8 / CCD-0009390 chunks (Water Heaters under `(any)` + keep short fault-code token).
- Live GSWH-2 E8 retest **HIT** (Petit Tube realign; cited pp.35–36; off-path 2).

---

## 4) PR ledger (#1–#12)

| PR | Status | One-liner |
|----|--------|-----------|
| **#1** | **OPEN** (not merged) | Furnace OEM order: thermostat bypass + sail-switch IN/OUT first; created **2026-09-02**; tip `c97725a` on v4.7.9; https://github.com/nwmschase/TECHTRACK/pull/1 |
| **#2** | NOT product path | Hard recipe/cage GD architecture — Chase/Leader paused; do not ship as GD UX. |
| **#3** | NOT product path | Recipe/flowchart cage continuation — paused with #2. |
| **#4** | Reviewed; HOLD then superseded | Open library coach (v4.12.0) — localhost verify; not final land. |
| **#5** | Draft / conflicts; superseded by #6 | Simple open library coach v4.13.0 (hard tree exclusive OFF; no-reask). |
| **#6** | **MERGED 2026-09-09** | Land simple coach on main (v4.13.0 + `gd_library_coach.py` at root). |
| **#7** | **MERGED 2026-09-09** `fd0b663…` | v4.13.1: figure/terminal asks → real SM diagram pages. |
| **#8** | **MERGED 2026-09-09** `171c02a…` | v4.13.2: prefer Level-Up/OCTP/TI over Unity for 807662 GD. |
| **#9** | **MERGED 2026-09-12** `202c45d…` | v4.13.3: skip Unity board SM on Air Conditioning GD. |
| **#10** | **MERGED 2026-09-12** `bf0299c…` | v4.13.4: hotfix Streamlit ImportError loading `gd_library_coach`. |
| **#11** | **MERGED 2026-09-15** `0d2f13c` | v4.13.5: FCR E2 Fan Fault can reach freezer evaporator fan R&R. |
| **#12** | **MERGED 2026-09-15** `bd563d4` | v4.13.6: GD cites Girard GSWH-2 / CCD-0009390 for E8. |

Open issues/PRs beyond #12: GitHub once reported `open_issues_count: 5` — **which ones UNKNOWN** without authenticated API.

---

## 5) Open holes / UNKNOWN eras

| Gap | Status |
|-----|--------|
| Inception → **v4.7.1** land SHAs / PT dates | **FILLED 2026-09-16** from anonymous git clone `/tmp/TECHTRACK` |
| Exact first Streamlit Cloud deploy date | **UNKNOWN** |
| **v4.7.5** contents | **UNKNOWN** |
| Exact ship dates for most v4.8.x–v4.10.x / v4.11.0 | **UNKNOWN** (bullets known; dates thin) |
| **PR #1** | **OPEN** not merged — title/URL/tip known (Furnace OEM order…; tip `c97725a` on v4.7.9) |
| **Grok technician-training thread** contents | **CONTENTS MINED 2026-09-16** — https://grok.com/c/4a4dd5bd-91f2-4c2f-b7ce-017ef27edd06; notes in `grok-technician-training-thread-notes-2026-09-16.md` |
| **Sister Grok thread** *Streamlit Training Program Code Review* | **not yet mined** — https://grok.com/c/4a6a6bca-6137-4b44-b841-8cf6bcb9a1f2 |
| GitHub Releases / tags | **0** tags (anonymous clone 2026-09-16); full authenticated chronology still thin |
| Live sidebar string often invisible on Streamlit UI | Confirm via behavior + module version, not banner alone |
| Water Heaters category still missing from GD UI picker | Retrieval works with `(any)` after v4.13.6 |
| Stabilizer jack roll-pin assembly R&R library hole | 2026-09-15 GD **PARTIAL** |

---

## 6) Living log rules

1. **Append on each merge/deploy** — do not rewrite history; correct with dated “errata” notes if needed.
2. **Tech Track + Leader co-maintain** this file under `/workspace/techtrack-validation/`.
3. **Never invent** version numbers, dates, PR titles, or features. Use **UNKNOWN** or **NEEDS GROK THREAD**.
4. Prefer **features/fixes only** (2–6 bullets). Link evidence paths in Source Index when non-obvious.
5. After live WO validation, append scoreboard pointers (do not duplicate full case write-ups here) → `real-world-gd-summary-2026-09-12.md`.
6. When `gh` is authenticated, refresh PR ledger SHAs/titles from `nwmschase/TECHTRACK`; until then keep **GH_UNAUTH** notes.

---

## SOURCE INDEX

### Used (on box)

| Source | What it contributed |
|--------|---------------------|
| `/workspace/techtrack-validation/version-history-dump-for-leader-2026-09-15.md` | **Authoritative spine** — version table, PR #2–#12 one-liners/SHAs, eras, repo created 2026-07-21 |
| Parent steering (2026-09-15) | Confirmed **v4.13.2** = Level Up/807662 vs Unity (PR #8); current main **v4.13.6** |
| Anonymous `git clone` → `/tmp/TECHTRACK` (**2026-09-16**, `gh` unauth) | Pre-v4.7.1 land SHAs/PT dates v3.0–v4.7.1; repo created 2026-07-21; 0 tags; hold at v4.2 through `0457fcb474`; PR #1 open tip `c97725a` |
| `/workspace/shein/imagine-thread-notes.md` (Aug 21 sidebar dump) | Earlier Grok URL discovery: *Tacoma RV Technician Training Program* → https://grok.com/c/4a4dd5bd-91f2-4c2f-b7ce-017ef27edd06 |
| `/workspace/techtrack-validation/grok-technician-training-thread-notes-2026-09-16.md` | **CONTENTS MINED 2026-09-16** — product-intent reframing; Groq→gpt-oss-120b notice; v4.7.8–v4.8.6 rewrite-era narrative; sister thread URL not yet mined |
| `/workspace/techtrack-patches/TECHTRACK-BRIEF.md` | Live URL; Groq model; R2 free tier; SQLite wipe; v4.7.8 / `2cb39ba` |
| `/workspace/techtrack-patches/GD-BRIEF-2026-09-09.md` | Open coach vs Jobs; PR #2/#3 paused |
| `/workspace/techtrack-patches/APPLY.md`, `APPLY_BRAND.md`, `STORY_REGEN.md` | v4.7.1–4.7.4, v4.7.6–4.7.7 Ask TechTrack / branding / warranty remount |
| `/workspace/techtrack-patches/pr4-open-coach/rv_techtrack.py` | Embedded changelog v4.8.2→v4.12.0 |
| `/workspace/techtrack-patches/pr5-simple-coach/rv_techtrack.py` | v4.13.0 simple coach bullets |
| `/workspace/tt-incoming/rv_techtrack.py`, `rv_techtrack_v487.py`, `grok-prompt-v482…v487*.md` | v4.8.1–4.8.7 prompts; v4.10.2 snapshot; cookie/layout bullets |
| `/workspace/tt-live-test/REPORT.md` | Live v4.7.7 sidebar confirmation |
| `/workspace/techtrack-validation/real-world-gd-summary-2026-09-12.md` | PR #8–#12 validation; v4.13.3–4; Sep 15 FCR/GSWH scores |
| `/workspace/techtrack-validation/eod-draft-2026-09-15.md` | PR #11 PASS / PR #12 HIT / stabilizer PARTIAL |
| `/home/box/agent-data/projects/techtrack/memory/.../log/2026-08.md`, `2026-09.md` | v4.7.7/4.7.8 commits; v4.7.9 + GC cheat sheet 2026-09-02; R2 notes |
| `/workspace/cloud-agent-transcripts/*.jsonl` | PR #2–#12 agent intents; **v4.11.0** JSON-tree bullets; v4.8.0 cookie notes; v4.13.1–6 docstring lines |
| `/workspace/techtrack-patches/validation/pr4-*.md`, `leveling-library-fix-2026-09-09.md` | PR #4 review; live v4.13.0 caption |

### Attempted / blocked

| Attempt | Result |
|---------|--------|
| `gh` against `nwmschase/TECHTRACK` | **GH_UNAUTH** — not logged in; skipped inventing from empty |
| GitHub REST API anonymous PR list | **403 rate limit** |
| Anonymous `git clone` `nwmschase/TECHTRACK` → `/tmp/TECHTRACK` | **OK 2026-09-16** — filled pre-v4.7.1 SHAs; 0 tags/releases |

### Still missing (top)

1. **Sister Grok thread** *Streamlit Training Program Code Review* — https://grok.com/c/4a6a6bca-6137-4b44-b841-8cf6bcb9a1f2 — **not yet mined**.
2. **PR #1** remains **OPEN** (not merged) — title/URL known; full body/review history still thin without auth.
3. First Streamlit Cloud deploy date still **UNKNOWN**.
4. Exact ship dates for most v4.8.x–v4.11.0 bumps (Grok thread adds rewrite-era narrative for v4.7.8–v4.8.6; land dates still thin).
5. Whether open GitHub issues/PRs beyond #12 matter to product (count was 5; IDs unknown).

---

*First draft written 2026-09-15 PT. Pre-v4.7.1 filled from anonymous git clone 2026-09-16 PT. Grok technician-training thread CONTENTS MINED 2026-09-16 PT (product intent + v4.7.8–v4.8.6 rewrite narrative; git SHAs remain land-date authority). Current main **v4.13.6**. Append-only from here.*

### v? — 2026-09-16 — PR #14 merged `9622463933ba4fcac08354d2d992bf58454aea6b`
- GD coach: cooktop pan-on → tip position + cookware-on **before** parts R&R
- GD coach: stabilizer override roll pin → **complete jack assembly** (not coupler-only)
- PR #13 (category picker) still open / unmerged

### 2026-09-17 — PR #15 hotfix `bb42cdd`
- Fix live AttributeError after #13: reload gd_library_coach when category sentinels missing (stale Streamlit sys.modules)
- Tests: 140 OK; re-export bind + stale-cache reload coverage

### 2026-09-18 — PR #16 merged `ebba8f7`
- GD coach: fridge rear/back-wall ice/frost → CCD-0008122 Ice/Moisture p.36 / Fig.36 (not fuse/12V no-power tree)

### 2026-09-18 — PR #17 merged `69ff738`
- FACR freeze/condensate/base-pan retrieval ranks CCD-0007990 with CCD-0008666 (live spot-check: 7990 cited)

### 2026-09-18 — PR #18 merged `f16e0b2`
- GD coach: Level Up Advantage 807662 Manual Mode flash-home when Auto Level still works → Firefly/OneControl CAN isolate prove (terminator in, wired CAN out)
- Branches: Manual stays CAN-out → Firefly USB FW (GUI+CCM, 574-825-4600, ≤4 GB) + interim; Manual still dumps → Lippert path (no Firefly USB / no 807662 swap for Firefly blame)
- Tests: 176 passed before merge; v4.13.12

### 2026-09-18 — PR #19 merged `67f82a1b546352a26eaa35a9573b382c191bd1a1`
- Replaces Diagnostic Jobs with **Bay procedure PDF** builder (GD chat unchanged)
- Seed HIT: FCR ice→8122 p.36; FACR freeze→7990; Level Up Manual Mode→CAN+Firefly USB

### v4.18.0 — 2026-09-24 — PR #26 merged `28878cf657a812f13e9b774e63fc7622b04d94b1`
- Guided Diagnostics primary provider **xAI** (`grok-4.6` via `https://api.x.ai/v1`); Groq remains automatic fallback
- Shared helper `gd_llm.complete_chat` for GD chat / warranty-story / data-plate photo paths
- Secrets: require `XAI_API_KEY` for primary; keep `GROQ_API_KEY`; optional `XAI_MODEL` / `XAI_BASE_URL` / `GD_LLM_PRIMARY`
- No OEM / FACR / Coleman recipe changes; missing XAI key falls back to Groq until Streamlit secret is set

### v4.18.1 — 2026-10-09 15:29 PT — PR #30 (GitHub shows closed/unmerged; squash commit on main says “Fixes #30”) — main SHA `d709703dd67d1c2df9ddc86dca9b0ff4d4ab1489`
- Bay procedure PDF layout: every sheet measures text before it draws
- Flowchart ovals, diamonds, rectangles grow to the inscribed text box; section bars follow the previous block's real height; arrows stay in the gutters
- Known-good tags: none

### v4.18.2 — 2026-10-09 15:31 PT — PR #27 merged — main SHA `bae23e427d64b2485611f53cd2d7796275b477d6`
- Bay PDF stays on the named brand (Coleman-Mach jobs cite Coleman manuals); brand lookup shared with Guided Diagnostics
- A known brand with no matching manual is stated instead of borrowing another maker
- Unlocked bay sheets are yes/no shop steps instead of raw OCR
- Furnace sheets jumper R/W at the furnace, then prove the sail switch; FCR E2 follows Fan Fault Diagnostics to the inverter PCB and fan
- Known-good tags: none

### v4.18.3 — 2026-10-09 15:46 PT — PR #31 merged — main SHA `65470f6222c283520956b72157f21895d6cfc87c`
- Bay PDF SOURCES use human titles and whole sentences
- Drops filename slugs, flat-rate lines for a different assembly, and mid-word OCR scraps; locked sheets keep known cites
- Known-good tags: none

### v4.18.4 — 2026-10-09 15:54 PT — PR #28 merged — main SHA `f140af7abf96cc6cf2374482242f753cd29f497f`
- Ban “channel” from GD and Bay PDF tech wording (output wire / check the wire / check the circuit)
- BAL: no 12V on tongue output wire → replace soft-touch user panel 20300427; 12V present → repair tongue pigtail
- Commit notes full suite 290 tests OK
- Known-good tags: none

### v4.19.0 — 2026-10-09 15:57 PT — PR #29 merged — main SHA `b47716b62d7a7651cf6782639e82a0a73ea0a932`
- Bound AI calls: each provider gets one 150s attempt, then Groq or a send-again message (was SDK default 10 min + 2 retries)
- Section choice and Category/Model live in session state; Ctrl+Enter submits the message form
- Known-good tags: none

### v4.19.1 — 2026-10-09 16:15 PT — PR #32 merged — main SHA `cc5bbaa889da8b3c48f868dc699ddbd551c18cec`
- FACR rooftop assembly R&R waits until refrigerant pressures are reported
- Rear-wall ice keeps the one-month replace-the-unit close
- Ground Control and Dometic no-cool retrieval share the Bay PDF brand/model match; closes grok-4.3 gaps
- Known-good tags: none

### v4.19.2 — 2026-10-09 16:19 PT — PR #33 merged — main SHA `ce736eb27b1e5f6911bbef0d3db361ca62aa7b19`
- Bay sheets kept to 3 pages; crop cited figures instead of full manual pages; drop raw OCR
- Skip placeholder/orphan source pages; FACT12 file whose body is the FACR08 8K book is not cited as the FACT12 manual
- Known-good tags: none

### v4.19.3 — 2026-10-09 16:31 PT — PR #34 merged — main SHA `2eb6c686cd41689b8c42154a608f1a96999b9f7d`
- Ground Control auto-level lifting one side gets the Electric Leveling zero-point sequence once (no repeat, no sensor swap)
- Dometic fan-runs/no-cold opens on manual 3311071 with Peacemaker and ceiling-selector bypass
- Library-coverage sentence said at most once
- Known-good tags: none

### v4.19.4 — 2026-10-09 16:41 PT — PR #35 merged — main SHA `6ce4c7c74eb6cdc91731298237d9ea5d416c5e81`
- B57915 turns-on/no-cold opens on 3311071: confirm fan runs, then Peacemaker bypass, on turn 1
- Live check FAILED (FIX-REPORT-LOG ~4:43 PM PT 10-09): T1 still library-miss + filter → root-caused in v4.19.5
- Known-good tags: none

### v4.19.5 — 2026-10-09 16:51 PT — PR #36 merged — main SHA `cbb1d84137a44163ef5de27cd9f5e11c1cc3f13f`
- Root cause: Streamlit kept the stale v4.19.3 coach module across redeploy; reload that cache
- Apply the 3311071 guard on the raw complaint after the model draft (live OK per FIX-REPORT-LOG)
- Known-good tags: none

### v4.19.6 — 2026-10-09 16:55 PT — PR #37 merged (commit subject says “v4.19.4”; header/PR title say v4.19.6) — main SHA `759bea14ebcfc03d95a9f795431f5b41870df7ef`
- Bay PDF shares GD corrections: ice, Dometic no-cool, Ground Control, FACT12 E2/E3, Girard E8, stabilizer override, cooktop tip use the GD climax
- Captions match the drainage figure; generated sketches not painted as OEM pages
- Known-good tags: none

### v4.19.7 — 2026-10-09 17:17 PT — PR #38 merged — main SHA `023a971ef4cd26b8e76da3d0b1174724795dba04`
- Snippets drop flowchart OCR, fig-ref scraps, part-number runs, cut endings
- Furnace, Dometic bypass, Ground Control, FACT12, Girard charts follow bay order; figures keep a full region
- Known-good tags: none

### v4.19.8 — 2026-10-09 17:33 PT — PR #39 merged — main SHA `2baf123a2e9a9aa2bf3c3da4d1a09f1d5112921e`
- One guard reloads coach, gd_llm, bay_procedure unless their revision matches the app version (stale-module fix)
- Bay sheet DATE uses America/Los_Angeles
- Known-good tags: none

### v4.19.9 — 2026-10-09 17:56 PT — PR #40 merged — main SHA `e2ba172733f9082daa3f8cdd9e5e8cbf05c1945d`
- Bay snippet line joins keep spaces; repeated clauses/duplicate pages drop; voltage ranges stay intact
- Drop illegible figures; NO labels sit on arrows; FACT12 sheet with only the FACR08 book says so
- Known-good tags: none

### v4.19.10 — 2026-10-09 18:16 PT — PR #41 merged — main SHA `f4d4478b3b3155f89ed92caaba426e0d9285f4cd`
- Drop near-duplicate pages, stray question bullets, cut color endings, leading figure numbers
- Attach YES/NO to arrows; add ice unit ID table; cooktop sheet cites only burner/thermocouple text
- Known-good tags: none

### v4.19.11 — 2026-10-09 18:40 PT — PR #42 merged — main SHA `529a475d738721b4db43b0e7b5a07642277447af`
- Em/en dashes become spaces; all-lowercase joins (e.g. willgo) split when both parts are dictionary words
- Eight clean Bay sheets snapshot-locked (added bay_words.txt.gz)
- Known-good tags: none

### v4.19.12 — 2026-10-09 19:02 PT — PR #43 merged — main SHA `04779ada2ca58e9fcd20763ef745cf4b89af6b11`
- A page named in PRIMARY survives snippet dedupe
- Dictionary splits need two real words whose join is not a word (ducted, petit stay whole); drainage figure is one bordered row
- Known-good tags: none

### v4.19.13 — 2026-10-09 19:27 PT — PR #44 merged — main SHA `290d474bfd870adf24ca791713ff4f1c646fc396`
- CCD-0007990 p.7 drainage crop shows the full row
- Hyphen after one capital stays F-/T-; prepositional fragments with no verb dropped
- Known-good tags: none

### v4.19.14 — 2026-10-09 19:44 PT — PR #45 merged — main SHA `239cee85d2dbaff98f459ecbd223325ea1dfba40`
- Source snippet ends at the last sentence with a verb; trailing noun phrase dropped when a full sentence precedes it
- Known-good tags: none

### v4.19.15 — 2026-10-09 20:01 PT — PR #46 merged — main SHA `a8627c66fdd6c3040723e23bcee9a02f2131cbb9`
- Shop word list stored as text (bay_words.txt) so Community Cloud follows main again (gzip root binary kept squash merges off live)
- Rename gitignore → .gitignore
- Known-good tags: none

### v4.19.16 — 2026-10-09 21:09 PT — PR #47 (GitHub shows closed/unmerged; squash commit on main references #47) — main SHA `c747a119dceffebdb42c1e69f4d240a83c1f37d1`
- Bay Sources keep whole on-topic sentences; drop scanned fragments, index notes, contradicting snippets
- Figures keep borders; no-12V fan branch names board and fan; blank stabilizer job prints its model; clears GD model field
- Known-good tags: none

### v4.19.17 — 2026-10-09 22:07 PT — PR #48 (GitHub shows closed/unmerged; squash commit on main references #48) — main SHA `6f48a603717c22221e1f5632b957ee37e65083fe`
- Sources line is one complete sentence about this procedure
- GD handles instruction echoes, repeated checks, already-supported repairs; cooktop tip cites Suburban SDN2U p.4 Figs. 3-4
- Known-good tags: none

### v4.19.18 — 2026-10-09 23:08 PT — PR #49 (GitHub shows closed/unmerged; squash commit on main references #49) — main SHA `ff5ae01c98c0212a4b0137d2977728654eb43a9b`
- Sources line needs a page; quote is one verbatim sentence from that page or page cited with no quote
- FACT12 repairs stay on a FACT12 model; same canned reply not sent twice
- Known-good tags: none

### v4.19.19 — 2026-10-09 23:53 PT — PR #50 (GitHub shows closed/unmerged; squash commit on main references #50) — main SHA `89ff6b2905431ed726bdec89c49b0872a5876c04`
- Copy bay quotes from retrieved chunks; polish shop replies (commit body empty)
- Per FIX-REPORT-LOG: quotes only from retrieved chunk text + substring test; restored cites; no 'See doc.'; S04 full model
- Known-good tags: none

### v4.19.20 — 2026-10-10 00:39 PT — PR #51 merged — main SHA `990c1a75cea3472dd4a1491154587fc2429b8571`
- Start new chat clears Category; named model beats leftover category
- Noted/reported claims must be in the tech's words; reply keeps a next step
- Bay sheet naming a page in PRIMARY keeps that page in Sources (furnace sources restored)
- Known-good tags: none

### v4.19.21 — 2026-10-10 01:04 PT — PR #52 merged — main SHA `2be0315a8503f4be44677f141363e5d9e77bdb92`
- Replies no longer open with Noted/Heard; good/reported/checked claims only when in the tech's words
- After the repair is given, a later turn answers or says the repair stands once; no repeated sentence
- Known-good tags: none

### v4.19.22 — 2026-10-10 01:47 PT — PR #53 merged — main SHA `c3c0f25ad82f867b3031598d60969e65006b4ffe`
- Ask for the proving check before a repair; later turn follows the measurement just reported
- Girard E8 = air-pressure switch at the blower; FACT12 E3 shows 12 V and data-line path
- Live GD REGRESSED per FIX-REPORT-LOG (proving gate blocked repairs; S10 blank replies) → fix round 8
- Known-good tags: none

### v4.19.23 — 2026-10-10 02:37 PT — PR #54 merged — main SHA `57c7d81b1482ef5af1e0dc4c00a0973b078352a7`
- Conditional If-X-then-Z repair after the prove; no blank or repeated sentence
- Bay sheets close Fig. 36, drop rear-stabilizer cite on a front jack, list Level Up docs only, add missing dial-off/FACT12/Girard/Dometic lines
- Live GD SEVERE REGRESSION per FIX-REPORT-LOG (cross-case leaks) → v4.19.24
- Known-good tags: none

### v4.19.24 — 2026-10-10 03:19 PT — PR #56 merged (PR #55 closed with merge conflicts) — main SHA `d6f1a3ac4c70ba0c5c74b7236acc2d024f8715df`
- Lock each GD reply to its own job: Category and Model win over earlier coach lines (root cause of cross-case leaks)
- Placeholders and broken If-sentences cannot ship; firm repair stays the repair
- Bay sheets drop reversed C/T note, cite Level Up p.1, name Brisk II p.23, finish FACT12 and Girard charts
- Known-good tags: none

### v4.19.25 — date **UNKNOWN** (never on main) — PR #57 (`9cebf4d`) — **NOT MERGED** (closed)
- Contingency v4.19.25-revert: restore the v4.19.21 GD reply layer; never shipped to main
- Per FIX-REPORT-LOG: not merged because live v4.19.24 showed no cross-case leaks
- Known-good tags: none

### v4.19.26 — 2026-10-10 03:57 PT — PR #58 merged — main SHA `a5eb2bdf2401072a2451f444342b52f18d9ddd52`
- Firm repair reads “The repair is to <verb>”; answered check not asked again or restated as the repair
- Ground Control keeps FRONT ×5, REAR ×5, then ENTER; Girard chart lines no longer cross; FACT12 E2 chart says Reseat
- Known-good tags: none

### v4.19.27 — date **UNKNOWN** (never on main) — PR #59 (`c40685e`) — **NOT MERGED** (closed); contents shipped inside PR #60 / v4.19.28
- Keep a firm repair firm; Girard decisions get their own exits; sail-switch continuity OK counts as the prove
- Per FIX-REPORT-LOG: merge approval card interrupted with no decision
- Known-good tags: none

### v4.19.28 — 2026-10-10 08:29 PT — PR #60 merged (includes #59's v4.19.27 commits) — main SHA `f8debe56e9817e0eaf5b059005005fe982e217ba`
- Do not cite another brand when the shop library has no match (Thetford toilet no longer cites Norcold fridge)
- Reading filler line cannot ship, including when the job has no lock
- Plumbing / Toilets is a library category
- Known-good tags: none

### v4.19.29 — 2026-10-10 09:41 PT — PR #61 merged — main SHA `7d11571141d0cca5c697cc55a5539122ce5d6e6d`
- Thetford flush-lever leak follows supply connection → water valve at pedal → vacuum breaker during flush → floor flange
- Multilingual lines and other troubleshooting rows stay off the sheet
- Known-good tags: `known-good-v4.19.29`

### v4.19.30 — date **UNKNOWN** (never on main) — UNKNOWN
- **UNKNOWN** — no v4.19.30 string found in rv_techtrack.py history, commit messages, PR titles, or box notes (apparent skip 4.19.29 → 4.19.31)
- Known-good tags: none

### v4.19.31 — 2026-10-10 10:57 PT — PR #63 merged — main SHA `ca2c02462054d88acca3873525d153ee290df873`
- FACR retest NO arrow leaves the diamond for the clear-drain end; drain NO label off the return-line junction
- After pressures, rooftop assembly R&R authorized once; overnight ice, Girard seating, cooktop tip close as firm repairs
- Coleman stop line dropped; ask turns use smaller context with low reasoning cap
- Known-good tags: none

### v4.19.32 — 2026-10-10 10:59 PT — PR #62 merged — main SHA `e86bc0dc2894579eb62a267deadc1830e562721c`
- Level Up S20 lead-jack drift: ask gray-wire coil, swap plumbing, override screw before front lead-jack cartridge 177094
- S20 stays off the Manual Mode path (GD and Bay sheet)
- Known-good tags: none

### v4.19.33 — 2026-10-10 11:30 PT — Direct commit on main (rollback; no PR) — main SHA `5a2f2e98aff32f42041afbe33234fc485a16911d`
- **REVERT** of v4.19.31 + v4.19.32: content matches known-good-v4.19.29 (`7d11571`)
- Revert reason: **UNKNOWN** beyond commit text (“changes are off this deploy”); no gate summary or fix-log entry found
- Known-good tags: none

### v4.19.34 — 2026-10-10 11:52 PT — PR #64 merged — main SHA `9933fe75bfffaf56611decd0457f6a48dabbdc43`
- Restore the live GD fixes without the blank Thetford turn or the slow S20 plumbing loop
- Source-only/empty Thetford turn returns the next cited leak check; Level Up lead-jack plumbing answered without a model call
- Cartridge 177094 cites Level Up Towable OM p.15 or FW OM p.18; answered plumbing slot not re-asked
- Known-good tags: `known-good-v4.19.34`

### v4.19.35 — 2026-10-10 12:28 PT — PR #65 merged — main SHA `2b1b0e79e85208d7a02411dd60e7e9344db02c63`
- After pressures, authorize rooftop R&R without internal FACR prove guard or thermostat-setpoint ask
- Dry-and-wait with frost back replaces the cooling unit; Water Heaters stays atop GD category list
- Level Up hose cite FW OM p.13; Thetford kit sources drop non-leak install quotes
- Known-good tags: none

### v4.19.36 — 2026-10-10 12:55 PT — Direct commit on main (rollback; no PR) — main SHA `d45710affa606bffcec3b7324f7126dcb6fd792d`
- **REVERT** of v4.19.35: content matches known-good-v4.19.34 (`9933fe75`)
- Revert reason: **UNKNOWN** beyond commit text (“v4.19.35 is off this deploy”)
- Known-good tags: `known-good-v4.19.36`

### v4.19.37 — 2026-10-10 13:07 PT — PR #66 merged — main SHA `9975665611be52adff4fb8dc40e429d69313669c`
- Re-applies v4.19.35 fixes on the v4.19.36 rollback
- Start new chat clears history, slots, model, category, Unity gate
- FACR prove asks refrigerant pressures first so a five-turn path can authorize rooftop R&R
- Known-good tags: none

### v4.19.38 — 2026-10-10 13:35 PT — Direct commit on main (rollback; no PR) — main SHA `110c4b8ec40adbe2417d2a7674f09d064dcb9aad`
- **REVERT** of v4.19.37: content matches known-good-v4.19.36 (`d45710af`)
- Revert reason: **UNKNOWN** beyond commit text (“v4.19.37 is off this deploy”)
- Known-good tags: `known-good-v4.19.38`

### v4.19.39 — 2026-10-10 13:43 PT — PR #67 merged; also PR #69 `1a34c92` (bulk importer, same v4.19.39 header) — main SHA `d646e4071f8ed7254de78371d5e1e739b66e7ce1`
- Re-applies v4.19.37 fixes on the v4.19.38 rollback; Thetford 'Not checked yet' advances to next unasked check
- Pressures by turn 4 authorize FACR rooftop R&R on turn 5 once drain, pan, fan, freeze sensor are in
- PR #69: Manager bulk library importer (ZIP batches, brand/model/keyword metadata, brand/model filters for search/GD/Bay)
- Known-good tag `known-good-v4.19.39-importer` → `1a34c92` (PR #69 squash)
- Known-good tags: `known-good-v4.19.39`

### v4.19.40 — 2026-10-10 15:15 PT — PR #68 merged — main SHA `1dd8c6d6d94aee731a0ac25c8bd42313d5a80bc3`
- GD and Bay PDF walk a proved repair in short steps from the cited library page, with kit figure and yes/no check
- Leader NOT CLEARED on live Thetford pack (FIX-REPORT-LOG ~4:24 PM PT): Bay PDF flowchart-only; GD figure path broken
- Known-good tags: `known-good-v41940`

### v4.19.41 — 2026-10-10 17:10 PT — PR #72 merged (also PR #71 `f3f5e8f`; PR #73 `fdd2f05`; PR #70 closed unmerged) — main SHA `69d30e7e1a19d6c4f30fa8265e00fbf3be2f5d72`
- PR #72: library figures for every brand + crop backfill; figure PNGs in R2 (not DB); Thetford shop template + shop-sheet leak order; optional xAI step-photo read
- PR #71: delete finished bulk-import ZIPs from R2; cleanup button for leftovers
- PR #73 (`fdd2f05`): Level Up S20 stops repeating 177094; live Thetford/S13/S10/S01 fixes
- Known-good tags: `known-good-v41941-pre74`

### v4.19.42 — 2026-10-10 18:44 PT — PR #74 merged — main SHA `f25ec8a65d7fe648c98ad11b1a40ddbafec95101`
- Keep bulk import and page rendering inside a memory bound
- Known-good tags: `known-good-v41942`

### v4.19.43 — 2026-10-10 19:29 PT — Direct stamp commit on main (no PR) — main SHA `1c21ef06da92ada20043d9aa6dca983ce85ea2db`
- Sidebar stamp distinct from v4.19.42 (stamp follows PR #73 merge)
- PR #76 (brand/product-line figure gate, title “v4.19.43”) merged `cd26564` after this stamp; ships live as v4.19.44
- Known-good tags: none; other tags: `pre76-v41943`

### v4.19.44 — 2026-10-10 23:01 PT — PR #76 merged `cd26564` + stamp `f27d739` — main SHA `f27d739d9e1901b6dfaf1983e7e9780e8145320f`
- Gate How blocks and figures to case brand and product line; require brand, model, system before a figure/How block
- Keep Thetford on its kit crops and off the vacuum step
- Live gate crashed (AttributeError; v41944-gate) → reverted by v4.19.45
- Known-good tags: none

### v4.19.45 — 2026-10-10 23:20 PT — Direct commit on main (restore; no PR) — main SHA `800665c107b7d15044fcf6d239bd6738a2e02174`
- **REVERT** of v4.19.44 / PR #76: tree returned to `pre76-v41943`
- Revert reason (commit + hourly-nonstop 2026-10-10-2326): v4.19.44 called `fits_case` / `off_brand_figure` on a cached `library_figure_backfill` lacking those helpers → AttributeError crash
- v41945 quick check: no AttributeError; S20 T3–T5 still repeat 177094; Thetford still off-topic How blocks
- Known-good tags: none

### v4.19.46 — 2026-10-10 23:38 PT — PR #77 merged — main SHA `c473b7f40e3185dc2f6d24de73150126956c8d87`
- Reload every GD and Bay module and log its revision so a stale coach cannot repeat a step
- Reload the figure bank and skip a figure when its helper is missing; re-lands the #76 brand/product-line gate
- Known-good tags: none; other tags: `pre78-v41946`

### v4.19.47 — 2026-10-11 01:11 PT — PR #78 merged `2ca1c64` + stamp `b546299` — main SHA `b546299218d838a22429c875a982b4d04c688540`
- Keep Thetford figures on screen and walk the valve kit; Thetford fact sequence walks steps 1–14 (test)
- Step cursor and system gates
- Known-good tags: `known-good-v41947`

### v4.19.48 — 2026-10-11 02:41 PT — PR #79 merged `b02817d` + stamp `4dd6f68` — main SHA `4dd6f68678c5934568558359f2a40c2dfc3bf958`
- Carry the Thetford repair on the bay sheet; Thetford crops stay on cited steps
- Drop the S20 bleed clause; empty fields, figure gates, S01 and S13 leftovers
- Known-good tags: `known-good-v41948`

### v4.19.49 — 2026-10-11 04:20 PT — PR #80 merged `b30d23d` + stamp `cd04634` — main SHA `cd046349cebc6b52c9a90bf4ddd05bee20b5485f`
- Thetford figure captions stay with kit crops; no quote ending on “Fig.”
- Reported clear drain counts as an FACR prove; live gate stays on the confirmed repair (S01, S13, S04)
- Known-good tags: `known-good-v41949`

### v4.19.50 — 2026-10-11 05:40 PT — PR #81 merged `c92b93a` + stamp `e7b2bad` — main SHA `e7b2bad47a9812cab718052cb7c3595873436af7`
- Hold FACR rooftop R&R until refrigerant pressures are reported (S01)
- Thetford review fixes on leak test, captions, sheet layout
- Known-good tags: `known-good-v41950`

### v4.19.51 — 2026-10-11 07:13 PT — PR #82 merged `2f499e7` + PR #83 merged `7012b04` + stamp `b7325c1` — main SHA `b7325c190a87f6b0897119cb367cc0208ce4900f`
- PR #82: v4.19.50 cosmetics (leak period, kit caption, cited count) and S02 bypass re-ask; S20
- PR #83: S01 FACR08 proving checks and rooftop removal sheet
- Live gate WORSE (v41951-gate GATE-SUMMARY) → reverted by v4.19.52
- Known-good tags: none

### v4.19.52 — 2026-10-11 07:59 PT — Revert `1388291` + stamp `8acbcbf` (direct on main; no PR) — main SHA `8acbcbfbb9482b5775fb2600a52ef2040281afd6`
- **REVERT** of v4.19.51 (PRs #82, #83): tree restored to known-good-v41950 (`e7b2bad`)
- Revert reason (v41951-gate GATE-SUMMARY, verified): Thetford T2 show-me lost its page image and leaked “could not load…” / “will display… below” text; T3 Step 1 lost the GOOD vs BAD block
- Also: S01 Bay PDF 12 pages (v50: 2) with every cited figure as a text-only FIGURE line (1 image only)
- Known-good tags: `known-good-v41952`

### v4.19.53 — 2026-10-11 09:03 PT — PR #84 squash-merged — main SHA `0d0fe8b7d93313079f17c6522e4b4f8200dd9e7d`
- Shared step format for every Bay PDF step and GD reply: heading, Where, Tools, Do this, Good looks like, Next; canned photo/yes-no script removed from PDF
- Thetford show-me kept; per-document figure backfill selector limited to CCD-0008666, CCD-0007990, Thetford Style II docs
- Each HOW line one action, every step names good and bad; FACR sheet no longer capped at three pages
- Live gate WORSE at Thetford (v41953-gate GATE-SUMMARY) → reverted by v4.19.54
- Known-good tags: none

### v4.19.54 — 2026-10-11 09:22 PT — Revert `1011ef4` + stamp `fb713fc` (direct on main; no PR) — main SHA `fb713fc9d22ff9a6a38c01b74c212c7f47f41bdc`
- **REVERT** of v4.19.53 (PR #84): tree restored to known-good-v41952 (`8acbcbf`)
- Revert reason (v41953-gate GATE-SUMMARY, verified): Thetford Step 12 had two actions in one HOW (“Grab the front of the pedal. / Pull the pedal up and off.”); T2 showed 42088 p7 instead of cited p3; every Bad line generic (“It does not look right.”); stray “2.” on Step 1 Do this
- Gate stopped at Thetford; S01–S15, S20 not run on v4.19.53
- Open (do not touch): PR #75 (Coleman 2111-0001 eight-field), PR #85 (v4.19.55 draft)
- Known-good tags: none

### v4.19.55 — 2026-10-11 12:50 PT — PR #85 squash-merged — main SHA `3cc517644d20f3a0eed19f83f2f16aac8252708c`
- Guided Diagnostics is a conversational product-specialist chat: plain sentences, no Where / Do this / Good / Bad / Next block and no "Step X of N" counter; manual figures only when the tech asks; a photo is asked only when the check is something the tech can see
- Bay PDF keeps the diagnosis flowchart, then one branch per repair (Thetford 42070: supply connection, vacuum breaker 34123/34122, water valve 42109, flange seal 02125), each with Before you start (safety note once), numbered Removal and Installation, and a verify step with pass/fail
- Each Bay figure sits centered under the step that cites it at 75% of the page width
- Thetford fixes 1-5: one action per HOW line, cited-page image (42088 p3), specific or omitted Bad line, no stray "2.", per-document backfill counts
- Established profiles in docs/profiles (GD v1.2, PDF v1.4, PDF-PAST-FAILS, PROFILE-CHANGE-LOG) plus scripts/profile_check.py, which grades scorecards and PF-01–PF-33 with PASS / FAIL / MANUAL; Thetford 42070 and S01 pass every automatable check
- Status: live gate WORSE (v41955-gate) → reverted by v4.19.56. Pre-merge tests: 747 passed, 1 env-caused failure (test_gd_nav_and_send two_sends; passes with XAI_API_KEY/GROQ_API_KEY unset; also fails on main)
- Known-good tags: none (`known-good-v41954` → `a76c68f` is the pre-merge rollback point)

### v4.19.56 — 2026-10-11 — Revert `0d57348` (direct on main; no PR) — main SHA `0d57348943618bf65ba1c6c048ab6985344b448b`
- **REVERT** of v4.19.55 (PR #85, `3cc5176`): shop code restored to known-good-v41954 (`a76c68f`). CHANGELOG.md and docs/profiles stay as they were on main
- Revert reason (v41955-gate, live library path): Thetford GD show-me leaked a template block and a page-7 caption on a page-3 cite. The Bay PDF printed 2 of 4 flowchart branches, a vacuum-breaker branch with no Installation, garbled "Put the vot.", towel-only tools, Bad lines that only negate Good, a glued "Flush 3 times. dry", off-case Do Not lines, and 4 figure cites with 1 image. profile_check scored that PDF 5/10 with an automatic FAIL
- Version stamp v4.19.56 so this deploy is distinct from v4.19.55
- Known-good tags: `known-good-v41954` → `a76c68f`

### v4.19.57 — 2026-10-11 — draft, live Thetford library path
- The figure-attach path no longer replaces the four Thetford repair branches. Supply, vacuum breaker 34123/34122, water valve 42109, and the flange seal each keep Removal, Installation, and a confirm step
- A Guided Diagnostics show-me names the supply connection at the back of the toilet and does not paste the How template. A figure caption follows the cited page (42088 page 3), not page 7 / Step 1
- Valve tools come from the kit Needed list. A Bad line names a real failure or stays off. The flush check no longer glues "Flush 3 times. dry". The Do Not list drops the winterizing antifreeze and ice lines
- Proof is the live retrieval shape: tests/fixtures/thetford_live_retrieval.json (900/120 windows from 42088, 42109, and 34123/34122). Live R2 was not reachable. 42110 and the Thetford parts list have no local PDF
- Bay tab copy describes repair branches. Version stamp v4.19.57
- Headless pre-merge check, from the repo root: `python3 scripts/thetford_live_gate.py --db PATH --cache DIR --out DIR`. It reads the shop database read-only, loads figure PNGs from the R2 cache, writes the Thetford Bay PDF, and plays Guided Diagnostics turns T1-T4 including "Show me where that connection is". `--live-llm` runs those turns through grok-4.6 (`XAI_API_KEY`) before the shop guards. The report includes both scorecards, and the PDF is rendered at 90 dpi. The committed stand-in library is `tests/fixtures/thetford_live_library/`; what it lacks versus live is in `FIXTURE-GAPS.md`
- The scored sheet is the ranked 12 chunks, English columns stitched and cut at 4000 characters. It does not read the full kit PDF. 42110 and the Thetford parts list are absent from the fixture
- A vacuum-breaker reply names kit 34123, a bad result, and a question, and the page in the sentence matches the source line. A copied turn fails. HTML comments, including `gd-step`, are stripped from the reply
- Supply and flange are real removal and installation steps. Tools are named on the step that uses them, or once in Before you start. Before you start stays on the leak. Fig. 1 PEDAL REMOVED sits on the pedal-off step. Fig. 3 keeps the full caption. The water-valve YES label sits on the left-going arrow
- The vacuum-breaker branch takes the bolt covers and nuts off before the toilet is lifted, and puts the covers back after the nuts are tight. The flange branch lifts the toilet, pulls the old seal, covers the hole, and checks the 7/16 inch height during Removal. A water-valve source quote comes from that kit and stays on the sheet. Fig. 3 is the drawing, with the caption in type under it. The first valve reply names the place and the tools. `--live-llm` writes transcript-raw.txt and how many turns the guards rewrote
- The live model prompt leads with the 42088 troubleshooting order, then the current step's tool, place, safety line, and the facts the tech already reported. It addresses the tech as you. A complete raw reply is kept; the shop line is the backstop. `--live-llm` exits non-zero when the raw reply fails. Source quotes are verbatim sentences from each document. The flange branch pulls the water hose off before the lift, pushes it back on after, and covers the holding tank opening at the closet flange
- A guard does not replace a passing vacuum-breaker reply, and it does not say the Thetford manual is missing once 42088, 34123, 34122, or 42109 is already cited. `--live-llm` exits 1 only on a real FAIL. A MANUAL scorecard line does not fail the exit. After a weep at the pedal, the next reply starts the 42109 replacement. A flush-and-watch check does not name pliers. Each reply labels a good result and a bad result and says what to report back. The vacuum-breaker and water-valve branches say holding tank opening at the closet flange. The flange height step's next line is the uncover step, and that step's good line says the opening is clear
- A reply is not a library miss when it cites a retrieved document for this case, by title, brand, or document number. That check is not a Thetford number list. An observation-only flush-and-watch names no wrench, pliers, or screwdriver. Figures attach only when the tech asked. The water-valve reply walks kit 42109: water off, the toilet off the bolts, then the rest one step at a time, with the Bay PDF for the full list. The report-back line is "Tell me what you see." The supply good line says dry. A PF result other than PASS, FAIL, or MANUAL fails the exit. The kit uncover step says "Uncover the holding tank opening at the closet flange."
- An observation-only reply is complete with where, what to look for, a good result, a bad result, and a report-back. It does not need a tool word, so a correct flush-and-watch is not replaced by the scripted card. That card ends with "Tell me what you see." and does not ask for a photo. The live report names the guard that fired on each turn. A show-me adds location detail the previous turn did not give (which side, what it connects to, what it looks like) and names a figure only when one exists. The water-valve turn says "Turn the RV water off" once, uses a 1/2-inch wrench on the bolts, and the result matches that bolt step.
- The no-model water-valve card says "Turn off the water to the RV." once, names a 1/2-inch wrench and not pliers, and ends "Tell me what you see." A show-me uses the 42088 words (back of the toilet, water supply line connection at the water valve) and does not invent a side or a shape. The closet bolts are at the floor, on the closet flange. A reply does not name Figure N unless that figure is attached.
- A show-me attaches the cited page image when one is stored and points at it in the manual's words. When the page has no image, it says the manual has no picture, restates the location once, and may ask for a photo. That show-me is exempt from the near-duplicate check only in those two cases. The supply good result stays dry.
- A show-me answers where the part is. It does not name a tool and it does not repeat the previous turn's good or bad result. It ends with "Then do that check and tell me what you see." The water-valve action is "Take the toilet off the closet bolts."
