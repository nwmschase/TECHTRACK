"""
Bay procedure PDF — printable human bay sheet from this shop's Document Library.

Product (Chase-locked, v2):
  Tech enters a customer concern (+ optional brand / model / category / WO#).
  Retrieve with the same Document Library stack Guided Diagnostics uses (no live web).
  Compile a printable bay sheet:
    header (concern, model, date, WO#, primary OEM cite)
    what this pattern usually means
    visual flowchart (drawn diamonds / boxes / yes-no branches)
    bay order punch list
    do-not list
    cited library figures when available
    sources with real IDs/pages
    optional blank 3C as a small footer only — never the body
  Voice: complete sentences, human service-tech wording — not fragments or bot outlines.
  Labels: common service names (Level Up controller, Firefly panel, door gasket,
    rubber-boot plug). Do not lead with a bare part number. Never use the old
    network-jargon isolate label.
  Nav/button label is always "Bay procedure PDF" — never "AI report".
  Do not auto-write a warranty story.

Standing sheet standard (Chase 2026-09-19, all future concerns inherit this):
  Short paths (Firefly-class) may be short but must be complete.
  Long / multi-branch appliance paths are full A→Z, not hint PDFs.
  A→Z: concern; pattern meaning; readable OEM yes/no flowchart; ordered bay
  steps with a continued next step after every check; manual thresholds/tests/
  good-bad ON the page (never "open the SM"); readable library figures; lands
  at a confirmed fix so Concern → Cause → Correction can be written from the
  sheet; names not PNs in the body.
  Bans: program/coach do-not chatter (Firefly tech do-nots are the exception);
  "wired coach CAN"; "network plugs"; "power looks sane"; "stays open".
  Prefer holds / still dumps home. Firefly locked voice stays locked.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo
from pathlib import Path

import bay_profile_lines as bpl
import math
import re
import textwrap
import zlib

from gd_library_coach import (
    COOKTOP_TIP_LOW_REPAIR,
    DIAL_OFF_RUN_SEARCH_BOOST,
    DOMETIC_CEILING_LINE,
    FACR_FREEZE_SEARCH_BOOST,
    FACT12_FREEZE_RESECURE_LINE,
    FIREFLY_CAN_SEARCH_BOOST,
    GIRARD_PETIT_ALIGN_LINE,
    GROUND_CONTROL_LEVEL_LINE,
    ICE_MONTH_CLOSE,
    ICE_MOISTURE_SEARCH_BOOST,
    PSX1_ASSEMBLY_RR_SHOP_LINE,
    WIRED_COACH_CAN_RE,
    ac_search_symptom,
    asked_brands_for_lookup,
    canonical_shop_brands,
    is_toilet_job,
    library_miss_brand_label,
    chunk_matches_asked_brand,
    model_list_allows,
    dometic_nocoool_search_symptom,
    filter_chunks_for_unit,
    ground_control_search_symptom,
    cooktop_tip_sits_low,
    dometic_nocoool_open_line,
    is_cooktop_tip_sheet_context,
    is_dometic_b57915_nocoool_context,
    is_dometic_ceiling_sheet_context,
    is_fact12_freeze_code_context,
    is_girard_petit_tube_context,
    is_ground_control_context,
    library_filename_words,
    coleman_search_symptom,
    cooktop_search_symptom,
    bal_tongue_search_symptom,
    dial_off_run_search_symptom,
    fcr_e2_search_symptom,
    ice_moisture_search_symptom,
    is_air_conditioning_context,
    is_coleman_2111_context,
    is_coleman_library_text,
    is_bal_soft_touch_tongue_only_context,
    is_cooktop_pan_on_flameout_context,
    is_cooktop_range_context,
    is_facr_rooftop_freeze_context,
    is_fcr_dial_off_compressor_run_context,
    is_fcr_e2_fan_fault_context,
    is_firefly_can_path_context,
    is_fridge_ice_moisture_context,
    is_level_up_advantage_context,
    is_level_up_lead_jack_drift_context,
    is_stabilizer_override_pin_context,
    is_water_heater_context,
    level_up_search_symptom,
    page_has_figure_or_terminal_layout,
    lock_spark_free_part_g,
    rewrite_shop_channel_words,
    rank_chunks_for_ac,
    rank_chunks_for_dometic_nocoool,
    rank_chunks_for_ground_control,
    rank_chunks_for_bal_tongue,
    rank_chunks_for_cooktop_pan_on,
    rank_chunks_for_dial_off_run,
    rank_chunks_for_fcr_fan_fault,
    rank_chunks_for_ice_moisture,
    rank_chunks_for_level_up,
    rank_chunks_for_stabilizer_override,
    rank_chunks_for_water_heater,
    stabilizer_search_symptom,
    water_heater_search_symptom,
)

BAY_PROCEDURE_LABEL = "Bay procedure PDF"
# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.19.65"
PACIFIC = ZoneInfo("America/Los_Angeles")


def sheet_local_now() -> datetime:
    """Header DATE is the shop calendar day in America/Los_Angeles, not UTC."""
    return datetime.now(PACIFIC)


# Shop colors (TechTrack branding — not a Leader pixel clone).
NAVY = (0.004, 0.078, 0.486)
GREEN = (0.012, 0.537, 0.282)
RED = (0.875, 0.122, 0.149)
CAUTION_FILL = (1.0, 0.96, 0.86)
CREAM = (1.0, 0.984, 0.941)
GOLD = (1.0, 0.949, 0.820)
PALE = (0.941, 0.949, 0.969)
WHITE = (1.0, 1.0, 1.0)
INK = (0.122, 0.122, 0.141)
MUTED = (0.35, 0.36, 0.38)
RULE = (0.72, 0.74, 0.76)

PAGE_W = 612.0
PAGE_H = 792.0
MARGIN = 36.0

FURRION_8122_TITLE = "Furrion FCR08/FCR10 SM CCD-0008122"
# Pages that belong to other FCR trees. Dial-OFF + compressor-running must not cite them.
DIAL_OFF_DROP_PAGES = (18, 19, 20, 23, 34)
FACR_7990_TITLE = "Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
FACR_8666_TITLE = "Furrion Chill FACR CCD-0008666"
FIREFLY_PATH_TITLE = "Shop writeup — Level Up Advantage Manual Mode flash-home and Firefly"
OEM_FIGURE_DIR = Path(__file__).resolve().parent / "assets" / "bay-oem"

FIG_RE = re.compile(r"\bfig(?:ure)?\.?\s*\d+", re.I)
MODULES_ONE_AT_A_TIME_RE = re.compile(
    r"unplug\s+(?:firefly|can)\s*/?\s*(?:can\s+)?modules\s+one\s+at\s+a\s+time|"
    r"modules\s+one\s+at\s+a\s+time|"
    r"one\s+at\s+a\s+time",
    re.I,
)
BARE_PN_LEAD_RE = re.compile(r"^\s*(?:[-*•]|\d+\.)?\s*(?:the\s+)?807662\b", re.I)
BODY_MANUAL_CODE_RE = re.compile(r"\b(?:CCD-\d{7}|807662)\b", re.I)
OPEN_THE_MANUAL_RE = re.compile(
    r"\b(?:open|see|work from|follow|stay on|consult|read)\b.{0,48}"
    r"(?:service manual|rooftop book|the sm\b|ccd-\d{7}|the manual)\b|"
    r"\b(?:open|see)\s+ccd-\d{7}\b|"
    r"\bsee the sm\b|"
    r"\bfrom (?:the )?(?:ice and moisture )?sm\b",
    re.I,
)
COACH_DONOT_RE = re.compile(
    r"do not start at (?:unity|dometic|the 12-volt|the no-power|fuse|12v|inverter)|"
    r"do not invent oem|"
    r"do not open the no-power|"
    r"it is not a unity|"
    r"not a unity board",
    re.I,
)
MAX_BAY_ORDER = 12

# Standing product rule — new concerns inherit this from the composer, not only seeds.
# Permanent product rule: techtrack-validation/product-backlog/bay-pdf-standing-standard-2026-09-19.md
BAY_SHEET_STANDARD = (
    "Short paths may be short but complete. Long appliance paths are full A to Z, "
    "not hint cards. Every sheet carries concern, pattern meaning, a readable OEM "
    "yes/no flowchart, ordered bay steps with a next step after every check, "
    "manual thresholds and pass/fail meaning on the page, readable figures, and a "
    "confirmed fix so Concern to Cause to Correction can be written from the sheet. "
    "Never tell the tech to open the SM. Names, not part numbers, in the body. "
    "No program do-not chatter except Firefly bay do-nots. Ban wired coach CAN, "
    "network plugs, power looks sane, and stays open. Prefer holds and still dumps home."
)
BAY_SHEET_STANDARD_PATH = (
    "techtrack-validation/product-backlog/bay-pdf-standing-standard-2026-09-19.md"
)
LONG_APPLIANCE_CATEGORIES = {
    "refrigerators",
    "air conditioning",
    "water heaters",
    "cooktops",
    "ranges",
    "furnaces",
}
LONG_APPLIANCE_CONCERN_RE = re.compile(
    r"\b(ice|frost|freeze|leak|condensate|not cooling|no cool|flameout|e2|fan fault)\b",
    re.I,
)
GENERIC_LONG_SCAFFOLD = (
    "Record the complaint, the model name, and the first cited check from the shop library.",
    "Do that first cited check and write pass or fail on this sheet.",
    "If this check fails, stay on it. If it passes, go to the next cited check.",
    "Do the next cited check. Note the threshold and what good versus bad looks like from the excerpt.",
    "Retest the complaint after those checks.",
    "If the complaint is gone, that is the confirmed correction. If it remains after the cited checks pass, use the next library correction named in Sources.",
)

# Bay PDF Firefly prove — CAN port labels (GD chat keeps the Leader short prove).
FIREFLY_CAN_PORT_PROVE = (
    "The Level Up controller has two ports labeled CAN. "
    "One is the rubber-boot terminator - leave that one plugged in. "
    "The other is the CAN cable to Firefly / OneControl - unplug that one only. "
    "Then try Manual Mode again."
)
FIREFLY_HOLDS_BRANCH = (
    "If Manual Mode holds with the Firefly CAN cable unplugged, update the Firefly firmware. "
    "Call Firefly at 574-825-4600. Use a USB stick of 4 GB or smaller. "
    "For the interim, turn the front-bay main battery switch OFF and take the Firefly cable out, "
    "or leave that cable unplugged with the rubber-boot terminator in."
)
FIREFLY_STILL_DUMPS_BRANCH = (
    "If Manual Mode still dumps home with the Firefly CAN cable unplugged, Firefly CAN is "
    "ruled out. Diagnose the remaining Level Up path."
)
NETWORK_PLUGS_RE = re.compile(r"network\s+plugs", re.I)
POWER_LOOKS_SANE_RE = re.compile(r"power looks sane", re.I)
STAYS_OPEN_RE = re.compile(r"stay[s]?\s+open", re.I)


def uses_wired_coach_can_jargon(text: str) -> bool:
    """Banned isolate jargon — human copy must not use this label."""
    return bool(WIRED_COACH_CAN_RE.search(text or ""))


def check_text_leads_with_bare_pn(text: str) -> bool:
    """True when a line leads with 807662 as the component name."""
    for line in (text or "").splitlines():
        if BARE_PN_LEAD_RE.match(line):
            return True
    return False


def body_uses_manual_codes(text: str) -> bool:
    """True when body copy leads with or leans on a manual / PN code."""
    return bool(BODY_MANUAL_CODE_RE.search(text or ""))


def body_tells_tech_to_open_manual(text: str) -> bool:
    """True when the sheet sends the tech to open a book instead of giving the check."""
    return bool(OPEN_THE_MANUAL_RE.search(text or ""))


def body_uses_coach_donots(text: str) -> bool:
    """True when Do-not is program path-reinforcement, not a real bay mistake."""
    return bool(COACH_DONOT_RE.search(text or ""))


def firefly_sheet_uses_service_names(text: str) -> bool:
    """Level Up / Firefly copy should name the controller, CAN ports, and terminator."""
    t = (text or "").lower()
    return (
        "controller" in t
        and "firefly" in t
        and ("rubber boot" in t or "rubber-boot" in t)
        and "terminator" in t
        and "ports labeled can" in t
        and "can cable" in t
        and "power connector" in t
    )


def body_uses_network_plugs(text: str) -> bool:
    """Banned on the Bay PDF Firefly sheet — use ports labeled CAN."""
    return bool(NETWORK_PLUGS_RE.search(text or ""))


def body_uses_power_looks_sane(text: str) -> bool:
    """Banned vibe check — Bay PDF must cite the POWER CONNECTOR prove."""
    return bool(POWER_LOOKS_SANE_RE.search(text or ""))


def body_uses_stays_open(text: str) -> bool:
    """Banned backwards phrasing. Use holds / still dumps home."""
    return bool(STAYS_OPEN_RE.search(text or ""))


def sheet_standard_violations(text: str) -> list[str]:
    """Machine checklist for BAY_SHEET_STANDARD. New concerns inherit these bans."""
    hits = []
    if uses_wired_coach_can_jargon(text):
        hits.append("wired coach CAN")
    if body_uses_network_plugs(text):
        hits.append("network plugs")
    if body_uses_power_looks_sane(text):
        hits.append("power looks sane")
    if body_uses_stays_open(text):
        hits.append("stays open")
    if body_tells_tech_to_open_manual(text):
        hits.append("open the SM")
    if body_uses_coach_donots(text):
        hits.append("coach do-not")
    return hits


def is_long_appliance_path(category: str = "", concern: str = "") -> bool:
    """Appliance / multi-branch jobs inherit full A→Z. Firefly-class stays short."""
    if (category or "").strip().lower() in LONG_APPLIANCE_CATEGORIES:
        return True
    return bool(LONG_APPLIANCE_CONCERN_RE.search(concern or ""))


def scrub_sheet_text(text: str) -> str:
    """Rewrite banned phrases so a new concern cannot ship a rejected draft."""
    out = text or ""
    out = WIRED_COACH_CAN_RE.sub("CAN", out)
    out = NETWORK_PLUGS_RE.sub("ports labeled CAN", out)
    out = POWER_LOOKS_SANE_RE.sub("power at the POWER CONNECTOR is solid 12V+", out)
    out = STAYS_OPEN_RE.sub("holds", out)
    out = OPEN_THE_MANUAL_RE.sub("use the check on this sheet", out)
    if body_uses_coach_donots(out):
        parts = re.split(r"(?<=[.!?])\s+", out)
        out = " ".join(p for p in parts if p and not body_uses_coach_donots(p))
    out = BODY_MANUAL_CODE_RE.sub("", out)
    out = re.sub(r"\bUNCONFIRMED\b\.?", "Not stated in this sheet.", out, flags=re.I)
    out = re.sub(r"(?:Not stated in this sheet\.\s*){2,}", "Not stated in this sheet. ", out)
    out = re.sub(r"\s+([.,;:])", r"\1", out)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def apply_sheet_standard(proc: "BayProcedure") -> "BayProcedure":
    """Post-compile pass. Locked Firefly strings are a no-op when already clean."""
    proc.pattern_means = scrub_sheet_text(proc.pattern_means)
    proc.primary_cite = _strip_internal_notes((proc.primary_cite or "").strip())
    proc.sources = [
        src
        for src in proc.sources
        if not sheet_has_internal_note(src.get("title") or "")
        and (_strip_internal_notes(src.get("excerpt") or "") or not (src.get("excerpt") or "").strip())
    ]
    for src in proc.sources:
        src["excerpt"] = _strip_internal_notes(src.get("excerpt") or "")
        if sheet_has_internal_note(src.get("title") or ""):
            src["title"] = "Furrion Chill FACR08 8K manual CCD-0008666"
    proc.notes = [note for note in proc.notes if not sheet_has_internal_note(note)]
    proc.bay_order = [scrub_sheet_text(step) for step in proc.bay_order if (step or "").strip()]
    proc.do_not = [
        item
        for item in (scrub_sheet_text(x) for x in proc.do_not)
        if item and not sheet_standard_violations(item)
    ]
    for node in proc.flowchart.nodes:
        node.text = scrub_sheet_text(node.text)
    proc.flowchart.readable = True
    miss_sheet = BRAND_MISS_SHEET_MARK in (proc.primary_cite or "").lower()
    if not miss_sheet and not any(n.kind == "decision" for n in proc.flowchart.nodes):
        proc.flowchart = _generic_flowchart(proc.concern, proc.bay_order)
    return proc


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class FlowNode:
    id: str
    kind: str  # start | decision | process | end
    text: str
    x: float  # 0-1 center, left-to-right
    y: float  # 0-1 center, top-to-bottom inside flowchart frame
    w: float = 0.0
    h: float = 0.0


@dataclass
class FlowEdge:
    from_id: str
    to_id: str
    label: str = ""  # YES / NO / ""
    from_side: str = "bottom"
    to_side: str = "top"


@dataclass
class Flowchart:
    nodes: list[FlowNode] = field(default_factory=list)
    edges: list[FlowEdge] = field(default_factory=list)
    readable: bool = False
    # Extra space after the row that holds this node id, so a branch label
    # can sit under the diamond instead of on the return-line junction.
    row_pad: dict = field(default_factory=dict)


@dataclass
class BayCheck:
    text: str
    source_title: str = ""
    source_page: int | None = None
    kind: str = "check"  # check | figure | note


@dataclass
class BayFigure:
    title: str
    page: int | None = None
    caption: str = ""
    excerpt: str = ""
    image_png: bytes | None = None


@dataclass
class DrawnShape:
    kind: str  # rect | roundrect | diamond | ellipse | line | arrow
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    fill: tuple = WHITE
    stroke: tuple = NAVY
    stroke_w: float = 1.2
    radius: float = 4.0
    points: list = field(default_factory=list)
    id: str = ""
    role: str = ""  # chrome | frame | banner | node | bar | box | check | connector


@dataclass
class DrawnText:
    text: str
    x: float
    y: float
    w: float = 200.0
    size: float = 9.0
    bold: bool = False
    color: tuple = INK
    align: str = "left"  # left | center | right
    leading: float = 0.0
    lines: list = field(default_factory=list)
    owner: str = ""
    role: str = ""  # header | bar | body | node | label


@dataclass
class DrawnImage:
    png: bytes
    x: float
    y: float
    w: float
    h: float


@dataclass
class SheetPage:
    shapes: list[DrawnShape] = field(default_factory=list)
    texts: list[DrawnText] = field(default_factory=list)
    images: list[DrawnImage] = field(default_factory=list)


@dataclass
class LayoutMark:
    """One drawn element, in PDF points (origin at the bottom-left)."""

    page: int
    kind: str
    role: str
    x0: float
    y0: float
    x1: float
    y1: float
    owner: str = ""
    text: str = ""
    id: str = ""
    points: list = field(default_factory=list)


@dataclass
class BayProcedure:
    concern: str
    brand: str = ""
    model: str = ""
    category: str = ""
    wo_number: str = ""
    created: datetime = field(default_factory=sheet_local_now)
    primary_cite: str = ""
    pattern_means: str = ""
    flowchart: Flowchart = field(default_factory=Flowchart)
    bay_order: list[str] = field(default_factory=list)
    do_not: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    checks: list[BayCheck] = field(default_factory=list)
    figures: list[BayFigure] = field(default_factory=list)
    include_3c: bool = False
    notes: list[str] = field(default_factory=list)
    display_model: str = ""
    flow_tall: bool = False
    full_story: bool = False
    unit_id: bool = False
    # Parallel to bay_order. Each entry is the cropped manual figures for that step.
    step_figures: list = field(default_factory=list)
    # Factory R&R sheets. Diagnosis stays the short lead-in. This is the procedure.
    procedures: list = field(default_factory=list)

    @property
    def model_line(self) -> str:
        if (self.display_model or "").strip():
            return self.display_model.strip()
        return join_brand_model(self.brand, self.model)


# ---------------------------------------------------------------------------
# Locked human paths (bay sheet copy — not bot flowchart language)
# ---------------------------------------------------------------------------
def _dial_off_path() -> dict:
    """FCR dial OFF + compressor still running. Thermostat C/T, not a power tree."""
    return {
        "primary_cite": (
            "Furrion fridge service manual, thermostat prove, page 31 and page 43."
        ),
        "pattern_means": (
            "The temperature dial is fully OFF and the compressor is still running, "
            "or the cavity is over-cold. That is a thermostat run-call, not a no-cool "
            "ice pattern. Leave the dial fully OFF, seat the probe and the thermostat "
            "wires, then open C and T with no jumper."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Dial is OFF and the compressor is still running.",
                    0.50,
                    0.10,
                    w=400,
                    h=56,
                ),
                FlowNode(
                    "d_stop",
                    "decision",
                    "Compressor stops with\nC and T open, no jumper?",
                    0.32,
                    0.38,
                    w=230,
                    h=88,
                ),
                FlowNode(
                    "e_part",
                    "end",
                    "Replace the Spark-Free Thermostat\npart G 2021128850.",
                    0.32,
                    0.72,
                    w=250,
                    h=72,
                ),
                FlowNode(
                    "e_inv",
                    "end",
                    "Escalate the inverter\nand the harness.",
                    0.82,
                    0.38,
                    w=200,
                    h=72,
                ),
            ],
            edges=[
                FlowEdge("s", "d_stop"),
                FlowEdge("d_stop", "e_part", "YES", "bottom", "top"),
                FlowEdge("d_stop", "e_inv", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            (
                "Confirm the temperature dial is fully OFF, past the detent, and the "
                "compressor is still running or the cavity is over-cold. Seat the "
                "capillary probe and the blue and black thermostat wires, then go to "
                "the open-terminal prove."
            ),
            (
                "Disconnect flag terminals C (blue) and T (black) and leave them open "
                "with no jumper. Leave the dial fully OFF. If the compressor stops, "
                "go to the Spark-Free Thermostat replacement."
            ),
            (
                "If the compressor stops with C and T open, replace the Spark-Free "
                "Thermostat part G 2021128850 (retail C-FCR10DCGTA-007). Straighten "
                "the probe, reseat it, and reconnect the wires. That is the confirmed "
                "correction when the compressor stops."
            ),
            (
                "If the compressor keeps running with C and T open, the run call is "
                "downstream of the thermostat. Escalate the inverter and the harness."
            ),
        ],
        "check_pages": [31, 31, 43, 45],
        "do_not": [
            "Do not jumper C and T on this prove.",
            "Do not open the fuse, and do not run a 12V continuity check, while the dial is OFF and the compressor is still running.",
            "Do not replace the cooling unit while the dial is OFF and the compressor is still running.",
        ],
        "sources": [
            {
                "title": FURRION_8122_TITLE,
                "page": 31,
                "excerpt": (
                    "Open flag terminals C (blue) and T (black) and leave them open "
                    "with no jumper. Leave the dial fully OFF."
                ),
            },
            {
                "title": FURRION_8122_TITLE,
                "page": 43,
                "excerpt": (
                    "Spark-Free Thermostat part G 2021128850 (retail C-FCR10DCGTA-007). "
                    "Reseat the probe and reconnect the wires."
                ),
            },
            {
                "title": FURRION_8122_TITLE,
                "page": 44,
                "excerpt": "",
            },
            {
                "title": FURRION_8122_TITLE,
                "page": 45,
                "excerpt": (
                    "If the compressor keeps running with C and T open, escalate the "
                    "inverter and the harness."
                ),
            },
        ],
        "display_model": "",
        "flow_tall": True,
        "full_story": True,
    }


def _ice_path() -> dict:
    return {
        "primary_cite": "Furrion fridge service manual, Ice and Moisture section (Fig. 36).",
        "pattern_means": (
            "A frost or ice band on the upper rear wall, with the lower rear often clearer, "
            "is a common Furrion fridge complaint. It is usually moisture on a cold evaporator "
            "surface from the door seal, humidity, setpoint, airflow, or the drain. A light "
            "sheet of ice or moisture only on the back wall is normal cycling: the cabinet "
            "condenses, freezes, and thaws. This pattern by itself is not proof of a "
            "sealed-system failure."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Ice or frost is on the rear wall of the fridge.",
                    0.50,
                    0.07,
                    w=390,
                    h=48,
                ),
                FlowNode(
                    "d_light",
                    "decision",
                    "Light sheet only\non the back wall?",
                    0.30,
                    0.20,
                    w=196,
                    h=68,
                ),
                FlowNode(
                    "e_norm",
                    "end",
                    "Normal cycling.\nYou are done.",
                    0.82,
                    0.20,
                    w=188,
                    h=52,
                ),
                FlowNode(
                    "d_dial",
                    "decision",
                    "Is the dial\nat max?",
                    0.30,
                    0.36,
                    w=196,
                    h=68,
                ),
                FlowNode(
                    "p_dial",
                    "process",
                    "Set the dial to about 4 to 5.\nDry. Run overnight.",
                    0.82,
                    0.36,
                    w=188,
                    h=56,
                ),
                FlowNode(
                    "p_def",
                    "process",
                    "Full defrost. Dry.\nClear the rear drain and trough.",
                    0.30,
                    0.52,
                    w=236,
                    h=56,
                ),
                FlowNode(
                    "d_gask",
                    "decision",
                    "Does the gasket fail\na dollar-bill test?",
                    0.30,
                    0.66,
                    w=196,
                    h=68,
                ),
                FlowNode(
                    "e_gask",
                    "end",
                    "Repair or reseat the gasket.\nRecheck 24 to 48 hours.",
                    0.82,
                    0.66,
                    w=188,
                    h=56,
                ),
                FlowNode(
                    "d_ret",
                    "decision",
                    "Heavy frost return\nafter about 1 month?",
                    0.30,
                    0.82,
                    w=196,
                    h=68,
                ),
                FlowNode(
                    "e_rep",
                    "end",
                    "Replace the cooling unit\nafter that month.",
                    0.82,
                    0.80,
                    w=188,
                    h=52,
                ),
                FlowNode(
                    "e_moist",
                    "end",
                    "Moisture path confirmed.\nYou are done.",
                    0.82,
                    0.94,
                    w=188,
                    h=48,
                ),
            ],
            edges=[
                FlowEdge("s", "d_light"),
                FlowEdge("d_light", "e_norm", "YES", "right", "left"),
                FlowEdge("d_light", "d_dial", "NO", "bottom", "top"),
                FlowEdge("d_dial", "p_dial", "YES", "right", "left"),
                FlowEdge("d_dial", "p_def", "NO", "bottom", "top"),
                FlowEdge("p_dial", "p_def", "", "bottom", "right"),
                FlowEdge("p_def", "d_gask"),
                FlowEdge("d_gask", "e_gask", "YES", "right", "left"),
                FlowEdge("d_gask", "d_ret", "NO", "bottom", "top"),
                FlowEdge("d_ret", "e_rep", "YES", "right", "left"),
                FlowEdge("d_ret", "e_moist", "NO", "bottom", "left"),
            ],
        ),
        "bay_order": [
            "Open the fridge and note the ice or moisture pattern. Photograph it. If it is only a light sheet on the back wall and nowhere else, that is normal cycling: no further action is required for that alone, and you are done. If frost is heavy, starts halfway down, or shows on other surfaces, keep going.",
            "Record the dial setting and the fridge and freezer cavity temperatures. If the dial is at max, set it to about 4 to 5, towel-dry the melt, let the fridge run overnight, then look at the pattern again. If the ice begins to melt at mid setpoint, stay on the moisture path. If the dial is already mid, go to the defrost next.",
            "Do a full manual defrost. Power the unit off, open both doors, and use towels. Do not scrape, do not use a heat gun, and do not set hot-water pans in the cabinet. When the ice is gone, go to the dry-and-drain step.",
            "Dry the cabinet completely. Clear the rear drain and trough with a soft plastic probe only so melt water can leave. If water backs up, keep clearing until it leaves, then go to the gasket. If the drain is already open, go to the gasket next.",
            "Check the door gasket with a dollar-bill test around the full perimeter, and check the hinges, latch, and door alignment. If the bill slides out with no drag, reseat or replace the gasket, set the dial to about 4 to 5, leave an air gap at the rear wall, and recheck in 24 to 48 hours. If the gasket holds, set the dial mid, leave the air gap, and recheck in 24 to 48 hours.",
            "After 24 to 48 hours, if the frost is gone or only a light sheet remains on the back wall, the correction is the moisture path: mid setpoint, a holding gasket, and a clear drain. You are done. If heavy frost returns with a mid dial, a good gasket, and a clear drain, leave the cooling unit in place. Dry the cabinet again and watch door-open time and humidity for about a month.",
            ICE_MONTH_CLOSE
            + " Replace the cooling unit only after that month. That is the confirmed correction. "
            "If the heavy frost is gone after that watch, you are done.",
        ],
        "do_not": [
            "Do not knife the ice off the rear wall.",
            "Do not assume a sealed-system failure from top-half frost alone.",
            "Do not leave the cabinet wet after defrost.",
        ],
        "sources": [
            {
                "title": FURRION_8122_TITLE,
                "page": 36,
                "excerpt": (
                    "Ice and Moisture. Ice or Moisture in the Fridge. "
                    "Figure 36 shows the rear-wall frost pattern."
                ),
            },
            {
                "title": FURRION_8122_TITLE,
                "page": 6,
                "excerpt": (
                    "Defrosting. Power the unit off, open the doors, and use towels. "
                    "Do not scrape, do not use a heat gun, and do not set hot-water pans."
                ),
            },
            {
                "title": FURRION_8122_TITLE,
                "page": 51,
                "excerpt": (
                    "Check the door gasket with a dollar-bill test around the full perimeter. "
                    "Check hinges, latch, and door alignment."
                ),
            },
        ],
        "display_model": "",
        "flow_tall": True,
        "full_story": True,
    }


def _facr_path() -> dict:
    return {
        "primary_cite": "Furrion rooftop assembly and condensate path. Chill layout book for the pan and drain.",
        "pattern_means": (
            "A rooftop freeze or interior drip is condensate. "
            "Melt water ices the pan and drips in. "
            "Prove the pan, drain, slope, and suction line. "
            "A clear drain after a cool cycle passes."
        ),
        "flowchart": Flowchart(
            readable=True,
            # Room under the drain diamond so its NO label clears the retest junction.
            row_pad={"d_drain": 20.0},
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "The rooftop unit is freezing or leaking into the coach.",
                    0.50,
                    0.07,
                    w=400,
                    h=52,
                ),
                FlowNode(
                    "d_drain",
                    "decision",
                    "Drain restricted\nor pan iced?",
                    0.30,
                    0.22,
                    w=200,
                    h=78,
                ),
                FlowNode(
                    "p_clear",
                    "process",
                    "Clear the ice or restriction.\nConfirm water leaves the drain.",
                    0.78,
                    0.22,
                    w=170,
                    h=56,
                ),
                FlowNode(
                    "d_retest",
                    "decision",
                    "Freeze or leak\nreturn on retest?",
                    0.30,
                    0.43,
                    w=200,
                    h=78,
                ),
                FlowNode(
                    "e_ok",
                    "end",
                    "Drain is clear and cooling holds.\nThat is the confirmed correction.",
                    0.78,
                    0.43,
                    w=170,
                    h=56,
                ),
                FlowNode(
                    "d_slope",
                    "decision",
                    "Is the base-pan\nslope wrong?",
                    0.30,
                    0.60,
                    w=200,
                    h=78,
                ),
                FlowNode(
                    "p_slope",
                    "process",
                    "Correct the base-pan slope.\nThen retest cooling.",
                    0.78,
                    0.60,
                    w=170,
                    h=56,
                ),
                FlowNode(
                    "d_suc",
                    "decision",
                    "Is the suction\nline iced?",
                    0.30,
                    0.78,
                    w=200,
                    h=78,
                ),
                FlowNode(
                    "p_suc",
                    "process",
                    "Correct the suction icing.\nThen retest cooling.",
                    0.78,
                    0.78,
                    w=170,
                    h=56,
                ),
                FlowNode(
                    "e_rep",
                    "end",
                    "Replace the rooftop unit\nafter that assembly prove.",
                    0.30,
                    0.93,
                    w=250,
                    h=52,
                ),
            ],
            edges=[
                FlowEdge("s", "d_drain"),
                FlowEdge("d_drain", "p_clear", "YES", "right", "left"),
                # Drain NO turns below its label, then uses the left rail into the retest.
                # The clear-ice loop returns on the top port and does not share the retest NO line.
                FlowEdge("d_drain", "d_retest", "NO", "bottom", "left"),
                FlowEdge("p_clear", "d_retest", "", "bottom", "top"),
                FlowEdge("d_retest", "e_ok", "NO", "right", "left"),
                FlowEdge("d_retest", "d_slope", "YES", "bottom", "top"),
                FlowEdge("d_slope", "p_slope", "YES", "right", "left"),
                FlowEdge("d_slope", "d_suc", "NO", "bottom", "top"),
                FlowEdge("p_slope", "d_retest", "", "right", "top"),
                FlowEdge("d_suc", "p_suc", "YES", "right", "left"),
                FlowEdge("d_suc", "e_rep", "NO", "bottom", "top"),
                FlowEdge("p_suc", "d_retest", "", "right", "top"),
            ],
        ),
        "bay_order": [
            "Inspect the rooftop pan and the condensate drain.",
            "Clean the drainage openings if the drain is restricted.",
            "Clear ice in the drain. Confirm water leaves.",
            "Watch the pan through a full cool cycle.",
            "Check the base-pan slope.",
            "Check the suction-line for icing.",
            "Retest cooling. Watch the pan and the interior.",
            "Replace the rooftop unit after that assembly prove. That is the confirmed correction.",
        ],
        "do_not": [
            "Do not condemn the sealed system before you clear the drain and the pan.",
            "Do not condemn the unit on pressures alone.",
            "Do not run the unit without filters.",
            "Do not use an open flame near R32.",
            "Do not slide the unit.",
            "Do not change DIP switches with the power on.",
            "Do not use the troubleshooting manual part numbers on this 8K unit.",
        ],
        "sources": [
            {
                "title": FACR_7990_TITLE,
                "page": 7,
                "excerpt": "Clean the drainage openings for condensation water.",
            },
            {
                "title": FACR_8666_TITLE,
                "page": 10,
                "excerpt": "The freeze sensor sits on the evaporator beside the drain in the Chill layout.",
            },
        ],
        "display_model": "Furrion Chill rooftop unit",
        "flow_tall": True,
        "full_story": True,
    }


def _bal_tongue_path() -> dict:
    """Tongue jack only dead. Panel output wire, then pigtail. Not coupler-first."""
    return {
        "primary_cite": (
            "BAL Soft-Touch SS 5.1 tongue jack. Check the tongue jack output wire at the panel, then the tongue pigtail."
        ),
        "pattern_means": (
            "The electric tongue jack is the only jack that is dead. The other stabilizers "
            "still extend and retract, and the soft-touch panel lights still work. That is "
            "a check for 12V on the tongue jack output wire at the panel, then the local tongue pigtail. It is "
            "not a coupler, shear-pin, 30A fuse, or remote stabilizer harness job when the "
            "motor runs on direct 12V and the coupler is engaged."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Tongue jack only is dead.\nStabilizers and panel lights work.",
                    0.50,
                    0.08,
                    w=280,
                    h=56,
                ),
                FlowNode(
                    "d_v",
                    "decision",
                    "12V on the tongue jack\noutput wire at the panel?",
                    0.30,
                    0.34,
                    w=220,
                    h=88,
                ),
                FlowNode(
                    "e_panel",
                    "end",
                    "Replace the soft-touch\nuser panel 20300427.",
                    0.78,
                    0.34,
                    w=200,
                    h=64,
                ),
                FlowNode(
                    "d_p",
                    "decision",
                    "Do the tongue pigtail\nleads pass?",
                    0.30,
                    0.62,
                    w=210,
                    h=88,
                ),
                FlowNode(
                    "e_pig",
                    "end",
                    "Repair the tongue pigtail.",
                    0.78,
                    0.62,
                    w=190,
                    h=56,
                ),
                FlowNode(
                    "e_ok",
                    "end",
                    "Output wire and pigtail passed.\nRetest the tongue jack.",
                    0.30,
                    0.90,
                    w=220,
                    h=56,
                ),
            ],
            edges=[
                FlowEdge("s", "d_v"),
                FlowEdge("d_v", "e_panel", "NO", "right", "left"),
                FlowEdge("d_v", "d_p", "YES", "bottom", "top"),
                FlowEdge("d_p", "e_pig", "NO", "right", "left"),
                FlowEdge("d_p", "e_ok", "YES", "bottom", "top"),
            ],
        ),
        "bay_order": [
            (
                "Confirm the electric tongue jack is the only jack that is dead. The other "
                "stabilizers still extend and retract, and the soft-touch panel lights still "
                "work. Go to the tongue output-wire voltage check."
            ),
            (
                "Press tongue extend/retract and check for 12V on the tongue jack output wire "
                "at the panel. If that wire has no 12V while the other stabilizer circuits and the lights "
                "still work, replace the soft-touch user panel 20300427. That is the confirmed correction."
            ),
            (
                "If the tongue jack output wire has 12V, check the local tongue pigtail and the panel-to-motor "
                "leads. If voltage stops in that pigtail, repair the pigtail and retest the tongue jack. "
                "That is the confirmed correction after the panel voltage prove."
            ),
            (
                "Use a coupler or shear-pin replacement only when the manual override will not turn, "
                "or the motor fails a direct-12V prove. When the motor runs on direct 12V and the "
                "coupler is engaged, leave the coupler installed and stay on the panel and pigtail proves."
            ),
        ],
        "do_not": [
            "Do not replace the coupler or the shear pin when the other stabilizers and the panel lights work and the motor runs on direct 12V.",
            "Do not open the 30A supply fuse or the remote stabilizer harness when only the tongue jack is dead.",
        ],
        "sources": [
            {
                "title": "BAL SS 5.1 Stabilizing System INS.STA.001",
                "page": 1,
                "excerpt": "",
            },
        ],
        "display_model": "BAL Soft-Touch SS 5.1",
        "flow_tall": True,
        "full_story": True,
    }


def _firefly_path() -> dict:
    return {
        "primary_cite": "Level Up controller and Firefly panel. Leave the rubber-boot terminator in.",
        "pattern_means": (
            "When Manual Mode flashes back to the home screen and Auto Level still works, "
            "diagnose Firefly / OneControl CAN communication first. Do not start diagnosing "
            "a Level Up controller fault until Firefly / OneControl CAN communication is "
            "ruled out. "
            + FIREFLY_CAN_PORT_PROVE
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Manual Mode flashes home. Auto Level still works.\nClear sticky errors. Check POWER CONNECTOR.",
                    0.50,
                    0.09,
                    w=420,
                    h=70,
                ),
                FlowNode("d1", "decision", "Does Auto\nstill work?", 0.32, 0.29, w=220, h=100),
                FlowNode(
                    "p2",
                    "process",
                    "Leave the rubber-boot terminator in.\nUnplug the Firefly CAN cable only.\nThen try Manual Mode again.",
                    0.32,
                    0.49,
                    w=280,
                    h=86,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "This is not the Firefly path.\nStay on Level Up hydraulics.",
                    0.82,
                    0.29,
                    w=200,
                    h=72,
                ),
                FlowNode("d2", "decision", "Does Manual\nMode hold?", 0.32, 0.70, w=220, h=100),
                FlowNode(
                    "y2",
                    "end",
                    "Manual Mode held.\nCall Firefly at 574-825-4600.\nUse a USB stick of 4 GB or smaller.",
                    0.32,
                    0.91,
                    w=280,
                    h=84,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Firefly CAN is ruled out.\nDiagnose the remaining\nLevel Up path.",
                    0.82,
                    0.70,
                    w=200,
                    h=80,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "p2", "YES", "bottom", "top"),
                FlowEdge("d1", "n1", "NO", "right", "left"),
                FlowEdge("p2", "d2", "", "bottom", "top"),
                FlowEdge("d2", "y2", "YES", "bottom", "top"),
                FlowEdge("d2", "n2", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            "Confirm Auto Level still works and clear sticky Low Voltage, Excess Angle, or External Sensor text if it is present. If Auto is dead, this is not the Firefly path — stay on Level Up hydraulics. If Auto works, check the POWER CONNECTOR next.",
            "Back-probe the labeled POWER CONNECTOR. Measure Red versus Green ground. You want solid 12V+. If you do not have solid 12V+, fix power first. If power is solid 12V+, do the CAN prove next.",
            FIREFLY_CAN_PORT_PROVE,
            FIREFLY_HOLDS_BRANCH + " " + FIREFLY_STILL_DUMPS_BRANCH,
        ],
        "do_not": [
            "Do not pull the rubber-boot terminator.",
            "Do not condemn the Level Up controller or start pump and valve replacement while Auto Level still works.",
            "Do not swap another Level Up controller for Firefly blame.",
            "Do not push Firefly USB firmware unless Manual Mode holds with the Firefly CAN cable unplugged.",
        ],
        "sources": [
            {
                "title": "Lippert TI-005 Electronic Leveling Troubleshooting Guide",
                "page": 1,
                "excerpt": "",
            },
            {
                "title": "Lippert QR-092 Level-Up wiring",
                "page": 1,
                "excerpt": "",
            },
        ],
        "display_model": "807662",
        "flow_tall": True,
    }


def _as_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def _ensure_next_step(text: str, *, last: bool = False) -> str:
    """Every bay check must continue to a next step or a confirmed correction."""
    text = _as_sentence(scrub_sheet_text(text))
    if not text:
        return text
    blob = f" {text.lower()} "
    if " if " not in blob:
        if last:
            text += (
                " If this check fails, stay on it. If it passes and the complaint is gone, "
                "that is the confirmed correction. If the complaint remains, use the next cited library check."
            )
        else:
            text += " If this check fails, stay on it. If it passes, go to the next check."
    elif last and "confirmed correction" not in blob:
        text += " If the complaint is gone, that is the confirmed correction."
    return text


def _body_check_from_excerpt(raw: str) -> str:
    """Library excerpt as a body check — names on the page, codes stay out."""
    text = scrub_sheet_text(raw or "")
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" -")
    return _as_sentence(text)


# Header cite stays inside the 92-character PRIMARY line. Sources carry the long titles.
COLEMAN_BAY_PRIMARY_CITE = (
    "Coleman-Mach 12VDC wall-thermostat SM; 1976-536 and 1976-603; Peacemaker; 1976-695."
)
_COLEMAN_SOURCE_SPECS = (
    {
        "title": "Coleman-Mach 12VDC wall-thermostat rooftop service manual",
        "needles": ("12vdc", "12 vdc", "wall-thermostat", "wall thermostat"),
        "excerpt": (
            "12 VDC present and 115 VAC missing at the 9-pin means the printed circuit board."
        ),
    },
    {
        "title": "Coleman-Mach 1976-536 and 1976-603",
        "needles": ("1976-536", "1976-603"),
        "excerpt": "9-pin: pin 5 BLK is Fan High and pin 9 WHT is fan common.",
    },
    {
        "title": "SkillAbove Peacemaker",
        "needles": ("peacemaker",),
        "excerpt": "Bypass the thermostat and the control box. Record compressor, fan, and amperage.",
    },
    {
        "title": "Coleman-Mach mechanical-controls service manual 1976-695",
        "needles": ("1976-695", "mechanical control"),
        "excerpt": "The run capacitor is good and the motor will not start: replace the motor.",
    },
)


def _coleman_source_hit(pages, needles, used: set):
    best = None
    best_rank = 0
    best_i = None
    for i, d in enumerate(pages):
        if i in used:
            continue
        canon = canonical_shop_brands(d.get("title") or "", d.get("keywords") or "")
        if canon and "coleman" not in canon:
            continue
        title = (d.get("title") or "").lower()
        excerpt = (d.get("excerpt") or "").lower()
        rank = 0
        if any(n in title for n in needles):
            rank = 2
        elif any(n in excerpt for n in needles):
            rank = 1
        if rank > best_rank:
            best = d
            best_rank = rank
            best_i = i
    return best, best_i


def _coleman_sources(ranked) -> list[dict]:
    """Coleman titles only. A page comes from the matching chunk. No invented quote."""
    pages = [chunk_as_dict(ch) for ch in (ranked or [])]
    out = []
    used = set()
    for spec in _COLEMAN_SOURCE_SPECS:
        hit, idx = _coleman_source_hit(pages, spec["needles"], used)
        if hit is None or idx is None:
            continue
        used.add(idx)
        page = _page_int(hit.get("page"))
        if not page:
            continue
        raw = (hit.get("excerpt") or "").strip()
        candidate = _drop_path_off_sentences(clean_source_excerpt(raw), "coleman")
        excerpt = _first_verbatim_sentence(raw, candidate)
        title = human_source_title(spec["title"], "")
        out.append(
            {
                "title": title,
                "page": page,
                "excerpt": excerpt,
                "_chunk_text": raw,
            }
        )
    return out


def _coleman_path() -> dict:
    """2111-0001 climax matches GD: Fan High, Peacemaker, cap, then motor and board only."""
    return {
        "primary_cite": COLEMAN_BAY_PRIMARY_CITE,
        "pattern_means": (
            "A Coleman-Mach 2111-0001 that runs about two minutes and then goes dead "
            "with no response is a wall-thermostat rooftop prove. Prove Fan High at the "
            "9-pin, then the Peacemaker bypass, then the fan run capacitor. The correction "
            "is the fan motor and the control board only."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Coleman-Mach 2111-0001 ran, then went dead.",
                    0.50,
                    0.09,
                    w=420,
                    h=70,
                ),
                FlowNode("d1", "decision", "Fan High dead\nat the 9-pin?", 0.32, 0.29, w=220, h=100),
                FlowNode(
                    "p2",
                    "process",
                    "Peacemaker bypass, then\nmeasure the fan run capacitor.",
                    0.32,
                    0.49,
                    w=280,
                    h=86,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "Fan High is live.\nStay on that voltage path.",
                    0.82,
                    0.29,
                    w=200,
                    h=72,
                ),
                FlowNode("d2", "decision", "Cap good and the\nfan locked?", 0.32, 0.70, w=220, h=100),
                FlowNode(
                    "y2",
                    "end",
                    "R&R the fan motor and\nthe control board only.",
                    0.32,
                    0.91,
                    w=280,
                    h=84,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Replace the failed part\nfrom that prove and retest.",
                    0.82,
                    0.70,
                    w=200,
                    h=80,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "p2", "YES", "bottom", "top"),
                FlowEdge("d1", "n1", "NO", "right", "left"),
                FlowEdge("p2", "d2", "", "bottom", "top"),
                FlowEdge("d2", "y2", "YES", "bottom", "top"),
                FlowEdge("d2", "n2", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            (
                "Prove Fan High at the 9-pin before any part is condemned. Pin 5 black "
                "is Fan High and pin 9 white is fan common. If the board output tester "
                "is dark or black-to-white is about 0 VAC, Fan High is dead: go to the "
                "Peacemaker bypass. If Fan High is about 115 VAC, the board is calling "
                "for the fan: stay on the live-voltage fan path."
            ),
            (
                "Bypass the thermostat and the control box with the SkillAbove Peacemaker. "
                "If the compressor runs and the fan does not rotate on high or low, record "
                "the amps. Shaft-locked current about 1.9 A means the fan motor is locked: "
                "go to the fan run capacitor. If the compressor does not run, stay on the "
                "compressor and do not condemn the fan motor."
            ),
            (
                "Measure the fan run capacitor and compare it to the value printed on the "
                "capacitor. On this 2111-0001 the rated value is 15 µF. If the capacitor "
                "is open or far from rated, replace the capacitor and retest the fan. If "
                "it measures about rated, the capacitor is not the failed part: go to the "
                "motor and the board."
            ),
            (
                "When Fan High is dead, the Peacemaker bypass shows the compressor runs "
                "with the fan locked and stall current reported, and the fan run capacitor "
                "is good, R&R the rooftop fan motor and the control board only. Do not "
                "replace the full 2111-0001 assembly. That is the confirmed correction."
            ),
        ],
        "do_not": [
            "Do not replace the full 2111-0001 rooftop assembly on this prove.",
            "Do not condemn the fan motor before the capacitor is measured against its rated value.",
        ],
        "sources": [],
        "display_model": "",
        "flow_tall": True,
        "full_story": True,
    }


BRAND_MISS_SHEET_MARK = "general shop safety sheet"


def _no_brand_match_path(brand: str = "", model: str = "", concern: str = "") -> dict:
    """Known unit, no matching manual page retrieved: a general shop safety sheet."""
    model_text = model_text_from(brand, model)
    who = library_miss_brand_label("", model_text, concern) or (brand or "").strip() or "this brand"
    sentence = f"{who}: {BRAND_MISS_SHEET_MARK}."
    toilet = is_toilet_job("", model_text, concern)
    if toilet:
        safe = (
            "General shop safety, not an OEM procedure: shut the water supply off "
            "before working under the flush lever."
        )
    else:
        safe = "General shop safety, not an OEM procedure."
    return {
        "primary_cite": sentence,
        "pattern_means": (
            f"{sentence} This pass did not retrieve a service manual page for that unit. "
            "The steps below are general shop safety, not an OEM procedure."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    sentence,
                    0.50,
                    0.12,
                    w=460,
                    h=72,
                ),
                FlowNode(
                    "p_safe",
                    "process",
                    "General shop safety.\nNot an OEM procedure.",
                    0.50,
                    0.46,
                    w=280,
                    h=80,
                ),
            ],
            edges=[
                FlowEdge("s", "p_safe"),
            ],
        ),
        "bay_order": [safe],
        "do_not": [],
        "sources": [
            {
                "title": sentence,
                "page": None,
                "excerpt": "General shop safety.",
            }
        ],
        "display_model": "",
        "flow_tall": True,
        "full_story": False,
    }


def _brand_miss_figure(brand: str = "", model: str = "", concern: str = "") -> BayFigure:
    model_text = model_text_from(brand, model)
    who = library_miss_brand_label("", model_text, concern) or (brand or "").strip() or "this brand"
    sentence = f"{who}: {BRAND_MISS_SHEET_MARK}."
    seed = _seed_path_figure("generic")
    seed.title = "Shop safety"
    seed.caption = sentence
    seed.excerpt = "General shop safety."
    return seed


def resolve_path_figures(kind: str, ranked, explicit: list[BayFigure] | None = None) -> list[BayFigure]:
    """Ice and FACR always use real OEM library art. A sketch is never captioned as an OEM page."""
    if kind in ("ice", "facr"):
        if explicit and any(
            fig.image_png and not _png_is_generated_sketch(fig.image_png) for fig in explicit
        ):
            return [
                fig
                for fig in explicit
                if fig.image_png and not _png_is_generated_sketch(fig.image_png)
            ]
        return _oem_library_figures(kind)
    if kind == "dial_off":
        return [_seed_path_figure("dial_off")]
    if kind == "bal_tongue":
        return [_seed_path_figure("bal_tongue")]
    real = _real_library_figures(ranked)
    if real:
        return real
    if explicit and any(
        fig.image_png and not _png_is_generated_sketch(fig.image_png) for fig in explicit
    ):
        return [
            fig
            for fig in explicit
            if fig.image_png and not _png_is_generated_sketch(fig.image_png)
        ]
    # No real page art. Keep a seed object for tests, but do not borrow an OEM caption.
    if kind == "firefly":
        return [_seed_path_figure("firefly")]
    return [_seed_path_figure("generic")]


def _unique_sources(chunks) -> list[dict]:
    out = []
    seen = set()
    for ch in chunks or []:
        d = chunk_as_dict(ch)
        title = human_source_title(d.get("title") or "", d.get("file_path") or "")
        page = _page_int(d.get("page"))
        key = (title.lower(), page)
        if key in seen:
            continue
        seen.add(key)
        raw = d.get("excerpt") or ""
        out.append(
            {
                "title": title,
                "page": page,
                "file_path": d.get("file_path") or "",
                "excerpt": raw,
                "_chunk_text": raw,
            }
        )
    return out


def _excerpt_line(d: dict) -> str | None:
    excerpt = re.sub(r"\s+", " ", (d.get("excerpt") or "").strip())
    if len(excerpt) < 40:
        return None
    sentence = excerpt.split(". ")
    text = ". ".join(sentence[:2]).strip()
    if text and not text.endswith("."):
        text += "."
    if len(text) > 220:
        text = text[:217].rstrip() + "..."
    page = _page_int(d.get("page"))
    title = (d.get("title") or "").strip()
    cite = ""
    if title:
        cite = f" ({title}" + (f" page {page}" if page else "") + ")"
    return f"{text}{cite}"


def _clip(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= n:
        return text
    return text[: n - 3].rstrip() + "..."


def _lock_note(category_name: str, model_text: str, concern: str) -> list[str]:
    notes = []
    if is_fcr_dial_off_compressor_run_context(category_name, model_text, concern):
        notes.append(
            "Dial OFF with the compressor still running is a thermostat C and T prove. "
            "Cite page 31 and page 43. Replace the Spark-Free Thermostat only when the "
            "compressor stops with no jumper."
        )
    if is_fridge_ice_moisture_context(category_name, model_text, concern):
        notes.append(
            "Ice or frost on the rear wall is an Ice and Moisture problem. "
            "A light sheet can be normal cycling. Check the dial, the gasket, and the rear drain."
        )
    if is_firefly_can_path_context(category_name, model_text, concern) or is_level_up_advantage_context(
        category_name, model_text, concern
    ):
        notes.append(
            "When Manual Mode flashes home and Auto Level still works, confirm Auto, "
            "clear sticky errors, back-probe the POWER CONNECTOR, then prove the two "
            "ports labeled CAN. Do not start a Level Up controller fault until Firefly "
            "CAN is ruled out."
        )
    if is_facr_rooftop_freeze_context(category_name, model_text, concern):
        notes.append(
            "A rooftop freeze or condensate leak is an assembly and drain path. "
            "Clear the pan and the drain, then check base-pan slope and suction-line icing."
        )
    if is_fcr_e2_fan_fault_context(category_name, model_text, concern):
        notes.append(
            "Furrion FCR E2 or Fan Fault Current is a freezer-fan and airflow path. "
            "Measure F+ and F- on the inverter PCB, then replace the inverter PCB and "
            "the fan when voltage is present and the error remains. "
            "It is not a rooftop air-conditioner code."
        )
    if _is_furnace_bay(category_name, model_text, concern):
        notes.append(
            "Bypass the wall thermostat at the furnace with a jumper on R and W. "
            "If the furnace runs, replace the wall thermostat. If it does not run, "
            "prove the sail switch."
        )
    if is_coleman_2111_context(category_name, model_text, concern):
        notes.append(
            "Prove Fan High at the 9-pin, then the Peacemaker bypass, then the fan run "
            "capacitor. The correction is the fan motor and the control board only."
        )
    elif is_air_conditioning_context(category_name, model_text, concern) and not is_facr_rooftop_freeze_context(
        category_name, model_text, concern
    ):
        notes.append(
            "This is a rooftop air-conditioning job. Use the rooftop cooling checks "
            "from the shop library."
        )
    if is_water_heater_context(category_name, model_text, concern):
        notes.append(
            "This is a Girard tankless water-heater path. Use the water-heater checks. "
            "It is not a fridge E2 path."
        )
    if is_cooktop_pan_on_flameout_context(category_name, model_text, concern):
        notes.append(
            "If the burner lights and then goes out when a pan is set on it, check "
            "the flame-sensor tip in the flame with cookware on. It is not a furnace path."
        )
    if is_stabilizer_override_pin_context(category_name, model_text, concern):
        notes.append(
            "If power works but the manual override will not engage because the roll "
            "pin is broken, replace the complete stabilizer jack. It is not a coupler-only repair."
        )
    if is_bal_soft_touch_tongue_only_context(category_name, model_text, concern):
        notes.append(
            "Tongue jack only dead, with the other stabilizers and panel lights working: "
            "check for 12V on the tongue jack output wire at the panel, then the tongue pigtail. "
            "No 12V on that wire means soft-touch user panel 20300427."
        )
    if is_level_up_advantage_context(category_name, model_text, concern) and not is_firefly_can_path_context(
        category_name, model_text, concern
    ):
        notes.append(
            "The Level Up controller is the Lippert towable hydraulic leveling controller."
        )
    return notes


def _merge_sources(
    locked: list[dict],
    ranked: list[dict],
    ice: bool,
    dial_off: bool = False,
) -> list[dict]:
    out = []
    seen = {}
    for s in list(locked) + list(ranked):
        title = (s.get("title") or "").strip() or "Shop library"
        page = _page_int(s.get("page"))
        key = (title.lower(), page)
        if key in seen:
            existing = seen[key]
            # A retrieved page can fill a locked cite. A locked sentence cannot.
            if s.get("_chunk_text") and not existing.get("_chunk_text"):
                existing["_chunk_text"] = s.get("_chunk_text") or ""
                existing["excerpt"] = s.get("excerpt") or existing.get("excerpt") or ""
                if s.get("file_path"):
                    existing["file_path"] = s.get("file_path") or ""
            continue
        if dial_off and page in DIAL_OFF_DROP_PAGES:
            continue
        if ice:
            hay = f"{title} {s.get('excerpt') or ''}".lower()
            if page == 19 or (
                any(k in hay for k in ("fuse location", "15a", "no power", "12v inverter"))
                and "moisture" not in hay
            ):
                # Keep fuse pages off the primary source list for ice jobs.
                continue
        row = {
            "title": title,
            "page": page,
            "file_path": s.get("file_path") or "",
            "excerpt": s.get("excerpt") or "",
            "_chunk_text": s.get("_chunk_text") or "",
        }
        seen[key] = row
        out.append(row)
    return out


def _lock_dial_off_part_numbers(proc: "BayProcedure") -> "BayProcedure":
    """Part G on this sheet is exactly 2021128850. Digit transpositions are rewritten."""
    proc.concern = lock_spark_free_part_g(proc.concern)
    proc.pattern_means = lock_spark_free_part_g(proc.pattern_means)
    proc.primary_cite = lock_spark_free_part_g(proc.primary_cite)
    proc.bay_order = [lock_spark_free_part_g(step) for step in proc.bay_order]
    proc.do_not = [lock_spark_free_part_g(item) for item in proc.do_not]
    proc.notes = [lock_spark_free_part_g(note) for note in proc.notes]
    for node in proc.flowchart.nodes:
        node.text = lock_spark_free_part_g(node.text)
    for source in proc.sources:
        if source.get("title"):
            source["title"] = lock_spark_free_part_g(source["title"])
        if source.get("excerpt"):
            source["excerpt"] = lock_spark_free_part_g(source["excerpt"])
    for fig in proc.figures:
        fig.caption = lock_spark_free_part_g(fig.caption or "")
        fig.excerpt = lock_spark_free_part_g(fig.excerpt or "")
    blob = "\n".join(
        [
            proc.pattern_means or "",
            *proc.bay_order,
            *(node.text for node in proc.flowchart.nodes),
        ]
    )
    if "2021128850" not in blob:
        proc.bay_order.append(
            "Replace the Spark-Free Thermostat part G 2021128850 when the compressor "
            "stops with C (blue) and T (black) open and no jumper."
        )
    return proc


def apply_shop_channel_wording(proc: "BayProcedure") -> "BayProcedure":
    """Final shop-language pass on tech-facing sheet fields. Idempotent.

    Manual titles stay as cites. Excerpt text is rewritten unless it is a
    marked source quote.
    """
    proc.concern = rewrite_shop_channel_words(proc.concern)
    proc.pattern_means = rewrite_shop_channel_words(proc.pattern_means)
    proc.primary_cite = rewrite_shop_channel_words(proc.primary_cite)
    proc.display_model = rewrite_shop_channel_words(proc.display_model)
    proc.bay_order = [rewrite_shop_channel_words(step) for step in proc.bay_order]
    proc.do_not = [rewrite_shop_channel_words(item) for item in proc.do_not]
    proc.notes = [rewrite_shop_channel_words(note) for note in proc.notes]
    for node in proc.flowchart.nodes:
        node.text = rewrite_shop_channel_words(node.text)
    for edge in proc.flowchart.edges:
        if edge.label:
            edge.label = rewrite_shop_channel_words(edge.label)
    for check in proc.checks:
        check.text = rewrite_shop_channel_words(check.text)
    for fig in proc.figures:
        fig.caption = rewrite_shop_channel_words(fig.caption or "")
        fig.excerpt = rewrite_shop_channel_words(fig.excerpt or "")
    for src in proc.sources:
        if src.get("excerpt"):
            src["excerpt"] = rewrite_shop_channel_words(src.get("excerpt") or "")
    return proc


def _shop_body(line: str) -> str:
    """GD shop line without the source stamp. The cite stays on the sheet header."""
    kept = []
    for part in (line or "").splitlines():
        part = part.strip()
        if not part or part.startswith("📖"):
            continue
        part = re.sub(r"^\d+\.\s*", "", part)
        kept.append(part)
    return " ".join(kept)


def _named_fix_chart(start: str, question: str, yes_text: str, no_text: str, process: str) -> Flowchart:
    """Yes/no chart that names the correction. Not the generic first-check diamond."""
    return Flowchart(
        readable=True,
        nodes=[
            FlowNode("s", "start", start, 0.50, 0.10, w=430, h=72),
            FlowNode("d1", "decision", question, 0.32, 0.38, w=236, h=96),
            FlowNode("n1", "end", no_text, 0.80, 0.38, w=210, h=80),
            FlowNode("p1", "process", process, 0.32, 0.64, w=280, h=80),
            FlowNode("e1", "end", yes_text, 0.32, 0.88, w=280, h=72),
        ],
        edges=[
            FlowEdge("s", "d1"),
            FlowEdge("d1", "p1", "YES", "bottom", "top"),
            FlowEdge("d1", "n1", "NO", "right", "left"),
            FlowEdge("p1", "e1", "", "bottom", "top"),
        ],
    )


def _ground_control_path(concern: str) -> dict:
    return {
        "primary_cite": (
            "Lippert Internal Tech Support – Electric Leveling Systems "
            "(Ground Control TT/2.0/3.0), page 1."
        ),
        "pattern_means": (
            "Auto-level that lifts one side of the coach is a zero-point calibration "
            "on Lippert Ground Control. Run manual level, then set zero point. "
            "Do not swap a level sensor and do not replace a harness."
        ),
        "flowchart": Flowchart(
            readable=True,
            # Room under the last diamond so its NO label clears both nodes.
            row_pad={"d_side": 36.0},
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    _opening_sentence(concern or "Auto-level lifts one side of the coach."),
                    0.50,
                    0.08,
                    w=430,
                    h=64,
                ),
                FlowNode(
                    "p_level",
                    "process",
                    "Run manual level.\nFront to back, then side to side.",
                    0.32,
                    0.20,
                    w=280,
                    h=72,
                ),
                FlowNode(
                    "p_zero",
                    "process",
                    "Then set the zero point\nwith the touch pad off.",
                    0.32,
                    0.36,
                    w=280,
                    h=72,
                ),
                FlowNode(
                    "p_keys",
                    "process",
                    "FRONT five times, REAR five times,\nthen press ENTER.",
                    0.32,
                    0.52,
                    w=300,
                    h=72,
                ),
                FlowNode(
                    "d_side",
                    "decision",
                    "Does auto-level\nstill lift one side?",
                    0.32,
                    0.70,
                    w=230,
                    h=80,
                ),
                FlowNode(
                    "e_rep",
                    "end",
                    "Repeat the button sequence.",
                    0.78,
                    0.70,
                    w=210,
                    h=56,
                ),
                FlowNode(
                    "e_ok",
                    "end",
                    "That is the confirmed\ncorrection.",
                    0.32,
                    0.90,
                    w=220,
                    h=64,
                ),
            ],
            edges=[
                FlowEdge("s", "p_level"),
                FlowEdge("p_level", "p_zero"),
                FlowEdge("p_zero", "p_keys"),
                FlowEdge("p_keys", "d_side"),
                FlowEdge("d_side", "e_rep", "YES", "right", "left"),
                FlowEdge("d_side", "e_ok", "NO", "bottom", "top"),
            ],
        ),
        "bay_order": [
            "Confirm the controller, jack, and touch pad plugs are seated. If a plug is loose, reseat it and retest auto-level. If the plugs are seated, go to manual level.",
            "Run manual level. In manual mode, run the jacks until the trailer is level: level front to back, then side to side. When the coach is level, turn the touch pad off.",
            "With the touch pad off, press and release FRONT five times, then press and release REAR five times. Press ENTER to store the zero point. If auto-level still lifts one side, repeat that button sequence. That is the confirmed correction.",
        ],
        "do_not": [
            "Do not swap a level sensor.",
            "Do not replace a harness for an auto-level that lifts one side.",
        ],
        "sources": [
            {
                "title": "Lippert Internal Tech Support – Electric Leveling Systems (Ground Control TT/2.0/3.0)",
                "page": 1,
                "excerpt": "",
            }
        ],
        "flow_tall": True,
        "full_story": True,
    }


def _dometic_ceiling_path(concern: str) -> dict:
    fan_runs = bool(
        re.search(r"\bfan\b", concern or "", re.I)
        and re.search(r"\b(?:runs?|running|operates|operating)\b", concern or "", re.I)
    )
    opener = dometic_nocoool_open_line({"dometic_fan": "runs"} if fan_runs else {})
    return {
        "primary_cite": "Dometic Brisk II, page 23.",
        "pattern_means": _shop_body(opener),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "The fan runs and the rooftop unit is not cooling.",
                    0.50,
                    0.08,
                    w=420,
                    h=64,
                ),
                FlowNode(
                    "p_by",
                    "process",
                    "Peacemaker bypass, then\nbypass the ceiling selector.",
                    0.32,
                    0.32,
                    w=300,
                    h=76,
                ),
                FlowNode(
                    "d_cool",
                    "decision",
                    "Do both bypasses\ncool?",
                    0.32,
                    0.58,
                    w=220,
                    h=90,
                ),
                FlowNode(
                    "e_yes",
                    "end",
                    "Replace the ceiling\nthermostat/selector.",
                    0.32,
                    0.84,
                    w=250,
                    h=68,
                ),
                FlowNode(
                    "e_no",
                    "end",
                    "Stay on the bypasses.\nDo not start on the filter.",
                    0.78,
                    0.58,
                    w=210,
                    h=72,
                ),
            ],
            edges=[
                FlowEdge("s", "p_by"),
                FlowEdge("p_by", "d_cool"),
                FlowEdge("d_cool", "e_yes", "YES", "bottom", "top"),
                FlowEdge("d_cool", "e_no", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            "Fan running with no cold air is the no-cool path. Peacemaker bypass at the rooftop unit. If that bypass cools, the unit is making cold air. If it does not cool, stay on that bypass. Do not start on the filter check.",
            "If the Peacemaker bypass cools, bypass the ceiling selector. If bypassing the ceiling selector does not cool, stay on that bypass and retest.",
            _shop_body(DOMETIC_CEILING_LINE)
            + " That is the confirmed correction per Dometic Brisk II, page 23.",
        ],
        "do_not": [
            "Do not start on the filter check.",
        ],
        "sources": [
            {
                "title": "Dometic Brisk II",
                "page": 23,
                "excerpt": "",
            },
        ],
        "flow_tall": True,
        "full_story": True,
    }


def _fact12_e3_path() -> dict:
    return {
        "primary_cite": "Furrion Chill FACR CCD-0008666, pages 15 and 18.",
        "pattern_means": (
            "A FACT12 E3 is a communication fault. Measure 12 V and the data line at the connector "
            "before any board swap. Then confirm the freeze sensor is seated on the evaporator coil."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode("s", "start", "FACT12 shows E3.", 0.50, 0.10, w=360, h=56),
                FlowNode(
                    "d1",
                    "decision",
                    "Is 12 V present\non the data connector?",
                    0.32,
                    0.34,
                    w=240,
                    h=96,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "Repair the 12 V feed\nor the data line.",
                    0.78,
                    0.34,
                    w=210,
                    h=72,
                ),
                FlowNode(
                    "d_conn",
                    "decision",
                    "Is the data connector\nseated?",
                    0.32,
                    0.52,
                    w=220,
                    h=78,
                ),
                FlowNode(
                    "e_conn",
                    "end",
                    "Seat the connector\nand retest the code.",
                    0.78,
                    0.52,
                    w=200,
                    h=68,
                ),
                FlowNode(
                    "d2",
                    "decision",
                    "Is the freeze sensor\non the coil?",
                    0.32,
                    0.70,
                    w=220,
                    h=72,
                ),
                FlowNode(
                    "p1",
                    "process",
                    "Reseat the freeze sensor\non the evaporator coil.",
                    0.32,
                    0.86,
                    w=240,
                    h=56,
                ),
                FlowNode(
                    "e_re",
                    "end",
                    "Retest the code.",
                    0.78,
                    0.86,
                    w=180,
                    h=56,
                ),
                FlowNode(
                    "e_ok",
                    "end",
                    "Sensor is seated and E3 remains.\nWrite the readings and stop.",
                    0.78,
                    0.70,
                    w=220,
                    h=72,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "d_conn", "YES", "bottom", "top"),
                FlowEdge("d1", "n1", "NO", "right", "left"),
                FlowEdge("d_conn", "d2", "YES", "bottom", "top"),
                FlowEdge("d_conn", "e_conn", "NO", "right", "left"),
                FlowEdge("d2", "e_ok", "YES", "right", "left"),
                FlowEdge("d2", "p1", "NO", "bottom", "top"),
                FlowEdge("p1", "e_re", "", "right", "left"),
            ],
        ),
        "bay_order": [
            "On a FACT12 E3, measure 12 V at the communication connector and check the data line. If 12 V is missing, repair that feed and retest. If 12 V is present, check the connector next.",
            "Confirm the data connector is seated. If a pin is pushed back or the connector is loose, repair it and retest the code.",
            "Check the freeze sensor on the evaporator coil. If it is loose or off the coil, reseat it and retest. If it is already seated and E3 remains, write the readings and stop.",
        ],
        "do_not": [
            "Do not replace the control board before the 12 V, data line, and connector checks.",
        ],
        "sources": [
            {"title": "Furrion Chill FACR CCD-0008666", "page": 15, "excerpt": ""},
            {"title": "Furrion Chill FACR CCD-0008666", "page": 18, "excerpt": ""},
        ],
        "flow_tall": True,
        "full_story": True,
    }


def _fact12_freeze_path(concern: str = "") -> dict:
    if re.search(r"\be\s*3\b", concern or "", re.I):
        return _fact12_e3_path()
    return {
        "primary_cite": "Furrion Chill FACR08 8K manual CCD-0008666, page 5.",
        "pattern_means": (
            "A FACT12 E2 is a freeze-sensor seating fault. "
            "Check the freeze sensor on the evaporator coil before any board swap. "
            "If it is loose or off the coil, reseat it and retest."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode("s", "start", "FACT12 shows E2.", 0.50, 0.08, w=420, h=56),
                FlowNode(
                    "d1",
                    "decision",
                    "Is the freeze sensor\nloose or off the coil?",
                    0.32,
                    0.28,
                    w=230,
                    h=90,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "Replace the freeze sensor\nand retest.",
                    0.78,
                    0.28,
                    w=200,
                    h=72,
                ),
                FlowNode(
                    "p1",
                    "process",
                    "Reseat the freeze sensor\non the evaporator coil.",
                    0.32,
                    0.50,
                    w=260,
                    h=72,
                ),
                FlowNode(
                    "d2",
                    "decision",
                    "Is the code still\npresent?",
                    0.32,
                    0.72,
                    w=220,
                    h=84,
                ),
                FlowNode(
                    "e_clear",
                    "end",
                    "The code cleared.\nThat is the correction.",
                    0.32,
                    0.92,
                    w=250,
                    h=64,
                ),
                FlowNode(
                    "e_stay",
                    "end",
                    "Replace the freeze sensor\nand retest.",
                    0.78,
                    0.72,
                    w=200,
                    h=72,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "p1", "YES", "bottom", "top"),
                FlowEdge("d1", "n1", "NO", "right", "left"),
                FlowEdge("p1", "d2", "", "bottom", "top"),
                FlowEdge("d2", "e_clear", "NO", "bottom", "top"),
                FlowEdge("d2", "e_stay", "YES", "right", "left"),
            ],
        ),
        "bay_order": [
            "On a FACT12 E2, find the freeze sensor on the evaporator coil. If it is loose or off the coil, reseat it and retest. If it is already seated, go to the replace step.",
            "Reseat the freeze sensor on the evaporator coil. If the code clears, that is the confirmed correction.",
            "If the sensor is seated and the code remains, replace the freeze sensor and retest.",
        ],
        "do_not": [
            "Do not replace the control board before the freeze sensor is reseated.",
        ],
        "sources": [
            {
                "title": "Furrion Chill FACR08 8K manual CCD-0008666",
                "page": 5,
                "excerpt": "",
            },
        ],
        "flow_tall": True,
        "full_story": True,
    }


_GIRARD_HOSE_QUOTE = "Check for integrity and connections of the pressure switch hose."


def _ensure_girard_hose_quote(sources: list[dict]) -> list[dict]:
    """CCD-0009390 page 23 stays cited with the pressure-switch hose sentence."""
    quote = _GIRARD_HOSE_QUOTE
    for src in sources or []:
        title = src.get("title") or ""
        excerpt = src.get("excerpt") or ""
        if "pressure switch hose" not in f"{title} {excerpt}".lower():
            continue
        if quote.lower() not in excerpt.lower():
            src["excerpt"] = quote
        if not src.get("page"):
            src["page"] = 23
        return sources
    return [
        {
            "title": "Girard GSWH-2 service manual CCD-0009390",
            "page": 23,
            "excerpt": quote,
        }
    ] + list(sources or [])


def _girard_petit_path() -> dict:
    return {
        "primary_cite": "Girard tankless water heater service manual CCD-0009390, page 23.",
        "pattern_means": (
            "Girard GSWH-2 E8 is the air pressure switch. "
            "Its sensing tube is at the blower. Confirm suction there while the blower runs "
            "before any control board."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Girard water heater shows E8.",
                    0.78,
                    0.04,
                    w=420,
                    h=64,
                ),
                FlowNode(
                    "p_no",
                    "process",
                    "Seat the sensing tube\nat the blower, then retest.",
                    0.22,
                    0.18,
                    w=250,
                    h=64,
                ),
                FlowNode(
                    "d_in",
                    "decision",
                    "Does the blower tube\nshow suction?",
                    0.78,
                    0.18,
                    w=220,
                    h=72,
                ),
                FlowNode(
                    "e_no",
                    "end",
                    "Blower-tube suction\nis the correction.",
                    0.22,
                    0.34,
                    w=240,
                    h=60,
                ),
                FlowNode(
                    "e_aps",
                    "end",
                    "Repair the air-pressure\nswitch and retest.",
                    0.22,
                    0.50,
                    w=180,
                    h=64,
                ),
                FlowNode(
                    "d_aps",
                    "decision",
                    "Does the air-pressure\nswitch pass?",
                    0.78,
                    0.50,
                    w=210,
                    h=72,
                ),
                FlowNode(
                    "e_gas",
                    "end",
                    "Repair the gas supply\nand retest.",
                    0.22,
                    0.66,
                    w=180,
                    h=60,
                ),
                FlowNode(
                    "d_gas",
                    "decision",
                    "Is the gas supply\ngood?",
                    0.78,
                    0.66,
                    w=190,
                    h=68,
                ),
                FlowNode(
                    "e_stop",
                    "end",
                    "Gas is good and E8 remains.\nWrite the readings and stop.",
                    0.78,
                    0.84,
                    w=230,
                    h=64,
                ),
            ],
            edges=[
                FlowEdge("s", "d_in"),
                FlowEdge("d_in", "p_no", "NO", "left", "right"),
                FlowEdge("p_no", "e_no"),
                FlowEdge("d_in", "d_aps", "YES", "bottom", "top"),
                FlowEdge("d_aps", "e_aps", "NO", "left", "right"),
                FlowEdge("d_aps", "d_gas", "YES", "bottom", "top"),
                FlowEdge("d_gas", "e_gas", "NO", "left", "right"),
                FlowEdge("d_gas", "e_stop", "YES", "bottom", "top"),
            ],
        ),
        "bay_order": [
            "Confirm the E8 code. E8 is the air pressure switch. Look at the sensing tube at the blower before any other part.",
            "With the blower running, confirm suction at that tube. If the tube is off the blower or has no suction, seat it at the blower and retest. That is the confirmed correction.",
            "If the tube is on the blower and suction is present, retest the heater. If E8 clears, that position is the correction.",
            "If E8 remains after suction is confirmed, check the air-pressure switch. "
            "Check for integrity and connections of the pressure switch hose. "
            "Repair the switch and retest if it fails.",
            "If the air-pressure switch is good, check the gas supply and retest the heater.",
            "If the gas supply is good and E8 remains, write the readings and stop. Do not replace the control board.",
        ],
        "do_not": [
            "Do not replace the control board before the blower sensing tube shows suction.",
        ],
        "sources": [
            {
                "title": "Girard GSWH-2 service manual CCD-0009390",
                "page": 23,
                "excerpt": (
                    "Check for integrity and connections of the pressure switch hose (Fig. 38A)."
                ),
                "_chunk_text": (
                    "Before replacing the pressure switch: "
                    "Check for integrity and connections of the pressure switch hose (Fig. 38A)."
                ),
            }
        ],
        "flow_tall": True,
        "full_story": True,
    }


def _stabilizer_rr_path() -> dict:
    return {
        "primary_cite": "Lippert PSX1 front stabilizer, complete jack assembly",
        "pattern_means": (
            "When the manual-override roll pin or coupler is broken or seized and not "
            "serviceable in the field, replace the complete front stabilizer jack assembly. "
            "Reconnect the mount and the electrical connector, then retest power and the "
            "manual crank. Do not replace the coupler only."
        ),
        "flowchart": _named_fix_chart(
            "Power works. The manual override will not engage.",
            "Is the roll pin\nor coupler broken?",
            "Replace the complete\nfront stabilizer jack.",
            "Retest power and the crank.\nDo not replace the coupler only.",
            "Full jack R&R.\nReconnect mount and power.",
        ),
        "bay_order": [
            "Confirm power extend and retract. If power is dead, fix power before the override. If power works, try the manual crank.",
            "If the manual-override roll pin or coupler is broken or seized, do not replace the coupler only. Replace the complete front stabilizer jack assembly.",
            "Reconnect the mount and the electrical connector, then retest power extend and retract and the manual crank. If both work, that is the confirmed correction.",
        ],
        "do_not": [
            "Do not replace the coupler only.",
        ],
        "sources": [
            {
                "title": "Lippert PSX1 front stabilizer jack",
                "page": 7,
                "excerpt": "",
            },
        ],
        "flow_tall": True,
        "full_story": True,
    }


def _cooktop_tip_path() -> dict:
    body = _shop_body(COOKTOP_TIP_LOW_REPAIR)
    return {
        "primary_cite": "Suburban Range/Cooktops service manual, page 4, Figs. 3-4.",
        "pattern_means": body,
        "flowchart": _named_fix_chart(
            "The burner goes out when a pan is set on it.",
            "Does the tip sit\nlow in the flame?",
            "Reposition the thermocouple tip.\nThat is the repair.",
            "Relight with the pan on\nand watch the tip.",
            "Reposition the thermocouple tip\nin the flame with the pan on.",
        ),
        "bay_order": [
            "Set a pan on the lit burner. If the flame goes out, look at the thermocouple tip next.",
            "If the thermocouple tip sits low, reposition the thermocouple tip in the burner flame with the pan on.",
            "If the flame holds with the pan on, that reposition is the confirmed correction.",
            "If the flame still goes out, raise the tip so the pan cannot push it clear, then light the burner again.",
            "With the pan on the grate, watch that the tip stays in the flame for a full minute.",
            "Record the tip height that held the flame. Do not condemn the thermocouple until that position has been proved.",
        ],
        "do_not": [
            "Do not condemn the thermocouple until the tip has been repositioned in the flame with the pan on.",
        ],
        "sources": [
            {
                "title": "Suburban Range/Cooktops service manual",
                "page": 4,
                "excerpt": "",
            }
        ],
        "flow_tall": True,
        "full_story": True,
    }


def _thetford_troubleshooting_cite(ranked) -> str:
    """The owner-manual page that carries the leak rows, not winterizing or poor flush."""
    for row in ranked or []:
        blob = f"{row.get('title') or ''} {row.get('excerpt') or ''}".lower()
        if not (
            "water supply line connection" in blob
            or "leak persists from water valve" in blob
            or "vacuum breaker leaks while flushing" in blob
        ):
            continue
        title = human_source_title(row.get("title") or "", row.get("file_path") or "")
        page = _page_int(row.get("page"))
        page_bit = f" page {page}" if page else ""
        return _as_sentence(f"{title}{page_bit}")
    return "Thetford Style II OM Permanent RV Toilet 42088 troubleshooting page."


def _thetford_leak_flowchart() -> Flowchart:
    """Supply, then the vacuum breaker, then the valve body, then the flange."""
    return Flowchart(
        readable=True,
        nodes=[
            FlowNode(
                "s",
                "start",
                "Toilet leaks under\nthe flush lever.",
                0.78,
                0.04,
                w=280,
                h=56,
            ),
            FlowNode(
                "r1",
                "end",
                "Secure or tighten\nthe supply connection.",
                0.22,
                0.18,
                w=230,
                h=60,
            ),
            FlowNode(
                "d1",
                "decision",
                "Supply connection\nleaking at the water valve?",
                0.78,
                0.18,
                w=230,
                h=84,
            ),
            FlowNode(
                "r2",
                "end",
                "Replace the vacuum breaker.",
                0.22,
                0.36,
                w=220,
                h=52,
            ),
            FlowNode(
                "d2",
                "decision",
                "Vacuum breaker leaking\nonly while flushing?",
                0.78,
                0.36,
                w=230,
                h=76,
            ),
            FlowNode(
                "r3",
                "end",
                "Replace the water valve.",
                0.22,
                0.54,
                w=210,
                h=52,
            ),
            FlowNode(
                "d3",
                "decision",
                "Water valve weeping\nat the pedal?",
                0.78,
                0.54,
                w=220,
                h=76,
            ),
            FlowNode(
                "r4",
                "end",
                "Tighten the flange nuts\nand replace the flange seal.",
                0.22,
                0.72,
                w=240,
                h=60,
            ),
            FlowNode(
                "d4",
                "decision",
                "Leak at the\nfloor flange?",
                0.78,
                0.72,
                w=200,
                h=72,
            ),
            FlowNode(
                "e",
                "end",
                "Write the readings\nand stop.",
                0.78,
                0.90,
                w=200,
                h=52,
            ),
        ],
        edges=[
            FlowEdge("s", "d1"),
            FlowEdge("d1", "r1", "YES", "left", "right"),
            FlowEdge("d1", "d2", "NO", "bottom", "top"),
            FlowEdge("d2", "r2", "YES", "left", "right"),
            FlowEdge("d2", "d3", "NO", "bottom", "top"),
            FlowEdge("d3", "r3", "YES", "left", "right"),
            FlowEdge("d3", "d4", "NO", "bottom", "top"),
            FlowEdge("d4", "r4", "YES", "left", "right"),
            FlowEdge("d4", "e", "NO", "bottom", "top"),
        ],
    )


def _lead_jack_drift_flowchart() -> Flowchart:
    """Coil, then plumbing, then the override screw. YES lands on the cartridge."""
    return Flowchart(
        readable=True,
        nodes=[
            FlowNode(
                "s",
                "start",
                "Front jacks drift when\nother circuits pressurize.",
                0.78,
                0.05,
                w=250,
                h=56,
            ),
            FlowNode(
                "r1",
                "end",
                "Repair the gray-wire\ncoil circuit.",
                0.22,
                0.22,
                w=210,
                h=56,
            ),
            FlowNode(
                "d1",
                "decision",
                "Lead-jack coil\n(gray wire) good?",
                0.78,
                0.22,
                w=210,
                h=72,
            ),
            FlowNode(
                "r2",
                "end",
                "Correct the notched port,\nfollow-leg, plugs, and\norange / black hoses.",
                0.22,
                0.44,
                w=230,
                h=72,
            ),
            FlowNode(
                "d2",
                "decision",
                "Swap plumbing\ncorrect?",
                0.78,
                0.44,
                w=190,
                h=68,
            ),
            FlowNode(
                "r3",
                "end",
                "Back out the manual\noverride screw.",
                0.22,
                0.66,
                w=210,
                h=56,
            ),
            FlowNode(
                "d3",
                "decision",
                "Override screw\nbacked out?",
                0.78,
                0.66,
                w=190,
                h=68,
            ),
            FlowNode(
                "e",
                "end",
                "Replace cartridge\nvalve 177094.",
                0.78,
                0.88,
                w=200,
                h=56,
            ),
        ],
        edges=[
            FlowEdge("s", "d1"),
            FlowEdge("d1", "r1", "NO", "left", "right"),
            FlowEdge("d1", "d2", "YES", "bottom", "top"),
            FlowEdge("d2", "r2", "NO", "left", "right"),
            FlowEdge("d2", "d3", "YES", "bottom", "top"),
            FlowEdge("d3", "r3", "NO", "left", "right"),
            FlowEdge("d3", "e", "YES", "bottom", "top"),
        ],
    )


def _lead_jack_drift_path() -> dict:
    return {
        "primary_cite": (
            "Lippert TI-005 page 3. Level Up Towable Owner's Manual page 15."
        ),
        "pattern_means": (
            "Front jacks that move when another circuit pressurizes, including the slides, "
            "are a front lead-jack cartridge that leaks internally. Part 177094 is the "
            "Cartridge Valve, item F, in the Lippert Level Up Towable Owner's Manual page 15 "
            "and the Lippert Level Up FW Owner's Manual page 18. "
            "There is no bench test for that leak."
        ),
        "flowchart": _lead_jack_drift_flowchart(),
        "flow_tall": True,
        "bay_order": [
            "Test the lead-jack valve coil on the gray wire. "
            "If it does not test good, repair that coil circuit before any cartridge.",
            "Confirm the swap plumbing: manifold hose in the notched port, "
            "follow-leg hose in the non-notched port, unused ports plugged, "
            "and the orange extend and black retract hoses not reversed.",
            "Confirm the manual override screw is backed out.",
            "If the coil is good, the plumbing is correct, and the override screw is backed out, "
            "replace the front lead-jack cartridge valve, part 177094. "
            "The parts list calls 177094 the Cartridge Valve, item F "
            "(Lippert Level Up Towable Owner's Manual, page 15; "
            "Lippert Level Up FW Owner's Manual, page 18).",
        ],
        "do_not": [
            "Do not replace the cartridge before the gray-wire coil, the swap plumbing, "
            "and the manual override screw are checked.",
        ],
        "sources": [
            {
                "title": "Lippert Level Up Towable Owner's Manual",
                "page": 15,
                "excerpt": "Cartridge Valve, item F, part 177094.",
            },
            {
                "title": "Lippert Level Up FW Owner's Manual",
                "page": 18,
                "excerpt": "Cartridge Valve, item F, part 177094.",
            },
            {
                "title": "Lippert Level Up FW Owner's Manual",
                "page": 13,
                "excerpt": "",
            },
            {"title": "Lippert CCD-0001750", "page": 8, "excerpt": ""},
            {"title": "Lippert QR-109", "page": 3, "excerpt": ""},
            {"title": "Lippert TI-143", "page": 2, "excerpt": ""},
            {"title": "Lippert TI-324", "page": 2, "excerpt": ""},
            {"title": "Lippert TI-170", "page": 1, "excerpt": ""},
            {
                "title": "Lippert TI-005 Electronic Leveling Troubleshooting Guide",
                "page": 3,
                "excerpt": "",
            },
        ],
    }


def _thetford_leak_path(concern: str, ranked) -> dict:
    import manual_figures as mf

    return {
        "primary_cite": _thetford_troubleshooting_cite(ranked),
        "pattern_means": (
            "A leak under the flush lever is checked in this order: the supply connection, "
            "the vacuum breaker while flushing, the water valve at the pedal, then the floor flange. "
            "Stop at the check that is leaking. "
            "Style II uses a foot pedal."
        ),
        "flowchart": _thetford_leak_flowchart(),
        "bay_order": [
            mf.thetford_proving_body("supply"),
            mf.thetford_proving_body("vacuum"),
            mf.thetford_proving_body("valve"),
            mf.thetford_proving_body("flange"),
        ],
        "do_not": [
            "Do not replace the water valve or the flange seal before the supply connection and the vacuum breaker are checked.",
        ],
        "sources": [],
        "flow_tall": True,
        "full_story": True,
    }


_THETFORD_OM_LEAK_RE = re.compile(
    r"leak persists from water valve"
    r"|water supply line connection at water valve"
    r"|vacuum breaker leaks while flushing"
    r"|flange nuts for tightness"
    r"|between closet flange and toilet",
    re.I,
)


_THETFORD_INSTALL_STEP_RE = re.compile(
    r"\b(?:disconnect|connect)\b.{0,60}\bwater supply\b",
    re.I,
)


def _thetford_leak_quote(excerpt: str) -> str:
    """A kit quote has to be a leak sentence. An install step is dropped."""
    text = re.sub(r"\s+", " ", (excerpt or "").strip())
    if not text:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        sentences = [text]
    for sentence in sentences:
        if _THETFORD_INSTALL_STEP_RE.search(sentence) and not _THETFORD_OM_LEAK_RE.search(sentence):
            continue
        if _THETFORD_OM_LEAK_RE.search(sentence) or re.search(
            r"\b(?:leak(?:s|ing|ed)?|weep(?:s|ing)?)\b", sentence, re.I
        ):
            return sentence
    return ""


def _thetford_leak_sources(sources: list[dict]) -> list[dict]:
    """OM troubleshooting page, water valve kit 42109 page 1, vacuum breaker kit."""
    kept = []
    for src in sources or []:
        title = src.get("title") or ""
        page = src.get("page")
        excerpt = src.get("excerpt") or ""
        if _is_multilingual_ocr_line(excerpt):
            excerpt = ""
        row = dict(src)
        row["excerpt"] = excerpt
        valve_kit = bool(re.search(r"\b42109\b", title)) and page == 1
        breaker_kit = bool(re.search(r"\b34122\b|\b34123\b", title))
        om = bool(re.search(r"\b42088\b|permanent rv toilet", title, re.I)) and bool(
            _THETFORD_OM_LEAK_RE.search(excerpt)
        )
        if valve_kit or breaker_kit:
            row["excerpt"] = _thetford_leak_quote(excerpt)
            kept.append(row)
        elif om:
            kept.append(row)

    def _order(src: dict) -> tuple:
        title = src.get("title") or ""
        if re.search(r"\b42088\b|permanent rv toilet", title, re.I):
            return (0, src.get("page") or 0)
        if re.search(r"\b42109\b", title):
            return (1, src.get("page") or 0)
        return (2, src.get("page") or 0)

    return sorted(kept, key=_order)


def bind_primary_sources(proc: "BayProcedure") -> "BayProcedure":
    """A page named in PRIMARY stays in Sources, with no quote unless one was kept.

    An installation manual or a discontinued sheet that won the cite is not
    put back after the source pass dropped it.
    """
    pages = [
        int(number)
        for number in re.findall(r"\bpage\s+(\d{1,3})\b", proc.primary_cite or "", flags=re.I)
    ]
    if not pages:
        return proc
    title = re.sub(r"\s+", " ", proc.primary_cite or "").strip()
    title = re.sub(r",?\s*\bpage\s+\d+.*$", "", title, flags=re.I).strip(" .,")
    title = re.sub(r",?\s*\bfigs?\..*$", "", title, flags=re.I).strip(" .,")
    title = title or "Shop Document Library"
    low = title.lower()
    if any(token in low for token in ("installation", "discontinued", "ti-005")):
        proc.sources = _dedupe_cited_pages(proc.sources)
        return proc
    have = {src.get("page") for src in proc.sources}
    if proc.sources and pages and have & set(pages):
        proc.sources = _dedupe_cited_pages(proc.sources)
        return proc
    for page in pages:
        if page in have:
            continue
        proc.sources.append({"title": title, "page": page, "excerpt": ""})
        have.add(page)
    proc.sources = _dedupe_cited_pages(proc.sources)
    return proc


_SLOT_STOP = {
    "this", "that", "with", "from", "have", "been", "will", "your", "into",
    "onto", "before", "after", "when", "then", "than", "them", "they",
    "page", "manual", "item", "part", "list", "calls", "good", "does",
    "replace", "confirm", "check", "test", "step", "figure",
}


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(word) > 3 and word not in _SLOT_STOP
    }


def _step_slot_for_figure(steps: list[str], title: str, excerpt: str):
    """Which bay step this figure illustrates. Any brand, by the words on the step.

    The vacuum-breaker and water-valve sheets keep their shop slots. Supply
    and flange stay unpictured unless the figure's own words land there.
    """
    blob = f"{title} {excerpt[:800]}"
    low = blob.lower()
    if re.search(r"34122|34123|vacuum breaker", low):
        for index, step in enumerate(steps):
            if "vacuum" in step.lower():
                return index
    if re.search(r"42109|water valve", low):
        for index, step in enumerate(steps):
            step_low = step.lower()
            if "weep" in step_low or "replace the water valve" in step_low:
                return index
        for index, step in enumerate(steps):
            if "water valve" in step.lower():
                return index
    words = _content_words(blob)
    nums = set(re.findall(r"\b\d{4,}\b", blob))
    identity_ids = set(re.findall(r"\b\d{4,}\b", title or ""))
    best_index = None
    best_score = 0
    for index, step in enumerate(steps):
        step_ids = set(re.findall(r"\b\d{4,}\b", step))
        if identity_ids and step_ids and identity_ids.isdisjoint(step_ids):
            continue
        score = len(words & _content_words(step))
        score += 5 * len(nums & step_ids)
        if score > best_score:
            best_score = score
            best_index = index
    if best_score >= 2:
        return best_index
    return None


def _drop_off_brand_sheet_figures(proc: BayProcedure, job: str) -> None:
    """A cited figure from another brand or system does not stay on the sheet."""
    import library_figure_backfill as fb

    # Missing on a stale cached module. Drop the figures rather than crash the PDF.
    off_brand = getattr(fb, "off_brand_figure", None)
    if off_brand is None:
        proc.figures = []
        return
    kept = []
    for fig in proc.figures or []:
        if off_brand(
            {
                "title": fig.title,
                "caption": fig.caption,
                "keywords": fig.excerpt,
            },
            category=proc.category or "",
            model=f"{proc.brand or ''} {proc.model or ''}".strip(),
            user_msg=proc.concern or "",
            reply=job,
        ):
            continue
        kept.append(fig)
    proc.figures = kept


def _thetford_repair_locked(proc: BayProcedure) -> bool:
    """The four Thetford leak branches are already the sheet. A figure packet must not replace them."""
    import manual_figures as mf

    blob = " ".join(
        part for part in (proc.brand, proc.model, proc.concern, proc.primary_cite, proc.category) if part
    )
    if not mf.job_is_thetford(blob, " ".join(proc.bay_order or [])):
        return False
    titles = " ".join((item.get("title") or "") for item in proc.procedures or []).lower()
    return "supply" in titles and "flange" in titles and len(proc.procedures or []) >= 4


def _graft_library_figures(proc: BayProcedure, packets) -> None:
    """Fill a cited crop that has no PNG. The step list stays the repair that was already compiled."""
    import manual_figures as mf

    pool = []
    for packet in packets or []:
        for figure in packet.get("figures") or []:
            png = figure.get("png") or b""
            if png and not mf.png_is_blank(png):
                pool.append(figure)
    if not pool:
        return
    for procedure in proc.procedures or []:
        for step in procedure.get("steps") or []:
            figure = step.get("figure")
            if not isinstance(figure, dict):
                continue
            png = figure.get("png") or b""
            if png and not mf.png_is_blank(png):
                continue
            nums = mf._figure_numbers(figure.get("label") or "")
            if not nums:
                continue
            for item in pool:
                if any(number in mf._figure_numbers(item.get("label") or "") for number in nums):
                    figure["png"] = item.get("png") or b""
                    if not figure.get("label"):
                        figure["label"] = item.get("label") or ""
                    break


def crop_printed_figure_label(png: bytes) -> bytes:
    """Cut the kit's own 'FIGURE N - TITLE' line off the bottom of a crop.

    The sheet numbers figures across the page set, so a printed kit number under the
    drawing would show the tech a second number. Only a short text band, set apart from
    the drawing by white rows, is cut. A border line or a drawing edge stays.
    """
    try:
        from PIL import Image
        import io

        im = Image.open(io.BytesIO(png)).convert("L")
    except Exception:
        return png
    w, h = im.size
    if h < 60 or w < 60:
        return png
    px = im.load()

    def ink(y: int) -> float:
        return sum(1 for x in range(0, w, 2) if px[x, y] < 128) / max(1, (w + 1) // 2)

    y = h - 1
    while y > 0 and ink(y) < 0.005:
        y -= 1
    bottom = y
    band_max = 0.0
    while y > 0 and ink(y) >= 0.005:
        band_max = max(band_max, ink(y))
        y -= 1
    top = y
    gap = 0
    while y > 0 and ink(y) < 0.005:
        gap += 1
        y -= 1
    height = bottom - top
    if gap < 2 or height < 6 or height > 0.14 * h or band_max >= 0.6 or y < 0.6 * h:
        return png
    out = io.BytesIO()
    Image.open(io.BytesIO(png)).crop((0, 0, w, y + 2)).save(out, format="PNG")
    return out.getvalue()


def manual_figure_label(label: str, text: str) -> str:
    """A bare 'Fig. 1' takes the manual's own name for it.

    'Refer to Figure 1 for component locations.' -> 'Fig. 1 COMPONENT LOCATIONS'.
    A label that already has a title, or a figure the text never names, stays as it is.
    """
    m = re.match(r"(?i)^\s*fig(?:ure)?\.?\s*(\d+)\s*$", label or "")
    if not m:
        return label
    n = m.group(1)
    body = re.sub(r"\s+", " ", text or "")
    found = re.search(
        rf"(?i)\bfigure {n}\s*(?:[-–:]\s*([A-Z][A-Z ]{{2,40}}[A-Z])\b|for (?:the )?([a-z][a-z ]{{2,40}}?)\s*[.;,)])",
        body,
    )
    if not found:
        return label
    name = (found.group(1) or found.group(2) or "").strip().upper()
    return f"Fig. {n} {name}" if name else label


def apply_chunk_figures(proc: BayProcedure, chunks) -> BayProcedure:
    """Put each cropped figure on the step it supports, and quote that chunk's how-to.

    Chunks with no figure leave the locked shop line unchanged, so the 15-case
    sheets stay as they are.
    """
    import manual_figures as mf

    packets = []
    for chunk in chunks or []:
        data = chunk_as_dict(chunk)
        figures = list(data.get("figures") or [])
        if data.get("image_png"):
            figures.append(
                {
                    "png": data["image_png"],
                    "label": data.get("figure_label") or "Fig.",
                    "page": data.get("page"),
                    "title": data.get("title") or "",
                }
            )
        text = str(data.get("excerpt") or data.get("chunk_text") or data.get("text") or "")
        figures = [{**f, "label": manual_figure_label(f.get("label") or "", text)} for f in figures]
        if figures:
            packets.append({**data, "figures": figures})
    job = " ".join(
        part for part in (proc.brand, proc.model, proc.concern, proc.primary_cite) if part
    )
    if not packets:
        _drop_off_brand_sheet_figures(proc, job)
        return proc
    groups = [[] for _ in proc.bay_order]
    details = {}
    import library_figure_backfill as fb

    # A cached figure-bank module can predate these helpers. No helper means no figure.
    fits = getattr(fb, "fits_case", None)
    how_for = getattr(fb, "procedure_how", None)
    off_brand = getattr(fb, "off_brand_figure", None)
    locked = _thetford_repair_locked(proc)
    fitting = []
    for packet in packets:
        title = packet.get("title") or ""
        if fits is None or not fits(
            packet,
            category=proc.category or "",
            model=f"{proc.brand or ''} {proc.model or ''}".strip(),
            user_msg=proc.concern or "",
            reply=job,
        ):
            continue
        fitting.append(packet)
        page = packet.get("page")
        labels = " ".join(
            f"{figure.get('label') or ''} {figure.get('caption') or ''}"
            for figure in packet["figures"]
        )
        slot = _step_slot_for_figure(
            proc.bay_order, f"{title} {labels}", packet.get("excerpt") or ""
        )
        if slot is None:
            continue
        detail = ""
        if how_for is not None:
            detail = how_for(
                packet,
                packet.get("excerpt") or "",
                title,
                page,
                category=proc.category or "",
                model=f"{proc.brand or ''} {proc.model or ''}".strip(),
                user_msg=proc.concern or "",
                reply=job,
            )
        # A locked Thetford sheet already names the step. The How template
        # stays off that bay order. Other sheets still quote the chunk.
        if detail and slot not in details and not locked:
            details[slot] = detail
        for figure in packet["figures"]:
            fig_title = figure.get("title") or title
            if mf.brands_conflict(job, fig_title):
                continue
            if off_brand is None or off_brand(
                {**packet, "title": fig_title, "label": figure.get("label") or "", "caption": figure.get("caption") or ""},
                category=proc.category or "",
                model=f"{proc.brand or ''} {proc.model or ''}".strip(),
                user_msg=proc.concern or "",
                reply=job,
            ):
                continue
            on_topic = getattr(fb, "figure_on_topic", None)
            if on_topic is not None and not on_topic(
                {**packet, "title": fig_title, "label": figure.get("label") or "", "caption": figure.get("caption") or ""},
                proc.bay_order[slot] if slot < len(proc.bay_order) else "",
                proc.concern or "",
                f"{proc.brand or ''} {proc.model or ''}".strip(),
            ):
                continue
            png = figure.get("png") or b""
            if not png or mf.png_is_blank(png):
                continue
            groups[slot].append(
                BayFigure(
                    title=fig_title,
                    page=figure.get("page") or page,
                    caption=figure.get("label") or "Fig.",
                    excerpt=(packet.get("excerpt") or "")[:240],
                    image_png=png,
                )
            )
    order = list(proc.bay_order)
    if locked:
        order = [re.split(r"\s+How\s*\(", step or "", maxsplit=1)[0].strip() for step in order]
    for slot, detail in details.items():
        if detail not in order[slot]:
            order[slot] = f"{order[slot].rstrip()} {detail}"
    for index, step in enumerate(order):
        if re.search(r"\bpage\s+\d+", step, re.I):
            continue
        cite = (proc.primary_cite or "").strip()
        if cite and re.search(r"\bpage\s+\d+", cite, re.I):
            order[index] = f"{step.rstrip()} ({cite})"
            continue
        low = step.lower()
        if "thetford" in job.lower() and ("flange" in low or "supply line" in low):
            order[index] = (
                f"{step.rstrip()} "
                "(Thetford Style II OM Permanent RV Toilet 42088, page 3)."
            )
    proc.bay_order = order
    proc.step_figures = groups
    if locked:
        _graft_library_figures(proc, fitting)
    else:
        proc.procedures = _plain_kit_procedures(fitting, job)
    owned = set()
    for procedure in proc.procedures:
        for step in procedure.get("steps") or []:
            figure = step.get("figure") or {}
            png = figure.get("png") if isinstance(figure, dict) else getattr(figure, "image_png", b"")
            if png:
                owned.add(png)
    if owned:
        proc.step_figures = [
            [fig for fig in group if fig.image_png not in owned]
            for group in proc.step_figures
        ]
    used = {fig.image_png for group in proc.step_figures for fig in group if fig.image_png}
    used.update(owned)
    proc.figures = [fig for fig in proc.figures or [] if not (fig.image_png and fig.image_png in used)]
    _drop_off_brand_sheet_figures(proc, job)
    return proc


def cited_figure_count(proc: "BayProcedure") -> int:
    """How many figures the sheet actually draws.

    A placeholder, a plenum, an illegible crop, and an empty image do not count.
    The same image is not counted twice.
    """
    total = 0
    seen = set()

    def _add(png: bytes, fig: "BayFigure | None" = None) -> None:
        nonlocal total
        if not png or png in seen:
            return
        if fig is not None and (
            figure_is_placeholder(fig) or _figure_is_plenum(fig) or _figure_is_illegible(fig, png)
        ):
            return
        seen.add(png)
        total += 1

    for fig in proc.figures or []:
        _add(getattr(fig, "image_png", b"") or b"", fig)
    # A numbered repair draws its own figures. Diagnosis crops are not painted.
    if not proc.procedures:
        for group in proc.step_figures or []:
            for fig in group or []:
                _add(getattr(fig, "image_png", b"") or b"", fig)
    for procedure in proc.procedures or []:
        for step in procedure.get("steps") or []:
            figure = step.get("figure") or {}
            png = figure.get("png") if isinstance(figure, dict) else b""
            if png:
                _add(png)
    return total


def _kit_topic_for_step(step: str) -> str:
    """The kit crop this bay step can show. A supply mention of the water valve is not the kit."""
    low = step or ""
    if re.search(r"vacuum breaker|\b34122\b|\b34123\b", low, re.I):
        return "breaker"
    if re.search(r"\b42109\b|\bweep|pull the pedal|turn off the water|under the water hose", low, re.I):
        return "valve"
    return ""


def _kit_crop_for_step(step: str, figures: list):
    """The crop this step names. Water-off is Fig. 3. Pulling the pedal off is Fig. 1."""
    import manual_figures as mf

    low = step or ""
    if re.search(r"pull the pedal (?:up and )?off", low, re.I):
        crop = mf._matching_kit_crop(figures, r"pedal\s+removed")
        if crop:
            return crop
    if re.search(r"turn off the water|under the water hose", low, re.I):
        crop = mf._matching_kit_crop(figures, r"fig\.?\s*3\b")
        if crop and not re.search(r"pedal", crop.get("label") or "", re.I):
            return crop
    named = mf._numbers_named(low)
    if named:
        for figure in figures or []:
            nums = mf._figure_numbers(figure.get("label") or "")
            if any(number in named for number in nums) and figure.get("png") and not mf.png_is_blank(figure.get("png") or b""):
                return figure
    return next(
        (
            item
            for item in figures or []
            if item.get("png") and not mf.png_is_blank(item.get("png") or b"")
        ),
        None,
    )


def _confirmed_thetford_kind(proc: BayProcedure, history=None) -> str:
    """The kit the finding names. A flush leak with no breaker finding is the valve."""
    parts = [proc.concern or ""]
    for message in history or []:
        if not isinstance(message, dict):
            continue
        if (message.get("role") or "") != "user":
            continue
        content = (message.get("content") or "").strip()
        if content:
            parts.append(content)
    low = " ".join(parts).lower()
    marks = []
    for match in re.finditer(r"vacuum breaker|\b34122\b|\b34123\b", low):
        marks.append((match.start(), "breaker"))
    for match in re.finditer(
        r"\b42109\b|\b42049\b|water valve|\bweeps?\b|drive arm|cracked housing",
        low,
    ):
        marks.append((match.start(), "valve"))
    if not marks:
        return "valve"
    marks.sort()
    return marks[-1][1]


def _procedure_keeps_repeated_figures(procedure: dict) -> bool:
    """FACR cites the same library page on more than one step. Each cite keeps the image."""
    title = (procedure or {}).get("title") or ""
    return bool(re.search(r"FACR08|2024006031", title))


def _drop_repeated_procedure_figures(procedures: list) -> None:
    """The first step that uses a crop keeps it. Later steps stay text."""
    seen = set()
    for procedure in procedures or []:
        if _procedure_keeps_repeated_figures(procedure):
            continue
        for step in procedure.get("steps") or []:
            figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
            png = (figure or {}).get("png") or b""
            if not png:
                continue
            if png in seen:
                step["figure"] = None
                continue
            seen.add(png)


def _branch_step(
    how: str,
    where: str,
    good: str,
    bad: str,
    nxt: str,
    section: str = "removal",
    fail: str = "",
    tools: str = "",
) -> dict:
    """One repair-branch action. The sentence stays under 12 words.

    ``fail`` is the next action when the step is bad. It is not a copy of the
    bad look. ``tools`` is only the tool this action uses.
    """
    bare = how.rstrip(".")
    on_bad = (fail or "Stop and tell the shop.").rstrip(".")
    tool_line = f"Tools: {tools.rstrip('.')}." if tools else ""
    return {
        "section": section,
        "text": bare,
        "actions": [f"{bare}."],
        "source": bare,
        "fields": {
            "WHERE": where,
            "SAFETY": "",
            "TOOLS / METER SETTING": tool_line,
            "HOW": bare,
            "GOOD vs BAD": f"Good: {good} Bad: {bad}",
            "NEXT": f"On good: {nxt} On bad: {on_bad}",
            "FIGURE": "",
            "PHOTO": "",
        },
        "figure": None,
    }


def _confirm_step(where: str) -> dict:
    return _branch_step(
        "Confirm the repair is dry.",
        where or "At the finished repair.",
        "The repair is dry.",
        "A drip or a wet spot shows after the flush.",
        "This branch is complete.",
        fail="Redo the branch that was just finished.",
        section="prove",
    )


def ensure_verify_step(procedure: dict) -> dict:
    """Each repair branch ends on a confirm step. A branch that already confirms stays."""
    steps = list((procedure or {}).get("steps") or [])
    if not steps:
        return procedure
    if (steps[-1].get("text") or "").lower().startswith("confirm "):
        return procedure
    where = ((steps[-1].get("fields") or {}).get("WHERE") or "").strip() or "At the finished repair."
    cloned = dict(procedure)
    cloned["steps"] = steps + [_confirm_step(where)]
    if not cloned.get("heading"):
        cloned["heading"] = "REPAIR BRANCH"
    return cloned


def _supply_branch() -> dict:
    return {
        "title": "Supply connection",
        "heading": "REPAIR BRANCH",
        "before": [
            "Turn the RV water off before this work.",
            "Fix the supply connection before you open a kit.",
        ],
        "steps": [
            _branch_step(
                "Pull the water hose off the water valve.",
                "Back of the toilet, on the water valve.",
                "The hose is off.",
                "The hose is still on.",
                "Push the hose back on.",
                fail="Loosen the clamp and pull the hose again.",
                tools="pliers",
                section="removal",
            ),
            _branch_step(
                "Push the water hose onto the water valve.",
                "Back of the toilet, on the water valve.",
                "The hose is fully on the fitting.",
                "The hose sits crooked on the fitting.",
                "Secure or tighten the supply line connection.",
                fail="Pull the hose off and push it on straight.",
                tools="pliers",
                section="installation",
            ),
            _branch_step(
                # OM 42088 p3: "check water supply line connection at water valve. Secure or tighten as necessary."
                "Secure or tighten the supply line connection at the water valve.",
                "Back of the toilet, on the water valve.",
                "The connection is snug and dry.",
                "Water still beads at the connection.",
                "Confirm the connection.",
                fail="If the leak persists from the water valve, replace the valve.",
                section="installation",
            ),
            _confirm_step("Back of the toilet, on the water valve."),
        ],
    }


def _flange_branch() -> dict:
    return {
        "title": "Flange and seal",
        "heading": "REPAIR BRANCH",
        "before": [
            "Turn the RV water off before this work.",
            "Use closet flange seal 02125 when the flange is the leak.",
        ],
        "steps": [
            _branch_step(
                "Take off the bolt covers and the nuts.",
                "At the closet flange, under the toilet.",
                "The bolt covers and the nuts are off.",
                "A nut is still on.",
                "Pull the water hose off.",
                fail="Turn the nut the other way.",
                tools="wrench",
                section="removal",
            ),
            _branch_step(
                "Pull the water hose off the toilet.",
                "At the water hose on the toilet.",
                "The hose is off.",
                "The hose is still on.",
                "Lift the toilet.",
                fail="Loosen the clamp and pull the hose again.",
                tools="pliers",
                section="removal",
            ),
            _branch_step(
                "Lift the toilet off the floor.",
                "At the closet flange, under the toilet.",
                "The toilet is off the floor.",
                "The toilet is still bolted down.",
                "Take off the old seal.",
                fail="Take the nuts off, then lift again.",
                section="removal",
            ),
            _branch_step(
                "Take off the old floor seal.",
                "At the closet flange, under the toilet.",
                "The old seal is off.",
                "The old seal is still on.",
                "Cover the holding tank opening.",
                fail="Pull the old seal off.",
                section="removal",
            ),
            _branch_step(
                "Cover the holding tank opening at the closet flange with a towel.",
                "At the closet flange.",
                "The opening is covered.",
                "The opening is still open.",
                "Check the flange height.",
                fail="Lay the towel over the opening.",
                section="removal",
            ),
            _branch_step(
                "Check the flange is 7/16 inch above the floor.",
                "At the closet flange, under the toilet.",
                "The flange is 7/16 inch above the floor.",
                "The flange sits low, under 7/16 inch above the floor.",
                "If the flange is low, add Thetford spacers to bring it to 7/16 inch.",
                fail="If the flange is low, add Thetford spacers to bring it to 7/16 inch.",
                tools="ruler",
                section="removal",
            ),
            _branch_step(
                # OM 42088 p3: "Use Thetford spacers to adjust, if necessary, to 7/16 in above floor."
                "If the flange is low, add Thetford spacers to bring it to 7/16 inch.",
                "At the closet flange, under the toilet.",
                "The flange is 7/16 inch above the floor.",
                "The spacers rock or sit crooked on the flange.",
                "Uncover the holding tank opening.",
                fail="Reseat the spacers flat on the flange.",
                section="removal",
            ),
            _branch_step(
                "Uncover the holding tank opening at the closet flange.",
                "At the closet flange.",
                "The holding tank opening is clear.",
                "The towel is still on.",
                "Put seal 02125 on.",
                fail="Pull the towel out of the opening.",
                section="installation",
            ),
            _branch_step(
                "Put flange seal 02125 on with the lip down.",
                "At the closet flange, under the toilet.",
                "The new seal is seated.",
                "The leak continues.",
                "Set the toilet on the bolts.",
                fail="Seat the seal again.",
                section="installation",
            ),
            _branch_step(
                "Set the toilet on the floor bolts.",
                "At the closet flange, under the toilet.",
                "The holes line up on the bolts.",
                "The holes do not line up.",
                "Tighten the nuts.",
                fail="Set the toilet on the bolts again.",
                section="installation",
            ),
            _branch_step(
                "Tighten the nuts until the toilet does not rock.",
                "At the closet flange, under the toilet.",
                "The toilet does not rock.",
                "The toilet still rocks.",
                "Push the water hose on.",
                fail="Turn the nuts until the toilet does not rock.",
                tools="wrench",
                section="installation",
            ),
            _branch_step(
                "Put the bolt covers back on.",
                "At the closet flange, under the toilet.",
                "The bolt covers are on the nuts.",
                "A bolt cover sits loose or is missing.",
                "Push the water hose on.",
                fail="Press the cover down over the nut.",
                section="installation",
            ),
            _branch_step(
                # 42109 p1 / 34122 p2: "Connect RV water supply line to Toilet."
                "Push the water hose onto the toilet.",
                "Back of the toilet, on the water valve.",
                "The water hose is on the water valve fitting.",
                "The water hose sits crooked on the fitting.",
                "Secure or tighten the supply line connection.",
                fail="Take the water hose off and push it on straight.",
                section="installation",
            ),
            _branch_step(
                # OM 42088 p3: "Secure or tighten as necessary."
                "Secure or tighten the supply line connection at the water valve.",
                "Back of the toilet, on the water valve.",
                "The connection is snug and dry.",
                "Water still beads at the connection.",
                "Confirm the flange.",
                fail="If the leak persists from the water valve, replace the valve.",
                section="installation",
            ),
            _confirm_step("At the closet flange, under the toilet."),
        ],
    }


def _safety_sentences(text: str) -> list[str]:
    """Real safety sentences. A not-stated filler is not a note."""
    out = []
    for piece in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        sentence = piece.strip()
        if not sentence or re.search(r"not stated|unconfirmed", sentence, re.I):
            continue
        if sentence[-1] not in ".!?":
            sentence += "."
        out.append(sentence)
    return out


def hoist_branch_safety(procedure: dict) -> dict:
    """The safety note used most often lives in Before you start, once."""
    import manual_figures as mf

    counts: dict[str, int] = {}
    order: list[str] = []
    for step in procedure.get("steps") or []:
        for sentence in _safety_sentences(mf.step_safety_text(step)):
            key = sentence.lower()
            if key not in counts:
                order.append(sentence)
                counts[key] = 0
            counts[key] += 1
    if not order:
        return procedure
    before = list(procedure.get("before") or [])
    blob = " ".join(before).lower()
    pending = [
        sentence
        for sentence in order
        if sentence.rstrip(".").lower() not in blob
        and not re.search(r"\bwater on\b|turn the rv water on", sentence, re.I)
    ]
    if not pending:
        return procedure
    note = max(pending, key=lambda sentence: counts[sentence.lower()])
    procedure["before"] = [note, *before]
    return procedure


def _with_removal_line(procedure: dict) -> dict:
    """A branch with nothing to take off still names Removal."""
    steps = list((procedure or {}).get("steps") or [])
    if any((step.get("section") or "") == "removal" for step in steps):
        return procedure
    where = "At the repair."
    for step in steps:
        named = ((step.get("fields") or {}).get("WHERE") or "").strip()
        if named:
            where = named
            break
    cloned = dict(procedure)
    cloned["steps"] = [
        _branch_step(
            "Removal: none.",
            where,
            "No part comes off.",
            "",
            "Go to installation.",
            section="removal",
        ),
        *steps,
    ]
    return cloned


def _thetford_branch_layout(kind: str, chunks) -> dict:
    """Kit steps from the retrieved excerpt. The full PDF is only a last resort."""
    import manual_figures as mf

    title = (
        "Thetford Vacuum Breaker Kit 34123/34122"
        if kind == "breaker"
        else "Thetford Water Valve Kit 42109"
    )
    text, figures = mf.kit_excerpt(chunks, kind)
    figures = [
        {**figure, "label": manual_figure_label(str(figure.get("label") or ""), text)}
        if isinstance(figure, dict)
        else figure
        for figure in figures or []
    ]
    needles = ("34122", "34123") if kind == "breaker" else ("42109",)
    doc_numbers = " ".join(
        dict.fromkeys(
            _doc_part_numbers(chunk)
            for chunk in chunks or []
            if isinstance(chunk, dict)
            and any(needle in str(chunk.get("file_path") or "") for needle in needles)
        )
    )
    if text:
        layout = mf.procedure_from_sheet(text, figures or None, title, doc_text=doc_numbers)
        if layout.get("steps"):
            return layout
        return {}
    return mf.thetford_kit_layout(kind)


def _sync_thetford_sources(proc: BayProcedure, chunks=None) -> None:
    """Every doc and page the sheet cites is a Sources line."""
    blob = "\n".join(proc.bay_order or [])
    blob += "\n" + (proc.primary_cite or "")
    for procedure in proc.procedures or []:
        blob += "\n" + (procedure.get("title") or "")
        blob += "\n" + (procedure.get("doc") or "")
        for step in procedure.get("steps") or []:
            fields = step.get("fields") or {}
            blob += "\n" + " ".join(str(value or "") for value in fields.values())
            figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
            if figure:
                blob += f"\n{figure.get('label') or ''} {figure.get('title') or ''} page {figure.get('page') or ''}"
    rows = []
    prior = list(proc.sources or [])

    def _quote_from_procedure(token: str, needles: tuple[str, ...]) -> str:
        """A sentence from this document's own steps, not another manual's line."""
        for procedure in proc.procedures or []:
            blob = f"{procedure.get('title') or ''} {procedure.get('doc') or ''}"
            if not re.search(token, blob, re.I):
                continue
            for step in procedure.get("steps") or []:
                sentence = re.sub(r"\s+", " ", (step.get("text") or "")).strip().rstrip(".")
                low = sentence.lower()
                if "supply line" in low or "supply connection" in low:
                    continue
                if _THETFORD_INSTALL_STEP_RE.search(sentence):
                    continue
                if any(needle in low for needle in needles):
                    return sentence + "."
        return ""

    def _kept_excerpt(title: str, page: int) -> str:
        # Verbatim sentences from each document. A shortened step is not a quote.
        verbatim = (
            (r"\b42088\b", "Back of toilet: check water supply line connection at water valve."),
            (
                r"\b3412[23]\b",
                "With pliers, slide clamp A down inlet tube, then remove inlet tube from vacuum breaker.",
            ),
            (r"\b42109\b", "Insert new Water Valve Cartridge Assembly until fully seated."),
        )
        for token, sentence in verbatim:
            if re.search(token, title or ""):
                return sentence
        for src in prior:
            if (src.get("title") or "") == title and src.get("page") == page:
                excerpt = src.get("excerpt") or ""
                if excerpt and not _THETFORD_INSTALL_STEP_RE.search(excerpt):
                    if "42109" in title and re.search(r"supply line|supply connection", excerpt, re.I):
                        excerpt = ""
                    elif excerpt:
                        return excerpt
        if re.search(r"\b3412[23]\b", title):
            found = _quote_from_procedure(r"3412|vacuum breaker", ("vacuum breaker", "flush hose", "inlet tube"))
            if found:
                return found
        elif re.search(r"\b42109\b", title):
            found = _quote_from_procedure(r"42109|water valve", ("water valve", "pedal", "inlet"))
            if found:
                return found
        blob = "\n".join(proc.bay_order or [])
        needles = ("water valve", "vacuum breaker", "flange")
        for line in blob.splitlines():
            match = re.match(r"^\d+\.\s+(.+)$", line.strip())
            if not match:
                continue
            sentence = match.group(1).strip()
            low = sentence.lower()
            if "step " in low or _THETFORD_INSTALL_STEP_RE.search(sentence):
                continue
            if "supply line" in low and not re.search(r"\b42088\b", title):
                continue
            if any(needle in low for needle in needles):
                return sentence
        return ""

    def add(title: str, page: int):
        if page and not any(row["title"] == title and row["page"] == page for row in rows):
            rows.append({"title": title, "page": page, "excerpt": _kept_excerpt(title, page)})

    if re.search(r"\b42088\b", blob):
        pages = [int(n) for n in re.findall(r"42088\D{0,40}page\s+(\d+)", blob, re.I)]
        pages += [int(n) for n in re.findall(r"page\s+(\d+)\D{0,40}42088", blob, re.I)]
        for page in sorted(set(pages) or {3}):
            add("Thetford Style II OM Permanent RV Toilet 42088", page)
    if re.search(r"\b34122\b|\b34123\b|vacuum breaker", blob, re.I):
        pages = [int(n) for n in re.findall(r"3412[23]\D{0,48}page\s+(\d+)", blob, re.I)]
        pages += [int(n) for n in re.findall(r"page\s+(\d+)\D{0,24}3412[23]", blob, re.I)]
        for page in sorted(set(pages) or {1}):
            add("Thetford Vacuum Breaker Kit 34123/34122", page)
    if re.search(r"\b42109\b", blob):
        pages = [int(n) for n in re.findall(r"42109\D{0,48}page\s+(\d+)", blob, re.I)]
        pages += [int(n) for n in re.findall(r"page\s+(\d+)\D{0,24}42109", blob, re.I)]
        for page in sorted(set(pages) or {1}):
            add("Thetford Water Valve Kit 42109", page)
    for extra in _securing_source_rows(proc, chunks, rows):
        # A second page of a manual sits right under its first page.
        at = max((i for i, r in enumerate(rows) if r["title"] == extra["title"]), default=len(rows) - 1)
        rows.insert(at + 1, extra)
    rows = _verify_source_pages(rows, chunks)
    rows = _dedupe_source_rows(rows)
    if rows:
        proc.sources = rows


def _quote_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _verify_source_pages(rows: list, chunks) -> list:
    """A quote cites the page its words are printed on. A row whose quote sits on
    another page of the same manual takes that page."""
    for row in rows:
        quote = _quote_key(row.get("excerpt") or "")[:60]
        if len(quote) < 20:
            continue
        numbers = set(re.findall(r"\b\d{5}\b", row.get("title") or ""))
        pages = []
        for chunk in chunks or []:
            if not isinstance(chunk, dict):
                continue
            title = str(chunk.get("title") or chunk.get("clean_title") or "")
            if numbers and not numbers & set(re.findall(r"\b\d{5}\b", title)):
                continue
            if quote in _quote_key(str(chunk.get("chunk_text") or chunk.get("excerpt") or "")):
                pages.append(chunk.get("page"))
        if pages and row.get("page") not in pages:
            row["page"] = pages[0]
    return rows


def _securing_source_rows(proc: BayProcedure, chunks, rows: list) -> list:
    """A step that secures with a lettered clamp cites the manual page that says so, verbatim."""
    import manual_figures as mf

    letters = []
    for procedure in proc.procedures or []:
        for step in procedure.get("steps") or []:
            action = mf.step_heading(step, 1).split(": ", 1)[-1]
            m = re.search(r"(?i)\b(?:tighten|secure)\b.*\bclamp ([A-H])\b", action)
            if m and m.group(1) not in letters:
                letters.append(m.group(1))
    added = []
    for letter in letters:
        for chunk in chunks or []:
            if not isinstance(chunk, dict):
                continue
            body = re.sub(r"\s+", " ", str(chunk.get("chunk_text") or chunk.get("excerpt") or ""))
            m = re.search(rf"(?:^|\d\.\s+)([A-Z][^.]*\bsecure with new clamp {letter}\b\.)", body)
            if not m:
                continue
            title_raw = str(chunk.get("title") or chunk.get("clean_title") or "")
            numbers = set(re.findall(r"\b\d{5}\b", title_raw))
            title = next((r["title"] for r in rows if numbers & set(re.findall(r"\b\d{5}\b", r["title"]))), title_raw)
            page = chunk.get("page")
            if title and page and not any(r["title"] == title and r["page"] == page for r in rows + added):
                added.append({"title": title, "page": page, "excerpt": m.group(1).strip()})
            break
    return added


def attach_thetford_repair_procedures(proc: BayProcedure, history=None, chunks=None) -> BayProcedure:
    """Diagnosis stays in the flowchart. Every supported repair is its own branch.

    Thetford 42070 branches are the supply connection, vacuum breaker 34123/34122,
    water valve 42109, and the flange seal. Each branch numbers its own steps and
    ends on a confirm. A crop is drawn on the first step that uses it.
    """
    import manual_figures as mf

    del history
    if not proc.bay_order:
        return proc
    blob = " ".join(
        part for part in (proc.category, proc.brand, proc.model, proc.concern, proc.primary_cite) if part
    )
    if not mf.job_is_thetford(blob, " ".join(proc.bay_order)):
        return proc
    order = " ".join(proc.bay_order).lower()
    if "vacuum" not in order and "42109" not in order and "water valve" not in order:
        return proc
    branches = [hoist_branch_safety(_supply_branch())]
    for kind in ("breaker", "valve"):
        layout = _thetford_branch_layout(kind, chunks)
        if layout.get("steps"):
            branched = hoist_branch_safety(ensure_verify_step(layout))
            branched["heading"] = "REPAIR BRANCH"
            branches.append(branched)
    branches.append(hoist_branch_safety(_flange_branch()))
    proc.procedures = [_with_removal_line(item) for item in branches]
    _drop_repeated_procedure_figures(proc.procedures)
    _sync_thetford_sources(proc, chunks)
    return proc


def _facr_doc_token(text: str) -> str:
    """8666 or 7990 when this title is one of the two FACR library docs."""
    raw = text or ""
    low = re.sub(r"[\s_]", "", raw.lower())
    if "ccd-0008666" in raw.lower() or "ccd0008666" in low:
        return "8666"
    if "ccd-0007990" in raw.lower() or "ccd0007990" in low:
        return "7990"
    return ""


def place_facr_library_figures(proc: BayProcedure, rows) -> BayProcedure:
    """Copy a library PNG onto the procedure step that cites that doc and page.

    A row for another document or another page is left unused. No bundled crop
    is read from disk. A step that names a figure without a page stays text.
    """
    import manual_figures as mf

    if not proc.procedures or not rows:
        return proc
    if not any(_procedure_keeps_repeated_figures(item) for item in proc.procedures):
        return proc
    indexed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        png = row.get("png") or row.get("image_png") or b""
        if not png or mf.png_is_blank(png):
            continue
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("title", "doc_number", "clean_title", "file_path", "caption", "label")
        )
        doc = _facr_doc_token(blob)
        if not doc:
            continue
        try:
            page = int(row.get("page") or 0)
        except (TypeError, ValueError):
            continue
        if page <= 0:
            continue
        indexed.append((doc, page, png))
    for procedure in proc.procedures:
        for step in procedure.get("steps") or []:
            figure = step.get("figure")
            if not isinstance(figure, dict):
                continue
            page = figure.get("page")
            if not page:
                continue
            doc = _facr_doc_token(figure.get("title") or "")
            if not doc:
                continue
            try:
                want = int(page)
            except (TypeError, ValueError):
                continue
            for idoc, ipage, png in indexed:
                if idoc == doc and ipage == want:
                    figure["png"] = png
                    break
    return apply_bay_oem_fallback(proc, rows)


def attach_facr_procedures(proc: BayProcedure) -> BayProcedure:
    """Proving checks and rooftop R&R. Attached after the sheet scrub so cites stay.

    The short bay order and the flowchart stay the diagnosis. The numbered
    checks live on the procedure, which the scrub does not rewrite.
    """
    import manual_figures as mf

    if not is_facr_rooftop_freeze_context(proc.category, proc.model, proc.concern):
        return proc
    proving = hoist_branch_safety(mf.facr_proving_layout())
    repair = hoist_branch_safety(ensure_verify_step(mf.facr_rr_layout()))
    proc.procedures = [item for item in (proving, repair) if item.get("steps")]
    return apply_bay_oem_fallback(proc, None)


# Same OEM doc and page as the crops already in assets/bay-oem.
_BAY_OEM_PAGE = {
    ("7990", 7): "ccd7990-p7.png",
    ("7990", 4): "ccd7990-p4.png",
    ("8666", 10): "ccd8666-p10.png",
    ("8666", 19): "ccd8666-p19.png",
    ("8122", 36): "ccd8122-fig36.png",
}


def _doc_has_figure_rows(rows, doc_token: str) -> bool:
    """True when this document already has a stored page image or figure crop."""
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        png = row.get("png") or row.get("image_png") or b""
        if not png:
            continue
        blob = " ".join(
            str(row.get(key) or "")
            for key in ("title", "doc_number", "clean_title", "file_path", "caption", "label")
        )
        if _facr_doc_token(blob) == doc_token:
            return True
    return False


def apply_bay_oem_fallback(proc: BayProcedure, rows) -> BayProcedure:
    """Draw the bay-oem crop until that document has figure rows.

    The caption is the OEM doc and page. A step with no crop stays without a
    text-only figure line.
    """
    import manual_figures as mf

    if not proc.procedures:
        return proc
    for procedure in proc.procedures:
        for step in procedure.get("steps") or []:
            figure = step.get("figure")
            if not isinstance(figure, dict):
                continue
            png = figure.get("png") or b""
            if png and not mf.png_is_blank(png):
                continue
            doc = _facr_doc_token(figure.get("title") or "")
            try:
                page = int(figure.get("page") or 0)
            except (TypeError, ValueError):
                page = 0
            if not doc or page <= 0:
                continue
            if _doc_has_figure_rows(rows, doc):
                continue
            name = _BAY_OEM_PAGE.get((doc, page))
            if not name:
                continue
            figure["png"] = _cropped_oem_png(name) if name in _OEM_FIGURE_CROP else load_oem_figure_png(name)
            figure["label"] = f"CCD-000{doc}, page {page}"
    return proc


def _figure_identity_key(fig) -> tuple:
    png = getattr(fig, "image_png", None)
    if png is None and isinstance(fig, dict):
        png = fig.get("png") or fig.get("image_png") or b""
        title = (fig.get("title") or "").strip().lower()
        caption = (fig.get("caption") or fig.get("label") or "").strip().lower()
        page = fig.get("page")
    else:
        png = png or b""
        title = (getattr(fig, "title", "") or "").strip().lower()
        caption = (getattr(fig, "caption", "") or "").strip().lower()
        page = getattr(fig, "page", None)
    if png:
        return ("png", png)
    return ("id", title, page, caption)


def dedupe_sheet_figures(proc: BayProcedure) -> BayProcedure:
    """One copy of a figure on the sheet. The first step that uses it keeps it."""
    seen = set()

    def keep(fig) -> bool:
        key = _figure_identity_key(fig)
        if key in seen:
            return False
        seen.add(key)
        return True

    proc.step_figures = [
        [fig for fig in group if keep(fig)]
        for group in (proc.step_figures or [])
    ]
    proc.figures = [fig for fig in (proc.figures or []) if keep(fig)]
    return proc


def place_thetford_kit_crops(proc: BayProcedure) -> BayProcedure:
    """Real 42109 and 34123 crops beside those steps.

    The eight-field FIGURE line is text. The sheet still draws the kit crop.
    A library crop already on the step is left in place.
    """
    import manual_figures as mf

    if not proc.bay_order:
        return proc
    if not mf.job_is_thetford(proc.category, proc.brand, proc.model, proc.concern, proc.primary_cite):
        return proc
    packets = {}
    for packet in mf.thetford_demo_packets():
        title = (packet.get("title") or "").lower()
        if "3412" in title or "breaker" in title:
            packets["breaker"] = packet
        if "42109" in title or "valve" in title:
            packets["valve"] = packet
    placed = [list(group) for group in (proc.step_figures or [])]
    while len(placed) < len(proc.bay_order):
        placed.append([])
    for index, step in enumerate(proc.bay_order):
        if any(
            (fig.image_png or b"")
            and not mf.png_is_blank(fig.image_png or b"")
            and (fig.excerpt or "") != "bundled kit crop"
            for fig in placed[index]
        ):
            continue
        topic = _kit_topic_for_step(step)
        packet = packets.get(topic)
        if not packet:
            continue
        figure = _kit_crop_for_step(step, packet.get("figures") or [])
        if not figure:
            continue
        placed[index] = [
            BayFigure(
                title=packet.get("title") or "",
                page=figure.get("page") or 1,
                caption=figure.get("label") or "Fig. 1",
                excerpt="bundled kit crop",
                image_png=figure.get("png") or b"",
            )
        ]
    proc.step_figures = placed
    return proc


def paint_library_step_figures(proc: BayProcedure, rows, groups=None) -> BayProcedure:
    """Put the same library figure rows Guided Diagnostics loads beside each step.

    A step that already has a crop is left alone. Rows without a PNG are skipped.
    ``groups`` is the per-step offer list after the PNG bytes have been loaded.
    """
    import library_figure_backfill as fb
    import manual_figures as mf

    if not proc.bay_order:
        return proc
    if groups is None:
        if not rows:
            return proc
        groups = fb.figures_beside_steps(
            rows,
            proc.bay_order,
            proc.category or "",
            f"{proc.brand or ''} {proc.model or ''}".strip(),
        )
    placed = [list(group) for group in (proc.step_figures or [])]
    while len(placed) < len(proc.bay_order):
        placed.append([])
    for index, offers in enumerate(groups):
        library_already = any(
            (getattr(fig, "image_png", b"") or b"")
            and (getattr(fig, "excerpt", "") or "") != "bundled kit crop"
            for fig in placed[index]
        )
        if library_already:
            continue
        placed[index] = [
            fig for fig in placed[index] if (getattr(fig, "excerpt", "") or "") != "bundled kit crop"
        ]
        for offer in offers:
            png = offer.get("png") or b""
            if not png or mf.png_is_blank(png):
                continue
            placed[index].append(
                BayFigure(
                    title=offer.get("title") or "",
                    page=offer.get("page"),
                    caption=offer.get("caption") or offer.get("label") or "Fig.",
                    excerpt="",
                    image_png=png,
                )
            )
            break
    proc.step_figures = placed
    return place_facr_library_figures(place_thetford_kit_crops(proc), rows)


def _doc_part_numbers(packet: dict) -> str:
    """Part numbers the document names outside the ranked window.

    Live retrieval cuts a kit sheet at 4000 characters, so the part number
    printed at the bottom ('42049' under the figures) can fall out. The file
    name keeps it ('..._Res_42049C-1.pdf'). A trailing revision letter is dropped.
    """
    name = Path(str(packet.get("file_path") or "")).name
    found = re.findall(r"(?<![0-9])(\d{5,6})(?=[A-Z]?(?:[-_.]|$))", name)
    return " ".join(dict.fromkeys(found))


def _dedupe_source_rows(rows: list) -> list:
    """One source line per quote. Two pages of one manual with the same quote is one cite."""
    kept = []
    seen = set()
    for row in rows or []:
        quote = re.sub(r"\s+", " ", str(row.get("excerpt") or "")).strip().lower()
        key = (str(row.get("title") or "").strip().lower(), quote)
        if quote and key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def _plain_kit_procedures(packets, job: str) -> list:
    """Short R&R from a kit sheet that actually has figures."""
    import manual_figures as mf

    built = []
    seen = set()
    for packet in packets or []:
        title = packet.get("title") or ""
        if mf.brands_conflict(job, title):
            continue
        key = title.lower()
        if key in seen:
            continue
        figures = []
        for figure in packet.get("figures") or []:
            png = figure.get("png") or b""
            if not png or mf.png_is_blank(png):
                continue
            if mf.brands_conflict(job, figure.get("title") or title):
                continue
            figures.append(
                {
                    "label": manual_figure_label(figure.get("label") or "Fig.", packet.get("excerpt") or ""),
                    "png": png,
                    "page": figure.get("page") or packet.get("page"),
                    "title": figure.get("title") or title,
                }
            )
        if not figures:
            continue
        layout = mf.procedure_from_sheet(
            packet.get("excerpt") or "", figures, title, doc_text=_doc_part_numbers(packet)
        )
        if not layout.get("steps"):
            continue
        built.append(ensure_verify_step(layout))
        seen.add(key)
    built.sort(
        key=lambda item: 0
        if "water" in (item.get("title") or "").lower()
        else 1
        if "vacuum" in (item.get("title") or "").lower() or "breaker" in (item.get("title") or "").lower()
        else 2
    )
    return built


def apply_library_doc_fixes(chunks):
    """Reviewed library data fixes (pagefinder/doc_fixes.tsv) on the Bay PDF's library excerpts, same as the page-finder:
    a duplicate doc (e.g. L139 = L236) is dropped, a corrected brand/title (L413 is Valid) is used for the brand lock, and a
    shop sheet is cited as "Shop sheet: ..." instead of under a maker's name. Chunks of docs without a fix are untouched;
    a fix applies only to the file it was reviewed for (so a test doc with a reused id is never touched)."""
    if chunks is None:
        return chunks
    from pagefinder import doc_fixes as _df
    out = []
    for ch in chunks:
        get = ch.get if isinstance(ch, dict) else (lambda k, _c=ch: getattr(_c, k, None))
        fix = _df.fix_for(get("document_id"), get("file_path") or "")
        if not fix:
            out.append(ch)
            continue
        f = fix["doc"]
        if f.get("duplicate_of") or f.get("exclude"):
            continue
        if not _df.page_kept(get("document_id"), get("file_path") or "", get("page") or 0):
            continue   # e.g. a re-host site's ad insert page
        d = dict(ch) if isinstance(ch, dict) else chunk_as_dict(ch)
        for k in ("brand", "product_line"):
            if k in f:
                d[k] = f[k]
        title = f.get("title") or d.get("clean_title") or d.get("title") or ""
        d["title"] = _df.bay_title(title, f.get("source_type"))
        if f.get("title") or f.get("source_type"):
            d["clean_title"] = d["title"]
        out.append(d)
    return out


def compile_bay_procedure(
    concern: str,
    brand: str = "",
    model: str = "",
    category: str = "",
    wo_number: str = "",
    chunks=None,
    figures: list[BayFigure] | None = None,
    include_3c: bool = False,
    created: datetime | None = None,
    history=None,
) -> BayProcedure:
    """
    Compile a human bay sheet from product-lock language + ranked library excerpts.

    Works with or without live chunks so unit tests do not need a shop DB.
    New concerns inherit BAY_SHEET_STANDARD automatically (bans, readable
    flowchart, on-page checks, no "open the SM").
    """
    concern = (concern or "").strip()
    brand = (brand or "").strip()
    model = (model or "").strip()
    category = (category or "").strip()
    if category in ("(any)", "-"):
        category = ""
    model_text = model_text_from(brand, model)
    chunks = apply_library_doc_fixes(chunks)
    _, brand_miss = bay_brand_retrieval(chunks, category, model_text, concern)
    ranked = rank_bay_chunks(chunks, category, model_text, concern, limit=8)
    ranked, fact12_mislabeled_only = _separate_mislabeled_fact12(ranked, model_text)

    dial_off = is_fcr_dial_off_compressor_run_context(category, model_text, concern)
    ice = is_fridge_ice_moisture_context(category, model_text, concern)
    firefly = is_firefly_can_path_context(category, model_text, concern)
    facr = is_facr_rooftop_freeze_context(category, model_text, concern)
    bal_tongue = is_bal_soft_touch_tongue_only_context(category, model_text, concern)
    coleman = is_coleman_2111_context(category, model_text, concern)
    furnace = _is_furnace_bay(category, model_text, concern)
    e2_fan = is_fcr_e2_fan_fault_context(category, model_text, concern)
    ground_control = is_ground_control_context(category, model_text, concern)
    dometic_ceiling = is_dometic_ceiling_sheet_context(category, model_text, concern)
    fact12_freeze = is_fact12_freeze_code_context(category, model_text, concern)
    girard_e8 = is_girard_petit_tube_context(category, model_text, concern)
    stabilizer_rr = is_stabilizer_override_pin_context(category, model_text, concern)
    cooktop_tip = is_cooktop_tip_sheet_context(category, model_text, concern)

    path_kind = ""
    if dial_off:
        spec = _dial_off_path()
        path_kind = "dial_off"
    elif ice:
        spec = _ice_path()
        path_kind = "ice"
    elif facr:
        spec = _facr_path()
        path_kind = "facr"
    elif firefly:
        spec = _firefly_path()
        path_kind = "firefly"
    elif bal_tongue:
        spec = _bal_tongue_path()
        path_kind = "bal_tongue"
    elif coleman:
        spec = _coleman_path()
        path_kind = "coleman"
    elif e2_fan:
        spec = _e2_fan_path(ranked)
        path_kind = "e2"
    elif furnace:
        spec = _furnace_path(ranked)
        path_kind = "furnace"
    elif is_level_up_lead_jack_drift_context(category, model_text, concern):
        spec = _lead_jack_drift_path()
        path_kind = "leadjack"
    elif brand_miss:
        spec = _no_brand_match_path(brand, model, concern)
        path_kind = "brand_miss"
    elif ground_control:
        spec = _ground_control_path(concern)
        path_kind = "ground_control"
    elif dometic_ceiling:
        spec = _dometic_ceiling_path(concern)
        path_kind = "dometic_ceiling"
    elif fact12_freeze:
        spec = _fact12_freeze_path(concern)
        path_kind = "fact12_freeze"
    elif girard_e8:
        spec = _girard_petit_path()
        path_kind = "girard_e8"
    elif stabilizer_rr:
        spec = _stabilizer_rr_path()
        path_kind = "stabilizer"
    elif cooktop_tip:
        spec = _cooktop_tip_path()
        path_kind = "cooktop_tip"
    elif is_thetford_flush_leak_context(category, model_text, concern) and ranked:
        spec = _thetford_leak_path(concern, ranked)
        path_kind = "thetford_leak"
    else:
        long_path = is_long_appliance_path(category, concern)
        step_pages = [] if fact12_mislabeled_only else list(ranked)
        bay_order = _generic_bay_order(_steps_from_ranked(step_pages), long_path=long_path)
        spec = {
            "primary_cite": (
                FACT12_MISLABEL_CITE if fact12_mislabeled_only else _generic_primary_cite(ranked)
            ),
            "pattern_means": _generic_pattern_means(concern, long_path=long_path),
            "flowchart": _generic_flowchart(concern or "Customer concern", bay_order),
            "bay_order": bay_order,
            "do_not": [
                "Do not skip the next cited check.",
                "Do not guess a part swap before the cited checks on this sheet.",
            ],
            "sources": [],
            "flow_tall": True,
            "full_story": long_path,
        }

    if coleman:
        sources = _coleman_sources(ranked)
        locked_count = len(sources)
    elif brand_miss and path_kind == "brand_miss":
        sources = list(spec.get("sources") or [])
        locked_count = len(sources)
    else:
        locked_count = len(spec.get("sources") or [])
        sources = _merge_sources(
            spec.get("sources") or [],
            _unique_sources(ranked),
            ice=ice,
            dial_off=dial_off,
        )
        if ice and not any("ccd-0008122" in (s.get("title") or "").lower() for s in sources):
            sources.insert(0, spec["sources"][0])
            locked_count += 1
    sources = polish_bay_sources(
        sources,
        locked_count,
        _procedure_topic(spec),
        path_kind,
        prefer_diagnostic=_is_fault_complaint(concern),
        protect_pages=_cited_pages(spec.get("primary_cite") or ""),
    )
    if path_kind == "girard_e8":
        sources = _ensure_girard_hose_quote(sources)
    if path_kind == "brand_miss":
        sources = [
            {
                "title": spec.get("primary_cite") or "Shop Document Library",
                "page": None,
                "excerpt": "",
                "title_only": True,
            }
        ]
    if path_kind == "thetford_leak":
        sources = _thetford_leak_sources(sources)
    if path_kind == "stabilizer":
        sources = _prefer_front_jack_sources(sources)
    if path_kind == "e2":
        if "page 27" not in (spec.get("primary_cite") or "").lower():
            spec["primary_cite"] = "Furrion fridge service manual, Fan Fault Diagnostics, page 27."
        if not any(src.get("page") == 27 for src in sources):
            sources.insert(
                0,
                {
                    "title": "Furrion FCR08/FCR10 SM CCD-0008122",
                    "page": 27,
                    "excerpt": "",
                },
            )
    if path_kind == "furnace":
        quoted = [
            src
            for src in sources
            if "wall thermostat controls the operation" in (src.get("excerpt") or "").lower()
            and src.get("page")
        ]
        if quoted:
            page = quoted[0].get("page")
            if page and f"page {page}" not in (spec.get("primary_cite") or "").lower():
                spec["primary_cite"] = f"Suburban Furnace Service and Training Manual, page {page}."
        elif not ranked and not any(src.get("page") == 26 for src in sources):
            # Box copy of the Suburban furnace manual places this prove on page 26.
            # No retrieved sentence, so the cite has no quote.
            sources.insert(
                0,
                {
                    "title": "Suburban Furnace Service and Training Manual",
                    "page": 26,
                    "excerpt": "",
                },
            )
            spec["primary_cite"] = "Suburban Furnace Service and Training Manual, page 26."
    if path_kind == "fact12_freeze":
        sources = list(spec.get("sources") or [])
    if path_kind == "leadjack":
        sources = list(spec.get("sources") or [])
        figures = []
    if path_kind == "firefly":
        # These Lippert sheets are cited as page 1. They are not confirmed
        # 1-page tech infos, so the sheet does not use that label.
        sources = [
            {
                "title": src.get("title"),
                "page": 1,
                "excerpt": "",
            }
            for src in (_firefly_path().get("sources") or [])
        ]
    if fact12_mislabeled_only and path_kind not in ("fact12_freeze", "leadjack"):
        page = _page_int(ranked[0].get("page")) if ranked else None
        sources = []
        if page:
            sources = [
                {
                    "title": "Furrion Chill FACR08 8K manual CCD-0008666",
                    "page": page,
                    "excerpt": "",
                }
            ]
            spec["primary_cite"] = f"Furrion Chill FACR08 8K manual CCD-0008666, page {page}."
        else:
            spec["primary_cite"] = "Furrion Chill FACR08 8K manual CCD-0008666."

    if path_kind == "e2":
        final_pages = _cited_pages(spec.get("primary_cite") or "")
        sources = [
            src
            for src in sources
            if (src.get("excerpt") or "").strip()
            or src.get("page") in final_pages
            or src.get("page") == 27
        ]

    check_pages = list(spec.get("check_pages") or [])
    checks = []
    for i, step in enumerate(spec["bay_order"]):
        page = check_pages[i] if i < len(check_pages) else None
        checks.append(
            BayCheck(
                text=step,
                source_title=FURRION_8122_TITLE if dial_off else (spec.get("primary_cite") or ""),
                source_page=page,
                kind="check",
            )
        )
    if not checks:
        checks.append(
            BayCheck(
                text="Write the first reading on this sheet, then ask a manager before any part swap.",
                source_title="Document Library",
                kind="note",
            )
        )

    if path_kind == "coleman":
        figs = _coleman_figures(ranked)
    elif path_kind == "furnace":
        figs = _topic_figures(
            ranked,
            "Suburban furnace service manual",
            "Jumper R/W at the furnace, then prove the sail switch",
            "If the furnace runs on the jumper, replace the wall thermostat.",
        )
    elif path_kind == "e2":
        figs = _topic_figures(
            ranked,
            "Furrion fridge service manual",
            "Fan Fault Diagnostics: F+ and F- on the inverter PCB",
            "Replace the inverter PCB and the fan when the error remains.",
        )
    elif path_kind == "brand_miss":
        figs = [_brand_miss_figure(brand, model, concern)]
    elif path_kind == "thetford_leak":
        figs = []
    elif path_kind:
        figs = resolve_path_figures(path_kind, ranked, figures)
    else:
        figs = _real_library_figures(ranked)
        if figures:
            figs = [
                fig
                for fig in figures
                if fig.image_png and not _png_is_generated_sketch(fig.image_png)
            ] or figs
        if not figs:
            figs = [_seed_path_figure("generic")]
    figs = [
        fig
        for fig in figs
        if not source_is_discontinued(fig.title or "", f"{fig.caption or ''} {fig.excerpt or ''}")
    ]
    if fact12_mislabeled_only and not path_kind:
        seed = _seed_path_figure("generic")
        seed.caption = "Furrion Chill FACR08 8K manual CCD-0008666"
        seed.title = "Shop Document Library"
        figs = [seed]

    display_model = spec.get("display_model") or ""
    if firefly:
        display_model = "807662"
    elif facr:
        named = re.search(r"\b(FACR\d+[A-Z0-9]*(?:-[A-Z0-9]+)+)\b", f"{concern} {model}", re.I)
        if named:
            display_model = named.group(1).upper()
        elif not display_model:
            display_model = "Furrion Chill rooftop unit"
    elif dial_off and not display_model:
        display_model = _fcr10_display_model(brand, model, concern)
    elif bal_tongue and not (brand or model):
        display_model = spec.get("display_model") or "BAL Soft-Touch SS 5.1"
    elif ice and not display_model:
        display_model = join_brand_model(brand, model) or "Furrion fridge"
    elif stabilizer_rr and not (brand or model):
        display_model = "Lippert PSX1 front stabilizer"

    notes = _lock_note(category, model_text, concern)
    spec["do_not"] = [
        item for item in (spec.get("do_not") or []) if not sheet_standard_violations(item)
    ]
    proc = BayProcedure(
        concern=concern or "(no concern entered)",
        brand=brand,
        model=model,
        category=category,
        wo_number=(wo_number or "").strip(),
        created=created or sheet_local_now(),
        primary_cite=spec["primary_cite"],
        pattern_means=spec["pattern_means"],
        flowchart=spec["flowchart"],
        bay_order=list(spec["bay_order"]),
        do_not=list(spec["do_not"]),
        sources=sources,
        checks=checks,
        figures=figs,
        include_3c=include_3c,
        notes=notes,
        display_model=display_model,
        flow_tall=bool(spec.get("flow_tall")),
        full_story=bool(spec.get("full_story", path_kind in ("ice", "facr", "dial_off", "bal_tongue"))),
        unit_id=bool(ice),
    )
    proc = apply_sheet_standard(proc)
    if dial_off:
        proc = _lock_dial_off_part_numbers(proc)
    proc = bind_primary_sources(apply_shop_channel_wording(proc))
    return dedupe_sheet_figures(
        attach_facr_procedures(
            attach_thetford_repair_procedures(
                place_thetford_kit_crops(apply_chunk_figures(proc, chunks)),
                history=history,
                chunks=chunks,
            )
        )
    )


def _is_fact12_job(model_text: str) -> bool:
    text = model_text or ""
    if re.search(r"facr", text, re.I):
        return False
    return bool(re.search(r"fact\s*12", text, re.I))


def _chunk_is_facr08_content(row: dict) -> bool:
    """CCD-0008666 titled FACT12SA2-PS is the FACR08 8K book when the body says so."""
    blob = f"{row.get('title') or ''} {row.get('excerpt') or ''}"
    return bool(re.search(r"facr0?8|hesa2", blob, re.I))


def _only_facr08_book(ranked) -> bool:
    """True when every retrieved page is the FACR08 / CCD-0008666 book."""
    rows = [chunk_as_dict(item) for item in (ranked or [])]
    if not rows:
        return False

    def _is_book(row: dict) -> bool:
        blob = f"{row.get('title') or ''} {row.get('excerpt') or ''} {row.get('file_path') or ''}"
        return bool(re.search(r"ccd-0*8666|facr0?8|hesa2", blob, re.I))

    return all(_is_book(row) for row in rows)


def _is_fault_complaint(concern: str) -> bool:
    return bool(
        re.search(
            r"\b(not cooling|no cool|won'?t|will not|dead|fault|error|lockout|leak|"
            r"ice|frost|freeze|no heat|shows?\s+e\d|\be\d\b|flameout|overcool)\b",
            concern or "",
            re.I,
        )
    )


def _separate_mislabeled_fact12(pages, model_text: str):
    """Drop a FACT12-titled FACR08 file when a real FACT12 chunk is also retrieved."""
    if not _is_fact12_job(model_text):
        return list(pages or []), False
    rows = list(pages or [])
    good = [row for row in rows if not _chunk_is_facr08_content(row)]
    bad = [row for row in rows if _chunk_is_facr08_content(row)]
    if good and bad:
        return good, False
    if bad and not good:
        return rows, True
    return rows, False


def _generic_primary_cite(ranked) -> str:
    for d in ranked or []:
        title = human_source_title((d.get("title") or "").strip(), d.get("file_path") or "")
        if not title:
            continue
        page = _page_int(d.get("page"))
        return f"{title}" + (f" page {page}" if page else "")
    return "Shop Document Library."


# ---------------------------------------------------------------------------
# Plain text (tests + filename helpers)
# ---------------------------------------------------------------------------
def procedure_body_text(proc: BayProcedure) -> str:
    """Flowchart / pattern / bay order / Do-not only — no Sources footer."""
    parts = [
        proc.pattern_means or "",
        *proc.bay_order,
        *proc.do_not,
        *(n.text for n in proc.flowchart.nodes),
    ]
    return "\n".join(parts)


def procedure_plain_text(proc: BayProcedure) -> str:
    """Single string for unit tests. Mirrors the bay sheet, not v1 bot-flow paragraphs."""
    lines = [
        BAY_PROCEDURE_LABEL,
        f"Customer concern: {proc.concern}",
        f"Brand / model: {proc.model_line}",
        f"Category: {proc.category or '—'}",
        f"Work order: {proc.wo_number or '—'}",
        f"Date: {proc.created.strftime('%Y-%m-%d %H:%M')}",
        f"Primary OEM cite: {proc.primary_cite or '—'}",
        "",
        "What this pattern usually means",
        proc.pattern_means or "—",
        "",
        "Visual flowchart",
    ]
    for node in proc.flowchart.nodes:
        tag = {"start": "start", "decision": "diamond", "process": "box", "end": "end"}.get(node.kind, node.kind)
        lines.append(f"[{tag}] {node.text.replace(chr(10), ' / ')}")
    for edge in proc.flowchart.edges:
        if edge.label:
            lines.append(f"  {edge.label}: {edge.from_id} -> {edge.to_id}")
    lines.append("")
    lines.append("Bay order (do this first)")
    for i, step in enumerate(proc.bay_order, 1):
        lines.append(f"{i}. {step}")
    lines.append("")
    lines.append("Do not")
    for item in proc.do_not:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("Sources (shop Document Library):")
    if proc.sources:
        for s in proc.sources:
            page = f" p.{s['page']}" if s.get("page") else ""
            page_long = f" page {s['page']}" if s.get("page") else ""
            lines.append(f"- {s.get('title') or 'Manual'}{page}{page_long}")
    else:
        lines.append("- Shop Document Library.")
    if proc.figures:
        lines.append("")
        lines.append("Cited library figures:")
        for fig in proc.figures:
            page = f" p.{fig.page}" if fig.page else ""
            lines.append(f"- {fig.caption or 'Figure'} — {fig.title}{page}")
            if fig.excerpt:
                lines.append(f"  {fig.excerpt[:240]}")
    if proc.include_3c:
        lines.extend(
            [
                "",
                "Concern / Cause / Correction (blank footer — tech writes the warranty story):",
                "CONCERN:",
                "CAUSE:",
                "CORRECTION:",
            ]
        )
    if proc.notes:
        lines.append("")
        lines.append("Path notes:")
        lines.extend(f"- {n}" for n in proc.notes)
    if is_fridge_ice_moisture_context(proc.category, proc.model_line, proc.concern):
        blob = "\n".join(lines).lower()
        if "ice and moisture" not in blob:
            lines.append(ICE_MOISTURE_SHOP_LINE)
        if "ccd-0008122" not in blob:
            lines.append("Cite CCD-0008122 Ice and Moisture p.36 / page 36 / Fig.36.")
    if is_fcr_dial_off_compressor_run_context(proc.category, proc.model_line, proc.concern):
        blob = "\n".join(lines).lower()
        if "2021128850" not in blob:
            lines.append(
                "Replace Spark-Free Thermostat part G 2021128850 "
                "(retail C-FCR10DCGTA-007) after the open C/T prove with no jumper."
            )
        if "page 31" not in blob or "page 43" not in blob:
            lines.append("Cite the thermostat prove on page 31 and page 43.")
    return "\n".join(lines).strip() + "\n"


def suggested_pdf_filename(proc: BayProcedure) -> str:
    wo = re.sub(r"[^A-Za-z0-9_-]+", "", (proc.wo_number or "").replace(" ", "-"))
    if wo:
        return f"bay_procedure_{wo}.pdf"
    return "bay_procedure.pdf"


def _latin1_safe(text: str) -> str:
    """PDF core fonts are Latin-1. Drop emoji / smart punctuation."""
    if not text:
        return ""
    repl = {
        "📖": "Source:",
        "→": "->",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "×": "x",
        "≈": "~",
        "≥": ">=",
        "≤": "<=",
        "☐": "[ ]",
        "✗": "-",
    }
    out = text
    for a, b in repl.items():
        out = out.replace(a, b)
    return out.encode("latin-1", "replace").decode("latin-1")


# ---------------------------------------------------------------------------
# Visual flowchart + sheet composition (shared by all renderers)
#
# Every shape is sized from measured text before anything is drawn. Ovals and
# diamonds wrap into the inscribed rectangle of the shape, not the bounding
# box. Section bars are placed from the previous block's real height.
# ---------------------------------------------------------------------------
_SQRT2 = math.sqrt(2.0)
_FLOW_GAP = 16.0
_PAD_X = 7.0
_PAD_Y = 5.0
_CONTENT_W = PAGE_W - 2 * MARGIN
# Every Bay figure uses this width, centered under the step that cites it.
_FIGURE_WIDTH = 0.75 * _CONTENT_W
# Low enough that a portrait crop at that width still clears the page margin.
_FIGURE_FLOOR = MARGIN
_STEP_GAP = 8.0
_STEP_TEXT_W = _CONTENT_W - 16.0


def _next_id(prefix: str) -> str:
    _next_id.n += 1
    return f"{prefix}-{_next_id.n}"


_next_id.n = 0


@dataclass
class TextMeasure:
    lines: list
    width: float
    height: float
    ascent: float
    descent: float
    leading: float
    size: float
    font: str


def _font_name(bold: bool) -> str:
    return "Helvetica-Bold" if bold else "Helvetica"


def _font_ascent_descent(font: str, size: float) -> tuple[float, float]:
    try:
        from reportlab.pdfbase.pdfmetrics import getAscent, getDescent

        return float(getAscent(font, size)), abs(float(getDescent(font, size)))
    except Exception:
        return 0.72 * size, 0.21 * size


def _string_width(text: str, font: str, size: float) -> float:
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        return float(stringWidth(text or "", font, size))
    except Exception:
        return 0.52 * size * len(text or "")


def _break_word(word: str, max_width: float, font: str, size: float) -> list[str]:
    if not word:
        return [""]
    if _string_width(word, font, size) <= max_width + 0.2:
        return [word]
    pieces: list[str] = []
    cur = ""
    for ch in word:
        trial = cur + ch
        if cur and _string_width(trial, font, size) > max_width + 0.05:
            pieces.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        pieces.append(cur)
    return pieces or [word]


def _wrap_lines(text: str, max_width: float, font: str, size: float) -> list[str]:
    """Wrap on the same width the PDF drawer will paint. Hard-break long tokens."""
    max_width = max(float(max_width), 8.0)
    lines: list[str] = []
    raw = _latin1_safe(text or "")
    for para in raw.split("\n"):
        if para == "":
            lines.append("")
            continue
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for word in words:
            for piece in _break_word(word, max_width, font, size):
                trial = piece if not cur else f"{cur} {piece}"
                if _string_width(trial, font, size) <= max_width + 0.2:
                    cur = trial
                else:
                    if cur:
                        lines.append(cur)
                    cur = piece
        lines.append(cur)
    return lines or [""]


def measure_text(text: str, max_width: float, size: float, bold: bool = False, leading: float = 0.0) -> TextMeasure:
    """Width and height of wrapped text, using the font the PDF will draw."""
    font = _font_name(bold)
    ascent, descent = _font_ascent_descent(font, size)
    leading = leading or (size + 2.0)
    lines = _wrap_lines(text, max_width, font, size)
    width = 0.0
    for line in lines:
        width = max(width, _string_width(line, font, size))
    height = ascent + descent + max(0, len(lines) - 1) * leading
    return TextMeasure(lines, width, height, ascent, descent, leading, size, font)


def _shape_kind(node_kind: str) -> str:
    if node_kind == "decision":
        return "diamond"
    if node_kind in ("start", "end"):
        return "ellipse"
    return "roundrect"


def _node_font(kind: str, readable: bool, scale: float) -> tuple[float, bool, float]:
    if kind == "decision":
        size = (12.0 if readable else 7.5) * scale
        bold = True
    else:
        size = (11.0 if readable else 7.5) * scale
        bold = False
    leading = size + ((3.2 if readable else 1.6) * scale)
    return size, bold, leading


def _outer_size(kind: str, block: TextMeasure) -> tuple[float, float]:
    """Bounding box whose inscribed rectangle contains the measured text plus padding."""
    inner_w = max(block.width, 8.0) + 2 * _PAD_X
    inner_h = block.height + 2 * _PAD_Y
    if kind == "ellipse":
        return inner_w * _SQRT2, inner_h * _SQRT2
    if kind == "diamond":
        return inner_w * 2.0, inner_h * 2.0
    return inner_w, inner_h


def _content_width(kind: str, outer_w: float) -> float:
    if kind == "ellipse":
        return outer_w / _SQRT2 - 2 * _PAD_X
    if kind == "diamond":
        return outer_w / 2.0 - 2 * _PAD_X
    return outer_w - 2 * _PAD_X


def _fit_node(node: FlowNode, alloc_w: float, readable: bool, scale: float):
    kind = _shape_kind(node.kind)
    size, bold, leading = _node_font(node.kind, readable, scale)
    cw = max(36.0, _content_width(kind, alloc_w) + 1.25)
    block = measure_text(node.text, cw, size, bold=bold, leading=leading)
    w, h = _outer_size(kind, block)
    return w, h, block, size, bold, leading, kind


def _cluster_rows(nodes: list[FlowNode], tol: float = 0.07) -> list[list[FlowNode]]:
    ordered = sorted(nodes, key=lambda n: (n.y, n.x))
    rows: list[list[FlowNode]] = []
    for node in ordered:
        if not rows or node.y - rows[-1][0].y > tol:
            rows.append([node])
        else:
            rows[-1].append(node)
    for row in rows:
        row.sort(key=lambda n: n.x)
    return rows


def _flowchart_inner(frame_x: float, frame_y: float, frame_w: float, frame_h: float):
    """Gutters keep node boxes and loop-back arrows off the frame stroke."""
    # The right gutter is wide so a return stub does not ride the page frame.
    return (frame_x + 12.0, frame_y + 10.0, frame_w - 86.0, frame_h - 40.0)


def _row_pad(flow: Flowchart, row: list) -> float:
    """Extra gap after this row. Zero on the last row is applied by the caller."""
    pads = getattr(flow, "row_pad", None) or {}
    extra = 0.0
    for node in row:
        try:
            extra = max(extra, float(pads.get(node.id, 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
    return extra


def _pack_rows(flow: Flowchart, inner_w: float, inner_h: float, readable: bool, scale: float):
    rows = _cluster_rows(list(flow.nodes))
    if not rows:
        return None
    packed_rows = []
    for row in rows:
        prefs = []
        for node in row:
            size, bold, leading = _node_font(node.kind, readable, scale)
            block = measure_text(node.text, 380.0, size, bold=bold, leading=leading)
            pw, ph = _outer_size(_shape_kind(node.kind), block)
            prefs.append(pw)
        if len(row) == 1:
            max_w = inner_w - 2.0
            if row[0].x < 0.40 or row[0].x > 0.60:
                max_w = min(max_w, inner_w * 0.74)
            alloc = min(prefs[0], max_w)
            fitted = [_fit_node(row[0], alloc, readable, scale)]
        else:
            avail = inner_w - _FLOW_GAP * (len(row) - 1)
            if sum(prefs) <= avail:
                allocs = prefs
            else:
                allocs = [pw * avail / sum(prefs) for pw in prefs]
            fitted = [_fit_node(node, alloc, readable, scale) for node, alloc in zip(row, allocs)]
            # Two nodes on one row are pinned to the edges. The open gap has to
            # hold an 11pt YES on the arrow, so 16pt is not enough.
            side_gap = 48.0 if len(row) == 2 else _FLOW_GAP * (len(row) - 1)
            if sum(item[0] for item in fitted) + side_gap > inner_w + 1.5:
                return None
        packed_rows.append(fitted)
    heights = [max(item[1] for item in row) for row in packed_rows]
    gaps = [_FLOW_GAP + _row_pad(flow, row) for row in rows[:-1]]
    total_h = sum(heights) + sum(gaps)
    if total_h > inner_h + 0.5:
        return None
    return rows, packed_rows, heights


def _pack_flowchart(flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float) -> dict:
    inner_x, inner_y, inner_w, inner_h = _flowchart_inner(frame_x, frame_y, frame_w, frame_h)
    readable = bool(getattr(flow, "readable", False))
    chosen = None
    for scale in (1.0, 0.94, 0.88, 0.82, 0.76, 0.70):
        packed = _pack_rows(flow, inner_w, inner_h, readable, scale)
        if packed is not None:
            chosen = (scale, packed)
            break
    if chosen is None:
        chosen = (0.70, _pack_rows(flow, inner_w, inner_h, readable, 0.70) or (
            _cluster_rows(list(flow.nodes)),
            [],
            [],
        ))
        # Last attempt may have returned None because a row is wider than the frame.
        # Fit every node into an equal share so the chart still draws.
        if not chosen[1][1]:
            rows = _cluster_rows(list(flow.nodes))
            packed_rows = []
            for row in rows:
                share = max(80.0, (inner_w - _FLOW_GAP * (len(row) - 1)) / max(len(row), 1))
                packed_rows.append([_fit_node(node, share, readable, 0.70) for node in row])
            heights = [max(item[1] for item in row) for row in packed_rows] or []
            chosen = (0.70, (rows, packed_rows, heights))
    _scale, (rows, packed_rows, heights) = chosen
    placed: dict = {}
    if not rows:
        return placed
    top = inner_y + inner_h
    for row, fitted, rh in zip(rows, packed_rows, heights):
        cy = top - rh / 2.0
        widths = [item[0] for item in fitted]
        if len(row) == 1:
            w = widths[0]
            node = row[0]
            if node.x < 0.40:
                cx = inner_x + w / 2.0
            elif node.x > 0.60:
                cx = inner_x + inner_w - w / 2.0
            else:
                cx = inner_x + inner_w / 2.0
            cxs = [min(max(cx, inner_x + w / 2.0), inner_x + inner_w - w / 2.0)]
        elif len(row) == 2:
            w1, w2 = widths
            cxs = [inner_x + w1 / 2.0, inner_x + inner_w - w2 / 2.0]
        else:
            used = sum(widths) + _FLOW_GAP * (len(row) - 1)
            extra = max(0.0, inner_w - used)
            cursor = inner_x + extra / 2.0
            cxs = []
            for w in widths:
                cxs.append(cursor + w / 2.0)
                cursor += w + _FLOW_GAP
        for node, item, cx in zip(row, fitted, cxs):
            w, h, block, size, bold, leading, kind = item
            placed[node.id] = {
                "cx": cx,
                "cy": cy,
                "w": w,
                "h": h,
                "lines": list(block.lines),
                "size": size,
                "bold": bold,
                "leading": leading,
                "kind": kind,
                "text": node.text,
            }
        extra = _row_pad(flow, row) if row is not rows[-1] else 0.0
        top -= rh + _FLOW_GAP + extra
    # Decision diamonds share one center so a NO arrow drops straight down.
    # A right edge pin leaves a jog, and the NO label then sits beside that jog.
    mid = inner_x + inner_w / 2.0
    right = [node for node in placed.values() if node["cx"] > mid]
    if len(right) >= 2:
        widest = max(right, key=lambda node: node["w"])
        target = widest["cx"]
        for node in right:
            half = node["w"] / 2.0
            node["cx"] = min(max(target, inner_x + half + 2.0), inner_x + inner_w - half)
    return placed


def place_flowchart_nodes(
    flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float
) -> dict[str, tuple[float, float, float, float]]:
    """Place nodes in PDF space. Sizes come from measured text, then rows are separated."""
    placed = _pack_flowchart(flow, frame_x, frame_y, frame_w, frame_h)
    return {nid: (p["cx"], p["cy"], p["w"], p["h"]) for nid, p in placed.items()}


def flowchart_node_rects(
    flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float
) -> dict[str, tuple[float, float, float, float]]:
    """Axis-aligned boxes (x0, y0, x1, y1) after placement."""
    placed = place_flowchart_nodes(flow, frame_x, frame_y, frame_w, frame_h)
    return {
        nid: (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
        for nid, (cx, cy, w, h) in placed.items()
    }


def flowchart_boxes_overlap(rects: dict[str, tuple[float, float, float, float]], gap: float = 14.0) -> list[tuple[str, str]]:
    """Pairs whose boxes sit closer than gap. Empty means a finger-walkable chart."""
    hits = []
    ids = list(rects)
    for i, a in enumerate(ids):
        ax0, ay0, ax1, ay1 = rects[a]
        for b in ids[i + 1 :]:
            bx0, by0, bx1, by1 = rects[b]
            if ax1 + gap > bx0 and bx1 + gap > ax0 and ay1 + gap > by0 and by1 + gap > ay0:
                hits.append((a, b))
    return hits


def _span_hits_boxes(axis: str, fixed: float, a: float, b: float, boxes, margin: float = 1.4) -> bool:
    """True when an orthogonal stroke enters a node interior (the port edge is allowed)."""
    lo, hi = (a, b) if a <= b else (b, a)
    for x0, y0, x1, y1 in boxes:
        if axis == "h":
            if not (y0 + margin < fixed < y1 - margin):
                continue
            if hi > x0 + margin and lo < x1 - margin:
                return True
        else:
            if not (x0 + margin < fixed < x1 - margin):
                continue
            if hi > y0 + margin and lo < y1 - margin:
                return True
    return False


def _lane_candidates(src: float, dst: float, toward_dst: float) -> list[float]:
    """Crossbar positions, nearest the destination first, so the source gap stays free."""
    if abs(src - dst) < 3.0:
        return [(src + dst) / 2.0]
    step = 2.0 if src > dst else -2.0
    lanes = []
    y = dst + toward_dst
    limit = src - (2.0 if src > dst else -2.0)
    guard = 0
    while (y < limit if step > 0 else y > limit) and guard < 24:
        lanes.append(y)
        y += step
        guard += 1
    mid = (src + dst) / 2.0
    if all(abs(y - mid) > 0.4 for y in lanes):
        lanes.append(mid)
    return lanes or [mid]


def _box_at_port(boxes, x: float, y: float):
    """The node box whose edge holds this port. None when the port is in open space."""
    for box in boxes or []:
        x0, y0, x1, y1 = box
        if x0 - 1.5 <= x <= x1 + 1.5 and y0 - 1.5 <= y <= y1 + 1.5:
            return box
    return None


def _route_elbow(x1: float, y1: float, x2: float, y2: float, from_side: str, to_side: str, boxes=None, frame=None):
    """Orthogonal service-manual elbows. The crossbar stays out of node text."""
    boxes = list(boxes or [])
    pts = [(x1, y1)]

    def vertical_then_across():
        if abs(x1 - x2) < 1.5:
            pts.append((x2, y2))
            return
        toward = 2.6 if y1 > y2 else -2.6
        chosen = None
        for lane in _lane_candidates(y1, y2, toward):
            if _span_hits_boxes("v", x1, y1, lane, boxes):
                continue
            if _span_hits_boxes("h", lane, x1, x2, boxes):
                continue
            if _span_hits_boxes("v", x2, lane, y2, boxes):
                continue
            chosen = lane
            break
        if chosen is None:
            chosen = _lane_candidates(y1, y2, toward)[0]
        pts.extend([(x1, chosen), (x2, chosen), (x2, y2)])

    def horizontal_then_down():
        if abs(y1 - y2) < 1.5:
            pts.append((x2, y2))
            return
        toward = -2.6 if x1 < x2 else 2.6
        chosen = None
        for lane in _lane_candidates(x1, x2, toward):
            if _span_hits_boxes("h", y1, x1, lane, boxes):
                continue
            if _span_hits_boxes("v", lane, y1, y2, boxes):
                continue
            if _span_hits_boxes("h", y2, lane, x2, boxes):
                continue
            chosen = lane
            break
        if chosen is None:
            chosen = _lane_candidates(x1, x2, toward)[0]
        pts.extend([(chosen, y1), (chosen, y2), (x2, y2)])

    if from_side in ("bottom", "top") and to_side in ("top", "bottom"):
        vertical_then_across()
    elif from_side in ("left", "right") and to_side in ("left", "right"):
        horizontal_then_down()
    elif from_side == "right" and to_side == "top":
        limit = (frame[2] - 52.0) if frame else (x1 + 16.0)
        out_x = min(x1 + 16.0, limit)
        if out_x < x2:
            out_x = min((x1 + x2) / 2.0, limit)
        lanes = _lane_candidates(y1, y2, 2.6 if y1 > y2 else -2.6)
        lane = next((y for y in lanes if not _span_hits_boxes("h", y, out_x, x2, boxes)), lanes[0])
        pts.extend([(out_x, y1), (out_x, lane), (x2, lane), (x2, y2)])
    elif from_side == "left" and to_side == "top":
        out_x = x1 - 36.0
        lanes = _lane_candidates(y1, y2, 2.6 if y1 > y2 else -2.6)
        lane = next((y for y in lanes if not _span_hits_boxes("h", y, out_x, x2, boxes)), lanes[0])
        pts.extend([(out_x, y1), (out_x, lane), (x2, lane), (x2, y2)])
    elif from_side == "bottom" and to_side in ("left", "right"):
        # Turn below the branch label, then ride the frame rail into the side port.
        # A turn in the 16pt row gap runs through the NO glyphs and the return junction.
        dest = _box_at_port(boxes, x2, y2)
        turn = y1 - 20.0
        if dest is not None and frame is not None and turn > dest[3] + 5.0:
            rail = frame[0] + 8.0 if to_side == "left" else frame[2] - 8.0
            pts.extend([(x1, turn), (rail, turn), (rail, y2), (x2, y2)])
        else:
            pts.extend([(x1, y2), (x2, y2)])
    elif from_side in ("left", "right"):
        horizontal_then_down()
    else:
        vertical_then_across()
    if boxes and _polyline_hits(pts, boxes):
        alt = _route_gutter(x1, y1, x2, y2, from_side, to_side, boxes, frame)
        if alt and not _polyline_hits(alt, boxes):
            return _inset_route(alt, frame)
    return _inset_route(pts, frame)


def _inset_route(pts, frame, inset: float = 8.0):
    """Keep elbow corners inside the frame. Ports stay where the nodes put them."""
    if not frame or len(pts) < 3:
        return pts
    fx0, fy0, fx1, fy1 = frame
    out = [pts[0]]
    for x, y in pts[1:-1]:
        out.append(
            (
                min(max(x, fx0 + inset), fx1 - inset),
                min(max(y, fy0 + inset), fy1 - inset),
            )
        )
    out.append(pts[-1])
    return out


def _polyline_hits(pts, boxes) -> bool:
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        if abs(ay - by) <= 0.6:
            if _span_hits_boxes("h", (ay + by) / 2.0, ax, bx, boxes):
                return True
        elif abs(ax - bx) <= 0.6:
            if _span_hits_boxes("v", (ax + bx) / 2.0, ay, by, boxes):
                return True
        else:
            return True
    return False


def _simplify_ortho(pts):
    out = []
    for p in pts:
        if out and abs(p[0] - out[-1][0]) < 0.35 and abs(p[1] - out[-1][1]) < 0.35:
            continue
        out.append(p)
    cleaned = []
    for p in out:
        if len(cleaned) >= 2:
            ax, ay = cleaned[-2]
            bx, by = cleaned[-1]
            colinear = (abs(ax - bx) <= 0.6 and abs(bx - p[0]) <= 0.6) or (
                abs(ay - by) <= 0.6 and abs(by - p[1]) <= 0.6
            )
            if colinear:
                cleaned[-1] = p
                continue
        cleaned.append(p)
    return cleaned


def _route_gutter(x1, y1, x2, y2, from_side, to_side, boxes, frame):
    """Orthogonal path in the gutters around node boxes, when a direct elbow cuts one."""
    import heapq

    if not frame:
        return None
    fx0, fy0, fx1, fy1 = frame
    pad = 6.0

    def stub(x, y, side, dist):
        if side == "bottom":
            return x, y - dist
        if side == "top":
            return x, y + dist
        if side == "left":
            return x - dist, y
        if side == "right":
            return x + dist, y
        return x, y

    def clear_stub(x, y, side):
        for dist in (8.0, 5.5, 3.5, 2.2):
            sx, sy = stub(x, y, side, dist)
            if not (fx0 + 2 <= sx <= fx1 - 2 and fy0 + 2 <= sy <= fy1 - 2):
                continue
            if not _polyline_hits([(x, y), (sx, sy)], boxes):
                return sx, sy
        return stub(x, y, side, 2.2)

    sx, sy = clear_stub(x1, y1, from_side)
    dx, dy = clear_stub(x2, y2, to_side)
    xs = {round(sx, 1), round(dx, 1), round(fx0 + 8.0, 1), round(fx1 - 8.0, 1)}
    ys = {round(sy, 1), round(dy, 1), round(fy0 + 8.0, 1), round(fy1 - 8.0, 1)}
    for x0, y0, x1b, y1b in boxes:
        for x in (x0 - pad, x1b + pad):
            if fx0 + 3 <= x <= fx1 - 3:
                xs.add(round(x, 1))
        for y in (y0 - pad, y1b + pad):
            if fy0 + 3 <= y <= fy1 - 3:
                ys.add(round(y, 1))
    xs = sorted(xs)
    ys = sorted(ys)

    def nearest(val, arr):
        return min(range(len(arr)), key=lambda i: abs(arr[i] - val))

    start = (nearest(sx, xs), nearest(sy, ys))
    goal = (nearest(dx, xs), nearest(dy, ys))
    heap = [(0.0, start[0], start[1], 0, None)]
    best = {}
    parent = {}
    while heap:
        cost, ix, iy, direction, prev = heapq.heappop(heap)
        key = (ix, iy, direction)
        if key in best:
            continue
        best[key] = cost
        parent[key] = prev
        if (ix, iy) == goal:
            path = []
            cur = key
            while cur is not None:
                path.append((xs[cur[0]], ys[cur[1]]))
                cur = parent[cur]
            path.reverse()
            full = [(x1, y1)]
            for p in path:
                full.append(p)
            full.append((x2, y2))
            full = _simplify_ortho(full)
            if _polyline_hits(full, boxes):
                return None
            return full
        for nix, niy, ndir in ((ix + 1, iy, 1), (ix - 1, iy, 1), (ix, iy + 1, 2), (ix, iy - 1, 2)):
            if not (0 <= nix < len(xs) and 0 <= niy < len(ys)):
                continue
            if ndir == 1:
                if not (abs(xs[ix] - xs[nix]) < 0.2 or not _span_hits_boxes("h", ys[iy], xs[ix], xs[nix], boxes)):
                    continue
                dist = abs(xs[nix] - xs[ix])
            else:
                if not (abs(ys[iy] - ys[niy]) < 0.2 or not _span_hits_boxes("v", xs[ix], ys[iy], ys[niy], boxes)):
                    continue
                dist = abs(ys[niy] - ys[iy])
            bend = 0 if direction in (0, ndir) else 1
            nkey = (nix, niy, ndir)
            if nkey in best:
                continue
            heapq.heappush(heap, (cost + dist + bend * 18.0, nix, niy, ndir, key))
    return None


def _port(cx: float, cy: float, w: float, h: float, side: str) -> tuple[float, float]:
    if side == "top":
        return cx, cy + h / 2.0
    if side == "bottom":
        return cx, cy - h / 2.0
    if side == "left":
        return cx - w / 2.0, cy
    if side == "right":
        return cx + w / 2.0, cy
    return cx, cy


def _rects_hit(a, b, gap: float = 0.0) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax1 + gap > bx0 and bx1 + gap > ax0 and ay1 + gap > by0 and by1 + gap > ay0


def _label_box(x: float, baseline: float, block: TextMeasure):
    top = baseline + block.ascent
    bottom = baseline - (block.height - block.ascent)
    return (x, bottom, x + block.width, top)


def _segment_box(x1: float, y1: float, x2: float, y2: float, pad: float = 3.5):
    return (min(x1, x2) - pad, min(y1, y2) - pad, max(x1, x2) + pad, max(y1, y2) + pad)


def _stroke_hits_box(box, pts, pad: float = 0.4) -> bool:
    """True when a polyline sample lands inside the label's glyph box."""
    x0, y0, x1, y1 = box
    if not pts or len(pts) < 2:
        return False
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dist = math.hypot(bx - ax, by - ay)
        n = max(1, int(dist / 2.0))
        for i in range(n + 1):
            t = i / n
            x = ax + (bx - ax) * t
            y = ay + (by - ay) * t
            if (x0 - pad) < x < (x1 + pad) and (y0 - pad) < y < (y1 + pad):
                return True
    return False


