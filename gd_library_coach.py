"""
Guided Diagnostics — simple open library coach.

Chase product (2026-09-09):
  Jobs / WO diagnostic plans stay the plan feature.
  GD chat = complaint → shop Document Library coach → questions, figures, mid-chat pivots.
  Hard tree / Yes-No gate quiz must NOT drive GD chat.
  Never re-ask facts the tech already stated.
  Never invent OEM steps. Cite 📖 Source: manual title - page N.
"""
from __future__ import annotations

import re

# Product path: hard tree is never exclusive GD chat.
HARD_TREE_EXCLUSIVE_CHAT = False

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
- If they already said the cavity light is on and the fridge is not cooling, do NOT ask those again. Do NOT restart at the fuse / no-power path. Follow the cited service-manual section for a powered unit that is not cooling (e.g. inoperable compressor). Do not force a fan-replacement leaf unless THIS turn's excerpt actually says that.
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
        return extra
    if wants_library_figures(user_msg):
        extra = "Fig. figure illustration diagram drawing"
        if is_level_up_advantage_context("", "", user_msg):
            extra = f"{LEVEL_UP_FIGURE_SEARCH_BOOST} {extra}"
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


def level_up_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    """Rewrite the library query toward Level-Up / OCTP / TI docs. Never add Unity terms."""
    symptom = (symptom or "").strip()
    if not is_level_up_advantage_context(category_name, model_text, symptom):
        return symptom
    return f"{symptom} {LEVEL_UP_SEARCH_BOOST}".strip()


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
    if title and is_unity_board_manual(title):
        return (
            "That Unity / OneControl awning-slide board manual is the wrong book for "
            "Level Up Advantage / 807662. The leveling figure is in a Leveling Level-Up / "
            "OCTP / TI-005 PDF in the shop library. If the page image did not render, "
            "download that Level-Up PDF or ask for a reindex."
        )
    return (
        "You asked for a figure/page. TechTrack could not load a matching shop-library PDF page "
        "(missing file path, download failed, unindexed PDF, or page render unavailable). "
        "If a Level-Up / TI-005 / QR-092 title is on the Document Library catalog, the figure "
        "is in that PDF — say so and ask for reindex. Do not invent a Unity substitute."
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
    if facts.get("light") == "on" and facts.get("cooling") == "not_cooling":
        lines.append(
            "Power is present and the unit is not cooling. Do NOT ask whether the light is on "
            "or whether it is cooling. Do NOT restart at fuse / no-power. Follow the shop "
            "service-manual section for a powered unit that is not cooling (inoperable compressor "
            "/ not-cooling diagnostics) from the excerpts — not a hardcoded fan-replacement leaf."
        )
    if facts.get("pivot") == "compressor" or facts.get("compressor") == "not_running":
        lines.append(
            "The tech wants compressor / inoperable-compressor guidance. Use the cited SM pages "
            "for that section. Do not force Fan Replacement unless this turn's excerpt says so."
        )
    return "\n".join(lines)


def coach_library_search_boost(facts: dict) -> str:
    """
    Extra library search terms from stated facts.
    Does not encode the wrong Furrion hard-tree path.
    """
    if not facts:
        return ""
    parts = []
    if facts.get("light") == "on" and facts.get("cooling") == "not_cooling":
        parts.append("not cooling inoperable compressor section 2 powered")
    if facts.get("compressor") == "not_running" or facts.get("pivot") == "compressor":
        parts.append("inoperable compressor compressor diagnostics")
    if facts.get("dial") == "on_4_5":
        parts.append("thermostat dial not cooling")
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
