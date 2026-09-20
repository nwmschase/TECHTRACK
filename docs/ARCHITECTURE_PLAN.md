# TechTrack architecture plan (research, not a rewrite)

**For:** Chase’s Leader Bot — synthesize and decide.  
**Repo inspected:** `nwmschase/TECHTRACK` at `957bc50` (`rv_techtrack.py` v4.10.1, ~4808 lines).  
**Scope of this PR:** written plan only. Do **not** treat this as permission to rewrite the app.

This document is grounded in the current code. Hypotheses in the research brief are **verified or discarded** in §2.

---

## 1. Leader Bot one-pager

**Unique bet (keep):** shop-owned RAG over real OEM PDFs + a **hard** flowchart that waits for the tech + a warranty write-up with page citations. Not ServiceNomad. Not ALLDATA.

**Recommended posture (do this, not a factory rewrite):**

| Decision | Recommendation | Why |
|---|---|---|
| Host / UI | **Keep Streamlit** on Streamlit Cloud | iPad already works; 7 tabs + cookie + CSS already paid for; a front/API split is a rewrite |
| Procedure trees | **JSON files in git** (`procedures/*.json`), generic engine | Adding Lippert / Atwood / Schwintek as more Python dicts + node-id `if`s will become spaghetti |
| Persistence | **Keep SQLite + R2 backup**; harden it | Wipe pain is real, but the app already restores from R2. Do not buy a database yet |
| LLM | **Forbidden to pick the next gate when a tree matches.** Allowed: plate read, warranty prose, excerpt-bound coach **only** when no tree | Matches the unique bet. Current Jobs tab still dumps a full LLM plan — that is the main contradiction |
| Next work | **3 extract-and-scale milestones** | Engine + Furrion JSON + golden WO tests → second shop-mainstay tree → third tree + wipe/catalog harden |

**Do not build:** embeddings, Workers/FastAPI rewrite, auto-generated trees from PDFs, field-case memory, shop management, more certificate/safety product surface.

---

## 2. Brief vs repo — keep / correct / discard

| Brief hypothesis | Verdict | What the code actually does |
|---|---|---|
| Monolithic Streamlit app, main file `rv_techtrack.py` | **Keep** | Single 4808-line module. No `procedures/`, no tests, no package split. Supporting files: `requirements.txt`, `DEPLOY.txt`, `AUTH_COOKIE.txt`, `assets/tacoma-rv-logo.png`, `.devcontainer` |
| SQLite for users/jobs/metadata; wipe risk on Streamlit Cloud | **Keep the risk; discard “no mitigation”** | Local file `rv_techtrack_v4.db`. **Already** auto-backups to R2 `backups/rv_techtrack_v4.db` (+ `.prev.db`), restores on boot if local library looks empty (`maybe_restore_db_from_r2` / `maybe_backup_db_to_r2`). Catalog JSON export exists. Pain is residual race/threshold, not “nothing is saved” |
| R2 for PDFs | **Keep** | `boto3` S3 client; keys under `documents/`, `certificates/`, `safety/`, `backups/` |
| Groq `openai/gpt-oss-120b` is the coach | **Correct as fallback only** | `ai_chat()` **prefers xAI Grok** (`XAI_API_KEY`, default `grok-4.6`) then Groq. Plate vision: xAI, then Groq `GROQ_VISION_MODEL` or `meta-llama/llama-4-scout-17b-16e-instruct` |
| Hard Furrion fridge procedure tree | **Keep** | `PROCEDURE_FURRION_FCR_CCD_0008122` (~330 lines of Python dict). `PROCEDURE_TREES` has **one** entry. Engine: `engine_turn` → `advance_flow` only via edges |
| Page/figure pipeline | **Keep** | Cite parse → resolve Document/page → R2 download → `pymupdf` PNG. Chat shows pages **only on request**; Jobs tab has a source-page expander |
| Warranty story writer | **Keep** | `improve_tech_story` / `ask_chat_to_warranty_story` / `story_from_diagnostic_job`. Hard rules: tech-reported facts only, PASS-BIND, source cite, open vs complete |
| Data-plate photo fills brand/model | **Keep** | `read_data_plate_from_image` + `apply_plate_read_to_model_key` on both Jobs and Guided Diagnostics |
| Validation = recreate real WOs from complaint | **Keep as the method; not implemented as tests** | No `tests/` in repo. Engine is designed for this (complaint → start node → tech results → next node) |
| App is “just” Library + GD + warranty | **Discard** | Also: login/roles, certificates, safety meetings + acknowledgements, team overview, manager CRUD, R2 re-link. Adjacent to ServiceNomad, not the unique bet |