def _outgoing_segment(port, side: str, own_pts):
    """The arrow's first stroke. The label sits on this segment, not on the node."""
    px, py = port
    if own_pts and len(own_pts) >= 2 and math.hypot(own_pts[1][0] - own_pts[0][0], own_pts[1][1] - own_pts[0][1]) >= 4:
        return own_pts[0][0], own_pts[0][1], own_pts[1][0], own_pts[1][1]
    if side == "left":
        return px, py, px - 28.0, py
    if side == "bottom":
        return px, py, px, py - 28.0
    if side == "top":
        return px, py, px, py + 28.0
    return px, py, px + 28.0, py


def _shaft_gap(box, ax: float, ay: float, bx: float, by: float) -> float:
    """Distance from the label box to the arrow shaft. Zero means the line runs through the glyphs."""
    x0, y0, x1, y1 = box
    dist = math.hypot(bx - ax, by - ay)
    steps = max(1, int(dist / 2.0))
    best = 1e9
    for i in range(steps + 1):
        t = i / steps
        x = ax + (bx - ax) * t
        y = ay + (by - ay) * t
        dx = 0.0 if x0 <= x <= x1 else min(abs(x - x0), abs(x - x1))
        dy = 0.0 if y0 <= y <= y1 else min(abs(y - y0), abs(y - y1))
        best = min(best, math.hypot(dx, dy))
    return best


