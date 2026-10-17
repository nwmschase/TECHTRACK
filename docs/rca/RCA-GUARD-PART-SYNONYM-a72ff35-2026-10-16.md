# RCA: condemn guard did not treat "board" and "PCB" as the same part (stray hold line in RC12 on e82df6b)
Commit: a72ff35 (gd_official.py _PART_SYNONYMS, _part_words; test in tests/test_condemn_norepeat_locked.py). 2026-10-16.

### RCA: part-word matching blind to same-component synonyms
1. **Problem statement.**
   - RC12 (Furrion fridge E2) on e82df6b, turn 3. GD said "replace inverter PCB and cooling fan together" (doc 298 p.27) after the tech recorded "Fan voltage at F+/F- was 14.28-10.37 V" in answer to "Probe F+ and F- on the inverter PCB".
   - The guard then rewrote a second line about "the board" into "Before condemning the board, record its isolation reading…". The result was a contradictory reply: replace, and also hold.
   - Expected: a reading taken at the inverter PCB isolates "the board".
2. **IS / IS-NOT.**
   - IS: condemn wording that uses a different name for the same component than the request did ("board" vs "PCB").
   - IS NOT: the "inverter PCB" line in the same reply, which shares the word "pcb" with the request and was released correctly.
3. **Timeline.** Seen in the e82df6b hold-set rerun at 10:4x PM; fixed in a72ff35.
4. **Evidence.**
   - e82df6b-holdset/RC12.md turn 3.
   - Repro: `go.isolation_recorded('the board', ['Fan voltage at F+/F- was 14.28-10.37 V'], ['Probe F+ and F- on the inverter PCB…'])` returned False before the fix and True after.
5. **Causal chain.**
   - _part_words('the board') = {board}. The request words were {inverter, pcb}, so there was no overlap and the part counted as not isolated.
   - Root: **part identity was literal-word only, with no same-component equivalence.**
6. **Why existing checks missed it.** The locked tests always used the same part word in the request and in the condemn.
7. **Class of failure.** "Lexical identity: a synonym of the same component is treated as a different part" (the same family as the edc11db part-words RCA).
8. **Prior incidents.** edc11db (junk or partial part names), and RC12 on 200306c. Searched stored transcripts for "Before condemning the board": only e82df6b RC12.
9. **Fix + proof.**
   - _PART_SYNONYMS = [{pcb, board}]. _part_words adds the whole group when any member is present. This is a general component-class equivalence, not a case key.
   - Test: test_board_and_pcb_name_the_same_part. 147 GD-side tests pass.
   - Final sweep: RC12 row in the pack.
