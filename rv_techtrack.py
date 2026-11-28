"""
RV TechTrack v4.20.11
- v4.20.11: Audit fixes, no product change (Chase 2026-11-28 t1741u). Calls Grok still asks for on the last (tools off) round are not run, so a page Grok never saw is not counted as opened or cited; a crash in the app's picture-page lookup or in a library tool prints a GD_FALLBACK line and lands in the turn log; the app's own failed-turn line stays in the chat but is no longer sent to Grok as if Grok said it; the turn log is published after the reply-findings and cited-ledger steps so their fallbacks land in the same turn; the never-filled notes_next field is deleted; the state format now says what the code does (a left-out field keeps its value, except cited); stale comments and README fixed; an order-dependent test fixed.
- v4.20.10: Request order for xAI's prompt cache (Chase 2026-11-28 t1732u). Grok gets the same text; the order is primer, pages read, history, the tech's new message, then the rest of the job context (unit, lookups, state, summary) last; each job sends a prompt_cache_key; the GD turn log shows tokens_cached and cached_share.
- v4.20.9: Code cleanup and real errors (Chase 2026-11-28 t1727u / t1729u; audit 2026-11-28). (1) New chat and Open clear the whole GD job record (gd_state.clear_job_session): no cause, closed flag, access answer, cited pages or found manuals carry into the next job. (2) The wrap-up and the access question come only at a real end of job: the new Diagnosis complete / Repair complete buttons, Grok's repair.verified or closed (not done alone), or a plain close statement from the tech; questions, 'not working now' and conditional phrases never trigger it, and the next message is taken as the access answer only when the app asked and the reply answers it. The old substring phrase triggers are deleted. (3) A failed GD turn names its cause to the tech (took too long / xAI error with status / app bug / no key), always writes a turn log with the error type and a short traceback, and prints GD_ERROR. (4) Every fallback on the GD path (photo read, plate read, story, state block, picture not drawn, page links, page search) prints GD_FALLBACK and lands in that turn's log. (5) The double-send guard holds for the whole turn (6 rounds x 245 s + margin) and the paid photo read runs after the guard. (6) Deleted: legacy_selector.py, rv_techtrackpr4, scripts/picker_sweep.py, the manual pickers (gd_pages pick_manual/fetch_part/entry_pages/toc_pages, search pick_manual/fetch_by_part), the hard procedure trees, gd_official's old web search, the story state field, and every def or constant left with no caller. (7) Guardrails: tests/test_dead_code_guard.py fails on code with no caller; one TT_STARTUP line at start; the model is set in code only (grok-4.3, XAI_MODEL no longer read; the running model is unchanged).
- v4.20.8: Meaning (smart) search off by default (Chase 2026-11-28 t1725u). The page search Grok uses is word-match only; the embedding model and passage vectors are never loaded, so there is no download, no ~300 MB, and nothing to fail. TT_PAGEFINDER_MEANING=on still turns it back on (environment only; the app no longer reads a Streamlit secret for this, so an old "on" secret cannot switch it back). When off or when the model fails, hybrid() is word-match only (no 0.5 blend toward zeros), so a page search with no matching words comes back empty and the v4.20.7 web gate can open. One tagged SMART_SEARCH_OFF line is printed to the Streamlit log at startup or when the state changes (never per query); the GD turn log records MEANING_SEARCH_OFF once per job and usage.meaning is on/off/failed. Manager Tools shows the same state. The index vectors stay in place. No new primer rule.
- v4.20.7: GD library-first in code, temperature, remnant cleanup (Chase 2026-11-28 t1713u; test8). (1) Web gate: the web tools (web_search with image search, open_web_document) are left out of Grok's tool list until a library page has been opened in the job or the library comes back with nothing for the unit (decided from the app's own tool records); on a picture request they also wait until the library was looked at that turn. (2) Picture request: when Grok opens no library page, the app opens the best picture-labelled page of the manuals found for the unit and shows that one page; no library picture = Grok's reply only. (3) Cited is this turn's list only (a state block that leaves it out clears it; it no longer carries over) and only pages opened in the job stay cited; others are dropped and logged CITED_NOT_OPENED. The log-only WEB_BEFORE_LIBRARY_SEARCH trigger is replaced by the gate. (4) The GD answer call runs at temperature 0.7 (was 0.2); reasoning effort unchanged. (5) Retired: the old text/figure picture path (resolve_requested_library_pages and its seed/page parsers, render_on_demand_library_pages, render_library_page_image, ask_auto_show, _stored_figure_matches, step figures, figure_render_honesty_note and its Level-Up/AC/water-heater boilerplate, library_figure_backfill offers_for_turn / gd_figures_under_step and their helpers, the regex picture-ask checks wants_library_page_shown / tech_asked_for_manual_figure (now gd_picture.is_picture_request), reading page numbers out of Grok's reply text, and every old figure helper left with no caller in gd_library_coach, manual_figures and library_figure_backfill); primer lines that contradicted the gate (web photos, several lookups in one round).
- v4.20.6: GD test7b fixes (Chase 2026-11-27 pt1664u). (1) Picture: when the tech asks for a photo or diagram the reply shows the one page that best shows it, picked from the pages Grok opened this turn (gd_picture: the page Grok names for that item, then its cited pages, then the page label and text), drawn the same way as the page images Grok was given (only the page reference is kept in the session, no image bytes); the old figure lookups and the long 'could not load' note are gone from this path ('That page didn't load; tap Open PDF.' + Open PDF only when nothing could be drawn). (2) No <state> block: the pages Grok opened this turn fill cited, so the page buttons and story sources stay. (3) The REPLY FORMAT reminder (same words) is the last item of every model round, after the tool results. (4) Double send: server-side guard (gd_sends) keyed by tech + turn + message + photo, 10-minute TTL; the reply is put in the chat and the database as soon as Grok returns; a kept reply no screen drew is shown on the next run. (5) Meaning search: pagefinder/build_index sets HF_HUB_OFFLINE only in its own main(), so the live app can download the model again.
- v4.20.5: GD test7 fixes (Chase 2026-11-27 t1653u). (1) pagefinder Library.doc_tf (and gd_tools label / stub caches) built whole and published under the lock: two runs on a cold library read a half-built cache, KeyError 'L166', and turn 1 fell to the web. (2) Primer: Grok describes only pages it opened in this job; a contents-page listing is not a read. (3) Primer: before giving a test, reading or picture Grok opens the page that has it, searching the library again (other manuals for the unit) before the web. Rules 2 and 3 approved by Chase. (4) Double-send guard: a repeat Send while Grok is answering waits for and reuses that reply (gd_send_key / gd_wait_for_kept_reply). Web search stays on.
- v4.20.4: Guided Diagnostics library first (Chase 2026-11-27, test6: Grok went straight to the web with the library tools offered). Primer: "Each job starts in the library: a document or page search for the unit comes before any web search; the web is for what the library does not have." and "then, when the library has nothing that fits, goes to the internet". One new rule, approved by Chase.
- v4.20.3: Guided Diagnostics library lookup fix (Chase 2026-11-27, test3): find_documents compared unit types letter for letter, so Grok's "Slide-outs" missed the library category "Slideouts" and every slide-out manual was filtered out (Grok then went to the web). Unit types now ignore spaces, dashes, case and a plural s, as brands already did, and maker / unit-type filters that leave nothing widen (maker kept, then the whole library) instead of returning an empty list. Each turn's context also reminds Grok that the reply ends with the <state> block. Primer: a diagnosis is worked "until a test or measurement shows the fault; what the tech sees points to the next test" (wording only). The published turn log (Manage app GD_TURN line and R2 gd-turn-logs/) also carries the tech's message and Grok's reply, each capped near 8 KB with a cut marker. No new rules.
- v4.20.2: Guided Diagnostics wording (Chase 2026-11-27, test2): the primer no longer says the internet is open at any point or that a cited web address opens the whole document; a good answer is built on (not led by) the maker manual's pages; a fault code table is for reference and for help planning the diagnostic steps, the checks come from the manual's test pages for that part; a walkthrough step is the check to make, the reading to expect, and what each result means. The per-turn tool log also prints to the Manage app logs (GD_TURN ...) and is saved to R2 gd-turn-logs/<date>/. No new rules.
- v4.20.1: Guided Diagnostics sees the library pages it opens (Chase 2026-11-27, test1 Schwintek slide): read_pages also hands Grok each page as a picture, drawn from the library PDF the same way Show page draws it, picture-labelled pages first, up to 6 per read and 12 per turn (logged). Grok's web search can find and show photos (image search and image understanding on). The primer no longer says a page is only text; it says a cited library page shows the tech that exact page while a web address opens the whole document, and that a web photo may be a different model.
- v4.20.0: Go-live package (2026-11-03). Full manual library: 2,848 new docs (Lippert, Furrion, Onan/Truma, InVision; Chase's 10/31 content decisions) plus the 6 Lippert masters split per product. The page-finder index is no longer shipped in git: the build pinned in pagefinder/INDEX_MANIFEST.json is downloaded from R2 at app start (index_fetch.py: stream to disk, size+sha256 check, build_id and fingerprint check, 3 retries, disk cache); while it loads GD says the library is loading, and if it cannot load GD says so plainly (never a silent keyword-only or empty library), with the reason on Manager Tools. Plate-read crash fixed (the read model is applied on the next run before the Model box is drawn). Grok default model grok-4.3. Memory: the passage vectors are memory-mapped and page caches trimmed.
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
import subprocess
import sys
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
_GDC_REQUIRED_REVISION = "v4.20.11"
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


# 2026-11-25 (live crash, WO SW6DE): the Guided Diagnostics stack below is imported with a plain `import` inside the
# functions that use it and carries no MODULE_REVISION, and APP_VERSION has not changed since v4.20.0. On a redeploy
# Streamlit re-executes this file but keeps sys.modules, so the new rv_techtrack.py called the previous gd_story
# (record_access_answer(_rec, msg, history) against the old 2-argument one: TypeError). Each run compares every file's
# content hash with the one last loaded in this process and, when any changed, drops the whole stack from sys.modules so
# the next import executes the files that shipped with this deploy (together, so none keeps an older sibling).
_GD_PLAIN_MODULES = ("gd_state", "gd_pages", "gd_prompt", "gd_official", "gd_tools", "gd_turn", "gd_story",
                     "gd_work_orders", "gd_page_links", "gd_picture", "gd_sends", "gd_errors")


def _drop_changed_gd_modules():
    """Drop the plain-imported GD modules from sys.modules when any of their files changed since they were loaded.
    Returns the names dropped (empty when nothing changed)."""
    import hashlib
    import sys
    import types

    root = Path(__file__).resolve().parent
    with _app_module_lock():
        holder = sys.modules.get("_techtrack_src_stamps")
        if holder is None:
            fresh = types.ModuleType("_techtrack_src_stamps")
            fresh.stamps = {}
            holder = sys.modules.setdefault("_techtrack_src_stamps", fresh)
        stamps = holder.stamps
        current = {}
        for name in _GD_PLAIN_MODULES:
            try:
                current[name] = hashlib.sha256((root / f"{name}.py").read_bytes()).hexdigest()
            except OSError:
                current[name] = ""
        stale = [n for n in _GD_PLAIN_MODULES if n in sys.modules and stamps.get(n) != current[n]]
        dropped = []
        if stale:
            for name in _GD_PLAIN_MODULES:
                if sys.modules.pop(name, None) is not None:
                    dropped.append(name)
        stamps.update(current)
        return dropped


_gdc = _load_gd_library_coach()
# After the loader slice tests exec. APP_VERSION is this deploy's header.
# Rebind the coach after the ordered reload. An earlier pass can bind it
# before manual_figures is current.
_gdc = _reload_stale_app_modules(APP_VERSION)
_drop_changed_gd_modules()
# Import after the reload so this script binds the new function objects.
# Streamlit Cloud does not always start with the repo root on sys.path.
import gd_llm


def _gd_fb(where, why, exc=None, **fields):
    """v4.20.9 ("no silent fallbacks"): a GD place that carries on without something prints a GD_FALLBACK line to the Manage
    app logs and goes into the next GD turn log (gd_errors). Key values are masked; logging never breaks the app."""
    try:
        import gd_errors

        gd_errors.fallback(where, why, exc=exc, secrets=_gd_secret_values(), **fields)
    except Exception as e:   # the logger itself failed: one plain stdout line, then carry on
        print(f"GD_FALLBACK_LOGGER_FAILED {where} {type(e).__name__}", flush=True)


DEFAULT_LIBRARY_CATEGORIES = _gdc.DEFAULT_LIBRARY_CATEGORIES
gd_category_select_options = _gdc.gd_category_select_options
library_category_picker_names = _gdc.library_category_picker_names
groq_vision_model_candidates = _gdc.groq_vision_model_candidates
complete_chat_with_payload_retry = _gdc.complete_chat_with_payload_retry
xai_vision_model_candidates = _gdc.xai_vision_model_candidates

# ---------------- SHOP BRANDING ----------------


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


# ---------------- CLOUD DB SYNC GUARD (2026-11-25) ----------------
# 2026-11-25: the 11/24 library label fix written to R2 was overwritten at 2:06 PM PT by the running app. Restore pulls
# R2 only when the local DB is (nearly) empty, and the backup's "no changes" check lived in per-browser-session
# st.session_state, so the first run of every new session uploaded this server's local file over whatever R2 held,
# including a newer copy written after this server loaded its library. The sidecar below remembers which cloud copy
# (ETag) this local file came from or was last saved as, and the local file's mtime at that moment, across sessions.
DB_CLOUD_STATE = DB_PATH + ".cloud.json"


def _db_cloud_state() -> dict:
    try:
        data = json.loads(Path(DB_CLOUD_STATE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _db_cloud_state_save(etag, mtime) -> None:
    try:
        Path(DB_CLOUD_STATE).write_text(json.dumps({
            "etag": str(etag or "").strip('"'),
            "mtime": float(mtime or 0),
            "at": datetime.now().isoformat(timespec="seconds"),
        }), encoding="utf-8")
    except Exception:
        pass


def _r2_db_etag(client, bucket):
    """ETag of the cloud DB: '' when there is no cloud copy, None when it could not be checked."""
    try:
        return str(client.head_object(Bucket=bucket, Key=R2_DB_KEY).get("ETag") or "").strip('"')
    except Exception as exc:
        code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
        if code in ("404", "NoSuchKey", "NotFound"):
            return ""
        return None


def cloud_db_conflict(known_etag, remote_etag) -> str:
    """'' when this server may upload over the cloud DB, else why not.

    known_etag: the cloud copy this local file was restored from or last saved as ('' = not recorded yet: a server that
    started before this check, or a local run). remote_etag: what R2 holds now ('' = nothing, None = could not check).
    """
    if remote_etag is None:
        return "Could not check the cloud copy, so nothing was overwritten. It will try again on the next save."
    known = str(known_etag or "").strip('"')
    if not remote_etag or not known or known == remote_etag:
        return ""
    return ("Not saved to cloud: the cloud copy changed after this app loaded its library (another save, or a fix "
            "uploaded to the cloud). Saving now would undo that change. Reboot the app from Manage app so it loads the "
            "cloud copy. Anything done here since the last cloud save is only on this server until then.")


# ---------------- LIBRARY LABEL FIXES (2026-11-25) ----------------
# Library label corrections ship with the code (data/label_fixes/<name>.csv: id,field,before,after,evidence) and are
# applied to whatever DB this server has: a fresh restore, an older backup, or a running server's local file. Each
# file runs once per DB (marker row in app_data_migrations). A field is changed only while it still holds the
# recorded `before`; a value already at `after` is counted, and a value someone edited since is kept.
LABEL_FIX_DIR = Path(__file__).resolve().parent / "data" / "label_fixes"
LABEL_FIX_FIELDS = ("title", "clean_title", "brand", "models", "product_line")


def apply_label_fixes(db_path=None, fix_dir=None) -> dict:
    import csv
    import sqlite3

    db_path = db_path or DB_PATH
    fix_dir = Path(fix_dir or LABEL_FIX_DIR)
    out = {"applied": [], "changed": 0, "already": 0, "kept": 0, "missing": 0}
    files = sorted(fix_dir.glob("*.csv")) if fix_dir.is_dir() else []
    if not files or not Path(db_path).exists():
        return out
    con = sqlite3.connect(db_path, timeout=30)
    try:
        tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        if not {"documents", "categories"} <= tables:
            return out
        if not con.execute("select count(*) from documents").fetchone()[0]:
            return out          # empty library (restore not done yet): run later, against the real one
        con.execute("create table if not exists app_data_migrations (name varchar(200) primary key, "
                    "applied_at varchar(40), changed integer, already integer, kept integer, missing integer)")
        con.commit()
        done = {r[0] for r in con.execute("select name from app_data_migrations")}
        chunk_cols = {r[1] for r in con.execute("pragma table_info(doc_chunks)")} if "doc_chunks" in tables else set()
        for path in files:
            name = f"label-fix:{path.stem}"
            if name in done:
                continue
            with path.open(encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            cats = {n: i for n, i in con.execute("select name, id from categories")}
            order_file = path.with_suffix(".categories.txt")
            wanted = [ln.strip() for ln in order_file.read_text(encoding="utf-8").splitlines()] if order_file.exists() else []
            wanted += [r.get("after") or "" for r in rows if r.get("field") == "category"]
            n = {"changed": 0, "already": 0, "kept": 0, "missing": 0}
            try:
                for cat in wanted:
                    if cat and cat not in cats:
                        cats[cat] = con.execute("insert into categories (name) values (?)", (cat,)).lastrowid
                for r in rows:
                    field = (r.get("field") or "").strip()
                    before, after = r.get("before") or "", r.get("after") or ""
                    try:
                        doc_id = int(r.get("id") or "")
                    except ValueError:
                        continue
                    if field == "category":
                        cur = con.execute("select c.name from documents d left join categories c on c.id = d.category_id "
                                          "where d.id = ?", (doc_id,)).fetchone()
                    elif field in LABEL_FIX_FIELDS:
                        cur = con.execute(f"select {field} from documents where id = ?", (doc_id,)).fetchone()
                    else:
                        continue
                    if cur is None:
                        n["missing"] += 1
                        continue
                    value = cur[0] or ""
                    if value == after:
                        n["already"] += 1
                        continue
                    if value != before:
                        n["kept"] += 1          # edited since the fix was made: the newer value wins
                        continue
                    if field == "category":
                        con.execute("update documents set category_id = ? where id = ?", (cats[after], doc_id))
                        if "category_id" in chunk_cols and "document_id" in chunk_cols:
                            con.execute("update doc_chunks set category_id = ? where document_id = ?", (cats[after], doc_id))
                    else:
                        con.execute(f"update documents set {field} = ? where id = ?", (after, doc_id))
                    n["changed"] += 1
                con.execute("insert into app_data_migrations (name, applied_at, changed, already, kept, missing) "
                            "values (?, ?, ?, ?, ?, ?)", (name, datetime.now().isoformat(timespec="seconds"),
                                                          n["changed"], n["already"], n["kept"], n["missing"]))
                con.commit()
            except Exception:
                con.rollback()
                raise
            out["applied"].append(name)
            for k, v in n.items():
                out[k] += v
        return out
    finally:
        con.close()


def maybe_restore_db_from_r2() -> bool:
    """If Streamlit wiped the local DB, pull the last good copy from R2 and remember which cloud copy it was."""
    if not r2_available():
        return False
    local_n = _local_doc_count()
    if local_n >= MIN_DOCS_TO_BACKUP:
        return False
    client = get_r2_client()
    if not client:
        return False
    try:
        obj = client.get_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=R2_DB_KEY)
        data = obj["Body"].read()
        etag = str(obj.get("ETag") or "").strip('"')
    except Exception:
        return False
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
        _db_cloud_state_save(etag, Path(DB_PATH).stat().st_mtime)
        try:
            st.session_state["_db_restored_from_r2"] = True
            st.session_state["_db_restored_docs"] = restored_n
        except Exception:
            pass
        return True
    except Exception:
        return False


def maybe_backup_db_to_r2(force: bool = False):
    """Upload the full SQLite file to R2. Never overwrite a good cloud copy with an empty local DB, and never overwrite
    a cloud copy that changed after this server loaded or last saved its library (cloud_db_conflict)."""
    if not r2_available():
        return False, "Storage not configured"
    local_n = _local_doc_count()
    if local_n < MIN_DOCS_TO_BACKUP:
        return False, "Local library too small to overwrite the cloud backup"
    if not Path(DB_PATH).exists():
        return False, "No local database file"
    now = time.time()
    state = _db_cloud_state()
    try:
        last = float(st.session_state.get("_db_backup_ts") or 0)
        last_mtime = float(st.session_state.get("_db_backup_mtime") or 0)
    except Exception:
        last, last_mtime = 0.0, 0.0
    # The sidecar survives across browser sessions; session_state alone made every new session's first run upload.
    try:
        last_mtime = max(last_mtime, float(state.get("mtime") or 0))
    except Exception:
        pass
    if not force and (now - last) < BACKUP_DEBOUNCE_SEC:
        return False, "Recently saved"
    mtime = Path(DB_PATH).stat().st_mtime
    if not force and last_mtime and mtime <= last_mtime:
        return False, "No database changes"
    client = get_r2_client()
    if not client:
        return False, "Storage not configured"
    bucket = st.secrets["R2_BUCKET_NAME"]
    remote = _r2_db_etag(client, bucket)
    why = cloud_db_conflict(state.get("etag"), remote)
    if why:
        try:
            st.session_state["_db_cloud_conflict"] = why
            st.session_state["_db_backup_ts"] = now      # do not re-check R2 on every rerun
        except Exception:
            pass
        return False, why
    try:
        try:
            if remote:
                client.copy_object(Bucket=bucket, CopySource={"Bucket": bucket, "Key": R2_DB_KEY}, Key=R2_DB_PREV_KEY)
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
        resp = None
        try:
            with open(tmp, "rb") as f:   # streamed from disk, not read whole into RAM (memtest 2026-11-03)
                put = {"Bucket": bucket, "Key": R2_DB_KEY, "Body": f, "ContentType": "application/x-sqlite3"}
                if remote:
                    put["IfMatch"] = '"' + remote + '"'     # R2 refuses (412) if another save landed since the check
                try:
                    resp = client.put_object(**put)
                except Exception as exc:
                    code = str(getattr(exc, "response", {}).get("Error", {}).get("Code", ""))
                    if code in ("412", "PreconditionFailed"):
                        why = cloud_db_conflict(remote, "changed-during-save")
                        try:
                            st.session_state["_db_cloud_conflict"] = why
                        except Exception:
                            pass
                        return False, why
                    if "IfMatch" in put and type(exc).__name__ == "ParamValidationError":   # older boto3: HEAD check only
                        put.pop("IfMatch")
                        f.seek(0)
                        resp = client.put_object(**put)
                    else:
                        raise
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        new_etag = str((resp or {}).get("ETag") or "").strip('"') or (_r2_db_etag(client, bucket) or "")
        _db_cloud_state_save(new_etag, mtime)
        try:
            st.session_state.pop("_db_cloud_conflict", None)
            st.session_state["_db_backup_ts"] = now
            st.session_state["_db_backup_mtime"] = mtime
            st.session_state["_db_backup_ok"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state["_db_backup_docs"] = local_n
        except Exception:
            pass
        return True, f"Saved {local_n} documents to cloud"
    except Exception as e:
        return False, f"Upload failed: {e}"


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
    # llama-4-scout stays off the Groq list (HTTP 404). grok-4.3 accepts the image.
    try:
        raw = gd_llm.complete_chat(
            messages,
            temperature=0.0,
            max_tokens=400,
            secret_fn=_secret,
            models={
                "xai": xai_vision_model_candidates(
                    preferred_vision=_secret("XAI_VISION_MODEL") or "",
                    preferred_chat=gd_llm.DEFAULT_XAI_MODEL,   # v4.20.9: the code is the one source of the model
                ),
                "groq": groq_vision_model_candidates(_secret("GROQ_VISION_MODEL") or ""),
            },
            empty_is_failure=True,
        )
    except Exception as e:
        _gd_fb("plate_read", "the data-plate photo could not be read; the tech types the model", exc=e)
        _gd_publish_turn_log({"event": "plate_read_failed"})
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
        _gd_fb("story_old_writer", "the old story writer could not reach the AI; the tech sees the error text", exc=e)
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
    except Exception as e:
        _gd_fb("render_pdf_page", "a PDF page could not be drawn", exc=e, page=page_num)
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


def _gd_doc_file_path(doc_id) -> str:
    """Storage key of a library doc's PDF (Document.file_path) for a page-finder id L<Document.id>; "" when unknown."""
    m = re.match(r"^L(\d+)$", str(doc_id or "").strip())
    if not m:
        return ""
    try:
        d = session.get(Document, int(m.group(1)))
    except Exception as e:
        _gd_fb("doc_file_path", "library document lookup failed; its page row has no PDF", exc=e, doc_id=str(doc_id))
        return ""
    return (d.file_path or "") if d is not None else ""


