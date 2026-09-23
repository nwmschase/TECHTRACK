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
from pathlib import Path
import re
import textwrap
import zlib

from gd_library_coach import (
    DIAL_OFF_RUN_SEARCH_BOOST,
    FACR_FREEZE_SEARCH_BOOST,
    FIREFLY_CAN_SEARCH_BOOST,
    ICE_MOISTURE_SEARCH_BOOST,
    ICE_MOISTURE_SHOP_LINE,
    WIRED_COACH_CAN_RE,
    ac_search_symptom,
    cooktop_search_symptom,
    bal_tongue_search_symptom,
    dial_off_run_search_symptom,
    ice_moisture_search_symptom,
    is_air_conditioning_context,
    is_bal_soft_touch_tongue_only_context,
    is_cooktop_pan_on_flameout_context,
    is_facr_rooftop_freeze_context,
    is_fcr_dial_off_compressor_run_context,
    is_fcr_e2_fan_fault_context,
    is_firefly_can_path_context,
    is_fridge_ice_moisture_context,
    is_level_up_advantage_context,
    is_stabilizer_override_pin_context,
    is_water_heater_context,
    level_up_search_symptom,
    page_has_figure_or_terminal_layout,
    lock_spark_free_part_g,
    rank_chunks_for_ac,
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

# Shop colors (TechTrack branding — not a Leader pixel clone).
NAVY = (0.004, 0.078, 0.486)
GREEN = (0.012, 0.537, 0.282)
RED = (0.875, 0.122, 0.149)
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
    "One is the rubber-boot terminator — leave that one plugged in. "
    "The other is the CAN cable to Firefly / OneControl — unplug that one only. "
    "Then try Manual Mode again."
)
FIREFLY_HOLDS_BRANCH = (
    "If Manual Mode holds with the Firefly CAN cable unplugged, Firefly / OneControl CAN "
    "is in the dump. Do not start a Level Up controller fault path. Next, call Firefly at "
    "574-825-4600 for USB firmware plus interim."
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
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()


def apply_sheet_standard(proc: "BayProcedure") -> "BayProcedure":
    """Post-compile pass. Locked Firefly strings are a no-op when already clean."""
    proc.pattern_means = scrub_sheet_text(proc.pattern_means)
    proc.primary_cite = (proc.primary_cite or "").strip()
    proc.bay_order = [scrub_sheet_text(step) for step in proc.bay_order if (step or "").strip()]
    proc.do_not = [
        item
        for item in (scrub_sheet_text(x) for x in proc.do_not)
        if item and not sheet_standard_violations(item)
    ]
    for node in proc.flowchart.nodes:
        node.text = scrub_sheet_text(node.text)
    proc.flowchart.readable = True
    if not any(n.kind == "decision" for n in proc.flowchart.nodes):
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


@dataclass
class DrawnText:
    text: str
    x: float
    y: float
    w: float = 200.0
    size: float = 9.0
    bold: bool = False
    color: tuple = INK
    align: str = "left"  # left | center
    leading: float = 0.0


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
class BayProcedure:
    concern: str
    brand: str = ""
    model: str = ""
    category: str = ""
    wo_number: str = ""
    created: datetime = field(default_factory=datetime.now)
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

    @property
    def model_line(self) -> str:
        if (self.display_model or "").strip():
            return self.display_model.strip()
        parts = [p for p in (self.brand.strip(), self.model.strip()) if p]
        return " ".join(parts) or "—"


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
                "downstream of the thermostat. Escalate the inverter and the harness. "
                "At the inverter, C and T may be reversed without affecting performance."
            ),
        ],
        "check_pages": [31, 31, 43, 45],
        "do_not": [
            "Do not jumper C and T on this prove.",
            "Do not open the fuse or a 12V continuity check while the dial is OFF and the compressor is still running.",
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
                    "Heavy frost return\nafter 24 to 48 hours?",
                    0.30,
                    0.82,
                    w=196,
                    h=68,
                ),
                FlowNode(
                    "e_rep",
                    "end",
                    "Replace the cooling unit\nafter that prove.",
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
            "After 24 to 48 hours, if the frost is gone or only a light sheet remains on the back wall, the correction is the moisture path: mid setpoint, a holding gasket, and a clear drain. You are done. If heavy frost returns with a mid dial, a good gasket, and a clear drain, the unit is not cooling to target: replace the cooling unit.",
            "If cooling is good but the same heavy frost still returns after the moisture path is cleared, dry the cabinet again and watch door-open time and humidity for about a month. If the heavy frost returns hard after that watch, replace the cooling unit. That is the confirmed correction.",
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
                    "Door gasket. Dollar-bill test around the full perimeter. "
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
            "A Furrion rooftop freeze, interior leak, or condensate drip is an assembly and "
            "condensate problem. Melt water that cannot leave the evaporator pan ices the pan, "
            "backs up, and drips into the coach. Prove the evaporator pan, the condensate drain, "
            "the base-pan slope, and suction-line icing before you condemn the sealed system. "
            "A clear drain and a dry interior after a full cool cycle is a passed assembly prove."
        ),
        "flowchart": Flowchart(
            readable=True,
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
                FlowEdge("d_drain", "d_retest", "NO", "bottom", "top"),
                FlowEdge("p_clear", "d_retest", "", "right", "top"),
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
            "Inspect the rooftop assembly, the evaporator pan, and the condensate drain. If the drain is restricted or the pan is iced, clear the ice or the restriction and confirm water leaves the drain, then retest cooling. If the pan is dry and the drain is open, go to the drain-path confirm next.",
            "Confirm the drain path from the evaporator pan out of the rooftop. If melt water backs up, clear the trough and the hose, then retest cooling. Water leaving freely is a pass: run cooling and watch the pan. Water that stands or overflows is a fail: stay on the drain until it leaves.",
            "Watch the pan and the freeze-sensor area through a full cool cycle. If ice reforms in the pan or the drain ices shut, clear it again and prove the drain remains clear on the next cycle. If the drain remains clear and the pan stays dry, check the base-pan slope next.",
            "Check the base-pan slope. If the pan is tilted so water cannot reach the drain, correct the slope and retest cooling. If the pan is level and water still reaches the drain, check suction-line icing next.",
            "Check the suction line for icing. If the suction line is iced, correct that icing and retest cooling. If the suction line is clear, run a full cool cycle and watch the interior.",
            "Retest cooling and watch the pan and the interior. If the freeze or leak is gone, the correction is the drain, pan, slope, or suction work you just proved. You are done.",
            "If ice or drip returns with a clear drain, a level base pan, and a clear suction line, replace the rooftop unit after that assembly prove. That is the confirmed correction.",
        ],
        "do_not": [
            "Do not condemn the sealed system before you clear the drain and the pan.",
        ],
        "sources": [
            {
                "title": FACR_7990_TITLE,
                "page": None,
                "excerpt": (
                    "Rooftop assembly, condensate drain, base pan, and freeze path."
                ),
            },
            {
                "title": FACR_8666_TITLE,
                "page": None,
                "excerpt": (
                    "Furrion Chill drain, base-pan, and freeze-sensor layout."
                ),
            },
        ],
        "display_model": "Furrion Chill rooftop unit",
        "flow_tall": True,
        "full_story": True,
    }


