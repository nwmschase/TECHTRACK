"""Warranty story for a Guided Diagnostics job (Complaint / Cause / Correction).

2026-11-24 (Chase, M1066): the Write-warranty-story button gives a real warranty story.
- Complaint: the customer's complaint the job started with (never the photo note).
- Cause: what the diagnosis found, as a tech writes it: the tests done, the readings and results, the failed part.
- Correction: the repair and its verification when the tech did the repair; otherwise, in general terms, the
  recommended repair (e.g. "Recommend replacing the evaporator fan assembly and verifying proper cooling operation.").

write_warranty_story() has Grok write it from the whole chat and the stored case state, then checks the result (three
sections, a recommendation when no repair was done, no part numbers that are not in the chat). warranty_story() builds the
same three sections from the stored case state alone; it is the fallback when Grok is not available or its text fails the
check. A story Grok wrote into the state block when the tech called the repair verified is used as written.
"""
from __future__ import annotations

import json

PHOTO_NOTE = "The file did not count."
PHOTO_NOTE_LINE = "\n(The file did not count as a finding.)"
HEADERS = ("COMPLAINT", "CAUSE", "CORRECTION")


def _clean_user(text: str) -> str:
    t = (text or "").replace(PHOTO_NOTE_LINE, "").strip()
    return "" if t == PHOTO_NOTE else t


def complaint_of(case: dict, history: list = None) -> str:
    """The job's starting complaint: the first thing the tech typed (photo note removed), else the stored complaint."""
    first = next(((m.get("content") or "").strip() for m in (history or []) if m.get("role") == "user"
                  and (m.get("content") or "").strip()), "")
    return _clean_user(first) or (case or {}).get("complaint", "") or ""


def repair_done(case: dict, history: list = None) -> bool:
    """The repair counts as done when Grok recorded it in the state block (repair.done); the chat is not regex-read."""
    rep = ((case or {}).get("state") or {}).get("repair") or {}
    return bool(rep.get("done"))


def _sentence(s: str) -> str:
    s = (s or "").strip()
    return s if not s or s.endswith((".", "!", "?")) else s + "."


def _recommendation(st: dict) -> str:
    part = (st.get("order_part") or "").strip()
    if part:
        for lead in ("replacing ", "replace "):
            if part.lower().startswith(lead):
                part = part[len(lead):].strip()
        if part.lower().startswith("the "):
            part = part[4:]
        return f"Recommend replacing the {part} and verifying proper operation."
    if (st.get("cause") or "").strip():
        return "Recommend repairing or replacing the failed component identified above and verifying proper operation."
    return "Recommend further diagnosis to confirm the cause before repair."


def warranty_story(case: dict, history: list = None, model_text: str = "") -> str:
    """Complaint / Cause / Correction from the stored case state (no AI)."""
    case = case or {}
    st = case.get("state") or {}
    if (st.get("story") or "").strip():
        return st["story"].strip()
    complaint = complaint_of(case, history)
    if not complaint and not st:
        return "No session recorded."
    unit = (case.get("unit") or {}).get("model_text") or model_text or ""
    cause_lines = []
    if unit:
        cause_lines.append(f"Diagnosed {unit}.")
    for f in st.get("facts") or []:
        item, value = (f.get("item") or "").strip(), (f.get("value") or "").strip()
        if item or value:
            cause_lines.append(_sentence(f"{item}: {value}" if item and value else item or value))
    cause_lines.append(_sentence(f"Cause: {st['cause'].strip()}") if (st.get("cause") or "").strip()
                       else "Cause not confirmed during diagnosis.")
    rep = st.get("repair") or {}
    if rep.get("done"):
        corr = _sentence(rep.get("what") or "Repair performed")
        corr += " Repair verified working." if rep.get("verified") else " Recommend verifying proper operation."
    else:
        corr = _recommendation(st)
    return "\n".join(["COMPLAINT:", _sentence(complaint) or "Not recorded.", "",
                      "CAUSE:", "\n".join(cause_lines), "",
                      "CORRECTION:", corr])


STORY_SYSTEM = """You write the warranty story for an RV repair job from a Guided Diagnostics session, the way an experienced RV warranty technician writes it for a Lippert, Furrion or Dometic claim: plain shop language, past tense, third person or tech voice, no markdown, no bullet symbols.

The story has exactly three sections, each header on its own line:
COMPLAINT:
CAUSE:
CORRECTION:

COMPLAINT: the customer's complaint the job started with, in the customer's terms ("Customer states ...").
CAUSE: what the diagnosis found, as a tech writes it: the tests the tech reported doing, in order, with the readings and results the tech reported, ending with the failed component or condition. Steps the assistant only suggested belong here when the tech reported doing them.
CORRECTION: when the job's repair status says the repair was performed, the repair and how it was verified. When it says the repair was not performed (diagnosis only), the recommended repair in general terms, starting with "Recommend", for example: "Recommend replacing the evaporator fan assembly and verifying proper cooling operation." A secondary issue the tech chose to leave can be noted as a separate recommendation.

Everything in the story comes from the session: readings, part names and results as the tech gave them. Part numbers, labor operation codes and times appear only when the tech gave them. Internal words such as OPEN, state, session, assistant, GD or TechTrack stay out of the story."""