**Extra facts the brief did not name (material):**

- **Two coaches, not one.** `Diagnostic Jobs` calls `run_guided_diagnostics()` and stores a **full LLM plan**. `Guided Diagnostics` chat uses the hard tree (or excerpt-bound LLM if no tree) **one gate per turn**. The Jobs path contradicts “one next test then wait.”
- **Flow state is RAM-only.** `st.session_state["ask_flow"]` is not written to `AskChat`. Opening a saved chat **clears** `ask_flow` (line ~4097).
- **WO context is not pinned into chat.** Jobs and Guided Diagnostics have separate category/model widgets. Plate fill writes a Streamlit key, not a shared job object.
- **Matcher is Furrion-hardcoded.** The tree already has `models` / `categories`, but `find_matching_procedure()` only special-cases FCR / CCD-0008122. `select_start_node_id()` and much of `map_tech_text_to_answer()` name Furrion node ids (`is_operating_diamond`, `fuse_front_vent`, …).
- **“RAG” is keyword scoring, not embeddings.** `DocChunk` rows from `pypdf` text. Scanned PDFs stay unindexed (`index_note`: “No extractable text”). Brand lock + index-chart row expansion are already good.
- **Prompt spaghetti already exists** beside the hard tree: `FURNACE_OEM_ORDER`, `FRIDGE_OEM_ORDER`, `UNITY_OEM_ORDER`, `DIAG_LED_HONESTY` injected into both the Jobs planner and the no-tree chat.
- Version drift: file header is **v4.10.1**; sidebar caption still says **v4.10.0**.
- Seed users `manager` / `alex` / `jordan` with default passwords if the DB is empty after a wipe.

---

## 3. Current architecture (as built)

```
iPad Safari/Chrome
        │
        ▼
Streamlit Cloud  ── rv_techtrack.py (UI + engine + prompts + models)
        │
        ├── local SQLite  rv_techtrack_v4.db
        │      users, categories, documents, doc_chunks,
        │      diagnostic_jobs, ask_chats / ask_messages,
        │      certificates, safety_*
        │
        ├── Cloudflare R2
        │      PDFs (source of truth for files)
        │      SQLite snapshots (backups/…)
        │
        └── LLM
               xAI Grok preferred
               Groq gpt-oss-120b fallback
               vision: plate OCR only
```

### 3.1 What each tab is for

| Tab | Role vs unique bet |
|---|---|
| Document Library | **Core.** Browse/download R2 PDFs by category. Search is title/keyword, not chunk RAG |
| Guided Diagnostics | **Core.** Chat + hard tree + on-demand page render + warranty from chat |
| Diagnostic Jobs (WO) | **Core-ish, split-brained.** Pins WO #, category, model, concern. Builds a **full plan**, manual step log, story. Does **not** run `engine_turn` |
| Dashboard / Safety / Team / Manager | **Keep as-is, freeze growth.** Useful shop hygiene. Not the product bet |

### 3.2 Diagnostic data path (today)

1. Manager uploads PDF → R2 `documents/…` → `Document` row → `index_document_from_bytes` → `DocChunk` (page + ~900-char slices).
2. Search: `search_manual_chunks` token overlap + model prefixes (`FCR10DCGTA` → `fcr10…`) + brand lock (`SHOP_BRANDS`) + optional TSB / Electrical / Reference cross-search + index-chart page expansion.
3. **If hard tree matches** (Furrion FCR only): `guided_diagnostics_reply` → `engine_turn`. Prompt text is **verbatim from the node**. LLM is not called. Unmapped tech text **re-asks**; it does not invent a gate.
4. **If no tree:** `ask_techtrack_reply` + `ASK_FLOWCHART_PAGE_LOCK` + OEM-order prompt blobs. LLM may still hallucinate; prompts try to stop it.
5. Warranty: tech lines + silent `ask_cited_log` → `improve_tech_story`. Coach suggestions are labeled “not performed.”

This is already the right *shape*. The scale problem is **where trees and start/answer rules live** (Python, one file, Furrion-specific).

---

