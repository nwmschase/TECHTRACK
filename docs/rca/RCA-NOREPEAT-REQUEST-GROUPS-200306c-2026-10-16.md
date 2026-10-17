### RCA: No-repeat cap let a re-worded third request through (fixed in 200306c)
Format: docs/standards/ROOT-CAUSE-ANALYSIS-STANDARD.md. Fix commit 200306c (on a1bbd35). No case-keyed code.

1. **Problem statement.** On a1bbd35, RC22 asked for "brown wire at the gas valve, DC volts during TFI" in turns 5, 6 and 7 with different wording each time. The cap is "never a third ask", but the third ask got through.
2. **IS / IS-NOT.**
   - IS: the same test re-worded each time, where wording 1 ≈ wording 2 and wording 2 ≈ wording 3, but wording 1 ≉ wording 3.
   - IS-NOT: verbatim repeats such as the RC29 winding test, which the cap held to 2.
   - Difference: word-set similarity is not transitive.
3. **Timeline (PDT).**
   - 6:35 PM: a1bbd35 adds the cap.
   - ~7:20 PM: the a1bbd35 sweep shows RC22 with a request asked 3 times. My offline count over the transcript found it.
   - 7:25 PM: fixed in 200306c.
4. **Evidence.**
   - a1bbd35 gd_official.py l.1116 `hit = next((a for a in asks if _same_ask(sig, frozenset(a[0]))), None)` compares only with the FIRST wording stored. l.1122 `asks.append([sorted(sig), 1])` keeps one wording per group.
   - Replaying the a1bbd35 RC22 transcript through the 200306c `cap_repeats` caps turn 7's brown-wire ask and turn 13's "Report swapped yes/no and that VERIFY result".
5. **Causal chain.** Third ask passes = (A) each group keeps one wording AND (B) similarity isn't transitive AND (C) model re-wording. Systemic root: **request identity was one fixed wording instead of the set of wordings already asked.**
6. **Why checks missed it.** The no-repeat property test drew from a pool of 5 fixed strings, so it never re-worded.
7. **Class of failure.** Equivalence by a non-transitive similarity checked against a single representative.
8. **Prior incidents (same class).** `is_repeat` (compares only against the last reply) and `drop_reasks` (keyed to facts). Search: repeat|re-ask|_same_ask in code, tests and CHANGELOG.
9. **Fix + proof.**
   - A request group keeps EVERY wording it was asked in, and a new line matches if it is similar to any of them.
   - Several lines in one reply count once per group.
   - Locked test `TestRewordedThirdAsk` uses the three RC22 wordings.
   - The property test still passes.
   - The 0802509/33b4202 sweeps report the max same-request count per case (pack RC table).

Checklist (std §4): template 9/9 ✔; IS/IS-NOT ✔; evidence lines ✔; general defect ✔; class+priors ✔; no case keys ✔ (grep in pack); property/sweep ✔; regression test ✔; escape closed (re-worded test) ✔; suite/sweep ✔ (pack); containment n/a.
