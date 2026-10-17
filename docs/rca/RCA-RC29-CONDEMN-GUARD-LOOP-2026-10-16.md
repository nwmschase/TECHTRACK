### RCA: Condemn guard loops RC29: a recorded normal/OK test result is not recognized, and nothing stops a repeated request
Format: docs/standards/ROOT-CAUSE-ANALYSIS-STANDARD.md. Leader HOLD on PR #92 at 6:23 PM PDT. No RC29-keyed code; the fix is general.

1. **Problem statement.** RC29 (Furrion FACR13LPSA2-PS rooftop A/C with a gurgling/grinding noise from inside the sealed compressor) ran for 14 turns with the guard on. The GD asked for the same compressor winding/ground ohms test 9 times. The tech answered "Winding and ground checks look normal/OK." each time. The whole-unit OEM call ("Replace complete rooftop unit" via OEM authorization) was never reached. Before the guard (rootfix-1640), RC29 reached that call in 5 turns. Expected: accept the recorded result and route to the OEM whole-unit authorization.
2. **IS / IS-NOT.**
   - IS:
     - Answers that report a test result without a number ("checks look normal/OK").
     - Answers whose sentence does not repeat the part's name, because the part was named in GD's request.
     - Whole-unit calls ("complete rooftop unit"), where no reading "at the unit itself" exists.
   - IS-NOT:
     - RC30: "fuse reads open". The sentence has the part and an open/ohm result.
     - RC12: "At inverter F+/F– … 14.28–10.37 V". The sentence has the part and a meter value.
     - Conditional lines ("If … replace X"), which the guard never matched.
   - Difference: the guard recognized only a meter value or an open/jumper result in the same sentence as the part's noun. A test-named normal/OK answer to a GD request, and an elimination-based whole-unit call, can never satisfy that.
3. **Timeline (PDT).**
   - 5:21 PM: Leader orders the guard.
   - ~5:35 PM: the guard is implemented in fea86b4 with a model retry ("Give the isolation test for that part and ask for the reading").
   - ~5:55 PM: tightened to the same sentence after the first RC12 run was judged weak.
   - ~6:00 PM: RC29 rerun (final-guard2): 14 turns, no fix. My verdict note read "looped winding/ground ohms … never directed rooftop replacement". It was reported as "for review" and not flagged as a regression. That was my error.
   - b472d1b: the retry was replaced by a deterministic rewrite. The loop condition is unchanged: the rewrite asks for the reading again.
   - 6:23 PM: Leader HOLD.
4. **Evidence (fea86b4 / b472d1b, gd_official.py).**
   - l.1035-1043 `isolation_recorded`: passes only if `ISOLATION_RE.search(low)` (a number+unit, continuity/open/OL, jumper/bypass) AND the part's noun appear in the same sentence (l.1040 splits into sentences). "Winding and ground checks look normal/OK." matches neither.
   - l.1046 `unproven_condemns(reply, tech_msgs)` receives only the tech's messages. GD's requests are never passed, so an answer cannot inherit the part named in the request.
   - Repro on b472d1b: `unproven_condemns('Requested authorization: Replace complete rooftop unit (FACR13LPSA2-PS).', ['Winding and ground checks look normal/OK.']*9) -> ['complete rooftop unit']`, and the same for `'Replace the compressor.'`.
   - fea86b4 l.1384: the retry tells the model to "give the isolation test for that part and ask for the reading". This is exactly the winding test RC29 repeated. b472d1b l.1382 rewrites the line into the same ask.
   - l.1201-1206 `is_repeat`: compares only with the LAST GD message (Jaccard > 0.8) and retries once. l.1375 keeps the repeated reply when the retry repeats too. There is **no rule that caps how many times one test can be requested** (code search for a request counter: none).
   - Transcript: /workspace/techtrack-validation/gd-official-sim-2026-10-16/final-guard2/RC29.md, turns 6-14.
5. **Causal chain.** Loop = (A AND B) AND C.
   - A: the guard requires a meter value in the part's sentence and ignores both test-result words and the request being answered.
   - B: a whole-unit call has no "reading at the part"; it is an elimination conclusion.
   - C: no no-repeat rule. Nothing stops the third, fourth … ninth identical request, and a stubborn retry keeps the repeat.
   - Systemic root: **the guard treated "evidence recorded" as a lexical property of one sentence instead of a property of the session's request/answer record, and GD had no bound on re-asking**. Any step whose evidence the guard cannot parse therefore becomes an infinite re-ask.
6. **Why checks missed it.**
   - The guard tests covered only part+value sentences.
   - No test walked a multi-turn session with normal/OK answers.
   - No property test bounded the number of repeated requests.
   - The RC rerun verdict was read for "condemned before reading" only, not for regression against the earlier RC29 outcome.
7. **Class of failure.** Evidence gate with a narrower recognizer than the evidence it gates, combined with an unbounded retry. Unparseable evidence becomes an infinite re-ask.
8. **Prior incidents (same class).** Searched CHANGELOG.md, TECHTRACK-VERSION-HISTORY.md, tests and debriefs for repeat|re-ask|loop|asked again|not checked.
   - (1) The `drop_reasks` / "TECH HAS REPORTED" fixes (re-asks of a reported fact).
   - (2) The `is_repeat` retry (a word-for-word repeat).
   - (3) The S20 lead-jack "plumbing is not asked again" tests.
   - (4) RC29 here.
   - Each earlier fix was per-message, never a session-wide bound.
9. **Fix + proof (a1bbd35).**
   - **(1) The guard reads the whole session.**
     - `session_tests()` pairs every tech answer with the GD request it answers.
     - `isolation_recorded(part, answers, requests)` accepts a sentence with a meter value OR a test result. `TEST_RESULT_RE` requires a test word: check/test/reading/measure/ohm/winding/ground … plus normal/OK/good/pass/in spec. The part must be named in that sentence OR in the GD request it answers. A meter value is preferred, not required.
     - A visual "plugs look seated/OK" is still NOT a test result. This keeps the RC12 strictness.
     - Whole-unit calls (unit/appliance/rooftop) need at least one recorded test result in the session. This is a general rule: a whole-unit call is an elimination conclusion.
   - **(2) NO-REPEAT rule.**
     - `cap_repeats()` counts each test request across the session in pin["asks"]. Requests are matched by word-set Jaccard ≥ 0.6, excluding labels.
     - A request already asked twice is dropped. If no request is left, GD accepts the answer ("Accepted as reported: …") and routes to the next step or to OEM authorization.
     - The model prompt also lists the tests already asked twice under a NO-REPEAT RULE, so the second ask is the one "ask once for the specific value".
   - **(3) Tests (tests/test_condemn_norepeat_locked.py, LOCKED).**
     - An RC29-shape walk. A stubborn model repeats the winding request three times; the third is replaced by "Accepted as reported", and the OEM whole-unit call then passes the guard.
     - Normal/OK in answer to the request counts. A visual OK does not.
     - PROPERTY test: 60 random sessions of 4-12 turns, with any mix of 5 test requests from a stubborn model. No request appears more than twice in a session.
   - Reruns and the suite are in the PR body.

CONTAINMENT: none. FU-4: move the request/answer record into the pin as structured facts (test id, value, verdict) instead of word-set matching.