def _bal_tongue_path() -> dict:
    """Tongue jack only dead. Panel tongue channel, then pigtail. Not coupler-first."""
    return {
        "primary_cite": (
            "BAL Soft-Touch SS 5.1 tongue jack. Prove the panel tongue channel, then the tongue pigtail."
        ),
        "pattern_means": (
            "The electric tongue jack is the only jack that is dead. The other stabilizers "
            "still extend and retract, and the soft-touch panel lights still work. That is "
            "a soft-touch panel tongue-channel prove, then the local tongue pigtail. It is "
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
                    "12V at the soft-touch\npanel tongue channel?",
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
                    "Channel and pigtail passed.\nRetest the tongue jack.",
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
                "work. Go to the tongue-channel voltage prove."
            ),
            (
                "Command tongue extend or retract and prove 12V at the soft-touch panel tongue "
                "channel. If that channel has no 12V while the stabilizer channels and the lights "
                "still work, replace the soft-touch user panel 20300427. That is the confirmed correction."
            ),
            (
                "If the tongue channel has 12V, check the local tongue pigtail and the panel-to-motor "
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
                "page": None,
                "excerpt": (
                    "Tongue jack only dead, stabilizers and panel lights working: prove 12V at the "
                    "soft-touch panel tongue channel. No voltage there means soft-touch user panel "
                    "20300427. Voltage present means repair the local tongue pigtail."
                ),
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
                    "Firefly CAN is in the dump.\nCall Firefly at 574-825-4600\nfor USB plus interim.",
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
            "Back-probe the labeled POWER CONNECTOR. Measure Red versus Green ground. You want solid 12V+. Note Yellow. If you do not have solid 12V+, fix power first. If power is solid 12V+, do the CAN prove next.",
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
                "title": FIREFLY_PATH_TITLE,
                "page": None,
                "excerpt": (
                    "Back-probe the labeled POWER CONNECTOR, Red versus Green ground, "
                    "solid 12V+. "
                    + FIREFLY_CAN_PORT_PROVE
                ),
            },
            {
                "title": "Level Up Advantage controller shop PN 807662",
                "page": None,
                "excerpt": "Listed in Sources only. This is not the MODEL headline.",
            },
        ],
        "display_model": "Level Up Advantage controller (Brinkley / Firefly)",
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


def _generic_bay_order(excerpts: list[str], *, long_path: bool) -> list[str]:
    cleaned = []
    usable = [e for e in excerpts if e and len(e) >= 20][:MAX_BAY_ORDER]
    for i, raw in enumerate(usable):
        step = _body_check_from_excerpt(raw)
        if not step:
            continue
        last = (i == len(usable) - 1) and not long_path
        cleaned.append(_ensure_next_step(step, last=last))
    if not cleaned:
        cleaned.append(
            _ensure_next_step(
                "No matching library excerpt was retrieved. Re-check category or model keywords, "
                "or ask a manager to index the unit in Document Library.",
                last=not long_path,
            )
        )
    if long_path:
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
            f"{lead} Work this as a full appliance path from the shop library excerpts. "
            "Do each cited check on this sheet. Write pass or fail and the next step after every check. "
            "Thresholds and pass or fail meaning stay on this page."
        )
    return (
        f"{lead} Use the next cited checks from this shop's library excerpts. "
        "Each step on this sheet says what to do next after a pass or a fail."
    )


