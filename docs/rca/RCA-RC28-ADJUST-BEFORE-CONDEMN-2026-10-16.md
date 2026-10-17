### RCA: Slide diagnosis could condemn motors/columns before the pinned manual's cable adjustment/synchronization step (RC28)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Fix commit 33b4202. No case-keyed code (no brand/model/part number in the rule).

1. **Problem statement.**
   - RC28 (BAL Exact-Slide cable slide, crooked travel), edc11db run: GD condemned both motor assemblies at turn 3 (gd-official-sim-2026-10-16/edc11db/RC28.md l.33) and never asked for the cable alignment/tension steps.
   - The pinned manual has those steps: the BAL EXACT-SLIDE Service Manual, p.2 cable adjustment and p.6 "Adjust the bottom cable first, and then the top cable".
   - Chase's pass rule: cables first, then the column replacement.
   - The e75ad8b run did check cables first (l.26, l.36–37; tech l.33, l.45) and condemned at turn 4 (l.55). So the method didn't guarantee the order; the model chose it.
2. **IS / IS-NOT.**
   - IS: mechanical complaints whose manual has an adjustment/synchronization procedure (cables, sync, re-learn, zero-point), condemned on observation.
   - IS-NOT: electrical isolations (RC30 fuse, RC12 board), where the manual's first test is a meter reading.
   - Difference: nothing in the method required the manual's adjustment/sync items before a condemn. The order depended on model sampling (edc11db vs e75ad8b).
3. **Timeline.**
   - edc11db run 8:02 PM: condemn at turn 3, no cables.
   - Checker note 8:24 PM.
   - Leader 8:23/8:40 PM.
   - Fixed in 33b4202.
4. **Evidence.**
   - 0802509 gd_official.py l.1093 `unproven_condemns` checks only isolation readings. No function reads the section text for adjustment/sync steps (grep for adjust|sync|cable in the guard: none).
   - The edc11db transcript has no "cable" request before l.33.
5. **Causal chain.** Condemn before adjust = (A) the guard knew only isolation readings AND (B) the model sometimes skips manual adjustment items when flex is reported. Systemic root: **the method had no rule that the pinned manual's adjustment/synchronization items precede a condemn.**
6. **Why checks missed it.** Guard tests had no mechanical/adjustment case, and the RC rerun verdicts were not checked against each case file's order rule.
7. **Class of failure.** Required precondition left to model sampling (ordering not enforced).
8. **Prior incidents.** Leveling zero-point/calibration (RC01/RC15 reached calibration, good), Lippert re-learn/resync paths (UNITY_PATH_RULES). Search: calibrat|resync|zero-point|re-learn in CHANGELOG/tests.
9. **Fix + proof.**
   - `ADJUST_RE` / `manual_adjust_steps(section_text)`: if the pinned section has adjustment/sync steps (synchronize, re-sync, cable tension/adjust, take slack, re-learn/erase-learn, zero-point, re-index/timing), then `unadjusted_condemns()` holds every condemn until the session records one: a tech answer to a request with those words, or a tech message reporting one.
   - The held line quotes the manual's step.
   - Tests: `TestAdjustBeforeCondemn` (held / released / no-adjustment-manual no hold).
   - **Part numbers R25079/R25078:** VERIFIED in the pinned manual.
     - Library doc **5** "BAL EXACT-SLIDE Service Manual", **p.6**: "Part #: Left Hand R25079, Right Hand R25078".
     - Same doc **p.8** (service parts): "MOTOR G5.5 LH R25079".
     - Also flat-rate guide doc 36 p.3.
     - GD cited the manufacturer-site copy of the same manual at p.6 (e75ad8b l.55). The part numbers came from the pinned page, so the judge's "invented" (edc11db) was wrong.
   - Contributing finding (FU-5, not in this fix): selection returned "none" for "BAL Exact-Slide Emforce cable slide, column tag 22000928", so GD used the web copy instead of library doc 5. The only model token is 22000928, and the product-line words "Exact-Slide" aren't used as evidence when the library docs have no models/product_line metadata. The general fix belongs in selector tier 2 (product-line phrase from the title); left as FU-5 for Leader.

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; class/priors ✔; no case keys ✔; sweep (full RC set on the final SHA, pack) ✔; regression tests ✔; escape closed ✔; containment n/a.