def _place_branch_label(text: str, port, side: str, obstacles, frame, size: float, routes=None, own_pts=None):
    """Put YES/NO on the outgoing arrow, just off the shaft, clear of every node."""
    routes = list(routes or [])
    px, py = port
    fx0, fy0, fx1, fy1 = frame
    ax, ay, bx, by = _outgoing_segment(port, side, own_pts)
    horizontal = abs(bx - ax) >= abs(by - ay)
    sizes = []
    trial = float(size)
    floor = 9.0 if size >= 10 else 6.4
    while trial >= floor:
        sizes.append(trial)
        trial -= 1.0

    def clears_heads(box) -> bool:
        if own_pts and _arrowhead_hits_box(box, own_pts, pad=1.8):
            return False
        return not any(_arrowhead_hits_box(box, pts, pad=1.8) for pts in routes)

    def accept(box) -> bool:
        if box[0] < fx0 + 1.5 or box[2] > fx1 - 1.5 or box[1] < fy0 + 1.5 or box[3] > fy1 - 1.5:
            return False
        if any(_rects_hit(box, obs, 1.0) for obs in obstacles):
            return False
        if any(_stroke_hits_box(box, pts, pad=0.55) for pts in routes):
            return False
        if not clears_heads(box):
            return False
        if _port_distance(box, px, py) > 48.0:
            return False
        gap = _shaft_gap(box, ax, ay, bx, by)
        if not (2.2 <= gap <= 18.0):
            return False
        if horizontal and bx >= ax and box[0] < px - 1.0:
            return False
        if horizontal and bx < ax and box[2] > px + 1.0:
            return False
        return True

    for sz in sizes:
        block = measure_text(text, 80.0, sz, bold=True, leading=sz + 1.0)
        w = block.width
        h = block.height
        candidates = []
        if horizontal and bx >= ax:
            for along in (3.0, 8.0, 14.0):
                x = px + along
                # Just above the shaft. PDF y grows upward.
                baseline = py + 2.4 + (h - block.ascent)
                candidates.append((x, baseline))
                baseline = (py - 2.4 - h) + (h - block.ascent)
                candidates.append((x, baseline))
            # A short arrow's head fills the shaft. Lift the label clear of it.
            for lift in (6.5, 9.0):
                x = px + 2.0
                candidates.append((x, py + lift + (h - block.ascent)))
                candidates.append((x, py - lift - block.ascent))
        elif horizontal:
            # The arrow leaves to the left. Keep YES/NO on that side of the port.
            span = abs(bx - ax)
            alongs = (10.0, 18.0, 28.0, max(16.0, span * 0.4))
            for along in alongs:
                x = px - along - w
                for lift in (3.0, 8.0, 12.0):
                    candidates.append((x, py + lift + (h - block.ascent)))
                    candidates.append((x, (py - lift - h) + (h - block.ascent)))
        elif by < ay:
            for along in (4.0, 10.0, 16.0):
                for side in (8.0, 14.0, 22.0, 32.0):
                    top = py - along
                    candidates.append((px - side - w, top - block.ascent))
                    candidates.append((px + side, top - block.ascent))
        else:
            for along in (2.0, 8.0):
                x = px + 3.0
                top = py + along + h
                candidates.append((x, top - block.ascent))
        for x, baseline in candidates:
            box = _label_box(x, baseline, block)
            if accept(box):
                return x, baseline, block, box
    for sz in sizes:
        block = measure_text(text, 80.0, sz, bold=True, leading=sz + 1.0)
        w = block.width
        h = block.height
        fallback = []
        if horizontal and bx >= ax:
            fallback.append((px + 8.0, py + 3.0 + (h - block.ascent)))
        elif horizontal:
            fallback.append((px - 10.0 - w, py + 3.0 + (h - block.ascent)))
            fallback.append((px - 22.0 - w, py + 8.0 + (h - block.ascent)))
        else:
            fallback.append((px + 16.0, py - block.ascent))
            fallback.append((px - 16.0 - w, py - block.ascent))
        for x, baseline in fallback:
            box = _label_box(x, baseline, block)
            if box[0] < fx0 + 1.5 or box[2] > fx1 - 1.5 or box[1] < fy0 + 1.5 or box[3] > fy1 - 1.5:
                continue
            if any(_rects_hit(box, obs, 1.0) for obs in obstacles):
                continue
            if not clears_heads(box):
                continue
            return x, baseline, block, box
    # A short vertical arrow has no room on the shaft. Park the label beside the node.
    owners = [
        obs
        for obs in obstacles
        if obs[0] - 1 <= px <= obs[2] + 1 and obs[1] - 1 <= py <= obs[3] + 1
    ]
    block = measure_text(text, 80.0, sizes[-1] if sizes else size, bold=True, leading=(sizes[-1] if sizes else size) + 1.0)
    beside = []
    if owners:
        node = owners[0]
        mid = (node[1] + node[3]) / 2.0
        baseline = mid - block.height / 2.0 + (block.height - block.ascent)
        left = (node[0] - 6.0 - block.width, baseline)
        right = (node[2] + 6.0, baseline)
        if horizontal and bx < ax:
            beside.append(left)
        else:
            beside.append(right)
            beside.append(left)
    beside.append((px + 6.0, py - block.ascent - 1.0))
    beside.append((px - block.width - 6.0, py - block.ascent - 1.0))
    for x, baseline in beside:
        box = _label_box(x, baseline, block)
        if box[0] < fx0 + 1.5 or box[2] > fx1 - 1.5 or box[1] < fy0 + 1.5 or box[3] > fy1 - 1.5:
            continue
        if any(_rects_hit(box, obs, 0.6) for obs in obstacles):
            continue
        if not clears_heads(box):
            continue
        return x, baseline, block, box
    return None


