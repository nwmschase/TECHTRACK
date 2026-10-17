### RCA: GD called No Problem Found while the tech reported the complaint still present and a bypass split pointed at the ceiling control (RC14)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Fix commit 33b4202. No case keys.

1. **Problem statement.**
   - RC14 (Dometic B57915 rooftop A/C, "turns on but won't blow cold"), bdee295 run.
   - Tech turn 2: "[Peacemaker and control bypass both cool.]". Tech turn 11: "…with the ceiling controls it still isn't blowing cold."
   - GD replied "No Problem Found - operating as designed" (bdee295/RC14.md l.121).
   - Expected (case file): the split (bypass cools, ceiling control doesn't) isolates the ceiling thermostat/selector; replace it.
2. **IS / IS-NOT.**
   - IS: complaints that reproduce through one control path while another path works.
   - IS-NOT: true NPF, where the complaint isn't reproduced and readings are normal (RC27 earlier).
   - Difference: rooftop readings were all normal, and the NPF rule keys on "readings normal" without checking that the complaint is gone.
3. **Timeline.**
   - bdee295 run ~7:55 PM.
   - Checker 8:24 PM, Leader 8:40 PM.
   - Fixed in 33b4202.
4. **Evidence.**
   - 0802509 gd_official.py l.882 `NPF_RULE`: "If the verification shows the unit WORKS AS DESIGNED (complaint not reproduced, readings normal)…". Nothing checks it in code.
   - `NO_SPECIAL_TESTER_RULE` (l.855) tells GD not to REQUIRE a Peacemaker. GD then ignored the tech's volunteered bypass result.
   - No code path looks at a bypass/alternate-path result.
5. **Causal chain.** Wrong NPF = (A) NPF allowed on normal readings with no check that the complaint is gone AND (B) no rule turning a path split into an isolation. Systemic root: **NPF was a model judgment with no gate on "complaint still present", and the method had no split-isolation rule.**
6. **Why checks missed it.** NPF tests only covered not-reproduced cases, and the earlier RC14 runs ended at turn 1 on a premature [END] (see the harness RCA), so the miss was hidden.
7. **Class of failure.** Terminal verdict issued against contradicting session evidence.
8. **Prior incidents.** NPF over-call memory (v4.19.4x "NPF_RULE" introduction). The RC27 NPF was correct. Search: NPF|operating as designed in CHANGELOG/tests.
9. **Fix + proof.**
   - `npf_blocked()`: an NPF line is removed and replaced by "Not No Problem Found: the complaint is still present (quote) … run the manual's differentiating check …" when any tech sentence says the complaint is still present.
   - NPF_RULE now states the SPLIT RULE.
   - `split_result_recorded()`: a bypass/direct-power/alternate-control "works" result, in a message naming the part, counts as that part's isolation, so the failing-path part can be condemned.
   - Tests: `TestNpfAndSplit` (held while present; allowed when not reproduced; split isolates).
   - RC14 on the final SHA is in the pack.

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; class/priors ✔; no case keys ✔; sweep ✔ (pack); regression tests ✔; escape closed ✔; containment n/a.