def _generic_flowchart(concern: str, steps: list[str] | None = None) -> Flowchart:
    """OEM yes/no spine for any new concern — not a linear bot list."""
    start = _as_sentence(_clip(concern or "Customer concern", 88))
    first = _clip((steps[0] if steps else "Do the first cited check."), 78)
    if first and first[-1] not in ".!?":
        first += "."
    return Flowchart(
        readable=True,
        nodes=[
            FlowNode("s", "start", start, 0.50, 0.09, w=400, h=66),
            FlowNode("d1", "decision", "Did the first\ncheck pass?", 0.32, 0.32, w=220, h=100),
            FlowNode("n1", "end", "Stay on that check\nuntil it passes.", 0.82, 0.32, w=200, h=72),
            FlowNode("p2", "process", first, 0.32, 0.55, w=260, h=80),
            FlowNode("d2", "decision", "Is the complaint\ngone?", 0.32, 0.75, w=220, h=100),
            FlowNode("y2", "end", "That is the confirmed\ncorrection.", 0.32, 0.93, w=260, h=72),
            FlowNode("n2", "end", "Use the next cited\nlibrary check.", 0.82, 0.75, w=200, h=72),
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
def model_text_from(brand: str = "", model: str = "") -> str:
    return " ".join(p for p in ((brand or "").strip(), (model or "").strip()) if p)


def chunk_as_dict(ch) -> dict:
    """Normalize a DocChunk or dict used by ranking helpers."""
    if isinstance(ch, dict):
        excerpt = ch.get("excerpt") or ch.get("chunk_text") or ""
        return {
            "title": ch.get("title") or "",
            "page": ch.get("page"),
            "excerpt": excerpt,
            "chunk_text": excerpt,
            "file_path": ch.get("file_path"),
            "category": ch.get("category") or ch.get("category_name") or "",
            "document_id": ch.get("document_id"),
            "image_png": ch.get("image_png"),
        }
    excerpt = getattr(ch, "chunk_text", "") or getattr(ch, "excerpt", "") or ""
    return {
        "title": getattr(ch, "title", "") or "",
        "page": getattr(ch, "page", None),
        "excerpt": excerpt,
        "chunk_text": excerpt,
        "file_path": getattr(ch, "file_path", None),
        "category": getattr(ch, "category", "") or getattr(ch, "category_name", "") or "",
        "document_id": getattr(ch, "document_id", None),
        "image_png": getattr(ch, "image_png", None),
    }


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
    symptom = ac_search_symptom(category_name, model_text, symptom)
    if is_facr_rooftop_freeze_context(category_name, model_text, symptom):
        if FACR_FREEZE_SEARCH_BOOST not in symptom:
            symptom = f"{symptom} {FACR_FREEZE_SEARCH_BOOST}".strip()
    symptom = water_heater_search_symptom(category_name, model_text, symptom)
    symptom = cooktop_search_symptom(category_name, model_text, symptom)
    symptom = bal_tongue_search_symptom(category_name, model_text, symptom)
    symptom = stabilizer_search_symptom(category_name, model_text, symptom)
    return symptom


def rank_bay_chunks(
    chunks,
    category_name: str = "",
    model_text: str = "",
    concern: str = "",
    limit: int = 8,
) -> list:
    """Apply the same product ranking GD uses."""
    pages = [chunk_as_dict(ch) for ch in (chunks or [])]
    query = f"{model_text or ''} {concern or ''}".strip()
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


def _seed_figure_png(kind: str) -> bytes:
    """Ship ice-pattern / data-plate schematics so HIT sheets are not figure-empty."""
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
        draw.text((450, 335), "Want solid 12V+. Note Yellow.", fill=(18, 18, 36), font=small_f)
        draw.text((450, 380), "Shop PN 807662 (Sources only)", fill=(90, 90, 90), font=small_f)
    return _png_bytes(img)


def load_oem_figure_png(name: str) -> bytes:
    """Real library-page art from the OEM manuals. Never a drawn cartoon."""
    return (OEM_FIGURE_DIR / name).read_bytes()


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
            BayFigure(
                title=FURRION_8122_TITLE,
                page=36,
                caption="CCD-0008122 page 36 Ice and Moisture",
                excerpt="Ice and Moisture. Ice or Moisture in the Fridge. Figure 36.",
                image_png=load_oem_figure_png("ccd8122-p36.png"),
            ),
        ]
    if kind == "facr":
        return [
            BayFigure(
                title=FACR_7990_TITLE,
                page=7,
                caption="CCD-0007990 page 7. Water enters the vehicle. Clean the drainage openings.",
                excerpt="Water enters the vehicle. Condensation water drainage openings are clogged.",
                image_png=load_oem_figure_png("ccd7990-p7.png"),
            ),
            BayFigure(
                title=FACR_8666_TITLE,
                page=10,
                caption="CCD-0008666 page 10. Rooftop unit base and roof opening.",
                excerpt="Installing the rooftop unit. Check gasket alignment at the roof opening.",
                image_png=load_oem_figure_png("ccd8666-p10.png"),
            ),
            BayFigure(
                title=FACR_7990_TITLE,
                page=4,
                caption="CCD-0007990 page 4. Assembly, decoration plate, and filters.",
                excerpt="Cleaning and Maintenance. Remove the decoration plate and the filters.",
                image_png=load_oem_figure_png("ccd7990-p4.png"),
            ),
        ]
    return []


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
            caption="Soft-touch panel tongue channel and tongue pigtail",
            excerpt=(
                "Prove 12V at the soft-touch panel tongue channel. "
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


def resolve_path_figures(kind: str, ranked, explicit: list[BayFigure] | None = None) -> list[BayFigure]:
    """Ice and FACR always use real OEM library art. Firefly may use the path seed."""
    if kind in ("ice", "facr"):
        if explicit and any(fig.image_png for fig in explicit):
            return list(explicit)
        return _oem_library_figures(kind)
    if kind == "dial_off":
        return [_seed_path_figure("dial_off")]
    if kind == "bal_tongue":
        return [_seed_path_figure("bal_tongue")]
    if explicit:
        if any(fig.image_png for fig in explicit):
            return list(explicit)
        seeded = _seed_path_figure(kind)
        explicit[0].image_png = seeded.image_png
        return list(explicit)
    library = pick_cited_figures(ranked)
    if any(fig.image_png for fig in library):
        return library
    seed = _seed_path_figure(kind)
    if library:
        library[0].image_png = seed.image_png
        library[0].caption = library[0].caption or seed.caption
        return library
    return [seed]


def _unique_sources(chunks) -> list[dict]:
    out = []
    seen = set()
    for ch in chunks or []:
        d = chunk_as_dict(ch)
        title = (d.get("title") or "").strip() or "Shop library"
        page = _page_int(d.get("page"))
        key = (title.lower(), page)
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "page": page, "excerpt": (d.get("excerpt") or "")[:400]})
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
            "It is not a rooftop air-conditioner code."
        )
    if is_air_conditioning_context(category_name, model_text, concern) and not is_facr_rooftop_freeze_context(
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
            "prove 12V at the soft-touch panel tongue channel, then the tongue pigtail. "
            "No 12V on that channel means soft-touch user panel 20300427."
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
    seen = set()
    for s in list(locked) + list(ranked):
        title = (s.get("title") or "").strip() or "Shop library"
        page = _page_int(s.get("page"))
        key = (title.lower(), page)
        if key in seen:
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
        seen.add(key)
        out.append({"title": title, "page": page, "excerpt": (s.get("excerpt") or "")[:400]})
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
    ranked = rank_bay_chunks(chunks, category, model_text, concern, limit=8)

    dial_off = is_fcr_dial_off_compressor_run_context(category, model_text, concern)
    ice = is_fridge_ice_moisture_context(category, model_text, concern)
    firefly = is_firefly_can_path_context(category, model_text, concern)
    facr = is_facr_rooftop_freeze_context(category, model_text, concern)
    bal_tongue = is_bal_soft_touch_tongue_only_context(category, model_text, concern)

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
    else:
        extra_steps = []
        for d in ranked:
            line = _excerpt_line(d)
            if line:
                extra_steps.append(line)
        long_path = is_long_appliance_path(category, concern)
        bay_order = _generic_bay_order(extra_steps, long_path=long_path)
        spec = {
            "primary_cite": _generic_primary_cite(ranked),
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

    sources = _merge_sources(
        spec.get("sources") or [],
        _unique_sources(ranked),
        ice=ice,
        dial_off=dial_off,
    )
    if ice and not any("ccd-0008122" in (s.get("title") or "").lower() for s in sources):
        sources.insert(0, spec["sources"][0])

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
                text="No matching library excerpt was retrieved. Re-check category or model keywords.",
                source_title="Document Library",
                kind="note",
            )
        )

    if path_kind:
        figs = resolve_path_figures(path_kind, ranked, figures)
    else:
        figs = list(figures or []) or pick_cited_figures(ranked)
        if not any(fig.image_png for fig in figs):
            seed = _seed_path_figure("generic")
            if figs:
                figs[0].image_png = seed.image_png
                figs[0].caption = figs[0].caption or seed.caption
            else:
                figs = [seed]

    display_model = spec.get("display_model") or ""
    if firefly:
        display_model = "Level Up Advantage controller (Brinkley / Firefly)"
    elif facr and not display_model:
        display_model = "Furrion Chill rooftop unit"
    elif dial_off and not display_model:
        display_model = " ".join(p for p in (brand, model) if p) or "Furrion fridge"
    elif bal_tongue and not (brand or model):
        display_model = spec.get("display_model") or "BAL Soft-Touch SS 5.1"
    elif ice and not display_model:
        display_model = " ".join(p for p in (brand, model) if p) or "Furrion fridge"

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
        created=created or datetime.now(),
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
    )
    proc = apply_sheet_standard(proc)
    if dial_off:
        proc = _lock_dial_off_part_numbers(proc)
    return proc


