# RCA: GD calls No Problem Found after only operating the unit, with no inspection of the complaint's path (RC27, every run)
Commit: 3e948c2 + 9930f93 (gd_official.py NPF READINESS prompt line, INSPECTION_RESULT_RE, REPAIR_DONE_RE, npf_unready, hold_npf_inspection; negated condemns ignored by condemned_parts; tests/test_npf_readiness.py). 2026-10-16. Leader order 10:21 PM item 5.

### RCA: NPF readiness was "complaint not reproduced" only
1. **Problem statement.**
   - RC27 (Furrion FCR fridge, "fridge compartment not cold, freezer fine"). On 0c4a291 GD said "No Problem Found - operating as designed" at turn 2, right after the tech's pull-down run (fridge reached ~38F).
   - It never had the tech remove the interior airflow cover and check the freezer-to-fridge passage for ice or blockage. Chase's PASS line for RC27 requires that check.
   - The same reply carried a junk line: "Before condemning the parts, record its isolation reading…".
   - Expected: inspect the path the complaint depends on, then NPF with the customer explanation.
2. **IS / IS-NOT.**
   - IS: all 11 stored RC27 runs (a1bbd35, edc11db, d416c94, 0c4a291, final-fea86b4, followup-1504, passA, rc30fix-1527, rootfix-1640, selector-1532 and the earliest run). Each called NPF with no recorded inspection.
   - IS NOT: RC15, RC16 and RC17 "operating as designed" after a recalibration, reseat or petit-tube realign. Those are close-outs after a repair, and correct.
   - IS NOT: RC14 on bdee295, where the complaint was still present. The 33b4202 NPF block handles that case.
   - Correction to the premise: the RC27 transcript shows the complaint was NOT reproduced (fridge reached ~38F). That is why the "NPF blocked while complaint present" rule correctly did not fire. The defect is the missing inspection, not a missed still-present report.
3. **Timeline.**
   - NPF_RULE (prompt) has existed since the GD official build. The still-present block came in 33b4202.
   - Checker flagged the missing airflow-cover check earlier on 10/16. Leader order 10:21 PM; fixed in 3e948c2.
4. **Evidence.**
   - Transcript: gd-official-sim-2026-10-16/0c4a291/RC27.md turn 2.
   - Case file: real-cases/RC27-furrion-fcr-fridge-npf.md, PASS line ("Checks the airflow passage/cover for ice/blockage").
   - Code before the fix: npf_blocked() only checks STILL_PRESENT_RE, and NPF_RULE only requires "complaint not reproduced, readings normal".
   - Junk line: condemned_parts matched the model's negated "condemn no parts", and "parts" was not a stop word.
   - Replay: with the new npf_unready, 10 RC27 replies are held, and 0 others after the close-out rule (scripts in the pack).
5. **Causal chain.**
   - Trigger: the tech reports normal temperatures after a run.
   - Condition 1: the NPF readiness definition = not reproduced, with no inspection requirement.
   - Condition 2: no deterministic barrier besides still-present.
   - Systemic root: **NPF readiness lacked an inspection-of-the-path requirement.** The junk line has a separate root: condemn detection did not exclude negated condemns.
6. **Why existing checks missed it.**
   - test_condemn_norepeat_locked only tests NPF blocked while present and NPF allowed when not reproduced. The latter encoded the too-weak definition as correct.
   - The RC sweep judge is neutral and doesn't apply Chase's PASS line.
7. **Class of failure.** "Premature closure: a no-fault verdict on an operational check alone, without inspecting the mechanism the complaint depends on."
8. **Prior incidents.**
   - All 11 RC27 runs, as listed above (replay over 1,198 stored replies).
   - Same family: RC14 NPF while present (bdee295), fixed in 33b4202. Its test still passes.
9. **Fix + proof.**
   - NPF_RULE gains an NPF READINESS line.
   - npf_unready(reply, tech_msgs): NPF is called, no repair was done in the session (REPAIR_DONE_RE; after a repair, "as designed" is a close-out), and no tech sentence records an inspection result (INSPECTION_RESULT_RE: no ice/debris/blockage/leak…, a clear passage, or a removed/opened cover with a finding; never a pending one).
   - When npf_unready is true, hold_npf_inspection removes the NPF and customer-explanation lines and asks for the inspection of that path, with a category-generic example. It runs right after the still-present NPF block.
   - condemned_parts ignores negated condemns, and "parts"/"no" are stop words.
   - No case keys.
   - Tests: tests/test_npf_readiness.py, 6 tests (held without inspection, allowed after inspection, a pending inspection doesn't count, 5 close-out phrasings untouched, the still-present block wins, negated condemn). All pass, as do the 147 GD-side tests.
   - Rerun: RC27 + RC15/RC16/RC17 on 3e948c2 and the final sweep. See the pack.
   - Not CONTAINMENT.
