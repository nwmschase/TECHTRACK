# RCA: after an unauthorized tech swap, GD itself directed further condemns (RC20 e77941b, turns 7-13); NO-REPEAT accepted a question as a test answer
Commit: 4aff2a6 (follow-up exemption) + this commit (answer_has_result in cap_repeats; DONE_REPORT_RE pending clear; tests/test_pending_hold_pipeline.py).

### RCA: Leader 11:25 PM checker items (a)
1. **Problem statement.**
   - RC20 on e77941b: the tech replaced cartridges at turn 7 against a GD hold. From then on GD directed the power unit (t7, OEM authorization), both jacks (t10) and the hoses (t11/t12), while the plumbing check and gray-coil unplug were still pending. NO-REPEAT printed `Accepted as reported: "Before I replace that - anything else to check?" … asked twice`.
   - Expected: the hold persists for as long as any isolation test is pending, including after a tech swap. NO-REPEAT routes only to "accept a real result / ask once for the value / shop-OEM", never toward the next replace.
2. **IS / IS-NOT.**
   - IS: the e77941b RC20 turns 7-13 replies; each slipped line contains the word "verify".
   - IS NOT: the pending list. Replay shows `pending_isolation_tests` stayed populated on all 14 turns, so the hold did NOT "drop" after the swap. The tech's "remain pending" kept it alive.
   - IS NOT: cap_repeats emitting a replace. It runs after the hold, and its text has no replace verb. It did, however, *accept a question* as an answer: a separate defect in the same exchange.
3. **Timeline.** e77941b hold set 11:19 PM, then the checker at 11:25 PM. Root (verify exemption) fixed in 4aff2a6 at about 11:26 PM. NO-REPEAT and done-report defects found by the new end-to-end test, 2026-10-17 00:15 PT.
4. **Evidence.**
   - e77941b-holdset/RC20.md turns 5-13.
   - The replay script (pack §5) gives 0 replace lines surviving at 4aff2a6.
   - New end-to-end test: official_turn with a stubborn fake model replaying the slipped lines through a tech swap and repeated "anything else to check?".
     - Before this commit: NO-REPEAT emitted `Accepted as reported: "<question>"`.
     - With the 4aff2a6 hold alone, a real "Plumbing check done: no leaks …" did not clear the pending entry (an over-hold that can loop).
5. **Causal chain.**
   - Swap reported while tests are pending; GD writes replace lines that contain "verify". The follow-up exemption matched "verify" anywhere, so the lines passed; root fixed in 4aff2a6 with `_follow_up_line`.
   - Tech asks "anything else to check?" twice; cap_repeats treats the last tech message as the answer whatever it is. Systemic root: **NO-REPEAT had no notion of "answer holds a result"**.
   - Over-hold: the pending-clear only recognized `_is_result` sentences, not "<test> done: <outcome>".
6. **Why existing checks missed it.** The pending-hold tests were line-level. Nothing walked official_turn across a swap. The NO-REPEAT tests used "normal/OK" answers only.
7. **Class of failure.** "Guard state machine: an escape route (exemption or acceptance) that bypasses the barrier on wording alone."
8. **Prior incidents.**
   - RC20 on 215fce8 and e77941b; RC22 golive-1431 and final-fea86b4 (pending loops).
   - "Accepted as reported: <question>" appears in RC20 e77941b turns 8, 9, 13, 14 and in RC20 215fce8 turns 10, 13, 14.
9. **Fix + proof.**
   - 4aff2a6: `_follow_up_line` (exemption only at the start of a line).
   - This commit:
     - `answer_has_result()` (a test result, a "normal/OK" outcome per the RC29 lock, or a reading with units; never a question or a pending report). When the capped answer has no result, cap_repeats says "No result is recorded … do it once and send the reading, or call the shop/OEM tech line … No part is replaced on an unrecorded test" instead of "Accepted as reported".
     - `DONE_REPORT_RE`: "<test> done/completed: <outcome>" clears the matching pending entry.
   - Tests: tests/test_pending_hold_pipeline.py (5 tests):
     - end to end through official_turn across a tech swap;
     - a property test over 5 slipped wordings × repeated questions;
     - a recorded result releases the hold;
     - answer_has_result unit cases;
     - capped-question routing.
   - The locked RC29 NO-REPEAT tests still pass unchanged ("normal/OK" stays accepted). 159 GD-side tests pass.
   - The final sweep is in the pack.
