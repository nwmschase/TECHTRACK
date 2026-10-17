### RCA: The simulated tech refused GD's correct part when GD named it differently, and re-asked forever (commits 8333d14, e75ad8b)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Harness only (TECH_SYS in scripts/gd_rc_sim.py). No case keys.

1. **Problem statement.** On edc11db, RC12 ran 14 turns.
   - GD directed "replace inverter PCB (AL 2021149633) + cooling fan (AB)" at turn 3–4, matching the manual's part names.
   - The case file says "rear control board and freezer evaporator fan".
   - The sim tech answered "Before I replace that - anything else to check?" for 10 turns, so the run never reached the verified repair.
   - Expected: a real tech recognizes the same component under the manual's name. A wrong part leaves the complaint present.
2. **IS / IS-NOT.**
   - IS: the Fix part named by function/part number in the manual vs by location in the case file.
   - IS-NOT: names that match literally (RC30 fuse, RC29 rooftop unit).
   - Difference: the instruction "If GD tells you to replace a part NOT in the Fix…" was applied by literal string.
3. **Timeline.**
   - Present since the harness was written.
   - Seen in the edc11db sweep (~8:05 PM).
   - 8333d14 (rename rule plus once per part) and e75ad8b (a non-Fix replacement leaves the complaint present).
4. **Evidence.**
   - edc11db/RC12.md l.48–154: "Before I replace that…" ×11.
   - TECH_SYS (edc11db) l.45 had no alias or limit rule.
5. **Causal chain.** Loop = (A) literal part matching AND (B) no limit on the challenge. Systemic root: **the simulated tech's knowledge model had no notion of component identity across naming schemes.**
6. **Why checks missed it.** Earlier runs used names that matched literally.
7. **Class of failure.** Simulated actor less competent than the real role (identity by string).
8. **Prior incidents.** RC22 (a1bbd35) "Before I replace that" ×3 against board 520814, where the case cause is undetermined; that behaviour was correct there. Search: "Before I replace that" across the sim transcripts.
9. **Fix + proof.**
   - A differently-named part that is the same component as the Fix part counts as the Fix.
   - "Anything else to check?" is asked once per part.
   - If GD repeats the same replacement with no new check, the tech does it and reports **the complaint is still present** unless that part is the Fix.
   - **Bar check:** this makes a wrong-part call visibly FAIL (the complaint persists) instead of looping silently. A correct part under another name passes only if it is the same component per the case file, which the judge (unchanged) still checks against the case file. The rename rule is the only easing; it matches what a real tech does.
   - Before/after: RC12 went from 14 turns (loop) to 3 turns (repair, verified).

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; class/priors ✔; sweep on the final SHA ✔ (pack); regression: harness tests cover the gate. TECH_SYS is an LLM prompt, verified by the full sweep, not a unit test (noted as a limitation); containment n/a.