def _gd_cited_page_refs(cited) -> list:
    """The cited pages of one GD reply as page-row data (gd_page_links.page_refs): PDF sheet (looked up from the printed
    label when Grok did not open the page), title, storage key. Stored on the chat message; links are built when drawn."""
    if not cited:
        return []
    import gd_page_links

    pages_fn = title_fn = None
    try:
        finder = _gd_page_finder()
        lib = getattr(finder, "lib", None)
        pages_fn = getattr(lib, "pages", None)
        title_fn = finder.doc_title
    except Exception as e:
        _gd_fb("cited_page_refs", "page finder not ready; page buttons built without sheet / title lookup", exc=e)
    try:
        return gd_page_links.page_refs(cited, pages_fn=pages_fn, file_fn=_gd_doc_file_path, title_fn=title_fn)
    except Exception as e:
        _gd_fb("cited_page_refs", "no page buttons for this reply", exc=e)
        return []


def _gd_pdf_in_storage(key: str) -> bool:
    """The cited PDF is in R2 (HEAD, yes/no remembered 10 minutes in gd_page_links; no bytes are cached)."""
    import gd_page_links

    try:
        bucket = st.secrets["R2_BUCKET_NAME"]
    except Exception as e:
        _gd_fb("pdf_in_storage", "R2 bucket not set up; cited PDFs show as not in storage", exc=e)
        return False
    return gd_page_links.object_exists_cached(get_r2_client, bucket, key)


