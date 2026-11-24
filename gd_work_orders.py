"""Past work orders for Guided Diagnostics (Chase 2026-10-24 2:51 PM).

A finished or saved GD job is kept as a DiagnosticJob row (table diagnostic_jobs) for WORK_ORDER_RETENTION_DAYS and listed
for the signed-in tech in the GD area, newest first: WO number, status, category, model, complaint, date. Each one downloads
as a self-contained HTML file (opens in any browser and prints to PDF from there): the complaint, the unit, the full chat,
the readings / state summary, the pages and web sources cited, and the technician story. The app has no PDF renderer since
the Bay PDF builder was removed (cleanup 2026-10-24), so the file is HTML.

Row fields (the DiagnosticJob columns, reused from the old work-order flow):
  wo_number      the WO # the tech typed, else "GD-<chat id>"
  status         closed (the job closed in GD) | story written | saved
  category_name, model_text, concern (the complaint)
  step_log       JSON: the full chat [{role, content}]
  findings       JSON: the case state (facts / readings, fault code, pending test, part, cause, repair, summary)
  sources_json   JSON: {"pages": [{doc_id, title, page, sheet}], "web": [{url, title}]}
  sources_text   the same, one line each
  final_story    the technician story
  ask_chat_id    the saved GD chat (ask_chats.id) this work order came from; marks the row as a GD work order
Old rows from the retired WO flow (ask_chat_id empty) are listed too but never purged here.

Pure functions; the app passes its SQLAlchemy session and the DiagnosticJob model. No network.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta

WORK_ORDER_RETENTION_DAYS = 30      # Chase 2026-10-24: 30 days
LIST_LIMIT = 50
STATUS_CLOSED, STATUS_STORY, STATUS_SAVED = "closed", "story written", "saved"
STATE_FIELDS = ("fault_code", "pending_test", "part_working", "cause", "order_part", "recommendation", "help_mode")


def default_wo_number(chat_id) -> str:
    return f"GD-{chat_id}"


def _complaint(history, case):
    if (case or {}).get("complaint"):
        return case["complaint"]
    for m in history or []:
        if (m.get("role") or "") == "user" and (m.get("content") or "").strip():
            return m["content"].strip()
    return ""


def cited_pages(case, cited_log=()):
    """Pages cited in the job: the state's cited list with the read page's title / sheet (gd_turn), else the app's 📖 log."""
    out = []
    try:
        import gd_turn
        if case:
            for c in gd_turn._cited_with_pages((case.get("state") or {}).get("cited") or [], case):
                out.append({k: c.get(k) for k in ("doc_id", "title", "page", "sheet", "url") if c.get(k) not in (None, "")})
    except Exception:
        out = []
    seen = {((c.get("title") or "").lower(), str(c.get("page") or "")) for c in out}
    for c in cited_log or []:
        k = ((c.get("title") or "").lower(), str(c.get("page") or ""))
        if k not in seen:
            seen.add(k)
            out.append({"title": c.get("title") or "", "page": c.get("page")})
    return out


def snapshot(*, history, case=None, category="", model_text="", story="", cited_log=(), wo_number="", chat_id=None):
    """The work-order fields from the GD session (pure). case: the gd_turn case (store['gd_case']) or None."""
    case = case or {}
    state = dict(case.get("state") or {})
    closed = bool(state.get("closed"))
    story = (story or state.get("story") or "").strip()
    unit = case.get("unit") or {}
    pages = cited_pages(case, cited_log)
    web = [{"url": w.get("url"), "title": w.get("title") or ""} for w in case.get("web_sources") or [] if w.get("url")]
    chat = [{"role": m.get("role") or "user", "content": m.get("content") or ""} for m in history or []]
    findings = {k: state[k] for k in ("facts", "summary", "repair", *STATE_FIELDS) if state.get(k) not in (None, "", [], {})}
    lines = [f"{p.get('title') or p.get('doc_id')} - page {p.get('page')}" for p in pages] + [w["url"] for w in web]
    return {"wo_number": (wo_number or "").strip() or (default_wo_number(chat_id) if chat_id else ""),
            "status": STATUS_CLOSED if closed else (STATUS_STORY if story else STATUS_SAVED),
            "category_name": category or unit.get("category") or "", "model_text": model_text or unit.get("model_text") or "",
            "concern": _complaint(history, case), "step_log": json.dumps(chat, ensure_ascii=False),
            "findings": json.dumps(findings, ensure_ascii=False), "sources_json": json.dumps({"pages": pages, "web": web},
                                                                                           ensure_ascii=False, default=str),
            "sources_text": "\n".join(lines), "final_story": story, "plan_text": ""}


