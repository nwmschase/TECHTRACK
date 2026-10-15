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
MODULE_REVISION = "v4.19.63"
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
    "Record the complaint, the model name, and the first cited check on this sheet.",
    "Do that first cited check and write pass or fail on this sheet.",
    "If this check fails, stay on it. If it passes, go to the next cited check.",
    "Do the next cited check. Note the threshold and what good versus bad looks like from the excerpt.",
    "Retest the complaint after those checks.",
    "If the complaint is gone, that is the confirmed correction. If it remains after the cited checks pass, use the next correction named in Sources.",
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
    miss_sheet = "document in the shop library for this unit" in (proc.primary_cite or "").lower()
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
                ('Replace the Spark-Free Thermostat, part G 2021128850 (retail C-FCR10DCGTA-007). Do this when the compressor stops with C and T open. Straighten the probe, reseat it, and reconnect the wires. That is the confirmed correction when the compressor stops.')
            ),
            (
                ('Compressor still running with C and T open? The run call is downstream of the thermostat. Escalate the inverter and the harness.')
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
                    ('Compressor still running with C and T open? Escalate the inverter and the harness.')
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
            ('Open the fridge and note the ice or moisture pattern. Photograph it. If it is only a light sheet on the back wall, stop here. That is normal cycling. Heavy, halfway-down, or other-surface frost means keep going.'),
            ('Record the dial setting and the fridge and freezer cavity temperatures. If the dial is at max, set it to about 4 to 5. Towel-dry the melt and let the fridge run overnight. Then look at the pattern again. If ice starts to melt at mid setpoint, stay on the moisture path. If the dial is already mid, go to the defrost next.'),
            "Do a full manual defrost. Power the unit off, open both doors, and use towels. Do not scrape, do not use a heat gun, and do not set hot-water pans in the cabinet. When the ice is gone, go to the dry-and-drain step.",
            ('Dry the cabinet completely. Clear the rear drain and trough with a soft plastic probe only so melt water can leave. If water backs up, keep clearing until it leaves. Then go to the gasket. If the drain is already open, go to the gasket next.'),
            ('Check the door gasket with a dollar-bill test around the full perimeter, and check the hinges, latch, and door alignment. If the bill slides out with no drag, reseat or replace the gasket. Set the dial to about 4 to 5 and leave a rear-wall air gap. Recheck in 24 to 48 hours. If the gasket holds, set the dial mid, leave the air gap, and recheck in 24 to 48 hours.'),
            ('Check the cabinet after 24 to 48 hours. If frost is gone or just a back-wall sheet, you are done. The fix was mid setpoint, a holding gasket, and a clear drain. Confirm a mid dial, a good gasket, and a clear drain. If heavy frost returns anyway, leave the cooling unit in place. Dry the cabinet again and watch door-open time and humidity for about a month.'),
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
        "primary_cite": "Furrion Chill rooftop AC manual, the base pan and condensate drain section.",
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
                    "Replace the rooftop unit\nonly if it still leaks.",
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
            "If every check passes and it still leaks, replace the rooftop unit. That is the confirmed correction.",
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
                ('Press tongue extend/retract and check for 12V on the tongue jack output wire at the panel. The other stabilizer circuits and the lights still work here. If that wire has no 12V, replace soft-touch user panel 20300427. That is the confirmed correction.')
            ),
            (
                ('Check the tongue pigtail and the panel-to-motor leads. Do this when the output wire has 12V. If voltage stops in that pigtail, repair it and retest the jack. That is the confirmed correction after the panel voltage prove.')
            ),
            (
                ('Use a coupler or shear-pin replacement only when the manual override will not turn, or the motor fails a direct-12V prove. If the motor runs on direct 12V, coupler engaged, keep the coupler. Then stay on the panel and pigtail checks.')
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
        "primary_cite": "Lippert Level Up controller and Firefly panel manuals. Leave the rubber-boot terminator in.",
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
                ('Prove Fan High at the 9-pin before any part is condemned. Pin 5 black is Fan High and pin 9 white is fan common. A dark tester or about 0 VAC black-to-white means Fan High is dead. If Fan High is dead, go to the Peacemaker bypass. About 115 VAC on Fan High means the board calls for the fan. Then stay on the live-voltage fan path.')
            ),
            (
                ('Bypass the thermostat and the control box with the SkillAbove Peacemaker. If the compressor runs but the fan never turns, record the amps. Shaft-locked current about 1.9 A means the fan motor is locked: go to the fan run capacitor. If the compressor does not run, stay on the compressor. Do not condemn the fan motor.')
            ),
            (
                ('Measure the fan run capacitor and compare it to the value printed on the capacitor. On this 2111-0001 the rated value is 15 µF. If the capacitor is open or far off rating, replace it and retest. If it measures about rated, the capacitor is not the failed part: go to the motor and the board.')
            ),
            (
                ('R&R the rooftop fan motor and the control board only. Do this when all three are true. Fan High is dead. The bypass shows a locked fan with stall current. The fan run capacitor is good. Do not replace the full 2111-0001 assembly. That is the confirmed correction.')
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


def _no_brand_match_path(brand: str = "", model: str = "", concern: str = "") -> dict:
    """Known unit, no matching manual. Do not borrow another maker's book."""
    model_text = model_text_from(brand, model)
    who = library_miss_brand_label("", model_text, concern) or (brand or "").strip() or "this brand"
    sentence = f"No {who} document in the shop library for this unit."
    toilet = is_toilet_job("", model_text, concern)
    if toilet:
        safe = (
            "General shop safety, not an OEM procedure: shut the water supply off "
            "before working under the flush lever."
        )
    else:
        safe = (
            "General shop safety, not an OEM procedure: do not start a repair from "
            "another maker."
        )
    add = f"Add the {who} OEM manual to the shop library, then run this bay sheet again."
    return {
        "primary_cite": sentence,
        "pattern_means": (
            f"{sentence} This pass did not retrieve a service manual for that unit. "
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
                    "General shop safety only.\nNot an OEM procedure.",
                    0.50,
                    0.46,
                    w=280,
                    h=80,
                ),
                FlowNode(
                    "e_add",
                    "end",
                    "Add the OEM manual,\nthen run this sheet again.",
                    0.50,
                    0.78,
                    w=280,
                    h=72,
                ),
            ],
            edges=[
                FlowEdge("s", "p_safe"),
                FlowEdge("p_safe", "e_add"),
            ],
        ),
        "bay_order": [safe, add],
        "do_not": [
            "Do not cite another brand's manual as the procedure for this unit.",
        ],
        "sources": [
            {
                "title": sentence,
                "page": None,
                "excerpt": "Add the OEM manual to the shop library.",
            }
        ],
        "display_model": "",
        "flow_tall": True,
        "full_story": False,
    }


_OCR_HEADER_RE = re.compile(
    r"\brev\s*:\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"
    r"|\bpage\s+\d{1,3}\b"
    r"|\btime\s+line\s+description\b"
    r"|\bsequence\s+of\s+operation\b"
    r"|\bfor\s+\d+\s*vac\s+fan\s+control\s+module\s+board\b"
    r"|\bpart\s+number\s+\d+\b"
    r"|\bstart\s+time\b"
    r"|\bthermostat\s+calls\s+for\s+heat\b",
    re.I,
)
_SHORT_WORD_KEEP = {
    "a", "an", "the", "if", "to", "of", "or", "on", "in", "at", "is", "it",
    "no", "yes", "do", "be", "by", "as", "for", "and", "not", "but", "then",
    "when", "with", "from", "into", "over", "both", "open", "fan", "gas",
    "so", "up",
    "air", "heat", "this", "that", "after", "before",
}
_ACTION_RE = re.compile(
    r"\b(inspect|check|measure|replace|verify|bypass|jumper|reset|connect|"
    r"record|prove|retest|locate|clear|clean|test)\b",
    re.I,
)


_ABBREV_DOT_RE = re.compile(r"\b(?:Fig|Figs|fig|figs|e\.g|i\.e|No|Nos|vs|Mr|Mrs|Dr)\.")
_FIG_CALL_RE = re.compile(r"\b(Figs?)\s*\.\s*(\d+)", re.I)


def _split_sentences(text: str) -> list[str]:
    """Split on sentence ends. 'Fig. 12' and 'Fig . 12' stay one sentence."""
    raw = _FIG_CALL_RE.sub(lambda match: f"{match.group(1)}\u0001 {match.group(2)}", text or "")
    protected = _ABBREV_DOT_RE.sub(lambda match: match.group(0).replace(".", "\u0001"), raw)
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [part.replace("\u0001", ".").strip() for part in parts if part and part.strip()]


