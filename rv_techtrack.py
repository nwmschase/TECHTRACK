"""
RV TechTrack v4.10.0
- Login + Roles (Technician / Manager)
- Certificate Hub
- Searchable Document Library by Category
- Guided Diagnostics Jobs (WO #) + interactive findings + warranty story
- Diagnostic INDEX charts: match ONE symptom row, expand real PROCEDURE tests in OEM order
- Source page viewer (Jobs WO panel; chat is on-demand only)
- Safety / Compliance + Meeting Acknowledgements
- Team Overview (Certificates + Safety Progress)
- AI Tech Story Improver (xAI Grok, Groq fallback) - standalone + end-of-job
- Guided Diagnostics chat (manuals + Grok/Groq)
- Tacoma RV Center shop branding (logo + colors)
- Permanent file storage via Cloudflare R2
- R2 re-link (recover library without re-upload)
- Library catalog export + manager backup warning
- Auto SQLite backup/restore to R2 (survives Streamlit wipes)
- Guided Diagnostics chats saved 30 days
- Write warranty story remounts the copy box and uses latest tech status
- Guided Diagnostics refuses wrong-brand manuals; TSB / Recall searched with the system category
- Warranty stories include every recorded reading without inventing tests
- Signed login cookie (~10 hours) so a dropped websocket does not force re-login
- Layout fills the screen (no 1200px cap)
- v4.8.2: harden Streamlit CSS so side gutters stay dead on Streamlit Cloud
- v4.8.2: Unity / OneControl CAN multiplex gate + OEM test order + Electrical cross-search
- v4.8.3: collapsed sidebar must not reserve 220px left gap
- v4.8.4: never brand-lock to empty; fridge synonyms + FCR model prefix match
- v4.8.4: fridge no-power OEM order (accessible fuse before teardown)
- v4.8.4: warranty story binds vague tech “pass/good” to coach’s last recommended test
- v4.8.5: coach language attributes excerpts to the shop Document Library - never “the text you uploaded”
- v4.8.5: Guided Diagnostics is a branching flowchart - 1-2 tests per turn, wait for results
- v4.8.5: warranty story cites 📖 Source (manual + page) on each tech-performed step
- v4.8.6: Guided Diagnostics chat does not dump source-page UI every turn
- v4.8.6: show library text/illustration pages ONLY when the tech asks
- v4.8.6: silent source ledger still records cited pages for the warranty story
- v4.8.7: never invent built-in fault/blink LEDs; Furrion FCR flash codes need SM clip-on diagnostic LED (or skip that gate)
- v4.8.8: figure/page requests lock to the cited manual only - never cross-book Fig./page matches
- v4.8.9: never emit markdown/fake images; 📖 Source page must match the claim; only R2 renderer shows photos
- v4.9.0: data-plate photo fills Model/System (camera or upload; uses existing shop AI key)
- v4.9.1: fix library page miss — Source en-dash cites + page-of-manual + DB title fallback for figures
- v4.9.2: rebuild Guided Diagnostics page pipeline — detect→parse→resolve Document/page→R2+pymupdf render
- v4.10.0: Guided Testing flowchart ENGINE — hard procedure trees; TECH reports, tree edges decide next gate
- v4.10.0: Furrion FCR CCD-0008122 tree (fuse→dial/battery→paper→operating?/Not Cooling); no invented fan volts after paper
- Mobile-friendly
"""
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil
import hashlib
import secrets
import io
import re
import json
import base64
import time

try:
    import extra_streamlit_components as stx
    COOKIE_MGR_AVAILABLE = True
except ImportError:
    COOKIE_MGR_AVAILABLE = False

try:
    from itsdangerous import URLSafeTimedSerializer, BadSignature, BadTimeSignature
    ITSDANGEROUS_AVAILABLE = True
except ImportError:
    ITSDANGEROUS_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import boto3
    from botocore.client import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import fitz  # pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ---------------- SHOP BRANDING ----------------
HEADER_GREEN = "#038944"
DEALER_RED = "#DF1F26"
NAVY = "#01147C"
DARKER_GREEN = "#02763A"


def shop_logo_path():
    """Official Tacoma RV Center logo. Prefer assets/ next to this script."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "assets" / "tacoma-rv-logo.png",
        here / "tacoma-rv-logo.png",
        Path.cwd() / "assets" / "tacoma-rv-logo.png",
    ]
    for p in candidates:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


# ---------------- PAGE CONFIG ----------------
_logo_for_icon = shop_logo_path()
st.set_page_config(
    page_title="TechTrack · Tacoma RV Center",
    page_icon=str(_logo_for_icon) if _logo_for_icon else "🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)
st.markdown("""
<style>
    /* Tacoma RV Center shop colors: header green, dealer red, navy */
    header[data-testid="stHeader"] {
        background-color: #038944;
    }
    .stButton > button {
        min-height: 2.6rem;
        font-size: 1.02rem;
        border-radius: 8px;
    }
    button[kind="primary"],
    [data-testid="stBaseButton-primary"],
    .stFormSubmitButton button,
    div[data-testid="stFormSubmitButton"] button {
        background-color: #DF1F26 !important;
        border-color: #9D151A !important;
        color: #ffffff !important;
    }
    button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover,
    .stFormSubmitButton button:hover,
    div[data-testid="stFormSubmitButton"] button:hover {
        background-color: #9D151A !important;
        border-color: #9D151A !important;
        color: #ffffff !important;
    }
    button[kind="secondary"],
    [data-testid="stBaseButton-secondary"] {
        border-color: #038944 !important;
        color: #02763A !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px;
    }
    /* v4.8.2 - kill Streamlit side gutters / 730-1200px content box */
    html, body, [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    .stApp, section.main {
        max-width: 100% !important;
    }
    .block-container,
    [data-testid="stMainBlockContainer"],
    [data-testid="stAppViewContainer"] > .main > .block-container,
    section.main > div.block-container,
    .main .block-container {
        max-width: none !important;
        width: 100% !important;
        padding-top: 2.4rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 1.25rem !important;
        padding-right: 1.25rem !important;
    }
    [data-testid="stSidebar"] ~ section.main,
    [data-testid="stAppViewContainer"] section.main {
        max-width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"] {
        margin-top: 0.55rem;
        margin-bottom: 0.3rem;
    }
    [data-testid="stTabs"] button {
        font-size: 1rem;
        font-weight: 600;
        white-space: nowrap;
    }
    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #038944 !important;
    }
    /* v4.8.3 - collapsed sidebar must not reserve flex width */
    section[data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 220px;
    }
    section[data-testid="stSidebar"][aria-expanded="false"] {
        min-width: 0 !important;
        width: 0 !important;
        max-width: 0 !important;
        flex: 0 0 0px !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        border: none !important;
        transform: translateX(-100%) !important;
    }
    section[data-testid="stSidebar"][aria-expanded="false"] > * {
        min-width: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
    }
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMain"],
    section.main {
        margin-left: 0 !important;
        flex: 1 1 100% !important;
        width: 100% !important;
        max-width: 100% !important;
    }
    h1, h2, h3 {
        color: #01147C;
    }
</style>
""", unsafe_allow_html=True)

# ---------------- CONFIG ----------------
DB_PATH = "rv_techtrack_v4.db"
R2_DB_KEY = "backups/rv_techtrack_v4.db"
R2_DB_PREV_KEY = "backups/rv_techtrack_v4.prev.db"
MIN_DOCS_TO_BACKUP = 10
BACKUP_DEBOUNCE_SEC = 90
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# ---------------- R2 STORAGE ----------------
def get_r2_client():
    if not BOTO3_AVAILABLE:
        return None
    try:
        needed = ["R2_ENDPOINT_URL", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]
        if any(k not in st.secrets for k in needed):
            return None
        return boto3.client(
            "s3",
            endpoint_url=st.secrets["R2_ENDPOINT_URL"],
            aws_access_key_id=st.secrets["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["R2_SECRET_ACCESS_KEY"],
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    except Exception:
        return None


def r2_upload(file_obj, key: str, content_type: str = "application/octet-stream") -> bool:
    client = get_r2_client()
    if not client:
        return False
    try:
        client.put_object(
            Bucket=st.secrets["R2_BUCKET_NAME"],
            Key=key,
            Body=file_obj,
            ContentType=content_type,
        )
        return True
    except Exception as e:
        st.error(f"Upload to storage failed: {e}")
        return False


def r2_download_bytes(key: str):
    client = get_r2_client()
    if not client or not key:
        return None
    try:
        obj = client.get_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=key)
        return obj["Body"].read()
    except Exception:
        return None


def r2_download_button(label: str, key: str, filename: str, button_key: str):
    data = r2_download_bytes(key)
    if data is None:
        st.caption("Storage not configured" if not get_r2_client() else "Could not download file")
        return
    st.download_button(label, data=data, file_name=filename, key=button_key)


def r2_available() -> bool:
    return get_r2_client() is not None and "R2_BUCKET_NAME" in st.secrets


def r2_list_keys(prefix: str = "", max_keys: int = 500):
    """List object keys in the R2 bucket under prefix."""
    client = get_r2_client()
    if not client:
        return [], "Storage not configured"
    keys = []
    try:
        token = None
        while len(keys) < max_keys:
            kwargs = {
                "Bucket": st.secrets["R2_BUCKET_NAME"],
                "Prefix": prefix or "",
                "MaxKeys": min(1000, max_keys - len(keys)),
            }
            if token:
                kwargs["ContinuationToken"] = token
            resp = client.list_objects_v2(**kwargs)
            for item in resp.get("Contents") or []:
                k = item.get("Key") or ""
                if k and not k.endswith("/"):
                    keys.append(k)
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return keys, ""
    except Exception as e:
        return [], f"Could not list storage: {e}"


def r2_key_already_registered(key: str) -> bool:
    if session.query(Document).filter_by(file_path=key).first():
        return True
    if session.query(Certificate).filter_by(file_path=key).first():
        return True
    if session.query(SafetyDocument).filter_by(file_path=key).first():
        return True
    if session.query(SafetyMeeting).filter_by(file_path=key).first():
        return True
    return False


def guess_title_from_key(key: str) -> str:
    name = key.split("/")[-1]
    name = re.sub(r"^\d+_\d+_", "", name)
    name = re.sub(r"^[a-f0-9]{8,}_", "", name, flags=re.I)
    name = re.sub(r"\.[^.]+$", "", name)
    name = name.replace("_", " ").replace("-", " ").strip()
    return name or key


def export_library_catalog() -> str:
    """JSON catalog of documents so titles/keywords survive even if DB is lost."""
    cats = {c.id: c.name for c in session.query(Category).all()}
    rows = []
    for d in session.query(Document).order_by(Document.id).all():
        rows.append({
            "id": d.id,
            "title": d.title,
            "keywords": d.keywords,
            "category": cats.get(d.category_id, ""),
            "category_id": d.category_id,
            "file_path": d.file_path,
            "file_type": d.file_type,
            "indexed": bool(d.indexed),
        })
    return json.dumps({"exported_at": datetime.now().isoformat(), "documents": rows}, indent=2)

# ---------------- DATABASE MODELS ----------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(String(20), default="Technician")
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=func.now())


class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), unique=True, nullable=False)


class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    title = Column(String(250), nullable=False)
    file_path = Column(String(400), nullable=False)
    file_type = Column(String(20), default="pdf")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())
    keywords = Column(Text, default="")
    indexed = Column(Boolean, default=False)
    index_note = Column(String(250), default="")


class DocChunk(Base):
    __tablename__ = "doc_chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    title = Column(String(250), default="")
    page = Column(Integer, default=1)
    chunk_text = Column(Text, nullable=False)
    keywords = Column(Text, default="")


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(250), nullable=False)
    issuer = Column(String(150), default="")
    file_path = Column(String(400), nullable=False)
    issued_date = Column(String(50), default="")
    notes = Column(Text, default="")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())


class SafetyDocument(Base):
    __tablename__ = "safety_documents"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    file_path = Column(String(400), nullable=False)
    file_type = Column(String(20), default="pdf")
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())
    keywords = Column(Text, default="")


class SafetyMeeting(Base):
    __tablename__ = "safety_meetings"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    meeting_date = Column(String(50), default="")
    file_path = Column(String(400), default="")
    notes = Column(Text, default="")
    created_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())


class SafetyAcknowledgement(Base):
    __tablename__ = "safety_acknowledgements"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("safety_meetings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    signed_at = Column(DateTime, default=func.now())
    understood = Column(Boolean, default=True)


class DiagnosticJob(Base):
    """Work-order based diagnostic session - resume anytime, story at end."""
    __tablename__ = "diagnostic_jobs"
    id = Column(Integer, primary_key=True)
    wo_number = Column(String(80), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_name = Column(String(150), default="")
    model_text = Column(String(250), default="")
    concern = Column(Text, default="")
    plan_text = Column(Text, default="")
    findings = Column(Text, default="")
    step_log = Column(Text, default="[]")
    sources_text = Column(Text, default="")
    sources_json = Column(Text, default="[]")
    final_story = Column(Text, default="")
    status = Column(String(30), default="in_progress")
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())


class AskChat(Base):
    """Saved Ask TechTrack conversation (30-day retention)."""
    __tablename__ = "ask_chats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_name = Column(String(150), default="")
    model_text = Column(String(250), default="")
    title = Column(String(250), default="")
    final_story = Column(Text, default="")
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())


class AskMessage(Base):
    __tablename__ = "ask_messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("ask_chats.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, default="")
    created_date = Column(DateTime, default=func.now())


Base.metadata.create_all(engine)
session = Session()


def _ensure_schema_upgrades():
    try:
        with engine.connect() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documents)").fetchall()]
            if "indexed" not in cols:
                conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN indexed BOOLEAN DEFAULT 0")
            if "index_note" not in cols:
                conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN index_note VARCHAR(250)")
            job_cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(diagnostic_jobs)").fetchall()]
            if "sources_json" not in job_cols:
                conn.exec_driver_sql("ALTER TABLE diagnostic_jobs ADD COLUMN sources_json TEXT")
            conn.commit()
    except Exception:
        pass


_ensure_schema_upgrades()


def _local_doc_count() -> int:
    try:
        return session.query(Document).count()
    except Exception:
        return 0


def _reopen_db():
    global engine, session
    try:
        session.close()
    except Exception:
        pass
    try:
        engine.dispose()
    except Exception:
        pass
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Session.configure(bind=engine)
    session = Session()
    _ensure_schema_upgrades()


def maybe_restore_db_from_r2() -> bool:
    """If Streamlit wiped the local DB, pull the last good copy from R2."""
    if not r2_available():
        return False
    local_n = _local_doc_count()
    if local_n >= MIN_DOCS_TO_BACKUP:
        return False
    data = r2_download_bytes(R2_DB_KEY)
    if not data or len(data) < 50000 or not data.startswith(b"SQLite format 3"):
        return False
    try:
        if Path(DB_PATH).exists():
            shutil.copy(DB_PATH, DB_PATH + ".pre_restore")
        with open(DB_PATH, "wb") as f:
            f.write(data)
        _reopen_db()
        restored_n = _local_doc_count()
        if restored_n < max(local_n, 1):
            if Path(DB_PATH + ".pre_restore").exists():
                shutil.copy(DB_PATH + ".pre_restore", DB_PATH)
                _reopen_db()
            return False
        try:
            st.session_state["_db_restored_from_r2"] = True
            st.session_state["_db_restored_docs"] = restored_n
        except Exception:
            pass
        return True
    except Exception:
        return False


def maybe_backup_db_to_r2(force: bool = False):
    """Upload the full SQLite file to R2. Never overwrite a good cloud copy with an empty local DB."""
    if not r2_available():
        return False, "Storage not configured"
    local_n = _local_doc_count()
    if local_n < MIN_DOCS_TO_BACKUP:
        return False, "Local library too small to overwrite the cloud backup"
    if not Path(DB_PATH).exists():
        return False, "No local database file"
    now = time.time()
    try:
        last = float(st.session_state.get("_db_backup_ts") or 0)
        last_mtime = float(st.session_state.get("_db_backup_mtime") or 0)
    except Exception:
        last, last_mtime = 0.0, 0.0
    if not force and (now - last) < BACKUP_DEBOUNCE_SEC:
        return False, "Recently saved"
    mtime = Path(DB_PATH).stat().st_mtime
    if not force and last_mtime and mtime <= last_mtime:
        return False, "No database changes"
    client = get_r2_client()
    if not client:
        return False, "Storage not configured"
    try:
        try:
            client.copy_object(
                Bucket=st.secrets["R2_BUCKET_NAME"],
                CopySource={"Bucket": st.secrets["R2_BUCKET_NAME"], "Key": R2_DB_KEY},
                Key=R2_DB_PREV_KEY,
            )
        except Exception:
            pass
        tmp = DB_PATH + ".r2snap"
        import sqlite3
        src_con = sqlite3.connect(DB_PATH)
        dst_con = sqlite3.connect(tmp)
        with dst_con:
            src_con.backup(dst_con)
        dst_con.close()
        src_con.close()
        with open(tmp, "rb") as f:
            ok = r2_upload(f.read(), R2_DB_KEY, "application/x-sqlite3")
        try:
            os.remove(tmp)
        except OSError:
            pass
        if ok:
            try:
                st.session_state["_db_backup_ts"] = now
                st.session_state["_db_backup_mtime"] = mtime
                st.session_state["_db_backup_ok"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.session_state["_db_backup_docs"] = local_n
            except Exception:
                pass
            return True, f"Saved {local_n} documents to cloud"
        return False, "Upload failed"
    except Exception as e:
        return False, str(e)


def purge_old_ask_chats(days: int = 30):
    try:
        cutoff = datetime.now() - timedelta(days=days)
        old = session.query(AskChat).filter(AskChat.updated_date < cutoff).all()
        for chat in old:
            session.query(AskMessage).filter_by(chat_id=chat.id).delete()
            session.delete(chat)
        if old:
            session.commit()
    except Exception:
        session.rollback()


def load_ask_chat(chat_id: int):
    chat = session.query(AskChat).get(chat_id)
    if not chat:
        return None, []
    msgs = (
        session.query(AskMessage)
        .filter_by(chat_id=chat.id)
        .order_by(AskMessage.id)
        .all()
    )
    history = [{"role": m.role, "content": m.content or ""} for m in msgs]
    return chat, history


def persist_ask_turn(user_id: int, chat_id, category_name: str, model_text: str, user_msg: str, reply: str):
    """Create or update a saved Ask TechTrack chat and append this turn."""
    chat = session.query(AskChat).get(chat_id) if chat_id else None
    if not chat:
        title = (user_msg or "Guided Diagnostics").strip().replace("\n", " ")[:80]
        chat = AskChat(
            user_id=user_id,
            category_name=category_name or "",
            model_text=model_text or "",
            title=title or "Guided Diagnostics",
        )
        session.add(chat)
        session.commit()
    else:
        chat.updated_date = datetime.now()
        if category_name:
            chat.category_name = category_name
        if model_text:
            chat.model_text = model_text
    session.add(AskMessage(chat_id=chat.id, role="user", content=user_msg or ""))
    session.add(AskMessage(chat_id=chat.id, role="assistant", content=reply or ""))
    session.commit()
    return chat.id


# ---------------- AUTH HELPERS ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except Exception:
        return False



AUTH_COOKIE_NAME = "tt_auth"
AUTH_COOKIE_HOURS = 10


def _auth_serializer():
    secret = _secret("AUTH_COOKIE_SECRET")
    if not secret or not ITSDANGEROUS_AVAILABLE:
        return None
    return URLSafeTimedSerializer(str(secret), salt="techtrack-auth-v1")


def _issue_auth_token(user_row) -> str:
    ser = _auth_serializer()
    if not ser:
        return ""
    return ser.dumps({
        "id": int(user_row.id),
        "username": user_row.username,
        "role": user_row.role,
    })


def _load_auth_token(token: str):
    ser = _auth_serializer()
    if not ser or not token:
        return None
    try:
        data = ser.loads(token, max_age=AUTH_COOKIE_HOURS * 3600)
    except (BadSignature, BadTimeSignature, Exception):
        return None
    if not isinstance(data, dict) or "id" not in data or "username" not in data:
        return None
    row = session.query(User).filter_by(id=int(data["id"]), is_active=True).first()
    if not row or row.username != data.get("username"):
        return None
    return {
        "id": row.id,
        "username": row.username,
        "full_name": row.full_name,
        "role": row.role,
    }


def _cookie_manager():
    """Instantiate every run with a stable key so the browser component can hydrate."""
    if not COOKIE_MGR_AVAILABLE:
        return None
    try:
        return stx.CookieManager(key="tt_cookie_mgr")
    except Exception:
        return None


def _cookie_get(mgr, name: str) -> str:
    if not mgr:
        return ""
    try:
        # get_all() forces the browser component to send cookies on the next run
        bag = mgr.get_all() or {}
        val = bag.get(name) if isinstance(bag, dict) else None
        if val is None:
            val = mgr.get(name)
    except Exception:
        return ""
    return val if isinstance(val, str) else ""


def _cookie_set_auth(mgr, token: str):
    if not mgr or not token:
        return
    try:
        mgr.set(
            AUTH_COOKIE_NAME,
            token,
            expires_at=datetime.now() + timedelta(hours=AUTH_COOKIE_HOURS),
            same_site="lax",
            secure=True,
            key="tt_set_auth",
        )
    except Exception:
        pass


def _cookie_clear_auth(mgr):
    if not mgr:
        return
    try:
        mgr.delete(AUTH_COOKIE_NAME, key="tt_del_auth")
    except Exception:
        pass


def get_safety_progress(user_id: int) -> float:
    meetings = session.query(SafetyMeeting).count()
    if meetings == 0:
        return 100.0
    signed = (
        session.query(SafetyAcknowledgement)
        .filter_by(user_id=user_id)
        .count()
    )
    return round(100.0 * signed / meetings, 1)

# ---------------- AI CLIENT (xAI Grok preferred, Groq fallback) ----------------
def _secret(name: str):
    """Read a Streamlit secret, then an env var."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def ai_available() -> bool:
    return bool(_secret("XAI_API_KEY") or (GROQ_AVAILABLE and _secret("GROQ_API_KEY")))


