# RCA: sim harness never ends a run after a verified repair (RC19/RC30 at 14 turns, d416c94 sweep); sim tech did conditional repairs whose condition was unmet
Commit: 0c4a291 (scripts/gd_rc_sim.py REPAIR_VERB_RE, CLOSE_OUT_RE/RESOLVED_RE/STILL_RE in end_accepted, TECH_SYS conditional-repair line; tests/test_rc_sim_end_gate.py +6). 2026-10-16.

### RCA: [END] gate too strict for adjustment repairs and close-out confirmations
1. **Problem statement.**
   - On d416c94, RC30 (fuse) reached the fix and the tech verified cooling at turn 4. RC19 (thermocouple reposition) verified at turn 5. Both then ran to the 14-turn cap with "early [END] ignored" on every turn, so their turn counts were inflated.
   - Expected: the run ends once GD has given the repair and the tech reports it verified.
   - In RC22 the sim tech replaced the gas valve under GD's "If voltage still drops with a known-good source, replace the valve" while the known-good-source test was pending.
2. **IS / IS-NOT.**
   - IS: repairs phrased with verbs the gate didn't know ("bend each thermocouple so the tip sits in the flame", RC19), and close-outs phrased as conditional on a result the tech then reports ("If X (cold, light OK): complaint resolved, no further action", RC30).
   - IS NOT: RC17, RC29 and RC14, which ended normally because they used "reorient … then retest", "submit to the OEM" or "replace". The gate knew those words.
3. **Timeline.**
   - The 8149dec gate stops premature [END]s. bdee295 and 0802509 loosened it for VERIFY lines and "fix is verified". 33b4202 tightened it: VERIFY counts only next to an unconditional repair verb, and conditional lines are excluded (closing the RC22 pending loophole).
   - That tightening also excluded RC30's conditional close-out and RC19's "bend". Detected in the d416c94 sweep at 9:25 PM.
4. **Evidence.**
   - Transcripts: d416c94/RC30.md lines 44-183 (26 ignored [END]s after "Complaint resolved") and d416c94/RC19.md lines 37-175.
   - Code: gd_terminal drops lines starting "If" and requires REPAIR_VERB_RE, which lacked bend/reposition.
   - Replay of every d416c94 transcript through the new end_accepted: RC30 ends at turn 4, RC19 at turn 5, RC17 at turn 6. RC22, RC13, RC14, RC16 and RC23 do not end on any early [END] (unchanged).
5. **Causal chain.**
   - Trigger: the tech's resolved [END] after GD's close-out line.
   - Condition: gd_terminal treats every "If…" line as non-terminal, including a close-out whose condition the tech has just reported met. Its verb list also lacked reposition/bend.
   - Systemic root: the gate judged GD's wording alone, never GD's close-out together with the tech's reported outcome.
   - Separate root (tech): TECH_SYS had no rule for conditional repairs, so the tech treated "If X, replace Y" as an order.
6. **Why existing checks missed it.** tests/test_rc_sim_end_gate.py covered early, pending and conditional-repair cases, but had no case of a close-out after a reported resolution and no reposition-verb repair.
7. **Class of failure.** "Session-end detection keyed on directive wording only (no pairing of GD's close-out with the tech's reported result)."
8. **Prior incidents.** Same family as 8149dec (too loose, RC07/RC14/RC17 premature), bdee295/0802509 (too strict, RC17 held to 14) and 33b4202 (pending accepted). See RCA-HARNESS-END-GATE-2026-10-16.md. Each has a test in test_rc_sim_end_gate.py, and all still pass.
9. **Fix + proof.**
   - REPAIR_VERB_RE gains re-position, bend and re-aim.
   - end_accepted also accepts [END] when some GD reply has a close-out line (complaint resolved / close the job / no further action) AND the tech's [END] message reports resolution (resolved / fixed / stays lit / cooling / verified) AND it is not pending and not still-present.
   - TECH_SYS: a conditional repair is done only when the case file shows its condition was met.
   - The bar is not lowered: a pending or still-present report never ends a run (tests), and a close-out without a resolution report doesn't either.
   - Tests: 6 new tests, 15 in the file, all pass.
   - Replay proof above. Full sweep on 0c4a291: see the pack.
