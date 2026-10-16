### RCA: Library docs 309 and 631 filed under the wrong category, so the selector correctly refuses them
Format: /workspace/crew/standards/ROOT-CAUSE-ANALYSIS-STANDARD.md. Branch cursor/library-category-fix. 2026-10-16 PDT.

1. **Problem statement.** Sweep input "Girard GRG17ABS" with category Range & Cooktops, and "Power Gear 140-1161" with category Leveling. Observed: no manual pinned ("No ... manual found"). Expected: doc 309 (Girard 17" All Glass Gas Range, CCD-0007861) and doc 631 (Power Gear T.I.P. Automatic Level Controller Set-Up).
2. **IS / IS-NOT.**
   - IS: 309, stored under category 18 "awnings", with a range/cooktop title; 631, stored under 20 "slide-outs", with a leveling title.
   - IS-NOT: the other 87 sweep docs with model numbers, which are stored under the category their title names, all pin their own manual. Other Girard docs under Water Heaters and other Power Gear docs under Leveling work too.
   - Difference: only the stored category_id disagrees with the doc's own product type. Brand, model field and text are fine. The v4.19.64 type hard filter (gd_official.doc_eligible) therefore rejects the docs as "wrong product type", which is correct behavior on bad data.
3. **Timeline (PDT).** The file paths carry the category id at upload: 309 `documents/18_20261010222343_...` (uploaded 2026-10-10 15:23 into awnings), 631 `documents/20_20261011003813_...` (2026-10-10 17:38 into slide-outs, a TI sheet whose keywords include "slide-"). The bug went unnoticed while selection ignored category. It surfaced 2026-10-16 ~3:45 PM in the v4.19.64 library sweep (scripts/manual_selection_sweep.py, 89/93), the first time the category was enforced.
4. **Evidence.** Sweep JSON manual-selection-sweep-2026-10-16.json: 309 and 631 were rejected as "wrong product type". library_category_fix.plan() dry run on a library copy: 309 awnings(18) -> Range & Cooktops(12); 631 slide-outs(20) -> Leveling(6). Audit over a library copy (category -> CATEGORY_TYPES vs doc_product_types(title)), after the fix: 361 checkable docs, 2 more mismatches: 565 (slide-outs, title says leveling, title text garbled) and 629 "Power Gear T.I.P. - DMI LEVELING PUMP TEST PROCEDURE" (slide-outs).
5. **Causal chain.** Wrong category = A AND B. The not-found outcome = (wrong category) AND C.
   - A, input path: the upload/register flow (rv_techtrack Manager Tools upload + bulk register, ~l.7351) takes the category from the batch or uploader, and Power Gear TI sheets mix slide-out and leveling topics.
   - B, missing gate: nothing at upload checks the chosen category against the doc's own product type (title/product_line). Contributing: the categories have no product-type metadata, and the only map is CATEGORY_TYPES in gd_official.py.
   - C, downstream: since v4.19.64 the category is a hard filter (by design), so a misfiled doc becomes unfindable instead of mis-ranked.
   - Systemic root: **library metadata is accepted without validation against the document's own content, and nothing audits it afterward.** That's the input-data / gates leg of the fishbone. Blaming "the uploader picked wrong" would be the blame-the-input trap.
6. **Why checks missed it.** No test or Manager Tools audit compares category with doc type. Before v4.19.64, selection ignored category, so the bad data had no visible effect. The sweep is the first check that exercises every doc with its own category, and it did catch the problem.
7. **Class of failure.** Unvalidated library metadata (category disagrees with the document's own product type).
8. **Prior incidents (same class).** Searched CHANGELOG.md, TECHTRACK-VERSION-HISTORY.md, PDF-PAST-FAILS.md and profiles/ for recategor|wrong category|miscategor|filed under. No earlier recorded incident. Related data note: 28 docs whose models field holds a rating or series ("8,000 lb", "8K"), the same class family (unvalidated metadata fields). New instances found by the audit: 565 and 629.
9. **Fix + proof.**
   - **CONTAINMENT (this branch):** library_category_fix.py plus the Manager Tools panel. It fixes 309 and 631 by id and title prefix, with a dry run, confirm, R2 backup, apply (documents + doc_chunks), and rollback. Re-running shows "already correct". This is a data correction keyed on doc ids, so under standard section 3 it is containment, not a root fix.
   - Proof on a library copy: dry run, apply, re-plan "already correct", rollback all verified. Sweep 89/93 -> 89/89 (100%). tests/test_library_category_fix.py (2 tests) passes.
   - **Root-fix follow-up items (open):**
     - R1: a category/type audit (the check used above) as a Manager Tools report plus a test over the shipped library snapshot that fails on any mismatch.
     - R2: an upload/register-time warning plus confirmation when the chosen category disagrees with the title's product type.
     - R3: review 565 and 629 (likely Leveling) and fix them through the same panel after Leader approval. They are not included in FIXES because they haven't been reviewed.
     - R4: move the category -> type map into category metadata so the map isn't kept in code.
   - Live: not applied. It needs this PR merged (Leader clearance) and a signed-in manager to run dry run -> confirm -> apply.

### Section-4 checklist (self-graded)
| # | Item | Result |
|---|---|---|
| 1 | Full 9-field template | PASS |
| 2 | IS/IS-NOT with working cases, difference explained | PASS |
| 3 | Evidence per link | PASS (paths, sweep JSON, dry run, audit) |
| 4 | General logic defect reached | PASS (no metadata validation) |
| 5 | Class named, prior search listed | PASS |
| 6 | No new case keyed on id/brand/file | **FAIL -> labeled CONTAINMENT** (FIXES keyed on doc ids 309/631, by nature of a data correction) |
| 7 | Whole-class sweep/property test, before/after | PASS for the sweep (89/93 -> 89/89); the class audit found 2 more (R3) |
| 8 | Regression test per prior incident | PASS (no prior incidents; plan/apply/rollback tests added) |
| 9 | Escape point closed | **FAIL** until R1/R2 land |
| 10 | Full suite + sweep zero new regressions | see PR/report |
| 11 | Containment labeled with follow-up | PASS (R1-R4) |
Overall: shipped as CONTAINMENT, with R1-R2 as the root fix.
