"""
Guided Diagnostics — open library coach helpers.

Chase product ruling 2026-09-09:
  Jobs / diagnostic work orders stay the plan feature.
  Guided Diagnostics chat is an OPEN LIBRARY COACH over cited shop manuals.
  Hard flowchart trees must not trap the tech ("path complete / start a new chat").
"""
from __future__ import annotations

import re

# Product path: hard tree is citation hint only — never exclusive GD chat.
HARD_TREE_EXCLUSIVE_CHAT = False

# Groq shut down llama-4-scout on 2026-07-17 for free/dev tiers (404 / no access).
# Current Groq vision models: https://console.groq.com/docs/vision
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
    "show me the diagram", "show me the drawing",
)

COACH_REQUEST_PHRASES = (
    "go back", "need to test", "test the compressor", "test compressor",
    "show me", "what does", "what is", "what are", "how do i", "how do you",
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
- Take the complaint and guide the tech from THIS SHOP's Document Library excerpts only.
- Answer clarifying questions, figure/diagram/illustration requests, and mid-job pivots in THIS chat.
- NEVER say "This path is complete" or tell the tech to start a new chat for another symptom branch.
- If they want to test the compressor after a paper test (or any other change of direction), follow that request using cited library pages. Do not refuse because a flowchart leaf was reached.
- Cite 📖 Source: [Exact manual title from excerpt] - page [N] when you use a page. Never invent OEM steps or page numbers.
- If the tech asks to see a figure/diagram/page, say TechTrack will display the shop library PDF page below. Do not invent markdown images.
- When you are recommending the next check (not answering a question), give at most 1-2 concrete tests, then wait. Questions still get answers.
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


def tech_wants_open_coach(user_msg: str) -> bool:
    """
    True when the tech is asking a question, pivoting, or requesting figures —
    never consume that line as a locked-tree gate answer.
    """
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
    Soft-disable cage: yield to the open coach on questions/pivots/figures,
    and whenever the tree is on an end / no-edge leaf (so 'go back, test compressor'
    is never answered with 'path complete').
    """
    if tech_wants_open_coach(user_msg):
        return True
    if not node:
        return False
    ntype = (node.get("type") or "").strip().lower()
    edges = node.get("edges") or {}
    if ntype == "end" or not edges:
        return True
    return False


def _clean_model_id(name: str) -> str:
    return (name or "").strip()


def pick_working_vision_model(candidates, call_model):
    """
    Try vision models in order. Used so a retired id (llama-4-scout 404)
    falls through to qwen/qwen3.6-27b instead of aborting the plate read.
    call_model(model_id) -> raw text (empty string counts as miss).
    Returns (model_id, raw, errors).
    """
    errors = []
    for model in candidates or []:
        try:
            raw = (call_model(model) or "").strip()
            if raw:
                return model, raw, errors
            errors.append(f"{model}: empty vision response")
        except Exception as e:
            errors.append(f"{model}: {e}")
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
    """Prefer an explicit vision model, then the shop chat model, then known xAI vision-capable ids."""
    out = []
    for m in (_clean_model_id(preferred_vision), _clean_model_id(preferred_chat)):
        if m and m not in out:
            out.append(m)
    for m in DEFAULT_XAI_VISION_MODELS:
        if m and m not in out:
            out.append(m)
    return out


def format_procedure_library_hint(procedure: dict) -> str:
    """
    Compact OEM-order + 📖 Source pages from a hard tree.
    Hint only — never a lock, never 'path complete'.
    """
    if not procedure:
        return ""
    title = (procedure.get("title") or procedure.get("id") or "shop manual").strip()
    lines = [
        f"SHOP LIBRARY HINT for {title} (citation aid only — not a lock).",
        "Use these shop-manual pages when they match the complaint. The tech may ask questions or change direction.",
        "Never say the path is complete or to start a new chat.",
    ]
    seen = set()
    nodes = procedure.get("nodes") or {}
    # Stable-ish order: keep dict order (Python 3.7+)
    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        src_title = (node.get("source_title") or title).strip()
        page = node.get("source_page")
        if page is None:
            continue
        try:
            page = int(page)
        except Exception:
            continue
        key = (src_title.lower(), page)
        if key in seen:
            continue
        seen.add(key)
        nid = (node.get("id") or "").replace("_", " ")
        lines.append(f"- {nid}: 📖 Source: {src_title} - page {page}")
    return "\n".join(lines)
