"""Saved Guided Diagnostics sessions and the reopen review log.

This module does not import rv_techtrack. Callers pass a SQLAlchemy session
or a connection that accepts text() statements. Messages, facts, case fields,
and cited manual pages stay on the session row. A reopen is a separate log
row flagged for review.
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import text

# rv_techtrack reloads this file when the stamp is not the app version.
MODULE_REVISION = "v4.19.56"

_CITE_RE = re.compile(r"Source:\s*(.+?),\s*page\s+(\d+)", re.I)
_CONCERN_RE = re.compile(r"leak|weep|not cool|freeze|came back|wasn't the fix|not the fix", re.I)

_CHAT_DDL = """
CREATE TABLE IF NOT EXISTS ask_chats (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    category_name VARCHAR(150) DEFAULT '',
    model_text VARCHAR(250) DEFAULT '',
    title VARCHAR(250) DEFAULT '',
    final_story TEXT DEFAULT '',
    created_date DATETIME,
    updated_date DATETIME,
    status VARCHAR(40) DEFAULT 'in_progress',
    concern TEXT DEFAULT '',
    facts_json TEXT DEFAULT '[]',
    cited_json TEXT DEFAULT '[]',
    case_json TEXT DEFAULT '{}'
)
"""

_MESSAGE_DDL = """
CREATE TABLE IF NOT EXISTS ask_messages (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT DEFAULT '',
    created_date DATETIME
)
"""

_LOG_DDL = """
CREATE TABLE IF NOT EXISTS gd_reopen_log (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL,
    user_id INTEGER,
    who_name VARCHAR(150) DEFAULT '',
    reason TEXT DEFAULT '',
    status VARCHAR(40) DEFAULT 'flagged_for_review',
    opened_at DATETIME
)
"""

_CHAT_COLUMNS = (
    ("status", "VARCHAR(40) DEFAULT 'in_progress'"),
    ("concern", "TEXT DEFAULT ''"),
    ("facts_json", "TEXT DEFAULT '[]'"),
    ("cited_json", "TEXT DEFAULT '[]'"),
    ("case_json", "TEXT DEFAULT '{}'"),
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _execute(db, sql, params=None):
    return db.execute(text(sql), params or {})


def _rows(db, sql, params=None) -> list[dict]:
    result = _execute(db, sql, params)
    if hasattr(result, "mappings"):
        return [dict(row) for row in result.mappings()]
    keys = list(result.keys())
    return [dict(zip(keys, row)) for row in result.fetchall()]


def _loads(raw, fallback):
    try:
        return json.loads(raw or "")
    except (TypeError, ValueError):
        return fallback


def ensure_schema(engine) -> None:
    """Create the session tables and add the context columns on an older DB."""
    with engine.connect() as conn:
        conn.exec_driver_sql(_CHAT_DDL)
        conn.exec_driver_sql(_MESSAGE_DDL)
        conn.exec_driver_sql(_LOG_DDL)
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "ask_chats" in tables:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(ask_chats)").fetchall()]
            for name, ddl in _CHAT_COLUMNS:
                if name not in cols:
                    conn.exec_driver_sql(f"ALTER TABLE ask_chats ADD COLUMN {name} {ddl}")
        conn.commit()


def start_chat(
    db,
    user_id: int,
    category_name: str = "",
    model_text: str = "",
    title: str = "",
    status: str = "in_progress",
) -> int:
    now = _now()
    result = _execute(
        db,
        """
        INSERT INTO ask_chats (
            user_id, category_name, model_text, title, final_story,
            created_date, updated_date, status, concern, facts_json, cited_json, case_json
        ) VALUES (
            :uid, :cat, :model, :title, '',
            :now, :now, :status, '', '[]', '[]', '{}'
        )
        """,
        {
            "uid": int(user_id),
            "cat": category_name or "",
            "model": model_text or "",
            "title": title or "Guided Diagnostics",
            "now": now,
            "status": status or "in_progress",
        },
    )
    db.commit()
    return int(result.lastrowid)


def append_message(db, chat_id: int, role: str, content: str) -> None:
    _execute(
        db,
        """
        INSERT INTO ask_messages (chat_id, role, content, created_date)
        VALUES (:cid, :role, :content, :now)
        """,
        {
            "cid": int(chat_id),
            "role": role or "user",
            "content": content or "",
            "now": _now(),
        },
    )
    _execute(
        db,
        "UPDATE ask_chats SET updated_date = :now WHERE id = :cid",
        {"now": _now(), "cid": int(chat_id)},
    )
    db.commit()


def cited_from_messages(messages) -> list[dict]:
    found = []
    seen = set()
    for message in messages or []:
        if (message.get("role") or "") != "assistant":
            continue
        for match in _CITE_RE.finditer(message.get("content") or ""):
            title = match.group(1).strip()
            page = int(match.group(2))
            key = (title.lower(), page)
            if key in seen:
                continue
            seen.add(key)
            found.append({"title": title, "page": page})
    return found


def _brand_from(model_text: str) -> str:
    low = (model_text or "").lower()
    if "thetford" in low or "42070" in low:
        return "Thetford"
    return ""


def _concern_from(messages, existing: str) -> str:
    if (existing or "").strip():
        return existing.strip()
    users = [
        (message.get("content") or "").strip()
        for message in messages or []
        if (message.get("role") or "") == "user" and (message.get("content") or "").strip()
    ]
    for content in users:
        if _CONCERN_RE.search(content):
            return content[:500]
    return (users[0] if users else "")[:500]


def sync_context(db, chat_id: int) -> dict:
    """Store facts, the case, and cited pages from the messages already saved."""
    chats = _rows(db, "SELECT * FROM ask_chats WHERE id = :cid", {"cid": int(chat_id)})
    if not chats:
        return {}
    chat = chats[0]
    messages = _rows(
        db,
        """
        SELECT role, content FROM ask_messages
        WHERE chat_id = :cid ORDER BY id
        """,
        {"cid": int(chat_id)},
    )
    facts = [
        message.get("content") or ""
        for message in messages
        if (message.get("role") or "") == "user"
    ]
    cited = cited_from_messages(messages)
    concern = _concern_from(messages, chat.get("concern") or "")
    case = {
        "category": chat.get("category_name") or "",
        "model": chat.get("model_text") or "",
        "brand": _brand_from(chat.get("model_text") or ""),
        "concern": concern,
    }
    _execute(
        db,
        """
        UPDATE ask_chats
        SET concern = :concern,
            facts_json = :facts,
            cited_json = :cited,
            case_json = :case,
            updated_date = :now
        WHERE id = :cid
        """,
        {
            "concern": concern,
            "facts": json.dumps(facts),
            "cited": json.dumps(cited),
            "case": json.dumps(case),
            "now": _now(),
            "cid": int(chat_id),
        },
    )
    db.commit()
    try:
        db.expire_all()
    except Exception:
        pass
    return {"facts": facts, "cited": cited, "case": case, "concern": concern}


def list_sessions(db, user_id=None) -> list[dict]:
    """Every saved session, including ones marked complete."""
    sql = """
        SELECT id, user_id, category_name, model_text, title, status,
               concern, updated_date, created_date
        FROM ask_chats
    """
    params = {}
    if user_id is not None:
        sql += " WHERE user_id = :uid"
        params["uid"] = int(user_id)
    sql += " ORDER BY updated_date DESC, id DESC"
    rows = _rows(db, sql, params)
    for row in rows:
        if not (row.get("status") or "").strip():
            row["status"] = "in_progress"
    return rows


def load_session(db, chat_id: int) -> dict | None:
    chats = _rows(db, "SELECT * FROM ask_chats WHERE id = :cid", {"cid": int(chat_id)})
    if not chats:
        return None
    chat = chats[0]
    messages = _rows(
        db,
        """
        SELECT role, content FROM ask_messages
        WHERE chat_id = :cid ORDER BY id
        """,
        {"cid": int(chat_id)},
    )
    facts = _loads(chat.get("facts_json"), [])
    cited = _loads(chat.get("cited_json"), [])
    case = _loads(chat.get("case_json"), {})
    if not isinstance(facts, list):
        facts = []
    if not isinstance(cited, list):
        cited = []
    if not isinstance(case, dict):
        case = {}
    return {
        "id": chat.get("id"),
        "user_id": chat.get("user_id"),
        "status": chat.get("status") or "in_progress",
        "title": chat.get("title") or "",
        "category": chat.get("category_name") or "",
        "model": chat.get("model_text") or "",
        "concern": chat.get("concern") or "",
        "messages": messages,
        "facts": facts,
        "cited": cited,
        "case": case,
    }


def mark_complete(db, chat_id: int) -> None:
    _execute(
        db,
        """
        UPDATE ask_chats
        SET status = 'complete', updated_date = :now
        WHERE id = :cid
        """,
        {"now": _now(), "cid": int(chat_id)},
    )
    db.commit()
    try:
        db.expire_all()
    except Exception:
        pass


def record_reopen(db, chat_id: int, user_id, who_name: str, reason: str) -> int | None:
    """Log who reopened the session, when, and why. Flag it for review."""
    chats = _rows(db, "SELECT id FROM ask_chats WHERE id = :cid", {"cid": int(chat_id)})
    if not chats:
        return None
    opened = _now()
    result = _execute(
        db,
        """
        INSERT INTO gd_reopen_log (session_id, user_id, who_name, reason, status, opened_at)
        VALUES (:sid, :uid, :who, :reason, 'flagged_for_review', :opened)
        """,
        {
            "sid": int(chat_id),
            "uid": int(user_id) if user_id else None,
            "who": who_name or "",
            "reason": reason or "",
            "opened": opened,
        },
    )
    _execute(
        db,
        """
        UPDATE ask_chats
        SET status = 'in_progress', updated_date = :now
        WHERE id = :cid
        """,
        {"now": opened, "cid": int(chat_id)},
    )
    db.commit()
    try:
        db.expire_all()
    except Exception:
        pass
    return int(result.lastrowid)


def list_flags(db) -> list[dict]:
    """Reopen rows still flagged for review. Newest first."""
    return _rows(
        db,
        """
        SELECT id, session_id, user_id, who_name, reason, status, opened_at
        FROM gd_reopen_log
        WHERE status = 'flagged_for_review'
        ORDER BY id DESC
        """,
    )


def latest_reason(db, chat_id: int) -> str:
    rows = _rows(
        db,
        """
        SELECT reason FROM gd_reopen_log
        WHERE session_id = :sid
        ORDER BY id DESC
        LIMIT 1
        """,
        {"sid": int(chat_id)},
    )
    if not rows:
        return ""
    return rows[0].get("reason") or ""
