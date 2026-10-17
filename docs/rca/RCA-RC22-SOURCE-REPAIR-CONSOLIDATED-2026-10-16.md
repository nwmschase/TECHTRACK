# RCA: RC22 pinned doc 124 but never reached a source repair (consolidated; Leader order 10:21 PM item 6)
Commits: 33b4202 (PENDING_RULE + harness pending gate), 1518c10 (upstream-first sequence), e82df6b + 750b5cf (pending test blocks every condemn; pending answer is never a result; per-sentence negation). 2026-10-16.
Supersedes the scope of RCA-RC22-PENDING-DECISIVE-TEST-2026-10-16.md (kept as the 33b4202 record).

### RCA: GD on the right manual never delivered the manual's repair
1. **Problem statement.**
   - RC22 (Suburban SW6DE: gas clicks, never lights, shorter try; the 12 V feed collapses from ~14.2 V idle to ~5-10 V on each try; OPEN case with the battery-jump test and tech-line call pending).
   - GD pinned doc 124, "Suburban Water Heater Master Service and Training Manual", correctly, but no run delivered the manual's repair:
     - a1bbd35: 14 turns, the same test asked 3 times, ending in a DSI-board condemn.
     - edc11db: 4 turns, "none"; the harness accepted a pending [END].
     - d416c94: board, then valve, then switch replaced in sequence; "none".
   - Expected (the Leader's bar): a source repair from doc 124. Here that is "correct the coach 12 V supply so it holds 10.5-13.5 VDC through the try" (p.10 / p.17), then the module board only if the fault remains, with the tech-line escalation (p.3).
2. **IS / IS-NOT.**
   - IS: RC22 runs where the decisive test (battery jump at the heater feed) was reported pending.
   - IS NOT: RC30 and RC14, single-path repairs with no pending test, which reached their repair.
   - IS NOT: RC22 on 0c4a291, which reached the source repair at turn 6 (p.17) with the board conditional. The difference: 1518c10 sequenced the parallel board condemn, and the 33b4202 pending rule stopped the re-asks.
3. **Timeline.**
   - a1bbd35 / edc11db / d416c94 failures as above.
   - 33b4202 (8:3x PM): PENDING_RULE plus the harness pending gate.
   - 1518c10 (9:31 PM): upstream-first.
   - 0c4a291: first pass, turn 6.
   - e82df6b / 750b5cf (10:3x PM): the pending-test barrier.
4. **Evidence.**
   - a1bbd35/RC22.md: 14 turns, max repeats 3.
   - edc11db/RC22.md: [END] on "pending".
   - d416c94/RC22.md, turn 6 lines 56-75: "Correct the coach 12 V supply first" next to "Replace the DSI module board", then a board-valve-switch cascade (lines 80, 142, 164).
   - 0c4a291/RC22.md turn 6 and e82df6b-holdset/RC22.md turns 8, 9 and 12 (p.10/p.17).
   - Code lines: UNAVAILABLE_RE without "pending" (before 33b4202); end_accepted with no PENDING_RE (before 33b4202); no ordering check (before 1518c10); _is_result counting "pending … normal/OK" and line-level negation (before e82df6b / 750b5cf).
5. **Causal chain.**
   - Trigger: the decisive test cannot be done now ("pending").
   - Condition 1: "pending" was not read as unavailable, so GD re-asked the test (a1bbd35).
   - Condition 2: the harness ended runs on a pending [END] (edc11db).
   - Condition 3: the manual's ordered step ("correct supply first, then board if it remains") was flattened into parallel directives (d416c94).
   - Condition 4: condemns were not blocked while the decisive test was pending, and "pending … looks normal/OK" counted as evidence (d416c94 valve/switch).
   - Systemic root: **GD had no deterministic handling of a pending decisive test.** It neither turned it into the manual's repair decision nor blocked parts while it was open, and it lost the manual's order between steps.
6. **Why existing checks missed it.**
   - The RC sweep judge is neutral and has no "source repair" bar.
   - No unit tests existed for a pending test, an ordered first-step, or a mixed negated line before tonight.
7. **Class of failure.** "Pending decisive test mishandled: re-asked, ignored, or bypassed by parallel/premature condemns, so the manual's repair decision is never delivered."
8. **Prior incidents.**
   - RC22 on a1bbd35, edc11db, d416c94 and golive-1431 (replay: the pending hold changes 2-4 replies in each).
   - RC20 on d416c94, 0c4a291 and e82df6b (the same class; see RCA-RC20-PENDING-TEST-PARTS-CANNON-e82df6b).
   - edc11db RC08 (1 reply).
9. **Fix + proof.**
   - 33b4202: PENDING_RULE and UNAVAILABLE_RE recognize pending; the harness never ends on a pending report.
   - 1518c10: sequence_condemns.
   - e82df6b: pending_isolation_tests and hold_while_pending block every unconditional condemn/replace (a tech-proposed one and an OEM replacement request included) while a test is pending, and a pending answer is never a result.
   - 750b5cf: negation is judged per sentence.
   - Tests: test_upstream_first_sequence (5), test_pending_blocks_condemn (13, including the property test), test_rc_sim_end_gate (15). All pass.
   - Runs: 0c4a291 turn 6 and e82df6b turn 8 deliver "restore coach 12 V so it holds 10.5-13.5 VDC through a try" (doc 124 p.10/p.17), with the board/electrode conditional and the tech line 423-775-2131 x7102 (p.3).
   - The run still shows 14 turns because the case is OPEN: the tech can never report an outcome, and a pending [END] is correctly refused.
   - Final sweep: see the pack.