def ai_chat(messages, temperature=0.2, max_tokens=1400) -> str:
    """One chat completion. Prefer xAI Grok; fall back to Groq. Retrieval/RAG is unchanged."""
    errors = []
    xai_key = _secret("XAI_API_KEY")
    if xai_key and OPENAI_AVAILABLE:
        try:
            client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
            model = _secret("XAI_MODEL") or "grok-4.6"
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            errors.append(f"xAI: {e}")
    groq_key = _secret("GROQ_API_KEY")
    if GROQ_AVAILABLE and groq_key:
        try:
            client = Groq(api_key=groq_key)
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            errors.append(f"Groq: {e}")
    if errors:
        raise RuntimeError(" | ".join(errors))
    raise RuntimeError("No AI key configured. Add XAI_API_KEY (preferred) or GROQ_API_KEY in Streamlit secrets.")


def _image_to_data_url(image_bytes: bytes, mime: str = "image/jpeg") -> str:
    mime = (mime or "image/jpeg").split(";")[0].strip() or "image/jpeg"
    b64 = base64.b64encode(image_bytes or b"").decode("ascii")
    return f"data:{mime};base64,{b64}"


def read_data_plate_from_image(image_bytes: bytes, mime: str = "image/jpeg") -> dict:
    """Read brand + model from a data-plate photo using the shop's existing AI key (no extra paid OCR service)."""
    if not image_bytes:
        return {"ok": False, "error": "No photo provided.", "brand": "", "model": "", "raw": ""}
    if not ai_available():
        return {
            "ok": False,
            "error": "AI is offline. Add the shop AI key in Streamlit secrets, or type the model by hand.",
            "brand": "",
            "model": "",
            "raw": "",
        }
    prompt = (
        "You are reading an RV appliance data plate / rating label photo for a shop tech. "
        "Extract the manufacturer BRAND and the MODEL number/string exactly as printed. "
        "Return ONLY compact JSON with keys brand, model, notes. "
        "model should be the full model token (example FCR10DCGTA). "
        "If unreadable, set brand and model to empty strings and explain in notes. "
        "No markdown fences."
    )
    data_url = _image_to_data_url(image_bytes, mime)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]
    errors = []
    raw = ""
    xai_key = _secret("XAI_API_KEY")
    if xai_key and OPENAI_AVAILABLE:
        try:
            client = OpenAI(api_key=xai_key, base_url="https://api.x.ai/v1")
            model = _secret("XAI_MODEL") or "grok-4.6"
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
                max_tokens=400,
            )
            raw = (response.choices[0].message.content or "").strip()
        except Exception as e:
            errors.append(f"xAI vision: {e}")
    if not raw:
        groq_key = _secret("GROQ_API_KEY")
        if GROQ_AVAILABLE and groq_key:
            try:
                # Groq vision model when available; if it fails, surface the error.
                client = Groq(api_key=groq_key)
                vision_model = _secret("GROQ_VISION_MODEL") or "meta-llama/llama-4-scout-17b-16e-instruct"
                response = client.chat.completions.create(
                    model=vision_model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=400,
                )
                raw = (response.choices[0].message.content or "").strip()
            except Exception as e:
                errors.append(f"Groq vision: {e}")
    if not raw:
        return {
            "ok": False,
            "error": " | ".join(errors) if errors else "Could not read the plate photo.",
            "brand": "",
            "model": "",
            "raw": "",
        }
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    brand = ""
    model_out = ""
    try:
        data = json.loads(cleaned)
        brand = str(data.get("brand") or "").strip()
        model_out = str(data.get("model") or "").strip()
    except Exception:
        # Fallback: pull a model-looking token
        m = re.search(r"model[\"'\s:]+([A-Za-z0-9][A-Za-z0-9\-]{3,})", cleaned, re.I)
        if m:
            model_out = m.group(1).strip()
        b = re.search(r"brand[\"'\s:]+([A-Za-z][A-Za-z0-9 \-]{1,40})", cleaned, re.I)
        if b:
            brand = b.group(1).strip().strip(',"\'')
    if not model_out and not brand:
        return {
            "ok": False,
            "error": "Could not read a model from that photo. Try a sharper shot of the plate, or type it.",
            "brand": "",
            "model": "",
            "raw": raw[:500],
        }
    return {"ok": True, "error": "", "brand": brand, "model": model_out, "raw": raw[:500]}


def apply_plate_read_to_model_key(model_key: str, image_file, button_key: str):
    """Shared UI: read plate photo into a Streamlit text_input key."""
    if image_file is None:
        return
    if not st.button("Read plate into Model", type="secondary", key=button_key):
        return
    raw = image_file.getvalue() if hasattr(image_file, "getvalue") else image_file
    mime = getattr(image_file, "type", None) or "image/jpeg"
    with st.spinner("Reading data plate…"):
        result = read_data_plate_from_image(raw, mime)
    if not result.get("ok"):
        st.warning(result.get("error") or "Could not read plate.")
        return
    brand = (result.get("brand") or "").strip()
    model = (result.get("model") or "").strip()
    filled = model
    if brand and model and brand.lower() not in model.lower():
        filled = f"{brand} {model}".strip()
    elif brand and not model:
        filled = brand
    st.session_state[model_key] = filled
    st.success(f"Model set to: {filled}")
    st.rerun()


# ---------------- AI STORY ----------------
def _notes_say_incomplete(text: str) -> bool:
    """True only if the latest status language is still open.

    Midway Guided Diagnostics chats type "No repair yet" then later record the
    real fix. Matching ANY "no repair" in the transcript would lock every later
    Write-warranty-story click on the OPEN / no-repair template.
    """
    t = (text or "").lower()
    incomplete_markers = (
        "no fix yet", "not repaired", "not repaired yet", "unit not repaired",
        "not fixed", "no repair", "still open", "handoff", "hold this info",
        "not finished", "incomplete", "left off", "pick up", "will press button",
        "need warranty story",
    )
    complete_markers = (
        "job complete",
        "repair completed",
        "replaced the",
        "compressor started",
        "compressor ran",
        "returned to service",
    )
    last_incomplete = max(t.rfind(m) for m in incomplete_markers)
    last_complete = max(t.rfind(m) for m in complete_markers)
    if last_complete > last_incomplete:
        return False
    return last_incomplete >= 0


def improve_tech_story(concern: str, tech_notes: str, status_text=None) -> str:
    """Write a warranty narrative or an open-job handoff. Never invent tests or a completed repair."""
    concern = (concern or "").strip()
    tech_notes = (tech_notes or "").strip()
    # status_text should be TECH-reported lines only (not coach suggestions).
    incomplete = _notes_say_incomplete(
        status_text if status_text is not None else tech_notes
    )
    if not ai_available():
        if incomplete:
            return (
                f"**CONCERN**\n{concern or 'Customer reported an issue requiring diagnosis.'}\n\n"
                f"**TESTING PERFORMED**\n{tech_notes or 'See technician notes.'}\n\n"
                "**STATUS**\nOpen. No repair completed. Next tech: resume from testing performed. "
                "Do not treat recommended checks as done."
            )
        return (
            f"**CONCERN**\n{concern or 'Customer reported an issue requiring diagnosis and repair.'}\n\n"
            f"**TESTING / FINDINGS**\n{tech_notes or 'See technician notes.'}\n\n"
            "**CAUSE**\nOnly as stated in the technician notes. If no root cause was recorded, leave unknown.\n\n"
            "**CORRECTION**\nOnly repairs the technician recorded. If none were recorded, none were performed."
        )
    try:
        system_prompt = """You write shop documentation for RV warranty claims (Lippert, Dometic, Furrion, etc.).

HARD RULES - facts (violating any of these is a failed write-up):
1. Use ONLY facts the TECHNICIAN recorded as already done or measured. Coach/AI recommended tests are NOT performed work unless the tech later said they did that exact test and reported a result.
2. NEVER invent voltages, ohm readings, parts, corrosion, failed fuses, connector damage, reset buttons pressed, photos taken, or a completed repair.
3. NEVER write that the unit was repaired, corrected, restored, returned to service, or fully functional unless the tech explicitly said the repair was done and the unit works.
4. Decide OPEN vs complete from the LATEST technician status. An earlier "no repair yet" / "need warranty story" / handoff does NOT override a later recorded repair (replaced / job complete / compressor ran). Only if the latest status is still open: do NOT write a completed CAUSE or CORRECTION. Write a handoff log instead.
5. Do not turn "I will press the Write warranty story button" into a controller reset or any shop-floor button press.
6. You may clean up grammar. You may NOT add tests, parts, or steps that were not recorded.

HARD RULES - writing quality (a thin checklist that drops readings is also a failed write-up):
7. Include EVERY recorded test, location, and reading. If the tech wrote 13.8 V at the converter, 13.5 V at the controller, 12.8 V at the display, a 1.0 V drop, or continuity - those numbers MUST appear. Do not collapse several measurements into "voltage checked OK."
8. After each reading, add one short interpretation grounded only in that number and what the tech said it meant. Example: "13.8 V at the converter is supply/charging voltage; a 1.0 V drop to the display is more than a healthy short run of wire usually shows." Do not invent a spec chart the tech did not record.
9. Write chronological shop paragraphs, not a one-line bullet dump. Short paragraphs are fine. Sentence fragments that drop the numbers are not.
10. Cite a manual only if the tech or the notes already named that source. Do not invent page numbers.
11. Professional warranty tone. No fluff, no first-person diary, no "I then proceeded to."
12. PASS-BIND: If the coach recommended a specific test (location + expected threshold/action) and the technician later replied with only a vague pass ("good", "done", "pass", "step 2 good", "voltage good", "completed test"), write a clean professional line bound to THAT exact check. Example: coach said measure at the front-vent fuse / supply and expect ≥11.3 V, tech said "voltage good" → write that voltage was checked at that location and confirmed at/above the stated threshold. Do NOT leave "completed voltage test, it was good." Do NOT invent a numeric reading the tech did not give (do not invent 12.6 V). Using the coach's stated threshold as the pass criterion is allowed when the tech only said good/pass. Do NOT invent pins, parts, or steps the coach never asked for.
13. SOURCE CITE: For every test the technician reported as done, write it in order with the reading/result. When the coach cited 📖 Source: [manual title] - page [N] for that check (or the notes include that title + page), put the same citation on that story paragraph. Prefer binding the tech result to the matching coach step AND carry that step's source into TESTING / CAUSE. Do not invent page numbers. If no source was cited for a tech-reported check, write the fact without a fake citation. Open jobs stay handoff-only; still cite sources on tests that were actually performed.

IF THE JOB IS OPEN / NOT REPAIRED, use EXACTLY this structure:
CONCERN
(Restate the customer symptom in one or two complete sentences. Do not add unstated details.)

TESTING PERFORMED
(Full paragraphs covering every recorded test and reading, in the order they were done, with the interpretation rule above. Do not omit a number.)

STATUS
Open. No repair completed.
Next tech: [where they left off, using only recorded facts].

IF THE JOB IS COMPLETE (tech said they repaired it), use EXACTLY this structure:
CONCERN
(Restate the customer symptom.)

CAUSE
(Only if the tech stated a root cause. Otherwise write: Not confirmed.)
Include the testing narrative and every recorded reading that supports the cause. Do not invent a cause from a recommended-but-untested theory.

CORRECTION
(Only the repair steps the tech said they performed. No extra typical steps.)
"""

        status_line = (
            "JOB STATUS: OPEN / NOT REPAIRED (latest tech status). Write the handoff structure. Do not invent a cause or a fix."
            if incomplete
            else (
                "JOB STATUS: Write a completed warranty story ONLY if the notes clearly say a repair was performed. "
                "If they do not, treat it as OPEN. If a later tech message recorded a repair, do not keep the job "
                "OPEN because an earlier message said no repair yet."
            )
        )
        user_prompt = f"""CUSTOMER CONCERN:
{concern or '(not provided)'}

TECHNICIAN NOTES (tech-reported facts only unless labeled otherwise):
{tech_notes or '(not provided)'}

{status_line}

Write the document now."""

        return ai_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=1600,
        )
    except Exception as e:
        return f"Error contacting AI: {e}\n\nConcern: {concern}\nNotes: {tech_notes}"


def story_from_diagnostic_job(job: "DiagnosticJob") -> str:
    """Merge concern + diagnostic plan context + findings into warranty story."""
    notes_parts = []
    if job.model_text:
        notes_parts.append(f"Model/System: {job.model_text}")
    if job.category_name:
        notes_parts.append(f"Category: {job.category_name}")
    if job.findings:
        notes_parts.append("Technician findings and work performed:\n" + job.findings)
    try:
        steps = json.loads(job.step_log or "[]")
        if steps:
            lines = []
            for s in steps:
                line = f"- {s.get('test','')}: {s.get('result','')}"
                if s.get("notes"):
                    line += f" ({s.get('notes')})"
                lines.append(line)
            notes_parts.append("Diagnostic step log:\n" + "\n".join(lines))
    except Exception:
        pass
    if job.plan_text:
        notes_parts.append(
            "NOT PERFORMED unless also listed above - this was only the suggested test plan, do not copy it into CORRECTION:\n"
            + (job.plan_text or "")[:800]
        )
    tech_notes = "\n\n".join(notes_parts).strip()
    return improve_tech_story(job.concern or "", tech_notes)

# ---------------- PDF INDEXING ----------------
def extract_pdf_pages(file_bytes: bytes):
    if not PYPDF_AVAILABLE:
        return []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for i, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            if text.strip():
                pages.append((i, text))
        return pages
    except Exception:
        return []


def chunk_page_text(page_num: int, text: str, chunk_size: int = 900, overlap: int = 120):
    if len(text) <= chunk_size:
        return [(page_num, text)]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append((page_num, piece))
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def clear_document_chunks(document_id: int):
    session.query(DocChunk).filter_by(document_id=document_id).delete()
    session.commit()


def index_document_from_bytes(doc: Document, file_bytes: bytes):
    clear_document_chunks(doc.id)
    if (doc.file_type or "").lower() != "pdf":
        doc.indexed = False
        doc.index_note = "Only PDF files are indexed for guided diagnostics"
        session.commit()
        return False, doc.index_note
    if not PYPDF_AVAILABLE:
        doc.indexed = False
        doc.index_note = "pypdf not installed on server"
        session.commit()
        return False, doc.index_note
    pages = extract_pdf_pages(file_bytes)
    if not pages:
        doc.indexed = False
        doc.index_note = "No extractable text (scanned PDF may need OCR)"
        session.commit()
        return False, doc.index_note
    count = 0
    for page_num, page_text in pages:
        for p, chunk in chunk_page_text(page_num, page_text):
            session.add(DocChunk(
                document_id=doc.id,
                category_id=doc.category_id,
                title=doc.title,
                page=p,
                chunk_text=chunk,
                keywords=doc.keywords or "",
            ))
            count += 1
    doc.indexed = True
    doc.index_note = f"Indexed {count} chunks from {len(pages)} pages"
    session.commit()
    return True, doc.index_note


def index_document_from_r2(doc: Document):
    data = r2_download_bytes(doc.file_path)
    if not data:
        doc.indexed = False
        doc.index_note = "Could not download file from storage"
        session.commit()
        return False, doc.index_note
    return index_document_from_bytes(doc, data)

# ---------------- MANUAL SEARCH + INDEX EXPANSION ----------------
def tokenize(text: str):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2]


def model_search_terms(model_text: str) -> set:
    """Expand FCR10DCGTA-BL into fcr10dcgta, fcr10, fcr10dc, etc. Never emit bare 'fcr'."""
    out = set()
    raw = (model_text or "").strip().lower()
    if not raw:
        return out
    for chunk in re.split(r"[\s_/]+", raw):
        for piece in chunk.split("-"):
            alnum = re.sub(r"[^a-z0-9]", "", piece)
            if len(alnum) < 4:
                continue
            out.add(alnum)
            m = re.match(r"([a-z]{2,}\d{2,})", alnum)
            if not m:
                continue
            root = m.group(1)
            out.add(root)
            for n in range(len(root) + 1, len(alnum)):
                out.add(alnum[:n])
    return out


def is_fridge_context(category_name: str = "", model_text: str = "", symptom: str = "") -> bool:
    cat = (category_name or "").lower()
    if "refriger" in cat:
        return True
    blob = f"{category_name or ''} {model_text or ''} {symptom or ''}".lower()
    if any(w in blob for w in ("fridge", "reefer", "refrigerator", "fcr0", "fcr1")):
        return True
    if "norcold" in blob:
        return True
    if "furrion fcr" in blob or re.search(r"\bfcr\d", blob):
        return True
    if "dometic rm" in blob or re.search(r"\brm\d{3,}", blob):
        return True
    if "12v" in blob and any(w in blob for w in ("fridge", "refrigerator", "reefer")):
        return True
    return False


PAGE_REF_RE = re.compile(r"page\s*0*(\d+)", re.I)

PROCEDURE_TOPIC_TERMS = [
    "ventilation", "leveling", "level", "ambient", "air leak", "thermistor",
    "cooling unit", "heating element", "heater", "igniter", "electrode",
    "high voltage", "solenoid", "orifice", "flue baffle", "flue tube", "burner",
    "upper circuit board", "lower circuit board", "control board", "fuse",
    "wiring", "dc volt", "ac volt", "lp gas", "propane", "manual gas",
    "door seal", "frame heater", "climate control", "diagnostic mode",
    "error code", "fault code", "sequence of operation", "ohms", "voltage",
    "sail switch", "sail", "limit switch", "high limit", "thermostat bypass",
    "blower", "airflow",
]


def is_diagnostic_index_text(text: str) -> bool:
    t = (text or "").lower()
    if not t or len(t) < 80:
        return False
    page_hits = len(PAGE_REF_RE.findall(t))
    if "section & page" in t or "section and page" in t:
        return True
    if "symptom" in t and "cause" in t and page_hits >= 2:
        return True
    if page_hits >= 4 and any(
        s in t for s in ("no operation", "insufficient cooling", "no gas", "no ac", "freezes")
    ):
        return True
    return False


def extract_page_refs(text: str):
    return {int(m) for m in PAGE_REF_RE.findall(text or "")}


def symptom_matched_pages_from_index(index_text: str, symptom: str):
    """
    From a diagnostic index chart, pick ONLY page numbers on rows that match the concern.
    Does NOT dump every page on the chart.
    """
    t_sym = (symptom or "").lower()
    terms = set(tokenize(symptom))
    want_gas = any(w in t_sym for w in ("gas", "lp", "propane", "flame", "igniter", "burner"))
    want_ac = any(w in t_sym for w in ("ac", "electric", "120", "element", "shore", "electric"))
    want_cool = any(w in t_sym for w in ("cool", "cold", "warm", "temp", "not cooling", "won't cool", "wont cool"))
    want_dead = any(w in t_sym for w in ("dead", "no power", "no operation", "won't turn", "wont turn", "blank"))
    want_lights_off = any(w in t_sym for w in ("no light", "no panel", "dark", "blank display"))
    want_lights_on = any(w in t_sym for w in ("display is on", "lights on", "panel on", "display on"))
    want_freeze = any(w in t_sym for w in ("freeze", "freezing", "frozen", "too cold"))
    both_modes = (
        (want_gas and want_ac)
        or ("gas" in t_sym and "electric" in t_sym)
        or ("gas or electric" in t_sym)
        or ("gas and electric" in t_sym)
        or ("neither" in t_sym)
        or ("all mode" in t_sym)
    )

    scored_lines = []
    lines = re.split(r"[\n\r]+|(?=\d+\.\s)", index_text or "")
    for line in lines:
        ll = line.lower().strip()
        if len(ll) < 8:
            continue
        line_pages = extract_page_refs(line)
        if not line_pages:
            continue
        score = 0
        # Primary symptom rows
        if want_freeze and "freeze" in ll:
            score += 10
        if want_cool and "insufficient cooling" in ll:
            if both_modes and "all mode" in ll:
                score += 12
            elif want_ac and not want_gas and ("on ac" in ll or "ac -" in ll or "ac mode" in ll):
                score += 10
            elif want_gas and not want_ac and ("on gas" in ll or "gas -" in ll or "gas mode" in ll):
                score += 10
            elif "all mode" in ll:
                score += 9
            else:
                score += 6
        if want_dead or want_lights_off:
            if "no operation" in ll and "no panel" in ll:
                score += 10
            elif "no operation" in ll and "has panel" in ll:
                score += 8 if want_lights_on else 6
        if want_lights_on and "has panel" in ll:
            score += 5
        if want_ac and not both_modes and ("no ac" in ll or "operates on gas" in ll):
            score += 8
        if want_gas and not both_modes and ("no gas" in ll or "operates on ac" in ll):
            score += 8
        # Weak keyword overlap
        score += min(2, sum(1 for term in terms if term in ll and term not in ("the", "and", "for")))
        # Penalize clearly wrong rows
        if want_cool and not want_freeze and "freeze" in ll and "insufficient" not in ll:
            score -= 6
        if want_lights_on and "no panel" in ll:
            score -= 4
        if score >= 6:
            scored_lines.append((score, line_pages, ll[:80]))

    scored_lines.sort(key=lambda x: x[0], reverse=True)
    pages = set()
    if scored_lines:
        # Take top-scoring rows only (same band as best)
        best = scored_lines[0][0]
        for sc, lp, _ in scored_lines:
            if sc >= best - 2:
                pages |= lp
    else:
        # Narrow fallback: only insufficient-cooling / no-operation rows, never whole chart
        for line in lines:
            ll = line.lower()
            if "insufficient cooling" in ll or "no operation" in ll or "no gas" in ll or "no ac" in ll:
                pages |= extract_page_refs(line)
    # Always include a couple of early procedure pages often needed first
    if pages:
        pages.update({6, 7, 9, 10})  # operation / voltage common early pages in Americana-style books
        # but drop junk if we only wanted freeze etc. - keep simple
    return pages


