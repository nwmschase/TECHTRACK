### RCA: The S20 lead-jack replay assertion was loosened to "177094 OR held" (16ce4f0); tightened in 33b4202 (Leader 8:23 PM call b)
Format: ROOT-CAUSE-ANALYSIS-STANDARD.md. Test-only change. No case keys in app code (S20 is a locked replay test file).

1. **Problem statement.** 16ce4f0 changed `_assert_reaches_cartridge_fix` to accept either 177094 or the held line in EVERY walk. A walk that had recorded the isolation step could then stop at "held" and still pass.
2. **IS / IS-NOT.**
   - IS: walks with the coil test on record (the cartridge isolation step in the S20 path).
   - IS-NOT: walks with no coil test (concern only, override only, the live-turns walk), where held is correct.
   - Difference: whether the isolation step precedes the call.
3. **Timeline.** 16ce4f0, 6:12 PM; Leader 8:23 PM; tightened in 33b4202.
4. **Evidence.** 16ce4f0 tests/test_v41929_levelup_leadjack.py `assertRegex(joined.lower(), r"177094|before condemning …")`.
5. **Causal chain.** The loosened assertion = the old test assumed an immediate cartridge call, and the guard made that illegal; I widened instead of conditioning. Root: **the assertion wasn't conditioned on the evidence state.**
6. **Why checks missed it.** Self-review only; no reviewer had looked yet.
7. **Class of failure.** Test weakened to fit new behaviour.
8. **Prior incidents.** None found. Search: git log -p tests/ for "assertRegex(.*|" widenings.
9. **Fix + proof.**
   - With the coil test on record, 177094 is REQUIRED (with its owner's-manual page), it must first appear at or after the isolation turn, and never in a reply before it.
   - Without it, 177094 must NOT print and the held line must be present.
   - 8/8 pass on 33b4202.
   - Per-walk probe: coil walks print 177094 after the coil turn; concern-only, override-only and live-turns walks are held.

Checklist: 9/9 ✔; IS/IS-NOT ✔; evidence ✔; general ✔; priors searched ✔; no case keys in app code ✔; tests ✔; escape closed ✔; containment n/a.
