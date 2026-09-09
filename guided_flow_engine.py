"""
Guided Diagnostics flowchart engine.

Loads hard procedure trees from procedures/*.json. TECH reports Pass/Fail/readings;
tree edges choose the next gate. Never invents OEM steps.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

PROCEDURES_DIR = Path(__file__).resolve().parent / "procedures"

ASK_FLOWCHART_PAGE_LOCK = (
    "HARD FLOWCHART PAGE LOCK: You may only prescribe the next test that appears as "
    "the next decision on the cited excerpt page; never invent adjacent gates from "
    "other sections. Prefer the hard procedure tree when one exists for this model."
)

# Ordered alias lists: first matching key that is an allowed edge wins.
DEFAULT_ANSWER_ALIAS_GROUPS = [
    ("light_on_not_cooling", [
        "light on not cooling", "light on, not cooling", "has power not cooling",
        "power on not cooling", "light works not cooling", "light on but not cool",
        "cavity light on not cooling", "powered but not cooling",
    ]),
    ("light_on_cooling", [
        "light on cooling", "light on and cooling", "power restored cooling",
        "working now", "cools now", "issue resolved",
    ]),
    ("replaced", ["fuse replaced", "replaced fuse", "replaced the fuse", "new fuse installed", "swapped fuse"]),
    ("blown", ["fuse blown", "blown fuse", "fuse is blown", "was blown"]),
    ("good", ["fuse good", "fuse ok", "fuse fine", "fuse intact", "continuity good", "not blown"]),
    ("pass", ["pass", "passed", "paper moves", "sucks and blows", "left suck", "right blow", "airflow good"]),
    ("fail", [
        "fail", "failed", "no paper", "paper no", "no movement", "no paper movement",
        "doesn't move", "does not move", "no suck", "no blow", "paper fails",
    ]),
    ("off", ["dial off", "set to off", "was off", "in off"]),
    ("yes", [
        "yes", "y", "yeah", "yep", "affirmative", "correct", "confirmed",
        "light on", "it is on", "dial is on", "on 4", "on 5", "position 4", "position 5",
        "operating", "compressor running", "running", "amps >1", "greater than 1",
        "12v", "12 v", "between 12", "ok", "good", "voltage good", ">=10.5", "10.5", "11v", "13v", "14v",
    ]),
    ("no", [
        "no", "n", "nope", "negative", "not operating", "not running", "dead compressor",
        "no light", "still dark", "below 10.5", "low voltage", "9v", "under 11",
        "current <3", "less than 3", "<3",
    ]),
]


def _norm_flow_text(s: str) -> str:
    t = (s or "").lower().strip()
    t = t.replace("—", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t)
    return t


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def validate_procedure(procedure: dict) -> list:
    """Return a list of validation errors. Empty means the tree is loadable."""
    errors = []
    if not isinstance(procedure, dict):
        return ["procedure is not an object"]
    pid = (procedure.get("id") or "").strip()
    if not pid:
        errors.append("missing id")
    if not (procedure.get("title") or "").strip():
        errors.append(f"{pid or '?'}: missing title")
    if not (procedure.get("brand") or "").strip():
        errors.append(f"{pid or '?'}: missing brand (job pin requires it)")
    nodes = procedure.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        errors.append(f"{pid or '?'}: missing nodes")
        return errors
    default_start = procedure.get("default_start")
    if default_start and default_start not in nodes:
        errors.append(f"{pid}: default_start {default_start!r} is not a node")
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            errors.append(f"{pid}.{nid}: node is not an object")
            continue
        if (node.get("id") or nid) != nid:
            errors.append(f"{pid}.{nid}: node.id mismatch")
        if not (node.get("type") or "").strip():
            errors.append(f"{pid}.{nid}: missing type")
        if not (node.get("prompt") or "").strip():
            errors.append(f"{pid}.{nid}: missing prompt")
        if not (node.get("source_title") or "").strip():
            errors.append(f"{pid}.{nid}: missing source_title")
        if node.get("source_page") is None:
            errors.append(f"{pid}.{nid}: missing source_page")
        else:
            try:
                int(node.get("source_page"))
            except (TypeError, ValueError):
                errors.append(f"{pid}.{nid}: source_page is not an int")
        edges = node.get("edges") or {}
        if (node.get("type") or "") != "end" and not edges:
            errors.append(f"{pid}.{nid}: non-end node has no edges")
        for key, dest in (edges or {}).items():
            if dest not in nodes:
                errors.append(f"{pid}.{nid}: edge {key!r} → unknown node {dest!r}")
    return errors


def load_procedure_trees(directory=None) -> dict:
    """Load every procedures/*.json except _*.json. Invalid trees are skipped."""
    root = Path(directory) if directory else PROCEDURES_DIR
    trees = {}
    if not root.is_dir():
        return trees
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        errors = validate_procedure(data)
        if errors:
            continue
        trees[data["id"]] = data
    return trees


PROCEDURE_TREES = load_procedure_trees()


def reload_procedure_trees(directory=None) -> dict:
    """Reload trees (tests / new files). Updates the module-level registry."""
    global PROCEDURE_TREES
    PROCEDURE_TREES = load_procedure_trees(directory)
    return PROCEDURE_TREES


def get_procedure(procedure_id: str):
    if not procedure_id:
        return None
    return PROCEDURE_TREES.get(procedure_id)


def get_procedure_node(procedure: dict, node_id: str):
    if not procedure:
        return None
    return (procedure.get("nodes") or {}).get(node_id)


def procedure_matches(procedure: dict, category_name: str = "", model_text: str = "", concern: str = "") -> bool:
    """True when category + model + concern pin this tree. No invented match."""
    if not procedure:
        return False
    cat = _norm_flow_text(category_name)
    model = _norm_flow_text(model_text)
    concern_n = _norm_flow_text(concern)
    blob = _norm_flow_text(f"{category_name or ''} {model_text or ''} {concern or ''}")
    compact = blob.replace(" ", "")

    match = procedure.get("match") or {}
    for rule in _as_list(match.get("any")):
        if not isinstance(rule, dict):
            continue
        token = _norm_flow_text(str(rule.get("contains") or ""))
        if token and (token in blob or token.replace(" ", "") in compact):
            return True
        if rule.get("all_contains") and all(
            _norm_flow_text(x) in blob for x in _as_list(rule.get("all_contains"))
        ):
            return True
        pat = rule.get("regex")
        if pat:
            try:
                if re.search(pat, blob):
                    return True
            except re.error:
                pass

    combo = match.get("or_category_and_model") or {}
    if combo:
        cat_ok = any(tok in cat for tok in _as_list(combo.get("category_any")))
        model_blob = _norm_flow_text(f"{model_text or ''} {concern or ''}")
        model_ok = any(tok in model_blob for tok in _as_list(combo.get("model_any")))
        if cat_ok and model_ok:
            return True

    # Fallback: published model tokens + category tokens (legacy trees).
    if not match:
        models = [_norm_flow_text(m) for m in _as_list(procedure.get("models"))]
        cats = [_norm_flow_text(c) for c in _as_list(procedure.get("categories"))]
        if any(m and m in blob for m in models):
            return True
        if cats and any(c in cat or c in concern_n for c in cats) and any(
            m and m in model for m in models
        ):
            return True
    return False


def find_matching_procedure(category_name: str = "", model_text: str = "", concern: str = ""):
    """Return the first loaded tree that matches category+model+concern, else None."""
    for proc in PROCEDURE_TREES.values():
        if procedure_matches(proc, category_name, model_text, concern):
            return proc
    return None


def format_gate_reply(node: dict, preface: str = "") -> str:
    """Shop language for the current gate + 📖 Source from the node (prompt verbatim)."""
    if not node:
        return "No active diagnostic gate."
    prompt = (node.get("prompt") or "").strip()
    title = (node.get("source_title") or "").strip()
    page = node.get("source_page")
    parts = []
    if preface:
        parts.append(preface.strip())
        parts.append("")
    parts.append(prompt)
    if title and page is not None:
        parts.append("")
        parts.append(f"📖 Source: {title} - page {page}")
    return "\n".join(parts).strip()


def _flag_true(spec: dict, blob: str) -> bool:
    if not isinstance(spec, dict):
        return False
    for pat in _as_list(spec.get("any_regex")):
        try:
            if re.search(pat, blob):
                return True
        except re.error:
            continue
    for group in _as_list(spec.get("any_all_contains")):
        items = [_norm_flow_text(x) for x in _as_list(group)]
        if items and all(x in blob for x in items):
            return True
    for phrase in _as_list(spec.get("any_contains")):
        if _norm_flow_text(phrase) in blob:
            return True
    return False


def _eval_when(cond, flags: dict, blob: str) -> bool:
    if cond is None:
        return True
    if not isinstance(cond, dict):
        return False
    if "flag" in cond:
        return bool(flags.get(cond["flag"]))
    if "not" in cond:
        return not _eval_when(cond.get("not"), flags, blob)
    if "all" in cond:
        return all(_eval_when(c, flags, blob) for c in _as_list(cond.get("all")))
    if "any" in cond:
        return any(_eval_when(c, flags, blob) for c in _as_list(cond.get("any")))
    if "regex" in cond:
        try:
            return bool(re.search(cond["regex"], blob))
        except re.error:
            return False
    return False


def select_start_node_id(procedure: dict, user_msg: str, history: list = None) -> str:
    """
    Start node from tech free text. Does not invent tests — only picks an entry gate
    using procedure.flags + start_rules. Falls back to default_start.
    """
    default = (procedure or {}).get("default_start") or ""
    nodes = (procedure or {}).get("nodes") or {}
    if default and default not in nodes:
        default = next(iter(nodes), "")
    prior = " ".join(
        (m.get("content") or "") for m in (history or []) if m.get("role") == "user"
    )
    blob = _norm_flow_text(f"{prior} {user_msg}")
    flags = {}
    for name, spec in ((procedure or {}).get("flags") or {}).items():
        flags[name] = _flag_true(spec, blob)
    for rule in _as_list((procedure or {}).get("start_rules")):
        if not isinstance(rule, dict):
            continue
        start = rule.get("start")
        if start not in nodes:
            continue
        if _eval_when(rule.get("when"), flags, blob):
            return start
    return default


def _phrase_hit(phrase: str, text: str) -> bool:
    if phrase not in text:
        return False
    if not re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text):
        return False
    if re.search(r"\b(?:not|no|never|isn't|isnt|wasn't|wasnt|ain't|aint)\s+" + re.escape(phrase), text):
        return False
    if re.search(r"\b(?:does\s+not|doesn't|doesnt|not|no|never)\b.{0,48}" + re.escape(phrase), text):
        return False
    return True


def _first_allowed(edges: dict, *keys):
    for key in keys:
        if key and key in edges:
            return key
    return None


def _hint_matches(rule: dict, raw: str) -> bool:
    if not isinstance(rule, dict):
        return False
    if rule.get("regex"):
        try:
            if not re.search(rule["regex"], raw):
                return False
        except re.error:
            return False
    if rule.get("none_regex"):
        try:
            if re.search(rule["none_regex"], raw):
                return False
        except re.error:
            pass
    if rule.get("any_contains"):
        if not any(p in raw for p in _as_list(rule.get("any_contains"))):
            return False
    if rule.get("all_contains"):
        if not all(p in raw for p in _as_list(rule.get("all_contains"))):
            return False
    if rule.get("none_contains"):
        if any(p in raw for p in _as_list(rule.get("none_contains"))):
            return False
    if rule.get("all_groups"):
        for group in _as_list(rule.get("all_groups")):
            if not any(p in raw for p in _as_list(group)):
                return False
    has_condition = any(
        k in rule
        for k in ("regex", "any_contains", "all_contains", "all_groups")
    )
    return has_condition


def _apply_hint_rules(rules, raw: str, edges: dict):
    for rule in _as_list(rules):
        if not _hint_matches(rule, raw):
            continue
        key = _first_allowed(edges, rule.get("answer"), rule.get("fallback"))
        if key:
            return key
    return None


def _apply_reading(spec: dict, raw: str, edges: dict):
    """Map a meter reading to an edge using node.reading. Returns (edge, reading) or (None, reading)."""
    if not isinstance(spec, dict):
        return None, None
    reading_val = None
    pat = spec.get("regex") or r"(\d+(?:\.\d+)?)"
    try:
        m = re.search(pat, raw)
    except re.error:
        m = None
    if m:
        try:
            reading_val = float(m.group(1))
        except (TypeError, ValueError, IndexError):
            reading_val = None

    compare = (spec.get("compare") or "").strip().lower()
    true_key = spec.get("true") or spec.get("in_range")
    false_key = spec.get("false") or spec.get("out_of_range")

    if reading_val is not None and compare:
        ok = None
        if compare in ("gte", "min"):
            ok = reading_val >= float(spec.get("threshold", spec.get("min", 0)))
        elif compare in ("lte", "max"):
            ok = reading_val <= float(spec.get("threshold", spec.get("max", 0)))
        elif compare == "gt":
            ok = reading_val > float(spec.get("threshold", 0))
        elif compare == "lt":
            ok = reading_val < float(spec.get("threshold", 0))
        elif compare == "between":
            lo = float(spec.get("min", 0))
            hi = float(spec.get("max", lo))
            ok = lo <= reading_val <= hi
        elif compare == "eq":
            ok = abs(reading_val - float(spec.get("threshold", 0))) < 0.05
        if ok is True:
            key = _first_allowed(edges, true_key, "yes", "pass")
            if key:
                return key, reading_val
        if ok is False:
            key = _first_allowed(edges, false_key, "no", "fail")
            if key:
                return key, reading_val

    for phrase in _as_list(spec.get("text_true")):
        if phrase and phrase in raw:
            key = _first_allowed(edges, true_key, "yes", "pass")
            if key:
                return key, reading_val
    for phrase in _as_list(spec.get("text_false")):
        if phrase and phrase in raw:
            key = _first_allowed(edges, false_key, "no", "fail")
            if key:
                return key, reading_val
    return None, reading_val


def map_tech_text_to_answer(node: dict, tech_text: str, procedure: dict = None):
    """
    Map free text to ONE allowed edge key for the CURRENT node.
    Returns (answer_key, None, reading) or (None, reason, reading) if unmapped.
    Caller must re-ask, not advance, when unmapped.
    """
    if not node:
        return None, "no_node", None
    edges = node.get("edges") or {}
    if not edges:
        return None, "end_node", None
    raw = _norm_flow_text(tech_text)
    if not raw:
        return None, "empty", None

    for key in edges:
        if raw == key or raw.startswith(key + " ") or raw.endswith(" " + key):
            return key, None, None

    hints = node.get("map_hints") or {}
    pre = _apply_hint_rules(hints.get("pre_alias"), raw, edges)
    if pre:
        return pre, None, None

    alias_groups = list(DEFAULT_ANSWER_ALIAS_GROUPS)
    extra = (procedure or {}).get("answer_aliases") if procedure else None
    if extra:
        alias_groups = list(extra) + alias_groups
    for key, phrases in alias_groups:
        if key not in edges:
            continue
        for p in phrases:
            if _phrase_hit(p, raw):
                return key, None, None

    post = _apply_hint_rules(hints.get("rules"), raw, edges)
    if post:
        return post, None, None

    reading_key, reading_val = _apply_reading(node.get("reading"), raw, edges)
    if reading_key:
        return reading_key, None, reading_val

    lead = raw.split(",", 1)[0].strip()
    if lead in ("yes", "y", "yeah", "yep", "pass", "ok", "good") or raw in ("yes", "y", "yeah", "yep", "pass", "ok", "good"):
        key = _first_allowed(edges, "yes", "pass")
        if key:
            return key, None, reading_val
    if lead in ("no", "n", "nope", "fail", "failed") or raw in ("no", "n", "nope", "fail", "failed"):
        key = _first_allowed(edges, "no", "fail")
        if key:
            return key, None, reading_val

    return None, "unmapped", reading_val


def advance_flow(procedure: dict, node_id: str, answer_key: str):
    """Advance ONLY via tree edges. Returns (next_node_id, next_node) or (None, None)."""
    node = get_procedure_node(procedure, node_id)
    if not node:
        return None, None
    edges = node.get("edges") or {}
    nxt = edges.get(answer_key)
    if not nxt:
        return None, None
    return nxt, get_procedure_node(procedure, nxt)


def binary_button_labels(node: dict):
    """Optional Pass/Fail or Yes/No labels when node is binary."""
    if not node or (node.get("type") or "") != "binary":
        return None
    edges = node.get("edges") or {}
    if "pass" in edges and "fail" in edges:
        return ("Pass", "pass", "Fail", "fail")
    if "yes" in edges and "no" in edges:
        return ("Yes", "yes", "No", "no")
    return None


def node_source_item(node: dict) -> dict:
    if not node:
        return {}
    title = (node.get("source_title") or "").strip()
    page = node.get("source_page")
    if not title or page is None:
        return {}
    try:
        page = int(page)
    except (TypeError, ValueError):
        return {}
    return {
        "title": title,
        "page": page,
        "node_id": node.get("id"),
    }


def append_source_ledger(flow: dict, node: dict) -> dict:
    """Silent append-only ledger of cited pages for the warranty story."""
    flow = dict(flow or {})
    item = node_source_item(node)
    if not item:
        return flow
    ledger = list(flow.get("source_ledger") or [])
    key = ((item.get("title") or "").strip().lower(), int(item.get("page") or 0))
    seen = {
        ((s.get("title") or "").strip().lower(), int(s.get("page") or 0))
        for s in ledger
        if isinstance(s, dict)
    }
    if key not in seen:
        ledger.append(item)
    flow["source_ledger"] = ledger
    return flow


def pin_job(flow: dict, procedure: dict, category_name: str = "", model_text: str = "", concern: str = "") -> dict:
    """Bind brand / model / concern / procedure for the rest of this chat."""
    flow = dict(flow or {})
    flow["procedure_id"] = procedure.get("id")
    flow["brand"] = (procedure.get("brand") or flow.get("brand") or "").strip()
    flow["family"] = (procedure.get("family") or flow.get("family") or "").strip()
    if category_name and not flow.get("category"):
        flow["category"] = category_name.strip()
    if model_text and not flow.get("model"):
        flow["model"] = model_text.strip()
    if not flow.get("model"):
        flow["model"] = (procedure.get("family") or procedure.get("title") or "").strip()
    if concern and not flow.get("concern"):
        flow["concern"] = (concern or "").strip()[:400]
    flow.setdefault("history", list(flow.get("history") or []))
    flow.setdefault("source_ledger", list(flow.get("source_ledger") or []))
    return flow


def job_pin_caption(flow: dict) -> str:
    if not flow or not flow.get("procedure_id"):
        return ""
    brand = (flow.get("brand") or "").strip()
    model = (flow.get("model") or flow.get("family") or "").strip()
    concern = (flow.get("concern") or "").strip()
    bits = [b for b in (brand, model) if b]
    head = " · ".join(bits) if bits else flow.get("procedure_id")
    if concern:
        return f"Pinned job: {head} — {concern[:80]}"
    return f"Pinned job: {head}"


def _reask_preface(node: dict) -> str:
    edges_keys = ", ".join((node.get("edges") or {}).keys())
    custom = (node.get("reask_preface") or "").strip()
    if custom:
        return custom.replace("{edges}", edges_keys)
    return (
        "I need a result that matches this gate "
        f"({edges_keys}). "
        "Report only this check — I will not skip ahead."
    )


def engine_turn(
    ask_flow: dict,
    user_msg: str,
    category_name: str = "",
    model_text: str = "",
    chat_history: list = None,
):
    """
    One Guided Diagnostics engine turn.

    Job pin: once a tree is chosen, brand/model/concern/procedure stay bound
    even if the UI category/model widgets change. Free-text never invents a gate.

    Returns dict: used_engine, reply, ask_flow, reask, node, ...
    If no matching tree: used_engine=False (caller uses AI path with page-lock).
    """
    flow = dict(ask_flow or {})
    concern = (flow.get("concern") or user_msg or "").strip()
    procedure = None
    pinned_id = flow.get("procedure_id")
    if pinned_id:
        procedure = get_procedure(pinned_id)
    if not procedure:
        hist_blob = " ".join(
            (m.get("content") or "") for m in (chat_history or []) if m.get("role") == "user"
        )
        procedure = find_matching_procedure(
            category_name,
            model_text,
            f"{concern} {hist_blob} {user_msg}",
        )
    if not procedure:
        return {
            "used_engine": False,
            "reply": None,
            "ask_flow": ask_flow,
            "reask": False,
            "node": None,
        }

    hist = list(flow.get("history") or [])
    node_id = flow.get("node_id")
    proc_id = procedure["id"]

    if flow.get("procedure_id") != proc_id or not node_id:
        node_id = select_start_node_id(procedure, user_msg, chat_history)
        node = get_procedure_node(procedure, node_id)
        flow = pin_job(flow, procedure, category_name, model_text, user_msg)
        flow["node_id"] = node_id
        flow["history"] = hist
        flow = append_source_ledger(flow, node)
        return {
            "used_engine": True,
            "reply": format_gate_reply(node),
            "ask_flow": flow,
            "reask": False,
            "node": node,
            "opened": True,
            "start_id": node_id,
        }

    node = get_procedure_node(procedure, node_id)
    if not node:
        node_id = select_start_node_id(procedure, user_msg, chat_history)
        node = get_procedure_node(procedure, node_id)
        flow = pin_job(flow, procedure, category_name, model_text, user_msg)
        flow["node_id"] = node_id
        flow["history"] = hist
        flow = append_source_ledger(flow, node)
        return {
            "used_engine": True,
            "reply": format_gate_reply(node),
            "ask_flow": flow,
            "reask": False,
            "node": node,
        }

    flow = pin_job(flow, procedure, category_name, model_text, concern)
    flow = append_source_ledger(flow, node)

    if (node.get("type") or "") == "end" or not (node.get("edges") or {}):
        return {
            "used_engine": True,
            "reply": format_gate_reply(
                node,
                preface="This path is complete. Start a new chat for another symptom branch.",
            ),
            "ask_flow": flow,
            "reask": False,
            "node": node,
        }

    answer, reason, reading_val = map_tech_text_to_answer(node, user_msg, procedure)
    if not answer:
        return {
            "used_engine": True,
            "reply": format_gate_reply(node, preface=_reask_preface(node)),
            "ask_flow": flow,
            "reask": True,
            "node": node,
            "unmapped_reason": reason,
            "reading": reading_val,
        }

    next_id, next_node = advance_flow(procedure, node_id, answer)
    if not next_id or not next_node:
        return {
            "used_engine": True,
            "reply": format_gate_reply(
                node,
                preface="That result does not match an edge on this gate. Re-report for this check only.",
            ),
            "ask_flow": flow,
            "reask": True,
            "node": node,
        }

    hist.append({
        "node_id": node_id,
        "result": answer,
        "reading": reading_val,
        "source_title": node.get("source_title"),
        "source_page": node.get("source_page"),
    })
    flow = pin_job(flow, procedure, category_name, model_text, concern)
    flow["node_id"] = next_id
    flow["history"] = hist
    flow = append_source_ledger(flow, next_node)
    return {
        "used_engine": True,
        "reply": format_gate_reply(next_node),
        "ask_flow": flow,
        "reask": False,
        "node": next_node,
        "advanced_from": node_id,
        "answer": answer,
        "reading": reading_val,
    }
