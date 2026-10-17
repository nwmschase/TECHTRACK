### RCA: Condemn guard misread part names, and the no-repeat cap swallowed the repair itself (fixed in edc11db)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Fix commit edc11db (on 200306c). Follow-up refinements in 33b4202. No case-keyed code.

1. **Problem statement.** The 200306c RC12 run took 14 turns with 6 identical requests:
   - GD held "Before condemning the instead…" (a junk part name) and "…the inverter pcb part al fully seated…".
   - It did not accept "Isolation at that board looks OK".
   - After the repair was given, the no-repeat cap replaced the repair/VERIFY lines with "Accepted as reported…". The sim tech kept asking.
   - Expected: condemn after the F+/F– reading and E2 after reset, then the repair and VERIFY stay intact.
2. **IS / IS-NOT.**
   - IS:
     - Part phrases with trailing qualifiers ("… instead", "… Part AL fully seated").
     - Answers naming the part by a modifier word ("inverter", "board") rather than its head noun ("pcb").
     - Result words "isolation", "voltage".
     - Repair/VERIFY lines that contain report/check words.
   - IS-NOT: RC29/RC30, where part phrases were clean nouns and no repair line was re-asked.
   - Difference: the part phrase parser and the request detector treated every line with a test verb as a test request, and every trailing word as the noun.
3. **Timeline.**
   - 200306c run, ~7:45 PM: RC12 has 14 turns and 6 repeats.
   - edc11db, ~7:55 PM: fixed.
   - 33b4202: words split only after the first word ("both motor…" had produced an empty noun); position words (front/lead/left…) never identify a part.
4. **Evidence.**
   - 200306c gd_official.py l.1026 `core = re.split(r"\s(?:in|on|at|of|from|inside|behind|under|near|for)\s", …)`: no cut at "part/fully/instead/together"; `_part_heads` takes the last word.
   - TEST_RESULT_RE has no isolation/continuity/volt.
   - `cap_repeats` l.1108 has no exemption for the repair line.
   - Transcript: gd-official-sim-2026-10-16/200306c/RC12.md l.39, l.99, l.135.
5. **Causal chain.** RC12 loop = (A) junk/over-long part names AND (B) the guard reading only the head noun AND (C) the cap treating repair/VERIFY as requests, with the sim tech re-asking (harness, see the harness RCA). Systemic root: **the guard and the cap parsed free text with no notion of "part phrase boundary" or "direction vs request".**
6. **Why checks missed it.** The unit tests used clean part phrases, and no test re-sent a reply containing the repair.
7. **Class of failure.** Free-text classifier with no boundary/role model (noun phrase, request vs direction).
8. **Prior incidents.**
   - RC29 loop (the guard recognizer was too narrow).
   - 200306c (request identity).
   - Search: _part_heads|cap_repeats changes.
9. **Fix + proof.**
   - Part phrase cut at part-number/qualifier words.
   - `_part_words` holds every identifying word, minus position words. Mechanical observation uses the head noun only (33b4202).
   - Result words: isolation/continuity/volt.
   - Repair/VERIFY/reconnect lines are never capped.
   - Locked tests: `TestRepairLinesAreNotRequests` (RC12 shape), plus the junk-name cases in the guard tests.
   - RC12 on e75ad8b: 3 turns. The final sweep is in the pack.

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; class/priors ✔; no case keys ✔; property/sweep ✔; regression tests ✔; escape closed ✔; suite/sweep (pack); containment n/a.
