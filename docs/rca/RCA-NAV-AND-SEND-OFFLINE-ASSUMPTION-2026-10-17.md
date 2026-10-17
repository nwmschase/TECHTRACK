# RCA: test_gd_nav_and_send fails 3/3 on the box: the walks assume GD offline, and the box has a live model key
Commit: see the pack (tests/test_gd_nav_and_send.py setUp isolation + TestNavWalksAreOffline). No app code change.

### RCA: nav walks were not isolated from the process environment
1. **Problem statement.**
   - The 11:25 PM checker found test_two_sends_keep_section_category_and_model failing 3/3 (navsend-3x-0c4a291, and again in suite-e77941b, suite-4aff2a6 and navsend-3x-4aff2a6), and test_start_new_chat_drops_the_previous_case_before_the_next_reply failing 2/3 to 3/3. The checker classed this as a regression, not flakiness.
   - The failing assertion is tests/test_gd_nav_and_send.py:79, `assertIn("AI is offline", joined)`. Every navigation, section, category, model and session-state assertion before it passed.
   - Expected: the walk tests nav/state with GD in offline mode, deterministically, wherever the suite runs.
2. **IS / IS-NOT.**
   - IS: any run where XAI_API_KEY (and the R2 keys) are in the process environment, as on this box, where the RC sim needs them. GD then answers live: the transcript shows a real "Safety first … Report cavity temp …" reply instead of the offline notice.
   - IS: b1e363d (the known-good pre-selector base) fails identically with the key set (run at 00:10 PT in worktree /tmp/wt-base: "1 failed, 5 passed", same assertion). It also fails on main ab090e4 (earlier run).
   - IS NOT: the same HEAD with the keys unset (`env -u XAI_API_KEY -u R2_ACCESS_KEY_ID -u R2_SECRET_ACCESS_KEY`): passes.
   - IS NOT: any commit since b1e363d. **No commit broke it.** The failure is consistent (not flaky) because the environment is constant, not because the app changed.
3. **Timeline.**
   - The test landed with the nav fix (pre-b1e363d) and was written for an environment with no model key.
   - Model key exported on the box for the RC sweeps (2026-10-16).
   - First observed in the suites; classified as "pre-existing, fails on main" at 10:2x PM; root-caused 2026-10-17 00:10 PT.
4. **Evidence.**
   - Assertion and rendered transcript: pytest --tb=short at HEAD, with the key set (live GD reply shown, no "AI is offline").
   - With the keys unset: `1 passed`.
   - b1e363d worktree with the key set: same failure.
   - Fixed test with the key set: `7 passed in 7.78s`, versus 99-270 s for live runs (the live calls also explain the start_new_chat timeouts).
5. **Causal chain.**
   - Trigger: the suite runs on a box that exports a model key.
   - Condition: AppTest runs the app in-process with the inherited os.environ, so gd_llm sees the key and calls the live model.
   - Systemic root: **the test asserted an environment-dependent mode (offline) without establishing it.** The test had a hidden dependency on the environment.
6. **Why existing checks missed it.** CI and the dev machine where the test was written had no model key. Nothing asserted that the walk runs offline.
7. **Class of failure.** "Hermeticity: a test depends on ambient credentials/env, so the same code passes or fails by machine."
8. **Prior incidents.**
   - Same class: the live-results tests (test_v41941_live_*) intentionally use the key and are not affected.
   - v41931's 10 carryover failures are a separate open item (they fail identically on main); hermeticity was not verified for them tonight.
9. **Fix + proof.**
   - TestGdNavSurvivesSend.setUp removes the model and storage keys (OFFLINE_ENV_KEYS) from os.environ for every walk via mock.patch.dict, restoring them afterward. The walks now test exactly what they claim: nav/state with GD offline.
   - No app change and no lowered bar: all original assertions are kept, including "AI is offline".
   - New TestNavWalksAreOffline proves setUp removes every listed key and restores it on cleanup.
   - Proof: with the key set, `7 passed` (was 2 failed). navsend-3x on the final SHA is in the pack.
