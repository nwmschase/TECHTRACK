### RCA: Manual selector accepts weak or tied evidence as a confident pick (v4.19.65 root fix)
Format: docs/standards/ROOT-CAUSE-ANALYSIS-STANDARD.md. Branch cursor/selector-root-fix. Leader GO 2026-10-16 4:02 PM PDT; B13 added 4:04 PM.

1. **Problem statement.** The selector picked or missed manuals on weak evidence. Examples:
   - RC30 "Furrion FCR08DCGTA 12V DC refrigerator" pinned a 12V vent fan (fixed in v4.19.64).
   - B13 "Suburban SW6DE" (Water Heaters) found no manual, though doc 124 "Suburban Water Heater Master Service and Training Manual" has SW6DE in its page text and SW6 in its keywords.
   - On v4.19.64, 15 sweep picks were decided by read order between DIFFERENT manuals, and 9 cross-category picks were the wrong product type (GSWH-2 queried under Refrigerators pinned the water-heater manual).
   - Expected: the most specific manual, or no pick + the official web lookup, or a question to the tech when the unit type is unknown.
2. **IS / IS-NOT.**
   - IS:
     - A rating sitting next to a model ("12V", "50Ah", "13500 BTU" with a space).
     - A model whose series has one digit (SW6DE -> SW6).
     - A model present only in keywords or page text (doc 124 has no models field).
     - Two different manuals carrying the same model (Power Gear 140-1224 / 140-1226 / 140-1146, Lippert PSX2).
     - A model typed under the wrong category (GSWH-2 under Refrigerators).
     - An unbranded toilet job (Thetford was assumed).
     - A category that maps to no type (Electrical, slugged categories), which skipped the type gate.
   - IS-NOT:
     - A model in exactly one manual's models field: RC17 GSWH-2 under Water Heaters, MaxxFan 11F90000K, Dometic B57915. These picked correctly before and after.
     - Duplicate uploads of one manual (186/298, 208/328): harmless before and after.
   - Difference: in the failures the deciding evidence was non-identifying (a rating), unread (a field the matcher never read), or equal between different manuals, and the code fell back to read order or passed the type gate by default. One distinctive token in exactly one doc leaves nothing weak to decide.
3. **Timeline (PDT).**
   - Earlier patches, each for its own case:
     - Girard fridge-for-water-heater.
     - Thetford guard: `bay_brand_retrieval` turned a toilet job with no brand into Thetford, and `is_thetford_flush_leak_context` matched any plumbing/toilet job.
     - Coleman page rank (`_rank_coleman_pages`, keyed on part numbers).
     - MaxxFan p9 (`supplement_maxxfan_remote_pages`, doc 11F90000K page 9 hard-coded).
     - Unknown-brand borrowing.
   - 2026-10-16 ~3:20 PM: RC30 failed in Leader's sim.
   - 3:58 PM: v4.19.64 (dbd2cce) merged: exact model first + type/brand filters.
   - 4:00 PM: the self-graded RCA of v4.19.64 rejected it on standard section-6 items B/C/D.
   - 4:02 PM: Leader GO for the root fix.
   - 4:04 PM: B13 reported as a new incident of the class (found in the shop B-case run, not by a test).
4. **Evidence (lines are origin/main b1e363d).**
   - `gd_official.model_tokens` l.110-122: the unit filter is a fullmatch on "number+unit" with no space, so "13500 BTU" keeps "13500"; there's no "ah" in the list, so `model_tokens("50Ah") -> ['50ah']`.
   - `model_keys` l.262-272: the series regex `[a-z]{2,}\d{2,}` needs two digits, so `model_keys({'tokens':['sw6de']}) -> ['sw6de']` with no 'sw6'.
   - `model_hit_len` l.292-299: reads only title/models/doc_number/clean_title. Doc 124 has models=NULL, and keywords/page text are never read, so B13 gets 0 hits.
   - `select_manual` l.328-371: strict ">" keeps the first doc read on equal keys (exact key l.346; scored key (trouble, hits) l.362, where any hits>0 is enough).
   - `doc_eligible` l.302-316: when the unit has no type (category not in CATEGORY_TYPES), the type check is skipped.
   - `PRODUCT_TYPES` held "gswh" (a model name) in water_heater, so typing GSWH-2 added the water-heater type to any job.
   - `bay_procedure.bay_brand_retrieval`: `if toilet and not asked: asked = {"thetford"}`.
   - Sweep (scripts/selector_sweep.py, live library copy 2026-10-13): v4.19.64 = 15 ambiguous-tie picks and 9 cross-category wrong-type picks.
