# RCA: a pending isolation test was text, not a scope, so replace/repair paraphrases slipped (RC20) or unrelated proven repairs were held (RC04)
Ruling: Leader 2026-10-17 1:45 AM on PR #92 @174d094 (5c + 5e combined; 5e options (i) more phrasings and (iii) sim change rejected).
Commit: see PR #92 head (this commit adds `PendingTest`, `pending_tests`, `components`, `complaint_path`, `decisive_result`,
`scope_gate`, `structural_reply` in gd_official.py, wired into `official_turn` in place of `hold_while_pending`).

### RCA: pending-test hold keyed on reply wording instead of the test's component scope
1. **Problem statement.**
   - 174d094 RC20: while the plumbing check and the gray-coil unplug were still pending, GD emitted "Repair both front jacks as a
     matched pair at cylinder/assembly level ..." (no replace verb), the hold did not catch it, and the sim tech swapped the jacks.
   - 174d094 RC04: the tech recorded a voltage-drop result across the 30A charge-path breaker, but the hold blocked the breaker
     replacement because an unrelated controller-harness voltage was pending, so RC04 never reached its fix.
   - Expected: a replace/repair line for X goes out only if X has its own decisive result and no pending test's scope contains X.
     While a pending test's scope covers the complaint path, the reply is the pending test + tech line + safety only.
2. **IS / IS-NOT.**
   - IS: replies where a pending test exists AND the model phrases a repair without a CONDEMN/REPLACE verb (RC20 174d094 t8/t10:
     "Repair ... at assembly level"; e77941b "commit to the repair"), and replies where the pending test is about a different
     circuit than the proven part (RC04 4aff2a6 t7 breaker).
   - IS NOT: sessions with no pending test (20 of 22 RCs on 174d094; replay shows 0 mode changes there), and pending sessions whose
     replies used a replace verb (held correctly since e77941b).
   - Distinguishing factor: the barrier inspected the reply's WORDS (replace-verb regex) and treated "a test is pending" as a single
     global boolean. It never knew WHICH components a test isolates. Hence the two symmetric failures: unknown wording leaks
     (under-hold), and unrelated parts are held (over-hold).
3. **Timeline.**
   - e77941b (2026-10-16 11:19 PM PT): every replace held while anything is pending; 4aff2a6, 642b658 and 174d094 each closed
     one more wording path (verify exemption, NO-REPEAT, hold line capped, orphan install steps).
   - 174d094 final sweep (2026-10-17 1:40 AM PT): RC20 1 swap via the "Repair ... assembly level" paraphrase; RC04 held (Leader 5c).
   - Leader ruling 1:45 AM: build the structural root rule. Implemented 2026-10-17 1:50-2:30 AM PT.
4. **Evidence.**
   - Transcripts: gd-official-sim-2026-10-16/174d094/RC20.md lines 107 and 162; 4aff2a6/RC04.md turns 5-7; 0c4a291/RC04.md turn 7
     (the breaker fix the strict hold removed).
   - Code at 174d094: `pending_isolation_tests()` returns strings; `hold_while_pending(reply, pend)` drops lines matching
     `REPLACE_ANY_RE`/`CONDEMN_RE`. There is no per-component state.
   - Repro: tests/test_scope_root_rule.py::test_rc04_breaker_outside_scope_reaches_its_fix fails at 174d094 (the breaker held).
     The RC20/RC22 locked tests fail there too (no structural reply).
   - Replay (/tmp/replay_scope.py logic, recorded in the pack): 796 stored turns from 6 sweeps.
5. **Causal chain to systemic root.**
   - Proximate trigger (RC20): the model writes the repair without a replace verb. AND the hold matches verbs only. AND the sim tech
     acts on any repair instruction.
   - Proximate trigger (RC04): an unrelated test is pending. AND the hold is global. So a proven, out-of-circuit part is held.
   - Systemic root: **a pending test had no structure.** It was a sentence, so the guard could only (a) look for words in the reply
     and (b) decide all-or-nothing. Neither "is X inside what that test isolates?" nor "does X have its own result?" could be asked.
6. **Why existing checks didn't catch it.**
   - The tests were wording-indexed: each new paraphrase became a new regex and a new test (5 rounds tonight). There was no
     property over arbitrary replace/repair phrasings, and no test where an unrelated, proven part had to survive a pending hold.
7. **Class of failure.** "Barrier keyed on output wording instead of domain state (scope), producing both leaks (unseen
   paraphrase) and over-blocking (unrelated parts)."