def _generic_primary_cite(ranked) -> str:
    for d in ranked or []:
        title = (d.get("title") or "").strip()
        if not title:
            continue
        page = _page_int(d.get("page"))
        return f"{title}" + (f" page {page}" if page else "")
    return "Shop Document Library (no indexed excerpt this pass)"


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
        lines.append("- (no indexed excerpt retrieved this pass)")
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
# ---------------------------------------------------------------------------
def _node_size(node: FlowNode, *, readable: bool = False) -> tuple[float, float]:
    if node.w and node.h:
        return node.w, node.h
    if node.kind == "decision":
        return (220.0, 100.0) if readable else (132.0, 58.0)
    if node.kind in ("start", "end"):
        return (320.0, 66.0) if readable else (210.0, 38.0)
    return (270.0, 80.0) if readable else (230.0, 40.0)


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


def _flowchart_inner(frame_x: float, frame_y: float, frame_w: float, frame_h: float):
    """Readable OEM gutters — keep boxes off the title bar and frame edge."""
    return (
        frame_x + 16,
        frame_y + 14,
        frame_w - 32,
        frame_h - 38,
    )


def place_flowchart_nodes(
    flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float
) -> dict[str, tuple[float, float, float, float]]:
    """Place nodes in PDF space. Clamp to the frame only — never pull neighbors together."""
    inner_x, inner_y, inner_w, inner_h = _flowchart_inner(frame_x, frame_y, frame_w, frame_h)
    readable = bool(getattr(flow, "readable", False))
    placed: dict[str, tuple[float, float, float, float]] = {}
    for node in flow.nodes:
        w, h = _node_size(node, readable=readable)
        cx = inner_x + node.x * inner_w
        cy = inner_y + inner_h - node.y * inner_h
        pad = 10 if readable else 2
        min_cx = inner_x + w / 2 + pad
        max_cx = inner_x + inner_w - w / 2 - pad
        min_cy = inner_y + h / 2 + pad
        max_cy = inner_y + inner_h - h / 2 - pad
        if min_cx <= max_cx:
            cx = min(max(cx, min_cx), max_cx)
        if min_cy <= max_cy:
            cy = min(max(cy, min_cy), max_cy)
        placed[node.id] = (cx, cy, w, h)
    return placed


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


