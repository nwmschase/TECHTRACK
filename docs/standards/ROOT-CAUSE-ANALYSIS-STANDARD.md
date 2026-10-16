# Root Cause Analysis Standard: Supervising Software Fixes (TechTrack)

**Who this is for:** the lead AI assistant that supervises software work on the TechTrack Streamlit app (picks RV repair manuals, guides techs).
**What it prevents:** fixing one test case instead of the logic, the "whack-a-mole" pattern.
**Rule zero:** Every fix report opens with the RCA template in section 2. No template, no review.

---

## 1. What the experts do (short version)

| Method | Core idea | What we take from it |
|---|---|---|
| **5 Whys** (Toyota/Ohno) | Keep asking "why" to get past the symptom. | Fine as a warm-up. It follows **one linear path** to **one root** and assumes the deepest "why" is the best place to fix, so it misses parallel causes. The answers also vary by who asks [1][2]. Never use it alone. |
| **Ishikawa / fishbone** | Sort candidate causes by category before picking one. | Brainstorm across categories so you don't lock onto the first cause [3]. Our categories: *Input data, Parsing/tokenizing, Matching/scoring, Gates/filters, Fallback/control flow, Tests/eval.* |
| **Fault tree analysis** | Start from the top failure event and break it down with AND/OR gates [4]. | A wrong manual pick usually needs several defects at once (an **AND gate**). Fix each leg, or at least the one that ends the class. |
| **8D (Ford)** | Teams work in disciplines: D3 contain, D4 root cause + **escape point**, D5–D6 permanent fix and verify, D7 prevent recurrence systemically [5]. | Ask two questions: *why did it happen* and *why did it escape detection*. Containment is not a fix. |
| **DMAIC Analyze** (Six Sigma) | Form cause hypotheses and **test them with data** before you improve anything [6]. | Every root claim needs a check against data, such as a sweep over the corpus. |
| **Apollo RCA** (Gano) | Every effect has at least one *action* cause and one *condition* cause. Causes must be backed by evidence [7]. | Each link in the causal chain cites evidence: a log, a repro, or a code line. |
| **Kepner-Tregoe IS / IS-NOT** | State what the problem is and what it **is not** (what, where, when, extent). The true cause has to explain both sides [8]. | This kills theories that only explain the case in front of you. |
| **Barrier analysis** / Swiss cheese (Reason) | Accidents get through holes lined up across several defenses. Look for the barriers that failed or were missing [9]. | Our barriers: type gate, match threshold, tie-break, fallback, tests. Ask which ones failed. |
| **NASA / aviation / medical RCA** | Separate **proximate** causes (what triggered it) from **systemic/root** causes (the conditions that allowed it). Aim for strong actions such as design changes, not weak ones like "be careful" or retraining [10][11][12]. | A case-specific patch is a *weak action*. |
| **Google SRE postmortems** | Blameless. Several **contributing** causes, not one villain. Track trigger vs root category for trends. Action items have owners [13][14][15]. | Don't blame the input data or the last author. Look for the class of failure and log it so trends show. |

---

## 2. Mandatory RCA template (every fix report opens with this)

```
### RCA: <short title>
1. Problem statement: observed vs expected, one or two sentences, with the concrete input.
2. IS / IS-NOT:
   - IS: which inputs/brands/types/pages fail.   IS-NOT: similar inputs that work.
   - What distinguishes them? (This difference points at the cause.)
3. Timeline: when it was first seen, related commits/patches, when it was detected, and by whom/which test.
4. Evidence: repro command, logs/debug scores, the code lines involved. No claim without evidence.
5. Causal chain to systemic root: proximate trigger → each contributing condition → the general
   logic defect(s). Use AND/OR where several defects were all needed.
6. Why existing checks didn't catch it: which test/gate/barrier should have, and why it didn't
   (missing, too narrow, tuned to fixtures).
7. Class of failure: a general name, e.g. "token-overlap matcher accepts non-identifying tokens".
8. Prior incidents of the same class: list them with links. If there are none, say how you searched.
9. Fix + proof: what general logic changed; sweep/property-test results; regression tests added.
```

---

## 3. Root fix vs patch: rules

A change counts as a **root fix** only if all of these hold:

1. **It changes the general logic.** No new special case keyed on a brand, filename, page, model, or test ID. Allow-lists and deny-lists are patches unless they encode a general rule with a reason written down.
2. **It is proven on the whole class.** Run a sweep (every manual × every appliance type/brand in the corpus) or a property test (e.g. "a pick's type always equals the requested type", "a unit/voltage token never counts as a model match"). Report before/after counts.
3. **It adds regression tests for every prior incident of the class**, not just the newest one.
4. **The IS / IS-NOT analysis fits.** The fix explains why the failures failed and why the non-failures worked.
5. **It closes the escape.** At least one test or gate now exists that would have caught the original failure.
6. **No collateral damage.** The full suite and the sweep show no new failures. Where a pick changed, it was reviewed.

A patch is allowed only as **containment**, labeled `CONTAINMENT`, with an open item for the root fix.

---

## 4. Reviewer checklist (each item pass/fail; any FAIL means reject)

- [ ] Does the report open with the full RCA template, all 9 fields filled?
- [ ] Does IS / IS-NOT list at least one similar case that works, and does the cause explain the difference?
- [ ] Does every causal link cite evidence (repro, log, code line)?
- [ ] Does the chain reach a **general logic defect**, not "this manual/input was odd"?
- [ ] Is the class of failure named, and were prior incidents searched for and listed?
- [ ] Does the diff contain **no** new case keyed on brand/file/page/model/test ID?
- [ ] Was a sweep or property test run on the whole class, with before/after numbers?
- [ ] Is there a regression test for **each** prior incident, and do they all pass?
- [ ] Is there now a check that would have caught this originally (escape point closed)?
- [ ] Do the full test suite and the sweep show zero new regressions?
- [ ] If any part is a containment patch, is it labeled, with a follow-up item?

---

## 5. Common RCA traps

- **Stopping at the first cause.** The first plausible "why" is usually the proximate trigger. Keep going until you reach logic that would fail on *other* inputs too. Look for several legs (AND gates) [1][4].
- **Blaming the input.** "The manual has odd text" or "the brand is unknown" describes the input. Real-world input is messy, so the code has to handle it. That is the blameless principle applied to data [13].
- **Tuning to the test case.** Changing weights, page ranks, or lists until *this* fixture passes. Signs: magic numbers, brand names in code, the fix not generalizing in the sweep.
- **Confirmation bias.** Only looking for evidence that supports your theory. Counter it with IS-NOT and by trying to break your own fix on the whole corpus [8].
- **Single root fixation.** Most failures have several contributing factors. Name all of them, even if you fix them in order [2][14].
- **Weak actions.** "Add a note", "be careful", "add this one case". Prefer design changes such as gates, invariants, and tests [12].
- **Treating every incident as new.** Without a class name and a prior-incident search, the same bug comes back under a new name.

---

## 6. Worked example: RC30 manual selection

**1. Problem.** For several requests, TechTrack pinned the wrong manual, e.g. a Girard *fridge* manual for a *water heater* job. Expected: the right type and brand manual, or a web fallback.

**2. IS / IS-NOT.**
- IS: requests whose text holds generic tokens (e.g. "12V"); unknown or unlisted brands; types the gate didn't recognize; several candidate manuals sharing any token.
- IS-NOT: requests with a distinctive model number and a known type/brand. Those picked correctly.
- Difference: the failures had **no distinctive identifying token**, so weak overlap decided the pick.

**3. Timeline.** A series of separate patches: Girard fridge-for-water-heater, a Thetford guard, a MaxxFan page-rank tweak, unknown-brand borrowing. Each fixed its own case. Then **RC30** failed again through the same mechanism, which showed the earlier fixes were patches.

**4. Evidence.** Debug output of `model_tokens` showed `12V` as a model token. `pin_document` scores showed ties at 1 shared token, decided by file read order. The type gate passed `type=unknown`. When anything matched, `found=True` was set and the web fallback was skipped.

**5. Causal chain (fault tree: wrong pick = A AND B AND (C OR D)).**
- Proximate trigger: a request containing "12V" with a brand/type not in the library.
- A, tokenizer: `model_tokens` treats unit/voltage strings ("12V") as model numbers. Non-identifying tokens look identifying.
- B, matcher: `pin_document` counts **any** shared token as a match and breaks ties by **read order**. A single weak token, plus file order, picks the winner.
- C, type gate: unknown types pass instead of being blocked or sent for review, so a fridge manual is eligible for a water-heater job.
- D, control flow: `found` set by a weak match **blocks the web fallback**, so the system never looks for the right manual.
- Systemic root: **selection had no concept of match strength or confidence.** Any overlap counted as success, and success shut off the safety net.