def _gd_sheet_png(doc_id, sheet: int, file_path: str, pdf_cache: dict | None = None):
    """PNG bytes of exactly one library PDF sheet: the page image indexing stored in R2 (library-pages/<id>/p<sheet>-page.png)
    when there is one, else that sheet rendered from the PDF (render_pdf_page_png). Never a bundled kit figure. None when
    neither works. pdf_cache (optional, per turn) keeps a downloaded PDF for the next sheet of the same file."""
    import manual_figures as mf

    m = re.match(r"^L(\d+)$", str(doc_id or "").strip())
    png = None
    if m:
        try:
            import library_figure_backfill as fb

            png = fb.fetch_png(mf.asset_path(int(m.group(1)), int(sheet), "page", "page"), download=r2_download_bytes)
        except Exception as e:
            _gd_fb("sheet_png", "stored page image not read; drawing the page from the PDF", exc=e, doc_id=str(doc_id),
                   sheet=sheet)
            png = None
    if not png or mf.png_is_blank(png):
        local = Path(str(file_path or ""))
        data = None
        if pdf_cache is not None and file_path in pdf_cache:
            data = pdf_cache[file_path]
        elif file_path and local.is_file():
            try:
                data = local.read_bytes()
            except Exception as e:
                _gd_fb("sheet_png", "local PDF not readable; page not drawn", exc=e, doc_id=str(doc_id), sheet=sheet)
                data = None
        elif file_path:
            data = r2_download_bytes(file_path)
        if pdf_cache is not None and file_path and data:
            pdf_cache.clear()          # one PDF at a time: memory stays bounded
            pdf_cache[file_path] = data
        png = render_pdf_page_png(data, int(sheet)) if data else None
    if png and not mf.png_is_blank(png):
        return png
    return None


