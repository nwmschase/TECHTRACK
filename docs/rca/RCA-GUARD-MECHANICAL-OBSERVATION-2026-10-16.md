### RCA: The condemn guard had no rule for mechanical failures, where observation is the manual's own test (Leader 8:23 PM call c)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Fix commit 33b4202. No case keys.

1. **Problem statement.** The guard (a1bbd35–0802509) accepted only meter values or test-result words. For mechanical failures (binding, flex, crooked travel, drift) the manual's check is an observation, so a correct condemn could be held or passed only by accident.
   - The RC28 e75ad8b condemn passed only because the whole-unit/OEM line wording matched.
   - S20 coil walks passed because "valve … tests good" matched "cartridge valve".
2. **IS / IS-NOT.**
   - IS: mechanical failure modes recorded by observation against a part.
   - IS-NOT: electrical parts with a manual meter test (fuse, board, coil), which must keep a reading.
   - Difference: whether the pinned manual gives an electrical test for that part.
3. **Timeline.** RC28 review 8:23 PM; implemented in 33b4202.
4. **Evidence.**
   - 0802509 l.1093 `unproven_condemns` → `isolation_recorded` only (ISOLATION_RE / TEST_RESULT_RE).
   - No observation path.
5. **Causal chain.** Wrong hold/pass = (A) the evidence model was electrical-only AND (B) the part-word overlap was broad. Systemic root: **evidence type wasn't matched to failure type.**
6. **Why checks missed it.** All guard tests were electrical.
7. **Class of failure.** Evidence gate with a single evidence type for multiple failure modes.
8. **Prior incidents.** RC29 loop (gate too narrow), edc11db part words (gate too broad). Search: guard RCAs.
9. **Fix + proof.**
   - `mechanical_observation_recorded()`: a sentence with a mechanical failure word (MECH_OBS_RE) that names the part's OWN noun (head word, not the system: "jacks drift" ≠ "cartridge valve"), in the sentence or the GD request it answers, counts as isolation, **only if** `manual_has_electrical_test(part, section_text)` is false.
   - Position words (front/lead/left…) never identify a part.
   - Tests: `TestMechanicalObservationRule` (counts with no electrical test / not when the manual has one / system observation ≠ part).

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; class/priors ✔; no case keys ✔; sweep ✔ (pack); tests ✔; escape closed ✔; containment n/a.
