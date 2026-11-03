"""
RV TechTrack v4.19.65
- v4.19.65: Manual selector root fix. Rating values (12 V, 50 Ah, 13,500 BTU, 6,000 lb) are never model numbers. Evidence is ranked by specificity: exact model in the doc fields, exact model in keywords or page text, series, then brand; brand alone never picks a manual. Two different manuals that match equally are not guessed between: no pick, and the official web lookup runs. Every library category maps to product types; an unmapped category or a model that only exists under another type asks the tech to confirm the unit type. A doc whose file or text cannot be reached is skipped for the next one. Brand-, page- and doc-keyed page rankers (Thetford, Coleman, MaxxFan page 9) are replaced by one page ranker; no toilet job assumes Thetford. Manager Tools has a library category audit (dry run, confirm, backup, rollback) and uploads warn when the category does not match the title.
- v4.19.64: One manual selector for every search (GD and the library/Bay search): an exact model number from the model field, complaint or label wins outright; category product type and brand are hard filters, so another product's or brand's manual is never pinned; "No <brand> <model> <type> manual found" counts as not found and the official web lookup runs. Label/diagram text and photos drive the walk. The warranty story records the final correction.
- v4.19.63: Guided Diagnostics official method (GD_OFFICIAL_METHOD=True). GD identifies the unit, pins its own-brand manual (library, then official OEM sites), reads the full troubleshooting section, and walks the tech one labeled step at a time. Verify the complaint first or call No Problem Found. Reported facts are never asked again. The Unity selector drives the OneControl controller path. Warranty-shop OEM escalation with a findings block. The warranty story is built from recorded readings only. Groq fallback is labeled reduced mode.
- v4.19.57: The live Thetford library path keeps every flowchart repair: supply connection, vacuum breaker, water valve, and flange seal. A retrieved figure no longer replaces those branches or pastes the How template into a reply. The supply connection is named in plain words, and a figure caption uses the cited page. Tools come from the kit sheet. A Bad line names a real failure or stays off. The Do Not list stays on this leak. Version stamp so this deploy is distinct from v4.19.56.
- v4.19.56: Live v4.19.55 is reverted. Shop behavior is known-good-v41954 again. Version stamp so this deploy is distinct from v4.19.55.
- v4.19.55: Thetford HOW is one action per line, including the pedal grab and the pedal pull. A cited page with no figure shows that page image. Each step names its own bad look, or the Bad line is left off. A failed R2 upload does not count as stored, and Index status shows page-image and figure counts. Each Bay figure sits under the step that cites it, centered at 75% of the page width, and stays on that step's page. Guided Diagnostics replies are plain sentences with no label block and no step counter, and a manual figure appears only when the tech asks. The Bay PDF keeps the diagnosis flowchart, then a numbered branch for each repair. Established profiles v1.0 are in docs/profiles. Each repair branch has Before you start with the safety note once, numbered Removal and Installation, and a verify step with a pass or fail. A Guided Diagnostics photo is asked only when it would help. Version stamp so this deploy is distinct from v4.19.54.
- v4.19.54: Live v4.19.53 is reverted. Shop behavior is known-good-v41952 again. Version stamp so this deploy is distinct from v4.19.53.
- v4.19.53: Every Bay step and Guided Diagnostics reply uses one short layout. Backfill is per case for CCD-0008666, CCD-0007990, and the Thetford Style II docs. Version stamp so this deploy is distinct from v4.19.52.
- v4.19.52: Live v4.19.51 is reverted. Shop behavior is known-good-v41950 again. Version stamp so this deploy is distinct from v4.19.51.
- v4.19.50: The Thetford leak test turns the RV water back on, names the pedal and the valve, and gives a good versus bad flush check. The closing line keeps Look for leaks. A page-image instruction and a bundled kit sheet caption stay off the reply. The pedal pull is one step. A bad supply connection says to fix or tighten it, and the flange line drops off-sheet part numbers. REMOVAL stays with its first step. A Brisk II sentence keeps the period before Next. A cited-figure count matches the images drawn. A sources block does not open a near-empty last page. FACR holds rooftop assembly R&R until refrigerant pressures are reported, then the next fact moves to the R&R and the verify. Version stamp so this deploy is distinct from v4.19.49.
- v4.19.49: A Thetford figure caption stays under its figure on the same page. A water-valve finding prints the 14-step valve repair only, and a vacuum-breaker finding prints the 13-step repair only. The same crop is not drawn twice. The flush-leak sheet does not say Not stated in this sheet, and a diagnosis line does not end at That limit is. FACR short turns authorize the rooftop repair by turn 5. The Girard pressure-switch hose sentence stays on page 23. A source quote keeps Fig. 12 and does not stop at Fig. Version stamp so this deploy is distinct from v4.19.48.
- v4.19.48: The Thetford Bay PDF carries the numbered 14-step water-valve repair, with a manual figure only beside a step the sheet cites. HappiJac stays off the PSX1 sheet. Level Up drops LCD tables, header strips, and off-topic same-family crops. Ground Control draws one crop. FACR authorizes the rooftop repair by turn 5. The Girard pressure-switch hose sentence stays. Empty fields stay off the reply, and the filler sentence is said at most once. The lead-jack bleed answer is yes or no. Version stamp so this deploy is distinct from v4.19.47.
- v4.19.47: A Thetford water-valve answer walks Step 1 through Step 14. A missing page image shows no download-failure caption. Version stamp so this deploy is distinct from v4.19.46.
- v4.19.46: Reload every Guided Diagnostics and Bay PDF module and log its revision. Version stamp so this deploy is distinct from v4.19.45.
- v4.19.45: Shop behavior is the pre-#76 release again. Version stamp so this deploy is distinct from v4.19.44.
- v4.19.44: Version stamp so this deploy is distinct from v4.19.43.
- v4.19.43: Version stamp so this deploy is distinct from v4.19.42.
- v4.19.42: Bulk import streams the ZIP to disk. Each page image is uploaded and released before the next page. A long manual continues from a page cursor, and a batch starts two files, so a 136-page owner's manual does not hold every page in memory. After the lead-jack cartridge repair is named, the next turn gives the numbered R&R and the parts-list figure, then bleed and resync with a yes or no. A check that already shipped advances on the next real answer, including a Thetford flush check. That internal marker is not printed in the reply, the bay order, or the do-not list. The Bay PDF uses the same library figure rows as the chat, beside the step they match, and a vacuum-breaker step shows the vacuum-breaker figure. A figure that already loaded does not add a failed download caption. The Girard hose sentence stays on the sheet when the same line names the blower. Ground Control's level reply says zero-point calibration is the repair. Drain, pan, fan, pressures, and a freeze sensor at 2k at 25C authorize the rooftop repair by turn 5.
- v4.19.41: A Thetford flush leak follows the shop sheet. The checks go supply connection, then the vacuum breaker while flushing, then the water valve body and drive-arm seal, then the flange. A weep at the pedal does not skip the vacuum breaker. A fact the manual does not state is marked UNCONFIRMED. Guided Diagnostics can take an optional step photo. xAI vision states what it sees. An unclear or mismatched photo asks for another and does not count as the finding. The tech can type the finding instead. Each Thetford check and each repair step uses the same fields: where, safety, tools and meter setting, how, good versus bad, next, the manual figure, and a photo ask. A field the document does not state says UNCONFIRMED. Every library document stores a rendered page image and each figure crop in cloud storage. The database keeps the key, the caption, the page, the box, and the link to the chunk. Guided Diagnostics and the Bay PDF show those figures for any brand. A bundled Thetford kit image is a last resort only, and its caption says it is not from the shop library. A manager can backfill figures for manuals already loaded, including a Lippert bulk import, and can resume that job. Those steps are grouped into short sections. A typed yes, no, or short answer moves to the next step, and the photo ask is not repeated. Asking for the repair procedure returns that numbered list. A freeze sensor report such as 2k at 25C counts as the sensor reading. The BAL troubleshooting page and the Girard pressure-switch hose sentence stay on the Bay sheet. A cooktop reply does not repeat a library-excerpt instruction. Level Up replies do not repeat the same line. Ground Control says zero-point calibration is the repair, and its NO label sits off the node. Bulk import Auto-continue keeps loading the next batch.
- v4.19.40: Guided Diagnostics and the Bay PDF say how to do each test from the cited manual page, and they show that page's cropped figure. Library indexing stores a 150 dpi page image and each Fig. crop with the chunks. A value the manual does not state is marked not stated in that document. A FACR turn does not condemn the rooftop before the pressures and does not print the internal prove note. Coleman and rear-wall ice turns do not repeat the last line. The tongue-jack part waits for the 12V reading. The dial-off prompt is not pasted twice. Ground Control reaches the manual-level step. A loose lead-jack cartridge is the 177094 repair. A Thetford flush leak starts at the supply connection, then water valve 42049/42109, then the vacuum breaker, then the flange. Once that fault is proven, Guided Diagnostics hands off one short repair step at a time and waits for a photo. The Bay procedure uses those same short Removal and Installation steps, read from the library sheet, with the kit figure beside the step and a yes or no check under it.
- v4.19.39: A Thetford 'Not checked yet' advances to the next unasked check: supply, water valve, vacuum breaker, then the flange seal. FACR pressures reported by turn 4 authorize rooftop assembly R&R on turn 5 once the drain, pan, fan, and freeze sensor are in. A Level Up lead-jack turn does not ask the plumbing question again after the cartridge.
- v4.19.38: Shop behavior is the v4.19.36 release again. The v4.19.37 changes are not in this deploy.
- v4.19.37: Start new chat clears the Guided Diagnostics conversation, answered slots, model, and category before the next message. The FACR prove asks for refrigerant pressures on the first check so a five-turn path can authorize rooftop assembly R&R.
- v4.19.36: Shop behavior is the v4.19.34 release again. The v4.19.35 changes are not in this deploy.
- v4.19.35: After refrigerant pressures, Guided Diagnostics authorizes rooftop assembly R&R and does not print the internal FACR prove guard or ask for the thermostat setpoint. Dry-and-wait with frost back replaces the cooling unit. Water Heaters stays at the top of the Guided Diagnostics category picker. The Level Up hose cite is the FW Owner's Manual page 13, and page 1 cites the Towable Owner's Manual page 15 with part 177094. Thetford kit sources drop install-step quotes that are not leak sentences.
- v4.19.34: A Thetford flush-lever leak keeps the next cited check when the draft is only a source line. An empty or source-only reply falls back to that check. A Level Up lead-jack turn answers the plumbing question once and does not wait on the model. Part 177094 cites the Level Up Towable Owner's Manual page 15 or the Level Up FW Owner's Manual page 18.
- v4.19.33: Shop behavior is the v4.19.29 release again. The v4.19.31 and v4.19.32 changes are not in this deploy.
- v4.19.32: Level Up front jacks that drift after a jack swap ask for the gray-wire coil, the swap plumbing, and the manual override screw before the lead-jack cartridge 177094.
- v4.19.31: The FACR retest NO goes out to the clear-drain end, and the drain NO sits off the line junction. After refrigerant pressures, Guided Diagnostics authorizes rooftop assembly R&R on CCD-0007990 and does not ask for pressures again. Overnight dry-and-wait with frost back replaces the cooling unit. Confirmed Girard seating is the repair. The cooktop repair repositions the thermocouple tip in the flame, and a run-on tip sentence does not ship. The Coleman authorization drops the extra stop line. Ask turns use a smaller library context and a low reasoning cap.
- v4.19.29: A Thetford flush-lever leak sheet keeps the English leak checks only: supply connection, water valve weeping at the pedal, vacuum breaker leaking during flush, then the floor flange. Multilingual lines, poor flush, flow rate, blade seal, frozen lines, and the riser stay off. Sources are the 42088 troubleshooting page, water valve kit 42109 page 1, and vacuum breaker kit 34122/34123.
- v4.19.28: A typed unit with no matching shop manual does not borrow another brand. Thetford with no Thetford document says so. The reading filler cannot ship on any path, including a job with no lock. Plumbing / Toilets is a library category.
- v4.19.27: A firm repair stays the repair. An answered check, including sail-switch continuity OK, is not asked again. The reading filler cannot ship. The Girard chart runs blower suction YES to the air-pressure switch, then that switch's own YES to the gas supply. The FACT12 E2 do-not says reseated.
- v4.19.26: A repair already proved is stated as the repair, and an answered check is not asked again or restated as the repair. The next turn is not a copy of the last one. Ground Control keeps FRONT five times, REAR five times, then ENTER. The Girard chart lines do not cross, and the FACT12 E2 chart says Reseat.
- v4.19.24: A Guided Diagnostics repair is chosen from the category and model, not from loose words in an earlier chat. Placeholders and broken If-sentences cannot ship, and a firm repair stays the repair. Bay sheets drop the reversed C/T note, cite Level Up page 1, name Brisk II page 23, and finish the FACT12 and Girard charts.
- v4.19.23: After the proving check, a reported result, "Not checked yet", or "What is the repair?" gets the next step and a conditional repair. A reply cannot be blank or a repeated sentence. Bay sheets close Fig. 36, drop the rear-stabilizer cite on a front jack, list Level Up documents only, and add the missing dial-off, FACT12, Girard, and Dometic lines.
- v4.19.22: Ask for the proving check before any repair. A later turn answers the new fact. Heard, Noted, repair-stands, and unchanged fillers stay off the reply. Girard E8 is the air-pressure switch at the blower. FACT12 E3 shows the 12 V and data-line path.
- v4.19.20: Start new chat clears Category. A named model beats a leftover category. A shop reply keeps a short traceable fact or none, and it always has a next step. A Bay sheet that names a page in PRIMARY keeps that page in Sources.
- v4.19.19: A Sources quote is copied from a retrieved manual chunk for that page, or the cite has no quote. Expected pages stay on the sheet. Guided Diagnostics does not show a model instruction, does not invent a fact the tech did not report, and does not echo a fallback question.
- v4.19.18: A Sources quote is one verbatim sentence from that page, or the page is cited with no quote. FACT12 repairs stay on a FACT12 model. The same canned reply is not sent twice in a row.
- v4.19.17: A Sources quote is one complete sentence about this procedure. Table glue, headings, catalog lines, scan text, and off-topic pages stay off the sheet. Guided Diagnostics drops an instruction echo, does not repeat a check the tech already answered, and gives the repair once the facts support it. The cooktop tip cites Suburban SDN2U page 4, Figs. 3-4. Turn-1 tongue, ceiling, and Ground Control replies are short steps.
- v4.19.16: Sources stay on the job: whole sentences only, no scanned fragments, and no snippet that contradicts the sheet. Internal index notes stay off the page. Figures keep their borders, YES/NO clears the arrowhead, and a clause dash stays a dash. The no-12V fan branch names the board and the fan. A blank stabilizer job still prints its model. Guided Diagnostics strips a leaked prompt and Start new chat clears Model.
- v4.19.15: A merge to main shows up on the sidebar by itself. The shop word list is plain text, so Community Cloud's GitHub sync can read the repo root and redeploy.
- v4.19.14: A source snippet ends at the last sentence that has a verb, so a trailing noun phrase such as "Fan quick connection to harness" is dropped. A cite that is only a part name stays.
- v4.19.13: The drainage figure includes the full row through its bottom rule, so "vehicle" is not cut. A hyphen after a single capital (F-, T-) stays, and a prepositional source fragment with no verb is dropped.
- v4.19.12: A page named in PRIMARY stays in Sources. A dictionary split runs only when both halves are words and the joined form is not, so ducted and petit stay whole. The drainage figure is one bordered table row. A cooktop sheet keeps thermocouple and flame lines only.
- v4.19.11: An em dash or en dash becomes a space, never a deleted character, so shop lines do not glue. All-lowercase joins such as willgo split when both parts are dictionary words. The drainage figure keeps the full row. Clean bay sheets are locked by text snapshots.
- v4.19.10: Bay sheets drop near-duplicate pages, stray question bullets, cut color endings, and leading figure numbers. Voltage ranges stay 3-9V or the clause is dropped. YES and NO sit on their arrows. The ice sheet has a unit ID line. A cooktop sheet cites the burner or the thermocouple, or the manual title alone.
- v4.19.9: Bay snippets join lines on a space, drop repeated clauses, boilerplate, and duplicate pages, and keep numeric ranges. Figures are a legible cited drawing or none. NO labels sit on their arrows. A FACT12 sheet that only has the FACR08 book says so.
- v4.19.8: A redeploy reloads every Bay PDF and content module whose revision is not this app version, so a cached import cannot keep the previous sheet. The bay sheet DATE is the Pacific calendar day.
- v4.19.7: Bay snippets are whole sentences (flowchart OCR, fig-ref scraps, part-number runs, and cut endings drop). Flowcharts follow the bay steps. Figures are full regions, not thin cut strips or a blank page. FACR08 CCD-0008666 is labeled as FACR08, and a front jack cites the front/PSX1 book
- v4.19.6: Bay sheets use the same correction as Guided Diagnostics (1-month cooling-unit close, ceiling thermostat 3311071, Ground Control zero-point, FACT12 freeze-sensor resecure, petit tube before the control board, full jack R&R, thermocouple tip). Captions match the figure, generated sketches are not OEM pages, and snippets are not cut mid-word
- v4.19.5: The Send path rewrites a B57915 turns-on / will-not-blow-cold reply after the model returns, from the raw complaint. A cached coach that still requires the word fan is reloaded.
- v4.19.4: Dometic B57915 that turns on and will not blow cold opens turn 1 on diagnostic manual 3311071: confirm the fan runs, then the Peacemaker bypass. A stated running fan still starts at the Peacemaker bypass.
- v4.19.3: Ground Control 343633 gives the Electric Leveling zero-point sequence once (manual level, FRONT five times, REAR five times, ENTER) and does not swap a sensor. Dometic B57915 fan-runs/no-cold opens on diagnostic manual 3311071 with the Peacemaker and ceiling-selector bypass. A library-coverage sentence is said at most once.
- v4.19.2: Bay sheets stay within 3 pages. Figures are the cited crop (1-2 per sheet), not a full manual page or a blank "Cited library figure" page. Generic steps are whole sentences, snippets drop OCR splits and parts-list dumps, the model line keeps the typed string, and a FACT12 file that is actually the FACR08 8K book is not cited as the FACT12 manual
- v4.18.1: Bay procedure PDF measures wrapped text before drawing; flowchart ovals, diamonds, and rectangles grow to the inscribed text box; section bars follow the previous block's real height
- Login + Roles (Technician / Manager)
- Certificate Hub
- Searchable Document Library by Category
- Guided Diagnostics Jobs (WO #) + interactive findings + warranty story
- Diagnostic INDEX charts: match ONE symptom row, expand real PROCEDURE tests in OEM order
- Source page viewer (Jobs WO panel; chat is on-demand only)
- Safety / Compliance + Meeting Acknowledgements
- Team Overview (Certificates + Safety Progress)
- AI Tech Story Improver (xAI Grok, Groq fallback) - standalone + end-of-job
- Guided Diagnostics chat (manuals + Grok/Groq)
- Tacoma RV Center shop branding (logo + colors)
- Permanent file storage via Cloudflare R2
- R2 re-link (recover library without re-upload)
- Library catalog export + manager backup warning
- Auto SQLite backup/restore to R2 (survives Streamlit wipes)
- Guided Diagnostics chats saved 30 days
- Write warranty story remounts the copy box and uses latest tech status
- Guided Diagnostics refuses wrong-brand manuals; TSB / Recall searched with the system category
- Warranty stories include every recorded reading without inventing tests
- Signed login cookie (~10 hours) so a dropped websocket does not force re-login
- Layout fills the screen (no 1200px cap)
- v4.8.2: harden Streamlit CSS so side gutters stay dead on Streamlit Cloud
- v4.8.2: Unity / OneControl CAN multiplex gate + OEM test order + Electrical cross-search
- v4.8.3: collapsed sidebar must not reserve 220px left gap
- v4.8.4: never brand-lock to empty; fridge synonyms + FCR model prefix match
- v4.8.4: fridge no-power OEM order (accessible fuse before teardown)
- v4.8.4: warranty story binds vague tech “pass/good” to coach’s last recommended test
- v4.8.5: coach language attributes excerpts to the shop Document Library - never “the text you uploaded”
- v4.8.5: Guided Diagnostics is a branching flowchart - 1-2 tests per turn, wait for results
- v4.8.5: warranty story cites 📖 Source (manual + page) on each tech-performed step
- v4.8.6: Guided Diagnostics chat does not dump source-page UI every turn
- v4.8.6: show library text/illustration pages ONLY when the tech asks
- v4.8.6: silent source ledger still records cited pages for the warranty story
- v4.8.7: never invent built-in fault/blink LEDs; Furrion FCR flash codes need SM clip-on diagnostic LED (or skip that gate)
- v4.8.8: figure/page requests lock to the cited manual only - never cross-book Fig./page matches
- v4.8.9: never emit markdown/fake images; 📖 Source page must match the claim; only R2 renderer shows photos
- v4.9.0: data-plate photo fills Model/System (camera or upload; uses existing shop AI key)
- v4.9.1: fix library page miss — Source en-dash cites + page-of-manual + DB title fallback for figures
- v4.9.2: rebuild Guided Diagnostics page pipeline — detect→parse→resolve Document/page→R2+pymupdf render
- v4.10.0: Guided Testing flowchart ENGINE — hard procedure trees; TECH reports, tree edges decide next gate
- v4.10.0: Furrion FCR CCD-0008122 tree (fuse→dial/battery→paper→operating?/Not Cooling); no invented fan volts after paper
- v4.10.1: fix Yes/No gate buttons (no ask_input write after widget); map not-operating tech language on operating diamond
- v4.13.0: Guided Diagnostics chat is a SIMPLE open library coach (cite shop manuals; questions; figures; pivots)
- v4.13.0: hard-tree / Yes-No gate quiz does not drive GD chat; never re-ask facts the tech already stated
- v4.13.0: plate photo uses working Groq vision (qwen/qwen3.6-27b) after xAI; llama-4-scout 404 retired
- v4.13.1: figure/terminal asks retrieve real SM diagram pages (not Quick Notes p.13)
- v4.13.2: Level Up Advantage / 807662 library search prefers Level-Up/OCTP/TI over Unity board SM
- v4.13.3: Air Conditioning GD search skips Unity board SM unless the tech names OneControl/Unity/CAN
- v4.13.4: Streamlit loads gd_library_coach from this file's folder (no stale/missing-module ImportError)
- v4.13.5: Furrion FCR E2 / Fan Fault Current can reach freezer evaporator fan R&R (and board+fan)
- v4.13.6: Water Heaters / Girard GSWH-2 E8 GD search skips Unity and keeps E8 / CCD-0009390 chunks
- v4.13.7: GD category picker includes Water Heaters and Range & Cooktops (seed upserts missing names)
- v4.13.8: cooktop pan-on flame-out checks thermocouple tip with pan on; PSX1 seized override pin is complete jack assembly R&R
- v4.13.9: reload stale gd_library_coach when category constants are missing (Streamlit AttributeError)
- v4.13.10: fridge rear/back-wall ice/frost retrieves CCD-0008122 Ice and Moisture p.36 / Fig.36 (not fuse/12V)
- v4.13.11: Furrion FACR* rooftop freeze/condensate/base-pan ranks CCD-0007990 with CCD-0008666
- v4.13.12: Level Up Manual Mode flash-home + Auto works is Firefly/OneControl CAN isolate (terminator in)
- v4.14.0: Bay procedure PDF replaces Diagnostic Jobs as the printable plan UI (GD chat stays)
- v4.14.1: FCR08/FCR10 dial OFF + compressor running jumps to thermostat C/T prove (part 2021128850), not fuse/12V; GD retries a 413 with a smaller payload
- v4.15.0: Bay procedure PDF is a human bay sheet — drawn yes/no flowchart, punch list, small 3C footer
- v4.19.1: FACR freeze authorizes rooftop assembly R&R only after refrigerant pressures are reported. FCR rear-wall ice closes with a 1-month watch, then replace the unit. Ground Control 343633 retrieval matches the Bay PDF Ground Control book and ends at manual level plus zero-point calibration. Dometic B57915 fan-runs/no-cold uses diagnostic manual 3311071 and replaces the ceiling thermostat/selector when both bypasses cool. Suburban NT-20SEQT commits to the wall thermostat after an R/W jumper that lights and runs. SDN2U tip-low pan-on flame-out states the tip-position repair
- v4.19.0: AI calls time out (150s, no SDK retries) and fall back or show a send-again message instead of hanging the page; the selected section and GD Category/Model stay across reruns; Ctrl+Enter sends; inactive sections are not drawn under the active one, so the Stop indicator can clear when the run finishes
- v4.18.4: Guided Diagnostics replies and Bay PDF sheets use shop words (output wire, check the wire, check the circuit). A final pass rewrites engineering jargon in guard text, flowchart labels, bay-order steps, and sheet excerpts. Marked OEM source quotes stay verbatim
- v4.18.3: Bay PDF SOURCES use a human document title, keep only cites that belong to the procedure, and quote whole sentences. Raw filenames, flat-rate lines for a different assembly, and mid-word OCR scraps stay off the sheet
- v4.18.2: Generic bay sheets turn cited manual text into yes/no steps and end at a confirmed correction. OCR headers, footers, and duplicated words are stripped from the bay order and from SOURCES. A furnace job jumps R/W at the furnace, then proves the sail switch. Furrion FCR E2 follows Fan Fault Diagnostics and ends at the inverter PCB and fan. The MODEL line no longer repeats the brand.
- v4.18.1: Bay procedure PDF keeps a known brand on its own manuals. Coleman-Mach 2111-0001 cites the Coleman rooftop books (12VDC wall-thermostat SM, 1976-536 and 1976-603, Peacemaker, 1976-695) and ends at fan motor plus control board only. If that brand has no manual, the sheet says so instead of citing another brand
- v4.18.0: Guided Diagnostics, warranty story, and data-plate photos call xAI first (grok-4.6); Groq is the automatic fallback when the primary key is missing or the provider returns 401/403, 429, 5xx, timeout, or a transport error
- v4.17.0: FACR08 freeze/leak climax is an authorization card for rooftop assembly R&R (CCD-0007990), never a library-miss R&R refusal or a compressor/DC-bus detour; Coleman-Mach 2111-0001 authorizes fan motor and control board only when Fan High is dead, the Peacemaker fan is locked, and the run cap is good
- v4.16.1: FACR08 freeze/leak terminal card is rooftop assembly R&R (CCD-0007990) after the drain/pan/filter/suction/sensor/nozzle/pressure path, never a blank card
- v4.16.0: BAL tongue-only dead climaxes at soft-touch panel 20300427; FACR freeze continues to rooftop assembly R&R; FCR10 OFF bay sheet locks part G 2021128850
- Mobile-friendly
"""
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil
import hashlib
import secrets
import io
import re
import json
import base64
import time
import library_bulk_import


