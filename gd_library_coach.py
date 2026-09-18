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

# Document Library names. GD chat / Jobs / library pickers and seed_data share this list.
# Match live library labels — do not invent OEM manuals here.
WATER_HEATERS_CATEGORY = "Water Heaters"
RANGE_COOKTOPS_CATEGORY = "Range & Cooktops"
AIR_CONDITIONING_CATEGORY = "Air Conditioning"
REFRIGERATORS_CATEGORY = "Refrigerators"

DEFAULT_LIBRARY_CATEGORIES = (
    REFRIGERATORS_CATEGORY,
    "Furnaces",
    WATER_HEATERS_CATEGORY,
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
    """Same list the Guided Diagnostics category selectbox uses."""
    return ["(any)"] + library_category_picker_names(existing_names)

# Groq retired llama-4-scout on 2026-07-17 (404 / no access).
# Current Groq vision: https://console.groq.com/docs/vision
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

OPEN_LIBRARY_COACH_RULE = """
OPEN LIBRARY COACH (product path — not a locked flowchart, not a Jobs WO plan):
- Take the complaint and guide the tech from THIS SHOP's Document Library / service-manual excerpts only.
- Say "the shop Document Library" or "the Furrion (or brand) service manual" — never "the text you uploaded."
- Answer clarifying questions, figure/diagram/illustration requests, and mid-job pivots in THIS chat.
- NEVER say "This path is complete" or tell the tech to start a new chat for another symptom branch.
- NEVER re-ask a fact the tech already stated in this chat (including the latest message). Restate briefly what you heard, then give the next cited check or answer their question.
- If they already said the cavity light is on and the fridge is not cooling, do NOT ask those again. Do NOT restart at the fuse / no-power path. Follow the cited service-manual section for a powered unit that is not cooling (e.g. inoperable compressor). Do not force Fan Replacement on that not-cooling / compressor path unless THIS turn's excerpt or an already-stated Furrion FCR E2 / 2-flash / Fan Fault Current says so.
- Furrion FCR08/FCR10 E2 / 2-flash / Fan Fault Current is freezer-fan / airflow (CCD-0008122 Error Code — Fan Fault Diagnostics + Fan Replacement). The SM fan on F+/F− is a replaceable part (shop name: freezer evaporator fan). Do not cage that path to rear inverter/control board only. Recommend freezer evaporator fan R&R, and board + fan when readings support both.
- Suburban / gas cooktop burner lights then goes out when a pan is placed: verify the thermocouple / flame-sensor tip is in the flame WITH COOKWARE ON before condemning thermocouple, safety valve, orifice, regulator, or igniter. Cite Suburban Range/Cooktops SM. Do not invent voltages.
- Front stabilizer / PSX1 power works but manual crank/override will not engage with a broken or seized roll pin / override coupler: replace the complete stabilizer jack assembly (not coupler-only). Lippert PSX1 CCD-0007345 override-usage pages are for using the override, not the end fix for a destroyed pin.
- Furrion FCR / Arctic / similar fridge ice, frost, or icing on the rear/back wall (including about half from the top) or moisture in the fridge cavity: follow CCD-0008122 Ice and Moisture → Ice or Moisture in the Fridge (p.36 / Fig.36). Coach order: pattern note → dial max? → gasket → cooling verify → watch/replace. Do NOT open No Power / fuse / 12V inverter unless the complaint is no power / dead / won't run / no light. Cite page 36 and Fig. 36 — never a fake "Fuse location" title with no page.
- Furrion FACR* rooftop freeze / ice / frost / condensate / base-pan / suction icing / melt-leak: search and cite existing CCD-0007990 Furrion Rooftop HVAC Troubleshooting & Service Manual and CCD-0008666 (Furrion Chill FACR) — not Dometic-only rooftop books. Do not invent OEM steps.
- Level-Up Manual Mode flashes or dumps to home while Auto still works: Firefly CAN path — cheap proves, then isolate with the rubber-boot terminator left in (wired CAN out). If Manual stays: Firefly USB firmware, 574-825-4600, stick ≤4 GB + interim. Do not frame it as confirm Manual dump works.
- If they say "go to compressor section" (or any other change of direction), follow that request using cited library pages.
- Cite 📖 Source: [Exact manual title from excerpt] - page [N] when you use a page. Never invent OEM steps or page numbers.
- If the tech asks to see a figure/diagram/page, say TechTrack will display the shop library PDF page below. Do not invent markdown images.
- If they ask for labeled terminals / PCB / inverter board / pinout / wiring: cite a page that actually has Fig./F+/F−/inverter PCB/wiring/housing labels. If the excerpt is Quick Notes / Nominal voltage with no diagram, say so — do not invent pad locations. Try the next figure page, or ask which: wiring / LED D/+ / fan F+ F− / housing labels.
- When recommending the next check (not answering a question), give at most 1-2 concrete tests, then wait. Ask only for facts that are still missing.
"""

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
# Manual Mode dump works + Auto works → Firefly CAN isolate / terminator (not Unity).
FIREFLY_CAN_SEARCH_BOOST = (
    "Firefly CAN isolate terminator rubber-boot terminator left in "
    "wired CAN out USB firmware 574-825-4600 interim 4 GB "
    "Manual Mode flashes home Auto Level works"
)
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
- Manual Mode flashes / dumps to home while Auto still works is the Firefly CAN path — not a hydraulic dump test. Cheap-prove Auto, then CAN isolate with the rubber-boot terminator left in (wired CAN out). If Manual stays on flash/home: Firefly USB firmware, 574-825-4600, stick 4 GB or smaller + interim file. Do not start at pump R&R.
- Do NOT say the shop library does not include Level Up controller diagnostics if any Level-Up / OCTP / TI-005 / QR-092 / QR-059 / Leveling Level-Up title exists in the catalog.
- If the best Level-Up hit is unindexed or has zero searchable chunks, name that title and ask a manager to re-index it. Do not invent Unity as a substitute.
- If a figure/page render fails, say the figure is in that shop-library PDF and the page image could not be shown. Do not claim the library lacks the procedure.
"""
LEVEL_UP_EMPTY_CLAIM_RE = re.compile(
    r"(library|manuals?|document library).{0,80}(does not|doesn't|do not|don't|lacks?|no |without).{0,60}"
    r"(level[\s-]*up|807662|leveling controller)|"
    r"(no|not|lack|missing|doesn't have|does not have|do not have).{0,50}"
    r"(level[\s-]*up|807662).{0,40}(manual|procedure|diagnos|controller|guide)",
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
- Furrion FACR* rooftop freeze / ice / frost / condensate / base-pan / suction icing / melt-leak: search and cite CCD-0007990 Furrion Rooftop HVAC Troubleshooting & Service Manual AND CCD-0008666 (Furrion Chill FACR) — not Dometic-only rooftop books. Do not invent OEM steps or page numbers; use those existing titles.
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
- Early in this path, instruct the tech to verify the thermocouple / flame-sensor TIP is positioned in the burner flame WITH COOKWARE ON. Factory often sets the tip too close to the burner head; the flame can leave the tip under load.
- Do this BEFORE condemning or R&R of the thermocouple, safety valve, orifice, regulator, or igniter.
- Only if tip geometry is correct WITH the pan on and the flame still drops out, proceed to parts / readings from the Suburban Range/Cooktops SM excerpt actually used.
- Never invent OEM voltages or page numbers. Cite 📖 Source from an excerpt actually used.
"""
COOKTOP_TIP_PAN_SHOP_LINE = (
    "Before condemning the thermocouple, safety valve, orifice, regulator, or igniter: "
    "verify the thermocouple / flame-sensor tip is positioned in the burner flame "
    "WITH COOKWARE ON. Reposition the tip so the flame stays on the tip under load. "
    "Only if tip geometry is correct and the flame still drops out, proceed to parts "
    "R&R from the Suburban Range/Cooktops SM.\n"
    "📖 Source: Suburban Range/Cooktops SM"
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
PSX1_ASSEMBLY_RR_SHOP_LINE = (
    "When the manual-override roll pin / coupler is broken or seized and not "
    "serviceable in the field, replace the complete front stabilizer jack assembly "
    "(reconnect mount and electrical; retest power extend/retract and manual crank). "
    "Do not replace the coupler only. Lippert PSX1 CCD-0007345 override-usage pages "
    "(including p.7) are for using the override, not the end fix for a destroyed pin.\n"
    "📖 Source: Lippert PSX1 CCD-0007345"
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
- Coach order — open language, one clarifying ask or 1–2 next checks per turn, not a quiz cage: pattern note → dial max? → gasket → cooling verify → watch/replace.
- Do NOT open No Power / fuse / 12V inverter unless the complaint is no power / dead / won't run / no light.
- Cite the real page and figure: 📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36 (Fig. 36). Never invent a "Fuse location" title with no page.
- Never invent other OEM steps or page numbers. Use the Ice and Moisture excerpt actually retrieved.
"""
ICE_MOISTURE_SHOP_LINE = (
    "CCD-0008122 Ice and Moisture → Ice or Moisture in the Fridge (p.36 / Fig.36). "
    "Rear/back-wall ice or frost (including half from the top) is a moisture path, "
    "not a no-power fuse / 12V inverter tree. Next from that section: note the frost "
    "pattern, then check whether the dial is at max, then the door gasket, then verify "
    "cooling — watch/replace only from that Ice and Moisture page. Do not open the "
    "15A fuse / 12V inverter path unless the complaint is no power / dead / won't run "
    "/ no light.\n"
    "📖 Source: Furrion FCR08/FCR10 SM CCD-0008122 - page 36"
)
FRIDGE_NO_POWER_RE = re.compile(
    r"\b("
    r"no\s+power|completely\s+dead|no\s+light|no\s+juice|"
    r"won'?t\s+turn(?:\s+on)?|wont\s+turn(?:\s+on)?|"
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


def is_level_up_advantage_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Hydraulic Level Up Advantage / 807662 / OCTP / leveling Manual Mode.
    Ground Control electric alone is a different product.
    """
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


def is_firefly_can_path_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Level-Up / Firefly: Manual Mode dump works + Auto works → CAN isolate / terminator.
    Do not steal fridge, rooftop AC, water heater, or cooktop jobs.
    """
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
    dump = bool(re.search(r"\bdump\b", blob))
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


def is_air_conditioning_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Rooftop Air Conditioning: category, Furrion FACT*, Furrion FACR* / Chill,
    Dometic B57915/Brisk, ADB, E2/E3 AC codes, no-cool AC. Fridge 'not cooling' is not AC.
    """
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


def ensure_cooktop_tip_pan_check(reply: str) -> str:
    """
    Deterministic shop line so pan-on flame-out cannot skip tip geometry.
    Prepends so tip/position/pan appear before any parts R&R.
    """
    if not reply or not cooktop_reply_needs_tip_pan(reply):
        return reply
    if reply_has_tip_pan_before_parts(reply):
        return reply
    if "with cookware on" in _norm(reply) and "tip" in _norm(reply):
        if reply_has_tip_pan_before_parts(f"{COOKTOP_TIP_PAN_SHOP_LINE}\n\n{reply}"):
            return f"{COOKTOP_TIP_PAN_SHOP_LINE}\n\n{reply}".strip()
    return f"{COOKTOP_TIP_PAN_SHOP_LINE}\n\n{reply}".strip()


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


def is_stabilizer_override_pin_context(
    category_name: str = "",
    model_text: str = "",
    symptom: str = "",
) -> bool:
    """
    Front stabilizer / PSX1: power works, manual override will not engage
    (broken/seized roll pin). Level-Up hydraulic 807662 must lose.
    """
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


def ensure_fridge_ice_moisture_path(reply: str) -> str:
    """
    Deterministic shop line so rear-wall ice cannot ship as fuse / 12V no-power.
    Uses CCD-0008122 Ice and Moisture p.36 / Fig.36 already in-library.
    """
    if not reply or not ice_moisture_reply_needs_guard(reply):
        return reply
    cleaned = strip_fuse_12v_no_power_claims(reply)
    if cleaned and reply_opens_fuse_12v_no_power(cleaned):
        cleaned = ""
    if reply_names_ice_moisture_p36(cleaned) and not reply_opens_fuse_12v_no_power(cleaned):
        return cleaned
    if "ice and moisture" in _norm(cleaned) and any(
        k in _norm(cleaned) for k in ("page 36", "p.36", "p. 36", "fig. 36", "fig 36")
    ):
        if not reply_opens_fuse_12v_no_power(cleaned):
            return cleaned
    return f"{ICE_MOISTURE_SHOP_LINE}\n\n{cleaned}".strip()


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
        facts["ice_moisture"] = "rear_wall"

    return facts


def facts_from_chat(history: list = None, latest_msg: str = "") -> dict:
    """Merge facts from prior tech lines plus the latest message. Latest wins on conflict."""
    merged = {}
    for m in history or []:
        if (m.get("role") or "") != "user":
            continue
        merged.update(extract_stated_facts(m.get("content") or ""))
    merged.update(extract_stated_facts(latest_msg or ""))
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
    }
    lines = [
        "TECH ALREADY STATED IN THIS CHAT — never re-ask these facts:",
    ]
    for key, val in facts.items():
        pretty = (labels.get(key) or {}).get(val) or f"{key}={val}"
        lines.append(f"- {pretty}")
    lines.append(
        "Acknowledge briefly what you heard, then give the next cited service-manual check "
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
    if fan_fault:
        parts.append(FAN_FAULT_SEARCH_BOOST)
    elif ice_moisture:
        parts.append(ICE_MOISTURE_SEARCH_BOOST)
    elif facts.get("light") == "on" and facts.get("cooling") == "not_cooling":
        parts.append("not cooling inoperable compressor section 2 powered")
    if (
        (facts.get("compressor") == "not_running" or facts.get("pivot") == "compressor")
        and not fan_fault
        and not ice_moisture
    ):
        parts.append("inoperable compressor compressor diagnostics")
    if facts.get("dial") == "on_4_5" and not fan_fault and not ice_moisture:
        parts.append("thermostat dial not cooling")
    if facts.get("pan_on_flameout"):
        parts.append(COOKTOP_SEARCH_BOOST)
    if facts.get("override_pin") == "broken_or_seized":
        parts.append(PSX1_SEARCH_BOOST)
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