def score_chunk(ch, query_terms, model_text: str, procedure_boost: bool = True) -> int:
    hay = f"{ch.title or ''} {ch.keywords or ''} {ch.chunk_text or ''}".lower()
    if not query_terms:
        return 1
    score = 0
    for term in query_terms:
        if term in hay:
            title_kw = f"{ch.title or ''} {ch.keywords or ''}".lower()
            score += 4 if term in title_kw else 1
            score += min(hay.count(term), 3)
    if model_text.strip() and model_text.strip().lower() in hay:
        score += 8
    if procedure_boost:
        proc_signals = (
            "check ", "measure", "volt", "ohm", "if ", "disconnect", "replace",
            "inspect", "amp", "continuity", "resistance", "should be", "spec",
            "heating element", "thermistor", "cooling unit", "ventilation", "burner"
        )
        score += sum(1 for s in proc_signals if s in hay)
        if is_diagnostic_index_text(ch.chunk_text or ""):
            score -= 3
    return score


SHOP_BRANDS = (
    "furrion", "norcold", "dometic", "suburban", "atwood", "lippert", "lci",
    "bal", "keystone", "jayco", "brinkley", "kz", "victron", "renogy",
    "wfco", "progressive dynamics", "power gear", "schwintek", "carefree",
    "intelli-power", "pd", "on-an", "onan", "generac", "winegard",
)


def named_brands(*texts: str) -> list:
    blob = " ".join(t or "" for t in texts).lower()
    found = [b for b in SHOP_BRANDS if b in blob]
    # PD alone is too noisy unless Progressive is also there
    if "pd" in found and "progressive" not in blob and "intelli" not in blob:
        found = [b for b in found if b != "pd"]
    return found


def chunk_brands(ch) -> list:
    return named_brands(ch.title or "", ch.keywords or "")