def product_version_from_doc(doc):
    """First vX.Y.Z in the module docstring is the live sidebar version.

    The header line (``RV TechTrack v4.19.19``) is canonical. Later changelog
    bullets must not override it.
    """
    match = re.search(r"\bv\d+\.\d+\.\d+\b", doc or "")
    return match.group(0) if match else "unknown"


# Sidebar deploy signal. Bump the module docstring header, not a caption literal.
APP_VERSION = product_version_from_doc(__doc__)

try:
    import extra_streamlit_components as stx
    COOKIE_MGR_AVAILABLE = True
except ImportError:
    COOKIE_MGR_AVAILABLE = False

try:
    from itsdangerous import URLSafeTimedSerializer, BadSignature, BadTimeSignature
    ITSDANGEROUS_AVAILABLE = True
except ImportError:
    ITSDANGEROUS_AVAILABLE = False

try:
    import boto3
    from botocore.client import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import fitz  # pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Sentinels that must exist on a cached gd_library_coach. Streamlit Cloud can
# keep a pre-v4.13.7 coach that has cooktop/stab helpers but no category constants.
_GDC_STALE_GUARD_ATTRS = (
    "is_fcr_e2_fan_fault_context",
    "is_cooktop_pan_on_flameout_context",
    "is_stabilizer_override_pin_context",
    "is_facr_rooftop_freeze_context",
    "is_bal_soft_touch_tongue_only_context",
    "is_coleman_2111_context",
    "asked_brands_for_lookup",
    "chunk_matches_asked_brand",
    "COACH_REVISION",
    "AIR_CONDITIONING_CATEGORY",
    "DEFAULT_LIBRARY_CATEGORIES",
    "RANGE_COOKTOPS_CATEGORY",
    "REFRIGERATORS_CATEGORY",
    "WATER_HEATERS_CATEGORY",
    "PLUMBING_TOILETS_CATEGORY",
    "gd_category_select_options",
    "library_category_picker_names",
)
# Must match the docstring header (APP_VERSION) and each sibling MODULE_REVISION.
# A cached module is dropped when the stamp is missing or not this revision,
# even if every older function name is still present. Equality, not sort order:
# "v4.19.10" is not older than "v4.19.9" as text.
_GDC_REQUIRED_REVISION = "v4.19.65"
# Import order. gd_llm and the photo helper have no app import at load time.
# manual_figures is next because the coach and the figure bank import it while
# they load. The coach is before the figure bank, which imports it.
_APP_MODULES = (
    "gd_llm",
    "gd_step_photo",
    "manual_figures",
    "gd_library_coach",
    "library_figure_backfill",
)


def _app_module_lock():
    """ONE process-wide lock for loading the sibling modules.

    Streamlit runs every session's script in its own thread. On a reboot two sessions ran this loader at once: one
    thread had put a half-executed sibling module into sys.modules (MODULE_REVISION already set near the top), the
    other took it as current and failed with an ImportError on a name defined further down (live 2026-10-20). The script itself is re-executed per run, so the lock lives on a stable holder in sys.modules."""
    import sys
    import threading
    import types

    holder = sys.modules.get("_techtrack_module_lock")
    if holder is None:
        fresh = types.ModuleType("_techtrack_module_lock")
        fresh.lock = threading.RLock()
        holder = sys.modules.setdefault("_techtrack_module_lock", fresh)   # atomic: every thread gets the same lock
    return holder.lock


def _cached_module_is_current(mod, required_revision, required_attrs=()):
    """True only when a cached module's stamp equals this app revision."""
    if mod is None:
        return False
    module_rev = getattr(mod, "MODULE_REVISION", None)
    coach_rev = getattr(mod, "COACH_REVISION", None)
    if module_rev in (None, "") and coach_rev in (None, ""):
        return False
    if module_rev not in (None, "") and str(module_rev) != required_revision:
        return False
    if coach_rev not in (None, "") and str(coach_rev) != required_revision:
        return False
    if required_attrs and not all(hasattr(mod, name) for name in required_attrs):
        return False
    return True


