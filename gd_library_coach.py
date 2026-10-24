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

import contextvars
import re

# Product path: hard tree is never exclusive GD chat.
HARD_TREE_EXCLUSIVE_CHAT = False
# Bump with the app version. rv_techtrack reloads a cached module whose
# revision is missing or is not this stamp, even when every old name exists.
COACH_REVISION = "v4.19.65"
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
SHOP_LANGUAGE_RULE = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23


OPEN_LIBRARY_COACH_RULE = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23
OPEN_LIBRARY_COACH_RULE = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

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

FIGURE_PAGE_HONESTY = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

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
LEVEL_UP_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

# Level Up Manual Mode flash-home while Auto Level still works — Firefly/OneControl
# CAN isolate. Narrow shop path only. Not a Firefly encyclopedia. Not Unity SM.
LEVEL_UP_CAN_SEARCH_BOOST = (
    "Manual Mode flash home Auto Level Firefly terminator "
    "rubber boot network plugs Firefly cable isolate Level Up controller USB firmware"
)
LEVEL_UP_CAN_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

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
AC_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

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
WATER_HEATER_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

# Furrion FCR08/FCR10 fridge E2 / 2-flash / Fan Fault Current (CCD-0008122).
# Pages already encoded from the shop SM in this repo (figure fixture + leftover tree).
# Do not invent other page numbers.
FURRION_FCR_FAN_FAULT_PAGES = (27, 33)
FAN_FAULT_SEARCH_BOOST = (
    "Error Code Fan Fault Diagnostics Fan Fault Current "
    "F+ F- Fan Replacement inverter PCB and fan "
    "freezer evaporator fan airflow"
)
FCR_E2_FAN_FAULT_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

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
COOKTOP_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

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
PSX1_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23

# Furrion FCR / Arctic fridge rear-wall ice / frost / moisture (CCD-0008122 p.36 / Fig.36).
# Shop SM page already in the library. Do not invent other OEM pages.
FURRION_FCR_ICE_MOISTURE_PAGES = (36,)
ICE_MOISTURE_SEARCH_BOOST = (
    "Ice and Moisture Ice or Moisture in the Fridge "
    "rear wall back wall frost gasket Fig. 36 figure 36"
)
ICE_MOISTURE_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23
ICE_MONTH_CLOSE = (
    "If ice or moisture persists after drying and waiting 1 month, replace the unit."
)


def _norm(text: str) -> str:
    t = (text or "").lower().strip()
    t = t.replace("—", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t)
    return t


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
FACR_FREEZE_ASSEMBLY_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23
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