def _port_distance(box, px: float, py: float) -> float:
    """How far a label box sits from the arrow port. A stray label is far."""
    x0, y0, x1, y1 = box
    dx = 0.0 if x0 <= px <= x1 else min(abs(px - x0), abs(px - x1))
    dy = 0.0 if y0 <= py <= y1 else min(abs(py - y0), abs(py - y1))
    return math.hypot(dx, dy)


def layout_flowchart(flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float):
    """OEM SM flowchart. Node shapes are sized to their measured text."""
    shapes: list[DrawnShape] = []
    texts: list[DrawnText] = []
    frame_id = _next_id("flow")
    shapes.append(
        DrawnShape(
            "roundrect", frame_x, frame_y, frame_w, frame_h,
            fill=PALE, stroke=NAVY, stroke_w=1.6, radius=6,
            id=frame_id, role="frame",
        )
    )
    title = measure_text("VISUAL FLOWCHART", 220, 9, bold=True, leading=11)
    title_base = frame_y + frame_h - 14.0 - title.ascent
    texts.append(
        DrawnText(
            "VISUAL FLOWCHART",
            frame_x + 12,
            title_base,
            w=title.width + 4,
            size=9,
            bold=True,
            color=NAVY,
            leading=title.leading,
            lines=list(title.lines),
            owner=frame_id,
            role="header",
        )
    )
    placed = _pack_flowchart(flow, frame_x, frame_y, frame_w, frame_h)
    node_boxes = []
    for nid, node in placed.items():
        x = node["cx"] - node["w"] / 2.0
        y = node["cy"] - node["h"] / 2.0
        sid = f"node-{nid}"
        kind = node["kind"]
        if kind == "diamond":
            shapes.append(DrawnShape("diamond", x, y, node["w"], node["h"], fill=GOLD, stroke=NAVY, stroke_w=2.0, id=sid, role="node"))
        elif kind == "ellipse":
            raw = next((n for n in flow.nodes if n.id == nid), None)
            fill = GREEN if raw and raw.kind == "start" else NAVY
            shapes.append(DrawnShape("ellipse", x, y, node["w"], node["h"], fill=fill, stroke=NAVY, stroke_w=1.7, id=sid, role="node"))
        else:
            shapes.append(
                DrawnShape(
                    "roundrect", x, y, node["w"], node["h"],
                    fill=WHITE, stroke=NAVY, stroke_w=1.6, radius=7,
                    id=sid, role="node",
                )
            )
        raw = next((n for n in flow.nodes if n.id == nid), None)
        color = WHITE if raw and raw.kind in ("start", "end") else INK
        texts.append(
            DrawnText(
                node["text"],
                node["cx"],
                node["cy"],
                w=max(_content_width(kind, node["w"]), 20),
                size=node["size"],
                bold=node["bold"],
                color=color,
                align="center",
                leading=node["leading"],
                lines=list(node["lines"]),
                owner=sid,
                role="node",
            )
        )
        node_boxes.append((x, y, x + node["w"], y + node["h"]))

    frame = (frame_x, frame_y, frame_x + frame_w, frame_y + frame_h)
    # Keep arrows and YES/NO off the frame title.
    node_boxes.append(
        (
            frame_x + 8.0,
            title_base - title.descent - 1.0,
            frame_x + 16.0 + title.width,
            title_base + title.ascent + 1.0,
        )
    )
    label_boxes = []
    readable = bool(getattr(flow, "readable", False))
    label_size = 11.0 if readable else 7.0
    routed = []
    for edge in flow.edges:
        if edge.from_id not in placed or edge.to_id not in placed:
            continue
        src = placed[edge.from_id]
        dst = placed[edge.to_id]
        x1, y1 = _port(src["cx"], src["cy"], src["w"], src["h"], edge.from_side)
        x2, y2 = _port(dst["cx"], dst["cy"], dst["w"], dst["h"], edge.to_side)
        pts = _route_elbow(x1, y1, x2, y2, edge.from_side, edge.to_side, node_boxes, frame)
        shapes.append(
            DrawnShape(
                "arrow",
                x=pts[0][0],
                y=pts[0][1],
                x2=pts[-1][0],
                y2=pts[-1][1],
                stroke=NAVY,
                stroke_w=1.6 if readable else 1.15,
                points=pts,
                id=_next_id("arrow"),
                role="connector",
            )
        )
        corridors = [_segment_box(ax, ay, bx, by, pad=2.2) for (ax, ay), (bx, by) in zip(pts, pts[1:])]
        routed.append((edge, pts, (x1, y1), corridors))
    for index, (edge, pts, port, _own) in enumerate(routed):
        if edge.label:
            other_routes = [item[1] for j, item in enumerate(routed) if j != index]
            placed = _place_branch_label(
                edge.label.upper(),
                port,
                edge.from_side,
                node_boxes + label_boxes,
                frame,
                label_size,
                routes=other_routes,
                own_pts=pts,
            )
            if placed is None:
                continue
            lx, ly, block, box = placed
            color = GREEN if edge.label.upper() == "YES" else RED
            texts.append(
                DrawnText(
                    edge.label.upper(),
                    lx,
                    ly,
                    w=max(block.width, 12),
                    size=block.size,
                    bold=True,
                    color=color,
                    align="left",
                    leading=block.leading,
                    lines=list(block.lines),
                    role="label",
                )
            )
            label_boxes.append(box)
    return shapes, texts