def _gd_page_image_fn():
    """page_image_fn for gd_turn.run_turn (Chase 2026-11-27, test1): the library page Grok opened, as the same picture the
    tech's "Show page" button draws. A fresh one per turn (its PDF cache lives only for that turn)."""
    pdf_cache: dict = {}
    drawn: set = set()

    def fn(doc_id, sheet):
        png = _gd_sheet_png(doc_id, int(sheet), _gd_doc_file_path(doc_id), pdf_cache)
        if png:
            drawn.add((str(doc_id), int(sheet)))   # v4.20.6: which sheets drew (the tech's picture is the same drawing)
        return png

    fn.drawn = drawn
    return fn


def _render_cited_sheet(doc_id, sheet: int, file_path: str, caption: str) -> bool:
    """Draw exactly the cited PDF sheet (_gd_sheet_png). It never swaps in a bundled kit
    figure, so the tech always sees the page that was cited."""
    png = _gd_sheet_png(doc_id, sheet, file_path)
    if png:
        st.image(png, caption=caption, use_container_width=True)
        return True
    return False


def _render_gd_page_links(pages, key_prefix: str) -> None:
    """One compact row per cited page under a GD reply: 📄 Open PDF (short-lived link, opens at the cited sheet) and
    🖼 Show page (draws the page only when tapped). Nothing when nothing was cited; no expanders."""
    if not pages:
        return
    import gd_page_links

    for i, ref in enumerate(pages[: gd_page_links.MAX_PAGE_LINKS]):
        if not isinstance(ref, dict):
            continue
        label = ref.get("label") or ref.get("title") or "Manual page"
        if ref.get("kind") == "web":
            c1, c2 = st.columns([3, 2])
            c1.caption(f"🌐 {label}")
            if ref.get("url"):
                c2.link_button("🌐 Open page", ref["url"], use_container_width=True)
            continue
        key = ref.get("file_path") or ""
        local = Path(key).is_file() if key else False
        in_storage = bool(key) and (local or _gd_pdf_in_storage(key))
        if not in_storage:
            st.caption(f"📖 {label} — the PDF for this page is not in the shop library storage.")
            continue
        sheet = ref.get("sheet")
        c1, c2, c3 = st.columns([3, 2, 2])
        c1.caption(f"📖 {label}")
        url = ""
        if not local:
            try:
                url = gd_page_links.pdf_link(get_r2_client(), st.secrets["R2_BUCKET_NAME"], key, sheet)
            except Exception as e:
                _gd_fb("page_link", "no Open PDF link for a cited page", exc=e)
                url = ""
        if url:
            c2.link_button("📄 Open PDF", url, use_container_width=True)
        show_key = f"{key_prefix}_show_{i}"
        if sheet:
            def _flip(k=show_key):
                st.session_state[k] = not st.session_state.get(k)

            shown = bool(st.session_state.get(show_key))
            c3.button("✖ Hide page" if shown else "🖼 Show page", key=f"{show_key}_btn", on_click=_flip,
                      use_container_width=True)
            if shown:
                try:
                    ok = _render_cited_sheet(ref.get("doc_id"), int(sheet), key, label)
                except Exception as e:
                    _gd_fb("show_page", "a cited page could not be drawn", exc=e, doc_id=str(ref.get("doc_id")), sheet=sheet)
                    ok = False
                if not ok:
                    st.caption("Couldn't draw that page here. Use Open PDF.")
        else:
            c3.caption("Page not found in the index; the PDF opens at page 1.")


def clear_ask_source_state():
    st.session_state["ask_sources"] = []
    st.session_state.pop("ask_sources_json", None)
    st.session_state.pop("ask_cited_log", None)


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
    st.session_state["gd_help_mode"] = None       # the next job asks again: manual pages or a walkthrough
    st.session_state["ask_model"] = ""
    st.session_state["gd_model_memory"] = ""
    st.session_state["ask_cat"] = "(any)"
    st.session_state["gd_category_memory"] = "(any)"
    st.session_state.pop("ask_plate_cam", None)
    st.session_state.pop("ask_plate_upload", None)
    st.session_state.pop("ask_plate_read_btn", None)
    st.session_state["ask_wo_number"] = ""
    # v4.20.9 (audit H1): the whole job record goes too (cause, closed, access answer, complaint, unit, pages read, web gate,
    # found documents, cited, order_part, ...). Before this, nothing cleared gd_pin_store after v4.19.39.
    import gd_state as _gs
    _gs.clear_job_session(st.session_state)


# ---------------- GD OFFICIAL METHOD (Chase approved 2026-10-16) ----------------
GD_OFFICIAL_METHOD = True
GD_USAGE_LOG = os.environ.get("GD_USAGE_LOG", "")
# Test hooks: replay tests set these to stay offline. None = live xAI call with the library tools + built-in web search.
# _gd_official_chat(messages, max_tokens, effort) -> str is a text-only fake; _gd_official_respond(items, tools, tool_choice)
# -> gd_llm.respond()-shaped dict is a fake that can make tool calls.
_gd_official_chat = None
_gd_official_respond = None
# Grok searches the internet itself with xAI's built-in web_search inside its own call (Chase 2026-10-24); the app-side
# gd_official search is retired from the GD path. open_web_document still fetches a URL Grok found (plain HTTP, free).


_gd_finder = None  # test hook: a gd_pages finder (e.g. StubPageFinder). None = the fresh library's page-finder.
GD_ACCESS_PROMPT = "What did you have to remove or move to get access (for example the fridge pulled out, battery box covers off, panels, ducts, counters, drawers)? And anything else that took extra time, or that the repair itself will need removed? Just list it out, a run-on sentence is fine."
GD_ACCESS_BOX = "Removed or moved for access, extra time, and what the repair will need removed"
GD_ACCESS_SAVE = "Save and write story"
GD_ACCESS_NONE = "Nothing removed, write story"


def _gd_record():
    """The job record (the gd_turn case in gd_pin_store) for this chat; a light one is started when GD has not made one yet
    (offline, or a reopened chat), so the tech's recommendation and access answer always have a place."""
    pin = st.session_state.setdefault("gd_pin_store", {})
    case = pin.get("gd_case")
    cid = st.session_state.get("ask_chat_id")
    if case is None or (cid and st.session_state.get("gd_case_chat_id") not in (None, cid)):
        import gd_state as _gs
        first = next((m.get("content") or "" for m in (st.session_state.get("ask_chat") or [])
                      if (m.get("role") or "") == "user"), "")
        case = {"unit": {"category": "", "model_text": st.session_state.get("gd_model_memory") or ""}, "complaint": first,
                "state": _gs.new_state()}
        pin["gd_case"] = case
        if cid:
            st.session_state["gd_case_chat_id"] = cid
    case.setdefault("state", {})
    return case


def _gd_page_lookup(doc_ref, page):
    """A library page by doc id or title and printed page / sheet, for the story's procedure references."""
    lib = _gd_page_finder().lib
    doc = lib.docs.get(str(doc_ref))
    doc_id = str(doc_ref)
    if not doc:
        for k, d in lib.docs.items():
            if (d.get("title") or "").strip().lower() == str(doc_ref).strip().lower():
                doc, doc_id = d, k
                break
    if not doc:
        return None
    for p in lib.pages(doc_id):
        if str(p.get("printed_page") or "") == str(page) or str(p.get("pdf_sheet")) == str(page):
            return {"doc_id": doc_id, "title": doc.get("title") or "", "doc_number": doc.get("doc_number") or "",
                    "text": p.get("text") or "", "page": str(page), "source": "library"}
    return None


GD_HELP_QUESTION = "How do you want help on this job?"
GD_HELP_OPTIONS = {"📖 Pull up the manual pages": "pages", "🧭 Walk me through the repair": "walkthrough"}
GD_WALK_ME_BUTTON = "🧭 Walk me through it"
GD_WALK_ME_MESSAGE = "I'm stuck. Walk me through it from here."
GD_OFFLINE_LINE = "The AI is offline, so Guided Diagnostics cannot answer. Nothing was guessed."


def _gd_page_finder():
    """The one page-finder behind Guided Diagnostics (the Library tab filters the DB directly). Its index ships in pagefinder/index; the app DB is
    the source of truth for document metadata and for documents added after the index build."""
    global _gd_finder
    if _gd_finder is None:
        import gd_pages

        import index_fetch

        # v4.20.0: the index is the build pinned in pagefinder/INDEX_MANIFEST.json, fetched from R2 and verified
        # (index_fetch). Raises index_fetch.IndexLoading / IndexUnavailable instead of running on a wrong library.
        # v4.20.8: meaning search follows TT_PAGEFINDER_MEANING (default off). Not a Streamlit secret.
        index_dir = index_fetch.ready_dir(get_r2_client, _index_bucket())
        _gd_finder = gd_pages.LibraryPageFinder(index_dir=index_dir, app_db=os.path.abspath(DB_PATH))
    return _gd_finder