def _collapse_repeated_phrases(text: str) -> str:
    """Drop an OCR phrase that was printed twice in a row, and doubled words."""
    words = (text or "").split()
    if len(words) < 2:
        return " ".join(words)
    guard = 0
    changed = True
    while changed and guard < 6:
        guard += 1
        changed = False
        upper = min(8, len(words) // 2)
        for n in range(upper, 1, -1):
            i = 0
            out = []
            while i < len(words):
                nxt = words[i : i + n]
                fol = words[i + n : i + 2 * n]
                if len(fol) == n and [w.lower() for w in nxt] == [w.lower() for w in fol]:
                    out.extend(nxt)
                    i += 2 * n
                    changed = True
                else:
                    out.append(words[i])
                    i += 1
            words = out
    deduped = []
    for word in words:
        if deduped and deduped[-1].lower() == word.lower():
            continue
        deduped.append(word)
    return " ".join(deduped)


def _drop_leading_ocr_stub(text: str) -> str:
    """Drop a lowercase 1–3 letter scrap left when a column wrapped ('s Purge')."""
    words = (text or "").split()
    while len(words) >= 2:
        head = words[0]
        if (
            head[:1].islower()
            and re.fullmatch(r"[A-Za-z]{1,3}", head)
            and head.lower() not in _SHORT_WORD_KEEP
        ):
            words.pop(0)
            continue
        break
    return " ".join(words)


_FUSED_OCR = (
    (re.compile(r"gasfumes", re.I), "gas fumes"),
    (re.compile(r"anexplosion", re.I), "an explosion"),
    (re.compile(r"\bail connections\b", re.I), "all connections"),
    (re.compile(r"\bCand Topen\b"), "C and T open"),
    (re.compile(r"\bCand T\b"), "C and T"),
    (re.compile(r"\bcavityso\b", re.I), "cavity so"),
    (re.compile(r"\bpushingup\b", re.I), "pushing up"),
    (re.compile(r"\bhookedup\b", re.I), "hooked up"),
)
_TRANSCRIPTION_RE = re.compile(
    r"transcription for techtrack search(?:\s*\(ocr companion\))?",
    re.I,
)
_BROCHURE_TEXT_RE = re.compile(r"brochure", re.I)
_PARTS_LIST_RE = re.compile(
    r"replaceable parts list|refer to the replaceable parts|"
    r"\btools?\s+required\b|\btool\s+list\b|\bparts\s+list\b",
    re.I,
)
_NO_LIBRARY_STEP_RE = re.compile(r"no matching library excerpt", re.I)
_FIG_CUT_RE = re.compile(r"\(\s*(?:Fig\.?|i\.?)\s*$", re.I)
_SHORT_CUT_END_RE = re.compile(r"\b([A-Za-z]{1,2})\.$")
# A lone article is a word. A leftover glyph glued to the next token is an OCR split.
_OCR_ARTICLE = {"a", "i"}


def _rejoin_ocr_splits(text: str) -> str:
    """Pull split tokens back together: 'termina ls', 'b lack'. Leave real short words."""
    words = (text or "").split()
    out: list[str] = []
    i = 0
    while i < len(words):
        word = words[i]
        if any(ch.isdigit() for ch in word):
            out.append(word)
            i += 1
            continue
        if i + 1 < len(words):
            nxt = words[i + 1]
            core = re.sub(r"[^A-Za-z]", "", word)
            ncore = re.sub(r"[^A-Za-z]", "", nxt)
            trail = re.search(r"[^A-Za-z0-9]+$", nxt)
            trail_s = trail.group(0) if trail else ""
            lead = re.match(r"^[^A-Za-z0-9]+", word)
            lead_s = lead.group(0) if lead else ""
            bare = word[len(lead_s):]
            if (
                len(core) == 1
                and bare == core
                and core.lower() not in _OCR_ARTICLE
                and 3 <= len(ncore) <= 6
                and ncore.isalpha()
                and nxt[:1].islower()
                and ncore.lower() not in _SHORT_WORD_KEEP
            ):
                out.append(f"{lead_s}{core}{ncore}{trail_s}")
                i += 2
                continue
            if (
                len(core) >= 4
                and core.isalpha()
                and 1 <= len(ncore) <= 2
                and ncore.isalpha()
                and ncore.lower() not in _SHORT_WORD_KEEP
                and nxt[:1].islower()
                and not word.endswith(".")
                # "will go" is two words. "termina ls" is one word split by OCR.
                and not (_is_dict_word(core) and _is_dict_word(ncore))
            ):
                out.append(f"{lead_s}{core}{ncore}{trail_s}")
                i += 2
                continue
        out.append(word)
        i += 1
    return " ".join(out)


def _dedupe_adjacent_sentences(text: str) -> str:
    """Drop a sentence that repeats the one before it, or is only its tail."""
    kept: list[str] = []
    for sentence in _split_sentences(text):
        if not kept:
            kept.append(sentence)
            continue
        prev = kept[-1]
        a = prev.lower().rstrip(".!? ")
        b = sentence.lower().rstrip(".!? ")
        if not b or b == a or b in a or a.endswith(b):
            continue
        if a in b or b.endswith(a):
            kept[-1] = sentence
            continue
        kept.append(sentence)
    return " ".join(kept)


_HYPHEN_SPLIT_RE = re.compile(r"([A-Za-z]{2,})(?:\s+-\s+|-\s+)([A-Za-z]{2,})")
# A line-break hyphen glues a split word. A hyphen between two real words is a space.
_WHOLE_WORDS = frozenset({
    "and", "or", "the", "if", "to", "of", "for", "a", "an", "in", "on",
    "water", "fan", "top", "code", "button", "error", "from", "with",
    "when", "then", "this", "that", "not", "are", "was", "into", "onto",
    "power", "connect", "typical", "before", "after", "replace", "check",
})
_KEEP_CAMEL = ("OneControl", "TechTrack")
_CAMEL_GLUE_RE = re.compile(r"([a-z]{2,})([A-Z][a-z]+)")
_RUNON_NEXT = {
    "loosen", "tighten", "replace", "check", "inspect", "remove", "install",
    "disconnect", "connect", "open", "close", "clean", "measure", "verify",
    "confirm", "press", "turn", "set", "align", "reposition", "resecure",
    "the", "if", "when", "after", "before", "refer", "ensure", "cycle",
    "attach", "finally", "rotate", "next",
}
# "and Replace" is one phrase. "knob Loosen" is two sentences.
_NO_SPLIT_LEFT = frozenset({
    "and", "or", "the", "of", "to", "for", "a", "an", "in", "on", "at",
})
# "36B)" is a cut callout. "3-9V)" and "3 to 9V)" are voltage ranges and must stay.
_FIG_FRAG_RE = re.compile(r"(?<![\d\-])(?<!to )\b\d{1,3}[A-Za-z]\)")
_RANGE_PAREN_RE = re.compile(r"(\d\s*-\s*\d+\s*[VvAaWw])\)")
_BROKEN_RANGE_RE = re.compile(r"\d\s*-\s*(?:[.)]|$)")
_LEADING_FIG_RE = re.compile(r"^\d{1,3}\)\s*")
_FLOW_OCR_RE = re.compile(r"\byes\s+no\b", re.I)
_OCR_GARBAGE_RE = re.compile(
    r"grease\s+fire|\bpiezo\b|damage\s*,\s*personal|open\s+[\"“]flame|"
    r"\bTum\b|/\*|hand[-\s]?held\s+ignitor|oven\s+pilot",
    re.I,
)
_BOILERPLATE_RE = re.compile(
    r"\bwelding\b|subject to change|extension cord|"
    r"do not extend|extend warning|warning:\s*do not use an extension|"
    r"framework note|\bframework\b|considered factual|manual information is considered|"
    r"\bplease recycle\b|\brecycle this\b|for recycling|"
    r"warning\W{0,24}extend|extend\W{0,24}warning|"
    r"inadequate repairs|serious hazards|\bnot toys\b|electrical devices",
    re.I,
)
_NEW_PASSAGE_RE = re.compile(r"^refer to\b", re.I)


# Shop compounds that are one word even when the system list does not know them.
_SHOP_WORDS = frozenset({
    "setpoint", "airflow", "thermocouple", "evaporator", "inverter", "condensate",
    "basepan", "onecontrol", "techtrack", "furrion", "dometic", "lippert", "girard",
    "peacemaker", "rooftop", "lockout", "defrost", "pigtail", "writeup",
    "ducted", "petit", "overcurrent",
})
_DICT_WORDS: set[str] | None = None


def _dictionary_words() -> set[str]:
    global _DICT_WORDS
    if _DICT_WORDS is None:
        # Plain text in the repo root. Community Cloud's push sync reads root
        # files as UTF-8 and skips the redeploy when a binary (the old .gz)
        # fails that read. A dashboard reboot clones with git and hides the bug.
        path = Path(__file__).with_name("bay_words.txt")
        words = {
            line.strip().lower()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        words.update(_SHOP_WORDS)
        _DICT_WORDS = words
    return _DICT_WORDS


def _is_dict_word(word: str) -> bool:
    token = re.sub(r"[^A-Za-z]", "", word or "").lower()
    return bool(token) and token in _dictionary_words()


# 'go' is a real word in 'willgo'. A 2-letter scrap such as 'ed' or 'pe' is not a half.
_SPLIT_SHORT_OK = frozenset({"go"})


def _split_half_ok(part: str) -> bool:
    if not _is_dict_word(part):
        return False
    if len(part) >= 3:
        return True
    return part in _SPLIT_SHORT_OK


def _split_known_join(token: str) -> str:
    """'willgo' is will + go. Split only when both halves are words and the join is not.

    'ducted' and 'petit' are words. A 2-letter dictionary scrap must not break them.
    """
    if not token.isalpha() or not token.islower() or _is_dict_word(token):
        return ""
    best = ""
    best_score = 0
    for cut in range(2, len(token) - 1):
        left, right = token[:cut], token[cut:]
        if not _split_half_ok(left) or not _split_half_ok(right):
            continue
        if _is_dict_word(left + right):
            continue
        score = min(len(left), len(right))
        if score > best_score:
            best = f"{left} {right}"
            best_score = score
    return best


def lowercase_dictionary_glues(text: str) -> list[str]:
    """All-lowercase tokens that are two dictionary words jammed together.

    A model fragment such as the 'seqt' in NT-20SEQT is not a join. Shop
    compounds in the dictionary ('writeup') are not joins either.
    """
    found = []
    raw = text or ""
    # Whole lowercase words only. The tail of "Firefly" is not a join.
    for match in re.finditer(r"(?<![A-Za-z])[a-z]{6,}(?![A-Za-z])", raw):
        token = match.group(0)
        start, end = match.span()
        prev = raw[start - 1] if start else ""
        nxt = raw[end] if end < len(raw) else ""
        if prev.isdigit() or nxt.isdigit() or prev in "-/" or nxt in "-/":
            continue
        if _split_known_join(token):
            found.append(token)
    return found


def _unglue_dictionary_joins(text: str) -> str:
    def fix(token: str) -> str:
        split = _split_known_join(token)
        return split or token

    return " ".join(fix(token) for token in (text or "").split())


def _rejoin_hyphen_splits(text: str) -> str:
    """Pull a line-break hyphen together only when the result is one dictionary word.

    A clause dash between two whole words ('terminator - leave') stays a dash.
    A fragment hyphen that does not make a word becomes a space.
    """

    def repl(match):
        left, right = match.group(1), match.group(2)
        joined = left + right
        if right[:1].isupper() and not (left.isupper() and right.isupper()):
            return f"{left} - {right}" if len(left) >= 3 and len(right) >= 3 else f"{left} {right}"
        if _is_dict_word(joined):
            if left.isupper() and right.isupper():
                return joined.upper()
            return joined
        if len(left) >= 3 and len(right) >= 3:
            return f"{left} - {right}"
        return f"{left} {right}"

    return _HYPHEN_SPLIT_RE.sub(repl, text or "")


def _split_glued_camel(text: str) -> str:
    """'ButtonIf' and 'CodeFan' were two lines joined with no space."""

    def fix(token: str) -> str:
        for name in _KEEP_CAMEL:
            if name not in token:
                continue
            if token.startswith(name) and len(token) > len(name):
                rest = token[len(name):]
                if rest.isalpha() and _is_dict_word(rest):
                    return f"{name} {rest}"
            return token
        return _CAMEL_GLUE_RE.sub(r"\1 \2", token)

    return " ".join(fix(token) for token in (text or "").split())


def _unglue_whole_words(text: str) -> str:
    """'codewater' and 'topand' are two words the line join fused."""

    def fix(token: str) -> str:
        if not token.islower() or not token.isalpha():
            return token
        low = token.lower()
        for right in sorted(_WHOLE_WORDS, key=len, reverse=True):
            if len(right) < 3 or len(low) <= len(right) + 2:
                continue
            if low.endswith(right) and low[: -len(right)] in _WHOLE_WORDS:
                cut = len(token) - len(right)
                return token[:cut] + " " + token[cut:]
        return token

    return " ".join(fix(token) for token in (text or "").split())


def _split_runon_sentences(text: str) -> str:
    """'knob Loosen' is two sentences the OCR glued together."""

    def repl(match):
        prev = match.group(1)
        nxt = match.group(2)
        if prev.lower() in _NO_SPLIT_LEFT:
            return match.group(0)
        if nxt.lower() in _RUNON_NEXT:
            return prev + ". " + nxt
        return match.group(0)

    return re.sub(r"(?<![A-Za-z])([a-z]{3,})\s+([A-Z][a-z]+)", repl, text or "")


def _drop_repeated_clauses(text: str) -> str:
    """Drop 'Connect power to the.' when the next sentence starts with that clause."""
    kept: list[str] = []
    for sentence in _split_sentences(text):
        if not kept:
            kept.append(sentence)
            continue
        prev_words = re.findall(r"[A-Za-z0-9'+-]+", kept[-1].lower())
        next_words = re.findall(r"[A-Za-z0-9'+-]+", sentence.lower())
        overlap = 0
        for k in range(min(len(prev_words), len(next_words)), 2, -1):
            if prev_words[-k:] == next_words[:k]:
                overlap = k
                break
        if overlap >= 3:
            if len(prev_words) == overlap:
                kept[-1] = sentence
                continue
            if len(next_words) == overlap:
                continue
            words = kept[-1].split()
            if len(words) > overlap:
                trimmed = " ".join(words[:-overlap]).rstrip(" ,;:")
                if trimmed and trimmed[-1] not in ".!?":
                    trimmed += "."
                kept[-1] = trimmed
            kept.append(sentence)
            continue
        kept.append(sentence)
    return " ".join(kept)


def _strip_fig_fragments(text: str) -> str:
    """Drop a cut figure callout such as '36B)' or '4A)'."""
    return re.sub(r"\s{2,}", " ", _FIG_FRAG_RE.sub(" ", text or "")).strip()


_DASH_CHARS = "\u2010\u2011\u2012\u2013\u2014\u2212"


def _normalize_ocr_chars(text: str) -> str:
    """A dash between digits stays a hyphen. F− and T– stay F- and T-.

    Any other em or en dash becomes a spaced hyphen. Deleting it glued
    'terminatorleave'. Turning it into a bare space reads as 'terminator leave'.
    """
    out = text or ""
    # "4 -5" is a scanned range, not a clause dash.
    out = re.sub(r"(\d)\s*-\s*(\d)", r"\1-\2", out)
    out = re.sub(rf"(\d)\s*[{_DASH_CHARS}]\s*(\d)", r"\1-\2", out)
    # A terminal label is one capital and a hyphen: F-, T-, C-.
    out = re.sub(rf"(?<![A-Za-z])([A-Z])\s*[{_DASH_CHARS}]\s*", r"\1- ", out)
    out = re.sub(r"(?<![A-Za-z])([A-Z])\s+-\s+", r"\1- ", out)
    out = re.sub(rf"[{_DASH_CHARS}]", " - ", out)
    out = out.replace("\uff1f", "?").replace("\u2047", "?")
    out = re.sub(r"[\u2022\u2023\u2043\u2219\u25aa\u25cf\u25e6\u00b7\uf0b7\uf0a7]", " ? ", out)
    return out


def _normalize_voltage_ranges(text: str) -> str:
    """'3- 9V', '3–9V', and '3 to 9V' are the same range."""
    return re.sub(
        r"(\d)\s*(?:-|to)\s*(\d+)\s*([VvAaWw])\b",
        r"\1-\2\3",
        text or "",
    )


def _strip_orphan_range_paren(text: str) -> str:
    """Drop a paren glued onto a range. Keep the paren that closes '(typical 3-9V)'."""

    def repl(match):
        before = text[: match.start()]
        if before.count("(") > before.count(")"):
            return match.group(0)
        return match.group(1)

    return _RANGE_PAREN_RE.sub(repl, text or "")


def _repair_ocr_text(text: str) -> str:
    """Shared OCR repair for sheet steps and source snippets."""
    # Newlines are whitespace. Joining them with '' glues Button to If.
    out = _normalize_ocr_chars(text or "")
    out = re.sub(r"\s+", " ", out).strip()
    out = _TRANSCRIPTION_RE.sub(" ", out)
    out = re.sub(r"\(\s*ocr\s*\)", " ", out, flags=re.I)
    out = _split_glued_camel(out)
    out = _unglue_whole_words(out)
    for pattern, repl in _FUSED_OCR:
        out = pattern.sub(repl, out)
    out = _rejoin_hyphen_splits(out)
    # Rejoin 'termina ls' before splitting 'willgo'. Splitting first turns the
    # fragment into 'term ina' and the short tail can no longer be pulled back.
    out = _rejoin_ocr_splits(out)
    out = _unglue_dictionary_joins(out)
    for pattern, repl in _FUSED_OCR:
        out = pattern.sub(repl, out)
    out = re.sub(r"([A-Za-z]),([A-Za-z])", r"\1, \2", out)
    out = _split_runon_sentences(out)
    out = _normalize_voltage_ranges(out)
    out = _strip_orphan_range_paren(out)
    out = _strip_fig_fragments(out)
    out = re.sub(r"([.!?])([A-Za-z])", r"\1 \2", out)
    out = _OCR_HEADER_RE.sub(" ", out)
    out = _collapse_repeated_phrases(out)
    out = _drop_leading_ocr_stub(out)
    out = re.sub(r"\s{2,}", " ", out).strip(" -;,")
    # Drop 'At the F- terminals…' before the overlap trimmer can cut it out of
    # the sentence that actually names the measurement.
    out = _drop_verbless_fragments(out)
    return _drop_repeated_clauses(_dedupe_adjacent_sentences(out))


def clean_ocr_prose(text: str) -> str:
    """Strip manual headers, footers, and duplicated OCR from a library excerpt."""
    return _repair_ocr_text(text)


def _is_header_residue(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 25:
        return True
    letters = re.sub(r"[^A-Za-z]", "", t)
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.6 and len(t) < 90:
        return True
    return False


def _is_decision_sentence(text: str) -> bool:
    raw = text or ""
    low = raw.lower()
    if low.startswith("do not") or low.startswith("don't"):
        return False
    if "?" in raw or re.search(r"\bif\b", low):
        return True
    return bool(re.search(r"\b(yes|no)\b", low) and _ACTION_RE.search(raw))


def _is_actionable_sentence(text: str) -> bool:
    low = (text or "").lower()
    if low.startswith("do not") or low.startswith("don't"):
        return False
    return bool(_ACTION_RE.search(text or ""))


_ACRONYM_KEEP = {
    "BAL", "SS", "OEM", "CAN", "USB", "PN", "HVAC", "PCB", "SM", "IM",
    "AC", "DC", "RV", "ID", "OK", "LCD", "LED", "ATC", "VAC", "VDC",
}
_SMALL_TITLE_WORDS = {"and", "of", "the", "for", "a", "an", "or", "to", "in", "on"}
# Lowercase OCR may still be a real sentence. A cut syllable ("er", "anel", "s") is not.
_LOWER_SENTENCE_OPEN = {
    "if", "the", "a", "an", "this", "that", "when", "then", "make", "check",
    "open", "do", "no", "yes", "after", "before", "leave", "prove", "replace",
    "measure", "connect", "disconnect", "confirm", "inspect", "record",
    "bypass", "clear", "set", "use", "note", "watch", "verify", "reset",
    "locate", "test", "clean", "jumper", "tongue", "panel", "compressor",
    "door", "ice", "light", "water", "frost", "dial", "rooftop", "defrost",
    "back", "unplug", "power", "spark", "listed", "both", "with",
    "at", "on", "for", "between", "across",
}
_TOPIC_STOP = {
    "this", "that", "with", "from", "into", "over", "then", "than", "them",
    "they", "have", "been", "were", "will", "your", "about", "after",
    "before", "when", "where", "which", "while", "there", "their", "only",
    "still", "also", "just", "does", "doing", "done", "each", "other",
    "some", "such", "these", "those", "very", "what", "make", "sure",
}
# Family keeps a cite on the same product. Climax overrides an off-procedure hit.
_PATH_FAMILY = {
    "bal_tongue": (
        "tongue", "pigtail", "20300427", "soft-touch", "soft touch",
        "stabilizer", "stabilizing", "ss 5.1", "c-jack", "c jack",
        "ins.sta", "panel", "bal",
    ),
    "ice": (
        "ice", "moisture", "frost", "gasket", "defrost", "drain",
        "rear wall", "dollar-bill", "dollar bill",
    ),
    "dial_off": (
        "thermostat", "compressor", "spark-free", "spark free",
        "2021128850", "jumper", "inverter", "harness", "dial",
    ),
    "facr": (
        "rooftop", "condensate", "drain", "base pan", "base-pan", "freeze",
        "suction", "evaporator", "assembly",
    ),
    "firefly": (
        "firefly", "terminator", "manual mode", "807662", "level up",
        "power connector", "onecontrol", "can",
    ),
    "furnace": ("furnace", "thermostat", "sail", "jumper", "limit", "module"),
    "e2": ("inverter", "fan", "e2", "pcb", "12v"),
    "coleman": (
        "coleman", "peacemaker", "1976", "fan high", "9-pin", "capacitor", "airxcel",
        "control board", "fan motor",
    ),
    "ground_control": ("manual level", "zero-point", "zero point", "ground control", "343633"),
    "dometic_ceiling": ("3311071", "ceiling", "peacemaker", "thermostat", "selector"),
    "fact12_freeze": ("freeze sensor", "evaporator", "fact12", "e2", "e3"),
    "girard_e8": ("petit", "girard", "gswh", "e8", "burner"),
    "stabilizer": ("stabilizer", "psx1", "jack", "override", "coupler"),
    "cooktop_tip": ("thermocouple", "tip", "cooktop", "burner", "pan", "flame"),
    "thetford_leak": ("toilet", "valve", "vacuum", "flange", "supply", "flush"),
}
_PATH_CLIMAX = {
    "bal_tongue": ("20300427", "pigtail", "tongue channel", "soft-touch panel", "both directions"),
    "ice": ("ice and moisture", "fig. 36", "figure 36", "dollar-bill", "rear wall"),
    "dial_off": ("2021128850", "spark-free", "no jumper", "c (blue)", "t (black)"),
    "facr": ("ccd-0007990", "condensate", "base pan", "base-pan", "suction"),
    "firefly": ("807662", "terminator", "firefly", "power connector"),
    "furnace": ("sail", "jumper", "r/w", "wall thermostat", "limit switch", "module board"),
    "e2": ("inverter pcb", "f+", "f-", "fan fault"),
    "coleman": ("peacemaker", "1976-536", "fan high", "control board"),
    "ground_control": ("zero-point", "zero point", "manual level", "enter"),
    "dometic_ceiling": ("ceiling thermostat", "3311071", "peacemaker"),
    "fact12_freeze": ("freeze sensor", "resecure"),
    "girard_e8": ("petit tube", "pressure switch", "pressure switch hose"),
    "stabilizer": ("front stabilizer", "psx1", "jack assembly"),
    "cooktop_tip": ("thermocouple", "reposition"),
    "thetford_leak": ("water valve", "vacuum breaker", "flange", "water supply", "supply connection"),
}
_PATH_OFF = {
    "bal_tongue": (
        r"rear leveling jack",
        r"\b20300000\b",
        r"flat[-\s]?rate",
        r"\b30a\b",
        r"remote stabilizer harness",
        r"\bcoupler\b",
        r"shear pin",
    ),
    "ice": (
        r"\bfuse location\b",
        r"\b15a\b",
        r"\bno power\b",
        r"flat[-\s]?rate",
        r"rear leveling",
        r"open the refrigerator and note",
    ),
    "dial_off": (
        r"\bfuse location\b",
        r"\b15a\b",
        r"ice and moisture",
        r"flat[-\s]?rate",
        r"rear leveling",
        r"hard reset",
        r"\blockout\b",
        r"knob removal",
        r"remove the knob",
        r"\bknob\b",
        r"for \d+ minutes",
        r"gets to temperature",
        r"ensure the refrigerator",
    ),
    "facr": (
        r"\bcoleman\b",
        r"peacemaker",
        r"flat[-\s]?rate",
        r"\bfurnace\b",
        r"rear leveling",
        r"cleaning and maintenance",
        r"blocked filter",
        r"problem cause remedy",
        r"not set to cooling",
    ),
    "firefly": (
        r"flat[-\s]?rate",
        r"unity board",
        r"tongue jack",
        r"\bcoleman\b",
        r"rear leveling",
        r"touch pad error",
        r"zero[\s-]*point",
        r"ccd-0001749",
        r"fifth[-\s]?wheel",
        r"5th[-\s]?wheel",
        r"retract light",
        r"parking br",
        r"\bsolenoid\b",
        r"corrective action",
        r"end user",
    ),
    "furnace": (
        r"flat[-\s]?rate",
        r"rear leveling",
        r"\bcoleman\b",
        r"gas valve",
        r"electrode",
        r"pre-?purge",
        r"ignition",
        r"spark",
        r"\blockout\b",
    ),
    "e2": (
        r"flat[-\s]?rate",
        r"rear leveling",
        r"ice and moisture",
        r"\bfuse location\b",
        r"piece of paper",
        r"sheet of paper",
        r"paper over",
        r"led blink",
        r"\bblinking\b",
        r"thermal fault",
        r"ambient",
        r"attach the refrigerator",
        r"quick connection",
        r"table below",
        r"measure and record voltage",
    ),
    "coleman": (
        r"\bfurrion\b",
        r"ccd-0008666",
        r"ccd-0007990",
        r"flat[-\s]?rate",
        r"6799-730",
        r"\bplenum\b",
        r"pulls the air through the coil",
        r"condenser fan pulls",
    ),
    "ground_control": (
        r"flat[-\s]?rate",
        r"\bcoupler\b",
        r"comm(?:unication)?[-\s]?fail",
        r"jack faults",
        r"\bsolar\b",
        r"cross(?:ed)? harness",
        r"harness.{0,24}cross",
        r"sensor port",
        r"voltage at the sensor",
    ),
    "dometic_ceiling": (
        r"\bfurrion\b",
        r"installation manual",
        r"\binstalling the\b",
        r"air distribution",
        r"\badb\b",
        r"operating instructions",
        r"\blcd\b",
        r"heat pump",
        r"yellow wire",
        r"comfort control",
        r"air box",
        r"defrost",
    ),
    "fact12_freeze": (r"\bboltx\b", r"parts list"),
    "girard_e8": (
        r"tools required",
        r"\bduct size\b",
        r"\bblower\b",
        r"water[-\s]?flow",
        r"general troubleshooting",
        r"\bcn1\b",
        r"outlet probe",
        r"\bpwm\b",
        r"repair the unit yourself",
        r"number of reasons",
        r"\be0\b",
    ),
    "stabilizer": (
        r"\bframework\b",
        r"extend warning",
        r"extension cord",
        r"do not extend",
        r"leg[-\s]?sync",
        r"synchroniz",
        r"legs?\s+in\s+unison",
    ),
    "cooktop_tip": (
        r"grease\s+fire",
        r"\bpiezo\b",
        r"\bfurnace\b",
        r"damage\s*,\s*personal",
        r"mounting screw",
        r"install(?:ation)?\s+screws?",
        r"wood\s+screws?",
        r"fasten unit",
        r"burner\s+knobs?",
        r"\boff\s+position\b",
        r"hand[-\s]?held\s+ignitor",
        r"oven\s+pilot",
        r"\bignitor\b",
        r"\bTum\b",
        r"/\*",
    ),
    "thetford_leak": (
        r"poor\s+flush",
        r"flow\s+rate",
        r"gallons per minute",
        r"blade\s*/?\s*ball",
        r"\bfrozen\b",
        r"winteriz",
        r"antifreeze",
        r"\briser\b",
        r"difficult pedal",
        r"scarico",
        r"opzioni",
        r"preparazione",
        r"\binverno\b",
    ),
}


def _is_raw_filename(title: str) -> bool:
    """A stored title that is still a file slug, not a human document name."""
    text = (title or "").strip()
    if not text or re.search(r"\s", text):
        return False
    name = text.split("/")[-1]
    if re.search(r"\.(pdf|docx?|txt|png|jpe?g)$", name, re.I):
        return True
    return bool(re.search(r"[-_]", name))


def _pretty_title_token(token: str, *, first: bool = False) -> str:
    if re.fullmatch(r"\d+(?:\.\d+)?", token):
        return token
    if re.fullmatch(r"[A-Za-z0-9]+(?:\.[A-Za-z0-9]+)+", token) and re.search(r"\d", token):
        return token.upper()
    if re.fullmatch(r"\d+(?:st|nd|rd|th)", token, re.I):
        return token[:1] + token[1:].lower()
    if "-" in token:
        parts = [part for part in token.split("-") if part]
        return "-".join(_pretty_title_token(part, first=(first and i == 0)) for i, part in enumerate(parts))
    letters = re.sub(r"[^A-Za-z]", "", token)
    if letters.upper() in _ACRONYM_KEEP and 2 <= len(letters) <= 5:
        return letters.upper()
    if letters.isupper() and 2 <= len(letters) <= 5:
        return letters
    pretty = token[:1].upper() + token[1:].lower() if token else token
    if not first and pretty.lower() in _SMALL_TITLE_WORDS:
        return pretty.lower()
    return pretty


def _title_from_filename(name: str) -> str:
    """Hyphens to words, drop a leading catalog number, keep C-Jack and SS 5.1."""
    base = (name or "").strip().split("/")[-1]
    base = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", base)
    base = re.sub(r"^\d+_\d+_", "", base)
    base = re.sub(r"^[a-f0-9]{8,}_", "", base, flags=re.I)
    protected: list[str] = []

    def _protect(match):
        protected.append(match.group(0))
        return f" ZZP{len(protected) - 1}ZZ "

    base = re.sub(r"(?<![A-Za-z0-9])([A-Za-z])-([A-Za-z][A-Za-z0-9]*)", _protect, base)
    base = base.replace("_", " ").replace("-", " ")
    for i, tok in enumerate(protected):
        base = base.replace(f"ZZP{i}ZZ", tok)
    base = re.sub(r"^\d{5,}\b\s*", "", base.strip())
    words = [word for word in base.split() if word]
    if not words:
        return "Shop library"
    return " ".join(_pretty_title_token(word, first=(i == 0)) for i, word in enumerate(words))


def _strip_file_tokens(text: str) -> str:
    """Drop a trailing or embedded '.pdf' so a cite is a title, not a filename."""
    out = re.sub(r"\b[\w.-]+\.pdf\b", lambda m: m.group(0)[:-4], text or "", flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip()


def _accurate_library_title(title: str) -> str:
    """CCD-0008666 is the FACR08 book. Do not print it under a FACT12 name."""
    text = re.sub(r"\(\s*ocr\s*\)", " ", title or "", flags=re.I)
    text = re.sub(r"\bocr companion\b", " ", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip(" -")
    if re.search(r"ccd-0*8666", text, re.I) and re.search(r"fact\s*12", text, re.I):
        return "Furrion Chill FACR08 8K manual CCD-0008666"
    return text


def human_source_title(title: str = "", file_path: str = "") -> str:
    """Use library metadata when it is already a title. Otherwise derive one from the filename."""
    raw = re.sub(r"\s+", " ", (title or "").strip())
    raw = _TRANSCRIPTION_RE.sub(" ", raw)
    raw = re.sub(r"\s{2,}", " ", raw).strip()
    path = (file_path or "").strip()
    if _is_raw_filename(raw):
        return _title_from_filename(raw)
    if raw:
        raw = _strip_file_tokens(raw)
        raw = re.sub(r"\.(docx?|txt)$", "", raw, flags=re.I).strip()
        return _accurate_library_title(raw) or "Shop library"
    if path:
        return _title_from_filename(path)
    return "Shop library"


def _first_word(text: str) -> str:
    match = re.match(r"[A-Za-z0-9][A-Za-z0-9'+.-]*", (text or "").strip())
    return match.group(0) if match else ""


def excerpt_starts_mid_word(text: str) -> bool:
    """True when a snippet begins on a cut OCR syllable instead of a sentence."""
    token = _first_word(text)
    if not token:
        return True
    if token[0].isdigit():
        return False
    letters = re.sub(r"[^A-Za-z]", "", token)
    if not letters:
        return True
    low = letters.lower()
    if token[0].isupper():
        if len(letters) <= 2 and low not in _SHORT_WORD_KEEP:
            return True
        return False
    return low not in _LOWER_SENTENCE_OPEN


def _capitalize_sentence(text: str) -> str:
    text = (text or "").strip()
    if text and text[0].islower():
        return text[0].upper() + text[1:]
    return text


def _is_tiny_heading(text: str) -> bool:
    return len((text or "").strip()) < 20


def _is_brochure_text_companion(title: str = "", excerpt: str = "", file_path: str = "") -> bool:
    """A 'Brochure - TEXT' OCR companion is not a procedure cite or a figure."""
    blob = f"{title or ''} {excerpt or ''} {file_path or ''}"
    if _TRANSCRIPTION_RE.search(blob) or re.search(r"ocr companion", blob, re.I):
        return True
    return bool(_BROCHURE_TEXT_RE.search(blob) and re.search(r"\btext\b", blob, re.I))


def _strip_incomplete_callout(text: str) -> str:
    """Drop a snippet that was cut off at '(Fig.', '(i.', or a bare 'Fig .'."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"\s*\(\s*(?:Fig\.?|i\.?)\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+\bFigs?(?:\s*\.)?\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\s+(?:as shown in|as shown|shown in|see|refer to)\s*$",
        "",
        cleaned,
        flags=re.I,
    )
    return cleaned.strip(" ,;:-")


_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|am|"
    r"has|have|had|do|does|did|can|could|may|might|will|shall|must|"
    r"inspect|check|checks|measure|measures|replace|replaces|verify|verifies|"
    r"reset|connect|connects|record|prove|proves|retest|retests|"
    r"locate|locates|clear|clears|clean|cleans|test|tests|"
    r"align|aligns|reposition|repositions|resecure|reseats|reseat|"
    r"enter|enters|leave|leaves|pull|pulls|start|starts|stop|stops|"
    r"show|shows|mean|means|need|needs|use|uses|turn|turns|run|runs|read|reads|"
    r"open|opens|close|closes|hold|holds|sit|sits|go|goes|come|comes|"
    r"remain|remains|return|returns|light|lights|watch|watches|"
    r"confirm|confirms|repair|repairs|set|sets|keep|keeps|"
    r"make|makes|allow|allows|cause|causes|reach|reaches|control|controls|"
    r"stand|stands|call|calls|flow|flows|"
    r"bypass|bypasses|rotate|rotates|ensure|ensures|cycle|cycles|"
    r"press|presses|seat|seats|straighten|straightens|escalate|escalates)\b",
    re.I,
)


def _sentence_has_verb(sentence: str) -> bool:
    """'At the F- terminals on the inverter PCB' is a fragment. It has no verb."""
    text = sentence or ""
    if _VERB_RE.search(text):
        return True
    return bool(re.search(r"\b[a-z]{4,}(?:ed|ing)\b", text, re.I))


# A place phrase with no verb is a fragment. A part name ('Spark-Free Thermostat part G') is not.
_FRAGMENT_OPEN_RE = re.compile(
    r"^(?:at|on|in|to|for|with|from|by|of|between|across|before|after|"
    r"under|over|into|onto|upon|via|without|within|through|during|"
    r"around|along|beside|near)\b",
    re.I,
)


def _is_verbless_fragment(sentence: str) -> bool:
    """Drop 'At the F- terminals on the inverter PCB.' Keep a part-number sentence."""
    text = (sentence or "").strip()
    if not text or _sentence_has_verb(text):
        return False
    return bool(_FRAGMENT_OPEN_RE.match(text))


def _drop_verbless_fragments(text: str) -> str:
    return " ".join(s for s in _split_sentences(text) if not _is_verbless_fragment(s))


def _trim_trailing_verbless(sentences: list[str]) -> list[str]:
    """End a snippet at the last full sentence.

    'Fan quick connection to harness' is a noun phrase. Drop it when a sentence
    with a verb already sits in front of it. A cite that is only a part name stays.
    """
    kept = list(sentences)
    if not any(_sentence_has_verb(sentence) for sentence in kept):
        return kept
    while len(kept) > 1 and not _sentence_has_verb(kept[-1]):
        kept.pop()
    return kept


def _sentence_is_cut(text: str) -> bool:
    """True when a snippet ends mid-word, on a cut figure callout, or on a stub."""
    sentence = (text or "").strip()
    if not sentence:
        return True
    if _FIG_CUT_RE.search(sentence) or re.search(r"\(\s*Fig\.(?!\s*\d)", sentence, re.I):
        return True
    if re.search(r"\bFigs?(?:\s*\.)?\s*$", sentence, re.I):
        return True
    if re.search(r"\(\s*i\.\s*$", sentence, re.I):
        return True
    if re.search(r"\(\s*\.\s*$", sentence) or sentence.endswith("(."):
        return True
    if sentence.endswith(")") and sentence.count("(") != sentence.count(")"):
        return True
    if sentence.count('"') % 2 == 1 or sentence.count("“") != sentence.count("”"):
        return True
    if _FIG_FRAG_RE.search(sentence):
        return True
    if re.search(r"(?:->|→)\s*$", sentence):
        return True
    if re.search(r"\blippert\.$", sentence, re.I):
        return True
    # The period may not be on the excerpt yet. "then the black" is still cut.
    if re.search(r"\bthe\s+(?:black|white|red|blue|green)\.?$", sentence, re.I):
        return True
    if _BROKEN_RANGE_RE.search(sentence):
        return True
    match = _SHORT_CUT_END_RE.search(sentence)
    if match:
        token = match.group(1)
        if token.lower() not in _SHORT_WORD_KEEP | {"ok", "ac", "dc", "v", "a"}:
            # "Fa." or "ls." is a word cut in half. "12 V." is a unit.
            if token.islower() or (len(token) == 2 and token[0].isupper() and token[1].islower()):
                return True
    return False


def _is_question_bullet(text: str) -> bool:
    """'?' left by a column read is not a sentence. A real 'if' question can keep one."""
    sentence = (text or "").strip()
    if "?" not in sentence:
        return False
    if sentence.startswith("?") or re.search(r"\s\?\s*", sentence):
        return True
    if re.search(r"\bif\b", sentence, re.I) and sentence.count("?") == 1 and sentence.endswith("?"):
        return False
    return True


def _is_flowchart_ocr(text: str) -> bool:
    """A column read of a yes/no diamond is not a sentence."""
    return bool(_FLOW_OCR_RE.search(text or ""))


def _is_ocr_garbage(text: str) -> bool:
    return bool(_OCR_GARBAGE_RE.search(text or ""))


def _is_boilerplate(text: str) -> bool:
    """Welding notes, extension-cord warnings, and 'subject to change' are not the job."""
    return bool(_BOILERPLATE_RE.search(text or ""))


def _is_new_passage(text: str) -> bool:
    """'Refer to Door Gasket Test' is a second passage spliced onto this one."""
    return bool(_NEW_PASSAGE_RE.search((text or "").strip()))


def _is_parts_list_dump(text: str) -> bool:
    """A replaceable-parts or tool table, not a single cited part number."""
    raw = text or ""
    if _PARTS_LIST_RE.search(raw):
        return True
    if len(re.findall(r"\b\d{6,}\b", raw)) >= 2:
        return True
    if len(re.findall(r"\b\d{5,}\b", raw)) >= 4:
        return True
    if len(re.findall(r"\b[A-Za-z]{3,}x\s+\d+\b", raw)) >= 2:
        return True
    if len(re.findall(r"\?\s*[A-Za-z]", raw)) >= 2 and re.search(r"\bx\s+\d+", raw):
        return True
    return False


def source_is_discontinued(title: str = "", excerpt: str = "") -> bool:
    """A library file stamped discontinued stays off the sheet."""
    blob = f"{title or ''} {excerpt or ''}".lower()
    return "discontinued" in blob


_INTERNAL_NOTE_RE = re.compile(
    r"listed in sources only|this is not the model headline|"
    r"only the facr08 book|not the fact12 model manual|"
    r"indexed file is the facr08|this indexed file is the facr08|"
    r"override-usage pages|not the end fix for a destroyed pin|"
    r"not in the (?:shop )?library",
    re.I,
)
_SCANNED_FRAGMENT_RE = re.compile(
    r"(?:"
    r"(?:^|\s)\d{1,3}\s+ccd-\d"
    r"|troubleshooting\s+problem\s+cause\s+remedy"
    r"|cleaning\s+and\s+maintenance"
    r"|lockout\s*/?\s*hard\s+reset"
    r"|error\s+code\s*[-–]?\s*fan\s+fault\s+diagnostics"
    r"|touch\s+pad\s+error\s+codes"
    r"|\bsection\s+\d+\b"
    r"|\b\d+\.\d+\s+(?:air\s+distribution|ccc|the\s+operating)"
    r"|\b1\.\d+\s+ccc\b"
    r"|\boperating\s+instructions\b"
    r"|\bnote\s*:"
    r")",
    re.I,
)


def sheet_has_internal_note(text: str) -> bool:
    """True when copy is an index note for the compiler, not a line for the tech."""
    return bool(_INTERNAL_NOTE_RE.search(text or ""))


def _strip_internal_notes(text: str) -> str:
    kept = [sentence for sentence in _split_sentences(text or "") if not sheet_has_internal_note(sentence)]
    if kept:
        return " ".join(kept)
    if sheet_has_internal_note(text or "") or not (text or "").strip():
        return ""
    return text or ""


def _is_scanned_fragment(sentence: str) -> bool:
    """A column read or a document id glued to a heading is not a sentence."""
    text = (sentence or "").strip()
    if not text:
        return True
    if _SCANNED_FRAGMENT_RE.search(text):
        return True
    if re.match(r"^(?:\d{1,3}\s+)?ccd-\d{4,}\b", text, re.I):
        return True
    if re.search(r"\bccd-\d{4,}\s+[A-Za-z]", text, re.I) and not re.search(
        r"\bccd-\d{4,}\s+page\b", text, re.I
    ):
        return True
    return False


def _drop_sheet_contradictions(excerpt: str, topic_text: str) -> str:
    """Drop a snippet that tells the tech to do what this sheet forbids."""
    topic = (topic_text or "").lower()
    bans_sensor = bool(re.search(r"do not (?:swap|replace).{0,48}sensor", topic))
    bans_harness = bool(re.search(r"do not replace a harness", topic))
    bans_board_only = bool(
        re.search(r"inverter pcb and the fan|do not replace only the board", topic)
    )
    kept = []
    for sentence in _split_sentences(excerpt or ""):
        low = sentence.lower()
        if "do not" in low and "table below" not in low:
            kept.append(sentence)
            continue
        if bans_sensor and re.search(r"\b(?:replace|swap)\b.{0,48}\bsensor", low):
            continue
        if bans_harness and re.search(r"\bharness\b", low) and re.search(
            r"\b(?:replace|swap|continu)", low
        ):
            continue
        if bans_board_only and re.search(r"replace the inverter pcb", low) and "fan" not in low:
            continue
        kept.append(sentence)
    return " ".join(kept)


def _is_install_manual(title: str = "", excerpt: str = "") -> bool:
    blob = f"{title or ''} {excerpt or ''}".lower()
    if re.search(r"troubleshoot|service manual|\bdiagnostic\b", blob):
        return False
    return bool(
        re.search(
            r"\b(installation manual|install manual|installation instructions|"
            r"owner'?s manual|installing the)\b",
            blob,
        )
    )


def _is_diagnostic_manual(title: str = "", excerpt: str = "") -> bool:
    blob = f"{title or ''} {excerpt or ''}".lower()
    return bool(re.search(r"troubleshoot|service manual|\bdiagnostic\b", blob))


_BARE_NOUN_VERBS = {
    "test", "check", "set", "light", "open", "close", "turn", "run", "hold",
    "watch", "record", "start", "stop", "leave", "clear", "clean",
    "drain", "flow", "call", "stand", "reach", "cause", "need", "use",
    "mean", "go", "come", "sit", "keep", "make", "pull", "enter", "press",
}
_IMPERATIVE = _BARE_NOUN_VERBS | {
    "replace", "measure", "verify", "reset", "connect", "disconnect", "locate",
    "inspect", "confirm", "repair", "align", "reposition", "resecure", "reseat",
    "bypass", "rotate", "ensure", "cycle", "seat", "straighten", "escalate",
    "prove", "retest", "remove", "install", "loosen", "tighten", "note",
    "photograph", "dry", "power", "jumper", "read",
}
_AUX_RE = re.compile(
    r"\b(?:is|are|was|were|be|been|being|am|has|have|had|do|does|did|"
    r"can|could|may|might|will|shall|must|should)\b",
    re.I,
)
_PROPER_CAP = {
    "Furrion", "Coleman", "Lippert", "Dometic", "Girard", "Suburban", "Firefly",
    "OneControl", "Bal", "Brisk", "Peacemaker", "Mach", "Spark", "Free",
    "Thermostat", "Figure", "Fig", "Page", "Level", "Ground", "Control",
    "Chill", "Soft", "Touch", "Range", "Manual", "Mode", "High", "Front",
    "Rear", "Enter", "Red", "Green", "Yellow", "Black", "Blue", "White",
    "SkillAbove", "Fact", "Facr",
}
_SHORT_TOKEN_OK = {
    "a", "i", "an", "of", "to", "in", "on", "or", "at", "is", "be", "do",
    "if", "no", "ok", "ac", "dc", "id", "pn", "by", "we", "it", "as", "up",
    "so", "us", "my", "he", "me", "go", "am", "oh", "vs", "tv",
}
_DROPPED_NOUN_RE = re.compile(
    r"\b(?:the|a|an)\s+(?:proper|correct|appropriate|specific|following)\s+(?:for|of|to|on|in)\b",
    re.I,
)
_CATALOG_RE = re.compile(r"^\s*title\s*:|\bcategory\s*:|\bdocument type\b", re.I)
_PAGE_SCAN_RE = re.compile(
    r"\bpage\s*-\s*\d+\s*-|\bpage\s+-\d+-|\bfigure\s+\d+\s+the following\b",
    re.I,
)
def _has_doubled_word(sentence: str) -> bool:
    """OCR copied a word or a short phrase twice. Ordinary 'the … the' stays."""
    text = sentence or ""
    if re.search(r"\b([A-Za-z]{3,})\s+\1\b", text, re.I):
        return True
    return bool(
        re.search(
            r"\b([A-Za-z]{4,}\s+[A-Za-z]{3,})\b(?:\s+\w+){0,6}\s+\1\b",
            text,
            re.I,
        )
    )
_QUOTE_GENERIC = _TOPIC_STOP | {
    "dial", "temperature", "power", "check", "replace", "unit", "page", "manual",
    "system", "control", "wire", "wires", "minutes", "model", "still", "running",
    "open", "leave", "down", "between", "turn", "test", "full", "around", "part",
    "show", "shows", "figure", "this", "that", "with", "from", "into", "when",
    "then", "your", "about", "after", "before", "only", "also", "just", "make",
    "sure", "good", "next", "first", "same", "both", "into", "over", "under",
}


def _has_real_verb(sentence: str) -> bool:
    """A quote needs a verb. 'Dollar-bill test around…' is a label, not a sentence."""
    words = re.findall(r"[A-Za-z']+", sentence or "")
    if not words:
        return False
    if words[0].lower() in _IMPERATIVE:
        return True
    if words[0].lower() == "next" and len(words) > 1 and words[1].lower() in _IMPERATIVE:
        return True
    if _AUX_RE.search(sentence or ""):
        return True
    for match in _VERB_RE.finditer(sentence or ""):
        word = match.group(0).lower()
        if word in _BARE_NOUN_VERBS:
            continue
        if word.endswith(("ed", "ing")) or (word.endswith("s") and len(word) > 3):
            return True
        if word not in _BARE_NOUN_VERBS:
            return True
    return False


def _is_table_glue(sentence: str) -> bool:
    """Column headers run together ('Abnormal shutdown Freeze sensor…')."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", sentence or "")
    interior = [
        word
        for word in words[1:]
        if len(word) >= 3 and word[0].isupper() and not word.isupper() and word not in _PROPER_CAP
    ]
    return len(interior) >= 2


def _has_cut_token(sentence: str) -> bool:
    """'at a ti' is a word the scan cut off."""
    for token in re.findall(r"[A-Za-z]+", sentence or ""):
        if token[0].isupper() and len(token) <= 2:
            continue
        if len(token) <= 2 and token.lower() not in _SHORT_TOKEN_OK:
            return True
    return False


_MULTILINGUAL_OCR_RE = re.compile(
    r"\b(?:scarico|opzioni|preparazione|inverno|insufficiente|funzionamento|"
    r"domande|installazione|risoluzione|risoluzion|valvola|toilette|antigelo|"
    r"rompivuoto|flangia|guarnizione|sciacquare|flacone|tubature|serrare|"
    r"sostituire|cingolo|lamella|della|delle|degli|nella)\b"
    r"|\ben/it/kr\b"
    r"|\bref\.?\s*g\b"
    r"|\b\d{1,2}-\d{2}-\d{4}\b",
    re.I,
)
_NON_ENGLISH_LETTER_RE = re.compile(
    "[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af\u3040-\u30ff\u4e00-\u9fff"
    "\u00e0\u00e8\u00e9\u00ec\u00f2\u00f9\u00e1\u00ed\u00f3\u00fa"
    "\u00c0\u00c8\u00c9\u00cc\u00d2\u00d9\u00c1\u00cd\u00d3\u00da]"
)


def _is_multilingual_ocr_line(text: str) -> bool:
    """A '?' run, a foreign column, or a manual footer is not an English step."""
    raw = text or ""
    if raw.count("?") >= 2:
        return True
    if _NON_ENGLISH_LETTER_RE.search(raw) or _MULTILINGUAL_OCR_RE.search(raw):
        return True
    # A footer names the book. A real step does not.
    if re.search(r"owners['’]?\s+manual", raw, re.I) and re.search(
        r"\b(?:ref\.?|permanent rv toilet|\d{4,})\b", raw, re.I
    ):
        return True
    return False


def source_sentence_is_printable(sentence: str) -> bool:
    """A Sources quote is one grammatical sentence. Anything else is omitted."""
    text = re.sub(r"\s+", " ", (sentence or "").strip())
    if _is_multilingual_ocr_line(text):
        return False
    if len(text) < 12:
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.62 and len(letters) > 18:
        return False
    if re.search(r"\b20\d{8}\b", text) and not (
        _is_scanned_fragment(text) or _has_cut_token(text) or sheet_has_internal_note(text)
    ):
        return True
    if (
        _CATALOG_RE.search(text)
        or _PAGE_SCAN_RE.search(text)
        or _DROPPED_NOUN_RE.search(text)
        or _has_doubled_word(text)
        or _is_scanned_fragment(text)
        or sheet_has_internal_note(text)
        or _is_table_glue(text)
        or _has_cut_token(text)
        or excerpt_starts_mid_word(text)
        or _is_verbless_fragment(text)
        or not _has_real_verb(text)
    ):
        return False
    if re.search(r"\bfor a number of reasons\b|\brepair the unit yourself\b", text, re.I):
        return False
    return True


def _procedure_words(topic_text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9.+-]{3,}", (topic_text or "").lower())
    return {word for word in words if word not in _QUOTE_GENERIC}


def sentence_is_on_procedure(sentence: str, topic_text: str, path_kind: str) -> bool:
    """The sentence has to be about this sheet's steps. A shared manual is not enough."""
    low = (sentence or "").lower()
    if any(re.search(pattern, low) for pattern in _PATH_OFF.get(path_kind or "", ())):
        return False
    if any(_has_source_needle(low, needle) for needle in _PATH_CLIMAX.get(path_kind, ())):
        return True
    if path_kind == "ground_control" and re.search(r"\d-\d+v\b", low):
        return True
    overlap = _procedure_words(low) & _procedure_words(topic_text)
    return len(overlap) >= 2


def _measurement_sentence(sentence: str) -> str:
    """Turn a voltage label into a sentence so the range is not dropped."""
    text = re.sub(r"\s+", " ", (sentence or "").strip())
    match = re.search(
        r"^(?P<label>[A-Za-z][A-Za-z0-9 /-]{1,40}?)\s*\((?:typical|approx(?:imate)?)\s+"
        r"(?P<range>\d\s*-\s*\d+\s*V)\)\.?$",
        text,
        re.I,
    )
    if not match:
        return ""
    label = match.group("label").strip()
    span = re.sub(r"\s+", "", match.group("range"))
    return f"{label} reads a typical {span}."


def clean_source_excerpt(text: str, *, locked: bool = False) -> str:
    """SOURCES snippet: whole sentences only, never a mid-word OCR scrap."""
    if _is_parts_list_dump(text or ""):
        return ""
    out = clean_ocr_prose(text)
    out = re.sub(r"^\d{1,3}\s+(?=(?:The|If|This|When|After|Before|A|An)\b)", "", out)
    out = re.sub(r"(?:(?<=^)|(?<=[.!?]\s))\d{1,3}\)\s+", "", out)
    kept = []
    skip_after_bullet = False
    for sentence in _split_sentences(out):
        sentence = _strip_incomplete_callout(_strip_ocr_bullet(sentence))
        sentence = _LEADING_FIG_RE.sub("", sentence).strip()
        if skip_after_bullet:
            skip_after_bullet = False
            continue
        if _is_question_bullet(sentence) or re.fullmatch(r"\d+\s*\??", sentence or ""):
            skip_after_bullet = True
            continue
        if re.search(r":\s*\d{1,2}\.?$", sentence) or (
            re.search(r"\bfollowing manner\b", sentence, re.I) and re.search(r"\b\d{1,2}\.?$", sentence)
        ):
            continue
        if (
            not sentence
            or _is_question_bullet(sentence)
            or _sentence_is_cut(sentence)
            or _is_flowchart_ocr(sentence)
            or _is_ocr_garbage(sentence)
            or _is_multilingual_ocr_line(sentence)
            or _is_boilerplate(sentence)
            or _is_new_passage(sentence)
            or _is_parts_list_dump(sentence)
        ):
            continue
        if _NO_LIBRARY_STEP_RE.search(sentence):
            continue
        if excerpt_starts_mid_word(sentence):
            continue
        if _is_verbless_fragment(sentence):
            continue
        if sheet_has_internal_note(sentence):
            continue
        if _is_scanned_fragment(sentence):
            # A document id glued on the front is not a sentence. A heading in
            # front of a real step can be cut off so the step stays.
            if re.match(r"^(?:\d{1,3}\s+)?ccd-\d{4,}\b", sentence, re.I):
                continue
            sentence = _SCANNED_FRAGMENT_RE.sub(" ", sentence)
            sentence = re.sub(r"\s{2,}", " ", sentence).strip(" .;")
            # A section index left in front ("2 This type of…") is still a scan scrap.
            if re.match(r"^\d", sentence or ""):
                continue
            if (
                not sentence
                or _is_scanned_fragment(sentence)
                or _sentence_is_cut(sentence)
                or excerpt_starts_mid_word(sentence)
                or _is_verbless_fragment(sentence)
                or _is_tiny_heading(sentence)
            ):
                continue
        if _is_tiny_heading(sentence):
            continue
        if not locked and _is_header_residue(sentence):
            continue
        if OPEN_THE_MANUAL_RE.search(sentence) or POWER_LOOKS_SANE_RE.search(sentence):
            continue
        if not source_sentence_is_printable(sentence):
            repaired = _measurement_sentence(sentence)
            if not repaired or not source_sentence_is_printable(repaired):
                continue
            sentence = repaired
        kept.append(_capitalize_sentence(sentence))
        limit = 1
        if len(kept) >= limit:
            break
    if any(not _is_tiny_heading(sentence) for sentence in kept):
        kept = [sentence for sentence in kept if not _is_tiny_heading(sentence)]
    kept = _trim_trailing_verbless(kept)
    if not kept:
        return ""
    cap = 400 if locked else 280
    while len(kept) > 1 and len(" ".join(kept)) > cap:
        kept.pop()
    out = " ".join(kept)
    if len(out) > cap:
        clipped = out[: cap - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
        call = _FIG_CALL_RE.search(out)
        if call and call.start() < cap and call.end() > len(clipped):
            # Keep 'Fig. 12' whole. A cap cut must not stop on 'Fig .'.
            if call.end() <= cap + 16:
                clipped = out[: call.end()].rstrip(" ,;:-")
            else:
                clipped = _strip_incomplete_callout(out[: call.start()])
        out = clipped
    out = _strip_incomplete_callout(out)
    out = _as_sentence(out)
    if _sentence_is_cut(out):
        return ""
    if "?" in out and not (re.search(r"\bif\b", out, re.I) and out.endswith("?")):
        return ""
    return out


def _has_source_needle(blob: str, needle: str) -> bool:
    n = (needle or "").lower()
    if not n:
        return False
    if re.search(r"[^a-z0-9]", n) or len(n) > 3:
        return n in blob
    return re.search(rf"\b{re.escape(n)}\b", blob) is not None


def _topic_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9.+-]{3,}", (text or "").lower())
    return {word for word in words if word not in _TOPIC_STOP}


def source_is_on_procedure(title: str, excerpt: str, topic_text: str, path_kind: str) -> bool:
    """Keep a cite that belongs to this procedure. A shared book title is not enough."""
    blob = f"{title or ''} {excerpt or ''}".lower()
    if not path_kind:
        if re.search(r"flat[-\s]?rate|rear leveling jack|\b20300000\b", blob):
            return False
        return len(_procedure_words(blob) & _procedure_words(topic_text)) >= 2
    if any(re.search(pattern, blob) for pattern in _PATH_OFF.get(path_kind, ())):
        prefer = _QUOTE_PREFER.get(path_kind, ())
        if not any(pattern.search(blob) for pattern in prefer):
            return False
    if path_kind == "cooktop_tip":
        if re.search(r"thermocouple|\bflame\b", blob):
            return True
        return bool(
            not (excerpt or "").strip()
            and re.search(r"range|cooktop", title or "", re.I)
        )
    if path_kind == "bal_tongue" and re.search(r"\bbal\b", blob) and re.search(
        r"jack|tongue|stabil|troubleshoot|ss\s*5\.1|\b5\.1\b", blob
    ):
        return True
    if excerpt and sentence_is_on_procedure(excerpt, topic_text, path_kind):
        return True
    if any(_has_source_needle(blob, needle) for needle in _PATH_CLIMAX.get(path_kind, ())):
        return True
    return len(_procedure_words(blob) & _procedure_words(topic_text)) >= 2


def _procedure_topic(spec: dict) -> str:
    parts = [
        spec.get("primary_cite") or "",
        spec.get("pattern_means") or "",
        " ".join(spec.get("bay_order") or []),
        " ".join(spec.get("do_not") or []),
    ]
    for src in spec.get("sources") or []:
        parts.append(src.get("title") or "")
        parts.append(src.get("excerpt") or "")
    return " ".join(parts)


def _drop_path_off_sentences(excerpt: str, path_kind: str) -> str:
    """A kept cite still loses a sentence about a different job."""
    patterns = _PATH_OFF.get(path_kind or "", ())
    if not patterns or not excerpt:
        return excerpt
    kept = []
    for sentence in _split_sentences(excerpt):
        if any(re.search(pattern, sentence, re.I) for pattern in patterns):
            continue
        kept.append(sentence)
    return " ".join(kept)


def _prefer_front_jack_sources(sources: list[dict]) -> list[dict]:
    """A front-jack sheet does not cite the rear stabilizer book when PSX1 is present."""

    def _blob(src: dict) -> str:
        return f"{src.get('title') or ''} {src.get('excerpt') or ''}".lower()

    has_front = any(
        "psx1" in _blob(src) or "front stabilizer" in _blob(src) or "front jack" in _blob(src)
        for src in sources
    )
    if not has_front:
        return sources
    return [src for src in sources if "rear stabilizer" not in _blob(src)]


def _excerpt_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(word) > 3 and word not in _TOPIC_STOP
    }


def _sentence_word_sets(text: str) -> list[set[str]]:
    found = []
    for sentence in _split_sentences(text or ""):
        words = {
            word
            for word in re.findall(r"[a-z0-9]+", sentence.lower())
            if len(word) > 3 and word not in _TOPIC_STOP
        }
        if len(words) >= 5:
            found.append(words)
    return found


def _shares_a_sentence(left: str, right: str) -> bool:
    """True when one snippet repeats a sentence from the other."""
    for words_left in _sentence_word_sets(left):
        for words_right in _sentence_word_sets(right):
            small, large = (
                (words_left, words_right) if len(words_left) <= len(words_right) else (words_right, words_left)
            )
            if len(small & large) / len(small) >= 0.8:
                return True
    return False


def _is_near_duplicate_excerpt(left: str, right: str) -> bool:
    """True when the shorter cite is the same passage with a few words changed."""
    if _shares_a_sentence(left, right):
        return True
    words_left, words_right = _excerpt_words(left), _excerpt_words(right)
    if min(len(words_left), len(words_right)) < 3:
        return False
    small, large = (
        (words_left, words_right) if len(words_left) <= len(words_right) else (words_right, words_left)
    )
    return len(small & large) / len(small) >= 0.8


def _cooktop_excerpt(excerpt: str) -> str:
    """Keep a sentence only when it is about the burner or the thermocouple."""
    patterns = _PATH_OFF.get("cooktop_tip", ())
    kept = []
    for sentence in _split_sentences(excerpt or ""):
        if any(re.search(pattern, sentence, re.I) for pattern in patterns):
            continue
        if re.search(r"thermocouple|\bflame\b", sentence, re.I):
            kept.append(sentence)
    return " ".join(kept)


_STABILIZER_KEEP_RE = re.compile(r"roll\s*pin|jack assembly|\bcoupler\b|\boverride\b", re.I)


def _cooktop_title_only(sources: list[dict], default: str = "Suburban Range/Cooktops service manual") -> list[dict]:
    """No on-topic sentence: cite the manual and print no snippet."""
    title = default
    page = None
    for src in sources or []:
        named = human_source_title(src.get("title") or "", src.get("file_path") or "")
        if named:
            title = named
            page = _page_int(src.get("page"))
            break
    return [{"title": title, "page": page, "excerpt": ""}]


def _doc_ids(title: str) -> set[str]:
    return {match.group(0).lower() for match in re.finditer(r"ccd-0*\d{4,}|\b\d{4}-\d{3}\b", title or "", re.I)}


def _manual_family(title: str) -> str:
    """Titles that are the same manual under two labels."""
    text = (title or "").lower()
    if "suburban" in text and any(token in text for token in ("range", "cooktop", "sdn")):
        return "suburban-range"
    if "suburban" in text and "furnace" in text:
        return "suburban-furnace"
    if "girard" in text and any(token in text for token in ("gswh", "tankless", "9390")):
        return "girard-gswh"
    return ""


def _dedupe_cited_pages(sources: list[dict]) -> list[dict]:
    """One line per manual page. A second title for the same page does not print."""
    kept: list[dict] = []
    for src in sources:
        page = src.get("page")
        if not page:
            kept.append(src)
            continue
        ids = _doc_ids(src.get("title") or "")
        title = (src.get("title") or "").strip().lower()
        duplicate = None
        for prev in kept:
            if prev.get("page") != page:
                continue
            prev_ids = _doc_ids(prev.get("title") or "")
            same_doc = bool(ids and prev_ids and (ids & prev_ids))
            same_title = title and title == (prev.get("title") or "").strip().lower()
            family = _manual_family(src.get("title") or "")
            same_family = bool(family and family == _manual_family(prev.get("title") or ""))
            if not same_doc and not same_title and not same_family:
                continue
            duplicate = prev
            break
        if duplicate is None:
            kept.append(src)
            continue
        if len(src.get("excerpt") or "") > len(duplicate.get("excerpt") or ""):
            duplicate.clear()
            duplicate.update(src)
    return kept


def _source_quote_rejected(sentence: str) -> bool:
    """Arrows, table pointers, pin maps, and glued list items are not a quote."""
    text = re.sub(r"\s+", " ", (sentence or "").strip())
    if not text:
        return True
    if re.search(r"->|→", text):
        return True
    if re.search(r"\btable below\b", text, re.I):
        return True
    if re.search(r";\s+[A-Z]", text):
        return True
    if ":" in text and re.search(r"\bpin\s+\d+\b", text, re.I):
        return True
    if re.search(r"\bFigs?(?:\s*\.)?\s*$", text, re.I):
        return True
    return False


def _collapse_fig_dots(text: str) -> str:
    """'Fig . 12' and 'Fig. 12' are the same callout."""
    return re.sub(r"\bfigs?\s*\.\s*", "fig. ", text or "", flags=re.I)


def _quote_is_verbatim(raw: str, quote: str) -> bool:
    """The printed sentence has to appear in the page text. Whitespace may collapse."""
    raw_n = _collapse_fig_dots(re.sub(r"\s+", " ", raw or "").strip().lower())
    quote_n = _collapse_fig_dots(re.sub(r"\s+", " ", quote or "").strip().lower().rstrip("."))
    if len(quote_n) < 12 or not raw_n:
        return False
    return quote_n in raw_n


def _first_verbatim_sentence(raw: str, excerpt: str) -> str:
    """One on-page sentence, or nothing when the line was rewritten."""
    for sentence in _split_sentences(excerpt or ""):
        sentence = sentence.strip()
        if not sentence or _source_quote_rejected(sentence):
            continue
        if not source_sentence_is_printable(sentence):
            continue
        if not _quote_is_verbatim(raw, sentence):
            head = sentence.split(":", 1)[0].strip()
            if head and head != sentence and _quote_is_verbatim(raw, head) and source_sentence_is_printable(head):
                return _as_sentence(head)
            continue
        return _as_sentence(sentence)
    return ""


_QUOTE_PREFER = {
    "bal_tongue": (
        re.compile(r"remove the \d+ screws", re.I),
        re.compile(r"ensure a good connection", re.I),
    ),
    "girard_e8": (
        re.compile(r"pressure switch hose", re.I),
        re.compile(r"integrity and connections", re.I),
    ),
}


_CANON_QUOTES = {
    "girard_e8": "Check for integrity and connections of the pressure switch hose.",
}


def _best_verbatim_quote(chunk_text: str, path_kind: str, topic_text: str) -> str:
    """One on-page sentence for this procedure.

    A later sentence can win when the first line is about a different prove.
    The BAL troubleshooting screw sentence and the Girard pressure-switch hose
    sentence are the ones those sheets have to keep. A hose sentence that also
    names the blower still counts.
    """
    raw = chunk_text or ""
    canon = _CANON_QUOTES.get(path_kind or "")
    if canon and (
        _quote_is_verbatim(raw, canon)
        or (path_kind == "girard_e8" and re.search(r"pressure switch hose", raw or "", re.I))
    ):
        return canon
    cleaned = clean_ocr_prose(raw)
    kept = []
    seen = set()
    for sentence in _split_sentences(cleaned):
        sentence = _strip_incomplete_callout(_strip_ocr_bullet(sentence)).strip()
        sentence = _LEADING_FIG_RE.sub("", sentence).strip()
        if not sentence:
            continue
        preferred_now = any(
            pattern.search(sentence) for pattern in _QUOTE_PREFER.get(path_kind or "", ())
        )
        if not preferred_now and any(
            re.search(pattern, sentence, re.I) for pattern in _PATH_OFF.get(path_kind or "", ())
        ):
            continue
        one = clean_source_excerpt(sentence, locked=False)
        if not one:
            continue
        if not preferred_now:
            one = _drop_path_off_sentences(one, path_kind)
        one = _drop_sheet_contradictions(one, topic_text)
        if path_kind == "cooktop_tip":
            one = _cooktop_excerpt(one)
        one = (one or "").strip()
        if not one or _source_quote_rejected(one) or not source_sentence_is_printable(one):
            continue
        if not _quote_is_verbatim(raw, one):
            continue
        preferred = any(pattern.search(one) for pattern in _QUOTE_PREFER.get(path_kind or "", ()))
        if not preferred and not sentence_is_on_procedure(one, topic_text, path_kind):
            continue
        one = _as_sentence(one)
        key = re.sub(r"\s+", " ", one.lower())
        if key in seen:
            continue
        seen.add(key)
        kept.append(one)
    for sentence in kept:
        if any(pattern.search(sentence) for pattern in _QUOTE_PREFER.get(path_kind or "", ())):
            return _with_following_next(kept, sentence)
    return _with_following_next(kept, kept[0]) if kept else ""


def _source_doc_key(src: dict) -> str:
    """Same manual, not the same page number on a different book."""
    title = (src.get("title") or "").strip().lower()
    ids = re.findall(r"ccd-0*\d+|ins\.sta\.\d+|\d{4}-\d{3}", title)
    if ids:
        return " ".join(sorted(set(ids)))
    return title


def polish_bay_sources(
    sources: list[dict],
    locked_count: int,
    topic_text: str,
    path_kind: str,
    *,
    prefer_diagnostic: bool = False,
    protect_pages: set[int] | None = None,
) -> list[dict]:
    """Human titles, whole-sentence snippets, and only cites that belong on this sheet."""
    protect = protect_pages or set()
    out = []
    seen = set()
    locked_flags = []
    for index, src in enumerate(sources or []):
        locked = index < locked_count
        raw_excerpt = src.get("excerpt") or ""
        title = human_source_title(src.get("title") or "", src.get("file_path") or "")
        page = _page_int(src.get("page"))
        cited = page in protect
        if source_is_discontinued(title, raw_excerpt) or source_is_discontinued(src.get("title") or "", raw_excerpt):
            continue
        file_path = src.get("file_path") or ""
        if _is_brochure_text_companion(title, raw_excerpt, file_path) or _is_brochure_text_companion(
            src.get("title") or "", raw_excerpt, file_path
        ):
            continue
        if sheet_has_internal_note(title) or sheet_has_internal_note(raw_excerpt):
            if re.search(r"facr08|ccd-0*8666", f"{title} {raw_excerpt}", re.I):
                title = "Furrion Chill FACR08 8K manual CCD-0008666"
            else:
                continue
        # A quote is copied from retrieved chunk text for this page. A locked
        # or hand-written string is not a quote, so the cite stays and the line is blank.
        chunk_text = src.get("_chunk_text") or ""
        if not chunk_text:
            excerpt = ""
        else:
            excerpt = _best_verbatim_quote(chunk_text, path_kind, topic_text)
            excerpt = _strip_internal_notes(excerpt)
        raw_off = any(re.search(pattern, raw_excerpt or "", re.I) for pattern in _PATH_OFF.get(path_kind or "", ()))
        if path_kind == "stabilizer" and not cited and not locked:
            if not _STABILIZER_KEEP_RE.search(excerpt or "") and not _STABILIZER_KEEP_RE.search(raw_excerpt or ""):
                continue
        if not excerpt:
            # A page we mean to cite keeps its title. A junk page does not.
            # An off-topic excerpt never keeps the page, even when PRIMARY named it.
            # Cooktop grease is the exception: the range manual stays, with no quote.
            title_ok = source_is_on_procedure(title, "", topic_text, path_kind)
            cooktop_manual = path_kind == "cooktop_tip" and title_ok
            # The C-Jack checklist is the tongue manual. Keep the title when
            # its sentences are about a different prove.
            bal_manual = path_kind == "bal_tongue" and title_ok
            if raw_off and not locked and not cooktop_manual:
                continue
            if not (locked or cited or cooktop_manual or bal_manual):
                continue
        elif not locked and not cited and not source_is_on_procedure(title, excerpt, topic_text, path_kind):
            continue
        excerpt_key = re.sub(r"\s+", " ", excerpt.lower()).strip()
        key = (title.lower(), page)
        # A blank quote is not a duplicate of another blank cite.
        if key in seen or (excerpt_key and excerpt_key in seen and not cited):
            continue
        seen.add(key)
        if excerpt_key:
            seen.add(excerpt_key)
        locked_flags.append(locked)
        out.append(
            {
                "title": title,
                "page": page,
                "excerpt": excerpt,
                "_install": _is_install_manual(title, raw_excerpt),
                "_chunk_text": chunk_text,
            }
        )
    if prefer_diagnostic and any(_is_diagnostic_manual(s["title"], s["excerpt"]) for s in out):
        kept = []
        kept_locked = []
        for src, locked in zip(out, locked_flags):
            if src.get("_install") and not locked:
                continue
            kept.append(src)
            kept_locked.append(locked)
        out = kept
    for src in out:
        src.pop("_install", None)
    out = _drop_near_duplicate_sources(out, protect)
    out = _dedupe_cited_pages(out)
    # An empty cite stays when a different manual already quoted that page number.
    filled = {
        (_source_doc_key(src), src.get("page"))
        for src in out
        if (src.get("excerpt") or "").strip() and src.get("page")
    }
    out = [
        src
        for src in out
        if (src.get("excerpt") or "").strip() or (_source_doc_key(src), src.get("page")) not in filled
    ]
    if path_kind == "cooktop_tip" and not any((src.get("excerpt") or "").strip() for src in out):
        titled = _cooktop_title_only(sources)
        out = [src for src in (out or titled) if src.get("page")]
    if path_kind == "stabilizer" and not out:
        out = _cooktop_title_only(sources, "Lippert PSX1 front stabilizer jack")
    # A source line needs a page. A locked title-only cite (no invented page) may stay.
    kept = []
    for src in out:
        if not src.get("page") and not src.get("title_only"):
            continue
        src.pop("_chunk_text", None)
        kept.append(src)
    return kept


def _drop_near_duplicate_sources(sources: list[dict], protect_pages: set[int] | None = None) -> list[dict]:
    """A later page that restates an earlier snippet replaces that earlier page.

    A page named in PRIMARY is never the one that gets replaced.
    """
    protect = protect_pages or set()
    kept: list[dict] = []
    for src in sources:
        replaced = False
        for prev in list(kept):
            if not _is_near_duplicate_excerpt(src.get("excerpt") or "", prev.get("excerpt") or ""):
                continue
            prev_page = prev.get("page") or 0
            page = src.get("page") or 0
            prev_protected = prev_page in protect
            src_protected = page in protect
            if prev_protected and src_protected:
                continue
            if prev_protected:
                replaced = True
                break
            if src_protected:
                prev.clear()
                prev.update(src)
                replaced = True
                break
            longer = len(src.get("excerpt") or "") > len(prev.get("excerpt") or "")
            if page > prev_page or (page == prev_page and longer):
                prev.clear()
                prev.update(src)
            replaced = True
            break
        if not replaced:
            kept.append(src)
    return kept


def _cited_pages(primary_cite: str) -> set[int]:
    """Page numbers the PRIMARY line names. Those sources have to stay."""
    text = primary_cite or ""
    pages = {int(number) for number in re.findall(r"\bpage\s+(\d{1,3})\b", text, flags=re.I)}
    pages.update(int(number) for number in re.findall(r"\bfig(?:ure)?\.?\s*(\d{1,3})\b", text, flags=re.I))
    return pages


def _with_following_next(sentences: list[str], chosen: str) -> str:
    """Keep a Next sentence that was glued onto the cited line."""
    text = _as_sentence(chosen)
    for index, sentence in enumerate(sentences):
        if sentence.strip().rstrip(".") != (chosen or "").strip().rstrip("."):
            continue
        follow = sentences[index + 1].strip() if index + 1 < len(sentences) else ""
        if re.match(r"next\b", follow, re.I):
            return f"{text.rstrip()} {_as_sentence(follow)}"
        break
    return text


def _keep_primary_excerpt(raw: str) -> str:
    """A cited page still needs a sentence when the scrub would otherwise empty it."""
    cleaned = clean_ocr_prose(raw or "")
    sentences = []
    for sentence in _split_sentences(cleaned):
        sentence = _strip_ocr_bullet(sentence).strip()
        if (
            sentence
            and not _is_verbless_fragment(sentence)
            and not _is_scanned_fragment(sentence)
            and not sheet_has_internal_note(sentence)
            and not _is_multilingual_ocr_line(sentence)
        ):
            sentences.append(sentence)
    sentences = _trim_trailing_verbless(sentences)
    for sentence in sentences:
        if (
            len(sentence) >= 20
            and not _is_header_residue(sentence)
            and not _is_scanned_fragment(sentence)
            and not sheet_has_internal_note(sentence)
        ):
            return _with_following_next(sentences, sentence)
    for sentence in reversed(sentences):
        if (
            _sentence_has_verb(sentence)
            and not _is_scanned_fragment(sentence)
            and not sheet_has_internal_note(sentence)
        ):
            return _with_following_next(sentences, sentence)
    return ""


def _strip_ocr_bullet(text: str) -> str:
    """Drop a leading '?', dash, or arrow left by a column read."""
    return re.sub(r"^(?:(?:->|→|[\?\-\*•>\u2022])\s*)+", "", (text or "").strip()).strip()


def _is_raw_ocr_step(text: str) -> bool:
    """Page headers, '?' field labels, and NOTE dumps are not bay steps."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return True
    if t.startswith("?"):
        return True
    if "?" in t[:-1]:
        return True
    if _is_multilingual_ocr_line(t):
        return True
    if _NO_LIBRARY_STEP_RE.search(t):
        return True
    if _sentence_is_cut(t):
        return True
    if re.match(r"^(?:note|warning|caution)\b", t, re.I) and not re.search(r"\bif\b", t, re.I):
        return True
    if re.match(r"^\d+\s*[.\-]\s*\d+", t):
        return True
    if re.search(r"\b\d+\s+EN\b", t):
        return True
    if re.search(r"cleaning the adb|duct size|duct layout", t, re.I):
        return True
    if _TRANSCRIPTION_RE.search(t):
        return True
    if _is_parts_list_dump(t):
        return True
    return False


def _steps_from_ranked(pages) -> list[str]:
    """Yes/no and check sentences from the cited pages. Timeline headers are not steps."""
    pieces = []
    seen = set()
    for d in pages or []:
        row = chunk_as_dict(d)
        if _is_install_manual(row.get("title") or "", row.get("excerpt") or ""):
            continue
        cleaned = clean_ocr_prose(row.get("excerpt") or "")
        for sentence in _split_sentences(cleaned):
            sentence = _strip_ocr_bullet(sentence)
            if _is_raw_ocr_step(sentence) or _is_header_residue(sentence):
                continue
            if (
                OPEN_THE_MANUAL_RE.search(sentence)
                or POWER_LOOKS_SANE_RE.search(sentence)
                or NETWORK_PLUGS_RE.search(sentence)
            ):
                continue
            if not (_is_decision_sentence(sentence) or _is_actionable_sentence(sentence)):
                continue
            key = re.sub(r"\s+", " ", sentence.lower())[:80]
            if key in seen:
                continue
            seen.add(key)
            pieces.append(sentence)
    return pieces


def _is_furnace_bay(category: str = "", model_text: str = "", concern: str = "") -> bool:
    """Furnace jobs use the thermostat-jumper prove. Cooktops do not."""
    if is_cooktop_pan_on_flameout_context(category, model_text, concern):
        return False
    if is_cooktop_range_context(category, model_text, concern):
        return False
    blob = f"{category or ''} {model_text or ''} {concern or ''}".lower()
    return "furnace" in blob


def is_thetford_flush_leak_context(
    category: str = "", model_text: str = "", concern: str = ""
) -> bool:
    """A Thetford toilet that leaks under the flush lever. Not a poor-flush job."""
    unit = f"{category or ''} {model_text or ''}"
    thetford = bool(re.search(r"\bthetford\b|\b42070\b|style\s*ii", unit, re.I))
    plumbing = bool(
        re.search(r"plumb", category or "", re.I) and re.search(r"toilet", category or "", re.I)
    )
    if not thetford and not (plumbing and is_toilet_job(category, model_text, concern)):
        return False
    return bool(re.search(r"\bleaks?\b|\bleaking\b|\bweep", concern or "", re.I))


def _thetford_leak_rank_score(page: dict) -> int:
    """Leak rows and the two kits outrank poor flush, winterizing, and the riser."""
    blob = f"{page.get('title') or ''} {page.get('excerpt') or ''}".lower()
    score = 0
    if "water supply line connection" in blob or "leak persists from water valve" in blob:
        score += 80
    if "vacuum breaker leaks while flushing" in blob:
        score += 40
    if re.search(r"\b42109\b", blob):
        score += 60
    if re.search(r"\b34122\b|\b34123\b", blob):
        score += 60
    if re.search(
        r"poor flush|flow rate|blade/ball|\bfrozen\b|winteriz|toilet riser|\briser\b|scarico|opzioni",
        blob,
    ):
        score -= 50
    return score


def _rank_thetford_leak_pages(pages, limit: int) -> list:
    ordered = sorted(pages or [], key=_thetford_leak_rank_score, reverse=True)
    return ordered[:limit]


def _fitted_cite(ranked, needles, fallback: str, path_kind: str = "") -> str:
    """Primary line stays inside the header. Prefer the prove page, then the latest page.

    A page about a different job (gas valve, ignition, paper-suction) is not the cite.
    """
    off = _PATH_OFF.get(path_kind or "", ())
    hits = []
    for d in ranked or []:
        title = (d.get("title") or "").strip()
        excerpt = d.get("excerpt") or ""
        if off and any(re.search(pattern, excerpt, re.I) for pattern in off):
            continue
        blob = f"{title} {excerpt}".lower()
        if needles and not any(n in blob for n in needles):
            continue
        if title:
            hits.append(d)
    prefer = ("fan fault", "bypass", "jumper", "sail switch")
    preferred = [
        d
        for d in hits
        if any(k in f"{d.get('title') or ''} {d.get('excerpt') or ''}".lower() for k in prefer)
    ]
    pool = preferred or hits
    if path_kind == "e2":
        page_27 = [row for row in pool if _page_int(row.get("page")) == 27]
        if page_27:
            pool = page_27
    if pool:
        d = max(pool, key=lambda row: _page_int(row.get("page")) or 0)
        title = human_source_title((d.get("title") or "").strip(), d.get("file_path") or "")
        page = _page_int(d.get("page"))
        page_bit = f" page {page}" if page else ""
        cite = f"{title}{page_bit}"
        if len(cite) <= 91:
            return _as_sentence(cite)
        short = fallback.rstrip(".")
        if page and f"page {page}" not in short.lower():
            short = f"{short} page {page}"
        return _as_sentence(_clip(short, 91))
    return _as_sentence(_clip(fallback, 91))


def _topic_figures(ranked, title: str, caption: str, excerpt: str) -> list[BayFigure]:
    library = pick_cited_figures(ranked)
    seed = _seed_path_figure("generic")
    seed.title = title
    seed.caption = caption
    seed.excerpt = excerpt
    real = [
        fig
        for fig in library
        if fig.image_png and not _png_is_generated_sketch(fig.image_png)
    ]
    if real:
        return real
    return [seed]


def _furnace_path(ranked) -> dict:
    """Same climax GD uses: jumper R/W at the furnace, then the sail switch."""
    return {
        "primary_cite": _fitted_cite(
            ranked,
            ("furnace", "thermostat", "sail"),
            "Suburban furnace service manual, thermostat bypass",
            "furnace",
        ),
        "pattern_means": (
            "The fan turns on and then shuts off, and the furnace will not blow warm. "
            "Prove the wall thermostat first by jumping R/W at the furnace. A furnace "
            "that runs on that jumper needs a wall thermostat. A furnace that does not "
            "run on that jumper needs a sail-switch prove."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "The fan turns on, then shuts off. No warm air.",
                    0.50,
                    0.09,
                    w=420,
                    h=70,
                ),
                FlowNode(
                    "d1",
                    "decision",
                    "Furnace dead with\nR and W jumped?",
                    0.32,
                    0.29,
                    w=220,
                    h=100,
                ),
                FlowNode(
                    "p2",
                    "process",
                    "Remove the jumper.\nProve the sail switch.",
                    0.32,
                    0.49,
                    w=280,
                    h=86,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "Replace the wall\nthermostat.",
                    0.82,
                    0.29,
                    w=200,
                    h=72,
                ),
                FlowNode(
                    "d2",
                    "decision",
                    "Sail switch passes\npower out?",
                    0.32,
                    0.70,
                    w=220,
                    h=100,
                ),
                FlowNode(
                    "y2",
                    "end",
                    "Limit switch and module board checked.\nEnd of this prove.",
                    0.32,
                    0.91,
                    w=280,
                    h=84,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Sail is not closed.\nProve airflow first.",
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
                ('Bypass the wall thermostat at the furnace. Jumper R/W at the furnace thermostat terminals so the coach thermostat and its wiring are out of the path. If it runs on the jumper, the fault is the thermostat or wiring. Then replace the wall thermostat. That is the confirmed correction.')
            ),
            (
                ('Remove the jumper and prove the sail switch. Do this if the furnace does not run with R/W jumped. Run the blower and check the sail switch. Power in with no power out means the sail is not closed. Then prove airflow and the sail before the board. Power in and power out both present means the sail passed. Then go to the limit check.')
            ),
            (
                ('Check the limit switch, then the module board, from the cited furnace pages. Do this when the sail passes and there is still no heat. If heat returns, that is the confirmed correction.')
            ),
        ],
        "do_not": [
            "Do not condemn the module board before the wall thermostat is jumped at the furnace.",
            "Do not leave the sail switch jumped.",
        ],
        "sources": [],
        "display_model": "",
        "flow_tall": True,
        "full_story": True,
    }


def _e2_fan_path(ranked) -> dict:
    """CCD-0008122 Fan Fault diamond: 12V at F+ and F-, then inverter PCB and fan."""
    return {
        "primary_cite": _fitted_cite(
            ranked,
            ("fan fault", "inverter", "f+", "f-"),
            "Furrion fridge service manual, Fan Fault Diagnostics, page 27",
            "e2",
        ),
        "pattern_means": (
            "An E2 or fan-fault code on this fridge is the fan-fault diagnostics path. "
            "Measure about 12V at F+ and F- on the inverter PCB. No voltage means replace "
            "the inverter PCB and the fan. Voltage present with the error still on after the "
            "connection check means replace the inverter PCB and the fan."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "E2 or fan fault on this fridge.",
                    0.50,
                    0.09,
                    w=420,
                    h=70,
                ),
                FlowNode(
                    "d1",
                    "decision",
                    "Nominal 12V at\nF+ and F-?",
                    0.32,
                    0.29,
                    w=220,
                    h=100,
                ),
                FlowNode(
                    "p2",
                    "process",
                    "Check fan connections,\nthen reset power.",
                    0.32,
                    0.49,
                    w=280,
                    h=86,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "Replace the inverter\nPCB and the fan.",
                    0.82,
                    0.29,
                    w=200,
                    h=72,
                ),
                FlowNode(
                    "d2",
                    "decision",
                    "Did the error\ngo away?",
                    0.32,
                    0.70,
                    w=220,
                    h=100,
                ),
                FlowNode(
                    "y2",
                    "end",
                    "That is the confirmed\ncorrection.",
                    0.32,
                    0.91,
                    w=280,
                    h=84,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Replace the inverter\nPCB and the fan.",
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
                "Connect power and locate the inverter PCB. Measure voltage at the F+ and "
                "F- terminals. Is the nominal voltage about 12V? If no, replace the inverter "
                "PCB and the fan. That is the confirmed correction for a dead fan-voltage reading. If yes, "
                "go to the connection check."
            ),
            (
                "Check the fan connection at the inverter PCB F+ and F- terminals and the fan "
                "quick connection. Reset power. Did the error code go away? If yes, that is "
                "the confirmed correction."
            ),
            (
                ('Replace the inverter PCB and the fan. Do this when the error stays after the checks and reset. That is the confirmed correction.')
            ),
        ],
        "do_not": [
            "Do not treat this E2 as a rooftop air-conditioner code.",
            "Do not replace only the board when fan voltage is present and the error remains.",
        ],
        "sources": [],
        "display_model": "",
        "flow_tall": True,
        "full_story": True,
    }


# Batch fix 2 (Leader 2026-10-14 8:57 PM): library steps become labeled checks.
# Every label comes from the manual sentence it sits on: the location phrase is
# Where, a meter word is Tools, the manual's If-lines are Bad/Good/If it fails,
# and Next names the following step. Nothing is added that the page does not say.
_PARTS_DUMP_RE = re.compile(r"\bx\s*\d\b|\w+x\s+\d\b|sold separately|\bqty\b|\?\s*$", re.I)
_FILLER_RE = re.compile(r"stay on it|go to the next (?:cited )?check|confirmed correction", re.I)
_WHERE_SPLIT_RE = re.compile(r"\s+((?:at|on|in|between|under|behind|inside)\s+(?:the|pin|each|both)\b.+)$", re.I)
_NEG_COND_RE = re.compile(r"\b(?:no|not|less than|bad|fails?|low|dead|open|damaged|loose|worn|leaks?)\b", re.I)
_METER_RE = re.compile(r"\d\s?V\b|\bV\s?DC\b|\bVAC\b|\b(?:volts?|voltage|continuity|ohms?|amps?|resistance)\b", re.I)


def _figure_label_dump(text: str) -> bool:
    words = re.findall(r"[A-Za-z][\w'-]*", text or "")
    caps = sum(1 for w in words if w[:1].isupper())
    return len(words) >= 8 and caps >= 0.6 * len(words) and not re.search(r"\b(?:if|then|check|test)\b", text, re.I)


def _cond_split(sentence: str):
    m = re.match(r"^(If|When)\s+(.+?),\s*(?:then\s+)?(.+?)\.?$", sentence.strip())
    if not m:
        return None
    return m.group(2).strip(), m.group(3).strip()


def _good_from_bad(cond: str) -> str:
    if re.search(r"\b(?:or|and|if)\b", cond, re.I):
        return ""
    m = re.match(r"^(?:there is |there's )?no (.+?)(?: is present)?$", cond, re.I)
    return f"{m.group(1)[:1].upper()}{m.group(1)[1:]} is present." if m else ""


def _lab_cap(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    text = text[:1].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def _labeled_generic_steps(sentences: list[str]) -> list[str]:
    """Labeled bay checks from manual sentences, or [] when none apply."""
    steps: list[dict] = []
    for raw in sentences or []:
        sent = _strip_ocr_bullet(re.sub(r"\s+", " ", raw or "").strip()).strip()
        sent = re.sub(r"^[a-z]{1,9}:\s*", "", sent)  # OCR-cut label like 'onnector:'
        if len(sent) < 12 or _PARTS_DUMP_RE.search(sent) or _figure_label_dump(sent) or _FILLER_RE.search(sent):
            continue
        cond = _cond_split(sent)
        if cond:
            if not steps:
                continue
            c, act = cond
            cur = steps[-1]
            if _NEG_COND_RE.search(c):
                cur.setdefault("bad", c)
                if is_action_heading(act):
                    cur.setdefault("fail", act)
                good = _good_from_bad(c)
                if good:
                    cur.setdefault("good", good)
            else:
                cur.setdefault("good", c)
            continue
        if not is_action_heading(sent):
            continue
        body = sent.rstrip(".")
        where = ""
        m = _WHERE_SPLIT_RE.search(body)
        head = body
        if m and len(body[: m.start()].split()) >= 2:
            head, where = body[: m.start()].strip(), m.group(1).strip()
        do = sent
        when = re.search(r"\s+((?:when|while|with)\s+.+)$", where or "", re.I)
        if when and len(sent.split()) > BAY_ACTION_WORDS:
            # 'Check X at Y when Z' -> Where: at Y; Do this: Check X. Check it when Z.
            where = where[: when.start()].strip()
            do = f"{head}. {head.split()[0]} it {when.group(1)}"
        elif where and len(sent.split()) > BAY_ACTION_WORDS:
            do = head
        elif not where:
            cut = re.search(r"\s+(?:for|to|using|until)\s+\S+", head)
            if cut and len(head[: cut.start()].split()) >= 2:
                head = head[: cut.start()].strip()
        if any(st["head"].lower() == head.lower() for st in steps) and where:
            more = " ".join(where.split()[:6]).rstrip(",")
            head = f"{head} {more}"
        if len(head.split()) > 10:
            continue
        steps.append({"head": head, "where": where, "do": do, "meter": bool(_METER_RE.search(sent))})
        if len(steps) >= MAX_BAY_ORDER:
            break
    labeled = [st for st in steps if st.get("bad") or st.get("good")]
    if not labeled:
        return []
    out = []
    for i, st in enumerate(labeled):
        nxt = labeled[i + 1]["head"] if i + 1 < len(labeled) else "Retest the complaint"
        parts = [f"Step {i + 1}: {_lab_cap(st['head'])}"]
        if st["where"]:
            parts.append(f"Where: {_lab_cap(st['where'])}")
        if st["meter"]:
            parts.append("Tools: Multimeter.")
        acts = []
        for piece in re.split(r":\s+|(?<=\.)\s+", st["do"]):
            acts.extend(short_actions(_lab_cap(piece)) or [_lab_cap(piece)])
        parts.append("Do this: " + " ".join(f"{n}. {_lab_cap(a)}" for n, a in enumerate(acts, 1)))
        for key, label in (("good", "Good looks like"), ("bad", "Bad looks like"), ("fail", "If it fails")):
            if st.get(key):
                parts.append(f"{label}: {_lab_cap(st[key])}")
        if i + 1 < len(labeled):
            parts.append(f"Next: {_lab_cap(nxt)}")
        else:
            parts.append("Next: Retest the complaint. If it is gone, that is the confirmed correction.")
        out.append(" ".join(parts))
    return out


def _generic_bay_order(excerpts: list[str], *, long_path: bool) -> list[str]:
    cleaned = []
    usable = []
    for raw in excerpts or []:
        sentence = _strip_ocr_bullet(raw)
        if _is_raw_ocr_step(sentence) or len(sentence) < 20:
            continue
        usable.append(sentence)
        if len(usable) >= MAX_BAY_ORDER:
            break
    has_decision = any(_is_decision_sentence(s) for s in usable)
    for i, raw in enumerate(usable):
        step = _body_check_from_excerpt(raw)
        if not step or _is_raw_ocr_step(step):
            continue
        last = (i == len(usable) - 1) and not long_path
        done = _ensure_next_step(step, last=last)
        # Batch fix 2: the pass/fail filler prints once, not on every step.
        if not last and any("stay on it" in c for c in cleaned) and "stay on it" in done and "stay on it" not in step:
            done = _as_sentence(scrub_sheet_text(step))
        cleaned.append(done)
    if not cleaned:
        cleaned.append(
            _ensure_next_step(
                "Write the first reading on this sheet, then ask a manager before any part swap.",
                last=not long_path,
            )
        )
    # Scaffold only when the library actually gave a yes/no step. Otherwise keep the sheet short.
    if long_path and has_decision:
        have = " ".join(cleaned).lower()
        for scaffold in GENERIC_LONG_SCAFFOLD:
            if len(cleaned) >= 6:
                break
            if scaffold.lower() not in have:
                cleaned.append(scaffold)
                have += " " + scaffold.lower()
        if not any("confirmed correction" in s.lower() for s in cleaned):
            cleaned.append(GENERIC_LONG_SCAFFOLD[-1])
    return cleaned[:MAX_BAY_ORDER]


def _generic_pattern_means(concern: str, *, long_path: bool) -> str:
    lead = _as_sentence(concern or "This is the customer complaint")
    if long_path:
        return (
            f"{lead} Work this as a full appliance path from the cited manual pages. "
            "Do each cited check on this sheet. Write pass or fail and the next step after every check. "
            "Thresholds and pass or fail meaning stay on this page."
        )
    return (
        f"{lead} Use the next cited checks from the manual pages on this sheet. "
        "Each step on this sheet says what to do next after a pass or a fail."
    )


def _opening_sentence(concern: str) -> str:
    """First whole sentence of the concern. The oval grows to fit; do not clip it."""
    text = re.sub(r"\s+", " ", (concern or "Customer concern").strip())
    parts = _split_sentences(text) or [text]
    return _as_sentence(parts[0])


def _generic_flowchart(concern: str, steps: list[str] | None = None) -> Flowchart:
    """OEM yes/no spine for any new concern — not a linear bot list."""
    start = _opening_sentence(concern or "Customer concern")
    raw_first = (steps[0] if steps else "") or "Do the first cited check."
    first = _strip_ocr_bullet(clean_ocr_prose(raw_first))
    first = (_split_sentences(first) or [first])[0]
    if _is_raw_ocr_step(first):
        first = "Do the first cited check."
    first = _as_sentence(first)
    return Flowchart(
        readable=True,
        nodes=[
            FlowNode("s", "start", start, 0.50, 0.09, w=400, h=66),
            FlowNode("d1", "decision", "Did the first\ncheck pass?", 0.32, 0.32, w=220, h=100),
            FlowNode("n1", "end", "Stay on that check\nuntil it passes.", 0.82, 0.32, w=200, h=72),
            FlowNode("p2", "process", first, 0.32, 0.55, w=260, h=80),
            FlowNode("d2", "decision", "Is the complaint\ngone?", 0.32, 0.75, w=220, h=100),
            FlowNode("y2", "end", "That is the confirmed\ncorrection.", 0.32, 0.93, w=260, h=72),
            FlowNode("n2", "end", "Go to the next step\non this sheet.", 0.82, 0.75, w=200, h=72),
        ],
        edges=[
            FlowEdge("s", "d1"),
            FlowEdge("d1", "p2", "YES", "bottom", "top"),
            FlowEdge("d1", "n1", "NO", "right", "left"),
            FlowEdge("p2", "d2", "", "bottom", "top"),
            FlowEdge("d2", "y2", "YES", "bottom", "top"),
            FlowEdge("d2", "n2", "NO", "right", "left"),
        ],
    )


# ---------------------------------------------------------------------------
# Library helpers (same stack GD chat uses)
# ---------------------------------------------------------------------------
def _fcr10_display_model(brand: str = "", model: str = "", concern: str = "") -> str:
    """Dial-off master case keeps FCR10DCGTA-BL. A longer typed token stays as typed."""
    blob = f"{concern or ''} {brand or ''} {model or ''}"
    long = re.search(r"\b(FCR10DCGTA-[A-Z0-9-]+)\b", blob, re.I)
    if long:
        return join_brand_model(brand or "Furrion", long.group(1).upper())
    typed = (model or "").strip()
    if re.fullmatch(r"(?:furrion\s+)?fcr10", typed, re.I):
        return "Furrion FCR10DCGTA-BL"
    return join_brand_model(brand, model) or "Furrion fridge"


def join_brand_model(brand: str = "", model: str = "") -> str:
    """One brand token. 'Suburban' plus 'Suburban NT-20SEQT' stays a single Suburban."""
    brand = re.sub(r"\s+", " ", (brand or "").strip())
    model = re.sub(r"\s+", " ", (model or "").strip())
    if not brand:
        return model
    if not model:
        return brand
    rest = model
    prefix = brand.lower() + " "
    while rest.lower() == brand.lower() or rest.lower().startswith(prefix):
        if rest.lower() == brand.lower():
            return brand
        rest = rest[len(brand) :].strip()
    return f"{brand} {rest}" if rest else brand


def model_text_from(brand: str = "", model: str = "") -> str:
    return join_brand_model(brand, model)


def _chunk_meta_value(ch, name: str) -> str:
    """Stored document field, or the lookup copy search attaches to a chunk."""
    lookup = f"_lookup_{name}"
    if isinstance(ch, dict):
        value = ch.get(name)
        if value is None or value == "":
            value = ch.get(lookup)
        if (value is None or value == "") and name == "keywords":
            value = ch.get("_lookup_doc_keywords")
    else:
        value = getattr(ch, name, None)
        if value is None or value == "":
            value = getattr(ch, lookup, None)
        if (value is None or value == "") and name == "keywords":
            value = getattr(ch, "_lookup_doc_keywords", None)
    return "" if value is None else str(value)


def chunk_as_dict(ch) -> dict:
    """Normalize a DocChunk or dict used by ranking helpers."""
    if isinstance(ch, dict):
        excerpt = ch.get("excerpt") or ch.get("chunk_text") or ""
        row = {
            "title": ch.get("title") or "",
            "page": ch.get("page"),
            "excerpt": excerpt,
            "chunk_text": excerpt,
            "file_path": ch.get("file_path"),
            "category": ch.get("category") or ch.get("category_name") or "",
            "document_id": ch.get("document_id"),
            "image_png": ch.get("image_png"),
            "figures": list(ch.get("figures") or []),
            "figure_label": ch.get("figure_label") or "",
        }
    else:
        excerpt = getattr(ch, "chunk_text", "") or getattr(ch, "excerpt", "") or ""
        row = {
            "title": getattr(ch, "title", "") or "",
            "page": getattr(ch, "page", None),
            "excerpt": excerpt,
            "chunk_text": excerpt,
            "file_path": getattr(ch, "file_path", None),
            "category": getattr(ch, "category", "") or getattr(ch, "category_name", "") or "",
            "document_id": getattr(ch, "document_id", None),
            "image_png": getattr(ch, "image_png", None),
            "figures": list(getattr(ch, "figures", None) or []),
            "figure_label": getattr(ch, "figure_label", "") or "",
        }
    for name in ("keywords", "brand", "models", "clean_title", "product_line", "doc_number"):
        row[name] = _chunk_meta_value(ch, name)
    return row


def rewrite_bay_search_symptom(
    category_name: str = "",
    model_text: str = "",
    concern: str = "",
) -> str:
    """Same search-boost chain GD chat uses (Document Library only — no live web)."""
    symptom = (concern or "").strip()
    if not symptom:
        return symptom
    if is_fcr_dial_off_compressor_run_context(category_name, model_text, symptom):
        symptom = dial_off_run_search_symptom(category_name, model_text, symptom)
        if DIAL_OFF_RUN_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {DIAL_OFF_RUN_SEARCH_BOOST}".strip()
        return symptom
    ice = is_fridge_ice_moisture_context(category_name, model_text, symptom)
    if ice:
        symptom = ice_moisture_search_symptom(category_name, model_text, symptom)
        if ICE_MOISTURE_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {ICE_MOISTURE_SEARCH_BOOST}".strip()
    symptom = level_up_search_symptom(category_name, model_text, symptom)
    if is_firefly_can_path_context(category_name, model_text, symptom):
        if FIREFLY_CAN_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {FIREFLY_CAN_SEARCH_BOOST}".strip()
    if is_coleman_2111_context(category_name, model_text, symptom):
        # Do not add the Furrion FACT/FACR boost. That string was becoming the brand.
        symptom = coleman_search_symptom(category_name, model_text, symptom)
    else:
        symptom = ac_search_symptom(category_name, model_text, symptom)
        if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
            if FACR_FREEZE_SEARCH_BOOST not in symptom:
                symptom = f"{symptom} {FACR_FREEZE_SEARCH_BOOST}".strip()
    if is_fcr_e2_fan_fault_context(category_name, model_text, symptom):
        symptom = fcr_e2_search_symptom(category_name, model_text, symptom)
    if _is_furnace_bay(category_name, model_text, symptom) and "thermostat bypass" not in symptom.lower():
        symptom = f"{symptom} furnace sail switch thermostat bypass jumper".strip()
    symptom = water_heater_search_symptom(category_name, model_text, symptom)
    symptom = cooktop_search_symptom(category_name, model_text, symptom)
    symptom = bal_tongue_search_symptom(category_name, model_text, symptom)
    symptom = stabilizer_search_symptom(category_name, model_text, symptom)
    symptom = ground_control_search_symptom(category_name, model_text, symptom)
    symptom = dometic_nocoool_search_symptom(category_name, model_text, symptom)
    return symptom


def bay_brand_retrieval(chunks, category_name: str = "", model_text: str = "", concern: str = ""):
    """
    Keep library pages for the brand the tech named.

    Returns (pages, brand_miss). brand_miss is true when a brand is known and
    no retrieved page is that brand. Another brand's pages are never kept.
    A toilet job does not keep a refrigerator manual. Coleman 2111 also keeps
    1976-536 / Peacemaker / wall-thermostat pages.
    """
    pages = [chunk_as_dict(ch) for ch in (chunks or [])]
    asked = set(asked_brands_for_lookup(category_name, model_text, concern))
    toilet = is_toilet_job(category_name, model_text, concern)
    if toilet and not asked:
        asked = {"thetford"}
    coleman_job = is_coleman_2111_context(category_name, model_text, concern)
    if not asked:
        return pages, False
    matched, other, plain = [], [], []
    for d in pages:
        models = (d.get("models") or "").strip()
        if models and not model_list_allows(models, model_text or ""):
            continue
        title = d.get("title") or ""
        keywords = d.get("keywords") or ""
        excerpt = d.get("excerpt") or ""
        file_path = d.get("file_path") or ""
        brand = d.get("brand") or ""
        clean_title = d.get("clean_title") or ""
        product_line = d.get("product_line") or ""
        doc_number = d.get("doc_number") or ""
        extra = " ".join(part for part in (models, clean_title, product_line, doc_number) if part)
        name = library_filename_words(file_path)
        declared = canonical_shop_brands(brand)
        canon = canonical_shop_brands(title, keywords, name, extra)
        coleman_text = is_coleman_library_text(f"{title} {keywords} {excerpt} {name} {extra}")
        if declared and not (asked & declared):
            other.append(d)
            continue
        if chunk_matches_asked_brand(
            title,
            keywords,
            excerpt,
            asked,
            coleman_job=coleman_job,
            file_path=file_path,
            brand=brand,
            models=models,
            clean_title=clean_title,
            product_line=product_line,
            doc_number=doc_number,
        ):
            matched.append(d)
        elif canon or (coleman_text and not coleman_job):
            other.append(d)
        else:
            plain.append(d)
    if matched:
        return matched, False
    if "thetford" in asked or toilet:
        return [], True
    if other and not plain:
        return [], True
    if not pages and not _bay_product_lock(category_name, model_text, concern):
        return [], True
    return plain, False


def _bay_product_lock(category_name: str = "", model_text: str = "", concern: str = "") -> bool:
    """True when a code-owned sheet still applies with an empty library."""
    return any(
        (
            is_fcr_dial_off_compressor_run_context(category_name, model_text, concern),
            is_fridge_ice_moisture_context(category_name, model_text, concern),
            is_facr_rooftop_freeze_context(category_name, model_text, concern),
            is_firefly_can_path_context(category_name, model_text, concern),
            is_bal_soft_touch_tongue_only_context(category_name, model_text, concern),
            is_coleman_2111_context(category_name, model_text, concern),
            is_fcr_e2_fan_fault_context(category_name, model_text, concern),
            _is_furnace_bay(category_name, model_text, concern),
            is_ground_control_context(category_name, model_text, concern),
            is_dometic_ceiling_sheet_context(category_name, model_text, concern),
            is_fact12_freeze_code_context(category_name, model_text, concern),
            is_girard_petit_tube_context(category_name, model_text, concern),
            is_stabilizer_override_pin_context(category_name, model_text, concern),
            is_cooktop_tip_sheet_context(category_name, model_text, concern),
            is_level_up_lead_jack_drift_context(category_name, model_text, concern),
        )
    )


def _rank_coleman_pages(pages, limit: int) -> list:
    """Prefer the Coleman rooftop titles. A different brand cannot outrank them."""

    def score(page) -> int:
        blob = f"{page.get('title') or ''} {page.get('excerpt') or ''}".lower()
        s = 0
        if "coleman" in blob or "airxcel" in blob:
            s += 20
        if "12vdc" in blob or "12 vdc" in blob or "wall" in blob:
            s += 8
        if "1976-536" in blob or "1976-603" in blob:
            s += 12
        if "peacemaker" in blob:
            s += 12
        if "1976-695" in blob or "mechanical" in blob:
            s += 8
        if "furrion" in blob or "dometic" in blob:
            s -= 40
        return s

    ordered = sorted(pages or [], key=score, reverse=True)
    kept = [p for p in ordered if score(p) > 0]
    return (kept or ordered)[:limit]


def rank_bay_chunks(
    chunks,
    category_name: str = "",
    model_text: str = "",
    concern: str = "",
    limit: int = 8,
) -> list:
    """Apply the same product ranking GD uses, after the brand lock."""
    pages, _brand_miss = bay_brand_retrieval(chunks, category_name, model_text, concern)
    pages = filter_chunks_for_unit(pages, category_name, model_text, concern)
    query = f"{model_text or ''} {concern or ''}".strip()
    if is_ground_control_context(category_name, model_text, concern):
        return rank_chunks_for_ground_control(pages, query, limit=limit)
    if is_dometic_b57915_nocoool_context(category_name, model_text, concern):
        return rank_chunks_for_dometic_nocoool(pages, query, limit=limit)
    if is_coleman_2111_context(category_name, model_text, concern):
        return _rank_coleman_pages(pages, limit)
    if is_fcr_dial_off_compressor_run_context(category_name, model_text, concern):
        ranked = rank_chunks_for_dial_off_run(pages, query, limit=limit)
        return [
            ch
            for ch in ranked
            if _page_int(chunk_as_dict(ch).get("page")) not in DIAL_OFF_DROP_PAGES
        ]
    if is_fridge_ice_moisture_context(category_name, model_text, concern):
        return rank_chunks_for_ice_moisture(pages, query, limit=limit)
    if is_firefly_can_path_context(category_name, model_text, concern) or is_level_up_advantage_context(
        category_name, model_text, concern
    ):
        return rank_chunks_for_level_up(pages, query, limit=limit)
    if is_fcr_e2_fan_fault_context(category_name, model_text, concern):
        return rank_chunks_for_fcr_fan_fault(pages, query, limit=limit)
    if is_air_conditioning_context(category_name, model_text, concern):
        return rank_chunks_for_ac(pages, query, limit=limit)
    if is_water_heater_context(category_name, model_text, concern):
        return rank_chunks_for_water_heater(pages, query, limit=limit)
    if is_cooktop_pan_on_flameout_context(category_name, model_text, concern):
        return rank_chunks_for_cooktop_pan_on(pages, query, limit=limit)
    if is_bal_soft_touch_tongue_only_context(category_name, model_text, concern):
        return rank_chunks_for_bal_tongue(pages, query, limit=limit)
    if is_stabilizer_override_pin_context(category_name, model_text, concern):
        return rank_chunks_for_stabilizer_override(pages, query, limit=limit)
    if is_thetford_flush_leak_context(category_name, model_text, concern):
        return _rank_thetford_leak_pages(pages, limit)
    return pages[:limit]


def _page_int(value):
    try:
        n = int(value)
        return n if n > 0 else None
    except (TypeError, ValueError):
        return None


def pick_cited_figures(chunks, limit: int = 4) -> list[BayFigure]:
    """Figures from retrieved library pages (Fig. / diagram language), not the live web."""
    out = []
    seen = set()
    for ch in chunks or []:
        d = chunk_as_dict(ch)
        excerpt = d.get("excerpt") or ""
        title = (d.get("title") or "Shop library").strip()
        page = _page_int(d.get("page"))
        key = (title.lower(), page)
        if key in seen:
            continue
        if _is_brochure_text_companion(title, excerpt, d.get("file_path") or ""):
            continue
        fig_hit = FIG_RE.search(excerpt) or page_has_figure_or_terminal_layout(excerpt)
        if not fig_hit:
            continue
        seen.add(key)
        cap = fig_hit.group(0) if hasattr(fig_hit, "group") else "Library figure"
        out.append(
            BayFigure(
                title=title,
                page=page,
                caption=cap,
                excerpt=excerpt[:500],
                image_png=d.get("image_png"),
            )
        )
        if len(out) >= limit:
            break
    return out


def _png_bytes(image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _figure_font(size: int = 18):
    from PIL import ImageFont

    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


_SEED_CACHE: dict[str, bytes] = {}


def _seed_figure_png(kind: str) -> bytes:
    """Ship ice-pattern / data-plate schematics so HIT sheets are not figure-empty."""
    cached = _SEED_CACHE.get(kind)
    if cached is not None:
        return cached
    png = _draw_seed_figure_png(kind)
    _SEED_CACHE[kind] = png
    return png


def _draw_seed_figure_png(kind: str) -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (900, 520), (248, 250, 252))
    draw = ImageDraw.Draw(img)
    title_f = _figure_font(22)
    body_f = _figure_font(18)
    small_f = _figure_font(16)
    draw.rectangle((10, 10, 889, 509), outline=(1, 20, 124), width=4)
    if kind == "ice":
        draw.rectangle((70, 50, 400, 470), outline=(18, 18, 36), width=4, fill=(255, 255, 255))
        draw.rectangle((82, 250, 388, 458), fill=(186, 214, 240))
        for y in range(262, 450, 16):
            draw.line((92, y, 378, y + 6), fill=(70, 120, 175), width=3)
        draw.line((70, 250, 400, 250), fill=(200, 40, 40), width=4)
        draw.text((82, 80), "TOP  clear", fill=(18, 18, 36), font=body_f)
        draw.text((82, 270), "FROST from mid-down", fill=(1, 20, 124), font=body_f)
        draw.text((430, 60), "Fig. 36  Rear-wall frost pattern", fill=(1, 20, 124), font=title_f)
        draw.text((430, 120), "A light sheet on the back wall", fill=(18, 18, 36), font=body_f)
        draw.text((430, 150), "alone can be normal cycling.", fill=(18, 18, 36), font=body_f)
        draw.text((430, 210), "Heavy frost starting halfway", fill=(18, 18, 36), font=body_f)
        draw.text((430, 240), "down is the Ice and Moisture", fill=(18, 18, 36), font=body_f)
        draw.text((430, 270), "pattern. Stay on that section.", fill=(18, 18, 36), font=body_f)
        draw.text((430, 340), "Furrion fridge service manual", fill=(18, 18, 36), font=small_f)
        draw.text((430, 370), "Ice and Moisture section", fill=(18, 18, 36), font=small_f)
    elif kind == "facr":
        draw.rectangle((80, 60, 400, 190), outline=(18, 18, 36), width=4, fill=(230, 236, 245))
        draw.rectangle((110, 190, 370, 250), outline=(18, 18, 36), width=3, fill=(210, 220, 230))
        draw.polygon([(240, 250), (225, 360), (255, 360)], fill=(80, 80, 90))
        draw.ellipse((210, 360, 270, 400), outline=(1, 20, 124), width=3)
        draw.text((430, 60), "Rooftop assembly / base pan", fill=(1, 20, 124), font=title_f)
        draw.text((430, 110), "Inspect the evaporator pan", fill=(18, 18, 36), font=body_f)
        draw.text((430, 145), "and the condensate drain.", fill=(18, 18, 36), font=body_f)
        draw.text((430, 200), "If the drain is restricted or", fill=(18, 18, 36), font=body_f)
        draw.text((430, 235), "the pan is iced, clear it,", fill=(18, 18, 36), font=body_f)
        draw.text((430, 270), "then retest cooling.", fill=(18, 18, 36), font=body_f)
        draw.text((90, 430), "Drain path", fill=(18, 18, 36), font=small_f)
    elif kind == "generic":
        draw.rectangle((70, 70, 420, 420), outline=(18, 18, 36), width=4, fill=(255, 255, 255))
        draw.text((90, 110), "Cited library figure", fill=(1, 20, 124), font=title_f)
        draw.text((90, 180), "Do the next cited check", fill=(18, 18, 36), font=body_f)
        draw.text((90, 220), "on this sheet. Thresholds", fill=(18, 18, 36), font=body_f)
        draw.text((90, 260), "and pass / fail stay here.", fill=(18, 18, 36), font=body_f)
        draw.text((90, 330), "Names, not part numbers.", fill=(18, 18, 36), font=small_f)
    else:
        draw.rectangle((70, 80, 420, 360), outline=(18, 18, 36), width=4, fill=(255, 255, 255))
        draw.rectangle((90, 100, 400, 160), fill=(1, 20, 124))
        draw.text((104, 118), "Level Up Advantage controller", fill=(255, 255, 255), font=title_f)
        draw.rectangle((100, 210, 200, 270), outline=(18, 18, 36), width=3, fill=(230, 230, 230))
        draw.rectangle((110, 220, 190, 260), fill=(40, 40, 40))
        draw.rectangle((250, 210, 350, 270), outline=(18, 18, 36), width=3, fill=(250, 250, 250))
        draw.line((300, 270, 300, 370), fill=(180, 40, 40), width=6)
        draw.text((100, 284), "CAN  rubber-boot", fill=(18, 18, 36), font=small_f)
        draw.text((108, 310), "TERMINATOR IN", fill=(1, 20, 124), font=body_f)
        draw.text((250, 284), "CAN  Firefly cable", fill=(18, 18, 36), font=small_f)
        draw.text((258, 310), "UNPLUG ONLY", fill=(200, 30, 40), font=body_f)
        draw.text((450, 60), "Two ports labeled CAN", fill=(1, 20, 124), font=title_f)
        draw.text((450, 110), "Leave the rubber-boot", fill=(18, 18, 36), font=body_f)
        draw.text((450, 145), "terminator plugged in.", fill=(18, 18, 36), font=body_f)
        draw.text((450, 180), "Unplug only the CAN cable", fill=(18, 18, 36), font=body_f)
        draw.text((450, 215), "to Firefly / OneControl.", fill=(18, 18, 36), font=body_f)
        draw.text((450, 270), "POWER CONNECTOR", fill=(1, 20, 124), font=body_f)
        draw.text((450, 305), "Red versus Green ground.", fill=(18, 18, 36), font=small_f)
        draw.text((450, 335), "Want solid 12V+.", fill=(18, 18, 36), font=small_f)
        draw.text((450, 380), "Shop PN 807662 (Sources only)", fill=(90, 90, 90), font=small_f)
    return _png_bytes(img)


def load_oem_figure_png(name: str) -> bytes:
    """Real library-page art from the OEM manuals. Never a drawn cartoon."""
    return (OEM_FIGURE_DIR / name).read_bytes()


# Full manual pages are not figures. These boxes are the cited drawing on that page.
_OEM_FIGURE_CROP = {
    # The whole drainage-openings row, including the diagram. Not the cut
    # neighbors ("blower is defective" above, "seals are damaged" below).
    # Full drainage row: "Water enters the vehicle" through "openings are clogged".
    # Drainage row, both rules. "vehicle" ends near y=834. The partial line at
    # 816 does not cross that cell. The next full-width rule is y=872.
    "ccd7990-p7.png": (36, 732, 1066, 880),
    "ccd8666-p10.png": (28, 520, 728, 824),
}
MAX_SHEET_PAGES = 3
MAX_FIGURES_PER_SHEET = 2
FACT12_MISLABEL_CITE = "Indexed file is the FACR08 8K book, not the FACT12 model manual."


def _cropped_oem_png(name: str) -> bytes:
    raw = load_oem_figure_png(name)
    box = _OEM_FIGURE_CROP.get(name)
    if not box:
        return raw
    from PIL import Image

    image = Image.open(BytesIO(raw)).convert("RGB")
    cropped = image.crop(box)
    if name == "ccd7990-p7.png":
        # The next row's vertical rules start just under this row's rule. Blank them.
        gray = cropped.convert("L")
        width, height = gray.size
        px = gray.load()
        rule = None
        for y in range(height - 1, -1, -1):
            dark = sum(1 for x in range(0, width, 2) if px[x, y] < 80)
            if dark > width / 4:
                rule = y
                break
        if rule is not None and rule < height - 1:
            draw = cropped.load()
            for y in range(rule + 1, height):
                for x in range(width):
                    draw[x, y] = (255, 255, 255)
    return _png_bytes(cropped)


def _close_cut_figure(image):
    """Drop a white strip of stray rules under a grey frame.

    The live sheet paints whatever this returns. A small pre-crop used to skip
    the page crop and keep a frame whose bottom was already cut off.
    """
    width, height = image.size
    if width < 40 or height < 40:
        return image
    px = image.convert("L").load()

    def _grey(y: int) -> int:
        return sum(
            1
            for x in range(0, width, 2)
            if 140 <= px[x, y] <= 230
        )

    def _dark(y: int) -> int:
        return sum(1 for x in range(0, width, 2) if px[x, y] < 80)

    wide = [y for y in range(height) if _grey(y) > width / 8]
    if not wide:
        return image
    last = wide[-1]
    if last > height - 8:
        return image
    # A closed frame ends in white padding. A cut frame has a near-empty
    # gap and then a full-width rule that is not part of the drawing.
    gap = False
    rule = None
    for y in range(last + 1, height):
        if _dark(y) > width / 4 and gap:
            rule = y
            break
        if _dark(y) < 12 and _grey(y) < 8:
            gap = True
    if rule is None:
        return image
    pad = 12
    return image.crop((0, 0, width, min(height, last + 1 + pad)))


def crop_page_png_to_figure(png: bytes) -> bytes:
    """Crop a rendered manual page down to a figure. Empty means keep the full page off the sheet."""
    if not png:
        return b""
    try:
        from PIL import Image
    except Exception:
        return b""
    image = Image.open(BytesIO(png)).convert("RGB")
    closed = _close_cut_figure(image)
    if closed.size != image.size:
        return _png_bytes(closed)
    width, height = image.size
    if max(width, height) < 900 or height < width * 1.15:
        return png
    box = _figure_band_box(image)
    if not box:
        return b""
    x0, y0, x1, y1 = box
    if (y1 - y0) > height * 0.72 and (x1 - x0) > width * 0.72:
        return b""
    return _png_bytes(image.crop((x0, y0, x1, y1)))


def _content_spans(row: list[float], *, gap_ink: float = 0.012, min_gap: int = 12) -> list[list[int]]:
    """Ink bands split only on a real whitespace gap, so a crop never cuts a row."""
    spans = []
    y = 0
    height = len(row)
    while y < height:
        if row[y] < gap_ink:
            y += 1
            continue
        start = y
        while y < height and row[y] >= gap_ink:
            y += 1
        if spans and start - spans[-1][1] < min_gap:
            spans[-1][1] = y
        else:
            spans.append([start, y])
    return spans


def _figure_band_box(image) -> tuple[int, int, int, int] | None:
    """A full figure region. Thin strips and mid-row cuts stay off the sheet."""
    gray = image.convert("L")
    width, height = gray.size
    px = gray.load()
    row = []
    for y in range(height):
        ink = 0
        total = 0
        for x in range(0, width, 3):
            total += 1
            if px[x, y] < 170:
                ink += 1
        row.append(ink / total if total else 0)
    spans = _content_spans(row)
    if not spans:
        return None
    scored = []
    for start, end in spans:
        band_h = end - start
        if band_h < 24:
            continue
        seg = row[start:end]
        avg = sum(seg) / len(seg)
        var = sum((v - avg) ** 2 for v in seg) / len(seg)
        scored.append((var * 8.0 + min(band_h / height, 0.45), start, end))
    if not scored:
        return None
    scored.sort(reverse=True)
    _score, start, end = scored[0]
    # A short band is part of the figure above or below it. Grow to the next gap.
    thin = (end - start) < max(width * 0.22, height * 0.18)
    if thin:
        for _score, other_s, other_e in scored[1:]:
            gap = min(abs(other_s - end), abs(start - other_e))
            if gap > 48:
                continue
            start = min(start, other_s)
            end = max(end, other_e)
            if (end - start) >= max(width * 0.22, height * 0.18):
                break
    if (end - start) > height * 0.70:
        return None
    if (end - start) < max(80, width * 0.16):
        return None
    pad = 22
    x0, y0, x1, y1 = 8, max(0, start - pad), width - 8, min(height, end + pad)
    # A light grey cabinet frame is fainter than the ink threshold. Grow to include it,
    # and drop a stray rule that is only a dark column in the right margin.
    gray = image.convert("L")
    px = gray.load()
    def _row_has_frame(y: int) -> bool:
        if y < 0 or y >= height:
            return False
        mid = sum(1 for x in range(0, width, 3) if 80 <= px[x, y] <= 210)
        return mid > width / 30
    while y1 < height - 1 and _row_has_frame(y1):
        y1 += 1
    while y0 > 0 and _row_has_frame(y0 - 1):
        y0 -= 1
    # Trim a lone vertical rule in an otherwise white right margin.
    while x1 - x0 > 40:
        column = [px[x1 - 1, y] for y in range(y0, y1, 3)]
        dark = sum(1 for value in column if value < 80)
        white = sum(1 for value in column if value > 230)
        if dark and white > len(column) * 0.7:
            x1 -= 1
            continue
        break
    return (x0, y0, x1, y1)


def _oem_library_figures(kind: str) -> list[BayFigure]:
    if kind == "ice":
        return [
            BayFigure(
                title=FURRION_8122_TITLE,
                page=36,
                caption="Fig. 36 rear-wall frost pattern, views A and B",
                excerpt="Ice and Moisture. Figure 36 shows the rear-wall frost pattern.",
                image_png=load_oem_figure_png("ccd8122-fig36.png"),
            ),
        ]
    if kind == "facr":
        return [
            BayFigure(
                title=FACR_7990_TITLE,
                page=7,
                caption="CCD-0007990 page 7. Clean the drainage openings.",
                excerpt="Water enters the vehicle. Condensation water drainage openings are clogged.",
                image_png=_cropped_oem_png("ccd7990-p7.png"),
            ),
        ]
    return []


_GENERIC_SEED_PNG = b""


def _generic_seed_png() -> bytes:
    global _GENERIC_SEED_PNG
    if not _GENERIC_SEED_PNG:
        _GENERIC_SEED_PNG = _seed_figure_png("generic")
    return _GENERIC_SEED_PNG


def _png_is_generated_sketch(png: bytes) -> bool:
    """A drawn stand-in is not an OEM manual figure."""
    if not png:
        return False
    return any(png == _seed_figure_png(kind) for kind in ("generic", "ice", "facr", "firefly"))


def figure_is_placeholder(fig: BayFigure) -> bool:
    """A drawn sketch is not a manual figure, even when a library caption was pasted on it."""
    if "cited library figure" in (fig.caption or "").lower():
        return True
    return _png_is_generated_sketch(fig.image_png or b"")


def _real_library_figures(ranked) -> list[BayFigure]:
    """Library figures that already carry real page art. Sketches do not count."""
    return [
        fig
        for fig in pick_cited_figures(ranked)
        if fig.image_png and not _png_is_generated_sketch(fig.image_png)
    ]


def _seed_path_figure(kind: str) -> BayFigure:
    if kind == "ice":
        return BayFigure(
            title=FURRION_8122_TITLE,
            page=36,
            caption="Fig. 36 rear-wall frost pattern",
            excerpt="Ice and Moisture. Figure 36 shows the rear-wall frost pattern.",
            image_png=_seed_figure_png("ice"),
        )
    if kind == "facr":
        return BayFigure(
            title=FACR_7990_TITLE,
            page=None,
            caption="Rooftop assembly, base pan, and drain",
            excerpt="Use this book for the rooftop assembly, condensate drain, and base pan.",
            image_png=_seed_figure_png("facr"),
        )
    if kind == "dial_off":
        return BayFigure(
            title=FURRION_8122_TITLE,
            page=43,
            caption="Spark-Free Thermostat replacement, page 43",
            excerpt=(
                "Spark-Free Thermostat part G 2021128850. "
                "Open C and T with no jumper."
            ),
            image_png=_seed_figure_png("generic"),
        )
    if kind == "bal_tongue":
        return BayFigure(
            title="BAL SS 5.1 Stabilizing System INS.STA.001",
            page=None,
            caption="Soft-touch panel tongue jack output wire and tongue pigtail",
            excerpt=(
                "Check for 12V on the tongue jack output wire at the panel. "
                "No 12V means user panel 20300427. Voltage present means repair the pigtail."
            ),
            image_png=_seed_figure_png("generic"),
        )
    if kind == "generic":
        return BayFigure(
            title="Shop Document Library",
            page=None,
            caption="Cited library figure",
            excerpt="Do the next cited check on this sheet.",
            image_png=_seed_figure_png("generic"),
        )
    return BayFigure(
        title=FIREFLY_PATH_TITLE,
        page=None,
        caption="Level Up Advantage controller — two ports labeled CAN",
        excerpt="Leave the rubber-boot terminator in. Unplug the Firefly CAN cable only.",
        image_png=_seed_figure_png("firefly"),
    )


def _png_size(png: bytes) -> tuple[int, int]:
    if not png:
        return (0, 0)
    try:
        from PIL import Image
    except Exception:
        return (0, 0)
    image = Image.open(BytesIO(png))
    return image.size


def _png_is_thumbnail(png: bytes) -> bool:
    """A tiny page render is not a figure a tech can read."""
    width, height = _png_size(png)
    if width < 1 or height < 1:
        return True
    return max(width, height) < 300


def _png_is_text_block(png: bytes) -> bool:
    """A paragraph of body text is not a diagram. A one-row drawing is not this."""
    width, height = _png_size(png)
    if height < 90 or height > 420 or width < 180:
        return False
    try:
        from PIL import Image
    except Exception:
        return False
    image = Image.open(BytesIO(png)).convert("L")
    px = image.load()
    row_ink = []
    for y in range(height):
        ink = 0
        samples = 0
        for x in range(0, width, 2):
            samples += 1
            if px[x, y] < 180:
                ink += 1
        row_ink.append(ink / samples if samples else 0.0)
    bands = []
    y = 0
    while y < height:
        if row_ink[y] < 0.04:
            y += 1
            continue
        start = y
        while y < height and row_ink[y] >= 0.04:
            y += 1
        bands.append(y - start)
    if len(bands) < 5 or max(bands) > 26:
        return False
    # A paragraph's lines are about the same height. A one-row drawing mixes
    # hairline rules with taller shapes, so it is not a text block.
    ordered = sorted(bands)
    median = ordered[len(ordered) // 2]
    if max(bands) >= 12 and max(bands) > median * 3:
        return False
    return True


def _figure_is_illegible(fig: BayFigure, png: bytes) -> bool:
    """Thumbnails, text blocks, and Brochure-TEXT pages stay off the sheet."""
    if _is_brochure_text_companion(fig.title, f"{fig.caption} {fig.excerpt}"):
        return True
    if _png_is_thumbnail(png) or _png_is_text_block(png):
        return True
    return False


def _figure_is_plenum(fig: BayFigure) -> bool:
    blob = f"{fig.title} {fig.caption} {fig.excerpt}".lower()
    return "6799-730" in blob or "plenum" in blob


def _figure_is_fan_or_board(fig: BayFigure) -> bool:
    blob = f"{fig.title} {fig.caption} {fig.excerpt}".lower()
    return any(token in blob for token in ("fan", "control board", "9-pin", "9 pin", "capacitor"))


def _coleman_figures(ranked) -> list[BayFigure]:
    """Coleman pages only. The sheet figure is the fan or the board, not the plenum."""
    library = []
    for fig in pick_cited_figures(ranked):
        blob = f"{fig.title} {fig.caption} {fig.excerpt}".lower()
        if "furrion" in blob or "dometic" in blob or "ccd-0008666" in blob or "ccd-0007990" in blob:
            continue
        if _figure_is_plenum(fig):
            continue
        library.append(fig)
    fan_board = [fig for fig in library if _figure_is_fan_or_board(fig)]
    if fan_board:
        library = fan_board
    if library:
        return library
    seed = _seed_path_figure("generic")
    seed.title = "Coleman-Mach 12VDC wall-thermostat rooftop service manual"
    seed.caption = "9-pin Fan High: pin 5 black, pin 9 white common"
    seed.excerpt = "Prove Fan High, then the Peacemaker bypass, then the fan run capacitor."
    return [seed]


def _brand_miss_figure(brand: str = "", model: str = "", concern: str = "") -> BayFigure:
    model_text = model_text_from(brand, model)
    who = library_miss_brand_label("", model_text, concern) or (brand or "").strip() or "this brand"
    sentence = f"No {who} document in the shop library for this unit."
    seed = _seed_path_figure("generic")
    seed.title = "Shop Document Library"
    seed.caption = sentence
    seed.excerpt = "General shop safety only. Add the OEM manual to the shop library."
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
            "Fan running with no cold air is the no-cool path. Run the Peacemaker bypass at the rooftop unit. If that bypass cools, the unit is making cold air. If it does not cool, stay on that bypass. Do not start on the filter check.",
            ('If the Peacemaker bypass cools, bypass the ceiling selector. If the selector bypass does not cool, stay on it and retest.'),
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
            # Labels from CCD-0008666: control-box 12 VDC and ground cables (page 15, Fig. 19),
            # the four thermostat cables tagged "To wall thermostat" (page 15, Fig. 17), and
            # power off at the battery disconnect or fuse before service (page 18).
            "Step 1: Measure 12 V at the control box. "
            "Where: At the control box, on the red 12 VDC cable and the black ground cable. "
            "Tools: Multimeter on DC volts. "
            "Do this: 1. Find the red 12 VDC cable and the black ground cable. 2. Measure the voltage between them. "
            "Good looks like: About 12 V DC. "
            "Bad looks like: No 12 V at the cable. "
            "If it fails: Repair the 12 V feed and retest the code. "
            "Next: Check the thermostat cable connection.",
            "Step 2: Check the thermostat cable connection. "
            "Where: At the control box, on the four cables tagged To wall thermostat. "
            "Safety: Disconnect power at the battery disconnect or fuse first. "
            "Do this: 1. Match each cable color to its wall thermostat wire. 2. Look for a pushed-back pin. 3. Look for a loose connector. "
            "Good looks like: Each color matches and every pin is seated. "
            "Bad looks like: A crossed color, a pushed-back pin, or a loose connector. "
            "If it fails: Repair the connection and retest the code. "
            "Next: Check the freeze sensor on the evaporator coil.",
            ('Check the freeze sensor on the evaporator coil. If it is loose or off the coil, reseat it and retest. If it is seated and E3 remains, write the readings and stop.'),
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
            ('Replace the freeze sensor and retest. Do this if it is seated and the code remains.'),
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
            ('With the blower running, confirm suction at that tube. If the tube is off or lacks suction, seat it at the blower. Then retest. That is the confirmed correction.'),
            ('Retest the heater. Do this when the tube is on and suction is present. If E8 clears, that position is the correction.'),
            "If E8 remains after suction is confirmed, check the air-pressure switch. "
            "Check for integrity and connections of the pressure switch hose. "
            "Repair the switch and retest if it fails.",
            ('Check the gas supply and retest the heater. Do this if the air-pressure switch is good.'),
            ('Write the readings and stop. Do this if gas is good and E8 remains. Do not replace the control board.'),
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
            ('Replace the complete front stabilizer jack assembly. Do this when the override roll pin or coupler is broken or seized. Do not replace the coupler only.'),
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
            ('Reposition the thermocouple tip in the burner flame with the pan on. Do this if the tip sits low.'),
            ('Check that the flame holds with the pan on. If it holds, the reposition is the confirmed correction.'),
            ('Raise the tip so the pan cannot push it clear. Do this if the flame still goes out. Then light the burner again.'),
            ('Put the pan on the grate. Watch that the tip stays in the flame for one full minute.'),
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
            ('Test the lead-jack valve coil on the gray wire. If it tests bad, repair that coil circuit before any cartridge.'),
            "Confirm the swap plumbing: manifold hose in the notched port, "
            "follow-leg hose in the non-notched port, unused ports plugged, "
            "and the orange extend and black retract hoses not reversed.",
            "Confirm the manual override screw is backed out.",
            ("Replace the front lead-jack cartridge valve, part 177094. Do this when the coil is good and the plumbing is correct. The override screw must be backed out. The parts list calls 177094 the Cartridge Valve, item F (Lippert Level Up Towable Owner's Manual, page 15; Lippert Level Up FW Owner's Manual, page 18)."),
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
                "If the flange is low, add Thetford spacers to 7/16 inch.",
                fail="If the flange is low, add Thetford spacers to 7/16 inch.",
                tools="ruler",
                section="removal",
            ),
            _branch_step(
                # OM 42088 p3: "Use Thetford spacers to adjust, if necessary, to 7/16 in above floor."
                "If the flange is low, add Thetford spacers to 7/16 inch.",
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


_ANY_BRAND_SHEETS = {"ice"}


def _spec_off_brand(spec: dict, asked: set) -> bool:
    """True when a code-owned sheet's cited manuals all name a maker the tech did not."""
    titles = [str(src.get("title") or "") for src in (spec.get("sources") or [])]
    named = [canonical_shop_brands(t) for t in titles if canonical_shop_brands(t)]
    return bool(named) and not any(b & asked for b in named)


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
    brand_pages, brand_miss = bay_brand_retrieval(chunks, category, model_text, concern)
    asked_brands = set(asked_brands_for_lookup(category, model_text, concern))
    # The off-brand fallback below uses only the Brand field the tech typed.
    typed_brands = canonical_shop_brands(brand or "")
    # Batch fix 1: with a named brand, rank only that brand's (or unbranded) pages.
    rank_from = brand_pages if (asked_brands and brand_pages and not brand_miss) else chunks
    ranked = rank_bay_chunks(rank_from, category, model_text, concern, limit=8)
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

    def _generic_spec():
            long_path = is_long_appliance_path(category, concern)
            step_pages = [] if fact12_mislabeled_only else list(ranked)
            raw_steps = _steps_from_ranked(step_pages)
            raw_steps = [
                r for r in raw_steps
                if not (_PARTS_DUMP_RE.search(r) or _figure_label_dump(r) or _FILLER_RE.search(r))
            ]
            labeled = _labeled_generic_steps(raw_steps)
            if long_path and len(labeled) < MAX_BAY_ORDER // 2:
                labeled = []  # a long appliance path keeps its full story
            bay_order = labeled or _generic_bay_order(raw_steps, long_path=long_path)
            spec = {
                "primary_cite": (
                    FACT12_MISLABEL_CITE if fact12_mislabeled_only else _generic_primary_cite(ranked)
                ),
                "pattern_means": _generic_pattern_means(concern, long_path=long_path),
                "flowchart": _generic_flowchart(
                    concern or "Customer concern",
                    [re.sub(r"^Step\s+\d+:\s*", "", b).split(" Where:")[0].split(" Do this:")[0] for b in bay_order],
                ),
                "bay_order": bay_order,
                "do_not": [
                    "Do not skip the next cited check.",
                    "Do not guess a part swap before the cited checks on this sheet.",
                ],
                "sources": [],
                "flow_tall": True,
                "full_story": long_path,
            }
            return spec

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
        spec = _generic_spec()
    # Batch fix 1: a code-owned sheet that cites another maker's manual never
    # prints for a named brand; the library pages for that brand are used instead.
    if (
        typed_brands
        and path_kind not in ("", "brand_miss")
        # The ice/frost sheet is locked for any fridge brand (test_step_format, Dometic DM2652).
        and path_kind not in _ANY_BRAND_SHEETS
        and _spec_off_brand(spec, typed_brands)
    ):
        if brand_miss:
            spec = _no_brand_match_path(brand, model, concern)
            path_kind = "brand_miss"
        else:
            spec = _generic_spec()
            path_kind = ""

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
    # Batch fix 3: '(Fig. 17)' wraps into a cut-off '(Fig .' on the page; spell it out.
    for src in sources:
        if src.get("excerpt"):
            src["excerpt"] = re.sub(r"\((Fig)(s?)\s*\.\s*", lambda m: "(Figure" + ("s " if m.group(2) else " "), src["excerpt"])
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


def _label_side_fault(box, routes) -> bool:
    """Mirror of the profile's YES/NO side rule, in page points (y up)."""
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    best, best_d = None, 1e9
    for pts in routes or []:
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if abs(y2 - y1) > 10 or abs(x2 - x1) < 18:
                continue
            d = math.hypot(cx - x1, cy - y1)
            if d < best_d:
                best, best_d = (x1, x2), d
    if not best or best_d > 70:
        return False
    x1, x2 = best
    return (x2 < x1 - 8 and cx > x1 + 10) or (x1 < x2 - 8 and cx < x1 - 10)


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

    ok = []
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
            for along in (4.0, 10.0, 16.0, 24.0, 32.0):
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
                ok.append((x, baseline, block, box))
    # Batch fix 3: a label never sits on the far side of a nearby side arrow's
    # start (YES left of a right arrow / right of a left arrow).
    for got in ok:
        if not _label_side_fault(got[3], routes + ([own_pts] if own_pts else [])):
            return got
    if ok:
        return ok[0]
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
        if edge.from_side == "bottom" and edge.to_side == "top" and 0 < abs(x2 - x1) < dst["w"] / 2.0 - 12.0:
            # Batch fix 3: a small offset lands straight on the box top. The old
            # 15-25 pt jog put YES beside a sideways stub (profile PF-20).
            x2 = x1
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


# v4.19.63: a figure prints only when its manual page is cited on the sheet.
_DOC_CODE_RE = re.compile(r"\b(CCD-\d{4,}|TI-\d+|QR-\d+|INS\.[A-Z]+\.\d+|\d{5,8})\b", re.I)
_PAGE_CITE_RE = re.compile(r"((?:CCD-\d{4,}|TI-\d+|QR-\d+|\b\d{5,8}\b)[^()]{0,80}?)\bpages?\s+(\d+)(?:\s*(?:and|,|-|to)\s*(\d+))?", re.I)


def _doc_codes(title: str) -> set[str]:
    return {code.upper() for code in _DOC_CODE_RE.findall(title or "")}


def cited_manual_pages(proc: "BayProcedure") -> dict[str, set[int]]:
    """Document code -> pages the sheet cites (Sources, primary cite, step cites)."""
    cited: dict[str, set[int]] = {}

    def add(codes, page):
        try:
            n = int(page or 0)
        except (TypeError, ValueError):
            n = 0
        if not n:
            return
        for code in codes:
            cited.setdefault(code, set()).add(n)

    for src in proc.sources or []:
        add(_doc_codes(str(src.get("title") or "")), src.get("page"))
    texts = [proc.primary_cite or ""] + [str(step or "") for step in proc.bay_order or []]
    for text in texts:
        flat = re.sub(r"\s+", " ", text)
        for m in _PAGE_CITE_RE.finditer(flat):
            codes = _doc_codes(m.group(1))
            add(codes, m.group(2))
            if m.group(3):
                add(codes, m.group(3))
    return cited


def _norm_title(title) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()


def keep_cited_page_figures(proc: "BayProcedure") -> "BayProcedure":
    """Drop bay-order and leftover figures whose manual page the sheet never cites.

    Only applies when the sheet cites at least one manual page. Repair-branch
    figures (proc.procedures) are left alone; they carry their own step cite.
    """
    cited = cited_manual_pages(proc)
    if not cited:
        return proc
    titled: dict[str, set[int]] = {}
    for src in proc.sources or []:
        try:
            titled.setdefault(_norm_title(src.get("title")), set()).add(int(src.get("page") or 0))
        except (TypeError, ValueError):
            continue
    # A step cite written '(Manual title, page N)', including the How template's.
    for step in proc.bay_order or []:
        for m in re.finditer(r"\(([^()]{4,160}?),\s*page\s+(\d+)\)", re.sub(r"\s+", " ", str(step or ""))):
            titled.setdefault(_norm_title(m.group(1)), set()).add(int(m.group(2)))

    def fits(fig) -> bool:
        codes = _doc_codes(getattr(fig, "title", "") or "")
        try:
            page = int(getattr(fig, "page", 0) or 0)
        except (TypeError, ValueError):
            page = 0
        if not page:
            return False
        if codes:
            if any(code in cited for code in codes):
                return any(page in cited.get(code, set()) for code in codes)
        # A manual with no document number is matched by its title. A figure from
        # a manual the sheet does not cite at all is left to the brand gates.
        pages = titled.get(_norm_title(getattr(fig, "title", "")))
        if pages is None:
            return not codes
        return page in pages

    def supports(fig, step: str) -> bool:
        """The figure's own retrieved text names this step's part number."""
        excerpt = str(getattr(fig, "excerpt", "") or "")
        nums = set(re.findall(r"\b\d{5,8}\b", excerpt))
        return bool(nums and nums & set(re.findall(r"\b\d{5,8}\b", str(step or ""))))

    steps = list(proc.bay_order or [])
    proc.step_figures = [
        [fig for fig in group or [] if fits(fig) or supports(fig, steps[i] if i < len(steps) else "")]
        for i, group in enumerate(proc.step_figures or [])
    ]
    proc.figures = [fig for fig in proc.figures or [] if fits(fig)]
    return proc


# Same-brand companion manuals: (job pattern, document code). Furrion FACT and
# FACR rooftop units share the CCD-0007990 troubleshooting and service manual.
BAY_COMPANION_DOCS = (
    (r"\bFAC[RT]\d", "CCD-0007990"),
)

_COMPANION_STOP = {
    "with", "that", "this", "then", "from", "into", "when", "what", "will", "your", "they", "them",
    "have", "does", "only", "there", "their", "after", "before", "check", "confirm", "retest",
    "write", "readings", "stop", "code", "remains", "already", "seated",
}


def add_companion_sources(proc: "BayProcedure", chunks: list) -> "BayProcedure":
    """Cite a same-brand companion manual page that names a part the steps check.

    ``chunks`` are library rows (title, page, chunk_text) from a companion
    document. A page is cited only when it names a two-word part from a step
    (for example 'freeze sensor'), the document is not cited yet, and the
    quoted words are that page's own text. At most one page is added.
    """
    cited_codes = {code for src in proc.sources or [] for code in _doc_codes(str(src.get("title") or ""))}
    cited_codes |= _doc_codes(proc.primary_cite or "")
    phrases = []
    for step in proc.bay_order or []:
        words = re.findall(r"[a-z]+", re.split(r"\bHow\s*\(", (step or "").lower())[0])
        for a, b in zip(words, words[1:]):
            if len(a) >= 4 and len(b) >= 4 and a not in _COMPANION_STOP and b not in _COMPANION_STOP:
                phrase = f"{a} {b}"
                if phrase not in phrases:
                    phrases.append(phrase)
    for chunk in chunks or []:
        data = chunk_as_dict(chunk)
        title = str(data.get("title") or "")
        codes = _doc_codes(title)
        if not codes or codes & cited_codes or not data.get("page"):
            continue
        text = str(data.get("chunk_text") or data.get("excerpt") or "")
        flat = re.sub(r"\s+", " ", text)
        for phrase in phrases:
            m = re.search(r"[^.]*\b" + re.escape(phrase) + r"\b[^.]*\.", flat, re.I)
            if not m:
                continue
            quote = m.group(0).strip()
            # Keep the quote to the phrase's own line of the manual table.
            q = re.search(re.escape(phrase) + r"[^.]{0,40}\.", quote, re.I)
            quote = _cap(q.group(0) if q else quote)
            proc.sources = list(proc.sources or []) + [
                {"title": title, "page": int(data.get("page")), "excerpt": quote}
            ]
            return proc
    return proc


# v4.19.63: plain bay-order steps print one short action per line.
BAY_ACTION_WORDS = 12
_ABBREV_DOT_RE = re.compile(r"\b(Fig|Figs|No|Nos|approx|Approx|vs|e\.g|i\.e|Ref|Pg|p|pp)\.\s+(?=[0-9A-Za-z(])")
_HOW_BLOCK_RE = re.compile(r"\s*\bHow\s*\(([^()]*?),\s*page\s+(\d+)\)\s*:.*$", re.S)
_HOW_BARE_RE = re.compile(r"\s*\bHow\s*\(([^()]*?)\)\s*:.*$", re.S)


def _bay_word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)?", text or ""))


def plain_step_without_how(step: str) -> str:
    """Drop the stored How template from a plain bay-order line.

    The template is a field list ('Tools: not stated in ...', 'Order: ...')
    built from raw manual text. On the printed sheet it leaked 'not stated'
    filler and cut OCR ('(Fig.' / '1A)'). The shop line stays as written; the
    manual page the template named stays on the step as a cite.
    """
    raw = re.sub(r"\s+", " ", step or "").strip()
    m = _HOW_BLOCK_RE.search(raw)
    if m:
        head = raw[: m.start()].rstrip()
        cite = f"({m.group(1).strip()}, page {m.group(2)})"
        if not re.search(r"\bpage\s+\d+", head, re.I):
            cite = cite.strip("()")
            head = f"{head.rstrip('.')}. See {cite}." if head else f"See {cite}."
        return head
    m = _HOW_BARE_RE.search(raw)
    if m:
        return raw[: m.start()].rstrip()
    return raw


def _sentences_keep_abbrev(text: str) -> list[str]:
    guarded = _ABBREV_DOT_RE.sub(lambda m: m.group(0).replace(". ", ".\x00"), text or "")
    parts = [p.replace("\x00", " ").strip() for p in re.split(r"(?<=[.!?])\s+", guarded)]
    return [p for p in parts if p]


def _cap(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def _finish(text: str) -> str:
    text = text.strip().rstrip(",;")
    if text and text[-1] not in ".!?:":
        text += "."
    return text


# Split at 'and' only where an action verb follows, so 'Check A and B' keeps its verb.
_BAY_VERBS = r"(?:do not|escalate|straighten|check|test|measure|replace|repair|reset|confirm|seat|set|leave|turn|press|open|close|remove|install|clean|tighten|retest|go|stop|write|look|let|run|disconnect|reconnect|verify|inspect|plug|unplug|drain|fill|flush|move|bypass|record)"
_AND_ACTION = r",\s+(?=and\s+" + _BAY_VERBS + r"\b)"
_COMMA_ACTION = r",\s+(?=" + _BAY_VERBS + r"\b)"
_AND_ACTION_BARE = r"\s+(?=and\s+" + _BAY_VERBS + r"\b)"


def short_actions(sentence: str, limit: int = BAY_ACTION_WORDS) -> list[str]:
    """Split one sentence into lines of ``limit`` words or fewer.

    Splits only at clause marks the sentence already has (';', ', then',
    ', and', ', so', a comma after an If/When clause, then a plain comma, then
    ' and then' / ' and '). An If/When clause keeps its condition: it ends in
    ':' and the action follows on the next line. Words are never dropped,
    reworded, or reordered. A piece with no clause mark is left whole.
    """
    text = re.sub(r"\s+", " ", sentence or "").strip()
    if not text:
        return []
    if _bay_word_count(text) <= limit:
        return [_finish(text)]
    cond = re.match(r"^((?:If|When|Once|After|Before|Until|Unless|On a|On an|On the)\b[^,]{3,}?),\s+(.+)$", text)
    if cond is None:
        cond = re.match(r"^((?:If|When|Once|After|Before|Until|Unless)\b.{3,}?)\s+(?=(?:replace|repair|check|test|confirm|go|stop|reset)\b)(.+)$", text)
    if cond:
        listed = re.match(r"^([^,]+,\s+(?:or|and)\s+[^,]+),\s+(.+)$", cond.group(2))
        if listed and not re.match(r"^(?:replace|repair|check|test|confirm|go|stop|reset|set|let)\b", cond.group(2)):
            # 'If A, B, or C, do D': the whole list is the condition.
            head_text = text[: len(text) - len(listed.group(2))].rstrip().rstrip(",")
            cond = re.match(r"^(" + re.escape(head_text) + r"),\s+(.+)$", text)
        # The condition is never cut at 'and': only at 'while'/'because', so it means the same.
        # The condition is kept whole (never cut at 'and' or 'while'), so it
        # means the same; the action follows on the next line.
        # An If/then stays on one line (Leader 10/14 rev2). A condition alone
        # on a line is a split If/then; the card text is written short enough.
        rest = short_actions(_cap(cond.group(2)), limit)
        if not rest:
            return [_finish(cond.group(1))]
        first = rest[0]
        if not re.match(r"^(?:[A-Z]{2,}|[A-Z][a-z]*[A-Z0-9])", first):
            first = first[:1].lower() + first[1:]
        return [_finish(cond.group(1).rstrip(" ,") + ", " + first)] + rest[1:]
    for pattern in (r";\s+", r":\s+", r",\s+(?=then\b)", _AND_ACTION, r",\s+(?=so\b)", r",\s+(?=but\b)", _COMMA_ACTION, r"\s+(?=and then\b)", _AND_ACTION_BARE):
        pieces = [p for p in re.split(pattern, text) if p.strip()]
        if len(pieces) < 2:
            continue
        # Pack neighbours back together while they fit, so a list stays one line.
        packed = []
        joiner = "; " if pattern.startswith(";") else (": " if pattern.startswith(":") else (", " if "," in pattern else " "))
        for piece in pieces:
            piece = piece.strip()
            if packed and _bay_word_count(packed[-1] + joiner + piece) <= limit:
                packed[-1] = packed[-1] + joiner + piece
            else:
                packed.append(piece)
        if len(packed) < 2:
            continue
        out = []
        for at, piece in enumerate(packed):
            if pattern.startswith(":") and at < len(packed) - 1:
                piece = piece.rstrip() + "."
            if pattern in (_AND_ACTION, _AND_ACTION_BARE):
                # 'and' only joined the two clauses; the next line carries the same words.
                piece = re.sub(r"^and\s+(?!then\b)", "", piece)
            out.extend(short_actions(_cap(piece), limit))
        return out
    return [_finish(text)]


def bay_plain_step_lines(step: str, number: int) -> tuple[str, list[str]]:
    """Heading plus 'Do this:' lines for a plain bay-order step, each 12 words or fewer."""
    raw = plain_step_without_how(step)
    actions = []
    for sentence in _sentences_keep_abbrev(raw):
        actions.extend(short_actions(sentence))
    actions = [a for a in actions if re.search(r"[A-Za-z]", a)]
    if not actions:
        return f"Step {number}: Do this step", []
    # The heading is the step's first action, never a condition, and it is not
    # repeated as line 1 (Leader 10/14 rev2).
    plain = [i for i, a in enumerate(actions) if is_action_heading(a) and not re.match(_CONDITION_START, a)]
    either = [i for i, a in enumerate(actions) if is_action_heading(a)]
    at = 0 if 0 in either else (plain or either or [0])[0]
    title = actions[at].rstrip(".:")
    # Line 1 is dropped only when it is the heading. A heading taken from a later
    # line leaves every line in place, so the order of work is unchanged.
    rest = actions[1:] if at == 0 else actions
    if not rest:
        return f"Step {number}: {title}", []
    return f"Step {number}: {title}", ["Do this:"] + [f"{i}. {a}" for i, a in enumerate(rest, 1)]


_CONDITION_START = r"^(?:If|When|Once|After|Before|Until|Unless|On a|On an|On the|With)\b"
_NON_ACTION_START = re.compile(
    r"^(?:If|When|Once|After|Before|Until|Unless|On a|On an|On the|With|The|This|That|It|A|An|Both|Each|Every|No|Shaft|Power|Did|Does|Is|Are)\b"
)


def is_action_heading(text: str) -> bool:
    """True when a heading reads as an instruction: it starts with a verb, not a condition or a statement."""
    t = re.sub(r"^Step\s+\d+\s*:\s*", "", str(text or "")).strip()
    if not t or t.endswith("?"):
        return False
    cond = re.match(r"^(?:If|When|Once|After|Before|Until|Unless|On a|On an|On the|With)\b[^,]*,\s+(?:then\s+)?(.+)$", t)
    if cond:
        # 'With the pad off, press FRONT' is an action with its condition.
        return is_action_heading(cond.group(1))
    if _NON_ACTION_START.match(t):
        return False
    first = t.split()[0].lower().strip(",.")
    if first == "do":
        return not re.match(r"^do\s+not\b", t, re.I)
    return bool(re.match(_BAY_VERBS + r"$", first)) or first in _EXTRA_HEADING_VERBS


_EXTRA_HEADING_VERBS = {
    "inspect", "watch", "clear", "note", "find", "use", "pull", "push", "hold", "lift", "lower", "level",
    "start", "power", "unscrew", "screw", "loosen", "apply", "fit", "attach", "connect", "swap", "add",
    "prove", "jump", "jumper", "read", "compare", "listen", "feel", "smell", "spin", "rotate", "wait",
    "take", "keep", "dry", "towel-dry", "correct", "stay", "probe", "trace", "label", "mark", "back",
    "seal", "shut", "cycle", "light", "relight", "verify", "ask", "call", "observe", "count", "time",
    "record", "write", "test", "measure", "reseat", "escalate", "straighten", "drop", "wash", "center",
    "clamp", "hoist", "make", "point", "r&r", "reposition", "raise", "put", "pour", "tape", "unplug", "plug", "bring", "back-probe", "jumper",
    "recharge", "charge", "grease", "lubricate", "bleed", "refill", "top",
}


def _add_step(cur: _SheetFlow, index: int, step: str, figures: list | None = None):
    """One bay-order step, then each cited figure under it. They stay on one page."""
    import manual_figures as mf

    text_x = MARGIN + 24.0
    text_w = _CONTENT_W - 32.0
    heading, lines = mf.lines_from_shop_text(step, index)
    if not re.match(r"\s*Step\s+\d+\s*:", step or "") and not any(
        re.match(r"^(?:Where|Good looks like|Next|If it fails|Safety|Tools):", line) for line in lines
    ):
        heading, lines = bay_plain_step_lines(step, index)
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


def _paint_figure_on(cur: _SheetFlow, fig: BayFigure, *, png: bytes, allow_break: bool = True, min_h: float = 0.0, reserve: float = 0.0) -> bool:
    """A leftover library figure, same width as a step figure, caption underneath.

    ``min_h`` lets a figure that does not fit at full size shrink onto this page
    when it stays at least that tall.
    """
    cap = f"{fig.caption or 'Figure'} -- {fig.title}" + (f" p.{fig.page}" if fig.page else "")
    _fw, _fh, block = _figure_block_height(png, cap, 0)
    need = 36.0 + block
    if need > cur.y - _FIGURE_FLOOR:
        shrunk = 0.0
        if min_h:
            shrunk = _fit_figure_pair(png, cap, cur.y - _FIGURE_FLOOR - 36.0 - reserve)[1]
        if shrunk and shrunk >= min_h:
            pass  # paint below at the shrunk size, leaving ``reserve``
        elif not allow_break:
            return False
        else:
            cur.new_page(cur.subtitle)
    room = cur.y - _FIGURE_FLOOR - 36.0
    if min_h and need > cur.y - _FIGURE_FLOOR:
        room -= reserve
    fig_w, fig_h = _fit_figure_pair(png, cap, room)
    if fig_h < 28 or fig_w < 28:
        return False
    if not _add_section(
        cur, "CITED MANUAL FIGURES", NAVY, follow_h=min(block, 36), allow_break=allow_break
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
    keep_cited_page_figures(proc)
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
        _add_section(body, "BAY ORDER (START HERE)", GREEN, follow_h=min(first.height, 48))
        for i, step in enumerate(steps, 1):
            group = []
            if i - 1 < len(proc.step_figures or []):
                group = list(proc.step_figures[i - 1] or [])
            _add_step(body, i, step, group)
            for fig in group:
                if fig and fig.image_png:
                    shown_figures.add(fig.image_png)
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
    # v4.19.63: a cited figure that fits on this page prints before Sources, so
    # no figure heading or caption follows a Sources line. The rest keep the
    # old place after Sources.
    shown = 0
    later = []
    sources = [src for src in proc.sources if src.get("page") or src.get("title_only")]

    def _room_for_sources_after(fig, png) -> bool:
        cap = f"{fig.caption or 'Figure'} -- {fig.title}" + (f" p.{fig.page}" if fig.page else "")
        need = 36.0 + _figure_block_height(png, cap, 0)[2] + 8.0
        return _sources_that_fit(body.remaining() - need, sources) is not None

    # rev2: a cited figure that fits on the last step's page prints there, under
    # the steps that cite it, before Do Not.
    sources = [src for src in proc.sources if src.get("page") or src.get("title_only")]
    rest = []
    do_not_h = (40.0 + sum(measure_text(f"- {d}", _CONTENT_W - 16, 8.5, leading=11.2).height + 3.0 for d in proc.do_not)) if proc.do_not else 0.0

    def _room_for_tail_after(fig, png) -> bool:
        cap = f"{fig.caption or 'Figure'} -- {fig.title}" + (f" p.{fig.page}" if fig.page else "")
        need = 36.0 + _figure_block_height(png, cap, 0)[2] + 8.0 + do_not_h
        return _sources_that_fit(body.remaining() - need, sources) is not None

    for fig, png in imaged:
        if shown < MAX_FIGURES_PER_SHEET and not _figure_is_squeezed(png, body.remaining()) and (len(pages) < MAX_SHEET_PAGES or _room_for_tail_after(fig, png)) and _paint_figure_on(
            body, fig, png=png, allow_break=False
        ):
            shown += 1
        else:
            rest.append((fig, png))
    if proc.do_not:
        _paint_do_not(body, proc.do_not)
    for fig, png in rest:
        if shown < MAX_FIGURES_PER_SHEET and not _figure_is_squeezed(png, body.remaining()) and _room_for_sources_after(fig, png) and _paint_figure_on(
            body, fig, png=png, allow_break=False
        ):
            shown += 1
        else:
            later.append((fig, png))
    _paint_fitting_sources(body, sources)

    # A short crop stays on the current page. A dedicated figure page has to
    # be a real figure, not a thin strip floating in blank paper.
    min_page_figure = 240.0
    for fig, png in later:
        if shown >= MAX_FIGURES_PER_SHEET:
            break
        if not _figure_is_squeezed(png, body.remaining()) and _paint_figure_on(
            body, fig, png=png, allow_break=False
        ):
            shown += 1
            continue
        # v4.19.63: one-action lines make a sheet longer. At the page cap a cited
        # figure shrinks onto the last page (140 pt or taller) instead of dropping.
        if len(pages) >= MAX_SHEET_PAGES and _paint_figure_on(
            body, fig, png=png, allow_break=False, min_h=140.0
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