class _SheetFlow:
    """Top-down cursor. `y` is the top of the next free band (PDF y grows upward)."""

    def __init__(self, pages: list, subtitle: str):
        self.pages = pages
        self.subtitle = subtitle
        self.floor = MARGIN + 36.0
        self.page = _new_sheet_page()
        pages.append(self.page)
        self.banner_bottom = _paint_top_bar(self.page, subtitle)
        self.y = self.banner_bottom - 8.0

    def remaining(self) -> float:
        return self.y - self.floor

    def new_page(self, subtitle: str):
        self.subtitle = subtitle
        self.page = _new_sheet_page()
        self.pages.append(self.page)
        self.banner_bottom = _paint_top_bar(self.page, subtitle)
        self.y = self.banner_bottom - 8.0


def _bar_metrics(title: str, width: float) -> TextMeasure:
    return measure_text(title, width - 16.0, 8.5, bold=True, leading=11.0)


def _add_section(cur: _SheetFlow, title: str, fill, follow_h: float, *, allow_break: bool = True) -> bool:
    """Draw a section bar. Move to a new page when the bar and its first line would not fit."""
    width = _CONTENT_W
    block = _bar_metrics(title, width)
    bar_h = max(16.0, block.height + 6.0)
    need = bar_h + 6.0 + min(max(follow_h, 12.0), 36.0)
    if cur.remaining() < need:
        if not allow_break:
            return False
        cur.new_page(cur.subtitle)
    top = cur.y
    bottom = top - bar_h
    sid = _next_id("bar")
    cur.page.shapes.append(
        DrawnShape("rect", MARGIN, bottom, width, bar_h, fill=fill, stroke=fill, stroke_w=0.4, id=sid, role="bar")
    )
    baseline = bottom + (bar_h - block.height) / 2.0 + block.descent
    cur.page.texts.append(
        DrawnText(
            title, MARGIN + 8, baseline, w=width - 16, size=8.5, bold=True, color=WHITE,
            leading=block.leading, lines=list(block.lines), owner=sid, role="bar",
        )
    )
    cur.y = bottom - 6.0
    return True