## 4. Answers the brief asked for

### 4.1 Keep Streamlit vs split front / API?

**Decision: keep Streamlit. Do not split for iPad + free hosting.**

Reasons that are about *this* shop, not generic taste:

1. The last ~15 versions (cookie, collapsed sidebar, 100% width, Yes/No buttons without writing `ask_input` after the widget) are Streamlit-tax already paid. A React/Workers rewrite throws that away.
2. Free hosting today is **Streamlit Cloud + R2 + xAI/Groq**. A real API needs another always-on host or a Cloudflare Workers rewrite of login, cookies, file upload, PDF render, and seven tabs.
3. iPad Safari is a **rerun-and-big-buttons** UI. Streamlit is ugly-but-adequate. The unique bet is flowchart honesty, not a design system.
4. Concurrency is one shop, a handful of techs, one Cloud replica. Not a multi-tenant SaaS.

**Extract modules later, still imported by Streamlit.** That is not a front/API split:

```
rv_techtrack.py          # stay the Streamlit UI for now
procedures/engine.py     # engine_turn, advance_flow, generic matcher
procedures/*.json        # trees
```

**Revisit a split only if** Streamlit Cloud wipe/restore keeps losing live jobs *after* the harden in §4.3, or widget/rerun bugs block Yes/No gates on iPad again. Preferred later host if that happens: Cloudflare Worker + D1 + same R2 bucket — still not a shop-management rewrite.

### 4.2 How should procedure trees be stored?

**Decision: versioned JSON in the git repo (`procedures/`). Not more Python. Not SQLite. Not “the LLM reads the PDF and builds a tree.”**

| Option | Verdict | Why |
|---|---|---|
| More dicts in `rv_techtrack.py` | **No** | Furrion tree is already ~330 lines. Start-node + answer mapping is already Furrion-id spaghetti. Lippert + Atwood + Schwintek will not fit |
| SQLite / manager UI “tree editor” | **Not yet** | Trees are OEM-critical. They need PR review. SQLite also dies on wipe. Editor is a product we should not build |
| YAML | Fine, slightly worse than JSON | JSON is enough; no extra parser |
| **JSON files + tiny schema + generic engine** | **Yes** | Git-diffable, survives Streamlit disk wipe (code is redeployed), one engine for every brand |
| LLM-extracted trees from the PDF | **Forbidden** | Violates “never invent OEM steps.” Humans encode diamonds from the SM; the engine only walks edges |

The Furrion dict is already 90% of the target schema (`id`, `title`, `models`, `categories`, `nodes` with `type`, `prompt`, `source_title`, `source_page`, `edges`). What is **missing from the data** and therefore hardcoded in Python:

- Entry rules (no-power → fuse; fuse-replaced + not-cooling → dial; 2-flash → fan-fault volts)
- Answer aliases per node (yes/no/pass/fail/blown/replaced…)
- Reading rules (`≥10.5 V`, `12–15 V`, `<3 A`)
- Generic model/category match (fields exist, matcher ignores the registry)

**Target tree file (illustrative — Furrion today, same shape for the next brands):**

```json
{
  "id": "furrion_fcr_ccd_0008122",
  "title": "Furrion FCR08/FCR10 SM CCD-0008122",
  "models": ["fcr08", "fcr10", "fcr10dcgta", "ccd-0008122"],
  "categories": ["refrigerat", "fridge"],
  "source_manual_title": "Furrion FCR08/FCR10 SM CCD-0008122",
  "entry_rules": [
    {"if_any": ["2 flash", "fan fault"], "start": "fan_fault_f_terminal_volts"},
    {"if_all_groups": [["fuse replaced", "replaced fuse"], ["not cooling", "no cool"]], "start": "dial_on_4_5"},
    {"if_any": ["no power", "dead", "won't turn on"], "start": "fuse_front_vent"},
    {"if_any": ["not cooling", "not cold"], "start": "dial_on_4_5"},
    {"default": "fuse_front_vent"}
  ],
  "nodes": {
    "battery_under_load": {
      "id": "battery_under_load",
      "type": "reading",
      "prompt": "Per General Troubleshooting: check battery voltage for 10.5V under load…",
      "source_page": 12,
      "reading": {"unit": "V", "pass_min": 10.5, "pass": "yes", "fail": "no"},
      "aliases": {"yes": ["pass", "ok", "10.5", "11v"], "no": ["fail", "low", "9v"]},
      "edges": {"yes": "paper_test", "pass": "paper_test", "no": "external_power_issue", "fail": "external_power_issue"}
    }
  }
}
```

