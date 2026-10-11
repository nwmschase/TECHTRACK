# Bay PDF past failures: regression checkpoints (DRAFT)
Built 2026-10-11 ~10:50 AM PT from LEADER-REVIEW-*.md, CHECKER-NOTES-*.md, FIX-REPORT-LOG.md, TECHTRACK-VERSION-HISTORY.md, REVIEW-PACK-2026-10-10/**/GATE-SUMMARY.md + *notes*.md, eod-draft-*.md. September eod drafts and leader files had no specific Bay PDF defects; I found no September LEADER-REVIEW files.
"Occ." counts distinct recorded instances (version x case). The same issue repeated across several gate packs counts once per version where it was listed. Only Bay PDF items are included. GD-only defects (echo, guard text, step cursor, download banner in chat) are left out unless the PDF also showed them.

## Text / sentences
| ID | Checkpoint (PASS/FAIL) | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-01 | No sentence or source quote ends mid-thought or mid-word | v4.19.41/43/46/47/48 S04 Sources quote cut "Straighten the temperature probe (Fig ." (fixed v49); v4.19.48 Thetford diag step 2 GOOD vs BAD ended "That limit is"; v4.19.6 fix "no mid-word snippets"; v4.19.14 S07 verbless trailing fragment | 8 | partly: flag lines ending without terminal punctuation or ending in "(Fig .", "is", "the", "and" |
| PF-02 | Every sentence/final line ends with a period | v4.19.50 Thetford "Look for leaks" (no period; carried into next draft); v4.19.49 S09 "cools Next check" missing period; v4.19.51 S01 last line no period | 3 | yes: regex for missing terminal punctuation / lowercase-capital run-ons |
| PF-03 | No placeholder or filler tokens (UNCONFIRMED, "Not stated in this sheet", "See doc.") | v4.19.41 Thetford p2 literal UNCONFIRMED in SAFETY/TOOLS/GOOD vs BAD/FIGURE/PHOTO on all 4 steps + p3 DO NOT rows; v4.19.48 p2 "not stated in this sheet"; v4.19.18 "See doc." placeholders | 3 | yes: grep blacklist |
| PF-04 | No OCR junk or multilingual garble in steps or quotes | v4.19.27-28 Thetford steps 6/8 + a source quote multilingual OCR junk; S07/S08 raw OCR steps (10/9, Coleman fix PR #31) | 3 | partly: non-ASCII/non-English ratio, dictionary hit rate |
| PF-05 | Source quotes are verbatim, single-sentence manual text, no doc-ID or heading glued in front | 10/9 v4.19.14 S01 "18 CCD-0008666 Troubleshooting Problem Cause Remedy...", S04 "CCD-0008122 Lockout/Hard Reset...", S05 "CCD-0008122 Open the...", S10 "Jack Faults Ground Control TT..."; v4.19.17 reworded/multi-sentence quotes; v4.19.18 hand-written quotes (12 FAIL) | 7 | yes: substring check against retrieved chunk text; regex for leading doc IDs |
| PF-06 | Diagnosis/step sentences stay short (about 12 words or fewer) | v4.19.51 S01 diagnosis items 13-26 words (item 7 = 26) | 1 | yes: word count per sentence |
| PF-07 | No doubled words, brand names, or labels | v4.19.17 S04 doubled brand; 10/9 Suburban "Suburban" header | 2 | yes: repeated-token regex |

## Structure / steps
| ID | Checkpoint | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-08 | The Bay PDF has the full numbered repair procedure, not a flowchart-only or diagnostic-only sheet | v4.19.39b/v4.19.40 Thetford flowchart-only (FAIL new standard); v4.19.47 Thetford 4-check sheet without the 14-step repair (OVERRIDE voided the clear) | 3 | partly: count numbered REPAIR steps against the expected count |
| PF-09 | No step duplicates the previous step's action, and no other procedure is appended that wasn't asked for | v4.19.49 Thetford step 4 repeats "Pull the pedal up and off" (step 3 NEXT); v4.19.48 extra 13-step vacuum-breaker R&R p6-p8; v4.19.22 S13 duplicate; v4.19.20 S15 p.4 duplicate | 4 | partly: fuzzy-match adjacent step HOW text; check procedure titles against the fix part |
| PF-10 | Every step has the required labeled lines in order (Where / Tools / Do this / Good looks like / Bad looks like when specific / Next), safety is stated once per section and is correct, and no line contradicts another | v4.19.49 Thetford step 14 SAFETY "water off" vs HOW "water ON", no WHERE, no GOOD vs BAD; v4.19.51 S01 diagnosis items lack all five fields | 2 | partly: field counts are scriptable; contradictions need on/off keyword pairing |
| PF-11 | Flowchart logic is complete: every diamond has both a YES and a NO exit, with no doubled labels | v4.19.20-26 S13 doubled "YES YES" / APS diamond has no YES exit / gas check branches off the blower line; v4.19.17-18 S13 thin flowchart; v4.19.22 S11 flowchart end; v4.19.23 S13 arrowhead + end box | 6 | partly: pdftotext label counts per diamond; the graph needs layout parse |
| PF-12 | The fix in the PDF matches the MASTER expected repair | Thetford v4.19.26 Norcold steps on a toilet job; v4.19.27 Thetford off-topic rows (poor flush, blade seal, riser) + generic flowchart | 2 | partly: grep the expected part number or repair phrase from MASTER-CASES |
| PF-13 | Each Sources section is present and every source has a page | v4.19.19 S08 Sources section dropped; v4.19.17 S08 empty Sources, no page on sources; v4.19.20 S09 3311071 no Sources line; v4.19.22-23 S06 no pages; v4.19.34 S20 "Lippert Level Up owner's manual, hose diagram" no page | 7 | yes: parse Sources, require "p." per line |
| PF-14 | Expected cites are not dropped between versions | v4.19.18 dropped cites S03/S07/S10/S13; SAT v4.19.26 S14 rear stab p.11 cite dropped (was in v4.19.20); v4.19.17 S14 lost p.11; S14 MODEL blank, p.11/p.7 cites missing (10/10) | 5 | yes: diff cite set against the last known-good |

## Figures / images
| ID | Checkpoint | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-15 | Every step that cites a figure shows that figure beside it ("Cited figures" > 0 and equal to the embedded images) | v4.19.41 + v4.19.43 Thetford "Cited figures: 0", pdfimages empty; v4.19.47 only 2 of 4 steps have crops; v4.19.49 step 6 cites Fig.1 with no image; v4.19.50 diagnosis steps cite figures in text only, and cited count 5 vs 4 drawn; v4.19.51 S01 12pp with figures cited as text only (steps 4, 5, 8, 16, 17, 19) | 7 | yes: pdfimages count vs "Fig." cites and the form's "Cited figures" value |
| PF-16 | Figures are not clipped or cropped (whole frame, labels and caption visible) | 10/9 + v4.19.20 + v4.19.22 S05 Fig.36 bottom cut ("Fridge cavity" label, cabinet frame, white strip + stray rule); 10/9 S01 p.2 CCD-0007990 p.7 table crop; v4.19.48 Fig.2 bottom caption may clip; v4.19.50 embedded kit caption slice | 6 | partly: edge-content detection on image bbox; caption bbox inside page |
| PF-17 | Each figure appears once, beside the step that cites it, not repeated | v4.19.48 Vacuum Breaker Fig.1 repeated 4x (steps 5-8); v4.19.47 S10 frame diagram x3; v4.19.51 S01 CCD table on p12 away from citing steps | 3 | yes: image md5 dedupe + page/step proximity |
| PF-18 | Figure captions are correct and from the manual (no "Bundled kit sheet", no sketches passed off as OEM) | v4.19.48-49 Step 8 caption placement; v4.19.49 "Bundled kit sheet" caption (blocker); v4.19.50 step 4 caption label; v4.19.6 "no sketches as OEM" | 4 | partly: caption text blacklist; caption-to-figure-ID match |
| PF-19 | Figures match the case's brand and topic | v4.19.47 S14 HappiJac other-brand figure; v4.19.41 S20 Titan Fig.4; v4.19.43 cross-case off-topic figures on many sheets | 3 | partly: figure doc brand vs case brand |

## Layout / pagination
| ID | Checkpoint | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-20 | No label overlaps or crowds connectors or arrowheads | S01 NO label crowded on the down connector / return-line arrowhead (v4.19.17-18, 10/9, v4.19.20, SAT v4.19.26 at 200 dpi); v4.19.40 S10 p1 NO touches node; v4.19.24 S13 crossing connectors | 6 | partly: bbox intersection of text vs vector paths |
| PF-21 | Text stays inside its shape; section bars don't cover content | 10/9 oval text overflow + DO NOT/SOURCES bars overlap content (FIX-REPORT TOP); S10 oval (v4.19.2); S03 diamond awkward wrap (advisory) | 3 | yes: text bbox inside shape bbox / bar bbox |
| PF-22 | No orphaned heading at the bottom of a page | v4.19.48-49 Thetford "REMOVAL" orphaned at the bottom of p2 | 2 | yes: heading is the last line on a page |
| PF-23 | Lists aren't split across pages with a repeated heading; no near-empty trailing page | v4.19.50 DO NOT list split p5/p6 with repeated heading; v4.19.48 S14 p3 holds only the Sources line | 2 | yes: per-page line counts, heading repeats |
| PF-24 | Page count is reasonable (no bloat vs the previous version) | v4.19.51 S01 12pp vs v50 2pp (WORSE); v4.19.48 Thetford 8pp (v49 6pp) | 2 | yes: page count vs baseline |

## Leaks / noise
| ID | Checkpoint | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-25 | No internal or meta notes on the sheet | v4.19.20 S11/S12 "(FACR08 manual, closest reference)" in Sources (moved from PRIMARY); v4.19.17 S11/S12 internal note repeated; v4.19.18 fake source line; S06 meta text (10/9) | 5 | yes: grep blacklist ("closest reference", "library", "excerpt") |
| PF-26 | No off-topic source snippets or rows | 10/9 S04 p.24 hard reset + p.44 knob snippets; S10 p.4 "If a sensor is bad, replace" (contradicts DO NOT) + p.3 comm-fail; 10/9 S02 off-topic snippet | 4 | partly: topic keyword overlap |
| PF-27 | No banned jargon or raw filenames ("channel", ".pdf") | FIX-REPORT 10/9 "channel" in GD/PDF output (PR #28) | 1 | yes: grep |
| PF-28 | No stray numbering or list artifacts | v4.19.9 stray question bullets / leading figure numbers (VERSION-HISTORY) | 1 | yes: regex for a leading "\d+\." inside a sentence field |
| PF-29 | The PDF is fresh for this case (not the previous case's file) | v4.19.46 S02 download returned the S01 PDF byte-identical (harness) | 1 | yes: md5 unique + CONCERN text grep |

## Source / brand accuracy
| ID | Checkpoint | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-30 | Every cite and step comes from the case's own brand/unit manual | 10/9 Coleman 2111 cites Furrion manuals; Thetford v4.19.26 cites Norcold 619394E (2 pages of fridge steps for a toilet); FACT12 body = FACR08 book cited as FACT12 | 3 | yes: cite doc brand/model vs case |
| PF-31 | MODEL/header string is complete and correct | v4.19.18 S04 full model missing; S06 wrong MODEL string; S14 MODEL blank | 3 | yes: header vs pinned input |

## Safety
| ID | Checkpoint | Past examples | Occ. | Auto? |
|---|---|---|---|---|
| PF-32 | Technical content is correct (no wrong part or location advice) | v4.19.20 S13 "petit tube in the flame" (APS tube is at the blower); S11/S12 "E2 or E3 is a freeze-sensor seating fault" (contradicts the OEM E3 comms path); v4.19.23 S04 C/T sentence | 3 | no (expert review); partly via banned-phrase list per case |
| PF-33 | SAFETY lines agree with the action (power/water/propane state) | v4.19.49 Thetford step 14 SAFETY "Turn the RV water off" vs HOW "turn water ON" | 1 | partly: on/off keyword conflict check |

Total: 33 checkpoints.

Not included because they are GD-only or Bay wasn't run: v4.19.53 two-action HOW (step 12), generic "Bad: It does not look right.", stray "2." in step 1, show-me page 3 vs 7 (GD; the Bay PDF was not run on v53). Chase's partial-approval format ask (drop the repeating PHOTO/Yes-No script) comes from shared memory per CHECKER-NOTES-0821 and isn't a recorded failure.
