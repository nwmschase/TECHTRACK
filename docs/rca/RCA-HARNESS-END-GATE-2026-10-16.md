### RCA: Sim harness ended runs on the simulated tech's [END] before GD had made any call (commits 8149dec, bdee295, 0802509, 33b4202)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Harness only (scripts/gd_rc_sim.py). App code untouched by these commits. No case keys.

1. **Problem statement.** The simulated tech wrote [END] and the harness stopped the run before GD had given any repair, NPF or OEM call.
   - RC14 (a1bbd35): [END] in the complaint itself, run over at turn 1.
   - RC07 and RC17 (a1bbd35): [END] at turn 2 after only a verify request.
   - These runs were reported as "for review" with fix "none". That says nothing about GD.
   - Expected: a run ends only after GD reaches a terminal call, or at the turn cap.
2. **IS / IS-NOT.**
   - IS: sim-tech messages that end on their own initiative ("Stop.", "pending", the complaint text).
   - IS-NOT: [END] after GD's repair plus the tech's verified result (RC30, RC12).
   - Difference: the harness checked only for the presence of "[END]" (edc11db l.79/l.83), never whether GD had made a call.
3. **Timeline.**
   - Present since the harness was written (pre-a1bbd35).
   - Detected by the Checker at 7:24 PM and by Leader at 7:32 PM.
   - 8149dec: gate added.
   - Refinements:
     - bdee295: "VERIFY:" counts as terminal (RC17 had been held to 14 turns).
     - 0802509: "fix is verified" counts.
     - 33b4202 tightens: a VERIFY counts only next to an UNCONDITIONAL repair line; "If …" lines and held lines don't count; a tech message reporting "pending/not done" is never an end.
4. **Evidence.**
   - edc11db gd_rc_sim.py l.79 `if "[END]" in msg: break` and l.83 `if "[END]" in msg and t > 1:`.
   - Transcripts: a1bbd35/RC14.md l.5, RC07.md l.19, RC17.md l.18.
   - RC22 (edc11db) ended on "…isn't done yet—that test is still pending… [END]". It was accepted because ensure_verify had appended "VERIFY:" to a CONDITIONAL repair, which led to the 33b4202 tightening.
5. **Causal chain.** Premature end = (A) the [END] marker alone ended the run AND (B) the role-play model writes [END] when it thinks it's done or stuck. Systemic root: **run termination was owned by the simulated tech instead of by GD's state.**
6. **Why checks missed it.** There were no tests for the harness, and the verdict JSON reports fix "none" with no reason field for how the run ended.
7. **Class of failure.** Test oracle controlled by the simulated party (the harness ends on the actor's say-so).
8. **Prior incidents.** None recorded for the harness. Searched validation debriefs/CHECKER notes for "[END]" and "premature".
9. **Fix + proof.**
   - `end_accepted(msg, gd_replies)`: [END] counts only if some earlier GD reply is terminal (an unconditional repair, NPF, OEM authorization, or a VERIFY next to an unconditional repair) and the tech message is not a pending/not-done report.
   - An early [END] is ignored, written into the transcript as `_harness: early [END] ignored_`, and the tech is told to keep answering.
   - The turn-1 [END] is stripped.
   - tests/test_rc_sim_end_gate.py: 9 tests, including pending and conditional+VERIFY.
   - **Bar check (doesn't lower the bar for GD):**
     - The gate can only make a run LONGER. It never marks anything passed, and the judge prompt and verdict fields are unchanged.
     - Terminal detection only decides whether the simulated tech may stop.
     - Before/after per case is in the pack. No case flipped from a GD fail to a pass because of the gate: RC07/RC14/RC17 went from "no GD call at all" to an actual GD outcome.

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general (no case keys; grep in pack) ✔; class/priors ✔; property/sweep: full RC sweep on the final SHA ✔ (pack); regression tests ✔; escape closed ✔; containment n/a.