5. **Causal chain (fault tree).** Wrong or missed pick = (A OR A2 OR B) AND (C OR D) AND E.
   - A, tokenizer: ratings with a space, or Ah, become model tokens.
   - A2, series key: a one-digit series (SW6) is never derived.
   - B, evidence fields: keywords and page text are never read, so a doc with no models data can't be found by its model number.
   - C, matcher: no specificity ladder or threshold, so one weak hit picks, and a tie is broken by read order.
   - D, type gate: an unmapped category or a type-less unit skips the gate; a model name inside a type regex (gswh) adds a type.
   - E, compensating patches: brand/page/doc-keyed rankers and a default brand (Thetford) cover particular cases and hide the general defect.
   - Contributing condition G, library data: misfiled categories (309, 631, 629 and 14 more) make even a correct gate refuse the right doc. Fixed in the data layer by R1/R2.
   - Systemic root: **selection had no explicit, ordered notion of evidence strength, no rule for equal evidence, and no "type unknown" state**, so weak, unread or tied evidence was silently converted into a confident pick or a miss.
6. **Why existing checks missed it.**
   - Tests were per-incident fixtures with one right doc each. None had two different manuals with equal evidence, a model only in page text, a one-digit series, or a rating with a space.
   - v4.19.64's sweep measured only whether the pick carried the model, not tie-decided or cross-category picks.
   - No unit-token property test existed.
7. **Class of failure.** Weak-evidence document match accepted as confident and suppressing fallback (subclasses: non-identifying token, unread evidence field, order-decided tie, skipped type gate, misfiled metadata).
8. **Prior incidents (same class).** Searched code, tests, CHANGELOG.md, TECHTRACK-VERSION-HISTORY.md and the validation debriefs for thetford|maxxfan|coleman|borrow|girard|unknown brand|miscategor.
   - (1) Girard fridge pinned for a water heater.
   - (2) Thetford guard / assumed brand.
   - (3) MaxxFan p9 page patch.
   - (4) Coleman page rank.
   - (5) Unknown-brand borrowing (Brinkley 3100 -> Lippert).
   - (6) RC30.
   - (7) Misfiled library docs 309 / 631 / 629, with 565 found by the audit.
   - (8) B13 Suburban SW6DE.