**Engine contract (already true in v4.10.0 — keep it):**

- TECH reports. Tree edges decide. Unmapped → re-ask current gate. Never invent the next test.
- `format_gate_reply` prints `node.prompt` + `📖 Source: {title} - page {N}`.
- `engine_turn` is brand-agnostic once match / start / aliases live on the JSON.

**Who writes a new tree:** a human (Chase / a tech / Leader Bot) with the SM open. Encode one symptom path first (the WO that actually hits the shop), not the whole book. Cite page numbers from the **shop library title**, not a guessed filename.

**First three shop-mainstay candidates** (Leader Bot should pick by real WO volume, not this list’s order):

1. Furrion FCR CCD-0008122 — **already encoded** (extract, don’t rewrite).
2. Furnace (Atwood / Dometic / Suburban sail-switch path) — today only a **prompt** (`FURNACE_OEM_ORDER`). Highest “spaghetti risk” if left as more prompt text.
3. Lippert Schwintek / in-wall slide, **or** Lippert Unity / OneControl money-test — Unity is also prompt-only today (`UNITY_OEM_ORDER`). Pick whichever Tacoma writes more claims on.

### 4.3 How to stop SQLite wipe pain without paid infra?

**Decision: do not buy Postgres. Harden the R2 snapshot you already have. Optionally add a second R2 JSON sidecar.**

What already works:

- Restore if local `Document` count `< MIN_DOCS_TO_BACKUP` (10) and R2 object looks like a real SQLite file (`SQLite format 3`, ≥50 KB).
- Backup refuses to overwrite a good cloud copy when the local library is tiny.
- Previous snapshot rotated to `backups/rv_techtrack_v4.prev.db`.
- Manager can download `.db` and `library_catalog.json`.
- Re-link + re-index from R2 if metadata dies but PDFs live.

Residual failure modes (these are the real wipe pain):

| Failure | Why it still hurts |
|---|---|
| Shop has **< 10 manuals** | Restore never runs; backup never uploads. Empty seed users appear |
| Wipe **between** debounce (90s) and next request | Last minutes of WO notes / chat / `ask_flow` (already RAM-only) vanish |
| Restore races two replicas / a half-written file | Unlikely on Streamlit Cloud (one container) but the code is not WAL-aware across machines |
| Chunks live only in SQLite | After restore you may still need **Re-index All PDFs** (manager tool exists) |
| Opening a saved chat drops the flowchart | Product bug, not wipe — feels like “lost the job” |

**Harden (still free, still R2):**

1. **Drop or special-case `MIN_DOCS_TO_BACKUP`.** Backup if *any* of: ≥N docs, ≥1 user beyond seed, ≥1 `DiagnosticJob`, or manager “Save to cloud now.” Restore if local docs == 0 **or** local users look like fresh seed and R2 has a larger library.
2. **Write a second object** `backups/library_catalog.json` on every successful DB snapshot (you already have `export_library_catalog()`). Titles/keywords/R2 keys survive even if the `.db` blob is unreadable.
3. **Persist `ask_flow` + cited ledger on `AskChat`** (new JSON columns, schema upgrade pattern already exists). Same for a `flow_json` on `DiagnosticJob` when chat and WO are linked. Then a wipe+restore actually resumes the diamond.
4. Keep PDFs on R2 as the file source of truth. Never “fix wipe” by copying manuals onto Streamlit’s disk.
5. **Do not** introduce embeddings or a second database “for durability.”

**Paid / new host only if** two consecutive shop weeks still lose open WOs after (1)–(3). Then Turso/libSQL or Cloudflare D1 is a *remote SQLite*, not a schema redesign.

### 4.4 Where the LLM is allowed vs forbidden

Lock this. Prompts are not a lock; **control flow** is.

```
tech message
     |
     v
tree match on category + model?
     |
     |-- yes -> HARD ENGINE ONLY
     |          next prompt = node.prompt
     |          next node   = edges[answer]
     |          LLM is not called
     |
     `-- no  -> EXCERPT COACH (LLM)
                1 gate, must cite Source
                excerpts only; else "not in library"
                no invented page / LED / pin
