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
COACH_REVISION = "v4.20.6"
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

DEFAULT_GROQ_VISION_MODELS = (
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
)
DEFAULT_XAI_VISION_MODELS = (
    "grok-4.3",
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


# Board / terminal / PCB figure asks (Chase live: "show me labeled output terminals").
BOARD_FIGURE_ASK_HINTS = (
    "pcb", "inverter board", "board layout", "pinout", "pin-out", "pin out",
    "output terminal", "terminals labeled", "labeled terminal", "terminal label",
    "housing label", "wiring diagram", "inverter pcb", "inverter terminal",
    "fan terminal", "labeled pcb", "label the terminal", "label the board",
    "where are the terminal", "where is the terminal", "f+", "f-", "f–", "f−",
    "d/+", "silkscreen",
)


# CCD-0008122 shop SM pages that actually show board / terminal figures.
# ~11 wiring, ~16–17 Fig. 2–4 inverter + D/+, ~27 Fig. 21 F+/F−, ~45–46 Fig. 68–69 housing.
FURRION_FCR_BOARD_FIGURE_PAGES = (16, 17, 27, 11, 45, 46)
FURRION_FCR_TEXT_ONLY_PAGES = (13,)  # Troubleshooting Instructions / Quick Notes

FIG_CAPTION_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d+", re.I)
F_PLUS_MINUS_RE = re.compile(r"\bf\s*[+\-–−]", re.I)


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

# Thin title hints (no invented page numbers) — same idea as Furrion board-figure pages.
LEVEL_UP_ADVANTAGE_HINT_TITLES = (
    "TI-005 Electronic Leveling Troubleshooting Guide",
    "TI-170",
    "QR-092 Level-Up OCTP wiring",
    "QR-059 ID guide",
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

# Girard GSWH-2 tankless water heater (CCD-0009390). Not fridge FCR E2, not rooftop AC E2.
# Live library: Water Heaters / Girard GSWH-2 Troubleshooting Manual, 109 chunks.
# Do not invent blink LEDs or OEM page numbers.
WATER_HEATER_MODELS = ("gswh-2", "gswh2", "gswh 2")
WATER_HEATER_HINT_TITLES = (
    "Girard GSWH-2 Troubleshooting Manual",
    "CCD-0009390",
    "GSWH-2",
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


# FACR freeze + interior leak: once drain / fan-filter / freeze sensor are proved,
# the coach must finish on rooftop assembly R&R (CCD-0007990). Do not stall.
FACR_ASSEMBLY_SEARCH_BOOST = (
    "CCD-0007990 rooftop assembly condensate R&R replace rooftop assembly"
)


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


import manual_figures as _manual_figures


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
    # v4.20.6 (Chase, test7b): one plain line; the reply's Open PDF button sits under it.
    return "That page didn't load; tap Open PDF."


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


COACH_EXCERPT_CHAR_CAP = 700
COACH_CONTEXT_CHAR_CAP = 4200
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