def story_messages(case: dict, history: list = None, model_text: str = "") -> list:
    case = case or {}
    st = case.get("state") or {}
    unit = (case.get("unit") or {}).get("model_text") or model_text or "not recorded"
    category = (case.get("unit") or {}).get("category") or ""
    lines = []
    for m in history or []:
        role, text = m.get("role"), (m.get("content") or "").strip()
        if role == "user":
            text = _clean_user(text)
            if text:
                lines.append("TECH: " + text)
        elif role == "assistant" and text:
            lines.append("ASSISTANT (suggestions; done only when the tech reported it): " + text)
    keep = {k: st.get(k) for k in ("facts", "cause", "repair", "order_part") if st.get(k)}
    status = ("REPAIR STATUS: performed (write the CORRECTION as the repair done and its verification)."
              if repair_done(case, history) else
              "REPAIR STATUS: not performed - diagnosis only (write the CORRECTION as a general recommendation starting with \"Recommend\").")
    user = "\n\n".join([
        f"UNIT: {category + ' / ' if category else ''}{unit}",
        "CUSTOMER COMPLAINT (job start): " + (complaint_of(case, history) or "not recorded"),
        status,
        "CASE RECORD: " + json.dumps(keep, ensure_ascii=False),
        "SESSION:\n" + "\n\n".join(lines),
        "Write the warranty story now.",
    ])
    return [{"role": "system", "content": STORY_SYSTEM}, {"role": "user", "content": user}]


def _header(line: str):
    """("CAUSE", rest) when the line opens a section (COMPLAINT / CAUSE / CORRECTION, with or without markdown)."""
    t = line.strip().lstrip("#*_ ").strip()
    up = t.upper()
    for h in HEADERS:
        if up.startswith(h):
            rest = t[len(h):].lstrip("*_ ")
            if rest == "" or rest.startswith(":"):
                return h, rest[1:].strip(" *_") if rest.startswith(":") else ""
    return None


def parse_story(text: str) -> dict | None:
    """{COMPLAINT, CAUSE, CORRECTION} from Grok's text, or None when a section is missing."""
    sec, cur = {}, None
    for raw in (text or "").replace("\r", "").split("\n"):
        hd = _header(raw)
        if hd and hd[0] not in sec:
            cur = hd[0]
            sec[cur] = [hd[1]] if hd[1] else []
            continue
        if cur:
            line = raw.replace("**", "").rstrip()
            if line.lstrip().startswith(("- ", "* ", "• ")):
                line = line.lstrip()[2:]
            sec[cur].append(line)
    out = {h: "\n".join(sec.get(h, [])).strip() for h in HEADERS}
    return out if all(out.values()) else None


def _scrub(t: str) -> str:
    for tag in ("OPEN - ", "OPEN – ", "OPEN: ", "OPEN -", "OPEN:"):
        t = t.replace(tag, "")
    for note in ("not yet performed", "not performed", "pending"):
        while True:
            i = t.lower().find(f"({note})")
            if i < 0:
                break
            t = (t[:i].rstrip() + t[i + len(note) + 2:])
    while "\n\n\n" in t:
        t = t.replace("\n\n\n", "\n\n")
    return t.strip()


def _long_numbers(t: str, n: int = 7) -> list:
    out, run = [], ""
    for ch in t + " ":
        if ch.isdigit():
            run += ch
        else:
            if len(run) >= n:
                out.append(run)
            run = ""
    return out


def check_story(text: str, case: dict, history: list = None) -> str | None:
    """The cleaned story, or None when it fails: a missing section, a correction that is not a recommendation on a
    diagnosis-only job, or a long number (part number) that is nowhere in the session."""
    sec = parse_story(text)
    if not sec:
        return None
    sec = {k: _scrub(v) for k, v in sec.items()}
    if not repair_done(case, history) and "recommend" not in sec["CORRECTION"].lower():
        return None
    source = json.dumps(case or {}, ensure_ascii=False) + " ".join(m.get("content") or "" for m in history or [])
    for num in _long_numbers(" ".join(sec.values())):
        if num not in source:
            return None
    return "\n".join(["COMPLAINT:", sec["COMPLAINT"], "", "CAUSE:", sec["CAUSE"], "", "CORRECTION:", sec["CORRECTION"]])


def write_warranty_story(case: dict, history: list = None, model_text: str = "", chat_fn=None) -> str:
    """The Write-warranty-story button: Grok writes it (chat_fn(messages) -> text), checked; else the state template."""
    case = case or {}
    st = case.get("state") or {}
    if (st.get("story") or "").strip():
        return st["story"].strip()
    if chat_fn is not None and (history or complaint_of(case, history)):
        try:
            ok = check_story(chat_fn(story_messages(case, history, model_text)) or "", case, history)
            if ok:
                return ok
        except Exception:
            pass
    return warranty_story(case, history, model_text)