def save(session, Job, user_id, chat_id, snap, now=None):
    """Create or update the work order for this GD chat (one row per user + chat). Returns the row, or None when there is
    no saved chat yet. A WO # typed earlier is kept when this save has none of its own."""
    if not chat_id or not (snap.get("step_log") and json.loads(snap["step_log"])):
        return None
    now = now or datetime.now()
    row = session.query(Job).filter_by(user_id=user_id, ask_chat_id=chat_id).first()
    snap = dict(snap)
    if row is None:
        row = Job(user_id=user_id, ask_chat_id=chat_id, created_date=now)
        session.add(row)
    elif row.wo_number and snap.get("wo_number") == default_wo_number(chat_id):
        snap["wo_number"] = row.wo_number
    if row.status == STATUS_CLOSED and snap["status"] != STATUS_CLOSED:
        snap["status"] = STATUS_CLOSED
    empty = {"findings": "{}", "sources_json": json.dumps({"pages": [], "web": []}), "sources_text": "", "final_story": "",
             "concern": "", "category_name": "", "model_text": ""}
    for k, v in snap.items():
        if k in empty and v in (empty[k], None) and getattr(row, k, None):
            continue      # a reopened chat without its case keeps what an earlier save recorded
        setattr(row, k, v)
    row.wo_number = row.wo_number or default_wo_number(chat_id)
    if row.status == STATUS_SAVED and (row.final_story or "").strip():
        row.status = STATUS_STORY
    row.updated_date = now
    session.commit()
    return row


def purge_old(session, Job, days=None, now=None) -> int:
    """Delete GD work orders (ask_chat_id set) last updated more than `days` ago. Returns how many."""
    days = WORK_ORDER_RETENTION_DAYS if days is None else days
    cutoff = (now or datetime.now()) - timedelta(days=days)
    try:
        old = session.query(Job).filter(Job.ask_chat_id.isnot(None), Job.updated_date < cutoff).all()
        for r in old:
            session.delete(r)
        if old:
            session.commit()
        return len(old)
    except Exception:
        session.rollback()
        return 0


def list_jobs(session, Job, user_id, days=None, now=None, limit=LIST_LIMIT):
    """The tech's own work orders inside the retention window, newest first."""
    days = WORK_ORDER_RETENTION_DAYS if days is None else days
    cutoff = (now or datetime.now()) - timedelta(days=days)
    return (session.query(Job).filter(Job.user_id == user_id, Job.updated_date >= cutoff)
            .order_by(Job.updated_date.desc(), Job.id.desc()).limit(limit).all())


def _when(row):
    d = getattr(row, "updated_date", None) or getattr(row, "created_date", None)
    return d.strftime("%Y-%m-%d %I:%M %p") if d else ""


def list_label(row) -> str:
    """'WO 4471 · closed · Furnaces · Suburban NT-20SEQT · blower runs, no heat · 2026-10-24 02:10 PM'"""
    complaint = re.sub(r"\s+", " ", row.concern or "").strip()
    if len(complaint) > 80:
        complaint = complaint[:80].rsplit(" ", 1)[0] + "…"
    return " · ".join([f"WO {row.wo_number}", row.status or "", row.category_name or "-", row.model_text or "-",
                       complaint or "-", _when(row)])


def file_name(row) -> str:
    wo = re.sub(r"[^A-Za-z0-9_-]+", "-", row.wo_number or "GD").strip("-") or "GD"
    d = getattr(row, "updated_date", None) or datetime.now()
    return f"work-order-{wo}-{d.strftime('%Y%m%d')}.html"


def _loads(text, default):
    try:
        v = json.loads(text or "")
        return v if v is not None else default
    except ValueError:
        return default


_CSS = ("body{font-family:Arial,Helvetica,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#111;line-height:1.45}"
        "h1{font-size:22px;margin-bottom:4px}h2{font-size:17px;border-bottom:1px solid #bbb;padding-bottom:3px;margin-top:26px}"
        "table.meta td{padding:2px 12px 2px 0;vertical-align:top}.msg{border:1px solid #ddd;border-radius:6px;padding:8px 10px;"
        "margin:8px 0;white-space:pre-wrap}.tech{background:#f4f7fb}.gd{background:#fff}.who{font-size:12px;color:#555;"
        "font-weight:bold;margin-bottom:3px}.story{white-space:pre-wrap;border:1px solid #999;padding:10px}"
        "@media print{.msg{break-inside:avoid}}")


