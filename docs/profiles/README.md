# TechTrack established profiles
GD-PROFILE.md and PDF-PROFILE.md are the standard. Every change is recorded in PROFILE-CHANGE-LOG.md.

## Rules for Leader and TT
1. Before ANY TechTrack change (a feature, fix, definition, or behavior), check it against the profiles.
2. If the change, or a question Chase raises, MIGHT alter or add a profile rule, Leader ASKS Chase first. Leader never updates a profile silently.
3. Leader asks with a message that starts with "🔶 PROFILE CHANGE? (GD/PDF)", says what would change and from what to what, then gives a yes/no choice.
4. Only after Chase says yes: edit the profile, bump its version, add a changelog line in the profile, and add a row to PROFILE-CHANGE-LOG.md.
5. Leader then confirms with a message that starts with "✅ PROFILE UPDATED: GD vX.Y / PDF vX.Y" and a one-line summary.
6. TT never edits a profile. TT flags conflicts to Leader.
Each gate review checks the output against the profiles.

## Change log
- 2026-10-16 3:31 PM - Dev rule (GD + PDF): every fix starts with a written ROOT CAUSE analysis and fixes the root, never a one-case patch; every fix report and debrief opens with a ROOT CAUSE section. Chase-approved 2026-10-16 via Leader. (Row added to PROFILE-CHANGE-LOG.md.)
- 2026-10-16 3:59 PM - BINDING standard (GD + PDF): /workspace/crew/standards/ROOT-CAUSE-ANALYSIS-STANDARD.md. Every fix report opens with its 9-field RCA template and passes the section-4 reviewer checklist (any FAIL = reject). Patches allowed only labeled CONTAINMENT, with a root-fix follow-up item. Supersedes the 3:31 PM ROOT CAUSE line format. (Row added to PROFILE-CHANGE-LOG.md.)