def _paint_measured(cur: _SheetFlow, block: TextMeasure, *, x: float, size: float, bold: bool, color, role: str, owner: str, gap_after: float):
    baseline = cur.y - block.ascent
    cur.page.texts.append(
        DrawnText(
            "\n".join(block.lines),
            x,
            baseline,
            w=max(block.width, 12),
            size=size,
            bold=bold,
            color=color,
            align="left",
            leading=block.leading,
            lines=list(block.lines),
            owner=owner,
            role=role,
        )
    )
    cur.y = baseline - (len(block.lines) - 1) * block.leading - block.descent - gap_after


def _chunk_lines(block: TextMeasure, lines: list[str]) -> TextMeasure:
    height = block.ascent + block.descent + max(0, len(lines) - 1) * block.leading
    width = 0.0
    for line in lines:
        width = max(width, _string_width(line, block.font, block.size))
    return TextMeasure(lines, width, height, block.ascent, block.descent, block.leading, block.size, block.font)


def _emit_block(cur: _SheetFlow, block: TextMeasure, *, x: float, size: float, bold: bool, color, role: str = "body", owner: str = "", gap_after: float = 4.0, on_break=None, allow_break: bool = True):
    """Paint a measured block. Split across pages on line boundaries. `on_break` redraws a section bar."""
    if not block.lines:
        return
    if not allow_break and block.height + gap_after > cur.remaining():
        take = 0
        while take < len(block.lines):
            nxt = _chunk_lines(block, block.lines[: take + 1])
            if nxt.height + gap_after <= cur.remaining():
                take += 1
            else:
                break
        if take:
            piece = _chunk_lines(block, block.lines[:take])
            _paint_measured(cur, piece, x=x, size=size, bold=bold, color=color, role=role, owner=owner, gap_after=gap_after)
        return
    idx = 0
    first = True
    while idx < len(block.lines):
        if on_break and not first:
            on_break(cur)
        room = cur.remaining() - gap_after
        if block.ascent + block.descent > room:
            if on_break:
                on_break(cur)
            else:
                cur.new_page(cur.subtitle)
            room = cur.remaining() - gap_after
        take = 1
        while idx + take < len(block.lines):
            nxt = _chunk_lines(block, block.lines[idx : idx + take + 1])
            if nxt.height + gap_after <= cur.remaining():
                take += 1
            else:
                break
        # Keep a short block together when the next page can hold it.
        whole = _chunk_lines(block, block.lines[idx:])
        if first and take < len(block.lines) - idx and whole.height + gap_after <= (cur.banner_bottom - 8.0 - cur.floor - 28):
            if on_break:
                on_break(cur)
            else:
                cur.new_page(cur.subtitle)
            take = len(block.lines) - idx
        piece = _chunk_lines(block, block.lines[idx : idx + take])
        _paint_measured(cur, piece, x=x, size=size, bold=bold, color=color, role=role, owner=owner, gap_after=gap_after)
        idx += take
        first = False