def _index_bucket():
    try:
        return st.secrets["R2_BUCKET_NAME"] if r2_configured() else None
    except Exception as e:
        _gd_fb("index_bucket", "R2 bucket name not readable; the library index cannot be fetched from R2", exc=e)
        return None


def _start_index_fetch():
    """Start the background index download at app start (idempotent on every rerun; no-op with TT_PAGEFINDER_DIR)."""
    try:
        import index_fetch

        index_fetch.start(get_r2_client, _index_bucket())
    except Exception as e:
        _gd_fb("index_fetch_start", "the library index download did not start", exc=e)
    try:
        from pagefinder import search as _pf
        if not _pf.MEANING_ON:
            _pf.announce_meaning_state(force=True)
    except Exception as e:
        _gd_fb("smart_search_announce", "the smart-search state line was not printed", exc=e)


_start_index_fetch()


def _git_commit() -> str:
    """The deployed commit (short), or "" when git or the .git folder is not there."""
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=os.path.dirname(os.path.abspath(__file__)),
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception as e:
        _gd_fb("startup_commit", "git commit not read for TT_STARTUP", exc=e)
        return ""


def _git_commit_cheap() -> str:
    """The deployed commit (short) read straight from .git (HEAD, its ref file or packed-refs): no subprocess, so it is cheap
    enough for every Streamlit rerun. "" when it cannot be read (then _git_commit's subprocess is the fallback)."""
    try:
        g = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".git")
        with open(os.path.join(g, "HEAD"), encoding="utf-8") as fh:
            head = fh.read().strip()
        if not head.startswith("ref:"):
            return head[:7]
        ref = head[4:].strip()
        rp = os.path.join(g, *ref.split("/"))
        if os.path.exists(rp):
            with open(rp, encoding="utf-8") as fh:
                return fh.read().strip()[:7]
        with open(os.path.join(g, "packed-refs"), encoding="utf-8") as fh:
            for ln in fh:
                parts = ln.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0][:7]
    except OSError:
        return ""
    return ""


def _print_startup_line():
    """v4.20.9 (Chase t1727u): the TT_STARTUP line on stdout (Manage app logs): version, commit, model, GD temperature,
    reasoning effort, smart search, web gate, round limit. Streamlit re-runs this script on every click, so the last
    printed version+commit lives in sys.modules. v4.20.12: keyed on version+commit, not once per process, so a hot reload
    after a push (Streamlit "Updated app!") prints one new line with the new version and commit; a plain rerun prints none."""
    holder = "_techtrack_startup_printed"
    commit = _git_commit_cheap() or _git_commit()
    key = f"{APP_VERSION}@{commit or 'unknown'}"
    mod = sys.modules.get(holder)
    if mod is not None and getattr(mod, "key", None) == key:
        return
    import types
    import gd_errors
    import gd_turn

    mod = types.ModuleType(holder)
    mod.key = key
    sys.modules[holder] = mod
    gd_errors.emit(gd_errors.TAG_STARTUP, **gd_turn.startup_fields(APP_VERSION, commit))


_print_startup_line()


GD_TURN_LOG_TEXT_CAP = 8192   # bytes per text field in the published turn log (tech message, Grok reply)


def _gd_log_text(text, cap=GD_TURN_LOG_TEXT_CAP):
    """Text for the turn log, cut at about `cap` UTF-8 bytes with a marker saying where and how much was cut."""
    text = text if isinstance(text, str) else ("" if text is None else str(text))
    raw = text.encode("utf-8")
    if len(raw) <= cap:
        return text
    kept = raw[:cap].decode("utf-8", errors="ignore")
    return kept + f" [...cut here: {len(kept)} of {len(text)} characters kept]"


def _gd_publish_turn_log(log, user_msg=None, reply=None):
    """2026-11-27 (Chase, "find its tool log"): the per-turn tool log (gd_turn's record: tool calls, pages opened, web
    searches, page images, tokens, cost) also goes to the Manage app logs (stdout) and to R2 gd-turn-logs/<date>/, so a
    test job can be read after the fact. Since v4.20.3 (Chase "yes", 2026-11-27) it also carries the tech's message and
    Grok's reply for the turn (tech_message / reply, each capped near 8 KB with a cut marker). No secrets. A failure here
    never touches the turn."""
    import gd_errors

    if not log:
        log = {"event": "turn_without_log"}
    try:
        log = dict(log)
        fb = gd_errors.take_fallbacks()   # v4.20.9: every quiet fallback of this run goes into the turn log
        if fb:
            log["fallbacks"] = fb
        if user_msg is not None:
            log["tech_message"] = _gd_log_text(user_msg)
        if reply is not None:
            log["reply"] = _gd_log_text(reply)
        line = json.dumps(log, default=str)
    except Exception as e:
        gd_errors.emit(gd_errors.TAG_ERROR, **gd_errors.error_record(e, "turn_log_json"))
        return
    try:
        print("GD_TURN " + line, flush=True)
    except Exception:   # stdout closed; the R2 copy below still goes
        pass
    try:
        now = time.gmtime()
        try:
            chat = st.session_state.get("ask_chat_id") or "new"
        except Exception:   # no Streamlit session (offline / tests): the key just says "new"
            chat = "new"
        key = (f"gd-turn-logs/{time.strftime('%Y-%m-%d', now)}/"
               f"{time.strftime('%Y%m%dT%H%M%SZ', now)}-{int(time.time() * 1000) % 1000:03d}-{chat}.json")
        if not r2_put_bytes(line.encode("utf-8"), key, "application/json"):
            gd_errors.emit(gd_errors.TAG_FALLBACK, where="turn_log_r2", why="turn log not saved to R2 (R2 not set up or "
                           "the upload failed); the GD_TURN line above is the only copy")
    except Exception as e:
        gd_errors.emit(gd_errors.TAG_ERROR, **gd_errors.error_record(e, "turn_log_r2", secrets=_gd_secret_values()))


def _gd_is_picture_request(msg) -> bool:
    """The tech asked to see a photo, picture or diagram (v4.20.7: the one check, gd_picture.is_picture_request; the old
    coach / manual_figures regex detectors are retired)."""
    import gd_picture

    return gd_picture.is_picture_request(msg)


def _gd_official_reply(user_msg, category_name, model_text, history, pin_store=None, help_mode=None, picture_request=False):
    """One GD turn on the fresh core (gd_turn). The brain decides; this wrapper only wires the app to it."""
    import gd_turn

    # 2026-11-25 (Chase, "love it build it"): the pages Grok cited this turn are kept for the clickable page row under the
    # reply (gd_page_links). Cleared first so an offline or failed turn never shows the previous turn's pages.
    st.session_state.pop("gd_last_cited", None)

    if pin_store is None:
        try:
            pin_store = st.session_state.setdefault("gd_pin_store", {})
        except Exception as e:
            _gd_fb("pin_store", "no session store; this turn's job record is not kept", exc=e)
            pin_store = {}

    def respond_fn(items, tools, tool_choice=None):
        if _gd_official_respond is not None:
            return _gd_official_respond(items, tools, tool_choice)
        if _gd_official_chat is not None:
            return _gd_official_chat(items, None, None)
        return gd_llm.respond(items, tools, tool_choice=tool_choice, secret_fn=_secret,
                              cache_key=pin_store.get(gd_turn.CACHE_KEY))   # v4.20.10: one cache key per job

    import gd_errors
    import index_fetch

    try:
        finder = _gd_page_finder()
    except index_fetch.IndexLoading:
        gd_errors.fallback("page_finder", "library index still loading; the turn did not run")
        _gd_publish_turn_log({"event": "turn_not_run", "why": "index_loading"}, user_msg, index_fetch.LOADING_LINE)
        return index_fetch.LOADING_LINE
    except Exception as e:
        # Not "could not reach the AI": the manual library itself is not ready (named reason on the manager page).
        rec = gd_errors.error_record(e, "page_finder", secrets=_gd_secret_values())
        gd_errors.emit(gd_errors.TAG_ERROR, **rec)
        _gd_publish_turn_log({"event": "turn_failed", "error": rec}, user_msg, index_fetch.UNAVAILABLE_LINE)
        return index_fetch.UNAVAILABLE_LINE
    try:
        # 2026-11-27 (test1): Grok sees the library pages it opens, not only their text. A failure here costs the images,
        # never the turn (v4.20.9: and it is logged).
        page_image_fn = _gd_page_image_fn()
    except Exception as e:
        gd_errors.fallback("page_images", "page pictures off for this turn; Grok gets page text only", exc=e,
                           secrets=_gd_secret_values())
        page_image_fn = None
    try:
        result = gd_turn.run_turn(
            user_msg, category_name, model_text, history,
            finder=finder, respond_fn=respond_fn, store=pin_store,
            log_path=GD_USAGE_LOG or None,   # None = gd_turn.DEFAULT_LOG_PATH (GD_TURN_LOG or the temp dir)
            help_mode=help_mode,
            page_image_fn=page_image_fn,
            picture_request=bool(picture_request),   # v4.20.7: web waits for the library on a picture turn
        )
    except Exception as e:
        # v4.20.9 (audit H3): no generic "could not reach the AI". The tech gets the real reason in one plain line
        # (timeout / xAI error with its status code / a bug in the app), stdout gets a GD_ERROR line and the GD turn log
        # (Manage app logs + R2 gd-turn-logs/) gets the failed turn with the error type and a traceback summary.
        rec = gd_errors.error_record(e, "run_turn", secrets=_gd_secret_values())
        line = gd_errors.tech_line(rec["type"], rec["status"], e)
        gd_errors.emit(gd_errors.TAG_ERROR, **rec)
        _gd_publish_turn_log({"event": "turn_failed", "error": rec,
                              "unit": {"category": category_name or "", "model_text": model_text or ""}}, user_msg, line)
        return line
    try:
        # 2026-11-24 (M1066): a reply that confirms a cause or a recommendation puts it in the job record even when the
        # state block did not carry it, so the work order and the warranty story have it.
        import gd_story
        gd_story.record_reply_findings(pin_store.get(gd_turn.STORE_KEY), result.get("reply") or "")
    except Exception as e:
        gd_errors.fallback("reply_findings", "cause / recommendation from the reply not recorded", exc=e)
    for c in result.get("cited") or []:
        try:
            # The warranty story and source ledger are keyed by manual TITLE (parse_cited_pages_from_text), so the
            # cited doc id is turned into its library title here; an unknown id stays as the id.
            record_cited_pages(f"📖 Source: {_gd_page_finder().doc_title(c.get('doc_id'))} - page {c.get('page')}")
        except Exception as e:
            gd_errors.fallback("cited_ledger", "a cited page was left out of the source ledger", exc=e,
                               doc_id=str(c.get("doc_id")), page=str(c.get("page")))
    # v4.20.11: published after the reply-findings and cited-ledger steps, so their fallbacks land in THIS turn's log
    _gd_publish_turn_log(result.get("log"), user_msg, result.get("reply"))   # Manage app logs + R2 gd-turn-logs/
    st.session_state["gd_last_cited"] = list(result.get("cited") or [])
    st.session_state["gd_last_turn_pages"] = list(result.get("turn_pages") or [])   # v4.20.6: for the tech's picture
    st.session_state["gd_last_drawn"] = list(getattr(page_image_fn, "drawn", None) or ())   # (doc_id, sheet) keys only
    return result["reply"]