# Coleman-Mach 2111-0001: Fan High dead + Peacemaker fan locked + run cap OK
# authorizes fan motor + control board only. Compose from shop library titles.
# Do not invent a 2111-0001 bulletin or a page number.
COLEMAN_2111_SEARCH_BOOST = (
    "Coleman-Mach 2111-0001 12VDC wall thermostat rooftop service manual "
    "1976-536 1976-603 fan high pin 5 black pin 9 white "
    "Peacemaker control box bypass "
    "1976-695 mechanical controls fan motor run capacitor"
)
COLEMAN_MOTOR_BOARD_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23
_COLEMAN_2111_RE = re.compile(r"\b2111[\s-]*0001\b", re.I)


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
    "coleman", "airxcel", "thetford", "happijac", "happi jac",
    "maxxair", "maxx air", "maxxfan", "maxx fan",
)
_THETFORD_UNIT_RE = re.compile(r"\bthetford\b|\b42070\b|style\s*ii", re.I)
BRAND_CANON = {
    "airxcel": "coleman",
    "coleman": "coleman",
    # MaxxAir (Airxcel) roof fans are their own brand. A Coleman-Mach AC book is
    # not a MaxxFan source, and a MaxxFan manual is not a Coleman AC source.
    "maxxair": "maxxair",
    "maxx air": "maxxair",
    "maxxfan": "maxxair",
    "maxx fan": "maxxair",
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
    """Collapse maker aliases (Airxcel and Coleman-Mach) to one brand id.

    "Airxcel" on a MaxxAir / MaxxFan page names the parent company, not
    Coleman-Mach, so it does not add Coleman when MaxxAir is also named.
    """
    found = named_shop_brands(*texts)
    canon = {BRAND_CANON.get(b, b) for b in found}
    if "maxxair" in canon and "coleman" in canon and "coleman" not in found:
        canon.discard("coleman")
    return canon


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


def reply_names_fact12_freeze_resecure(reply: str) -> bool:
    t = _norm(reply)
    return "resecure" in t and "freeze sensor" in t


GROUND_CONTROL_SEARCH_BOOST = (
    "Lippert Ground Control electric leveling manual level zero-point calibration 343633"
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
    "Zero-point calibration is the repair.\n"
    "📖 Source: Lippert Internal Tech Support – Electric Leveling Systems "
    "(Ground Control TT/2.0/3.0)"
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
# Shared with the Bay PDF. E8 is the air-pressure switch. The sensing tube is at the blower.
GIRARD_PETIT_ALIGN_LINE = (
    "E8 is the air pressure switch. The sensing tube is at the blower. "
    "Look through the exhaust vent, confirm the tube is connected at the blower and the switch, "
    "and report what you find.\n"
    "📖 Source: Girard tankless water heater service manual CCD-0009390, page 23"
)


def ground_control_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if not is_ground_control_context(category_name, model_text, symptom):
        return symptom
    if GROUND_CONTROL_SEARCH_BOOST in symptom:
        return symptom
    return f"{symptom} {GROUND_CONTROL_SEARCH_BOOST}".strip()


def reply_names_ground_control_calibration(reply: str) -> bool:
    t = _norm(reply)
    manual = "manual level" in t
    zero = "zero-point" in t or "zero point" in t
    return bool(manual and zero)


def dometic_nocoool_open_line(facts: dict | None = None) -> str:
    """Fan already running starts at the Peacemaker. Otherwise confirm the fan first."""
    if (facts or {}).get("dometic_fan") == "runs":
        return DOMETIC_NOCOOL_OPEN
    return DOMETIC_NOCOOL_CONFIRM_FAN


def _repair_stands_said(history: list = None) -> bool:
    return "repair stands" in _prior_assistant_text(history).lower()


def _prior_assistant_text(history: list = None) -> str:
    return " ".join(
        message.get("content") or ""
        for message in history or []
        if (message.get("role") or "") == "assistant"
    )


_GUARD_FIRED: contextvars.ContextVar = contextvars.ContextVar("tt_guard_fired", default="")
_SUPPLY_PAGE_ART: contextvars.ContextVar = contextvars.ContextVar("tt_supply_page_art", default=False)


def last_guard_name() -> str:
    """The guard that replaced the draft on the last avoid_duplicate_reply call."""
    return _GUARD_FIRED.get() or ""


def note_supply_page_art(has_art: bool):
    """The supply show-me uses the page image when 42088 page 3 has one."""
    return _SUPPLY_PAGE_ART.set(bool(has_art))


def reset_supply_page_art(token) -> None:
    _SUPPLY_PAGE_ART.reset(token)


import manual_figures as _manual_figures

THETFORD_CITE_42088 = "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3"


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


BAL_TONGUE_DOC = "INS.STA.001"
BAL_TONGUE_SEARCH_BOOST = (
    "BAL Soft-Touch SS 5.1 INS.STA.001 20300427 soft-touch user panel "
    "tongue jack output wire pigtail panel-to-motor"
)
BAL_TONGUE_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23
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


def bal_tongue_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if not is_bal_soft_touch_tongue_only_context(category_name, model_text, symptom):
        return symptom
    if BAL_TONGUE_SEARCH_BOOST in symptom:
        return symptom
    return f"{symptom} {BAL_TONGUE_SEARCH_BOOST}".strip()


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


def _ice_has_month_close(reply: str) -> bool:
    t = _norm(reply)
    return "1 month" in t and "replace the unit" in t


# Furrion Arctic FCR08/FCR10 — dial/control OFF, compressor still running / overcooling.
# Locked climax cites: open C (blue) / T (black) — inverse of the p.31 jumper —
# then, if the compressor stops, R&R part G 2021128850 on p.43–45.
# Locked cites for this prove are p.31 and p.43–45 only.
FURRION_FCR_DIAL_OFF_RUN_PAGES = (31, 43, 44, 45)
FCR_DIAL_OFF_RUN_RETAIL = "C-FCR10DCGTA-007"


DIAL_OFF_RUN_SEARCH_BOOST = (
    "Spark-Free Thermostat temperature controller Thermostat Replacement "
    "flag terminals C blue T black probe seated Fig. 24 Fig. 25 "
    "part 2021128850 Repair Section 2"
)
DIAL_OFF_RUN_PRODUCT_LOCK = ""  # prompt rule text removed 2026-10-23 (Chase order); original in drafts/REMOVED-RULES-2026-10-23


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
        (shrink_ai_messages(messages, level=1), None if max_tokens is None else min(max_tokens, 700), 1),
        (shrink_ai_messages(messages, level=2), None if max_tokens is None else min(max_tokens, 480), 2),
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
