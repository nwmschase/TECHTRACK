# RCA: GD directed part replacements while isolation tests were pending (RC20 regression on 0c4a291)
Commit: e82df6b (gd_official.py NOT_DONE_RE, pending_isolation_tests, hold_while_pending, REPLACE_ANY_RE, CONDEMN_RE 60-char/" as" stop; scripts/gd_rc_sim.py TECH_SYS pending rule; tests/test_pending_blocks_condemn.py). 2026-10-16. Leader order 10:21 PM item 1.

### RCA: pending isolation tests did not block condemns
1. **Problem statement.**
   - RC20 (Lippert Level Up 807662; front jacks drift when other circuits pressurize; OPEN case) on 0c4a291.
   - The tech reported "Gray-coil unplug isn't in the notes (still pending)" (turn 7) and "Plumbing check isn't in the notes (still pending); hoses/fittings/manifold look normal/OK" (turn 8).
   - GD then wrote "Gray-coil unplug and plumbing check stay skipped — do not retry them". At turn 10 it said "Commit to Lippert auth and replace both front valves/manifold as a matched set". At turn 13 it said "Commit to replace the remaining front jack".
   - The tech replaced both. The complaint was still present after each.
   - Expected: no part is replaced or submitted for replacement while a decisive isolation test is pending. GD gives the repair decision per result (PENDING_RULE) or the tech-line escalation.
2. **IS / IS-NOT.**
   - IS: sessions where the tech reports an isolation test as pending and GD then gives an unconditional replace (RC20 on 0c4a291, d416c94, followup-1504; RC22 on a1bbd35, d416c94, golive-1431).
   - IS NOT: RC22 on 0c4a291. It was pending too, but GD gave only the conditional source repair decision and no condemn. So pending alone is not the trigger; the trigger is an unconditional replace that slips through.
   - IS NOT: RC29, RC30 and RC14. No test was pending, and their condemns were backed by recorded readings.
3. **Timeline.**
   - PENDING_RULE (prompt only) arrived in 33b4202.
   - In d416c94, RC20 was already condemning while tests were pending (4 replies, found by the replay below) but ended in OEM auth.
   - 0c4a291 adds the sim-tech conditional-repair rule. The tech now actually performs GD's unconditional "commit to replace" lines, so the regression became visible: two swaps.
   - Checker flagged it 10:20 PM; Leader order 10:21 PM; fixed in e82df6b.
4. **Evidence.**
   - Transcript: gd-official-sim-2026-10-16/0c4a291/RC20.md, turns 7-14 (lines 84-176).
   - Code before the fix: _is_result counted any sentence matching TEST_RESULT_RE ("look normal/OK"), even in a sentence that says the test is pending. So isolation_recorded('manifold', …) was True from the turn-8 answer.
   - CONDEMN_RE limited the part phrase to 40 characters before a terminator. "replace both front valves/manifold as a matched set" has no terminator within 40 characters, so condemned_parts() returned [] and no guard ever saw the turn-10 line. Repro: `go.condemned_parts('Replace both front valves/manifold as a matched set.')` returned [] before the fix and returns ['both front valves/manifold'] after.
   - PENDING_RULE is a prompt rule with no deterministic barrier.
5. **Causal chain.**
   - Trigger: the tech reports decisive tests pending; GD (model) declares them "skipped" and commits to replacements.
   - Condition 1: no code path blocks a condemn while a test is pending; PENDING_RULE is advisory text.
   - Condition 2: a "pending … looks normal/OK" answer counted as a recorded result, so the guard believed isolation was done.
   - Condition 3: CONDEMN_RE missed long part phrases, so the guard could not see the condemn at all.
   - Condition 4 (harness): TECH_SYS told the tech to say "looks normal/OK" for anything unrecorded, even when the case file marks it pending. That produced the contradictory answers.
   - Systemic root: **evidence-gating treated "not done" text as evidence and had no pending-test barrier.** Both GD (conditions 1-3) and the sim (condition 4) contributed. GD is the primary cause, because GD issued the unconditional replace lines; the sim only obeyed them.
6. **Why existing checks missed it.**
   - The locked tests covered unproven condemns with no reading, but not a reading-shaped sentence that says "pending".
   - The PENDING_RULE test only checked that UNAVAILABLE_RE recognizes "pending", not that a condemn is blocked.
   - No test used a part phrase longer than 40 characters.