def search_manual_chunks(category_id, model_text: str, symptom: str, limit: int = 14, unity_context: bool = False):
    """Keyword search + expand matching INDEX chart rows into real SECTION pages."""
    q = session.query(DocChunk)
    if category_id:
        cat_ids = [category_id]
        tsb = session.query(Category).filter(Category.name == "TSB / Recall").first()
        if tsb and tsb.id not in cat_ids:
            cat_ids.append(tsb.id)
        if unity_context:
            for extra_name in ("Electrical", "Reference", "ID & Reference"):
                extra = session.query(Category).filter(Category.name == extra_name).first()
                if extra and extra.id not in cat_ids:
                    cat_ids.append(extra.id)
        q = q.filter(DocChunk.category_id.in_(cat_ids))
    elif unity_context:
        cat_ids = []
        for extra_name in ("Electrical", "Reference", "ID & Reference"):
            extra = session.query(Category).filter(Category.name == extra_name).first()
            if extra and extra.id not in cat_ids:
                cat_ids.append(extra.id)
        if cat_ids:
            q = q.filter(DocChunk.category_id.in_(cat_ids))
    all_chunks = q.all()
    asked = named_brands(model_text or "", symptom or "")
    fridge_job = is_fridge_context("", model_text or "", symptom or "")
    branded = []
    if asked:
        branded = [ch for ch in all_chunks if any(b in chunk_brands(ch) for b in asked)]
        if branded:
            all_chunks = branded
        else:
            extra_names = ["Refrigerators", "Electrical"] if (fridge_job or category_id) else []
            have_ids = set()
            if category_id:
                have_ids.add(category_id)
            for extra_name in extra_names:
                extra = session.query(Category).filter(Category.name == extra_name).first()
                if extra:
                    have_ids.add(extra.id)
            if have_ids:
                more = session.query(DocChunk).filter(DocChunk.category_id.in_(list(have_ids))).all()
                seen = {(c.document_id, c.page, (c.chunk_text or "")[:40]) for c in all_chunks}
                for ch in more:
                    key = (ch.document_id, ch.page, (ch.chunk_text or "")[:40])
                    if key not in seen:
                        all_chunks.append(ch)
                        seen.add(key)
            branded = [ch for ch in all_chunks if any(b in chunk_brands(ch) for b in asked)]
            if branded:
                all_chunks = branded
    if not all_chunks:
        return []

    query_terms = set(tokenize(f"{model_text} {symptom}"))
    query_terms |= model_search_terms(model_text or "")
    # Light topic boost from symptom only (do NOT dump every OEM topic every time)
    for topic in PROCEDURE_TOPIC_TERMS:
        if any(tok in (symptom or "").lower() for tok in tokenize(topic)):
            query_terms |= set(tokenize(topic))
    # Core path terms for reefer no-cool
    if any(k in (symptom or "").lower() for k in ("cool", "gas", "electric", "ac", "refriger", "fridge", "reefer")):
        for t in ("heating", "element", "thermistor", "cooling", "unit", "ventilation",
                  "burner", "orifice", "solenoid", "igniter", "board", "fuse", "voltage"):
            query_terms.add(t)
    if fridge_job or any(k in (symptom or "").lower() for k in ("fridge", "reefer", "no power")):
        for t in ("fuse", "voltage", "front", "vent", "display", "refrigerator", "fridge"):
            query_terms.add(t)
    # Core path terms for RV furnace - sail switch is first-line, even if the tech
    # only typed "won't light" / "fan runs" / Dometic furnace.
    furnace_blob = f"{model_text or ''} {symptom or ''}".lower()
    if any(k in furnace_blob for k in ("furnace", "sail", "blower", "won't light", "wont light", "no heat", "no ignition")):
        for t in ("sail", "switch", "limit", "thermostat", "bypass", "blower",
                  "airflow", "voltage", "igniter", "electrode", "valve", "propane"):
            query_terms.add(t)

    scored = []
    asked_set = set(asked or [])
    for ch in all_chunks:
        sc = score_chunk(ch, query_terms, model_text or "")
        title_kw = f"{ch.title or ''} {ch.keywords or ''}".lower()
        hay = f"{title_kw} {(ch.chunk_text or '').lower()}"
        if asked_set and any(b in title_kw for b in asked_set):
            sc += 6
        for term in model_search_terms(model_text or ""):
            if term in title_kw:
                sc += 8
            elif term in hay:
                sc += 3
        if fridge_job:
            if any(x in title_kw for x in ("refriger", "fridge", "fcr", "norcold", "12v refrigerator")):
                sc += 5
            if any(x in title_kw for x in ("furnace", "rooftop", "chill cube", "air condition")) and "refriger" not in title_kw:
                sc -= 8
        if sc > 0:
            scored.append((sc, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return all_chunks[:limit]

    seed = [c for _, c in scored[: max(limit, 8)]]
    by_key = {}

    def add_chunk(ch):
        key = (ch.document_id, ch.page, (ch.chunk_text or "")[:60])
        if key not in by_key:
            by_key[key] = ch

    for ch in seed:
        add_chunk(ch)

    target_doc_ids = set()
    target_pages = set()
    for ch in seed[:5]:
        target_doc_ids.add(ch.document_id)
        if is_diagnostic_index_text(ch.chunk_text or ""):
            target_pages |= symptom_matched_pages_from_index(ch.chunk_text or "", symptom)
            if ch.page:
                target_pages.add(int(ch.page))

    # Neighbors of top non-index hits only
    for ch in seed[:3]:
        if ch.page and not is_diagnostic_index_text(ch.chunk_text or ""):
            p = int(ch.page)
            target_pages.update({max(1, p - 1), p, p + 1})
            target_doc_ids.add(ch.document_id)

    if target_doc_ids and target_pages:
        for ch in all_chunks:
            if ch.document_id not in target_doc_ids:
                continue
            if ch.page and int(ch.page) in target_pages:
                add_chunk(ch)

    # Prefer same-title manuals as top seed (e.g. Americana)
    top_titles = {((seed[0].title or "").lower())} if seed else set()
    for ch in seed[:3]:
        if ch.title:
            top_titles.add(ch.title.lower())

    merged = list(by_key.values())
    rescored = []
    for ch in merged:
        sc = score_chunk(ch, query_terms, model_text or "")
        if (ch.title or "").lower() in top_titles:
            sc += 3
        rescored.append((sc, ch))
    rescored.sort(
        key=lambda x: (x[0], 0 if not is_diagnostic_index_text(x[1].chunk_text or "") else -1),
        reverse=True,
    )
    out = []
    index_kept = False
    for sc, ch in rescored:
        if is_diagnostic_index_text(ch.chunk_text or ""):
            if index_kept:
                continue
            index_kept = True
        out.append(ch)
        if len(out) >= limit:
            break
    return out


def build_sources_payload(chunks) -> tuple:
    """Build human text + JSON list of unique document/page sources with excerpts."""
    sources_lines = []
    payload = []
    seen = set()
    for ch in chunks:
        doc = session.query(Document).get(ch.document_id)
        file_path = doc.file_path if doc else None
        key = (ch.document_id, ch.page)
        sources_lines.append(f"- {ch.title} (page {ch.page})")
        if key in seen:
            continue
        seen.add(key)
        payload.append({
            "document_id": ch.document_id,
            "title": ch.title,
            "page": ch.page,
            "file_path": file_path,
            "file_type": (doc.file_type if doc else "pdf") or "pdf",
            "excerpt": (ch.chunk_text or "")[:1800],
        })
    by_key = {(p["document_id"], p["page"]): p for p in payload}
    for ch in chunks:
        k = (ch.document_id, ch.page)
        if k in by_key:
            ex = by_key[k].get("excerpt") or ""
            more = ch.chunk_text or ""
            if more and more not in ex:
                by_key[k]["excerpt"] = (ex + "\n\n" + more)[:2500]
    return "\n".join(sources_lines), json.dumps(payload)


def render_pdf_page_png(file_bytes: bytes, page_num: int, zoom: float = 1.6):
    """Return PNG bytes for a 1-based page number, or None."""
    if not PYMUPDF_AVAILABLE:
        return None
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        idx = max(0, min(page_num - 1, doc.page_count - 1))
        page = doc.load_page(idx)
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
    except Exception:
        return None


CITED_PAGE_RE = re.compile(
    r"(?:📖\s*)?Source:\s*(.+?)\s*[-–—―]+\s*page\s*(\d+)",
    re.I,
)

PAGE_OF_MANUAL_RE = re.compile(
    r"\bpage\s*(\d+)\s+of\s+(?:the\s+)?(.+?)(?=\s*\(|\s*$|\.|\n)",
    re.I,
)

EXPLICIT_PAGE_RE = re.compile(r"\bpage\s*(\d+)\b", re.I)

FIGURE_REQ_RE = re.compile(
    r"\b(?:fig(?:ure)?\.?|illustration)\s*([0-9]+[a-z]?)\b",
    re.I,
)


def parse_cited_pages_from_text(assistant_text: str) -> list:
    """Pull manual title + page from coach 📖 Source lines and 'page N of TITLE' phrases."""
    out = []
    seen = set()

    def _add(title, page):
        title = (title or "").strip().strip("*").strip().rstrip(".,;:")
        title = re.sub(r"\s*\([^)]*$", "", title).strip()
        try:
            page = int(page)
        except Exception:
            return
        if not title or not page:
            return
        key = (title.lower(), page)
        if key in seen:
            return
        seen.add(key)
        out.append({"title": title, "page": page})

    for m in CITED_PAGE_RE.finditer(assistant_text or ""):
        _add(m.group(1), m.group(2))
    for m in PAGE_OF_MANUAL_RE.finditer(assistant_text or ""):
        _add(m.group(2), m.group(1))
    return out


def strip_fake_markdown_images(text: str) -> str:
    """Remove invented markdown/HTML images from coach replies. Real pages use st.image only."""
    if not text:
        return text
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def wants_library_figures(text: str) -> bool:
    """Detect that the tech wants a shop-library illustration / figure / page shown."""
    t = (text or "").lower()
    keys = (
        "illustration", "illustrations", "figure", "fig.", " fig ",
        "drawing", "diagram", "show me that page", "show that page",
        "show the page", "show page", "show me the page", "show the figure",
        "show the illustration", "associated illustrations", "associated illustration",
        "source page", "that page", "this page", "show me fig",
        "picture of", "pictures", "photo of", "pcb layout",
        "where are they", "where they are", "where is it", "where it is",
        "show me where", "show where", "label the", "labeled",
    )
    return any(k in t for k in keys)


def _titles_compatible(cited_title: str, source_title: str) -> bool:
    """True when the source row belongs to the cited manual. Never treat empty cite as a free pass across books."""
    ct = (cited_title or "").strip().lower()
    stitle = (source_title or "").strip().lower()
    if not ct or not stitle:
        return False
    if ct == stitle or ct in stitle or stitle in ct:
        return True
    ct_toks = {t for t in re.findall(r"[a-z0-9]+", ct) if len(t) > 3}
    st_toks = {t for t in re.findall(r"[a-z0-9]+", stitle) if len(t) > 3}
    if not ct_toks or not st_toks:
        return False
    return len(ct_toks & st_toks) >= 2


def match_cited_to_sources(cited: list, sources: list, fallback: bool = False) -> list:
    """Map 📖 Source title/page cites onto the silent ledger. Title-locked. Never cross-book page matches."""
    if not sources or not cited:
        return []
    matched = []
    used = set()
    for c in cited:
        ct = (c.get("title") or "").strip()
        try:
            cp = int(c.get("page") or 0)
        except Exception:
            cp = 0
        pick = None
        if cp:
            for i, s in enumerate(sources):
                if i in used:
                    continue
                try:
                    sp = int(s.get("page") or 0)
                except Exception:
                    sp = 0
                if sp == cp and _titles_compatible(ct, s.get("title") or ""):
                    pick = i
                    break
        if pick is None and ct:
            same_doc = []
            for i, s in enumerate(sources):
                if i in used:
                    continue
                if _titles_compatible(ct, s.get("title") or ""):
                    try:
                        sp = int(s.get("page") or 0)
                    except Exception:
                        sp = 0
                    same_doc.append((i, sp, s))
            if same_doc and cp:
                same_doc.sort(key=lambda x: abs(x[1] - cp))
                pick = same_doc[0][0]
            elif same_doc:
                pick = same_doc[0][0]
        if pick is not None:
            used.add(pick)
            row = dict(sources[pick])
            if cp:
                row["page"] = cp
            matched.append(row)
    return matched


def _source_ledger_key(item: dict) -> tuple:
    title = (item.get("title") or "").strip().lower()
    try:
        page = int(item.get("page") or 0)
    except Exception:
        page = 0
    return (item.get("document_id"), page, title)


def merge_ask_source_ledger(items: list):
    """Quiet append-only ledger used by warranty citations. Never drives chat UI."""
    if not items:
        return
    ledger = list(st.session_state.get("ask_sources") or [])
    seen = {_source_ledger_key(s) for s in ledger}
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        key = _source_ledger_key(item)
        if key in seen:
            continue
        seen.add(key)
        ledger.append(item)
        changed = True
    if changed:
        st.session_state["ask_sources"] = ledger
        try:
            st.session_state["ask_sources_json"] = json.dumps(ledger)
        except Exception:
            pass


def record_cited_pages(assistant_text: str):
    """Keep 📖 Source lines from coach turns for the warranty story."""
    cited = parse_cited_pages_from_text(assistant_text)
    if not cited:
        return cited
    log = list(st.session_state.get("ask_cited_log") or [])
    seen = {
        ((c.get("title") or "").strip().lower(), int(c.get("page") or 0))
        for c in log
    }
    for c in cited:
        key = ((c.get("title") or "").strip().lower(), int(c.get("page") or 0))
        if key in seen:
            continue
        seen.add(key)
        log.append({"title": c.get("title"), "page": c.get("page")})
    st.session_state["ask_cited_log"] = log
    ledger = list(st.session_state.get("ask_sources") or [])
    extras = []
    for c in cited:
        hit = match_cited_to_sources([c], ledger, fallback=False)
        if hit:
            extras.extend(hit)
        else:
            extras.append({
                "document_id": None,
                "title": c.get("title"),
                "page": c.get("page"),
                "file_path": None,
                "file_type": "pdf",
                "excerpt": "",
            })
    merge_ask_source_ledger(extras)
    return cited


def store_ask_sources(chunks):
    if not chunks:
        return
    _text, payload = build_sources_payload(chunks)
    try:
        data = json.loads(payload) if payload else []
    except Exception:
        data = []
    if isinstance(data, list) and data:
        merge_ask_source_ledger(data)


def parse_figure_requests(user_msg: str) -> list:
    """Pull Fig./Figure N requests from the tech message."""
    out = []
    seen = set()
    for m in FIGURE_REQ_RE.finditer(user_msg or ""):
        tok = m.group(1).upper()
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def parse_library_page_targets(user_msg: str, coach_text: str = "", prior_cited: list = None) -> dict:
    """
    Parse illustration/page targets from tech msg + coach reply + prior Source lines.
    Returns figures, explicit/cited pages, and the title-locked manual name.
    """
    coach_text = coach_text or ""
    user_msg = user_msg or ""
    prior_cited = list(prior_cited or [])

    cited = parse_cited_pages_from_text(coach_text)
    if not cited:
        cited = list(prior_cited)

    figures = parse_figure_requests(user_msg)

    # Explicit "page N" in the tech message (title filled later from locked manual)
    explicit_pages = []
    for m in EXPLICIT_PAGE_RE.finditer(user_msg):
        # Skip "page N of TITLE" — those already carry a title via parse_cited_pages_from_text
        span_end = m.end()
        tail = user_msg[span_end:span_end + 12].lower()
        if tail.lstrip().startswith("of "):
            continue
        try:
            explicit_pages.append(int(m.group(1)))
        except Exception:
            pass

    # Also accept page-of-title phrases from the tech message
    for c in parse_cited_pages_from_text(user_msg):
        if c not in cited:
            cited.append(c)

    manual_title = ""
    if cited:
        manual_title = (cited[-1].get("title") or "").strip()
    elif prior_cited:
        manual_title = (prior_cited[-1].get("title") or "").strip()

    return {
        "figures": figures[:3],
        "cited": cited,
        "explicit_pages": explicit_pages[:3],
        "manual_title": manual_title,
    }


def resolve_document_by_title(title: str):
    """
    Resolve a Document row by title compatibility.
    Returns a page-ref seed with document_id + file_path, or None.
    Never cross-book: caller must pass the cited manual title.
    """
    title = (title or "").strip()
    if not title:
        return None
    try:
        docs = session.query(Document).all()
    except Exception:
        return None
    best = None
    best_score = 0
    for d in docs:
        dt = d.title or ""
        if not _titles_compatible(title, dt):
            continue
        ct_toks = {t for t in re.findall(r"[a-z0-9]+", title.lower()) if len(t) > 3}
        st_toks = {t for t in re.findall(r"[a-z0-9]+", dt.lower()) if len(t) > 3}
        score = len(ct_toks & st_toks)
        if title.lower() in dt.lower() or dt.lower() in title.lower():
            score += 5
        if score > best_score and d.file_path:
            best_score = score
            best = {
                "document_id": d.id,
                "title": d.title,
                "page": 1,
                "file_path": d.file_path,
                "file_type": d.file_type or "pdf",
                "excerpt": "",
            }
    return best


def find_figure_page_in_document(document_id, figure_token: str) -> int:
    """Locate Fig. N inside ONE document's indexed DocChunks. Returns page or 0."""
    if not document_id or not figure_token:
        return 0
    fig = figure_token.lower().lstrip("0") or figure_token.lower()
    patterns = [
        re.compile(rf"\bfig(?:ure)?\.?\s*0*{re.escape(fig)}\b", re.I),
        re.compile(rf"\bfig(?:ure)?\s*0*{re.escape(fig)}\b", re.I),
    ]
    try:
        chunks = (
            session.query(DocChunk)
            .filter_by(document_id=int(document_id))
            .order_by(DocChunk.page)
            .all()
        )
    except Exception:
        return 0
    for ch in chunks:
        blob = ch.chunk_text or ""
        for pat in patterns:
            if pat.search(blob):
                try:
                    return int(ch.page or 0)
                except Exception:
                    return 0
    return 0


def _page_ref(seed: dict, page: int, title_fallback: str = "") -> dict:
    """Build a renderable page dict. Document title + page + file_path is enough."""
    return {
        "document_id": seed.get("document_id"),
        "title": seed.get("title") or title_fallback or "Manual",
        "page": int(page),
        "file_path": seed.get("file_path"),
        "file_type": seed.get("file_type") or "pdf",
        "excerpt": seed.get("excerpt") or "",
    }


def resolve_requested_library_pages(user_msg: str, assistant_text: str = "") -> list:
    """
    Clean page pipeline (display path):
      detect (caller) → parse targets → resolve Document (title-locked) → resolve page → list of page refs.
    Silent ask_sources ledger is NOT required for display; Document.title + page + file_path is enough.
    Never cross-book.
    """
    prior = list(st.session_state.get("ask_cited_log") or [])
    targets = parse_library_page_targets(user_msg or "", assistant_text or "", prior_cited=prior)
    manual_title = (targets.get("manual_title") or "").strip()
    cited = list(targets.get("cited") or [])
    figures = list(targets.get("figures") or [])
    explicit_pages = list(targets.get("explicit_pages") or [])

    if not manual_title:
        # No cited shop manual — refuse to guess across books
        return []

    seed = resolve_document_by_title(manual_title)
    if not seed or not seed.get("file_path"):
        return []

    out = []
    seen_pages = set()

    def _add_page(page_num: int):
        try:
            page_num = int(page_num)
        except Exception:
            return
        if not page_num or page_num in seen_pages:
            return
        seen_pages.add(page_num)
        out.append(_page_ref(seed, page_num, manual_title))

    # 1) Fig./Figure N → search ONLY this document's DocChunks
    for fig in figures:
        page = find_figure_page_in_document(seed.get("document_id"), fig)
        if not page:
            # Fall back to last cited Source page from this same title
            for c in reversed(cited):
                if _titles_compatible(manual_title, c.get("title") or ""):
                    try:
                        page = int(c.get("page") or 0)
                    except Exception:
                        page = 0
                    break
        if page:
            _add_page(page)

    # 2) Explicit "page N" in the tech message (title-locked to cited manual)
    for p in explicit_pages:
        _add_page(p)

    # 3) Cited Source pages / page-of-title (when coach named them)
    if not out:
        for c in cited:
            if not _titles_compatible(manual_title, c.get("title") or manual_title):
                continue
            try:
                p = int(c.get("page") or 0)
            except Exception:
                p = 0
            if p:
                _add_page(p)

    return out[:3]


def render_on_demand_library_pages(pages: list):
    """Show only the requested shop-library page(s). No source-menu forest."""
    st.markdown("#### Shop library page")
    st.caption("From the shop Document Library - not uploaded by the technician.")
    if not pages:
        st.info("No matching shop-library page was found for that request.")
        ledger = list(st.session_state.get("ask_sources") or [])
        best = next((s for s in reversed(ledger) if s.get("file_path")), None)
        if best and best.get("file_path"):
            r2_download_button(
                "⬇️ Download best matching library PDF",
                best["file_path"],
                f"{(best.get('title') or 'manual')[:40]}.pdf",
                "ask_ondemand_best_dl",
            )
        return
    shown_pdf = set()
    for i, src in enumerate(pages[:3]):
        render_library_page_image(src, f"ondemand_{i}")
        excerpt = (src.get("excerpt") or "").strip()
        if excerpt:
            with st.expander("Text from this page", expanded=False):
                st.text(excerpt[:1800])
        fpath = src.get("file_path")
        if fpath and fpath not in shown_pdf:
            shown_pdf.add(fpath)
            r2_download_button(
                "⬇️ Download this PDF",
                fpath,
                f"{(src.get('title') or 'manual')[:40]}.pdf",
                f"ask_ondemand_dl_{i}",
            )


def clear_ask_source_state():
    st.session_state["ask_sources"] = []
    st.session_state.pop("ask_sources_json", None)
    st.session_state.pop("ask_auto_show", None)
    st.session_state.pop("ask_auto_show_failed", None)
    st.session_state.pop("ask_cited_log", None)
    st.session_state.pop("ask_flow", None)


def render_library_page_image(src: dict, key_suffix: str):
    """R2 download → pymupdf page → st.image. No markdown image embeds."""
    title = src.get("title") or "Manual"
    try:
        page = int(src.get("page") or 1)
    except Exception:
        page = 1
    fpath = src.get("file_path")
    if not fpath:
        st.caption(f"{title} p.{page} - no storage path on this library record.")
        return False
    with st.spinner(f"Loading shop library page {page}…"):
        data = r2_download_bytes(fpath)
    if not data:
        st.error("Could not download that PDF from shop storage.")
        return False
    png = render_pdf_page_png(data, page)
    if png:
        st.image(png, caption=f"Shop Document Library - {title} - page {page}", use_container_width=True)
        return True
    if not PYMUPDF_AVAILABLE:
        st.warning(
            "Page images need `pymupdf` in requirements.txt. "
            "Use Download full PDF and jump to this page. Text excerpt below."
        )
    else:
        st.warning("Could not render page image. Download the PDF and jump to this page.")
    if src.get("excerpt"):
        st.text(src.get("excerpt"))
    return False


def load_job_sources(job: DiagnosticJob) -> list:
    if not getattr(job, "sources_json", None):
        return []
    try:
        data = json.loads(job.sources_json)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def run_guided_diagnostics(category_name: str, model_text: str, symptom: str, chunks, unity_gate: str = "") -> tuple:
    """Returns (plan_text, sources_text, sources_json)."""
    if not chunks:
        asked = named_brands(model_text or "", symptom or "")
        brand_line = ""
        if asked:
            brand_line = (
                f"- Named brand/model: {', '.join(asked)}. Nothing in the library "
                "for that brand in this category.\n"
                "- Do not use another brand's voltages, ohms, or pin names.\n"
            )
        msg = (
            "No matching manual text was found in TechTrack.\n\n"
            + brand_line
            + "- Check category selection\n"
            "- Try different keywords / model number\n"
            "- Ask a manager to upload/index the service manual\n"
            "- Scanned PDFs with no text cannot be searched until OCR is added"
        )
        return msg, "", "[]"

    sources_text, sources_json = build_sources_payload(chunks)
    context_parts = []
    for i, ch in enumerate(chunks, 1):
        label = "INDEX CHART" if is_diagnostic_index_text(ch.chunk_text or "") else "PROCEDURE"
        context_parts.append(
            f"[EXCERPT {i} | {label}] Manual: {ch.title} | Page: {ch.page}\n{ch.chunk_text}"
        )
    context = "\n\n".join(context_parts)

    if not ai_available():
        body = [
            "**Guided Diagnostics (AI offline - matching manual excerpts)**",
            "",
            f"**Category:** {category_name}",
            f"**Model/System:** {model_text or '-'}",
            f"**Symptom:** {symptom}",
            "",
            "**Sources:**",
            sources_text,
            "",
        ]
        for i, ch in enumerate(chunks[:8], 1):
            kind = "INDEX" if is_diagnostic_index_text(ch.chunk_text or "") else "PROC"
            body.append(f"**Excerpt {i} [{kind}] - {ch.title} p.{ch.page}**")
            body.append(ch.chunk_text[:700] + ("..." if len(ch.chunk_text) > 700 else ""))
            body.append("")
        body.append(
            "\nCite 📖 Source lines from the excerpts above. Ask Guided Diagnostics chat "
            "to show a page only if you need the illustration."
        )
        return "\n".join(body), sources_text, sources_json

    try:
        system_prompt = """You are an expert RV technician coach helping shop techs diagnose and repair units on the floor.

You will receive:
- Category, optional model/system, and the reported symptom
- EXCERPTS from the shop's uploaded service manuals only
- Some excerpts may be labeled INDEX CHART (symptom → cause → section/page tables)
- Others are labeled PROCEDURE (actual tests, specs, wiring, measurements)
- Each PROCEDURE excerpt includes Manual title and Page number - you MUST use those on every step

CRITICAL RULES:
1. Use ONLY the provided manual excerpts for procedures, specs, LED codes, and test steps.
2. If an INDEX CHART is present: pick ONLY the single best matching symptom row for THIS concern (not every row on the chart). Name that row once. Then expand ITS causes only into shop-floor tests using PROCEDURE excerpts.
3. NEVER paste the whole index chart as the plan. NEVER list 15+ causes as step 1. Max about 10-12 guided steps.
4. NEVER end a step with only "refer to page X", "see the manual", or "contact support" if any PROCEDURE excerpt covers that check. Write the actual check (measure/inspect/expected reading/pass-fail).
5. OEM ORDER for refrigerator "not cooling" (when relevant):
   a) Confirm operation / display / mode
   b) DC power / fuses / supply voltage
   c) Heat source path - AC/electric (element, AC volts, board) AND/OR gas (LP, valve, igniter/solenoid, burner, orifice) as the concern requires
   d) Shared: ventilation, level (skip if already confirmed), door seals/air leaks
   e) Thermistor / controls
   f) Cooling unit performance LAST (only after heat source proven)
5b. OEM ORDER for RV furnace (Dometic / Atwood / Suburban) when category is Furnaces or the item is a furnace - do this almost first, before board, igniter, gas valve, or electrode:
   a) Bypass the wall thermostat at the furnace (jumper t-stat terminals / local heat call) so coach controls are out of the path
   b) Confirm 12V at the furnace under load while the blower runs (about 10.5-13.5 VDC)
   c) Verify sail-switch POWER IN and POWER OUT with the blower running. IN without OUT = sail not closed or no airflow. No IN = wiring/board/limit/t-stat path - do not replace the sail yet
   d) Then dirty blower / restricted return-exhaust / high-limit in series / correct sail part and paddle position
   e) Temporary sail jumper only AFTER the blower is running; never leave jumped
   f) Igniter, gas valve, and flame sense ONLY after the sail/limit path is proven
   If the concern is fan runs / won't light / no heat / 1-flash airflow on a Dometic furnace, steps a-c are mandatory first recommendations even if the tech did not mention the sail switch.
6. Start with brief SAFETY notes when relevant.
7. Output format:
   - SAFETY (short)
   - MATCHED SYMPTOM ROW (one line from index if used)
   - GUIDED TEST SEQUENCE (numbered)
8. REQUIRED - cite source INLINE on EVERY numbered step (not only at the bottom).
   Use this exact pattern:

   N. [Action]. Expected: [result]. If fail: [next].
      📖 Source: [Exact manual title from excerpt] - page [N]

   - The page number MUST match the PROCEDURE excerpt page you used for that step.
   - If two pages apply, list both on that step: page 11, page 12.
   - Do NOT leave any step without a 📖 Source line.
9. After all steps, add a short SOURCES list (optional recap). The inline citations are the primary requirement.
10. Plain shop language. Do not invent OEM procedures not in the excerpts.
11. BRAND LOCK: If the tech named a brand or model (Furrion, Norcold N641, etc.) and the excerpts are a DIFFERENT brand, do NOT use those excerpts as the procedure. Say the library does not have that brand's service manual and ask only what they can see (blower run, spark, lockout, check light). No borrowed voltages, ohms, pin names, or step order from the other brand.
12. Sister-model specs from the SAME brand are OK only if you label them (e.g. "RM1350 chart says 34.3 Ω - confirm on the RM2662 page before using it").
13. HARDWARE LOCK: An LCD screen is not automatically a separate touchpad. On Lippert Level-Up and similar systems the display may be the controller interface. Do not tell the tech to unplug, test, or replace a "touchpad" unless THIS model's manual excerpt or the tech notes name a separate touchpad. Do not invent a second control device.
14. If the coach may have Lippert OneControl/Unity (CAN multiplex), follow UNITY OEM ORDER before condemning awning/slide motors. If the tech confirmed NO Unity board, skip Unity steps entirely. Do not invent connector letters or pin names unless they appear in the SPMP / excerpt.
15. DIAG LED HONESTY: NEVER invent built-in fault/blink LEDs. Furrion FCR08/FCR10 flash codes need the SM temporary 10 mA LED on rear inverter D/+ - say that, or skip flash codes. Never invent a control-panel blink LED.
16. SOURCE PAGE HONESTY: 📖 Source page must be the excerpt page that actually shows the figure/terminals you describe. Never invent markdown images.
17. NO FAKE IMAGES: Never output ![alt](url) or HTML img tags in the plan."""

        furnace_rule = FURNACE_OEM_ORDER if is_furnace_context(category_name, model_text, symptom) else ""
        unity_rule = UNITY_OEM_ORDER if is_unity_context(category_name, model_text, symptom, unity_gate) else ""
        fridge_rule = FRIDGE_OEM_ORDER if is_fridge_context(category_name, model_text, symptom) else ""
        user_prompt = f"""CATEGORY: {category_name}
MODEL / SYSTEM: {model_text or "(not provided)"}
SYMPTOM: {symptom}
{furnace_rule}
{unity_rule}
{fridge_rule}
{DIAG_LED_HONESTY}

MANUAL EXCERPTS (INDEX CHART = pick one matching row only; PROCEDURE = write real tests from these).
Each excerpt header has Manual + Page - copy those into every step's 📖 Source line:

{context}

Write the guided diagnostic plan now.
Pick the ONE best index symptom row if a chart is present.
Give a tight GUIDED TEST SEQUENCE in OEM order.
EVERY step must end with:
📖 Source: [manual title] - page [N]
Do not tell the tech to open a Source pages dropdown.
Do not put sources only at the bottom. Do not dump the entire chart."""

        answer = ai_chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.15,
            max_tokens=2400,
        )
        if "source" not in answer.lower():
            answer += "\n\n**Sources used**\n" + sources_text
        answer = (
            "**WO plan (documentation).** Live coaching in Guided Diagnostics chat still goes "
            "gate-by-gate: run the next 1-2 tests only, then report results before the rest.\n\n"
            + answer
        )
        answer += (
            "\n\n---\n"
            "Citations are 📖 Source lines from the shop Document Library. "
            "Ask Guided Diagnostics chat to show a page only if you need the illustration."
        )
        return answer, sources_text, sources_json
    except Exception as e:
        return f"Error contacting AI: {e}", sources_text, sources_json



# ---------------- FURNACE OEM ORDER (always-on coach rule) ----------------
def is_furnace_context(category_name: str = "", model_text: str = "", symptom: str = "") -> bool:
    blob = f"{category_name or ''} {model_text or ''} {symptom or ''}".lower()
    return "furnace" in blob


def furnace_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if is_furnace_context(category_name, model_text, symptom):
        return f"{symptom} furnace sail switch thermostat bypass airflow limit".strip()
    return symptom


def fridge_search_symptom(category_name: str, model_text: str, symptom: str) -> str:
    symptom = (symptom or "").strip()
    if is_fridge_context(category_name, model_text, symptom):
        return f"{symptom} refrigerator fridge fuse voltage front vent no power display".strip()
    return symptom


FURNACE_OEM_ORDER = """
FURNACE OEM ORDER (Dometic / Atwood / Suburban and any RV furnace job) - use this whenever the category is Furnaces OR the item/model/concern is a furnace. Do this almost first. Do not wait for the tech to ask about the sail switch.

1) Bypass the wall thermostat / coach climate board at the FURNACE: jumper the furnace thermostat terminals (or apply a known-good heat call at the furnace) so a bad t-stat or AC control board is out of the path. Confirm the furnace blower starts from that local call.
2) Measure sail-switch POWER IN and POWER OUT while the blower is running (12 VDC typical).
   - IN present, OUT absent with blower running = sail not closed (switch, paddle alignment, or not enough airflow).
   - IN absent = do not condemn the sail yet (call circuit, wiring, board, or series high-limit).
3) If IN is good and OUT is dead: watch the paddle, check dirty blower wheel, restricted return/exhaust, low voltage under load (need about 10.5-13.5 VDC at the furnace while running), then high-limit in series. Replace the sail only after those checks or a failed manual-actuate/continuity test.
4) Temporary sail jumper is DIAGNOSTIC ONLY and ONLY after the blower is already running. Never jumper before the motor starts (lockout). Never leave a safety switch jumped.
5) Only after the t-stat-bypass + sail/limit path is proven: electrode/igniter, gas pressure/valve, flame sense.

When the concern is fan runs / no light / no heat / airflow or 1-flash limit fault on a Dometic furnace, the FIRST recommended inspections must be thermostat bypass and sail-switch voltage in vs out. Do not skip them because the tech did not type "sail switch".
"""


FRIDGE_OEM_ORDER = """
FRIDGE / 12V COMPRESSOR NO-POWER OEM ORDER (Furrion FCR08/FCR10 and similar 12V residential-style RV fridges) - only when this is a refrigerator job:
1) Do NOT remove the fridge first.
2) Check accessible customer/tech fuse first (Furrion FCR08/FCR10: front vent cover, left side of front vent cavity, 15A ATC blade fuse / cartridge - follow the shop SM excerpt). If blown, replace and retest before any teardown.
3) Confirm dial is ON (not OFF), about 4-5. Confirm 12V supply at the unit only after the accessible fuse path is checked (or if this model has no front fuse per the excerpt - say so from the manual). If still no cool: hard reset / lockout path from the SM (disconnect all power at the fridge, wait, restore, wait 5-10 minutes) when that path is in the excerpts.
4) Fault flash codes on Furrion FCR08/FCR10 (CCD-0008122): NOT a built-in LED on the temperature dial / control panel. The SM requires a TEMPORARY 10 mA diagnostic LED clipped to the rear inverter/driver terminals D (LED negative) and + (LED positive, piggyback). Say that clearly, or SKIP flash codes and meter 12V into the inverter/board instead. NEVER say "watch the control panel LED blink" or that the driver board "just has an LED that flashes" without the clip-on procedure.
5) Only then harness, inverter/PCB, compressor / fan paths from the manual.
6) Cite 📖 Source lines from the Furrion/Norcold/Dometic excerpt actually used. Brand lock: do not use a furnace or rooftop AC manual for a fridge.
"""

DIAG_LED_HONESTY = """
DIAGNOSTIC LED HONESTY (ALL brands / models):
- NEVER invent indicator lights, LEDs, displays, buttons, or connectors that are not in the provided manual excerpts.
- If the excerpt describes a temporary / jumper / clip-on diagnostic LED (Furrion FCR CCD-0008122 style), you MUST say: tech supplies a 10 mA LED, remove rear cover, clip to terminals D (-) and + (+), then count flashes. Do NOT call that a front control-panel LED.
- If the excerpts do not describe any built-in flash LED, do NOT ask the tech to count flashes on a panel LED.
- Prefer real gates (fuse, dial, hard reset, metered voltage) over a special LED setup the tech may not have ready.
"""


def is_unity_context(category_name: str = "", model_text: str = "", symptom: str = "", unity_gate: str = "") -> bool:
    """True when this coach has or may have a Lippert OneControl / Unity multiplex board."""
    gate = (unity_gate or "").strip()
    if gate == "No":
        return False
    if gate in ("Yes", "Not sure"):
        return True
    cat = (category_name or "").lower()
    if "electrical" in cat:
        return True
    blob = f"{category_name or ''} {model_text or ''} {symptom or ''}".lower()
    markers = (
        "unity", "onecontrol", "one control", "x270", "x270d", "multiplex",
        "can bus", "can-bus", "can network",
    )
    if any(m in blob for m in markers):
        return True
    smell = (
        "relay click", "touch panel", "onecontrol", "latching",
        "water pump", "generator start", "from panel",
    )
    load = any(w in blob for w in ("awning", "slide", "retract", "extend"))
    intermittent = any(w in blob for w in ("intermittent", "dropout", "drop out", "sometimes", "in and out"))
    if load and (intermittent or any(s in blob for s in smell)):
        return True
    if any(s in blob for s in ("latching light", "lights on panel", "water pump on panel", "generator from panel")):
        return True
    return False


def unity_search_symptom(category_name: str, model_text: str, symptom: str, unity_gate: str = "") -> str:
    symptom = (symptom or "").strip()
    if is_unity_context(category_name, model_text, symptom, unity_gate):
        return (
            f"{symptom} Unity OneControl X270 BAT1 BAT2 reversing output "
            "awning slide CAN software fuse"
        ).strip()
    return symptom


UNITY_OEM_ORDER = """
UNITY / ONECONTROL BOARD OEM ORDER (only when this coach has or may have a Lippert Unity / OneControl multiplex board - CAN/bus). Skip entirely if the tech confirmed the coach has NO Unity board.

Not every RV has a Unity board. Direct-switch Carefree awnings, standalone slide controllers, etc. stay on their own OEM path.

When Unity / OneControl IS in play:
1) Confirm command: switch/panel command produces a relay click at the Unity. Click alone does NOT prove the board is good - only that the control/coil side received a command.
2) BAT1 and BAT2 at the Unity: resting ~12-14 VDC each. Trace feeds to protection and RECORD fuse/breaker sizes as found (do not invent a failure cause from fuse size alone - note for OEM review). X270 / X270D boards are commonly specified with dedicated 30A on EACH battery feed; if mixed sizes are found, document them.
3) MONEY TEST at the Unity reversing (or latching) output for THIS function (awning, slide, etc.): resting; hold EXTEND; hold RETRACT. Pass ≈ ~12 V with polarity reverse on REV outputs. FAIL / authorize board R&R when BAT supply is solid, relay clicks, and at the Unity pins: no ~12 V, no polarity flip, stuck mid-voltage (~4-5 V), or intermittent spike-then-dropout while commanding.
4) Same measurement at the motor/load. Good at Unity, bad at motor → harness/connector. Good at motor, no move → motor/mechanical bind.
5) Optional: brief direct 12 V reverse-polarity at the motor only. Runs both ways → motor OK.
6) Intermittent catch: when fault is present, retest immediately at Unity pins. Dropout at Unity → board. Cite the shop PRIMARY Unity Board Diagnostic and the coach SPMP pin map from the library (Electrical / Reference). Do not invent connector letters if the SPMP for this coach is not in the excerpts - tell the tech to open the SPMP / silkscreen for that function.
7) CAN note: some functions (e.g. bed slide on some builds) are CAN-only with no local REV pin on the Unity. If SPMP says CAN-only, diagnose via CAN/module path - do not invent a REV meter point.
8) Always ask early if unknown: "Does this coach have Lippert OneControl / Unity board (CAN multiplex)?"

HARDWARE LOCK: Do not treat an LCD as a separate touchpad. Do not invent pins. Brand lock still applies.
"""


# ---------------- GUIDED FLOW ENGINE (v4.10.0) ----------------
# Chase's rule: TECH reports results; TechTrack advances ONLY via hard tree edges.
# Free-text concerns never invent the next test. Prefer node.prompt verbatim.

ASK_FLOWCHART_PAGE_LOCK = (
    "HARD FLOWCHART PAGE LOCK: You may only prescribe the next test that appears as "
    "the next decision on the cited excerpt page; never invent adjacent gates from "
    "other sections. Prefer the hard procedure tree when one exists for this model."
)

FURRION_FCR_SM_TITLE = "Furrion FCR08/FCR10 SM CCD-0008122"

# First hard tree: Furrion FCR08/FCR10 / FCR10DCGTA / CCD-0008122
# Encoded from shop SM: Sec1 Fuse p.19 → Gen TS dial/battery p.12 → Sec3 paper p.33 →
# operating? diamond → Fan Replacement OR Not Cooling p.34.
# Fan F+/F- supply volts live on Fan Fault flash-code path (p.27) ONLY — never after paper test.
PROCEDURE_FURRION_FCR_CCD_0008122 = {
    "id": "furrion_fcr_ccd_0008122",
    "title": FURRION_FCR_SM_TITLE,
    "models": ("fcr08", "fcr10", "fcr10dcgta", "fcr08dcgta", "ccd-0008122", "ccd0008122"),
    "categories": ("refrigerat", "fridge"),
    "nodes": {
        "fuse_front_vent": {
            "id": "fuse_front_vent",
            "type": "multi",
            "prompt": (
                "DISCONNECT POWER. Pull the front vent cover off the bottom of the refrigerator. "
                "Locate the fuse in the top left section of the front vent cavity (Fig. 7A) — "
                "15A ATC blade / cartridge. Visually check the fuse, confirm with continuity, "
                "check fitment in the holder, replace if blown, then reapply power.\n\n"
                "Report fuse result: blown / replaced / good."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {
                "blown": "cavity_light_after_fuse",
                "replaced": "cavity_light_after_fuse",
                "good": "cavity_light_check",
            },
        },
        "cavity_light_check": {
            "id": "cavity_light_check",
            "type": "binary",
            "prompt": (
                "Open the door. Does the refrigerator cavity light come on?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {
                "yes": "dial_on_4_5",
                "no": "fuse_front_vent",
            },
        },
        "cavity_light_after_fuse": {
            "id": "cavity_light_after_fuse",
            "type": "multi",
            "prompt": (
                "After the fuse check/replace and power reapplied: does the refrigerator cavity "
                "light come on when opening the door? Also say if it is cooling or not cooling."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {
                "light_on_cooling": "resolved_power",
                "light_on_not_cooling": "dial_on_4_5",
                "yes": "dial_on_4_5",
                "light_on": "dial_on_4_5",
                "no": "power_continuity_voltage",
                "no_light": "power_continuity_voltage",
            },
        },
        "resolved_power": {
            "id": "resolved_power",
            "type": "end",
            "prompt": (
                "Power issue resolved. Confirm the refrigerator performs. "
                "No further action is required on the No-Power path."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 19,
            "edges": {},
        },
        "power_continuity_voltage": {
            "id": "power_continuity_voltage",
            "type": "binary",
            "prompt": (
                "Slide the unit out to access power connections. Measure and record voltage at the "
                "appliance connection (Fig. 8 / Fig. 9). Is the voltage between 12V–15V?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 20,
            "edges": {
                "yes": "dial_on_4_5",
                "no": "external_power_issue",
            },
        },
        "external_power_issue": {
            "id": "external_power_issue",
            "type": "end",
            "prompt": (
                "Insufficient RV supply voltage. Correct power supply: connect shore power, check "
                "converter, check wiring and switches, charge batteries. Document as "
                "\"external power issue.\" Contact RV manufacturer for additional troubleshooting."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 20,
            "edges": {},
        },
        "dial_on_4_5": {
            "id": "dial_on_4_5",
            "type": "binary",
            "prompt": (
                "Open the door and locate the temperature dial. Confirm the dial is ON — not OFF — "
                "set to position 4 or 5 (Fig. 17 / Fig. 32).\n\n"
                "Is the dial ON at 4 or 5?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 23,
            "edges": {
                "yes": "battery_under_load",
                "no": "set_dial_then_battery",
                "off": "set_dial_then_battery",
            },
        },
        "set_dial_then_battery": {
            "id": "set_dial_then_battery",
            "type": "gate",
            "prompt": (
                "Turn the refrigerator ON to dial position 4 or 5. Then check battery voltage under "
                "load (General Troubleshooting: ≥10.5V under load).\n\n"
                "Report when dial is set to 4–5 and the under-load voltage reading."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 12,
            "edges": {
                "pass": "paper_test",
                "yes": "paper_test",
                "ok": "paper_test",
                "set": "paper_test",
                "fail": "external_power_issue",
                "low": "external_power_issue",
                "no": "external_power_issue",
            },
        },
        "battery_under_load": {
            "id": "battery_under_load",
            "type": "binary",
            "prompt": (
                "Per General Troubleshooting: check battery voltage for 10.5V under load "
                "(operating range). Is battery voltage ≥10.5V under load?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 12,
            "edges": {
                "yes": "paper_test",
                "pass": "paper_test",
                "no": "external_power_issue",
                "fail": "external_power_issue",
            },
        },
        "paper_test": {
            "id": "paper_test",
            "type": "binary",
            "prompt": (
                "Insufficient Temperature — paper test for cooling-fan airflow (air in/out):\n"
                "1. Open the door.\n"
                "2. Droop a piece of paper over the edge of the cavity so it hangs over the front of the vent.\n"
                "3. Facing the unit, left side of the vent cover should SUCK the paper in (Fig. 33).\n"
                "4. Facing the unit, right side of the vent cover should BLOW the paper out (Fig. 34).\n\n"
                "Does the paper move correctly (left suck / right blow)?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 33,
            "edges": {
                "yes": "not_cooling_current",
                "pass": "not_cooling_current",
                "no": "is_operating_diamond",
                "fail": "is_operating_diamond",
            },
        },
        "is_operating_diamond": {
            "id": "is_operating_diamond",
            "type": "binary",
            "prompt": (
                "Is the refrigerator operating? (Compressor working/running — it may not be cold yet. "
                "Amperage should be greater than 1 amp to indicate it is working.)"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 33,
            "edges": {
                "no": "fan_replacement",
                "yes": "not_cooling_current",
            },
        },
        "fan_replacement": {
            "id": "fan_replacement",
            "type": "end",
            "prompt": (
                "Potential air blockage or bad fan. Proceed to Fan Replacement in Repair Section 2 "
                "for further information. Do not meter fan supply voltage on this path; "
                "that check belongs only on the Fan Fault / flash-code diagnostics, not after the paper test."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 33,
            "edges": {},
        },
        "not_cooling_current": {
            "id": "not_cooling_current",
            "type": "binary",
            "prompt": (
                "Not Cooling Diagnostics: Pull the unit out to measure current. Run the refrigerator "
                "for at least 1 hour before proceeding. Use a DC clamp meter to measure and record "
                "current.\n\n"
                "Is current <3 amps?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "oily_substance_check",
                "no": "dial_max_one_hour",
            },
        },
        "oily_substance_check": {
            "id": "oily_substance_check",
            "type": "binary",
            "prompt": (
                "Shut off the refrigerator and let sit for 1 hour. Remove the back cover and touch "
                "the inlet and outlet tubes with fingers to check for oily substance.\n\n"
                "Is there an oily substance present?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "replace_unit_coolant",
                "no": "replace_unit_return",
            },
        },
        "dial_max_one_hour": {
            "id": "dial_max_one_hour",
            "type": "binary",
            "prompt": (
                "Turn dial up to max setting and run for 1 hour.\n\n"
                "Is the refrigerator operating correctly?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "replace_thermostat",
                "no": "compressor_running_constant",
            },
        },
        "compressor_running_constant": {
            "id": "compressor_running_constant",
            "type": "binary",
            "prompt": "Is the compressor running constantly?",
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {
                "yes": "replace_unit_coolant",
                "no": "replace_thermostat",
            },
        },
        "replace_thermostat": {
            "id": "replace_thermostat",
            "type": "end",
            "prompt": (
                "Replace the thermostat to recalibrate the unit. Proceed to Thermostat Replacement "
                "in Repair Section 2. If issues persist, replace unit."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {},
        },
        "replace_unit_coolant": {
            "id": "replace_unit_coolant",
            "type": "end",
            "prompt": (
                "Likely a coolant leak. Replace unit and determine if unit needs to be returned."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {},
        },
        "replace_unit_return": {
            "id": "replace_unit_return",
            "type": "end",
            "prompt": (
                "Replace unit and determine if unit needs to be returned."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 34,
            "edges": {},
        },
        # Flash-code Fan Fault path ONLY (p.27) — F+/F− volts live here, not after paper test.
        "fan_fault_f_terminal_volts": {
            "id": "fan_fault_f_terminal_volts",
            "type": "binary",
            "prompt": (
                "Error Code — Fan Fault Diagnostics: Connect power, locate the inverter PCB. "
                "Measure and record voltage at the F+ and F− terminals on the inverter PCB.\n\n"
                "Is the nominal voltage 12V?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {
                "yes": "fan_fault_connections",
                "no": "replace_inverter_pcb",
            },
        },
        "fan_fault_connections": {
            "id": "fan_fault_connections",
            "type": "binary",
            "prompt": (
                "Check connections: fan into inverter PCB F+/F− terminals, and fan quick connection "
                "to harness. Reset power.\n\n"
                "Did the error code go away after resetting power?"
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {
                "yes": "resolved_power",
                "no": "replace_inverter_and_fan",
            },
        },
        "replace_inverter_pcb": {
            "id": "replace_inverter_pcb",
            "type": "end",
            "prompt": (
                "Replace the inverter PCB. Proceed to Compressor Inverter PCB Replacement in "
                "Repair Section 2."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {},
        },
        "replace_inverter_and_fan": {
            "id": "replace_inverter_and_fan",
            "type": "end",
            "prompt": (
                "Replace the inverter PCB and fan. Proceed to Compressor Inverter PCB Replacement "
                "and Fan Replacement in Repair Section 2."
            ),
            "source_title": FURRION_FCR_SM_TITLE,
            "source_page": 27,
            "edges": {},
        },
    },
}

PROCEDURE_TREES = {
    PROCEDURE_FURRION_FCR_CCD_0008122["id"]: PROCEDURE_FURRION_FCR_CCD_0008122,
}


def _norm_flow_text(s: str) -> str:
    t = (s or "").lower().strip()
    t = t.replace("—", "-").replace("–", "-")
    t = re.sub(r"\s+", " ", t)
    return t


def flow_matches_fcr_model(category_name: str = "", model_text: str = "") -> bool:
    blob = _norm_flow_text(f"{category_name or ''} {model_text or ''}")
    if "ccd-0008122" in blob or "ccd0008122" in blob:
        return True
    if re.search(r"\bfcr0?8\b", blob) or re.search(r"\bfcr10\b", blob):
        return True
    if "fcr10dcgta" in blob.replace(" ", "") or "fcr08dcgta" in blob.replace(" ", ""):
        return True
    if "furrion" in blob and ("fcr" in blob or "fridge" in blob or "refriger" in blob):
        # Prefer hard tree only when FCR family / CCD is clear enough
        if "fcr" in blob:
            return True
    return False


def find_matching_procedure(category_name: str = "", model_text: str = ""):
    """Return procedure dict if a hard tree matches category+model, else None."""
    if flow_matches_fcr_model(category_name, model_text):
        return PROCEDURE_FURRION_FCR_CCD_0008122
    cat = _norm_flow_text(category_name)
    model = _norm_flow_text(model_text)
    if any(c in cat for c in ("refriger", "fridge")) and (
        "fcr" in model or "ccd-0008122" in model or "ccd0008122" in model
    ):
        return PROCEDURE_FURRION_FCR_CCD_0008122
    return None


def get_procedure_node(procedure: dict, node_id: str):
    if not procedure:
        return None
    return (procedure.get("nodes") or {}).get(node_id)


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


def select_start_node_id(procedure: dict, user_msg: str, history: list = None) -> str:
    """
    Start node from tech free text. Does not invent tests — only picks an entry gate.
    no power / dead → fuse. Fuse replaced + light on + not cooling → dial (post-power path).
    Fan-fault flash → F+/F− path only.
    """
    blob = _norm_flow_text(user_msg)
    prior = " ".join(
        (m.get("content") or "") for m in (history or []) if m.get("role") == "user"
    )
    blob = _norm_flow_text(f"{prior} {user_msg}")

    # Flash / fan fault code path (only place F+/F− volts belong)
    if re.search(r"\b(2\s*flash|flash\s*2|fan fault|fan.?fault)\b", blob):
        return "fan_fault_f_terminal_volts"

    fuse_done = bool(
        re.search(
            r"\b(fuse\s+(?:is\s+|was\s+)?(?:blown\s+)?replaced|replaced\s+(?:the\s+)?fuse|"
            r"new\s+fuse|fuse\s+(?:was\s+)?blown\s+replac\w*|fuse\s+blown.*replac\w*)\b",
            blob,
        )
        or ("fuse" in blob and "blown" in blob and "replac" in blob)
        or ("fuse" in blob and "replac" in blob)
    )
    light_on = bool(
        re.search(r"\b(light\s+on|cavity light|interior light|has power|powered|power.?on)\b", blob)
    )
    not_cooling = bool(
        re.search(
            r"\b(not\s+cool(?:ing)?|no\s+cool(?:ing)?|won'?t\s+cool|wont\s+cool|not\s+cold|warm|insufficient\s+temp|no\s+cold)\b",
            blob,
        )
    )
    no_power = bool(
        re.search(
            r"\b(no power|dead|no light|won'?t turn on|wont turn on|blank|no juice|completely dead)\b",
            blob,
        )
    )

    if fuse_done and (light_on or not no_power) and not_cooling:
        return "dial_on_4_5"
    if fuse_done and light_on and not not_cooling:
        return "cavity_light_after_fuse"
    if no_power and not (fuse_done and light_on):
        return "fuse_front_vent"
    if not_cooling and not no_power:
        return "dial_on_4_5"
    if light_on and not_cooling:
        return "dial_on_4_5"
    return "fuse_front_vent"


# Ordered alias lists: first matching key wins for ambiguous text.
_ANSWER_ALIAS_GROUPS = [
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


def map_tech_text_to_answer(node: dict, tech_text: str):
    """
    Map free text to ONE allowed edge key for the CURRENT node.
    Returns (answer_key, None) or (None, reason) if unmapped — caller must re-ask, not advance.
    """
    if not node:
        return None, "no_node"
    edges = node.get("edges") or {}
    if not edges:
        return None, "end_node"
    raw = _norm_flow_text(tech_text)
    if not raw:
        return None, "empty"

    allowed = list(edges.keys())

    # Exact / startswith key
    for key in allowed:
        if raw == key or raw.startswith(key + " ") or raw.endswith(" " + key):
            return key, None

    # Alias groups that intersect allowed edges (preserve group priority).
    # Skip a positive phrase if it sits inside a negation ("not running", "no light").
    def _phrase_hit(phrase: str, text: str) -> bool:
        if phrase not in text:
            return False
        # Word-ish boundaries
        if not re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", text):
            return False
        # Negation immediately before phrase
        if re.search(r"\b(?:not|no|never|isn't|isnt|wasn't|wasnt|ain't|aint)\s+" + re.escape(phrase), text):
            return False
        return True

    for key, phrases in _ANSWER_ALIAS_GROUPS:
        if key not in edges:
            continue
        for p in phrases:
            if _phrase_hit(p, raw):
                return key, None

    # Node-specific heuristics
    nid = node.get("id") or ""
    if nid in ("cavity_light_after_fuse",):
        if ("light" in raw or "power" in raw) and any(
            w in raw for w in ("not cool", "no cool", "warm", "not cold")
        ):
            if "light_on_not_cooling" in edges:
                return "light_on_not_cooling", None
            if "yes" in edges:
                return "yes", None
        if "light" in raw and "on" in raw and "cool" in raw and "not" not in raw:
            if "light_on_cooling" in edges:
                return "light_on_cooling", None
        if any(w in raw for w in ("no light", "still dead", "dark", "no power")):
            if "no" in edges:
                return "no", None

    if nid == "fuse_front_vent":
        if "replac" in raw or ("blown" in raw and "replac" in raw):
            if "replaced" in edges:
                return "replaced", None
        if "blown" in raw:
            if "blown" in edges:
                return "blown", None
        if any(w in raw for w in ("good", "ok", "fine", "intact", "not blown")):
            if "good" in edges:
                return "good", None

    if nid == "paper_test":
        if any(w in raw for w in ("no movement", "no paper", "doesn't move", "does not move", "fail", "no suck", "no blow")):
            if "fail" in edges:
                return "fail", None
            if "no" in edges:
                return "no", None
        if any(w in raw for w in ("suck", "blow", "moves", "pass", "airflow ok")):
            if "pass" in edges:
                return "pass", None
            if "yes" in edges:
                return "yes", None

    if nid == "is_operating_diamond":
        if re.search(r"\b(not\s+operat|not\s+running|isn't\s+running|compressor\s+not|no\s+compressor|dead)\b", raw):
            if "no" in edges:
                return "no", None
        if re.search(r"\b(operat|compressor\s+running|amps?\s*>\s*1|greater\s+than\s+1)\b", raw) and not re.search(r"\bnot\b", raw):
            if "yes" in edges:
                return "yes", None

    if nid in ("battery_under_load", "set_dial_then_battery", "power_continuity_voltage"):
        m = re.search(r"(\d+(?:\.\d+)?)\s*v", raw)
        if m:
            try:
                volts = float(m.group(1))
                if nid == "battery_under_load":
                    if volts >= 10.5 and "yes" in edges:
                        return "yes", None
                    if volts < 10.5 and "no" in edges:
                        return "no", None
                if nid == "power_continuity_voltage":
                    if 12.0 <= volts <= 15.0 and "yes" in edges:
                        return "yes", None
                    if (volts < 12.0 or volts > 15.0) and "no" in edges:
                        return "no", None
            except ValueError:
                pass

    if nid == "not_cooling_current":
        m = re.search(r"(\d+(?:\.\d+)?)\s*a", raw)
        if m:
            try:
                amps = float(m.group(1))
                if amps < 3.0 and "yes" in edges:
                    return "yes", None
                if amps >= 3.0 and "no" in edges:
                    return "no", None
            except ValueError:
                pass
        if "<3" in raw or "less than 3" in raw:
            if "yes" in edges:
                return "yes", None
        if ">3" in raw or "over 3" in raw or "greater than 3" in raw:
            if "no" in edges:
                return "no", None

    # Soft yes/no — leading token or whole-message affirmation/negation
    lead = raw.split(",", 1)[0].strip()
    if lead in ("yes", "y", "yeah", "yep", "pass", "ok", "good") or raw in ("yes", "y", "yeah", "yep", "pass", "ok", "good"):
        if "yes" in edges:
            return "yes", None
        if "pass" in edges:
            return "pass", None
    if lead in ("no", "n", "nope", "fail", "failed") or raw in ("no", "n", "nope", "fail", "failed"):
        if "no" in edges:
            return "no", None
        if "fail" in edges:
            return "fail", None

    return None, "unmapped"


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


def engine_turn(ask_flow: dict, user_msg: str, category_name: str = "", model_text: str = "", chat_history: list = None):
    """
    One Guided Diagnostics engine turn.
    Returns dict:
      used_engine, reply, ask_flow, reask, node (current after turn)
    If no matching tree: used_engine=False (caller uses AI path with page-lock rule).
    """
    procedure = find_matching_procedure(category_name, model_text)
    if not procedure:
        return {
            "used_engine": False,
            "reply": None,
            "ask_flow": ask_flow,
            "reask": False,
            "node": None,
        }

    flow = dict(ask_flow or {})
    hist = list(flow.get("history") or [])
    node_id = flow.get("node_id")
    proc_id = procedure["id"]

    # New / mismatched procedure → pick start from this message
    if flow.get("procedure_id") != proc_id or not node_id:
        node_id = select_start_node_id(procedure, user_msg, chat_history)
        # If the start message already encodes fuse-replaced+light+not cooling,
        # land on dial without requiring a prior answer.
        node = get_procedure_node(procedure, node_id)
        flow = {
            "procedure_id": proc_id,
            "node_id": node_id,
            "history": hist,
        }
        # Opening turn: present the start gate (do not consume message as an answer
        # unless we jumped into post-power because message already answered prior gates).
        start_id = node_id
        # When entry is dial_on_4_5 because message already reported fuse+light+not cooling,
        # present dial gate (message was entry selection, not dial answer).
        reply = format_gate_reply(node)
        return {
            "used_engine": True,
            "reply": reply,
            "ask_flow": flow,
            "reask": False,
            "node": node,
            "opened": True,
            "start_id": start_id,
        }

    node = get_procedure_node(procedure, node_id)
    if not node:
        node_id = select_start_node_id(procedure, user_msg, chat_history)
        node = get_procedure_node(procedure, node_id)
        flow = {"procedure_id": proc_id, "node_id": node_id, "history": hist}
        return {
            "used_engine": True,
            "reply": format_gate_reply(node),
            "ask_flow": flow,
            "reask": False,
            "node": node,
        }

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

    answer, reason = map_tech_text_to_answer(node, user_msg)
    if not answer:
        # Unmapped → re-ask CURRENT gate. Do NOT advance. Do NOT invent a new test.
        reask_preface = (
            "I need a result that matches this gate "
            f"({', '.join((node.get('edges') or {}).keys())}). "
            "Report only this check — I will not skip ahead."
        )
        return {
            "used_engine": True,
            "reply": format_gate_reply(node, preface=reask_preface),
            "ask_flow": flow,
            "reask": True,
            "node": node,
            "unmapped_reason": reason,
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

    hist.append({"node_id": node_id, "result": answer})
    flow = {
        "procedure_id": proc_id,
        "node_id": next_id,
        "history": hist,
    }
    return {
        "used_engine": True,
        "reply": format_gate_reply(next_node),
        "ask_flow": flow,
        "reask": False,
        "node": next_node,
        "advanced_from": node_id,
        "answer": answer,
    }


def guided_diagnostics_reply(
    user_msg: str,
    category_name: str,
    model_text: str,
    history: list,
    unity_gate: str = "",
    ask_flow: dict = None,
):
    """
    Router: hard tree ENGINE when category+model match; else AI ask_techtrack_reply
    with page-lock rule injected.
    Returns (reply_text, new_ask_flow_dict_or_None).
    """
    result = engine_turn(ask_flow, user_msg, category_name, model_text, history)
    if result.get("used_engine"):
        reply = result.get("reply") or ""
        # Silent ledger: record cited page from node
        node = result.get("node") or {}
        title = node.get("source_title")
        page = node.get("source_page")
        if title and page is not None:
            try:
                record_cited_pages(f"📖 Source: {title} - page {page}")
            except Exception:
                pass
        return reply, result.get("ask_flow")

    # No hard tree — AI path with hard page-lock system rule
    return ask_techtrack_reply(
        user_msg,
        category_name,
        model_text,
        history,
        unity_gate=unity_gate,
        extra_system_rule=ASK_FLOWCHART_PAGE_LOCK,
    ), ask_flow


# ---------------- END GUIDED FLOW ENGINE ----------------


# ---------------- ASK TECHTRACK (chat diagnose) ----------------
ASK_TECHTRACK_SYSTEM = """You are an expert RV shop technician coach helping techs diagnose and repair units on the floor.

You have excerpts from THIS SHOP's Document Library (indexed service manuals stored by Tacoma RV Center). The technician did not upload those excerpts. Never say "the text you uploaded," "the excerpts you provided," or "images weren't in what you uploaded." Say "the shop Document Library" or "the Furrion/Norcold/… manual in TechTrack." Figures live in those PDFs. If the tech asks to see a page, say it is shown below from the shop library. Do not tell them to open a Source pages dropdown.

You are a BRANCHING FLOWCHART, not a dump of the whole diagnostic tree.

Rules:
1. Use ONLY the provided Document Library excerpts for procedures, specs, LED codes, and test steps. If excerpts are missing or do not cover the issue, say so and ask a clarifying question - do not invent OEM procedures.
2. FLOWCHART GATE: Each assistant turn is at most ONE clarifying question OR 1-2 concrete tests that are the next decision gate. Prefer ONE test when possible.
3. NEVER list Step 3 / 4 / 5 or a long numbered sequence in one chat turn unless the tech explicitly asks for the full plan.
4. After giving 1-2 tests, STOP and ask only for those results (reading, pass/fail, flash count - whatever that gate needs).
5. On the next turn, use the tech's result + library excerpts to choose the NEXT branch. Skip tests the result made unnecessary.
6. Do not front-load inverter PCB teardown, compressor fan, and error-code flash together if fuse/supply gates are still open. Follow OEM order one gate at a time.
7. If the tech pastes multiple results at once, acknowledge each, then give only the next 1-2 gates.
8. Cite sources inline when you use an excerpt:
   📖 Source: [Exact manual title from excerpt] - page [N]
9. Do not paste index charts. If an INDEX CHART excerpt is present, pick the single best matching symptom row for THIS concern.
10. Start with a brief SAFETY note only when the next test is hazardous (LP, 120VAC, high voltage, refrigerant).
11. Plain shop language. Short sentences. No fluff.
12. After the tech reports a result, interpret it and give the next 1-2 checks.
13. If the tech says the job is not repaired, they need a warranty story, they will press the Write warranty story button, or they want you to hold/record the notes for a handoff: acknowledge, restate ONLY the tests and readings they already reported, and STOP. Do not give more tests. Do not treat "press the button" as a controller reset or any shop-floor button. The warranty story button is in this app, not on the unit.
14. HARDWARE LOCK: An LCD screen is not automatically a separate touchpad. On Lippert Level-Up and similar systems the display may be the controller interface. Do not tell the tech to unplug, test, or replace a "touchpad" unless THIS model's manual excerpt or the tech notes name a separate touchpad. Do not invent a second control device.
15. Do not invent tests the tech has not run. When they report readings, acknowledge every number before giving the next check.
16. FURNACE OEM ORDER (when category is Furnaces or the item/model/concern is a furnace, especially Dometic): start almost first with (1) bypass the wall thermostat at the furnace so the unit has a local heat call, then (2) verify sail-switch power IN and power OUT while the blower is running. Do not skip the sail switch because the tech did not name it. Do not go to board / igniter / gas valve first on fan-runs-no-light. Temporary sail jumper is diagnostic only after the blower is running; never leave jumped. Low voltage under load and dirty blower / restricted airflow are why a NEW sail still will not pass power.
17. If the coach may have Lippert OneControl/Unity (CAN multiplex), follow UNITY OEM ORDER before condemning awning/slide motors. If the tech confirmed NO Unity board, skip Unity steps entirely. Do not invent connector letters. If Unity is unknown and excerpts do not mention Unity, ask once: Does this coach have Lippert OneControl / Unity board (CAN multiplex)?
18. FRIDGE / 12V COMPRESSOR NO-POWER: when this is a refrigerator job, follow FRIDGE OEM ORDER. Do not pull the fridge first. Check the accessible front-vent / customer fuse before rear voltage or teardown. Do not use a furnace or rooftop AC manual for a fridge.
19. If the tech asks for illustrations, figures, drawings, associated illustrations, Fig. N, or "show that page": do not say the drawings are missing from text they uploaded. Tell them the shop Document Library PDF page is displayed below from the SAME cited 📖 Source manual title and page. NEVER pull a figure from a different brand or manual. Do not invent markdown images. Do not instruct them to open a Source pages dropdown or list every linked page.
21. NO FAKE IMAGES: Never output markdown images (![alt](url)), HTML img tags, or pretend photo embeds in chat. If a figure is needed, say TechTrack will display the shop Document Library page below. Do not draw a fake picture.
20. DIAG LED HONESTY: NEVER invent built-in fault/blink LEDs. For Furrion FCR08/FCR10 (CCD-0008122), flash codes require a temporary 10 mA LED clipped to rear inverter terminals D (-) and + (+). Say that full clip-on procedure, or skip flash codes and go dial / hard reset / meter 12V. NEVER say the control panel or driver board simply has an LED that blinks when power is applied.
22. SOURCE PAGE HONESTY: The page number in 📖 Source MUST be the Document Library excerpt page that actually contains the figure or terminal you are describing. Do not say page 18 shows power-input terminals if that excerpt is the diagnostic LED page. If you do not have the correct page in the excerpts, say so - do not invent page-to-figure mapping."""


def _ask_chat_transcript(history: list) -> str:
    lines = []
    for m in history or []:
        role = (m.get("role") or "user").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        label = "Tech" if role == "user" else "Guided Diagnostics"
        lines.append(f"{label}: {content}")
    return "\n\n".join(lines)


def _ask_manual_context(category_name: str, model_text: str, symptom: str, limit: int = 8, unity_gate: str = ""):
    """Search uploaded manuals when category and/or symptom is known. Returns (chunks, context_text)."""
    category_name = (category_name or "").strip()
    model_text = (model_text or "").strip()
    symptom = (symptom or "").strip()
    if not category_name and not symptom:
        return [], ""
    cat_obj = None
    if category_name:
        cat_obj = session.query(Category).filter_by(name=category_name).first()
    category_id = cat_obj.id if cat_obj else None
    chunks = search_manual_chunks(
        category_id,
        model_text,
        symptom,
        limit=limit,
        unity_context=is_unity_context(category_name, model_text, symptom, unity_gate),
    )
    if not chunks:
        return [], ""
    parts = []
    for i, ch in enumerate(chunks, 1):
        label = "INDEX CHART" if is_diagnostic_index_text(ch.chunk_text or "") else "PROCEDURE"
        parts.append(
            f"[EXCERPT {i} | {label}] Manual: {ch.title} | Page: {ch.page}\n{ch.chunk_text}"
        )
    return chunks, "\n\n".join(parts)


def ask_techtrack_reply(user_msg: str, category_name: str, model_text: str, history: list, unity_gate: str = "", extra_system_rule: str = "") -> str:
    """One chat turn: optional manual search + Grok/Groq coach reply."""
    user_msg = (user_msg or "").strip()
    if not user_msg:
        return "Type a symptom or question first."

    prior_user = " ".join(
        (m.get("content") or "") for m in (history or []) if m.get("role") == "user"
    )
    search_symptom = f"{prior_user} {user_msg}".strip()
    search_symptom = furnace_search_symptom(category_name, model_text, search_symptom)
    search_symptom = fridge_search_symptom(category_name, model_text, search_symptom)
    search_symptom = unity_search_symptom(category_name, model_text, search_symptom, unity_gate)
    chunks, context = _ask_manual_context(
        category_name, model_text, search_symptom, limit=8, unity_gate=unity_gate
    )
    store_ask_sources(chunks)

    system_prompt = ASK_TECHTRACK_SYSTEM
    if category_name:
        system_prompt += f"\n\nCategory selected: {category_name}"
    if model_text:
        system_prompt += f"\nModel/system: {model_text}"
    if is_furnace_context(category_name, model_text, search_symptom):
        system_prompt += "\n\n" + FURNACE_OEM_ORDER
    if is_unity_context(category_name, model_text, search_symptom, unity_gate):
        system_prompt += "\n\n" + UNITY_OEM_ORDER
    if is_fridge_context(category_name, model_text, search_symptom):
        system_prompt += "\n\n" + FRIDGE_OEM_ORDER
    system_prompt += "\n\n" + DIAG_LED_HONESTY
    if extra_system_rule:
        system_prompt += "\n\n" + extra_system_rule
    if context:
        system_prompt += (
            "\n\nMANUAL EXCERPTS from this shop's Document Library "
            "(INDEX CHART = pick one matching row only; PROCEDURE = write real tests). "
            "The technician did not upload these excerpts. "
            "Each header has Manual + Page - copy those into 📖 Source lines:\n\n"
            + context
        )
    else:
        system_prompt += (
            "\n\nNo matching manual excerpts were found for this turn. "
            "Ask 1-2 questions to narrow category/model/symptom, or give safe general next checks. "
            "Do not invent OEM page numbers."
        )

    if not ai_available():
        fallback = ["AI is offline (no XAI_API_KEY or GROQ_API_KEY). Matching manual excerpts:", ""]
        if chunks:
            for i, ch in enumerate(chunks[:6], 1):
                fallback.append(f"**{ch.title}** p.{ch.page}")
                fallback.append((ch.chunk_text or "")[:500])
                fallback.append("")
        else:
            fallback.append(
                "No matching manual text found. Check category / try different wording, "
                "or ask a manager to index the manual."
            )
        return "\n".join(fallback)

    messages = [{"role": "system", "content": system_prompt}]
    for m in history or []:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_msg})

    try:
        reply = ai_chat(messages, temperature=0.2, max_tokens=900)
    except Exception as e:
        return f"Error contacting AI: {e}"
    reply = strip_fake_markdown_images(reply)
    record_cited_pages(reply)
    if wants_library_figures(user_msg):
        reply += (
            "\n\nThe figure is in the shop Document Library PDF. "
            "If a page image appears below, that is the real shop library page "
            "(not a chat photo embed). If nothing appears below, say so and use Download PDF / meter from the text labels."
        )
    return reply


def ask_chat_to_warranty_story(history: list, category_name: str = "", model_text: str = "") -> str:
    """Feed Guided Diagnostics tech lines into improve_tech_story. Coach lines are recommendations only."""
    tech_lines = []
    coach_lines = []
    first_user = ""
    for m in history or []:
        role = (m.get("role") or "").strip()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            if not first_user:
                first_user = content
            tech_lines.append(content)
        else:
            coach_lines.append(content[:1600])
    notes_parts = []
    if category_name:
        notes_parts.append(f"Category: {category_name}")
    if model_text:
        notes_parts.append(f"Model/System: {model_text}")
    tech_blob = "\n\n".join(tech_lines) if tech_lines else "(none)"
    notes_parts.append(
        "TECH REPORTED (only these are performed tests / readings / status):\n"
        + tech_blob
    )
    if coach_lines:
        notes_parts.append(
            "COACH SUGGESTIONS (recommended only - do NOT treat as performed unless the tech later confirmed the result). "
            "If the tech later said good/pass/done on a recommended check, bind that pass to the coach's exact location and threshold; do not invent a reading:\n"
            + "\n---\n".join(coach_lines[:4])
        )
    cite_lines = []
    seen_cites = set()
    for c in (st.session_state.get("ask_cited_log") or []):
        title = (c.get("title") or "").strip()
        page = c.get("page")
        if not title or not page:
            continue
        key = (title.lower(), int(page))
        if key in seen_cites:
            continue
        seen_cites.add(key)
        cite_lines.append(f"📖 Source: {title} - page {page}")
    for s in (st.session_state.get("ask_sources") or []):
        title = (s.get("title") or "").strip()
        page = s.get("page")
        if not title or not page:
            continue
        key = (title.lower(), int(page))
        if key in seen_cites:
            continue
        seen_cites.add(key)
        cite_lines.append(f"📖 Source: {title} - page {page}")
    if cite_lines:
        notes_parts.append(
            "SILENT SOURCE LEDGER (attach the matching 📖 Source line to tests the technician actually performed; "
            "do not invent pages; do not cite a page the tech did not run):\n"
            + "\n".join(cite_lines)
        )
    # Status from tech lines only so coach "replace the overload" cannot flip OPEN/complete.
    return improve_tech_story(first_user, "\n\n".join(notes_parts), status_text=tech_blob)


def load_step_log(job: DiagnosticJob) -> list:
    if not job.step_log:
        return []
    try:
        data = json.loads(job.step_log)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_step_log(job: DiagnosticJob, steps: list):
    job.step_log = json.dumps(steps)
    job.updated_date = datetime.now()
    session.commit()


def seed_data():
    if session.query(User).count() == 0:
        session.add(User(username="manager", password_hash=hash_password("manager123"), full_name="Shop Manager", role="Manager"))
        session.add(User(username="alex", password_hash=hash_password("tech123"), full_name="Alex Tech", role="Technician"))
        session.add(User(username="jordan", password_hash=hash_password("tech123"), full_name="Jordan Tech", role="Technician"))
        session.commit()
    if session.query(Category).count() == 0:
        for name in ["Refrigerators", "Furnaces", "Water Heaters", "Air Conditioning", "Slideouts", "Leveling", "Electrical", "ID & Reference", "Warranty Forms", "Solar"]:
            session.add(Category(name=name))
        session.commit()


maybe_restore_db_from_r2()
seed_data()
purge_old_ask_chats(30)

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "active_job_id" not in st.session_state:
    st.session_state.active_job_id = None
if "ask_chat" not in st.session_state:
    st.session_state["ask_chat"] = []
if "ask_chat_id" not in st.session_state:
    st.session_state["ask_chat_id"] = None

_cookie_mgr = _cookie_manager()
if st.session_state.user is None:
    restored = _load_auth_token(_cookie_get(_cookie_mgr, AUTH_COOKIE_NAME))
    if restored:
        st.session_state.user = restored
        row = session.query(User).get(restored["id"])
        if row:
            _cookie_set_auth(_cookie_mgr, _issue_auth_token(row))

if st.session_state.user is None:
    _lc, login_col, _rc = st.columns([1, 1.5, 1])
    with login_col:
        _logo = shop_logo_path()
        if _logo:
            st.image(str(_logo), use_container_width=True)
        st.markdown(
            "<h1 style='text-align:center;margin:0.35rem 0 0;color:#01147C;font-size:2rem;'>TechTrack</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='text-align:center;color:#02763A;font-weight:600;margin:0.2rem 0 1.1rem;'>"
            "Tacoma RV Center · Service</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", type="primary"):
                user = session.query(User).filter_by(username=u.strip().lower(), is_active=True).first()
                if user and verify_password(p, user.password_hash):
                    st.session_state.user = {
                        "id": user.id,
                        "username": user.username,
                        "full_name": user.full_name,
                        "role": user.role,
                    }
                    _cookie_set_auth(_cookie_mgr, _issue_auth_token(user))
                    st.rerun()
                else:
                    st.error("Invalid username or password")
        if not _auth_serializer() or not COOKIE_MGR_AVAILABLE:
            st.caption(
                "Stay-signed-in is off until AUTH_COOKIE_SECRET is in Streamlit secrets "
                "and extra-streamlit-components is installed."
            )
    st.stop()

user = st.session_state.user
is_manager = user["role"] == "Manager"

# ---------------- HEADER / NAV ----------------
_hdr_logo = shop_logo_path()
hdr_l, hdr_r = st.columns([1.05, 3.6])
with hdr_l:
    if _hdr_logo:
        st.image(str(_hdr_logo), use_container_width=True)
with hdr_r:
    st.markdown(
        "<h1 style='margin:0.4rem 0 0;color:#01147C;font-size:1.85rem;'>TechTrack</h1>",
        unsafe_allow_html=True,
    )
    st.caption(f"Signed in as **{user['full_name']}** ({user['role']}) · Tacoma RV Center · Service")
if st.sidebar.button("Log out"):
    _cookie_clear_auth(_cookie_mgr)
    st.session_state.user = None
    st.session_state.active_job_id = None
    st.session_state["ask_chat"] = []
    st.session_state.pop("ask_story_out", None)
    st.session_state.pop("ask_story_area", None)
    st.rerun()
st.sidebar.caption(f"Role: {user['role']}")

tabs = ["📱 My Dashboard", "🔍 Diagnostic Jobs (Work Order)", "💬 Guided Diagnostics", "📚 Document Library", "🛡️ Safety / Compliance"]
if is_manager:
    tabs.extend(["👥 Team Overview", "🛠️ Manager Tools"])
tab_objs = st.tabs(tabs)
tab_dash = tab_objs[0]
tab_jobs = tab_objs[1]
tab_ask = tab_objs[2]
tab_lib = tab_objs[3]
tab_safety = tab_objs[4]
tab_team = tab_objs[5] if is_manager else None
tab_mgr = tab_objs[6] if is_manager else None

# =========================================================
# MY DASHBOARD
# =========================================================
with tab_dash:
    st.subheader("📱 My Dashboard")
    c1, c2, c3 = st.columns(3)
    my_certs = session.query(Certificate).filter_by(user_id=user["id"]).count()
    safety_pct = get_safety_progress(user["id"])
    my_open = session.query(DiagnosticJob).filter_by(user_id=user["id"], status="in_progress").count()
    c1.metric("Certificates", my_certs)
    c2.metric("Safety Progress", f"{safety_pct}%")
    c3.metric("Open WO Jobs", my_open)

    st.markdown("#### 📜 My Certificates")
    certs = session.query(Certificate).filter_by(user_id=user["id"]).order_by(Certificate.created_date.desc()).all()
    if certs:
        for cert in certs:
            with st.container(border=True):
                st.write(f"**{cert.title}** - {cert.issuer or '-'}")
                if cert.issued_date:
                    st.caption(f"Issued: {cert.issued_date}")
                if cert.notes:
                    st.caption(cert.notes)
                r2_download_button("⬇️ Download", cert.file_path, f"{cert.title}.pdf", f"dl_cert_{cert.id}")
    else:
        st.info("No certificates uploaded yet.")

    with st.expander("⬆️ Upload Certificate", expanded=False):
        if not r2_available():
            st.warning("File storage is not configured yet. Contact a manager.")
        else:
            ct = st.text_input("Certificate Title", key="cert_title")
            ci = st.text_input("Issuer (Lippert, RVTI, Airexcel, etc.)", key="cert_issuer")
            cd = st.text_input("Issued Date (optional)", key="cert_date")
            cn = st.text_area("Notes (optional)", key="cert_notes")
            cf = st.file_uploader("PDF Certificate", type=["pdf"], key="cert_file")
            if st.button("Save Certificate", type="primary", key="save_cert"):
                if ct and cf:
                    key = f"certificates/{user['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{cf.name}"
                    if r2_upload(cf.getvalue(), key, "application/pdf"):
                        session.add(Certificate(
                            user_id=user["id"],
                            title=ct.strip(),
                            issuer=ci.strip(),
                            file_path=key,
                            issued_date=cd.strip(),
                            notes=cn.strip(),
                            uploaded_by=user["id"],
                        ))
                        session.commit()
                        st.success("Certificate saved permanently!")
                        st.rerun()
                else:
                    st.warning("Title and PDF are required.")

    st.markdown("#### ✍️ Quick Story Improver (no WO)")
    st.caption("For one-off claims. For full jobs with saved progress, use Diagnostic Jobs above.")
    sc = st.text_area("1. Customer Concern", key="story_concern", placeholder="Customer states the air conditioner is not cooling…")
    sn = st.text_area("2. What you found and did", key="story_notes", placeholder="Found bad compressor. Recovered, replaced, evacuated, recharged, tested.")
    if st.button("Improve Story", type="primary", key="improve_story_btn"):
        if sc.strip() or sn.strip():
            with st.spinner("Writing improved warranty story..."):
                improved = improve_tech_story(sc, sn)
            st.markdown("### Improved Version")
            st.text_area("Copy this improved story", value=improved, height=320, key="story_improved")
        else:
            st.warning("Please enter at least the customer concern or your notes.")

# =========================================================
# DIAGNOSTIC JOBS
# =========================================================
with tab_jobs:
    st.subheader("🔍 Diagnostic Jobs (Work Order)")
    st.caption(
        "Start or resume a job by work order number. TechTrack searches your manuals, "
        "guides testing, saves progress, and can write the warranty story when you're done."
    )

    tab_start, tab_list, tab_active = st.tabs(["Start / Resume", "My Jobs", "Active Job"])

    with tab_start:
        st.markdown("#### Start a new job or resume by WO #")
        resume_wo = st.text_input("Work Order Number", key="resume_wo", placeholder="e.g. 4521 or WO-4521")
        if st.button("Resume this WO", key="btn_resume"):
            if not resume_wo.strip():
                st.warning("Enter a work order number.")
            else:
                q = session.query(DiagnosticJob).filter_by(wo_number=resume_wo.strip())
                if not is_manager:
                    q = q.filter_by(user_id=user["id"])
                job = q.order_by(DiagnosticJob.updated_date.desc()).first()
                if not job:
                    st.warning("No job found for that WO #. Start a new one below.")
                else:
                    st.session_state.active_job_id = job.id
                    st.success(f"Resumed WO {job.wo_number}")
                    st.rerun()

        st.markdown("#### New diagnostic job")
        cats = session.query(Category).order_by(Category.name).all()
        cat_names = [c.name for c in cats]
        if not cat_names:
            st.warning("No categories yet. Ask a manager to create categories and upload manuals.")
        else:
            nj_wo = st.text_input("Work Order #", key="nj_wo")
            nj_cat = st.selectbox("Category", cat_names, key="nj_cat")
            nj_model = st.text_input("Model / System (optional)", key="nj_model", placeholder="Schwintek, RM2652, Hydro-Sync…")
            with st.expander("📷 Read model from data plate photo", expanded=False):
                st.caption("Snap or upload the rating plate. Fills Model/System for this job.")
                nj_cam = st.camera_input("Snap data plate", key="nj_plate_cam")
                nj_up = st.file_uploader(
                    "Or upload plate photo",
                    type=["jpg", "jpeg", "png", "webp"],
                    key="nj_plate_upload",
                )
                nj_img = nj_cam or nj_up
                if nj_img is not None:
                    st.image(nj_img, caption="Plate photo", width=280)
                    apply_plate_read_to_model_key("nj_model", nj_img, "nj_plate_read_btn")
            nj_unity = st.selectbox(
                "Lippert OneControl / Unity board on this coach?",
                ["Not sure", "Yes", "No"],
                key="nj_unity_gate",
                help="Not every unit has one. Yes/Not sure = include Unity board tests + Electrical manuals. No = skip Unity path.",
            )
            nj_concern = st.text_area(
                "Customer concern / symptom",
                key="nj_concern",
                height=100,
                placeholder="Customer states slide only moves ~2 inches then one side stops.",
            )
            if st.button("Start Job + Build Test Plan", type="primary", key="nj_start"):
                if not nj_wo.strip() or not nj_concern.strip():
                    st.warning("Work order number and concern are required.")
                else:
                    existing = (
                        session.query(DiagnosticJob)
                        .filter_by(wo_number=nj_wo.strip(), status="in_progress")
                        .first()
                    )
                    if existing and existing.user_id == user["id"]:
                        st.warning(
                            f"Open job already exists for WO {nj_wo.strip()} "
                            f"(id {existing.id}). Use Resume, or complete that job first."
                        )
                    else:
                        cat_obj = session.query(Category).filter_by(name=nj_cat).first()
                        with st.spinner("Searching manuals and building guided tests..."):
                            nj_sym = furnace_search_symptom(nj_cat, nj_model, nj_concern)
                            nj_sym = fridge_search_symptom(nj_cat, nj_model, nj_sym)
                            nj_sym = unity_search_symptom(nj_cat, nj_model, nj_sym, nj_unity)
                            hits = search_manual_chunks(
                                cat_obj.id if cat_obj else None,
                                nj_model,
                                nj_sym,
                                limit=16,
                                unity_context=is_unity_context(nj_cat, nj_model, nj_concern, nj_unity),
                            )
                            plan, sources, sources_json = run_guided_diagnostics(
                                nj_cat, nj_model, nj_concern, hits, unity_gate=nj_unity
                            )
                        job = DiagnosticJob(
                            wo_number=nj_wo.strip(),
                            user_id=user["id"],
                            category_name=nj_cat,
                            model_text=nj_model or None,
                            concern=nj_concern.strip(),
                            plan_text=plan,
                            findings="",
                            step_log="[]",
                            sources_text=sources,
                            sources_json=sources_json,
                            status="in_progress",
                        )
                        session.add(job)
                        session.commit()
                        st.session_state.active_job_id = job.id
                        st.success(f"Job started for WO {job.wo_number}")
                        st.rerun()

    with tab_list:
        q = session.query(DiagnosticJob)
        if not is_manager:
            q = q.filter_by(user_id=user["id"])
        my_jobs = q.order_by(DiagnosticJob.updated_date.desc()).limit(40).all()
        if is_manager:
            st.caption("Showing all jobs. Managers can open any WO via Resume.")
        if not my_jobs:
            st.info("No diagnostic jobs yet.")
        else:
            for j in my_jobs:
                owner = session.query(User).get(j.user_id)
                label = f"WO {j.wo_number} · {j.status} · {j.category_name or '-'} · {(j.updated_date or j.created_date).strftime('%Y-%m-%d %H:%M') if (j.updated_date or j.created_date) else ''}"
                if is_manager and owner:
                    label += f" · {owner.full_name}"
                cols = st.columns([4, 1])
                cols[0].write(label)
                if cols[1].button("Open", key=f"open_job_{j.id}"):
                    st.session_state.active_job_id = j.id
                    st.rerun()

    with tab_active:
        jid = st.session_state.active_job_id
        job = session.query(DiagnosticJob).get(jid) if jid else None
        if not job:
            st.info("No active job. Use **Start / Resume** to open a work order.")
        else:
            owner = session.query(User).get(job.user_id)
            st.markdown(f"### WO **{job.wo_number}** · {job.status}")
            st.caption(f"{job.category_name or '-'} · {job.model_text or '-'} · Tech: {owner.full_name if owner else job.user_id}")
            st.markdown("**Customer concern**")
            st.write(job.concern)

            with st.expander("📋 Guided test plan (from manuals)", expanded=True):
                st.markdown(job.plan_text or "_No plan saved._")
                if job.sources_text:
                    st.markdown("**Sources (text list)**")
                    st.text(job.sources_text)

            sources = load_job_sources(job)
            # Rebuild sources_json from sources_text is not possible; offer rebuild if empty
            with st.expander(
                "📷 Source pages (figures & full page view)",
                expanded=False,
            ):
                st.caption(
                    "When the plan says Fig. 1F / LCD / diagram - open that page here. "
                    "This is the actual PDF page from your uploaded manual."
                )
                if not sources:
                    st.warning(
                        "No structured source pages on this job yet. "
                        "Click **🔄 Rebuild test plan** below - that re-attaches manuals and pages."
                    )
                else:
                    st.success(f"{len(sources)} source page(s) linked to this plan.")
                    labels = [
                        f"{(s.get('title') or 'Manual')[:60]} - p.{s.get('page') or '?'}"
                        for s in sources
                    ]
                    pick = st.selectbox("Choose a source page", labels, key=f"src_pick_{job.id}")
                    idx = labels.index(pick) if pick in labels else 0
                    src = sources[idx]
                    title = src.get("title") or "Manual"
                    page = int(src.get("page") or 1)
                    fpath = src.get("file_path")
                    st.markdown(f"**{title}** - page **{page}**")
                    bcols = st.columns(2)
                    with bcols[0]:
                        if fpath:
                            r2_download_button(
                                "⬇️ Download full PDF",
                                fpath,
                                f"{title[:40]}.pdf",
                                f"src_dl_{job.id}_{idx}",
                            )
                        else:
                            st.caption("No file path on record for this source.")
                    with bcols[1]:
                        show = st.button("📷 Show this page", type="primary", key=f"src_show_{job.id}_{idx}")
                    if show:
                        if not fpath:
                            st.error("Missing storage path for this manual.")
                        else:
                            with st.spinner(f"Loading page {page}…"):
                                data = r2_download_bytes(fpath)
                            if not data:
                                st.error("Could not download PDF from storage. Check R2 secrets / file still in bucket.")
                            else:
                                png = render_pdf_page_png(data, page)
                                if png:
                                    st.image(png, caption=f"{title} - page {page}", use_container_width=True)
                                else:
                                    if not PYMUPDF_AVAILABLE:
                                        st.warning(
                                            "Page images need `pymupdf` in requirements.txt. "
                                            "Download the PDF and jump to this page. Showing text excerpt below."
                                        )
                                    else:
                                        st.warning("Could not render page image. Download the PDF and jump to this page.")
                    if src.get("excerpt"):
                        with st.expander("Text excerpt from this page", expanded=not show):
                            st.text(src.get("excerpt"))
                    st.markdown("**All linked pages**")
                    for i, s in enumerate(sources):
                        st.caption(f"{i+1}. {(s.get('title') or 'Manual')[:50]} - p.{s.get('page')}")

            st.markdown("#### Log tests as you go")
            st.caption("Record each test result so you can stop and resume later. This also feeds the warranty story.")
            steps = load_step_log(job)
            if steps:
                st.markdown("**Progress so far**")
                for s in steps:
                    test = (s.get("test") or s.get("step") or s.get("what") or s.get("action") or "").strip() or "(unnamed step)"
                    result = s.get("result") or s.get("outcome") or "-"
                    notes = (s.get("notes") or s.get("note") or "").strip()
                    line = f"- **{test}** → {result}"
                    if notes:
                        line += f" · {notes}"
                    st.write(line)

            t1, t2 = st.columns(2)
            with t1:
                step_test = st.text_input("What test / step did you do?", key=f"step_test_{job.id}", placeholder="e.g. Checked 30A fuse / battery voltage")
            with t2:
                step_result = st.selectbox("Result", ["Pass", "Fail", "Inconclusive", "Info"], key=f"step_res_{job.id}")
            step_notes = st.text_input("Notes (readings, LED codes, etc.)", key=f"step_notes_{job.id}", placeholder="e.g. 12.4V, motor LED red")
            if st.button("Add to job log", key=f"add_step_{job.id}"):
                if step_test.strip():
                    steps.append({
                        "test": step_test.strip(),
                        "result": step_result,
                        "notes": step_notes.strip(),
                        "at": datetime.now().isoformat(timespec="minutes"),
                    })
                    save_step_log(job, steps)
                    st.success("Step saved.")
                    st.rerun()
                else:
                    st.warning("Enter what you tested.")

            st.markdown("#### Findings / work performed (running notes)")
            findings_val = st.text_area(
                "Everything you found and fixed",
                value=job.findings or "",
                height=160,
                key=f"findings_{job.id}",
                placeholder="Found left Schwintek motor open circuit. Replaced motor, synced system, cycled room 3x OK.",
            )
            rebuild_unity = st.selectbox(
                "Lippert OneControl / Unity board on this coach?",
                ["Not sure", "Yes", "No"],
                key=f"rebuild_unity_gate_{job.id}",
                help="Used when rebuilding the test plan. Yes/Not sure includes Unity + Electrical manuals.",
            )
            b1, b2, b3, b4 = st.columns(4)
            with b1:
                if st.button("💾 Save progress", key=f"save_{job.id}", use_container_width=True):
                    job.findings = findings_val
                    job.updated_date = datetime.now()
                    session.commit()
                    st.success("Progress saved.")
            with b2:
                if st.button("🔄 Rebuild test plan", key=f"rebuild_{job.id}", use_container_width=True):
                    cat_obj = session.query(Category).filter_by(name=job.category_name).first()
                    with st.spinner("Re-searching manuals..."):
                        rb_sym = furnace_search_symptom(job.category_name, job.model_text or "", job.concern)
                        rb_sym = fridge_search_symptom(job.category_name, job.model_text or "", rb_sym)
                        rb_sym = unity_search_symptom(job.category_name, job.model_text or "", rb_sym, rebuild_unity)
                        hits = search_manual_chunks(
                            cat_obj.id if cat_obj else None,
                            job.model_text or "",
                            rb_sym,
                            limit=16,
                            unity_context=is_unity_context(
                                job.category_name, job.model_text or "", job.concern, rebuild_unity
                            ),
                        )
                        plan, sources, sources_json = run_guided_diagnostics(
                            job.category_name, job.model_text or "", job.concern, hits, unity_gate=rebuild_unity
                        )
                    job.plan_text = plan
                    job.sources_text = sources
                    job.sources_json = sources_json
                    job.findings = findings_val
                    job.updated_date = datetime.now()
                    session.commit()
                    st.success("Test plan rebuilt from current manuals.")
                    st.rerun()
            with b3:
                if st.button("✍️ Generate warranty story", key=f"story_{job.id}", type="primary", use_container_width=True):
                    job.findings = findings_val
                    session.commit()
                    with st.spinner("Writing CONCERN → CAUSE → CORRECTION from this job..."):
                        story = story_from_diagnostic_job(job)
                    job.final_story = story
                    job.updated_date = datetime.now()
                    session.commit()
                    st.success("Story generated and saved on this WO.")
                    st.rerun()
            with b4:
                if st.button("✅ Mark complete", key=f"done_{job.id}", use_container_width=True):
                    job.findings = findings_val
                    job.status = "complete"
                    job.updated_date = datetime.now()
                    session.commit()
                    st.success("Job marked complete.")
                    st.rerun()

            if job.final_story:
                st.markdown("### Warranty story (saved on this WO)")
                st.text_area("Copy into the warranty claim", value=job.final_story, height=280, key=f"final_story_{job.id}")
                st.caption("This story is stored on the work order. Resume the same WO later and it will still be here.")

            if st.button("Close active job view", key="clear_active"):
                st.session_state.active_job_id = None
                st.rerun()


# =========================================================
# ASK TECHTRACK
# =========================================================
with tab_ask:
    st.subheader("💬 Guided Diagnostics")
    st.caption(
        "Chat diagnose from this shop's Document Library manuals. Hard flowchart trees (when matched) "
        "advance only on reported gate results — free-text concerns never invent the next test. "
        "One gate per turn; report that result before the next. Ask to see a page only when you need it. "
        "Write warranty story uses the chat plus any unsent text. Only records what you actually tested."
    )

    if "ask_chat" not in st.session_state:
        st.session_state["ask_chat"] = []
    if "ask_chat_id" not in st.session_state:
        st.session_state["ask_chat_id"] = None
    if "ask_sources" not in st.session_state:
        st.session_state["ask_sources"] = []
    if "ask_cited_log" not in st.session_state:
        st.session_state["ask_cited_log"] = []
    if "ask_flow" not in st.session_state:
        st.session_state["ask_flow"] = None

    with st.expander("Recent chats (saved 30 days)", expanded=False):
        qch = session.query(AskChat)
        if not is_manager:
            qch = qch.filter_by(user_id=user["id"])
        recents = qch.order_by(AskChat.updated_date.desc()).limit(20).all()
        if not recents:
            st.caption("No saved chats yet. Send a message and it stays here.")
        for ch in recents:
            owner = session.query(User).get(ch.user_id)
            when = (ch.updated_date or ch.created_date)
            when_s = when.strftime("%b %d %I:%M %p") if when else ""
            who = f" · {owner.full_name}" if is_manager and owner else ""
            label = f"{(ch.title or 'Chat')[:60]} · {ch.category_name or 'any'}{who} · {when_s}"
            cols = st.columns([4, 1])
            cols[0].write(label)
            if cols[1].button("Open", key=f"open_ask_{ch.id}"):
                loaded, hist = load_ask_chat(ch.id)
                st.session_state["ask_chat_id"] = ch.id
                st.session_state["ask_chat"] = hist
                st.session_state["ask_sources"] = []
                st.session_state["ask_cited_log"] = []
                st.session_state["ask_flow"] = None
                st.session_state.pop("ask_auto_show", None)
                for m in hist:
                    if (m.get("role") or "") == "assistant":
                        record_cited_pages(m.get("content") or "")
                st.session_state.pop("ask_story_out", None)
                st.session_state.pop("ask_story_area", None)
                st.session_state["ask_story_n"] = int(st.session_state.get("ask_story_n") or 0) + 1
                if loaded and loaded.final_story:
                    st.session_state["ask_story_out"] = loaded.final_story
                st.rerun()

    cats = session.query(Category).order_by(Category.name).all()
    cat_names = ["(any)"] + [c.name for c in cats]
    c1, c2 = st.columns(2)
    with c1:
        ask_cat = st.selectbox("Category (optional)", cat_names, key="ask_cat")
    with c2:
        ask_model = st.text_input(
            "Model / System (optional)",
            key="ask_model",
            placeholder="RM2652, Schwintek, Hydro-Hot…",
        )
    with st.expander("📷 Read model from data plate photo", expanded=False):
        st.caption("Snap or upload the rating plate. TechTrack fills Model/System. Uses the shop AI already on this app.")
        plate_cam = st.camera_input("Snap data plate", key="ask_plate_cam")
        plate_up = st.file_uploader(
            "Or upload plate photo",
            type=["jpg", "jpeg", "png", "webp"],
            key="ask_plate_upload",
        )
        plate_img = plate_cam or plate_up
        if plate_img is not None:
            st.image(plate_img, caption="Plate photo", width=280)
            apply_plate_read_to_model_key("ask_model", plate_img, "ask_plate_read_btn")
    unity_gate = st.selectbox(
        "Lippert OneControl / Unity board on this coach?",
        ["Not sure", "Yes", "No"],
        key="ask_unity_gate",
        help="Not every unit has one. Yes/Not sure = include Unity board tests + Electrical manuals. No = skip Unity path.",
    )
    category_name = "" if ask_cat == "(any)" else ask_cat

    history = st.session_state.get("ask_chat") or []
    if history:
        st.markdown("#### Conversation")
        for m in history:
            role = m.get("role") or "user"
            content = m.get("content") or ""
            label = "You" if role == "user" else "Guided Diagnostics"
            with st.container(border=True):
                st.caption(label)
                st.markdown(content)
    else:
        st.info("Describe the symptom, what you have already checked, or paste an error code.")
    if st.session_state.pop("ask_reset_input", False):
        st.session_state["ask_input"] = ""

    auto_pages = st.session_state.get("ask_auto_show") or []
    if auto_pages:
        render_on_demand_library_pages(auto_pages)
    elif st.session_state.pop("ask_auto_show_failed", None):
        st.warning(
            "You asked for a figure/page, but TechTrack could not load a matching shop-library PDF page "
            "(wrong/missing file path, R2 download failed, or page render unavailable). "
            "There is no chat photo embed — only the real library renderer."
        )

    st.text_area(
        "Your message",
        key="ask_input",
        height=100,
        placeholder="Customer states fridge not cooling on gas or electric. Display is on. Unit is level…",
    )

    # Optional Pass/Fail or Yes/No when the hard-tree current node is binary
    _flow_now = st.session_state.get("ask_flow") or {}
    _proc_now = None
    _node_now = None
    if _flow_now.get("procedure_id") and _flow_now.get("node_id"):
        _proc_now = PROCEDURE_TREES.get(_flow_now.get("procedure_id"))
        _node_now = get_procedure_node(_proc_now, _flow_now.get("node_id")) if _proc_now else None
    _bin = binary_button_labels(_node_now) if _node_now else None
    if _bin:
        _bl, _bk, _br, _brk = _bin
        bb1, bb2 = st.columns(2)
        if bb1.button(_bl, key="ask_flow_yes", use_container_width=True):
            st.session_state["ask_input"] = _bk
            st.session_state["ask_force_send"] = True
        if bb2.button(_br, key="ask_flow_no", use_container_width=True):
            st.session_state["ask_input"] = _brk
            st.session_state["ask_force_send"] = True

    b1, b2, b3 = st.columns(3)
    with b1:
        send = st.button("Send", type="primary", key="ask_send", use_container_width=True)
    with b2:
        new_chat = st.button("Start new chat", key="ask_new", use_container_width=True)
    with b3:
        write_story = st.button("Write warranty story", key="ask_story", use_container_width=True)

    if send or st.session_state.pop("ask_force_send", False):
        msg = (st.session_state.get("ask_input") or "").strip()
        if not msg:
            st.warning("Type a message first.")
        else:
            with st.spinner("Searching manuals and thinking…"):
                reply, new_flow = guided_diagnostics_reply(
                    msg,
                    category_name,
                    ask_model or "",
                    history,
                    unity_gate=unity_gate,
                    ask_flow=st.session_state.get("ask_flow"),
                )
            st.session_state["ask_flow"] = new_flow
            history = list(history)
            history.append({"role": "user", "content": msg})
            history.append({"role": "assistant", "content": reply})
            st.session_state["ask_chat"] = history
            st.session_state["ask_chat_id"] = persist_ask_turn(
                user["id"],
                st.session_state.get("ask_chat_id"),
                category_name,
                ask_model or "",
                msg,
                reply,
            )
            if wants_library_figures(msg):
                # Prefer current reply cites; else fall back to prior coach Source lines
                coach_for_pages = reply or ""
                if not parse_cited_pages_from_text(coach_for_pages):
                    for m in reversed(history[:-1] if history else []):
                        if (m.get("role") or "") == "assistant":
                            coach_for_pages = m.get("content") or coach_for_pages
                            break
                pages = resolve_requested_library_pages(msg, coach_for_pages)
                st.session_state["ask_auto_show"] = pages
                st.session_state["ask_auto_show_failed"] = not bool(pages)
            else:
                st.session_state.pop("ask_auto_show", None)
                st.session_state.pop("ask_auto_show_failed", None)
            st.session_state["ask_reset_input"] = True
            st.rerun()

    if new_chat:
        st.session_state["ask_chat"] = []
        st.session_state["ask_chat_id"] = None
        clear_ask_source_state()
        st.session_state.pop("ask_story_out", None)
        st.session_state.pop("ask_story_area", None)
        st.session_state["ask_story_n"] = int(st.session_state.get("ask_story_n") or 0) + 1
        st.session_state["ask_reset_input"] = True
        st.rerun()

    if write_story:
        draft = (st.session_state.get("ask_input") or "").strip()
        if draft:
            history = list(history)
            history.append({"role": "user", "content": draft})
            st.session_state["ask_chat"] = history
            st.session_state["ask_chat_id"] = persist_ask_turn(
                user["id"],
                st.session_state.get("ask_chat_id"),
                category_name,
                ask_model or "",
                draft,
                "(notes recorded for warranty story)",
            )
            st.session_state["ask_reset_input"] = True
        if not history:
            st.warning("Chat is empty. Type the notes or send a message first, then write the story.")
        else:
            with st.spinner("Writing shop notes from what you actually recorded…"):
                story = ask_chat_to_warranty_story(history, category_name, ask_model or "")
            st.session_state["ask_story_out"] = story
            # text_area(key=) ignores value= after first mount. Bump the key so
            # this click remounts the box with the newly generated story.
            st.session_state.pop("ask_story_area", None)
            n = int(st.session_state.get("ask_story_n") or 0) + 1
            st.session_state["ask_story_n"] = n
            st.session_state[f"ask_story_area_{n}"] = story
            cid = st.session_state.get("ask_chat_id")
            if cid:
                chat_row = session.query(AskChat).get(cid)
                if chat_row:
                    chat_row.final_story = story
                    chat_row.updated_date = datetime.now()
                    session.commit()
            st.rerun()

    if st.session_state.get("ask_story_out"):
        st.markdown("### Shop notes / warranty story")
        _story_n = int(st.session_state.get("ask_story_n") or 0)
        _story_key = f"ask_story_area_{_story_n}"
        if _story_key not in st.session_state:
            st.session_state[_story_key] = st.session_state["ask_story_out"]
        st.text_area(
            "Copy into the warranty claim",
            height=280,
            key=_story_key,
        )
        st.caption(
            "Only uses tests and readings you typed. Recommended checks are left out unless you said you did them. "
            "Start a new chat to begin a different job."
        )

# =========================================================
# DOCUMENT LIBRARY
# =========================================================
with tab_lib:
    st.subheader("📚 Document Library (Manuals & Troubleshooting)")
    cats = session.query(Category).order_by(Category.name).all()
    if not cats:
        st.warning("No categories yet. Ask a manager to create some.")
    else:
        cat_name = st.selectbox("Select Category", [c.name for c in cats], key="lib_cat")
        cat = next(c for c in cats if c.name == cat_name)
        q = st.text_input("Search documents by title or keyword", key="lib_search")
        docs = session.query(Document).filter_by(category_id=cat.id).order_by(Document.title).all()
        if q.strip():
            terms = q.lower().split()
            docs = [
                d for d in docs
                if all(t in f"{d.title} {d.keywords or ''}".lower() for t in terms)
            ]
        st.write(f"**{len(docs)} document(s) found**")
        if not docs:
            st.info("No documents matched your search.")
        for d in docs:
            with st.container(border=True):
                idx = "✅" if d.indexed else "⚠️ not indexed"
                st.write(f"**{d.title}** · {idx}")
                if d.keywords:
                    st.caption(d.keywords)
                r2_download_button("⬇️ Download", d.file_path, f"{d.title}.pdf", f"lib_dl_{d.id}")

# =========================================================
# SAFETY
# =========================================================
with tab_safety:
    st.subheader("🛡️ Safety / Compliance")
    st.markdown("#### Safety Documents")
    sq = st.text_input("Search safety documents", key="safety_doc_search")
    sdocs = session.query(SafetyDocument).order_by(SafetyDocument.title).all()
    if sq.strip():
        terms = sq.lower().split()
        sdocs = [d for d in sdocs if all(t in f"{d.title} {d.keywords or ''}".lower() for t in terms)]
    if not sdocs:
        st.info("No safety documents available.")
    for d in sdocs:
        with st.container(border=True):
            st.write(f"**{d.title}**")
            r2_download_button("⬇️ Download", d.file_path, f"{d.title}.pdf", f"saf_dl_{d.id}")

    st.markdown("#### Safety Meetings - Acknowledgement Required")
    meetings = session.query(SafetyMeeting).order_by(SafetyMeeting.created_date.desc()).all()
    if not meetings:
        st.info("No safety meetings have been created yet.")
    for m in meetings:
        with st.container(border=True):
            st.write(f"**{m.title}**")
            st.caption(f"Meeting Date: {m.meeting_date or '-'} · Created: {m.created_date}")
            if m.notes:
                st.write(m.notes)
            if m.file_path:
                r2_download_button("Download Presentation", m.file_path, f"{m.title}.pdf", f"meet_dl_{m.id}")
            ack = session.query(SafetyAcknowledgement).filter_by(meeting_id=m.id, user_id=user["id"]).first()
            if ack:
                st.success(f"✅ You acknowledged this meeting on {ack.signed_at}")
            else:
                if st.checkbox(
                    "I attended this safety meeting, received the training, and understand the material.",
                    key=f"ack_chk_{m.id}",
                ):
                    if st.button("Sign Acknowledgement", key=f"ack_btn_{m.id}", type="primary"):
                        session.add(SafetyAcknowledgement(meeting_id=m.id, user_id=user["id"], understood=True))
                        session.commit()
                        st.success("Acknowledgement recorded. Thank you.")
                        st.rerun()

# =========================================================
# TEAM OVERVIEW (manager)
# =========================================================
if is_manager and tab_team is not None:
    with tab_team:
        st.subheader("Certificate & Safety Summary")
        techs = session.query(User).filter_by(is_active=True).order_by(User.full_name).all()
        for t in techs:
            cert_n = session.query(Certificate).filter_by(user_id=t.id).count()
            sp = get_safety_progress(t.id)
            with st.container(border=True):
                st.write(f"**{t.full_name}** ({t.role})")
                c1, c2 = st.columns(2)
                c1.metric("Certificates", cert_n)
                c2.metric("Safety Progress", f"{sp}%")
                if sp < 100:
                    meetings = session.query(SafetyMeeting).all()
                    missing = []
                    for m in meetings:
                        if not session.query(SafetyAcknowledgement).filter_by(meeting_id=m.id, user_id=t.id).first():
                            missing.append(m.title)
                    if missing:
                        st.warning("⚠️ Missing acknowledgements: " + ", ".join(missing))
                with st.expander(f"{t.full_name}'s certificates"):
                    for cert in session.query(Certificate).filter_by(user_id=t.id).all():
                        st.write(f"- **{cert.title}** ({cert.issuer or '-'})")

        st.markdown("#### Recent Diagnostic Jobs (all techs)")
        jobs = session.query(DiagnosticJob).order_by(DiagnosticJob.updated_date.desc()).limit(25).all()
        for j in jobs:
            u = session.query(User).get(j.user_id)
            st.write(f"**WO {j.wo_number}** · {j.status} · {u.full_name if u else '?'} · {j.category_name} · {(j.concern or '')[:80]}")

# =========================================================
# MANAGER TOOLS
# =========================================================
if is_manager and tab_mgr is not None:
    with tab_mgr:
        st.subheader("🛠️ Manager Tools")
        st.warning(
            "The full database (titles, keywords, users, WO jobs, chats) now auto-saves to R2. "
            "If Streamlit wipes the local file, TechTrack restores the last good copy on boot. "
            "You can still download a copy under **Database Backup & Restore**."
        )
        doc_count = session.query(Document).count()
        st.info(f"Library right now: **{doc_count}** document record(s) in the database.")

        with st.expander("👤 User Management", expanded=False):
            st.markdown("#### Add New User")
            nu = st.text_input("Username", key="new_username")
            nn = st.text_input("Full Name", key="new_fullname")
            np = st.text_input("Temporary Password", key="new_pass")
            nr = st.selectbox("Role", ["Technician", "Manager"], key="new_role")
            if st.button("Create User"):
                if nu and nn and np:
                    if session.query(User).filter_by(username=nu.strip().lower()).first():
                        st.error("Username already exists.")
                    else:
                        session.add(User(
                            username=nu.strip().lower(),
                            password_hash=hash_password(np),
                            full_name=nn.strip(),
                            role=nr,
                        ))
                        session.commit()
                        st.success(f"Created {nu}")
                        st.rerun()
                else:
                    st.warning("All fields required.")

            st.markdown("#### Existing Users")
            for u in session.query(User).order_by(User.full_name).all():
                with st.container(border=True):
                    st.write(f"**{u.full_name}** (@{u.username}) · {u.role} · Active: {u.is_active}")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        new_role = st.selectbox("Role", ["Technician", "Manager"], index=0 if u.role != "Manager" else 1, key=f"role_{u.id}")
                        if st.button("Update Role", key=f"upd_role_{u.id}"):
                            u.role = new_role
                            session.commit()
                            st.success("Role updated")
                            st.rerun()
                    with c2:
                        if st.button("Reset Password", key=f"reset_{u.id}"):
                            u.password_hash = hash_password("temp123")
                            session.commit()
                            st.success(f"Password for {u.username} reset to: temp123")
                    with c3:
                        if st.button("Deactivate" if u.is_active else "Activate", key=f"act_{u.id}"):
                            u.is_active = not u.is_active
                            session.commit()
                            st.rerun()

        with st.expander("📁 Manage Categories", expanded=False):
            st.markdown("#### Add Category")
            cn = st.text_input("Category Name", key="cat_new")
            if st.button("Create Category"):
                if cn.strip() and not session.query(Category).filter_by(name=cn.strip()).first():
                    session.add(Category(name=cn.strip()))
                    session.commit()
                    st.success("Category created.")
                    st.rerun()
                else:
                    st.warning("Name required or already exists.")
            for c in session.query(Category).order_by(Category.name).all():
                cols = st.columns([3, 1])
                cols[0].write(f"**{c.name}**")
                if cols[1].button("Delete", key=f"del_cat_{c.id}"):
                    if session.query(Document).filter_by(category_id=c.id).count() == 0:
                        session.delete(c)
                        session.commit()
                        st.rerun()
                    else:
                        st.error("Category has documents - move or delete them first.")

        with st.expander("📤 Upload Documents to Categories", expanded=False):
            if not r2_available():
                st.error("R2 storage is not configured. Check Streamlit Secrets.")
            else:
                cats = session.query(Category).order_by(Category.name).all()
                if cats:
                    ucat = st.selectbox("Category", [c.name for c in cats], key="up_cat")
                    utitle = st.text_input("Document Title", key="up_title")
                    ukw = st.text_input("Keywords (models, brand names - helps search)", key="up_kw", placeholder="Schwintek, In-Wall, Lippert, error codes")
                    ufile = st.file_uploader("PDF / PPTX / Image", type=["pdf", "pptx", "png", "jpg", "jpeg"], key="up_file")
                    if st.button("Upload Document", type="primary"):
                        if utitle and ufile:
                            cat = session.query(Category).filter_by(name=ucat).first()
                            ext = (ufile.name.split(".")[-1] or "pdf").lower()
                            key = f"documents/{cat.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{ufile.name}"
                            ctype = "application/pdf" if ext == "pdf" else "application/octet-stream"
                            if r2_upload(ufile.getvalue(), key, ctype):
                                doc = Document(
                                    category_id=cat.id,
                                    title=utitle.strip(),
                                    file_path=key,
                                    file_type=ext,
                                    uploaded_by=user["id"],
                                    keywords=ukw.strip(),
                                )
                                session.add(doc)
                                session.commit()
                                if ext == "pdf":
                                    ok, note = index_document_from_bytes(doc, ufile.getvalue())
                                    if ok:
                                        st.success(f"Document uploaded and indexed. {note}")
                                    else:
                                        st.warning(f"Uploaded, but not indexed: {note}")
                                else:
                                    st.success("Document uploaded (non-PDF - not indexed for guided diagnostics).")
                                st.rerun()
                        else:
                            st.warning("Title and file required.")

        with st.expander("🧠 Re-index Manuals for Guided Diagnostics", expanded=False):
            st.caption(
                "Pulls each PDF from storage, extracts text, and stores searchable chunks. "
                "Run this after restoring a database or if older uploads were never indexed."
            )
            if not PYPDF_AVAILABLE:
                st.error("Add `pypdf` to requirements.txt and reboot the app.")
            total_docs = session.query(Document).count()
            indexed_docs = session.query(Document).filter_by(indexed=True).count()
            chunk_count = session.query(DocChunk).count()
            st.write(f"Documents: **{total_docs}** • Indexed: **{indexed_docs}** • Text chunks: **{chunk_count}**")
            if st.button("Re-index All PDFs", type="primary"):
                ok_n = fail_n = 0
                prog = st.progress(0.0)
                docs = session.query(Document).all()
                for i, doc in enumerate(docs):
                    ok, note = index_document_from_r2(doc)
                    if ok:
                        ok_n += 1
                    else:
                        fail_n += 1
                    st.write(f"{'✅' if ok else '⚠️'} {doc.title} - {note}")
                    prog.progress((i + 1) / max(len(docs), 1))
                st.success(f"Indexed OK: {ok_n} · Skipped/failed: {fail_n}")

            st.markdown("#### Index status by document")
            for d in session.query(Document).order_by(Document.title).all():
                st.write(f"{'✅' if d.indexed else '⚠️'} **{d.title}** - {d.index_note or ('indexed' if d.indexed else 'not indexed')}")

        with st.expander("✏️ Manage Documents (Rename / Edit / Delete)", expanded=False):
            cats = session.query(Category).order_by(Category.name).all()
            if not cats:
                st.info("No categories yet.")
            else:
                mcat = st.selectbox("Category", [c.name for c in cats], key="manage_doc_cat")
                cat = session.query(Category).filter_by(name=mcat).first()
                docs = session.query(Document).filter_by(category_id=cat.id).order_by(Document.title).all()
                st.write(f"**{len(docs)} document(s) in {mcat}**")
                if not docs:
                    st.info("No documents in this category.")
                for d in docs:
                    with st.container(border=True):
                        st.write(f"**Current title:** {d.title}")
                        st.caption("Indexed" if d.indexed else "Not indexed")
                        nt = st.text_input("Title", value=d.title, key=f"edit_title_{d.id}")
                        nk = st.text_input("Keywords", value=d.keywords or "", key=f"edit_kw_{d.id}")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("💾 Save Changes", key=f"save_doc_{d.id}"):
                                d.title = nt.strip()
                                d.keywords = nk.strip()
                                session.query(DocChunk).filter_by(document_id=d.id).update(
                                    {"title": d.title, "keywords": d.keywords}
                                )
                                session.commit()
                                st.success("Saved")
                                st.rerun()
                        with c2:
                            r2_download_button("⬇️ Download", d.file_path, f"{d.title}.pdf", f"mgr_dl_{d.id}")
                        with c3:
                            if st.button("🗑️ Delete", key=f"del_doc_{d.id}"):
                                clear_document_chunks(d.id)
                                session.delete(d)
                                session.commit()
                                st.success("Document deleted from library.")
                                st.rerun()

        with st.expander("🛡️ Safety Documents & Meetings", expanded=False):
            if r2_available():
                st.markdown("#### Upload Safety Document")
                stitle = st.text_input("Safety Document Title", key="saf_up_title")
                skw = st.text_input("Keywords", key="saf_up_kw")
                sfile = st.file_uploader("File", type=["pdf", "pptx", "png", "jpg"], key="saf_up_file")
                if st.button("Upload Safety Document"):
                    if stitle and sfile:
                        key = f"safety/docs/{datetime.now().strftime('%Y%m%d%H%M%S')}_{sfile.name}"
                        if r2_upload(sfile.getvalue(), key, "application/pdf"):
                            session.add(SafetyDocument(
                                title=stitle.strip(),
                                file_path=key,
                                file_type=(sfile.name.split(".")[-1] or "pdf").lower(),
                                uploaded_by=user["id"],
                                keywords=skw.strip(),
                            ))
                            session.commit()
                            st.success("Safety document uploaded permanently!")
                            st.rerun()

                st.markdown("#### Create Safety Meeting")
                mt = st.text_input("Meeting Title", key="meet_title")
                md = st.text_input("Meeting Date", key="meet_date")
                mn = st.text_area("Notes / Agenda", key="meet_notes")
                mf = st.file_uploader("PowerPoint or PDF of the training", type=["pdf", "pptx"], key="meet_file")
                if st.button("Create Safety Meeting", type="primary"):
                    if mt.strip():
                        fpath = ""
                        if mf:
                            key = f"safety/meetings/{datetime.now().strftime('%Y%m%d%H%M%S')}_{mf.name}"
                            if r2_upload(mf.getvalue(), key, "application/pdf"):
                                fpath = key
                            else:
                                st.error("Failed to upload the presentation file.")
                                fpath = None
                        if fpath is not None:
                            session.add(SafetyMeeting(
                                title=mt.strip(),
                                meeting_date=md.strip(),
                                file_path=fpath,
                                notes=mn.strip(),
                                created_by=user["id"],
                            ))
                            session.commit()
                            st.success("Safety meeting created. Technicians can now acknowledge it.")
                            st.rerun()
                    else:
                        st.error("Title is required.")
            else:
                st.error("R2 storage is not configured.")

        with st.expander("🔗 Re-link files already in R2 (no re-upload)", expanded=False):
            st.caption(
                "Your PDFs may still be in cloud storage even if the app library shows 0. "
                "List them here, set title/category/keywords once, and register - no upload from your PC."
            )
            if not r2_available():
                st.error("R2 storage is not configured.")
            else:
                folder = st.selectbox(
                    "Folder to scan",
                    ["documents/", "certificates/", "safety/docs/", "safety/meetings/"],
                    key="r2_folder",
                )
                if st.button("List files in R2", key="r2_list_btn"):
                    with st.spinner("Listing storage..."):
                        keys, err = r2_list_keys(folder, max_keys=300)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["r2_keys"] = keys
                keys = st.session_state.get("r2_keys") or []
                if keys:
                    unlinked = [k for k in keys if not r2_key_already_registered(k)]
                    linked_n = len(keys) - len(unlinked)
                    st.write(f"**{len(keys)}** file(s) · **{len(unlinked)}** not in library · **{linked_n}** already linked")
                    cats = session.query(Category).order_by(Category.name).all()
                    techs = session.query(User).filter_by(is_active=True).order_by(User.full_name).all()
                    show = unlinked[:300]
                    for i, key in enumerate(show):
                        with st.container(border=True):
                            st.caption(key)
                            default_title = guess_title_from_key(key)
                            if key.startswith("documents/"):
                                if not cats:
                                    st.warning("Create at least one category before linking manuals.")
                                    continue
                                t = st.text_input("Title", value=default_title, key=f"r2t_{i}")
                                cat_name = st.selectbox("Category", [c.name for c in cats], key=f"r2c_{i}")
                                kw = st.text_input("Keywords", key=f"r2k_{i}", placeholder="Schwintek, model numbers…")
                                if st.button("Link into library + index", key=f"r2l_{i}"):
                                    cat = session.query(Category).filter_by(name=cat_name).first()
                                    doc = Document(
                                        category_id=cat.id,
                                        title=t.strip() or default_title,
                                        file_path=key,
                                        file_type="pdf" if key.lower().endswith(".pdf") else "bin",
                                        uploaded_by=user["id"],
                                        keywords=kw.strip(),
                                    )
                                    session.add(doc)
                                    session.commit()
                                    if doc.file_type == "pdf":
                                        ok, note = index_document_from_r2(doc)
                                        st.success(f"Linked and indexed: {note}" if ok else f"Linked, index issue: {note}")
                                    else:
                                        st.success("Linked (non-PDF, not indexed).")
                                    st.rerun()
                            elif key.startswith("certificates/"):
                                t = st.text_input("Certificate title", value=default_title, key=f"r2ct_{i}")
                                tech_names = [u.full_name for u in techs]
                                tn = st.selectbox("Assign to tech", tech_names, key=f"r2cu_{i}")
                                if st.button("Link certificate", key=f"r2cl_{i}"):
                                    tech = next(u for u in techs if u.full_name == tn)
                                    session.add(Certificate(
                                        user_id=tech.id,
                                        title=t.strip() or default_title,
                                        file_path=key,
                                        uploaded_by=user["id"],
                                    ))
                                    session.commit()
                                    st.success("Certificate linked.")
                                    st.rerun()
                            elif key.startswith("safety/"):
                                t = st.text_input("Safety doc / meeting title", value=default_title, key=f"r2st_{i}")
                                if st.button("Link as safety document", key=f"r2sl_{i}"):
                                    session.add(SafetyDocument(
                                        title=t.strip() or default_title,
                                        file_path=key,
                                        uploaded_by=user["id"],
                                    ))
                                    session.commit()
                                    st.success("Safety document linked.")
                                    st.rerun()
                            else:
                                st.caption("Unknown folder - open documents/ certificates/ or safety/ for guided linking.")
                    if len(unlinked) > 40:
                        st.info(f"Showing first 300 of {len(unlinked)} unlinked files. Link some, then list again.")
                    if not unlinked:
                        st.success("All listed files are already linked in the database.")

        with st.expander("📦 Export library catalog (titles & keywords)", expanded=False):
            st.caption(
                "Download a JSON list of every manual title, keywords, category, and R2 path. "
                "Keep this with your DB backup - it is the naming work."
            )
            if session.query(Document).count() == 0:
                st.info("No documents in the database to export yet.")
            else:
                catalog = export_library_catalog()
                st.download_button(
                    "⬇️ Download library_catalog.json",
                    catalog,
                    file_name=f"techtrack_library_catalog_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    type="primary",
                )

        with st.expander("💾 Database Backup & Restore", expanded=True):
            last_ok = st.session_state.get("_db_backup_ok")
            last_n = st.session_state.get("_db_backup_docs")
            if st.session_state.get("_db_restored_from_r2"):
                st.success(
                    f"Restored library from cloud backup "
                    f"({st.session_state.get('_db_restored_docs') or '?'} documents)."
                )
            if last_ok:
                st.info(f"Last automatic cloud save: **{last_ok}** · {last_n or '?'} documents")
            else:
                st.caption("Automatic cloud save runs after real library / job / chat changes.")
            if st.button("Save to cloud now", type="primary", key="force_r2_db"):
                ok, note = maybe_backup_db_to_r2(force=True)
                if ok:
                    st.success(note)
                else:
                    st.warning(note)
            c1, c2 = st.columns(2)
            with c1:
                if Path(DB_PATH).exists():
                    with open(DB_PATH, "rb") as f:
                        st.download_button(
                            "⬇️ Download Current Database",
                            f,
                            file_name=f"techtrack_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                            mime="application/octet-stream",
                            type="primary",
                        )
            with c2:
                up_db = st.file_uploader("Upload .db backup to restore", type=["db"], key="restore_db")
                if up_db and st.button("Restore Database"):
                    if Path(DB_PATH).exists():
                        shutil.copy(DB_PATH, DB_PATH + ".bak")
                    with open(DB_PATH, "wb") as f:
                        f.write(up_db.getbuffer())
                    st.success("Database restored. Refresh the page, then run Re-index All PDFs.")
                    st.rerun()

        with st.expander("📜 All Team Certificates"):
            all_certs = session.query(Certificate).order_by(Certificate.created_date.desc()).all()
            for cert in all_certs:
                u = session.query(User).get(cert.user_id)
                st.write(f"**{cert.title}** - {u.full_name if u else 'Unknown'} ({cert.issuer or '-'})")

maybe_backup_db_to_r2(force=False)
st.sidebar.caption("v4.10.0 • Tacoma RV Center • Guided Testing ENGINE • Auto DB backup")
