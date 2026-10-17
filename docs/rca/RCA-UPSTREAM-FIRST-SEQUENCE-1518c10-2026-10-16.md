# RCA: GD condemns a downstream part in the same reply as the manual's upstream "correct first" repair (RC22 FAIL, d416c94 sweep)
Commit: 1518c10 (gd_official.py sequence_condemns / first_fix_line; tests/test_upstream_first_sequence.py). Author: TT. 2026-10-16.

### RCA: upstream-first correction and a downstream condemn issued together
1. **Problem statement.** On the d416c94 full sweep, RC22 (Suburban SW6DE, no gas ignition, 12 V collapses on each try) got the manual's source repair at turn 6, "Correct the coach 12 V supply first so it stays 10.5-13.5 VDC during a try" [Library: Suburban Water Heater Master Service and Training Manual p.10]. The same reply also said "Replace the DSI module board" unconditionally (p.17). The sim tech replaced the board, then the valve and then the switch, and none of them fixed it. 14 turns, no repair reached. Expected: the supply correction first, and the board only "if the drop remains" (the manual line GD itself quoted at turn 5: "correct the 12 V supply first, then replace the module board if the drop remains", p.17).
2. **IS / IS-NOT.**
   - IS: a reply containing an unconditional "correct/repair/fix X first" line plus an unconditional condemn of another part. On d416c94 this was RC22, turns 6 and 9.
   - IS NOT: replies whose condemn is already conditional ("If the drop remains, replace the board"). Example: RC22 turn 5, where the sequence was correct.
   - IS NOT: replies with a single repair and no upstream-first step. Examples: RC30 fuse, RC14 ceiling selector, RC29 whole unit. Those worked because there was nothing to sequence.
   - Across 1,057 stored GD replies (all sim dirs 2026-10-16), the pattern occurs exactly 2 times, both in RC22 d416c94. That explains why RC22 failed and the others did not.
3. **Timeline.**
   - The condemn guard (a1bbd35), the NPF/split rule and PENDING_RULE (33b4202) all landed earlier.
   - The d416c94 full sweep ran 9:00-9:50 PM; TT reviewed it at 9:25 PM.
   - Fixed in 1518c10, 9:31 PM.
4. **Evidence.**
   - Transcript: gd-official-sim-2026-10-16/d416c94/RC22.md turn 6 (lines 56-75). The first line corrects the supply, line 3 says "Replace the DSI module board". The tech's line 80 reads "Replaced the DSI module board … Complaint is still present."
   - Code before the fix: official_turn ran hold_npf, then unproven_condemns, then hold_for_adjustment, then cap_repeats. None of these looks at the order between an upstream correction and a condemn in the same reply.
   - The condemn guard passed the board because isolation readings existed: "collapses to ~5-10 V on a try (same at the board feed)" satisfies ISOLATION_RE plus part words.
5. **Causal chain.**
   - Trigger: the model emitted the manual's "first" step and the downstream replacement as two parallel lines.
   - Condition 1: the guards gate a condemn only on evidence (isolation/adjust/NPF), never on the ORDER the manual prescribes.
   - Condition 2: the supply reading counts as isolation for the board too, because it was taken at the board feed.
   - Systemic root: no rule makes a downstream condemn conditional on the result of an upstream correction given in the same reply.
6. **Why existing checks missed it.**
   - The locked tests cover unproven condemns, re-asks, NPF and pending tests, but none covers a reply that has both a correct first step and a parallel condemn.
   - The RC sweep before d416c94 had RC22 ending early (harness [END]) or stuck on the pending test, so the shape never appeared.
7. **Class of failure.** "Unordered parallel directives: the manual's sequence (correct upstream first, then replace downstream if the fault remains) is flattened into simultaneous actions."
8. **Prior incidents.**
   - Searched every stored transcript programmatically with first_fix_line plus sequence_condemns over 1,057 GD replies. Only RC22 d416c94, 2 replies.
   - Related but distinct: RC12 (edc11db), where two parts were condemned at once (board plus fan). There both were isolated and no upstream-first step existed, so it is a different class.
9. **Fix + proof.**
   - General logic: FIRST_FIX_RE / first_fix_line finds an unconditional, non-condemn "correct/repair/fix/restore … first" line. sequence_condemns rewrites every other unconditional, non-negated, non-VERIFY condemn line in that reply to "Only if the complaint remains after that first correction (…): replace …". It runs in official_turn before drop_reasks/cap_repeats. No brand, model, doc or case keys; the case-key grep returns 0 hits.
   - Tests: tests/test_upstream_first_sequence.py has 5 tests: condemn made conditional, negated and conditional lines untouched, no first-step means no change, a conditional first step doesn't trigger, VERIFY lines untouched. All pass.
   - Property sweep: of 1,057 stored replies, the rule changes 2 (both the RC22 defect) and 0 others.
   - Full RC sweep on 0c4a291: see PR92-HOLD-PACK-2026-10-16.md (RC22 row and regression list).
   - Not CONTAINMENT: this is a root fix to the general sequencing logic.