9. **Fix + proof.**
   - **F1:** `strip_unit_values()` removes number + unit, with or without a space or hyphen and with ","/"." grouping, for V/VAC/VDC/volt, A/amp, Ah/mAh, W/kW, BTU/BTUH, lb/pound, psi, Hz, gal, cfm, rpm, cu ft. K is a rating only as thousands-of-BTU (1-2 integer digits: 8K, 13.5K); 4500K stays a model. `is_unit_token()` is used wherever tokens are made.
     - Property test: 26 units x 11 number forms x 3 separators x 4 contexts = 3,432 cases. No unit value is ever a model token or key.
   - **F2:**
     - Specificity ladder: exact model in doc fields (5) > exact model in keywords/page text (4) > series in fields (3) > series in keywords/text or product-line phrase (2) > brand only (1, never picks).
     - Within a tier: longer key, then model named in the title, then troubleshooting/service manual > plain manual > form, then fewer models listed.
     - A remaining tie between DIFFERENT manuals (identity = file hash, doc number or title) gives `how='ambiguous'`: no pick, and the official web lookup runs. Duplicate uploads of one manual are one manual.
     - A2: series = leading letters+digits with any digit count (sw6de -> sw6). It matches only a doc token equal to it or continuing with a LETTER (SW6DE yes, SW60 no).
     - B: keywords and page text are read (one indexed query per key over the candidate docs).
   - **F3:**
     - All 24 library categories map to types (a test enforces it).
     - Type words are word-bounded and name only what the product is: no model names (gswh removed), and doc kinds (form/bulletin/reference) are not product types.
     - Unmapped category + no type in the model text -> `how='needs_confirmation'`; GD asks "what kind of unit is it", and the tech's answer is the confirmation.
     - A model that exists only under another type also asks (and names the type the library has it under) instead of pinning.
     - A doc's own words decide its type; its filing category is used only when it names none.
   - **File availability (rule 11 CONTAINMENT moved):** `select_manual(available=...)` skips an unreachable doc and tries the next eligible group; when nothing is left it's not found, so the web lookup runs. The app passes "the doc has indexed text". Rule 11 (its own branch) should switch to `available=` (follow-up FU-2).
   - **F4:**
     - Deleted: `_rank_coleman_pages`, `_rank_thetford_leak_pages` with `_thetford_leak_rank_score`, and `supplement_maxxfan_remote_pages` with the MAXXFAN_REMOTE_GUIDE_DOC/PAGE constants. Replaced by ONE `rank_pages_for_concern` (model/part numbers on the page, complaint words, troubleshooting tables; pages naming another brand ranked last).
     - Removed: the toilet -> Thetford default brand.
     - **Kept, with a written general rule:**
       - `is_thetford_flush_leak_context` fires only when the tech names Thetford (an OEM-authored repair path applies only to that OEM's unit).
       - `maxxfan -> maxxair` alias (a product-line name maps to its maker; a data table, like schwintek -> lippert).
     - **Flagged (out of Leader's F4 list):** the other context rankers in `rank_bay_chunks` (ground control, dometic no-cool, fcr dial-off, ice/moisture, BAL tongue, stabilizer pin, cooktop) remain (follow-up FU-1).
   - **R1:** `library_category_audit.py` + a Manager Tools panel (dry run, per-row untick, confirm, R2 backup, apply, rollback).
     - Rule: a doc is misfiled when both its title type and its page-text dominant type fall outside its category's types. Component-only titles (controller, power, chassis, axle) are consistent when the category's product appears in their text. Kind categories (forms, bulletins, reference) aren't audited.
     - Library copy: 17 moves, including 309 -> Range & Cooktops, 631 -> Leveling and 629 -> Leveling, with no doc ids in code.
     - **565 is NOT misfiled** by the rule: its page text is a room slide-out procedure and it sits in slide-outs. Its title/product_line (an OCR'd first line, "Leveling") is what's wrong, so it goes on the metadata-review list.
     - Snapshot test: the audited library snapshot plans 0 moves and 0 unmapped categories.
   - **R2:** single upload and R2 link require a confirm checkbox when the category disagrees with the title. Unattended bulk import writes "CATEGORY CHECK:" into the index note, and the audit picks the doc up.
   - **Sweep (live library copy, 89 docs with model numbers + 890 cross-category queries):**

     | | v4.19.64 raw lib | v4.19.64 audited lib | v4.19.65 raw lib | v4.19.65 audited lib |
     |---|---|---|---|---|
     | wrong-type picks (self) | 0 | 0 | 0 | **0** |
     | wrong-type picks (cross, 890) | 9 | 9 | 0 | **0** |
     | ambiguous-tie picks | 15 | 16 | 0 | **0** |
     | pinned the same model | 87 | 89 | 73 | 78 |
     | no pick -> web lookup | 2 | 0 | 16 (10 ambiguous, 6 confirm type) | 11 (all ambiguous) |

     The 11 audited-library no-picks are docs whose model sits in several different manuals with equal evidence: Power Gear 140-1224 (5 manuals), 140-1146 (2), 140-1161 (2), Lippert PSX2 (3). v4.19.64 "found" those by read order; they now go to the web lookup.
   - **Regression tests:** tests/test_selector_root_fix.py (27) + tests/test_gd_manual_selection_locked.py (9). One per incident: Girard, Thetford, MaxxFan p9, unknown brand, RC30, 309/631/629/565, B13; Coleman is covered by the existing Coleman suite with the generic ranker. Plus the F1 property test, F2 ties/threshold/web lookup, F3 confirmation, and availability.

Follow-ups (not containment of this fix; separate scope): FU-1 retire the remaining context rankers in rank_bay_chunks the same way; FU-2 rule 11 branch: call select_manual(available=pdf_reachable) and drop its own skip loop; FU-3 metadata review for 565 / 489 titles; R4 (Leader: later) category -> type map into category metadata.