7. **Class of failure.** "Evidence gate fooled by negated evidence ('pending … normal/OK'), plus a missing hard barrier for pending decisive tests."
8. **Prior incidents (replay of all 1,198 stored GD replies with the new hold).**
   - 23 replies change: RC20 on 0c4a291 (5), d416c94 (4), followup-1504 (3+1); RC22 on a1bbd35 (4), d416c94 (3), golive-1431 (2); and edc11db RC08 (1).
   - The edc11db RC08 hit is a real hold: the panel was condemned while "didn't get a harness-side bay reading", the panel-vs-harness split.
   - False positives found during development were removed by general rules, with tests:
     - "not in the notes" alone is the harness's unrecorded-normal convention, not pending;
     - generic "haven't checked anything yet";
     - negated "no board R&R";
     - "replaceable".
   - Searched with scripts/pending_sweep.py (techtrack-validation/scripts).
9. **Fix + proof.**
   - NOT_DONE_RE: a pending, not-done, didn't-do or skipped sentence is never a result (_is_result).
   - pending_isolation_tests(tech_msgs) tracks tests reported not done until a later recorded result clears them.
   - hold_while_pending removes EVERY unconditional replace, condemn or R&R line while any isolation test is pending. That includes a tech-proposed swap that GD would endorse and an OEM "Requested authorization: replace …" line. It writes a single hold line (do the test, or call the shop/OEM tech line). Conditional repair decisions ("If <result>, replace …") and VERIFY lines stay.
   - It runs in official_turn before sequence_condemns, drop_reasks and cap_repeats.
   - CONDEMN_RE: the part phrase may be up to 60 characters and stops at " as".
   - TECH_SYS: never add "looks normal/OK" to a pending test.
   - No case keys; the grep is in the pack.
   - Tests: tests/test_pending_blocks_condemn.py has 10 tests: the RC20 shape, pending-plus-OK is not a result, a result clears pending, no pending means no hold, long phrases, the not-in-notes convention, generic not-checked, negated R&R, the sim rule, plus a property test of 5 pending answers × 30 condemn pairs with no unconditional replace surviving. All pass. The 140 GD-side tests pass.
   - Reruns: RC20 plus the hold set (RC12, RC22, RC28, RC29, RC30) on e82df6b, and the final full sweep. See PR92-HOLD-PACK-2026-10-16.md.
   - Not CONTAINMENT.

## Addendum: 750b5cf (the e82df6b rerun still swapped parts)
- **Problem.** On e82df6b, RC20 still had the tech replace both front cartridges, then both jacks, then the HPU (turns 7-12) while "Plumbing check and gray-coil unplug test are still pending". The hold fired only at turns 6 and 13.
- **Cause (code evidence).** Every swap line also carried a negated sentence: "Replace both front jack solenoid cartridges as a matched pair at the manifold. Do not replace the LCD or 807662 board." hold_while_pending, sequence_condemns and (since 3e948c2) condemned_parts skipped any LINE containing a negation, so one "do not replace" hid the real condemn. Root: **negation was judged per line instead of per sentence.**
- **Fix.** _clauses, _negated and unnegated_condemn judge each sentence. A line is a condemn when any unnegated sentence condemns. condemned_parts drops only the negated sentences.
- **Proof.**
  - 3 new tests (TestMixedLine); 150 GD-side tests pass.
  - The replay now holds 5 e82df6b RC20 replies (28 of 1,255 total, no new false positives).
  - Reruns: RC20/RC22 on 750b5cf plus the final full sweep (see the pack).

## Addendum 2: 215fce8 (750b5cf rerun: one swap still slipped)
- **Problem.** On 750b5cf, RC20 went from 3 swaps (e82df6b) to 1: both front cartridges at turn 8. Two GD lines let it through while plumbing and gray-coil were pending:
  - Turn 5: "Shop path without those tests: replace both … cartridges as a pair (… do not replace the cylinders for this alone)". The parenthetical negation negated the whole sentence.
  - Turn 7: "If they would still drift with coils unplugged (matches the voltages you already have), replace both … cartridges". A counterfactual condition that GD itself declares met, so it is effectively unconditional. The sim tech acted on it.
- **Root.** Negation was judged per sentence, not per verb, and a conditional's form was trusted even when its condition was counterfactual or asserted.
- **Fix.**
  - _verb_negated checks the 30 characters before EACH condemn/replace verb. That check is used by unnegated_condemn and condemned_parts.
  - COUNTERFACTUAL_RE (would / matches / already have…) in the condition makes a conditional replace count as unconditional while a test is pending.
  - TECH_SYS: a condition about a pending test is never met.
- **Proof.**
  - 4 new tests (TestDisguisedConditionals); 154 GD-side tests pass.
  - Replay: 30 of 1,312 replies held, including the 2 from 750b5cf RC20; the real repair decision ("If they still drift with both coils unplugged, replace …") is kept.
  - Final sweep on 215fce8: see the pack.
