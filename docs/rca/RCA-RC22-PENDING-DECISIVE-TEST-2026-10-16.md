### RCA: When the deciding test can't be done yet, GD re-asks it instead of giving the manual's repair decision (RC22)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Fix commit 33b4202. No case keys.

1. **Problem statement.**
   - RC22 (Suburban SW6DE DSI, voltage collapses on try) pins doc 124 correctly.
   - edc11db run: GD reached the deciding test (fused battery jumper to the switch feed, doc 124 p.17) with conditional repairs (feed repair p.10 / module board p.17).
   - The tech replied "…isn't done yet—that test is still pending… [END]". The run ended, fix "none".
   - The case file is OPEN: the jumper test is pending with the tech line, and the cause is undetermined.
   - Pass bar: a source repair from the manual.
2. **IS / IS-NOT.**
   - IS: jobs where the deciding test is pending, can't be done, or needs another visit.
   - IS-NOT: jobs whose deciding reading is on record (RC30, RC12), where GD gives the repair.
   - Difference: "pending / isn't done yet" didn't match UNAVAILABLE_RE, so the step was never treated as unavailable, and nothing told GD to give a repair decision.
   - Separately, the harness accepted [END] because ensure_verify had appended "VERIFY:" to a CONDITIONAL repair (fixed in 33b4202, see the harness RCA).
3. **Timeline.**
   - edc11db run 8:02 PM.
   - Checker 8:24 PM, Leader 8:40 PM.
   - Fixed in 33b4202.
4. **Evidence.**
   - 0802509 l.1297 `UNAVAILABLE_RE` has no pending / not done yet / isn't done.
   - l.952 "STEPS THE TECH COULD NOT DO" fires only on that regex.
   - edc11db/RC22.md "Tech final" line.
5. **Causal chain.** No repair = (A) pending not recognized as unavailable AND (B) no rule to answer an unavailable deciding test with the repair decision AND (C) the harness ended on a conditional VERIFY. Systemic root: **the method had no terminal form for "decision depends on a test that can't be done now".**
6. **Why checks missed it.** No test or case had a pending deciding test except RC22, and that run ended early.
7. **Class of failure.** Missing terminal state (decision tree with an unavailable branch input).
8. **Prior incidents.** "Not checked" HELD STEP handling (NOT_CHECKED_RE), and unavailable steps (rule "STEPS THE TECH COULD NOT DO"). Search: UNAVAILABLE_RE|NOT_CHECKED_RE history.
9. **Fix + proof.**
   - UNAVAILABLE_RE adds pending / not done yet / isn't done.
   - PENDING_RULE: when the deciding test is unavailable, GD gives the REPAIR DECISION, i.e. each possible result → the manual's repair with page, plus the shop/OEM tech-line escalation. That is the source repair for an OPEN case.
   - Harness: a pending report never ends a run, and conditional+VERIFY is not terminal.
   - Tests: `TestPendingDecisiveTest`, harness `test_pending_report_is_not_an_outcome`, `test_conditional_repair_with_verify_is_not_terminal`.
   - RC22 on the final SHA is in the pack.

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; class/priors ✔; no case keys ✔; sweep ✔ (pack); regression tests ✔; escape closed ✔; containment n/a.