def gd_send_key(chat_id, turns, msg, photo_len=0):
    """One GD send: the chat, how many turns came before it, the message and the photo size (v4.20.5 double-send guard)."""
    import hashlib
    raw = f"{chat_id}|{int(turns)}|{(msg or '').strip()}|{int(photo_len or 0)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _gd_secret_values():
    """The key values to mask in error text (never printed themselves)."""
    out = []
    for name in ("XAI_API_KEY", "GROQ_API_KEY", "R2_SECRET_ACCESS_KEY", "R2_ACCESS_KEY_ID"):
        try:
            v = _secret(name)
        except Exception:   # a missing secret is simply nothing to mask
            v = ""
        if v:
            out.append(v)
    return out


def _gd_reply_is_failure(reply) -> bool:
    """The turn did not happen (AI offline, an error line from gd_errors, library loading or unavailable): never kept for
    reuse."""
    import gd_errors
    if gd_errors.is_error_line(reply):
        return True
    lines = {GD_OFFLINE_LINE}
    try:
        import index_fetch

        lines |= {index_fetch.LOADING_LINE, index_fetch.UNAVAILABLE_LINE}
    except Exception as e:
        _gd_fb("reply_is_failure", "index_fetch lines not loaded for the failure check", exc=e)
    return (reply or "").strip() in {x.strip() for x in lines if x}


def _gd_case_copy():
    """A copy of this chat's job record (gd_turn case) to keep with a send on the server."""
    import copy
    try:
        return copy.deepcopy((st.session_state.get("gd_pin_store") or {}).get("gd_case"))
    except Exception as e:
        _gd_fb("case_copy", "the job record was not kept with the send (a reload starts without it)", exc=e)
        return None


def _gd_restore_case(entry):
    """A reply reused in a fresh session (a reload) brings its job record along when this session has none."""
    case = (entry or {}).get("case")
    pin = st.session_state.setdefault("gd_pin_store", {})
    if case is not None and pin.get("gd_case") is None:
        import copy
        pin["gd_case"] = copy.deepcopy(case)


def _gd_turn_picture(msg, reply, entry):
    """The one page shown when the tech asked for a picture: gd_picture picks it from the library pages opened this turn
    (Grok's reads, or the picture page the app opened when Grok opened none; gd_turn.app_open_picture_page). Only the page
    reference is stored on the reply (no PNG bytes in the session, see TestNoPngCache); _render_gd_picture draws it.
    None when no library page was opened this turn (no library picture: nothing is drawn and no note is shown)."""
    import gd_picture

    pages = list((entry or {}).get("turn_pages") or [])
    try:
        pick = gd_picture.pick_picture_page(msg, pages, list((entry or {}).get("cited") or []))
    except Exception as e:
        _gd_fb("picture_pick", "the asked-for picture was not picked; no picture shown", exc=e)
        pick = None
    if pick is None:
        return None
    get = (lambda k: pick.get(k)) if isinstance(pick, dict) else (lambda k: getattr(pick, k, None))
    doc_id, sheet = str(get("doc_id") or ""), int(get("sheet") or 0)
    title, page = get("title") or "", get("page") or sheet
    label = f"{title} — page {page}" if title else f"page {page}"
    ref = {"doc_id": doc_id, "sheet": sheet, "file_path": _gd_doc_file_path(doc_id), "label": label, "title": title,
           "page": page}
    drawn = (doc_id, sheet) in set((entry or {}).get("drawn_keys") or ())
    return {"ref": ref, "label": label, "drawn_for_grok": drawn}


def _render_gd_picture(pic, key_prefix: str) -> None:
    """The picture stored on a GD reply: that one PDF sheet (_render_cited_sheet, the drawing Grok was given); when it cannot
    be drawn, one plain line and an Open PDF button."""
    if not isinstance(pic, dict):
        return
    ref = pic.get("ref") or {}
    if ref.get("sheet") and ref.get("doc_id"):
        try:
            if _render_cited_sheet(ref["doc_id"], int(ref["sheet"]), ref.get("file_path") or "", pic.get("label") or ""):
                return
        except Exception as e:
            _gd_fb("picture_draw", "the picture page was not drawn; the tech gets the fail note and Open PDF", exc=e)
    import gd_picture

    st.caption(gd_picture.FAIL_NOTE)
    url = ""
    if ref.get("file_path"):
        try:
            import gd_page_links

            url = gd_page_links.pdf_link(get_r2_client(), st.secrets["R2_BUCKET_NAME"], ref["file_path"], ref.get("sheet"))
        except Exception as e:
            _gd_fb("picture_link", "no Open PDF link under the picture", exc=e)
            url = ""
    if url:
        st.link_button("📄 Open PDF", url, use_container_width=False)


def _gd_commit_send(entry, user_id, persist=True, story=True):
    """Put one finished send in the chat: the job record's findings and wrap-up (story), the user line and the reply (with
    its cited pages and, when asked, its picture) in this session's chat, and, when persist, the saved chat in the
    database. Draws nothing, so a rerun cannot stop it halfway. A send already in this session's chat is left alone."""
    import gd_step_photo as _photos
    import gd_story as _story

    history = list(st.session_state.get("ask_chat") or [])
    key = entry.get("key")
    if key and any(isinstance(m, dict) and m.get("send_key") == key for m in history):
        return history
    msg = entry.get("msg") or ""
    reply = entry.get("reply") or ""
    if persist and story:
        # 2026-11-24 (Chase, WO 156231): the tech's stated recommendation goes into the record, and when the job just
        # reached its end (diag complete / repair complete) GD logs it and asks what had to come off for access.
        _rec = _gd_record()
        _story.record_tech_findings(_rec, msg)
        _kind = _story.wrapup_due(_rec, msg)
        if _kind:
            _rec["state"]["access_asked"] = True
            _rec["state"]["wrapup"] = _kind
            # GD-4 (11/24): the access question comes first; a story GD wrote in this reply is cut off (the story
            # comes from the Write warranty story button)
            reply = _story.wrapup_reply(reply, _kind)
    stored_msg = entry.get("stored_msg") or _photos.history_user_text(
        msg, bool(entry.get("photo")), entry.get("photo_review"), asked=entry.get("asked") or "")
    picture = _gd_turn_picture(msg, reply, entry) if entry.get("asked_image") and not _gd_reply_is_failure(reply) else None
    history.append({"role": "user", "content": stored_msg})
    history.append({
        "role": "assistant",
        "content": reply,
        "pages": _gd_cited_page_refs(entry.get("cited")),
        "picture": picture,
        "send_key": key,
    })
    st.session_state["ask_chat"] = history
    if persist:
        st.session_state["ask_chat_id"] = persist_ask_turn(
            user_id,
            st.session_state.get("ask_chat_id"),
            entry.get("category") or "",
            entry.get("model") or "",
            stored_msg,
            reply,
        )
        st.session_state["gd_case_chat_id"] = st.session_state["ask_chat_id"]
        save_gd_work_order(user_id, only_if_closed_or_saved=True,
                           wo_number=st.session_state.get("ask_wo_number") or "")
    elif entry.get("chat_id") and not st.session_state.get("ask_chat_id"):
        st.session_state["ask_chat_id"] = entry["chat_id"]
        st.session_state["gd_case_chat_id"] = entry["chat_id"]
    if key:
        import gd_sends
        gd_sends.store().update(user_id, key, reply=reply, stored_msg=stored_msg,
                                chat_id=st.session_state.get("ask_chat_id"))
    return history