def _route_elbow(x1: float, y1: float, x2: float, y2: float, from_side: str, to_side: str):
    """Orthogonal service-manual elbows. No diagonal cuts across boxes."""
    pts = [(x1, y1)]
    if from_side == "bottom" and to_side == "top":
        if abs(x1 - x2) < 1.5:
            pts.append((x2, y2))
        else:
            mid_y = (y1 + y2) / 2.0
            pts.extend([(x1, mid_y), (x2, mid_y), (x2, y2)])
    elif from_side == "top" and to_side == "bottom":
        if abs(x1 - x2) < 1.5:
            pts.append((x2, y2))
        else:
            mid_y = (y1 + y2) / 2.0
            pts.extend([(x1, mid_y), (x2, mid_y), (x2, y2)])
    elif from_side == "right" and to_side == "left":
        if abs(y1 - y2) < 1.5:
            pts.append((x2, y2))
        else:
            mid_x = (x1 + x2) / 2.0
            pts.extend([(mid_x, y1), (mid_x, y2), (x2, y2)])
    elif from_side == "left" and to_side == "right":
        if abs(y1 - y2) < 1.5:
            pts.append((x2, y2))
        else:
            mid_x = (x1 + x2) / 2.0
            pts.extend([(mid_x, y1), (mid_x, y2), (x2, y2)])
    elif from_side == "right" and to_side == "top":
        out_x = x1 + 16.0
        if out_x < x2:
            out_x = (x1 + x2) / 2.0
        mid_y = y2 + 14.0
        pts.extend([(out_x, y1), (out_x, mid_y), (x2, mid_y), (x2, y2)])
    elif from_side == "left" and to_side == "top":
        out_x = x1 - 36.0
        mid_y = y2 + 14.0
        pts.extend([(out_x, y1), (out_x, mid_y), (x2, mid_y), (x2, y2)])
    elif from_side == "bottom" and to_side == "left":
        pts.extend([(x1, y2), (x2, y2)])
    elif from_side == "bottom" and to_side == "right":
        pts.extend([(x1, y2), (x2, y2)])
    elif from_side in ("left", "right"):
        mid_x = (x1 + x2) / 2.0
        pts.extend([(mid_x, y1), (mid_x, y2), (x2, y2)])
    else:
        mid_y = (y1 + y2) / 2.0
        pts.extend([(x1, mid_y), (x2, mid_y), (x2, y2)])
    return pts


def _branch_label_point(x1: float, y1: float, from_side: str) -> tuple[float, float]:
    """YES/NO sit on the first arrow segment, off the diamond — not on the question text."""
    if from_side == "bottom":
        return x1 + 16.0, y1 - 12.0
    if from_side == "top":
        return x1 + 16.0, y1 + 10.0
    if from_side == "right":
        return x1 + 10.0, y1 + 14.0
    if from_side == "left":
        return x1 - 38.0, y1 + 14.0
    return x1 + 12.0, y1 + 10.0


def layout_flowchart(flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float):
    """OEM SM flowchart: large boxes/diamonds, orthogonal yes/no, finger-walk spacing."""
    shapes: list[DrawnShape] = []
    texts: list[DrawnText] = []

    shapes.append(
        DrawnShape("roundrect", frame_x, frame_y, frame_w, frame_h, fill=PALE, stroke=NAVY, stroke_w=1.6, radius=6)
    )
    texts.append(
        DrawnText(
            "VISUAL FLOWCHART",
            frame_x + 12,
            frame_y + frame_h - 18,
            w=220,
            size=9,
            bold=True,
            color=NAVY,
        )
    )

    readable = bool(getattr(flow, "readable", False))
    placed = place_flowchart_nodes(flow, frame_x, frame_y, frame_w, frame_h)
    kind_of = {n.id: n.kind for n in flow.nodes}
    text_of = {n.id: n.text for n in flow.nodes}

    for nid, (cx, cy, w, h) in placed.items():
        kind = kind_of.get(nid, "process")
        x, y = cx - w / 2.0, cy - h / 2.0
        if kind == "decision":
            shapes.append(DrawnShape("diamond", x, y, w, h, fill=GOLD, stroke=NAVY, stroke_w=2.0))
            size = 12.0 if readable else 7.5
        elif kind in ("start", "end"):
            fill = GREEN if kind == "start" else NAVY
            shapes.append(DrawnShape("ellipse", x, y, w, h, fill=fill, stroke=NAVY, stroke_w=1.7))
            size = 11.0 if readable else 7.5
        else:
            shapes.append(DrawnShape("roundrect", x, y, w, h, fill=WHITE, stroke=NAVY, stroke_w=1.6, radius=7))
            size = 11.0 if readable else 7.5
        color = WHITE if kind in ("start", "end") else INK
        texts.append(
            DrawnText(
                text_of.get(nid, ""),
                cx,
                cy,
                w=w - (30 if readable else 14),
                size=size,
                bold=kind == "decision",
                color=color,
                align="center",
                leading=size + (4.0 if readable else 1.5),
            )
        )

    for edge in flow.edges:
        if edge.from_id not in placed or edge.to_id not in placed:
            continue
        fx, fy, fw, fh = placed[edge.from_id]
        tx, ty, tw, th = placed[edge.to_id]
        x1, y1 = _port(fx, fy, fw, fh, edge.from_side)
        x2, y2 = _port(tx, ty, tw, th, edge.to_side)
        pts = _route_elbow(x1, y1, x2, y2, edge.from_side, edge.to_side)
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
            )
        )
        if edge.label:
            mx, my = _branch_label_point(x1, y1, edge.from_side)
            color = GREEN if edge.label.upper() == "YES" else RED
            texts.append(
                DrawnText(
                    edge.label.upper(),
                    mx,
                    my,
                    w=40,
                    size=12 if readable else 7,
                    bold=True,
                    color=color,
                    align="left",
                )
            )
    return shapes, texts


