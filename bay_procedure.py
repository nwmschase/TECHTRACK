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
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
import re
import textwrap
import zlib

from gd_library_coach import (
    FACR_FREEZE_SEARCH_BOOST,
    FIREFLY_CAN_SEARCH_BOOST,
    ICE_MOISTURE_SEARCH_BOOST,
    ICE_MOISTURE_SHOP_LINE,
    WIRED_COACH_CAN_RE,
    ac_search_symptom,
    cooktop_search_symptom,
    ice_moisture_search_symptom,
    is_air_conditioning_context,
    is_cooktop_pan_on_flameout_context,
    is_facr_rooftop_freeze_context,
    is_fcr_e2_fan_fault_context,
    is_firefly_can_path_context,
    is_fridge_ice_moisture_context,
    is_level_up_advantage_context,
    is_stabilizer_override_pin_context,
    is_water_heater_context,
    level_up_search_symptom,
    page_has_figure_or_terminal_layout,
    rank_chunks_for_ac,
    rank_chunks_for_cooktop_pan_on,
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
FACR_7990_TITLE = "Furrion Rooftop HVAC Troubleshooting & Service Manual CCD-0007990"
FACR_8666_TITLE = "Furrion Chill FACR CCD-0008666"
FIREFLY_PATH_TITLE = "Shop writeup — Level Up Advantage Manual Mode flash-home and Firefly"

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
MAX_BAY_ORDER = 6

# Bay PDF Firefly prove — CAN port labels (GD chat keeps the Leader short prove).
FIREFLY_CAN_PORT_PROVE = (
    "The Level Up controller has two ports labeled CAN. "
    "One is the rubber-boot terminator — leave that one plugged in. "
    "The other is the CAN cable to Firefly / OneControl — unplug that one only. "
    "Then try Manual Mode again."
)
NETWORK_PLUGS_RE = re.compile(r"network\s+plugs", re.I)
POWER_LOOKS_SANE_RE = re.compile(r"power looks sane", re.I)


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

    @property
    def model_line(self) -> str:
        if (self.display_model or "").strip():
            return self.display_model.strip()
        parts = [p for p in (self.brand.strip(), self.model.strip()) if p]
        return " ".join(parts) or "—"


# ---------------------------------------------------------------------------
# Locked human paths (bay sheet copy — not bot flowchart language)
# ---------------------------------------------------------------------------
def _ice_path() -> dict:
    return {
        "primary_cite": "Furrion fridge service manual, Ice and Moisture section (Fig. 36).",
        "pattern_means": (
            "Ice or frost on the rear wall, including a pattern that starts about halfway "
            "down from the top, is an Ice and Moisture problem. A light sheet on the back "
            "wall alone can be normal cycling. This is a moisture, door gasket, drain, and "
            "cooling path."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "Ice or frost is on the rear wall of the fridge.",
                    0.50,
                    0.14,
                    w=300,
                    h=50,
                ),
                FlowNode(
                    "d1",
                    "decision",
                    "Light sheet only,\nor dial at max?",
                    0.50,
                    0.48,
                    w=180,
                    h=80,
                ),
                FlowNode(
                    "a1",
                    "process",
                    "Set the dial to about 4 to 5.\nRun overnight, then check the gasket.",
                    0.18,
                    0.48,
                    w=230,
                    h=62,
                ),
                FlowNode(
                    "d2",
                    "decision",
                    "Does the gasket fail\na dollar-bill test?",
                    0.50,
                    0.84,
                    w=180,
                    h=80,
                ),
                FlowNode(
                    "y2",
                    "end",
                    "Repair or reseat the gasket.\nClear the rear drain and trough.\nRecheck in 24 to 48 hours.",
                    0.18,
                    0.84,
                    w=230,
                    h=66,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Clear the rear drain and trough.\nRecheck in 24 to 48 hours.\nIf heavy frost returns, replace the cooling unit.",
                    0.82,
                    0.84,
                    w=236,
                    h=66,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "a1", "YES", "left", "right"),
                FlowEdge("d1", "d2", "NO", "bottom", "top"),
                FlowEdge("a1", "d2", "", "bottom", "left"),
                FlowEdge("d2", "y2", "YES", "left", "right"),
                FlowEdge("d2", "n2", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            "Look at the frost pattern on the rear wall. If it is only a light sheet, that can be normal cycling: set the dial to mid, about 4 to 5, run overnight, then look again. If frost is heavy or starts halfway down, keep going.",
            "Check the temperature dial. If it is at max, set it to about 4 to 5, let the fridge run overnight, then look at the pattern again. If the dial is already mid, go to the gasket next.",
            "Check the door gasket with a dollar-bill test. If the bill slides out with no drag, reseat or repair the gasket, then clear the rear drain and trough and recheck in 24 to 48 hours. If the gasket holds, clear the rear drain and trough next.",
            "Clear the rear drain and trough so melt water can leave. If the drain is open and the gasket is good, recheck the frost pattern in 24 to 48 hours.",
            "After 24 to 48 hours, if the frost is gone or only a light sheet remains, you are done. If heavy frost returns, replace the cooling unit.",
        ],
        "do_not": [
            "Do not knife the ice off the rear wall.",
            "Do not assume a sealed-system failure from top-half frost alone.",
        ],
        "sources": [
            {
                "title": FURRION_8122_TITLE,
                "page": 36,
                "excerpt": (
                    "Ice and Moisture. Ice or Moisture in the Fridge. "
                    "Figure 36 shows the rear-wall frost pattern."
                ),
            }
        ],
        "display_model": "",
        "flow_tall": True,
    }


def _facr_path() -> dict:
    return {
        "primary_cite": "Furrion rooftop assembly and condensate path. Chill layout book for the pan and drain.",
        "pattern_means": (
            "A Furrion rooftop freeze, interior leak, or condensate drip is an assembly and "
            "condensate problem. Prove the evaporator pan, the drain, the base-pan slope, and "
            "suction-line icing before you condemn the sealed system."
        ),
        "flowchart": Flowchart(
            readable=True,
            nodes=[
                FlowNode(
                    "s",
                    "start",
                    "The rooftop unit is freezing or leaking into the coach.",
                    0.50,
                    0.14,
                    w=310,
                    h=50,
                ),
                FlowNode(
                    "d1",
                    "decision",
                    "Drain restricted\nor pan iced?",
                    0.50,
                    0.48,
                    w=180,
                    h=80,
                ),
                FlowNode(
                    "a1",
                    "process",
                    "Clear the ice or restriction.\nConfirm water leaves the drain.\nThen retest cooling.",
                    0.18,
                    0.48,
                    w=230,
                    h=64,
                ),
                FlowNode(
                    "d2",
                    "decision",
                    "Does freeze or leak\nreturn on retest?",
                    0.50,
                    0.84,
                    w=180,
                    h=80,
                ),
                FlowNode(
                    "y2",
                    "end",
                    "Check base-pan slope and\nsuction-line icing. Correct that,\nthen retest. Replace only after.",
                    0.18,
                    0.84,
                    w=236,
                    h=66,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Drain is clear and cooling holds.\nYou are done.",
                    0.82,
                    0.84,
                    w=230,
                    h=56,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "a1", "YES", "left", "right"),
                FlowEdge("d1", "d2", "NO", "bottom", "top"),
                FlowEdge("a1", "d2", "", "bottom", "left"),
                FlowEdge("d2", "y2", "YES", "left", "right"),
                FlowEdge("d2", "n2", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            "Inspect the rooftop assembly, the evaporator pan, and the condensate drain. If the drain is restricted or the pan is iced, clear the ice or the restriction and confirm water leaves the drain, then retest cooling. If the pan is dry and the drain is open, go to the next check.",
            "Confirm the drain path from the evaporator pan out of the rooftop. If melt water backs up, clear the trough and the hose, then retest cooling. If water leaves freely, run cooling and watch the pan.",
            "Retest cooling and watch the pan and the interior. If the freeze or leak is gone, you are done. If ice or drip returns with a clear drain, check the base-pan slope and suction-line icing next.",
            "If the base pan is tilted or the suction line is iced, correct that and retest. If the pan is level, the suction line is clear, and the freeze or leak still returns, replace the rooftop unit after that assembly prove.",
        ],
        "do_not": [
            "Do not condemn the sealed system before you clear the drain and the pan.",
        ],
        "sources": [
            {
                "title": FACR_7990_TITLE,
                "page": None,
                "excerpt": (
                    "Use this book for the rooftop assembly, the condensate drain, "
                    "the base pan, and the freeze path."
                ),
            },
            {
                "title": FACR_8666_TITLE,
                "page": None,
                "excerpt": (
                    "This is the Furrion Chill model book for drain, base-pan, "
                    "and freeze-sensor layout."
                ),
            },
        ],
        "display_model": "Furrion Chill rooftop unit",
        "flow_tall": True,
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
                    0.14,
                    w=320,
                    h=52,
                ),
                FlowNode("d1", "decision", "Does Auto\nstill work?", 0.50, 0.48, w=172, h=78),
                FlowNode(
                    "p2",
                    "process",
                    "Leave the rubber-boot terminator in.\nUnplug the Firefly CAN cable only.\nThen try Manual Mode again.",
                    0.18,
                    0.48,
                    w=236,
                    h=64,
                ),
                FlowNode(
                    "n1",
                    "end",
                    "This is not the Firefly path.\nStay on Level Up hydraulics.",
                    0.82,
                    0.48,
                    w=220,
                    h=56,
                ),
                FlowNode("d2", "decision", "Does Manual\nMode hold?", 0.50, 0.84, w=172, h=78),
                FlowNode(
                    "y2",
                    "end",
                    "Firefly CAN is in the dump.\nDo not start a Level Up\ncontroller fault path.",
                    0.18,
                    0.84,
                    w=226,
                    h=64,
                ),
                FlowNode(
                    "n2",
                    "end",
                    "Firefly CAN is ruled out.\nDiagnose the Level Up path.",
                    0.82,
                    0.84,
                    w=220,
                    h=56,
                ),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "p2", "YES", "left", "right"),
                FlowEdge("d1", "n1", "NO", "right", "left"),
                FlowEdge("p2", "d2", "", "bottom", "left"),
                FlowEdge("d2", "y2", "YES", "left", "right"),
                FlowEdge("d2", "n2", "NO", "right", "left"),
            ],
        ),
        "bay_order": [
            "Confirm Auto Level still works and clear sticky Low Voltage, Excess Angle, or External Sensor text if it is present. If Auto is dead, this is not the Firefly path — stay on Level Up hydraulics. If Auto works, check the POWER CONNECTOR next.",
            "Back-probe the labeled POWER CONNECTOR. Measure Red versus Green ground. You want solid 12V+. Note Yellow. If you do not have solid 12V+, fix power first. If power is solid 12V+, do the CAN prove next.",
            FIREFLY_CAN_PORT_PROVE,
            "If Manual Mode holds with the Firefly CAN cable unplugged, Firefly / OneControl CAN communication is in the dump. Do not start diagnosing a Level Up controller fault. If Manual Mode still dumps, Firefly / OneControl CAN is ruled out — now diagnose the Level Up path that remains.",
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


def _generic_flowchart(concern: str, steps: list[str]) -> Flowchart:
    short = re.sub(r"\s+", " ", (concern or "Customer concern").strip())
    if len(short) > 56:
        short = short[:53].rstrip() + "..."
    nodes = [FlowNode("s", "start", short, 0.50, 0.12)]
    edges = []
    shown = steps[:3] or ["Use the next cited check from the shop library excerpts."]
    ys = [0.38, 0.62, 0.82] if len(shown) >= 2 else [0.50, 0.78]
    prev = "s"
    for i, step in enumerate(shown):
        nid = f"p{i}"
        y = ys[i] if i < len(ys) else 0.90
        nodes.append(FlowNode(nid, "process" if i < len(shown) - 1 else "end", _clip(step, 90), 0.50, y))
        edges.append(FlowEdge(prev, nid))
        prev = nid
    if len(shown) == 1:
        nodes.append(FlowNode("e", "end", "Use the next cited check.", 0.50, 0.78))
        edges.append(FlowEdge(prev, "e"))
    return Flowchart(nodes=nodes, edges=edges)


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
    return BayFigure(
        title=FIREFLY_PATH_TITLE,
        page=None,
        caption="Level Up Advantage controller — two ports labeled CAN",
        excerpt="Leave the rubber-boot terminator in. Unplug the Firefly CAN cable only.",
        image_png=_seed_figure_png("firefly"),
    )


def resolve_path_figures(kind: str, ranked, explicit: list[BayFigure] | None = None) -> list[BayFigure]:
    """Prefer library page images. If none, ship the path seed figure so the sheet is not empty."""
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
    if is_level_up_advantage_context(category_name, model_text, concern) and not is_firefly_can_path_context(
        category_name, model_text, concern
    ):
        notes.append(
            "The Level Up controller is the Lippert towable hydraulic leveling controller."
        )
    return notes


def _merge_sources(locked: list[dict], ranked: list[dict], ice: bool) -> list[dict]:
    out = []
    seen = set()
    for s in list(locked) + list(ranked):
        title = (s.get("title") or "").strip() or "Shop library"
        page = _page_int(s.get("page"))
        key = (title.lower(), page)
        if key in seen:
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
    """
    concern = (concern or "").strip()
    brand = (brand or "").strip()
    model = (model or "").strip()
    category = (category or "").strip()
    if category in ("(any)", "-"):
        category = ""
    model_text = model_text_from(brand, model)
    ranked = rank_bay_chunks(chunks, category, model_text, concern, limit=8)

    ice = is_fridge_ice_moisture_context(category, model_text, concern)
    firefly = is_firefly_can_path_context(category, model_text, concern)
    facr = is_facr_rooftop_freeze_context(category, model_text, concern)

    path_kind = ""
    if ice:
        spec = _ice_path()
        path_kind = "ice"
    elif facr:
        spec = _facr_path()
        path_kind = "facr"
    elif firefly:
        spec = _firefly_path()
        path_kind = "firefly"
    else:
        extra_steps = []
        for d in ranked:
            line = _excerpt_line(d)
            if line:
                extra_steps.append(line)
        if not extra_steps:
            extra_steps = [
                "No matching library excerpt was retrieved. Re-check category or model keywords, "
                "or ask a manager to index the unit in Document Library."
            ]
        spec = {
            "primary_cite": _generic_primary_cite(ranked),
            "pattern_means": (
                "Use the next cited check from this shop's library excerpts."
            ),
            "flowchart": _generic_flowchart(concern or "Customer concern", extra_steps),
            "bay_order": extra_steps[:6],
            "do_not": [
                "Do not skip the next cited check.",
            ],
            "sources": [],
        }

    sources = _merge_sources(spec.get("sources") or [], _unique_sources(ranked), ice=ice)
    if ice and not any("ccd-0008122" in (s.get("title") or "").lower() for s in sources):
        sources.insert(0, spec["sources"][0])

    checks = [
        BayCheck(text=step, source_title=spec.get("primary_cite") or "", kind="check")
        for step in spec["bay_order"]
    ]
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

    display_model = spec.get("display_model") or ""
    if firefly:
        display_model = "Level Up Advantage controller (Brinkley / Firefly)"
    elif facr and not display_model:
        display_model = "Furrion Chill rooftop unit"
    elif ice and not display_model:
        display_model = " ".join(p for p in (brand, model) if p) or "Furrion fridge"

    notes = _lock_note(category, model_text, concern)
    return BayProcedure(
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
    )


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
        return (176.0, 76.0) if readable else (132.0, 58.0)
    if node.kind in ("start", "end"):
        return (260.0, 50.0) if readable else (210.0, 38.0)
    return (230.0, 52.0) if readable else (230.0, 40.0)


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


def layout_flowchart(flow: Flowchart, frame_x: float, frame_y: float, frame_w: float, frame_h: float):
    """Return (shapes, texts) in PDF space (origin bottom-left)."""
    shapes: list[DrawnShape] = []
    texts: list[DrawnText] = []
    placed: dict[str, tuple[float, float, float, float]] = {}

    shapes.append(
        DrawnShape("roundrect", frame_x, frame_y, frame_w, frame_h, fill=PALE, stroke=NAVY, stroke_w=1.4, radius=6)
    )
    texts.append(
        DrawnText(
            "VISUAL FLOWCHART",
            frame_x + 10,
            frame_y + frame_h - 16,
            w=200,
            size=8,
            bold=True,
            color=NAVY,
        )
    )

    inner_x = frame_x + 10
    inner_y = frame_y + 10
    inner_w = frame_w - 20
    inner_h = frame_h - 28

    readable = bool(getattr(flow, "readable", False))
    for node in flow.nodes:
        w, h = _node_size(node, readable=readable)
        cx = inner_x + node.x * inner_w
        # node.y is top-to-bottom fraction; PDF y is bottom-up
        cy = inner_y + inner_h - node.y * inner_h
        # Keep shapes inside the frame.
        pad = 8 if readable else 2
        cx = min(max(cx, inner_x + w / 2 + pad), inner_x + inner_w - w / 2 - pad)
        cy = min(max(cy, inner_y + h / 2 + pad), inner_y + inner_h - h / 2 - pad)
        placed[node.id] = (cx, cy, w, h)
        x, y = cx - w / 2, cy - h / 2
        if node.kind == "decision":
            shapes.append(DrawnShape("diamond", x, y, w, h, fill=GOLD, stroke=NAVY, stroke_w=1.7))
            size = 9.5 if readable else 7.5
        elif node.kind in ("start", "end"):
            fill = GREEN if node.kind == "start" else NAVY
            shapes.append(DrawnShape("ellipse", x, y, w, h, fill=fill, stroke=NAVY, stroke_w=1.5))
            size = 9.0 if readable else 7.5
        else:
            shapes.append(DrawnShape("roundrect", x, y, w, h, fill=WHITE, stroke=NAVY, stroke_w=1.4, radius=6))
            size = 9.0 if readable else 7.5
        color = WHITE if node.kind in ("start", "end") else INK
        texts.append(
            DrawnText(
                node.text,
                cx,
                cy,
                w=w - (22 if readable else 14),
                size=size,
                bold=node.kind == "decision",
                color=color,
                align="center",
                leading=size + (3.0 if readable else 1.5),
            )
        )

    for edge in flow.edges:
        if edge.from_id not in placed or edge.to_id not in placed:
            continue
        fx, fy, fw, fh = placed[edge.from_id]
        tx, ty, tw, th = placed[edge.to_id]
        x1, y1 = _port(fx, fy, fw, fh, edge.from_side)
        x2, y2 = _port(tx, ty, tw, th, edge.to_side)
        shapes.append(DrawnShape("arrow", x=x1, y=y1, x2=x2, y2=y2, stroke=NAVY, stroke_w=1.15))
        if edge.label:
            mx, my = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            if edge.from_side == "left":
                mx, my = mx, my + 8
            elif edge.from_side == "right":
                mx, my = mx, my + 8
            else:
                mx, my = mx + 12, my
            color = GREEN if edge.label.upper() == "YES" else RED
            texts.append(
                DrawnText(
                    edge.label.upper(),
                    mx,
                    my,
                    w=36,
                    size=9 if readable else 7,
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
    """Build drawable pages for a human bay sheet."""
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

    # Header fields — form row, not a stacked bot dump
    header_top = bar_y - 8
    header_h = 64
    header_y = header_top - header_h
    page.shapes.append(
        DrawnShape("rect", MARGIN, header_y, PAGE_W - 2 * MARGIN, header_h, fill=CREAM, stroke=NAVY, stroke_w=1.0)
    )
    y = header_top - 16
    page.texts.append(DrawnText("CONCERN", MARGIN + 8, y, w=70, size=7, bold=True, color=GREEN))
    concern_lines = _wrap(proc.concern or "-", 88)
    page.texts.append(DrawnText(concern_lines[0], MARGIN + 78, y, w=450, size=9, bold=True, color=INK))
    y -= 14
    if len(concern_lines) > 1:
        page.texts.append(DrawnText(concern_lines[1], MARGIN + 78, y, w=450, size=9, bold=True, color=INK))
        y -= 12
    page.texts.append(DrawnText("MODEL", MARGIN + 8, y, w=70, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(_clip(proc.model_line, 56), MARGIN + 78, y, w=230, size=9, bold=True, color=INK))
    page.texts.append(DrawnText("DATE", MARGIN + 310, y, w=36, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(proc.created.strftime("%Y-%m-%d"), MARGIN + 348, y, w=80, size=9, bold=True, color=INK))
    page.texts.append(DrawnText("WO#", MARGIN + 440, y, w=28, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(_clip(proc.wo_number or "-", 16), MARGIN + 470, y, w=70, size=9, bold=True, color=INK))
    y -= 14
    page.texts.append(DrawnText("PRIMARY", MARGIN + 8, y, w=70, size=7, bold=True, color=GREEN))
    page.texts.append(DrawnText(_clip(proc.primary_cite or "-", 92), MARGIN + 78, y, w=460, size=9, bold=True, color=INK))

    # What this pattern usually means
    means_top = header_y - 10
    means_lines = _wrap(proc.pattern_means or "-", 96)
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

    # Flowchart frame — the product, not a paragraph list
    flow_top = means_y - 8
    if proc.flow_tall or getattr(proc.flowchart, "readable", False):
        flow_h = 252
    elif len(proc.bay_order) > 4:
        flow_h = 188
    else:
        flow_h = 210
    flow_y = flow_top - flow_h
    f_shapes, f_texts = layout_flowchart(proc.flowchart, MARGIN, flow_y, PAGE_W - 2 * MARGIN, flow_h)
    page.shapes.extend(f_shapes)
    page.texts.extend(f_texts)

    # Bay order then Do not — full width so complete sentences are not clipped.
    col_top = flow_y - 8
    shown_order = proc.bay_order[:MAX_BAY_ORDER]
    order_lines = []
    for i, step in enumerate(shown_order, 1):
        order_lines.append(_wrap(f"{i}. {step}", 98)[:4])
    do_lines = [_wrap(f"- {item}", 98)[:2] for item in proc.do_not[:4]]
    order_h = 22 + sum(len(block) * 10 + 3 for block in order_lines)
    do_h = 22 + sum(len(block) * 10 + 2 for block in do_lines)
    order_y = col_top - order_h
    do_top = order_y - 6
    do_y = do_top - do_h
    page.shapes.append(DrawnShape("rect", MARGIN, order_y, PAGE_W - 2 * MARGIN, order_h, fill=WHITE, stroke=NAVY, stroke_w=1.0))
    _add_section_bar(page, MARGIN, col_top - 16, PAGE_W - 2 * MARGIN, "BAY ORDER (DO THIS FIRST)", GREEN)
    y = col_top - 28
    for i, step in enumerate(shown_order, 1):
        page.shapes.append(DrawnShape("rect", MARGIN + 8, y - 1, 8, 8, fill=WHITE, stroke=NAVY, stroke_w=0.9))
        wrapped = _wrap(f"{i}. {step}", 98)[:4]
        for line in wrapped:
            page.texts.append(DrawnText(line, MARGIN + 22, y, w=520, size=7.5, color=INK))
            y -= 10
        y -= 3
    page.shapes.append(DrawnShape("rect", MARGIN, do_y, PAGE_W - 2 * MARGIN, do_h, fill=CREAM, stroke=RED, stroke_w=1.1))
    _add_section_bar(page, MARGIN, do_top - 16, PAGE_W - 2 * MARGIN, "DO NOT", RED)
    y = do_top - 28
    for item in proc.do_not[:4]:
        for line in _wrap(f"- {item}", 98)[:2]:
            page.texts.append(DrawnText(line, MARGIN + 8, y, w=520, size=7.5, color=INK))
            y -= 10
        y -= 2

    col_y = do_y

    # Sources + figure citations (compact). Page 2 only when a library image exists.
    imaged = [fig for fig in proc.figures if fig.image_png]
    src_top = col_y - 8
    src_h = 78 if not proc.include_3c else 58
    src_y = max(MARGIN + (22 if proc.include_3c else 8), src_top - src_h)
    page.shapes.append(
        DrawnShape("rect", MARGIN, src_y, PAGE_W - 2 * MARGIN, src_top - src_y, fill=WHITE, stroke=NAVY, stroke_w=1.0)
    )
    _add_section_bar(page, MARGIN, src_top - 16, PAGE_W - 2 * MARGIN, "SOURCES (SHOP DOCUMENT LIBRARY)")
    y = src_top - 28
    src_rows = proc.sources[:3] or [{"title": "(no indexed excerpt retrieved this pass)", "page": None}]
    for s in src_rows:
        page_bit = ""
        if s.get("page"):
            page_bit = f"  page {s['page']}"
        line = f"- {s.get('title') or 'Manual'}{page_bit}"
        page.texts.append(DrawnText(_clip(line, 110), MARGIN + 8, y, w=520, size=8, color=INK))
        y -= 11
        if y < src_y + 16:
            break
    if proc.figures and y > src_y + 14:
        fig_bits = []
        for fig in proc.figures[:3]:
            bit = fig.caption or "Figure"
            if fig.title:
                bit += f" — {fig.title}"
            if fig.page:
                bit += f" p.{fig.page}"
            fig_bits.append(bit)
        page.texts.append(
            DrawnText(_clip("Figures: " + "; ".join(fig_bits), 110), MARGIN + 8, y, w=520, size=8, color=MUTED)
        )
        y -= 11
    if imaged and y > src_y + 36:
        thumb = imaged[0]
        thumb_h = min(48, max(28, y - src_y - 8))
        page.images.append(DrawnImage(thumb.image_png, MARGIN + 8, src_y + 6, 90, thumb_h))
        page.texts.append(
            DrawnText(
                "Library figure on next page.",
                MARGIN + 106,
                src_y + 16,
                w=400,
                size=8,
                color=MUTED,
            )
        )

    if proc.include_3c and not imaged:
        _add_3c_footer(page)

    if imaged:
        page2 = SheetPage()
        pages.append(page2)
        page2.shapes.append(DrawnShape("rect", 0, 0, PAGE_W, PAGE_H, fill=WHITE, stroke=WHITE, stroke_w=0))
        page2.shapes.append(
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
        top = PAGE_H - MARGIN - 16
        _add_section_bar(page2, MARGIN, top, PAGE_W - 2 * MARGIN, "CITED LIBRARY FIGURES")
        y = top - 14
        for fig in imaged[:3]:
            cap = f"{fig.caption or 'Figure'} -- {fig.title}" + (f" p.{fig.page}" if fig.page else "")
            page2.texts.append(DrawnText(_clip(cap, 100), MARGIN + 8, y, w=520, size=9, bold=True, color=NAVY))
            y -= 12
            img_h = 320
            if y - img_h < MARGIN + 40:
                img_h = max(80, y - (MARGIN + 40))
            page2.images.append(DrawnImage(fig.image_png, MARGIN + 16, y - img_h, 520, img_h))
            y -= img_h + 10
            if y < MARGIN + 80:
                break
        if proc.include_3c:
            _add_3c_footer(page2)

    return pages


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
        c.line(sh.x, sh.y, sh.x2, sh.y2)
        if sh.kind == "arrow":
            _rl_arrowhead(c, sh.x, sh.y, sh.x2, sh.y2, stroke)


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
        pdf.line(sh.x, PAGE_H - sh.y, sh.x2, PAGE_H - sh.y2)


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
        ops.append(f"{sh.x:.1f} {sh.y:.1f} m")
        ops.append(f"{sh.x2:.1f} {sh.y2:.1f} l")
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