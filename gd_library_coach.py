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
"""


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
        return FIGURE_SEARCH_BOOST
    if wants_library_figures(user_msg):
        return "Fig. figure illustration diagram drawing"
    return ""


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