def _reload_app_module(name, required_revision, required_attrs=()):
    """
    Load one sibling module from this file's folder.

    Streamlit re-executes rv_techtrack.py on redeploy and leaves sys.modules
    in place. A plain import then binds the previous function objects. Drop
    that cache when MODULE_REVISION / COACH_REVISION is missing or is not
    this app version, then execute the file that shipped with this deploy.
    A matching revision is returned as-is so a later rerun does not reload.
    """
    import importlib.util
    import sys

    path = Path(__file__).resolve().parent / f"{name}.py"
    if not path.is_file():
        raise ImportError(
            f"{name}.py is missing next to rv_techtrack.py ({path}). "
            "Deploy the full GitHub repo, not only the main file."
        )
    root = str(path.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    with _app_module_lock():
        cached = sys.modules.get(name)
        if _cached_module_is_current(cached, required_revision, required_attrs):
            return cached
        sys.modules.pop(name, None)
        spec = importlib.util.spec_from_file_location(name, str(path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {name} from {path}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod   # needed while it runs (dataclasses, its own imports); other threads wait on the lock
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            # never leave a half-run module behind for the next import to bind
            if sys.modules.get(name) is mod:
                sys.modules.pop(name, None)
            raise
        return mod


def _load_gd_library_coach():
    """Load gd_library_coach.py from this file's folder. See _reload_app_module."""
    return _reload_app_module(
        "gd_library_coach",
        _GDC_REQUIRED_REVISION,
        required_attrs=_GDC_STALE_GUARD_ATTRS,
    )


def _log_loaded_revision(name, mod, required_revision):
    """Log the MODULE_REVISION that is actually bound for this module."""
    import logging

    loaded = getattr(mod, "MODULE_REVISION", None)
    if loaded in (None, ""):
        loaded = getattr(mod, "COACH_REVISION", None)
    loaded = "" if loaded in (None, "") else str(loaded)
    log = logging.getLogger("techtrack.modules")
    if loaded != str(required_revision):
        log.error(
            "MODULE_REVISION %s=%s expected %s",
            name,
            loaded or "missing",
            required_revision,
        )
        return
    log.warning("MODULE_REVISION %s=%s", name, loaded)


def _reload_stale_app_modules(required_revision):
    """Reload every Guided Diagnostics and library module when its stamp is old.

    A module that imports an earlier one is loaded again when that dependency
    was replaced, so it cannot keep the previous function objects. Each module
    logs the revision that ended up bound.
    """
    import sys

    with _app_module_lock():
        return _reload_stale_app_modules_locked(required_revision)


def _reload_stale_app_modules_locked(required_revision):
    import sys

    dependency_replaced = False
    coach = None
    for name in _APP_MODULES:
        if dependency_replaced:
            sys.modules.pop(name, None)
        before = sys.modules.get(name)
        attrs = _GDC_STALE_GUARD_ATTRS if name == "gd_library_coach" else ()
        mod = _reload_app_module(name, required_revision, required_attrs=attrs)
        if mod is not before:
            dependency_replaced = True
        if name == "gd_library_coach":
            coach = mod
        _log_loaded_revision(name, mod, required_revision)
    return coach


_gdc = _load_gd_library_coach()
# After the loader slice tests exec. APP_VERSION is this deploy's header.
# Rebind the coach after the ordered reload. An earlier pass can bind it
# before manual_figures is current.
_gdc = _reload_stale_app_modules(APP_VERSION)
# Import after the reload so this script binds the new function objects.
# Streamlit Cloud does not always start with the repo root on sys.path.
import gd_llm
AC_HINT_TITLES = _gdc.AC_HINT_TITLES
FURRION_FCR_BOARD_FIGURE_PAGES = _gdc.FURRION_FCR_BOARD_FIGURE_PAGES
HARD_TREE_EXCLUSIVE_CHAT = _gdc.HARD_TREE_EXCLUSIVE_CHAT
LEVEL_UP_ADVANTAGE_HINT_TITLES = _gdc.LEVEL_UP_ADVANTAGE_HINT_TITLES
WATER_HEATER_HINT_TITLES = _gdc.WATER_HEATER_HINT_TITLES
DEFAULT_LIBRARY_CATEGORIES = _gdc.DEFAULT_LIBRARY_CATEGORIES
gd_category_select_options = _gdc.gd_category_select_options
library_category_picker_names = _gdc.library_category_picker_names
figure_render_honesty_note = _gdc.figure_render_honesty_note
groq_vision_model_candidates = _gdc.groq_vision_model_candidates
is_ac_library_title = _gdc.is_ac_library_title
is_air_conditioning_context = _gdc.is_air_conditioning_context
is_furrion_ccd_0008122 = _gdc.is_furrion_ccd_0008122
is_level_up_advantage_context = _gdc.is_level_up_advantage_context
is_level_up_library_title = _gdc.is_level_up_library_title
is_unity_board_manual = _gdc.is_unity_board_manual
is_water_heater_context = _gdc.is_water_heater_context
is_water_heater_library_title = _gdc.is_water_heater_library_title
page_has_figure_or_terminal_layout = _gdc.page_has_figure_or_terminal_layout
page_is_text_only_notes = _gdc.page_is_text_only_notes
pick_diagram_page_numbers = _gdc.pick_diagram_page_numbers
complete_chat_with_payload_retry = _gdc.complete_chat_with_payload_retry
wants_board_or_terminal_figure = _gdc.wants_board_or_terminal_figure
wants_library_page_shown = _gdc.wants_library_page_shown
xai_vision_model_candidates = _gdc.xai_vision_model_candidates

# ---------------- SHOP BRANDING ----------------
HEADER_GREEN = "#038944"
DEALER_RED = "#DF1F26"
NAVY = "#01147C"
DARKER_GREEN = "#02763A"


def shop_logo_path():
    """Official Tacoma RV Center logo. Prefer assets/ next to this script."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "assets" / "tacoma-rv-logo.png",
        here / "tacoma-rv-logo.png",
        Path.cwd() / "assets" / "tacoma-rv-logo.png",
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


# ---------------- PAGE CONFIG ----------------
_logo_for_icon = shop_logo_path()
st.set_page_config(
    page_title="TechTrack · Tacoma RV Center",
    page_icon=str(_logo_for_icon) if _logo_for_icon else "🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
    /* Tacoma RV Center shop colors: header green, dealer red, navy */
    header[data-testid="stHeader"] {
        background-color: #038944;
    }
    .stButton > button {
        min-height: 2.6rem;
        font-size: 1.02rem;
        border-radius: 8px;
    }
    button[kind="primary"],
    [data-testid="stBaseButton-primary"],
    .stFormSubmitButton button,
    div[data-testid="stFormSubmitButton"] button {
        background-color: #DF1F26 !important;
        border-color: #9D151A !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover,
    .stFormSubmitButton button:hover,
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #9D151A !important;
        border-color: #9D151A !important;
        color: #ffffff !important;
    }
    button[kind="secondary"],
    [data-testid="stBaseButton-secondary"] {
        border-color: #038944 !important;
        color: #02763A !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px;
    }
    /* v4.8.2 - kill Streamlit side gutters / 730-1200px content box */
    html, body, [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    .stApp, section.main {
        max-width: 100% !important;
    }
    .block-container,
    [data-testid="stMainBlockContainer"],
    [data-testid="stAppViewContainer"] > .main > .block-container,
    section.main > div.block-container,
    .main .block-container {
        max-width: none !important;
        width: 100% !important;
        padding-top: 2.4rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }
    [data-testid="stSidebar"] ~ section.main,
    [data-testid="stAppViewContainer"] section.main {
        max-width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"] {
        margin-top: 0.55rem;
        margin-bottom: 0.3rem;
    }
    [data-testid="stTabs"] button {
        font-size: 1rem;
        font-weight: 600;
        white-space: nowrap;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #038944 !important;
    }
    /* Keyed section radio. Wrap on a phone. Selected label uses shop green. */
    div[data-testid="stRadio"] [role="radiogroup"] {
        flex-wrap: wrap;
        gap: 0.35rem 0.9rem;
    }
    div[data-testid="stRadio"] label:has(input:checked) {
        color: #038944 !important;
        font-weight: 700;
    }
    /* v4.8.3 - collapsed sidebar must not reserve flex width */
    section[data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 220px;
    }
    section[data-testid="stSidebar"][aria-expanded="false"] {
        min-width: 0 !important;
        width: 0 !important;
        max-width: 0 !important;
        flex: 0 0 0px !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        border: none !important;
        transform: translateX(-100%) !important;
    }
    section[data-testid="stSidebar"][aria-expanded="false"] > * {
        min-width: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
    }
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMain"],
    section.main {
        margin-left: 0 !important;
        flex: 1 1 100% !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    h1, h2, h3 {
        color: #01147C;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- CONFIG ----------------
DB_PATH = "rv_techtrack_v4.db"
R2_DB_KEY = "backups/rv_techtrack_v4.db"
R2_DB_PREV_KEY = "backups/rv_techtrack_v4.prev.db"
MIN_DOCS_TO_BACKUP = 10
BACKUP_DEBOUNCE_SEC = 90
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# ---------------- R2 STORAGE ----------------
def get_r2_client():
    if not BOTO3_AVAILABLE:
        return None
    try:
        needed = ["R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]
        if any(k not in st.secrets for k in needed):
            return None
        return boto3.client(
            "s3",
            endpoint_url=st.secrets["R2_ENDPOINT_URL"],
            aws_access_key_id=st.secrets["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["R2_SECRET_ACCESS_KEY"],
            config=Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=45,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
            region_name="auto",
        )
    except Exception:
        return None


def r2_delete_object(key: str) -> bool:
    """Delete one bulk-import staging ZIP. Document, certificate, and backup keys stay."""
    if not library_bulk_import.is_bulk_staging_key(key):
        return False
    client = get_r2_client()
    if not client or not key:
        return False
    try:
        client.delete_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=key)
        return True
    except Exception:
        return False


def r2_put_bytes(file_obj, key: str, content_type: str = "application/octet-stream") -> bool:
    """Upload bytes to R2. Bulk import uses this so a failed file does not write a page error."""
    client = get_r2_client()
    if not client or not key:
        return False
    try:
        client.put_object(
            Bucket=st.secrets["R2_BUCKET_NAME"],
            Key=key,
            Body=file_obj,
            ContentType=content_type or "application/octet-stream",
        )
        return True
    except Exception:
        return False


def r2_upload(file_obj, key: str, content_type: str = "application/octet-stream") -> bool:
    client = get_r2_client()
    if not client:
        return False
    try:
        client.put_object(
            Bucket=st.secrets["R2_BUCKET_NAME"],
            Key=key,
            Body=file_obj,
            ContentType=content_type,
        )
        return True
    except Exception as e:
        st.error(f"Upload to storage failed: {e}")
        return False


def r2_download_bytes(key: str):
    client = get_r2_client()
    if not client or not key:
        return None
    try:
        obj = client.get_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=key)
        return obj["Body"].read()
    except Exception:
        return None


def r2_download_to_file(key: str, dest) -> bool:
    """Stream one object to disk. Used for a staging ZIP so it is not held in memory."""
    client = get_r2_client()
    if not client or not key:
        return False
    path = Path(dest)
    try:
        obj = client.get_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=key)
        body = obj["Body"]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as out:
            while True:
                chunk = body.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        return path.is_file() and path.stat().st_size > 0
    except Exception:
        return False


def r2_configured() -> bool:
    """R2 settings present (no client is built and nothing is fetched)."""
    try:
        return BOTO3_AVAILABLE and all(k in st.secrets for k in ("R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME"))
    except Exception:
        return False


def r2_download_button(label: str, key: str, filename: str, button_key: str):
    """Download button that fetches the file from R2 only when it is clicked.

    Rendering a list of documents must never download them: the old version read every PDF of the
    selected category from R2 on every rerun, so Manage Documents never finished loading.
    """
    if not key:
        st.caption("No file on record")
        return
    if not r2_configured():
        st.caption("Storage not configured")
        return

    def _fetch():
        data = r2_download_bytes(key)
        if data is None:
            raise RuntimeError(f"Could not download {key} from storage")
        return data

    st.download_button(label, data=_fetch, file_name=filename, key=button_key, on_click="ignore")


def r2_available() -> bool:
    return get_r2_client() is not None and "R2_BUCKET_NAME" in st.secrets


def r2_list_keys(prefix: str = "", max_keys: int = 500):
    """List object keys in the R2 bucket under prefix."""
    client = get_r2_client()
    if not client:
        return [], "Storage not configured"
    keys = []
    try:
        token = None
        while len(keys) < max_keys:
            kwargs = {
                "Bucket": st.secrets["R2_BUCKET_NAME"],
                "Prefix": prefix or "",
                "MaxKeys": min(1000, max_keys - len(keys)),
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            for item in resp.get("Contents") or []:
                k = item.get("Key") or ""
                if k and not k.endswith("/"):
                    keys.append(k)
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return keys, ""
    except Exception as e:
        return [], f"Could not list storage: {e}"


def r2_prefix_totals(prefixes):
    """Count objects and sum sizes under each prefix.

    Returns ``(totals, error)``. A listing failure leaves totals empty so the
    caller can still show the document count and the database file size.
    ``bytes_known`` is false when the API omits Size.
    """
    client = get_r2_client()
    try:
        bucket = st.secrets["R2_BUCKET_NAME"]
    except Exception:
        bucket = None
    if not client or not bucket:
        return {}, "Storage not configured"
    grouped = {prefix: [] for prefix in prefixes}
    truncated = {prefix: False for prefix in prefixes}
    cap = 20000
    try:
        for prefix in prefixes:
            token = None
            while True:
                kwargs = {
                    "Bucket": bucket,
                    "Prefix": prefix or "",
                    "MaxKeys": 1000,
                }
                if token:
                    kwargs["ContinuationToken"] = token
                resp = client.list_objects_v2(**kwargs)
                for item in resp.get("Contents") or []:
                    grouped[prefix].append(item)
                    if len(grouped[prefix]) >= cap:
                        truncated[prefix] = True
                        break
                if truncated[prefix] or not resp.get("IsTruncated"):
                    break
                token = resp.get("NextContinuationToken")
                if not token:
                    break
        totals = library_bulk_import.summarize_prefix_objects(grouped)
        for prefix, hit in truncated.items():
            if prefix in totals and hit:
                totals[prefix]["truncated"] = True
        return totals, ""
    except Exception as e:
        return {}, f"Could not list storage: {e}"


def r2_key_already_registered(key: str) -> bool:
    if session.query(Document).filter_by(file_path=key).first():
        return True
    if session.query(Certificate).filter_by(file_path=key).first():
        return True
    if session.query(SafetyDocument).filter_by(file_path=key).first():
        return True
    if session.query(SafetyMeeting).filter_by(file_path=key).first():
        return True
    return False


def guess_title_from_key(key: str) -> str:
    name = key.split("/")[-1]
    name = re.sub(r"^\d+_\d+_", "", name)
    name = re.sub(r"^[a-f0-9]{8,}_", "", name, flags=re.I)
    name = re.sub(r"\.[^.]+$", "", name)
    name = name.replace("_", " ").replace("-", " ").strip()
    return name or key


def export_library_catalog() -> str:
    """JSON catalog of documents so titles/keywords survive even if DB is lost."""
    cats = {c.id: c.name for c in session.query(Category).all()}
    rows = []
    for d in session.query(Document).order_by(Document.id).all():
        rows.append({
            "id": d.id,
            "title": d.title,
            "keywords": d.keywords,
            "category": cats.get(d.category_id, ""),
            "category_id": d.category_id,
            "file_path": d.file_path,
            "file_type": d.file_type,
            "indexed": bool(d.indexed),
            "clean_title": d.clean_title or "",
            "brand": d.brand or "",
            "product_line": d.product_line or "",
            "models": d.models or "",
            "doc_type": d.doc_type or "",
            "doc_number": d.doc_number or "",
            "ti_number": d.ti_number or "",
            "revision_date": d.revision_date or "",
        })
    return json.dumps({"exported_at": datetime.now().isoformat(), "documents": rows}, indent=2)

# ---------------- DATABASE MODELS ----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(20), default="Technician")
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=func.now())


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    title = Column(String(250), nullable=False)
    file_path = Column(String(400), nullable=False)
    file_type = Column(String(20), default="pdf")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())
    keywords = Column(Text, default="")
    indexed = Column(Boolean, default=False)
    index_note = Column(String(250), default="")
    content_sha256 = Column(String(64), default=None)
    doc_type = Column(String(80), default="")
    ti_number = Column(String(80), default="")
    import_tier = Column(Integer, default=None)
    byte_size = Column(Integer, default=None)
    needs_ocr = Column(Boolean, default=False)
    clean_title = Column(String(250), default=None)
    brand = Column(String(80), default=None)
    product_line = Column(String(150), default=None)
    models = Column(Text, default=None)
    doc_number = Column(String(80), default=None)
    revision_date = Column(String(40), default=None)


class DocChunk(Base):
    __tablename__ = "doc_chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    title = Column(String(250), default="")
    page = Column(Integer, default=1)
    chunk_text = Column(Text, nullable=False)
    keywords = Column(Text, default="")


class DocAsset(Base):
    """Key for a page PNG or figure crop stored in R2.

    ``image_path`` is the object key. The caption, page, box, and chunk link
    live on this row. The PNG bytes do not. ``png_blob`` stays empty so an
    older database file still opens.
    """
    __tablename__ = "doc_assets"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    page = Column(Integer, nullable=False, default=1)
    kind = Column(String(20), nullable=False, default="page")
    label = Column(String(120), default="")
    image_path = Column(String(400), default="")
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)
    png_blob = Column(LargeBinary)
    caption = Column(Text, default="")
    bbox = Column(String(80), default="")
    chunk_id = Column(Integer, default=None)


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(250), nullable=False)
    issuer = Column(String(150), default="")
    file_path = Column(String(400), nullable=False)
    issued_date = Column(String(50), default="")
    notes = Column(Text, default="")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())


class SafetyDocument(Base):
    __tablename__ = "safety_documents"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    file_path = Column(String(400), nullable=False)
    file_type = Column(String(20), default="pdf")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())
    keywords = Column(Text, default="")


class SafetyMeeting(Base):
    __tablename__ = "safety_meetings"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    meeting_date = Column(String(50), default="")
    file_path = Column(String(400), default="")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())


class SafetyAcknowledgement(Base):
    __tablename__ = "safety_acknowledgements"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("safety_meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signed_at = Column(DateTime, default=func.now())
    understood = Column(Boolean, default=True)


class DiagnosticJob(Base):
    """Work-order based diagnostic session - resume anytime, story at end."""
    __tablename__ = "diagnostic_jobs"
    id = Column(Integer, primary_key=True)
    wo_number = Column(String(80), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_name = Column(String(150), default="")
    model_text = Column(String(250), default="")
    concern = Column(Text, default="")
    plan_text = Column(Text, default="")
    findings = Column(Text, default="")
    step_log = Column(Text, default="[]")
    sources_text = Column(Text, default="")
    sources_json = Column(Text, default="[]")
    final_story = Column(Text, default="")
    status = Column(String(30), default="in_progress")
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())
    ask_chat_id = Column(Integer, nullable=True, index=True)   # the GD chat a past work order came from (gd_work_orders)


class AskChat(Base):
    """Saved Ask TechTrack conversation (30-day retention)."""
    __tablename__ = "ask_chats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_name = Column(String(150), default="")
    model_text = Column(String(250), default="")
    title = Column(String(250), default="")
    final_story = Column(Text, default="")
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())


class AskMessage(Base):
    __tablename__ = "ask_messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("ask_chats.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, default="")
    created_date = Column(DateTime, default=func.now())


Base.metadata.create_all(engine)
session = Session()


def _ensure_schema_upgrades():
    try:
        with engine.connect() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documents)").fetchall()]
            if "indexed" not in cols:
                conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN indexed BOOLEAN DEFAULT 0")
            if "index_note" not in cols:
                conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN index_note VARCHAR(250)")
            job_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(diagnostic_jobs)").fetchall()]
            if "sources_json" not in job_cols:
                conn.exec_driver_sql("ALTER TABLE diagnostic_jobs ADD COLUMN sources_json TEXT")
            if "ask_chat_id" not in job_cols:
                conn.exec_driver_sql("ALTER TABLE diagnostic_jobs ADD COLUMN ask_chat_id INTEGER")
            conn.commit()
    except Exception:
        pass
    try:
        library_bulk_import.ensure_schema(engine)
    except Exception:
        pass
    try:
        import library_figure_backfill as _figure_backfill

        _figure_backfill.ensure_schema(engine)
    except Exception:
        pass


_ensure_schema_upgrades()


def _local_doc_count() -> int:
    try:
        return session.query(Document).count()
    except Exception:
        return 0


def _reopen_db():
    global engine, session
    try:
        session.close()
    except Exception:
        pass
    try:
        engine.dispose()
    except Exception:
        pass
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Session.configure(bind=engine)
    session = Session()
    _ensure_schema_upgrades()
    _reset_page_finder()


def _reset_page_finder():
    """The page-finder reads titles/brands/categories from the app DB; after a restore it must re-read them."""
    global _gd_finder
    _gd_finder = None
    try:
        from pagefinder import search as _pf_search
        _pf_search._L = None
    except Exception:
        pass


def db_snapshot_bytes() -> bytes:
    """A consistent copy of the live DB (SQLite online backup), made only when the download is clicked."""
    import sqlite3
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "snap.db")
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(out)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        with open(out, "rb") as fh:
            return fh.read()


def check_db_backup_bytes(data: bytes) -> str:
    """'' when the bytes are a sound TechTrack DB, else why not (nothing is written)."""
    import sqlite3
    import tempfile
    if not data or not data.startswith(b"SQLite format 3"):
        return "That file is not a SQLite database."
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "check.db")
        with open(path, "wb") as fh:
            fh.write(data)
        try:
            c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            if c.execute("pragma integrity_check").fetchone()[0] != "ok":
                return "The database file is damaged (integrity check failed)."
            have = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
            missing = {"users", "documents", "doc_chunks", "categories"} - have
            if missing:
                return "Not a TechTrack database (missing tables: " + ", ".join(sorted(missing)) + ")."
            if not c.execute("select count(*) from users").fetchone()[0]:
                return "The database has no users; restoring it would lock everyone out."
            c.close()
        except Exception as exc:
            return f"Could not read the database: {exc}"
    return ""


def restore_db_from_bytes(data: bytes) -> str:
    """Replace the live DB with a checked backup: keep a .bak, swap atomically, reopen. '' on success, else why not."""
    why = check_db_backup_bytes(data)
    if why:
        return why
    tmp = DB_PATH + ".restore_tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    try:
        session.close()
    except Exception:
        pass
    try:
        engine.dispose()
    except Exception:
        pass
    if Path(DB_PATH).exists():
        shutil.copy(DB_PATH, DB_PATH + ".bak")
    os.replace(tmp, DB_PATH)
    _reopen_db()
    return ""


def maybe_restore_db_from_r2() -> bool:
    """If Streamlit wiped the local DB, pull the last good copy from R2."""
    if not r2_available():
        return False
    local_n = _local_doc_count()
    if local_n >= MIN_DOCS_TO_BACKUP:
        return False
    data = r2_download_bytes(R2_DB_KEY)
    if not data or len(data) < 50000 or not data.startswith(b"SQLite format 3"):
        return False
    try:
        if Path(DB_PATH).exists():
            shutil.copy(DB_PATH, DB_PATH + ".pre_restore")
        with open(DB_PATH, "wb") as f:
            f.write(data)
        _reopen_db()
        restored_n = _local_doc_count()
        if restored_n < max(local_n, 1):
            if Path(DB_PATH + ".pre_restore").exists():
                shutil.copy(DB_PATH + ".pre_restore", DB_PATH)
                _reopen_db()
            return False
        try:
            st.session_state["_db_restored_from_r2"] = True
            st.session_state["_db_restored_docs"] = restored_n
        except Exception:
            pass
        return True
    except Exception:
        return False


def maybe_backup_db_to_r2(force: bool = False):
    """Upload the full SQLite file to R2. Never overwrite a good cloud copy with an empty local DB."""
    if not r2_available():
        return False, "Storage not configured"
    local_n = _local_doc_count()
    if local_n < MIN_DOCS_TO_BACKUP:
        return False, "Local library too small to overwrite the cloud backup"
    if not Path(DB_PATH).exists():
        return False, "No local database file"
    now = time.time()
    try:
        last = float(st.session_state.get("_db_backup_ts") or 0)
        last_mtime = float(st.session_state.get("_db_backup_mtime") or 0)
    except Exception:
        last, last_mtime = 0.0, 0.0
    if not force and (now - last) < BACKUP_DEBOUNCE_SEC:
        return False, "Recently saved"
    mtime = Path(DB_PATH).stat().st_mtime
    if not force and last_mtime and mtime <= last_mtime:
        return False, "No database changes"
    client = get_r2_client()
    if not client:
        return False, "Storage not configured"
    try:
        try:
            client.copy_object(
                Bucket=st.secrets["R2_BUCKET_NAME"],
                CopySource={"Bucket": st.secrets["R2_BUCKET_NAME"], "Key": R2_DB_KEY},
                Key=R2_DB_PREV_KEY,
            )
        except Exception:
            pass
        tmp = DB_PATH + ".r2snap"
        import sqlite3
        src_con = sqlite3.connect(DB_PATH)
        dst_con = sqlite3.connect(tmp)
        with dst_con:
            src_con.backup(dst_con)
        dst_con.close()
        src_con.close()
        with open(tmp, "rb") as f:
            ok = r2_upload(f, R2_DB_KEY, "application/x-sqlite3")   # streamed from disk, not read whole into RAM (memtest 2026-11-03)
        try:
            os.remove(tmp)
        except OSError:
            pass
        if ok:
            try:
                st.session_state["_db_backup_ts"] = now
                st.session_state["_db_backup_mtime"] = mtime
                st.session_state["_db_backup_ok"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state["_db_backup_docs"] = local_n
            except Exception:
                pass
            return True, f"Saved {local_n} documents to cloud"
        return False, "Upload failed"
    except Exception as e:
        return False, str(e)


def purge_old_ask_chats(days: int = 30):
    try:
        cutoff = datetime.now() - timedelta(days=days)
        old = session.query(AskChat).filter(AskChat.updated_date < cutoff).all()
        for chat in old:
            session.query(AskMessage).filter_by(chat_id=chat.id).delete()
            session.delete(chat)
        if old:
            session.commit()
    except Exception:
        session.rollback()


def save_gd_work_order(user_id, *, only_if_closed_or_saved=False, wo_number=""):
    """Past work orders (gd_work_orders): save the open GD job as a DiagnosticJob row. The case state is used only when it
    belongs to this chat (gd_case_chat_id); a reopened chat keeps what its earlier save recorded.
    only_if_closed_or_saved: the per-turn auto-save, which writes when the job closed or a work order already exists."""
    import gd_work_orders as wo

    chat_id = st.session_state.get("ask_chat_id")
    if not chat_id:
        return None
    case = (st.session_state.get("gd_pin_store") or {}).get("gd_case")
    if st.session_state.get("gd_case_chat_id") != chat_id:
        case = None
    closed = bool(((case or {}).get("state") or {}).get("closed"))
    if only_if_closed_or_saved and not closed and not session.query(DiagnosticJob).filter_by(
            user_id=user_id, ask_chat_id=chat_id).first():
        return None
    cat = st.session_state.get("gd_category_memory") or ""
    snap = wo.snapshot(history=st.session_state.get("ask_chat") or [], case=case,
                       category="" if cat == "(any)" else cat, model_text=st.session_state.get("gd_model_memory") or "",
                       story=st.session_state.get("ask_story_out") or "", cited_log=st.session_state.get("ask_cited_log") or [],
                       wo_number=wo_number, chat_id=chat_id)
    try:
        return wo.save(session, DiagnosticJob, user_id, chat_id, snap)
    except Exception:
        session.rollback()
        return None


def _render_past_work_orders(user_id):
    """GD area: the tech's own past work orders (newest first), each with a Download button (HTML work order)."""
    import gd_work_orders as wo

    jobs = wo.list_jobs(session, DiagnosticJob, user_id)
    with st.expander(f"🗂️ Past work orders (kept {wo.WORK_ORDER_RETENTION_DAYS} days)", expanded=False):
        if not jobs:
            st.caption("No saved work orders yet. Save work order keeps this job here; a closed job is saved by itself.")
        for j in jobs:
            cols = st.columns([4, 1])
            cols[0].write(wo.list_label(j))
            cols[1].download_button("Download", data=wo.render_html(j).encode("utf-8"), file_name=wo.file_name(j),
                                    mime="text/html", key=f"wo_dl_{j.id}", use_container_width=True)


def load_ask_chat(chat_id: int):
    chat = session.query(AskChat).get(chat_id)
    if not chat:
        return None, []
    msgs = (
        session.query(AskMessage)
        .filter_by(chat_id=chat.id)
        .order_by(AskMessage.id)
        .all()
    )
    history = [{"role": m.role, "content": m.content or ""} for m in msgs]
    return chat, history


def persist_ask_turn(user_id: int, chat_id, category_name: str, model_text: str, user_msg: str, reply: str):
    """Create or update a saved Ask TechTrack chat and append this turn."""
    chat = session.query(AskChat).get(chat_id) if chat_id else None
    if not chat:
        title = (user_msg or "Guided Diagnostics").strip().replace("\n", " ")[:80]
        chat = AskChat(
            user_id=user_id,
            category_name=category_name or "",
            model_text=model_text or "",
            title=title or "Guided Diagnostics",
        )
        session.add(chat)
        session.commit()
    else:
        chat.updated_date = datetime.now()
        if category_name:
            chat.category_name = category_name
        if model_text:
            chat.model_text = model_text
    session.add(AskMessage(chat_id=chat.id, role="user", content=user_msg or ""))
    session.add(AskMessage(chat_id=chat.id, role="assistant", content=reply or ""))
    session.commit()
    return chat.id


# ---------------- AUTH HELPERS ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False


AUTH_COOKIE_NAME = "tt_auth"
AUTH_COOKIE_HOURS = 10


def _auth_serializer():
    secret = _secret("AUTH_COOKIE_SECRET")
    if not secret or not ITSDANGEROUS_AVAILABLE:
        return None
    return URLSafeTimedSerializer(str(secret), salt="techtrack-auth-v1")


def _issue_auth_token(user_row) -> str:
    ser = _auth_serializer()
    if not ser:
        return ""
    return ser.dumps({
        "id": int(user_row.id),
        "username": user_row.username,
        "role": user_row.role,
    })


def _load_auth_token(token: str):
    ser = _auth_serializer()
    if not ser or not token:
        return None
    try:
        data = ser.loads(token, max_age=AUTH_COOKIE_HOURS * 3600)
    except (BadSignature, BadTimeSignature, Exception):
        return None
    if not isinstance(data, dict) or "id" not in data or "username" not in data:
        return None
    row = session.query(User).filter_by(id=int(data["id"]), is_active=True).first()
    if not row or row.username != data.get("username"):
        return None
    return {
        "id": row.id,
        "username": row.username,
        "full_name": row.full_name,
        "role": row.role,
    }


def _cookie_manager():
    """Instantiate every run with a stable key so the browser component can hydrate."""
    if not COOKIE_MGR_AVAILABLE:
        return None
    try:
        return stx.CookieManager(key="tt_cookie_mgr")
    except Exception:
        return None


def _cookie_get(mgr, name: str) -> str:
    if not mgr:
        return ""
    try:
        # get_all() forces the browser component to send cookies on the next run
        bag = mgr.get_all() or {}
        val = bag.get(name) if isinstance(bag, dict) else None
        if val is None:
            val = mgr.get(name)
    except Exception:
        return ""
    return val if isinstance(val, str) else ""


def _cookie_set_auth(mgr, token: str):
    if not mgr or not token:
        return
    try:
        mgr.set(
            AUTH_COOKIE_NAME,
            token,
            expires_at=datetime.now() + timedelta(hours=AUTH_COOKIE_HOURS),
            same_site="lax",
            secure=True,
            key="tt_set_auth",
        )
    except Exception:
        pass


def _cookie_clear_auth(mgr):
    if not mgr:
        return
    try:
        mgr.delete(AUTH_COOKIE_NAME, key="tt_del_auth")
    except Exception:
        pass


class _InactivePanel(Exception):
    """Raised so a nav section that is not selected skips its body."""


class _Panel:
    """One app section. Unlike ``st.tabs``, inactive sections do not render.

    ``st.tabs`` keeps every panel in the DOM and does not store the selected
    tab. A long run (the AI spinner) left the previous pass on screen faded —
    My Dashboard under the active tab — and the Stop control stayed up until
    that run finished. A server ``st.rerun()`` also sent the browser back to
    the first tab and dropped the GD fields.
    """

    def __init__(self, name: str, selected: str):
        self.name = name
        self.active = name == selected

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return exc_type is _InactivePanel


def _enter_panel(panel) -> None:
    if panel is None or not getattr(panel, "active", False):
        raise _InactivePanel()


def _restore_widget(widget_key: str, memory_key: str, allowed=None) -> None:
    """Copy a remembered value onto a widget key when this run does not have one."""
    if widget_key in st.session_state:
        return
    saved = st.session_state.get(memory_key)
    if not isinstance(saved, str):
        return
    if allowed is not None and saved not in allowed:
        return
    st.session_state[widget_key] = saved


def _remember_widget(widget_key: str, memory_key: str) -> None:
    val = st.session_state.get(widget_key)
    if isinstance(val, str):
        st.session_state[memory_key] = val


def get_safety_progress(user_id: int) -> float:
    meetings = session.query(SafetyMeeting).count()
    if meetings == 0:
        return 100.0
    signed = (
        session.query(SafetyAcknowledgement)
        .filter_by(user_id=user_id)
        .count()
    )
    return round(100.0 * signed / meetings, 1)

# ---------------- AI CLIENT (xAI primary, Groq fallback — see gd_llm.py) ----------------
def _secret(name: str):
    """Read a Streamlit secret, then an env var."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def ai_available() -> bool:
    return gd_llm.ai_configured(_secret)


def _ai_chat_once(messages, temperature=0.2, max_tokens=1400, reasoning_effort=None) -> str:
    """One chat completion via gd_llm (xAI primary, Groq fallback). Retrieval is unchanged."""
    return gd_llm.complete_chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        secret_fn=_secret,
        reasoning_effort=reasoning_effort,
    )


def ai_chat(messages, temperature=0.2, max_tokens=1400, reasoning_effort=None) -> str:
    """Chat completion. On HTTP 413 / request-too-large, retry with a smaller payload."""
    def call(payload, temp, tokens):
        return _ai_chat_once(payload, temp, tokens, reasoning_effort=reasoning_effort)

    return complete_chat_with_payload_retry(
        call,
        messages,
        temperature,
        max_tokens,
    )


def _image_to_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    mime = (mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    b64 = base64.b64encode(image_bytes or b"").decode("ascii")
    return f"data:{mime};base64,{b64}"


def read_data_plate_from_image(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    """Read brand + model from a data-plate photo using the shop's existing AI key (no extra paid OCR service)."""
    if not image_bytes:
        return {"ok": False, "error": "No photo provided.", "brand": "", "model": "", "raw": ""}
    if not ai_available():
        return {
            "ok": False,
            "error": "AI is offline. Add the shop AI key in Streamlit secrets, or type the model by hand.",
            "brand": "",
            "model": "",
            "raw": "",
        }
    prompt = (
        "You are reading an RV appliance data plate / rating label photo for a shop tech. "
        "Extract the manufacturer BRAND and the MODEL number/string exactly as printed. "
        "Return ONLY compact JSON with keys brand, model, notes. "
        "model should be the full model token (example FCR10DCGTA). "
        "If unreadable, set brand and model to empty strings and explain in notes. "
        "No markdown fences."
    )
    data_url = _image_to_data_url(image_bytes, mime)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    # llama-4-scout stays off the Groq list (HTTP 404). grok-4.6 accepts the image.
    try:
        raw = gd_llm.complete_chat(
            messages,
            temperature=0.0,
            max_tokens=400,
            secret_fn=_secret,
            models={
                "xai": xai_vision_model_candidates(
                    preferred_vision=_secret("XAI_VISION_MODEL") or "",
                    preferred_chat=_secret("XAI_MODEL") or "",
                ),
                "groq": groq_vision_model_candidates(_secret("GROQ_VISION_MODEL") or ""),
            },
            empty_is_failure=True,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": str(e) or "Could not read the plate photo.",
            "brand": "",
            "model": "",
            "raw": "",
        }
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    brand = ""
    model_out = ""
    try:
        data = json.loads(cleaned)
        brand = str(data.get("brand") or "").strip()
        model_out = str(data.get("model") or "").strip()
    except Exception:
        # Fallback: pull a model-looking token
        m = re.search(r"model[\"'\s:]+([A-Za-z0-9][A-Za-z0-9\-]{3,})", cleaned, re.I)
        if m:
            model_out = m.group(1).strip()
        b = re.search(r"brand[\"'\s:]+([A-Za-z][A-Za-z0-9 \-]{1,40})", cleaned, re.I)
        if b:
            brand = b.group(1).strip().strip(',"\'')
    if not model_out and not brand:
        return {
            "ok": False,
            "error": "Could not read a model from that photo. Try a sharper shot of the plate, or type it.",
            "brand": "",
            "model": "",
            "raw": raw[:500],
        }
    return {"ok": True, "error": "", "brand": brand, "model": model_out, "raw": raw[:500]}


def apply_plate_read_to_model_key(model_key: str, image_file, button_key: str):
    """Shared UI: read plate photo into a Streamlit text_input key."""
    if image_file is None:
        return
    if not st.button("Read plate into Model", type="secondary", key=button_key):
        return
    raw = image_file.getvalue() if hasattr(image_file, "getvalue") else image_file
    mime = getattr(image_file, "type", None) or "image/jpeg"
    with st.spinner("Reading data plate…"):
        result = read_data_plate_from_image(raw, mime)
    if not result.get("ok"):
        st.warning(result.get("error") or "Could not read plate.")
        return
    brand = (result.get("brand") or "").strip()
    model = (result.get("model") or "").strip()
    filled = model
    if brand and model and brand.lower() not in model.lower():
        filled = f"{brand} {model}".strip()
    elif brand and not model:
        filled = brand
    # The Model text box is already on the page this run, so Streamlit refuses a direct write to its key
    # (StreamlitWidgetAlreadyInstantiatedError, memory test 2026-11-03). Park the value; the next run puts it in the
    # box before the box is drawn (apply_pending_plate_read).
    st.session_state[_plate_pending_key(model_key)] = filled
    st.rerun()


def _plate_pending_key(model_key: str) -> str:
    return f"_plate_read_pending_{model_key}"


def apply_pending_plate_read(model_key: str, memory_key: str | None = None) -> None:
    """Call BEFORE the Model text_input with key=model_key is created: copies a parked plate read into the box."""
    filled = st.session_state.pop(_plate_pending_key(model_key), None)
    if not isinstance(filled, str) or not filled:
        return
    st.session_state[model_key] = filled
    if memory_key:
        st.session_state[memory_key] = filled
    st.session_state[f"_plate_read_note_{model_key}"] = filled


def show_plate_read_note(model_key: str) -> None:
    filled = st.session_state.pop(f"_plate_read_note_{model_key}", None)
    if filled:
        st.success(f"Model set to: {filled}")


# ---------------- AI STORY ----------------
def _notes_say_incomplete(text: str) -> bool:
    """True only if the latest status language is still open.

    Midway Guided Diagnostics chats type "No repair yet" then later record the
    real fix. Matching ANY "no repair" in the transcript would lock every later
    Write-warranty-story click on the OPEN / no-repair template.
    """
    t = (text or "").lower()
    incomplete_markers = (
        "no fix yet", "not repaired", "not repaired yet", "unit not repaired",
        "not fixed", "no repair", "still open", "handoff", "hold this info",
        "not finished", "incomplete", "left off", "pick up", "will press button",
        "need warranty story",
    )
    complete_markers = (
        "job complete",
        "repair completed",
        "replaced the",
        "compressor started",
        "compressor ran",
        "returned to service",
    )
    last_incomplete = max(t.rfind(m) for m in incomplete_markers)
    last_complete = max(t.rfind(m) for m in complete_markers)
    if last_complete > last_incomplete:
        return False
    return last_incomplete >= 0


def improve_tech_story(concern: str, tech_notes: str, status_text=None) -> str:
    """Write a warranty narrative or an open-job handoff. Never invent tests or a completed repair."""
    concern = (concern or "").strip()
    tech_notes = (tech_notes or "").strip()
    # status_text should be TECH-reported lines only (not coach suggestions).
    incomplete = _notes_say_incomplete(
        status_text if status_text is not None else tech_notes
    )
    if not ai_available():
        if incomplete:
            return (
                f"**CONCERN**\n{concern or 'Customer reported an issue requiring diagnosis.'}\n\n"
                f"**TESTING PERFORMED**\n{tech_notes or 'See technician notes.'}\n\n"
                "**STATUS**\nOpen. No repair completed. Next tech: resume from testing performed."
            )
        return (
            f"**CONCERN**\n{concern or 'Customer reported an issue requiring diagnosis and repair.'}\n\n"
            f"**TESTING / FINDINGS**\n{tech_notes or 'See technician notes.'}\n\n"
            "**CAUSE**\nAs stated in the technician notes; not confirmed when none was recorded.\n\n"
            "**CORRECTION**\nThe repairs the technician recorded; none when none were recorded."
        )
    try:
        system_prompt = """You write shop documentation for RV warranty claims (Lippert, Dometic, Furrion, etc.) from the technician's notes. The write-up is built from what the technician recorded as done or measured, with each test, location and reading in the order it was done, each reading followed by a short interpretation grounded in that number. Coach-recommended tests become part of the record when the technician reports doing them. The tone is plain shop documentation.

An open job (no repair recorded) is written as:
CONCERN
(the customer symptom)

TESTING PERFORMED
(each recorded test and reading, in order)

STATUS
Open. No repair completed.
Next tech: [where the work left off].

A completed job (the technician recorded a repair) is written as:
CONCERN
(the customer symptom)

CAUSE
(the root cause the technician stated, or: Not confirmed.)
The testing narrative and the readings that support the cause.

CORRECTION
(the repair steps the technician performed)
"""

        status_line = (
            "JOB STATUS: OPEN / NOT REPAIRED (latest tech status). The write-up uses the open structure."
            if incomplete
            else "JOB STATUS: the completed structure applies when the notes say a repair was performed; otherwise the job is open."
        )
        user_prompt = f"""CUSTOMER CONCERN:
{concern or '(not provided)'}

TECHNICIAN NOTES (tech-reported facts only unless labeled otherwise):
{tech_notes or '(not provided)'}

{status_line}

Write the document now."""

        return ai_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=1600,
        )
    except Exception as e:
        return f"Error contacting AI: {e}\n\nConcern: {concern}\nNotes: {tech_notes}"


# ---------------- PDF INDEXING ----------------
def extract_pdf_pages(file_bytes: bytes):
    if not PYPDF_AVAILABLE:
        return []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                pages.append((i, text))
        return pages
    except Exception:
        return []


def chunk_page_text(page_num: int, text: str, chunk_size: int = 900, overlap: int = 120):
    """900-character windows with 120 overlap. Shared with bulk import."""
    return library_bulk_import.chunk_page_text(
        page_num, text, chunk_size=chunk_size, overlap=overlap
    )


def clear_document_chunks(document_id: int):
    session.query(DocChunk).filter_by(document_id=document_id).delete()
    session.commit()


def clear_document_assets(document_id: int):
    session.query(DocAsset).filter_by(document_id=document_id).delete()
    session.commit()


def _download_library_pdf(file_path: str):
    """PDF bytes for a library row. Cloud storage first, then a local path."""
    data = None
    try:
        data = r2_download_bytes(file_path)
    except Exception:
        data = None
    if data:
        return data
    local = Path(file_path or "")
    if local.is_file():
        return local.read_bytes()
    return None


def _bulk_index_figures(document_id, pdf_bytes, title, start_page=1, max_pages=None):
    """Render one page window for a bulk-import file. The caller resumes the cursor."""
    import library_figure_backfill as fb

    if not document_id or not pdf_bytes:
        return ""
    window = fb.PAGES_PER_STEP if max_pages is None else max_pages
    return fb.store_pdf_figures(
        session,
        int(document_id),
        pdf_bytes,
        title=title or "",
        upload_png=r2_put_bytes,
        start_page=int(start_page or 1),
        max_pages=window,
    )


def _store_pdf_assets(doc: Document, file_bytes: bytes):
    """Render page PNGs and figure crops into R2. The database keeps the key."""
    import library_figure_backfill as fb

    indexed = fb.store_pdf_figures(
        session,
        doc.id,
        file_bytes,
        title=doc.title or "",
        upload_png=r2_put_bytes,
    )
    session.commit()
    return indexed


def index_document_from_bytes(doc: Document, file_bytes: bytes):
    clear_document_chunks(doc.id)
    if (doc.file_type or "").lower() != "pdf":
        doc.indexed = False
        doc.index_note = "Only PDF files are indexed for guided diagnostics"
        session.commit()
        return False, doc.index_note
    if not PYPDF_AVAILABLE:
        doc.indexed = False
        doc.index_note = "pypdf not installed on server"
        session.commit()
        return False, doc.index_note
    asset_note = ""
    scanned = False
    try:
        indexed_assets = _store_pdf_assets(doc, file_bytes)
        scanned = bool(indexed_assets.get("scanned"))
        asset_note = (
            f"Page images only ({len(indexed_assets['pages'])} pages, scanned PDF, no extractable text)"
            if scanned
            else f"{len(indexed_assets['pages'])} page images, {len(indexed_assets['figures'])} figures"
        )
    except Exception:
        asset_note = ""
    pages = extract_pdf_pages(file_bytes)
    if not pages:
        doc.indexed = scanned or bool(asset_note)
        doc.index_note = (asset_note or "No extractable text (scanned PDF may need OCR)")[:250]
        session.commit()
        return bool(doc.indexed), doc.index_note
    count = 0
    for page_num, page_text in pages:
        for p, chunk in chunk_page_text(page_num, page_text):
            session.add(DocChunk(
                document_id=doc.id,
                category_id=doc.category_id,
                title=doc.title,
                page=p,
                chunk_text=chunk,
                keywords=doc.keywords or "",
            ))
            count += 1
    try:
        import library_figure_backfill as fb

        session.flush()
        fb.link_chunk_ids(session, doc.id)
    except Exception:
        pass
    doc.indexed = True
    note = f"Indexed {count} chunks from {len(pages)} pages"
    if asset_note:
        note = f"{note}; {asset_note}"
    doc.index_note = note[:250]
    session.commit()
    return True, doc.index_note


def index_document_from_r2(doc: Document):
    data = r2_download_bytes(doc.file_path)
    if not data:
        doc.indexed = False
        doc.index_note = "Could not download file from storage"
        session.commit()
        return False, doc.index_note
    return index_document_from_bytes(doc, data)

# ---------------- MANUAL SEARCH + INDEX EXPANSION ----------------
FAULT_CODE_TOKEN_RE = re.compile(r"^[a-z]\d{1,3}$")


PAGE_REF_RE = re.compile(r"page\s*0*(\d+)", re.I)

PROCEDURE_TOPIC_TERMS = [
    "ventilation", "leveling", "level", "ambient", "air leak", "thermistor",
    "cooling unit", "heating element", "heater", "igniter", "electrode",
    "high voltage", "solenoid", "orifice", "flue baffle", "flue tube", "burner",
    "upper circuit board", "lower circuit board", "control board", "fuse",
    "wiring", "dc volt", "ac volt", "lp gas", "propane", "manual gas",
    "door seal", "frame heater", "climate control", "diagnostic mode",
    "error code", "fault code", "sequence of operation", "ohms", "voltage",
    "sail switch", "sail", "limit switch", "high limit", "thermostat bypass",
    "blower", "airflow",
]


SHOP_BRANDS = tuple(_gdc.SHOP_BRAND_TOKENS)


def render_pdf_page_png(file_bytes: bytes, page_num: int, zoom: float = 1.6):
    """Return PNG bytes for a 1-based page number, or None."""
    if not PYMUPDF_AVAILABLE:
        return None
    doc = None
    pix = None
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        idx = max(0, min(page_num - 1, doc.page_count - 1))
        page = doc.load_page(idx)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    except Exception:
        return None
    finally:
        if pix is not None:
            try:
                pix.close()
            except Exception:
                pass
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        try:
            fitz.TOOLS.store_shrink(100)
        except Exception:
            pass


CITED_PAGE_RE = re.compile(
    r"(?:📖\s*)?Source:\s*(.+?)\s*[-–—―]+\s*page\s*(\d+)",
    re.I,
)

PAGE_OF_MANUAL_RE = re.compile(
    r"\bpage\s*(\d+)\s+of\s+(?:the\s+)?(.+?)(?=\s*\(|\s*$|\.|\n)",
    re.I,
)

EXPLICIT_PAGE_RE = re.compile(r"\bpage\s*(\d+)\b", re.I)

FIGURE_REQ_RE = re.compile(
    r"\b(?:fig(?:ure)?\.?|illustration)\s*([0-9]+[a-z]?)\b",
    re.I,
)


def parse_cited_pages_from_text(assistant_text: str) -> list:
    """Pull manual title + page from coach 📖 Source lines and 'page N of TITLE' phrases."""
    out = []
    seen = set()

    def _add(title, page):
        title = (title or "").strip().strip("*").strip().rstrip(".,;:")
        title = re.sub(r"\s*\([^)]*$", "", title).strip()
        try:
            page = int(page)
        except Exception:
            return
        if not title or not page:
            return
        key = (title.lower(), page)
        if key in seen:
            return
        seen.add(key)
        out.append({"title": title, "page": page})

    for m in CITED_PAGE_RE.finditer(assistant_text or ""):
        _add(m.group(1), m.group(2))
    for m in PAGE_OF_MANUAL_RE.finditer(assistant_text or ""):
        _add(m.group(2), m.group(1))
    return out


def _titles_compatible(cited_title: str, source_title: str) -> bool:
    """True when the source row belongs to the cited manual. Never treat empty cite as a free pass across books."""
    ct = (cited_title or "").strip().lower()
    stitle = (source_title or "").strip().lower()
    if not ct or not stitle:
        return False
    if ct == stitle or ct in stitle or stitle in ct:
        return True
    ct_toks = {t for t in re.findall(r"[a-z0-9]+", ct) if len(t) > 3}
    st_toks = {t for t in re.findall(r"[a-z0-9]+", stitle) if len(t) > 3}
    if not ct_toks or not st_toks:
        return False
    return len(ct_toks & st_toks) >= 2


def match_cited_to_sources(cited: list, sources: list, fallback: bool = False) -> list:
    """Map 📖 Source title/page cites onto the silent ledger. Title-locked. Never cross-book page matches."""
    if not sources or not cited:
        return []
    matched = []
    used = set()
    for c in cited:
        ct = (c.get("title") or "").strip()
        try:
            cp = int(c.get("page") or 0)
        except Exception:
            cp = 0
        pick = None
        if cp:
            for i, s in enumerate(sources):
                if i in used:
                    continue
                try:
                    sp = int(s.get("page") or 0)
                except Exception:
                    sp = 0
                if sp == cp and _titles_compatible(ct, s.get("title") or ""):
                    pick = i
                    break
        if pick is None and ct:
            same_doc = []
            for i, s in enumerate(sources):
                if i in used:
                    continue
                if _titles_compatible(ct, s.get("title") or ""):
                    try:
                        sp = int(s.get("page") or 0)
                    except Exception:
                        sp = 0
                    same_doc.append((i, sp, s))
            if same_doc and cp:
                same_doc.sort(key=lambda x: abs(x[1] - cp))
                pick = same_doc[0][0]
            elif same_doc:
                pick = same_doc[0][0]
        if pick is not None:
            used.add(pick)
            row = dict(sources[pick])
            if cp:
                row["page"] = cp
            matched.append(row)
    return matched


def _source_ledger_key(item: dict) -> tuple:
    title = (item.get("title") or "").strip().lower()
    try:
        page = int(item.get("page") or 0)
    except Exception:
        page = 0
    return (item.get("document_id"), page, title)


def merge_ask_source_ledger(items: list):
    """Quiet append-only ledger used by warranty citations. Never drives chat UI."""
    if not items:
        return
    ledger = list(st.session_state.get("ask_sources") or [])
    seen = {_source_ledger_key(s) for s in ledger}
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _source_ledger_key(item)
        if key in seen:
            continue
        seen.add(key)
        ledger.append(item)
        changed = True
    if changed:
        st.session_state["ask_sources"] = ledger
        try:
            st.session_state["ask_sources_json"] = json.dumps(ledger)
        except Exception:
            pass


def record_cited_pages(assistant_text: str):
    """Keep 📖 Source lines from coach turns for the warranty story."""
    cited = parse_cited_pages_from_text(assistant_text)
    if not cited:
        return cited
    log = list(st.session_state.get("ask_cited_log") or [])
    seen = {
        ((c.get("title") or "").strip().lower(), int(c.get("page") or 0))
        for c in log
    }
    for c in cited:
        key = ((c.get("title") or "").strip().lower(), int(c.get("page") or 0))
        if key in seen:
            continue
        seen.add(key)
        log.append({"title": c.get("title"), "page": c.get("page")})
    st.session_state["ask_cited_log"] = log
    ledger = list(st.session_state.get("ask_sources") or [])
    extras = []
    for c in cited:
        hit = match_cited_to_sources([c], ledger, fallback=False)
        if hit:
            extras.extend(hit)
        else:
            extras.append({
                "document_id": None,
                "title": c.get("title"),
                "page": c.get("page"),
                "file_path": None,
                "file_type": "pdf",
                "excerpt": "",
            })
    merge_ask_source_ledger(extras)
    return cited


def resolve_level_up_document_seed():
    """First catalog Level-Up / OCTP / TI PDF. Never a Unity board SM."""
    for hint in LEVEL_UP_ADVANTAGE_HINT_TITLES:
        seed = resolve_document_by_title(hint)
        if seed and not is_unity_board_manual(seed.get("title") or ""):
            return seed
    try:
        docs = session.query(Document).all()
    except Exception:
        return None
    best = None
    for d in docs:
        title = d.title or ""
        if not is_level_up_library_title(title) or not d.file_path:
            continue
        row = {
            "document_id": d.id,
            "title": title,
            "page": 1,
            "file_path": d.file_path,
            "file_type": d.file_type or "pdf",
            "excerpt": "",
            "indexed": bool(d.indexed),
        }
        t = title.lower()
        if "ti-005" in t or "electronic leveling" in t:
            return row
        if best is None:
            best = row
    return best


def resolve_ac_document_seed():
    """First catalog rooftop AC / FACT / Brisk / ADB PDF. Never a Unity board SM."""
    for hint in AC_HINT_TITLES:
        seed = resolve_document_by_title(hint)
        if seed and not is_unity_board_manual(seed.get("title") or "") and is_ac_library_title(
            seed.get("title") or ""
        ):
            return seed
    try:
        docs = session.query(Document).all()
    except Exception:
        return None
    best = None
    for d in docs:
        title = d.title or ""
        if not is_ac_library_title(title) or not d.file_path:
            continue
        row = {
            "document_id": d.id,
            "title": title,
            "page": 1,
            "file_path": d.file_path,
            "file_type": d.file_type or "pdf",
            "excerpt": "",
            "indexed": bool(d.indexed),
        }
        t = title.lower()
        if "fact" in t or "b57915" in t or "brisk" in t:
            return row
        if best is None:
            best = row
    return best


def resolve_water_heater_document_seed():
    """First catalog Girard GSWH-2 / Water Heaters PDF. Never a Unity board SM."""
    for hint in WATER_HEATER_HINT_TITLES:
        seed = resolve_document_by_title(hint)
        if seed and not is_unity_board_manual(seed.get("title") or "") and is_water_heater_library_title(
            seed.get("title") or ""
        ):
            return seed
    try:
        docs = session.query(Document).all()
    except Exception:
        return None
    best = None
    for d in docs:
        title = d.title or ""
        if not is_water_heater_library_title(title) or not d.file_path:
            continue
        row = {
            "document_id": d.id,
            "title": title,
            "page": 1,
            "file_path": d.file_path,
            "file_type": d.file_type or "pdf",
            "excerpt": "",
            "indexed": bool(d.indexed),
        }
        t = title.lower()
        if "gswh" in t or "ccd-0009390" in t or "girard" in t:
            return row
        if best is None:
            best = row
    return best


def parse_figure_requests(user_msg: str) -> list:
    """Pull Fig./Figure N requests from the tech message."""
    out = []
    seen = set()
    for m in FIGURE_REQ_RE.finditer(user_msg or ""):
        tok = m.group(1).upper()
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def parse_library_page_targets(user_msg: str, coach_text: str = "", prior_cited: list = None) -> dict:
    """
    Parse illustration/page targets from tech msg + coach reply + prior Source lines.
    Returns figures, explicit/cited pages, and the title-locked manual name.
    """
    coach_text = coach_text or ""
    user_msg = user_msg or ""
    prior_cited = list(prior_cited or [])

    cited = parse_cited_pages_from_text(coach_text)
    if not cited:
        cited = list(prior_cited)

    figures = parse_figure_requests(user_msg)

    # Explicit "page N" in the tech message (title filled later from locked manual)
    explicit_pages = []
    for m in EXPLICIT_PAGE_RE.finditer(user_msg):
        # Skip "page N of TITLE" — those already carry a title via parse_cited_pages_from_text
        span_end = m.end()
        tail = user_msg[span_end:span_end + 12].lower()
        if tail.lstrip().startswith("of "):
            continue
        try:
            explicit_pages.append(int(m.group(1)))
        except Exception:
            pass

    # Also accept page-of-title phrases from the tech message
    for c in parse_cited_pages_from_text(user_msg):
        if c not in cited:
            cited.append(c)

    manual_title = ""
    if cited:
        manual_title = (cited[-1].get("title") or "").strip()
    elif prior_cited:
        manual_title = (prior_cited[-1].get("title") or "").strip()

    return {
        "figures": figures[:3],
        "cited": cited,
        "explicit_pages": explicit_pages[:3],
        "manual_title": manual_title,
    }


def resolve_document_by_title(title: str):
    """
    Resolve a Document row by title compatibility.
    Returns a page-ref seed with document_id + file_path, or None.
    Never cross-book: caller must pass the cited manual title.
    """
    title = (title or "").strip()
    if not title:
        return None
    try:
        docs = session.query(Document).all()
    except Exception:
        return None
    best = None
    best_score = 0
    for d in docs:
        dt = d.title or ""
        if not _titles_compatible(title, dt):
            continue
        ct_toks = {t for t in re.findall(r"[a-z0-9]+", title.lower()) if len(t) > 3}
        st_toks = {t for t in re.findall(r"[a-z0-9]+", dt.lower()) if len(t) > 3}
        score = len(ct_toks & st_toks)
        if title.lower() in dt.lower() or dt.lower() in title.lower():
            score += 5
        if score > best_score and d.file_path:
            best_score = score
            best = {
                "document_id": d.id,
                "title": d.title,
                "page": 1,
                "file_path": d.file_path,
                "file_type": d.file_type or "pdf",
                "excerpt": "",
            }
    return best


def find_figure_page_in_document(document_id, figure_token: str) -> int:
    """Locate Fig. N inside ONE document's indexed DocChunks. Returns page or 0."""
    if not document_id or not figure_token:
        return 0
    fig = figure_token.lower().lstrip("0") or figure_token.lower()
    patterns = [
        re.compile(rf"\bfig(?:ure)?\.?\s*0*{re.escape(fig)}\b", re.I),
        re.compile(rf"\bfig(?:ure)?\s*0*{re.escape(fig)}\b", re.I),
    ]
    try:
        chunks = (
            session.query(DocChunk)
            .filter_by(document_id=int(document_id))
            .order_by(DocChunk.page)
            .all()
        )
    except Exception:
        return 0
    for ch in chunks:
        blob = ch.chunk_text or ""
        for pat in patterns:
            if pat.search(blob):
                try:
                    return int(ch.page or 0)
                except Exception:
                    return 0
    return 0


def _page_ref(seed: dict, page: int, title_fallback: str = "") -> dict:
    """Build a renderable page dict. Document title + page + file_path is enough."""
    return {
        "document_id": seed.get("document_id"),
        "title": seed.get("title") or title_fallback or "Manual",
        "page": int(page),
        "file_path": seed.get("file_path"),
        "file_type": seed.get("file_type") or "pdf",
        "excerpt": seed.get("excerpt") or "",
    }


def resolve_requested_library_pages(user_msg: str, assistant_text: str = "") -> list:
    """
    Clean page pipeline (display path):
      detect (caller) → parse targets → resolve Document (title-locked) → resolve page → list of page refs.
    Silent ask_sources ledger is NOT required for display; Document.title + page + file_path is enough.
    Never cross-book.
    """
    prior = list(st.session_state.get("ask_cited_log") or [])
    targets = parse_library_page_targets(user_msg or "", assistant_text or "", prior_cited=prior)
    manual_title = (targets.get("manual_title") or "").strip()
    cited = list(targets.get("cited") or [])
    figures = list(targets.get("figures") or [])
    explicit_pages = list(targets.get("explicit_pages") or [])

    level_up_ask = is_level_up_advantage_context("", "", f"{user_msg} {assistant_text} {manual_title}")
    ac_ask = is_air_conditioning_context("", "", f"{user_msg} {assistant_text} {manual_title}")
    wh_ask = is_water_heater_context("", "", f"{user_msg} {assistant_text} {manual_title}")
    if level_up_ask and (not manual_title or is_unity_board_manual(manual_title)):
        seed_lu = resolve_level_up_document_seed()
        if seed_lu and seed_lu.get("file_path"):
            manual_title = seed_lu.get("title") or manual_title
    elif ac_ask and (not manual_title or is_unity_board_manual(manual_title)):
        seed_ac = resolve_ac_document_seed()
        if seed_ac and seed_ac.get("file_path"):
            manual_title = seed_ac.get("title") or manual_title
    elif wh_ask and (not manual_title or is_unity_board_manual(manual_title)):
        seed_wh = resolve_water_heater_document_seed()
        if seed_wh and seed_wh.get("file_path"):
            manual_title = seed_wh.get("title") or manual_title

    if not manual_title:
        # No cited shop manual — refuse to guess across books
        return []

    seed = resolve_document_by_title(manual_title)
    if (not seed or not seed.get("file_path")) and level_up_ask:
        seed = resolve_level_up_document_seed()
        if seed:
            manual_title = seed.get("title") or manual_title
    if (not seed or not seed.get("file_path")) and ac_ask:
        seed = resolve_ac_document_seed()
        if seed:
            manual_title = seed.get("title") or manual_title
    if (not seed or not seed.get("file_path")) and wh_ask:
        seed = resolve_water_heater_document_seed()
        if seed:
            manual_title = seed.get("title") or manual_title
    if not seed or not seed.get("file_path"):
        return []

    out = []
    seen_pages = set()

    def _add_page(page_num: int):
        try:
            page_num = int(page_num)
        except Exception:
            return
        if not page_num or page_num in seen_pages:
            return
        seen_pages.add(page_num)
        out.append(_page_ref(seed, page_num, manual_title))

    # 1) Fig./Figure N → search ONLY this document's DocChunks
    for fig in figures:
        page = find_figure_page_in_document(seed.get("document_id"), fig)
        if not page:
            # Fall back to last cited Source page from this same title
            for c in reversed(cited):
                if _titles_compatible(manual_title, c.get("title") or ""):
                    try:
                        page = int(c.get("page") or 0)
                    except Exception:
                        page = 0
                    break
        if page:
            _add_page(page)

    # 2) Explicit "page N" in the tech message (title-locked to cited manual)
    for p in explicit_pages:
        _add_page(p)

    ledger = list(st.session_state.get("ask_sources") or [])
    same_book = [
        s for s in ledger
        if _titles_compatible(manual_title, s.get("title") or "")
    ]

    # 3) Board / terminal / PCB figure ask — pick real diagram pages, not Quick Notes
    if not out and wants_board_or_terminal_figure(user_msg):
        picked = pick_diagram_page_numbers(same_book, user_msg, manual_title)
        for p in picked:
            _add_page(p)
        if not out and is_furrion_ccd_0008122(manual_title):
            for p in FURRION_FCR_BOARD_FIGURE_PAGES:
                _add_page(p)
                if len(out) >= 2:
                    break
        if not out and level_up_ask and is_level_up_library_title(manual_title):
            try:
                lu_chunks = (
                    session.query(DocChunk)
                    .filter(DocChunk.document_id == int(seed.get("document_id") or 0))
                    .all()
                    if seed.get("document_id") else []
                )
            except Exception:
                lu_chunks = []
            for p in pick_diagram_page_numbers(lu_chunks, user_msg, manual_title):
                _add_page(p)
        if not out and ac_ask and is_ac_library_title(manual_title):
            try:
                ac_chunks = (
                    session.query(DocChunk)
                    .filter(DocChunk.document_id == int(seed.get("document_id") or 0))
                    .all()
                    if seed.get("document_id") else []
                )
            except Exception:
                ac_chunks = []
            for p in pick_diagram_page_numbers(ac_chunks, user_msg, manual_title):
                _add_page(p)

    # 4) Cited Source pages — skip text-only notes on a figure ask
    if not out:
        for c in cited:
            if not _titles_compatible(manual_title, c.get("title") or manual_title):
                continue
            try:
                p = int(c.get("page") or 0)
            except Exception:
                p = 0
            if not p:
                continue
            excerpt = ""
            for s in same_book:
                try:
                    if int(s.get("page") or 0) == p:
                        excerpt = s.get("excerpt") or ""
                        break
                except Exception:
                    continue
            if (
                wants_library_page_shown(user_msg)
                and excerpt
                and page_is_text_only_notes(excerpt)
                and not page_has_figure_or_terminal_layout(excerpt)
            ):
                continue
            _add_page(p)

    return out[:3]


def _figures_for_session(offers) -> list:
    """Figure metadata for the next rerun. PNG bytes stay in R2, not in session_state."""
    kept = []
    for item in offers or []:
        if not isinstance(item, dict):
            continue
        kept.append({key: value for key, value in item.items() if key != "png"})
    return kept


def _render_gd_figures_under_step(figures, key_prefix: str) -> None:
    """Full-width figures directly under this step. A missing file stays blank."""
    import library_figure_backfill as fb

    for index, src in enumerate(figures or []):
        if not isinstance(src, dict):
            continue
        shown = dict(src)
        try:
            shown["caption"] = shown.get("gd_caption") or fb.gd_figure_caption(shown)
        except Exception:
            shown["caption"] = shown.get("caption") or ""
        try:
            render_library_page_image(shown, f"{key_prefix}_{index}")
        except Exception:
            continue


def render_on_demand_library_pages(pages: list):
    """Show only the requested shop-library page(s). No source-menu forest."""
    st.markdown("#### Shop library page")
    st.caption("From the shop Document Library - not uploaded by the technician.")
    if not pages:
        st.info("No matching shop-library page was found for that request.")
        ledger = list(st.session_state.get("ask_sources") or [])
        best = next((s for s in reversed(ledger) if s.get("file_path")), None)
        if best and best.get("file_path"):
            data = r2_download_bytes(best["file_path"])
            if data:
                st.download_button(
                    "⬇️ Download best matching library PDF",
                    data=data,
                    file_name=f"{(best.get('title') or 'manual')[:40]}.pdf",
                    key="ask_ondemand_best_dl",
                )
        return
    shown_pdf = set()
    for i, src in enumerate(pages[:3]):
        rendered = render_library_page_image(src, f"ondemand_{i}")
        excerpt = (src.get("excerpt") or "").strip()
        if excerpt:
            with st.expander("Text from this page", expanded=False):
                st.text(excerpt[:1800])
        fpath = src.get("file_path")
        if fpath and fpath not in shown_pdf and rendered:
            shown_pdf.add(fpath)
            local = Path(str(fpath))
            data = None
            if local.is_file():
                try:
                    data = local.read_bytes()
                except Exception:
                    data = None
            else:
                data = r2_download_bytes(fpath)
            if data:
                st.download_button(
                    "⬇️ Download this PDF",
                    data=data,
                    file_name=f"{(src.get('title') or 'manual')[:40]}.pdf",
                    key=f"ask_ondemand_dl_{i}",
                )


def clear_ask_source_state():
    st.session_state["ask_sources"] = []
    st.session_state.pop("ask_sources_json", None)
    st.session_state.pop("ask_auto_show", None)
    st.session_state.pop("ask_auto_show_failed", None)
    st.session_state.pop("ask_auto_show_fail_note", None)
    st.session_state.pop("ask_cited_log", None)
    st.session_state.pop("ask_flow", None)


def reset_guided_diagnostics_session():
    """Drop the open GD case before the next message is read.

    History is the slot store (lead-jack, FACR, and the rest). Clearing it
    clears those answered slots. Model, category, and the Unity gate go back
    to empty so the next case cannot inherit the previous one.
    """
    st.session_state["ask_chat"] = []
    st.session_state["ask_chat_id"] = None
    clear_ask_source_state()
    st.session_state.pop("ask_story_out", None)
    st.session_state.pop("ask_story_area", None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("ask_story_area_"):
            st.session_state.pop(key, None)
    st.session_state["ask_story_n"] = int(st.session_state.get("ask_story_n") or 0) + 1
    st.session_state["ask_input"] = ""
    st.session_state.pop("ask_pending_answer", None)
    st.session_state.pop("ask_force_send", None)
    st.session_state["ask_model"] = ""
    st.session_state["gd_model_memory"] = ""
    st.session_state["ask_cat"] = "(any)"
    st.session_state["gd_category_memory"] = "(any)"
    st.session_state.pop("ask_plate_cam", None)
    st.session_state.pop("ask_plate_upload", None)
    st.session_state.pop("ask_plate_read_btn", None)
    st.session_state["ask_wo_number"] = ""
    st.session_state.pop("gd_case_chat_id", None)


def render_library_page_image(src: dict, key_suffix: str):
    """Stored crop or R2 page → st.image. No markdown image embeds."""
    import manual_figures as mf

    title = src.get("title") or "Manual"
    try:
        page = int(src.get("page") or 1)
    except Exception:
        page = 1
    label = src.get("label") or ""
    caption = src.get("gd_caption") or src.get("caption") or mf.display_caption(title, page, label or "page")
    def _usable(blob) -> bool:
        if not blob:
            return False
        try:
            return not mf.png_is_blank(blob)
        except Exception:
            return False

    png = src.get("png")
    if not _usable(png) and src.get("image_path"):
        import library_figure_backfill as fb

        png = fb.fetch_png(src.get("image_path") or "", download=r2_download_bytes)
    if not _usable(png):
        # R2 missed the crop. A bundled kit sheet or a real local file can still draw.
        # A miss stays blank. The tech does not see a failed-download caption.
        png = mf.png_for_library_offer(src)
    if _usable(png):
        st.image(png, caption=caption, use_container_width=True)
        return True
    fpath = src.get("file_path")
    local = Path(str(fpath or ""))
    data = None
    if fpath and local.is_file():
        try:
            data = local.read_bytes()
        except Exception:
            data = None
    elif fpath:
        data = r2_download_bytes(fpath)
    if data:
        png = render_pdf_page_png(data, page)
        if png and not mf.png_is_blank(png):
            st.image(png, caption=caption, use_container_width=True)
            return True
    return False


FURNACE_OEM_ORDER = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23


FRIDGE_OEM_ORDER = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23


DIAG_LED_HONESTY = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23


UNITY_OEM_ORDER = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23


# ---------------- GUIDED FLOW ENGINE (v4.10.0, soft-disabled in GD chat v4.13.0) ----------------
# Tree data is leftover citation material only. GD chat is the open library coach.
# Do not encode this Furrion tree as GD UX (wrong fan-replacement leaf vs SM diamond).

FURRION_FCR_SM_TITLE = "Furrion FCR08/FCR10 SM CCD-0008122"

# First hard tree: Furrion FCR08/FCR10 / FCR10DCGTA / CCD-0008122
# Encoded from shop SM: Sec1 Fuse p.19 → Gen TS dial/battery p.12 → Sec3 paper p.33 →
# operating? diamond → Fan Replacement OR Not Cooling p.34.
# Fan F+/F- supply volts live on Fan Fault flash-code path (p.27) ONLY — never after paper test.
PROCEDURE_FURRION_FCR_CCD_0008122 = {
    "id": "furrion_fcr_ccd_0008122",
    "title": FURRION_FCR_SM_TITLE,
    "models": ("fcr08", "fcr10", "fcr10dcgta", "fcr08dcgta", "ccd-0008122", "ccd0008122"),
    "categories": ("refrigerat", "fridge"),
    "nodes": {
        "fuse_front_vent": {
            "id": "fuse_front_vent",
            "type": "multi",
            "prompt": (
                "DISCONNECT POWER. Pull the front vent cover off the bottom of the refrigerator. "
                "Locate the fuse in the top left section of the front vent cavity (Fig. 7A) — "
                "15A ATC blade / cartridge. Visually check the fuse, confirm with continuity, "
                "check fitment in the holder, replace if blown, then reapply power.\n\n"
                "Report fuse result: blown / replaced / good."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {
                "blown": "cavity_light_after_fuse",
                "replaced": "cavity_light_after_fuse",
                "good": "cavity_light_check",
            },
        },
        "cavity_light_check": {
            "id": "cavity_light_check",
            "type": "binary",
            "prompt": (
                "Open the door. Does the refrigerator cavity light come on?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {
                "yes": "dial_on_4_5",
                "no": "fuse_front_vent",
            },
        },
        "cavity_light_after_fuse": {
            "id": "cavity_light_after_fuse",
            "type": "multi",
            "prompt": (
                "After the fuse check/replace and power reapplied: does the refrigerator cavity "
                "light come on when opening the door? Also say if it is cooling or not cooling."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {
                "light_on_cooling": "resolved_power",
                "light_on_not_cooling": "dial_on_4_5",
                "yes": "dial_on_4_5",
                "light_on": "dial_on_4_5",
                "no": "power_continuity_voltage",
                "no_light": "power_continuity_voltage",
            },
        },
        "resolved_power": {
            "id": "resolved_power",
            "type": "end",
            "prompt": (
                "Power issue resolved. Confirm the refrigerator performs. "
                "No further action is required on the No-Power path."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {},
        },
        "power_continuity_voltage": {
            "id": "power_continuity_voltage",
            "type": "binary",
            "prompt": (
                "Slide the unit out to access power connections. Measure and record voltage at the "
                "appliance connection (Fig. 8 / Fig. 9). Is the voltage between 12V–15V?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 20,
            "edges": {
                "yes": "dial_on_4_5",
                "no": "external_power_issue",
            },
        },
        "external_power_issue": {
            "id": "external_power_issue",
            "type": "end",
            "prompt": (
                "Insufficient RV supply voltage. Correct power supply: connect shore power, check "
                "converter, check wiring and switches, charge batteries. Document as "
                "\"external power issue.\" Contact RV manufacturer for additional troubleshooting."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 20,
            "edges": {},
        },
        "dial_on_4_5": {
            "id": "dial_on_4_5",
            "type": "binary",
            "prompt": (
                "Open the door and locate the temperature dial. Confirm the dial is ON — not OFF — "
                "set to position 4 or 5 (Fig. 17 / Fig. 32).\n\n"
                "Is the dial ON at 4 or 5?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 23,
            "edges": {
                "yes": "battery_under_load",
                "no": "set_dial_then_battery",
                "off": "set_dial_then_battery",
            },
        },
        "set_dial_then_battery": {
            "id": "set_dial_then_battery",
            "type": "gate",
            "prompt": (
                "Turn the refrigerator ON to dial position 4 or 5. Then check battery voltage under "
                "load (General Troubleshooting: ≥10.5V under load).\n\n"
                "Report when dial is set to 4–5 and the under-load voltage reading."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 12,
            "edges": {
                "pass": "paper_test",
                "yes": "paper_test",
                "ok": "paper_test",
                "set": "paper_test",
                "fail": "external_power_issue",
                "low": "external_power_issue",
                "no": "external_power_issue",
            },
        },
        "battery_under_load": {
            "id": "battery_under_load",
            "type": "binary",
            "prompt": (
                "Per General Troubleshooting: check battery voltage for 10.5V under load "
                "(operating range). Is battery voltage ≥10.5V under load?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 12,
            "edges": {
                "yes": "paper_test",
                "pass": "paper_test",
                "no": "external_power_issue",
                "fail": "external_power_issue",
            },
        },
        "paper_test": {
            "id": "paper_test",
            "type": "binary",
            "prompt": (
                "Insufficient Temperature — paper test for cooling-fan airflow (air in/out):\n"
                "1. Open the door.\n"
                "2. Droop a piece of paper over the edge of the cavity so it hangs over the front of the vent.\n"
                "3. Facing the unit, left side of the vent cover should SUCK the paper in (Fig. 33).\n"
                "4. Facing the unit, right side of the vent cover should BLOW the paper out (Fig. 34).\n\n"
                "Does the paper move correctly (left suck / right blow)?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 33,
            "edges": {
                "yes": "not_cooling_current",
                "pass": "not_cooling_current",
                "no": "is_operating_diamond",
                "fail": "is_operating_diamond",
            },
        },
        "is_operating_diamond": {
            "id": "is_operating_diamond",
            "type": "binary",
            "prompt": (
                "Is the refrigerator operating? (Compressor working/running — it may not be cold yet. "
                "Amperage should be greater than 1 amp to indicate it is working.)"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 33,
            "edges": {
                "no": "fan_replacement",
                "yes": "not_cooling_current",
            },
        },
        "fan_replacement": {
            "id": "fan_replacement",
            "type": "end",
            "prompt": (
                "Potential air blockage or bad fan. Proceed to Fan Replacement in Repair Section 2 "
                "for further information. Do not meter fan supply voltage on this path; "
                "that check belongs only on the Fan Fault / flash-code diagnostics, not after the paper test."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 33,
            "edges": {},
        },
        "not_cooling_current": {
            "id": "not_cooling_current",
            "type": "binary",
            "prompt": (
                "Not Cooling Diagnostics: Pull the unit out to measure current. Run the refrigerator "
                "for at least 1 hour before proceeding. Use a DC clamp meter to measure and record "
                "current.\n\n"
                "Is current <3 amps?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "oily_substance_check",
                "no": "dial_max_one_hour",
            },
        },
        "oily_substance_check": {
            "id": "oily_substance_check",
            "type": "binary",
            "prompt": (
                "Shut off the refrigerator and let sit for 1 hour. Remove the back cover and touch "
                "the inlet and outlet tubes with fingers to check for oily substance.\n\n"
                "Is there an oily substance present?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "replace_unit_coolant",
                "no": "replace_unit_return",
            },
        },
        "dial_max_one_hour": {
            "id": "dial_max_one_hour",
            "type": "binary",
            "prompt": (
                "Turn dial up to max setting and run for 1 hour.\n\n"
                "Is the refrigerator operating correctly?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "replace_thermostat",
                "no": "compressor_running_constant",
            },
        },
        "compressor_running_constant": {
            "id": "compressor_running_constant",
            "type": "binary",
            "prompt": "Is the compressor running constantly?",
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "replace_unit_coolant",
                "no": "replace_thermostat",
            },
        },
        "replace_thermostat": {
            "id": "replace_thermostat",
            "type": "end",
            "prompt": (
                "Replace the thermostat to recalibrate the unit. Proceed to Thermostat Replacement "
                "in Repair Section 2. If issues persist, replace unit."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {},
        },
        "replace_unit_coolant": {
            "id": "replace_unit_coolant",
            "type": "end",
            "prompt": (
                "Likely a coolant leak. Replace unit and determine if unit needs to be returned."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {},
        },
        "replace_unit_return": {
            "id": "replace_unit_return",
            "type": "end",
            "prompt": (
                "Replace unit and determine if unit needs to be returned."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {},
        },
        # Flash-code Fan Fault path ONLY (p.27) — F+/F− volts live here, not after paper test.
        "fan_fault_f_terminal_volts": {
            "id": "fan_fault_f_terminal_volts",
            "type": "binary",
            "prompt": (
                "Error Code — Fan Fault Diagnostics: Connect power, locate the inverter PCB. "
                "Measure and record voltage at the F+ and F− terminals on the inverter PCB.\n\n"
                "Is the nominal voltage 12V?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {
                "yes": "fan_fault_connections",
                "no": "replace_inverter_pcb",
            },
        },
        "fan_fault_connections": {
            "id": "fan_fault_connections",
            "type": "binary",
            "prompt": (
                "Check connections: fan into inverter PCB F+/F− terminals, and fan quick connection "
                "to harness. Reset power.\n\n"
                "Did the error code go away after resetting power?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {
                "yes": "resolved_power",
                "no": "replace_inverter_and_fan",
            },
        },
        "replace_inverter_pcb": {
            "id": "replace_inverter_pcb",
            "type": "end",
            "prompt": (
                "Replace the inverter PCB. Proceed to Compressor Inverter PCB Replacement in "
                "Repair Section 2."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {},
        },
        "replace_inverter_and_fan": {
            "id": "replace_inverter_and_fan",
            "type": "end",
            "prompt": (
                "Replace the inverter PCB and fan. Proceed to Compressor Inverter PCB Replacement "
                "and Fan Replacement in Repair Section 2."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {},
        },
    },
}

PROCEDURE_TREES = {
    PROCEDURE_FURRION_FCR_CCD_0008122["id"]: PROCEDURE_FURRION_FCR_CCD_0008122,
}


def get_procedure_node(procedure: dict, node_id: str):
    if not procedure:
        return None
    return (procedure.get("nodes") or {}).get(node_id)


# Ordered alias lists: first matching key wins for ambiguous text.
_ANSWER_ALIAS_GROUPS = [
    ("light_on_not_cooling", [
        "light on not cooling", "light on, not cooling", "has power not cooling",
        "power on not cooling", "light works not cooling", "light on but not cool",
        "cavity light on not cooling", "powered but not cooling",
    ]),
    ("light_on_cooling", [
        "light on cooling", "light on and cooling", "power restored cooling",
        "working now", "cools now", "issue resolved",
    ]),
    ("replaced", ["fuse replaced", "replaced fuse", "replaced the fuse", "new fuse installed", "swapped fuse"]),
    ("blown", ["fuse blown", "blown fuse", "fuse is blown", "was blown"]),
    ("good", ["fuse good", "fuse ok", "fuse fine", "fuse intact", "continuity good", "not blown"]),
    ("pass", ["pass", "passed", "paper moves", "sucks and blows", "left suck", "right blow", "airflow good"]),
    ("fail", [
        "fail", "failed", "no paper", "paper no", "no movement", "no paper movement",
        "doesn't move", "does not move", "no suck", "no blow", "paper fails",
    ]),
    ("off", ["dial off", "set to off", "was off", "in off"]),
    ("yes", [
        "yes", "y", "yeah", "yep", "affirmative", "correct", "confirmed",
        "light on", "it is on", "dial is on", "on 4", "on 5", "position 4", "position 5",
        "operating", "compressor running", "running", "amps >1", "greater than 1",
        "12v", "12 v", "between 12", "ok", "good", "voltage good", ">=10.5", "10.5", "11v", "13v", "14v",
    ]),
    ("no", [
        "no", "n", "nope", "negative", "not operating", "not running", "dead compressor",
        "no light", "still dark", "below 10.5", "low voltage", "9v", "under 11",
        "current <3", "less than 3", "<3",
    ]),
]


def binary_button_labels(node: dict):
    """Optional Pass/Fail or Yes/No labels when node is binary."""
    if not node or (node.get("type") or "") != "binary":
        return None
    edges = node.get("edges") or {}
    if "pass" in edges and "fail" in edges:
        return ("Pass", "pass", "Fail", "fail")
    if "yes" in edges and "no" in edges:
        return ("Yes", "yes", "No", "no")
    return None


def _stored_figure_matches(reply: str, user_msg: str, category_name: str, model_text: str):
    """Figure crops for this job from the library. Any brand.

    PNG bytes load only for the rows that matched. A bundled Thetford kit
    sheet is the last resort, and its caption says so.
    """
    import library_figure_backfill as fb

    try:
        rows = fb.meta_rows(session)
    except Exception:
        rows = []
    offers = fb.offers_for_turn(rows, reply, user_msg, category_name, model_text)
    if not offers:
        return []
    if not offers[0].get("bundled"):
        try:
            fb.attach_pngs(session, offers, read_local=True, download=r2_download_bytes)
        except Exception:
            pass
    return [item for item in offers if item.get("png")]


# ---------------- GD OFFICIAL METHOD (Chase approved 2026-10-16) ----------------
GD_OFFICIAL_METHOD = True
GD_USAGE_LOG = os.environ.get("GD_USAGE_LOG", "")
REDUCED_MODE_LINE = "Reduced mode (fallback model, short manual excerpts only):"
# Test hooks: replay tests set these to stay offline. None = live xAI call with the library tools + built-in web search.
# _gd_official_chat(messages, max_tokens, effort) -> str is a text-only fake; _gd_official_respond(items, tools, tool_choice)
# -> gd_llm.respond()-shaped dict is a fake that can make tool calls.
_gd_official_chat = None
_gd_official_respond = None
# Grok searches the internet itself with xAI's built-in web_search inside its own call (Chase 2026-10-24); the app-side
# gd_official search is retired from the GD path. open_web_document still fetches a URL Grok found (plain HTTP, free).


_gd_finder = None  # test hook: a gd_pages finder (e.g. StubPageFinder). None = the fresh library's page-finder.
GD_UNAVAILABLE_LINE = "Guided Diagnostics could not reach the AI right now. Nothing was guessed. Send the same message again in a minute."
GD_OFFLINE_LINE = "The AI is offline, so Guided Diagnostics cannot answer. Nothing was guessed."


def _gd_page_finder():
    """The ONE page-finder (GD and library search). Its index ships in pagefinder/index; the app DB is
    the source of truth for document metadata and for documents added after the index build."""
    global _gd_finder
    if _gd_finder is None:
        import gd_pages

        flag = str(_secret("TT_PAGEFINDER_MEANING") or "on").strip().lower()
        _gd_finder = gd_pages.LibraryPageFinder(app_db=os.path.abspath(DB_PATH),
                                                meaning=flag not in ("0", "off", "false", "no"))
    return _gd_finder


def _gd_official_reply(user_msg, category_name, model_text, history, pin_store=None):
    """One GD turn on the fresh core (gd_turn). The brain decides; this wrapper only wires the app to it."""
    import gd_turn

    if pin_store is None:
        try:
            pin_store = st.session_state.setdefault("gd_pin_store", {})
        except Exception:
            pin_store = {}

    def respond_fn(items, tools, tool_choice=None):
        if _gd_official_respond is not None:
            return _gd_official_respond(items, tools, tool_choice)
        if _gd_official_chat is not None:
            return _gd_official_chat(items, None, None)
        return gd_llm.respond(items, tools, tool_choice=tool_choice, secret_fn=_secret)

    try:
        result = gd_turn.run_turn(
            user_msg, category_name, model_text, history,
            finder=_gd_page_finder(), respond_fn=respond_fn, store=pin_store,
            log_path=GD_USAGE_LOG or None,   # None = gd_turn.DEFAULT_LOG_PATH (GD_TURN_LOG or the temp dir)
        )
    except Exception:
        # No silent fallback to the old keyword coach: say plainly that the turn did not happen.
        return GD_UNAVAILABLE_LINE
    for c in result.get("cited") or []:
        try:
            # The warranty story and source ledger are keyed by manual TITLE (parse_cited_pages_from_text), so the
            # cited doc id is turned into its library title here; an unknown id stays as the id.
            record_cited_pages(f"📖 Source: {_gd_page_finder().doc_title(c.get('doc_id'))} - page {c.get('page')}")
        except Exception:
            pass
    return result["reply"]


def guided_diagnostics_reply(
    user_msg: str,
    category_name: str,
    model_text: str,
    history: list,
    unity_gate: str = "",
    ask_flow: dict = None,
    photo: tuple | None = None,
    photo_review: dict | None = None,
    pin_store: dict | None = None,
):
    """Guided Diagnostics on the fresh core. Returns (reply_text, None).

    unity_gate and ask_flow are accepted for old callers and ignored (the Unity selector and hard trees are gone).
    A step photo is read by the vision model and its reading is added to the tech's message, marked as such.
    """
    if not ai_available():
        return GD_OFFLINE_LINE, None
    official_msg = user_msg
    if photo_review is None and photo and photo[0]:
        try:
            import gd_step_photo as _photos
            photo_review = _photos.review_step_photo(photo[0], photo[1] if len(photo) > 1 else "image/jpeg", "", user_msg)
        except Exception:
            photo_review = None
    sees = (photo_review or {}).get("sees") if isinstance(photo_review, dict) else ""
    if sees:
        official_msg = (user_msg + "\n" if user_msg else "") + f"Label/photo shows: {sees}"
    return _gd_official_reply(official_msg, category_name, model_text, history, pin_store), None


# ---------------- END GUIDED FLOW ENGINE ----------------


# ---------------- ASK TECHTRACK (chat diagnose) ----------------
ASK_TECHTRACK_SYSTEM = ""  # removed 2026-10-23 (Chase order): the Ask prompt is now the primer (gd_prompt.PRIMER); original in drafts/REMOVED-RULES-2026-10-23


def ask_chat_to_warranty_story(history: list, category_name: str = "", model_text: str = "") -> str:
    # Rule 10: on the official GD path the story comes from the session's recorded facts only.
    if GD_OFFICIAL_METHOD:
        try:
            import gd_story
            _case = (st.session_state.get("gd_pin_store") or {}).get("gd_case")
            if _case:
                return gd_story.warranty_story(_case, history, model_text)
        except Exception:
            pass
    """Feed Guided Diagnostics tech lines into improve_tech_story. Coach lines are recommendations only."""
    tech_lines = []
    coach_lines = []
    first_user = ""
    for m in history or []:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            if not first_user:
                first_user = content
            tech_lines.append(content)
        else:
            coach_lines.append(content[:1600])
    notes_parts = []
    if category_name:
        notes_parts.append(f"Category: {category_name}")
    if model_text:
        notes_parts.append(f"Model/System: {model_text}")
    tech_blob = "\n\n".join(tech_lines) if tech_lines else "(none)"
    notes_parts.append(
        "TECH REPORTED (only these are performed tests / readings / status):\n"
        + tech_blob
    )
    if coach_lines:
        notes_parts.append(
            "COACH SUGGESTIONS (recommended only - do NOT treat as performed unless the tech later confirmed the result). "
            "If the tech later said good/pass/done on a recommended check, bind that pass to the coach's exact location and threshold; do not invent a reading:\n"
            + "\n---\n".join(coach_lines[:4])
        )
    cite_lines = []
    seen_cites = set()
    for c in (st.session_state.get("ask_cited_log") or []):
        title = (c.get("title") or "").strip()
        page = c.get("page")
        if not title or not page:
            continue
        key = (title.lower(), int(page))
        if key in seen_cites:
            continue
        seen_cites.add(key)
        cite_lines.append(f"📖 Source: {title} - page {page}")
    for s in (st.session_state.get("ask_sources") or []):
        title = (s.get("title") or "").strip()
        page = s.get("page")
        if not title or not page:
            continue
        key = (title.lower(), int(page))
        if key in seen_cites:
            continue
        seen_cites.add(key)
        cite_lines.append(f"📖 Source: {title} - page {page}")
    if cite_lines:
        notes_parts.append(
            "SILENT SOURCE LEDGER (attach the matching 📖 Source line to tests the technician actually performed; "
            "do not invent pages; do not cite a page the tech did not run):\n"
            + "\n".join(cite_lines)
        )
    # Status from tech lines only so coach "replace the overload" cannot flip OPEN/complete.
    return improve_tech_story(first_user, "\n\n".join(notes_parts), status_text=tech_blob)


def seed_data():
    if session.query(User).count() == 0:
        session.add(User(username="manager", password_hash=hash_password("manager123"), full_name="Shop Manager", role="Manager"))
        session.add(User(username="alex", password_hash=hash_password("tech123"), full_name="Alex Tech", role="Technician"))
        session.add(User(username="jordan", password_hash=hash_password("tech123"), full_name="Jordan Tech", role="Technician"))
        session.commit()
    existing = {c.name for c in session.query(Category).all()}
    added = False
    for name in DEFAULT_LIBRARY_CATEGORIES:
        if name not in existing:
            session.add(Category(name=name))
            added = True
    if added:
        session.commit()


maybe_restore_db_from_r2()
seed_data()
purge_old_ask_chats(30)
try:
    import gd_work_orders as _gd_wo
    _gd_wo.purge_old(session, DiagnosticJob)          # WORK_ORDER_RETENTION_DAYS (30), purged on load
except Exception:
    pass

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "active_job_id" not in st.session_state:
    st.session_state.active_job_id = None
if "ask_chat" not in st.session_state:
    st.session_state["ask_chat"] = []
if "ask_chat_id" not in st.session_state:
    st.session_state["ask_chat_id"] = None

# CookieManager mounts a component every run. Leaving it up after sign-in
# kept a custom-component callback in the script, so Stop never cleared
# on an idle page. Read or write the cookie only on the login and logout paths.
_cookie_mgr = _cookie_manager() if st.session_state.user is None else None
if st.session_state.user is None:
    restored = _load_auth_token(_cookie_get(_cookie_mgr, AUTH_COOKIE_NAME))
    if restored:
        st.session_state.user = restored
        row = session.query(User).get(restored["id"])
        if row:
            _cookie_set_auth(_cookie_mgr, _issue_auth_token(row))

if st.session_state.user is None:
    _lc, login_col, _rc = st.columns([1, 1.5, 1])
    with login_col:
        _logo = shop_logo_path()
        if _logo:
            st.image(str(_logo), use_container_width=True)
        st.markdown(
            "<h1 style='text-align:center;margin:0.35rem 0 0;color:#01147C;font-size:2rem;'>TechTrack</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#02763A;font-weight:600;margin:0.2rem 0 1.1rem;'>"
            "Tacoma RV Center · Service</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", type="primary"):
                user = session.query(User).filter_by(username=u.strip().lower(), is_active=True).first()
                if user and verify_password(p, user.password_hash):
                    st.session_state.user = {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.full_name,
                        "role": user.role,
                    }
                    _cookie_set_auth(_cookie_mgr, _issue_auth_token(user))
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        if not _auth_serializer() or not COOKIE_MGR_AVAILABLE:
            st.caption(
                "Stay-signed-in is off until AUTH_COOKIE_SECRET is in Streamlit secrets "
                "and extra-streamlit-components is installed."
            )
    st.stop()

user = st.session_state.user
is_manager = user["role"] == "Manager"

# ---------------- HEADER / NAV ----------------
_hdr_logo = shop_logo_path()
hdr_l, hdr_r = st.columns([1.05, 3.6])
with hdr_l:
    if _hdr_logo:
        st.image(str(_hdr_logo), use_container_width=True)
with hdr_r:
    st.markdown(
        "<h1 style='margin:0.4rem 0 0;color:#01147C;font-size:1.85rem;'>TechTrack</h1>",
        unsafe_allow_html=True,
    )
    st.caption(f"Signed in as **{user['full_name']}** ({user['role']}) · Tacoma RV Center · Service")
if st.sidebar.button("Log out"):
    _cookie_clear_auth(_cookie_manager())
    st.session_state.user = None
    st.session_state.active_job_id = None
    st.session_state["ask_chat"] = []
    st.session_state.pop("ask_story_out", None)
    st.session_state.pop("ask_story_area", None)
    st.rerun()
st.sidebar.caption(f"Role: {user['role']}")

tabs = ["📱 My Dashboard", "💬 Guided Diagnostics", "📚 Document Library", "🛡️ Safety / Compliance"]
if is_manager:
    tabs.extend(["👥 Team Overview", "🛠️ Manager Tools"])
# Keyed radio, not st.tabs. The choice lives in session_state and survives
# the rerun after a GD reply. Only the selected section is rendered.
if st.session_state.get("tt_nav") not in tabs:
    st.session_state["tt_nav"] = tabs[0]
selected_nav = st.radio(
    "Section",
    tabs,
    key="tt_nav",
    horizontal=True,
    label_visibility="collapsed",
)
tab_dash = _Panel(tabs[0], selected_nav)
tab_ask = _Panel(tabs[1], selected_nav)
tab_lib = _Panel(tabs[2], selected_nav)
tab_safety = _Panel(tabs[3], selected_nav)
tab_team = _Panel(tabs[4], selected_nav) if is_manager else None
tab_mgr = _Panel(tabs[5], selected_nav) if is_manager else None

# =========================================================
# MY DASHBOARD
# =========================================================
with tab_dash:
    _enter_panel(tab_dash)
    st.subheader("📱 My Dashboard")
    c1, c2, c3 = st.columns(3)
    my_certs = session.query(Certificate).filter_by(user_id=user["id"]).count()
    safety_pct = get_safety_progress(user["id"])
    my_open = session.query(DiagnosticJob).filter_by(user_id=user["id"], status="in_progress").count()
    c1.metric("Certificates", my_certs)
    c2.metric("Safety Progress", f"{safety_pct}%")
    c3.metric("Open WO Jobs", my_open)

    st.markdown("#### 📜 My Certificates")
    certs = session.query(Certificate).filter_by(user_id=user["id"]).order_by(Certificate.created_date.desc()).all()
    if certs:
        for cert in certs:
            with st.container(border=True):
                st.write(f"**{cert.title}** - {cert.issuer or '-'}")
                if cert.issued_date:
                    st.caption(f"Issued: {cert.issued_date}")
                if cert.notes:
                    st.caption(cert.notes)
                r2_download_button("⬇️ Download", cert.file_path, f"{cert.title}.pdf", f"dl_cert_{cert.id}")
    else:
        st.info("No certificates uploaded yet.")

    with st.expander("⬆️ Upload Certificate", expanded=False):
        if not r2_available():
            st.warning("File storage is not configured yet. Contact a manager.")
        else:
            ct = st.text_input("Certificate Title", key="cert_title")
            ci = st.text_input("Issuer (Lippert, RVTI, Airexcel, etc.)", key="cert_issuer")
            cd = st.text_input("Issued Date (optional)", key="cert_date")
            cn = st.text_area("Notes (optional)", key="cert_notes")
            cf = st.file_uploader("PDF Certificate", type=["pdf"], key="cert_file")
            if st.button("Save Certificate", type="primary", key="save_cert"):
                if ct and cf:
                    key = f"certificates/{user['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{cf.name}"
                    if r2_upload(cf.getvalue(), key, "application/pdf"):
                        session.add(Certificate(
                            user_id=user["id"],
                            title=ct.strip(),
                            issuer=ci.strip(),
                            file_path=key,
                            issued_date=cd.strip(),
                            notes=cn.strip(),
                            uploaded_by=user["id"],
                        ))
                        session.commit()
                        st.success("Certificate saved permanently!")
                        st.rerun()
                else:
                    st.warning("Title and PDF are required.")

    st.markdown("#### ✍️ Quick Story Improver (no WO)")
    st.caption(
        "For one-off claims after you already tested."
    )
    sc = st.text_area("1. Customer Concern", key="story_concern", placeholder="Customer states the air conditioner is not cooling…")
    sn = st.text_area("2. What you found and did", key="story_notes", placeholder="Found bad compressor. Recovered, replaced, evacuated, recharged, tested.")
    if st.button("Improve Story", type="primary", key="improve_story_btn"):
        if sc.strip() or sn.strip():
            with st.spinner("Writing improved warranty story..."):
                improved = improve_tech_story(sc, sn)
            st.markdown("### Improved Version")
            st.text_area("Copy this improved story", value=improved, height=320, key="story_improved")
        else:
            st.warning("Please enter at least the customer concern or your notes.")

# =========================================================
# ASK TECHTRACK
# =========================================================
with tab_ask:
    _enter_panel(tab_ask)
    # Apply before widgets and before history is read, so the next message
    # cannot see the previous case.
    if st.session_state.pop("ask_reset_session", False):
        reset_guided_diagnostics_session()
    st.subheader("💬 Guided Diagnostics")
    st.caption(
        "Guided Diagnostics works from the complaint, the shop's manuals and, when it helps, the web. "
        "Ask questions, ask for clarification, or ask to see a cited page figure/diagram in this chat. "
        "Write warranty story uses the chat plus any unsent text."
    )

    if "ask_chat" not in st.session_state:
        st.session_state["ask_chat"] = []
    if "ask_chat_id" not in st.session_state:
        st.session_state["ask_chat_id"] = None
    if "ask_sources" not in st.session_state:
        st.session_state["ask_sources"] = []
    if "ask_cited_log" not in st.session_state:
        st.session_state["ask_cited_log"] = []
    if "ask_flow" not in st.session_state:
        st.session_state["ask_flow"] = None

    with st.expander("Recent chats (saved 30 days)", expanded=False):
        qch = session.query(AskChat)
        if not is_manager:
            qch = qch.filter_by(user_id=user["id"])
        recents = qch.order_by(AskChat.updated_date.desc()).limit(20).all()
        if not recents:
            st.caption("No saved chats yet. Send a message and it stays here.")
        for ch in recents:
            owner = session.query(User).get(ch.user_id)
            when = (ch.updated_date or ch.created_date)
            when_s = when.strftime("%b %d %I:%M %p") if when else ""
            who = f" · {owner.full_name}" if is_manager and owner else ""
            label = f"{(ch.title or 'Chat')[:60]} · {ch.category_name or 'any'}{who} · {when_s}"
            cols = st.columns([4, 1])
            cols[0].write(label)
            if cols[1].button("Open", key=f"open_ask_{ch.id}"):
                loaded, hist = load_ask_chat(ch.id)
                st.session_state["ask_chat_id"] = ch.id
                st.session_state["ask_chat"] = hist
                st.session_state["ask_sources"] = []
                st.session_state["ask_cited_log"] = []
                st.session_state["ask_flow"] = None
                st.session_state.pop("ask_auto_show", None)
                for m in hist:
                    if (m.get("role") or "") == "assistant":
                        record_cited_pages(m.get("content") or "")
                st.session_state.pop("ask_story_out", None)
                st.session_state.pop("ask_story_area", None)
                st.session_state["ask_story_n"] = int(st.session_state.get("ask_story_n") or 0) + 1
                if loaded and loaded.final_story:
                    st.session_state["ask_story_out"] = loaded.final_story
                _wo_row = session.query(DiagnosticJob).filter_by(user_id=user["id"], ask_chat_id=ch.id).first()
                st.session_state["ask_wo_number"] = _wo_row.wo_number if _wo_row else ""
                st.rerun()

    _render_past_work_orders(user["id"])

    cats = session.query(Category).order_by(Category.name).all()
    cat_names = gd_category_select_options([c.name for c in cats])
    _restore_widget("ask_cat", "gd_category_memory", cat_names)
    if st.session_state.pop("ask_clear_cat", False):
        st.session_state["ask_cat"] = "(any)"
        st.session_state["gd_category_memory"] = "(any)"
    if st.session_state.pop("ask_clear_model", False):
        st.session_state["ask_model"] = ""
        st.session_state["gd_model_memory"] = ""
        st.session_state.pop("gd_pin_store", None)
    apply_pending_plate_read("ask_model", "gd_model_memory")
    _restore_widget("ask_model", "gd_model_memory")
    c1, c2 = st.columns(2)
    with c1:
        ask_cat = st.selectbox("Category (optional)", cat_names, key="ask_cat")
    with c2:
        ask_model = st.text_input(
            "Model / System (optional)",
            key="ask_model",
            placeholder="RM2652, Schwintek, Hydro-Hot…",
        )
        show_plate_read_note("ask_model")
    with st.expander("📷 Read model from data plate photo", expanded=False):
        st.caption("Snap or upload the rating plate. TechTrack fills Model/System. Uses the shop AI already on this app.")
        plate_cam = st.camera_input("Snap data plate", key="ask_plate_cam")
        plate_up = st.file_uploader(
            "Or upload plate photo",
            type=["jpg", "jpeg", "png", "webp"],
            key="ask_plate_upload",
        )
        plate_img = plate_cam or plate_up
        if plate_img is not None:
            st.image(plate_img, caption="Plate photo", width=280)
            apply_plate_read_to_model_key("ask_model", plate_img, "ask_plate_read_btn")
    unity_gate = ""  # Unity selector removed (fresh-core): the tech names the controller in chat if it matters
    _remember_widget("ask_cat", "gd_category_memory")
    _remember_widget("ask_model", "gd_model_memory")
    category_name = "" if ask_cat == "(any)" else ask_cat

    history = st.session_state.get("ask_chat") or []
    if history:
        st.markdown("#### Conversation")
        for index, m in enumerate(history):
            role = m.get("role") or "user"
            content = m.get("content") or ""
            label = "You" if role == "user" else "Guided Diagnostics"
            with st.container(border=True):
                st.caption(label)
                st.markdown(re.sub(r"<!--\s*gd-step:\d+\s*-->", "", content).strip())
                if role == "user":
                    continue
                # Figures render only when this turn stored them. A step reply
                # does not pull a manual image until the tech asks.
                step_figs = (m.get("figures") or []) if isinstance(m, dict) else []
                _render_gd_figures_under_step(step_figs, f"gd_step_{index}")
    else:
        st.info("Describe the symptom, what you have already checked, or paste an error code.")
    if st.session_state.pop("ask_reset_input", False):
        st.session_state["ask_input"] = ""

    _last_message = history[-1] if history else {}
    _last_has_figures = bool(isinstance(_last_message, dict) and _last_message.get("figures"))
    auto_pages = st.session_state.get("ask_auto_show") or []
    if auto_pages and not _last_has_figures:
        render_on_demand_library_pages(auto_pages)
    elif st.session_state.pop("ask_auto_show_failed", None):
        fail_note = st.session_state.pop("ask_auto_show_fail_note", None) or figure_render_honesty_note(
            "", True
        )
        st.warning(fail_note)

    # Hard-tree Yes/No buttons are off on the open-coach product path.
    if HARD_TREE_EXCLUSIVE_CHAT:
        _flow_now = st.session_state.get("ask_flow") or {}
        _proc_now = None
        _node_now = None
        if _flow_now.get("procedure_id") and _flow_now.get("node_id"):
            _proc_now = PROCEDURE_TREES.get(_flow_now.get("procedure_id"))
            _node_now = get_procedure_node(_proc_now, _flow_now.get("node_id")) if _proc_now else None
        _bin = binary_button_labels(_node_now) if _node_now else None
        if _bin:
            _bl, _bk, _br, _brk = _bin
            bb1, bb2 = st.columns(2)
            if bb1.button(_bl, key="ask_flow_yes", use_container_width=True):
                st.session_state["ask_pending_answer"] = _bk
                st.session_state["ask_force_send"] = True
                st.rerun()
            if bb2.button(_br, key="ask_flow_no", use_container_width=True):
                st.session_state["ask_pending_answer"] = _brk
                st.session_state["ask_force_send"] = True
                st.rerun()

    # Ctrl+Enter in a bare text_area only commits the widget and reruns.
    # It does not click Send, so the draft stayed in the box. A form submits
    # on Ctrl+Enter and sends the text with that same click (no lost first click).
    _photo_gen = int(st.session_state.get("ask_photo_gen") or 0)
    with st.form("gd_send_form", clear_on_submit=False):
        st.text_area(
            "Your message",
            key="ask_input",
            height=100,
            placeholder="Customer states fridge not cooling on gas or electric. Display is on. Unit is level…",
        )
        ask_photo = st.file_uploader(
            "Photo (optional)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"ask_photo_{_photo_gen}",
            help="Tag, leak, connector, meter reading, or the part. A photo is optional. You can type what you see.",
        )
        send_col, hint_col = st.columns([1, 2])
        with send_col:
            send = st.form_submit_button("Send", type="primary", use_container_width=True)
        with hint_col:
            st.caption("Ctrl+Enter sends this message. Add a photo when the step asks, or type what you see.")
    b2, b3 = st.columns(2)
    with b2:
        new_chat = st.button("Start new chat", key="ask_new", use_container_width=True)
    with b3:
        write_story = st.button("Write warranty story", key="ask_story", use_container_width=True)
    w1, w2 = st.columns([2, 1])
    with w1:
        st.text_input("Work order # (optional)", key="ask_wo_number", placeholder="WO number for this job")
    with w2:
        st.write("")
        save_wo = st.button("💾 Save work order", key="ask_save_wo", use_container_width=True)
    _wo_note = st.session_state.pop("ask_wo_saved_note", None)
    if _wo_note:
        st.success(_wo_note)
    if save_wo:
        _saved = save_gd_work_order(user["id"], wo_number=st.session_state.get("ask_wo_number") or "")
        if _saved is not None:
            # rerun so the Past work orders list above shows it now
            st.session_state["ask_wo_saved_note"] = f"Saved WO {_saved.wo_number}. It is under Past work orders."
            st.rerun()
        else:
            st.warning("Send a message first, then save the work order.")

    if new_chat:
        # Flag only. Widget keys are reset on the next run, before history is read.
        st.session_state["ask_reset_session"] = True
        st.session_state["ask_chat"] = []
        st.session_state["ask_chat_id"] = None
        clear_ask_source_state()
        st.session_state.pop("ask_pending_answer", None)
        st.session_state.pop("ask_force_send", None)
        st.session_state["gd_model_memory"] = ""
        st.session_state["gd_category_memory"] = "(any)"
        st.session_state["ask_photo_gen"] = int(st.session_state.get("ask_photo_gen") or 0) + 1
        st.rerun()

    if send or st.session_state.pop("ask_force_send", False):
        msg = (st.session_state.pop("ask_pending_answer", None) or st.session_state.get("ask_input") or "").strip()
        photo_bytes = b""
        photo_mime = "image/jpeg"
        if ask_photo is not None:
            photo_bytes = ask_photo.getvalue() if hasattr(ask_photo, "getvalue") else bytes(ask_photo)
            photo_mime = getattr(ask_photo, "type", None) or "image/jpeg"
        if not msg and not photo_bytes:
            st.warning("Type what you see, or add a photo.")
        else:
            import gd_step_photo as _photos

            photo_review = None
            if photo_bytes:
                asked = ""
                for message in reversed(history or []):
                    if (message.get("role") or "") == "assistant" and (message.get("content") or "").strip():
                        asked = message.get("content") or ""
                        break
                with st.spinner("Reading the photo…"):
                    photo_review = _photos.review_step_photo(
                        photo_bytes, photo_mime, asked, msg
                    )
            with st.spinner("Searching manuals and thinking…"):
                reply, new_flow = guided_diagnostics_reply(
                    msg,
                    category_name,
                    ask_model or "",
                    history,
                    unity_gate=unity_gate,
                    ask_flow=st.session_state.get("ask_flow"),
                    photo_review=photo_review,
                    pin_store=st.session_state.setdefault("gd_pin_store", {}),
                )
            st.session_state["ask_flow"] = new_flow
            history = list(history)
            stored_msg = _photos.history_user_text(msg, bool(photo_bytes), photo_review)
            history.append({"role": "user", "content": stored_msg})
            import manual_figures as _mf
            _asked_image = wants_library_page_shown(msg) or _mf.tech_asked_for_manual_figure(msg)
            _step_figs = []
            if _asked_image:
                try:
                    import library_figure_backfill as fb

                    _step_figs = fb.gd_figures_under_step(
                        fb.meta_rows(session), reply, msg, category_name, ask_model or ""
                    )
                except Exception:
                    _step_figs = []
            history.append({
                "role": "assistant",
                "content": reply,
                "figures": _figures_for_session(_step_figs),
            })
            st.session_state["ask_chat"] = history
            st.session_state["ask_photo_gen"] = _photo_gen + 1
            st.session_state["ask_chat_id"] = persist_ask_turn(
                user["id"],
                st.session_state.get("ask_chat_id"),
                category_name,
                ask_model or "",
                stored_msg,
                reply,
            )
            st.session_state["gd_case_chat_id"] = st.session_state["ask_chat_id"]
            save_gd_work_order(user["id"], only_if_closed_or_saved=True,
                               wo_number=st.session_state.get("ask_wo_number") or "")
            _offers = _stored_figure_matches(reply, msg, category_name, ask_model or "")
            if _step_figs:
                st.session_state.pop("ask_auto_show", None)
                st.session_state["ask_auto_show_failed"] = False
                st.session_state.pop("ask_auto_show_fail_note", None)
            elif _asked_image and _offers:
                st.session_state["ask_auto_show"] = _figures_for_session(
                    _offers[:3] if _asked_image else _offers[:1]
                )
                st.session_state["ask_auto_show_failed"] = False
                st.session_state.pop("ask_auto_show_fail_note", None)
            elif _asked_image:
                # Prefer current reply cites; else fall back to prior coach Source lines
                coach_for_pages = reply or ""
                if not parse_cited_pages_from_text(coach_for_pages):
                    for m in reversed(history[:-1] if history else []):
                        if (m.get("role") or "") == "assistant":
                            coach_for_pages = m.get("content") or coach_for_pages
                            break
                pages = resolve_requested_library_pages(msg, coach_for_pages)
                st.session_state["ask_auto_show"] = _figures_for_session(pages)
                st.session_state["ask_auto_show_failed"] = not bool(pages)
                if not pages:
                    cited = parse_cited_pages_from_text(coach_for_pages)
                    fail_title = (cited[-1].get("title") if cited else "") or ""
                    if is_unity_board_manual(fail_title) or is_level_up_advantage_context(
                        category_name, ask_model or "", msg
                    ):
                        seed_lu = resolve_level_up_document_seed()
                        fail_title = (seed_lu or {}).get("title") or fail_title
                    if is_air_conditioning_context(category_name, ask_model or "", msg) or (
                        is_unity_board_manual(fail_title)
                        and is_air_conditioning_context(category_name, ask_model or "", msg)
                    ):
                        seed_ac = resolve_ac_document_seed()
                        if seed_ac:
                            fail_title = seed_ac.get("title") or fail_title
                    if is_water_heater_context(category_name, ask_model or "", msg) or (
                        is_unity_board_manual(fail_title)
                        and is_water_heater_context(category_name, ask_model or "", msg)
                    ):
                        seed_wh = resolve_water_heater_document_seed()
                        if seed_wh:
                            fail_title = seed_wh.get("title") or fail_title
                    st.session_state["ask_auto_show_fail_note"] = figure_render_honesty_note(
                        fail_title, True
                    )
                else:
                    st.session_state.pop("ask_auto_show_fail_note", None)
            else:
                st.session_state.pop("ask_auto_show", None)
                st.session_state.pop("ask_auto_show_failed", None)
            st.session_state["ask_reset_input"] = True
            st.rerun()

    if write_story:
        draft = (st.session_state.get("ask_input") or "").strip()
        if draft:
            history = list(history)
            history.append({"role": "user", "content": draft})
            st.session_state["ask_chat"] = history
            st.session_state["ask_chat_id"] = persist_ask_turn(
                user["id"],
                st.session_state.get("ask_chat_id"),
                category_name,
                ask_model or "",
                draft,
                "(notes recorded for warranty story)",
            )
            st.session_state["ask_reset_input"] = True
        if not history:
            st.warning("Chat is empty. Type the notes or send a message first, then write the story.")
        else:
            with st.spinner("Writing shop notes from what you actually recorded…"):
                story = ask_chat_to_warranty_story(history, category_name, ask_model or "")
            st.session_state["ask_story_out"] = story
            # text_area(key=) ignores value= after first mount. Bump the key so
            # this click remounts the box with the newly generated story.
            st.session_state.pop("ask_story_area", None)
            n = int(st.session_state.get("ask_story_n") or 0) + 1
            st.session_state["ask_story_n"] = n
            st.session_state[f"ask_story_area_{n}"] = story
            cid = st.session_state.get("ask_chat_id")
            if cid:
                chat_row = session.query(AskChat).get(cid)
                if chat_row:
                    chat_row.final_story = story
                    chat_row.updated_date = datetime.now()
                    session.commit()
                save_gd_work_order(user["id"], wo_number=st.session_state.get("ask_wo_number") or "")
            st.rerun()

    if st.session_state.get("ask_story_out"):
        st.markdown("### Shop notes / warranty story")
        _story_n = int(st.session_state.get("ask_story_n") or 0)
        _story_key = f"ask_story_area_{_story_n}"
        if _story_key not in st.session_state:
            st.session_state[_story_key] = st.session_state["ask_story_out"]
        st.text_area(
            "Copy into the warranty claim",
            height=280,
            key=_story_key,
        )
        st.caption(
            "Only uses tests and readings you typed. Recommended checks are left out unless you said you did them. "
            "Start a new chat to begin a different job."
        )

# =========================================================
# DOCUMENT LIBRARY
# =========================================================
with tab_lib:
    _enter_panel(tab_lib)
    st.subheader("📚 Document Library (Manuals & Troubleshooting)")
    cats = session.query(Category).order_by(Category.name).all()
    cat_names = library_category_picker_names([c.name for c in cats])
    if not cat_names:
        st.warning("No categories yet. Ask a manager to create some.")
    else:
        cat_name = st.selectbox("Select Category", cat_names, key="lib_cat")
        cat = next((c for c in cats if c.name == cat_name), None) or session.query(Category).filter_by(name=cat_name).first()
        q = st.text_input("Search documents by title, keyword, or model", key="lib_search")
        docs = session.query(Document).filter_by(category_id=cat.id).order_by(Document.title).all() if cat else []
        brands = sorted(
            {(d.brand or "").strip() for d in docs if (d.brand or "").strip()},
            key=str.lower,
        )
        brand_pick = "(any)"
        if brands:
            brand_pick = st.selectbox("Brand", ["(any)", *brands], key="lib_brand")
        model_q = st.text_input("Model", key="lib_model")
        docs = [
            d for d in docs
            if library_bulk_import.library_record_matches(d, query=q, brand=brand_pick, model=model_q)
        ]
        st.write(f"**{len(docs)} document(s) found**")
        if not docs:
            st.info("No documents matched your search.")
        for d in docs:
            with st.container(border=True):
                idx = "✅" if d.indexed else "⚠️ not indexed"
                st.write(f"**{d.title}** · {idx}")
                meta_bits = [
                    bit
                    for bit in (
                        (d.brand or "").strip(),
                        (d.models or "").strip(),
                        (d.doc_number or d.ti_number or "").strip(),
                    )
                    if bit
                ]
                if meta_bits:
                    st.caption(" · ".join(meta_bits))
                if d.keywords:
                    st.caption(d.keywords)
                r2_download_button("⬇️ Download", d.file_path, f"{d.title}.pdf", f"lib_dl_{d.id}")

# =========================================================
# SAFETY
# =========================================================
with tab_safety:
    _enter_panel(tab_safety)
    st.subheader("🛡️ Safety / Compliance")
    st.markdown("#### Safety Documents")
    sq = st.text_input("Search safety documents", key="safety_doc_search")
    sdocs = session.query(SafetyDocument).order_by(SafetyDocument.title).all()
    if sq.strip():
        terms = sq.lower().split()
        sdocs = [d for d in sdocs if all(t in f"{d.title} {d.keywords or ''}".lower() for t in terms)]
    if not sdocs:
        st.info("No safety documents available.")
    for d in sdocs:
        with st.container(border=True):
            st.write(f"**{d.title}**")
            r2_download_button("⬇️ Download", d.file_path, f"{d.title}.pdf", f"saf_dl_{d.id}")

    st.markdown("#### Safety Meetings - Acknowledgement Required")
    meetings = session.query(SafetyMeeting).order_by(SafetyMeeting.created_date.desc()).all()
    if not meetings:
        st.info("No safety meetings have been created yet.")
    for m in meetings:
        with st.container(border=True):
            st.write(f"**{m.title}**")
            st.caption(f"Meeting Date: {m.meeting_date or '-'} · Created: {m.created_date}")
            if m.notes:
                st.write(m.notes)
            if m.file_path:
                r2_download_button("Download Presentation", m.file_path, f"{m.title}.pdf", f"meet_dl_{m.id}")
            ack = session.query(SafetyAcknowledgement).filter_by(meeting_id=m.id, user_id=user["id"]).first()
            if ack:
                st.success(f"✅ You acknowledged this meeting on {ack.signed_at}")
            else:
                if st.checkbox(
                    "I attended this safety meeting, received the training, and understand the material.",
                    key=f"ack_chk_{m.id}",
                ):
                    if st.button("Sign Acknowledgement", key=f"ack_btn_{m.id}", type="primary"):
                        session.add(SafetyAcknowledgement(meeting_id=m.id, user_id=user["id"], understood=True))
                        session.commit()
                        st.success("Acknowledgement recorded. Thank you.")
                        st.rerun()

# =========================================================
# TEAM OVERVIEW (manager)
# =========================================================
if is_manager and tab_team is not None:
    with tab_team:
        _enter_panel(tab_team)
        st.subheader("Certificate & Safety Summary")
        techs = session.query(User).filter_by(is_active=True).order_by(User.full_name).all()
        for t in techs:
            cert_n = session.query(Certificate).filter_by(user_id=t.id).count()
            sp = get_safety_progress(t.id)
            with st.container(border=True):
                st.write(f"**{t.full_name}** ({t.role})")
                c1, c2 = st.columns(2)
                c1.metric("Certificates", cert_n)
                c2.metric("Safety Progress", f"{sp}%")
                if sp < 100:
                    meetings = session.query(SafetyMeeting).all()
                    missing = []
                    for m in meetings:
                        if not session.query(SafetyAcknowledgement).filter_by(meeting_id=m.id, user_id=t.id).first():
                            missing.append(m.title)
                    if missing:
                        st.warning("⚠️ Missing acknowledgements: " + ", ".join(missing))
                with st.expander(f"{t.full_name}'s certificates"):
                    for cert in session.query(Certificate).filter_by(user_id=t.id).all():
                        st.write(f"- **{cert.title}** ({cert.issuer or '-'})")

        st.markdown("#### Recent Diagnostic Jobs (all techs)")
        jobs = session.query(DiagnosticJob).order_by(DiagnosticJob.updated_date.desc()).limit(25).all()
        for j in jobs:
            u = session.query(User).get(j.user_id)
            st.write(f"**WO {j.wo_number}** · {j.status} · {u.full_name if u else '?'} · {j.category_name} · {(j.concern or '')[:80]}")

# =========================================================
# MANAGER TOOLS
# =========================================================
if is_manager and tab_mgr is not None:
    with tab_mgr:
        _enter_panel(tab_mgr)
        st.subheader("🛠️ Manager Tools")
        st.warning(
            "The full database (titles, keywords, users, WO jobs, chats) now auto-saves to R2. "
            "If Streamlit wipes the local file, TechTrack restores the last good copy on boot. "
            "You can still download a copy under **Database Backup & Restore**."
        )
        doc_count = session.query(Document).count()
        st.info(f"Library right now: **{doc_count}** document record(s) in the database.")

        try:
            _bulk_open = library_bulk_import.latest_open_job(session)
        except Exception:
            _bulk_open = None
        with st.expander("📥 Bulk import", expanded=_bulk_open is not None):
            library_bulk_import.render_manager_bulk_panel(
                st,
                session=session,
                db_path=DB_PATH,
                user_id=user["id"],
                upload_bytes=r2_put_bytes,
                download_bytes=r2_download_bytes,
                backup_db=lambda: maybe_backup_db_to_r2(force=True),
                r2_prefix_totals=r2_prefix_totals,
                r2_ready=r2_available(),
                delete_bytes=r2_delete_object,
                index_figures=_bulk_index_figures,
                stream_download=r2_download_to_file,
            )

        with st.expander("👤 User Management", expanded=False):
            st.markdown("#### Add New User")
            nu = st.text_input("Username", key="new_username")
            nn = st.text_input("Full Name", key="new_fullname")
            np = st.text_input("Temporary Password", key="new_pass")
            nr = st.selectbox("Role", ["Technician", "Manager"], key="new_role")
            if st.button("Create User"):
                if nu and nn and np:
                    if session.query(User).filter_by(username=nu.strip().lower()).first():
                        st.error("Username already exists.")
                    else:
                        session.add(User(
                            username=nu.strip().lower(),
                            password_hash=hash_password(np),
                            full_name=nn.strip(),
                            role=nr,
                        ))
                        session.commit()
                        st.success(f"Created {nu}")
                        st.rerun()
                else:
                    st.warning("All fields required.")

            st.markdown("#### Existing Users")
            for u in session.query(User).order_by(User.full_name).all():
                with st.container(border=True):
                    st.write(f"**{u.full_name}** (@{u.username}) · {u.role} · Active: {u.is_active}")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        new_role = st.selectbox("Role", ["Technician", "Manager"], index=0 if u.role != "Manager" else 1, key=f"role_{u.id}")
                        if st.button("Update Role", key=f"upd_role_{u.id}"):
                            u.role = new_role
                            session.commit()
                            st.success("Role updated")
                            st.rerun()
                    with c2:
                        if st.button("Reset Password", key=f"reset_{u.id}"):
                            u.password_hash = hash_password("temp123")
                            session.commit()
                            st.success(f"Password for {u.username} reset to: temp123")
                    with c3:
                        if st.button("Deactivate" if u.is_active else "Activate", key=f"act_{u.id}"):
                            u.is_active = not u.is_active
                            session.commit()
                            st.rerun()

        with st.expander("📁 Manage Categories", expanded=False):
            st.markdown("#### Add Category")
            cn = st.text_input("Category Name", key="cat_new")
            if st.button("Create Category"):
                if cn.strip() and not session.query(Category).filter_by(name=cn.strip()).first():
                    session.add(Category(name=cn.strip()))
                    session.commit()
                    st.success("Category created.")
                    st.rerun()
                else:
                    st.warning("Name required or already exists.")
            for c in session.query(Category).order_by(Category.name).all():
                cols = st.columns([3, 1])
                cols[0].write(f"**{c.name}**")
                if cols[1].button("Delete", key=f"del_cat_{c.id}"):
                    if session.query(Document).filter_by(category_id=c.id).count() == 0:
                        session.delete(c)
                        session.commit()
                        st.rerun()
                    else:
                        st.error("Category has documents - move or delete them first.")

        with st.expander("📤 Upload Documents to Categories", expanded=False):
            if not r2_available():
                st.error("R2 storage is not configured. Check Streamlit Secrets.")
            else:
                cats = session.query(Category).order_by(Category.name).all()
                if cats:
                    ucat = st.selectbox("Category", [c.name for c in cats], key="up_cat")
                    utitle = st.text_input("Document Title", key="up_title")
                    ukw = st.text_input("Keywords (models, brand names - helps search)", key="up_kw", placeholder="Schwintek, In-Wall, Lippert, error codes")
                    ufile = st.file_uploader("PDF / PPTX / Image", type=["pdf", "pptx", "png", "jpg", "jpeg"], key="up_file")
                    import library_category_audit as _cataudit

                    _cat_warn = _cataudit.upload_category_warning(utitle, ucat) if utitle else ""
                    _cat_ok = True
                    if _cat_warn:
                        # R2: the chosen category disagrees with the document's own type words -> warn and require a confirmation.
                        st.warning(f"Category check: {_cat_warn}")
                        _cat_ok = st.checkbox(f"File it under '{ucat}' anyway", key="up_cat_confirm")
                    if st.button("Upload Document", type="primary", disabled=not _cat_ok):
                        if utitle and ufile:
                            cat = session.query(Category).filter_by(name=ucat).first()
                            ext = (ufile.name.split(".")[-1] or "pdf").lower()
                            key = f"documents/{cat.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{ufile.name}"
                            ctype = "application/pdf" if ext == "pdf" else "application/octet-stream"
                            raw = ufile.getvalue()
                            sha = hashlib.sha256(raw).hexdigest()
                            dup = session.query(Document).filter(Document.content_sha256 == sha).first()
                            if dup:
                                st.warning(f"This file is already in the library as {dup.title}.")
                            elif r2_upload(raw, key, ctype):
                                doc = Document(
                                    category_id=cat.id,
                                    title=utitle.strip(),
                                    file_path=key,
                                    file_type=ext,
                                    uploaded_by=user["id"],
                                    keywords=ukw.strip(),
                                    content_sha256=sha,
                                    byte_size=len(raw),
                                )
                                session.add(doc)
                                session.commit()
                                if ext == "pdf":
                                    ok, note = index_document_from_bytes(doc, raw)
                                    if ok:
                                        st.success(f"Document uploaded and indexed. {note}")
                                    else:
                                        st.warning(f"Uploaded, but not indexed: {note}")
                                else:
                                    st.success("Document uploaded (non-PDF - not indexed for guided diagnostics).")
                                st.rerun()
                        else:
                            st.warning("Title and file required.")

        with st.expander("🧠 Re-index Manuals for Guided Diagnostics", expanded=False):
            st.caption(
                "Pulls each PDF from storage, extracts text, and stores searchable chunks. "
                "Run this after restoring a database or if older uploads were never indexed. "
                "A large Lippert or Furrion drop belongs in Bulk import, which saves after each batch."
            )
            if not PYPDF_AVAILABLE:
                st.error("Add `pypdf` to requirements.txt and reboot the app.")
            total_docs = session.query(Document).count()
            indexed_docs = session.query(Document).filter_by(indexed=True).count()
            chunk_count = session.query(DocChunk).count()
            st.write(f"Documents: **{total_docs}** • Indexed: **{indexed_docs}** • Text chunks: **{chunk_count}**")
            if st.button("Re-index All PDFs", type="primary"):
                ok_n = fail_n = 0
                prog = st.progress(0.0)
                docs = session.query(Document).all()
                for i, doc in enumerate(docs):
                    ok, note = index_document_from_r2(doc)
                    if ok:
                        ok_n += 1
                    else:
                        fail_n += 1
                    st.write(f"{'✅' if ok else '⚠️'} {doc.title} - {note}")
                    prog.progress((i + 1) / max(len(docs), 1))
                st.success(f"Indexed OK: {ok_n} · Skipped/failed: {fail_n}")
            st.caption(
                "Backfill is per case. It renders page images and figure crops for "
                "CCD-0008666, CCD-0007990, and the Thetford Style II docs. "
                "Select those manuals below. Other library manuals are not queued. "
                "Each click does a few manuals and saves progress, so you can leave and continue."
            )
            import library_figure_backfill as _fb
            _open = None
            try:
                _est = _fb.estimate_backfill(session)
                st.write(_fb.estimate_caption(_est))
                _open = _fb.open_job(session)
                if _open:
                    _counts = _fb.job_progress(session, int(_open["id"]))
                    st.write(
                        f"Figure backfill: **{_counts['done']}** of **{_counts['total']}** manuals. "
                        f"Failed {_counts['failed']}. Remaining {_counts['pending']}."
                    )
            except Exception as exc:
                st.error(f"Could not read the figure backfill: {exc}")
            _pdf_choices = []
            try:
                _pdf_choices = _fb.pdf_choices(session)
            except Exception:
                _pdf_choices = []
            _picked = []
            if _pdf_choices:
                _choice_labels = {int(row["id"]): row["title"] for row in _pdf_choices}
                _picked = st.multiselect(
                    "Backfill selected manuals",
                    options=list(_choice_labels),
                    format_func=lambda doc_id: _choice_labels.get(int(doc_id), str(doc_id)),
                    key="figure_backfill_docs",
                    help="CCD-0008666, CCD-0007990, Thetford 42088, 42109, 42110, 34123, 34122, and the Thetford parts list.",
                )
            if _picked and st.button("Backfill selected manuals"):
                _job_id = _fb.ensure_job(session, _picked)
                _bar = st.progress(0.0)

                def _tick_selected(index, total, title):
                    _bar.progress(min(1.0, index / max(total, 1)), text=title or "Rendering")

                _result = _fb.process_backfill_batch(
                    session,
                    _job_id,
                    download_pdf=_download_library_pdf,
                    upload_png=r2_put_bytes,
                    batch_size=2,
                    progress=_tick_selected,
                )
                if _result.get("busy"):
                    st.warning("This backfill is already running.")
                elif not _job_id:
                    st.warning("Select at least one manual.")
                else:
                    st.success(_fb.backfill_batch_message(_result))
            elif _open and not _picked and st.button("Continue figure backfill"):
                _bar = st.progress(0.0)

                def _tick_open(index, total, title):
                    _bar.progress(min(1.0, index / max(total, 1)), text=title or "Rendering")

                _result = _fb.process_backfill_batch(
                    session,
                    int(_open["id"]),
                    download_pdf=_download_library_pdf,
                    upload_png=r2_put_bytes,
                    batch_size=2,
                    progress=_tick_open,
                )
                if _result.get("busy"):
                    st.warning("This backfill is already running.")
                else:
                    st.success(_fb.backfill_batch_message(_result))

            st.markdown("#### Index status by document")
            try:
                _asset_counts = _fb.document_asset_counts(session)
            except Exception:
                _asset_counts = {}
            for d in session.query(Document).order_by(Document.title).all():
                _counts = _asset_counts.get(int(d.id), {"pages": 0, "figures": 0})
                st.write(
                    _fb.index_status_line(
                        d.title,
                        bool(d.indexed),
                        d.index_note or "",
                        _counts["pages"],
                        _counts["figures"],
                    )
                )

        with st.expander("✏️ Manage Documents (Rename / Edit / Delete)", expanded=False):
            cats = session.query(Category).order_by(Category.name).all()
            if not cats:
                st.info("No categories yet.")
            else:
                mcat = st.selectbox("Category", [c.name for c in cats], key="manage_doc_cat")
                cat = session.query(Category).filter_by(name=mcat).first()
                docs = session.query(Document).filter_by(category_id=cat.id).order_by(Document.title).all()
                st.write(f"**{len(docs)} document(s) in {mcat}**")
                if not docs:
                    st.info("No documents in this category.")
                for d in docs:
                    with st.container(border=True):
                        st.write(f"**Current title:** {d.title}")
                        st.caption("Indexed" if d.indexed else "Not indexed")
                        nt = st.text_input("Title", value=d.title, key=f"edit_title_{d.id}")
                        nk = st.text_input("Keywords", value=d.keywords or "", key=f"edit_kw_{d.id}")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("💾 Save Changes", key=f"save_doc_{d.id}"):
                                d.title = nt.strip()
                                d.keywords = nk.strip()
                                session.query(DocChunk).filter_by(document_id=d.id).update(
                                    {"title": d.title, "keywords": d.keywords}
                                )
                                session.commit()
                                st.success("Saved")
                                st.rerun()
                        with c2:
                            r2_download_button("⬇️ Download", d.file_path, f"{d.title}.pdf", f"mgr_dl_{d.id}")
                        with c3:
                            if st.button("🗑️ Delete", key=f"del_doc_{d.id}"):
                                clear_document_chunks(d.id)
                                clear_document_assets(d.id)
                                session.delete(d)
                                session.commit()
                                st.success("Document deleted from library.")
                                st.rerun()

        with st.expander("🛡️ Safety Documents & Meetings", expanded=False):
            if r2_available():
                st.markdown("#### Upload Safety Document")
                stitle = st.text_input("Safety Document Title", key="saf_up_title")
                skw = st.text_input("Keywords", key="saf_up_kw")
                sfile = st.file_uploader("File", type=["pdf", "pptx", "png", "jpg"], key="saf_up_file")
                if st.button("Upload Safety Document"):
                    if stitle and sfile:
                        key = f"safety/docs/{datetime.now().strftime('%Y%m%d%H%M%S')}_{sfile.name}"
                        if r2_upload(sfile.getvalue(), key, "application/pdf"):
                            session.add(SafetyDocument(
                                title=stitle.strip(),
                                file_path=key,
                                file_type=(sfile.name.split(".")[-1] or "pdf").lower(),
                                uploaded_by=user["id"],
                                keywords=skw.strip(),
                            ))
                            session.commit()
                            st.success("Safety document uploaded permanently!")
                            st.rerun()

                st.markdown("#### Create Safety Meeting")
                mt = st.text_input("Meeting Title", key="meet_title")
                md = st.text_input("Meeting Date", key="meet_date")
                mn = st.text_area("Notes / Agenda", key="meet_notes")
                mf = st.file_uploader("PowerPoint or PDF of the training", type=["pdf", "pptx"], key="meet_file")
                if st.button("Create Safety Meeting", type="primary"):
                    if mt.strip():
                        fpath = ""
                        if mf:
                            key = f"safety/meetings/{datetime.now().strftime('%Y%m%d%H%M%S')}_{mf.name}"
                            if r2_upload(mf.getvalue(), key, "application/pdf"):
                                fpath = key
                            else:
                                st.error("Failed to upload the presentation file.")
                                fpath = None
                        if fpath is not None:
                            session.add(SafetyMeeting(
                                title=mt.strip(),
                                meeting_date=md.strip(),
                                file_path=fpath,
                                notes=mn.strip(),
                                created_by=user["id"],
                            ))
                            session.commit()
                            st.success("Safety meeting created. Technicians can now acknowledge it.")
                            st.rerun()
                    else:
                        st.error("Title is required.")
            else:
                st.error("R2 storage is not configured.")

        with st.expander("🔗 Re-link files already in R2 (no re-upload)", expanded=False):
            st.caption(
                "Your PDFs may still be in cloud storage even if the app library shows 0. "
                "List them here, set title/category/keywords once, and register - no upload from your PC."
            )
            if not r2_available():
                st.error("R2 storage is not configured.")
            else:
                folder = st.selectbox(
                    "Folder to scan",
                    ["documents/", "certificates/", "safety/docs/", "safety/meetings/"],
                    key="r2_folder",
                )
                if st.button("List files in R2", key="r2_list_btn"):
                    with st.spinner("Listing storage..."):
                        keys, err = r2_list_keys(folder, max_keys=300)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["r2_keys"] = keys
                keys = st.session_state.get("r2_keys") or []
                if keys:
                    unlinked = [k for k in keys if not r2_key_already_registered(k)]
                    linked_n = len(keys) - len(unlinked)
                    st.write(f"**{len(keys)}** file(s) · **{len(unlinked)}** not in library · **{linked_n}** already linked")
                    cats = session.query(Category).order_by(Category.name).all()
                    techs = session.query(User).filter_by(is_active=True).order_by(User.full_name).all()
                    show = unlinked[:300]
                    for i, key in enumerate(show):
                        with st.container(border=True):
                            st.caption(key)
                            default_title = guess_title_from_key(key)
                            if key.startswith("documents/"):
                                if not cats:
                                    st.warning("Create at least one category before linking manuals.")
                                    continue
                                t = st.text_input("Title", value=default_title, key=f"r2t_{i}")
                                cat_name = st.selectbox("Category", [c.name for c in cats], key=f"r2c_{i}")
                                kw = st.text_input("Keywords", key=f"r2k_{i}", placeholder="Schwintek, model numbers…")
                                import library_category_audit as _cataudit

                                _w = _cataudit.upload_category_warning(t or default_title, cat_name)
                                _ok = True
                                if _w:
                                    st.warning(f"Category check: {_w}")
                                    _ok = st.checkbox(f"Link under '{cat_name}' anyway", key=f"r2cc_{i}")
                                if st.button("Link into library + index", key=f"r2l_{i}", disabled=not _ok):
                                    cat = session.query(Category).filter_by(name=cat_name).first()
                                    doc = Document(
                                        category_id=cat.id,
                                        title=t.strip() or default_title,
                                        file_path=key,
                                        file_type="pdf" if key.lower().endswith(".pdf") else "bin",
                                        uploaded_by=user["id"],
                                        keywords=kw.strip(),
                                    )
                                    session.add(doc)
                                    session.commit()
                                    if doc.file_type == "pdf":
                                        ok, note = index_document_from_r2(doc)
                                        st.success(f"Linked and indexed: {note}" if ok else f"Linked, index issue: {note}")
                                    else:
                                        st.success("Linked (non-PDF, not indexed).")
                                    st.rerun()
                            elif key.startswith("certificates/"):
                                t = st.text_input("Certificate title", value=default_title, key=f"r2ct_{i}")
                                tech_names = [u.full_name for u in techs]
                                tn = st.selectbox("Assign to tech", tech_names, key=f"r2cu_{i}")
                                if st.button("Link certificate", key=f"r2cl_{i}"):
                                    tech = next(u for u in techs if u.full_name == tn)
                                    session.add(Certificate(
                                        user_id=tech.id,
                                        title=t.strip() or default_title,
                                        file_path=key,
                                        uploaded_by=user["id"],
                                    ))
                                    session.commit()
                                    st.success("Certificate linked.")
                                    st.rerun()
                            elif key.startswith("safety/"):
                                t = st.text_input("Safety doc / meeting title", value=default_title, key=f"r2st_{i}")
                                if st.button("Link as safety document", key=f"r2sl_{i}"):
                                    session.add(SafetyDocument(
                                        title=t.strip() or default_title,
                                        file_path=key,
                                        uploaded_by=user["id"],
                                    ))
                                    session.commit()
                                    st.success("Safety document linked.")
                                    st.rerun()
                            else:
                                st.caption("Unknown folder - open documents/ certificates/ or safety/ for guided linking.")
                    if len(unlinked) > 40:
                        st.info(f"Showing first 300 of {len(unlinked)} unlinked files. Link some, then list again.")
                    if not unlinked:
                        st.success("All listed files are already linked in the database.")

        with st.expander("📦 Export library catalog (titles & keywords)", expanded=False):
            st.caption(
                "Download a JSON list of every manual title, keywords, category, and R2 path. "
                "Keep this with your DB backup - it is the naming work."
            )
            if session.query(Document).count() == 0:
                st.info("No documents in the database to export yet.")
            else:
                catalog = export_library_catalog()
                st.download_button(
                    "⬇️ Download library_catalog.json",
                    catalog,
                    file_name=f"techtrack_library_catalog_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    type="primary",
                )

        with st.expander("🗂️ Library category audit (dry run first)", expanded=False):
            import library_category_audit as _cataudit

            _cataudit.render_manager_panel(
                st,
                raw_connection=lambda: engine.raw_connection(),
                backup_db=lambda: maybe_backup_db_to_r2(force=True),
            )
        with st.expander("💾 Database Backup & Restore", expanded=True):
            last_ok = st.session_state.get("_db_backup_ok")
            last_n = st.session_state.get("_db_backup_docs")
            if st.session_state.get("_db_restored_from_r2"):
                st.success(
                    f"Restored library from cloud backup "
                    f"({st.session_state.get('_db_restored_docs') or '?'} documents)."
                )
            if last_ok:
                st.info(f"Last automatic cloud save: **{last_ok}** · {last_n or '?'} documents")
            else:
                st.caption("Automatic cloud save runs after real library / job / chat changes.")
            if st.button("Save to cloud now", type="primary", key="force_r2_db"):
                ok, note = maybe_backup_db_to_r2(force=True)
                if ok:
                    st.success(note)
                else:
                    st.warning(note)
            c1, c2 = st.columns(2)
            with c1:
                if Path(DB_PATH).exists():
                    st.download_button(
                        "⬇️ Download Current Database",
                        data=db_snapshot_bytes,   # copied only on click, not on every render
                        file_name=f"techtrack_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                        mime="application/octet-stream",
                        type="primary",
                        on_click="ignore",
                        key="db_download",
                    )
            with c2:
                up_db = st.file_uploader("Upload .db backup to restore", type=["db"], key="restore_db")
                if up_db and st.button("Restore Database"):
                    why = restore_db_from_bytes(bytes(up_db.getbuffer()))
                    if why:
                        st.error(f"Not restored: {why}")
                    else:
                        st.session_state["_db_restore_note"] = "Database restored. Press Save to cloud now to keep it."
                        st.rerun()
                if st.session_state.get("_db_restore_note"):
                    st.success(st.session_state.pop("_db_restore_note"))

        with st.expander("📜 All Team Certificates"):
            all_certs = session.query(Certificate).order_by(Certificate.created_date.desc()).all()
            for cert in all_certs:
                u = session.query(User).get(cert.user_id)
                st.write(f"**{cert.title}** - {u.full_name if u else 'Unknown'} ({cert.issuer or '-'})")

maybe_backup_db_to_r2(force=False)
st.sidebar.caption(f"{APP_VERSION} • Tacoma RV Center • Open library coach • Auto DB backup")
