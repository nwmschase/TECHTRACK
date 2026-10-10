"""
Guided Diagnostics — simple open library coach.

Chase product (2026-09-12):
  Bay procedure PDF is the printable plan feature (replaces Diagnostic Jobs as the plan UI).
  GD chat = complaint → shop Document Library coach → questions, figures, mid-chat pivots.
  Hard tree / Yes-No gate quiz must NOT drive GD chat.
  Never re-ask facts the tech already stated.
  Never invent OEM steps. Cite 📖 Source: manual title - page N.
  Air Conditioning rooftop jobs skip OneControl Unity board manuals unless the tech names them.
"""
from __future__ import annotations

import re

# Product path: hard tree is never exclusive GD chat.
HARD_TREE_EXCLUSIVE_CHAT = False
# Bump with the app version. rv_techtrack reloads a cached module whose
# revision is missing or is not this stamp, even when every old name exists.
COACH_REVISION = "v4.19.40"
MODULE_REVISION = COACH_REVISION

# Document Library names. GD chat / Jobs / library pickers and seed_data share this list.
# Match live library labels — do not invent OEM manuals here.
WATER_HEATERS_CATEGORY = "Water Heaters"
RANGE_COOKTOPS_CATEGORY = "Range & Cooktops"
AIR_CONDITIONING_CATEGORY = "Air Conditioning"
REFRIGERATORS_CATEGORY = "Refrigerators"
PLUMBING_TOILETS_CATEGORY = "Plumbing / Toilets"

DEFAULT_LIBRARY_CATEGORIES = (
    REFRIGERATORS_CATEGORY,
    "Furnaces",
    WATER_HEATERS_CATEGORY,
    PLUMBING_TOILETS_CATEGORY,
    RANGE_COOKTOPS_CATEGORY,
    AIR_CONDITIONING_CATEGORY,
    "Slideouts",
    "Leveling",
    "Electrical",
    "ID & Reference",
    "Warranty Forms",
    "Solar",
)


def library_category_picker_names(existing_names=None):
    """Category names for Document Library and Jobs selects (no (any))."""
    names = set(DEFAULT_LIBRARY_CATEGORIES)
    for raw in existing_names or []:
        name = (raw or "").strip()
        if name:
            names.add(name)
    return sorted(names)


def gd_category_select_options(existing_names=None):
    """Guided Diagnostics category select. Water Heaters stays visible at the top."""
    names = library_category_picker_names(existing_names)
    if WATER_HEATERS_CATEGORY in names:
        names = [WATER_HEATERS_CATEGORY] + [
            name for name in names if name != WATER_HEATERS_CATEGORY
        ]
    return ["(any)"] + names

# Groq retired llama-4-scout on 2026-07-17 (404 / no access).
# Current Groq vision: https://console.groq.com/docs/vision
# Plate photos go through gd_llm (xAI grok-4.6 first, then this Groq list).
# Do not put llama-4-scout back on the default list.
DEAD_GROQ_SCOUT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
DEFAULT_GROQ_VISION_MODELS = (
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
)
DEFAULT_XAI_VISION_MODELS = (
    "grok-4.6",
    "grok-2-vision-1212",
)

PATH_COMPLETE_TRAP_RE = re.compile(
    r"this path is complete|start a new chat for another symptom branch",
    re.I,
)

FIGURE_HINTS = (
    "illustration", "illustrations", "figure", "fig.", " fig ",
    "drawing", "diagram", "show me that page", "show that page",
    "show the page", "show page", "show me the page", "show the figure",
    "show the illustration", "associated illustrations", "associated illustration",
    "source page", "that page", "this page", "show me fig",
    "picture of", "pictures", "photo of", "pcb layout",
    "where are they", "where they are", "where is it", "where it is",
    "show me where", "show where", "label the", "labeled",
    "the diagram", "show diagram", "show the drawing", "show the diagram",
    "can i see the page", "can i see the figure", "can i see that page",
    "pull up the page", "display the page", "let me see the figure",
    "let me see the page", "show that figure", "show that diagram",
    "show me the diagram", "show me the drawing", "show me the figure/page",
)

COACH_REQUEST_PHRASES = (
    "go back", "need to test", "test the compressor", "test compressor",
    "go to compressor", "compressor section", "show me",
    "what does", "what is", "what are", "how do i", "how do you",
    "how do we", "clarify", "clarification", "explain", "wait,",
    "instead", "different symptom", "another branch", "another path",
    "change direction", "pivot", "never mind", "hold on",
    "i'm confused", "im confused", "why is", "why do",
    "can you", "could you", "please explain",
    "after the paper", "rather than", "i want to", "let me",
    "new symptom", "different issue", "different test",
    "not that", "wrong path", "other check",
)

# Everyday shop words for tech-facing GD replies and Bay sheets.
# The ban names the jargon once so the model is told not to say it.
SHOP_LANGUAGE_RULE = (
    "SHOP WORDS: Use everyday shop words (wire, plug, terminal, circuit, connector). "
    'Avoid engineering jargon like "channel" or "channels". '
    'Say "output wire", "check the wire", or "check the circuit".'
)

# Longest shop phrases first. Leftover "channel" / "channels" becomes wire / circuit.
_CHANNEL_PHRASE_RE = re.compile(
    r"\bat the soft-touch panel tongue[\s-]+channels?\b"
    r"|\bsoft-touch panel tongue[\s-]+channels?\b"
    r"|\bpanel tongue[\s-]+channels?\b"
    r"|\btongue[\s-]+channels?\b"
    r"|\bstabilizer channels\b"
    r"|\bthat channels?\b"
    r"|\bthis channels?\b"
    r"|\bthe channels\b"
    r"|\bthe channel\b"
    r"|\bchannels\b"
    r"|\bchannel\b",
    re.I,
)
# A 📖 Source line, plus a quoted excerpt on the next line, stays verbatim.
# So does an explicit "OEM source quote:" / "Source quote:" span.
_MARKED_SOURCE_QUOTE_RE = re.compile(
    r"📖[^\n]*\bSource\b[^\n]*(?:\n[ \t]*(?:\"[^\"]*\"|“[^”]*”))?"
    r"|(?:OEM[ \t]+source[ \t]+quote|Source[ \t]+quote)[ \t]*:[ \t]*(?:\"[^\"]*\"|“[^”]*”)",
    re.I,
)


def _match_shop_case(sample: str, replacement: str) -> str:
    if sample.isupper():
        return replacement.upper()
    if sample[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _channel_phrase_replacement(match: re.Match) -> str:
    low = re.sub(r"[\s-]+", " ", match.group(0).lower()).strip()
    if low.startswith("at the soft"):
        repl = "on the tongue jack output wire at the panel"
    elif "panel tongue" in low:
        repl = "tongue jack output wire at the panel"
    elif low.startswith("tongue"):
        repl = "tongue jack output wire"
    elif low == "stabilizer channels":
        repl = "stabilizer circuits"
    elif low.startswith("that"):
        repl = "that wire"
    elif low.startswith("this"):
        repl = "this wire"
    elif low == "the channels":
        repl = "the circuits"
    elif low == "the channel":
        repl = "the wire"
    elif low == "channels":
        repl = "circuits"
    else:
        repl = "wire"
    return _match_shop_case(match.group(0), repl)


def _rewrite_channel_outside_quotes(text: str) -> str:
    return _CHANNEL_PHRASE_RE.sub(_channel_phrase_replacement, text)


def rewrite_shop_channel_words(text: str) -> str:
    """Final tech-facing filter. Rewrites channel/channels outside marked OEM quotes.

    Quoted OEM source snippets stay verbatim only inside a 📖 Source line
    (and a quoted excerpt on the following line) or an explicit Source quote.
    Everywhere else, use output wire / wire / circuit.
    """
    if not text:
        return text or ""
    if not _CHANNEL_PHRASE_RE.search(text):
        return text
    pieces = []
    pos = 0
    for marked in _MARKED_SOURCE_QUOTE_RE.finditer(text):
        pieces.append(_rewrite_channel_outside_quotes(text[pos:marked.start()]))
        pieces.append(marked.group(0))
        pos = marked.end()
    pieces.append(_rewrite_channel_outside_quotes(text[pos:]))
    return "".join(pieces)


_LEAKED_PROMPT_START = re.compile(
    r"^(?:"
    r"you are an open library coach\b"
    r"|open library coach\b"
    r"|product lock\b"
    r"|shop words:"
    r"|rules:"
    r"|manual excerpts\b"
    r"|your previous draft\b"
    r"|category selected:"
    r"|model/system:"
    r"|ground control 343633:"
    r"|dometic b57915 turns on\b"
    r"|furrion fcr .* ice\b"
    r"|dial[- ]off compressor\b"
    r"|bal tongue\b"
    r"|level up manual mode\b"
    r")",
    re.I,
)
# Instruction blocks the coach prepends in front of a real answer.
# A reply that is only this block stays; the echo in front of the answer does not.
_GUARD_ECHO_RE = re.compile(
    r"("
    r"is not a fuse or 12v-continuity tree"
    r"|skip ccd-0008122 fuse \(p\.19\)"
    r"|do not open the 15a fuse / 12v inverter path"
    r"|not a no-power fuse / 12v inverter tree"
    r"|ccd-0008122 ice and moisture\s*(?:→|->)"
    r"|dial/control off with the compressor still running"
    r")",
    re.I,
)


def _paragraph_is_prompt_echo(head: str) -> bool:
    first = head.splitlines()[0].strip() if head else ""
    return bool(first and _LEAKED_PROMPT_START.match(first))


def _paragraph_is_guard_echo(head: str) -> bool:
    return bool(head and _GUARD_ECHO_RE.search(head))


def strip_leaked_prompt(text: str) -> str:
    """Drop a prompt echo or a guard paragraph that landed in front of the answer.

    A tech-facing line that is only "Do not ..." stays. A leading guard is removed
    when a later paragraph is the real answer. The guard stays when it is the
    whole reply.
    """
    raw = (text or "").strip()
    if not raw:
        return text or ""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw) if part.strip()]
    while paragraphs and _paragraph_is_prompt_echo(paragraphs[0]):
        paragraphs.pop(0)
    while len(paragraphs) > 1 and _paragraph_is_guard_echo(paragraphs[0]):
        paragraphs.pop(0)
    cleaned = "\n\n".join(paragraphs).strip()
    return cleaned or raw


OPEN_LIBRARY_COACH_RULE = """
OPEN LIBRARY COACH (product path — not a locked flowchart, not a Jobs WO plan):
- Take the complaint and guide the tech from THIS SHOP's Document Library / service-manual excerpts only.
- Say "the shop Document Library" or "the Furrion (or brand) service manual" — never "the text you uploaded."
- Answer clarifying questions, figure/diagram/illustration requests, and mid-job pivots in THIS chat.
- NEVER say "This path is complete" or tell the tech to start a new chat for another symptom branch.
- NEVER re-ask a fact the tech already stated in this chat (including the latest message). Do not open or close with Heard or Noted. Start with the next check, or with the repair after that check is reported.
- If they already said the cavity light is on and the fridge is not cooling, do NOT ask those again. Do NOT restart at the fuse / no-power path. Follow the cited service-manual section for a powered unit that is not cooling (e.g. inoperable compressor). Do not force Fan Replacement on that not-cooling / compressor path unless THIS turn's excerpt or an already-stated Furrion FCR E2 / 2-flash / Fan Fault Current says so.
- Furrion FCR08/FCR10 E2 / 2-flash / Fan Fault Current is freezer-fan / airflow (CCD-0008122 Error Code — Fan Fault Diagnostics + Fan Replacement). The SM fan on F+/F− is a replaceable part (shop name: freezer evaporator fan). Do not cage that path to rear inverter/control board only. Recommend freezer evaporator fan R&R, and board + fan when readings support both.
- Suburban / gas cooktop burner lights then goes out when a pan is placed: verify the thermocouple / flame-sensor tip is in the flame WITH COOKWARE ON before condemning thermocouple, safety valve, orifice, regulator, or igniter. Cite Suburban Range/Cooktops SM. Do not invent voltages.
- Front stabilizer / PSX1 power works but manual crank/override will not engage with a broken or seized roll pin / override coupler: replace the complete stabilizer jack assembly (not coupler-only). Lippert PSX1 CCD-0007345 override-usage pages are for using the override, not the end fix for a destroyed pin.
- BAL Soft-Touch SS 5.1 electric tongue jack ONLY dead, other stabilizers and panel lights still work: press tongue extend/retract and check for 12V on the tongue jack output wire at the panel, then the local tongue pigtail / panel-to-motor leads. No 12V on the tongue output wire → soft-touch user panel 20300427. 12V present on that wire → repair the tongue pigtail. Do NOT lead with coupler / shear-pin / coupler replacement, and do NOT lead with the fuse / 30A / remote stabilizer harness. Coupler path only if the manual override will not turn or the motor fails a direct-12V prove. Cite INS.STA.001. Do not invent a page number.
- Furrion FCR / Arctic / similar fridge ice, frost, or icing on the rear/back wall (including about half from the top) or moisture in the fridge cavity: follow CCD-0008122 Ice and Moisture → Ice or Moisture in the Fridge (p.36 / Fig.36). Coach order: pattern note → dial max? → gasket → cooling verify → watch/replace. Closing step: if ice or moisture persists after drying and waiting 1 month, replace the unit. Do NOT open No Power / fuse / 12V inverter unless the complaint is no power / dead / won't run / no light. Cite page 36 and Fig. 36 — never a fake "Fuse location" title with no page.
- Furrion Arctic FCR08/FCR10 (FCR10DCGTA-class): temperature dial/control OFF but the compressor still runs or the cavity overcools (won't shut off, runs when Off, freezer frozen solid with control Off). Do NOT open fuse (p.19), 12V continuity (p.20), or diagnostic LED / inverter control voltage (p.18). Leave the dial fully OFF, seat the probe and thermostat wires (Repair §2 p.43), then open flag terminals C (blue) and T (black) with no jumper (tech adaptation; inverse of Intermittent Thermostat Operation p.31 Figs. 24–25). Compressor stops → R&R Spark-Free Thermostat part G 2021128850 (retail C-FCR10DCGTA-007) per p.43–45 Figs. 57–67. Compressor keeps running with C/T open → inverter/harness secondary. Thermostat cites are p.31 and p.43–45 only.
- Furrion FACR* rooftop freeze / ice / frost / condensate / base-pan / suction icing / melt-leak: search and cite existing CCD-0007990 Furrion Rooftop HVAC Troubleshooting & Service Manual and CCD-0008666 (Furrion Chill FACR) — not Dometic-only rooftop books. Do not invent OEM steps. Order on CCD-0007990: the condensation drain and the refrigerant pressures first, then the pan, filter and fan, suction line, and freeze sensor, then rooftop assembly replacement. Do NOT authorize rooftop assembly replacement until refrigerant pressures have been reported. When drain, pan/slope, filter/fan, suction, freeze sensor, thermostat, nozzles/ambient, and refrigerant pressures are reported and the freeze or interior leak remains, the terminal card must authorize rooftop assembly R&R and cite CCD-0007990. That card is an authorization to replace the rooftop assembly, not a procedure dump. If the excerpt has no R&R steps, still authorize once pressures are reported. Never say the library has no R&R steps. Never ask the tech to paste an R&R section. Once this freeze/leak prove is the complaint, do not leave it for compressor no-start, fan-winding continuity, or a DC bus measurement. Do not return a blank card. Do not open fuse or 12V first. Do not stall on searching manuals. Do not loop a drain-only check once those proves are in.
- Coleman-Mach 2111-0001 that ran and then went dead: when board Fan High is dead (tester dark and/or about 0 VAC on the 9-pin black/white Fan High path), a Peacemaker bypass shows the compressor runs while the fan does not rotate and stall current is about 1.9 A, and the fan run capacitor measures about its rated value, authorize R&R of the fan motor and the control board only. Do not authorize the full 2111-0001 assembly. Stop further tests. Cite the 12VDC wall-thermostat rooftop service manual, 1976-536, 1976-603, the Peacemaker manual, and the mechanical-controls manual / 1976-695. Do not invent page numbers.
- Lippert Level Up Manual Mode flashes then dumps to home while Auto Level (or other pad functions) still work: cheap proves first (power / no brownout; Auto works; dump is not sticky Low Voltage / Excess Angle / External Sensor). Then say: The Level Up controller has two network plugs. One has a rubber boot on it — leave that one alone. The other has a cable running to the Firefly / OneControl system — unplug that cable only. Then try Manual Mode again. Manual holds → Firefly USB firmware (GUI+CCM from Settings; Firefly 574-825-4600; USB ≤4 GB) plus interim (front-bay main battery OFF, solar OK, or leave the Firefly cable unplugged with the rubber-boot plug still in). Reconnect the Firefly cable after the prove unless using interim. Manual still dumps → not Firefly; stay Level Up sensor/harness. Do not swap another Level Up controller for Firefly blame. Do not push Firefly USB unless Manual holds with the Firefly cable unplugged. Do not frame it as confirm Manual dump works.
- If they say "go to compressor section" (or any other change of direction), follow that request using cited library pages.
- Cite 📖 Source: [Exact manual title from excerpt] - page [N] when you use a page. Never invent OEM steps or page numbers.
- If the tech asks to see a figure/diagram/page, say TechTrack will display the shop library PDF page below. Do not invent markdown images.
- If they ask for labeled terminals / PCB / inverter board / pinout / wiring: cite a page that actually has Fig./F+/F−/inverter PCB/wiring/housing labels. If the excerpt is Quick Notes / Nominal voltage with no diagram, say so — do not invent pad locations. Try the next figure page, or ask which: wiring / LED D/+ / fan F+ F− / housing labels.
- When recommending the next check (not answering a question), give at most 1-2 concrete tests, then wait. Ask only for facts that are still missing.
"""
OPEN_LIBRARY_COACH_RULE = (
    OPEN_LIBRARY_COACH_RULE.rstrip() + "\n- " + SHOP_LANGUAGE_RULE + "\n"
)

# Board / terminal / PCB figure asks (Chase live: "show me labeled output terminals").
BOARD_FIGURE_ASK_HINTS = (
    "pcb", "inverter board", "board layout", "pinout", "pin-out", "pin out",
    "output terminal", "terminals labeled", "labeled terminal", "terminal label",
    "housing label", "wiring diagram", "inverter pcb", "inverter terminal",
    "fan terminal", "labeled pcb", "label the terminal", "label the board",
    "where are the terminal", "where is the terminal", "f+", "f-", "f–", "f−",
    "d/+", "silkscreen",
)

# Search rewrite: pull figure pages, not Quick Notes / Nominal voltage.
FIGURE_SEARCH_BOOST = (
    "Fig. figure inverter PCB wiring diagram housing labels "
    "F+ F- terminal labels board layout pinout"
)
FIGURE_QUERY_TERMS = (
    "fig", "figure", "inverter", "pcb", "wiring", "diagram",
    "housing", "labels", "terminal", "terminals", "board",
    "layout", "pinout",
)

# CCD-0008122 shop SM pages that actually show board / terminal figures.
# ~11 wiring, ~16–17 Fig. 2–4 inverter + D/+, ~27 Fig. 21 F+/F−, ~45–46 Fig. 68–69 housing.
FURRION_FCR_BOARD_FIGURE_PAGES = (16, 17, 27, 11, 45, 46)
FURRION_FCR_TEXT_ONLY_PAGES = (13,)  # Troubleshooting Instructions / Quick Notes

FIG_CAPTION_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d+", re.I)
F_PLUS_MINUS_RE = re.compile(r"\bf\s*[+\-–−]", re.I)

FIGURE_PAGE_HONESTY = """
FIGURE / TERMINAL PAGE HONESTY:
- If the tech asks for a figure, diagram, labeled terminals, PCB / inverter board layout, or pinout: cite a page whose excerpt actually contains Fig./figure numbers, F+/F−, inverter PCB, wiring diagram, or housing labels.
- If the excerpt is Quick Notes / Nominal voltage / troubleshooting text with NO figure or terminal layout: say that page has no diagram. Do not invent pad locations. Try the next diagram-candidate excerpt, or ask which they need: wiring / LED terminals D/+ / fan F+ F− / housing labels.
- Never describe pad locations from a text-only Quick Notes page.
- If TechTrack cannot render the shop-library figure page, say that. Name the manual title if known. Do not invent a substitute product manual. Do not claim the PDF is missing from the library when the title is on the catalog.
"""

# Lippert Level Up Advantage hydraulic leveling controller (807662 / 25499 / 24999).
# NOT Ground Control electric. NOT OneControl Unity M-Series awning/slide reversing.
LEVEL_UP_PARTS = ("807662", "25499", "24999")
LEVEL_UP_DOC_MARKERS = (
    "ti-005", "ti 005", "ti005",
    "ti-170", "ti 170", "ti170",
    "qr-092", "qr 092", "qr092",
    "qr-059", "qr 059", "qr059",
    "octp",
    "level-up", "level up", "levelup",
    "electronic leveling troubleshooting",
)
LEVEL_UP_SEARCH_BOOST = (
    "Level-Up Level Up Advantage 807662 25499 24999 OCTP "
    "TI-005 Electronic Leveling Troubleshooting Guide "
    "QR-092 Level-Up OCTP wiring QR-059 touch pad LCD "
    "hydraulic leveling controller Manual Mode"
)
# Manual Mode dump works + Auto works → Firefly isolate / rubber-boot plug (not Unity).
# Search tokens only — not printed on the bay sheet.
FIREFLY_CAN_SEARCH_BOOST = (
    "Firefly isolate can isolate terminator rubber-boot plug left in "
    "Firefly cable network plugs USB firmware 574-825-4600 interim 4 GB "
    "Manual Mode flashes home Auto Level works"
)

# Exact bay voice for the Firefly / Level Up Manual Mode prove.
FIREFLY_TWO_PLUG_PROVE = (
    "The Level Up controller has two network plugs. "
    "One has a rubber boot on it — leave that one alone. "
    "The other has a cable running to the Firefly / OneControl system — unplug that cable only. "
    "Then try Manual Mode again."
)
FIREFLY_HOLDS_FIX = (
    "If Manual Mode stays open, Firefly is fighting the Level Up controller. "
    "Reconnect the Firefly cable after this prove unless you are using the interim. "
    "The real fix is a Firefly USB firmware update: read GUI and CCM from Settings, "
    "call Firefly 574-825-4600, and use a USB stick 4 GB or smaller plus the interim file they specify. "
    "Interim: turn the front-bay main battery switch OFF (solar can stay ON) so Firefly drops, "
    "or leave the Firefly cable unplugged with the rubber-boot plug still in."
)
LEVELUP_FIREFLY_FIRM_LINE = (
    "The repair is to update the Firefly firmware. "
    "Read GUI and CCM from Settings, call Firefly at 574-825-4600, "
    "and use a USB stick of 4 GB or smaller. "
    "Do not replace the Level Up controller."
)
FIREFLY_STILL_DUMPS = (
    "If Manual Mode still dumps home, this is not the Firefly path. "
    "Stay on the Level Up sensor and harness path. "
    "Do not swap another Level Up controller for Firefly blame. "
    "Do not push a Firefly USB firmware update as the fix."
)
WIRED_COACH_CAN_RE = re.compile(r"wired\s+coach\s+can", re.I)
LEVEL_UP_FIGURE_SEARCH_BOOST = (
    "Level-Up OCTP TI-005 QR-092 touch pad LCD wiring diagram "
    "hydraulic leveling controller 807662 Fig. figure"
)
# Thin title hints (no invented page numbers) — same idea as Furrion board-figure pages.
LEVEL_UP_ADVANTAGE_HINT_TITLES = (
    "TI-005 Electronic Leveling Troubleshooting Guide",
    "TI-170",
    "QR-092 Level-Up OCTP wiring",
    "QR-059 ID guide",
)
LEVEL_UP_PRODUCT_LOCK = """
LEVEL UP ADVANTAGE / 807662 PRODUCT LOCK:
- 807662 / 25499 / 24999 is the Lippert Level Up (Level-Up) towable hydraulic leveling controller with slide output. It is NOT Ground Control electric and NOT a Lippert OneControl Unity M-Series awning/slide reversing board.
- Search and cite Leveling Level-Up / OCTP / TI-005 / TI-170 / QR-092 / QR-059 / touch-pad leveling manuals FIRST.
- NEVER cite Lippert OneControl M Series Unity Board SM (Electrical) — or any Unity awning/slide reversing board — as the Level Up Advantage controller manual.
- Manual Mode flashes / dumps to home while Auto still works is the Firefly path — not a hydraulic dump test. Cheap-prove Auto, then leave the rubber-boot plug alone and unplug only the Firefly cable. If Manual stays on flash/home: Firefly USB firmware, 574-825-4600, stick 4 GB or smaller + interim file. Do not start at pump R&R.
- Do NOT say the shop library does not include Level Up controller diagnostics if any Level-Up / OCTP / TI-005 / QR-092 / QR-059 / Leveling Level-Up title exists in the catalog.
- If the best Level-Up hit is unindexed or has zero searchable chunks, name that title and ask a manager to re-index it. Do not invent Unity as a substitute.
- If a figure/page render fails, say the figure is in that shop-library PDF and the page image could not be shown. Do not claim the library lacks the procedure.
- Manual Mode flash/dump-to-home while Auto Level or other pad functions still work is a Firefly / OneControl prove: leave the rubber-boot plug alone and unplug only the Firefly cable. Do not open board/LCD swap first. Firefly USB firmware is the fix only when Manual holds with the Firefly cable unplugged. If Manual still dumps, stay on the Level Up sensor / harness path — do not swap another Level Up controller for Firefly blame and do not push Firefly USB.
"""
LEVEL_UP_EMPTY_CLAIM_RE = re.compile(
    r"(library|manuals?|document library).{0,80}(does not|doesn't|do not|don't|lacks?|no |without).{0,60}"
    r"(level[\s-]*up|807662|leveling controller)|"
    r"(no|not|lack|missing|doesn't have|does not have|do not have).{0,50}"
    r"(level[\s-]*up|807662).{0,40}(manual|procedure|diagnos|controller|guide)",
    re.I,
)

# Level Up Manual Mode flash-home while Auto Level still works — Firefly/OneControl
# CAN isolate. Narrow shop path only. Not a Firefly encyclopedia. Not Unity SM.
LEVEL_UP_CAN_SEARCH_BOOST = (
    "Manual Mode flash home Auto Level Firefly terminator "
    "rubber boot network plugs Firefly cable isolate Level Up controller USB firmware"
)
LEVEL_UP_CAN_PRODUCT_LOCK = """
LEVEL UP MANUAL MODE / FIREFLY PRODUCT LOCK (Level Up controller, Auto Level still works):
- Manual Mode flashes then dumps to home while Auto Level or other pad functions still work is a Firefly / OneControl prove. It is NOT a board/LCD swap-first path.
- Cheap proves first: power looks sane / no brownout; Auto Level works; dump is not sticky Low Voltage / Excess Angle / External Sensor (clear those first if present).
- Then use the two-plug prove: The Level Up controller has two network plugs. One has a rubber boot on it — leave that one alone. The other has a cable running to the Firefly / OneControl system — unplug that cable only. Then try Manual Mode again.
- Manual holds with the Firefly cable unplugged → Firefly / OneControl conflict confirmed. Tell the tech to reconnect the Firefly cable after the prove unless using the interim. Real fix = Firefly USB firmware update: read GUI + CCM from Settings, call Firefly 574-825-4600, USB stick 4 GB or smaller. Interim: front-bay main battery switch OFF (solar can stay ON) so Firefly drops, OR leave the Firefly cable unplugged with the rubber-boot plug still in.
- Manual still dumps with the Firefly cable unplugged → NOT this issue. Stay on the Level Up sensor / harness / support path. Do NOT swap another Level Up controller for Firefly blame alone. Do NOT push Firefly USB as the fix.
- Do not build a Firefly encyclopedia. Do not cite Unity awning/slide reversing SM as the Level Up procedure.
"""
LEVEL_UP_CAN_ISOLATE_SHOP_LINE = (
    "Confirm power looks sane and Auto Level still works. Clear sticky Low Voltage, "
    "Excess Angle, or External Sensor text if it is present. "
    + FIREFLY_TWO_PLUG_PROVE
    + "\n"
    "📖 Source: shop writeup — Level Up Advantage Manual Mode flash-home / Firefly"
)
LEVEL_UP_CAN_FIREFLY_SHOP_LINE = (
    "Manual Mode holds with the Firefly cable unplugged and the rubber-boot plug still in. "
    + FIREFLY_HOLDS_FIX
    + "\n"
    "📖 Source: shop writeup — Level Up Advantage Manual Mode flash-home / Firefly"
)
LEVEL_UP_CAN_NOT_FIREFLY_SHOP_LINE = (
    "Manual Mode still dumps with the Firefly cable unplugged and the rubber-boot plug still in. "
    + FIREFLY_STILL_DUMPS
    + "\n"
    "📖 Source: shop writeup — Level Up Advantage Manual Mode flash-home / Firefly"
)
LEVEL_UP_CAN_CHEAP_PROVES_SHOP_LINE = (
    "Manual Mode flashes then dumps to home on the Level Up controller. Before you unplug "
    "the Firefly cable or order parts, confirm power looks sane / no brownout, Auto Level "
    "(or other pad functions) still work, and the dump is not sticky Low Voltage / Excess "
    "Angle / External Sensor (clear those first if they are present).\n"
    "📖 Source: shop writeup — Level Up Advantage Manual Mode flash-home / Firefly"
)
LEVEL_UP_BOARD_SWAP_RE = re.compile(
    r"(replace|swap|r\s*&\s*r|r and r).{0,50}"
    r"(another\s+)?(807662|controller|level(?:ing)?\s+board|\blcd\b)",
    re.I,
)
FIREFLY_USB_PUSH_RE = re.compile(
    r"(firefly.{0,60}usb|usb.{0,40}(firmware|firefly|stick)|574[\s-]*825[\s-]*4600)",
    re.I,
)

# Rooftop Air Conditioning (Furrion FACT*, Furrion FACR* / Chill, Dometic B57915 / Brisk, ADB).
# NOT Lippert OneControl Unity M-Series awning/slide reversing — unless the tech
# explicitly names OneControl / Unity / CAN multiplex for the AC controls.
AC_MODELS = ("fact12sa2", "fact12", "facr08hesa2", "facr08", "facr13", "facr15", "b57915")
AC_DOC_MARKERS = (
    "fact12", "furrion fact",
    "facr08", "furrion facr", "furrion chill",
    "ccd-0007990", "ccd0007990",
    "ccd-0008666", "ccd0008666",
    "rooftop hvac",
    "b57915", "brisk",
    "rooftop ac", "roof top ac", "roof ac",
    "air condition", "air-condition",
    "air distribution", "adb",
    "penguin",
)
AC_SEARCH_BOOST = (
    "Furrion FACT rooftop air conditioner FACT12SA2 FACT12 "
    "Furrion FACR Chill rooftop HVAC "
    "Dometic Brisk B57915 ADB air distribution box "
    "rooftop AC no cool E2 E3"
)
AC_FIGURE_SEARCH_BOOST = (
    "Furrion FACT FACR Chill Dometic Brisk rooftop AC ADB "
    "air distribution box wiring diagram Fig. figure"
)
AC_HINT_TITLES = (
    "Furrion FACT12SA2",
    "Furrion FACT rooftop air conditioner",
    "Furrion Rooftop HVAC Troubleshooting & Service Manual",
    "CCD-0007990",
    "CCD-0008666",
    "Furrion Chill FACR",
    "Dometic Brisk B57915",
    "Dometic Brisk rooftop AC",
)
# Furrion FACR* rooftop freeze / condensate / base-pan / ice (live HIT 2026-09-18
# cited CCD-0008666 only). Prefer existing 7990 + 8666 titles — do not invent OEM text.
FACR_MODEL_RE = re.compile(r"\bfacr\d", re.I)
FACR_FREEZE_DOC_MARKERS = (
    "ccd-0007990", "ccd0007990",
    "ccd-0008666", "ccd0008666",
    "furrion rooftop hvac",
    "rooftop hvac troubleshooting",
    "furrion chill",
)
FACR_FREEZE_SEARCH_BOOST = (
    "CCD-0007990 Furrion Rooftop HVAC Troubleshooting & Service Manual "
    "CCD-0008666 Furrion Chill FACR rooftop air conditioner "
    "freeze ice frost condensate base pan suction icing melt leak"
)
FACR_FREEZE_FIGURE_SEARCH_BOOST = (
    "CCD-0007990 Furrion Rooftop HVAC Troubleshooting "
    "CCD-0008666 Furrion Chill FACR rooftop AC Fig. figure"
)
FACR_FREEZE_HINT_TITLES = (
    "CCD-0007990",
    "Furrion Rooftop HVAC Troubleshooting & Service Manual",
    "CCD-0008666",
    "Furrion Chill FACR",
)
AC_PRODUCT_LOCK = """
AIR CONDITIONING / ROOFTOP AC PRODUCT LOCK:
- Furrion FACT* (FACT12SA2), Furrion FACR* / Chill, Dometic B57915 / Brisk, rooftop AC / ADB, and E2/E3 AC codes are Air Conditioning jobs. They are NOT Lippert OneControl Unity M-Series awning/slide reversing board jobs.
- Search and cite Furrion / Dometic Air Conditioning rooftop / ADB / Brisk / FACT / FACR manuals FIRST.
- Furrion FACR* rooftop freeze / ice / frost / condensate / base-pan / suction icing / melt-leak: search and cite CCD-0007990 Furrion Rooftop HVAC Troubleshooting & Service Manual AND CCD-0008666 (Furrion Chill FACR) — not Dometic-only rooftop books. Do not invent OEM steps or page numbers; use those existing titles. Order: the condensation drain and the refrigerant pressures first, then the pan, filter and fan, suction line, and freeze sensor, then rooftop assembly replacement. Do NOT authorize rooftop assembly replacement until refrigerant pressures have been reported. When that path is reported and pressures are in, the terminal card authorizes rooftop assembly R&R and cites CCD-0007990. That card is the authorization, not an R&R procedure paste. Never say the library has no R&R steps. Never ask the tech to paste an R&R section. Do not leave this prove for compressor no-start, fan-winding continuity, or a DC bus measurement. Do not return a blank card. Do not open fuse or 12V first. Do not stall on searching manuals or repeat drain-only.
- Coleman-Mach 2111-0001: Fan High dead (tester dark and/or about 0 VAC on 9-pin black/white) plus Peacemaker compressor running with the fan locked at about 1.9 A plus a fan run capacitor near its rated value authorizes R&R of the fan motor and the control board only. Do not authorize the full assembly. Stop further tests. Cite the 12VDC wall-thermostat service manual, 1976-536, 1976-603, Peacemaker, and mechanical controls / 1976-695. Do not invent page numbers.
- NEVER cite Lippert OneControl M Series Unity Board SM (Electrical) — or any Unity awning/slide reversing board — as the rooftop AC procedure unless the tech explicitly named OneControl, Unity, or CAN multiplex for the AC controls.
- Do NOT say the shop library does not include an AC procedure, or that it only has Unity, if any Furrion/Dometic rooftop AC / FACT / FACR / Brisk / ADB title exists in the catalog or this turn's excerpts.
- If the best AC hit is unindexed or has zero searchable chunks, name that title and ask a manager to re-index it. Do not invent Unity as a substitute.
- If a figure/page render fails, say the figure is in that shop-library PDF and the page image could not be shown. Do not claim the library lacks the AC procedure.
"""
AC_EMPTY_CLAIM_RE = re.compile(
    r"(library|manuals?|document library).{0,80}(does not|doesn't|do not|don't|lacks?|no |without).{0,60}"
    r"(air\s*condit|rooftop\s+a/?c|fact\d|b57915|brisk)|"
    r"(no|not|lack|missing|doesn't have|does not have|do not have).{0,50}"
    r"(air\s*condit|rooftop\s+a/?c|fact\d|ac procedure).{0,40}(manual|procedure|diagnos|guide)|"
    r"(only (has|have)|library only|only the onecontrol|only onecontrol).{0,40}unity",
    re.I,
)
AC_UNITY_ASK_RE = re.compile(
    r"\b(one\s*control|unity|x270|can[\s-]*bus|can[\s-]*multiplex|can[\s-]*network)\b",
    re.I,
)

# Girard GSWH-2 tankless water heater (CCD-0009390). Not fridge FCR E2, not rooftop AC E2.
# Live library: Water Heaters / Girard GSWH-2 Troubleshooting Manual, 109 chunks.
# Do not invent blink LEDs or OEM page numbers.
WATER_HEATER_MODELS = ("gswh-2", "gswh2", "gswh 2")
WATER_HEATER_DOC_MARKERS = (
    "gswh",
    "ccd-0009390",
    "ccd0009390",
    "girard",
    "petit tube",
    "tankless water",
    "water heater",
    "water-heater",
)
WATER_HEATER_SEARCH_BOOST = (
    "Girard GSWH-2 GSWH2 CCD-0009390 E8 Petit Tube "
    "air pressure switch tankless water heater troubleshooting"
)
WATER_HEATER_FIGURE_SEARCH_BOOST = (
    "Girard GSWH-2 CCD-0009390 Petit Tube air pressure switch "
    "water heater wiring diagram Fig. figure"
)
WATER_HEATER_HINT_TITLES = (
    "Girard GSWH-2 Troubleshooting Manual",
    "CCD-0009390",
    "GSWH-2",
)
WATER_HEATER_PRODUCT_LOCK = """
WATER HEATER / GIRARD GSWH-2 PRODUCT LOCK:
- Girard GSWH-2, tankless water heater, E8, Petit Tube, and air-pressure-switch complaints are Water Heaters jobs. They are NOT Lippert OneControl Unity M-Series awning/slide reversing board jobs. They are NOT Furrion FCR fridge E2 / Fan Fault Current. They are NOT rooftop AC E2/E3.
- Search and cite Girard GSWH-2 / CCD-0009390 / Water Heaters troubleshooting manuals FIRST.
- NEVER cite Lippert OneControl M Series Unity Board SM (Electrical) — or any Unity awning/slide reversing board — as the water heater procedure unless the tech explicitly named OneControl, Unity, or CAN multiplex for the water heater controls.
- Do NOT say the shop library does not include a Girard GSWH-2 / E8 / water heater procedure if any Girard / GSWH-2 / CCD-0009390 / Water Heaters title exists in the catalog or this turn's excerpts.
- If the best Water Heaters hit is unindexed or has zero searchable chunks, name that title and ask a manager to re-index it. Do not invent Unity as a substitute.
- Use ONLY excerpted OEM steps. Never invent blink LEDs, fault-light flash counts, or page numbers.
"""
WATER_HEATER_EMPTY_CLAIM_RE = re.compile(
    r"(library|manuals?|document library).{0,80}"
    r"(does not include|doesn't include|does not have|doesn't have|do not have|lacks?|without).{0,60}"
    r"(girard|gswh|water\s*heater|ccd-0009390)|"
    r"(does not include|doesn't include|does not have|doesn't have|do not have|lacks?|missing|no matching).{0,50}"
    r"(girard|gswh-?2|water\s*heater|e8).{0,40}(manual|procedure|diagnos|guide)",
    re.I,
)
ERROR_CODE_QUERY_RE = re.compile(r"\b([a-z])[\s-]*([0-9]{1,3})\b", re.I)

# Furrion FCR08/FCR10 fridge E2 / 2-flash / Fan Fault Current (CCD-0008122).
# Pages already encoded from the shop SM in this repo (figure fixture + leftover tree).
# Do not invent other page numbers.
FURRION_FCR_FAN_FAULT_PAGES = (27, 33)
FAN_FAULT_SEARCH_BOOST = (
    "Error Code Fan Fault Diagnostics Fan Fault Current "
    "F+ F- Fan Replacement inverter PCB and fan "
    "freezer evaporator fan airflow"
)
FCR_E2_FAN_FAULT_PRODUCT_LOCK = """
FURRION FCR E2 / FAN FAULT CURRENT (CCD-0008122) — 12V fridge only, not rooftop AC E2:
- Furrion FCR08/FCR10 2-flash / E2 / Fan Fault Current is freezer-fan / airflow monitoring. It is NOT a Furrion FACT / Dometic rooftop AC freeze-sensor E2.
- CCD-0008122 Error Code — Fan Fault Diagnostics measures voltage at the F+ and F− terminals on the inverter PCB, then Fan Replacement in Repair Section 2. That SM fan is a separate replaceable part. Shop name: freezer evaporator fan. The excerpt may only say "fan" — that is still the freezer evaporator fan on F+/F−.
- NEVER say the shop Document Library or CCD-0008122 does not list a separate freezer evaporator fan. NEVER say E2 / Fan Fault Current repair is rear inverter/control board only forever.
- Fan Fault Current (1 A peak) is a diagnostic spec, not a board-only sentence. Fan amps under that peak do not prove the fan is good or that only the board is bad.
- SM diamond already in this shop's CCD-0008122 encoding: no nominal ~12 V at F+/F− → inverter/control board R&R. Nominal voltage at F+/F−, connections checked, error remains → replace the inverter PCB AND fan. When the tech already reported fan volts and/or fan amps and E2 / 2-flash returned after thaw or reset, recommend freezer evaporator fan R&R and the rear inverter/control board — not board only.
- Cite 📖 Source from the Fan Fault Diagnostics / Fan Replacement excerpt actually used. Do not invent blink LEDs or page numbers.
"""
FCR_E2_NO_SEPARATE_FAN_RE = re.compile(
    r"(does not list|doesn't list|does not include|doesn't include|"
    r"does not (?:have|name|show)|doesn't (?:have|name|show)|"
    r"no separate|not list a separate)"
    r".{0,60}(freezer )?(evaporator )?fan",
    re.I,
)
FCR_E2_BOARD_ONLY_RE = re.compile(
    r"(e2|fan fault|2[\s-]*flash).{0,50}"
    r"(repair |fix |r\s*&\s*r |= |is |means )?"
    r"(the )?(rear )?(inverter/?|control |driver )?(board only|inverter only)",
    re.I,
)
# SM language already in this repo (leftover tree + p.27 fixture). No invented pages.
FCR_E2_FAN_RR_SHOP_LINE = (
    "CCD-0008122 Error Code — Fan Fault Diagnostics includes Fan Replacement "
    "in Repair Section 2. The SM fan on F+/F− is a replaceable freezer evaporator fan. "
    "When fan volts/amps are present and E2 / 2-flash returned, recommend freezer "
    "evaporator fan R&R and the rear inverter/control board — not board only.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 27"
)
BOARD_RR_RE = re.compile(
    r"(replace|r\s*&\s*r|r and r).{0,40}"
    r"(inverter|control board|driver board|rear (?:control )?board|\bpcb\b)",
    re.I,
)

# Suburban Range / Cooktops — pan-on flame-out (thermocouple tip geometry).
# Do not invent OEM voltages or page numbers. Title bias only.
COOKTOP_HINT_TITLES = (
    "Suburban Range/Cooktops SM",
    "Suburban Range Cooktops",
)
COOKTOP_SEARCH_BOOST = (
    "Suburban Range Cooktops cooktop burner thermocouple flame sensor "
    "tip position cookware pan-on flame stays on tip"
)
COOKTOP_PRODUCT_LOCK = """
SUBURBAN / GAS COOKTOP PAN-ON FLAME-OUT PRODUCT LOCK:
- Burner lights, then goes out when a pan/cookware is placed (either burner) is a cooktop flame-sensor / thermocouple-tip geometry complaint. It is NOT a furnace sail-switch / draft / igniter-first path.
- Search and cite Suburban Range/Cooktops SM FIRST.
- Early in this path, instruct the tech to verify the thermocouple / flame-sensor TIP is positioned in the burner flame WITH COOKWARE ON. Factory often sets the tip too close to the burner head; the flame can leave the tip under load. End that sentence. Do not glue the next instruction onto "under load".
- Do this BEFORE condemning or R&R of the thermocouple, safety valve, orifice, regulator, or igniter.
- Only if tip geometry is correct WITH the pan on and the flame still drops out, proceed to parts / readings from the Suburban Range/Cooktops SM excerpt actually used.
- Never invent OEM voltages or page numbers. Cite 📖 Source from an excerpt actually used.
"""
COOKTOP_TIP_CITE = (
    "📖 Source: Suburban SDN2U Range/Cooktops SM - page 4 (Figs. 3-4)"
)
COOKTOP_TIP_PAN_SHOP_LINE = (
    "With a pan on the burner, check the thermocouple tip position in the flame. "
    "Report what you see.\n"
    + COOKTOP_TIP_CITE
)
COOKTOP_PARTS_RR_RE = re.compile(
    r"(?<!before )(?<!not )(?<!don't )(?<!do not )"
    r"(replace|r\s*&\s*r|r and r|condemn).{0,50}"
    r"(thermocouple|flame[\s-]*sensor|safety valve|orifice|regulator|igniter)",
    re.I,
)
COOKTOP_SKIP_AHEAD_RE = re.compile(
    r"\b(igniter|draft|regulator|orifice|safety valve)\b",
    re.I,
)

# Lippert PSX1 front stabilizer — broken/seized override roll pin.
# CCD-0007345 p.7 is override USAGE, not the end fix for a destroyed pin.
PSX1_HINT_TITLES = (
    "Lippert PSX1 CCD-0007345",
    "rear stabilizer owner",
)
PSX1_SEARCH_BOOST = (
    "Lippert PSX1 CCD-0007345 front stabilizer jack "
    "manual crank override roll pin complete assembly"
)
PSX1_PRODUCT_LOCK = """
LIPPERT PSX1 / FRONT STABILIZER MANUAL OVERRIDE PRODUCT LOCK:
- Power extend/retract works but manual crank/override will not engage, with a broken or seized roll pin / override coupler that is not field-serviceable, is a complete front stabilizer jack assembly R&R. It is NOT a coupler-only repair.
- Search Lippert PSX1 CCD-0007345 and the rear stabilizer owner manual for identification / override usage. Those pages tell how to USE the override — they are not the end fix for a destroyed pin.
- Do NOT recommend replacing the coupler only. Do NOT treat CCD-0007345 p.7 override usage as the repair.
- Steer to replace the COMPLETE front stabilizer jack assembly: reconnect mount + electrical; retest power AND manual.
- Never invent OEM voltages or extra page numbers.
"""
PSX1_PROVE_LINE = (
    "Does the manual crank turn, and what does the override roll pin or coupler look like? "
    "Report what you see.\n"
    "📖 Source: Lippert PSX1 front stabilizer, page 7"
)
PSX1_ASSEMBLY_RR_SHOP_LINE = (
    "Replace the complete front stabilizer jack assembly. "
    "Reconnect the mount and the electrical connector, then retest power and the manual crank.\n"
    "📖 Source: Lippert PSX1 CCD-0007345, page 7"
)
COUPLER_ONLY_RE = re.compile(
    r"(replace|r\s*&\s*r|r and r)\s+(the\s+)?(override\s+)?coupler.{0,20}(only|alone)|"
    r"\bcoupler[\s-]*only\b",
    re.I,
)
COMPLETE_JACK_ASSEMBLY_RE = re.compile(
    r"(replace|r\s*&\s*r|r and r).{0,50}"
    r"(complete|entire|whole).{0,20}"
    r"(front )?(stabilizer )?(jack )?assembly|"
    r"(complete|entire|whole).{0,20}"
    r"(front )?(stabilizer )?jack assembly.{0,30}"
    r"(replace|r\s*&\s*r|r and r)",
    re.I,
)

# Furrion FCR / Arctic fridge rear-wall ice / frost / moisture (CCD-0008122 p.36 / Fig.36).
# Shop SM page already in the library. Do not invent other OEM pages.
FURRION_FCR_ICE_MOISTURE_PAGES = (36,)
ICE_MOISTURE_SEARCH_BOOST = (
    "Ice and Moisture Ice or Moisture in the Fridge "
    "rear wall back wall frost gasket Fig. 36 figure 36"
)
ICE_MOISTURE_PRODUCT_LOCK = """
FURRION FCR / ARCTIC FRIDGE ICE AND MOISTURE PRODUCT LOCK (CCD-0008122 p.36 / Fig.36):
- Ice, frost, or icing on the rear/back wall (including about half from the top down) or moisture in the fridge cavity is Ice and Moisture → Ice or Moisture in the Fridge. It is NOT a No Power / 15A fuse / 12V inverter tree.
- Search and cite Furrion FCR08/FCR10 SM CCD-0008122 Ice and Moisture (page 36, Fig. 36) FIRST.
- Coach order — open language, one clarifying ask or 1–2 next checks per turn, not a quiz cage: pattern note → dial max? → gasket → cooling verify → watch/replace. Closing step: if ice or moisture persists after drying and waiting 1 month, replace the unit.
- Do NOT open No Power / fuse / 12V inverter unless the complaint is no power / dead / won't run / no light.
- Cite the real page and figure: 📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36 (Fig. 36). Never invent a "Fuse location" title with no page.
- Never invent other OEM steps or page numbers. Use the Ice and Moisture excerpt actually retrieved.
"""
ICE_MONTH_CLOSE = (
    "If ice or moisture persists after drying and waiting 1 month, replace the unit."
)
ICE_MOISTURE_SHOP_LINE = (
    "Rear-wall ice is the Ice and Moisture check. "
    "Check whether the temperature dial is at maximum. Report the setting.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36 (Fig. 36)"
)
ICE_COOLING_UNIT_LINE = (
    "Replace the cooling unit.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36 (Fig. 36)"
)
FRIDGE_NO_POWER_RE = re.compile(
    r"\b("
    r"no\s+power|completely\s+dead|no\s+light|no\s+juice|"
    r"won'?t\s+turn(?:\s+on)?(?!\s*off)|wont\s+turn(?:\s+on)?(?!\s*off)|"
    r"won'?t\s+run|wont\s+run|"
    r"blank\s+(?:display|screen)|"
    r"dead\s+(?:fridge|unit|refriger\w*)|"
    r"(?:fridge|refriger\w*|unit)\s+(?:is\s+)?dead"
    r")\b",
    re.I,
)
FUSE_12V_PATH_RE = re.compile(
    r"("
    r"15\s*a(?:tc)?(?:\s+blade)?(?:\s*/\s*cartridge)?(?:\s+fuse)?|"
    r"front\s+vent(?:\s+cover|\s+cavity)?|"
    r"fuse\s+location|"
    r"locate(?:\s+the)?\s+fuse|"
    r"pull\s+the\s+front\s+vent|"
    r"check(?:\s+the)?\s+(?:accessible\s+)?(?:customer/tech\s+)?fuse|"
    r"12\s*v(?:dc)?\s+inverter|"
    r"inverter\s+(?:pcb|board|path)|"
    r"no[\s-]*power\s+(?:path|tree|oem|order)"
    r")",
    re.I,
)


def _norm(text: str) -> str:
    t = (text or "").lower().strip()
    t = t.replace("—", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t)
    return t


def is_path_complete_trap(text: str) -> bool:
    """True if a reply uses the old locked-flowchart trap language."""
    t = text or ""
    if re.search(r"never say.{0,80}this path is complete", t, re.I | re.S):
        return False
    return bool(PATH_COMPLETE_TRAP_RE.search(t))


def wants_library_figures(text: str) -> bool:
    """Detect that the tech wants a shop-library illustration / figure / page shown."""
    t = _norm(text)
    return any(k in t for k in FIGURE_HINTS)


def wants_board_or_terminal_figure(text: str) -> bool:
    """True when the tech wants labeled terminals / PCB / inverter board / pinout / wiring."""
    raw = (text or "").strip()
    if not raw:
        return False
    t = _norm(raw)
    if any(k in t for k in BOARD_FIGURE_ASK_HINTS):
        return True
    if "terminal" in t and any(
        k in t for k in ("pcb", "inverter", "board", "label", "diagram", "figure", "layout", "show")
    ):
        return True
    if "inverter" in t and any(k in t for k in ("show", "page", "figure", "diagram", "layout", "label")):
        return True
    return False


def wants_library_page_shown(text: str) -> bool:
    """Show the shop-library PDF page: figure phrasing or a board/terminal ask."""
    return wants_library_figures(text) or wants_board_or_terminal_figure(text)


def is_furrion_ccd_0008122(text: str) -> bool:
    t = _norm(text)
    return "ccd-0008122" in t or "ccd0008122" in t or (
        "furrion" in t and ("fcr08" in t or "fcr10" in t) and " sm" in f" {t} "
    )


def figure_library_search_boost(user_msg: str) -> str:
    """
    Extra library search terms for figure / terminal / PCB asks.
    Does NOT include Nominal voltage / Quick Notes.
    """
    if wants_board_or_terminal_figure(user_msg):
        extra = FIGURE_SEARCH_BOOST
        if is_level_up_advantage_context("", "", user_msg):
            extra = f"{LEVEL_UP_FIGURE_SEARCH_BOOST} {extra}"
        if is_air_conditioning_context("", "", user_msg):
            extra = f"{AC_FIGURE_SEARCH_BOOST} {extra}"
            if is_facr_rooftop_freeze_context("", "", user_msg):
                extra = f"{FACR_FREEZE_FIGURE_SEARCH_BOOST} {extra}"
        if is_water_heater_context("", "", user_msg):
            extra = f"{WATER_HEATER_FIGURE_SEARCH_BOOST} {extra}"
        return extra
    if wants_library_figures(user_msg):
        extra = "Fig. figure illustration diagram drawing"
        if is_level_up_advantage_context("", "", user_msg):
            extra = f"{LEVEL_UP_FIGURE_SEARCH_BOOST} {extra}"
        if is_air_conditioning_context("", "", user_msg):
            extra = f"{AC_FIGURE_SEARCH_BOOST} {extra}"
            if is_facr_rooftop_freeze_context("", "", user_msg):
                extra = f"{FACR_FREEZE_FIGURE_SEARCH_BOOST} {extra}"
        if is_water_heater_context("", "", user_msg):
            extra = f"{WATER_HEATER_FIGURE_SEARCH_BOOST} {extra}"
        return extra
    return ""


def _blob(*texts: str) -> str:
    return _norm(" ".join(t or "" for t in texts))


def is_unity_board_manual(text: str) -> bool:
    """True for OneControl Unity M-Series awning/slide reversing board manuals."""
    t = _norm(text)
    if not t:
        return False
    if "x270" in t:
        return True
    unityish = "unity" in t or "onecontrol" in t or "one control" in t
    if not unityish:
        return False
    if any(k in t for k in ("awning", "reversing", "m series", "m-series", "x270")):
        return True
    if "unity board" in t or "onecontrol unity" in t or "one control unity" in t:
        return True
    return False


def is_ground_control_manual(text: str) -> bool:
    t = _norm(text)
    return "ground control" in t or "ground-control" in t


def is_level_up_library_title(title: str) -> bool:
    """Catalog titles that are Level-Up / OCTP / TI leveling docs — not Unity, not Ground Control."""
    t = _norm(title)
    if not t or is_unity_board_manual(t) or is_ground_control_manual(t):
        return False
    if any(p in t for p in LEVEL_UP_PARTS):
        return True
    if any(m in t for m in LEVEL_UP_DOC_MARKERS):
        return True
    if re.search(r"\blevel[\s-]*up\b", t) and "leveling" in t:
        return True
    return False


_LEAD_JACK_DRIFT_RE = re.compile(
    r"\bdrift(?:s|ing)?\b|move on (?:their|its) own|pressuriz|"
    r"front[-\s]*left jack|lead[-\s]*jack|cartridge valve|\b177094\b",
    re.I,
)


def is_level_up_lead_jack_drift_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Front jacks drift after a jack swap when another circuit pressurizes.

    This is the lead-jack cartridge. It is not Manual Mode flash-home and not
    Ground Control or a stabilizer jack.
    """
    blob = _blob(category_name, model_text, symptom)
    if not blob or not _LEAD_JACK_DRIFT_RE.search(blob):
        return False
    if _has_manual_mode_dump_marker(blob):
        return False
    if is_ground_control_manual(blob) and not re.search(r"level[\s-]*up", blob):
        return False
    if re.search(r"\bstabilizer\b|\bpsx1\b|\broll pin\b", blob) and not re.search(
        r"level[\s-]*up|lead[-\s]*jack|cartridge", blob
    ):
        return False
    level_up = bool(re.search(r"level[\s-]*up|levelup|\boctp\b", blob))
    hydraulic = "hydraulic" in blob and "level" in blob
    leveling = "leveling" in _norm(category_name) and (
        "lippert" in blob or "jack" in blob or level_up
    )
    return bool(level_up or hydraulic or leveling)


def is_level_up_advantage_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Hydraulic Level Up Advantage / 807662 / OCTP / leveling Manual Mode.
    Ground Control electric alone is a different product.
    A drifting lead jack is a cartridge job, not this Manual Mode path.
    """
    if is_level_up_lead_jack_drift_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if not blob:
        return False
    if is_ground_control_manual(blob) and not any(
        k in blob for k in (*LEVEL_UP_PARTS, "octp", "level-up", "level up", "levelup", "advantage")
    ):
        return False
    if any(p in blob for p in LEVEL_UP_PARTS):
        return True
    if "octp" in blob:
        return True
    if re.search(r"\blevel[\s-]*up\s+advantage\b", blob):
        return True
    if re.search(r"\blevel[\s-]*up\b", blob):
        return True
    if "hydraulic" in blob and "level" in blob and any(
        k in blob for k in ("leveling", "controller", "manual mode", "slide output")
    ):
        return True
    if "leveling" in blob and "manual mode" in blob:
        return True
    if "leveling" in blob and "slide output" in blob and "controller" in blob:
        return True
    cat = _norm(category_name)
    if "leveling" in cat and any(k in blob for k in ("touch pad", "touchpad", "lcd wiring", "pump")):
        if "controller" in blob or "807662" in blob or "level" in blob:
            return True
    return False


def skip_unity_for_level_up(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Coach-only: do not inject Unity Electrical search for a Level Up Advantage job."""
    return is_level_up_advantage_context(category_name, model_text, symptom)



def _has_manual_mode_dump_marker(blob: str) -> bool:
    """Manual Mode flashes / dumps / won't stay / returns to home on a Level Up pad."""
    t = _norm(blob)
    if not t:
        return False
    manual = bool(
        re.search(r"\bmanual\s+mode\b", t)
        or (
            re.search(r"\bmanual\b", t)
            and any(
                k in t
                for k in (
                    "level up",
                    "level-up",
                    "levelup",
                    "leveling",
                    "807662",
                    "octp",
                    "advantage",
                )
            )
        )
    )
    dump = bool(
        re.search(
            r"\b("
            r"flash(?:es|ing|ed)?|"
            r"dumps?|dumped|"
            r"won'?t\s+stay|will\s+not\s+stay|wont\s+stay|"
            r"returns?\s+(?:to\s+)?(?:home|first\s+screen)|"
            r"kicks?\s+(?:back|home|to\s+home)|"
            r"drops?\s+(?:to\s+)?home|"
            r"goes?\s+(?:back\s+)?(?:to\s+)?home|"
            r"home\s+screen"
            r")\b",
            t,
        )
        or "flash home" in t
        or "flash-home" in t
        or "flash then home" in t
    )
    return bool(manual and dump)


def _has_auto_level_fail(blob: str) -> bool:
    t = _norm(blob)
    if not t:
        return False
    return bool(
        re.search(
            r"\bauto(?:\s+level)?\b.{0,40}\b("
            r"won'?t|will\s+not|wont|doesn'?t|does\s+not|failed|fails|not\s+work"
            r")\b",
            t,
        )
        or re.search(
            r"\b("
            r"won'?t|will\s+not|wont|doesn'?t|does\s+not|failed|fails|not\s+work"
            r")\b.{0,40}\bauto(?:\s+level)?\b",
            t,
        )
    )


def _has_auto_or_other_pad_works(blob: str) -> bool:
    """Auto Level or other pad functions still work."""
    t = _norm(blob)
    if not t or _has_auto_level_fail(t):
        return False
    if re.search(
        r"\bauto(?:\s+level)?\b.{0,40}\b(works?|working|ok|okay|fine|good|still)\b",
        t,
    ):
        return True
    if re.search(
        r"\b(works?|working|ok|okay|fine|good|still)\b.{0,40}\bauto(?:\s+level)?\b",
        t,
    ):
        return True
    if re.search(
        r"\b(other|everything else|other pad|other functions?|other leveling)\b"
        r".{0,40}\b(works?|working|ok|fine|good)\b",
        t,
    ):
        return True
    if "auto level still work" in t or "auto still work" in t:
        return True
    return False


def is_level_up_manual_dump_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Level Up / 807662 Manual Mode flash-then-home. Fridge / AC / cooktop / stab lose."""
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    if is_water_heater_context(category_name, model_text, symptom):
        return False
    if is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return False
    if is_stabilizer_override_pin_context(category_name, model_text, symptom):
        return False
    if not is_level_up_advantage_context(category_name, model_text, symptom):
        return False
    return _has_manual_mode_dump_marker(_blob(category_name, model_text, symptom))


def is_level_up_manual_can_conflict_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Manual Mode dumps to home AND Auto Level / other pad functions still work.
    This is the Firefly/OneControl CAN-isolate pathway — not board/LCD first.
    """
    if not is_level_up_manual_dump_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if _has_auto_level_fail(blob):
        return False
    return _has_auto_or_other_pad_works(blob)


def is_firefly_can_path_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Bay procedure + coach: Firefly CAN isolate path for Level-Up Manual Mode."""
    if is_level_up_manual_can_conflict_context(category_name, model_text, symptom):
        return True
    blob = _blob(category_name, model_text, symptom)
    if not blob:
        return False
    if any(
        k in blob
        for k in (
            "fridge", "refriger", "reefer", "fcr0", "fcr1",
            "facr", "rooftop", "air condition",
            "water heat", "gswh", "cooktop", "range & cook",
        )
    ):
        return False
    dump = bool(re.search(r"\bdump", blob))
    auto_works = bool(
        re.search(r"\bauto(?:\s+level|\s+mode)?\s+works\b", blob)
        or re.search(r"\bauto\b.{0,24}\bworks\b", blob)
    )
    manual_mode = "manual mode" in blob
    firefly = "firefly" in blob
    if firefly and (manual_mode or dump or "terminator" in blob or "can" in blob):
        return True
    if dump and auto_works:
        return True
    if manual_mode and dump and re.search(r"\bauto\b", blob):
        return True
    if is_level_up_advantage_context(category_name, model_text, symptom) and (
        (dump and auto_works) or (manual_mode and auto_works)
    ):
        return True
    return False


def _compact_ccd(text: str) -> str:
    """ccd-0007990 / CCD 0007990 → ccd0007990 for title matching."""
    return re.sub(r"[^a-z0-9]", "", _norm(text))


def _looks_like_furrion_fcr_fridge(text: str) -> bool:
    """Furrion FCR08/FCR10 fridge — not rooftop FACR* (which contains the letters fcr)."""
    t = _norm(text)
    if not t or FACR_MODEL_RE.search(t):
        return False
    if "furrion fcr" in t or re.search(r"\bfcr\d", t):
        return True
    return "furrion" in t and bool(re.search(r"\bfcr\b", t))


def _fridge_blob_not_ac(blob: str) -> bool:
    """True when this looks like a refrigerator job, not rooftop AC."""
    if FACR_MODEL_RE.search(blob):
        return False
    if any(k in blob for k in ("fridge", "reefer", "refriger", "fcr0", "fcr1", "norcold")):
        if re.search(r"\bfact\d", blob) or FACR_MODEL_RE.search(blob):
            return False
        if "air condition" in blob or "rooftop" in blob:
            return False
        return True
    if _looks_like_furrion_fcr_fridge(blob) and not FACR_MODEL_RE.search(blob):
        if "air condition" in blob or "rooftop" in blob:
            return False
        return True
    return False


def tech_asks_unity_for_ac_controls(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
    unity_gate: str = "",
) -> bool:
    """
    Exception: tech clearly named OneControl / Unity / CAN multiplex for AC.
    Gate Yes is an explicit answer. Bare 'can' / 'Not sure' is not.
    """
    if (unity_gate or "").strip() == "Yes":
        return True
    blob = _blob(category_name, model_text, symptom)
    if not blob:
        return False
    return bool(AC_UNITY_ASK_RE.search(blob))


def named_appliance_family(model_text: str = "", symptom: str = "") -> str:
    """The appliance the model or complaint names. The category dropdown does not count."""
    blob = _blob(model_text, symptom)
    if not blob:
        return ""
    if any(m in blob for m in AC_MODELS) or re.search(r"\bfact\d", blob) or FACR_MODEL_RE.search(blob):
        return "ac"
    if "brisk" in blob or "b57915" in blob:
        return "ac"
    if any(m in blob for m in WATER_HEATER_MODELS) or "gswh" in blob or re.search(r"\bgirard\b", blob):
        return "water_heater"
    if "water heater" in blob or "water-heater" in blob:
        return "water_heater"
    if re.search(r"\bnt[\s-]*\d", blob) or ("furnace" in blob and "suburban" in blob):
        return "furnace"
    if "sdn2u" in blob or "cooktop" in blob or "gas range" in blob:
        return "cooktop"
    if re.search(r"\bfcr\s*1?0\b", blob) or "refrigerator" in blob:
        return "fridge"
    if any(k in blob for k in ("343633", "ground control", "soft-touch", "stabilizer", "psx1")):
        return "leveling"
    return ""


def category_conflicts_with_model(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """True when the dropdown names a different appliance than the model."""
    family = named_appliance_family(model_text, symptom)
    cat = _norm(category_name)
    if not family or not cat or cat in ("(any)", "any"):
        return False
    if family == "ac":
        return "air condition" not in cat and cat not in ("a/c", "ac", "hvac")
    if family == "water_heater":
        return "water" not in cat
    if family == "furnace":
        return "furnace" not in cat
    if family == "cooktop":
        return "cook" not in cat and "range" not in cat
    if family == "fridge":
        return "fridge" not in cat and "refriger" not in cat
    if family == "leveling":
        return "level" not in cat and "stabil" not in cat and "jack" not in cat
    return False


def is_air_conditioning_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Rooftop Air Conditioning: category, Furrion FACT*, Furrion FACR* / Chill,
    Dometic B57915/Brisk, ADB, E2/E3 AC codes, no-cool AC. Fridge 'not cooling' is not AC.
    A named water heater, furnace, cooktop, fridge, or jack beats the category dropdown.
    """
    if named_appliance_family(model_text, symptom) not in ("", "ac"):
        return False
    cat = _norm(category_name)
    if "air condition" in cat or cat in ("a/c", "ac", "hvac"):
        return True
    blob = _blob(category_name, model_text, symptom)
    if not blob or _fridge_blob_not_ac(blob):
        return False
    if any(m in blob for m in AC_MODELS):
        return True
    if re.search(r"\bfact\d", blob) or FACR_MODEL_RE.search(blob):
        return True
    if "brisk" in blob or "b57915" in blob:
        return True
    if "air condition" in blob or "air-condition" in blob:
        return True
    if re.search(r"\broof(?:[\s-]*top)?\s+a/?c\b", blob) or re.search(r"\ba/?c\s+unit\b", blob):
        return True
    if re.search(r"\badb\b", blob) and any(
        k in blob for k in ("ac", "a/c", "air", "cool", "roof", "furrion", "dometic", "distribution")
    ):
        return True
    if "penguin" in blob and any(k in blob for k in ("ac", "air", "cool", "roof", "dometic")):
        return True
    if re.search(r"\be\s*[23]\b", blob) and any(
        k in blob for k in ("ac", "a/c", "air", "cool", "roof", "ccc", "thermostat", "dometic", "furrion")
    ):
        return True
    if re.search(r"\b(?:no|not|won'?t|wont)\s+cool", blob) and any(
        k in blob for k in ("rooftop", "air condition", "a/c", "brisk", "adb", "fact")
    ):
        return True
    return False


def skip_unity_for_ac(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
    unity_gate: str = "",
) -> bool:
    """Coach: do not inject Unity Electrical search for a rooftop AC job."""
    if not is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if tech_asks_unity_for_ac_controls(category_name, model_text, symptom, unity_gate):
        return False
    return True


def is_ac_library_title(title: str) -> bool:
    """Catalog titles that are rooftop AC / FACT / FACR / Brisk / ADB — not Unity."""
    t = _norm(title)
    if not t or is_unity_board_manual(t):
        return False
    if any(m in t for m in AC_MODELS) or re.search(r"\bfact\d", t) or FACR_MODEL_RE.search(t):
        return True
    if any(p in t for p in AC_DOC_MARKERS):
        return True
    if is_facr_freeze_library_title(title):
        return True
    if "furrion" in t and any(k in t for k in ("fact", "facr", "chill", "air condition", "rooftop", "a/c", "hvac")):
        return True
    if "dometic" in t and any(k in t for k in ("brisk", "penguin", "air condition", "rooftop", "b57915", "adb")):
        return True
    return False


def looks_like_facr_rooftop(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """True for Furrion FACR* / Chill rooftop HVAC — not fridge FCR08/FCR10."""
    blob = _blob(category_name, model_text, symptom)
    if not blob:
        return False
    if FACR_MODEL_RE.search(blob) or any(
        m in blob for m in ("facr08hesa2", "facr08", "facr13", "facr15")
    ):
        return True
    if "facr" in blob and any(
        k in blob for k in ("furrion", "chill", "rooftop", "hvac", "air condition")
    ):
        return True
    return False


def looks_like_rooftop_freeze_complaint(text: str) -> bool:
    """Freeze / ice / frost / condensate / base-pan / suction icing / melt-leak wording."""
    t = _norm(text)
    if not t:
        return False
    if any(
        k in t
        for k in (
            "condensate",
            "condensation",
            "base pan",
            "base-pan",
            "basepan",
            "melt leak",
            "melt-leak",
            "suction ic",
        )
    ):
        return True
    return bool(re.search(r"\b(freeze|freezing|frozen|ice|icing|frost|frosting)\b", t))


def is_facr_rooftop_freeze_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Furrion FACR* rooftop + freeze / ice / frost / condensate / base pan / melt leak.
    Fridge FCR ice/moisture and Dometic-only rooftop jobs lose.
    """
    if is_water_heater_context(category_name, model_text, symptom):
        return False
    if is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return False
    if is_stabilizer_override_pin_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if _looks_like_furrion_fcr_fridge(blob) and not looks_like_facr_rooftop(
        category_name, model_text, symptom
    ):
        return False
    if not looks_like_facr_rooftop(category_name, model_text, symptom):
        return False
    return looks_like_rooftop_freeze_complaint(blob)


def is_facr_freeze_library_title(title: str) -> bool:
    """Existing shop titles for CCD-0007990 and CCD-0008666 — no invented names."""
    t = _norm(title)
    if not t:
        return False
    compact = _compact_ccd(t)
    if "ccd0007990" in compact or "ccd0008666" in compact:
        return True
    if any(p in t for p in FACR_FREEZE_DOC_MARKERS):
        return True
    if "furrion" in t and "rooftop" in t and "hvac" in t and any(
        k in t for k in ("troubleshoot", "service")
    ):
        return True
    if "furrion" in t and "chill" in t and any(
        k in t for k in ("facr", "rooftop", "air condition")
    ):
        return True
    if FACR_MODEL_RE.search(t) and any(k in t for k in ("rooftop", "air condition", "hvac", "chill")):
        return True
    return False


def is_dometic_only_rooftop_ac(title: str) -> bool:
    """Dometic Brisk / Penguin / B57915 rooftop books — not Furrion FACR 7990/8666."""
    t = _norm(title)
    if not t or is_facr_freeze_library_title(t):
        return False
    if "furrion" in t or FACR_MODEL_RE.search(t) or "facr" in t:
        return False
    return any(k in t for k in ("dometic", "brisk", "b57915", "penguin"))


def ac_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward FACT / FACR / Brisk / ADB rooftop AC. Never add Unity terms."""
    symptom = (symptom or "").strip()
    if not is_air_conditioning_context(category_name, model_text, symptom):
        return symptom
    extra = AC_SEARCH_BOOST
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        extra = f"{extra} {FACR_FREEZE_SEARCH_BOOST}"
    return f"{symptom} {extra}".strip()


def level_up_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward Level-Up / OCTP / TI docs. Never add Unity terms."""
    symptom = (symptom or "").strip()
    extras = []
    if is_level_up_advantage_context(category_name, model_text, symptom):
        extras.append(LEVEL_UP_SEARCH_BOOST)
    if is_firefly_can_path_context(category_name, model_text, symptom):
        extras.append(FIREFLY_CAN_SEARCH_BOOST)
    if is_level_up_manual_can_conflict_context(category_name, model_text, symptom):
        extras.append(LEVEL_UP_CAN_SEARCH_BOOST)
    if not extras:
        return symptom
    return f"{symptom} {' '.join(extras)}".strip()


def score_level_up_product(page, query: str = "", category: str = "") -> int:
    """
    Higher = Level-Up / OCTP / TI leveling doc for 807662 Manual Mode.
    Unity M-Series awning/slide reversing must lose. Ground Control electric is weaker.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    cat = _norm(category)
    if isinstance(page, dict):
        cat = cat or _norm(str(page.get("category") or page.get("category_name") or ""))
    else:
        cat = cat or _norm(str(getattr(page, "category", "") or getattr(page, "category_name", "") or ""))
    score = 0
    if is_level_up_library_title(title) or is_level_up_library_title(t):
        score += 22
    if any(p in t or p in q for p in LEVEL_UP_PARTS):
        score += 12
    if "octp" in t:
        score += 14
    if "ti-005" in t or "ti 005" in t or "electronic leveling troubleshooting" in t:
        score += 16
    if "qr-092" in t or "qr 092" in t:
        score += 12
    if "qr-059" in t or "qr 059" in t:
        score += 8
    if "ti-170" in t or "ti 170" in t:
        score += 10
    if "leveling" in cat:
        score += 8
    if "hydraulic" in t and "level" in t:
        score += 8
    if any(k in t for k in ("touch pad", "touchpad", "manual mode", "lcd")):
        score += 4
    if any(k in t for k in ("can isolate", "terminator", "firefly", "120 ohm", "120ohm")):
        score += 10
    if any(k in q for k in ("dump", "auto works", "terminator", "firefly")):
        if any(k in t for k in ("can", "terminator", "firefly", "isolate")):
            score += 8
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 36
    if "awning" in t and "slide" in t:
        score -= 18
    if "reversing" in t and any(k in t for k in ("awning", "unity", "slide")):
        score -= 18
    if "electrical" in cat and is_unity_board_manual(t):
        score -= 8
    if is_ground_control_manual(t) and is_level_up_advantage_context("", "", q or query):
        score -= 10
    return score


def rank_chunks_for_level_up(chunks, query: str, limit: int = 8) -> list:
    """Prefer Level-Up / OCTP / TI pages; drop Unity board SM when a Level-Up hit exists."""
    scored = [(score_level_up_product(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    has_level_up = any(
        sc > 0 and is_level_up_library_title(_page_title(ch) or _page_text_blob(ch))
        for sc, ch in scored
    )
    out = []
    for sc, ch in scored:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            if has_level_up or sc < 0:
                continue
        out.append(ch)
        if len(out) >= limit:
            break
    if out:
        return out
    return [
        ch for sc, ch in scored[:limit]
        if sc >= 0 and not is_unity_board_manual(_page_title(ch))
    ]


def drop_unity_chunks_for_level_up(chunks) -> list:
    """Never keep Unity awning/slide reversing excerpts as the Level Up controller manual."""
    kept = []
    for ch in chunks or []:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            continue
        kept.append(ch)
    return kept


def score_level_up_can_chunk(page, query: str = "", category: str = "") -> int:
    """
    Higher = CAN isolate / terminator / Firefly Manual Mode notes.
    Board/LCD swap-first pages lose when Auto Level still works.
    """
    score = score_level_up_product(page, query, category)
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    if "terminator" in t:
        score += 16
    if "firefly" in t:
        score += 14
    if "wired can" in t or "coach can" in t or "firefly cable" in t or "rubber boot" in t:
        score += 12
    if "can isolate" in t and "no can isolate" not in t:
        score += 8
    if "manual mode" in t and any(k in t for k in ("flash", "home", "dump")):
        score += 10
    if "auto level" in t:
        score += 6
    if re.search(r"\b(replace|swap).{0,30}(807662|controller|lcd)\b", t):
        if "terminator" not in t and "firefly" not in t:
            score -= 20
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 10
    return score


def rank_chunks_for_level_up_can(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer CAN isolate / Firefly writeup over board/LCD swap-first pages."""
    scored = [(score_level_up_can_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _sc, ch in scored:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            continue
        out.append(ch)
        if len(out) >= limit:
            break
    return out


def _claim_is_negated(text: str, match) -> bool:
    """True when the match sits behind never / do not / don't / unless."""
    line_start = text.rfind("\n", 0, match.start()) + 1
    prefix = text[line_start:match.start()].lower()
    window = text[max(0, match.start() - 90):match.start()].lower()
    return bool(
        re.search(
            r"(never|do not|don't|not a |not the |not push|not swap|"
            r"not replace|not conclude|unless )",
            f"{window} {prefix}",
        )
    )


def reply_offers_can_isolate(reply: str) -> bool:
    """True when the reply tells the tech to leave the rubber-boot plug and unplug the Firefly cable."""
    t = _norm(reply)
    if not t:
        return False
    boot = "rubber boot" in t or "rubber-boot" in t or "terminator" in t
    unplug = bool(re.search(r"\b(unplug|unplugg|disconnect)\b", t))
    firefly_cable = bool(
        ("firefly" in t and "cable" in t)
        or "network plug" in t
        or "two network" in t
        or re.search(r"\b(wired|coach)\b.{0,24}\bcan\b", t)
        or "wired can" in t
        or "coach can" in t
        or ("unplug" in t and "can" in t)
    )
    return bool(boot and unplug and firefly_cable)


def reply_names_firefly_usb_fix(reply: str) -> bool:
    """True when Firefly USB firmware is the recommended fix (not a do-not)."""
    t = reply or ""
    if not t:
        return False
    n = _norm(t)
    if "firefly" not in n and "574-825-4600" not in n and "5748254600" not in n.replace("-", ""):
        if not ("usb" in n and "firmware" in n):
            return False
    found = False
    for m in FIREFLY_USB_PUSH_RE.finditer(t):
        if _claim_is_negated(t, m):
            continue
        found = True
        break
    if not found and "574-825-4600" in n:
        idx = n.find("574-825-4600")
        window = n[max(0, idx - 80):idx]
        if not re.search(r"(never|do not|don't|not push|unless)", window):
            found = True
    if not found:
        return False
    return bool(
        ("usb" in n and ("firmware" in n or "firefly" in n or "4 gb" in n or "4gb" in n))
        or "574-825-4600" in n
    )


def reply_names_firefly_interim(reply: str) -> bool:
    t = _norm(reply)
    if not t:
        return False
    battery = ("battery" in t and any(k in t for k in ("off", "switch"))) or "main battery" in t
    can_out = (
        ("can" in t and any(k in t for k in ("unplug", "unplugg", "out")) and ("terminator" in t or "rubber" in t))
        or ("firefly" in t and "cable" in t and any(k in t for k in ("unplug", "unplugg")) and ("rubber" in t or "boot" in t or "terminator" in t))
    )
    return bool(battery or can_out)


def reply_names_can_reconnect(reply: str) -> bool:
    t = _norm(reply)
    if not t:
        return False
    return bool(
        re.search(r"\breconnect\b.{0,48}\bcan\b", t)
        or re.search(r"\bcan\b.{0,48}\breconnect\b", t)
        or re.search(r"\breconnect\b.{0,48}(firefly|cable)", t)
        or re.search(r"(firefly|cable).{0,48}\breconnect\b", t)
    )


def reply_swaps_807662_for_firefly(reply: str) -> bool:
    """True when the reply treats another 807662 / board / LCD swap as the Firefly fix."""
    t = reply or ""
    if not t:
        return False
    for m in LEVEL_UP_BOARD_SWAP_RE.finditer(t):
        if _claim_is_negated(t, m):
            continue
        return True
    return False


def reply_stays_lippert_path(reply: str) -> bool:
    t = _norm(reply)
    if not t:
        return False
    return bool(
        any(k in t for k in ("sensor", "harness", "support"))
        and any(k in t for k in ("lippert", "not this", "not a firefly", "not firefly"))
    )


def level_up_can_stage(facts: dict = None) -> str:
    """isolate | firefly | not_firefly | cheap_proves | ''."""
    facts = facts or {}
    if facts.get("can_isolate") == "stays":
        return "firefly"
    if facts.get("can_isolate") == "still_dumps":
        return "not_firefly"
    if facts.get("sticky_level_error") == "present" and facts.get("manual_dump") == "reported":
        return "cheap_proves"
    if facts.get("auto_level") == "works" and facts.get("manual_dump") == "reported":
        return "isolate"
    if facts.get("manual_dump") == "reported":
        return "cheap_proves"
    return ""


def level_up_can_reply_needs_guard(reply: str, facts: dict = None) -> bool:
    """True when this turn would miss the locked CAN / Firefly branch."""
    if not (reply or "").strip():
        return False
    stage = level_up_can_stage(facts)
    if not stage:
        return False
    if stage == "isolate":
        if reply_swaps_807662_for_firefly(reply) and not reply_offers_can_isolate(reply):
            return True
        if reply_names_firefly_usb_fix(reply) and not reply_offers_can_isolate(reply):
            return True
        return not reply_offers_can_isolate(reply)
    if stage == "firefly":
        if reply_swaps_807662_for_firefly(reply):
            return True
        return not (
            reply_names_firefly_usb_fix(reply)
            and reply_names_firefly_interim(reply)
            and reply_names_can_reconnect(reply)
        )
    if stage == "not_firefly":
        if reply_names_firefly_usb_fix(reply) or reply_swaps_807662_for_firefly(reply):
            return True
        return not reply_stays_lippert_path(reply)
    if stage == "cheap_proves":
        if reply_names_firefly_usb_fix(reply) or reply_swaps_807662_for_firefly(reply):
            return True
        if facts and facts.get("sticky_level_error") == "present":
            return "clear" not in _norm(reply) and "low voltage" not in _norm(reply)
        return False
    return False


def strip_level_up_board_swap_claims(reply: str) -> str:
    if not reply or not reply_swaps_807662_for_firefly(reply):
        return reply
    kept = []
    for part in re.split(r"(?<=[.!?])\s+", reply.strip()):
        if part and not reply_swaps_807662_for_firefly(part):
            kept.append(part)
    return " ".join(kept).strip()


def strip_firefly_usb_push_claims(reply: str) -> str:
    if not reply or not reply_names_firefly_usb_fix(reply):
        return reply
    kept = []
    for part in re.split(r"(?<=[.!?])\s+", reply.strip()):
        if part and not reply_names_firefly_usb_fix(part):
            kept.append(part)
    return " ".join(kept).strip()


def ensure_level_up_manual_can_path(reply: str, facts: dict = None) -> str:
    """
    Deterministic shop lines so Manual-dump + Auto-works cannot skip CAN isolate,
    and so the CAN-out branch cannot ship the wrong Firefly / board-swap fix.
    """
    if not reply or not level_up_can_reply_needs_guard(reply, facts):
        return reply
    stage = level_up_can_stage(facts)
    if stage == "isolate":
        cleaned = strip_level_up_board_swap_claims(reply)
        if reply_offers_can_isolate(cleaned) and not reply_swaps_807662_for_firefly(cleaned):
            return cleaned
        return f"{LEVEL_UP_CAN_ISOLATE_SHOP_LINE}\n\n{cleaned}".strip()
    if stage == "firefly":
        cleaned = strip_level_up_board_swap_claims(reply)
        if (
            reply_names_firefly_usb_fix(cleaned)
            and reply_names_firefly_interim(cleaned)
            and reply_names_can_reconnect(cleaned)
            and not reply_swaps_807662_for_firefly(cleaned)
        ):
            return cleaned
        return f"{cleaned.rstrip()}\n\n{LEVEL_UP_CAN_FIREFLY_SHOP_LINE}".strip()
    if stage == "not_firefly":
        cleaned = strip_firefly_usb_push_claims(strip_level_up_board_swap_claims(reply))
        if (
            cleaned
            and reply_stays_lippert_path(cleaned)
            and not reply_names_firefly_usb_fix(cleaned)
            and not reply_swaps_807662_for_firefly(cleaned)
        ):
            return cleaned
        return f"{cleaned.rstrip()}\n\n{LEVEL_UP_CAN_NOT_FIREFLY_SHOP_LINE}".strip()
    if stage == "cheap_proves":
        cleaned = strip_firefly_usb_push_claims(strip_level_up_board_swap_claims(reply))
        return f"{LEVEL_UP_CAN_CHEAP_PROVES_SHOP_LINE}\n\n{cleaned}".strip()
    return reply


def score_ac_product(page, query: str = "", category: str = "") -> int:
    """
    Higher = Furrion/Dometic rooftop AC / ADB / Brisk / FACT / FACR doc.
    Unity M-Series awning/slide reversing must lose on AC jobs.
    FACR freeze / condensate / base-pan prefers CCD-0007990 + CCD-0008666
    over Dometic-only rooftop books.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    cat = _norm(category)
    if isinstance(page, dict):
        cat = cat or _norm(str(page.get("category") or page.get("category_name") or ""))
    else:
        cat = cat or _norm(str(getattr(page, "category", "") or getattr(page, "category_name", "") or ""))
    score = 0
    if is_ac_library_title(title) or is_ac_library_title(t):
        score += 22
    if any(m in t or m in q for m in AC_MODELS) or re.search(r"\bfact\d", t) or re.search(r"\bfact\d", q):
        score += 12
    if FACR_MODEL_RE.search(t) or FACR_MODEL_RE.search(q):
        score += 12
    if "brisk" in t or "b57915" in t:
        score += 12
    if "air condition" in t or "rooftop" in t or "hvac" in t:
        score += 10
    if re.search(r"\badb\b", t) or "air distribution" in t:
        score += 8
    if "air condition" in cat:
        score += 8
    if any(k in t for k in ("e2", "e3", "no cool", "not cool")):
        score += 4
    compact = _compact_ccd(t)
    if "ccd0007990" in compact or "ccd0008666" in compact:
        score += 10
    if is_facr_freeze_library_title(title) or is_facr_freeze_library_title(t):
        score += 8
    if is_facr_rooftop_freeze_context("", "", q or query):
        if is_facr_freeze_library_title(title) or is_facr_freeze_library_title(t):
            score += 16
        if any(
            k in t
            for k in (
                "freeze", "ice", "frost", "condensate", "base pan",
                "icing", "melt leak", "suction",
            )
        ):
            score += 6
        if is_dometic_only_rooftop_ac(title) or is_dometic_only_rooftop_ac(t):
            score -= 22
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 36
    if "awning" in t and "slide" in t:
        score -= 18
    if "reversing" in t and any(k in t for k in ("awning", "unity", "slide")):
        score -= 18
    if "electrical" in cat and is_unity_board_manual(t):
        score -= 8
    if any(k in t for k in ("refriger", "fridge", "furnace")) and "air condition" not in t:
        score -= 8
    return score


def _chunk_has_ccd(page, ccd_compact: str) -> bool:
    blob = _compact_ccd(f"{_page_title(page)} {_page_text_blob(page)}")
    return ccd_compact in blob


def _ensure_facr_freeze_pair(out: list, scored: list, limit: int) -> list:
    """Keep both CCD-0007990 and CCD-0008666 in FACR freeze ranking when present."""
    missing = []
    for needle in ("ccd0007990", "ccd0008666"):
        if any(_chunk_has_ccd(ch, needle) for ch in out):
            continue
        for _sc, ch in scored:
            if _chunk_has_ccd(ch, needle):
                missing.append(ch)
                break
    if not missing:
        return out
    merged = list(missing) + list(out)
    seen = set()
    deduped = []
    for ch in merged:
        key = (_page_title(ch), _page_number(ch), _page_text_blob(ch)[:40])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ch)
        if len(deduped) >= limit:
            break
    return deduped


def rank_chunks_for_ac(chunks, query: str, limit: int = 8) -> list:
    """Prefer rooftop AC / FACT / FACR / Brisk / ADB pages; drop Unity board SM when an AC hit exists."""
    scored = [(score_ac_product(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    has_ac = any(
        sc > 0 and is_ac_library_title(_page_title(ch) or _page_text_blob(ch))
        for sc, ch in scored
    )
    facr_freeze = is_facr_rooftop_freeze_context("", "", query)
    has_facr_docs = any(
        is_facr_freeze_library_title(_page_title(ch) or _page_text_blob(ch))
        for _sc, ch in scored
    )
    out = []
    for sc, ch in scored:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            if has_ac or sc < 0:
                continue
        if facr_freeze and has_facr_docs and (
            is_dometic_only_rooftop_ac(title) or is_dometic_only_rooftop_ac(blob)
        ):
            continue
        out.append(ch)
        if len(out) >= limit:
            break
    if facr_freeze:
        out = _ensure_facr_freeze_pair(out, scored, limit)
    if out:
        return out
    return [
        ch for sc, ch in scored[:limit]
        if sc >= 0 and not is_unity_board_manual(_page_title(ch))
    ]


def drop_unity_chunks_for_ac(chunks) -> list:
    """Never keep Unity awning/slide reversing excerpts as the rooftop AC manual."""
    kept = []
    for ch in chunks or []:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            continue
        kept.append(ch)
    return kept


# FACR freeze + interior leak: once drain / fan-filter / freeze sensor are proved,
# the coach must finish on rooftop assembly R&R (CCD-0007990). Do not stall.
FACR_ASSEMBLY_SEARCH_BOOST = (
    "CCD-0007990 rooftop assembly condensate R&R replace rooftop assembly"
)
FACR_FREEZE_ASSEMBLY_LOCK = """
FURRION FACR FREEZE / INTERIOR LEAK — ASSEMBLY CLIMAX (CCD-0007990):
- Named branch: Furrion FACR* / Chill rooftop freeze, ice, frost, condensate, or interior leak.
- Cite CCD-0007990 Furrion Rooftop HVAC Troubleshooting & Service Manual and CCD-0008666. Do not invent page numbers.
- Walk order: the condensation drain and the refrigerant pressures first, then the pan, filter and fan, suction line, and freeze sensor, then rooftop assembly replacement. Suction line, thermostat, and nozzles/ambient stay on this prove.
- Do NOT authorize rooftop assembly replacement until refrigerant pressures have been reported. Drain clear plus fan/filter OK plus a good freeze sensor is not enough.
- When drain, pan/slope, filter/fan, suction, freeze sensor, thermostat, nozzles/ambient, and refrigerant pressure are all reported and the freeze or interior leak remains, the terminal card MUST authorize rooftop assembly R&R and cite CCD-0007990. The card is the authorization. Do not dump an R&R procedure. Do not return a blank card. Do not open a fuse or 12V-first tree.
- If the tech asks to authorize rooftop assembly R&R after that prove, emit that same authorization card. NEVER say the Document Library has no R&R steps. NEVER ask the tech to paste an R&R section or a page number.
- Once this freeze/leak prove is the complaint, stay on it. Do NOT drift into compressor no-start, fan-winding continuity, or a DC bus measurement.
- Do NOT stall on "searching manuals" / "searching the library". Do NOT loop a drain-only check once those three proves are in. An unfinished prove does not get the assembly authorization card.
"""
FACR_TERMINAL_ASSEMBLY_RR_LINE = (
    "Drain, pan and slope, filter and fan, suction line, freeze sensor, "
    "thermostat, nozzles, ambient, and refrigerant pressures are reported good. "
    "The freeze or interior leak remains. "
    "Authorize rooftop assembly R&R on the CCD-0007990 condensate and assembly path. "
    "Replace the rooftop assembly.\n"
    "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
)
def facr_reported_assembly_rr_line(facts: dict | None = None) -> str:
    """Rooftop R&R card. Name nozzles only when the tech reported them open."""
    facts = facts or {}
    if facts.get("facr_nozzle") == "open":
        proved = (
            "Drain, pan and slope, filter and fan, nozzles, and the freeze sensor are reported good. "
        )
    else:
        proved = (
            "Drain, pan and slope, filter and fan, and the freeze sensor are reported good. "
        )
    return (
        proved
        + "The freeze or interior leak remains. "
        "Authorize rooftop assembly R&R on the CCD-0007990 condensate and assembly path. "
        "Replace the rooftop assembly.\n"
        "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
    )


FACR_REPORTED_ASSEMBLY_RR_LINE = facr_reported_assembly_rr_line()
FACR_ASSEMBLY_RR_SHOP_LINE = (
    "Drain is clear, the fan and filter are good, and the freeze sensor is good. "
    "Do not keep searching manuals and do not repeat a drain-only check. "
    "Read the refrigerant pressures before any rooftop assembly replacement. "
    "Rooftop assembly replacement waits until those pressures are reported.\n"
    "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
)
FACR_FREEZE_NEXT_SHOP_LINE = (
    "Stay on the CCD-0007990 condensate path. "
    "Do not stop to search manuals. "
    "Order: the condensation drain and the refrigerant pressures first, then the pan, filter and fan, suction line, and freeze sensor. "
    "Rooftop assembly replacement waits until those pressures are reported.\n"
    "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
)
_SEARCHING_MANUALS_RE = re.compile(
    r"searching (?:the )?(?:manuals|library|documents|service manuals)|"
    r"let me search|still searching|looking through (?:the )?manuals",
    re.I,
)
_DRAIN_ACTION_RE = re.compile(
    r"\b(clear|recheck|check|clean|inspect)\b.{0,24}\bdrain\b",
    re.I,
)
_FACR_OFFPATH_RE = re.compile(
    r"\b("
    r"dc\s*bus|"
    r"350\s*v|"
    r"compressor[\s-]*side|"
    r"fan\s+(?:motor\s+)?windings?|"
    r"winding\s+continuity|"
    r"no\s+compressor\s+start|"
    r"compressor\s+(?:will\s+not|won't|does\s+not|doesn't)\s+start"
    r")\b",
    re.I,
)
_FACR_LIBRARY_RR_MISS_RE = re.compile(
    r"("
    r"(?:don'?t|do not|does not|doesn't)\s+have.{0,120}(?:r\s*&\s*r|r and r|removal)"
    r"|paste\s+(?:the\s+|an\s+)?(?:r\s*&\s*r|removal)"
    r"|(?:no|without|lack(?:ing)?|missing).{0,48}"
    r"(?:r\s*&\s*r|removal-and-replace|removal and replace).{0,48}"
    r"(?:step|excerpt|library|procedure|section)"
    r")",
    re.I,
)
_FACR_AUTH_ASK_RE = re.compile(
    r"\bauthori[sz]e\b.{0,60}\b(?:rooftop(?:\s+assembly)?|assembly)\b"
    r"|\brooftop\s+assembly\s+r\s*&\s*r\b",
    re.I,
)


def _facr_prep(text: str) -> str:
    """Lowercase shop text and fold ohm / degree marks so live readings match."""
    raw = text or ""
    raw = raw.replace("Ω", "ohm").replace("Ω", "ohm").replace("ω", "ohm")
    raw = _norm(raw)
    raw = raw.replace("@", " at ").replace("°", " ")
    return re.sub(r"\s+", " ", raw).strip()


_FACR_ASK_ORDER = (
    ("facr_pressure", re.compile(r"\b(refrigerant|pressures?|psi|high side|low side)\b")),
    ("facr_ambient", re.compile(r"\bambient\b")),
    ("facr_nozzle", re.compile(r"\bnozzles?\b")),
    ("facr_thermostat", re.compile(r"\b(thermostat|set ?point)\b")),
    ("facr_freeze_sensor", re.compile(r"\bfreeze[\s-]*sensor\b|\bsensor\b")),
    ("facr_suction", re.compile(r"\bsuction\b")),
    ("facr_fan_filter", re.compile(r"\b(filters?|fan)\b")),
    ("facr_pan_slope", re.compile(r"\b(slope|base pan|base-pan|evaporator pan|\bpan\b)\b")),
    ("facr_drain", re.compile(r"\bdrain\b")),
)
_FACR_PASS_VALUE = {
    "facr_drain": "clear",
    "facr_pan_slope": "ok",
    "facr_fan_filter": "ok",
    "facr_suction": "clear",
    "facr_freeze_sensor": "good",
    "facr_thermostat": "good",
    "facr_nozzle": "open",
    "facr_ambient": "ok",
    "facr_pressure": "ok",
}
_FACR_SHORT_PASS_RE = re.compile(
    r"(good|ok|okay|fine|pass|passed|clear|cleared|open|normal|level|dry|done)",
    re.I,
)
_FACR_YES_RE = re.compile(r"\b(yes|yep|yeah)\b", re.I)


def facr_freeze_proves_from_text(text: str) -> dict:
    """Drain / fan-filter / freeze-sensor phrases. Each phrase stands alone."""
    raw = _facr_prep(text)
    if not raw:
        return {}
    facts = {}
    if re.search(
        r"\bdrain\b.{0,32}\b(clear|open|ok|good|free|flowing)\b|"
        r"\b(clear|open|ok|good)\b.{0,16}\bdrain\b|"
        r"\bdrain\s+clear\b",
        raw,
    ):
        facts["facr_drain"] = "clear"
    if re.search(
        r"fan[\s-]*filter|filter[\s/]*fan|fan and filter|filter and fan",
        raw,
    ) and re.search(r"\b(ok|good|fine|clean|clear)\b", raw):
        facts["facr_fan_filter"] = "ok"
    elif (
        re.search(r"\bfan\b", raw)
        and re.search(r"\bfilters?\b", raw)
        and re.search(r"\b(ok|good|fine)\b", raw)
    ):
        facts["facr_fan_filter"] = "ok"
    if re.search(r"freeze[\s-]*sensor", raw) and re.search(
        r"\b(good|ok|fine|passed|pass)\b", raw
    ):
        facts["facr_freeze_sensor"] = "good"
    if re.search(r"\bfilters?\b", raw) and re.search(r"\b(clean|ok|good|fine|clear)\b", raw):
        facts["facr_filter"] = "ok"
    if re.search(r"\bfan\b", raw) and re.search(
        r"\b(spins?|spinning|runs?|running|freely|airflow)\b", raw
    ):
        facts["facr_fan"] = "ok"
    if facts.get("facr_filter") == "ok" and facts.get("facr_fan") == "ok":
        facts["facr_fan_filter"] = "ok"
    return facts


def _facr_extended_proves_from_text(text: str) -> dict:
    """
    Later FACR freeze-path reports. Only applied on an FACR freeze chat.
    Live readings are the reported results, not a new pass band.
    """
    raw = _facr_prep(text)
    if not raw:
        return {}
    facts = {}
    if re.search(
        r"\bpan\s*/\s*slope\b.{0,24}\b(good|ok|fine|level|correct|pass|passed)\b|"
        r"\bslope\b.{0,24}\b(good|ok|fine|correct|level|right)\b|"
        r"\b(base pan|base-pan|evaporator pan)\b.{0,30}\b(good|ok|level|dry|fine|clean)\b|"
        r"\bpan\b.{0,40}\b(level|dry|clean|draining|drains|drained)\b|"
        r"\b(clean|draining)\b.{0,24}\bpan\b",
        raw,
    ):
        facts["facr_pan_slope"] = "ok"
    if re.search(
        r"\bsuction(?:\s+line)?\b.{0,40}\b(clear|good|ok|dry|fine|pass|passed)\b|"
        r"\bsuction(?:\s+line)?\b.{0,32}\bnot\s+iced\b|"
        r"\bno\s+(?:ice|icing)\b.{0,24}\bsuction\b",
        raw,
    ):
        facts["facr_suction"] = "clear"
    if re.search(r"\b2\s*k\s*ohms?\b.{0,30}\b25\s*c\b|\b25\s*c\b.{0,30}\b2\s*k\s*ohms?\b", raw):
        facts["facr_sensor_reading"] = "reported"
    if re.search(
        r"\b(cool\s+)?set ?point\b.{0,20}\b68\s*f\b|"
        r"\b68\s*f\b.{0,24}\b(cool|set ?point|thermostat)\b|"
        r"\bthermostat\b.{0,30}\b(good|ok|fine|pass|passed)\b",
        raw,
    ):
        facts["facr_thermostat"] = "good"
    if re.search(
        r"\bopen\s+nozzles?\b|\bnozzles?\s+(?:are\s+)?open\b|"
        r"\bnozzles?\b.{0,16}\b(good|ok|clear)\b",
        raw,
    ):
        facts["facr_nozzle"] = "open"
    if re.search(
        r"\bambient\b.{0,24}\b72\s*f\b|"
        r"\b72\s*f\b.{0,20}\bambient\b|"
        r"\bambient\b.{0,16}\b(good|ok|fine|normal)\b",
        raw,
    ):
        facts["facr_ambient"] = "ok"
    if re.search(
        r"\b68\s*/\s*235\b|"
        r"\b(pressures?|refrigerant)\b.{0,32}\b(good|ok|normal|pass|passed|reported)\b|"
        r"\b(pressures?|refrigerant|psi)\b.{0,24}\b\d{2,3}\s*/\s*\d{2,3}\b|"
        r"\b\d{2,3}\s*/\s*\d{2,3}\b.{0,16}\bpsi\b",
        raw,
    ):
        facts["facr_pressure"] = "ok"
    return facts


def _facr_checks_named(text: str) -> list:
    asked = []
    for key, pat in _FACR_ASK_ORDER:
        if pat.search(text) and key not in asked:
            asked.append(key)
    return asked


def _facr_checks_asked(assistant_text: str) -> list:
    """
    The check the coach just asked.
    A recap that names the whole tree does not bind one short answer to every check.
    """
    raw = _facr_prep(assistant_text)
    if not raw or not re.search(r"\?|\b(check|inspect|read|measure|verify|confirm)\b", raw):
        return []
    focused = []
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", raw) if p.strip()]
    for part in parts:
        if not re.search(r"\?|\b(check|inspect|read|measure|verify|confirm)\b", part):
            continue
        keys = _facr_checks_named(part)
        if 1 <= len(keys) <= 2:
            focused = keys
    if focused:
        return focused
    asked = _facr_checks_named(raw)
    if len(asked) > 3:
        return []
    return asked


def _facr_question_fails_on_yes(assistant_text: str) -> bool:
    raw = _facr_prep(assistant_text)
    return bool(
        re.search(
            r"\b(restricted|clogged|clog|iced|icing|blocked|plugged|wrong|bad|failed|failing)\b",
            raw,
        )
    )


def _mark_facr_asked(asked: list) -> dict:
    facts = {}
    for key in asked:
        if key == "facr_freeze_sensor":
            # A short "good" proves the sensor for the terminal path.
            # The three-prove flag stays on an explicit "freeze sensor is good".
            facts["facr_sensor_reading"] = "reported"
        else:
            facts[key] = _FACR_PASS_VALUE[key]
    return facts


def _bind_facr_short_answer(asked: list, assistant_text: str, user_text: str) -> dict:
    """
    Bind a short tech answer to the check the coach just asked.
    'No' passes only when the question was the bad condition (iced, restricted).
    """
    if not asked:
        return {}
    raw = _facr_prep(user_text)
    if not raw or len(raw) > 64:
        return {}
    negative = _facr_question_fails_on_yes(assistant_text)
    negated = bool(re.search(r"\b(not|no|nope|isn'?t|is not)\b", raw))
    if negated and not negative:
        return {}
    if negated and negative:
        return _mark_facr_asked(asked)
    if _FACR_YES_RE.search(raw):
        if negative:
            if "facr_suction" in asked:
                return {"facr_suction": "iced"}
            return {}
        return _mark_facr_asked(asked)
    # A longer report ("fan spins freely with good airflow") is not a yes
    # to the pressure question. Only a short pass word binds the open ask.
    if (
        len(raw.split()) <= 4
        and _FACR_SHORT_PASS_RE.search(raw)
        and not re.search(r"\b(bad|fail|failed|iced|clogged|restricted)\b", raw)
    ):
        return _mark_facr_asked(asked)
    facts = {}
    if "facr_freeze_sensor" in asked and re.search(r"\b2\s*k\s*ohms?\b", raw):
        facts["facr_sensor_reading"] = "reported"
    if "facr_thermostat" in asked and re.search(r"\b68\s*f\b", raw):
        facts["facr_thermostat"] = "good"
    if "facr_ambient" in asked and re.search(r"\b72\s*f\b", raw):
        facts["facr_ambient"] = "ok"
    if "facr_pressure" in asked and re.search(r"\b68\s*/\s*235\b", raw):
        facts["facr_pressure"] = "ok"
    return facts


def facr_proves_from_chat(history: list = None, latest_msg: str = "") -> dict:
    """
    Merge explicit tech phrases with short answers to the coach's last check.
    FACR freeze context only. Readings alone do not finish the path.
    """
    turns = []
    for m in history or []:
        role = (m.get("role") or "").strip()
        content = m.get("content") or ""
        if role in ("user", "assistant") and content.strip():
            turns.append({"role": role, "content": content})
    if (latest_msg or "").strip():
        turns.append({"role": "user", "content": latest_msg})
    if not turns:
        return {}
    blob = " ".join(m["content"] for m in turns)
    facts = {}
    if not is_facr_rooftop_freeze_context("", "", blob):
        return facts
    pending = []
    pending_text = ""
    for m in turns:
        if m["role"] == "assistant":
            pending = _facr_checks_asked(m["content"])
            pending_text = m["content"]
            continue
        facts.update(facr_freeze_proves_from_text(m["content"]))
        facts.update(_facr_extended_proves_from_text(m["content"]))
        facts.update(_bind_facr_short_answer(pending, pending_text, m["content"]))
        if _FACR_AUTH_ASK_RE.search(m["content"] or ""):
            facts["facr_auth_request"] = "yes"
        pending = []
        pending_text = ""
    if facts.get("facr_filter") == "ok" and facts.get("facr_fan") == "ok":
        facts["facr_fan_filter"] = "ok"
    return facts


def facr_proves_complete(facts: dict | None) -> bool:
    facts = facts or {}
    return (
        facts.get("facr_drain") == "clear"
        and facts.get("facr_fan_filter") == "ok"
        and facts.get("facr_freeze_sensor") == "good"
    )


def facr_sensor_proved(facts: dict | None) -> bool:
    facts = facts or {}
    return facts.get("facr_freeze_sensor") == "good" or facts.get("facr_sensor_reading") == "reported"


def facr_reported_path_supports_rr(facts: dict | None) -> bool:
    """
    Drain, pan/slope, filter, fan, and a reported freeze sensor authorize
    rooftop assembly R&R. Nozzles and refrigerant pressures are not required.
    An iced suction line is not this path.
    """
    facts = facts or {}
    if facts.get("facr_suction") == "iced":
        return False
    fan = facts.get("facr_fan_filter") == "ok" or (
        facts.get("facr_filter") == "ok" and facts.get("facr_fan") == "ok"
    )
    return bool(
        facts.get("facr_drain") == "clear"
        and facts.get("facr_pan_slope") == "ok"
        and fan
        and facr_sensor_proved(facts)
    )


def facr_terminal_path_complete(facts: dict | None) -> bool:
    """
    Drain, pan/slope, filter/fan, suction, sensor, thermostat,
    nozzles, ambient, and refrigerant pressure are all reported good.
    """
    facts = facts or {}
    needed = (
        ("facr_drain", "clear"),
        ("facr_pan_slope", "ok"),
        ("facr_fan_filter", "ok"),
        ("facr_suction", "clear"),
        ("facr_thermostat", "good"),
        ("facr_nozzle", "open"),
        ("facr_ambient", "ok"),
        ("facr_pressure", "ok"),
    )
    if any(facts.get(key) != val for key, val in needed):
        return False
    return facr_sensor_proved(facts)


def facr_pressure_authorizes_rr(facts: dict | None) -> bool:
    """Pressures on the drain, pan, filter, fan, and sensor prove authorize rooftop R&R.

    The cool setpoint is not a later ask. Pressures alone do not authorize.
    An iced suction line is not this path. An unreported suction line does not
    hold the card once the other proves and the pressures are in.
    """
    facts = facts or {}
    if facts.get("facr_pressure") != "ok" or facts.get("facr_suction") == "iced":
        return False
    fan = facts.get("facr_fan_filter") == "ok" or (
        facts.get("facr_filter") == "ok" and facts.get("facr_fan") == "ok"
    )
    return bool(
        facts.get("facr_drain") == "clear"
        and facts.get("facr_pan_slope") == "ok"
        and fan
        and facr_sensor_proved(facts)
    )


def facr_pressure_rr_line(facts: dict | None = None) -> str:
    """Firm rooftop R&R once pressures are in. Do not claim a setpoint that was not reported."""
    if facr_terminal_path_complete(facts):
        return FACR_TERMINAL_ASSEMBLY_RR_LINE
    return (
        "Refrigerant pressures are reported and the freeze or interior leak remains. "
        "Authorize rooftop assembly R&R on the CCD-0007990 condensate and assembly path. "
        "Replace the rooftop assembly.\n"
        "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
    )


def reply_names_rooftop_assembly_rr(reply: str) -> bool:
    """True when the reply finishes on rooftop assembly R&R and CCD-0007990."""
    kept = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", reply or ""):
        if re.search(
            r"(do not|don't|not until|waits until|only after).{0,90}"
            r"(authoriz|replace|r\s*&\s*r|rooftop assembly)",
            part,
            re.I,
        ):
            continue
        kept.append(part)
    t = _norm(" ".join(kept))
    if not t:
        return False
    assembly = "rooftop" in t and (
        "assembly" in t or "r&r" in t or "r and r" in t
    )
    replace = bool(re.search(r"\b(replace|r&r|r and r)\b", t))
    cite = "ccd-0007990" in t or "ccd0007990" in t
    condensate = "condensate" in t or "assembly path" in t
    return bool(assembly and replace and cite and condensate)


def reply_stalls_searching_manuals(reply: str) -> bool:
    text = reply or ""
    for m in _SEARCHING_MANUALS_RE.finditer(text):
        if _mention_is_negated(text, m.start()):
            continue
        return True
    return False


def reply_loops_drain_only(reply: str) -> bool:
    """True when the next action is still 'clear the drain' and assembly R&R is absent."""
    text = reply or ""
    if reply_names_rooftop_assembly_rr(text):
        return False
    for m in _DRAIN_ACTION_RE.finditer(text):
        if _mention_is_negated(text, m.start()):
            continue
        return True
    return False


def _strip_facr_stall_sentences(reply: str) -> str:
    if not reply:
        return ""
    kept = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", reply.strip()):
        if not part:
            continue
        if reply_stalls_searching_manuals(part):
            continue
        if re.search(r"error contacting ai|no matching manual", part, re.I):
            continue
        if reply_loops_drain_only(part):
            continue
        kept.append(part)
    return " ".join(kept).strip()


def _facr_reply_unusable(reply: str) -> bool:
    """Blank card, whitespace, or an AI error with no shop action."""
    text = (reply or "").strip()
    if not text:
        return True
    return bool(re.fullmatch(r"error contacting ai:.*", text, flags=re.I | re.S))


def _facr_climax_line(facts: dict | None) -> str:
    if facr_terminal_path_complete(facts) or facr_pressure_authorizes_rr(facts):
        return facr_pressure_rr_line(facts)
    if facr_reported_path_supports_rr(facts):
        return facr_reported_assembly_rr_line(facts)
    return _facr_stay_on_prove_line(facts)


def reply_drifts_facr_off_freeze_path(reply: str) -> bool:
    """Compressor no-start, fan-winding continuity, or a DC bus reading."""
    return bool(_FACR_OFFPATH_RE.search(reply or ""))


def reply_refuses_facr_library_rr(reply: str) -> bool:
    """Library-miss refusal, or a request to paste an R&R section."""
    return bool(_FACR_LIBRARY_RR_MISS_RE.search(reply or ""))


def _facr_next_prove_prompt(facts: dict | None) -> str:
    facts = facts or {}
    pressures_in = facts.get("facr_pressure") == "ok"
    steps = (
        ("facr_drain", "clear", "Inspect the condensate drain and say whether it is clear."),
        ("facr_pressure", "ok", "Read the refrigerant pressures."),
        ("facr_pan_slope", "ok", "Inspect the evaporator pan and the base-pan slope."),
        ("facr_fan_filter", "ok", "Check the filter and the fan."),
        ("facr_suction", "clear", "Say whether the suction line is iced."),
        ("sensor", "proved", "Read the freeze sensor."),
        ("facr_thermostat", "good", "What is the cool setpoint on the thermostat?"),
        ("facr_nozzle", "open", "Are the nozzles open?"),
        ("facr_ambient", "ok", "What is the ambient temperature?"),
    )
    for key, val, prompt in steps:
        if pressures_in and key == "facr_thermostat":
            continue
        if key == "sensor":
            if not facr_sensor_proved(facts):
                return prompt
            continue
        if facts.get(key) != val:
            return prompt
    if pressures_in:
        return "Report the prove that is still open."
    return "Read the refrigerant pressures."


def _facr_pending_prompts(facts: dict | None = None, history: list = None) -> list[str]:
    """Open FACR checks, without a rooftop replacement and without a repeated ask."""
    facts = facts or {}
    asked = _norm(_prior_assistant_text(history))
    pressures_in = facts.get("facr_pressure") == "ok"
    steps = (
        ("facr_drain", "clear", "Inspect the condensate drain and say whether it is clear."),
        ("facr_pressure", "ok", "Read the refrigerant pressures."),
        ("facr_pan_slope", "ok", "Inspect the evaporator pan and the base-pan slope."),
        ("facr_fan_filter", "ok", "Check the filter and the fan."),
        ("facr_suction", "clear", "Say whether the suction line is iced."),
        ("sensor", "proved", "Read the freeze sensor."),
        ("facr_thermostat", "good", "What is the cool setpoint on the thermostat?"),
        ("facr_nozzle", "open", "Are the nozzles open?"),
        ("facr_ambient", "ok", "What is the ambient temperature?"),
    )
    prompts = []
    for key, val, prompt in steps:
        if pressures_in and key == "facr_thermostat":
            continue
        if key == "sensor":
            if facr_sensor_proved(facts):
                continue
        elif facts.get(key) == val:
            continue
        if key == "facr_pressure":
            continue
        if _norm(prompt) in asked:
            continue
        prompts.append(prompt)
    if not pressures_in:
        prompts = [
            "Check the refrigerant pressures and report the readings.",
            "Connect gauges and read the suction and discharge pressures. Report both readings.",
        ] + prompts
    if prompts:
        return prompts
    if not pressures_in:
        return ["Read the refrigerant pressures."]
    nxt = _facr_next_prove_prompt(facts)
    if _norm(nxt).startswith("report the prove"):
        return ["Read the refrigerant pressures."]
    return [nxt]


_FACR_INTERNAL_GUARD_RE = re.compile(
    r"Stay on the FACR condensate and freeze prove\.?\s*"
    r"|Do not leave this prove[^.]*\.?\s*"
    r"|Do not ask the tech to supply a procedure excerpt\.?\s*"
    r"|Next check on the CCD-0007990 condensate path:\s*"
    r"|Report the prove that is still open\.?\s*",
    re.I,
)
_EARLY_ROOFTOP_RR_RE = re.compile(r"replace the rooftop assembly", re.I)


def _strip_facr_internal_guard(text: str) -> str:
    """The prove-guard sentences are coach notes. They are not a shop reply."""
    cleaned = _FACR_INTERNAL_GUARD_RE.sub("", text or "")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _facr_stay_on_prove_line(facts: dict | None) -> str:
    prompt = _facr_next_prove_prompt(facts)
    return (
        f"Next check on the CCD-0007990 condensate path: {prompt}\n"
        "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
    )


_FACR_PRESSURE_ASK_RE = re.compile(
    r"refrigerant pressure|read the refrigerant|connect gauges|"
    r"suction and discharge pressure|read both gauges",
    re.I,
)


def _facr_pressures_already_asked(history: list = None) -> bool:
    """True once an earlier Guided Diagnostics turn already asked for pressures."""
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if _FACR_PRESSURE_ASK_RE.search(message.get("content") or ""):
            return True
    return False


def ensure_facr_early_pressure_ask(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """Ask for refrigerant pressures on the first FACR prove, then do not loop that ask.

    Pressures alone do not authorize. Once they are reported, they are not asked again.
    Once an assistant turn has asked, later proves (pan, fan, suction, sensor) can proceed.
    """
    if _job_key(history, latest_msg, category_name, model_text) != "facr":
        return reply or ""
    facts = facr_proves_from_chat(history, latest_msg)
    if facts.get("facr_pressure") == "ok" or _facr_pressures_already_asked(history):
        return reply or ""
    text = (reply or "").strip()
    if _FACR_PRESSURE_ASK_RE.search(text):
        return text
    ask = "Read the refrigerant pressures."
    if not text:
        return ask
    return f"{ask} {text}"


def _facr_terminal_reply_ok(reply: str) -> bool:
    return bool(
        reply_names_rooftop_assembly_rr(reply)
        and not reply_refuses_facr_library_rr(reply)
        and not reply_drifts_facr_off_freeze_path(reply)
        and not reply_stalls_searching_manuals(reply)
        and not reply_loops_drain_only(reply)
        and not reply_opens_fuse_12v_no_power(reply)
    )


def ensure_facr_freeze_assembly_rr(reply: str, facts: dict | None = None) -> str:
    """
    Rooftop assembly R&R is authorized only after refrigerant pressures are reported
    on the full drain/pan/filter/suction/sensor/thermostat/nozzle/pressure path.
    Drain clear plus fan/filter OK plus a good freeze sensor is not that card.
    A library-miss refusal, a paste-the-R&R request, or a compressor / DC-bus detour
    does not stand. A blank card stays blank until that full path is in.
    A searching-manuals stall is replaced even before those proves are all in.
    """
    facts = facts or {}
    if facr_terminal_path_complete(facts) or facr_pressure_authorizes_rr(facts):
        if _facr_terminal_reply_ok(reply):
            return reply
        return _facr_climax_line(facts)
    # The reported drain / pan / filter / fan / nozzle / sensor path is still open.
    if (
        reply_names_rooftop_assembly_rr(reply)
        or _EARLY_ROOFTOP_RR_RE.search(reply or "")
        or reply_drifts_facr_off_freeze_path(reply)
        or reply_refuses_facr_library_rr(reply)
    ):
        return _facr_stay_on_prove_line(facts)
    if facts.get("facr_auth_request") == "yes" and _facr_reply_unusable(reply):
        return _facr_stay_on_prove_line(facts)
    if facr_proves_complete(facts) and (
        reply_stalls_searching_manuals(reply)
        or reply_loops_drain_only(reply)
        or reply_opens_fuse_12v_no_power(reply)
    ):
        return _facr_stay_on_prove_line(facts)
    if reply and reply_stalls_searching_manuals(reply) and not reply_names_rooftop_assembly_rr(reply):
        cleaned = _strip_facr_stall_sentences(reply)
        return f"{FACR_FREEZE_NEXT_SHOP_LINE}\n\n{cleaned}".strip()
    return reply


# Coleman-Mach 2111-0001: Fan High dead + Peacemaker fan locked + run cap OK
# authorizes fan motor + control board only. Compose from shop library titles.
# Do not invent a 2111-0001 bulletin or a page number.
COLEMAN_2111_SEARCH_BOOST = (
    "Coleman-Mach 2111-0001 12VDC wall thermostat rooftop service manual "
    "1976-536 1976-603 fan high pin 5 black pin 9 white "
    "Peacemaker control box bypass "
    "1976-695 mechanical controls fan motor run capacitor"
)
COLEMAN_MOTOR_BOARD_LOCK = """
COLEMAN-MACH 2111-0001 — FAN MOTOR + CONTROL BOARD ONLY:
- Named unit: Coleman-Mach / Airxcel rooftop model 2111-0001. Not a Furrion FACR freeze job. Not the 2111-004x install book.
- Walk the prove: board Fan High (tester lamp and/or VAC on the 9-pin black/white Fan High path), then a Peacemaker or equivalent bypass of the thermostat and control box, then the fan run capacitor against its rated value.
- When Fan High is dead (tester dark and/or about 0 VAC), the bypass shows the compressor runs while the fan does not rotate on either speed and stall current is about 1.9 A, and the fan run capacitor measures about rated: TERMINAL CARD authorizes R&R of the fan motor and the control board ONLY. Do not authorize the full 2111-0001 assembly. Stop. Do not ask for more tests.
- Cite existing titles only: 12VDC wall-thermostat rooftop service manual (12 VDC present and 115 VAC missing at the 9-pin means the printed circuit board), 1976-536 and 1976-603 (pin 5 black is Fan High, pin 9 white is fan common), SkillAbove Peacemaker (bypass; compressor and fan; amperage), mechanical-controls service manual and 1976-695 (capacitor good and the motor will not start: replace the motor). Do not invent page numbers. Do not cite a 2111-0001-only bulletin.
- Incomplete evidence does not get this authorization card.
"""
COLEMAN_MOTOR_BOARD_AUTH_LINE = (
    "AUTHORIZATION: R&R the rooftop fan motor and the control board only on the Coleman-Mach 2111-0001. "
    "Fan High at the control board is dead (tester dark and about 0 VAC on the 9-pin black-to-white Fan High path). "
    "Peacemaker bypass: the compressor runs, the fan does not rotate on high or low, and shaft-locked current is about 1.9 A. "
    "The fan run capacitor measures about its rated value and is not the failed part.\n"
    "📖 Source: Coleman-Mach 12VDC Wall Thermostat rooftop service manual "
    "(printed circuit board; 115 VAC missing at the 9-pin means the board); "
    "1976-536 and 1976-603 (pin 5 black is Fan High, pin 9 white is fan common); "
    "SkillAbove Peacemaker (bypass the thermostat and control box; compressor and fan; amperage); "
    "Coleman-Mach mechanical controls service manual and 1976-695 "
    "(run capacitor good and the motor will not start: replace the motor)."
)
_COLEMAN_2111_RE = re.compile(r"\b2111[\s-]*0001\b", re.I)
_COLEMAN_ASK_ORDER = (
    ("cap", re.compile(r"\b(?:cap(?:acitor)?|microfarad|uf)\b")),
    ("peacemaker", re.compile(r"\b(?:peacemaker|bypass)\b")),
    ("fan_high", re.compile(r"\b(?:fan\s*high|9[\s-]*pin|light\s*bulb|lightbulb|tester)\b")),
)
# A meter range such as 0.000-0.048 VAC is still a dead Fan High reading.
_COLEMAN_NEAR_ZERO_VAC = r"0(?:\.\d+)?(?:\s*-\s*0(?:\.\d+)?)?\s*vac"
_COLEMAN_FAN_HIGH_DEAD_RE = re.compile(
    r"("
    r"fan\s*high.{0,80}(?:dead|dark|no\s+(?:lamp|light|illuminat\w*)|"
    r"did\s+not\s+illuminat\w*|does\s+not\s+illuminat\w*|"
    + _COLEMAN_NEAR_ZERO_VAC
    + r"|no\s+voltage)"
    r"|(?:tester|lightbulb|light\s*bulb|board\s+output).{0,48}"
    r"(?:dark|no\s+illuminat\w*|did\s+not\s+light).{0,40}fan\s*high"
    r"|fan\s*high.{0,40}(?:tester|light\s*bulb|lightbulb).{0,24}(?:dark|off|dead)"
    r"|(?:black\s*/?\s*white|9[\s-]*pin).{0,48}(?:"
    + _COLEMAN_NEAR_ZERO_VAC
    + r"|no\s+voltage)"
    r"|(?:"
    + _COLEMAN_NEAR_ZERO_VAC
    + r").{0,48}(?:fan\s*high|black|9[\s-]*pin)"
    r")",
    re.I,
)
_COLEMAN_FAN_HIGH_LIVE_RE = re.compile(
    r"\b(?:1[01]\d|120)\s*vac\b.{0,40}\bfan\s*high\b|"
    r"\bfan\s*high\b.{0,40}\b(?:1[01]\d|120)\s*vac\b",
    re.I,
)
_COLEMAN_COMP_OK_RE = re.compile(
    r"\bcompressor\b.{0,48}\b(?:runs|running|ok|okay|starts|started|good)\b|"
    r"\b(?:runs|running|starts|started)\b.{0,24}\bcompressor\b",
    re.I,
)
_COLEMAN_FAN_LOCKED_RE = re.compile(
    r"\bfan\b.{0,48}\b(?:no\s+rotate|not\s+rotate|does\s+not\s+rotate|doesn't\s+rotate|"
    r"never\s+turns|will\s+not\s+turn|won't\s+turn|locked|no\s+rotation|"
    r"does\s+not\s+turn|doesn't\s+turn)\b|"
    r"\bno\s+rotate\b.{0,24}\b(?:high|low|either)\b",
    re.I,
)
_COLEMAN_STALL_AMP_RE = re.compile(
    r"(?<!\d)(?:1\.[5-9]\d*|2(?:\.[0-5]\d*)?)\s*a(?:mps?)?\b",
    re.I,
)
_COLEMAN_CAP_UF_RE = re.compile(r"(?<!\d)1[4-6](?:\.\d+)?\s*uf\b", re.I)
_COLEMAN_CAP_OK_WORD_RE = re.compile(
    r"\bcap(?:acitor)?\b.{0,40}\b(?:ok|okay|good|rated|passes|passed)\b|"
    r"\b(?:ok|okay|good|rated)\b.{0,24}\bcap(?:acitor)?\b|"
    r"\bcap(?:acitor)?\b.{0,40}\bmeasures\s+correct",
    re.I,
)
_COLEMAN_CAP_BAD_RE = re.compile(
    r"\bcap(?:acitor)?\b.{0,32}\b(?:bad|open|short(?:ed)?|failed|0\s*uf)\b|"
    r"\b(?:bad|open|short(?:ed)?|failed)\b.{0,20}\bcap(?:acitor)?\b",
    re.I,
)
_COLEMAN_FISH_RE = re.compile(
    r"\b(?:next|also|then|another)\b.{0,48}\b(?:test|check|measure)\b|"
    r"\b(?:check|measure|test)\b.{0,40}\b(?:continuity|winding|ohm)\b|"
    r"\bcontinuity\b",
    re.I,
)


def _coleman_prep(text: str) -> str:
    raw = text or ""
    raw = raw.replace("µ", "u").replace("μ", "u").replace("Ω", "ohm")
    raw = raw.replace("≈", " ").replace("~", " ")
    raw = _norm(raw)
    return raw


def is_coleman_2111_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Coleman-Mach 2111-0001. Related 2111-004x install books are not this case."""
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    return bool(blob and _COLEMAN_2111_RE.search(blob))


def coleman_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if not is_coleman_2111_context(category_name, model_text, symptom):
        return symptom
    if COLEMAN_2111_SEARCH_BOOST in symptom:
        return symptom
    return f"{symptom} {COLEMAN_2111_SEARCH_BOOST}".strip()


# Same brand list Guided Diagnostics uses to keep a named unit on its own manuals.
# Coleman-Mach and Airxcel are one maker. Search boosts must not add a second brand.
SHOP_BRAND_TOKENS = (
    "furrion", "norcold", "dometic", "suburban", "atwood", "lippert", "lci",
    "bal", "keystone", "jayco", "brinkley", "kz", "victron", "renogy",
    "wfco", "progressive dynamics", "power gear", "schwintek", "carefree",
    "intelli-power", "pd", "on-an", "onan", "generac", "winegard", "girard",
    "coleman", "airxcel", "thetford",
)
_THETFORD_UNIT_RE = re.compile(r"\bthetford\b|\b42070\b|style\s*ii", re.I)
_TOILET_JOB_RE = re.compile(
    r"\b(?:toilet|thetford|42070)\b|style\s*ii|flush\s+lever|plumb",
    re.I,
)
_BRAND_DISPLAY = {
    "thetford": "Thetford",
    "norcold": "Norcold",
    "dometic": "Dometic",
    "furrion": "Furrion",
    "suburban": "Suburban",
    "atwood": "Atwood",
    "lippert": "Lippert",
    "lci": "LCI",
    "coleman": "Coleman",
    "airxcel": "Coleman",
    "girard": "Girard",
    "bal": "BAL",
    "wfco": "WFCO",
    "winegard": "Winegard",
    "generac": "Generac",
    "onan": "Onan",
    "on-an": "Onan",
    "victron": "Victron",
    "renogy": "Renogy",
    "jayco": "Jayco",
    "keystone": "Keystone",
    "brinkley": "Brinkley",
    "kz": "KZ",
    "carefree": "Carefree",
    "schwintek": "Schwintek",
    "progressive dynamics": "Progressive Dynamics",
    "power gear": "Power Gear",
    "intelli-power": "Intelli-Power",
    "pd": "PD",
}
BRAND_CANON = {
    "airxcel": "coleman",
    "coleman": "coleman",
}
COLEMAN_LIBRARY_NEEDLES = (
    "coleman", "airxcel", "1976-536", "1976-603", "1976-695",
    "peacemaker", "12vdc wall", "12 vdc wall",
    "wall-thermostat", "wall thermostat",
)


def named_shop_brands(*texts: str) -> list:
    """Brand tokens in tech text or a manual title. 'pd' alone is ignored."""
    blob = " ".join(t or "" for t in texts).lower()
    found = [b for b in SHOP_BRAND_TOKENS if b in blob]
    if "pd" in found and "progressive" not in blob and "intelli" not in blob:
        found = [b for b in found if b != "pd"]
    return found


def canonical_shop_brands(*texts: str) -> set:
    """Collapse maker aliases (Airxcel and Coleman-Mach) to one brand id."""
    return {BRAND_CANON.get(b, b) for b in named_shop_brands(*texts)}


def symptom_for_brand_detect(symptom: str) -> str:
    """Drop AC search-boost sentences so 'Furrion' in the boost is not the unit brand."""
    text = symptom or ""
    for boost in (
        AC_SEARCH_BOOST,
        AC_FIGURE_SEARCH_BOOST,
        FACR_FREEZE_SEARCH_BOOST,
        FACR_FREEZE_FIGURE_SEARCH_BOOST,
        FACR_ASSEMBLY_SEARCH_BOOST,
    ):
        if boost:
            text = re.sub(re.escape(boost), " ", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def asked_brands_for_lookup(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> set:
    """
    Brands the tech named. A Coleman-Mach 2111-0001 job is Coleman even when an
    Air Conditioning boost also says Furrion. Model/brand wins over the concern
    text when both are present, except the 2111-0001 lock above.
    """
    cleaned = symptom_for_brand_detect(symptom)
    if is_coleman_2111_context(category_name, model_text, cleaned):
        return {"coleman"}
    # Style II / 42070 is Thetford even when the concern also says "leak".
    if _THETFORD_UNIT_RE.search(model_text or "") or _THETFORD_UNIT_RE.search(category_name or ""):
        return {"thetford"}
    tech = canonical_shop_brands(model_text)
    if tech:
        return tech
    if _THETFORD_UNIT_RE.search(cleaned):
        return {"thetford"}
    return canonical_shop_brands(cleaned)


def display_shop_brand(token: str) -> str:
    """Shop-facing spelling for a brand token. 'thetford' is Thetford."""
    key = (token or "").strip().lower()
    if not key:
        return "this brand"
    return _BRAND_DISPLAY.get(key, key.capitalize())


def is_toilet_job(category_name: str = "", model_text: str = "", symptom: str = "") -> bool:
    """A toilet / flush-lever job. It is not a refrigerator."""
    return bool(_TOILET_JOB_RE.search(f"{category_name or ''} {model_text or ''} {symptom or ''}"))


def typed_unit_brand(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> str:
    """
    The brand the tech typed on this unit.

    Model text wins over the complaint, so the word "leak" cannot select Norcold.
    Thetford Style II and 42070 are Thetford.
    """
    if _THETFORD_UNIT_RE.search(f"{category_name or ''} {model_text or ''}"):
        return "Thetford"
    brands = asked_brands_for_lookup(category_name, model_text, "")
    if not brands and _THETFORD_UNIT_RE.search(symptom or ""):
        return "Thetford"
    if not brands:
        brands = asked_brands_for_lookup("", "", symptom or "")
    if not brands:
        return ""
    low_model = (model_text or "").lower()
    ordered = sorted(brands, key=lambda token: low_model.find(token) if token in low_model else 999)
    return display_shop_brand(ordered[0])


def library_miss_brand_label(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> str:
    """Name used in 'No {brand} document in the shop library for this unit.'"""
    brand = typed_unit_brand(category_name, model_text, symptom)
    if brand:
        return brand
    if is_toilet_job(category_name, model_text, symptom):
        return "toilet"
    return ""


def library_miss_shop_line(brand: str) -> str:
    """The only shop line when this unit's manual is not in the library."""
    who = (brand or "").strip() or "this brand"
    return (
        f"No {who} document in the shop library for this unit. "
        "Add the OEM manual to the shop library. "
        "What do you observe?"
    )


def is_coleman_library_text(text: str) -> bool:
    """True for the Coleman rooftop titles GD already cites. Not a Furrion FACT/FACR book."""
    t = _norm(text)
    if not t:
        return False
    return any(n in t for n in COLEMAN_LIBRARY_NEEDLES)


def library_filename_words(file_path: str = "") -> str:
    """Filename words Bay PDF uses when the stored title is a raw catalog name."""
    name = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"\.[A-Za-z0-9]{2,5}$", " ", name)
    return name.replace("_", " ").replace("-", " ")


def page_identity_blob(
    title: str = "",
    keywords: str = "",
    excerpt: str = "",
    file_path: str = "",
    brand: str = "",
    models: str = "",
    product_line: str = "",
    doc_number: str = "",
    clean_title: str = "",
) -> str:
    """Title, keywords, excerpt, and filename words. GD and the Bay PDF share this.

    Empty metadata collapses to the same identity as a page that has none.
    """
    bits = []
    for raw in (
        title,
        keywords,
        excerpt,
        library_filename_words(file_path),
        brand,
        models,
        product_line,
        doc_number,
        clean_title,
    ):
        text = (raw or "").replace("_", " ").replace("-", " ")
        bits.append(text)
    return _norm(" ".join(bits))


def chunk_matches_asked_brand(
    title: str = "",
    keywords: str = "",
    excerpt: str = "",
    asked=None,
    coleman_job: bool = False,
    file_path: str = "",
    brand: str = "",
    models: str = "",
    clean_title: str = "",
    product_line: str = "",
    doc_number: str = "",
) -> bool:
    """
    True when this library page is the asked brand, or a Coleman 2111 title
    (1976-536 / Peacemaker / wall-thermostat) that does not name a different maker.
    Brand tokens in the filename count, same as a human title.
    An empty asked set does not filter.

    A stored shop brand is authoritative: keywords that name a second maker do
    not pull the page in, and the title does not have to repeat the brand.
    With no stored brand, title, keywords, filename, models, and clean title
    are scanned the same way as before.
    """
    asked = set(asked or [])
    if not asked:
        return True
    declared = canonical_shop_brands(brand or "")
    if declared:
        return bool(asked & declared)
    name = library_filename_words(file_path)
    extra = " ".join(
        part for part in (models or "", clean_title or "", product_line or "", doc_number or "") if part
    )
    canon = canonical_shop_brands(title or "", keywords or "", name, extra)
    if asked & canon:
        return True
    if coleman_job and "coleman" in asked:
        if canon - {"coleman"}:
            return False
        return is_coleman_library_text(
            f"{title or ''} {keywords or ''} {excerpt or ''} {name} {extra}"
        )
    return False


# Brand words alone are not a model. "Lippert" does not exclude a model list.
# "Schwintek" is a product, so "Lippert Schwintek" is model-specific.
_PRIMARY_OEM_BRANDS = frozenset({
    "furrion", "norcold", "dometic", "suburban", "atwood", "lippert", "lci",
    "bal", "coleman", "airxcel", "thetford", "girard",
})


def _model_query_is_specific(query: str) -> bool:
    text = query or ""
    if re.search(r"\d", text):
        return True
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return any(len(tok) >= 4 and tok not in _PRIMARY_OEM_BRANDS for tok in tokens)


def model_list_allows(models, query: str) -> bool:
    """True when this page's model list does not rule out the tech's model.

    An empty list never excludes an older document. A brand-only query such as
    "Lippert" does not exclude a listed model. A specific model must hit the list.
    """
    from library_bulk_import import listed_models_match, split_semicolon_list

    if not split_semicolon_list(models):
        return True
    if not (query or "").strip():
        return True
    if not _model_query_is_specific(query):
        return True
    return listed_models_match(models, query)


def _page_fields(page) -> tuple:
    if isinstance(page, dict):
        excerpt = page.get("excerpt") or page.get("chunk_text") or ""
        return (
            page.get("title") or "",
            page.get("keywords") or "",
            excerpt,
            page.get("file_path") or "",
        )
    excerpt = getattr(page, "chunk_text", "") or getattr(page, "excerpt", "") or ""
    return (
        getattr(page, "title", "") or "",
        getattr(page, "keywords", "") or "",
        excerpt,
        getattr(page, "file_path", "") or getattr(page, "_lookup_file_path", "") or "",
    )


def _meta_field(page, name: str) -> str:
    lookup = f"_lookup_{name}"
    if isinstance(page, dict):
        value = page.get(name)
        if value is None or value == "":
            value = page.get(lookup)
    else:
        value = getattr(page, name, None)
        if value is None or value == "":
            value = getattr(page, lookup, None)
    return "" if value is None else str(value)


def identity_from_page(page) -> str:
    """Same identity blob, plus brand and models when the document stored them."""
    title, keywords, excerpt, path = _page_fields(page)
    return page_identity_blob(
        title,
        keywords,
        excerpt,
        path,
        brand=_meta_field(page, "brand"),
        models=_meta_field(page, "models"),
        product_line=_meta_field(page, "product_line"),
        doc_number=_meta_field(page, "doc_number"),
        clean_title=_meta_field(page, "clean_title"),
    )


def is_ground_control_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Lippert Ground Control electric leveling (including 343633).
    Hydraulic Level Up 807662 is a different product.
    """
    blob = _blob(category_name, model_text, symptom)
    if not blob:
        return False
    if any(p in blob for p in LEVEL_UP_PARTS) and "343633" not in blob and not is_ground_control_manual(blob):
        return False
    if "343633" in blob:
        return True
    if is_ground_control_manual(blob) and not any(p in blob for p in LEVEL_UP_PARTS):
        return True
    return False


_DOMETIC_NOCOOL_COMPLAINT_RE = re.compile(
    r"\b(?:no|not|isn'?t|isnt)\s+(?:cold|cool|cooling)\b|"
    r"\bwon'?t\s+cool\b|\bwont\s+cool\b|\bno\s+cooling\b|"
    r"\b(?:will not|won'?t|wont|does not|doesn'?t)\s+blow\s+cold\b|"
    r"\bnot\s+blow\s+cold\b",
    re.I,
)
_DOMETIC_NOCOOL_ON_RE = re.compile(
    r"\bfan\b|"
    r"\bturns?\s+on\b|"
    r"\bpowered\s+on\b|"
    r"\bpowers?\s+on\b|"
    r"\bcomes?\s+on\b",
    re.I,
)


def _dometic_complaint_blob(category_name: str, model_text: str, symptom: str) -> str:
    """Tech words only. An AC search boost that says 'no cool' is not the complaint."""
    cleaned = symptom or ""
    for boost in (
        AC_SEARCH_BOOST,
        AC_FIGURE_SEARCH_BOOST,
        "Dometic diagnostic service manual 3311071 no cool compressor ceiling thermostat selector",
    ):
        if boost and boost in cleaned:
            cleaned = cleaned.replace(boost, " ")
    return _blob(category_name, model_text, cleaned)


def is_dometic_b57915_nocoool_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Dometic B57915 that turns on, or whose fan runs, and will not blow cold.
    A Brisk E3 'no cool' with neither fact stays on the Brisk ranker.
    """
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        return False
    if is_coleman_2111_context(category_name, model_text, symptom):
        return False
    blob = _dometic_complaint_blob(category_name, model_text, symptom)
    if "b57915" not in blob and "3311071" not in blob:
        return False
    if not _DOMETIC_NOCOOL_ON_RE.search(blob):
        return False
    return bool(_DOMETIC_NOCOOL_COMPLAINT_RE.search(blob))


def is_dometic_ceiling_sheet_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Bay sheet for B57915 no-cool. An E-code filter job stays off 3311071."""
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        return False
    if is_coleman_2111_context(category_name, model_text, symptom):
        return False
    if is_dometic_b57915_nocoool_context(category_name, model_text, symptom):
        return True
    blob = _blob(category_name, model_text, symptom)
    if "b57915" not in blob and "3311071" not in blob:
        return False
    if re.search(r"\be\s*\d\b", blob):
        return False
    return bool(
        re.search(
            r"\b(?:no|not|isn'?t|isnt)\s+(?:cold|cool|cooling)\b|"
            r"\bwon'?t\s+cool\b|\bwont\s+cool\b|\bno\s+cooling\b",
            blob,
        )
    )


def is_fact12_freeze_code_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """FACT12 E2 or E3. The MODEL field must be FACT12. A search boost does not count.

    E2 or E3 has to be in the complaint after boosts are removed. Coleman-Mach
    and Dometic jobs do not match, even when the air-conditioning query mentions FACT12.
    """
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        return False
    if not re.search(r"fact\s*12", _norm(model_text)):
        return False
    complaint = symptom_for_brand_detect(symptom or "")
    return bool(re.search(r"\be\s*[23]\b", _norm(complaint)))


_FACT12_NO_CODE_RE = re.compile(
    r"("
    r"do not list or define"
    r"|does not list or define"
    r"|don'?t list or define"
    r"|no e2 definition"
    r"|not define an e\s*2"
    r")",
    re.I,
)


def reply_names_fact12_freeze_resecure(reply: str) -> bool:
    t = _norm(reply)
    return "resecure" in t and "freeze sensor" in t


def ensure_fact12_freeze_resecure(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> str:
    """FACT12 E2/E3 reseats the freeze sensor. A 'no E2 definition' line does not."""
    blob = _blob(
        category_name,
        model_text,
        symptom,
        _chat_user_blob(history, latest_msg),
    )
    if not is_fact12_freeze_code_context(category_name, model_text, blob):
        return reply or ""
    user = _chat_user_blob(history, latest_msg)
    if re.search(r"nozzle|outer temp", reply or "", re.I):
        reply = ""
    if _SENSOR_LOOSE_RE.search(user) and not _is_fallback_question(latest_msg or ""):
        return FACT12_FREEZE_RESECURE_LINE
    if re.search(r"\be\s*3\b", _norm(blob)):
        if re.search(r"\d+(?:\.\d+)?\s*v\b", _norm(user)):
            return FACT12_E3_AFTER_VOLTS_LINE
        return FACT12_E3_PROVE_LINE
    return FACT12_E2_PROVE_LINE


def page_is_ground_control_family(identity: str) -> bool:
    """Electric Leveling / Ground Control pages. A 'not Ground Control' aside does not count."""
    t = identity or ""
    if "343633" in t:
        return True
    if "ground control" in t and "not ground control" not in t:
        return True
    if "electric leveling" in t and "ground control" in t:
        return True
    return False


def page_is_dometic_nocoool_family(identity: str) -> bool:
    """Diagnostic manual 3311071 no-cool / compressor pages, not a filter-only page."""
    t = identity or ""
    if "3311071" in t:
        return True
    diagnostic = "diagnostic" in t or "service manual" in t
    nocoool = any(k in t for k in ("no cool", "not cool", "no-cool", "not cooling", "no cooling"))
    return bool(diagnostic and nocoool and "compressor" in t)


def filter_chunks_for_unit(chunks, category_name: str = "", model_text: str = "", symptom: str = "") -> list:
    """
    Shared brand/model pick used by Guided Diagnostics and the Bay PDF.
    When a Ground Control or Dometic no-cool page is in the set, keep that family.
    """
    rows = list(chunks or [])
    gc = is_ground_control_context(category_name, model_text, symptom)
    dom = is_dometic_b57915_nocoool_context(category_name, model_text, symptom)
    if not gc and not dom:
        return rows
    family = []
    for ch in rows:
        ident = identity_from_page(ch)
        if gc and page_is_ground_control_family(ident):
            family.append(ch)
        elif dom and page_is_dometic_nocoool_family(ident):
            family.append(ch)
    return family or rows


def unit_page_score(page, model_text: str = "", symptom: str = "") -> int:
    """Extra rank so the shared family page beats a same-brand cousin."""
    ident = identity_from_page(page)
    score = 0
    if is_ground_control_context("", model_text, symptom):
        if page_is_ground_control_family(ident):
            score += 36
            if "zero point" in ident or "zero-point" in ident:
                score += 14
            if "manual level" in ident:
                score += 10
        if "807662" in ident or "level up" in ident or "level-up" in ident:
            score -= 24
    if is_dometic_b57915_nocoool_context("", model_text, symptom):
        if "3311071" in ident:
            score += 36
        if "compressor" in ident and any(
            k in ident for k in ("no cool", "not cool", "no-cool", "not cooling")
        ):
            score += 16
        if "filter" in ident and "3311071" not in ident and "compressor" not in ident:
            score -= 14
    return score


def rank_chunks_for_ground_control(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer Ground Control electric leveling, manual level, and zero-point pages."""
    kept = filter_chunks_for_unit(chunks, "", query, query)
    scored = [(unit_page_score(ch, query, query), ch) for ch in kept]
    scored.sort(key=lambda row: row[0], reverse=True)
    return [ch for _sc, ch in scored[:limit]]


def rank_chunks_for_dometic_nocoool(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer Dometic diagnostic manual 3311071 over a filter-only page."""
    kept = filter_chunks_for_unit(chunks, "", query, query)
    scored = [(unit_page_score(ch, query, query) + score_ac_product(ch, query), ch) for ch in kept]
    scored.sort(key=lambda row: row[0], reverse=True)
    return [ch for _sc, ch in scored[:limit]]


GROUND_CONTROL_SEARCH_BOOST = (
    "Lippert Ground Control electric leveling manual level zero-point calibration 343633"
)
DOMETIC_NOCOOL_SEARCH_BOOST = (
    "Dometic diagnostic service manual 3311071 no cool compressor ceiling thermostat selector"
)
GROUND_CONTROL_PROVE_LINE = (
    "Confirm the controller, jack, and touch pad plugs are seated. "
    "Report whether those plugs are seated before any zero-point change.\n"
    "📖 Source: Lippert Internal Tech Support – Electric Leveling Systems "
    "(Ground Control TT/2.0/3.0)"
)
GROUND_CONTROL_LEVEL_LINE = (
    "Auto-level that lifts the driver side is a zero-point calibration on Lippert Ground Control.\n"
    "1. Do a manual level, then set zero point.\n"
    "2. Confirm the controller, jack, and touch pad plugs are seated.\n"
    "3. In manual mode, run the jacks until the trailer is level. Put a level in the center and level front to back, then side to side.\n"
    "4. Turn the touch pad off.\n"
    "5. With the touch pad off, press and release FRONT five times, then press and release REAR five times.\n"
    "6. The display reads ZERO POINT CALIBRATION, ENTER to set, Power to exit. Press ENTER.\n"
    "7. The display reads Zero point stability check, then Zero point set successfully.\n"
    "8. That stored position is the level state, and the touch pad turns off.\n"
    "📖 Source: Lippert Internal Tech Support – Electric Leveling Systems "
    "(Ground Control TT/2.0/3.0)"
)
GROUND_CONTROL_STAY_LINE = (
    "Stay on the zero-point sequence already given. Report the display after ENTER.\n"
    "📖 Source: Lippert Internal Tech Support – Electric Leveling Systems "
    "(Ground Control TT/2.0/3.0)"
)
DOMETIC_CEILING_LINE = (
    "Both bypasses cool. Replace the ceiling thermostat/selector.\n"
    "📖 Source: Dometic Brisk II, page 23"
)
DOMETIC_NOCOOL_OPEN = (
    "The fan is running and the air is not cold.\n"
    "Do the Peacemaker bypass at the rooftop unit and report whether it cools.\n"
    "📖 Source: Dometic diagnostic service manual 3311071"
)
DOMETIC_NOCOOL_CONFIRM_FAN = (
    "Dometic B57915 turns on and will not blow cold.\n"
    "Confirm the fan runs, then do the Peacemaker bypass at the rooftop unit "
    "and report whether it cools.\n"
    "📖 Source: Dometic diagnostic service manual 3311071"
)
DOMETIC_NOCOOL_STEER = DOMETIC_NOCOOL_OPEN
FURNACE_SAIL_PROVE_LINE = (
    "Prove the sail switch with the blower running. "
    "Report power in and power out before any thermostat replacement.\n"
    "📖 Source: Suburban Furnace Service and Training Manual"
)
FURNACE_WALL_TSTAT_LINE = (
    "Replace the wall thermostat.\n"
    "📖 Source: Suburban Furnace Service and Training Manual"
)
COOKTOP_TIP_LOW_REPAIR = (
    "Reposition the thermocouple tip in the flame with the pan on. "
    "Figs. 3-4 on page 4 show that tip height.\n"
    + COOKTOP_TIP_CITE
)
# Shared with the Bay PDF. Ask for the freeze-sensor check before the reseat.
FACT12_E2_PROVE_LINE = (
    "Check whether the freeze sensor is fastened on the evaporator coil. "
    "Report what you find before any repair.\n"
    "📖 Source: Furrion Chill FACR08 8K manual CCD-0008666, page 5"
)
FACT12_E3_PROVE_LINE = (
    "FACT12 E3 is the communication path. Measure 12 V and the data line at the connector, "
    "and check whether the freeze sensor is fastened on the evaporator coil. "
    "Report those before any repair.\n"
    "📖 Source: Furrion Chill FACR CCD-0008666, page 15\n"
    "📖 Source: Furrion Chill FACR CCD-0008666, page 18"
)
FACT12_E3_AFTER_VOLTS_LINE = (
    "Those supply readings are in. Check whether the freeze sensor is fastened "
    "on the evaporator coil. Report what you find.\n"
    "📖 Source: Furrion Chill FACR CCD-0008666, page 15"
)
FACT12_FREEZE_RESECURE_LINE = (
    "Reseat the freeze sensor on the evaporator coil and retest.\n"
    "📖 Source: Furrion Chill FACR08 8K manual CCD-0008666, page 5"
)
# Shared with the Bay PDF. E8 is the air-pressure switch. The sensing tube is at the blower.
GIRARD_PETIT_ALIGN_LINE = (
    "E8 is the air pressure switch. The sensing tube is at the blower. "
    "Look through the exhaust vent, confirm the tube is connected at the blower and the switch, "
    "and report what you find.\n"
    "📖 Source: Girard tankless water heater service manual CCD-0009390, page 23"
)
GIRARD_BLOWER_SUCTION_LINE = (
    "The sensing tube is at the blower for the air pressure switch. "
    "With the blower running, confirm suction at that tube and report the result.\n"
    "📖 Source: Girard tankless water heater service manual CCD-0009390, page 23"
)
GIRARD_SEATING_REPAIR_LINE = (
    "That seating is the repair.\n"
    "📖 Source: Girard tankless water heater service manual CCD-0009390, page 23"
)
_LIBRARY_NO_STEPS_RE = re.compile(
    r"("
    r"library has no|"
    r"no steps in the (?:library|manual|excerpt)|"
    r"(?:does not|doesn't|do not|don't) have.{0,48}(?:steps|procedure)|"
    r"no (?:procedure|steps).{0,30}(?:library|manual)|"
    r"library (?:does not|doesn't|doesnt) cover|"
    r"(?:library|manual|excerpt|excerpts).{0,120}(?:does not|doesn't|doesnt|do not|don't) cover|"
    r"(?:manual|excerpt|document library) (?:does not|doesn't|doesnt) cover|"
    r"not covered by (?:the |this )?(?:library|manual|excerpt)|"
    r"no diagnostic steps"
    r")",
    re.I,
)
_LIBRARY_MISS_NEG_RE = re.compile(
    r"\b(do not|don't|dont|never|not say)\b",
    re.I,
)


def ground_control_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if not is_ground_control_context(category_name, model_text, symptom):
        return symptom
    if GROUND_CONTROL_SEARCH_BOOST in symptom:
        return symptom
    return f"{symptom} {GROUND_CONTROL_SEARCH_BOOST}".strip()


def dometic_nocoool_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if not is_dometic_b57915_nocoool_context(category_name, model_text, symptom):
        return symptom
    if DOMETIC_NOCOOL_SEARCH_BOOST in symptom:
        return symptom
    return f"{symptom} {DOMETIC_NOCOOL_SEARCH_BOOST}".strip()


def _reply_sentences(reply: str) -> list:
    return [part for part in re.split(r"(?<=[.!?])\s+|\n+", (reply or "").strip()) if part]


def claims_library_missing_steps(reply: str) -> bool:
    """True when the reply says the library has no steps. A 'do not say' warning does not count."""
    text = reply or ""
    for match in _LIBRARY_NO_STEPS_RE.finditer(text):
        window = text[max(0, match.start() - 48):match.start()]
        if _LIBRARY_MISS_NEG_RE.search(window):
            continue
        return True
    return False


def strip_library_no_steps(reply: str) -> str:
    if not reply or not claims_library_missing_steps(reply):
        return reply or ""
    kept = []
    for part in _reply_sentences(reply):
        if not claims_library_missing_steps(part):
            kept.append(part)
    return " ".join(kept).strip()


def library_miss_already_said(history: list = None) -> bool:
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if claims_library_missing_steps(message.get("content") or ""):
            return True
    return False


def limit_library_miss_mentions(reply: str, history: list = None) -> str:
    """Keep one library-coverage sentence on the first turn that says it, and none after that."""
    if not reply or not claims_library_missing_steps(reply):
        return reply or ""
    if library_miss_already_said(history):
        return strip_library_no_steps(reply)
    kept = []
    seen = False
    for part in _reply_sentences(reply):
        if claims_library_missing_steps(part):
            if seen:
                continue
            seen = True
        kept.append(part)
    return " ".join(kept).strip()


def reply_names_ground_control_calibration(reply: str) -> bool:
    t = _norm(reply)
    manual = "manual level" in t
    zero = "zero-point" in t or "zero point" in t
    return bool(manual and zero)


def reply_has_zero_point_steps(reply: str) -> bool:
    """True when the reply gives the Electric Leveling button sequence, not only the opener."""
    t = _norm(reply)
    front = bool(re.search(r"\bfront\b.{0,48}\b(?:five|5)\b|\b(?:five|5)\b.{0,24}\bfront\b", t))
    rear = bool(re.search(r"\brear\b.{0,48}\b(?:five|5)\b|\b(?:five|5)\b.{0,24}\brear\b", t))
    enter = bool(re.search(r"\benter\b", t))
    return bool(front and rear and enter)


_GC_DRIFT_RE = re.compile(
    r"\bharness\b|\bsensor swap\b|\blevel sensor\b|"
    r"\b(?:replace|swap|swapping)\b.{0,24}\bsensor\b",
    re.I,
)
_GC_DRIFT_NEG_RE = re.compile(r"\b(do not|don't|dont|never)\b", re.I)
_ZP_REPEAT_RE = re.compile(
    r"press and release|five times|manual level|turn the touch pad off|"
    r"enter to set|zero point calibration|run the jacks|stability check|"
    r"run manual level, then zero-point",
    re.I,
)


def _gc_drift_sentence(part: str) -> bool:
    if _GC_DRIFT_NEG_RE.search(part or ""):
        return False
    return bool(_GC_DRIFT_RE.search(part or ""))


def _drop_gc_drift_sentences(reply: str) -> str:
    kept = [part for part in _reply_sentences(reply) if not _gc_drift_sentence(part)]
    return " ".join(kept).strip()


def _history_has_zero_point_steps(history: list = None) -> bool:
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if reply_has_zero_point_steps(message.get("content") or ""):
            return True
    return False


def _strip_repeated_zero_point(reply: str) -> str:
    text = (reply or "").strip()
    lead = GROUND_CONTROL_LEVEL_LINE.strip()
    if text.startswith(lead):
        text = text[len(lead):].strip()
    kept = []
    for part in _reply_sentences(text):
        if _ZP_REPEAT_RE.search(part):
            continue
        if part.strip() == "📖 Source: Lippert Internal Tech Support – Electric Leveling Systems (Ground Control TT/2.0/3.0)":
            continue
        kept.append(part)
    return " ".join(kept).strip()


def claims_library_missing_ground_control(reply: str) -> bool:
    t = _norm(reply)
    return bool(
        re.search(
            r"(library|manual|document).{0,70}(no|not|without|lack|missing).{0,40}"
            r"(ground control|electric leveling)|"
            r"(no|not any|don't have|do not have|doesn't have|does not have).{0,40}"
            r"(ground control|electric leveling)",
            t,
        )
    )


def _gc_plugs_reported(history: list = None) -> bool:
    parts = []
    for message in history or []:
        if (message.get("role") or "") == "user":
            parts.append(message.get("content") or "")
    blob = _norm(" ".join(parts))
    return bool(
        re.search(
            r"\b(?:plugs?|connectors?)\b.{0,48}\b(?:seated|tight|connected|good)\b|"
            r"\b(?:seated|tight)\b.{0,48}\b(?:plugs?|connectors?)\b",
            blob,
        )
    )


def _gc_plugs_already_asked(history: list = None) -> bool:
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if "plugs are seated" in _norm(message.get("content") or ""):
            return True
    return False


def ensure_ground_control_level_path(reply: str, history: list = None) -> str:
    """
    Ask whether the plugs are seated before the zero-point sequence.
    Once that ask has shipped, the next turn is the manual-level sequence.
    A later turn does not get that sequence again, and a harness or sensor swap does not replace it.
    """
    cleaned = _drop_gc_drift_sentences(strip_library_no_steps(reply or ""))
    if not _history_has_zero_point_steps(history) and not _gc_plugs_reported(history):
        if _gc_plugs_already_asked(history):
            return GROUND_CONTROL_LEVEL_LINE
        return GROUND_CONTROL_PROVE_LINE
    if _history_has_zero_point_steps(history):
        cleaned = _strip_repeated_zero_point(cleaned)
        if not cleaned:
            return GROUND_CONTROL_STAY_LINE
        return cleaned
    if reply_has_zero_point_steps(cleaned) and not claims_library_missing_ground_control(cleaned):
        return cleaned
    return GROUND_CONTROL_LEVEL_LINE


def dometic_bypass_facts(history: list = None, latest_msg: str = "") -> dict:
    parts = []
    for m in history or []:
        if (m.get("role") or "") == "user":
            parts.append(m.get("content") or "")
    if latest_msg:
        parts.append(latest_msg)
    blob = _norm(" ".join(parts))
    facts = {}
    if (
        "peacemaker" in blob
        and "bypass" in blob
        and re.search(r"\bcool", blob)
    ):
        facts["dometic_unit_bypass"] = "cools"
    ceiling_named = bool(
        re.search(r"selector|thermostat", blob)
        or "ceiling controls" in blob
        or "bypassing the ceiling" in blob
    )
    if (
        "ceiling" in blob
        and ceiling_named
        and "bypass" in blob
        and re.search(r"\bcool", blob)
    ):
        facts["dometic_ceiling_bypass"] = "cools"
    if re.search(r"\bfan\b", blob) and re.search(
        r"\b(?:runs?|running|operates|operating)\b", blob
    ):
        facts["dometic_fan"] = "runs"
    return facts


def dometic_nocoool_open_line(facts: dict | None = None) -> str:
    """Fan already running starts at the Peacemaker. Otherwise confirm the fan first."""
    if (facts or {}).get("dometic_fan") == "runs":
        return DOMETIC_NOCOOL_OPEN
    return DOMETIC_NOCOOL_CONFIRM_FAN


def _dometic_reply_has_bypass_path(reply: str) -> bool:
    low = _norm(reply)
    if "peacemaker" in low and not re.search(r"\b(clean|replace|check) the filter\b", low):
        return True
    return bool("3311071" in (reply or "") and "peacemaker" in low)


def _history_has_dometic_bypass(history: list = None) -> bool:
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if _dometic_reply_has_bypass_path(message.get("content") or ""):
            return True
    return False


def _dometic_reply_restarts_filter(reply: str) -> bool:
    text = reply or ""
    if not text.strip() or claims_library_missing_steps(text):
        return True
    return bool(re.search(r"\bfilters?\b", text, re.I))


def ensure_dometic_ceiling_thermostat(
    reply: str,
    facts: dict | None = None,
    history: list = None,
) -> str:
    """
    Turn 1 with no fan fact confirms the fan runs, then the 3311071 Peacemaker bypass.
    A stated running fan starts at that bypass. Both bypasses cooling replaces the
    ceiling thermostat/selector. A later turn keeps a real follow-up.
    """
    facts = facts or {}
    text = reply or ""
    open_line = dometic_nocoool_open_line(facts)
    if (
        facts.get("dometic_unit_bypass") == "cools"
        and facts.get("dometic_ceiling_bypass") == "cools"
    ):
        low = _norm(text)
        if "replace the ceiling thermostat" in low and "filter" not in low:
            return limit_library_miss_mentions(text, history)
        return DOMETIC_CEILING_LINE
    if _dometic_reply_has_bypass_path(text) and not re.search(
        r"\b(clean|replace|check) the filter\b", text, re.I
    ):
        return limit_library_miss_mentions(text, history)
    if _history_has_dometic_bypass(history) and not _dometic_reply_restarts_filter(text):
        return limit_library_miss_mentions(text, history)
    return open_line


def is_suburban_furnace_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Suburban furnace, including NT-20SEQT. Cooktops lose."""
    if is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return False
    if is_cooktop_range_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if re.search(r"\bnt[\s-]*20", blob):
        return True
    if "furnace" in blob and ("suburban" in blob or "nt-20" in blob or "nt20" in blob):
        return True
    if "furnace" in _norm(category_name) and "suburban" in blob:
        return True
    return False


def _chat_user_blob(history: list = None, latest_msg: str = "") -> str:
    parts = []
    for m in history or []:
        if (m.get("role") or "") == "user":
            parts.append(m.get("content") or "")
    if latest_msg:
        parts.append(latest_msg)
    return " ".join(parts)


def furnace_rw_jumper_ran(text: str) -> bool:
    """R/W jumper, or a thermostat bypass at the furnace, and the furnace runs."""
    t = _norm(text)
    jumper = bool(
        re.search(
            r"\br\s*/\s*w\b|\br\s+and\s+w\b|"
            r"thermostat bypassed|bypassed at the furnace|\bjumped\b",
            t,
        )
    )
    ran = bool(
        re.search(
            r"\b(lights?|lit|runs|running|fires|fired|ignites|ignited|operates|operating)\b",
            t,
        )
    )
    return bool(jumper and ran)


def asks_what_is_the_repair(text: str) -> bool:
    return bool(re.search(r"what is the repair|what'?s the repair", _norm(text)))


def asks_what_next(text: str) -> bool:
    return bool(
        re.search(
            r"what do you recommend|recommend next|what(?:'s| is) the next|what should i do next",
            _norm(text),
        )
    )


_REPEATED_CHECK_RES = (
    ("filter", re.compile(r"\bfilters?\b", re.I)),
    ("pressures", re.compile(r"\b(?:refrigerant\s+)?pressures?\b", re.I)),
    ("12v", re.compile(r"\b12\s*v(?:dc)?\b", re.I)),
    ("petit", re.compile(r"\bpetit[\s-]*tube\b|\bexhaust\s+vent\b", re.I)),
)


def _last_assistant_text(history: list = None) -> str:
    for message in reversed(history or []):
        if (message.get("role") or "") != "assistant":
            continue
        text = (message.get("content") or "").strip()
        if text:
            return text
    return ""


def _reply_asks_check(text: str, pattern: re.Pattern) -> bool:
    """True when a sentence asks for this check. A 'do not' sentence does not."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
        if re.search(r"\b(?:do not|don't|dont|never)\b", sentence, re.I):
            continue
        if not pattern.search(sentence):
            continue
        if re.search(r"\?|\b(?:check|inspect|read|measure|confirm|pull|verify|look)\b", sentence, re.I):
            return True
    return False


def _is_fallback_question(text: str) -> bool:
    blob = text or ""
    if asks_what_is_the_repair(blob) or asks_what_next(blob):
        return True
    return bool(re.search(r"\bnot checked yet\b", _norm(blob)))


_LEAKED_GUARD_RE = re.compile(
    r"that check was already asked\.?\s*"
    r"(?:use the facts already reported and give the next repair\.?)?",
    re.I,
)
_META_QUESTION_RE = re.compile(
    r"[^.?!]*(?:does the coach have any other symptoms|pivot to a different check|"
    r"any other symptoms|does the unit have a thermocouple or flame sensor)[^.?!]*[.?!]?",
    re.I,
)
_COOKTOP_GUARD_RE = re.compile(
    r"^(?:before condemning the thermocouple\b|"
    r"\d+\.\s*(?:confirm the flame is present|remove the pan|check the thermocouple position)\b)",
    re.I,
)
_CLAIM_STOP = frozenset(
    "the a an and or of to for with on in is are was were that this it its then so if when "
    "your you we but not".split()
)
_FALLBACK_ACK_RE = re.compile(
    r"^(?:noted|heard)\s*:\s*"
    r"(?:what is the repair\??|what'?s the repair\??|"
    r"not checked yet[^.?!]*[.?!]?|"
    r"what do you recommend(?: next)?\??)\s*",
    re.I,
)


def _split_reply_sentences(text: str) -> list[str]:
    protected = re.sub(
        r"\b(Figs?|Fig)\.(?=\s*\d)",
        lambda match: match.group(1) + "\x00",
        text or "",
    )
    protected = re.sub(
        r"(^|\s)(\d{1,2})\.\s+(?=[A-Za-z])",
        lambda match: f"{match.group(1)}{match.group(2)}\x00 ",
        protected,
    )
    parts = re.split(r"(?<=[.!?])\s+|\n+", protected)
    return [part.replace("\x00", ".").strip() for part in parts if part.strip()]


def _sentence_key(sentence: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _norm(sentence)).strip()


def _user_blob(history: list = None, latest_msg: str = "") -> str:
    parts = []
    for message in history or []:
        if (message.get("role") or "") == "user":
            parts.append(message.get("content") or "")
    parts.append(latest_msg or "")
    return _norm(" ".join(parts))


def _prior_sentence_keys(history: list = None) -> set[str]:
    keys = set()
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        for sentence in _split_reply_sentences(message.get("content") or ""):
            key = _sentence_key(sentence)
            if len(key) >= 30:
                keys.add(key)
    return keys


def _fresh_line(line: str, history: list = None) -> str:
    if _sentence_key(line) in _prior_sentence_keys(history):
        return ""
    return line


def _repair_from_chat(history: list = None, latest_msg: str = "", prior_text: str = "") -> str:
    """A real next repair from facts the tech reported. Never an instruction to the model."""
    blob = _user_blob(history, latest_msg)
    prior = _norm(prior_text)
    options = []
    if re.search(r"\b0\s*v\b.{0,80}\b(?:tongue|panel)\b", blob):
        options.append("Replace the soft-touch user panel (part 20300427).")
    if re.search(r"\btubing is clear\b", blob) and re.search(r"\be\s*8\b|\bgirard\b|\bpetit\b", blob):
        options.append(
            "With the blower running, confirm suction at the sensing tube and report the result."
        )
    if re.search(r"\bpan\b", blob) and re.search(
        r"\b(?:shut off|shuts off|goes out|flameout|flame out)\b", blob
    ):
        options.append(
            "Reposition the thermocouple tip in the flame with the pan on. That is the repair."
        )
    if re.search(r"\b(?:rear|back)\s*wall\b", blob) and re.search(r"\bice\b", blob):
        if re.search(r"\b(?:frost|ice|icing)\s+return", blob):
            options.append("Replace the cooling unit.")
        elif not re.search(r"\b4\s*(?:-|to)\s*5\b", prior):
            options.append("Turn the thermostat dial to 4-5 and recheck the rear wall for ice.")
        else:
            options.append("Report whether the rear-wall ice starts to melt after that overnight wait.")
    if re.search(r"\bfact\s*12\b", blob) and re.search(r"\be\s*[23]\b", blob):
        if re.search(r"disconnect|not in the evaporator|off the coil|loose|unseated", blob):
            options.append("Reseat the freeze sensor on the evaporator coil and retest.")
        else:
            options.append(
                "Check whether the freeze sensor is fastened on the evaporator coil and report what you find."
            )
    if re.search(r"\b(?:manual crank|psx1|roll pin|stabilizer jack)\b", blob) and not re.search(
        r"\bbal\b|soft[\s-]*touch|tongue", blob
    ):
        if re.search(r"\b(?:broken|seized)\b", blob):
            options.append(
                "Replace the complete front stabilizer jack assembly and retest power and the manual crank."
            )
        else:
            options.append(
                "Does the manual crank turn, and what does the override roll pin or coupler look like?"
            )
    if re.search(r"\b(?:bypass operates|thermostat bypassed|jumped)\b", blob) and re.search(
        r"\bfurnace\b", blob
    ):
        options.append(
            "With the blower running, measure power in and power out at the sail switch. "
            "If power is present in and out, replace the wall thermostat."
        )
    furnace_job = bool(re.search(r"\bfurnace\b|thermostat bypass|sail switch", blob)) and not re.search(
        r"2111|coleman|b57915|cooktop|\bpan\b", blob
    )
    if furnace_job and "wall thermostat" in prior:
        options.append(
            "If the sail switch has power in and power out while the blower runs, replace the wall thermostat."
        )
    if "freeze sensor" in prior and re.search(r"fact\s*12", blob) and not re.search(r"\bfacr\b", blob):
        options.append(
            "If the freeze sensor is loose or off the coil, reseat it and retest. "
            "If it is seated and the code remains, replace the freeze sensor."
        )
    if ("20300427" in prior or "soft-touch user panel" in prior) and re.search(
        r"\b0\s*v\b|no 12\s*v", blob
    ):
        options.append("Replace the soft-touch user panel, part 20300427.")
    if "inverter pcb" in prior:
        options.append("Replace the inverter PCB and the freezer evaporator fan.")
    job = _job_key(history, latest_msg)
    for line in options:
        if not _line_fits_job(line, job):
            continue
        fresh = _fresh_line(line, history)
        if fresh:
            return fresh
    return ""


def _alternate_lines(text: str) -> list[str]:
    """Different wordings for a card that was already sent."""
    low = _norm(text)
    options = (
        ("wall thermostat", "If the sail switch has power in and power out while the blower runs, replace the wall thermostat."),
        ("wall thermostat", "With the blower running, measure power in and power out at the sail switch. If power is present in and out, replace the wall thermostat."),
        ("petit tube", "With the blower running, confirm suction at the sensing tube and report the result."),
        ("petit tube", "The sensing tube is at the blower. Report the suction with the blower running."),
        ("freeze sensor", "Reseat the freeze sensor on the evaporator coil and retest."),
        ("freeze sensor", "Check whether the freeze sensor is fastened on the evaporator coil and report what you find."),
        ("20300427", "Replace the soft-touch user panel, part 20300427."),
        ("20300427", "The soft-touch user panel is the repair. Part 20300427."),
        ("thermocouple", "Reposition the thermocouple tip in the flame with the pan on."),
        ("thermocouple", "Put the thermocouple tip back in the flame with the pan on."),
        ("inverter pcb", "Replace the inverter PCB and the freezer evaporator fan."),
        ("inverter pcb", "The inverter PCB and the freezer evaporator fan are the repair."),
        ("dial", "Dry the cabinet and leave it overnight. Report whether heavy frost returns on the rear wall."),
    )
    return [line for needle, line in options if needle in low]


def _alternate_repair(text: str, history: list = None, latest_msg: str = "") -> str:
    """A different sentence for a card that was already sent."""
    used = {
        _norm(message.get("content") or "")
        for message in history or []
        if (message.get("role") or "") == "assistant"
    }
    for line in _alternate_lines(text):
        if _norm(line) in used:
            continue
        if _fresh_line(line, history):
            return line
    fresh = _repair_from_chat(history, latest_msg, text)
    if fresh and _norm(fresh) not in used and _norm(fresh) != _norm(text):
        return fresh
    return ""


def _drop_repeated_checks(text: str, prev: str, history: list = None, latest_msg: str = "") -> str:
    """Drop a check the previous turn already asked. Keep a repair sentence."""
    kept = []
    dropped = False
    for sentence in _split_reply_sentences(text):
        repeated = False
        for _name, pattern in _REPEATED_CHECK_RES:
            if _reply_asks_check(prev, pattern) and _reply_asks_check(sentence, pattern):
                repeated = True
                break
        if repeated:
            dropped = True
            continue
        kept.append(sentence)
    if not dropped:
        return text
    forward = " ".join(kept).strip()
    actionable = bool(
        re.search(r"\b(?:replace|reposition|align|resecure|reseat|repair|authorize)\b", forward, re.I)
    )
    if not actionable:
        repair = _repair_from_chat(history, latest_msg, text)
        return repair or forward
    return forward


def _scrub_unreported_sentence(sentence: str, user_blob: str) -> str:
    """Drop a claim the tech did not make. Keep a check that is still an instruction."""
    low = _norm(sentence)
    if re.search(r"\bnozzles?\b.{0,48}\breported good\b", low) and not re.search(r"\bnozzles?\b", user_blob):
        return ""
    if re.search(r"\b(?:dial turned down|dial adjusted)\b", low) and not re.search(
        r"\b(?:turned down|turned the dial|adjusted the dial|set the dial|dial adjusted)\b",
        user_blob,
    ):
        return ""
    if re.search(r"\berror remains\b", low) and not re.search(
        r"\berror remains\b|\berror (?:is )?still\b|\bstill (?:shows|showing|on)\b",
        user_blob,
    ):
        return ""
    if re.search(r"\b(?:tip sits low|sits low)\b", low) and not re.search(
        r"\bsits low\b|\btip (?:is )?low\b", user_blob
    ):
        return ""
    if re.search(r"\b(?:no|not) sticky\b", low) and not re.search(
        r"\bsticky\b|low voltage|excess angle", user_blob
    ):
        if not re.search(r"\b(?:confirm|check|if|clear|unless)\b", low):
            return ""
    if re.search(r"\bafter reset\b", low) and not re.search(r"\breset\b", user_blob):
        if re.search(r"\bthaw\b", user_blob):
            return re.sub(r"\bafter reset\b", "after the thaw", sentence, flags=re.I)
        return re.sub(r"\bafter reset\b", "after that", sentence, flags=re.I)
    return sentence


def _claim_words(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-z0-9]+", _norm(text))
        if word not in _CLAIM_STOP and (len(word) > 2 or word.isdigit())
    ]


_ACK_SENTENCE_RE = re.compile(
    r"^(?:noted|heard|you said|you reported|you measured)\b",
    re.I,
)
_STATUS_ASSERTION_RE = re.compile(
    r"\b(?:is|are|was|were|reads?|seems?|looks?)\s+(?:near\s+)?"
    r"(?:good|reported|checked|nominal|ok|okay|passed|failed|clear|aligned|broken|seized)\b"
    r"|\bnear\s+nominal\b"
    r"|\b(?:was|were|been)\s+reported\b"
    r"|\breported\s+(?:good|bad|clear|broken|checked)\b"
    r"|\b(?:after|was|were|been)\s+(?:the\s+)?(?:\w+\s+){0,2}(?:adjustment|adjusted|checked)\b"
    r"|\b(?:goes out|lights but)\b"
    r"|\bstill\s+active\b"
    r"|\baround\s+nominal\b"
    r"|\bcycling\s+around\b"
    r"|\bremains\b"
    r"|\boften too close\b"
    r"|\bfactory tip placement\b",
    re.I,
)
_DO_NOT_RE = re.compile(r"\b(?:do not|don't|dont|never)\b", re.I)
_REPAIR_VERB_RE = re.compile(
    r"\b(?:replace|align|reseat|re-?secures?|reposition|authorize)\b",
    re.I,
)
_FIRM_LEAD_RE = re.compile(
    r"^(?:the repair is to\s+)?(?:replace|reseat|re-?secures?|reposition|authorize)\b",
    re.I,
)
_FILLER_RE = re.compile(
    r"check the reading on this unit(?:\s+and write it down)?\.?",
    re.I,
)
_LIBRARY_MISS_LINE_RE = re.compile(
    r"no .+ document in the shop library for this unit",
    re.I,
)
_BARE_REPAIR_LABEL_RE = re.compile(r"^that is the repair\.?$", re.I)


def _flat_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _norm(text))


def _is_acknowledgement(sentence: str) -> bool:
    """Noted, Heard, and 'you measured' openers are not part of the reply."""
    return bool(_ACK_SENTENCE_RE.match((sentence or "").strip()))


def _is_shop_advice(sentence: str) -> bool:
    return bool(_DO_NOT_RE.search(sentence or ""))


def _assertion_supported(clause: str, user_blob: str) -> bool:
    """True when this status claim is a substring of the tech's messages."""
    claim = _flat_text(clause)
    user = _flat_text(user_blob)
    return bool(claim) and claim in user


def _strip_unreported_assertion(sentence: str, user_blob: str) -> str:
    """Drop a status claim the tech did not say. Shop 'Do not' advice stays."""
    text = (sentence or "").strip()
    if not text or _is_shop_advice(text) or not _STATUS_ASSERTION_RE.search(text):
        return text
    kept = []
    for clause in re.split(r"\s+\bso\b\s+|;\s+", text):
        clause = clause.strip(" ,")
        if not clause:
            continue
        if _STATUS_ASSERTION_RE.search(clause) and not _assertion_supported(clause, user_blob):
            if re.search(
                r"\b(?:replace|align|reseat|re-?secure|check|prove|wait|dry|turn|reposition|bypass)\b",
                clause,
                re.I,
            ):
                trimmed = _STATUS_ASSERTION_RE.sub("", clause)
                trimmed = re.sub(r"\s{2,}", " ", trimmed).strip(" ,;.")
                if trimmed:
                    kept.append(trimmed)
            continue
        kept.append(clause)
    return " ".join(kept).strip(" ,;.")


def _is_repair_sentence(sentence: str) -> bool:
    text = sentence or ""
    if _is_shop_advice(text) or re.search(r"\bmeans\b", text, re.I):
        return False
    return bool(_REPAIR_VERB_RE.search(text))


def _repair_words(sentence: str) -> set[str]:
    text = _norm(sentence)
    text = re.sub(r"re-?secures?", "seat", text)
    text = re.sub(r"\breseats?\b", "seat", text)
    text = re.sub(r"\bthat is the repair\b", "", text)
    text = re.sub(r"^repair stands\b", "", text)
    return set(_claim_words(text))


def _same_repair(left: str, right: str) -> bool:
    words_l = _repair_words(left)
    words_r = _repair_words(right)
    if len(words_l) < 3 or len(words_r) < 3:
        return False
    shorter, longer = (words_l, words_r) if len(words_l) <= len(words_r) else (words_r, words_l)
    return len(shorter & longer) / len(shorter) >= 0.6


def _prior_repair_sentences(history: list = None) -> list[str]:
    found = []
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        for sentence in _split_reply_sentences(message.get("content") or ""):
            if _is_repair_sentence(sentence) or sentence.lower().startswith("repair stands"):
                found.append(sentence)
    return found


def _repair_stands_said(history: list = None) -> bool:
    return "repair stands" in _prior_assistant_text(history).lower()


def _repair_stands_line(history: list = None, sentence: str = "") -> str:
    """One line. Said on a later turn, not as a bare 'That is the repair.'"""
    chosen = ""
    for candidate in _prior_repair_sentences(history) + [sentence]:
        line = re.sub(r"\bthat is the repair\.?", "", candidate or "", flags=re.I)
        line = re.sub(r"^repair stands:\s*", "", line, flags=re.I).strip(" .")
        if line and (not chosen or len(line) < len(chosen)):
            chosen = line
    if not chosen:
        return ""
    return f"Repair stands: {chosen}."


def _loose_sentence_key(sentence: str) -> str:
    text = re.sub(r"\bpart\b", " ", _sentence_key(sentence))
    return re.sub(r"\s+", " ", text).strip()


def _same_as_last_turn(sentence: str, history: list = None) -> bool:
    """No identical sentence on two turns in a row."""
    key = _loose_sentence_key(sentence)
    if not key:
        return False
    for previous in _split_reply_sentences(_last_assistant_text(history)):
        if _loose_sentence_key(previous) == key:
            return True
    return False


def _near_copy(left: str, right: str) -> bool:
    """A sentence that restates the previous turn. Looser overlap is a new step."""
    words_l = set(_claim_words(left))
    words_r = set(_claim_words(right))
    if len(words_l) < 4 or len(words_r) < 4:
        return _loose_sentence_key(left) == _loose_sentence_key(right) and bool(_loose_sentence_key(left))
    shorter = words_l if len(words_l) <= len(words_r) else words_r
    longer = words_r if shorter is words_l else words_l
    # A longer repair sentence is a new step, not a copy of the short ask inside it.
    if len(longer) >= len(shorter) * 1.6:
        return False
    return len(shorter & longer) / len(shorter) >= 0.75


_REPEAT_FAMILY_RE = re.compile(
    r"peacemaker|heavy frost|overnight|replace the cooling unit|fan-motor stall|run capacitor",
    re.I,
)


def _echoes_last_turn(sentence: str, history: list = None) -> bool:
    """True when a Coleman or ice sentence restates the previous turn."""
    if not sentence or sentence.startswith("📖"):
        return False
    if not _REPEAT_FAMILY_RE.search(sentence):
        return False
    for previous in _split_reply_sentences(_last_assistant_text(history)):
        if previous.startswith("📖"):
            continue
        if _near_copy(sentence, previous):
            return True
    return False


def _is_library_miss_line(text: str) -> bool:
    return bool(_LIBRARY_MISS_LINE_RE.search(text or ""))


def _reply_has_body(text: str) -> bool:
    if _is_library_miss_line(text):
        return True
    if _has_shop_step(text):
        return True
    return bool(re.search(r"\brepair stands\b|\brepair is unchanged\b", text or "", re.I))


def _prior_assistant_text(history: list = None) -> str:
    return " ".join(
        message.get("content") or ""
        for message in history or []
        if (message.get("role") or "") == "assistant"
    )


def _overlaps_prior(sentence: str, history: list = None) -> bool:
    """True when this sentence repeats a step the coach already gave."""
    prior = _prior_assistant_text(history)
    if not prior or not sentence:
        return False
    if re.search(r"\b4\s*(?:-|to)\s*5\b", sentence, re.I) and re.search(
        r"\b4\s*(?:-|to)\s*5\b", prior, re.I
    ):
        return True
    return False


def _has_shop_step(text: str) -> bool:
    body = "\n".join(
        line for line in (text or "").splitlines() if not line.strip().startswith("📖")
    )
    body = re.sub(r"\bthat is the repair\.?", "", body, flags=re.I)
    if len(body.strip()) < 20:
        return False
    return bool(
        re.search(
            r"\b(?:replace|r&r|authoriz\w*|align|reseat|re-?secure|check|prove|bypass|jumper|confirm|"
            r"measure|read|inspect|remove|wait|reposition|verify|install|turn|set|dry|write|"
            r"fasten|put|seat)\b",
            body,
            re.I,
        )
    )


_HEARD_CLAUSE_RE = re.compile(
    r"(?:^|\n|\s)(?:noted|heard)\s*:\s*.*?(?=(?:\s[A-Z📖])|(?:[.?!](?:\s|$))|$)",
    re.I,
)
_INTERNAL_LEAK_RE = re.compile(
    r"skip\s+ccd-|"
    r"cites for this prove|"
    r"watch/replace only|"
    r"write the reading on the sheet|"
    r"ask a manager before|"
    r"not in the shop library|"
    r"do not replace the full 2111|"
    r"closest reference|"
    r"tech adaptation|"
    r"\bdo not lead with\b|"
    r"\bdo not start on the filter\b|"
    r"\bdo not open the 15\s*a\b|"
    r"\bdo not replace the control board\b|"
    r"\bdo not swap (?:the level up controller|a level sensor)\b|"
    r"\bdo not replace a harness\b|"
    r"moisture path, not a|"
    r"\(ocr\)|"
    r"\brepair stands\b|"
    r"the repair is unchanged|"
    r"fixes this exact symptom",
    re.I,
)
_FILENAME_RE = re.compile(r"\b[A-Z][A-Za-z0-9]+(?:-[A-Za-z0-9]+){2,}\b")
_SENSOR_LOOSE_RE = re.compile(
    r"disconnect|not in the evaporator|off the coil|loose|unseated",
    re.I,
)


def _strip_heard_clauses(text: str) -> str:
    """Drop Heard/Noted echoes, including one glued onto a source line."""
    cleaned = _HEARD_CLAUSE_RE.sub(" ", text or "")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def _too_similar(left: str, right: str) -> bool:
    words_l = set(_claim_words(left))
    words_r = set(_claim_words(right))
    if len(words_l) < 3 or len(words_r) < 3:
        return _loose_sentence_key(left) == _loose_sentence_key(right) and bool(_loose_sentence_key(left))
    shorter = words_l if len(words_l) <= len(words_r) else words_r
    longer = words_r if shorter is words_l else words_l
    return len(shorter & longer) / len(shorter) >= 0.6


def _context_blob(history: list = None, latest_msg: str = "") -> str:
    """User words plus earlier coach lines, so a later turn still knows the job."""
    return _norm(_prior_assistant_text(history) + " " + _user_blob(history, latest_msg))


def _give_repair_now(latest_msg: str = "", history: list = None) -> bool:
    """The tech asked for the repair, or said the check is not done yet."""
    if not _last_assistant_text(history):
        return False
    return bool(asks_what_is_the_repair(latest_msg) or _is_fallback_question(latest_msg))


def _job_key(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """The open job from category, model, and the tech's words.

    Coach sentences are not part of the complaint. A later case in the same
    process cannot inherit a furnace or jack repair from an earlier chat.
    """
    symptom = _user_blob(history, latest_msg)
    cat = category_name or ""
    model = model_text or ""
    ident = _norm(f"{cat} {model}")
    cat_n = _norm(cat)
    # The dropdown names the unit. Earlier chats in the same session do not.
    if _THETFORD_UNIT_RE.search(ident):
        return "thetford"
    if re.search(r"b57915|3311071", ident):
        return "dometic"
    if re.search(r"fact\s*12", ident):
        return "fact12"
    if re.search(r"2111|coleman", ident):
        return "coleman"
    if re.search(r"facr", ident):
        return "facr"
    if "343633" in ident or "ground control" in ident:
        return "ground"
    if re.search(r"807662|level[\s-]*up", ident):
        if is_level_up_lead_jack_drift_context(cat, model, symptom):
            return "leadjack"
        return "levelup"
    if re.search(r"\bbal\b|soft[\s-]*touch", ident):
        return "bal"
    if re.search(r"gswh|girard", ident):
        return "girard"
    if "cooktop" in cat_n or re.search(r"\brange", cat_n) or re.search(r"\bsdn\s*2", ident):
        return "cooktop"
    if "furnace" in cat_n or re.search(r"\bnt[\s-]*20", ident):
        return "furnace"
    # No dropdown. The tech's own words name the job. Coach lines do not.
    user = symptom
    if _THETFORD_UNIT_RE.search(user) or re.search(r"flush\s+lever", user or "", re.I):
        return "thetford"
    if re.search(r"2111|coleman", user):
        return "coleman"
    if re.search(r"\bbal\b|soft[\s-]*touch|20300427", user) or (
        "tongue" in user and re.search(r"\b0\s*v\b|\bdead\b|panel", user)
    ):
        return "bal"
    if re.search(r"fact\s*12", user) or (
        "freeze sensor" in user and re.search(r"\be\s*[23]\b", user)
    ):
        if not re.search(r"interior leak|water leaking|condensate", user):
            return "fact12"
    if re.search(r"facr\d|interior leak|water leaking|condensate", user):
        return "facr"
    if re.search(r"\be\s*8\b", user) and re.search(r"girard|gswh|petit|water heater", user):
        return "girard"
    if re.search(r"\bpan\b", user) and re.search(r"shut off|shuts off|goes out", user):
        return "cooktop"
    if re.search(r"b57915|3311071|will not blow cold|ceiling thermostat", user):
        return "dometic"
    if re.search(r"ground control|343633|zero[\s-]*point|auto-level", user):
        return "ground"
    if re.search(r"807662|level[\s-]*up|firefly", user):
        if is_level_up_lead_jack_drift_context(cat, model, user):
            return "leadjack"
        return "levelup"
    if re.search(r"\be\s*2\b|fan fault|2[\s-]*flash", user) and re.search(r"inverter|f\+|fcr", user):
        return "e2"
    if re.search(r"\b(?:rear|back)[\s-]*wall\b", user) and re.search(r"\b(?:ice|icing|frost)\b", user):
        return "ice"
    if re.search(r"\bdial\b", user) and re.search(r"\bcompressor\b", user) and re.search(r"\boff\b", user):
        return "dial"
    if re.search(r"\bfurnace\b|sail switch|thermostat bypass", user) and not re.search(
        r"2111|coleman", user
    ):
        return "furnace"
    if re.search(r"stabilizer jack|psx1|roll pin|manual crank", user) and not re.search(
        r"\bbal\b|soft[\s-]*touch|tongue", user
    ):
        return "stab"
    if re.search(r"drain is clear", user):
        return "facr"
    if is_bal_soft_touch_tongue_only_context(cat, model, symptom):
        return "bal"
    if is_facr_rooftop_freeze_context(cat, model, symptom):
        return "facr"
    if is_coleman_2111_context(cat, model, symptom):
        return "coleman"
    if is_fcr_dial_off_compressor_run_context(cat, model, symptom):
        return "dial"
    if is_fcr_e2_fan_fault_context(cat, model, symptom):
        return "e2"
    if is_fridge_ice_moisture_context(cat, model, symptom):
        return "ice"
    if is_cooktop_pan_on_flameout_context(cat, model, symptom) or is_cooktop_tip_sheet_context(
        cat, model, symptom
    ):
        return "cooktop"
    if is_stabilizer_override_pin_context(cat, model, symptom):
        return "stab"
    if is_ground_control_context(cat, model, symptom):
        return "ground"
    if is_level_up_lead_jack_drift_context(cat, model, symptom):
        return "leadjack"
    if (
        is_firefly_can_path_context(cat, model, symptom)
        or is_level_up_manual_dump_context(cat, model, symptom)
        or is_level_up_advantage_context(cat, model, symptom)
    ):
        return "levelup"
    if is_dometic_b57915_nocoool_context(cat, model, symptom) or is_dometic_ceiling_sheet_context(
        cat, model, symptom
    ):
        return "dometic"
    if is_suburban_furnace_context(cat, model, symptom):
        return "furnace"
    if is_girard_petit_tube_context(cat, model, symptom):
        return "girard"
    fact_model = model if re.search(r"fact\s*12", _norm(model)) else symptom
    if is_fact12_freeze_code_context(cat, fact_model, symptom):
        return "fact12"
    return ""


_JOB_CITE = {
    "facr": "📖 Source: Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990",
    "coleman": (
        "📖 Source: Coleman-Mach rooftop service manual; "
        "1976-536 and 1976-603; SkillAbove Peacemaker; 1976-695"
    ),
    "dial": "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 31",
    "e2": "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 27",
    "ice": "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36",
    "cooktop": "📖 Source: Suburban Range/Cooktops service manual - page 4",
    "stab": "📖 Source: Lippert PSX1 CCD-0007345, page 7",
    "ground": (
        "📖 Source: Lippert Internal Tech Support – Electric Leveling Systems "
        "(Ground Control TT/2.0/3.0)"
    ),
    "levelup": "📖 Source: Lippert TI-005 Electronic Leveling Troubleshooting Guide, page 1",
    "leadjack": "📖 Source: Lippert TI-005 Electronic Leveling Troubleshooting Guide, page 3",
    "dometic": "📖 Source: Dometic Brisk II, page 23",
    "furnace": "📖 Source: Suburban Furnace Service and Training Manual",
    "girard": "📖 Source: Girard tankless water heater service manual CCD-0009390, page 23",
    "fact12": "📖 Source: Furrion Chill FACR08 8K manual CCD-0008666, page 5",
    "bal": "📖 Source: BAL SS 5.1 Stabilizing System INS.STA.001",
    "thetford": "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
}

# A phrase may appear only on its own job. Assistant text from another case does not unlock it.
_OWNED_PHRASES = (
    ("sail switch", "furnace"),
    ("replace the wall thermostat", "furnace"),
    ("front stabilizer jack", "stab"),
    ("20300427", "bal"),
    ("soft-touch user panel", "bal"),
    ("ceiling thermostat", "dometic"),
    ("thermocouple tip", "cooktop"),
    ("zero-point", "ground"),
    ("zero point", "ground"),
    ("firefly cable", "levelup"),
    ("rubber-boot", "levelup"),
    ("177094", "leadjack"),
    ("cartridge valve", "leadjack"),
    ("gray wire", "leadjack"),
    ("inverter pcb", "e2"),
    ("freezer evaporator fan", "e2"),
    ("spark-free thermostat", "dial"),
    ("replace the cooling unit", "ice"),
    ("rooftop assembly", "facr"),
    ("sensing tube", "girard"),
    ("air pressure switch", "girard"),
    ("air-pressure switch", "girard"),
)

_PLACEHOLDER_RE = re.compile(
    r"take the next check on this job|"
    r"check the first step on this job|"
    r"measure the open check|"
    r"write the open reading|"
    r"write reading \d+|"
    r"replace the part that check names|"
    r"replace the failed part",
    re.I,
)
_BROKEN_SENTENCE_RE = re.compile(
    r"\d+\.\s+\d+\.|"
    r"\b(?:pin|coupler)\s+or\s+seized\b|"
    r"\band the code\s*,|"
    r"\band e\s*2\s*,|"
    r"interior leak\s*,",
    re.I,
)


def _chunk_fields(chunk) -> tuple:
    if isinstance(chunk, dict):
        return (
            chunk.get("title") or "",
            chunk.get("keywords") or "",
            chunk.get("excerpt") or chunk.get("chunk_text") or "",
            chunk.get("file_path") or "",
        )
    return (
        getattr(chunk, "title", "") or "",
        getattr(chunk, "keywords", "") or "",
        getattr(chunk, "chunk_text", "") or "",
        getattr(chunk, "_lookup_file_path", "") or getattr(chunk, "file_path", "") or "",
    )


def _unmatched_unit_line(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """Miss line for a typed unit that has no job lock and no same-brand cite yet."""
    job = _job_key(history, latest_msg, category_name, model_text)
    if job and job != "thetford":
        return ""
    symptom = _user_blob(history, latest_msg)
    brand = library_miss_brand_label(category_name, model_text, symptom)
    if not brand:
        return ""
    prior = _prior_assistant_text(history)
    if "📖" in prior and brand.lower() in _norm(prior):
        return ""
    return library_miss_shop_line(brand)


def library_miss_reply_for_turn(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
    chunks=None,
) -> str:
    """
    Shop line when this turn's library pages are not the typed unit.

    A known job (furnace, fridge, leveling, and the rest) still uses its own
    prove. An empty job does not borrow another brand's excerpts.
    """
    job = _job_key(history, latest_msg, category_name, model_text)
    if job and job != "thetford":
        return ""
    symptom = symptom or _user_blob(history, latest_msg)
    brand = library_miss_brand_label(category_name, model_text, symptom)
    if not brand:
        return ""
    asked = set(asked_brands_for_lookup(category_name, model_text, symptom))
    if brand == "Thetford" or is_toilet_job(category_name, model_text, symptom):
        if not asked or asked == {"thetford"} or "thetford" in asked:
            asked = set(asked) | {"thetford"}
        elif not asked:
            asked = {"thetford"}
    if not asked:
        return ""
    for chunk in chunks or []:
        title, keywords, excerpt, file_path = _chunk_fields(chunk)
        if chunk_matches_asked_brand(
            title, keywords, excerpt, asked, file_path=file_path
        ):
            return ""
    return library_miss_shop_line(brand)


def _line_fits_job(text: str, job: str) -> bool:
    low = _norm(text)
    if (
        not low
        or _PLACEHOLDER_RE.search(low)
        or _BROKEN_SENTENCE_RE.search(text or "")
        or _FILLER_RE.search(text or "")
    ):
        return False
    # An unnamed job keeps the draft. It does not borrow another case's repair.
    # The reading filler is already rejected above, including this empty-job path.
    if not job:
        return True
    # A cleared chat is a new case. Coleman-Mach text cannot ride into it.
    if job not in ("coleman", "dometic") and re.search(
        r"\b(?:coleman(?:-mach)?|peacemaker|2111)\b", low
    ):
        return False
    for phrase, owner in _OWNED_PHRASES:
        if phrase in low and job != owner:
            return False
    if "freeze sensor" in low and job not in ("fact12", "facr"):
        return False
    if job == "facr" and re.search(r"replace the freeze sensor", low):
        return False
    return True


def _with_cite(text: str, job: str) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    if "📖" in body or _is_library_miss_line(body):
        return body
    cite = _JOB_CITE.get(job or "")
    if not cite:
        return body
    return body + "\n" + cite


def _sail_answered(blob: str) -> bool:
    """'continuity OK' and 'good' close the sail-switch prove."""
    low = _norm(blob)
    if "sail" not in low:
        return False
    return bool(
        re.search(
            r"sail(?:\s+switch)?(?:\s+\w+){0,4}\s+(?:is\s+)?(?:continuity\s+)?(?:ok|okay|good)|"
            r"continuity\s+(?:is\s+)?(?:ok|okay|good)|"
            r"power in and (?:power )?out",
            low,
        )
    )


def _levelup_firefly_confirmed(blob: str) -> bool:
    """The Firefly cable is already unplugged and Manual Mode holds."""
    low = _norm(blob)
    unplugged = bool(re.search(r"unplugg?ed", low) and "firefly" in low)
    holds = bool(re.search(r"manual mode (?:stays|holds|held|stayed)|mode stays", low))
    return unplugged and holds


def _answered_checks(blob: str) -> set[str]:
    """Checks the tech already reported. A later turn must not ask them again."""
    low = _norm(blob)
    found = set()
    if re.search(r"filter is clean|filters are clean", low):
        found.add("filter")
    if re.search(
        r"\b\d{2,3}\s*/\s*\d{2,3}\b|"
        r"\bpressures?\b.{0,24}\b(?:good|ok|normal|in range|reported)\b",
        low,
    ):
        found.add("pressure")
    if re.search(r"dial (?:is )?at max", low):
        found.add("dial")
    if _sail_answered(low):
        found.add("sail")
    if re.search(r"\d+(?:\.\d+)?\s*v\b", low):
        found.add("voltage")
    if re.search(r"wiring is good|data line is good", low):
        found.add("dataline")
    if "ceiling" in low and "bypass" in low and re.search(r"\bcool", low):
        found.add("ceiling")
    if _levelup_firefly_confirmed(low):
        found.add("can")
    return found


def _sentence_reasks_check(sentence: str, answered: set[str]) -> bool:
    """True when this sentence asks for a check the tech already answered."""
    low = _norm(sentence)
    if not low or not answered:
        return False
    if "filter" in answered and re.search(r"clean it if dirty|won'?t come clean|return air filter", low):
        return True
    if "dial" in answered and re.search(r"\bdial\b", low) and re.search(
        r"maximum|at max|report the setting", low
    ):
        return True
    if "sail" in answered and re.search(r"sail switch", low) and re.search(
        r"measure|prove|power in|report power", low
    ):
        return True
    if "voltage" in answered and re.search(
        r"measure 12\s*v|check (?:the )?12\s*v|12\s*v and the data line", low
    ):
        return True
    if "dataline" in answered and re.search(r"data line", low) and re.search(
        r"check|measure|report", low
    ):
        return True
    if "ceiling" in answered and re.search(r"ceiling", low) and re.search(
        r"bypass|report whether", low
    ):
        return True
    if "can" in answered and re.search(r"unplug", low) and "firefly" in low and re.search(
        r"report|try manual|whether it holds", low
    ):
        return True
    if "pressure" in answered and re.search(
        r"read the refrigerant|connect gauges|check refrigerant pressures|read both gauges",
        low,
    ):
        return True
    return False


def _reply_body(text: str) -> str:
    lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("📖") or stripped.lower().startswith("source:"):
            continue
        lines.append(stripped)
    return _norm(" ".join(lines))


def _repeats_last_body(text: str, history: list = None) -> bool:
    """True when this turn's shop text is the previous turn word for word."""
    prev = _last_assistant_text(history)
    body = _reply_body(text)
    return bool(body) and body == _reply_body(prev)


def _as_repair_statement(sentence: str) -> str:
    """'Reseat it…' becomes 'The repair is to reseat it…', not 'The repair is reseat it…'."""
    chosen = (sentence or "").strip()
    if not chosen.endswith("."):
        chosen += "."
    if re.match(r"(?i)^the repair\b", chosen):
        return chosen
    body = chosen[0].lower() + chosen[1:]
    if body.endswith("."):
        body = body[:-1]
    if not re.match(r"(?i)^to\b", body):
        body = "to " + body
    return "The repair is " + body + "."


def _direct_repair_sentence(sentence: str, job: str, answered: set[str]) -> bool:
    """A firm repair is an imperative, not a check and not an If-sentence."""
    text = (sentence or "").strip()
    if not text or text.startswith("📖") or "?" in text:
        return False
    if re.match(r"(?i)^if\b", text) or re.search(r"\bif\b", text):
        return False
    if not _is_repair_sentence(text) or not _line_fits_job(text, job):
        return False
    if _sentence_reasks_check(text, answered):
        return False
    return True


def _proved_shop_reply(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """The repair itself, once the proving fact is already in the tech's words."""
    job = _job_key(history, latest_msg, category_name, model_text)
    blob = _user_blob(history, latest_msg)
    if job == "furnace" and _sail_answered(blob):
        return FURNACE_WALL_TSTAT_LINE
    if job == "fact12" and _SENSOR_LOOSE_RE.search(blob):
        return FACT12_FREEZE_RESECURE_LINE
    if job == "coleman":
        facts = coleman_facts_from_chat(
            history, latest_msg, f"{category_name or ''} {model_text or ''}"
        )
        if coleman_motor_board_evidence_complete(facts):
            return COLEMAN_MOTOR_BOARD_AUTH_LINE
    if job == "dometic":
        facts = dometic_bypass_facts(history, latest_msg)
        if (
            facts.get("dometic_unit_bypass") == "cools"
            and facts.get("dometic_ceiling_bypass") == "cools"
        ):
            return DOMETIC_CEILING_LINE
    if job == "levelup" and _levelup_firefly_confirmed(blob):
        return LEVELUP_FIREFLY_FIRM_LINE
    if job == "leadjack" and _leadjack_stage(history, latest_msg) == "cartridge":
        return LEADJACK_CARTRIDGE_LINE
    if job == "facr":
        facr_facts = facr_proves_from_chat(history, latest_msg)
        if facr_terminal_path_complete(facr_facts) or facr_pressure_authorizes_rr(facr_facts):
            return facr_pressure_rr_line(facr_facts)
    if job == "ice" and _ice_cooling_unit_ready(blob):
        return ICE_COOLING_UNIT_LINE
    if job == "girard" and _girard_seating_confirmed(blob):
        return GIRARD_SEATING_REPAIR_LINE
    if job == "cooktop" and _cooktop_repair_ready(blob, latest_msg):
        return COOKTOP_TIP_LOW_REPAIR
    return ""


def _firm_repair_reply(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """A replace/reseat already given on THIS job stays the repair.

    An answered check is not restated as that repair, and the sentence is
    'The repair is to <verb>', not 'The repair is <verb>'.
    """
    if not (asks_what_is_the_repair(latest_msg) or _is_fallback_question(latest_msg)):
        return ""
    job = _job_key(history, latest_msg, category_name, model_text)
    answered = _answered_checks(_user_blob(history, latest_msg))
    lead = ""
    other = ""
    sources: list[str] = []
    other_sources: list[str] = []
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        content = message.get("content") or ""
        cites = [line.strip() for line in content.splitlines() if line.strip().startswith("📖")]
        for sentence in _split_reply_sentences(content):
            if not _direct_repair_sentence(sentence, job, answered):
                continue
            text = sentence.strip()
            if _FIRM_LEAD_RE.match(text):
                lead = text
                sources = cites
            else:
                other = text
                other_sources = cites
    chosen = lead or other
    if not lead:
        sources = other_sources
    if not chosen:
        proved = _proved_shop_reply(history, latest_msg, category_name, model_text)
        if not proved:
            return ""
        if not _repeats_last_body(proved, history):
            return proved
        for sentence in _split_reply_sentences(proved):
            if not _FIRM_LEAD_RE.match(sentence.strip()):
                continue
            restated = _as_repair_statement(sentence)
            if not _repeats_last_body(restated, history):
                return restated if "📖" in restated else _with_cite(restated, job)
        return ""
    chosen = _as_repair_statement(chosen)
    if _repeats_last_body(chosen, history):
        bare = re.sub(r"(?i)^the repair is to\s+", "", chosen).strip()
        if bare:
            bare = bare[0].upper() + bare[1:]
            if not _repeats_last_body(bare, history):
                chosen = bare
    if sources:
        chosen += "\n" + "\n".join(sources)
    return chosen


def _conditional_lines(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> list[str]:
    """Next step plus an If-then repair. Two wordings so a repeat can move on."""
    user = _user_blob(history, latest_msg)
    prior = _norm(_prior_assistant_text(history))
    job = _job_key(history, latest_msg, category_name, model_text)
    if job == "coleman":
        return [
            "Do the Peacemaker bypass at the rooftop unit and report whether the compressor runs while the fan stays still.",
            "Measure the fan-motor stall current and the run capacitor. Report both readings.",
            "Measure the run capacitor against its rated microfarad value and report that reading.",
            "If the compressor runs, the fan stays locked, the stall current is about 1.9 A, and the run capacitor is near rated, replace the fan motor and the control board only.",
            "The repair is to replace the fan motor and the control board only.",
        ]
    if job == "facr":
        facr_facts = facr_proves_from_chat(history, latest_msg)
        if facr_terminal_path_complete(facr_facts) or facr_pressure_authorizes_rr(facr_facts):
            return [facr_pressure_rr_line(facr_facts)]
        if facr_facts.get("facr_pressure") == "ok":
            return [_facr_stay_on_prove_line(facr_facts)]
        return _facr_pending_prompts(facr_facts, history)
    if job == "fact12":
        if re.search(r"\be\s*3\b", user + " " + prior):
            return [
                "Measure 12 V and the data line at the connector, and confirm the connector is seated. If 12 V is missing, repair that feed. If the freeze sensor is loose or off the coil, reseat it and retest.",
                "If the data connector is loose, seat it and retest. If the freeze sensor is loose or off the coil, reseat it and retest. If both are good and E3 remains, replace the freeze sensor.",
            ]
        return [
            "Look at the freeze sensor on the evaporator coil. If it is loose or off the coil, reseat it and retest. If it is already seated and the code remains, replace the freeze sensor.",
            "If the freeze sensor is loose or off the coil, reseat it and retest. If it is seated and E2 remains, replace the freeze sensor.",
        ]
    if job == "girard":
        return [
            "With the blower running, confirm suction at the sensing tube. If that tube has no suction, seat the sensing tube at the blower. That seating is the repair.",
            "If the sensing tube at the blower has no suction, seat that tube at the blower and call that the repair.",
            "If blower suction is missing, seat the sensing tube at the blower and treat that as the repair.",
        ]
    if job == "furnace":
        return [
            "With the blower running, measure power in and power out at the sail switch. If power is present in and out, replace the wall thermostat.",
            "If the sail switch has power in and power out while the blower runs, replace the wall thermostat.",
            "If power is present on both sail-switch terminals with the blower running, replace the wall thermostat.",
        ]
    if job == "ground":
        return [
            "Do a manual level, then set zero point. Press FRONT five times, then REAR five times, then press ENTER.",
            "If the plugs are seated, do a manual level. Press FRONT five times, then REAR five times, then ENTER. That calibration is the repair.",
            "Manual level comes before zero point. FRONT five times, REAR five times, ENTER. If the display reads Zero point set successfully, that calibration is the repair.",
        ]
    if job == "stab":
        return [
            "Look at the override roll pin and the coupler. If the pin or coupler is broken or seized, replace the complete front stabilizer jack assembly.",
            "If the override roll pin is broken or seized, replace the complete front stabilizer jack assembly and retest the manual crank.",
        ]
    if job == "ice":
        if _ice_cooling_unit_ready(user):
            return [ICE_COOLING_UNIT_LINE]
        if re.search(r"gasket", user) and re.search(r"seal", user):
            return [
                "Dry the cabinet and leave it overnight. Report whether heavy frost returns on the rear wall.",
                "Replace the cooling unit only after that overnight result is reported.",
            ]
        return [
            "Check the door gasket and report whether it seals.",
            "Check whether the temperature dial is at maximum and report the setting.",
        ]
    if job == "cooktop":
        return [
            "Set a pan on a lit burner and look at the thermocouple tip. If the tip sits low in the flame, reposition the thermocouple tip in the flame.",
            "If the thermocouple tip sits low once a pan is on the burner, reposition the thermocouple tip in the flame.",
        ]
    if job == "dial":
        return [
            "Leave the dial fully OFF and open flag terminals C and T with no jumper. If the compressor stops, replace the Spark-Free Thermostat part G 2021128850.",
            "If the compressor stops with C and T open, replace the Spark-Free Thermostat part G 2021128850.",
        ]
    if job == "dometic":
        return [
            "Bypass the ceiling selector and report whether it cools. If both bypasses cool, replace the ceiling thermostat/selector.",
            "If both bypasses cool, replace the ceiling thermostat/selector.",
        ]
    if job == "bal":
        if re.search(r"\b0\s*v\b|no 12\s*v", user):
            return [
                "No 12V on the tongue jack output wire. Replace the soft-touch user panel 20300427.",
            ]
        if re.search(r"\b12\s*v\b", user) and not re.search(r"\b0\s*v\b|no 12\s*v", user):
            return [
                "12V is present on the tongue jack output wire. Repair the tongue pigtail.",
            ]
        return [
            "Press tongue extend and check for 12V on the tongue jack output wire at the panel. Report that voltage.",
        ]
    if job == "e2":
        return [
            "Check voltage at the F+ and F- terminals on the inverter PCB and report the reading. If the fan voltage is present and E2 or the 2-flash returns, replace the inverter PCB and the freezer evaporator fan.",
            "If the fan voltage cycles and the fault remains, replace the inverter PCB and the freezer evaporator fan.",
        ]
    if job == "levelup":
        return [
            "Leave the rubber-boot terminator in. Unplug only the Firefly cable, try Manual Mode again, and report whether it holds. If Manual Mode holds, call Firefly at 574-825-4600 and update the firmware with a USB stick of 4 GB or smaller.",
            "If Manual Mode still dumps home with the Firefly cable unplugged, stay on the Level Up sensor and harness path.",
        ]
    if job == "leadjack":
        return [_leadjack_shop_line(history, latest_msg)]
    if job == "thetford":
        return [_thetford_shop_line(history, latest_msg)]
    return []


def _pick_fresh_line(lines: list[str], history: list = None) -> str:
    prior = _prior_sentence_keys(history)
    already = {
        _norm(message.get("content") or "")
        for message in history or []
        if (message.get("role") or "") == "assistant"
    }
    for line in lines:
        if not line or _norm(line) in already:
            continue
        sentences = _split_reply_sentences(line) or [line]
        if any(_sentence_key(sentence) in prior for sentence in sentences):
            continue
        if any(_same_as_last_turn(sentence, history) for sentence in sentences):
            continue
        if any(_echoes_last_turn(sentence, history) for sentence in sentences):
            continue
        return line
    return ""


LEADJACK_COIL_LINE = (
    "Test the lead-jack valve coil on the gray wire and report whether it tests good.\n"
    "📖 Source: Lippert CCD-0001750, page 8"
)
LEADJACK_PLUMB_LINE = (
    "Confirm the swap plumbing. The manifold hose goes in the notched port, "
    "the follow-leg hose goes in the non-notched port, and unused ports stay plugged. "
    "Orange extend and black retract hoses must not be reversed. Report what you find.\n"
    "📖 Source: Lippert QR-109, page 3\n"
    "📖 Source: Lippert TI-143, page 2\n"
    "📖 Source: Lippert TI-324, page 2\n"
    "📖 Source: Lippert Level Up FW Owner's Manual, page 13"
)
LEADJACK_OVERRIDE_LINE = (
    "Confirm the manual override screw is backed out and report what you find.\n"
    "📖 Source: Lippert TI-170, page 1"
)
LEADJACK_CARTRIDGE_CITE_TOWABLE = (
    "📖 Source: Lippert Level Up Towable Owner's Manual, page 15"
)
LEADJACK_CARTRIDGE_CITE_FW = "📖 Source: Lippert Level Up FW Owner's Manual, page 18"
LEADJACK_CARTRIDGE_LINE = (
    "Replace the front lead-jack cartridge valve, part 177094. "
    "The parts list calls 177094 the Cartridge Valve, item F.\n"
    + LEADJACK_CARTRIDGE_CITE_TOWABLE
    + "\n"
    + LEADJACK_CARTRIDGE_CITE_FW
    + "\n"
    "📖 Source: Lippert TI-005 Electronic Leveling Troubleshooting Guide, page 3"
)


def _leadjack_coil_good(blob: str) -> bool:
    low = _norm(blob)
    return bool(
        re.search(r"(?:coil|gray wire).{0,48}\b(?:good|ok|okay)\b", low)
        or re.search(r"\b(?:good|ok|okay)\b.{0,32}(?:coil|gray wire)", low)
    )


def _leadjack_plumbing_stated(blob: str) -> bool:
    """The plumbing fact itself. A later turn must not have to say it again."""
    low = _norm(blob)
    if re.search(r"plumbing (?:is |checks? )?(?:correct|good|ok)", low):
        return True
    ports = "notched" in low and (
        "non-notched" in low or "non notched" in low or "follow-leg" in low or "follow leg" in low
    )
    closed = "plugged" in low or "not reversed" in low or ("orange" in low and "black" in low)
    if ports and closed:
        return True
    if re.search(r"plumb\w*.{0,32}\b(?:correct|good|ok|okay|fine|right|confirmed)\b", low):
        if not re.search(
            r"plumb\w*.{0,24}\bnot\b.{0,12}\b(?:correct|good|ok|okay|fine|right|confirmed)\b",
            low,
        ):
            return True
    return bool(re.search(r"\b(?:correct|good|ok|okay|fine|right|confirmed)\b.{0,32}plumb", low))


def _leadjack_ask_slot(text: str) -> str:
    """Which lead-jack fact this assistant line was asking for."""
    low = _norm(text)
    if "notched" in low and "plumb" in low:
        return "plumb"
    if "override" in low:
        return "override"
    if "gray wire" in low or "coil" in low:
        return "coil"
    return ""


def _leadjack_affirmed(text: str) -> bool:
    low = _norm(text)
    if not low or re.search(
        r"\b(?:wrong|isn'?t|is not|not good|not correct|not ok|not okay|not backed)\b",
        low,
    ):
        return False
    return bool(re.search(r"\b(?:yes|correct|confirmed|good|ok|okay|fine|right)\b|\bchecks out\b", low))


def _leadjack_cartridge_already_given(history: list = None) -> bool:
    """The cartridge repair already shipped. Do not walk back to plumbing."""
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if "177094" in (message.get("content") or ""):
            return True
    return False


def _leadjack_answered_slots(history: list = None, latest_msg: str = "") -> set[str]:
    """Facts the tech already closed. A yes after the plumbing ask stays closed.

    'Not checked yet' closes the check that was just asked, so it is not asked again.
    """
    slots: set[str] = set()
    pending = ""

    def _consider(user_text: str, pending_ask: str) -> None:
        if _leadjack_coil_good(user_text):
            slots.add("coil")
        if _leadjack_plumbing_stated(user_text):
            slots.add("plumb")
        if _leadjack_override_out(user_text):
            slots.add("override")
        if pending_ask == "plumb" and _leadjack_affirmed(user_text):
            slots.add("plumb")
        if re.search(r"\b177094\b|cartridge valve", _norm(user_text)):
            slots.add("plumb")
        if pending_ask and re.search(r"\bnot checked yet\b", _norm(user_text)):
            slots.add(pending_ask)

    for message in history or []:
        role = message.get("role") or ""
        content = message.get("content") or ""
        if role == "assistant":
            pending = _leadjack_ask_slot(content) or pending
        elif role == "user":
            _consider(content, pending)
    _consider(latest_msg or "", pending)
    return slots


def _leadjack_plumbing_ok(blob: str, history: list = None, latest_msg: str = "") -> bool:
    if _leadjack_plumbing_stated(blob):
        return True
    return "plumb" in _leadjack_answered_slots(history, latest_msg)


def _leadjack_override_out(blob: str) -> bool:
    low = _norm(blob)
    return bool(
        re.search(r"override screw.{0,40}backed out", low)
        or re.search(r"backed out.{0,40}override", low)
    )


def _leadjack_loose_cartridge(text: str) -> bool:
    """The tech already found a loose cartridge. That fact is the repair."""
    return bool(
        re.search(r"\bloose\b.{0,40}\bcartridge\b|\bcartridge\b.{0,40}\bloose\b", _norm(text))
    )


def _leadjack_stage(history: list = None, latest_msg: str = "") -> str:
    """coil, then plumbing, then the override screw, then the cartridge.

    Answered slots stay answered. A later 'what is the repair?' does not
    open the plumbing question again. Once the cartridge line has shipped,
    the plumbing question does not return. A loose cartridge is that repair.
    """
    if _leadjack_cartridge_already_given(history):
        return "cartridge"
    blob = _user_blob(history, latest_msg)
    if _leadjack_loose_cartridge(blob):
        return "cartridge"
    slots = _leadjack_answered_slots(history, latest_msg)
    if _leadjack_coil_good(blob):
        slots.add("coil")
    if _leadjack_plumbing_stated(blob) or _leadjack_plumbing_ok(blob, history, latest_msg):
        slots.add("plumb")
    if _leadjack_override_out(blob):
        slots.add("override")
    if "coil" not in slots:
        return "coil"
    if "plumb" not in slots:
        return "plumb"
    if "override" not in slots:
        return "override"
    return "cartridge"


def _leadjack_shop_line(history: list = None, latest_msg: str = "") -> str:
    stage = _leadjack_stage(history, latest_msg)
    if stage == "plumb":
        return LEADJACK_PLUMB_LINE
    if stage == "override":
        return LEADJACK_OVERRIDE_LINE
    if stage == "cartridge":
        return LEADJACK_CARTRIDGE_LINE
    return LEADJACK_COIL_LINE


def ensure_level_up_lead_jack_reply(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """Coil, plumbing, and the override screw come before the cartridge."""
    if _job_key(history, latest_msg, category_name, model_text) != "leadjack":
        return reply
    return _leadjack_shop_line(history, latest_msg)


THETFORD_CITE_42088 = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"
THETFORD_SUPPLY_LINE = (
    "Back of the toilet: check the water supply line connection at the water valve. "
    "Secure or tighten it as necessary.\n"
    + THETFORD_CITE_42088
)
THETFORD_VALVE_LINE = (
    "Check whether water valve 42049 weeps at the pedal. "
    "If it weeps, replace it with water valve kit 42109.\n"
    "📖 Source: Thetford Water Valve Service Kit 42109, page 1"
)
THETFORD_VALVE_REPLACE_LINE = (
    "Water valve 42049 weeps at the pedal. Replace it with water valve kit 42109.\n"
    "📖 Source: Thetford Water Valve Service Kit 42109, page 1"
)
THETFORD_VACUUM_LINE = (
    "Check whether the vacuum breaker leaks while flushing. "
    "If it leaks, replace the vacuum breaker or the water module, depending on model.\n"
    "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2"
)
THETFORD_VACUUM_REPLACE_LINE = (
    "The vacuum breaker leaks while flushing. "
    "Replace the vacuum breaker or the water module, depending on model.\n"
    "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2"
)
THETFORD_FLANGE_LINE = (
    "Between the closet flange and the toilet, check the flange nuts. "
    "If the leak continues, check the flange height and replace the flange seal.\n"
    + THETFORD_CITE_42088
)


def _thetford_supply_ok(blob: str) -> bool:
    low = _norm(blob)
    if re.search(r"supply.{0,40}\b(?:tight|secure|secured|dry|good|ok|okay)\b", low):
        return True
    if re.search(r"\b(?:tightened|no leak)\b.{0,40}\b(?:supply|connection)\b", low):
        return True
    if re.search(r"\b(?:supply|connection)\b.{0,48}\b(?:tightened|no leak)\b", low):
        return True
    return bool(re.search(r"no leak (?:there|at the connection|at the supply)", low))


def _thetford_valve_ok(blob: str) -> bool:
    low = _norm(blob)
    return bool(
        re.search(r"does not weep|doesn't weep|do not weep|no weep|not weep", low)
        or re.search(r"valve (?:is |was )?(?:dry|good|ok|okay)", low)
    )


def _thetford_valve_bad(blob: str) -> bool:
    if _thetford_valve_ok(blob):
        return False
    return "weep" in _norm(blob)


def _thetford_vacuum_ok(blob: str) -> bool:
    low = _norm(blob)
    return bool(
        re.search(r"vacuum breaker.{0,40}\b(?:dry|good|ok|okay)\b", low)
        or re.search(r"vacuum breaker.{0,40}(?:no leak|does not leak|doesn't leak)", low)
        or re.search(r"(?:no leak|does not leak).{0,40}vacuum breaker", low)
    )


def _thetford_vacuum_bad(blob: str) -> bool:
    if _thetford_vacuum_ok(blob):
        return False
    low = _norm(blob)
    return bool(
        re.search(r"vacuum breaker.{0,40}\b(?:leak|leaks|leaking)\b", low)
        or re.search(r"\b(?:leak|leaks|leaking)\b.{0,40}vacuum breaker", low)
    )


def _thetford_line_slot(text: str) -> str:
    """Which Thetford check this shop line is asking."""
    low = _norm(text)
    if "flange" in low:
        return "flange"
    if "vacuum breaker" in low:
        return "vacuum"
    if "weep" in low or "pedal" in low:
        return "valve"
    if "supply" in low:
        return "supply"
    return ""


def _thetford_not_checked(text: str) -> bool:
    return bool(re.search(r"\bnot checked yet\b", _norm(text)))


def _thetford_closed_slots(history: list = None, latest_msg: str = "") -> set[str]:
    """Checks already answered, or skipped with 'Not checked yet'.

    A skipped check stays closed. The next reply asks the next one in order.
    """
    slots: set[str] = set()
    pending = ""

    def _consider(user_text: str, pending_ask: str) -> None:
        if _thetford_supply_ok(user_text):
            slots.add("supply")
        if _thetford_valve_ok(user_text) or _thetford_valve_bad(user_text):
            slots.add("valve")
        if _thetford_vacuum_ok(user_text) or _thetford_vacuum_bad(user_text):
            slots.add("vacuum")
        if _thetford_not_checked(user_text) and pending_ask:
            slots.add(pending_ask)

    for message in history or []:
        role = message.get("role") or ""
        content = message.get("content") or ""
        if role == "assistant":
            pending = _thetford_line_slot(content) or pending
        elif role == "user":
            _consider(content, pending)
    _consider(latest_msg or "", pending)
    return slots


def _thetford_stage(history: list = None, latest_msg: str = "") -> str:
    """Supply, then the pedal valve, then the vacuum breaker, then the flange.

    'Not checked yet' closes the check that was just asked and advances.
    A closed check is not asked again.
    """
    blob = _user_blob(history, latest_msg)
    slots = _thetford_closed_slots(history, latest_msg)
    if _thetford_valve_bad(blob):
        return "valve_replace"
    if _thetford_vacuum_bad(blob):
        return "vacuum_replace"
    if "supply" not in slots and not _thetford_supply_ok(blob):
        return "supply"
    if "valve" not in slots and not _thetford_valve_ok(blob):
        return "valve"
    if "vacuum" not in slots and not _thetford_vacuum_ok(blob):
        return "vacuum"
    return "flange"


_PHOTO_CONFIRM_RE = re.compile(
    r"\b(?:photo|picture|sent|attached|yes|done|ok|okay|here)\b",
    re.I,
)


def _thetford_step_confirmed(history: list, latest_msg: str, number: int) -> bool:
    """The tech sent a photo or said yes after this step was shown."""
    seen = False
    for message in history or []:
        role = message.get("role") or ""
        content = message.get("content") or ""
        if role == "assistant" and f"Step {number} of" in content:
            seen = True
            continue
        if seen and role == "user" and _PHOTO_CONFIRM_RE.search(content):
            if re.search(r"\bno\b", content, re.I) and not re.search(r"\b(?:photo|picture)\b", content, re.I):
                continue
            return True
    if seen and _PHOTO_CONFIRM_RE.search(latest_msg or ""):
        if re.search(r"\bno\b", latest_msg or "", re.I) and not re.search(
            r"\b(?:photo|picture)\b", latest_msg or "", re.I
        ):
            return False
        return True
    return False


def _thetford_procedure_turn(history: list, latest_msg: str, kind: str) -> str:
    """One short step. The next step waits for a photo."""
    try:
        import manual_figures as mf

        layout = mf.thetford_kit_layout(kind)
    except Exception:
        return ""
    steps = list(layout.get("steps") or [])
    if not steps:
        return ""
    number = 1
    while number <= len(steps) and _thetford_step_confirmed(history, latest_msg, number):
        number += 1
    if number > len(steps):
        return (
            "The repair procedure is done.\n"
            "Flush the toilet.\n"
            "Look for leaks."
        )
    text = mf.format_one_step(steps[number - 1], number, len(steps))
    already = any(
        f"Step {number} of" in (message.get("content") or "")
        for message in history or []
        if (message.get("role") or "") == "assistant"
    )
    if already:
        text = f"{text}\n{mf.PHOTO_WAIT}"
    if kind == "valve":
        cite = "📖 Source: Thetford Water Valve Kit 42109, page 1"
    else:
        cite = "📖 Source: Thetford Vacuum Breaker Kit 34123/34122, page 2"
    if cite not in text:
        text = f"{text}\n{cite}"
    return text


def _thetford_shop_line(history: list = None, latest_msg: str = "") -> str:
    stage = _thetford_stage(history, latest_msg)
    if stage == "valve":
        return THETFORD_VALVE_LINE
    if stage == "valve_replace":
        return _thetford_procedure_turn(history, latest_msg, "valve") or THETFORD_VALVE_REPLACE_LINE
    if stage == "vacuum":
        return THETFORD_VACUUM_LINE
    if stage == "vacuum_replace":
        return _thetford_procedure_turn(history, latest_msg, "breaker") or THETFORD_VACUUM_REPLACE_LINE
    if stage == "flange":
        return THETFORD_FLANGE_LINE
    return THETFORD_SUPPLY_LINE


def _thetford_source_only(text: str) -> bool:
    """A Thetford cite with no shop step. That is the blank turn."""
    raw = text or ""
    if "📖" not in raw or _reply_has_body(raw):
        return False
    return bool(re.search(r"thetford|42088|42070|42109|34122|34123", raw, re.I))


def _is_thetford_miss_line(text: str) -> bool:
    raw = text or ""
    return bool(_is_library_miss_line(raw) or "no thetford document" in _norm(raw))


def _thetford_cite_ok(line: str) -> bool:
    if not (line or "").strip().startswith("📖"):
        return True
    return bool(re.search(r"thetford|42088|42070|42109|34122|34123", line, re.I))


def _thetford_keep(text: str) -> str:
    """A flush-lever reply does not keep another unit's source line."""
    kept = [line for line in (text or "").splitlines() if _thetford_cite_ok(line)]
    return "\n".join(kept).strip()


def ensure_thetford_flush_reply(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
    original: str = "",
) -> str:
    """A flush-lever leak keeps the next cited check. A bare source line does not ship."""
    if _job_key(history, latest_msg, category_name, model_text) != "thetford":
        return reply
    stage = _thetford_stage(history, latest_msg)
    if stage in ("valve_replace", "vacuum_replace"):
        kind = "valve" if stage == "valve_replace" else "breaker"
        turned = _thetford_procedure_turn(history, latest_msg, kind)
        if turned:
            return turned
    nxt = _thetford_shop_line(history, latest_msg)
    stage = _thetford_stage(history, latest_msg)
    stage_slot = {"valve_replace": "valve", "vacuum_replace": "vacuum"}.get(stage, stage)
    asked = _thetford_line_slot(reply) or _thetford_line_slot(original)
    # A vacuum-breaker draft does not ship while the supply or the water valve is still open.
    if asked and asked != stage_slot:
        return nxt
    if _thetford_not_checked(latest_msg):
        return nxt
    closed = _thetford_closed_slots(history, latest_msg)
    if asked and asked in closed:
        return nxt
    if _thetford_source_only(original) or _thetford_source_only(reply):
        return nxt
    if _is_thetford_miss_line(reply) or _is_thetford_miss_line(original):
        kept = reply if _is_thetford_miss_line(reply) else original
        return _thetford_keep(kept)
    if _reply_has_body(reply) and _line_fits_job(reply, "thetford"):
        return _thetford_keep(reply)
    return nxt


def _prove_lines(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> list[str]:
    """The first ask. The repair waits until the tech answers or asks for it."""
    job = _job_key(history, latest_msg, category_name, model_text)
    if job == "coleman":
        return [
            "Do the Peacemaker bypass at the rooftop unit and report whether the compressor runs while the fan stays still.",
        ]
    if job == "facr":
        return [
            "Check the condensation drain openings and the base pan, and report whether the drain is clear. Read the refrigerant pressures.",
        ]
    if job == "fact12":
        return [
            "Check whether the freeze sensor is fastened on the evaporator coil and report what you find before any repair.",
        ]
    if job == "girard":
        return [
            "E8 is the air pressure switch. Confirm the sensing tube is connected at the blower and report what you find.",
        ]
    if job == "furnace":
        return [
            "Bypass the wall thermostat at the furnace and report whether the furnace operates.",
        ]
    if job == "ground":
        return [
            "Confirm the controller, jack, and touch pad plugs are seated and report whether those plugs are seated.",
        ]
    if job == "stab":
        return [
            "Does the manual crank turn, and what does the override roll pin or coupler look like? Report what you see.",
        ]
    if job == "ice":
        return [
            "Check whether the temperature dial is at maximum and report the setting.",
        ]
    if job == "cooktop":
        return [
            "With a pan on the burner, check the thermocouple tip position in the flame and report what you see.",
        ]
    if job == "dial":
        return [
            "Confirm the dial is fully OFF and report whether the compressor is still running.",
        ]
    if job == "dometic":
        return [
            "Confirm the fan runs, then do the Peacemaker bypass and report whether it cools.",
        ]
    if job == "bal":
        return [
            "Press tongue extend and check for 12V on the tongue jack output wire at the panel. Report that voltage.",
        ]
    if job == "e2":
        return [
            "Check voltage at the F+ and F- terminals on the inverter PCB with power applied and report the reading.",
        ]
    if job == "levelup":
        return [
            "Confirm Auto Level still works. Leave the rubber-boot terminator in, unplug only the Firefly cable, and report whether Manual Mode holds.",
        ]
    if job == "leadjack":
        return [_leadjack_shop_line(history, latest_msg)]
    if job == "thetford":
        return [_thetford_shop_line(history, latest_msg)]
    return []


def _final_shop_line(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """A job-specific line. Never a cross-case repair and never a placeholder."""
    locked = _firm_repair_reply(history, latest_msg, category_name, model_text)
    if locked:
        return locked
    proved = _proved_shop_reply(history, latest_msg, category_name, model_text)
    if proved and not _repeats_last_body(proved, history):
        return proved if "📖" in proved else _with_cite(proved, job)
    job = _job_key(history, latest_msg, category_name, model_text)
    miss = _unmatched_unit_line(history, latest_msg, category_name, model_text)
    if miss:
        return miss
    later = bool(_last_assistant_text(history))
    lines = (
        _conditional_lines(history, latest_msg, category_name, model_text)
        if later or _give_repair_now(latest_msg, history)
        else _prove_lines(history, latest_msg, category_name, model_text)
    )
    answered = _answered_checks(_user_blob(history, latest_msg))
    lines = [
        line
        for line in lines
        if _line_fits_job(line, job) and not _sentence_reasks_check(line, answered)
    ]
    chosen = _pick_fresh_line(lines, history)
    if not chosen:
        prior_keys = _prior_sentence_keys(history)
        for line in lines:
            sentences = _split_reply_sentences(line)
            if (
                line
                and not _repeats_last_body(line, history)
                and not _same_as_last_turn(line, history)
                and not any(_sentence_key(sentence) in prior_keys for sentence in sentences)
                and not any(_echoes_last_turn(sentence, history) for sentence in sentences)
            ):
                chosen = line
                break
    if not chosen:
        if proved and _line_fits_job(proved, job):
            if not _repeats_last_body(proved, history):
                return proved if "📖" in proved else _with_cite(proved, job)
            for sentence in _split_reply_sentences(proved):
                if not _FIRM_LEAD_RE.match(sentence.strip()):
                    continue
                restated = _as_repair_statement(sentence)
                if not _repeats_last_body(restated, history) and _line_fits_job(restated, job):
                    return restated if "📖" in restated else _with_cite(restated, job)
        prior_keys = _prior_sentence_keys(history)
        already = {
            _norm(message.get("content") or "")
            for message in history or []
            if (message.get("role") or "") == "assistant"
        }
        for line in _prove_lines(history, latest_msg, category_name, model_text):
            if not line or not _line_fits_job(line, job):
                continue
            if _sentence_reasks_check(line, answered) or _repeats_last_body(line, history):
                continue
            if _norm(line) in already:
                continue
            if any(_sentence_key(sentence) in prior_keys for sentence in _split_reply_sentences(line)):
                continue
            return _with_cite(line, job)
        return ""
    return _with_cite(chosen, job)


def without_reading_filler(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """The reading filler cannot ship, including when the job has no lock."""
    text = _FILLER_RE.sub(" ", reply or "")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" *\n *", "\n", text).strip(" \n.")
    if text and not _FILLER_RE.search(text):
        return text
    miss = _unmatched_unit_line(history, latest_msg, category_name, model_text)
    if miss and not _FILLER_RE.search(miss):
        return miss
    fallback = _final_shop_line(history, latest_msg, category_name, model_text)
    fallback = _FILLER_RE.sub(" ", fallback or "").strip(" \n.")
    if fallback and not _FILLER_RE.search(fallback):
        return fallback
    return ""


def _strip_source_header(text: str) -> str:
    """A copied excerpt header is not a shop line."""
    kept = []
    for line in (text or "").splitlines():
        if re.search(r"source\s*:\s*\|", line, re.I):
            continue
        if re.search(r"\bmanual\s*:.*\|\s*page\s*:", line, re.I):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _answer_latest(
    history: list = None,
    latest_msg: str = "",
    current: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """The next shop step for this turn. Empty when the draft can stand."""
    job = _job_key(history, latest_msg, category_name, model_text)
    locked = _firm_repair_reply(history, latest_msg, category_name, model_text)
    if locked:
        return locked
    miss = _unmatched_unit_line(history, latest_msg, category_name, model_text)
    if miss:
        return miss
    if _give_repair_now(latest_msg, history):
        fresh = _pick_fresh_line(
            _conditional_lines(history, latest_msg, category_name, model_text), history
        )
        if fresh and _line_fits_job(fresh, job):
            return _with_cite(fresh, job)
    blob = _user_blob(history, latest_msg)
    ctx = _context_blob(history, latest_msg)
    joined = _norm(ctx + " " + (current or ""))
    low = _norm(latest_msg)

    def _open(name: str) -> bool:
        """A named job stays on its own branch. An unnamed chat may use the symptom."""
        return not job or job == name

    if _open("facr") and re.search(r"\bthaw\b", low) and not re.search(r"\d+(?:\.\d+)?\s*v\b", low):
        return (
            "The code returned after the thaw. "
            "Read the refrigerant pressures before any rooftop replacement."
        )
    prior = _norm(_prior_assistant_text(history))
    if _open("fact12") and re.search(r"\be\s*[23]\b", joined) and re.search(
        r"fact\s*12|freeze sensor|ccd-0008666", joined
    ):
        if _SENSOR_LOOSE_RE.search(blob) and not _is_fallback_question(latest_msg):
            return (
                "The freeze sensor is off the coil. "
                "Reseat it on the evaporator coil and retest."
            )
        if re.search(r"\d+(?:\.\d+)?\s*v\b", low) or re.search(r"\d+(?:\.\d+)?\s*v\b", blob):
            return (
                "Those supply readings are in. Check whether the freeze sensor is fastened "
                "on the evaporator coil. Report what you find."
            )
        if _is_fallback_question(latest_msg):
            if re.search(r"\be\s*3\b", joined):
                return (
                    "The E3 check is still open. Measure 12 V and the data line at the connector, "
                    "and report whether the freeze sensor is on the evaporator coil."
                )
            return (
                "The freeze-sensor check is still open. "
                "Report whether it is fastened on the evaporator coil."
            )
        if re.search(r"\be\s*3\b", joined):
            return (
                "FACT12 E3 is the communication path. Measure 12 V and the data line at the connector, "
                "and check whether the freeze sensor is fastened on the evaporator coil. "
                "Report those before any repair."
            )
        return (
            "Check whether the freeze sensor is fastened on the evaporator coil. "
            "Report what you find before any repair."
        )
    if _open("girard") and re.search(r"\be\s*8\b", ctx) and re.search(r"girard|gswh|petit|blower", ctx):
        if re.search(r"tubing is clear|tube is clear", low):
            return (
                "The sensing tube is at the blower for the air pressure switch. "
                "With the blower running, confirm suction at that tube and report the result."
            )
        if _is_fallback_question(latest_msg):
            return (
                "The blower suction check is still open. With the blower running, "
                "report whether the sensing tube at the blower has suction."
            )
        return ""
    if job == "dometic" or (
        _open("dometic")
        and (
            re.search(r"b57915|3311071", blob)
            or (
                re.search(r"will not blow cold|won't blow cold|no cold|not blow cold", blob)
                and re.search(r"dometic|b57915|air conditioning", blob)
            )
        )
    ):
        facts = dometic_bypass_facts(history, latest_msg)
        ceiling = facts.get("dometic_ceiling_bypass") == "cools"
        unit = facts.get("dometic_unit_bypass") == "cools"
        if ceiling and unit:
            return "Both bypasses cool. Replace the ceiling thermostat/selector."
        if unit and not ceiling and re.search(r"cool", low):
            return "The rooftop bypass cools. Bypass the ceiling selector and report whether that also cools."
        return ""
    if _open("ice") and re.search(r"\b(?:rear|back)[\s-]*wall\b", blob) and re.search(r"\b(?:ice|icing|frost)\b", blob):
        if _ice_cooling_unit_ready(blob):
            return "Replace the cooling unit."
        if re.search(r"\b(?:frost|ice|icing)\s+returns?\b", low):
            return "Heavy frost returned. Replace the cooling unit."
        if re.search(r"still cooling|still cools", low):
            return (
                "Dry the cabinet and report the rear wall after the dial has been at 4-5. "
                "Replace the cooling unit only if heavy frost returns after that."
            )
        if re.search(r"still there|still icing|still iced", low):
            return (
                "Dry the cabinet and report the rear wall after overnight. "
                "Replace the cooling unit only if heavy frost returns."
            )
        if _is_fallback_question(latest_msg) and re.search(r"4\s*(?:-|to)\s*5", prior):
            return "Report whether the rear-wall ice starts to melt after the dial has been at 4-5 overnight."
        if re.search(r"gasket", low):
            return "Turn the thermostat dial to 4-5, dry the cabinet, and report the rear wall after overnight."
        if re.search(r"dial (?:is )?at max", low):
            return "Check the door gasket and report whether it seals."
        return ""
    if _open("dial") and re.search(r"\bdial\b", blob) and re.search(r"\bcompressor\b", blob) and re.search(r"\boff\b", blob):
        if re.search(r"compressor stopped|compressor stops", low):
            return (
                "Replace the Spark-Free Thermostat part G 2021128850 (retail C-FCR10DCGTA-007)."
            )
        return ""
    if _open("e2") and re.search(r"\be\s*2\b|2[\s-]*flash|fan fault", blob) and re.search(r"f\+|inverter|fcr", blob):
        if re.search(r"\d+(?:\.\d+)?\s*v\b", low) and not re.search(r"still active|around nominal|cycling around", _norm(current)):
            return ""
        if re.search(r"\d+(?:\.\d+)?\s*v\b", low):
            return "Replace the inverter PCB and the freezer evaporator fan."
        return ""
    if _open("cooktop") and re.search(r"\bpan\b", blob) and re.search(r"shut off|shuts off|goes out", blob):
        if asks_what_is_the_repair(latest_msg) or cooktop_tip_sits_low(blob):
            return "Reposition the thermocouple tip in the flame with the pan on."
        if _is_fallback_question(latest_msg):
            return "Set a pan on a lit burner and report whether the thermocouple tip stays in the flame."
        return ""
    if job == "furnace" or (
        not job and re.search(r"\bfurnace\b|thermostat bypass|sail switch", blob)
    ):
        user_said_sail = bool(re.search(r"\bsail\b", blob))
        if re.search(r"jumper|thermostat bypass|bypassed|jumped red|r\s*/\s*w", blob + " " + ctx):
            if _sail_answered(blob):
                return _with_cite("Replace the wall thermostat.", job)
            if user_said_sail and not _is_fallback_question(latest_msg):
                return ""
            fresh = _pick_fresh_line(
                _conditional_lines(history, latest_msg, category_name, model_text), history
            )
            if fresh:
                return _with_cite(fresh, job)
            return _with_cite(
                "Prove the sail switch with the blower running. "
                "Report power in and power out before any thermostat replacement.",
                job,
            )
        return ""
    if _open("stab") and job != "bal" and re.search(r"stabilizer jack|psx1|roll pin|manual crank", blob):
        user_bits = _user_blob(history, latest_msg)
        if re.search(r"\b(?:broken|seized)\b", user_bits) and not _is_fallback_question(latest_msg):
            return "Replace the complete front stabilizer jack assembly and retest power and the manual crank."
        if re.search(r"\bbroken or seized\b", _norm(current)) or _is_fallback_question(latest_msg) or not prior:
            return "Does the manual crank turn, and what does the override roll pin or coupler look like? Report what you see."
        return ""
    if _open("levelup") and re.search(r"807662|level[\s-]*up|manual mode", blob) and re.search(r"firefly|manual mode", blob):
        if _levelup_firefly_confirmed(blob):
            return LEVELUP_FIREFLY_FIRM_LINE
        if re.search(r"write the reading|ask a manager", _norm(current)):
            return (
                "Confirm power is solid and Auto Level still works. "
                "Unplug only the Firefly cable, try Manual Mode again, and report whether it holds."
            )
        return ""
    if re.search(r"\bthaw\b", low) and not re.search(r"\be\s*2\b|fan fault|f\+", blob):
        return (
            "The code returned after the thaw. "
            "Read the refrigerant pressures before any rooftop replacement."
        )
    return ""


def _is_offline_notice(text: str) -> bool:
    low = (text or "").lower()
    return "ai is offline" in low or low.startswith("error contacting ai")


def _draft_is_bad(
    text: str,
    history: list = None,
    latest_msg: str = "",
    *,
    similar: bool = True,
    category_name: str = "",
    model_text: str = "",
) -> bool:
    low = _norm(text)
    job = _job_key(history, latest_msg, category_name, model_text)
    if _FILLER_RE.search(text or ""):
        return True
    if not _line_fits_job(text, job):
        return True
    if not low or not _reply_has_body(text):
        return True
    if _INTERNAL_LEAK_RE.search(text or ""):
        return True
    if re.search(r"\b(?:heard|noted)\s*:", text or "", re.I):
        return True
    blob = _user_blob(history, latest_msg)
    if re.search(r"\bfact\s*12\b", blob) and re.search(r"nozzle|outer temp", low):
        return True
    if re.search(r"\be\s*8\b", blob) and "burner flame" in low:
        return True
    if (
        re.search(r"\bbroken or seized\b", low)
        and not re.search(r"\b(?:broken|seized)\b", _user_blob(history, latest_msg))
        and not re.search(r"\bif\b", low)
    ):
        return True
    if re.search(r"still cooling|still cools", _norm(latest_msg)) and re.search(r"1 month|replace the unit", low):
        return True
    if "module board" in low or "rear drain" in low or "voltage is missing" in low:
        return True
    if re.search(r"compressor starts|fan stays locked", low) and not re.search(
        r"compressor runs|shaft locked|fan does not rotate", _user_blob(history, latest_msg)
    ):
        return True
    if re.search(r"report the result of that check", low):
        return True
    ctx = _context_blob(history, latest_msg)
    if (
        re.search(r"replace the wall thermostat", low)
        and re.search(r"2111|coleman", ctx)
        and not re.search(r"\bfurnace\b", blob)
    ):
        return True
    if (
        re.search(r"replace the wall thermostat", low)
        and re.search(r"\bfurnace\b", ctx)
        and not re.search(r"\bsail\b", blob)
        and not re.search(r"\bif\b", low)
    ):
        return True
    if (
        re.search(r"\breseat the freeze sensor\b", low)
        and re.search(r"facr", ctx)
        and not re.search(r"fact\s*12", blob)
    ):
        return True
    joined = _norm(ctx + " " + (text or ""))
    if (
        re.search(r"\breseat the freeze sensor\b", low)
        and re.search(r"\be\s*[23]\b", joined)
        and not _SENSOR_LOOSE_RE.search(blob)
        and not re.search(r"\bif\b", low)
    ):
        return True
    answered = _answered_checks(blob)
    if any(_sentence_reasks_check(sentence, answered) for sentence in _split_reply_sentences(text or "")):
        return True
    proved = _proved_shop_reply(history, latest_msg, category_name, model_text)
    if proved and _reply_body(text) == _reply_body(proved):
        return False
    if similar:
        last = _last_assistant_text(history)
        if last and _too_similar(text, last) and not asks_what_is_the_repair(latest_msg):
            return True
    return False


def _next_unused_step(
    history: list = None,
    latest_msg: str = "",
    original: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    job = _job_key(history, latest_msg, category_name, model_text)
    candidates = []
    repair = _repair_from_chat(history, latest_msg, original)
    if repair and _line_fits_job(repair, job):
        candidates.append(repair)
    for line in _alternate_lines(original):
        if _line_fits_job(line, job):
            candidates.append(line)
    if _last_assistant_text(history) or _give_repair_now(latest_msg, history):
        candidates.extend(_conditional_lines(history, latest_msg, category_name, model_text))
    else:
        candidates.extend(_prove_lines(history, latest_msg, category_name, model_text))
    fresh = [
        line
        for line in candidates
        if line
        and _line_fits_job(line, job)
        and not _draft_is_bad(
            line, history, latest_msg, similar=False, category_name=category_name, model_text=model_text
        )
    ]
    chosen = _pick_fresh_line(fresh, history) or _final_shop_line(
        history, latest_msg, category_name, model_text
    )
    return _with_cite(chosen, job) if chosen and "📖" not in chosen else chosen


_SOURCE_ONLY_LINE_RE = re.compile(r"^(?:📖\s*)?source\s*:", re.I)


def reply_is_source_only_or_empty(text: str) -> bool:
    """True when the tech would see no shop step. A library-miss line is a step."""
    raw = (text or "").strip()
    if _is_library_miss_line(raw):
        return False
    if not raw:
        return True
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return True
    return all(_SOURCE_ONLY_LINE_RE.match(line) for line in lines)


def guard_blank_shop_reply(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """An empty reply or a bare source line becomes the next cited check."""
    if _is_offline_notice(reply):
        return reply
    if not reply_is_source_only_or_empty(reply):
        return reply
    job = _job_key(history, latest_msg, category_name, model_text)
    if job == "thetford":
        nxt = _thetford_shop_line(history, latest_msg)
    elif job == "leadjack":
        nxt = _leadjack_shop_line(history, latest_msg)
    else:
        nxt = _final_shop_line(history, latest_msg, category_name, model_text)
    if nxt and not reply_is_source_only_or_empty(nxt):
        return nxt
    return reply


def polish_shop_reply(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """Shop text only: no model instructions, no invented facts, no repeated block."""
    locked = _firm_repair_reply(history, latest_msg, category_name, model_text)
    if locked:
        if "📖" not in locked:
            locked = _with_cite(locked, _job_key(history, latest_msg, category_name, model_text))
        return locked
    text = _FILLER_RE.sub("", _STRAY_PAGE_RE.sub("", _strip_source_header((reply or "").strip())))
    if _is_offline_notice(text):
        return text
    if not text:
        text = _repair_from_chat(history, latest_msg, "")
    text = _strip_heard_clauses(text)
    if re.search(r"(?:^|\s)2\.", text or "") and not re.search(r"(?:^|\s)1\.", text or ""):
        text = re.sub(r"(?:^|\s)\d{1,2}\.\s+", " ", text or "")
    text = _FILENAME_RE.sub("", text)
    text = _strip_stop_no_further_tests(text)
    text = _LEAKED_GUARD_RE.sub("", text)
    text = _META_QUESTION_RE.sub("", text)
    text = re.sub(
        r"before condemning the thermocouple\b(?:(?!\d+\.)[^.?!])*[.?!]?",
        "",
        text,
        flags=re.I,
    )
    text = _FALLBACK_ACK_RE.sub("", text).strip()
    user_blob = _user_blob(history, latest_msg)
    answered = _answered_checks(user_blob)
    prior = _prior_sentence_keys(history)
    seen = set()
    seen_checks = set()
    lines_out = []
    changed = text != (reply or "").strip()
    kept_sentences = []
    for line in text.splitlines():
        kept = []
        pieces = _split_reply_sentences(line) or ([line] if line.strip() else [])
        for sentence in pieces:
            if sentence.startswith("📖"):
                key = _sentence_key(sentence)
                if key in seen:
                    changed = True
                    continue
                seen.add(key)
                kept.append(sentence)
                continue
            if _is_acknowledgement(sentence):
                changed = True
                continue
            if _BROKEN_SENTENCE_RE.search(sentence):
                changed = True
                continue
            cleaned = _scrub_unreported_sentence(sentence, user_blob)
            # An If-sentence is the instruction. Stripping "remains" or "is broken"
            # out of it leaves "interior leak , replace".
            if not re.match(r"(?i)^if\b", (cleaned or "").strip()):
                cleaned = _strip_unreported_assertion(cleaned, user_blob)
            if cleaned != sentence:
                changed = True
            sentence = cleaned
            if (
                re.search(r"\b1 month\b|replace the unit", sentence, re.I)
                and not re.search(r"frost return|heavy frost|waited a month|after 1 month", user_blob, re.I)
            ):
                changed = True
                continue
            if (
                not sentence
                or _LEAKED_GUARD_RE.search(sentence)
                or _META_QUESTION_RE.search(sentence)
                or _COOKTOP_GUARD_RE.search(sentence)
                or _INTERNAL_LEAK_RE.search(sentence)
                or re.fullmatch(r"figs?\.?", sentence.strip(), re.I)
                or _BARE_REPAIR_LABEL_RE.match(sentence.strip())
                or _overlaps_prior(sentence, history)
                or _same_as_last_turn(sentence, history)
                or any(_too_similar(sentence, earlier) for earlier in kept_sentences)
            ):
                changed = True
                continue
            if _is_repair_sentence(sentence) and any(
                _same_repair(sentence, earlier) for earlier in _prior_repair_sentences(history)
            ):
                if not asks_what_is_the_repair(latest_msg):
                    changed = True
                    continue
            if _sentence_reasks_check(sentence, answered):
                changed = True
                continue
            if _is_fallback_question(sentence) and len(_sentence_key(sentence)) < 80:
                changed = True
                continue
            key = _loose_sentence_key(sentence)
            if not key or key in seen or (len(key) >= 30 and _sentence_key(sentence) in prior):
                changed = True
                continue
            check = ""
            for name, pattern in _REPEATED_CHECK_RES:
                if _reply_asks_check(sentence, pattern):
                    check = name
                    break
            if check and check in seen_checks:
                changed = True
                continue
            if check:
                seen_checks.add(check)
            seen.add(key)
            kept_sentences.append(sentence)
            kept.append(sentence)
        if kept:
            lines_out.append(" ".join(kept))
        elif line.strip():
            changed = True
    text = "\n".join(lines_out).strip()
    if not changed:
        text = (reply or "").strip()
    job = _job_key(history, latest_msg, category_name, model_text)
    if not _reply_has_body(text) or _draft_is_bad(
        text, history, latest_msg, category_name=category_name, model_text=model_text
    ):
        step = _answer_latest(history, latest_msg, text or reply or "", category_name, model_text)
        if not step:
            step = _next_unused_step(history, latest_msg, reply or "", category_name, model_text)
            step = re.sub(r"\bthat is the repair\.?", "", step or "", flags=re.I).strip(" .")
            if step and "📖" not in step:
                step += "."
        if not step or _same_as_last_turn(step, history) or _INTERNAL_LEAK_RE.search(step or ""):
            step = _answer_latest(history, latest_msg, "", category_name, model_text)
        if step and not _same_as_last_turn(step, history) and _line_fits_job(step, job):
            sources = [
                line for line in (text or "").splitlines()
                if line.strip().startswith("📖")
                and not _INTERNAL_LEAK_RE.search(line)
                and _line_fits_job(line, job)
            ]
            text = step if "📖" in step else _with_cite(step, job)
            if sources and "📖" not in text:
                text = text + "\n" + "\n".join(sources)
            changed = True
    text = _strip_heard_clauses(text)
    text = _strip_source_header(text)
    asked = _give_repair_now(latest_msg, history) and not re.search(
        r"\bif\b.+\b(?:replace|reseat|repair)\b", text or "", re.I | re.S
    )
    if (
        not text
        or not _reply_has_body(text)
        or _draft_is_bad(
            text, history, latest_msg, similar=False, category_name=category_name, model_text=model_text
        )
        or re.search(r"report the result of that check", text or "", re.I)
        or asked
    ):
        nxt = _final_shop_line(history, latest_msg, category_name, model_text)
        if nxt and _line_fits_job(nxt, job):
            text = nxt
    if not (text or "").strip() or not _line_fits_job(text, job):
        text = _final_shop_line(history, latest_msg, category_name, model_text)
    if text and "📖" not in text:
        text = _with_cite(text, job)
    if _repeats_last_body(text, history):
        nxt = _final_shop_line(history, latest_msg, category_name, model_text)
        if nxt and not _repeats_last_body(nxt, history) and _line_fits_job(nxt, job):
            text = nxt
    text = re.sub(r"[ \t]{2,}", " ", (text or "").strip())
    text = ensure_level_up_lead_jack_reply(
        text, history, latest_msg, category_name, model_text
    )
    text = ensure_thetford_flush_reply(
        text, history, latest_msg, category_name, model_text, original=reply or ""
    )
    text = _strip_facr_internal_guard(text)
    text = guard_blank_shop_reply(text, history, latest_msg, category_name, model_text)
    return without_reading_filler(
        _strip_facr_internal_guard(text), history, latest_msg, category_name, model_text
    )


def _ice_cooling_unit_ready(blob: str) -> bool:
    """Dry-and-wait plus frost back is the cooling-unit repair."""
    raw = blob or ""
    overnight = bool(
        re.search(
            r"\bovernight\b"
            r"|\bdry-and-wait\b"
            r"|\bdry and wait\b"
            r"|\b(?:dried|drying|dry)\b.{0,48}\bwait(?:ed|ing|s)?\b"
            r"|\bwait(?:ed|ing)?\b.{0,48}\b(?:dry|dried|drying|overnight|month)\b"
            r"|\b(?:1|one)\s+month\b",
            raw,
            re.I,
        )
    )
    dried = bool(
        re.search(
            r"\b(?:dried|drying|towel)\b|\bdry-and-wait\b|\bdry and wait\b|\bdry\b|"
            r"\bovernight\b|\b(?:1|one)\s+month\b",
            raw,
            re.I,
        )
    )
    back = bool(
        re.search(
            r"\b(?:frost|ice|icing)\b.{0,40}\b(?:return(?:ed|s)?|came back|persists?)\b|"
            r"\bheavy frost\b|"
            r"\b(?:frost|ice|icing)\b.{0,24}\bstill\b|"
            r"\bstill (?:icing|iced|there)\b",
            raw,
            re.I,
        )
    )
    return bool(overnight and dried and back)


def _girard_seating_confirmed(blob: str) -> bool:
    """Seating is a reported fact. A clear tube is not seating."""
    raw = blob or ""
    if re.search(r"\b(?:not|isn't|is not)\s+seated\b|\bunseated\b", raw, re.I):
        return False
    return bool(
        re.search(
            r"\bseating(?:\s+is)?\s+confirmed\b|"
            r"\bseated the (?:sensing )?tube\b|"
            r"\b(?:sensing )?tube(?:\s+is|\s+was)?\s+seated\b|"
            r"\bi seated (?:it|the tube|the sensing tube)\b",
            raw,
            re.I,
        )
    )


def _cooktop_repair_ready(blob: str, latest_msg: str = "") -> bool:
    """The tip repair waits until the tip is low or the tech asks for the repair."""
    if cooktop_tip_sits_low(blob or ""):
        return True
    if not asks_what_is_the_repair(latest_msg or ""):
        return False
    return _has_pan_on_flameout_marker(blob or "")


def _live_close_reply(
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """Terminal card for a proved job. Other jobs stay on their own prove."""
    job = _job_key(history, latest_msg, category_name, model_text)
    blob = _user_blob(history, latest_msg)
    if job == "facr":
        facts = facr_proves_from_chat(history, latest_msg)
        if facr_terminal_path_complete(facts) or facr_pressure_authorizes_rr(facts):
            return facr_pressure_rr_line(facts)
        if facts.get("facr_pressure") == "ok":
            return _facr_stay_on_prove_line(facts)
        return ""
    if job == "ice" and _ice_cooling_unit_ready(blob):
        return ICE_COOLING_UNIT_LINE
    if job == "girard" and _girard_seating_confirmed(blob):
        return GIRARD_SEATING_REPAIR_LINE
    if job == "cooktop" and _cooktop_repair_ready(blob, latest_msg):
        return COOKTOP_TIP_LOW_REPAIR
    return ""


_STOP_NO_FURTHER_RE = re.compile(r"\bStop\.\s*No further tests\.?\s*", re.I)
_COOKTOP_RUNON_RE = re.compile(r"under load\s+[A-Z]")


def _strip_stop_no_further_tests(text: str) -> str:
    cleaned = _STOP_NO_FURTHER_RE.sub("", text or "")
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def avoid_duplicate_reply(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """Do not send the same reply twice, and do not ask a check that was already asked.

    A repeated card becomes the next repair for THIS job. Another case's repair
    cannot be pasted in, and a firm repair already given is not replaced by a new If.
    """
    def _out(text: str) -> str:
        text = _strip_facr_internal_guard(text)
        return guard_blank_shop_reply(text, history, latest_msg, category_name, model_text)

    text = _strip_stop_no_further_tests((reply or "").strip())
    if _is_offline_notice(text):
        return text
    closed = _live_close_reply(history, latest_msg, category_name, model_text)
    if closed:
        return _out(closed)
    locked = _firm_repair_reply(history, latest_msg, category_name, model_text)
    if locked:
        if "📖" not in locked:
            locked = _with_cite(locked, _job_key(history, latest_msg, category_name, model_text))
        return _out(locked)
    if not text:
        return _out(polish_shop_reply("", history, latest_msg, category_name, model_text))
    prev = _last_assistant_text(history)
    already = {
        _norm(message.get("content") or "")
        for message in history or []
        if (message.get("role") or "") == "assistant" and (message.get("content") or "").strip()
    }
    if prev and _norm(text) in already:
        chosen = ""
        for line in _alternate_lines(text):
            if not _line_fits_job(line, _job_key(history, latest_msg, category_name, model_text)):
                continue
            candidate = polish_shop_reply(line, history, latest_msg, category_name, model_text)
            if candidate and _norm(candidate) not in already:
                chosen = candidate
                break
        if not chosen:
            chosen = polish_shop_reply(
                _repair_from_chat(history, latest_msg, text),
                history,
                latest_msg,
                category_name,
                model_text,
            )
        chosen = chosen if chosen and _norm(chosen) not in already else polish_shop_reply(
            "", history, latest_msg, category_name, model_text
        )
        return _out(chosen or _final_shop_line(history, latest_msg, category_name, model_text))
    if prev:
        text = _drop_repeated_checks(text, prev, history, latest_msg)
    polished = polish_shop_reply(text, history, latest_msg, category_name, model_text)
    if prev and _norm(polished) in already:
        for line in _alternate_lines(text):
            if not _line_fits_job(line, _job_key(history, latest_msg, category_name, model_text)):
                continue
            candidate = polish_shop_reply(line, history, latest_msg, category_name, model_text)
            if candidate and _norm(candidate) not in already:
                return _out(candidate)
        polished = ""
    if not (polished or "").strip() or (prev and _norm(polished) in already):
        polished = _final_shop_line(history, latest_msg, category_name, model_text)
    return _out(polished)


def reply_loops_furnace_12v(reply: str) -> bool:
    if "replace the wall thermostat" in _norm(reply):
        return False
    return bool(re.search(r"\b12\s*v(?:dc)?\b", reply or "", re.I))


def _history_asked_furnace_12v(history: list = None) -> bool:
    for message in history or []:
        if (message.get("role") or "") != "assistant":
            continue
        if reply_loops_furnace_12v(message.get("content") or ""):
            return True
    return False


def ensure_furnace_wall_thermostat(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
) -> str:
    """
    A furnace that runs on a thermostat bypass gets the sail-switch prove first.
    The wall thermostat is replaced only after that prove is reported.
    """
    reply = limit_library_miss_mentions(reply or "", history)
    blob = _blob(category_name, model_text, _chat_user_blob(history, latest_msg))
    if not is_suburban_furnace_context(category_name, model_text, blob):
        return reply
    if not furnace_rw_jumper_ran(blob):
        return reply
    prior_user = _norm(_chat_user_blob(history, ""))
    latest_user = _norm(latest_msg or "")
    sail_reported = bool(re.search(r"\bsail\b", prior_user)) or (
        bool(re.search(r"\bsail\b", latest_user)) and not _is_fallback_question(latest_msg or "")
    )
    if not sail_reported:
        return FURNACE_SAIL_PROVE_LINE
    # The sail-switch result is the proving fact. The repair is the thermostat,
    # not another measure-the-sail-switch conditional.
    return FURNACE_WALL_TSTAT_LINE


def cooktop_tip_sits_low(text: str) -> bool:
    t = _norm(text)
    return bool(
        re.search(
            r"tip.{0,48}(?:sits?\s+low|is\s+low|too\s+low|gets?\s+pushed|pushed)|"
            r"(?:sits?|sitting|sat)\s+low|"
            r"gets?\s+pushed|"
            r"pushed\s+(?:down|out|away|off)",
            t,
        )
    )


def _coleman_checks_asked(assistant_text: str) -> str:
    raw = _coleman_prep(assistant_text)
    if not raw or not re.search(r"\?|\b(?:check|measure|read|what|bypass)\b", raw):
        return ""
    found = ""
    for key, pat in _COLEMAN_ASK_ORDER:
        if pat.search(raw):
            found = key
            break
    return found


def _coleman_note_fan_high(facts: dict, text: str, asked: str = "") -> None:
    raw = _coleman_prep(text)
    if not raw:
        return
    zero = bool(re.search(rf"\b{_COLEMAN_NEAR_ZERO_VAC}\b", raw))
    if _COLEMAN_FAN_HIGH_LIVE_RE.search(raw) and not zero and not re.search(
        r"\b(?:dark|dead|no\s+lamp|no\s+light)\b", raw
    ):
        facts["coleman_fan_high"] = "live"
        return
    if _COLEMAN_FAN_HIGH_DEAD_RE.search(raw):
        facts["coleman_fan_high"] = "dead"
        return
    if asked == "fan_high" and re.search(
        r"\b(?:dark|dead|no\s+lamp|no\s+light|0(?:\.\d+)?\s*vac)\b", raw
    ):
        facts["coleman_fan_high"] = "dead"


def _coleman_note_peacemaker(facts: dict, text: str) -> None:
    raw = _coleman_prep(text)
    if not raw:
        return
    compressor_down = re.search(
        r"\bcompressor\b.{0,40}\b(?:not|no|isn't|isnt|doesn't|does not|won't|wont)\b"
        r".{0,16}\b(?:run|running|start|ok|okay)\b",
        raw,
    )
    if _COLEMAN_COMP_OK_RE.search(raw) and not compressor_down:
        facts["coleman_compressor"] = "ok"
    if _COLEMAN_FAN_LOCKED_RE.search(raw):
        facts["coleman_fan_motor"] = "locked"
    if _COLEMAN_STALL_AMP_RE.search(raw) and (
        facts.get("coleman_fan_motor") == "locked"
        or _COLEMAN_FAN_LOCKED_RE.search(raw)
        or re.search(r"\b(?:shaft\s+locked|locked\s+rotor|stall)\b", raw)
    ):
        facts["coleman_stall_amps"] = "reported"


def _coleman_note_cap(facts: dict, text: str, asked: str = "") -> None:
    raw = _coleman_prep(text)
    if not raw:
        return
    if _COLEMAN_CAP_BAD_RE.search(raw):
        facts["coleman_cap"] = "bad"
        return
    if _COLEMAN_CAP_UF_RE.search(raw) or _COLEMAN_CAP_OK_WORD_RE.search(raw):
        facts["coleman_cap"] = "ok"
        return
    if asked == "cap" and re.search(r"\b(?:good|ok|okay|rated|pass|passed)\b", raw):
        if not re.search(r"\b(?:bad|open|short|fail)\b", raw):
            facts["coleman_cap"] = "ok"


def coleman_motor_board_evidence_complete(facts: dict | None) -> bool:
    facts = facts or {}
    return (
        facts.get("coleman_fan_high") == "dead"
        and facts.get("coleman_compressor") == "ok"
        and facts.get("coleman_fan_motor") == "locked"
        and facts.get("coleman_stall_amps") == "reported"
        and facts.get("coleman_cap") == "ok"
    )


def coleman_facts_from_chat(
    history: list = None,
    latest_msg: str = "",
    context_blob: str = "",
) -> dict:
    """Merge Coleman 2111-0001 prove facts. Other complaints return nothing."""
    turns = []
    for m in history or []:
        role = (m.get("role") or "").strip()
        content = m.get("content") or ""
        if role in ("user", "assistant") and content.strip():
            turns.append({"role": role, "content": content})
    if (latest_msg or "").strip():
        turns.append({"role": "user", "content": latest_msg})
    blob = " ".join(
        part for part in (context_blob, *(m["content"] for m in turns)) if part
    )
    if not is_coleman_2111_context("", "", blob):
        return {}
    facts = {"coleman_2111": "open"}
    pending = ""
    for m in turns:
        if m["role"] == "assistant":
            pending = _coleman_checks_asked(m["content"])
            continue
        _coleman_note_fan_high(facts, m["content"], pending)
        _coleman_note_peacemaker(facts, m["content"])
        _coleman_note_cap(facts, m["content"], pending)
        pending = ""
    if coleman_motor_board_evidence_complete(facts):
        facts["coleman_2111"] = "climax"
    return facts


def reply_names_coleman_motor_board_only(reply: str) -> bool:
    """True when the reply authorizes fan motor + control board and not the whole unit."""
    t = _norm(reply)
    if not t:
        return False
    motor = "fan motor" in t or ("motor" in t and "board" in t)
    board = "control board" in t or ("board" in t and "motor" in t)
    only = bool(re.search(r"\bonly\b|not the full|do not replace the full", t))
    auth = bool(re.search(r"\b(?:authoriz\w*|r&r|replace)\b", t))
    return bool(motor and board and only and auth)


def reply_authorizes_coleman_full_assembly(reply: str) -> bool:
    """True when a sentence authorizes the full 2111-0001 assembly."""
    text = reply or ""
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        if not part.strip():
            continue
        if not re.search(
            r"\b(?:full|complete|entire)\b.{0,48}\b(?:2111[\s-]*0001|assembly|rooftop)\b",
            part,
            re.I,
        ):
            continue
        if re.search(
            r"\b(?:do not|don't|dont|not)\b.{0,40}\b(?:replace|r\s*&\s*r|authoriz)",
            part,
            re.I,
        ):
            continue
        if re.match(r"\s*(?:do not|don't|dont)\b", part, re.I):
            continue
        if re.search(r"\b(?:replace|r\s*&\s*r|authoriz)", part, re.I):
            return True
    return False


def reply_fishes_coleman_more_tests(reply: str) -> bool:
    t = reply or ""
    if re.search(r"\b(?:no further tests|do not run more tests)\b", t, re.I):
        return False
    return bool(_COLEMAN_FISH_RE.search(t))


def ensure_coleman_motor_board_auth(reply: str, facts: dict | None = None) -> str:
    """
    Evidence complete → motor + control board authorization only.
    Incomplete evidence is left alone. No invented page numbers.
    """
    facts = facts or {}
    if not coleman_motor_board_evidence_complete(facts):
        return reply
    # Stall current and a near-rated capacitor close the prove. The card is the
    # repair. A conditional that still names those checks is not sent again.
    return COLEMAN_MOTOR_BOARD_AUTH_LINE


def format_level_up_library_honesty(catalog_docs, chunks=None) -> str:
    """
    When Level-Up titles exist on the catalog, never claim the library lacks them.
    If they are unindexed / have zero chunks, name them and ask for reindex.
    """
    rows = list(catalog_docs or [])
    level_up = []
    for d in rows:
        if isinstance(d, dict):
            title = str(d.get("title") or "")
            indexed = bool(d.get("indexed"))
            chunks_n = d.get("chunk_count")
        else:
            title = str(getattr(d, "title", "") or "")
            indexed = bool(getattr(d, "indexed", False))
            chunks_n = getattr(d, "chunk_count", None)
        if not is_level_up_library_title(title):
            continue
        level_up.append({"title": title, "indexed": indexed, "chunk_count": chunks_n})
    if not level_up:
        return ""
    titles = [r["title"] for r in level_up]
    unread = [
        r for r in level_up
        if (not r["indexed"]) or (r["chunk_count"] == 0)
    ]
    lines = [
        "LEVEL UP LIBRARY HONESTY:",
        "The shop Document Library DOES include Level Up / Level-Up controller material. "
        "Never claim those Level-Up / 807662 titles are absent from the catalog.",
        "Level-Up / OCTP / TI titles on the catalog:",
    ]
    for t in titles:
        lines.append(f"- {t}")
    retrieved = [
        _page_title(ch) for ch in (chunks or [])
        if is_level_up_library_title(_page_title(ch))
    ]
    if unread and not retrieved:
        lines.append(
            "Best Level-Up hit(s) are unindexed or have zero searchable chunks. "
            "Name the title(s) and ask a manager to re-index that PDF in Document Library. "
            "Do not substitute Lippert OneControl Unity M-Series awning/slide reversing."
        )
        for r in unread:
            note = "not indexed" if not r["indexed"] else "zero chunks"
            lines.append(f"- Reindex needed: {r['title']} ({note})")
    elif not retrieved:
        lines.append(
            "Level-Up titles exist. If this turn's excerpts missed them, say so and stay on those titles — "
            "do not invent Unity as the controller manual."
        )
    return "\n".join(lines)


def claims_level_up_library_empty(reply: str) -> bool:
    """True when a coach reply falsely says the library has no Level Up procedure."""
    t = reply or ""
    if not t:
        return False
    if LEVEL_UP_EMPTY_CLAIM_RE.search(t):
        return True
    low = _norm(t)
    if "unity" in low and any(
        p in low for p in ("only has", "only have", "library only", "only the onecontrol", "only onecontrol")
    ):
        return True
    return False


def format_ac_library_honesty(catalog_docs, chunks=None) -> str:
    """
    When rooftop AC titles exist on the catalog or in this turn's hits,
    never claim the library only has Unity / lacks an AC procedure.
    """
    rows = list(catalog_docs or [])
    ac_docs = []
    for d in rows:
        if isinstance(d, dict):
            title = str(d.get("title") or "")
            indexed = bool(d.get("indexed"))
            chunks_n = d.get("chunk_count")
        else:
            title = str(getattr(d, "title", "") or "")
            indexed = bool(getattr(d, "indexed", False))
            chunks_n = getattr(d, "chunk_count", None)
        if not is_ac_library_title(title):
            continue
        ac_docs.append({"title": title, "indexed": indexed, "chunk_count": chunks_n})
    retrieved = [
        _page_title(ch) for ch in (chunks or [])
        if is_ac_library_title(_page_title(ch))
    ]
    if not ac_docs and not retrieved:
        return ""
    titles = [r["title"] for r in ac_docs] or retrieved
    unread = [
        r for r in ac_docs
        if (not r["indexed"]) or (r["chunk_count"] == 0)
    ]
    lines = [
        "AIR CONDITIONING LIBRARY HONESTY:",
        "The shop Document Library DOES include rooftop Air Conditioning / FACT / Brisk / ADB material. "
        "Never claim those Furrion/Dometic AC titles are absent from the catalog. "
        "Do not invent Unity as the AC manual.",
        "Rooftop AC / FACT / Brisk / ADB titles on the catalog or this turn's excerpts:",
    ]
    for t in titles:
        lines.append(f"- {t}")
    if unread and not retrieved:
        lines.append(
            "Best Air Conditioning hit(s) are unindexed or have zero searchable chunks. "
            "Name the title(s) and ask a manager to re-index that PDF in Document Library. "
            "Do not substitute Lippert OneControl Unity M-Series awning/slide reversing."
        )
        for r in unread:
            note = "not indexed" if not r["indexed"] else "zero chunks"
            lines.append(f"- Reindex needed: {r['title']} ({note})")
    elif not retrieved:
        lines.append(
            "Air Conditioning titles exist. If this turn's excerpts missed them, say so and stay on those titles — "
            "do not invent Unity as the AC manual."
        )
    return "\n".join(lines)


def claims_ac_library_empty(reply: str) -> bool:
    """True when a coach reply falsely says the library has no AC procedure / only Unity."""
    t = reply or ""
    if not t:
        return False
    if AC_EMPTY_CLAIM_RE.search(t):
        return True
    low = _norm(t)
    if "unity" in low and any(
        p in low for p in ("only has", "only have", "library only", "only the onecontrol", "only onecontrol")
    ):
        if any(k in low for k in ("air condition", "rooftop", "fact", "brisk", "ac ")):
            return True
    return False


def error_code_query_terms(text: str) -> set:
    """Keep E8 / E2 / E3 style codes that tokenize() used to drop (len 2)."""
    return {f"{m.group(1).lower()}{m.group(2)}" for m in ERROR_CODE_QUERY_RE.finditer(text or "")}


def _fridge_blob_not_water_heater(blob: str) -> bool:
    """True when this looks like a refrigerator job, not a water heater."""
    if any(k in blob for k in ("fridge", "reefer", "refriger", "fcr0", "fcr1", "norcold")):
        if "water heater" in blob or "gswh" in blob or "girard" in blob:
            return False
        return True
    return False


def is_water_heater_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Water Heaters / Girard GSWH-2 / E8 / Petit Tube / air pressure switch.
    Fridge FCR E2 and rooftop AC E2/E3 must lose.
    """
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    cat = _norm(category_name)
    if "water heat" in cat:
        return True
    blob = _blob(category_name, model_text, symptom)
    if not blob or _fridge_blob_not_water_heater(blob):
        return False
    if any(m in blob for m in WATER_HEATER_MODELS) or "gswh" in blob:
        return True
    if "ccd-0009390" in blob or "ccd0009390" in blob:
        return True
    if "petit tube" in blob or "petit-tube" in blob:
        return True
    if "water heater" in blob or "water-heater" in blob or "tankless water" in blob:
        return True
    if "girard" in blob and any(
        k in blob for k in ("water", "heater", "tankless", "gswh", "e8", "petit", "gsw")
    ):
        return True
    if re.search(r"\be\s*8\b", blob) and any(
        k in blob for k in ("water", "heater", "girard", "gswh", "petit", "air pressure", "tankless")
    ):
        return True
    return False


def is_girard_petit_tube_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Girard GSWH-2 E8. Align the petit tube before a control board."""
    if not is_water_heater_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    return bool(re.search(r"\be\s*8\b", blob) or "petit tube" in blob or "petit-tube" in blob)


def girard_petit_facts(history: list = None, latest_msg: str = "") -> dict:
    """Tubing-clear and APS/harness facts from the tech's own words."""
    blob = _norm(_chat_user_blob(history, latest_msg))
    facts = {}
    if re.search(
        r"\btubing is clear\b|"
        r"\b(tubing|petit tube|petit-tube)\b.{0,32}\b(clear|ok|good|connected)\b|"
        r"\b(clear|connected)\b.{0,16}\b(tubing|petit tube)\b",
        blob,
    ):
        facts["girard_tube"] = "clear"
    if re.search(
        r"\baps\b.{0,48}\b(ok|okay|good|fine)\b|"
        r"\bharness continuity\b.{0,24}\b(ok|okay|good|fine)\b",
        blob,
    ):
        facts["girard_aps"] = "ok"
    return facts


def ensure_girard_petit_align(
    reply: str,
    history: list = None,
    latest_msg: str = "",
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> str:
    """
    After the tube is clear, an APS/harness pass or a repair ask is the
    alignment fix. Do not repeat the vent and petit-tube check.
    """
    blob = _blob(category_name, model_text, symptom, _chat_user_blob(history, latest_msg))
    if not is_girard_petit_tube_context(category_name, model_text, blob):
        return reply
    facts = girard_petit_facts(history, latest_msg)
    ready = facts.get("girard_tube") == "clear" and (
        facts.get("girard_aps") == "ok"
        or asks_what_is_the_repair(latest_msg or "")
        or asks_what_next(latest_msg or "")
        or bool(re.search(r"\btubing is clear\b", _norm(latest_msg or "")))
    )
    if "burner flame" in _norm(reply):
        reply = ""
    if _girard_seating_confirmed(_chat_user_blob(history, latest_msg)):
        return GIRARD_SEATING_REPAIR_LINE
    if facts.get("girard_tube") == "clear":
        return GIRARD_BLOWER_SUCTION_LINE
    if not ready:
        if reply and "blower" in _norm(reply):
            return reply
        return GIRARD_PETIT_ALIGN_LINE
    return GIRARD_BLOWER_SUCTION_LINE


def tech_asks_unity_for_water_heater(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
    unity_gate: str = "",
) -> bool:
    """Exception: tech clearly named OneControl / Unity / CAN for the water heater."""
    if (unity_gate or "").strip() == "Yes":
        return True
    blob = _blob(category_name, model_text, symptom)
    if not blob:
        return False
    return bool(AC_UNITY_ASK_RE.search(blob))


def skip_unity_for_water_heater(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
    unity_gate: str = "",
) -> bool:
    """Coach: do not inject Unity Electrical search for a water heater / GSWH-2 job."""
    if not is_water_heater_context(category_name, model_text, symptom):
        return False
    if tech_asks_unity_for_water_heater(category_name, model_text, symptom, unity_gate):
        return False
    return True


def is_water_heater_library_title(title: str) -> bool:
    """Catalog titles that are Girard / GSWH / Water Heaters — not Unity, not FCR fridge."""
    t = _norm(title)
    if not t or is_unity_board_manual(t):
        return False
    if "ccd-0008122" in t or "ccd0008122" in t:
        return False
    if any(m in t for m in WATER_HEATER_MODELS) or "gswh" in t:
        return True
    if "ccd-0009390" in t or "ccd0009390" in t:
        return True
    if "girard" in t and any(k in t for k in ("water", "heater", "tankless", "gswh", "troubleshoot")):
        return True
    if "water heater" in t or "water-heater" in t or "tankless water" in t:
        return True
    return False


def water_heater_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward Girard GSWH-2 / E8 / Petit Tube. Never add Unity terms."""
    symptom = (symptom or "").strip()
    if not is_water_heater_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {WATER_HEATER_SEARCH_BOOST}".strip()


def score_water_heater_product(page, query: str = "", category: str = "") -> int:
    """
    Higher = Girard GSWH-2 / CCD-0009390 / Water Heaters / E8 / Petit Tube / air pressure.
    Unity M-Series and Furrion FCR fridge E2 pages must lose.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    cat = _norm(category)
    if isinstance(page, dict):
        cat = cat or _norm(str(page.get("category") or page.get("category_name") or ""))
    else:
        cat = cat or _norm(str(getattr(page, "category", "") or getattr(page, "category_name", "") or ""))
    score = 0
    if is_water_heater_library_title(title) or is_water_heater_library_title(t):
        score += 22
    if any(m in t or m in q for m in WATER_HEATER_MODELS) or "gswh" in t or "gswh" in q:
        score += 14
    if "ccd-0009390" in t or "ccd0009390" in t or "ccd-0009390" in q:
        score += 14
    if "girard" in t or "girard" in q:
        score += 10
    if "water heat" in cat:
        score += 8
    if "water heater" in t or "tankless" in t:
        score += 8
    if re.search(r"\be\s*8\b", t) or re.search(r"\be\s*8\b", q):
        score += 12
    if "petit tube" in t or "petit-tube" in t or "petit tube" in q:
        score += 12
    if "air pressure" in t or "pressure switch" in t:
        score += 10
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 36
    if "awning" in t and "slide" in t:
        score -= 18
    if "ccd-0008122" in t or "ccd0008122" in t or is_furrion_ccd_0008122(title):
        score -= 20
    if any(k in t for k in ("refriger", "fridge", "furnace", "air condition")) and "water heater" not in t:
        score -= 8
    return score


def rank_chunks_for_water_heater(chunks, query: str, limit: int = 8) -> list:
    """Prefer Girard GSWH-2 / Water Heaters pages; drop Unity board SM when a WH hit exists."""
    scored = [(score_water_heater_product(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    has_wh = any(
        sc > 0 and is_water_heater_library_title(_page_title(ch) or _page_text_blob(ch))
        for sc, ch in scored
    )
    out = []
    for sc, ch in scored:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            if has_wh or sc < 0:
                continue
        out.append(ch)
        if len(out) >= limit:
            break
    if out:
        return out
    return [
        ch for sc, ch in scored[:limit]
        if sc >= 0 and not is_unity_board_manual(_page_title(ch))
    ]


def drop_unity_chunks_for_water_heater(chunks) -> list:
    """Never keep Unity awning/slide reversing excerpts as the water heater manual."""
    kept = []
    for ch in chunks or []:
        title = _page_title(ch)
        blob = _page_text_blob(ch)
        if is_unity_board_manual(title) or is_unity_board_manual(blob):
            continue
        kept.append(ch)
    return kept


def format_water_heater_library_honesty(catalog_docs, chunks=None) -> str:
    """
    When Girard / GSWH-2 / Water Heaters titles exist on the catalog or in this
    turn's hits, never claim the library lacks a GSWH-2 / E8 procedure.
    """
    rows = list(catalog_docs or [])
    wh_docs = []
    for d in rows:
        if isinstance(d, dict):
            title = str(d.get("title") or "")
            indexed = bool(d.get("indexed"))
            chunks_n = d.get("chunk_count")
        else:
            title = str(getattr(d, "title", "") or "")
            indexed = bool(getattr(d, "indexed", False))
            chunks_n = getattr(d, "chunk_count", None)
        if not is_water_heater_library_title(title):
            continue
        wh_docs.append({"title": title, "indexed": indexed, "chunk_count": chunks_n})
    retrieved = [
        _page_title(ch) for ch in (chunks or [])
        if is_water_heater_library_title(_page_title(ch))
    ]
    if not wh_docs and not retrieved:
        return ""
    titles = [r["title"] for r in wh_docs] or retrieved
    unread = [
        r for r in wh_docs
        if (not r["indexed"]) or (r["chunk_count"] == 0)
    ]
    lines = [
        "WATER HEATER LIBRARY HONESTY:",
        "The shop Document Library DOES include Girard GSWH-2 / Water Heaters material. "
        "Never claim those Girard / GSWH-2 / CCD-0009390 titles are absent from the catalog. "
        "Do not invent Unity as the water heater manual. Do not invent blink LEDs.",
        "Girard / GSWH-2 / Water Heaters titles on the catalog or this turn's excerpts:",
    ]
    for t in titles:
        lines.append(f"- {t}")
    if unread and not retrieved:
        lines.append(
            "Best Water Heaters hit(s) are unindexed or have zero searchable chunks. "
            "Name the title(s) and ask a manager to re-index that PDF in Document Library. "
            "Do not substitute Lippert OneControl Unity M-Series awning/slide reversing."
        )
        for r in unread:
            note = "not indexed" if not r["indexed"] else "zero chunks"
            lines.append(f"- Reindex needed: {r['title']} ({note})")
    elif not retrieved:
        lines.append(
            "Water Heaters titles exist. If this turn's excerpts missed them, say so and stay on those titles — "
            "do not invent Unity as the water heater manual."
        )
    return "\n".join(lines)


def claims_water_heater_library_empty(reply: str) -> bool:
    """True when a coach reply falsely says the library has no GSWH-2 / water heater procedure."""
    t = reply or ""
    if not t:
        return False
    if WATER_HEATER_EMPTY_CLAIM_RE.search(t):
        return True
    low = _norm(t)
    if "unity" in low and any(
        p in low for p in ("only has", "only have", "library only", "only the onecontrol", "only onecontrol")
    ):
        if any(k in low for k in ("water heater", "girard", "gswh", "e8")):
            return True
    return False


def _has_fcr_e2_fan_fault_marker(blob: str) -> bool:
    """E2 / 2-flash / Fan Fault Current / freezer-fan readings — fridge wording only."""
    t = _norm(blob)
    if not t:
        return False
    if "fan fault" in t or "fan-fault" in t:
        return True
    if re.search(r"\be\s*2\b", t):
        return True
    if re.search(r"\b(?:2\s*[\s-]*flash|flash(?:es|ing)?\s*2|blink(?:ing)?\s*2)\b", t):
        return True
    if re.search(r"\bfreezer\s+(?:evaporator\s+)?fan\b", t):
        return True
    if re.search(r"\bfan\s+(?:amps?|amperage|current|volts?|voltage)\b", t):
        return True
    if F_PLUS_MINUS_RE.search(blob or "") and "fan" in t:
        return True
    return False


def is_fcr_e2_fan_fault_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Furrion FCR08/FCR10 fridge E2 / 2-flash / Fan Fault Current.
    Rooftop AC E2 (FACT / Brisk freeze sensor) must lose.
    """
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    cat = _norm(category_name)
    blob = _blob(category_name, model_text, symptom)
    if not blob and "refriger" not in cat and "fridge" not in cat:
        return False
    fridge = (
        "refriger" in cat
        or "fridge" in cat
        or any(k in blob for k in ("fridge", "reefer", "refriger", "fcr08", "fcr10", "fcr0", "fcr1"))
        or "ccd-0008122" in blob
        or "ccd0008122" in blob
        or _looks_like_furrion_fcr_fridge(blob)
    )
    if not fridge:
        return False
    return _has_fcr_e2_fan_fault_marker(blob)


def fcr_e2_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward Fan Fault Diagnostics + Fan Replacement."""
    symptom = (symptom or "").strip()
    if not is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {FAN_FAULT_SEARCH_BOOST}".strip()


def score_fcr_fan_fault_chunk(page, query: str = "") -> int:
    """
    Higher = Fan Fault Diagnostics / Fan Replacement on CCD-0008122.
    Spec-only Fan Fault Current and board-only R&R lose to fan pages.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    page_no = _page_number(page)
    score = 0
    if "fan fault" in t:
        score += 16
    if "fan fault diagnostics" in t or ("error code" in t and "fan" in t):
        score += 10
    if "fan replacement" in t:
        score += 18
    if any(
        k in t
        for k in (
            "inverter pcb and fan",
            "inverter pcb and the fan",
            "board and fan",
            "replace the inverter pcb and fan",
        )
    ):
        score += 16
    if F_PLUS_MINUS_RE.search(raw):
        score += 8
    if "evaporator fan" in t or ("freezer" in t and "fan" in t):
        score += 8
    if "airflow" in t and "fan" in t:
        score += 4
    if is_furrion_ccd_0008122(title) or is_furrion_ccd_0008122(t):
        score += 6
    if page_no in FURRION_FCR_FAN_FAULT_PAGES:
        score += 15
    if "fan fault current" in t and "replacement" not in t and "diagnostics" not in t:
        score -= 6
    board_rr = any(
        k in t
        for k in (
            "inverter pcb replacement",
            "driver board",
            "replace the inverter",
            "compressor inverter pcb replacement",
        )
    )
    if board_rr and "fan" not in t:
        score -= 12
    if any(k in t for k in ("rooftop", "air condition", "fact12", "facr", "brisk", "b57915")):
        score -= 16
    q = _norm(query)
    if q and any(k in q for k in ("e2", "fan fault", "2 flash", "freezer")):
        if "fan" in t:
            score += 4
    return score


def rank_chunks_for_fcr_fan_fault(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer Fan Fault Diagnostics + Fan Replacement over board-only R&R."""
    scored = [(score_fcr_fan_fault_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _sc, ch in scored:
        out.append(ch)
        if len(out) >= limit:
            break
    return out


def _match_not_negated(pattern, text: str) -> bool:
    """True if pattern matches a claim that is not a 'never / do not' instruction."""
    t = text or ""
    for m in pattern.finditer(t):
        line_start = t.rfind("\n", 0, m.start()) + 1
        prefix = t[line_start:m.start()].lower()
        if re.search(
            r"(never say|never treat|do not|don't|do not treat|not treat|not say)",
            prefix,
        ):
            continue
        return True
    return False


def claims_fcr_e2_board_only_cage(reply: str) -> bool:
    """True when a coach reply cages FCR E2 to board-only / 'no separate fan'."""
    t = reply or ""
    if not t:
        return False
    if _match_not_negated(FCR_E2_NO_SEPARATE_FAN_RE, t):
        return True
    if _match_not_negated(FCR_E2_BOARD_ONLY_RE, t):
        return True
    return False


def reply_names_freezer_fan_rr(reply: str) -> bool:
    """True when the reply already reaches freezer evaporator fan / Fan Replacement."""
    t = _norm(reply)
    if not t:
        return False
    if "fan replacement" in t:
        return True
    if any(k in t for k in ("freezer evaporator fan", "evaporator fan")) and any(
        k in t for k in ("replace", "r&r", "r & r")
    ):
        return True
    if any(
        k in t
        for k in (
            "inverter pcb and fan",
            "board and fan",
            "board + fan",
            "board and the fan",
        )
    ):
        return True
    return False


def reply_recommends_rear_board_rr(reply: str) -> bool:
    return bool(BOARD_RR_RE.search(reply or ""))


def fcr_e2_reply_needs_fan_rr(reply: str, facts: dict = None) -> bool:
    """
    True when this E2 turn would ship without freezer evaporator fan R&R:
    explicit board-only cage, or board R&R with fan volts/amps already reported.
    """
    if not (reply or "").strip():
        return False
    if claims_fcr_e2_board_only_cage(reply):
        return True
    facts = facts or {}
    readings = bool(facts.get("fan_volts") or facts.get("fan_amps"))
    if readings and reply_recommends_rear_board_rr(reply) and not reply_names_freezer_fan_rr(reply):
        return True
    return False


def strip_fcr_e2_board_only_claims(reply: str) -> str:
    """Drop sentences that deny a separate fan or say E2 is board-only."""
    if not reply or not claims_fcr_e2_board_only_cage(reply):
        return reply
    kept = []
    for part in re.split(r"(?<=[.!?])\s+", reply.strip()):
        if part and not claims_fcr_e2_board_only_cage(part):
            kept.append(part)
    return " ".join(kept).strip() or reply


def ensure_fcr_e2_fan_rr(reply: str, facts: dict = None) -> str:
    """
    Deterministic shop line so E2 cannot ship as board-only.
    Uses CCD-0008122 Fan Fault Diagnostics / Fan Replacement language already in-repo.
    """
    if not reply or not fcr_e2_reply_needs_fan_rr(reply, facts):
        return reply
    cleaned = strip_fcr_e2_board_only_claims(reply)
    if "includes fan replacement in repair section 2" in _norm(cleaned):
        return cleaned
    return f"{cleaned.rstrip()}\n\n{FCR_E2_FAN_RR_SHOP_LINE}".strip()


def is_cooktop_library_title(title: str) -> bool:
    """Catalog titles that are Suburban Range / Cooktops — not furnace-only, not Unity."""
    t = _norm(title)
    if not t or is_unity_board_manual(t):
        return False
    if "furnace" in t and "cooktop" not in t and "range" not in t:
        return False
    if "suburban" in t and any(k in t for k in ("range", "cooktop", "cook top")):
        return True
    if "range" in t and "cooktop" in t:
        return True
    if "range/cooktop" in t or "range & cooktop" in t or "ranges & cooktops" in t:
        return True
    return False


def is_stabilizer_library_title(title: str) -> bool:
    """PSX1 / stabilizer jack / rear stabilizer owner — not Level-Up hydraulic, not Unity."""
    t = _norm(title)
    if not t or is_unity_board_manual(t) or is_level_up_library_title(t):
        return False
    if "psx1" in t or "ccd-0007345" in t or "ccd0007345" in t:
        return True
    if "stabilizer" in t and any(k in t for k in ("jack", "owner", "psx", "lippert")):
        return True
    if "rear stabilizer" in t:
        return True
    return False


def _is_cooktop_range_blob(blob: str) -> bool:
    """True when the blob names a gas range / cooktop, not a Suburban furnace."""
    t = _norm(blob)
    if not t:
        return False
    if any(k in t for k in ("cooktop", "cook top", "cook-top", "range/cooktop", "range & cooktop")):
        return True
    if re.search(r"\branges?\s*&\s*cooktops?\b", t):
        return True
    if re.search(r"\bsuburban\s+range\b", t):
        return True
    if re.search(r"\b(?:gas|lp|propane)\s+range\b", t):
        return True
    if re.search(r"\bsdn\s*2", t):
        return True
    return False


def is_cooktop_range_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Suburban / gas range or cooktop job. Furnace-only Suburban must lose."""
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    if is_water_heater_context(category_name, model_text, symptom):
        return False
    cat = _norm(category_name)
    blob = _blob(category_name, model_text, symptom)
    if "cooktop" in cat or "cook top" in cat or re.search(r"\brange", cat):
        if "furnace" not in cat or _is_cooktop_range_blob(blob):
            return True
    if _is_cooktop_range_blob(blob):
        return True
    return False


def _has_pan_on_flameout_marker(blob: str) -> bool:
    """Pan/cookware + flame drops out, or thermocouple path with pan-on shutoff."""
    t = _norm(blob)
    if not t:
        return False
    pan = bool(re.search(r"\b(pan|pans|cookware|pot|pots|skillet)\b", t) or "pan-on" in t or "pan on" in t)
    flameout = bool(
        re.search(
            r"\b(goes?\s+out|go\s+out|went\s+out|flame[\s-]*out|shuts?\s+off|"
            r"shut\s+off|drops?\s+out|drop\s+out|flame\s+dies|goes?\s+off)\b",
            t,
        )
        or re.search(r"\blights?\b.{0,40}\b(then\s+)?(goes?|went|drops?)\s+out\b", t)
    )
    sensor = bool(re.search(r"\b(thermocouple|flame[\s-]*sensor)\b", t))
    if pan and flameout:
        return True
    if pan and sensor:
        return True
    if flameout and sensor:
        return True
    return False


def is_cooktop_pan_on_flameout_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Suburban / gas cooktop: burner lights, then goes out when a pan is placed.
    Furnace sail-switch / fridge / AC / water heater must lose.
    """
    if not is_cooktop_range_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    return _has_pan_on_flameout_marker(blob)


def is_cooktop_tip_sheet_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """Pan-on flameout or a thermocouple tip that sits low. Reposition the tip."""
    if is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return True
    if not is_cooktop_range_context(category_name, model_text, symptom):
        return False
    return cooktop_tip_sits_low(_blob(category_name, model_text, symptom))


def cooktop_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward Suburban Range/Cooktops + tip/pan."""
    symptom = (symptom or "").strip()
    if not is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {COOKTOP_SEARCH_BOOST}".strip()


def score_cooktop_pan_on_chunk(page, query: str = "", category: str = "") -> int:
    """
    Higher = Suburban Range/Cooktops + thermocouple tip / pan-on geometry.
    Furnace sail-switch / draft / igniter-first pages lose.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    cat = _norm(category)
    if isinstance(page, dict):
        cat = cat or _norm(str(page.get("category") or page.get("category_name") or ""))
    else:
        cat = cat or _norm(str(getattr(page, "category", "") or getattr(page, "category_name", "") or ""))
    score = 0
    if is_cooktop_library_title(title) or is_cooktop_library_title(t):
        score += 22
    if "suburban" in t and any(k in t for k in ("range", "cooktop")):
        score += 12
    if "cooktop" in t or "cook top" in t:
        score += 10
    if re.search(r"\brange", cat) or "cooktop" in cat:
        score += 8
    if "thermocouple" in t or "flame sensor" in t or "flame-sensor" in t:
        score += 10
    if any(k in t for k in ("tip", "position", "geometry")):
        score += 12
    if any(k in t for k in ("pan", "cookware", "pan-on", "pan on")):
        score += 12
    if q and any(k in q for k in ("pan", "cookware", "thermocouple", "tip")):
        if "thermocouple" in t or "tip" in t:
            score += 4
    if "sail switch" in t or ("furnace" in t and "cooktop" not in t and "range" not in t):
        score -= 16
    if "draft" in t and "cooktop" not in t:
        score -= 8
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 20
    if any(k in t for k in ("refriger", "fridge", "air condition", "gswh")) and "cooktop" not in t:
        score -= 10
    return score


def rank_chunks_for_cooktop_pan_on(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer Suburban Range/Cooktops tip/pan pages over furnace / igniter-first."""
    scored = [(score_cooktop_pan_on_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _sc, ch in scored:
        out.append(ch)
        if len(out) >= limit:
            break
    return out


def reply_names_cooktop_tip_pan_check(reply: str) -> bool:
    """True when the reply already tells the tech to check tip position with a pan on."""
    t = _norm(reply)
    if not t:
        return False
    tip = "tip" in t or "geometry" in t
    position = any(k in t for k in ("position", "geometry", "in the flame", "in the burner"))
    pan = any(k in t for k in ("pan", "cookware", "pot", "skillet"))
    return bool(tip and position and pan)


def reply_jumps_to_cooktop_parts_rr(reply: str) -> bool:
    """True when the reply condemns / R&Rs cooktop parts without a tip+pan check."""
    return bool(COOKTOP_PARTS_RR_RE.search(reply or ""))


def cooktop_reply_needs_tip_pan(reply: str) -> bool:
    """True when a pan-on flame-out turn would ship without tip/position/pan first."""
    if not (reply or "").strip():
        return False
    if reply_names_cooktop_tip_pan_check(reply) and reply_has_tip_pan_before_parts(reply):
        return False
    if reply_jumps_to_cooktop_parts_rr(reply):
        return True
    if COOKTOP_SKIP_AHEAD_RE.search(reply or "") and not reply_names_cooktop_tip_pan_check(reply):
        return True
    if not reply_names_cooktop_tip_pan_check(reply):
        return True
    return False


def reply_has_tip_pan_before_parts(reply: str) -> bool:
    """Success check: tip/position/pan appear before parts R&R (or no parts R&R yet)."""
    text = reply or ""
    if not reply_names_cooktop_tip_pan_check(text):
        return False
    t = _norm(text)
    tip_at = t.find("tip")
    if tip_at < 0:
        tip_at = t.find("geometry")
    pan_at = -1
    for key in ("cookware", "pan", "pot", "skillet"):
        idx = t.find(key)
        if idx >= 0 and (pan_at < 0 or idx < pan_at):
            pan_at = idx
    first_check = min(i for i in (tip_at, pan_at) if i >= 0)
    parts_at = None
    for m in COOKTOP_PARTS_RR_RE.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        prefix = text[line_start:m.start()].lower()
        if re.search(r"(before|never|do not|don't|not condemn|not replace)", prefix):
            continue
        parts_at = m.start()
        break
    if parts_at is None:
        return True
    return first_check < parts_at


_COOKTOP_OTHER_PAGES_RE = re.compile(
    r"do you have other pages|other pages from that manual|"
    r"do you have a different page(?: or section)?|different page or section",
    re.I,
)
_STRAY_PAGE_RE = re.compile(
    r"do you have (?:other pages|a different page(?: or section)?)"
    r"(?: from (?:that|the) [\w /-]+manual)?[^.?!\n]*[.?!]?",
    re.I,
)


def _strip_cooktop_contradiction(reply: str) -> str:
    """Drop a library-coverage denial and the follow-up ask for other pages."""
    text = _STRAY_PAGE_RE.sub("", strip_library_no_steps(reply or ""))
    kept = []
    for part in _reply_sentences(text):
        if _COOKTOP_OTHER_PAGES_RE.search(part):
            continue
        if claims_library_missing_steps(part):
            continue
        kept.append(part)
    return " ".join(kept).strip()


def _cooktop_cites_page4(reply: str) -> bool:
    t = _norm(reply)
    page = "page 4" in t or "p.4" in t or "p. 4" in t
    figs = "fig" in t
    return bool(page and figs)


def _with_cooktop_page4_cite(reply: str) -> str:
    text = _strip_cooktop_contradiction(reply or "").strip()
    if not text:
        return COOKTOP_TIP_PAN_SHOP_LINE
    if _cooktop_cites_page4(text):
        return text
    return f"{text.rstrip()}\n{COOKTOP_TIP_CITE}"


def ensure_cooktop_tip_pan_check(reply: str, complaint: str = "", history: list = None) -> str:
    """
    Deterministic shop line so pan-on flame-out cannot skip tip geometry.
    A low tip that the pan pushes gets that repair and cites SDN2U page 4, Figs. 3-4.
    A sentence that says the library does not cover tip position does not ship with the repair.
    """
    cleaned = _strip_cooktop_contradiction(reply or "")
    repair_ask = asks_what_is_the_repair(complaint or "") and _has_pan_on_flameout_marker(
        complaint or ""
    )
    if _COOKTOP_RUNON_RE.search(cleaned):
        if cooktop_tip_sits_low(f"{complaint or ''} {cleaned}") or repair_ask:
            return COOKTOP_TIP_LOW_REPAIR
        return COOKTOP_TIP_PAN_SHOP_LINE
    if cooktop_tip_sits_low(f"{complaint or ''} {cleaned}") or repair_ask:
        low = _norm(cleaned)
        if (
            "reposition" in low
            and "tip" in low
            and ("pan" in low or "cookware" in low)
            and _cooktop_cites_page4(cleaned)
            and not claims_library_missing_steps(cleaned)
        ):
            return cleaned
        return COOKTOP_TIP_LOW_REPAIR
    reply = cleaned
    if reply and reply_names_cooktop_tip_pan_check(reply) and reply_has_tip_pan_before_parts(reply):
        return _with_cooktop_page4_cite(reply)
    if not reply or not cooktop_reply_needs_tip_pan(reply):
        return reply
    if "with cookware on" in _norm(reply) and "tip" in _norm(reply):
        if reply_has_tip_pan_before_parts(f"{COOKTOP_TIP_PAN_SHOP_LINE}\n\n{reply}"):
            return _with_cooktop_page4_cite(f"{COOKTOP_TIP_PAN_SHOP_LINE}\n\n{reply}")
    return _with_cooktop_page4_cite(f"{COOKTOP_TIP_PAN_SHOP_LINE}\n\n{reply}")


def _is_stabilizer_blob(blob: str) -> bool:
    t = _norm(blob)
    if not t:
        return False
    if "psx1" in t or "ccd-0007345" in t or "ccd0007345" in t:
        return True
    if "stabilizer" in t:
        return True
    return False


def _has_override_pin_marker(blob: str) -> bool:
    t = _norm(blob)
    if not t:
        return False
    override = bool(
        re.search(
            r"\b(manual\s+crank|manual\s+override|hand\s+crank|override|"
            r"roll[\s-]*pin|override[\s-]*pin|coupler|crank)\b",
            t,
        )
    )
    broken = bool(
        re.search(
            r"\b(broken|seized|seize|sheared|destroyed|snapped|won't engage|"
            r"will not engage|wont engage|not engage|not serviceable)\b",
            t,
        )
    )
    power_ok = bool(re.search(r"\b(power|electric|extend|retract)\b", t))
    manual_fail = bool(
        re.search(r"\b(manual|crank|override)\b", t)
        and re.search(r"\b(won't|will not|wont|not engage|broken|seized)\b", t)
    )
    if override and broken:
        return True
    if power_ok and manual_fail:
        return True
    if ("roll pin" in t or "override pin" in t or "coupler" in t) and broken:
        return True
    return False


# BAL Soft-Touch SS 5.1 — electric tongue jack ONLY dead.
# Other stabilizers and panel lights still work. Climax is the soft-touch
# user panel 20300427, or a tongue-pigtail repair after the panel voltage prove.
# Coupler / shear-pin / 30A fuse / remote stab harness are not the primary.
BAL_TONGUE_PART = "20300427"
BAL_TONGUE_DOC = "INS.STA.001"
BAL_TONGUE_SOURCE = "📖 Source: BAL SS 5.1 Stabilizing System INS.STA.001"
BAL_TONGUE_SEARCH_BOOST = (
    "BAL Soft-Touch SS 5.1 INS.STA.001 20300427 soft-touch user panel "
    "tongue jack output wire pigtail panel-to-motor"
)
BAL_TONGUE_PRODUCT_LOCK = """
BAL SOFT-TOUCH SS 5.1 TONGUE JACK ONLY DEAD (INS.STA.001):
- Named branch: electric tongue jack dead, other stabilizers still work, soft-touch panel lights still work. Motor OK on direct 12V and coupler OK is this complaint.
- Order: (1) Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel. (2) Then the local tongue pigtail / panel-to-motor leads. (3) No 12V on the tongue output wire → replace soft-touch user panel 20300427. 12V present on that wire → repair the tongue pigtail.
- Do NOT lead with coupler, shear-pin, or coupler replacement. Do NOT lead with the fuse, a 30A supply fuse, or the remote stabilizer harness.
- Coupler path ONLY if the manual override will not turn, or the motor fails a direct-12V prove. That is not this complaint when the motor runs on direct 12V and the coupler is engaged.
- Cite INS.STA.001. Do not invent a page number.
"""
BAL_TONGUE_PROVE_SHOP_LINE = (
    "The electric tongue jack is the only jack that is dead. The other stabilizers "
    "and the soft-touch panel lights still work.\n"
    "1. Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel. "
    "Report that voltage.\n"
    + BAL_TONGUE_SOURCE
)
BAL_TONGUE_PANEL_SHOP_LINE = (
    "No 12V on the tongue jack output wire at the panel, and the other stabilizers and panel lights still work. "
    "Replace the soft-touch user panel 20300427. Do not replace the coupler or the shear pin, and do not open "
    "the 30A fuse or the remote stabilizer harness.\n"
    + BAL_TONGUE_SOURCE
)
BAL_TONGUE_PIGTAIL_SHOP_LINE = (
    "12V is present on the tongue jack output wire at the panel. Repair the local tongue pigtail and the "
    "panel-to-motor leads. That is the confirmed correction after the panel voltage prove. "
    "Do not replace the coupler or open the 30A fuse or the remote stabilizer harness.\n"
    + BAL_TONGUE_SOURCE
)
BAL_TONGUE_COUPLER_SHOP_LINE = (
    "The manual override will not turn, or the motor failed a direct-12V prove. "
    "Replace the coupler. Do not start on the 30A fuse or the remote stabilizer harness, "
    "and do not replace the soft-touch user panel as the primary part for this prove.\n"
    + BAL_TONGUE_SOURCE
)
_BAL_FAMILY_RE = re.compile(
    r"\b(bal|norco|soft[\s-]*touch|ss\s*5\.1|ss5\.1|20300427|ins\.?\s*sta\.?\s*001)\b",
    re.I,
)
_TONGUE_DEAD_RE = re.compile(
    r"\btongue\b.{0,48}\b(dead|inop(?:erative)?|won't|wont|will not|does not|doesn't|not work|only)\b|"
    r"\b(dead|inop(?:erative)?|only)\b.{0,32}\btongue\b|"
    r"\btongue(?:\s+jack)?\s+only\b",
    re.I,
)
_STABS_OK_RE = re.compile(
    r"\b(stab(?:ilizer)?s?|stabilizers?|other jacks?)\b.{0,48}\b(work|works|working|ok|good|fine|operate)\b|"
    r"\b(work|works|working|ok|good)\b.{0,24}\b(stab(?:ilizer)?s?|stabilizers?)\b",
    re.I,
)
_LIGHTS_OK_RE = re.compile(
    r"\b(panel\s+)?lights?\b.{0,32}\b(work|works|working|ok|good|on)\b|"
    r"\blights?\s+(?:still\s+)?(?:work|works|working|ok|on|good)\b",
    re.I,
)
_ALL_JACKS_DEAD_RE = re.compile(
    r"\b(all|both|no)\s+(?:the\s+)?(?:jacks|stabilizers)\b.{0,24}\b(dead|won't|wont|not)\b|"
    r"\bstabilizers?\b.{0,24}\b(also\s+)?(dead|won't|wont|do not work|don't work)\b|"
    r"\bno\s+lights?\b|\blights?\s+(?:are\s+)?(?:out|dead|off)\b",
    re.I,
)
_BAL_BANNED_PRIMARY_RE = re.compile(
    r"("
    r"\bcoupler\b|"
    r"shear[\s-]*pin|"
    r"\b21700072\b|"
    r"\b30\s*a\b|"
    r"\bfuse\b|"
    r"remote\s+stab|"
    r"stabilizer harness"
    r")",
    re.I,
)
_BAL_FUSE_HARNESS_RE = re.compile(
    r"(\b30\s*a\b|\bfuse\b|remote\s+stab|stabilizer harness)",
    re.I,
)


def _bal_override_wont_turn(text: str) -> bool:
    return bool(
        re.search(
            r"\b(override|manual)\b.{0,48}\b(won't|wont|will not|does not|doesn't|cannot|can't)\s+turn\b|"
            r"\b(won't|wont|will not|does not)\s+turn\b.{0,32}\b(override|manual)\b",
            text or "",
            re.I,
        )
    )


_BAL_MOTOR_OK_RE = re.compile(
    r"\bmotor\b.{0,48}\b(ok|good|fine|runs|running|operates|operated|worked)\b|"
    r"\b(operates|runs|running|worked|ok)\b.{0,40}\b(?:on\s+|using\s+)?direct\s*12",
    re.I,
)
_BAL_MOTOR_FAIL_RE = re.compile(
    r"\bmotor\b.{0,56}\b(fail(?:s|ed)?|dead|no run|does not|doesn't|won't|wont|not operate|not run)\b|"
    r"\b(fail(?:s|ed)?|does not|doesn't|won't|wont)\b.{0,40}\b(?:run|operate).{0,32}\b(?:direct\s*12|12\s*v)\b|"
    r"\bdirect\s*12\s*v\b.{0,40}\b(fail(?:s|ed)?|dead|no run|does not|doesn't|won't|wont)\b",
    re.I,
)


def _bal_motor_direct_result(text: str) -> str:
    """OK or fail only when the words attach to the motor / direct-12V prove.

    A dead tongue jack in the same sentence is not a failed motor. Explicit
    "motor OK / runs on direct 12V" wins over that nearby "dead".
    """
    raw = text or ""
    if not re.search(r"\bmotor\b", raw, re.I):
        return ""
    if not re.search(r"\b(direct\s*12\s*v|12\s*v)\b", raw, re.I):
        return ""
    ok = _BAL_MOTOR_OK_RE.search(raw)
    fail = _BAL_MOTOR_FAIL_RE.search(raw)
    if ok and not fail:
        return "ok"
    if fail and not ok:
        return "fail"
    if ok and fail:
        return "ok" if ok.start() <= fail.start() else "fail"
    return ""


def bal_tongue_coupler_exception(text: str) -> bool:
    """Coupler is allowed only when override will not turn or the motor fails direct 12V."""
    if _bal_override_wont_turn(text or ""):
        return True
    return _bal_motor_direct_result(text or "") == "fail"


def is_bal_soft_touch_tongue_only_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    BAL / Norco Soft-Touch SS 5.1: tongue jack only is dead, stabilizers and
    panel lights still work. Not PSX1, not Level Up, not an all-jacks-dead power loss.
    """
    blob = _blob(category_name, model_text, symptom)
    if not blob or not _BAL_FAMILY_RE.search(blob):
        return False
    if looks_like_facr_rooftop(category_name, model_text, symptom):
        return False
    if _looks_like_furrion_fcr_fridge(blob):
        return False
    if any(k in blob for k in ("water heat", "cooktop", "furnace")):
        return False
    if _ALL_JACKS_DEAD_RE.search(blob):
        return False
    tongue_dead = bool(_TONGUE_DEAD_RE.search(blob)) or (
        "tongue" in blob and any(k in blob for k in ("dead", "won't", "wont", "will not", "does not", "inop", "only"))
    )
    if not tongue_dead:
        return False
    stabs_ok = bool(_STABS_OK_RE.search(blob))
    lights_ok = bool(_LIGHTS_OK_RE.search(blob))
    only = bool(re.search(r"\b(tongue(?:\s+jack)?\s+only|only(?:\s+the)?\s+tongue)\b", blob))
    return bool(stabs_ok or lights_ok or only)


def extract_bal_tongue_facts(text: str) -> dict:
    """Stage facts for the tongue-only path. Does not require the full complaint."""
    raw = text or ""
    norm = _norm(raw)
    if not norm:
        return {}
    facts = {}
    if re.search(
        r"(no|0|zero|missing|without)\s+12\s*v.{0,64}tongue|"
        r"\b0\s*v.{0,80}\b(?:tongue|panel)\b|"
        r"tongue (?:jack )?output(?: wire)?.{0,40}(no|0|zero|missing|dead)\s*12|"
        r"tongue channel.{0,40}(no|0|zero|missing|dead)\s*12|"
        r"no voltage.{0,32}tongue (?:jack )?output|"
        r"no voltage.{0,24}tongue channel",
        norm,
    ):
        facts["tongue_channel_volts"] = "missing"
    elif re.search(
        r"12\s*v.{0,72}tongue (?:jack )?output|"
        r"tongue (?:jack )?output(?: wire)?.{0,40}(has|have|shows|reads|present|good|ok)|"
        r"12\s*v.{0,48}tongue channel|tongue channel.{0,40}(has|have|shows|reads|present|good|ok)|"
        r"(have|has|shows)\s+12\s*v.{0,32}tongue",
        norm,
    ):
        facts["tongue_channel_volts"] = "present"
    motor = _bal_motor_direct_result(raw)
    if motor:
        facts["tongue_motor_12v"] = motor
    if re.search(r"\bcoupler\b", norm) and re.search(r"\b(ok|good|engaged|fine)\b", norm):
        if not re.search(r"\bcoupler\b.{0,24}\b(bad|broken|sheared|stripped|failed)\b", norm):
            facts["tongue_coupler"] = "ok"
    elif re.search(r"\b(shear[\s-]*pin|coupler\b.{0,24}\b(bad|broken|sheared|stripped))\b", norm):
        facts["tongue_coupler"] = "bad"
    if _bal_override_wont_turn(raw):
        facts["tongue_override"] = "wont_turn"
    elif re.search(r"\boverride\b.{0,32}\b(turns|turned|works|working)\b", norm):
        facts["tongue_override"] = "turns"
    if re.search(r"\bpigtail\b", norm) and re.search(
        r"\b(open|bad|broken|repair|failed|no continuity)\b", norm
    ):
        facts["tongue_pigtail"] = "bad"
    elif re.search(r"\bpigtail\b", norm) and re.search(r"\b(ok|good|fine)\b", norm):
        facts["tongue_pigtail"] = "good"
    return facts


def bal_tongue_stage(facts: dict | None) -> str:
    """prove | panel | pigtail | coupler."""
    facts = facts or {}
    if facts.get("tongue_override") == "wont_turn" or facts.get("tongue_motor_12v") == "fail":
        return "coupler"
    if facts.get("tongue_channel_volts") == "missing":
        return "panel"
    if facts.get("tongue_channel_volts") == "present":
        return "pigtail"
    return "prove"


def bal_tongue_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if not is_bal_soft_touch_tongue_only_context(category_name, model_text, symptom):
        return symptom
    if BAL_TONGUE_SEARCH_BOOST in symptom:
        return symptom
    return f"{symptom} {BAL_TONGUE_SEARCH_BOOST}".strip()


def score_bal_tongue_chunk(page, query: str = "", category: str = "") -> int:
    """
    Higher = INS.STA.001 / soft-touch user panel 20300427 / tongue output wire.
    Coupler, shear-pin, 30A, and remote-harness pages lose on the tongue-only class.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    score = 0
    if "20300427" in t:
        score += 24
    if "ins.sta.001" in t or "ins sta 001" in t:
        score += 18
    if "soft-touch" in t or "soft touch" in t or "user panel" in t:
        score += 12
    if "tongue" in t and any(k in t for k in ("pigtail", "channel", "panel")):
        score += 10
    if "ss 5.1" in t or "ss5.1" in t:
        score += 8
    if "bal" in t and "tongue" in t:
        score += 6
    if q and "20300427" in q and "20300427" in t:
        score += 6
    coupler_exception = bal_tongue_coupler_exception(q)
    if not coupler_exception:
        if any(
            k in t
            for k in (
                "21700072",
                "shear pin",
                "shear-pin",
                "coupler replacement",
                "replace the coupler",
            )
        ):
            score -= 22
        if any(k in t for k in ("30a", "30 a", "remote stab", "stabilizer harness")) and "20300427" not in t:
            score -= 16
    return score


_BAL_OFF_PATH_PAGE_RE = re.compile(
    r"(21700072|shear[\s-]*pin|coupler replacement|replace the coupler|"
    r"30\s*a\b|remote\s+stab|stabilizer harness)",
    re.I,
)


def rank_chunks_for_bal_tongue(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer 20300427 / INS.STA.001. Drop coupler and fuse pages when a panel hit exists."""
    scored = [(score_bal_tongue_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    has_panel = any(
        sc > 0 and "20300427" in _norm(f"{_page_title(ch)} {_page_text_blob(ch)}")
        for sc, ch in scored
    )
    coupler_exception = bal_tongue_coupler_exception(query)
    out = []
    for sc, ch in scored:
        blob = f"{_page_title(ch)} {_page_text_blob(ch)}"
        off_path = bool(_BAL_OFF_PATH_PAGE_RE.search(blob)) and "20300427" not in blob
        if has_panel and not coupler_exception and (sc < 0 or off_path):
            continue
        out.append(ch)
        if len(out) >= limit:
            break
    return out or [ch for _sc, ch in scored[:limit]]


def _first_unnegated(text: str, pattern: re.Pattern):
    for m in pattern.finditer(text or ""):
        if _mention_is_negated(text, m.start()):
            continue
        return m.start()
    return None


def reply_leads_with_bal_banned_primary(reply: str) -> bool:
    """Coupler / shear-pin / fuse / 30A / remote harness is the first action."""
    text = reply or ""
    banned_at = _first_unnegated(text, _BAL_BANNED_PRIMARY_RE)
    if banned_at is None:
        return False
    prove_at = None
    for pat in (
        r"20300427",
        r"tongue channel",
        r"tongue output",
        r"output wire",
        r"tongue pigtail",
        r"soft-touch user panel",
    ):
        m = re.search(pat, text, re.I)
        if m and (prove_at is None or m.start() < prove_at):
            prove_at = m.start()
    if prove_at is None:
        return True
    return banned_at < prove_at


def reply_leads_with_bal_fuse_harness(reply: str) -> bool:
    text = reply or ""
    fuse_at = _first_unnegated(text, _BAL_FUSE_HARNESS_RE)
    if fuse_at is None:
        return False
    action_at = None
    for pat in (
        r"\bcoupler\b",
        r"20300427",
        r"tongue channel",
        r"tongue output",
        r"output wire",
        r"tongue pigtail",
    ):
        m = re.search(pat, text, re.I)
        if m and (action_at is None or m.start() < action_at):
            action_at = m.start()
    if action_at is None:
        return True
    return fuse_at < action_at


def reply_names_tongue_channel_prove(reply: str) -> bool:
    t = _norm(reply)
    names_output = bool(
        re.search(r"tongue (?:jack )?output(?: wire)?|tongue channel", t)
    )
    return names_output and bool(re.search(r"12\s*v", t))


def reply_names_panel_20300427(reply: str) -> bool:
    return BAL_TONGUE_PART in (reply or "")


def reply_names_pigtail_repair(reply: str) -> bool:
    t = _norm(reply)
    return "pigtail" in t and bool(re.search(r"\b(repair|replace|open|bad)\b", t))


def reply_names_coupler_path(reply: str) -> bool:
    t = _norm(reply)
    return "coupler" in t and not reply_leads_with_bal_fuse_harness(reply)


def bal_tongue_reply_needs_guard(reply: str, facts: dict | None = None) -> bool:
    facts = facts or {}
    stage = bal_tongue_stage(facts)
    if stage == "coupler":
        if reply_leads_with_bal_fuse_harness(reply):
            return True
        return not reply_names_coupler_path(reply)
    if reply_leads_with_bal_banned_primary(reply):
        return True
    if stage == "panel":
        if not reply_names_panel_20300427(reply) or not reply_names_tongue_channel_prove(reply):
            return True
        # The prove script still asks for the 12V check. The panel is the repair.
        return _reply_asks_check(reply, _REPEATED_CHECK_RES[2][1])
    if stage == "pigtail":
        return not reply_names_pigtail_repair(reply) or not reply_names_tongue_channel_prove(reply)
    return not (
        reply_names_tongue_channel_prove(reply)
        and reply_names_panel_20300427(reply)
        and reply_names_pigtail_repair(reply)
    )


def _strip_bal_banned_primary_sentences(reply: str) -> str:
    if not reply:
        return ""
    kept = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", reply.strip()):
        if not part:
            continue
        if reply_leads_with_bal_banned_primary(part) or reply_leads_with_bal_fuse_harness(part):
            continue
        kept.append(part)
    return " ".join(kept).strip()


def ensure_bal_tongue_only_path(reply: str, facts: dict | None = None) -> str:
    """
    Tongue-only dead with stabilizers and panel lights working cannot ship
    coupler-first or fuse-first. Climax is 20300427 or the tongue pigtail.
    """
    facts = facts or {}
    stage = bal_tongue_stage(facts)
    if stage == "prove":
        if reply_names_panel_20300427(reply) or not reply_names_tongue_channel_prove(reply):
            return BAL_TONGUE_PROVE_SHOP_LINE
        return reply or ""
    lines = {
        "coupler": BAL_TONGUE_COUPLER_SHOP_LINE,
        "panel": BAL_TONGUE_PANEL_SHOP_LINE,
        "pigtail": BAL_TONGUE_PIGTAIL_SHOP_LINE,
        "prove": BAL_TONGUE_PROVE_SHOP_LINE,
    }
    shop = lines[stage]
    if not bal_tongue_reply_needs_guard(reply, facts):
        return reply
    if stage == "coupler":
        cleaned = reply or ""
        if reply_leads_with_bal_fuse_harness(cleaned):
            cleaned = _strip_bal_banned_primary_sentences(cleaned)
        if reply_names_coupler_path(cleaned) and not reply_leads_with_bal_fuse_harness(cleaned):
            return cleaned
        return f"{shop}\n\n{cleaned}".strip()
    cleaned = _strip_bal_banned_primary_sentences(reply or "")
    if not bal_tongue_reply_needs_guard(cleaned, facts):
        return cleaned
    return f"{shop}\n\n{cleaned}".strip()


def is_stabilizer_override_pin_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Front stabilizer / PSX1: power works, manual override will not engage
    (broken/seized roll pin). Level-Up hydraulic 807662 must lose.
    BAL Soft-Touch tongue-only dead is a different path.
    """
    if is_bal_soft_touch_tongue_only_context(category_name, model_text, symptom):
        return False
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    if is_water_heater_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if not _is_stabilizer_blob(blob):
        return False
    if any(p in blob for p in LEVEL_UP_PARTS) or "octp" in blob or re.search(r"\blevel[\s-]*up\b", blob):
        return False
    return _has_override_pin_marker(blob)


def stabilizer_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward PSX1 / complete jack assembly."""
    symptom = (symptom or "").strip()
    if not is_stabilizer_override_pin_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {PSX1_SEARCH_BOOST}".strip()


def score_stabilizer_override_chunk(page, query: str = "", category: str = "") -> int:
    """
    Higher = PSX1 / stabilizer jack / complete assembly.
    Coupler-only and override-usage-only pages lose to assembly R&R.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    cat = _norm(category)
    if isinstance(page, dict):
        cat = cat or _norm(str(page.get("category") or page.get("category_name") or ""))
    else:
        cat = cat or _norm(str(getattr(page, "category", "") or getattr(page, "category_name", "") or ""))
    score = 0
    if is_stabilizer_library_title(title) or is_stabilizer_library_title(t):
        score += 22
    if "psx1" in t or "ccd-0007345" in t or "ccd0007345" in t:
        score += 14
    if "stabilizer" in t and "jack" in t:
        score += 12
    if "leveling" in cat and "stabilizer" in t:
        score += 6
    if "complete" in t and "assembly" in t:
        score += 16
    if "roll pin" in t or "override" in t:
        score += 6
    if q and any(k in q for k in ("psx1", "stabilizer", "roll pin", "override")):
        if "stabilizer" in t or "psx1" in t:
            score += 4
    if re.search(r"\bcoupler\b", t) and "assembly" not in t:
        score -= 10
    if "override usage" in t or ("how to use" in t and "override" in t):
        score -= 8
    if is_level_up_library_title(title) or is_level_up_library_title(t):
        score -= 20
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 20
    return score


def rank_chunks_for_stabilizer_override(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer PSX1 / complete jack assembly over coupler-only or override-usage-only."""
    scored = [(score_stabilizer_override_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _sc, ch in scored:
        out.append(ch)
        if len(out) >= limit:
            break
    return out


def claims_coupler_only_rr(reply: str) -> bool:
    """True when a coach reply treats coupler-only as the end fix."""
    t = reply or ""
    if not t:
        return False
    for m in COUPLER_ONLY_RE.finditer(t):
        line_start = t.rfind("\n", 0, m.start()) + 1
        prefix = t[line_start:m.start()].lower()
        if re.search(r"(never|do not|don't|not a |not the |not treat)", prefix):
            continue
        return True
    return False


def reply_recommends_complete_jack_assembly(reply: str) -> bool:
    t = reply or ""
    if COMPLETE_JACK_ASSEMBLY_RE.search(t):
        return True
    n = _norm(t)
    if "complete" in n and "assembly" in n and any(k in n for k in ("replace", "r&r", "r & r")):
        if "jack" in n or "stabilizer" in n:
            return True
    return False


def stabilizer_reply_needs_assembly_rr(reply: str, facts: dict = None) -> bool:
    """True when a broken/seized override-pin turn would ship coupler-only or no assembly."""
    if not (reply or "").strip():
        return False
    if claims_coupler_only_rr(reply):
        return True
    facts = facts or {}
    pin_known = facts.get("override_pin") == "broken_or_seized"
    n = _norm(reply)
    pin_in_reply = bool(
        re.search(r"\b(roll[\s-]*pin|override[\s-]*pin|coupler)\b", n)
        and re.search(r"\b(broken|seized|seize|sheared|destroyed|not serviceable)\b", n)
    )
    if (pin_known or pin_in_reply) and not reply_recommends_complete_jack_assembly(reply):
        return True
    return False


def strip_coupler_only_claims(reply: str) -> str:
    """Drop sentences that recommend coupler-only R&R."""
    if not reply or not claims_coupler_only_rr(reply):
        return reply
    kept = []
    for part in re.split(r"(?<=[.!?])\s+", reply.strip()):
        if part and not claims_coupler_only_rr(part):
            kept.append(part)
    return " ".join(kept).strip() or reply


def ensure_stabilizer_assembly_rr(reply: str, facts: dict = None) -> str:
    """
    Deterministic shop line so a destroyed override pin cannot ship as coupler-only.
    """
    facts = facts or {}
    user_said_pin = facts.get("override_pin") == "broken_or_seized"
    if not user_said_pin:
        if re.search(r"\b(?:replace|r\s*&\s*r)\b", reply or "", re.I) and re.search(
            r"jack|stabilizer", reply or "", re.I
        ):
            return PSX1_PROVE_LINE
        return reply or PSX1_PROVE_LINE
    if not reply or not stabilizer_reply_needs_assembly_rr(reply, facts):
        return reply
    cleaned = strip_coupler_only_claims(reply)
    if reply_recommends_complete_jack_assembly(cleaned) and not claims_coupler_only_rr(cleaned):
        return cleaned
    if "complete front stabilizer jack assembly" in _norm(cleaned):
        return cleaned
    return f"{cleaned.rstrip()}\n\n{PSX1_ASSEMBLY_RR_SHOP_LINE}".strip()


def _is_fridge_job_blob(category_name: str = "", blob: str = "") -> bool:
    """True when category/model/symptom is a fridge job (Furrion FCR / Arctic / similar)."""
    cat = _norm(category_name)
    t = _norm(blob)
    if "refriger" in cat or "fridge" in cat:
        return True
    if FACR_MODEL_RE.search(t):
        return False
    if any(k in t for k in ("fridge", "reefer", "refriger", "fcr08", "fcr10", "fcr0", "fcr1")):
        return True
    if "ccd-0008122" in t or "ccd0008122" in t:
        return True
    if _looks_like_furrion_fcr_fridge(t):
        return True
    if "arctic" in t and any(
        k in t for k in ("fridge", "refriger", "ice", "icing", "frost", "moisture")
    ):
        return True
    return False


def _has_ice_moisture_marker(blob: str) -> bool:
    """
    Rear/back-wall ice, frost, icing (incl. half from the top), or moisture
    in the fridge cavity. Does not treat 'freezes contents' / E2 as this path.
    """
    t = _norm(blob)
    if not t:
        return False
    if "ice and moisture" in t or "ice or moisture" in t:
        return True
    if re.search(r"\bmoisture\b", t) and any(
        k in t for k in ("cavity", "fridge", "refriger", "in the fridge")
    ):
        return True
    ice = bool(re.search(r"\b(ice|icing|frost|frosting)\b", t))
    if not ice:
        return False
    if re.search(r"\b(rear|back)\s+wall\b", t):
        return True
    if re.search(r"\b(rear|back)\b", t) and re.search(r"\bwall\b", t):
        return True
    if re.search(r"\bhalf\b.{0,28}(top|from the top)", t) or "from the top" in t:
        return True
    if ice and any(k in t for k in ("cavity", "in the fridge", "rear", "back")):
        return True
    return False


def is_fridge_no_power_complaint(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """True when the complaint is no power / dead / won't run / no light."""
    blob = _blob(category_name, model_text, symptom)
    return bool(FRIDGE_NO_POWER_RE.search(blob))


def is_fridge_ice_moisture_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Fridge rear/back-wall ice/frost/moisture → CCD-0008122 Ice and Moisture p.36.
    Explicit no-power / E2 / AC / water-heater / cooktop / stab jobs lose.
    """
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    if is_water_heater_context(category_name, model_text, symptom):
        return False
    if is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return False
    if is_stabilizer_override_pin_context(category_name, model_text, symptom):
        return False
    if is_fcr_dial_off_compressor_run_context(category_name, model_text, symptom):
        return False
    if is_fridge_no_power_complaint(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if not _is_fridge_job_blob(category_name, blob):
        return False
    return _has_ice_moisture_marker(blob)


def ice_moisture_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward Ice and Moisture p.36 / Fig.36 — not fuse/12V."""
    symptom = (symptom or "").strip()
    if not is_fridge_ice_moisture_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {ICE_MOISTURE_SEARCH_BOOST}".strip()


def score_ice_moisture_chunk(page, query: str = "", category: str = "") -> int:
    """
    Higher = CCD-0008122 Ice and Moisture / Ice or Moisture in the Fridge p.36 / Fig.36.
    Fuse / 12V / no-power inverter pages lose.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    cat = _norm(category)
    if isinstance(page, dict):
        cat = cat or _norm(str(page.get("category") or page.get("category_name") or ""))
    else:
        cat = cat or _norm(str(getattr(page, "category", "") or getattr(page, "category_name", "") or ""))
    page_no = _page_number(page)
    score = 0
    if "ice and moisture" in t or "ice or moisture" in t:
        score += 22
    if "moisture in the fridge" in t or "moisture in fridge" in t:
        score += 16
    if any(k in t for k in ("rear wall", "back wall", "frost", "icing")):
        score += 12
    if "gasket" in t or "door seal" in t:
        score += 10
    if "dial" in t and "max" in t:
        score += 6
    if page_no in FURRION_FCR_ICE_MOISTURE_PAGES:
        score += 18
    if "fig. 36" in t or "fig 36" in t or "figure 36" in t:
        score += 12
    if is_furrion_ccd_0008122(title) or is_furrion_ccd_0008122(t):
        score += 6
    if "refriger" in cat or "fridge" in cat:
        score += 4
    if q and any(k in q for k in ("ice", "frost", "moisture", "rear wall", "gasket")):
        if any(k in t for k in ("ice", "moisture", "frost", "gasket")):
            score += 4
    fuse_or_power = any(
        k in t
        for k in (
            "15a",
            "15 a",
            "front vent",
            "fuse location",
            "no power",
            "inverter pcb",
            "12v inverter",
        )
    )
    ice_page = any(k in t for k in ("ice and moisture", "ice or moisture", "moisture in the fridge"))
    if fuse_or_power and not ice_page:
        score -= 16
    if "fuse" in t and not ice_page:
        score -= 10
    if "fan fault" in t or "fan replacement" in t:
        score -= 8
    if is_unity_board_manual(title) or is_unity_board_manual(t):
        score -= 20
    return score


def rank_chunks_for_ice_moisture(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer Ice and Moisture p.36 / Fig.36 over fuse / 12V no-power pages."""
    scored = [(score_ice_moisture_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for _sc, ch in scored:
        out.append(ch)
        if len(out) >= limit:
            break
    return out


def reply_opens_fuse_12v_no_power(reply: str) -> bool:
    """True when a coach reply opens the No Power / fuse / 12V inverter tree."""
    t = reply or ""
    if not t:
        return False
    for m in FUSE_12V_PATH_RE.finditer(t):
        line_start = t.rfind("\n", 0, m.start()) + 1
        prefix = t[line_start:m.start()].lower()
        window = t[max(0, m.start() - 90):m.start()].lower()
        if re.search(
            r"(never|do not|don't|not a |not the |unless |not open|"
            r"do not open|not a no-power|not no-power|not a no power)",
            f"{window} {prefix}",
        ):
            continue
        return True
    return False


def reply_names_ice_moisture_p36(reply: str) -> bool:
    """True when the reply already cites Ice and Moisture p.36 / Fig.36."""
    t = _norm(reply)
    if not t:
        return False
    ice = (
        "ice and moisture" in t
        or "ice or moisture" in t
        or ("moisture" in t and "fridge" in t)
    )
    page = any(
        k in t
        for k in (
            "page 36",
            "p.36",
            "p. 36",
            "fig. 36",
            "fig 36",
            "figure 36",
            "fig.36",
        )
    )
    return bool(ice and page)


def ice_moisture_reply_needs_guard(reply: str) -> bool:
    """True when a rear-wall ice turn would ship on fuse/12V or without p.36."""
    if not (reply or "").strip():
        return False
    if reply_names_ice_moisture_p36(reply) and not reply_opens_fuse_12v_no_power(reply):
        return False
    if reply_opens_fuse_12v_no_power(reply):
        return True
    if not reply_names_ice_moisture_p36(reply):
        return True
    return False


def strip_fuse_12v_no_power_claims(reply: str) -> str:
    """Drop sentences that open the fuse / 12V no-power tree."""
    if not reply or not reply_opens_fuse_12v_no_power(reply):
        return reply
    kept = []
    for part in re.split(r"(?<=[.!?])\s+", reply.strip()):
        if part and not reply_opens_fuse_12v_no_power(part):
            kept.append(part)
    return " ".join(kept).strip()


def _ice_has_month_close(reply: str) -> bool:
    t = _norm(reply)
    return "1 month" in t and "replace the unit" in t


def ensure_fridge_ice_moisture_path(reply: str) -> str:
    """
    Deterministic shop line so rear-wall ice cannot ship as fuse / 12V no-power.
    The first ask is the dial. Cooling-unit replacement waits until heavy frost returns.
    """
    if reply and reply_names_ice_moisture_p36(reply) and not ice_moisture_reply_needs_guard(reply):
        return reply
    if not reply or not ice_moisture_reply_needs_guard(reply):
        return reply
    cleaned = strip_fuse_12v_no_power_claims(reply)
    if cleaned and reply_opens_fuse_12v_no_power(cleaned):
        cleaned = ""
    if reply_names_ice_moisture_p36(cleaned) and not reply_opens_fuse_12v_no_power(cleaned):
        return cleaned
    if cleaned and not reply_opens_fuse_12v_no_power(cleaned) and "dial" in _norm(cleaned):
        return cleaned
    return ICE_MOISTURE_SHOP_LINE


# Furrion Arctic FCR08/FCR10 — dial/control OFF, compressor still running / overcooling.
# Locked climax cites: open C (blue) / T (black) — inverse of the p.31 jumper —
# then, if the compressor stops, R&R part G 2021128850 on p.43–45.
# Locked cites for this prove are p.31 and p.43–45 only.
FURRION_FCR_DIAL_OFF_RUN_PAGES = (31, 43, 44, 45)
FCR_DIAL_OFF_RUN_PART = "2021128850"
FCR_DIAL_OFF_RUN_RETAIL = "C-FCR10DCGTA-007"
_PART_G_CANDIDATE_RE = re.compile(r"\b20\d{8}\b")


def is_transposed_spark_free_part(token: str) -> bool:
    """True for a digit transposition of part G 2021128850. The exact PN is not a hit."""
    token = (token or "").strip()
    if token == FCR_DIAL_OFF_RUN_PART or len(token) != 10 or not token.isdigit():
        return False
    return sorted(token) == sorted(FCR_DIAL_OFF_RUN_PART)


def lock_spark_free_part_g(text: str) -> str:
    """Force every transposed Part G number back to exactly 2021128850."""
    if not text:
        return text or ""

    def repl(match):
        token = match.group(0)
        if is_transposed_spark_free_part(token):
            return FCR_DIAL_OFF_RUN_PART
        return token

    return _PART_G_CANDIDATE_RE.sub(repl, text)
DIAL_OFF_RUN_SEARCH_BOOST = (
    "Spark-Free Thermostat temperature controller Thermostat Replacement "
    "flag terminals C blue T black probe seated Fig. 24 Fig. 25 "
    "part 2021128850 Repair Section 2"
)
DIAL_OFF_RUN_PRODUCT_LOCK = """
FURRION FCR08/FCR10 DIAL OFF / COMPRESSOR STILL RUNNING (CCD-0008122):
- Named branch: temperature dial or control OFF and the compressor still runs, or the fridge/freezer overcools (won't shut off, runs when Off, overcooling with dial Off, freezer frozen solid with control Off). Family is Furrion Arctic FCR08/FCR10 / FCR10DCGTA-class.
- Compressor already running AND overcool proven means 12V is live. Do NOT lead with Fuse Diagnostics (p.19), 12V continuity (p.20), or diagnostic LED flash / inverter control voltage (p.18).
- Coach order, one or two checks then wait: (1) confirm the dial is fully OFF past the detent. (2) Seat the capillary probe and the blue/black thermostat wires — CCD-0008122 Repair §2 Thermostat Replacement p.43 steps 2–6, Figs. 59–60. (3) Disconnect flag terminals C (blue) and T (black) and leave them OPEN — no jumper. That is a tech adaptation of Intermittent Thermostat Operation p.31 Figs. 24–25 (OEM jumper forces a run for intermittent / won't-run). Do not call the open-circuit prove an OEM "runs when Off" flowchart.
- If the compressor STOPS with C/T open: the thermostat was holding a continuous run call. R&R Spark-Free Thermostat part G 2021128850 (retail C-FCR10DCGTA-007) per Repair §2 p.43–45 Figs. 57–67 (clocking pin, straighten probe, reseat, reconnect wires).
- If the compressor KEEPS RUNNING with C/T open: run-call is downstream of the thermostat. Escalate inverter/harness (secondary). At the inverter, C and T may be reversed without affecting performance (p.45 Fig. 70A). Do not go back to the fuse. Leave the dial fully OFF.
- Locked cites for this prove: p.31 (C/T terminals) and p.43–45 (Spark-Free Thermostat R&R, part G 2021128850). Leave the dial fully OFF.
- Never invent a dedicated OEM "runs when Off" tree. CCD-0008122 does not publish one.
"""
DIAL_OFF_RUN_SHOP_LINE = (
    "Confirm the dial is fully OFF, past the detent. "
    "Seat the capillary probe and the blue and black thermostat wires. "
    "Disconnect flag terminals C (blue) and T (black) and leave them open, with no jumper. "
    "Report whether the compressor stops.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 31\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 43"
)
DIAL_OFF_RUN_PART_SHOP_LINE = (
    "C (blue) and T (black) were opened with no jumper and the compressor stopped. "
    "The thermostat was holding a continuous run call. R&R Spark-Free Thermostat "
    "part G 2021128850 (retail C-FCR10DCGTA-007) per CCD-0008122 Repair §2 "
    "Thermostat Replacement p.43–45 Figs. 57–67: clocking pin to the housing indent, "
    "straighten the probe, reseat it, reconnect the wires. "
    "Cite pages 43–45 for the R&R and page 31 for the open C/T prove.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 43\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 31"
)
DIAL_OFF_RUN_INVERTER_SHOP_LINE = (
    "C (blue) and T (black) are open (no jumper) and the compressor keeps running. "
    "The run call is downstream of the thermostat — escalate inverter/harness "
    "(secondary), not a fuse recheck and not Spark-Free Thermostat R&R. "
    "CCD-0008122 p.45 Fig. 70A: at the inverter, C and T connections may be reversed "
    "and that does not affect product performance. "
    "Cite page 45 for the inverter note and page 31 for the open C/T prove.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 45\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 31"
)
_DIAL_OFF_RE = re.compile(
    r"\b("
    r"(?:temp(?:erature)?\s+)?(?:control\s+)?dial\s+(?:is\s+|was\s+|set\s+(?:fully\s+)?(?:to\s+)?)?off|"
    r"(?:temperature\s+)?control\s+(?:is\s+|was\s+|set\s+(?:fully\s+)?(?:to\s+)?)?off|"
    r"(?:control\s+)?knob\s+(?:is\s+|set\s+(?:to\s+)?)?off|"
    r"set\s+to\s+off|turned\s+(?:fully\s+)?off|in\s+(?:the\s+)?off\s+position|"
    r"past\s+(?:the\s+)?detent"
    r")\b",
    re.I,
)
_WONT_SHUT_OFF_RE = re.compile(
    r"\b("
    r"won'?t\s+shut\s+off|wont\s+shut\s+off|will\s+not\s+shut\s+off|"
    r"does\s+not\s+shut\s+off|doesn'?t\s+shut\s+off|"
    r"won'?t\s+turn\s+off|wont\s+turn\s+off|will\s+not\s+turn\s+off|"
    r"does\s+not\s+turn\s+off|doesn'?t\s+turn\s+off|"
    r"runs?\s+when\s+(?:(?:the|it(?:'s| is))\s+)?(?:dial\s+|control\s+|knob\s+)?off|"
    r"running\s+when\s+off|"
    r"runs?\s+with\s+(?:the\s+)?(?:dial|control|knob)\s+off"
    r")\b",
    re.I,
)
_STILL_RUNNING_RE = re.compile(
    r"\b("
    r"still\s+running|keeps?\s+running|kept\s+running|"
    r"won'?t\s+stop|wont\s+stop|will\s+not\s+stop|"
    r"does\s+not\s+stop|doesn'?t\s+stop|"
    r"continues?\s+to\s+run|runs?\s+constantly|running\s+constantly"
    r")\b",
    re.I,
)
_OVERCOOL_RE = re.compile(
    r"\b("
    r"over[\s-]?cool\w*|too\s+cold|ice[\s-]?cold|"
    r"frozen\s+solid|freezer\s+frozen|freezes?\s+solid|frozen\s+up|iced\s+solid"
    r")\b",
    re.I,
)
_COMPRESSOR_RUNNING_RE = re.compile(
    r"\bcompressor\b.{0,48}\b(?:is\s+|still\s+|keeps\s+)?(?:running|runs)\b|"
    r"\b(?:running|runs)\b.{0,24}\bcompressor\b",
    re.I,
)
_COMPRESSOR_NOT_RUNNING_RE = re.compile(
    r"\bcompressor\b.{0,40}\b(?:not|isn'?t|isnt|won'?t|wont|does\s+not|doesn'?t)\b.{0,20}\b(?:run|running|start|operate|operating)\b|"
    r"\bcompressor\s+(?:is\s+)?(?:not|isn'?t)\s+running\b|"
    r"\b(?:not|isn'?t|no)\s+running\b.{0,24}\bcompressor\b",
    re.I,
)
_NOT_COOLING_OPPOSITE_RE = re.compile(
    r"\b("
    r"not\s+cool(?:ing)?|no\s+cool(?:ing)?|won'?t\s+cool|wont\s+cool|"
    r"not\s+cold|isn'?t\s+cold|does\s+not\s+work|doesn'?t\s+work|not\s+working"
    r")\b",
    re.I,
)
_CT_OPEN_RE = re.compile(
    r"("
    r"\bc\s*/\s*t\b|"
    r"\bc\s+(?:and|&)\s+t\b|"
    r"flag\s+terminals?|"
    r"terminals?\s+c\b|"
    r"\b(?:blue|c)\b.{0,40}\b(?:black|t)\b.{0,24}\b(?:open|disconnect)|"
    r"no\s+jumper|"
    r"left\s+(?:them|the\s+terminals?|c\s*/?\s*t)\s+open|"
    r"open(?:ed)?\s+(?:the\s+)?(?:thermostat\s+)?(?:wires?|flag\s+)?terminals?"
    r")",
    re.I,
)
_CT_STOPPED_RE = re.compile(
    r"\b("
    r"compressor\s+(?:stopped|stops|quit|shut\s+off|turned\s+off|is\s+off|now\s+off)|"
    r"(?:it|unit)\s+stopped|"
    r"stopped\s+running|quit\s+running|"
    r"cycles?\s+off"
    r")\b",
    re.I,
)
_CT_STILL_RE = re.compile(
    r"\b("
    r"still\s+running|keeps?\s+running|kept\s+running|"
    r"did\s+not\s+stop|didn'?t\s+stop|does\s+not\s+stop|"
    r"won'?t\s+stop|wont\s+stop|continues?\s+to\s+run|"
    r"keeps?\s+going|still\s+runs"
    r")\b",
    re.I,
)
_DIAL_OFF_WRONG_TREE_RE = re.compile(
    r"("
    r"\bfuse\b|"
    r"15\s*a(?:tc)?|"
    r"front\s+vent|"
    r"12\s*v(?:dc)?\s+continuity|"
    r"power\s+continuity|"
    r"continuity\s+at\s+the\s+(?:appliance|power|unit)|"
    r"diagnostic\s+led|\bled\s+flash|"
    r"flash\s+codes?|"
    r"10\s*ma|"
    r"inverter\s+control\s+voltage|"
    r"\bpage\s+18\b|\bp\.\s*18\b|"
    r"\bpage\s+19\b|\bp\.\s*19\b|"
    r"\bpage\s+20\b|\bp\.\s*20\b"
    r")",
    re.I,
)
# Cites outside p.31 and p.43–45, and the written turn-ON sequence, are the wrong tree.
_PAGE_34_CITE_RE = re.compile(r"\b(?:page\s*34|p\.\s*34)\b", re.I)
_ON_OFF_AS_WRITTEN_RE = re.compile(
    r"("
    r"\bpage\s*23\b|\bp\.\s*23\b|"
    r"on\s*/\s*off\s+diagnostic|"
    r"\bfig\.?\s*16\b|"
    r"turn\s+(?:the\s+)?(?:refrigerator|dial|unit)\s+on\b|"
    r"(?:set\s+)?(?:the\s+)?dial\s+(?:on\s+)?to\s+(?:dial\s+)?(?:position\s+)?[45]\b|"
    r"wait\s+2\s+hours"
    r")",
    re.I,
)
_RUNNING_CONSTANT_THERMOSTAT_RE = re.compile(
    r"("
    r"running\s+constantly.{0,80}(?:replace\s+(?:the\s+)?thermostat|thermostat\s+replacement)|"
    r"(?:replace\s+(?:the\s+)?thermostat|thermostat\s+replacement).{0,80}running\s+constantly"
    r")",
    re.I,
)


def _mention_is_negated(text: str, start: int) -> bool:
    """True when the match sits in a 'do not / skip / unless' window."""
    raw = text or ""
    line_start = raw.rfind("\n", 0, start) + 1
    prefix = raw[line_start:start].lower()
    window = raw[max(0, start - 110):start].lower()
    return bool(
        re.search(
            r"(never|do not|don't|dont|not a |not the |unless |not open|"
            r"do not open|skip |not fuse|do not cite|do not start|do not lead|"
            r"do not go|not a no-power|not no-power|not fuse-first|"
            r"skip fuse|skip the|skip ccd)",
            f"{window} {prefix}",
        )
    )


def _is_fcr08_fcr10_family(category_name: str = "", blob: str = "") -> bool:
    """Furrion Arctic FCR08/FCR10 / FCR10DCGTA-class. Not rooftop FACR, not Norcold."""
    t = _norm(blob)
    if not t or FACR_MODEL_RE.search(t):
        return False
    if "norcold" in t or "dometic rm" in t or re.search(r"\brm\d{3,}", t):
        return False
    if "air condition" in t or "rooftop" in t:
        return False
    if _looks_like_furrion_fcr_fridge(t):
        return True
    if "ccd-0008122" in t or "ccd0008122" in t:
        return True
    if re.search(r"\bfcr\s*0?8\b|\bfcr\s*10\b", t):
        return True
    if "arctic" in t and _is_fridge_job_blob(category_name, t):
        return True
    if "furrion" in t and _is_fridge_job_blob(category_name, t):
        return True
    return False


def _has_dial_off_run_complaint(blob: str) -> bool:
    """
    Dial/control OFF + compressor still running / overcooling, or the natural
    one-liners (won't shut off, runs when Off, frozen solid with control Off).
    Not-cooling with the dial Off is the opposite tree (turn it ON).
    Not-cooling plus constant run is not this Off-but-running branch.
    """
    t = _norm(blob)
    if not t or _COMPRESSOR_NOT_RUNNING_RE.search(t):
        return False
    overcool = bool(_OVERCOOL_RE.search(t))
    if _NOT_COOLING_OPPOSITE_RE.search(t) and not overcool:
        return False
    dial_off = bool(_DIAL_OFF_RE.search(t))
    wont_stop = bool(_WONT_SHUT_OFF_RE.search(t))
    comp_run = bool(_COMPRESSOR_RUNNING_RE.search(t))
    still = bool(_STILL_RUNNING_RE.search(t))
    if wont_stop:
        return True
    if dial_off and (overcool or comp_run or still):
        return True
    # Live bay wording: "FCR10 OFF" plus compressor still running or overcool.
    fcr_off = bool(
        re.search(r"\bfcr\s*0?8\b|\bfcr\s*10\b|\bfcr10dcgta\b", t)
        and re.search(r"\boff\b", t)
    )
    if fcr_off and (overcool or comp_run or still or wont_stop):
        return True
    return False


def _ct_prove_result(blob: str) -> str:
    """'stopped' or 'still_running' when the tech reports an open C/T prove."""
    if not blob or not _CT_OPEN_RE.search(blob):
        return ""
    if _CT_STILL_RE.search(blob):
        return "still_running"
    if _CT_STOPPED_RE.search(blob):
        return "stopped"
    return ""


def ct_prove_from_turn(user_msg: str, facts: dict | None = None) -> str:
    """
    Open C/T result. The latest tech line wins over an older prove.
    Explicit C/T language, or a short follow-up ('compressor stopped'), counts.
    The original dial-off complaint is not a prove result.
    """
    msg = user_msg or ""
    found = _ct_prove_result(msg)
    if found:
        return found
    if not _has_dial_off_run_complaint(msg):
        norm = _norm(msg)
        if norm:
            if _CT_STILL_RE.search(msg) and (_CT_OPEN_RE.search(msg) or "open" in norm):
                return "still_running"
            if _CT_STOPPED_RE.search(msg):
                return "stopped"
            if len(norm) <= 80 and re.search(r"\bstopped\b", norm) and "still" not in norm:
                return "stopped"
    facts = facts or {}
    if facts.get("ct_prove") in ("stopped", "still_running"):
        return facts["ct_prove"]
    return ""


def is_fcr_dial_off_compressor_run_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    FCR08/FCR10 dial or control OFF while the compressor keeps running or the
    box overcools. E2 / AC / water heater / cooktop / stabilizer jobs lose.
    """
    if is_air_conditioning_context(category_name, model_text, symptom):
        return False
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        return False
    if is_water_heater_context(category_name, model_text, symptom):
        return False
    if is_cooktop_pan_on_flameout_context(category_name, model_text, symptom):
        return False
    if is_stabilizer_override_pin_context(category_name, model_text, symptom):
        return False
    blob = _blob(category_name, model_text, symptom)
    if not _is_fcr08_fcr10_family(category_name, blob):
        return False
    return _has_dial_off_run_complaint(blob)


def dial_off_run_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward thermostat C/T p.31 + R&R p.43–45, not fuse."""
    symptom = (symptom or "").strip()
    if not is_fcr_dial_off_compressor_run_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {DIAL_OFF_RUN_SEARCH_BOOST}".strip()


def score_dial_off_run_chunk(page, query: str = "", category: str = "") -> int:
    """
    Higher = CCD-0008122 thermostat operation p.31 and Thermostat Replacement p.43–45.
    Pages 18, 19, 20, and 34 lose.
    """
    raw = _page_text_blob(page)
    title = _page_title(page)
    t = _norm(f"{title} {raw}")
    q = _norm(query)
    page_no = _page_number(page)
    score = 0
    if "thermostat replacement" in t or "spark-free" in t or "spark free" in t:
        score += 22
    if "2021128850" in t or "c-fcr10dcgta-007" in t:
        score += 18
    if "flag terminal" in t or ("c (blue)" in t and "t (black)" in t):
        score += 16
    if "probe" in t and ("seat" in t or "seated" in t or "installed" in t):
        score += 10
    if page_no in FURRION_FCR_DIAL_OFF_RUN_PAGES:
        score += 18
    if page_no == 31:
        score += 6
    if page_no in (43, 44, 45):
        score += 8
    if "fig. 24" in t or "fig 24" in t or "fig. 25" in t or "fig 25" in t:
        score += 8
    if any(k in t for k in ("fig. 57", "fig 57", "fig. 59", "fig. 67", "fig 67")):
        score += 8
    if is_furrion_ccd_0008122(title) or is_furrion_ccd_0008122(t):
        score += 6
    if q and any(k in q for k in ("thermostat", "2021128850", "overcool", "dial off")):
        if "thermostat" in t:
            score += 4
    # Pages 18, 19, 20, and 34 belong to other trees. Always drop them here.
    if page_no in (18, 19, 20, 34):
        score -= 28
    elif any(
        k in t
        for k in (
            "fuse location",
            "front vent",
            "15a",
            "15 a",
            "diagnostic led",
            "coolant leak",
            "running constantly",
        )
    ) and page_no not in FURRION_FCR_DIAL_OFF_RUN_PAGES:
        score -= 16
    if "fan fault" in t or "fan replacement" in t:
        score -= 8
    if "ice and moisture" in t or "ice or moisture" in t:
        score -= 6
    return score


def rank_chunks_for_dial_off_run(chunks, query: str = "", limit: int = 8) -> list:
    """Prefer thermostat p.31 and R&R p.43–45. Drop pages 18, 19, 20, and 34."""
    scored = [(score_dial_off_run_chunk(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    thermo = [
        ch
        for sc, ch in scored
        if sc > 0 and (
            _page_number(ch) in FURRION_FCR_DIAL_OFF_RUN_PAGES
            or "thermostat" in _norm(_page_text_blob(ch))
        )
    ]
    out = []
    for _sc, ch in scored:
        page_no = _page_number(ch)
        if thermo and page_no in (18, 19, 20, 34):
            continue
        out.append(ch)
        if len(out) >= limit:
            break
    return out or [ch for _sc, ch in scored[:limit]]


def reply_opens_dial_off_wrong_tree(reply: str) -> bool:
    """True when a coach reply leads with fuse, 12V, LED, or a cite outside p.31 and p.43–45."""
    t = reply or ""
    if not t.strip():
        return False
    if (
        _PAGE_34_CITE_RE.search(t)
        or _ON_OFF_AS_WRITTEN_RE.search(t)
        or _RUNNING_CONSTANT_THERMOSTAT_RE.search(t)
    ):
        return True
    for m in _DIAL_OFF_WRONG_TREE_RE.finditer(t):
        if _mention_is_negated(t, m.start()):
            continue
        return True
    return False


def reply_names_dial_off_ct_prove(reply: str) -> bool:
    """True when the reply already gives the open C/T prove and cites p.31 + p.43."""
    t = _norm(reply)
    if not t:
        return False
    terminals = any(
        k in t
        for k in (
            "c (blue)",
            "c/t",
            "c and t",
            "flag terminal",
        )
    )
    open_circuit = "no jumper" in t or "leave them open" in t or "left open" in t
    page_31 = any(k in t for k in ("page 31", "p.31", "p. 31"))
    page_43 = any(k in t for k in ("page 43", "p.43", "p. 43"))
    return bool(terminals and open_circuit and page_31 and page_43)


def reply_names_spark_free_thermostat_part(reply: str) -> bool:
    """True when the reply names part G 2021128850 and the R&R pages."""
    t = _norm(reply)
    if "2021128850" not in t:
        return False
    return any(k in t for k in ("page 43", "p.43", "p. 43", "page 44", "page 45"))


def reply_names_dial_off_inverter_secondary(reply: str) -> bool:
    """True when C/T-open-still-running escalates to inverter/harness, not the fuse."""
    t = _norm(reply)
    if not t:
        return False
    if "inverter" not in t and "harness" not in t:
        return False
    if not any(k in t for k in ("c/t", "c and t", "c (blue)", "flag terminal", "open")):
        return False
    if reply_opens_dial_off_wrong_tree(reply):
        return False
    return True


def dial_off_run_reply_needs_guard(reply: str, facts: dict | None = None) -> bool:
    """True when this turn would ship fuse-first or skip the open C/T prove."""
    facts = facts or {}
    if not (reply or "").strip():
        return True
    if reply_opens_dial_off_wrong_tree(reply):
        return True
    prove = facts.get("ct_prove") or ""
    if prove == "stopped":
        return not reply_names_spark_free_thermostat_part(reply)
    if prove == "still_running":
        return not reply_names_dial_off_inverter_secondary(reply)
    if reply_names_dial_off_ct_prove(reply) and reply_names_spark_free_thermostat_part(reply):
        return False
    return True


def _drop_thermostat_rr_sentences(reply: str) -> str:
    """C/T-open-still-running is inverter/harness, not Spark-Free Thermostat R&R."""
    if not reply:
        return ""
    kept = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", reply.strip()):
        if re.search(r"2021128850|c-fcr10dcgta-007|spark-free thermostat", part, re.I):
            continue
        kept.append(part)
    return " ".join(kept).strip()


def strip_dial_off_wrong_tree_claims(reply: str) -> str:
    """Drop sentences that open fuse / continuity / LED or cite outside p.31 and p.43–45."""
    if not reply or not reply_opens_dial_off_wrong_tree(reply):
        return reply
    kept = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", reply.strip()):
        if not part or reply_opens_dial_off_wrong_tree(part):
            continue
        if re.search(r"error contacting ai|request too large|\b413\b", part, re.I):
            continue
        kept.append(part)
    return " ".join(kept).strip()


def ensure_fcr_dial_off_compressor_run_path(reply: str, facts: dict | None = None) -> str:
    """
    Deterministic shop line so dial-OFF + compressor-running cannot ship fuse-first.
    Stopped C/T prove climaxes at part G 2021128850. Still-running escalates
    inverter/harness. Uses CCD-0008122 p.31 and p.43–45 only.
    """
    facts = facts or {}
    prove = facts.get("ct_prove") or ""
    if prove == "stopped":
        cleaned = lock_spark_free_part_g(strip_dial_off_wrong_tree_claims(reply or ""))
        if reply_names_spark_free_thermostat_part(cleaned) and not reply_opens_dial_off_wrong_tree(cleaned):
            return cleaned
        return f"{DIAL_OFF_RUN_PART_SHOP_LINE}\n\n{cleaned}".strip()
    if prove == "still_running":
        cleaned = lock_spark_free_part_g(strip_dial_off_wrong_tree_claims(reply or ""))
        cleaned = _drop_thermostat_rr_sentences(cleaned)
        if reply_names_dial_off_inverter_secondary(cleaned):
            return cleaned
        return f"{DIAL_OFF_RUN_INVERTER_SHOP_LINE}\n\n{cleaned}".strip()
    if not dial_off_run_reply_needs_guard(reply, facts):
        return lock_spark_free_part_g(reply)
    cleaned = lock_spark_free_part_g(strip_dial_off_wrong_tree_claims(reply or ""))
    if reply_names_dial_off_ct_prove(cleaned) and reply_names_spark_free_thermostat_part(cleaned):
        if not reply_opens_dial_off_wrong_tree(cleaned):
            return cleaned
    if _dial_off_prompt_present(cleaned) or _dial_off_prompt_present(reply or ""):
        return DIAL_OFF_RUN_SHOP_LINE
    return f"{DIAL_OFF_RUN_SHOP_LINE}\n\n{cleaned}".strip()


def _dial_off_prompt_present(text: str) -> bool:
    """The open C/T prompt is already in this draft. Do not paste it again."""
    t = _norm(text)
    terminals = any(k in t for k in ("flag terminal", "c and t", "c (blue)", "c/t"))
    opened = any(k in t for k in ("no jumper", "leave them open", "left open"))
    return bool(terminals and opened)


def figure_render_honesty_note(manual_title: str = "", render_failed: bool = False) -> str:
    """Shop-floor line when a library figure page did not display."""
    if not render_failed:
        return ""
    title = (manual_title or "").strip()
    if title and is_level_up_library_title(title):
        return (
            f"The figure is in the shop Document Library PDF ({title}). "
            "TechTrack could not render that page image this turn. "
            "Download that PDF or ask a manager to re-index it — "
            "do not treat this as a missing Level Up procedure, and do not use the Unity board SM."
        )
    if title and is_ac_library_title(title):
        return (
            f"The figure is in the shop Document Library PDF ({title}). "
            "TechTrack could not render that page image this turn. "
            "Download that PDF or ask a manager to re-index it — "
            "do not treat this as a missing Air Conditioning procedure, and do not use the Unity board SM."
        )
    if title and is_water_heater_library_title(title):
        return (
            f"The figure is in the shop Document Library PDF ({title}). "
            "TechTrack could not render that page image this turn. "
            "Download that PDF or ask a manager to re-index it — "
            "do not treat this as a missing Girard GSWH-2 / water heater procedure, "
            "and do not use the Unity board SM."
        )
    if title and is_unity_board_manual(title):
        return (
            "That Unity / OneControl awning-slide board manual is the wrong book for "
            "rooftop Air Conditioning (Furrion FACT / Dometic Brisk), for "
            "Level Up Advantage / 807662, and for Girard GSWH-2 water heaters. "
            "The AC figure is in a Furrion/Dometic rooftop AC PDF; the leveling figure "
            "is in a Level-Up / OCTP / TI-005 PDF; the water heater figure is in a "
            "Girard GSWH-2 / CCD-0009390 PDF. "
            "If the page image did not render, download that OEM PDF or ask for a reindex."
        )
    return (
        "You asked for a figure/page. TechTrack could not load a matching shop-library PDF page "
        "(missing file path, download failed, unindexed PDF, or page render unavailable). "
        "If a Level-Up / TI-005 / QR-092, Furrion/Dometic rooftop AC, or Girard GSWH-2 "
        "water heater title is on the Document Library catalog, the figure is in that PDF — "
        "say so and ask for reindex. "
        "Do not invent a Unity substitute."
    )


def _page_text_blob(page) -> str:
    if isinstance(page, dict):
        return " ".join(
            str(page.get(k) or "")
            for k in ("chunk_text", "excerpt", "text", "title", "keywords")
        )
    return " ".join(
        str(getattr(page, k, "") or "")
        for k in ("title", "keywords", "chunk_text")
    )


def _page_number(page) -> int:
    try:
        if isinstance(page, dict):
            return int(page.get("page") or 0)
        return int(getattr(page, "page", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _page_title(page) -> str:
    if isinstance(page, dict):
        return str(page.get("title") or "")
    return str(getattr(page, "title", "") or "")


def page_has_figure_or_terminal_layout(text: str) -> bool:
    """True when page text looks like a board / wiring / terminal figure, not Quick Notes."""
    raw = text or ""
    t = _norm(raw)
    if not t:
        return False
    if FIG_CAPTION_RE.search(raw):
        return True
    if "wiring diagram" in t or "housing label" in t:
        return True
    if F_PLUS_MINUS_RE.search(raw) and any(k in t for k in ("inverter", "pcb", "terminal", "fan")):
        return True
    if "inverter pcb" in t and ("terminal" in t or "fig" in t or "board" in t):
        return True
    return False


def page_is_text_only_notes(text: str) -> bool:
    """Quick Notes / Nominal voltage / troubleshooting prose with no figure layout."""
    raw = text or ""
    t = _norm(raw)
    if not t or page_has_figure_or_terminal_layout(raw):
        return False
    return any(
        s in t
        for s in ("quick notes", "nominal voltage", "troubleshooting instructions")
    )


def score_figure_page(page, query: str = "") -> int:
    """
    Higher = more likely a real board/terminal figure page.
    Penalize CCD-0008122 Quick Notes page 13 and other text-only notes.
    """
    raw = _page_text_blob(page)
    t = _norm(raw)
    q = _norm(query)
    title = _page_title(page)
    page_no = _page_number(page)
    score = 0

    fig_hits = len(FIG_CAPTION_RE.findall(raw))
    score += min(fig_hits * 8, 24)
    if "inverter pcb" in t or "inverter board" in t:
        score += 10
    if F_PLUS_MINUS_RE.search(raw):
        score += 10
    if "wiring diagram" in t:
        score += 8
    if "housing label" in t:
        score += 8
    if "terminal" in t and ("label" in t or fig_hits):
        score += 6
    if "d/" in t or ("terminal d" in t) or re.search(r"\bd\s*[+/]", t):
        score += 4

    if any(w in q for w in ("fan", "f+", "f-")) and F_PLUS_MINUS_RE.search(raw):
        score += 6
    if any(w in q for w in ("housing", "label")) and "housing" in t:
        score += 4
    if "wiring" in q and "wiring" in t:
        score += 4
    if any(w in q for w in ("pcb", "inverter", "board", "terminal")) and (
        "inverter" in t or "pcb" in t or "terminal" in t
    ):
        score += 6

    if page_is_text_only_notes(raw):
        score -= 20
    if "nominal voltage" in t and not page_has_figure_or_terminal_layout(raw):
        score -= 12
    if "quick notes" in t and not page_has_figure_or_terminal_layout(raw):
        score -= 16

    furrion = is_furrion_ccd_0008122(title) or is_furrion_ccd_0008122(q)
    if furrion and page_no in FURRION_FCR_BOARD_FIGURE_PAGES:
        score += 15
    if furrion and page_no in FURRION_FCR_TEXT_ONLY_PAGES and not page_has_figure_or_terminal_layout(raw):
        score -= 20
    return score


def rank_chunks_for_figure_ask(chunks, query: str, limit: int = 8) -> list:
    """Prefer figure/terminal-layout pages; drop Quick Notes when a real figure page exists."""
    scored = [(score_figure_page(ch, query), ch) for ch in (chunks or [])]
    scored.sort(key=lambda x: x[0], reverse=True)
    has_fig = any(
        sc > 0 and page_has_figure_or_terminal_layout(_page_text_blob(ch))
        for sc, ch in scored
    )
    out = []
    for _sc, ch in scored:
        text = _page_text_blob(ch)
        if has_fig and page_is_text_only_notes(text):
            continue
        out.append(ch)
        if len(out) >= limit:
            break
    return out or [ch for _sc, ch in scored[:limit]]


def pick_diagram_page_numbers(candidates, query: str, manual_title: str = "") -> list:
    """
    Page numbers to show for a board/terminal figure ask.
    Never returns a text-only Quick Notes page when a diagram candidate exists.
    Falls back to CCD-0008122 board-figure pages when the SM is Furrion and nothing else qualifies.
    """
    ranked = rank_chunks_for_figure_ask(candidates, query, limit=8)
    pages = []
    title_blob = manual_title or ""
    for ch in ranked:
        title_blob = title_blob or _page_title(ch)
        text = _page_text_blob(ch)
        page_no = _page_number(ch)
        if not page_no:
            continue
        hint_ok = (
            is_furrion_ccd_0008122(_page_title(ch) or manual_title)
            and page_no in FURRION_FCR_BOARD_FIGURE_PAGES
        )
        if page_has_figure_or_terminal_layout(text) or hint_ok:
            if page_no not in pages:
                pages.append(page_no)
        if len(pages) >= 3:
            break
    if not pages and is_furrion_ccd_0008122(manual_title or title_blob) and wants_board_or_terminal_figure(query):
        pages = list(FURRION_FCR_BOARD_FIGURE_PAGES[:3])
    return pages[:3]


def tech_wants_open_coach(user_msg: str) -> bool:
    """True when the tech is asking a question, pivoting, or requesting figures."""
    raw = (user_msg or "").strip()
    if not raw:
        return False
    if wants_library_figures(raw):
        return True
    if "?" in raw:
        return True
    t = _norm(raw)
    return any(p in t for p in COACH_REQUEST_PHRASES)


def hard_tree_yields_to_coach(user_msg: str, node: dict | None = None) -> bool:
    """
    Exclusive hard-tree chat is off. If someone re-enables it, still yield on
    questions / pivots / figures / end leaves so the cage cannot trap the tech.
    """
    if not HARD_TREE_EXCLUSIVE_CHAT:
        return True
    if tech_wants_open_coach(user_msg):
        return True
    if not node:
        return False
    ntype = (node.get("type") or "").strip().lower()
    edges = node.get("edges") or {}
    if ntype == "end" or not edges:
        return True
    return False


def extract_stated_facts(text: str) -> dict:
    """
    Pull shop facts the tech already reported. Used to stop gate-parrot re-asks
    and to search the right manual section (powered / not-cooling vs no-power).
    """
    raw = _norm(text)
    if not raw:
        return {}
    facts = {}

    if re.search(
        r"\b(fuse\s+(?:is\s+|was\s+|already\s+)?(?:blown\s+)?replaced|replaced\s+(?:the\s+)?fuse|"
        r"new\s+fuse|fuse\s+(?:was\s+)?blown\s+replac\w*|found\s+fuse\s+blown\s+and\s+replaced|"
        r"fuse\s+already\s+replaced)\b",
        raw,
    ) or ("fuse" in raw and "replac" in raw):
        facts["fuse"] = "replaced"
    elif re.search(r"\b(fuse\s+(?:is\s+|was\s+)?blown|blown\s+fuse)\b", raw):
        facts["fuse"] = "blown"
    elif re.search(r"\b(fuse\s+(?:is\s+|was\s+)?(?:good|ok|fine|intact)|fuse\s+not\s+blown)\b", raw):
        facts["fuse"] = "good"

    if re.search(
        r"\b(light\s+comes\s+on|light\s+come\s+on|light\s+is\s+on|light\s+on|"
        r"cavity\s+light|interior\s+light|fridge\s+light\s+comes\s+on|"
        r"has\s+power|powered|display\s+is\s+on)\b",
        raw,
    ) and not re.search(r"\b(no\s+light|light\s+(?:is\s+)?off|light\s+does\s+not|light\s+doesn't)\b", raw):
        facts["light"] = "on"
    elif re.search(r"\b(no\s+light|light\s+(?:is\s+)?off|light\s+does\s+not\s+come|still\s+dark)\b", raw):
        facts["light"] = "off"

    if re.search(
        r"\b(not\s+cool(?:ing)?|no\s+cool(?:ing)?|won'?t\s+cool|wont\s+cool|"
        r"not\s+cold|is\s+not\s+cooling|fridge\s+is\s+not\s+cooling)\b",
        raw,
    ):
        facts["cooling"] = "not_cooling"
    elif re.search(r"\b(is\s+cooling|cooling\s+now|cools\s+now)\b", raw) and "not" not in raw:
        facts["cooling"] = "cooling"

    if re.search(
        r"\b(compressor\s+(?:is\s+)?(?:not|isn't|isnt)\s+runn|"
        r"compressor\s+(?:dead|not\s+running|won't\s+run|will\s+not\s+run)|"
        r"not\s+getting\s+power\s+to\s+compressor|compressor\s+not\s+running)\b",
        raw,
    ) or re.search(r"\b(does\s+not|doesn't|doesnt|not)\b.{0,40}\bcompressor\b.{0,20}\b(runn|operat)\b", raw):
        facts["compressor"] = "not_running"
    elif re.search(r"\bcompressor\s+(?:is\s+)?running\b", raw) and not re.search(r"\b(not|no|isn't|isnt)\b", raw):
        facts["compressor"] = "running"

    if re.search(
        r"\b(go\s+to\s+compressor|compressor\s+section|test\s+(?:the\s+)?compressor|"
        r"need\s+to\s+test\s+compressor|inoperable\s+compressor)\b",
        raw,
    ):
        facts["pivot"] = "compressor"

    if re.search(r"\b(dial\s+(?:is\s+)?(?:on|at)\s*[45]|set\s+to\s*[45]|position\s*[45])\b", raw):
        facts["dial"] = "on_4_5"
    elif re.search(r"\b(dial\s+(?:is\s+)?off|set\s+to\s+off)\b", raw):
        facts["dial"] = "off"

    if re.search(
        r"\b(?:e\s*2|2\s*[\s-]*flash|flash(?:es|ing)?\s*2|blink(?:ing)?\s*2|"
        r"fan[\s-]*fault)\b",
        raw,
    ):
        facts["fan_fault"] = "e2"
    if re.search(r"\bfan\s*(?:v|volts?|voltage)\b", raw) or (
        F_PLUS_MINUS_RE.search(text or "") and re.search(r"\b\d+(?:\.\d+)?\s*v", raw)
    ):
        facts["fan_volts"] = "reported"
    if re.search(r"\bfan\s*(?:amps?|amperage|current)\b", raw) or (
        "fan" in raw and re.search(r"\b0?\.\d+\s*a(?:mps?)?\b", raw)
    ):
        facts["fan_amps"] = "reported"

    if re.search(r"\b(pan|cookware|pot|skillet)\b", raw) and re.search(
        r"\b(goes?\s+out|went\s+out|flame[\s-]*out|shuts?\s+off|drops?\s+out)\b",
        raw,
    ):
        facts["pan_on_flameout"] = "reported"
    if re.search(
        r"\b(roll[\s-]*pin|override[\s-]*pin|override coupler|coupler)\b",
        raw,
    ) and re.search(r"\b(broken|seized|seize|sheared|destroyed|not serviceable)\b", raw):
        facts["override_pin"] = "broken_or_seized"

    if _has_ice_moisture_marker(raw) and not FRIDGE_NO_POWER_RE.search(raw):
        if not _has_dial_off_run_complaint(raw):
            facts["ice_moisture"] = "rear_wall"

    if _has_dial_off_run_complaint(raw) and (
        _is_fcr08_fcr10_family("", raw)
        or any(k in raw for k in ("fridge", "refriger", "reefer", "freezer", "compressor", "arctic"))
    ):
        facts["dial_off_run"] = "overcool"
    ct_prove = _ct_prove_result(text or "")
    if ct_prove:
        facts["ct_prove"] = ct_prove

    levelingish = any(
        k in raw
        for k in (
            "manual mode",
            "level up",
            "level-up",
            "levelup",
            "807662",
            "leveling pad",
            "auto level",
            "firefly",
            "octp",
        )
    )
    if _has_manual_mode_dump_marker(raw):
        facts["manual_dump"] = "reported"
    if _has_auto_level_fail(raw):
        facts["auto_level"] = "fails"
    elif _has_auto_or_other_pad_works(raw):
        facts["auto_level"] = "works"
    if re.search(
        r"\b(no\s+brownout|power\s+(?:is\s+)?(?:good|sane|ok|fine)|"
        r"voltage\s+(?:is\s+)?(?:good|ok|fine)|power\s+looks\s+sane)\b",
        raw,
    ):
        facts["level_up_power"] = "good"
    elif levelingish and re.search(r"\b(brownout|voltage\s+collapse)\b", raw):
        facts["level_up_power"] = "brownout"
    if re.search(
        r"\b(no|not|without|cleared|clear(?:ed)?\s+(?:those|them|it))\b.{0,48}"
        r"\b(low\s+voltage|excess\s+angle|external\s+sensor)\b",
        raw,
    ) or re.search(
        r"\b(low\s+voltage|excess\s+angle|external\s+sensor)\b.{0,32}"
        r"\b(cleared|not\s+present|none|no\s+error)\b",
        raw,
    ) or re.search(r"\bno\s+(?:sticky\s+)?(?:error\s+text|errors?)\b", raw):
        facts["sticky_level_error"] = "none"
    elif re.search(r"\b(excess\s+angle|external\s+sensor)\b", raw) or (
        levelingish and re.search(r"\blow\s+voltage\b", raw)
    ):
        facts["sticky_level_error"] = "present"

    can_unplug = bool(
        (
            (
                re.search(r"\bunplug", raw)
                or re.search(r"\bdisconnect", raw)
                or "can-out" in raw
                or "can out" in raw
            )
            and re.search(r"\bcan\b", raw)
        )
        or (
            re.search(r"\bunplug", raw)
            and re.search(r"\b(firefly|onecontrol).{0,32}cable|cable.{0,32}(firefly|onecontrol)", raw)
        )
    )
    manual_stays = bool(
        re.search(
            r"\bmanual(?:\s+mode)?\b.{0,56}\b("
            r"stays?|stayed|holds?|held|works?|worked|ok|good|"
            r"did\s+not\s+dump|doesn'?t\s+dump|does\s+not\s+dump"
            r")\b",
            raw,
        )
        or re.search(
            r"\b(stays?|stayed|holds?|held|works?|worked)\b.{0,40}\bmanual(?:\s+mode)?\b",
            raw,
        )
        or "manual works can-out" in raw
        or "manual works with can" in raw
        or "manual stayed" in raw
    )
    manual_still_dumps = bool(
        re.search(
            r"\bmanual(?:\s+mode)?\b.{0,56}\b(still\s+(?:dumps?|flash|returns?|home))\b",
            raw,
        )
        or re.search(
            r"\b(still\s+(?:dumps?|flashes?|returns?|homes?))\b.{0,40}\bmanual",
            raw,
        )
        or (
            can_unplug
            and re.search(r"\b(still\s+dumps?|still\s+dumped|still\s+flashes?|still\s+returns?\s+home)\b", raw)
        )
    )
    if can_unplug and manual_stays:
        facts["can_isolate"] = "stays"
    elif can_unplug and manual_still_dumps:
        facts["can_isolate"] = "still_dumps"

    if is_bal_soft_touch_tongue_only_context("", "", raw):
        facts["bal_tongue"] = "only_dead"
    if (
        facts.get("bal_tongue") == "only_dead"
        or "tongue" in raw
        or "20300427" in raw
        or "soft-touch" in raw
        or "soft touch" in raw
    ):
        facts.update(extract_bal_tongue_facts(text or ""))
    facts.update(facr_freeze_proves_from_text(text or ""))

    return facts


def facts_from_chat(history: list = None, latest_msg: str = "") -> dict:
    """Merge facts from prior tech lines plus the latest message. Latest wins on conflict."""
    merged = {}
    for m in history or []:
        if (m.get("role") or "") != "user":
            continue
        merged.update(extract_stated_facts(m.get("content") or ""))
    merged.update(extract_stated_facts(latest_msg or ""))
    merged.update(facr_proves_from_chat(history, latest_msg))
    merged.update(coleman_facts_from_chat(history, latest_msg))
    return merged


def format_stated_facts_rule(facts: dict) -> str:
    """System-prompt block: never re-ask these; search the matching SM section."""
    if not facts:
        return ""
    labels = {
        "fuse": {"replaced": "fuse blown and replaced", "blown": "fuse blown", "good": "fuse good / intact"},
        "light": {"on": "cavity / interior light is ON (unit has power)", "off": "cavity light is OFF"},
        "cooling": {"not_cooling": "fridge is NOT cooling", "cooling": "fridge is cooling"},
        "compressor": {"not_running": "compressor is NOT running", "running": "compressor is running"},
        "dial": {"on_4_5": "temperature dial is ON at 4 or 5", "off": "temperature dial is OFF"},
        "pivot": {"compressor": "tech asked to go to the compressor / inoperable-compressor section"},
        "fan_fault": {"e2": "Furrion FCR E2 / 2-flash / Fan Fault Current (freezer fan / airflow)"},
        "fan_volts": {"reported": "fan / F+ F− voltage already reported"},
        "fan_amps": {"reported": "fan amps / current already reported"},
        "pan_on_flameout": {
            "reported": "cooktop burner lights then goes out with pan / cookware on"
        },
        "override_pin": {
            "broken_or_seized": "stabilizer override roll pin / coupler is broken or seized"
        },
        "ice_moisture": {
            "rear_wall": "rear/back-wall ice, frost, or moisture in the fridge cavity"
        },
        "dial_off_run": {
            "overcool": (
                "FCR dial/control OFF and compressor still running or overcooling "
                "(not a fuse / 12V tree)"
            )
        },
        "ct_prove": {
            "stopped": "open C/T (no jumper) and the compressor STOPPED",
            "still_running": "open C/T (no jumper) and the compressor KEEPS RUNNING",
        },
        "manual_dump": {
            "reported": "Level Up Manual Mode flashes then dumps / returns to home"
        },
        "auto_level": {
            "works": "Auto Level (or other pad functions) still work",
            "fails": "Auto Level does not work",
        },
        "level_up_power": {
            "good": "Level Up power looks sane / no brownout",
            "brownout": "Level Up power brownout / voltage collapse",
        },
        "sticky_level_error": {
            "none": "no sticky Low Voltage / Excess Angle / External Sensor text",
            "present": "sticky Low Voltage / Excess Angle / External Sensor is present — clear first",
        },
        "can_isolate": {
            "stays": "Manual Mode STAYS with the Firefly cable unplugged (rubber-boot plug still in)",
            "still_dumps": "Manual Mode STILL DUMPS with the Firefly cable unplugged",
        },
        "bal_tongue": {
            "only_dead": "BAL Soft-Touch tongue jack only is dead; other stabilizers and panel lights work",
        },
        "tongue_channel_volts": {
            "missing": "no 12V on the tongue jack output wire at the panel",
            "present": "12V is present on the tongue jack output wire at the panel",
        },
        "tongue_motor_12v": {
            "ok": "tongue motor runs on direct 12V",
            "fail": "tongue motor fails a direct-12V prove",
        },
        "tongue_coupler": {
            "ok": "tongue coupler is engaged / OK",
            "bad": "tongue coupler or shear pin is bad",
        },
        "tongue_override": {
            "wont_turn": "manual override will not turn",
            "turns": "manual override turns",
        },
        "tongue_pigtail": {
            "bad": "tongue pigtail is open / needs repair",
            "good": "tongue pigtail is good",
        },
        "facr_drain": {"clear": "FACR condensate drain is clear"},
        "facr_pan_slope": {"ok": "FACR evaporator pan / base-pan slope is good"},
        "facr_fan_filter": {"ok": "FACR fan and filter are OK"},
        "facr_suction": {"clear": "FACR suction line is clear"},
        "facr_freeze_sensor": {"good": "FACR freeze sensor is good"},
        "facr_sensor_reading": {"reported": "FACR freeze sensor reading was reported"},
        "facr_thermostat": {"good": "FACR cool setpoint / thermostat is good"},
        "facr_nozzle": {"open": "FACR nozzles are open"},
        "facr_ambient": {"ok": "FACR ambient is good"},
        "facr_pressure": {"ok": "FACR refrigerant pressures are good"},
        "facr_auth_request": {
            "yes": "tech asked to authorize FACR rooftop assembly R&R",
        },
        "coleman_2111": {
            "open": "Coleman-Mach 2111-0001 is the unit under test",
            "climax": "Coleman-Mach 2111-0001 motor and control-board evidence is complete",
        },
        "coleman_fan_high": {
            "dead": "Coleman board Fan High is dead (tester dark and/or about 0 VAC)",
            "live": "Coleman board Fan High still has line voltage",
        },
        "coleman_compressor": {
            "ok": "Peacemaker bypass: the compressor runs",
        },
        "coleman_fan_motor": {
            "locked": "Peacemaker bypass: the fan does not rotate",
        },
        "coleman_stall_amps": {
            "reported": "fan stall current is about 1.9 A with the shaft locked",
        },
        "coleman_cap": {
            "ok": "fan run capacitor measures about its rated value",
            "bad": "fan run capacitor is bad",
        },
    }
    lines = [
        "TECH ALREADY STATED IN THIS CHAT — never re-ask these facts:",
    ]
    hidden = set()
    if facts.get("bal_tongue") != "only_dead":
        hidden.update(
            {
                "bal_tongue",
                "tongue_channel_volts",
                "tongue_motor_12v",
                "tongue_coupler",
                "tongue_override",
                "tongue_pigtail",
            }
        )
    if not facts.get("facr_fan_filter") and not facts.get("facr_freeze_sensor"):
        hidden.add("facr_drain")
    for key, val in facts.items():
        if key in hidden:
            continue
        pretty = (labels.get(key) or {}).get(val) or f"{key}={val}"
        lines.append(f"- {pretty}")
    lines.append(
        "Do not open or close with Heard or Noted. Give the next cited service-manual check "
        "or answer their question. Do not parrot a prior gate."
    )
    if facts.get("fan_fault") or facts.get("fan_volts") or facts.get("fan_amps"):
        lines.append(
            "E2 / Fan Fault Current is already in play. Do NOT claim CCD-0008122 has no "
            "separate freezer evaporator fan. Do NOT cage the repair to rear inverter/control "
            "board only. Fan Fault Diagnostics (F+/F−) and Fan Replacement are valid. "
            "If fan volts/amps are present and the fault returned, recommend freezer "
            "evaporator fan R&R and the rear inverter/control board when both are supported."
        )
    if facts.get("light") == "on" and facts.get("cooling") == "not_cooling":
        if facts.get("fan_fault") or facts.get("fan_volts") or facts.get("fan_amps"):
            lines.append(
                "Power is present. Stay on the cited Fan Fault / freezer-fan path. "
                "Do NOT ask whether the light is on or restart at fuse / no-power."
            )
        else:
            lines.append(
                "Power is present and the unit is not cooling. Do NOT ask whether the light is on "
                "or whether it is cooling. Do NOT restart at fuse / no-power. Follow the shop "
                "service-manual section for a powered unit that is not cooling (inoperable compressor "
                "/ not-cooling diagnostics) from the excerpts — not a hardcoded Fan Replacement leaf "
                "unless this turn's excerpt says so."
            )
    if facts.get("pivot") == "compressor" or facts.get("compressor") == "not_running":
        if facts.get("fan_fault"):
            lines.append(
                "Compressor questions do not cancel E2 / Fan Fault Current. Keep Fan Replacement "
                "and F+/F− in play when those excerpts apply."
            )
        else:
            lines.append(
                "The tech wants compressor / inoperable-compressor guidance. Use the cited SM pages "
                "for that section. Do not force Fan Replacement unless this turn's excerpt says so."
            )
    if facts.get("pan_on_flameout"):
        lines.append(
            "Pan-on cooktop flame-out is already in play. FIRST verify the thermocouple / "
            "flame-sensor tip is positioned in the burner flame WITH COOKWARE ON. Do NOT "
            "jump to thermocouple, safety valve, orifice, regulator, or igniter R&R until "
            "tip geometry is correct and the flame still drops out."
        )
    if facts.get("override_pin") == "broken_or_seized":
        lines.append(
            "Override roll pin / coupler is broken or seized and not field-serviceable. "
            "Recommend complete front stabilizer jack assembly R&R (mount + electrical; "
            "retest power and manual). Do NOT recommend coupler-only. CCD-0007345 override "
            "usage is not the end fix."
        )
    if facts.get("ice_moisture") == "rear_wall":
        lines.append(
            "Rear/back-wall ice, frost, or moisture is already in play. Follow "
            "CCD-0008122 Ice and Moisture → Ice or Moisture in the Fridge (p.36 / Fig.36). "
            "Coach order: pattern note → dial max? → gasket → cooling verify → watch/replace. "
            "Do NOT restart at fuse / 12V inverter / No Power unless the complaint is "
            "no power / dead / won't run / no light. Cite page 36 and Fig. 36 — never a "
            "fake Fuse location title with no page."
        )
    if facts.get("dial_off_run") == "overcool":
        lines.append(
            "FCR08/FCR10 dial/control OFF with the compressor still running or the "
            "cavity over-cold is already in play. Do NOT open fuse (p.19), 12V continuity "
            "(p.20), or diagnostic LED / inverter control voltage (p.18). Confirm dial "
            "fully OFF, seat the probe and thermostat wires (p.43), then open C (blue) "
            "and T (black) with no jumper (p.31 Figs. 24–25 inverse). Compressor stops → "
            "R&R Spark-Free Thermostat part G 2021128850 (retail C-FCR10DCGTA-007), "
            "p.43–45. Compressor keeps running with C/T open → inverter/harness. "
            "Cite p.31 and p.43–45 only. Leave the dial fully OFF."
        )
    if facts.get("ct_prove") == "stopped":
        lines.append(
            "Open C/T already stopped the compressor. Climax is R&R Spark-Free "
            "Thermostat part G 2021128850 (retail C-FCR10DCGTA-007) per CCD-0008122 "
            "p.43–45 Figs. 57–67. Cite p.31 for the open C/T prove and p.43–45 for the R&R."
        )
    elif facts.get("ct_prove") == "still_running":
        lines.append(
            "Open C/T and the compressor kept running. Escalate inverter/harness "
            "(CCD-0008122 p.45). Do not lead with fuse and do not R&R the thermostat "
            "as the climax of this prove."
        )
    if facts.get("can_isolate") == "stays":
        lines.append(
            "The Firefly-cable prove already showed Manual Mode HOLDS with the Firefly "
            "cable unplugged and the rubber-boot plug still in. Firefly / OneControl "
            "conflict is confirmed. Tell the tech to reconnect the Firefly cable after "
            "the prove unless using interim. Real fix: Firefly USB firmware — GUI + CCM "
            "from Settings, Firefly 574-825-4600, USB stick ≤4 GB. Interim: front-bay "
            "main battery OFF (solar OK) or leave the Firefly cable unplugged with the "
            "rubber-boot plug still in. Do NOT swap another Level Up controller for Firefly blame."
        )
    elif facts.get("can_isolate") == "still_dumps":
        lines.append(
            "The Firefly-cable prove already showed Manual Mode STILL DUMPS with the "
            "Firefly cable unplugged. This is NOT a Firefly / OneControl conflict. Stay "
            "on the Level Up sensor / harness / support path. Do NOT swap another Level "
            "Up controller for Firefly blame. Do NOT push Firefly USB as the fix."
        )
    elif facts.get("auto_level") == "works" and facts.get("manual_dump") == "reported":
        if facts.get("sticky_level_error") == "present":
            lines.append(
                "Clear sticky Low Voltage / Excess Angle / External Sensor first. "
                "Do not jump to Firefly USB or another Level Up controller swap."
            )
        else:
            lines.append(
                "Manual Mode dumps while Auto Level still works. Cheap proves first "
                "(power / no brownout; no sticky LV / Excess Angle / External Sensor). "
                + FIREFLY_TWO_PLUG_PROVE
                + " Do not open board/LCD swap first. Do not push Firefly USB until "
                "Manual Mode holds with the Firefly cable unplugged."
            )
    elif facts.get("manual_dump") == "reported":
        lines.append(
            "Manual Mode flash/dump-to-home is already in play. Ask/confirm Auto Level "
            "still works, power looks sane / no brownout, and the dump is not sticky "
            "Low Voltage / Excess Angle / External Sensor before you unplug the Firefly "
            "cable or order parts."
        )
    if facts.get("bal_tongue") == "only_dead":
        stage = bal_tongue_stage(facts)
        if stage == "coupler":
            lines.append(
                "Manual override will not turn, or the motor failed direct 12V. "
                "Coupler replacement is allowed. Do NOT lead with the 30A fuse or the "
                "remote stabilizer harness. Do NOT make soft-touch user panel 20300427 the primary."
            )
        elif stage == "panel":
            lines.append(
                "No 12V on the tongue jack output wire at the panel. Climax is soft-touch "
                "user panel 20300427. Do NOT lead with coupler, shear pin, 30A fuse, or "
                "the remote stabilizer harness."
            )
        elif stage == "pigtail":
            lines.append(
                "12V is present on the tongue jack output wire at the panel. Climax is tongue "
                "pigtail / panel-to-motor lead repair. Do NOT lead with coupler, 30A fuse, "
                "or the remote stabilizer harness."
            )
        else:
            lines.append(
                "BAL Soft-Touch tongue-only dead is in play. Press tongue extend/retract "
                "and check for 12V on the tongue jack output wire at the panel, then the "
                "local tongue pigtail. No 12V on the tongue output wire "
                "→ user panel 20300427. Do NOT lead with coupler / shear-pin or fuse / 30A / "
                "remote stabilizer harness. Coupler only if the override will not turn or the "
                "motor fails direct 12V."
            )
    if facr_terminal_path_complete(facts):
        lines.append(
            "Drain, pan/slope, filter/fan, suction line, freeze sensor, thermostat, "
            "nozzles/ambient, and refrigerant pressures are already reported good. "
            "The freeze or interior leak remains. TERMINAL CARD: authorize rooftop "
            "assembly R&R on the CCD-0007990 condensate and assembly path. Replace "
            "the rooftop assembly. This is an authorization card, not an R&R procedure. "
            "Do NOT say the library has no R&R steps. Do NOT ask the tech to paste an "
            "R&R section. Do NOT open compressor no-start, fan-winding continuity, or "
            "a DC bus measurement. Do NOT return a blank card. Do NOT open a fuse "
            "or 12V-first tree. Do NOT stall on searching manuals."
        )
    elif facts.get("facr_auth_request") == "yes":
        lines.append(
            "The tech asked to authorize rooftop assembly R&R before the freeze/leak "
            "prove is finished. Do NOT emit the assembly authorization card yet. "
            "Do NOT say the library has no R&R steps and do NOT ask for a pasted "
            "R&R section. Ask the next missing condensate/freeze check only. "
            "Do NOT open compressor no-start or a DC bus measurement."
        )
    elif facr_proves_complete(facts):
        lines.append(
            "Drain is clear, fan and filter are OK, and the freeze sensor is good. "
            "CONTINUE to rooftop assembly R&R on the CCD-0007990 condensate/assembly path. "
            "Do NOT stall on searching manuals. Do NOT repeat a drain-only check."
        )
    elif facts.get("facr_drain") == "clear" and (
        facts.get("facr_fan_filter") or facts.get("facr_freeze_sensor")
    ):
        lines.append(
            "FACR freeze proves are in progress. Do not stall on searching manuals. "
            "Do not repeat a drain check that is already clear. Move to the remaining "
            "fan/filter or freeze-sensor prove, then rooftop assembly R&R (CCD-0007990)."
        )
    if facts.get("coleman_2111") == "climax":
        lines.append(
            "Coleman-Mach 2111-0001 evidence is complete: Fan High is dead, the "
            "Peacemaker bypass shows the compressor runs with the fan locked at "
            "about 1.9 A, and the fan run capacitor is about rated. TERMINAL CARD: "
            "authorize R&R of the fan motor and the control board ONLY. Do NOT "
            "authorize the full 2111-0001 assembly. Stop. Do not ask for continuity "
            "or another test. Cite the 12VDC wall-thermostat service manual, "
            "1976-536, 1976-603, Peacemaker, and mechanical controls / 1976-695. "
            "Do not invent page numbers."
        )
    elif facts.get("coleman_2111") == "open":
        lines.append(
            "Coleman-Mach 2111-0001 is in play. Stay on Fan High, the Peacemaker "
            "bypass, and the fan run capacitor. Do not authorize the full assembly "
            "and do not authorize motor + board until Fan High is dead, the fan is "
            "locked at about 1.9 A with the compressor running, and the capacitor "
            "measures about rated."
        )
    return "\n".join(lines)


def coach_library_search_boost(facts: dict) -> str:
    """
    Extra library search terms from stated facts.
    Does not encode the wrong Furrion hard-tree path.
    E2 / Fan Fault Current steers to Fan Fault Diagnostics + Fan Replacement,
    not compressor-only or board-only R&R.
    """
    if not facts:
        return ""
    parts = []
    fan_fault = bool(facts.get("fan_fault") or facts.get("fan_volts") or facts.get("fan_amps"))
    ice_moisture = facts.get("ice_moisture") == "rear_wall"
    dial_off_run = facts.get("dial_off_run") == "overcool"
    if fan_fault:
        parts.append(FAN_FAULT_SEARCH_BOOST)
    elif dial_off_run:
        parts.append(DIAL_OFF_RUN_SEARCH_BOOST)
    elif ice_moisture:
        parts.append(ICE_MOISTURE_SEARCH_BOOST)
    elif facts.get("light") == "on" and facts.get("cooling") == "not_cooling":
        parts.append("not cooling inoperable compressor section 2 powered")
    if (
        (facts.get("compressor") == "not_running" or facts.get("pivot") == "compressor")
        and not fan_fault
        and not ice_moisture
        and not dial_off_run
    ):
        parts.append("inoperable compressor compressor diagnostics")
    if facts.get("dial") == "on_4_5" and not fan_fault and not ice_moisture and not dial_off_run:
        parts.append("thermostat dial not cooling")
    if facts.get("pan_on_flameout"):
        parts.append(COOKTOP_SEARCH_BOOST)
    if facts.get("bal_tongue") == "only_dead":
        parts.append(BAL_TONGUE_SEARCH_BOOST)
    elif facts.get("override_pin") == "broken_or_seized":
        parts.append(PSX1_SEARCH_BOOST)
    if facr_terminal_path_complete(facts) or facr_proves_complete(facts):
        parts.append(FACR_ASSEMBLY_SEARCH_BOOST)
    if facts.get("coleman_2111"):
        parts.append(COLEMAN_2111_SEARCH_BOOST)
    if (
        facts.get("can_isolate")
        or (
            facts.get("manual_dump") == "reported"
            and facts.get("auto_level") == "works"
        )
    ):
        parts.append(LEVEL_UP_CAN_SEARCH_BOOST)
    return " ".join(parts).strip()


def powered_not_cooling(facts: dict) -> bool:
    return bool(facts.get("light") == "on" and facts.get("cooling") == "not_cooling")


def reply_reasks_stated_facts(reply: str, facts: dict) -> list:
    """Fact keys the coach just re-asked. Empty means the turn is clean."""
    if not reply or not facts:
        return []
    t = _norm(reply)
    hits = []
    if facts.get("light") in ("on", "off"):
        if re.search(
            r"does the (?:refrigerator |fridge )?(?:cavity |interior )?light come on"
            r"|is the (?:cavity |interior )?light on"
            r"|also say if it is cooling",
            t,
        ):
            hits.append("light")
    if facts.get("cooling") in ("not_cooling", "cooling"):
        if re.search(
            r"also say if it is cooling"
            r"|say if it is cooling or not cooling"
            r"|is (?:the )?(?:fridge|refrigerator|it) cooling\b"
            r"|does it (?:seem to )?cool",
            t,
        ):
            hits.append("cooling")
    if facts.get("fuse") in ("replaced", "blown", "good"):
        if re.search(
            r"report fuse result|visually check the fuse|is the fuse (?:blown|good)|pull the front vent cover",
            t,
        ):
            hits.append("fuse")
    if facts.get("auto_level") == "works":
        if re.search(r"does auto level (?:still )?work|is auto level working", t):
            hits.append("auto_level")
    if facts.get("can_isolate") in ("stays", "still_dumps"):
        if re.search(
            r"unplug (?:only )?(?:the )?wired coach can|"
            r"unplug that cable only|two network plugs|retry manual mode",
            t,
        ):
            if "reconnect" not in t:
                hits.append("can_isolate")
    return hits


def strip_path_complete_trap(text: str) -> str:
    """Remove leftover cage captions if a model echoes them."""
    if not text:
        return text
    text = re.sub(
        r"this path is complete\.?\s*start a new chat for another symptom branch\.?",
        "",
        text,
        flags=re.I,
    )
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Coach turns re-send the full system prompt, manual excerpts, and every prior
# assistant reply. Groq/xAI answer that with HTTP 413 "request too large".
# Trim history and compact citations on every GD turn, then retry a 413 with
# a smaller payload so the session can still reach a part climax.
COACH_HISTORY_MAX_MESSAGES = 6
COACH_HISTORY_ASSISTANT_CAP = 480
COACH_EXCERPT_CHAR_CAP = 700
COACH_CONTEXT_CHAR_CAP = 4200
COACH_SYSTEM_CHAR_CAP = 16000
_PAYLOAD_TOO_LARGE_RE = re.compile(
    r"("
    r"\b413\b|"
    r"request too large|"
    r"payload too large|"
    r"request entity too large|"
    r"context[_ ]length|"
    r"maximum context|"
    r"too many tokens|"
    r"token limit|"
    r"reduce the length"
    r")",
    re.I,
)


def is_ai_request_too_large(exc) -> bool:
    """True for HTTP 413 / provider 'request too large' / context overflow."""
    return bool(_PAYLOAD_TOO_LARGE_RE.search(str(exc or "")))


def _compact_coach_text(text: str, cap: int) -> str:
    """Keep the shop action and source lines; drop pasted excerpt dumps."""
    raw = (text or "").strip()
    if not raw or len(raw) <= cap:
        return raw
    lines = []
    used = 0
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        keep = s.lower().startswith("source:") or s.startswith("📖") or "📖 source" in s.lower()
        if not keep and len(lines) >= 6:
            continue
        if used + len(s) + 1 > cap:
            break
        lines.append(s)
        used += len(s) + 1
    compact = "\n".join(lines).strip()
    if not compact:
        compact = raw[:cap].rstrip()
    if len(compact) > cap:
        compact = compact[: max(0, cap - 1)].rstrip() + "…"
    return compact


def trim_coach_history(
    history: list | None,
    max_messages: int = COACH_HISTORY_MAX_MESSAGES,
    assistant_cap: int = COACH_HISTORY_ASSISTANT_CAP,
) -> list:
    """
    Keep the original complaint plus the newest turns.
    Compact assistant citations so prior coach essays do not bloat the next call.
    """
    msgs = []
    for m in history or []:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            msgs.append({"role": role, "content": content})
    if not msgs:
        return []
    if len(msgs) > max_messages:
        tail_n = max(1, max_messages - 1)
        tail = msgs[-tail_n:]
        if msgs[0] not in tail:
            first = {"role": msgs[0]["role"], "content": msgs[0]["content"]}
            if len(first["content"]) > 700:
                first["content"] = first["content"][:699].rstrip() + "…"
            msgs = [first] + tail
        else:
            msgs = msgs[-max_messages:]
    out = []
    last_asst = max((i for i, m in enumerate(msgs) if m["role"] == "assistant"), default=-1)
    for i, m in enumerate(msgs):
        content = m["content"]
        if m["role"] == "assistant":
            cap = assistant_cap if i == last_asst else min(assistant_cap, 480)
            content = _compact_coach_text(content, cap)
        elif len(content) > 1600:
            content = content[:1599].rstrip() + "…"
        out.append({"role": m["role"], "content": content})
    return out


def compact_manual_context(
    context: str,
    excerpt_cap: int = COACH_EXCERPT_CHAR_CAP,
    total_cap: int = COACH_CONTEXT_CHAR_CAP,
) -> str:
    """Shorten each manual excerpt. Keep the header (manual title + page)."""
    raw = (context or "").strip()
    if not raw:
        return ""
    parts = re.split(r"(?=\[EXCERPT\s+\d+)", raw)
    if len(parts) == 1:
        if len(raw) <= total_cap:
            return raw
        return raw[: max(0, total_cap - 1)].rstrip() + "…"
    compacted = []
    for part in parts:
        block = part.strip()
        if not block:
            continue
        if len(block) > excerpt_cap:
            block = block[: max(0, excerpt_cap - 1)].rstrip() + "…"
        compacted.append(block)
    text = "\n\n".join(compacted)
    if len(text) > total_cap:
        text = text[: max(0, total_cap - 1)].rstrip() + "…"
    return text


def _shrink_system_content(text: str, system_cap: int, excerpt_cap: int) -> str:
    raw = text or ""
    idx = raw.lower().find("manual excerpts")
    if idx != -1:
        head = raw[:idx]
        tail = compact_manual_context(
            raw[idx:],
            excerpt_cap=excerpt_cap,
            total_cap=max(1800, system_cap // 2),
        )
        raw = head + tail
    if len(raw) <= system_cap:
        return raw
    head_keep = system_cap // 2
    tail_keep = max(0, system_cap - head_keep - 16)
    return raw[:head_keep].rstrip() + "\n…\n" + raw[-tail_keep:]


def shrink_ai_messages(
    messages: list | None,
    *,
    level: int = 1,
) -> list:
    """
    Smaller chat payload for a 413 retry.
    level 1 trims history and excerpts. level 2 keeps system + the latest turn only.
    """
    level = 2 if level >= 2 else 1
    history_max = 4 if level == 1 else 2
    assistant_cap = 420 if level == 1 else 220
    system_cap = 9000 if level == 1 else 4500
    excerpt_cap = 700 if level == 1 else 320
    user_cap = 800 if level == 1 else 400
    prepared = []
    for m in messages or []:
        role = (m.get("role") or "").strip()
        content = m.get("content")
        if not isinstance(content, str):
            prepared.append({"role": role, "content": content})
            continue
        prepared.append({"role": role, "content": content})
    system = [m for m in prepared if m.get("role") == "system"][:1]
    rest = [m for m in prepared if m.get("role") != "system"]
    if len(rest) > history_max:
        rest = rest[-history_max:]
    out = []
    for m in system:
        content = m.get("content")
        if isinstance(content, str):
            content = _shrink_system_content(content, system_cap, excerpt_cap)
        out.append({"role": "system", "content": content})
    last_user_idx = max((i for i, m in enumerate(rest) if m.get("role") == "user"), default=-1)
    for i, m in enumerate(rest):
        role = m.get("role") or "user"
        content = m.get("content")
        if isinstance(content, str):
            if role == "assistant":
                content = _compact_coach_text(content, assistant_cap)
            elif i != last_user_idx and len(content) > user_cap:
                content = content[: max(0, user_cap - 1)].rstrip() + "…"
        out.append({"role": role, "content": content})
    return out


def complete_chat_with_payload_retry(call, messages, temperature: float = 0.2, max_tokens: int = 1400) -> str:
    """
    call(messages, temperature, max_tokens) -> text.
    On 413 / request-too-large, retry twice with a smaller payload.
    Other errors propagate immediately.
    """
    attempts = (
        (list(messages or []), max_tokens, 0),
        (shrink_ai_messages(messages, level=1), min(max_tokens, 700), 1),
        (shrink_ai_messages(messages, level=2), min(max_tokens, 480), 2),
    )
    last = None
    for payload, tokens, _level in attempts:
        try:
            return call(payload, temperature, tokens)
        except Exception as exc:
            last = exc
            if not is_ai_request_too_large(exc):
                raise
    if last is not None:
        raise last
    raise RuntimeError("AI chat failed")


def _clean_model_id(name: str) -> str:
    return (name or "").strip()


def pick_working_vision_model(candidates, call_model):
    """
    Try vision models in order so a retired id (llama-4-scout 404)
    falls through to qwen/qwen3.6-27b instead of aborting the plate read.
    call_model(model_id) -> raw text (empty string counts as miss).
    Returns (model_id, raw, errors).
    """
    errors = []
    for model in candidates or []:
        mid = _clean_model_id(model)
        if not mid:
            continue
        try:
            raw = (call_model(mid) or "").strip()
            if raw:
                return mid, raw, errors
            errors.append(f"{mid}: empty vision response")
        except Exception as e:
            errors.append(f"{mid}: {e}")
    return None, "", errors


def groq_vision_model_candidates(preferred: str = "") -> list:
    """Working Groq vision models. Scout is dead unless a shop secret explicitly names it."""
    out = []
    pref = _clean_model_id(preferred)
    if pref:
        out.append(pref)
    for m in DEFAULT_GROQ_VISION_MODELS:
        if m and m not in out:
            out.append(m)
    return out


def xai_vision_model_candidates(preferred_vision: str = "", preferred_chat: str = "") -> list:
    """Prefer an explicit vision model, then the shop chat model, then known xAI vision ids."""
    out = []
    for m in (_clean_model_id(preferred_vision), _clean_model_id(preferred_chat)):
        if m and m not in out:
            out.append(m)
    for m in DEFAULT_XAI_VISION_MODELS:
        if m and m not in out:
            out.append(m)
    return out