```

| Situation | LLM? | Allowed to do | Forbidden |
|---|---|---|---|
| Hard tree matched | **No** | — | Next test, voltages, “also check…”, skip-ahead |
| Map “12.2 V” / “paper didn’t move” to an edge | **No** (keep regex / reading rules on the node) | — | Interpreting a reading into a *new* test |
| No tree, excerpts found | **Yes, tightly** | Rephrase the **cited** next diamond; ask for that result | Adjacent pages, other brands, flash LEDs not in excerpt, full 10-step dump |
| No tree, no excerpts | **Yes, but almost silent** | Ask category/model/symptom; say library miss | Any OEM procedure or page number |
| Warranty story | **Yes** | Grammar, CONCERN/TESTING/CAUSE/CORRECTION, PASS-BIND to last cited gate, copy 📖 Source from ledger | Invented readings, invented repair, citing unread pages |
| Data plate photo | **Yes (vision)** | Brand + model tokens into the pinned field | Using the plate shot as a diagnostic image / inventing a model family |
| Jobs “Build Test Plan” | **Today: yes, full dump. Target: no if a tree matches** | If no tree: same excerpt-coach rules, labeled “preview, not live coaching” | Presenting the dump as the live gate |

**Jobs tab vs unique bet:** Leader Bot should treat `run_guided_diagnostics()` as **documentation preview**, not the coach. Live coaching is Guided Diagnostics + hard tree. Milestone 1 can leave the planner in place; Milestone 3 should stop using it as the primary path when a tree exists (show the first gate + WO pin instead).

### 4.5 Minimal next 2–3 milestones (no rewrite factory)

Each milestone is a **thin extract or one new JSON tree**, plus a golden WO test. Not a platform.

#### Milestone 1 — Make the Furrion engine scalable (extract, don’t rewrite)

**Outcome:** same Furrion behavior on iPad; trees are data; adding brand #2 does not require editing `map_tech_text_to_answer`.

Work:

1. Move `PROCEDURE_FURRION_FCR_CCD_0008122` → `procedures/furrion_fcr_ccd_0008122.json` with entry rules + reading/aliases on nodes.
2. Move `engine_turn` / `advance_flow` / generic match / generic answer map → `procedures/engine.py`. `rv_techtrack.py` imports it.
3. Persist `ask_flow` (and cited ledger) on `AskChat`. Opening a chat resumes the diamond.
4. **Pin session context:** category + model + optional WO # stay sticky for the chat; plate fill writes that pin. Optional: “Send this WO to Guided Diagnostics” copies Job fields (do not merge the two tabs yet).
5. Add `tests/gd_golden/furrion_fcr_not_cooling.json` — complaint-only start node + a recorded Tacoma WO path (fuse → … → real fix). Run with `pytest` (no Streamlit). This **is** the shop validation method, automated.

**Out of scope:** new brands, Workers, embeddings, touching certificates/safety, rewriting Jobs UI.

#### Milestone 2 — Second shop-mainstay tree (data only)

**Outcome:** one more JSON file + golden WO. Engine unchanged.

Leader Bot picks **one** from real claim volume:

- Atwood / Dometic furnace (thermostat bypass → sail IN/OUT) — currently prompt-only, high hallucination risk.
- Lippert Schwintek / in-wall (hall sensor / motor / sync) — already named in UI placeholders.
- Lippert Unity money-test (BAT1/BAT2 → reversing output) — currently prompt-only.

Rule: encode **one symptom path** from the shop SM pages (same style as Furrion paper-test → operating diamond). Do not encode the whole manual. Do not add another `*_OEM_ORDER` string.

#### Milestone 3 — Third tree + wipe harden + stop the full-plan contradiction

**Outcome:** three mainstay trees; DB snapshot + catalog sidecar reliable; Jobs does not pretend a 12-step LLM dump is the coach when a tree exists.

1. Third JSON tree (the leftover from Milestone 2’s list).
2. Wipe harden from §4.3 (backup thresholds, `library_catalog.json` on R2, restore vs seed).
3. If a tree matches a new Job: store first gate + `flow_json` on the WO; chat and job share that pin. Keep `run_guided_diagnostics` only as a fallback preview when no tree matches.
4. Freeze certificate / safety / team feature work.

After Milestone 3, **stop**. Field-case layer, OCR for scans, and any host split are later decisions.

### 4.6 Risks / what NOT to build

**Product (abandon the bet if you build these):**

- Shop management (schedule, clock, parts, customer CRM). ServiceNomad exists.
- ALLDATA-scale coverage (every OEM, every model year).
- Field-case / “what we saw last time” memory. Manuals first.
- Auto-tree from PDF via LLM. That *is* inventing OEM steps.
- Chat that dumps the whole diagnostic chart (Jobs planner already drifts this way).

**Tech (cost / wipe / iPad):**

- Vector DB / embeddings on free tier. Keyword + index-row expansion is enough until a tree exists; trees beat retrieval.
- Front/API rewrite, Cloudflare Workers app, or “Streamlit is not real software.”
- Moving manuals onto Streamlit disk, or a second file store besides R2.
- OCR factory for every scanned PDF (say “not indexed” and ask for a text SM; optional later manager tool).
- In-app visual flowchart editor.
- Growing certificates / safety into an LMS.

**Integrity risks already in the file (do not make worse):**

- Seed default passwords after wipe.
- LLM Jobs planner can still invent steps when no tree matches — treat as untrusted.
- Brand-lock failure → wrong-manual voltages. Keep `SHOP_BRANDS` + refuse-other-brand behavior.
- `ASK_TECHTRACK_SYSTEM` rule 20/21 numbering is already tangled; don’t add more mega-prompts — add trees.

---

## 5. Success / validation (how Leader Bot knows a milestone worked)

The shop method in the brief is the right one. Encode it:

> Recreate a **real Tacoma WO from the complaint only**. Guided Diagnostics must land on the **same first gate** the SM uses, wait, then reach the **same fix** the tech actually performed — without extra invented tests.

Per tree, keep a golden file:

```json
{
  "wo": "anonymized-4521",
  "category": "Refrigerators",
  "model": "Furrion FCR10DCGTA",
  "complaint": "Customer states fridge not cooling. Light works.",
  "expect_start": "dial_on_4_5",
  "turns": [
    {"tech": "yes dial on 5", "expect_node": "battery_under_load"},
    {"tech": "12.4V under load", "expect_node": "paper_test"}
  ],
  "expect_end": "replace_thermostat"
}
```

If the engine skips a diamond or invents F+/F− volts after the paper test, the milestone **fails** (that exact bug is why the Furrion tree exists).

Human check on iPad: one gate on screen, Pass/Fail buttons on binary nodes, 📖 Source visible, Write warranty story cites those pages and no others.

---

## 6. Decisions for Leader Bot (please choose)

These are the only forks that change the next PR. Everything else above is recommended default.

1. **Milestone 2 brand:** furnace sail path vs Schwintek vs Unity? (Need WO volume, not preference.)
2. **Jobs tab:** keep the LLM full plan as a labeled preview through Milestone 2, or hide it as soon as Milestone 1 ships for tree-matched models?
3. **Host:** confirm **stay on Streamlit Cloud** unless wipe still loses WOs after Milestone 3 harden.
4. **Discard any remaining brief assumption** if shop reality differs (e.g. Groq-only keys, no xAI; or library already >10 docs so `MIN_DOCS` is fine).

---

## 7. File map (for the next implementer)

Do not rewrite these. Touch only what a milestone names.

| Region in `rv_techtrack.py` | Lines (approx.) | Role |
|---|---|---|
| Header / CSS / `st.set_page_config` | 1–240 | iPad layout — leave alone |
| R2 helpers | 251–376 | File + catalog |
| SQLAlchemy models | 378–505 | Add JSON columns later; don’t replace |
| R2 DB backup/restore | 553–642 | Harden in M3 |
| `ai_chat` / plate / `improve_tech_story` | 816–1150 | LLM policy |
| Index + `search_manual_chunks` | 1151–1642 | Keep; not embeddings |
| Page/figure pipeline | 1645–2164 | Keep |
| `run_guided_diagnostics` | 2167–2320 | Demote in M3 |
| OEM prompt blobs | 2324–2435 | Do not grow; replace with trees |
| **Hard engine + Furrion dict** | **2437–3303** | **Extract in M1** |
| Ask / story / seed | 3306–3558 | Persist flow in M1 |
| Streamlit tabs | 3560–4808 | Pin context; don’t restyle |

---

*Plan only. No application rewrite in this PR. Wrong assumptions above should be discarded after shop confirmation.*