**6. Why checks missed it.** Tests were per-incident fixtures. Each patch made its own fixture pass. No sweep over manuals × types, and no invariant such as "pick type == request type" or "a unit token never matches." Barriers C and D were both open.

**7. Class of failure.** *Weak-evidence document match accepted as confident and suppressing fallback.*

**8. Prior incidents of the class.** Girard fridge→water heater, Thetford guard, MaxxFan page rank, unknown-brand borrowing, RC30. All five are one class.

**9. Root fix + proof.**
- A: `model_tokens` rejects unit/measurement patterns (`^\d+(\.\d+)?(V|A|W|BTU|Ah)$` etc.). Property test: no unit token is ever emitted as a model.
- B: `pin_document` scores by token **specificity** (model > series > brand; generic = 0) with a minimum threshold. A tie means **no pick** (ambiguous), never read order.
- C: The type gate blocks a mismatched or unknown type. Unknown goes to "needs confirmation", not a pass.
- D: The fallback runs whenever confidence < threshold; `found` means "confident match", not "any match".
- Proof: a sweep of all library manuals × all appliance types/brands, with before/after wrong-type picks (target 0) and ambiguous-tie picks (target 0). Five regression tests, one per prior incident. Earlier case-specific patches (Thetford guard, page-rank tweak, borrowing rule) are removed if the sweep shows they are no longer needed.

---

## Sources

1. Card, A.J. "The problem with '5 whys'." *BMJ Quality & Safety* 26(8):671–677, 2017. https://qualitysafety.bmj.com/content/26/8/671 (PubMed: https://pubmed.ncbi.nlm.nih.gov/27590189/)
2. SafetyInsights.org summary of Card 2017. https://safetyinsights.org/2021/04/29/the-problem-with-5-whys/
3. ASQ, "What is a Fishbone Diagram? Ishikawa Cause & Effect Diagram." https://asq.org/quality-resources/fishbone
4. U.S. NRC, *Fault Tree Handbook* (NUREG-0492), 1981. https://www.nrc.gov/reading-rm/doc-collections/nuregs/staff/sr0492/ ; NASA *Fault Tree Handbook with Aerospace Applications*, 2002. https://www.mwftr.com/CS2/Fault%20Tree%20Handbook_NASA.pdf
5. ASQ, "What are the Eight Disciplines (8D)?" https://asq.org/quality-resources/eight-disciplines-8d
6. ASQ, "The Define Measure Analyze Improve Control (DMAIC) Process." https://asq.org/quality-resources/dmaic
7. Gano, D. *Apollo Root Cause Analysis*; ARMS Reliability, Apollo method overview. https://www.apollorootcause.com/about/apollo-root-cause-analysis-method
8. Kepner-Tregoe, "Problem Solving and Decision Making" (Problem Analysis, IS / IS NOT). https://kepner-tregoe.com/training/problem-solving-decision-making/
9. Reason, J. "Human error: models and management." *BMJ* 320:768–770, 2000. https://www.bmj.com/content/320/7237/768 ; U.S. DOE, *Root Cause Analysis Guidance Document* DOE-NE-STD-1004-92 (barrier analysis). https://www.standards.doe.gov/standards-documents/1000/1004-std-1992
10. NASA, *NASA Accident Precursor Analysis Handbook* / NPR 8621.1 Mishap and Close Call Reporting (proximate vs root causes). https://nodis3.gsfc.nasa.gov/displayDir.cfm?t=NPR&c=8621&s=1D
11. FAA, Safety Management System / root cause guidance. https://www.faa.gov/about/initiatives/sms
12. National Patient Safety Foundation, *RCA²: Improving Root Cause Analyses and Actions to Prevent Harm*, 2015 (action hierarchy: strong vs weak actions). https://www.ihi.org/resources/tools/rca2-improving-root-cause-analyses-and-actions-prevent-harm
13. Google SRE Book, Ch. 15 "Postmortem Culture: Learning from Failure." https://sre.google/sre-book/postmortem-culture/
14. Google SRE Workbook, "Postmortem Culture." https://sre.google/workbook/postmortem-culture/
15. Google SRE Workbook, Appendix C "Results of Postmortem Analysis" (trigger vs root-cause categories), and the example postmortem. https://sre.google/workbook/postmortem-analysis/ ; https://sre.google/sre-book/example-postmortem/
