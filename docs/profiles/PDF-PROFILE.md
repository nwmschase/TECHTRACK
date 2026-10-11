# PDF Builder (Bay Procedure): Established Profile
Version 1.4. Established by Chase on 2026-10-11. Owner: Leader.

## What it is
A strict, complete repair document in the ALLDATA / factory-manual style. Someone with no experience and limited reading must be able to follow it.

## Structure, every time
1. Header: concern, model, primary source.
2. Diagnosis flowchart.
3. Diagnosis checks, in order.
4. Branches: one section for each possible repair (for example: supply connection, vacuum breaker, water valve, flange). Each branch has:
   - a "Before you start" list, and the safety note once
   - numbered Removal steps and numbered Installation steps, through to completion
   - a final confirm / verify step with a clear pass or fail
5. Do Not list.
6. Sources.

## Step format
- Bold numbered heading, for example "Step 4: Release the retainer".
- Short labeled lines: Where, Tools, Do this, Good looks like, Bad looks like (specific to that step, or left out), Next.
- "Do this" is a list with one action per line.
- Short sentences, about 12 words or fewer. Plain words.
- The same order of lines in every step.

## Figures
- Real figures from the matching manual, same brand and model only. Never invent one, and never use another brand's.
- Large, about 70-80% of the page width.
- Centered directly under the step that cites it, with the caption below.
- A step is never split from its figure.
- No figure where the manual has none.

## Never
- PHOTO lines or "Yes, go to the next step / No, do this step again".
- UNCONFIRMED tags, disclaimers, or leaked app text.
- Cut-off sentences, or stray numbers.
- Web content, except in a separate "Outside sources" section that is clearly labeled.

## Model
Target detail level: /workspace/techtrack-validation/live-jobs/Thetford-42070-Lever-Leak-Shop-Sheet.pdf

## Testing standard (Chase 2026-10-11)
- Strict pass or fail. Every output is checked automatically against this profile, then Leader reviews every page at 90 dpi, then Chase gives final approval.
- If a GD session is reopened as "not the fix", the PDF for that job can be regenerated with the new findings and branches.

## Performance scorecard (grade every PDF, PASS/FAIL per line)
1. Structure complete: header, flowchart, diagnosis, a branch for every possible repair, Do Not list, sources.
2. Each branch runs to completion and ends with a confirm step with a clear pass or fail.
3. Every step has a bold numbered heading and the same labeled lines in the same order.
4. One action per line; sentences of about 12 words or fewer; plain words.
5. Bad looks like is specific to the step, or left out.
6. Real same-brand manual figure, large (about 70-80% width), centered under the step that cites it, with caption; never split from its step.
7. No figure where the manual has none; nothing invented or off-brand.
8. Safety stated once per section, and correct (no contradictions).
9. None of: PHOTO or yes/no lines, UNCONFIRMED tags, disclaimers, leaked app text, cut-off sentences, stray numbers.
10. Web content only in a separate labeled Outside sources section.
Result: X/10. Any FAIL on 2, 7, 8, or 9 is an automatic overall FAIL.

## Past fails (regression checkpoints)
Every PDF must PASS all 33 checks in PDF-PAST-FAILS.md (PF-01 to PF-33), on top of the scorecard. TT runs the auto-checkable ones by script on every gate. Leader checks the rest by eye at 90 dpi. Any new failure found in a review is added as a new PF item, with a profile change log row.

## Changelog
- 1.0 (2026-10-11 10:27 AM): Established. A strict branching repair document: flowchart, diagnosis, one branch per possible repair through to confirmation. Chase's format: bold step headings, labeled lines, one action per line, short sentences, no PHOTO or yes/no lines (replaces the 10/10 yes/no check after each step). Large figures centered under the steps. Web content only in a separate labeled section.
- 1.1 (2026-10-11 10:34 AM): Added the testing standard (strict pass/fail, Leader 90 dpi review, Chase final approval) and PDF regeneration after a GD reopen.
- 1.2 (2026-10-11 10:42 AM): Added a performance scorecard. Every rule is now a graded PASS/FAIL line.
- 1.3 (2026-10-11 10:50 AM): Added 33 past-fail regression checkpoints (PDF-PAST-FAILS.md).
- 1.4 (2026-10-11 12:11 PM): PF-10 reworded to match the approved step labels.