GD_CLOSE_DIAG_BUTTON = "✅ Diagnosis complete"
GD_CLOSE_REPAIR_BUTTON = "✅ Repair complete"


def _gd_close_job(kind, user_id, category="", model=""):
    """The tech's close button (v4.20.9, audit H2): log the job as diag / repair complete and ask the access question, with
    no AI call. False when the access question was already asked or answered for this job."""
    import gd_story as _story

    rec = _gd_record()
    if _story.wrapup_due(rec, "", close_action=kind) != kind:
        return False
    rec["state"]["access_asked"] = True
    rec["state"]["wrapup"] = kind
    said = "Repair complete." if kind == "repair" else "Diagnosis complete."
    _gd_commit_send({"key": None, "msg": said, "stored_msg": said, "reply": _story.access_question(kind),
                     "cited": [], "category": category, "model": model},
                    user_id, story=False)
    return True


def _gd_show_unseen_replies(user_id):
    """v4.20.6 (1c): a reply kept on the server that no screen has drawn (its run was stopped, or the page reloaded) goes
    into this chat when it belongs here: same saved chat, or this session is at the same turn of a fresh chat."""
    import gd_sends

    store = gd_sends.store()
    for e in store.unseen(user_id):
        hist = st.session_state.get("ask_chat") or []
        if any(isinstance(m, dict) and m.get("send_key") == e.get("key") for m in hist):
            continue
        cid = st.session_state.get("ask_chat_id")
        if e.get("turns") != len(hist) or cid not in (None, e.get("chat_id")):
            continue
        _gd_restore_case(e)
        _gd_commit_send(e, user_id, persist=store.take_commit(user_id, e.get("key")))


def _gd_mark_seen(user_id, history):
    """The replies this run drew are no longer waiting to be shown."""
    try:
        import gd_sends

        store = gd_sends.store()
        for m in history or []:
            if isinstance(m, dict) and m.get("send_key"):
                store.mark_seen(user_id, m["send_key"])
    except Exception as e:
        _gd_fb("mark_seen", "kept replies not marked as shown; one may be drawn again", exc=e)


def guided_diagnostics_reply(
    user_msg: str,
    category_name: str,
    model_text: str,
    history: list,
    photo: tuple | None = None,
    photo_review: dict | None = None,
    pin_store: dict | None = None,
    help_mode: str | None = None,
    picture_request: bool | None = None,
):
    """Guided Diagnostics on the fresh core. Returns the reply text (v4.20.9: the old flow slot and the ignored
    gate and flow arguments of the hard trees are deleted).
    A step photo is read by the vision model and its reading is added to the tech's message, marked as such.
    """
    if not ai_available():
        import gd_errors
        gd_errors.emit(gd_errors.TAG_ERROR, type="no_key", where="ai_available", message="no AI key configured")
        _gd_publish_turn_log({"event": "turn_not_run", "why": "ai_offline"}, user_msg, GD_OFFLINE_LINE)
        return GD_OFFLINE_LINE
    official_msg = user_msg
    if photo_review is None and photo and photo[0]:
        try:
            import gd_step_photo as _photos
            photo_review = _photos.review_step_photo(photo[0], photo[1] if len(photo) > 1 else "image/jpeg", "", user_msg)
        except Exception as e:
            _gd_fb("photo_read", "the tech's photo was not read; Grok gets the typed text only", exc=e)
            photo_review = None
    sees = (photo_review or {}).get("sees") if isinstance(photo_review, dict) else ""
    if sees:
        official_msg = (user_msg + "\n" if user_msg else "") + f"Label/photo shows: {sees}"
    if picture_request is None:
        picture_request = _gd_is_picture_request(user_msg)   # the tech's own words, not the photo reading added above
    return _gd_official_reply(official_msg, category_name, model_text, history, pin_store, help_mode=help_mode,
                              picture_request=picture_request)


# ---------------- END GUIDED FLOW ENGINE ----------------


# ---------------- ASK TECHTRACK (chat diagnose) ----------------


def ask_chat_to_warranty_story(history: list, category_name: str = "", model_text: str = "") -> str:
    # Rule 10: on the official GD path the story comes from the session's recorded facts only.
    if GD_OFFICIAL_METHOD:
        # 2026-11-24 (Chase, M1066): a real Complaint / Cause / Correction story written from the whole chat; a job not
        # repaired gets the correction as a recommendation. Grok writes it (checked in gd_story); the stored-state
        # template is the fallback. A case left from another chat is not used.
        try:
            import gd_story
            _case = (st.session_state.get("gd_pin_store") or {}).get("gd_case")
            _cid = st.session_state.get("ask_chat_id")
            if not _case or (_cid and st.session_state.get("gd_case_chat_id") not in (None, _cid)):
                _case = {"unit": {"category": category_name or "", "model_text": model_text or ""}, "complaint": "",
                         "state": {}}
            if not (_case.get("complaint") or "").strip() and _cid:
                # a reopened job without its case: the complaint its work order recorded
                _job = session.query(DiagnosticJob).filter_by(ask_chat_id=_cid).first()
                if _job is not None and (_job.concern or "").strip():
                    _case = {**_case, "complaint": _job.concern}
            # 2026-11-24 (Chase, WO 156231): the documents AND the procedure / flowchart the test steps came from, read from
            # the cited pages' own text; no page numbers, no library codes.
            try:
                _refs = gd_story.procedure_references(_case, history, st.session_state.get("ask_cited_log") or [],
                                                      page_lookup=_gd_page_lookup)
            except Exception as e:
                _gd_fb("story_references", "the story has no procedure references", exc=e)
                _refs = []
            _chat = (lambda msgs: ai_chat(msgs, temperature=0.2, max_tokens=3000)) if ai_available() else None
            _story_text = gd_story.write_warranty_story(_case, history, model_text, chat_fn=_chat, references=_refs)
            import gd_errors
            if gd_errors.pending():   # a story fallback (template story, missing references) goes to the GD turn log now
                _gd_publish_turn_log({"event": "story_fallback"})
            return _story_text
        except Exception as e:
            _gd_fb("story", "the GD story writer failed; falling back to the old improve_tech_story writer", exc=e)
            _gd_publish_turn_log({"event": "story_fallback"})
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
try:
    if apply_label_fixes().get("changed"):     # shipped library label corrections (data/label_fixes), once per DB
        session.expire_all()
