# Fixture gaps versus the live library

This directory is the library `scripts/thetford_live_gate.py` runs when live R2 is not mounted. It is not a copy of the shop database.

Command:

```
python3 scripts/thetford_live_gate.py \
    --db tests/fixtures/thetford_live_library/library.sqlite \
    --cache tests/fixtures/thetford_live_library/cache \
    --out /tmp/thetford-gate
```

The gate ranks about 12 chunks, keeps each window's English column, stitches the overlap, and cuts at 4000 characters. It does not open the full kit PDF to build the scored branches. A score that only passes when the full PDF is read does not count.

## Documents

Present, with local ids (not the live document ids):

| Local id | Document | What is stored |
|---|---|---|
| 3 | Thetford Style II OM 42088 | Text only |
| 1 | Water valve kit 42109 | Page-1 text and four figure crops |
| 2 | Vacuum breaker kit 34123/34122 | Page 1 and 2 text, and Fig. 1 |

Not in the fixture, and not in the repo as a public PDF:

- Service manual 42110. Marked absent. The gate does not invent it.
- Thetford parts list. Marked absent. The gate does not invent it.
- The rest of OM 42088. The text extract has pages 2, 3, 4, and 6 only. Pages 1, 5, and 7 onward are absent, and there is no 42088 PDF in the repo

## Pages

- 42088 chunks: pages 2, 3, 4, 6 (17 windows)
- 42109 chunks: page 1 only (5 windows)
- 34123/34122 chunks: pages 1 and 2 (16 windows)

38 chunks total. Each window is the indexer's 900-character slice with 120 characters of overlap. The gate ranks 12 of those windows. English kit windows outrank a translation column. The owner-manual mention of the water valve is not treated as the 42109 sheet.

## Figures

Cache crops, taken from the local kit PDFs with the same indexer the shop uses:

- 42109 page 1: Fig. 1 PEDAL REMOVED, Fig. 2 INSERTING WATER INLET SEAL ASSEMBLY, Fig. 3 WATER VALVE CLOSED POSITION, Fig. 4 PEDAL REATTACHMENT
- 34123/34122 page 1: Fig. 1

Fig. 3 is the 400 dpi crop. The caption is the full manual label, not the cut-off word WATER.

No 42088 page image. Live show-me can attach the stored page-3 image and point at it. This cache cannot, so the show-me says the manual has no picture of this spot.

No page-7 "Step 1" row. A temporary database used while writing the gate added that row, with a stub PNG, to prove a caption stays on the cited page. It is not in this library, and the stub is not a live crop.

## What the fixture does not invent

- Document ids 1, 2, and 3, and the file paths under `library/`, are local. They are not the live row ids or R2 keys.
- Figure PNG bytes are crops of the kit PDFs already in `tests/fixtures/`. They were not downloaded from live R2, so they are not byte-checked against the shop cache.
- 42088 chunks include the Italian and Korean text that is on those pages. The sheet stays in English.
- There is no parts-list figure and no 42110 figure.