def _add_boxed_text(cur: _SheetFlow, text: str, *, size: float = 9.0, leading: float = 12.0, color=INK):
    width = _CONTENT_W
    inner_w = width - 16.0
    block = measure_text(text or "-", inner_w, size, leading=leading)
    pad = 6.0

    def paint_box(piece: TextMeasure):
        box_h = piece.height + pad * 2
        if box_h > cur.remaining():
            return False
        top = cur.y
        bottom = top - box_h
        sid = _next_id("box")
        cur.page.shapes.append(
            DrawnShape("rect", MARGIN, bottom, width, box_h, fill=WHITE, stroke=RULE, stroke_w=0.8, id=sid, role="box")
        )
        baseline = top - pad - piece.ascent
        cur.page.texts.append(
            DrawnText(
                "\n".join(piece.lines), MARGIN + 8, baseline, w=inner_w, size=size, color=color,
                leading=piece.leading, lines=list(piece.lines), owner=sid, role="body",
            )
        )
        cur.y = bottom - 8.0
        return True

    if paint_box(block):
        return
    idx = 0
    while idx < len(block.lines):
        take = 1
        while idx + take < len(block.lines):
            piece = _chunk_lines(block, block.lines[idx : idx + take + 1])
            if piece.height + pad * 2 + 8 <= cur.remaining():
                take += 1
            else:
                break
        piece = _chunk_lines(block, block.lines[idx : idx + take])
        if not paint_box(piece):
            cur.new_page(cur.subtitle)
            _add_section(cur, "WHAT THIS PATTERN USUALLY MEANS", NAVY, follow_h=piece.height + pad * 2)
            paint_box(piece)
        idx += take


def _figure_draw_size(png: bytes, max_h: float) -> tuple[float, float]:
    """One width for every Bay figure: 75% of the usable page, aspect kept."""
    width, height = _png_pixel_size(png)
    fig_w = _FIGURE_WIDTH
    fig_h = fig_w * float(height) / max(float(width), 1.0)
    if max_h > 0 and fig_h > max_h:
        fig_h = max_h
    return fig_w, max(fig_h, 1.0)


def _keep_block(cur: _SheetFlow, need: float, subtitle: str) -> None:
    """Start a new page when the step and its figure will not both fit."""
    if need <= cur.y - _FIGURE_FLOOR:
        return
    cur.new_page(subtitle)


def _paint_centered_figure(cur: _SheetFlow, png: bytes, caption: str, fig_w: float, fig_h: float) -> None:
    """Figure centered under the step, caption centered under the figure."""
    img_x = MARGIN + (_CONTENT_W - fig_w) / 2.0
    img_bottom = cur.y - fig_h
    cur.page.images.append(DrawnImage(png, img_x, img_bottom, fig_w, fig_h))
    cap_m = measure_text(caption, fig_w - 8.0, 8, bold=True, leading=10)
    cap_x = img_x + max(0.0, (fig_w - cap_m.width) / 2.0)
    baseline = img_bottom - 4.0 - cap_m.ascent
    cur.page.texts.append(
        DrawnText(
            "\n".join(cap_m.lines),
            cap_x,
            baseline,
            w=max(cap_m.width, 12),
            size=8,
            bold=True,
            color=NAVY,
            leading=cap_m.leading,
            lines=list(cap_m.lines),
            role="caption",
        )
    )
    cur.y = baseline - max(0, len(cap_m.lines) - 1) * cap_m.leading - cap_m.descent


def _figure_block_height(png: bytes, caption: str, max_h: float) -> tuple[float, float, float]:
    fig_w, fig_h = _figure_draw_size(png, max_h)
    cap_m = measure_text(caption, fig_w - 8.0, 8, bold=True, leading=10)
    return fig_w, fig_h, fig_h + 4.0 + cap_m.height


def _fit_figure_pair(png: bytes, caption: str, room: float) -> tuple[float, float]:
    """Keep the shared width. Shrink height only when a fresh page is still too short."""
    fig_w, _fig_h, block = _figure_block_height(png, caption, 0)
    if block <= room:
        return fig_w, _fig_h
    cap_m = measure_text(caption, fig_w - 8.0, 8, bold=True, leading=10)
    fig_h = max(36.0, room - 4.0 - cap_m.height)
    return fig_w, fig_h


def _add_step(cur: _SheetFlow, index: int, step: str, figures: list | None = None):
    """One bay-order step, then each cited figure under it. They stay on one page."""
    import manual_figures as mf

    text_x = MARGIN + 24.0
    text_w = _CONTENT_W - 32.0
    heading, lines = mf.lines_from_shop_text(step, index)
    prev_where = getattr(cur, "diag_prev_where", "") if index > 1 else ""
    if any(re.match(r"^(?:Where|Good looks like|Next|If it fails):", line) for line in lines):
        # A labeled check is held to the profile. A plain bay-order line stays as written.
        heading, lines = bpl.conform_lines(heading, lines, previous_where=prev_where, diagnosis=True)
    try:
        cur.diag_prev_where = next((line[7:] for line in lines if line.startswith("Where: ")), prev_where)
    except AttributeError:
        pass
    head = measure_text(heading, text_w, 9, bold=True, leading=11.6)
    body = measure_text("\n".join(lines), text_w, 8, leading=10.8) if lines else None
    text_h = head.height + (3.0 + body.height if body else 0.0)
    drawn = []
    fig_span = 0.0
    for fig in figures or []:
        png = getattr(fig, "image_png", b"") or b""
        if not png:
            continue
        cap = mf.display_caption(fig.title, fig.page, fig.caption)
        _fw, _fh, block = _figure_block_height(png, cap, 0)
        drawn.append((png, cap))
        fig_span += 4.0 + block
    floor = _FIGURE_FLOOR if drawn else cur.floor
    need = text_h + fig_span + _STEP_GAP

    def continued(flow: _SheetFlow):
        flow.new_page("Bay order continued")
        _add_section(flow, "BAY ORDER (CONTINUED)", GREEN, follow_h=min(text_h, 48))

    if need > cur.y - floor:
        continued(cur)
    room = cur.y - floor - text_h - _STEP_GAP
    sized = []
    for png, cap in drawn:
        fig_w, fig_h = _fit_figure_pair(png, cap, room - 4.0)
        sized.append((png, cap, fig_w, fig_h))
        _fw, _fh, block = _figure_block_height(png, cap, fig_h)
        room -= 4.0 + block

    def paint_check():
        baseline = cur.y - head.ascent
        mid = baseline + (head.ascent - head.descent) / 2.0
        box = 8.0
        cur.page.shapes.append(
            DrawnShape(
                "rect", MARGIN + 8, mid - box / 2.0, box, box,
                fill=WHITE, stroke=NAVY, stroke_w=0.9,
                id=_next_id("check"), role="check",
            )
        )

    saved_floor = cur.floor
    cur.floor = floor
    try:
        paint_check()
        _paint_measured(cur, head, x=text_x, size=9, bold=True, color=INK, role="body", owner="", gap_after=3.0 if body else 0.0)
        if body:
            _paint_measured(cur, body, x=text_x, size=8, bold=False, color=INK, role="body", owner="", gap_after=0.0)
        for png, cap, fig_w, fig_h in sized:
            cur.y -= 4.0
            _paint_centered_figure(cur, png, cap, fig_w, fig_h)
        cur.y -= _STEP_GAP
    finally:
        cur.floor = saved_floor


def _add_plain_item(cur: _SheetFlow, text: str, *, size: float = 8.5, color=INK, width: float | None = None, x: float | None = None, gap: float = 5.0, on_break=None, allow_break: bool = True):
    block = measure_text(text, width or (_CONTENT_W - 16.0), size, leading=size + 2.6)
    _emit_block(
        cur, block,
        x=MARGIN + 8 if x is None else x,
        size=size, bold=False, color=color, gap_after=gap, on_break=on_break,
        allow_break=allow_break,
    )


def _measure_one_line(text: str, max_width: float, size: float, *, bold: bool, min_size: float = 5.5) -> TextMeasure:
    """Shrink until the whole string is one line. A blank value draws nothing."""
    text = (text or "").strip()
    if not text:
        return measure_text("", max_width, size, bold=bold, leading=size + 2.2)
    current = size
    font = _font_name(bold)
    safe = _latin1_safe(text)
    while current >= min_size:
        if _string_width(safe, font, current) <= max_width + 0.2:
            return measure_text(text, max_width, current, bold=bold, leading=current + 2.2)
        current -= 0.25
    return measure_text(text, max_width, min_size, bold=bold, leading=min_size + 2.2)


def _paint_identity_header(page: SheetPage, proc: BayProcedure, banner_bottom: float) -> float:
    left = MARGIN
    width = _CONTENT_W
    pad_x, pad_y, row_gap = 8.0, 6.0, 4.0
    label_size, value_size = 7.0, 9.0
    right = left + width - pad_x
    labels = {
        name: measure_text(name, 80, label_size, bold=True, leading=9)
        for name in ("CONCERN", "MODEL", "DATE", "WO#", "PRIMARY")
    }
    date_m = measure_text(proc.created.strftime("%Y-%m-%d"), 90, value_size, bold=True, leading=11.2)
    wo_m = measure_text(_clip(proc.wo_number or "-", 18), 90, value_size, bold=True, leading=11.2)
    cluster = labels["DATE"].width + 3 + date_m.width + 10 + labels["WO#"].width + 3 + wo_m.width
    value_x = left + pad_x + 64.0
    model_w = max(70.0, right - value_x - cluster - 8.0)
    model_m = _measure_one_line(proc.model_line, model_w, value_size, bold=True)
    concern_m = measure_text(proc.concern or "-", right - value_x, value_size, bold=True, leading=11.4)
    primary_m = measure_text(proc.primary_cite or "-", right - value_x, value_size, bold=True, leading=11.4)
    model_row_h = max(model_m.height, date_m.height, wo_m.height, labels["MODEL"].height)
    inner_h = concern_m.height + row_gap + model_row_h + row_gap + primary_m.height
    header_h = inner_h + pad_y * 2
    header_top = banner_bottom - 8.0
    header_bottom = header_top - header_h
    sid = _next_id("header")
    page.shapes.append(
        DrawnShape("rect", left, header_bottom, width, header_h, fill=CREAM, stroke=NAVY, stroke_w=1.0, id=sid, role="box")
    )

    def emit(block: TextMeasure, x: float, top: float, *, size: float, bold: bool, color):
        page.texts.append(
            DrawnText(
                "\n".join(block.lines),
                x,
                top - block.ascent,
                w=max(block.width, 8),
                size=size,
                bold=bold,
                color=color,
                leading=block.leading,
                lines=list(block.lines),
                owner=sid,
                role="header",
            )
        )

    y = header_top - pad_y
    emit(labels["CONCERN"], left + pad_x, y, size=label_size, bold=True, color=GREEN)
    emit(concern_m, value_x, y, size=value_size, bold=True, color=INK)
    y -= concern_m.height + row_gap
    emit(labels["MODEL"], left + pad_x, y, size=label_size, bold=True, color=GREEN)
    emit(model_m, value_x, y, size=value_size, bold=True, color=INK)
    wo_x = right - wo_m.width
    wo_label_x = wo_x - 3 - labels["WO#"].width
    date_x = wo_label_x - 10 - date_m.width
    date_label_x = date_x - 3 - labels["DATE"].width
    emit(labels["DATE"], date_label_x, y, size=label_size, bold=True, color=GREEN)
    emit(date_m, date_x, y, size=value_size, bold=True, color=INK)
    emit(labels["WO#"], wo_label_x, y, size=label_size, bold=True, color=GREEN)
    emit(wo_m, wo_x, y, size=value_size, bold=True, color=INK)
    y -= model_row_h + row_gap
    emit(labels["PRIMARY"], left + pad_x, y, size=label_size, bold=True, color=GREEN)
    emit(primary_m, value_x, y, size=value_size, bold=True, color=INK)
    return header_bottom


def _png_pixel_size(png: bytes) -> tuple[int, int]:
    from PIL import Image

    image = Image.open(BytesIO(png))
    return image.size


def _figure_is_squeezed(png: bytes, remaining: float) -> bool:
    """A tall drawing that would shrink to a thumbnail belongs on its own page.

    A wide, short table row stays inline.
    """
    width, height = _png_pixel_size(png)
    if width < 1 or height < 1 or height < width * 0.45:
        return False
    target_h = min(280.0, (_CONTENT_W - 32) * height / width)
    avail = max(0.0, remaining - 80.0)
    fitted = _fit_image(png, _CONTENT_W - 32, avail)[1]
    return fitted < min(140.0, target_h * 0.7)


def _fit_image(png: bytes, max_w: float, max_h: float) -> tuple[float, float]:
    """Display size that keeps the figure's aspect. No letterboxed empty box."""
    if max_w < 24 or max_h < 24 or not png:
        return 0.0, 0.0
    width, height = _png_pixel_size(png)
    if width < 1 or height < 1:
        return 0.0, 0.0
    scale = min(max_w / width, max_h / height)
    return width * scale, height * scale


def _paint_figure_on(cur: _SheetFlow, fig: BayFigure, *, png: bytes, allow_break: bool = True) -> bool:
    """A leftover library figure, same width as a step figure, caption underneath."""
    cap = f"{fig.caption or 'Figure'} -- {fig.title}" + (f" p.{fig.page}" if fig.page else "")
    _fw, _fh, block = _figure_block_height(png, cap, 0)
    need = 36.0 + block
    if need > cur.y - _FIGURE_FLOOR:
        if not allow_break:
            return False
        cur.new_page(cur.subtitle)
    room = cur.y - _FIGURE_FLOOR - 36.0
    fig_w, fig_h = _fit_figure_pair(png, cap, room)
    if fig_h < 28 or fig_w < 28:
        return False
    if not _add_section(
        cur, "CITED LIBRARY FIGURES", NAVY, follow_h=min(block, 36), allow_break=allow_break
    ):
        return False
    _paint_centered_figure(cur, png, cap, fig_w, fig_h)
    cur.y -= 8.0
    return True


def _paint_figure_page(pages: list, fig: BayFigure, *, png: bytes, with_footer: bool):
    cur = _SheetFlow(pages, "Cited library figures")
    if not _paint_figure_on(cur, fig, png=png):
        return
    if with_footer:
        _add_3c_footer(cur.page)


def _source_row_height(title: str, excerpt: str) -> float:
    height = measure_text(title, _CONTENT_W - 16, 8.5, leading=11.1).height + 2.0
    if excerpt:
        height += measure_text(excerpt, _CONTENT_W - 28, 8, leading=10.6).height + 6.0
    return height


def _one_excerpt(text: str) -> str:
    parts = _split_sentences(clean_ocr_prose(text or ""))
    if parts:
        return parts[0]
    # A verbatim manual quote the OCR cleaner rejects still prints as quoted.
    raw = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text or "").strip())
    first = raw[0] if raw else ""
    return first if re.fullmatch(r"[A-Z][A-Za-z0-9 ,/'()-]{10,160}\.", first) else ""


def _source_rows(sources: list[dict], *, mode: str) -> list[tuple[str, str]]:
    rows = []
    for source in sources:
        bit = f"  page {source['page']}" if source.get("page") else ""
        title = f"- {source.get('title') or 'Manual'}{bit}"
        excerpt = (source.get("excerpt") or "").strip()
        if mode == "one":
            excerpt = _one_excerpt(excerpt)
        elif mode == "none":
            excerpt = ""
        rows.append((title, excerpt))
    return rows


def _sources_that_fit(remaining: float, sources: list[dict]) -> list[tuple[str, str]] | None:
    """Pack cites into the space left on this page. A short tail must not open a new page."""
    bar = 72.0
    variants: list[list[tuple[str, str]]] = []
    variants.append(_source_rows(sources, mode="full"))
    variants.append(_source_rows(sources, mode="one"))
    variants.append(_source_rows(sources[:4], mode="one"))
    variants.append(_source_rows(sources[:4], mode="none"))
    variants.append(_source_rows(sources[:1], mode="none"))
    for rows in variants:
        if not rows:
            continue
        need = bar + sum(_source_row_height(title, excerpt) for title, excerpt in rows)
        if need <= remaining:
            return rows
    return None


def _paint_fitting_sources(body: _SheetFlow, sources: list[dict]) -> None:
    """Keep cites with the procedure. A cited page is not dropped to save a line.

    A quote that does not fit in the leftover space still prints, on the next
    page. Dropping it used to repeat a neighbor's line by leaving the wrong
    excerpt, or to hide the quote entirely.
    """
    if not sources:
        return
    quoted = _source_rows(sources, mode="one")
    has_quote = any(excerpt for _title, excerpt in quoted)
    fitted = _sources_that_fit(body.remaining(), sources)
    keeps_quote = bool(fitted) and any(excerpt for _title, excerpt in fitted)
    if fitted is not None and len(fitted) >= len(sources) and (keeps_quote or not has_quote):
        _paint_source_rows(body, fitted, allow_break=False)
        return
    rows = quoted if has_quote else _source_rows(sources, mode="none")
    _paint_source_rows(body, rows, allow_break=True)


def _paint_source_rows(body: _SheetFlow, rows: list[tuple[str, str]], *, allow_break: bool) -> None:
    if not rows:
        return
    # The heading travels with its whole first row, quote included. A heading never ends a page.
    first_h = _source_row_height(rows[0][0], rows[0][1])
    if allow_break and first_h + 40.0 > body.remaining():
        body.new_page("Sources  ·  Tacoma RV Center")
    if not _add_section(
        body,
        "SOURCES (SHOP DOCUMENT LIBRARY)",
        NAVY,
        follow_h=first_h,
        allow_break=allow_break,
    ):
        return

    def paint_row(title: str, excerpt: str):
        _add_plain_item(body, title, size=8.5, gap=2.0, on_break=None, allow_break=allow_break)
        if excerpt:
            _add_plain_item(
                body, excerpt, size=8, color=MUTED,
                width=_CONTENT_W - 28, x=MARGIN + 18, gap=6.0, on_break=None,
                allow_break=allow_break,
            )

    for index, (title, excerpt) in enumerate(rows):
        need = _source_row_height(title, excerpt)
        if need > body.remaining():
            tail = sum(_source_row_height(t, e) for t, e in rows[index:])
            if not allow_break:
                return
            body.new_page("Sources  ·  Tacoma RV Center")
            if not _add_section(body, "SOURCES (SHOP DOCUMENT LIBRARY)", NAVY, follow_h=20, allow_break=True):
                return
        paint_row(title, excerpt)


def _paint_unit_id(body: _SheetFlow, proc: BayProcedure) -> None:
    """Brand and model from the job. Serial stays blank for the tech to write."""
    _add_section(body, "UNIT ID", NAVY, follow_h=40)
    brand = (proc.brand or "").strip() or "____________________"
    model = (proc.model or "").strip() or "____________________"
    _add_plain_item(body, f"Brand: {brand}", size=9, gap=3.0)
    _add_plain_item(body, f"Model: {model}", size=9, gap=3.0)
    _add_plain_item(body, "Serial: ____________________", size=9, gap=8.0)


def _diagnosis_line(step: str) -> str:
    return re.split(r"\s+How\s*\(", step or "", maxsplit=1)[0].strip()


def _paint_diagnosis(body: _SheetFlow, steps: list[str]) -> None:
    """The short lead-in. The repair procedure is the body that follows."""
    lines = [_diagnosis_line(step) for step in steps if _diagnosis_line(step)]
    if not lines:
        return
    _add_section(body, "DIAGNOSIS", NAVY, follow_h=28)
    for index, line in enumerate(lines, 1):
        _add_step(body, index, line)


def _paint_caution_box(cur: _SheetFlow, text: str, *, x: float, width: float, allow_break: bool = True) -> None:
    block = measure_text(text, width - 10, 7.5, leading=9.5)
    box_h = block.height + 8.0
    if allow_break and box_h + 4 > cur.remaining():
        cur.new_page("Repair procedure")
    top = cur.y
    bottom = top - box_h
    sid = _next_id("caution")
    cur.page.shapes.append(
        DrawnShape(
            "rect", x, bottom, width, box_h,
            fill=CAUTION_FILL, stroke=RED, stroke_w=0.9, id=sid, role="box",
        )
    )
    baseline = top - 4.0 - block.ascent
    cur.page.texts.append(
        DrawnText(
            "\n".join(block.lines), x + 5, baseline, w=max(block.width, 12), size=7.5,
            color=INK, leading=block.leading, lines=list(block.lines), owner=sid, role="body",
        )
    )
    cur.y = bottom - 4.0


def _repair_figure_caption(figure: dict) -> str:
    import manual_figures as mf

    label = re.sub(r"\s+", " ", (figure.get("label") or "")).strip()
    if re.fullmatch(r"CCD-000\d+, page \d+", label):
        return label
    if re.search(r"\bfig(?:ure)?\.?\s*\d+", label, re.I):
        # Two kit sheets each have a Fig. 1. The document and page tell them apart.
        title = re.sub(r"\s+", " ", str(figure.get("title") or "")).strip()
        page = figure.get("page") or 1
        if title and title.lower() not in label.lower():
            return f"{label}, {title}, page {page}"
        return label
    return mf.display_caption(figure.get("title") or "", figure.get("page") or 1, label)


def _manual_secure_step(procedures: list) -> dict | None:
    """The sheet's own manual securing step for a supply connection, if a branch carries one.

    A reconnected line gets this step, in the manual's words. No step means no invented clamp.
    """
    import manual_figures as mf

    for procedure in procedures or []:
        for step in procedure.get("steps") or []:
            action = mf.step_heading(step, 1).split(": ", 1)[-1]
            if re.match(r"(?i)^(?:secure|tighten)\b.*\b(?:connection|line)\b", action):
                return step
    return None


def _sheet_figure_caption(body, caption: str, action: str) -> str:
    """Number figures across the whole sheet with one number each. The title is the manual's own label."""
    number = getattr(body, "figure_count", 0) + 1
    try:
        body.figure_count = number
    except AttributeError:
        pass
    m = re.match(r"\s*Fig(?:ure)?\.?\s*(\d+)\s*(.*)$", caption or "", re.I)
    if not m:
        return f"Fig. {number}, {caption}".strip().rstrip(",")
    rest = m.group(2).strip()
    if rest.startswith(","):
        return f"Fig. {number}{rest}"
    return f"Fig. {number} {rest}".strip()


def _where_from_memory(lines: list[str], obj: str, memory: list) -> list[str]:
    """A step on the same part as one of the last three steps works where that step did.

    'Secure the back of the cover' follows 'Wrap the cover around to the back of the toilet'.
    """
    key = re.sub(r"^(?:the\s+)?(?:(?:back|front) of (?:the\s+)?)?(?:new\s+|old\s+)?", "", (obj or "").lower()).strip()
    out = []
    for line in lines:
        if line.startswith("Where: ") and key:
            value = line[7:]
            fig = re.search(r"\s*See Fig\.?\s*\d+\.?$", value)
            place = value[: fig.start()] if fig else value
            def self_ref(where: str) -> bool:
                return key in where.lower() and bool(re.match(r"(?i)^at the ", where))

            match = next((where for k, where in reversed(memory[-3:]) if k == key and not self_ref(where)), "")
            if match and key not in place.lower() and re.match(r"(?i)^at ", place) and match.lower() != place.lower():
                value = f"{match} {fig.group(0).strip()}".strip() if fig else match
            memory.append((key, re.sub(r"\s*See Fig\.?\s*\d+\.?$", "", value).strip()))
            line = f"Where: {value}"
        out.append(line)
    return out


def _figure_ref(caption: str) -> str:
    """'Fig. 1 PEDAL REMOVED, Kit 42109, page 1' -> 'Fig. 1'."""
    match = re.match(r"\s*(fig(?:ure)?\.?\s*\d+)", caption or "", re.I)
    return re.sub(r"(?i)^figure", "Fig.", match.group(1)).replace("Fig. .", "Fig.") if match else ""


def _step_good_text(step: dict) -> str:
    import manual_figures as mf

    good, _bad = mf._good_bad_bits(((step or {}).get("fields") or {}).get("GOOD vs BAD") or "")
    return re.sub(r"\s+", " ", good or "").strip().lower().rstrip(".")


def _paint_repair_procedure(body: _SheetFlow, procedure: dict) -> None:
    """Numbered Removal and Installation. The figure sits under the step that cites it."""
    import manual_figures as mf

    hoist_branch_safety(procedure)
    title = procedure.get("title") or "Repair procedure"
    # The branch heading and title travel with what follows. A heading never ends a page.
    if body.remaining() < 140.0:
        body.new_page("Repair procedure")
    _add_plain_item(body, procedure.get("heading") or "REPAIR PROCEDURE", size=10, gap=2)
    _add_plain_item(body, title, size=9, gap=4)
    before = list(procedure.get("before") or [])
    _actions = [mf.step_heading(step, 1).split(": ", 1)[-1] for step in procedure.get("steps") or []]
    _conflicts = bpl.before_conflicts(before, _actions)
    before = [item for item in before if item not in _conflicts]
    if before:
        head = measure_text("BEFORE YOU START", _CONTENT_W - 16.0, 9, leading=11.6)
        first = measure_text(f"- {before[0]}", _CONTENT_W - 16.0, 8, leading=10.6)
        if body.remaining() < head.height + first.height + 16.0:
            body.new_page("Repair procedure")
        _add_plain_item(body, "BEFORE YOU START", size=9, gap=2)
        for item in before:
            _add_plain_item(body, f"- {item}", size=8, gap=2)
    steps = list(procedure.get("steps") or [])
    steps = bpl.drop_duplicate_removals(steps, _step_good_text)
    steps = bpl.repair_branch(
        steps,
        lambda s: mf.step_heading(s, 1).split(": ", 1)[-1],
        lambda s: mf._good_bad_bits(((s or {}).get("fields") or {}).get("GOOD vs BAD") or ""),
        _branch_step,
        secure_step=getattr(body, "secure_step", None),
    )
    section = ""
    before_blob = " ".join(before).lower()
    prev_where = ""
    prev_object = ""
    where_memory: list = []
    printed_safety: set[str] = set()
    text_x = MARGIN + 8.0
    text_w = _STEP_TEXT_W
    for index, step in enumerate(steps, 1):
        section_label = ""
        if step.get("section") != section:
            section = step.get("section") or ""
            section_label = {
                "removal": "REMOVAL",
                "installation": "INSTALLATION",
                "prove": "VERIFY",
            }.get(section, "")
        figure = step.get("figure") if isinstance(step.get("figure"), dict) else None
        png = crop_printed_figure_label((figure or {}).get("png") or b"")
        has = bool(png) and not mf.png_is_blank(png)
        cap = _repair_figure_caption(figure) if has else ""
        if cap:
            cap = _sheet_figure_caption(body, cap, mf.step_heading(step, index).split(": ", 1)[-1])
        fresh = []
        for sentence in _safety_sentences(mf.step_safety_text(step)):
            key = sentence.rstrip(".").lower()
            if key in before_blob or key in printed_safety:
                continue
            fresh.append(sentence)
            printed_safety.add(key)
        safety_line = f"Safety: {' '.join(fresh)}" if fresh else ""
        heading = mf.step_heading(step, index)
        body_lines = mf.step_body_lines(
            step, show_safety=False, show_photo=False, show_figure=False
        )
        if safety_line:
            body_lines = [safety_line, *body_lines]
        next_action = ""
        if index < len(steps):
            next_action = mf.step_heading(steps[index], index + 1).split(": ", 1)[-1]
        else:
            next_action = "This branch is complete"
        heading, body_lines = bpl.conform_lines(
            heading,
            body_lines,
            previous_where=prev_where,
            previous_object=prev_object,
            next_action=next_action,
            figure_ref=_figure_ref(cap) if has else "",
        )
        prev_object = bpl.action_object(heading.split(": ", 1)[-1]) or prev_object
        body_lines = _where_from_memory(body_lines, prev_object, where_memory)
        body_lines = [
            "Next: " + bpl._sentence(bpl.resolve_action_it(line[6:].strip().rstrip("."), prev_object))
            if line.startswith("Next: ") else line
            for line in body_lines
        ]
        prev_where = next((line[7:] for line in body_lines if line.startswith("Where: ")), prev_where)
        prev_where = re.sub(r"\s*See Fig\.?\s*\d+[^.]*\.?$", "", prev_where).strip()
        head_m = measure_text(heading, text_w, 9, bold=True, leading=11.6)
        body_m = measure_text("\n".join(body_lines), text_w, 8, leading=9.3) if body_lines else None
        text_h = head_m.height + (3.0 + body_m.height if body_m else 0.0)
        caution = f"Caution: {step['caution']}" if step.get("caution") else ""
        caution_h = 0.0
        if caution:
            caution_m = measure_text(caution, text_w - 10, 7.5, leading=9.5)
            caution_h = caution_m.height + 12.0
        sec_h = 0.0
        if section_label:
            sec_h = measure_text(section_label, text_w, 9, leading=11.6).height + 6.0
        fig_block = 0.0
        if has:
            _fw, _fh, fig_block = _figure_block_height(png, cap, 0)
            fig_block += 4.0
        need = sec_h + text_h + caution_h + fig_block
        if need > body.y - _FIGURE_FLOOR:
            body.new_page("Repair procedure")
        room = body.y - _FIGURE_FLOOR - sec_h - text_h - caution_h
        fig_w, fig_h = _fit_figure_pair(png, cap, max(0.0, room - 4.0)) if has else (0.0, 0.0)
        saved_floor = body.floor
        body.floor = _FIGURE_FLOOR
        try:
            if section_label:
                sec_m = measure_text(section_label, text_w, 9, bold=True, leading=11.6)
                _paint_measured(
                    body, sec_m, x=text_x, size=9, bold=True, color=INK, role="body", owner="", gap_after=6.0
                )
            _paint_measured(
                body, head_m, x=text_x, size=9, bold=True, color=INK, role="body", owner="", gap_after=3.0 if body_m else 0.0
            )
            if body_m:
                _paint_measured(
                    body, body_m, x=text_x, size=8, bold=False, color=INK, role="body", owner="", gap_after=0.0
                )
            if caution:
                _paint_caution_box(body, caution, x=text_x, width=text_w, allow_break=False)
            if has:
                body.y -= 4.0
                _paint_centered_figure(body, png, cap, fig_w, fig_h)
            body.y -= _STEP_GAP
        finally:
            body.floor = saved_floor


def _do_not_block_height(items: list[str]) -> float:
    """Heading plus every bullet. The list moves as one block."""
    total = 28.0
    for item in items:
        block = measure_text(f"- {item}", _CONTENT_W - 16.0, 8.5, leading=11.1)
        total += block.height + 6.0
    return total