8. **Prior incidents of the same class.**
   - RC20: 215fce8 (met conditional + "commit to the repair"), e77941b (verify-exempted lines), 642b658 (hold line capped, orphan
     "After install"), 174d094 ("Repair ... assembly level").
   - RC04: 4aff2a6, 642b658 and 174d094 (strict hold kept the breaker from its fix; Leader 5c).
   - RC22: pending loops in golive-1431, final-fea86b4, 215fce8 (board/valve conditionals while the brown-wire test was pending).
   - Searched: all docs/rca/*.md for "pending" and "hold"; all sweep transcript dirs for "Hold all part replacement".
9. **Fix + proof.**
   - **Structured pending test** (`PendingTest`: text, request lines, scope, anchor). The scope is the components named in the
     not-done report plus GD's own request for that test. The request is fixed to the GD message right before the report, else the
     first later one that asked, else the nearest earlier one, so a later rewording cannot widen or narrow it. The scope is widened
     to the whole assembly/circuit when it names 2+ members unique to that assembly (hydraulic; gas ignition). The pinned manual
     section can complete an assembly the request already touches, but it never adds a stray noun (e.g. the symptom in a condition
     clause).
   - **Complaint path** = components in the complaint plus the appliance the pinned manual covers, widened to their assembly.
   - **Structural mode** (some scope ∩ complaint path): the reply is rebuilt from scratch as safety line(s) + a hold header +
     GD's own request lines for the test (non-replace lines only; after 2 asks, the record-or-tech-line text) + the tech-line
     sentence + one contact line. The model's other lines are discarded, so **no wording detector** is involved. NO-REPEAT and the
     VERIFY appender are skipped for these replies.
   - **Gate mode** (no scope covers the complaint path): a replace/repair line for X survives only if `decisive_result(X)` (a tech
     sentence naming X with a meter reading, open/jumper/bypass, a test outcome, or a voltage drop; never a question, a not-done
     report, or a swap report) AND X is in no pending scope. Whole-unit or unidentifiable targets count as covered by any pending
     test. Identifying a repair line needs `_repair_verbs` (the verb, not the noun "the isolated repair"). That is grammar for
     finding the directive, not a list of phrasings to block.
   - No case keys: the diff contains no RC id, brand, model, doc id or part number (grep of the added lines: 0 hits). The
     component lexicon and the two assemblies are general RV trade vocabulary.
   - **Tests (tests/test_scope_root_rule.py, 9):**
     - locked RC04 (breaker reaches its fix; scope = controller/harness/battery/connector; breaker decisive);
     - locked RC20 (front jacks/cartridges/hoses blocked, structural, gray-coil test goes out; scope ⊇ jack, hose, cartridge,
       solenoid, valve, coil, manifold);
     - locked RC22 (board/valve blocked, structural, Suburban tech line survives);
     - structural repeat cap;
     - answered test releases its part;
     - **property over 400 random end-to-end sessions:** an in-scope part is never replaced, and an unrelated part with its own
       decisive result is never blocked;
     - unit-level gate property (400).
     The property test found one generator flaw (it recorded a reading on the pending test's own part, which legitimately
     answers the test); fixed in the generator, and the release is now asserted by its own test.
   - test_pending_hold_pipeline::test_recorded_result_releases_the_hold updated to the ruling: after the results are recorded the
     structural hold ends, and the cartridge then needs its OWN decisive result (a coil-unplug observation is not one).
   - GD-side: 174 passed + nav_and_send 7/7 (keys stripped).
   - **Replay over 796 stored turns:** mode changes only in RC20 and RC22 (every SHA), RC23 642b658 (bracket-squaring test pending
     → structural, the squaring steps go out) and RC01 642b658 t3 (harness repair held while the harness reseat is pending:
     correct). The first draft also held RC11 t12 ("Repair is already isolated", noun use) and turned RC08 642b658 t11+ structural
     on a post-repair "that check is still pending". Both fixed (`_repair_verbs`; function and post-repair words carry no scope)
     before commit.
   - Final 22-case sweep, full suite and navsend-3x on the final SHA: see the PR92 hold pack, root-rule section.

### Section-4 checklist
| Item | Result |
|---|---|
| Full template, 9 fields | PASS |
| IS / IS-NOT with working cases, cause explains the difference | PASS (20 RCs with no pending test unchanged; replace-verb lines were already held) |
| Every causal link cites evidence | PASS (transcript lines, 174d094 code, failing locked tests at 174d094, replay) |
| Chain reaches a general logic defect | PASS (pending test had no structure/scope) |
| Class named, prior incidents searched and listed | PASS |
| No new case keyed on brand/file/page/model/test ID | PASS (grep of added lines: 0) |
| Sweep or property test on the whole class, before/after | PASS (400+400 property sessions; 796-turn replay; 22-case sweep before 174d094 / after final) |
| Regression test for each prior incident | PASS (RC20, RC04, RC22 locked; prior RC20 wording tests kept and passing) |
| Check that would have caught it originally | PASS (property: any phrasing of an in-scope repair is dropped in structural mode) |
| Full suite and sweep show zero new regressions | see the pack root-rule section (final SHA results) |
| Containment labeled | N/A (root fix; no containment) |

## Addendum 1: c249638 sweep, the gate read a location phrase as a target (RC04) and a noun "repair" as a directive
- **Problem.** c249638 RC04, last turn: GD wrote "Repair already isolated: the 30A breaker in the isolator-to-battery lead …".
  The gate held it as "inside the scope of the pending test ('Battery amp-draw/Ah (capacity) test is still pending')". Transcript:
  gd-official-sim-2026-10-16/c249638/RC04.md line 162. (On that run GD never directed the breaker R&R in turns 4-9; the sim tech
  swapped it at turn 8. That part is model variance, not the gate. No root-rule hold fired before turn 14.)
- **IS / IS-NOT.** IS: a target line whose head part is out of scope but which names an in-scope component in a location phrase
  ("in the isolator-to-battery lead"). IS NOT: the locked RC04 line "Replace the 30A breaker between …", because `condemned_parts`
  returned just the breaker there.
- **Root (general).** (1) When `condemned_parts` found nothing, the gate fell back to *every* component on the line. (2)
  "Repair already isolated" was classed as a verb. (3) A conjunction ("module board … and the gas valve") yielded only the first
  part, an under-hold that the new property test exposed.
- **Fix.** `target_components()`: the target is the verb's object phrase (repair verbs and each unnegated replace verb), with a
  leading phrasal particle stripped ("swap in"). It is cut at the first location/manner preposition (in/at/between/as/…), then
  split on and/,/plus/& with every conjunct counted. A sub-object with no component of its own ("repair its lugs") belongs to the
  line's named part. "already/done/isolated/proven/confirmed" after "repair" mark the noun.
- **Tests (+5):** location phrase not a target; conjunctions all count; phrasal/noun uses; the c249638 RC04 shape (the battery
  test's scope excludes the breaker; the breaker line is not held); property over 400 random sessions (an unrelated part with an
  in-scope location phrase is kept; a conjunction including an in-scope part is held). All 5 fail on c249638 and pass now. GD-side
  179 pass.
- **Replay:** 857 stored turns (adds the c249638 sweep). Only RC20/RC22 (every SHA), RC23/RC01 642b658 and RC08 c249638 t5
  (harness-at-motor reading pending, on the complaint path; GD still reached the panel fix at t7 on that run) change.

## Addendum 2: ea06f7e sweep, RC22 swap (a missing measurement was not recognized as a pending test)
- **Problem.** ea06f7e RC22, T6-T7: the tech wrote "I don't have a separate brown-at-coil number" (the decisive brown-wire test,
  manual p.17). GD directed "Replace the DSI module board", repeated it after the tech's pushback, and the tech swapped the module
  (1 swap; the complaint stayed present). Transcript: gd-official-sim-2026-10-16/ea06f7e/RC22.md lines 65-87. Must-hold "RC22
  blocked" failed on that run.
- **IS / IS-NOT.** IS: not-done reports phrased as a missing value ("don't have … number/reading"). IS NOT: "didn't get a
  separate … voltage" (RC04) or "… still pending" (RC20/RC22 other runs), which were recognized. On those runs RC22 went
  structural.
- **Root (general).** The pending-test detector (`NOT_DONE_RE` + `PENDING_TEST_WORD_RE`) had no "do/did not have <measurement>"
  form, so no `PendingTest` existed. With no pending scope, the gate's condition (2) held vacuously, and the board's own reading
  ("yellow at the board ~-1.2 V") satisfied condition (1). The scope rule itself worked as written. Its input, the pending-test
  list, was incomplete. The same input gap affected the 174d094 hold (replay: identical outcome on 174d094 code).
- **Fix.** `NOT_DONE_RE`: "don't/do not/didn't/haven't have|got" when a measurement noun (reading, number, value, measurement,
  result, voltage, ohm) follows within the clause. The noun is matched by lookahead, so the test words stay in the signature.
  Part/model/serial numbers are excluded. `PENDING_TEST_WORD_RE` adds number/value/measurement under the same exclusion.
- **Tests (+2):** not-done shapes (3 positive, 3 negative, incl. "part number", "model number"); locked RC22 ea06f7e T6 session
  through official_turn (the DSI module board line is blocked, structural). Both fail on ea06f7e and pass now. GD-side 181 pass.
- **Replay:** 1,126 stored turns (8 sweeps). The new detector changes only ea06f7e RC22 (structural from T6). Every other mode
  change is identical on ea06f7e code.

## Addendum 3: 854ef47 sweep, RC22 board condemn, a GD FAILURE of rule condition (1) (Leader 3:30 AM 2026-10-17)
- **Problem.** 854ef47 RC22, T8-T9 (gd-official-sim-2026-10-16/854ef47/RC22.md lines 79-97): after T4-T8 tech answers of the
  form "<test> isn't in the notes; looks normal/OK", GD said "Replace the DSI module board" (T8, cited p.31, the parts list) and
  "Nothing else on this unit ... spark/valve/orifice/electrode/connectors already OK — replace the DSI module board" (T9, cited
  p.17). The tech swapped the board and the complaint stayed (1 swap). No pending scope covered the path at T8. Leader ruling:
  this is a GD failure of condition (1), not case design. Condition (1) must hold whether or not a pending scope exists. Options
  (a) (b) (c) rejected.
- **IS / IS-NOT.** IS: a condemn reached by eliminating other parts on normal/OK answers (valve coil 32 ohm, brown/WC/spark/
  orifice/connectors "OK"), plus a reading taken AT the board ("yellow at the board is 0 V / -1.2 V"). IS NOT: RC04 (drop
  recorded ACROSS the breaker), RC30 (fuse continuity OPEN), RC13 (thermostat bypassed, furnace runs), RC07 (fan motor shaft
  locked). Each of those has a failing result that belongs to the condemned part. Also IS NOT: RC12 (manual flowchart p.27 ends
  on "Replace the inverter PCB and fan"), RC08 (BAL 5.1 p.1 "the user panel will need to be replaced" after 12 V and harness
  are confirmed), RC29 (OEM authorization block).
- **Root (general).** Condition (1) was implemented as `decisive_result()` / `isolation_recorded()`. Both accept ANY tech sentence
  that names the part and holds a reading or a test outcome. Normal/OK outcomes and readings taken at the part (location) were
  included. So "a recorded result" stood in for "B's own failing result". The gate was also only reached when a pending test
  existed (`scope_gate`). With no pending tests, only the older `unproven_condemns` ran, and it has the same acceptance.
- **Fix (structural, no wording detector on the reply).** New `condemn_gate()` runs on every non-structural reply, with or
  without pending tests. For each replace/repair target B (its head noun: `target_heads`, e.g. "first-jack motor" -> motor),
  the line survives only with one of:
  (i) `own_failing_result`: a tech result sentence that BELONGS to B and FAILS. Ownership is the component at the head of the
  sentence, cut at the first location preposition, or the object of a test verb ("drop across X", "ohmed X"). A clause with no
  owner inherits the owner of the clause before it in the same sentence ("15A fuse is in the holder; continuity is OPEN"). A split
  result counts for the part that was bypassed ("thermostat bypassed ... furnace operates"). Direct power TO a part is that part's
  pass. A normal/OK result is a pass: it rules its owner out and never condemns another part. The complaint message is not a test.
  (ii) `manual_elimination_cite`: a page the reply cites holds a manual sentence that replaces B at the end of a decision path,
  and at least one normal/OK result is recorded. "Replace B if found to be defective" asks for B's OWN test, so it does not count.
  (iii) OEM path: the line sits in, or routes to, the OEM authorization request.
  A conditional "If X, replace B" survives only when X is B's own failing outcome. X must name no other part, and it must be a
  failing condition, a split test of B, or a result naming B. "If 30-50 ohm, replace the board" and "if valve and supply are
  good, replace the board" are held. A held line becomes "Hold all part replacement for the B: no failing result of its own is
  recorded. A normal/OK result on another part rules that part out; it never condemns the B." It also carries the manual's own
  test for B when the section has one ("test module board with field tester") and the OEM path. The test is asked at most twice.
  The RC29 lock is kept: `isolation_recorded()` still counts normal/OK as A's recorded result for the hold and NO-REPEAT logic.
- **Tests (tests/test_condemn_basis_rule.py; 22 in addendum 3 + 3 in 3b):** install-procedure-is-a-condemn (RC18 a4aef6c run 3 T5 verbatim: "Engage the new motor..." with no replace verb, held) and output-failure-with-good-input (RC02 a4aef6c own; RC22 feed collapsing, not own) added after the a4aef6c partial sweep; locked RC22 854ef47 T1-T9 verbatim (no pending scope at T8; the T8 and T9
  board condemns are held; the hold asks the field-tester test; the board has no own failing result; p.17 is not an elimination
  path; a recorded board failure releases the line). Basis paths: RC29 lock, OEM block, RC12 p.27 elimination, RC04/RC30/RC13/RC07
  own failing results, direct power is a pass, and conditionals. Property tests: 600 random sessions (no condemn of B survives
  without an own failing result; normal/OK on any part, B included, and readings AT B never condemn B; held >150, kept >100); 200
  sessions where the OEM and elimination paths survive. The locked RC22 tests fail on 854ef47 and pass now.
- **Replay (6 stored sweeps, 854ef47 back to 4aff2a6):** held on every SHA: the RC22 board condemns (854ef47 T8/T9, ea06f7e T6/T7,
  215fce8 conditionals); RC22 coach-feed conditionals with no own result ("If it lights, repair the coach feed"); RC20 matched-
  pair repairs; RC18 direct motor line (the OEM "Requested authorization" line next to it is kept); RC13 cable-after-thermostat
  conditional; Unity board direct lines on older SHAs (854ef47 used the OEM block). Kept with their basis: RC04 breaker (own:
  drop across), RC07 PCB + fan motor (own), RC08 panel (elimination p.1), RC12 PCB + fan (elimination p.27), RC13 thermostat (own
  split), RC23 bracket (own), RC28 jamb/column assemblies (own: motor/sprocket flex, assembly), RC29 (OEM), RC30 fuse (own).

## Addendum 3b: RC20 terminal (Leader 3:30 AM item 2)
- **Problem.** 854ef47 RC20 T10-T14: the same structural hold was sent five times, even after the tech reported the shop/OEM call
  ("Already called Lippert/Brinkley ... still pending"). It named the pending test and said "call the shop/OEM tech line", but it
  looped. It did not end. Leader: accepted ONLY if the final reply names the pending tests blocking progress AND gives the
  shop/OEM escalation step; if it stops or loops, add a general rule.
- **Root.** `structural_reply` had no terminal state. After the ask cap it repeated "asked twice ... call the tech line" every turn.
- **Fix (general).** When every covering pending test has been asked twice, or the tech reports the shop/OEM call is made, the
  structural reply is the ESCALATION SUMMARY. It holds: session parked; a hold line; each blocking pending test with its scope;
  the results recorded so far; the shop/OEM step with the tech-line contact (from the reply, the pin, or the manual). The sim
  harness ends a run on the ESCALATION SUMMARY ("session parked"). This is general and keyed on no case.
- **Tests (+3):** RC20 854ef47 walked verbatim through all 14 tech turns ends on the summary, which names the plumbing/gray-coil
  test and the shop/OEM tech line; the summary comes as soon as the tech reports the call; property over 100 random pending
  sessions (no summary on the first ask, summary at the cap naming the test and the tech line).

## Addendum 3c: a4aef6c partial sweep (stopped and re-based)
- **RC18 run 3 (a4aef6c), T5:** GD gave a full install procedure for a "new motor" ("lift the motor off", "engage the new motor's
  drive coupler") with no replace verb. The tech swapped the motor and the complaint stayed (1 swap). Root: condition (1) was
  keyed on replace/repair verbs, and an install procedure is a condemn without one. Fix: every component a directive line calls
  "new" is a replace target of that line, and "lift/remove the X off/out" is a step of that procedure. Both are held when X has no
  basis. Negated mentions ("do not replace the new jack yet") are not targets.
- **Own failure at the output (structural refinement of (i)).** A part's output read failing (no voltage, open/floating) while its
  input/feed is recorded good, and no feed reading fails, is that part's own failing result. This is the manual's standard "good
  in, bad out" test (RC02 a4aef6c X270D). With a failing feed (RC22: supply collapses with the board in circuit) an output
  reading is never the part's own failure.
- **RC04 (a4aef6c, 5 turns):** the complaint did not reproduce, and GD closed "no-trouble-found" after calibration. No hold fired.
  This is the intermittent-NPF gap, issue #94 (Leader item 5). It is not caused by condition (1).