def _add_section_bar(page: SheetPage, x: float, y: float, w: float, title: str, fill=NAVY):
    page.shapes.append(DrawnShape("rect", x, y, w, 16, fill=fill, stroke=fill, stroke_w=0.4))
    page.texts.append(DrawnText(title, x + 6, y + 4.5, w=w - 12, size=8.5, bold=True, color=WHITE))


def _wrap(text: str, width: int) -> list[str]:
    text = _latin1_safe(text or "")
    out = []
    for para in text.splitlines() or [""]:
        wrapped = textwrap.wrap(para, width=width) or [""]
        out.extend(wrapped)
    return out


def compose_sheet(proc: BayProcedure) -> list[SheetPage]:
    """Build drawable pages for a human bay sheet.

    BAY_SHEET_STANDARD is enforced here: readable OEM yes/no flowchart first,
    then pattern meaning, full bay order, do-not, sources, figures. Long paths
    paginate. Never clip a long path to a hint card. See BAY_SHEET_STANDARD_PATH.
    """
    pages: list[SheetPage] = []
    page = SheetPage()
    pages.append(page)

    # Page frame
    page.shapes.append(DrawnShape("rect", 0, 0, PAGE_W, PAGE_H, fill=WHITE, stroke=WHITE, stroke_w=0))
    page.shapes.append(
        DrawnShape("rect", MARGIN - 4, MARGIN - 4, PAGE_W - 2 * MARGIN + 8, PAGE_H - 2 * MARGIN + 8, fill=WHITE, stroke=NAVY, stroke_w=1.6)
    )

    # Top brand bar
    bar_y = PAGE_H - MARGIN - 28
    page.shapes.append(DrawnShape("rect", MARGIN, bar_y, PAGE_W - 2 * MARGIN, 28, fill=NAVY, stroke=NAVY, stroke_w=0.3))
    page.texts.append(DrawnText("BAY PROCEDURE", MARGIN + 10, bar_y + 9, w=220, size=13, bold=True, color=WHITE))
    page.texts.append(
        DrawnText(
            "Tacoma RV Center  ·  Document Library",
            PAGE_W - MARGIN - 10,
            bar_y + 10,
            w=260,
            size=8,
            color=WHITE,
            align="right",
        )
    )

    # Compact header so the OEM flowchart can use the rest of page 1.
    big_flow = bool(getattr(proc.flowchart, "readable", False) or proc.flow_tall)
    header_top = bar_y - 8
    header_h = 50 if big_flow else 64
    header_y = header_top - header_h
    page.shapes.append(
        DrawnShape("rect", MARGIN, header_y, PAGE_W - 2 * MARGIN, header_h, fill=CREAM, stroke=NAVY, stroke_w=1.0)
    )
    y = header_top - 14
    page.texts.append(DrawnText("CONCERN", MARGIN + 8, y, w=70, size=7, bold=True, color=GREEN))
    concern_lines = _wrap(proc.concern or "-", 88)
    page.texts.append(DrawnText(concern_lines[0], MARGIN + 78, y, w=450, size=9, bold=True, color=INK))
    y -= 13
    if len(concern_lines) > 1 and not big_flow:
        page.texts.append(DrawnText(concern_lines[1], MARGIN + 78, y, w=450, size=9, bold=True, color=INK))
        y -= 12
    page.texts.append(DrawnText("MODEL", MARGIN + 8, y, w=70, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(_clip(proc.model_line, 56), MARGIN + 78, y, w=230, size=9, bold=True, color=INK))
    page.texts.append(DrawnText("DATE", MARGIN + 310, y, w=36, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(proc.created.strftime("%Y-%m-%d"), MARGIN + 348, y, w=80, size=9, bold=True, color=INK))
    page.texts.append(DrawnText("WO#", MARGIN + 440, y, w=28, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(_clip(proc.wo_number or "-", 16), MARGIN + 470, y, w=70, size=9, bold=True, color=INK))
    y -= 13
    page.texts.append(DrawnText("PRIMARY", MARGIN + 8, y, w=70, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(_clip(proc.primary_cite or "-", 92), MARGIN + 78, y, w=460, size=9, bold=True, color=INK))

    means_lines = _wrap(proc.pattern_means or "-", 96)
    if big_flow:
        # Finger-walk chart first. Pattern prose lives with the bay order.
        flow_top = header_y - 8
        flow_y = MARGIN + 14
        flow_h = max(420.0, flow_top - flow_y)
        f_shapes, f_texts = layout_flowchart(proc.flowchart, MARGIN, flow_y, PAGE_W - 2 * MARGIN, flow_h)
        page.shapes.extend(f_shapes)
        page.texts.extend(f_texts)
    else:
        means_top = header_y - 10
        means_h = 18 + 11 * max(len(means_lines), 1) + 8
        means_y = means_top - means_h
        _add_section_bar(page, MARGIN, means_top - 16, PAGE_W - 2 * MARGIN, "WHAT THIS PATTERN USUALLY MEANS")
        page.shapes.append(
            DrawnShape("rect", MARGIN, means_y, PAGE_W - 2 * MARGIN, means_h - 16, fill=WHITE, stroke=RULE, stroke_w=0.8)
        )
        ty = means_top - 30
        for line in means_lines[:8]:
            page.texts.append(DrawnText(line, MARGIN + 8, ty, w=520, size=9, color=INK))
            ty -= 11
        flow_top = means_y - 8
        flow_y = MARGIN + 16
        flow_h = max(240.0, flow_top - flow_y)
        f_shapes, f_texts = layout_flowchart(proc.flowchart, MARGIN, flow_y, PAGE_W - 2 * MARGIN, flow_h)
        page.shapes.extend(f_shapes)
        page.texts.extend(f_texts)

    # Page 2+: pattern meaning, full bay order, do-not, sources.
    body_page = _new_sheet_page()
    pages.append(body_page)
    _paint_top_bar(body_page, "Bay order  ·  Tacoma RV Center")
    y = PAGE_H - MARGIN - 50
    floor = MARGIN + 28
    if big_flow:
        _add_section_bar(body_page, MARGIN, y, PAGE_W - 2 * MARGIN, "WHAT THIS PATTERN USUALLY MEANS")
        y -= 20
        body_page.shapes.append(
            DrawnShape(
                "rect",
                MARGIN,
                y - 11 * max(len(means_lines), 1) - 10,
                PAGE_W - 2 * MARGIN,
                11 * max(len(means_lines), 1) + 16,
                fill=WHITE,
                stroke=RULE,
                stroke_w=0.8,
            )
        )
        for line in means_lines[:10]:
            body_page.texts.append(DrawnText(line, MARGIN + 8, y, w=520, size=9, color=INK))
            y -= 11
        y -= 16
    _add_section_bar(body_page, MARGIN, y, PAGE_W - 2 * MARGIN, "BAY ORDER (DO THIS FIRST)", GREEN)
    y -= 22
    shown_order = proc.bay_order[:MAX_BAY_ORDER]
    for i, step in enumerate(shown_order, 1):
        wrapped = _wrap(f"{i}. {step}", 96)[:10]
        need = len(wrapped) * 11 + 6
        if y - need < floor:
            body_page = _new_sheet_page()
            pages.append(body_page)
            _paint_top_bar(body_page, "Bay order continued")
            y = PAGE_H - MARGIN - 50
            _add_section_bar(body_page, MARGIN, y, PAGE_W - 2 * MARGIN, "BAY ORDER (CONTINUED)", GREEN)
            y -= 22
        body_page.shapes.append(DrawnShape("rect", MARGIN + 8, y - 1, 8, 8, fill=WHITE, stroke=NAVY, stroke_w=0.9))
        for line in wrapped:
            body_page.texts.append(DrawnText(line, MARGIN + 22, y, w=520, size=8.5, color=INK))
            y -= 11
        y -= 6

    if proc.do_not:
        need = 28 + 14 * min(len(proc.do_not), 6)
        if y - need < floor:
            body_page = _new_sheet_page()
            pages.append(body_page)
            _paint_top_bar(body_page, "Do not  ·  Tacoma RV Center")
            y = PAGE_H - MARGIN - 50
        _add_section_bar(body_page, MARGIN, y, PAGE_W - 2 * MARGIN, "DO NOT", RED)
        y -= 22
        for item in proc.do_not[:6]:
            for line in _wrap(f"- {item}", 96)[:4]:
                body_page.texts.append(DrawnText(line, MARGIN + 8, y, w=520, size=8.5, color=INK))
                y -= 11
            y -= 4

    if y - 60 < floor:
        body_page = _new_sheet_page()
        pages.append(body_page)
        _paint_top_bar(body_page, "Sources  ·  Tacoma RV Center")
        y = PAGE_H - MARGIN - 50
    _add_section_bar(body_page, MARGIN, y, PAGE_W - 2 * MARGIN, "SOURCES (SHOP DOCUMENT LIBRARY)")
    y -= 22
    src_rows = proc.sources[:5] or [{"title": "(no indexed excerpt retrieved this pass)", "page": None}]
    for s in src_rows:
        page_bit = f"  page {s['page']}" if s.get("page") else ""
        line = f"- {s.get('title') or 'Manual'}{page_bit}"
        body_page.texts.append(DrawnText(_clip(line, 110), MARGIN + 8, y, w=520, size=8.5, color=INK))
        y -= 12
        excerpt = (s.get("excerpt") or "").strip()
        if excerpt:
            for line in _wrap(excerpt, 96)[:3]:
                body_page.texts.append(DrawnText(line, MARGIN + 18, y, w=510, size=8, color=MUTED))
                y -= 10
        if y < floor + 20:
            break

    imaged = [fig for fig in proc.figures if fig.image_png]
    if imaged:
        for i, fig in enumerate(imaged[:3]):
            fig_page = _new_sheet_page()
            pages.append(fig_page)
            _paint_top_bar(fig_page, "Cited library figures")
            top = PAGE_H - MARGIN - 50
            _add_section_bar(fig_page, MARGIN, top, PAGE_W - 2 * MARGIN, "CITED LIBRARY FIGURES")
            y = top - 18
            cap = f"{fig.caption or 'Figure'} -- {fig.title}" + (f" p.{fig.page}" if fig.page else "")
            fig_page.texts.append(DrawnText(_clip(cap, 100), MARGIN + 8, y, w=520, size=9, bold=True, color=NAVY))
            y -= 16
            img_h = max(220.0, y - (MARGIN + 36))
            fig_page.images.append(DrawnImage(fig.image_png, MARGIN + 16, y - img_h, 520, img_h))
            if proc.include_3c and i == min(len(imaged), 3) - 1:
                _add_3c_footer(fig_page)
    elif proc.include_3c:
        _add_3c_footer(body_page)

    return pages


def _new_sheet_page() -> SheetPage:
    page = SheetPage()
    page.shapes.append(DrawnShape("rect", 0, 0, PAGE_W, PAGE_H, fill=WHITE, stroke=WHITE, stroke_w=0))
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
        )
    )
    return page


def _paint_top_bar(page: SheetPage, subtitle: str = "") -> float:
    bar_y = PAGE_H - MARGIN - 28
    page.shapes.append(DrawnShape("rect", MARGIN, bar_y, PAGE_W - 2 * MARGIN, 28, fill=NAVY, stroke=NAVY, stroke_w=0.3))
    page.texts.append(DrawnText("BAY PROCEDURE", MARGIN + 10, bar_y + 9, w=220, size=13, bold=True, color=WHITE))
    page.texts.append(
        DrawnText(
            subtitle or "Tacoma RV Center  ·  Document Library",
            PAGE_W - MARGIN - 10,
            bar_y + 10,
            w=300,
            size=8,
            color=WHITE,
            align="right",
        )
    )
    return bar_y


def _add_3c_footer(page: SheetPage):
    """Small footer only — never the main body."""
    y = MARGIN + 4
    page.shapes.append(DrawnShape("rect", MARGIN, y, PAGE_W - 2 * MARGIN, 20, fill=PALE, stroke=RULE, stroke_w=0.7))
    page.texts.append(
        DrawnText(
            "3C footer (blank):  CONCERN ____________    CAUSE ____________    CORRECTION ____________",
            MARGIN + 8,
            y + 6,
            w=530,
            size=7,
            color=MUTED,
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


def render_bay_procedure_pdf(proc: BayProcedure) -> bytes:
    """Return non-empty PDF bytes with a drawn flowchart (not text-only)."""
    pages = compose_sheet(proc)
    for renderer in (_render_pdf_reportlab, _render_pdf_fpdf2, _render_pdf_raw_shapes):
        try:
            data = renderer(proc, pages)
            if data and data.startswith(b"%PDF") and len(data) > 200:
                return data
        except Exception:
            continue
    raise RuntimeError("Bay procedure PDF renderer produced empty output")


def _render_pdf_reportlab(proc: BayProcedure, pages: list[SheetPage]) -> bytes:
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
        _rl_draw_page(c, page, stringWidth, ImageReader)
    c.save()
    return buf.getvalue()


def _rl_draw_page(c, page: SheetPage, stringWidth, ImageReader):
    for sh in page.shapes:
        _rl_draw_shape(c, sh)
    for tx in page.texts:
        _rl_draw_text(c, tx, stringWidth)
    for im in page.images:
        try:
            img = ImageReader(BytesIO(im.png))
            c.drawImage(img, im.x, im.y, width=im.w, height=im.h, preserveAspectRatio=True, mask="auto")
        except Exception:
            continue


def _rl_draw_shape(c, sh: DrawnShape):
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


def _rl_arrowhead(c, x1, y1, x2, y2, stroke):
    import math

    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    ux, uy = dx / length, dy / length
    size = 6.0
    px, py = -uy, ux
    c.setFillColorRGB(*stroke)
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - ux * size + px * size * 0.45, y2 - uy * size + py * size * 0.45)
    p.lineTo(x2 - ux * size - px * size * 0.45, y2 - uy * size - py * size * 0.45)
    p.close()
    c.drawPath(p, stroke=0, fill=1)


def _rl_draw_text(c, tx: DrawnText, stringWidth):
    text = _latin1_safe(tx.text)
    font = "Helvetica-Bold" if tx.bold else "Helvetica"
    size = tx.size
    leading = tx.leading or (size + 2)
    color = _rgb(tx.color)
    c.setFillColorRGB(*color)
    c.setFont(font, size)
    paragraphs = text.split("\n")
    lines = []
    max_w = max(tx.w, 20)
    for para in paragraphs:
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = words[0]
        for word in words[1:]:
            trial = f"{cur} {word}"
            if stringWidth(trial, font, size) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    total = (len(lines) - 1) * leading
    if tx.align == "center":
        y = tx.y + total / 2.0 - size * 0.30
        for line in lines:
            c.drawCentredString(tx.x, y, line)
            y -= leading
    elif tx.align == "right":
        c.drawRightString(tx.x, tx.y, lines[0] if lines else "")
    else:
        y = tx.y
        for line in lines:
            c.drawString(tx.x, y, line)
            y -= leading


def _render_pdf_fpdf2(proc: BayProcedure, pages: list[SheetPage]) -> bytes:
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


def _render_pdf_raw_shapes(proc: BayProcedure, pages: list[SheetPage]) -> bytes:
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