def render_html(row) -> str:
    """The whole work order as one self-contained HTML page (every value escaped)."""
    e = lambda v: html.escape(str(v if v is not None else ""))
    chat = _loads(row.step_log, [])
    findings = _loads(row.findings, None)
    if not isinstance(findings, dict):     # the old WO flow kept findings as plain text
        findings = {"summary": row.findings} if (row.findings or "").strip() else {}
    src = _loads(row.sources_json, {})
    if isinstance(src, list):          # the old WO flow stored a list of sources
        src = {"pages": src, "web": []}
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>Work order {e(row.wo_number)}</title>"
           f"<style>{_CSS}</style></head><body>",
           f"<h1>Work order {e(row.wo_number)}</h1><p>TechTrack Guided Diagnostics</p>",
           "<table class='meta'>",
           *(f"<tr><td><b>{k}</b></td><td>{e(v)}</td></tr>" for k, v in (
               ("Status", row.status), ("Category", row.category_name or "-"), ("Unit / model", row.model_text or "-"),
               ("Started", row.created_date.strftime("%Y-%m-%d %I:%M %p") if row.created_date else ""),
               ("Last saved", _when(row)))),
           "</table>", "<h2>Complaint</h2>", f"<p>{e(row.concern or '-')}</p>"]
    out.append("<h2>Readings and findings</h2>")
    facts = findings.get("facts") or [] if isinstance(findings, dict) else []
    if facts:
        out.append("<ul>" + "".join(
            f"<li><b>{e(f.get('item'))}</b>: {e(f.get('value'))}" + (f" <i>(tech: “{e(f.get('quote'))}”)</i>" if f.get("quote") else "")
            + "</li>" for f in facts if isinstance(f, dict)) + "</ul>")
    rows = []
    for key, label in (("fault_code", "Fault code"), ("part_working", "Part being worked on"), ("pending_test", "Pending test"),
                       ("cause", "Cause"), ("order_part", "Part to order"), ("recommendation", "Recommended repair"),
                       ("help_mode", "Help asked for")):
        if isinstance(findings, dict) and findings.get(key):
            rows.append(f"<tr><td><b>{label}</b></td><td>{e(findings[key])}</td></tr>")
    rep = findings.get("repair") if isinstance(findings, dict) else None
    if isinstance(rep, dict) and (rep.get("what") or rep.get("done")):
        rows.append(f"<tr><td><b>Repair</b></td><td>{e(rep.get('what') or '')} — done: {'yes' if rep.get('done') else 'no'}, "
                    f"verified: {'yes' if rep.get('verified') else 'no'}" + (f" (“{e(rep.get('quote'))}”)" if rep.get("quote") else "")
                    + "</td></tr>")
    if rows:
        out.append("<table class='meta'>" + "".join(rows) + "</table>")
    if isinstance(findings, dict) and findings.get("summary"):
        out.append(f"<p><b>Summary:</b> {e(findings['summary'])}</p>")
    if not facts and not rows and not findings.get("summary"):
        out.append("<p>None recorded.</p>")
    out.append("<h2>Pages and sources cited</h2>")
    items = [f"<li>{e(p.get('title') or p.get('doc_id'))} — page {e(p.get('page'))}"
             + (f" (sheet {e(p.get('sheet'))})" if p.get("sheet") not in (None, "") else "") + "</li>"
             for p in src.get("pages") or [] if isinstance(p, dict)]
    items += [f"<li>Web: <a href='{e(w.get('url'))}'>{e(w.get('title') or w.get('url'))}</a> — {e(w.get('url'))}</li>"
              for w in src.get("web") or [] if isinstance(w, dict) and w.get("url")]
    out.append("<ul>" + "".join(items) + "</ul>" if items else f"<p>{e(row.sources_text or 'None cited.')}</p>")
    out.append("<h2>Technician story</h2>")
    out.append(f"<div class='story'>{e(row.final_story)}</div>" if (row.final_story or "").strip() else "<p>Not written yet.</p>")
    out.append("<h2>Full chat</h2>")
    for m in chat:
        tech = (m.get("role") or "") == "user"
        text = re.sub(r"<!--\s*gd-step:\d+\s*-->", "", m.get("content") or "").strip()
        out.append(f"<div class='msg {'tech' if tech else 'gd'}'><div class='who'>{'Tech' if tech else 'Guided Diagnostics'}</div>"
                   f"{e(text)}</div>")
    if not chat:
        out.append("<p>No chat saved.</p>")
    out.append("</body></html>")
    return "\n".join(out)