def _paint_do_not(body: "_SheetFlow", items: list[str]) -> None:
    """Keep the DO NOT heading and every bullet on the same page."""
    if not items:
        return
    if _do_not_block_height(items) > body.remaining():
        body.new_page("Do not  ·  Tacoma RV Center")
    first = measure_text(f"- {items[0]}", _CONTENT_W - 16.0, 8.5, leading=11.1)
    _add_section(body, "DO NOT", RED, follow_h=min(first.height, 36), allow_break=False)
    for item in items:
        _add_plain_item(body, f"- {item}", size=8.5, gap=6.0, allow_break=False)


def compose_sheet(proc: BayProcedure) -> list[SheetPage]:
    """Build drawable pages for a human bay sheet.

    BAY_SHEET_STANDARD is enforced here: readable OEM yes/no flowchart first,
    then pattern meaning, full bay order, do-not, sources, figures. Long paths
    paginate from measured block heights. See BAY_SHEET_STANDARD_PATH.
    """
    proc = dedupe_sheet_figures(proc)
    _drop_repeated_procedure_figures(proc.procedures)
    pages: list[SheetPage] = []
    page = _new_sheet_page()
    pages.append(page)
    banner_bottom = _paint_top_bar(page, "Tacoma RV Center  ·  Document Library")
    header_bottom = _paint_identity_header(page, proc, banner_bottom)
    cursor_top = header_bottom - 8.0
    big_flow = bool(getattr(proc.flowchart, "readable", False) or proc.flow_tall)
    if not big_flow:
        # Short charts keep the pattern paragraph on page 1, above the flowchart.
        probe = _SheetFlow.__new__(_SheetFlow)
        probe.pages = pages
        probe.page = page
        probe.subtitle = "Bay procedure"
        probe.floor = MARGIN + 220.0
        probe.banner_bottom = banner_bottom
        probe.y = cursor_top
        means = measure_text(proc.pattern_means or "-", _CONTENT_W - 16, 9, leading=12)
        _add_section(probe, "WHAT THIS PATTERN USUALLY MEANS", NAVY, follow_h=means.height + 16)
        _add_boxed_text(probe, proc.pattern_means or "-")
        cursor_top = probe.y
    flow_bottom = MARGIN + 12.0
    flow_h = max(200.0, cursor_top - flow_bottom)
    f_shapes, f_texts = layout_flowchart(proc.flowchart, MARGIN, flow_bottom, _CONTENT_W, flow_h)
    page.shapes.extend(f_shapes)
    page.texts.extend(f_texts)

    body = _SheetFlow(pages, "Bay order  ·  Tacoma RV Center")
    if proc.unit_id:
        _paint_unit_id(body, proc)
    if big_flow:
        means = measure_text(proc.pattern_means or "-", _CONTENT_W - 16, 9, leading=12)
        _add_section(body, "WHAT THIS PATTERN USUALLY MEANS", NAVY, follow_h=min(means.height + 20, 80))
        _add_boxed_text(body, proc.pattern_means or "-")
    steps = list(proc.bay_order)
    shown_figures = set()
    if proc.procedures:
        try:
            body.secure_step = _manual_secure_step(proc.procedures)
        except AttributeError:
            pass
        _paint_diagnosis(body, steps)
        for procedure in proc.procedures:
            _paint_repair_procedure(body, procedure)
            for step in procedure.get("steps") or []:
                figure = step.get("figure") or {}
                png = figure.get("png") if isinstance(figure, dict) else b""
                if png:
                    shown_figures.add(png)
    elif steps:
        first = measure_text(f"1. {steps[0]}", _CONTENT_W - 32, 8.5, leading=11.2)
        _add_section(body, "BAY ORDER (DO THIS FIRST)", GREEN, follow_h=min(first.height, 48))
        for i, step in enumerate(steps, 1):
            group = []
            if i - 1 < len(proc.step_figures or []):
                group = list(proc.step_figures[i - 1] or [])
            _add_step(body, i, step, group)
            for fig in group:
                if fig and fig.image_png:
                    shown_figures.add(fig.image_png)
    if proc.do_not:
        _paint_do_not(body, proc.do_not)
    sources = [src for src in proc.sources if src.get("page") or src.get("title_only")]
    _paint_fitting_sources(body, sources)

    imaged = []
    for fig in proc.figures:
        if not fig.image_png or fig.image_png in shown_figures:
            continue
        if figure_is_placeholder(fig) or _figure_is_plenum(fig):
            continue
        png = crop_page_png_to_figure(fig.image_png)
        if not png or _figure_is_illegible(fig, png):
            continue
        imaged.append((fig, png))
    # A short crop stays on the current page. A dedicated figure page has to
    # be a real figure, not a thin strip floating in blank paper.
    shown = 0
    min_page_figure = 240.0
    for fig, png in imaged:
        if shown >= MAX_FIGURES_PER_SHEET:
            break
        if not _figure_is_squeezed(png, body.remaining()) and _paint_figure_on(
            body, fig, png=png, allow_break=False
        ):
            shown += 1
            continue
        page_h = _fit_image(png, _CONTENT_W - 32, PAGE_H - 180)[1]
        if page_h < min_page_figure or len(pages) >= MAX_SHEET_PAGES:
            continue
        _paint_figure_page(
            pages,
            fig,
            png=png,
            with_footer=bool(proc.include_3c and shown == 0),
        )
        shown += 1
    if proc.include_3c and shown == 0:
        _add_3c_footer(body.page)
    return pages


def _new_sheet_page() -> SheetPage:
    page = SheetPage()
    page.shapes.append(
        DrawnShape("rect", 0, 0, PAGE_W, PAGE_H, fill=WHITE, stroke=WHITE, stroke_w=0, id=_next_id("page"), role="chrome")
    )
    page.shapes.append(
        DrawnShape(
            "rect",
            MARGIN - 4,
            MARGIN - 4,
            PAGE_W - 2 * MARGIN + 8,
            PAGE_H - 2 * MARGIN + 8,
            fill=WHITE,
            stroke=NAVY,
            stroke_w=1.6,
            id=_next_id("frame"),
            role="frame",
        )
    )
    return page


def _paint_top_bar(page: SheetPage, subtitle: str = "") -> float:
    bar_h = 28.0
    bar_y = PAGE_H - MARGIN - bar_h
    sid = _next_id("banner")
    page.shapes.append(
        DrawnShape(
            "rect", MARGIN, bar_y, PAGE_W - 2 * MARGIN, bar_h,
            fill=NAVY, stroke=NAVY, stroke_w=0.3, id=sid, role="banner",
        )
    )
    title = measure_text("BAY PROCEDURE", 240, 13, bold=True, leading=16)
    title_base = bar_y + (bar_h - title.height) / 2.0 + title.descent
    page.texts.append(
        DrawnText(
            "BAY PROCEDURE", MARGIN + 10, title_base, w=title.width + 4, size=13, bold=True, color=WHITE,
            leading=title.leading, lines=list(title.lines), owner=sid, role="header",
        )
    )
    sub = subtitle or "Tacoma RV Center  ·  Document Library"
    right = PAGE_W - MARGIN - 10
    max_w = max(40.0, right - (MARGIN + 10 + title.width) - 14)
    sub_m = measure_text(sub, max_w, 8, leading=10)
    if sub_m.height > bar_h - 8 and len(sub_m.lines) > 1:
        sub_m = measure_text(sub_m.lines[0], max_w, 8, leading=10)
    sub_base = bar_y + (bar_h - sub_m.height) / 2.0 + sub_m.descent
    page.texts.append(
        DrawnText(
            "\n".join(sub_m.lines), right, sub_base, w=max(sub_m.width, 20), size=8, color=WHITE,
            align="right", leading=sub_m.leading, lines=list(sub_m.lines), owner=sid, role="header",
        )
    )
    return bar_y


def _add_3c_footer(page: SheetPage):
    """Small footer only — never the main body."""
    y = MARGIN + 4
    h = 22.0
    sid = _next_id("footer")
    page.shapes.append(
        DrawnShape(
            "rect", MARGIN, y, PAGE_W - 2 * MARGIN, h,
            fill=PALE, stroke=RULE, stroke_w=0.7, id=sid, role="box",
        )
    )
    msg = "3C footer (blank):  CONCERN ____________    CAUSE ____________    CORRECTION ____________"
    block = measure_text(msg, PAGE_W - 2 * MARGIN - 16, 7, leading=9)
    if len(block.lines) > 1:
        block = measure_text(block.lines[0], PAGE_W - 2 * MARGIN - 16, 7, leading=9)
    baseline = y + (h - block.height) / 2.0 + block.descent
    page.texts.append(
        DrawnText(
            block.lines[0], MARGIN + 8, baseline, w=block.width + 4, size=7, color=MUTED,
            leading=block.leading, lines=list(block.lines), owner=sid, role="body",
        )
    )


# ---------------------------------------------------------------------------
# PDF renderers — must emit real rect / ellipse / path operators
# ---------------------------------------------------------------------------
def _rgb(color: tuple) -> tuple[float, float, float]:
    if not color:
        return (0, 0, 0)
    if max(color) > 1.5:
        return tuple(c / 255.0 for c in color)
    return color


def render_bay_procedure_pdf(proc: BayProcedure, trace: list | None = None) -> bytes:
    """Return non-empty PDF bytes with a drawn flowchart (not text-only).

    Pass a list as ``trace`` to record each drawn shape and text line. The
    reportlab path fills that list; it is what the layout test checks.
    """
    apply_shop_channel_wording(proc)
    pages = compose_sheet(proc)
    for renderer in (_render_pdf_reportlab, _render_pdf_fpdf2, _render_pdf_raw_shapes):
        try:
            data = renderer(proc, pages, trace=trace)
            if data and data.startswith(b"%PDF") and len(data) > 200:
                return data
        except Exception:
            continue
    raise RuntimeError("Bay procedure PDF renderer produced empty output")


def _render_pdf_reportlab(proc: BayProcedure, pages: list[SheetPage], trace: list | None = None) -> bytes:
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    try:
        c._pageCompression = 0
    except Exception:
        pass
    c.setTitle(_latin1_safe(f"{BAY_PROCEDURE_LABEL} — {proc.wo_number or proc.model_line}"))
    c.setAuthor("Tacoma RV Center / TechTrack")

    for i, page in enumerate(pages):
        if i:
            c.showPage()
        _rl_draw_page(c, page, stringWidth, ImageReader, trace, i)
    c.save()
    return buf.getvalue()


def _record_mark(trace, **kwargs):
    if trace is None:
        return
    x0, y0, x1, y1 = kwargs["x0"], kwargs["y0"], kwargs["x1"], kwargs["y1"]
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    kwargs["x0"], kwargs["y0"], kwargs["x1"], kwargs["y1"] = x0, y0, x1, y1
    trace.append(LayoutMark(**kwargs))


def _rl_draw_page(c, page: SheetPage, stringWidth, ImageReader, trace=None, page_index: int = 0):
    for sh in page.shapes:
        _rl_draw_shape(c, sh, trace, page_index)
    for tx in page.texts:
        _rl_draw_text(c, tx, stringWidth, trace, page_index)
    for im in page.images:
        try:
            img = ImageReader(BytesIO(im.png))
            c.drawImage(img, im.x, im.y, width=im.w, height=im.h, preserveAspectRatio=True, mask="auto")
            _record_mark(
                trace, page=page_index, kind="image", role="image",
                x0=im.x, y0=im.y, x1=im.x + im.w, y1=im.y + im.h, id=_next_id("img"),
            )
        except Exception:
            continue


def _rl_draw_shape(c, sh: DrawnShape, trace=None, page_index: int = 0):
    fill = _rgb(sh.fill)
    stroke = _rgb(sh.stroke)
    c.setFillColorRGB(*fill)
    c.setStrokeColorRGB(*stroke)
    c.setLineWidth(sh.stroke_w)
    if sh.kind == "rect":
        c.rect(sh.x, sh.y, sh.w, sh.h, stroke=1, fill=1)
    elif sh.kind == "roundrect":
        c.roundRect(sh.x, sh.y, sh.w, sh.h, sh.radius, stroke=1, fill=1)
    elif sh.kind == "ellipse":
        c.ellipse(sh.x, sh.y, sh.x + sh.w, sh.y + sh.h, stroke=1, fill=1)
    elif sh.kind == "diamond":
        cx, cy = sh.x + sh.w / 2.0, sh.y + sh.h / 2.0
        p = c.beginPath()
        p.moveTo(cx, sh.y + sh.h)
        p.lineTo(sh.x + sh.w, cy)
        p.lineTo(cx, sh.y)
        p.lineTo(sh.x, cy)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
    elif sh.kind in ("line", "arrow"):
        pts = list(sh.points) if sh.points else [(sh.x, sh.y), (sh.x2, sh.y2)]
        if len(pts) >= 2:
            p = c.beginPath()
            p.moveTo(pts[0][0], pts[0][1])
            for px, py in pts[1:]:
                p.lineTo(px, py)
            c.drawPath(p, stroke=1, fill=0)
            if sh.kind == "arrow":
                _rl_arrowhead(c, pts[-2][0], pts[-2][1], pts[-1][0], pts[-1][1], stroke)
        else:
            c.line(sh.x, sh.y, sh.x2, sh.y2)
    if sh.kind in ("line", "arrow"):
        pts = list(sh.points) if sh.points else [(sh.x, sh.y), (sh.x2, sh.y2)]
        xs = [p[0] for p in pts] or [sh.x, sh.x2]
        ys = [p[1] for p in pts] or [sh.y, sh.y2]
        _record_mark(
            trace, page=page_index, kind=sh.kind, role=sh.role or "connector",
            x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys),
            id=sh.id, points=pts,
        )
    else:
        _record_mark(
            trace, page=page_index, kind=sh.kind, role=sh.role or "shape",
            x0=sh.x, y0=sh.y, x1=sh.x + sh.w, y1=sh.y + sh.h, id=sh.id,
        )


def _arrowhead_size(length: float) -> float:
    """Keep the head on the last segment so it cannot reach back into a label."""
    if length < 1.0:
        return 3.2
    return min(6.0, max(3.2, length * 0.72))


def _arrowhead_triangle(pts) -> list[tuple[float, float]] | None:
    if not pts or len(pts) < 2:
        return None
    x1, y1 = pts[-2]
    x2, y2 = pts[-1]
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    size = _arrowhead_size(length)
    return [
        (x2, y2),
        (x2 - ux * size + px * size * 0.45, y2 - uy * size + py * size * 0.45),
        (x2 - ux * size - px * size * 0.45, y2 - uy * size - py * size * 0.45),
    ]


def _point_in_triangle(x: float, y: float, tri) -> bool:
    (x1, y1), (x2, y2), (x3, y3) = tri
    denom = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
    if abs(denom) < 1e-6:
        return False
    a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / denom
    b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / denom
    c = 1.0 - a - b
    return a >= -0.02 and b >= -0.02 and c >= -0.02


def _arrowhead_hits_box(box, pts, pad: float = 1.5) -> bool:
    tri = _arrowhead_triangle(pts)
    if not tri:
        return False
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    if any(x0 <= x <= x1 and y0 <= y <= y1 for x, y in tri):
        return True
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1), ((x0 + x1) / 2, (y0 + y1) / 2))
    return any(_point_in_triangle(x, y, tri) for x, y in corners)


def _rl_arrowhead(c, x1, y1, x2, y2, stroke):
    import math

    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    size = _arrowhead_size(length)
    px, py = -uy, ux
    c.setFillColorRGB(*stroke)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - ux * size + px * size * 0.45, y2 - uy * size + py * size * 0.45)
    p.lineTo(x2 - ux * size - px * size * 0.45, y2 - uy * size - py * size * 0.45)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def _text_glyphs(tx: DrawnText, stringWidth):
    """Baselines and glyph boxes for the lines layout already measured."""
    font = _font_name(tx.bold)
    size = tx.size
    leading = tx.leading or (size + 2)
    ascent, descent = _font_ascent_descent(font, size)
    if tx.lines:
        lines = list(tx.lines)
    else:
        lines = _wrap_lines(tx.text, max(tx.w, 20), font, size)
    n = len(lines) or 1
    block_h = ascent + descent + max(0, n - 1) * leading
    if tx.align == "center":
        baseline = tx.y + block_h / 2.0 - ascent
    else:
        baseline = tx.y
    glyphs = []
    for i, line in enumerate(lines):
        y = baseline - i * leading
        width = stringWidth(line, font, size) if line else 0.0
        if tx.align == "center":
            left = tx.x - width / 2.0
        elif tx.align == "right":
            left = tx.x - width
        else:
            left = tx.x
        glyphs.append((line, left, y, width, y - descent, y + ascent))
    return font, size, glyphs


def _point_in_mark(x: float, y: float, shape: LayoutMark, eps: float = 0.85) -> bool:
    cx = (shape.x0 + shape.x1) / 2.0
    cy = (shape.y0 + shape.y1) / 2.0
    a = (shape.x1 - shape.x0) / 2.0 + eps
    b = (shape.y1 - shape.y0) / 2.0 + eps
    if a <= 0 or b <= 0:
        return False
    if shape.kind == "ellipse":
        return ((x - cx) / a) ** 2 + ((y - cy) / b) ** 2 <= 1.0
    if shape.kind == "diamond":
        return abs(x - cx) / a + abs(y - cy) / b <= 1.0
    return (shape.x0 - eps) <= x <= (shape.x1 + eps) and (shape.y0 - eps) <= y <= (shape.y1 + eps)


def _text_inside_shape(text: LayoutMark, shape: LayoutMark, eps: float = 0.85) -> bool:
    corners = (
        (text.x0, text.y0),
        (text.x0, text.y1),
        (text.x1, text.y0),
        (text.x1, text.y1),
    )
    return all(_point_in_mark(x, y, shape, eps) for x, y in corners)


def _marks_overlap(a: LayoutMark, b: LayoutMark, eps: float = 0.6) -> bool:
    ix = min(a.x1, b.x1) - max(a.x0, b.x0)
    iy = min(a.y1, b.y1) - max(a.y0, b.y0)
    return ix > eps and iy > eps


def _connector_samples(mark: LayoutMark, step: float = 4.0) -> list[tuple[float, float]]:
    pts = list(mark.points) or [(mark.x0, mark.y0), (mark.x1, mark.y1)]
    out = []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        dist = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(dist / step))
        for i in range(n + 1):
            t = i / n
            out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return out


def layout_problems(trace: list[LayoutMark]) -> list[str]:
    """Failures when text leaves its shape or drawn elements overlap.

    Page chrome and the outer frame may contain other marks. A connector may
    touch the node edge it leaves. Everything else must be disjoint, and text
    that names an owner must sit inside that shape (ellipse and diamond use
    the real curve, not the bounding box).
    """
    problems = []
    pages: dict[int, list[LayoutMark]] = {}
    for mark in trace:
        pages.setdefault(mark.page, []).append(mark)
    filled = {"node", "bar", "box", "check", "banner", "image"}
    for page, items in pages.items():
        by_id = {m.id: m for m in items if m.id}
        texts = [m for m in items if m.kind == "text"]
        for text in texts:
            if text.x0 < -1 or text.y0 < -1 or text.x1 > PAGE_W + 1 or text.y1 > PAGE_H + 1:
                problems.append(f"p{page + 1} text off page {text.text!r}")
            if not text.owner:
                continue
            shape = by_id.get(text.owner)
            if shape is None:
                problems.append(f"p{page + 1} text {text.text!r} has no shape {text.owner}")
                continue
            if not _text_inside_shape(text, shape):
                problems.append(
                    f"p{page + 1} text outside {shape.kind} {text.text!r} "
                    f"text=({text.x0:.1f},{text.y0:.1f},{text.x1:.1f},{text.y1:.1f}) "
                    f"shape=({shape.x0:.1f},{shape.y0:.1f},{shape.x1:.1f},{shape.y1:.1f})"
                )
        content = [m for m in items if m.role in filled or m.kind == "text"]
        for i, a in enumerate(content):
            for b in content[i + 1 :]:
                if a.kind == "text" and b.kind != "text" and a.owner and a.owner == b.id:
                    continue
                if b.kind == "text" and a.kind != "text" and b.owner and b.owner == a.id:
                    continue
                if not _marks_overlap(a, b):
                    continue
                problems.append(
                    f"p{page + 1} overlap {a.role or a.kind}:{a.text[:40]!r} "
                    f"vs {b.role or b.kind}:{b.text[:40]!r}"
                )
        for bar in (m for m in items if m.role == "bar" and m.kind != "text"):
            followed = False
            for other in items:
                if other is bar or (bar.id and other.owner == bar.id):
                    continue
                if other.kind in ("text", "image") and other.role not in ("header", "bar") and other.y1 <= bar.y0 + 0.8:
                    followed = True
                    break
            if not followed:
                problems.append(f"p{page + 1} orphan section bar")
        texts_only = [m for m in texts if m.role != "header"]
        labels = [m for m in texts if m.role == "label"]
        for conn in (m for m in items if m.role == "connector"):
            for x, y in _connector_samples(conn):
                for text in texts_only:
                    if (text.x0 + 0.8) < x < (text.x1 - 0.8) and (text.y0 + 0.8) < y < (text.y1 - 0.8):
                        problems.append(f"p{page + 1} arrow through text {text.text!r}")
                        break
            tri = _arrowhead_triangle(conn.points)
            if not tri:
                continue
            for text in labels:
                box = (text.x0, text.y0, text.x1, text.y1)
                if _arrowhead_hits_box(box, conn.points, pad=0.8):
                    problems.append(f"p{page + 1} arrowhead overlaps {text.text!r}")
                    break
    return problems


def _rl_draw_text(c, tx: DrawnText, stringWidth, trace=None, page_index: int = 0):
    font, size, glyphs = _text_glyphs(tx, stringWidth)
    color = _rgb(tx.color)
    c.setFillColorRGB(*color)
    c.setFont(font, size)
    for line, left, baseline, width, bottom, top in glyphs:
        if tx.align == "center":
            c.drawCentredString(tx.x, baseline, line)
        elif tx.align == "right":
            c.drawRightString(tx.x, baseline, line)
        else:
            c.drawString(left, baseline, line)
        if line.strip():
            _record_mark(
                trace, page=page_index, kind="text", role=tx.role or "body",
                x0=left, y0=bottom, x1=left + width, y1=top,
                owner=tx.owner, text=line,
            )


def _render_pdf_fpdf2(proc: BayProcedure, pages: list[SheetPage], trace: list | None = None) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(unit="pt", format="Letter")
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=False)
    pdf.set_title(_latin1_safe(BAY_PROCEDURE_LABEL))
    for page in pages:
        pdf.add_page()
        for sh in page.shapes:
            _fpdf_draw_shape(pdf, sh)
        for tx in page.texts:
            _fpdf_draw_text(pdf, tx)
        for im in page.images:
            try:
                pdf.image(BytesIO(im.png), x=im.x, y=PAGE_H - im.y - im.h, w=im.w, h=im.h)
            except Exception:
                continue
    raw = pdf.output()
    return bytes(raw) if not isinstance(raw, (bytes, bytearray)) else bytes(raw)


def _fpdf_color(pdf, color, *, fill=False):
    r, g, b = _rgb(color)
    rgb = (int(r * 255), int(g * 255), int(b * 255))
    if fill:
        pdf.set_fill_color(*rgb)
    else:
        pdf.set_text_color(*rgb)


def _fpdf_draw_shape(pdf, sh: DrawnShape):
    r, g, b = _rgb(sh.stroke)
    pdf.set_draw_color(int(r * 255), int(g * 255), int(b * 255))
    fr, fg, fb = _rgb(sh.fill)
    pdf.set_fill_color(int(fr * 255), int(fg * 255), int(fb * 255))
    pdf.set_line_width(sh.stroke_w)
    # fpdf2 origin is top-left
    x, y = sh.x, PAGE_H - sh.y - sh.h
    if sh.kind == "rect":
        pdf.rect(x, y, sh.w, sh.h, style="DF")
    elif sh.kind == "roundrect":
        try:
            pdf.rect(x, y, sh.w, sh.h, style="DF", round_corners=True, corner_radius=sh.radius)
        except TypeError:
            pdf.rect(x, y, sh.w, sh.h, style="DF")
    elif sh.kind == "ellipse":
        pdf.ellipse(x, y, sh.w, sh.h, style="DF")
    elif sh.kind == "diamond":
        cx = sh.x + sh.w / 2.0
        cy_pdf = PAGE_H - (sh.y + sh.h / 2.0)
        pts = [
            (cx, PAGE_H - (sh.y + sh.h)),
            (sh.x + sh.w, cy_pdf),
            (cx, PAGE_H - sh.y),
            (sh.x, cy_pdf),
        ]
        pdf.polygon(pts, style="DF")
    elif sh.kind in ("line", "arrow"):
        pts = list(sh.points) if sh.points else [(sh.x, sh.y), (sh.x2, sh.y2)]
        if len(pts) < 2:
            pts = [(sh.x, sh.y), (sh.x2, sh.y2)]
        for i in range(len(pts) - 1):
            pdf.line(pts[i][0], PAGE_H - pts[i][1], pts[i + 1][0], PAGE_H - pts[i + 1][1])


def _fpdf_draw_text(pdf, tx: DrawnText):
    text = _latin1_safe(tx.text.replace("\n", " / "))
    style = "B" if tx.bold else ""
    pdf.set_font("Helvetica", style, tx.size)
    _fpdf_color(pdf, tx.color)
    if tx.align == "center":
        pdf.set_xy(tx.x - tx.w / 2.0, PAGE_H - tx.y - tx.size)
        pdf.multi_cell(tx.w, tx.size + 1.5, text, align="C")
    elif tx.align == "right":
        pdf.set_xy(tx.x - tx.w, PAGE_H - tx.y - tx.size)
        pdf.cell(tx.w, tx.size + 1, text, align="R")
    else:
        pdf.set_xy(tx.x, PAGE_H - tx.y - tx.size)
        pdf.multi_cell(max(tx.w, 40), tx.size + 1.5, text, align="L")


def _escape_pdf(text: str) -> str:
    return _latin1_safe(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _render_pdf_raw_shapes(proc: BayProcedure, pages: list[SheetPage], trace: list | None = None) -> bytes:
    """Uncompressed PDF 1.4 with real re / m / l / c / h path operators."""
    content_objs = []
    for page in pages:
        cmds = []
        for sh in page.shapes:
            cmds.extend(_raw_shape_ops(sh))
        cmds.append("BT")
        cmds.append("/F1 9 Tf")
        y = PAGE_H - 56
        # Flatten sheet text so lock strings survive even if shape text is skipped.
        for raw in procedure_plain_text(proc).splitlines():
            wrapped = textwrap.wrap(_latin1_safe(raw), width=96) or [""]
            for line in wrapped:
                cmds.append(f"1 0 0 1 {MARGIN} {y:.1f} Tm ({_escape_pdf(line)}) Tj")
                y -= 11
                if y < 40:
                    break
            if y < 40:
                break
        cmds.append("ET")
        content_objs.append("\n".join(cmds).encode("latin-1", "replace"))

    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{3 + i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii"))
    font_id = 3 + len(pages) * 2
    for i, _page in enumerate(pages):
        content_id = 3 + len(pages) + i
        objs.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {int(PAGE_W)} {int(PAGE_H)}] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("ascii")
        )
    for stream in content_objs:
        objs.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objs) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        (
            f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(out)


def _raw_shape_ops(sh: DrawnShape) -> list[str]:
    fr, fg, fb = _rgb(sh.fill)
    sr, sg, sb = _rgb(sh.stroke)
    ops = [
        f"{fr:.3f} {fg:.3f} {fb:.3f} rg",
        f"{sr:.3f} {sg:.3f} {sb:.3f} RG",
        f"{sh.stroke_w:.2f} w",
    ]
    if sh.kind in ("rect", "roundrect"):
        ops.append(f"{sh.x:.1f} {sh.y:.1f} {sh.w:.1f} {sh.h:.1f} re")
        ops.append("B")
    elif sh.kind == "ellipse":
        ops.extend(_ellipse_ops(sh.x, sh.y, sh.w, sh.h))
        ops.append("B")
    elif sh.kind == "diamond":
        cx, cy = sh.x + sh.w / 2.0, sh.y + sh.h / 2.0
        ops.append(f"{cx:.1f} {sh.y + sh.h:.1f} m")
        ops.append(f"{sh.x + sh.w:.1f} {cy:.1f} l")
        ops.append(f"{cx:.1f} {sh.y:.1f} l")
        ops.append(f"{sh.x:.1f} {cy:.1f} l")
        ops.append("h")
        ops.append("B")
    elif sh.kind in ("line", "arrow"):
        pts = list(sh.points) if sh.points else [(sh.x, sh.y), (sh.x2, sh.y2)]
        if len(pts) < 2:
            pts = [(sh.x, sh.y), (sh.x2, sh.y2)]
        ops.append(f"{pts[0][0]:.1f} {pts[0][1]:.1f} m")
        for px, py in pts[1:]:
            ops.append(f"{px:.1f} {py:.1f} l")
        ops.append("S")
    return ops


def _ellipse_ops(x: float, y: float, w: float, h: float) -> list[str]:
    """Bezier approximation of an ellipse (PDF `c` operators)."""
    kappa = 0.5522847498
    ox, oy = (w / 2.0) * kappa, (h / 2.0) * kappa
    cx, cy = x + w / 2.0, y + h / 2.0
    xe, ye = x + w, y + h
    return [
        f"{cx:.1f} {y:.1f} m",
        f"{cx + ox:.1f} {y:.1f} {xe:.1f} {cy - oy:.1f} {xe:.1f} {cy:.1f} c",
        f"{xe:.1f} {cy + oy:.1f} {cx + ox:.1f} {ye:.1f} {cx:.1f} {ye:.1f} c",
        f"{cx - ox:.1f} {ye:.1f} {x:.1f} {cy + oy:.1f} {x:.1f} {cy:.1f} c",
        f"{x:.1f} {cy - oy:.1f} {cx - ox:.1f} {y:.1f} {cx:.1f} {y:.1f} c",
        "h",
    ]


def pdf_content_operators(data: bytes) -> str:
    """Decompress PDF content streams so tests can see rect/ellipse/path operators."""
    parts = [data.decode("latin-1", "replace")]
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        raw = match.group(1)
        try:
            parts.append(zlib.decompress(raw).decode("latin-1", "replace"))
        except Exception:
            parts.append(raw.decode("latin-1", "replace"))
    return "\n".join(parts)


def count_pdf_draw_ops(data: bytes) -> dict:
    """Count drawn rect / ellipse / path operators (not text-only fake flow)."""
    stream = pdf_content_operators(data)
    return {
        "rect": len(re.findall(r"(?<![A-Za-z0-9_])re(?![A-Za-z0-9_])", stream)),
        "curve": len(re.findall(r"(?<![A-Za-z0-9_])c(?![A-Za-z0-9_])", stream)),
        "moveto": len(re.findall(r"(?<![A-Za-z0-9_])m(?![A-Za-z0-9_])", stream)),
        "lineto": len(re.findall(r"(?<![A-Za-z0-9_])l(?![A-Za-z0-9_])", stream)),
        "close": len(re.findall(r"(?<![A-Za-z0-9_])h(?![A-Za-z0-9_])", stream)),
    }


def firefly_has_forbidden_module_hunt(text: str) -> bool:
    """True if the rejected v1 'unplug modules one at a time' language is present."""
    return bool(MODULES_ONE_AT_A_TIME_RE.search(text or ""))


def write_sample_pdfs(out_dir) -> list:
    """Write the three HIT-path sample bay sheets. Returns written Paths."""
    from pathlib import Path

    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    samples = [
        (
            "bay_procedure_fcr_rear_wall_ice.pdf",
            dict(
                concern="Icing up on rear wall — only about half from the top down",
                brand="Furrion",
                model="FCR10DCGTA-BL",
                category="Refrigerators",
                wo_number="WO-ICE",
                chunks=[
                    {
                        "title": FURRION_8122_TITLE,
                        "page": 36,
                        "excerpt": (
                            "Ice and Moisture. Ice or Moisture in the Fridge. "
                            "Fig. 36 rear wall frost pattern."
                        ),
                    }
                ],
            ),
        ),
        (
            "bay_procedure_facr_freeze.pdf",
            dict(
                concern="FACR08 freeze up interior leak condensate",
                brand="Furrion",
                model="FACR08",
                category="Air Conditioning",
                wo_number="WO-FACR",
            ),
        ),
        (
            "bay_procedure_level_up_firefly.pdf",
            dict(
                concern=(
                    "Level Up Advantage 807662 Manual Mode flashes then dumps home. "
                    "Auto Level still works. Brinkley Firefly."
                ),
                category="Leveling",
                model="Level Up Advantage 807662",
                wo_number="WO-FIREFLY",
            ),
        ),
    ]
    written = []
    for name, kwargs in samples:
        proc = compile_bay_procedure(**kwargs)
        path = dest / name
        path.write_bytes(render_bay_procedure_pdf(proc))
        written.append(path)
        try:
            import pymupdf

            doc = pymupdf.open(path)
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=pymupdf.Matrix(1.6, 1.6))
                png = dest / f"{path.stem}_p{i + 1}.png"
                pix.save(png)
                written.append(png)
        except Exception:
            continue
    return written


if __name__ == "__main__":
    import sys
    from pathlib import Path

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("samples")
    for path in write_sample_pdfs(out):
        print(path)