except Exception:
    pass
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
                # v4.20.9 (audit H1): an opened chat starts from a clean job record (rebuilt from its own chat by
                # _gd_record), never the job that was open before it
                import gd_state as _gs
                _gs.clear_job_session(st.session_state)
                st.session_state["ask_chat_id"] = ch.id
                st.session_state["ask_chat"] = hist
                # v4.20.12 candidate (audit 3): the unit boxes come back with the opened job's own category and model.
                # Before, they kept whatever was typed for the previous job (or nothing after New chat), so the opened
                # job's next turn told Grok the wrong unit and saved that wrong model over the job's own. The widget keys
                # are dropped here (before the widgets are drawn) and _restore_widget refills them from the memory keys.
                st.session_state.pop("ask_cat", None)
                st.session_state.pop("ask_model", None)
                st.session_state["gd_category_memory"] = (ch.category_name or "").strip() or "(any)"
                st.session_state["gd_model_memory"] = (ch.model_text or "").strip()
                # The previous job's manual-pages / walkthrough choice does not carry into the opened job (it is not
                # saved with a chat yet: M8). None = the default walkthrough, same as sending without a pick.
                st.session_state["gd_help_mode"] = None
                # The double-send store is keyed by tech + turn count + words, not by chat: a short reply ("ok", "yes")
                # sent in the opened job at the same turn count as one sent in the job before it (kept up to ~37 min)
                # would reuse THAT job's reply and job record. New chat already clears it; Open now does the same.
                try:
                    import gd_sends
                    gd_sends.store().clear_user(user["id"])
                except Exception as e:
                    _gd_fb("open_chat_sends", "the double-send store was not cleared for the opened chat", exc=e)
                st.session_state["ask_sources"] = []
                st.session_state["ask_cited_log"] = []
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
    _remember_widget("ask_cat", "gd_category_memory")
    _remember_widget("ask_model", "gd_model_memory")
    category_name = "" if ask_cat == "(any)" else ask_cat

    try:
        _gd_show_unseen_replies(user["id"])   # v4.20.6: a reply kept on the server whose run was stopped before drawing it
    except Exception as e:
        _gd_fb("unseen_replies", "a kept reply was not restored into the chat", exc=e)
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
                # 2026-11-25: the pages this reply cited, as a compact clickable row (nothing when none were cited).
                # v4.20.6: the one page that shows what the tech asked a picture of (gd_picture), right under the reply.
                _render_gd_picture(m.get("picture") if isinstance(m, dict) else None, f"gd_pic_{index}")
                _render_gd_page_links((m.get("pages") or []) if isinstance(m, dict) else [], f"gd_pages_{index}")
        _gd_mark_seen(user["id"], history)
    else:
        st.info("Describe the symptom, what you have already checked, or paste an error code.")
    if st.session_state.pop("ask_reset_input", False):
        st.session_state["ask_input"] = ""

    # Up-front choice (Chase 2026-11-24): manual pages or a full walkthrough. Stored in the job state (gd_turn, help_mode)
    # and told to Grok as session context. In pages mode the tech can switch to a walkthrough any time, by the button or by
    # typing that he is stuck; Grok keeps the whole job either way. Sending without a pick works as before (walkthrough).
    if not history:
        _pick = st.radio(GD_HELP_QUESTION, list(GD_HELP_OPTIONS), index=None, key="gd_help_choice", horizontal=True)
        st.session_state["gd_help_mode"] = GD_HELP_OPTIONS.get(_pick) if _pick else None
    elif st.session_state.get("gd_help_mode") == "pages":
        hc1, hc2 = st.columns([2, 1])
        hc1.caption("Help on this job: manual pages. Stuck? Ask any time, or tap the button.")
        if hc2.button(GD_WALK_ME_BUTTON, key="gd_walk_me", use_container_width=True):
            st.session_state["gd_help_mode"] = "walkthrough"
            st.session_state["ask_pending_answer"] = GD_WALK_ME_MESSAGE
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
    if history:
        # v4.20.9 (audit H2): the tech's own close buttons, the structured end-of-job signal (no AI call)
        c1b, c2b = st.columns(2)
        _close = ""
        if c1b.button(GD_CLOSE_DIAG_BUTTON, key="gd_close_diag", use_container_width=True):
            _close = "diag"
        if c2b.button(GD_CLOSE_REPAIR_BUTTON, key="gd_close_repair", use_container_width=True):
            _close = "repair"
        if _close:
            if _gd_close_job(_close, user["id"], category_name, ask_model or ""):
                st.session_state["ask_reset_input"] = True
                st.rerun()
            st.info("The access question was already asked for this job.")
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
        try:
            import gd_sends
            gd_sends.store().clear_user(user["id"])   # a new chat never reuses the last chat's reply
        except Exception as e:
            _gd_fb("new_chat_sends", "the double-send store was not cleared for the new chat", exc=e)
        st.session_state["gd_model_memory"] = ""
        st.session_state["gd_category_memory"] = "(any)"
        st.session_state["gd_help_mode"] = None
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
            asked = ""
            for message in reversed(history or []):
                if (message.get("role") or "") == "assistant" and (message.get("content") or "").strip():
                    asked = message.get("content") or ""
                    break
            import gd_story as _story
            _rst = ((st.session_state.get("gd_pin_store") or {}).get("gd_case") or {}).get("state") or {}
            # v4.20.9 (audit H2): the message is the access answer only when the app's own access question is the last
            # GD reply AND the message plausibly answers it; anything else (a question, "the fan is not working now")
            # goes to Grok
            _access_open = bool(history and _rst.get("access_asked") and not _rst.get("access_answer"))
            _access_turn = _access_open and not photo_bytes and _story.answers_access(msg, history)
            if _access_open and not _access_turn:
                print("GD_ACCESS_NOT_ANSWER " + json.dumps({"why": "not a plausible access answer or the question was not "
                                                            "the last reply", "chars": len(msg)}), flush=True)
            if _access_turn:
                _rec = _gd_record()
                # the tech's answer to the end-of-job access question goes into the job record (no AI call)
                _story.record_access_answer(_rec, msg, history)
                reply = _story.access_logged_reply(_rec)
            _asked_image = _gd_is_picture_request(msg)
            _entry = {"key": None, "msg": msg, "photo": bool(photo_bytes), "photo_review": photo_review, "asked": asked,
                      "category": category_name, "model": ask_model or "", "turns": len(history or []),
                      "asked_image": _asked_image}
            if _access_turn:
                _gd_commit_send({**_entry, "reply": reply, "cited": []}, user["id"], story=False)
            else:
                # v4.20.6 (test7b, Chase go pt1664u): the double-send guard lives on the server (gd_sends), keyed by the
                # tech, the turns before this one, the message and the photo size. A second press, a second tab or a page
                # reload waits for or reuses the first reply instead of asking Grok again, and the reply is put in the chat
                # and the database the moment Grok returns, before anything is drawn (a run stopped by a rerun no longer
                # loses it; the next run shows a reply that was kept but never drawn).
                import gd_sends
                _sends = gd_sends.store()
                _send_user = user["id"]
                _send_key = gd_send_key(f"user:{_send_user}", len(history or []), msg, len(photo_bytes))
                _entry["key"] = _send_key
                with st.spinner("Searching manuals and thinking…"):
                    _status, _kept = _sends.claim(_send_user, _send_key)
                    if _status == "wait":
                        _kept = _sends.wait(_send_user, _send_key)
                if _kept is not None:
                    _gd_restore_case(_kept)
                    _gd_commit_send(_kept, _send_user, persist=_sends.take_commit(_send_user, _send_key))
                else:
                    try:
                        if photo_bytes:
                            # v4.20.9 (audit M6): the paid photo read runs only in the run that holds the send guard, so
                            # a double press never pays for the same photo twice
                            with st.spinner("Reading the photo…"):
                                photo_review = _photos.review_step_photo(photo_bytes, photo_mime, asked, msg)
                            _entry["photo_review"] = photo_review
                        with st.spinner("Searching manuals and thinking…"):
                            st.session_state.pop("gd_last_turn_pages", None)
                            st.session_state.pop("gd_last_drawn", None)
                            reply = guided_diagnostics_reply(
                                msg,
                                category_name,
                                ask_model or "",
                                history,
                                photo_review=photo_review,
                                pin_store=st.session_state.setdefault("gd_pin_store", {}),
                                help_mode=st.session_state.get("gd_help_mode") or None,
                                picture_request=_asked_image,
                            )
                            _done = _sends.finish(
                                _send_user, _send_key, **{k: v for k, v in _entry.items() if k != "key"}, reply=reply,
                                cited=list(st.session_state.pop("gd_last_cited", None) or []),
                                turn_pages=list(st.session_state.pop("gd_last_turn_pages", None) or []),
                                drawn_keys=list(st.session_state.pop("gd_last_drawn", None) or ()),
                                case=_gd_case_copy(),
                                chat_id=st.session_state.get("ask_chat_id"),
                            )
                            _gd_commit_send(_done, _send_user, persist=_sends.take_commit(_send_user, _send_key))
                            if _gd_reply_is_failure(reply):
                                _sends.forget(_send_user, _send_key)   # "send the same message again" must ask again
                    finally:
                        _sends.abandon(_send_user, _send_key)
            st.session_state["ask_photo_gen"] = _photo_gen + 1
            st.session_state["ask_reset_input"] = True
            st.rerun()

    if write_story and history and not _gd_record()["state"].get("access_answer"):
        # 2026-11-24 (Chase): the access / teardown question comes before the story when it was not answered in the chat
        st.session_state["gd_access_prompt"] = True
        write_story = False
    if st.session_state.get("gd_access_prompt") and history:
        with st.container(border=True):
            st.markdown("**Before I write the warranty story**")
            st.caption(GD_ACCESS_PROMPT)
            st.text_area(GD_ACCESS_BOX, key="gd_access_text", height=90)
            a1, a2 = st.columns(2)
            _ans = ""
            if a1.button(GD_ACCESS_SAVE, key="gd_access_save", use_container_width=True):
                _ans = (st.session_state.get("gd_access_text") or "").strip()
                if not _ans:
                    st.warning("List what you removed, or tap Nothing removed.")
            if a2.button(GD_ACCESS_NONE, key="gd_access_none", use_container_width=True):
                _ans = "nothing removed"
            if _ans:
                import gd_story as _story
                _story.record_access_answer(_gd_record(), _ans, history)
                st.session_state.pop("gd_access_prompt", None)
                write_story = True
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
            import index_fetch

            _ix_note = index_fetch.status_note()
            (st.error if index_fetch.STATE.status == "failed" else st.caption)(_ix_note)
        except Exception:
            pass
        try:
            from pagefinder import search as _pf
            _ms, _merr = _pf.meaning_status()
            if _ms == "failed":
                st.error("Smart search: OFF (" + (_merr or "model could not load") + "; using word match only)")
            elif _ms == "off_by_setting":
                st.caption("Smart search: OFF (word match only)")
            else:
                st.caption("Smart search: on")
        except Exception:
            pass

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
            if st.session_state.get("_db_cloud_conflict"):
                st.error(st.session_state["_db_cloud_conflict"])
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
if st.session_state.get("_db_cloud_conflict"):
    st.sidebar.warning("Cloud save paused: the cloud library changed since this app loaded it. Reboot the app from "
                       "Manage app to load it.")
st.sidebar.caption(f"{APP_VERSION} • Tacoma RV Center • Open library coach • Auto DB backup")
