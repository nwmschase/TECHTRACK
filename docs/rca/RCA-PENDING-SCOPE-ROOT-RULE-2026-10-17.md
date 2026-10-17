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
