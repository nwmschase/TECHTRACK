"""
RV TechTrack v4.4
- Login + Roles (Technician / Manager)
- Certificate Hub
- Searchable Document Library by Category
- Guided Diagnostics Jobs (WO #) + interactive findings + warranty story
- Safety / Compliance + Meeting Acknowledgements
- Team Overview (Certificates + Safety Progress)
- AI Tech Story Improver (Groq) — standalone + end-of-job
- Permanent file storage via Cloudflare R2
- Mobile-friendly
"""
import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
from pathlib import Path
import os
import shutil
import hashlib
import secrets
import io
import re
import json

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

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

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="RV TechTrack v4.4",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stButton > button {
        min-height: 2.8rem;
        font-size: 1.05rem;
        border-radius: 10px;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
    }
    .block-container {
        padding-top: 4rem !important;
        padding-bottom: 2rem;
    }
    div[data-testid="stHorizontalBlock"] {
        margin-top: 0.8rem;
        margin-bottom: 0.8rem;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------- CONFIG ----------------
DB_PATH = "rv_techtrack_v4.db"
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# ---------------- R2 HELPERS ----------------
def get_r2_client():
    if not BOTO3_AVAILABLE:
        return None
    required = ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT_URL", "R2_BUCKET_NAME"]
    if not all(k in st.secrets for k in required):
        return None
    return boto3.client(
        "s3",
        endpoint_url=st.secrets["R2_ENDPOINT_URL"],
        aws_access_key_id=st.secrets["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["R2_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )


def r2_upload(file_obj, key: str, content_type: str = "application/octet-stream") -> bool:
    client = get_r2_client()
    if client is None:
        return False
    try:
        client.upload_fileobj(
            file_obj,
            st.secrets["R2_BUCKET_NAME"],
            key,
            ExtraArgs={"ContentType": content_type}
        )
        return True
    except Exception as e:
        st.error(f"Upload to storage failed: {e}")
        return False


def r2_download_bytes(key: str):
    client = get_r2_client()
    if client is None:
        return None
    try:
        obj = client.get_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=key)
        return obj["Body"].read()
    except Exception:
        return None


def r2_download_button(label: str, key: str, filename: str, button_key: str):
    client = get_r2_client()
    if client is None:
        st.warning("Storage not configured")
        return
    try:
        obj = client.get_object(Bucket=st.secrets["R2_BUCKET_NAME"], Key=key)
        data = obj["Body"].read()
        st.download_button(label, data=data, file_name=filename, key=button_key)
    except Exception as e:
        st.error(f"Could not download file: {e}")


def r2_available() -> bool:
    return get_r2_client() is not None


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
    file_type = Column(String(20))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())
    keywords = Column(Text)
    indexed = Column(Boolean, default=False)
    index_note = Column(String(250))


class DocChunk(Base):
    __tablename__ = "doc_chunks"
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    title = Column(String(250))
    page = Column(Integer, default=1)
    chunk_text = Column(Text, nullable=False)
    keywords = Column(Text)


class Certificate(Base):
    __tablename__ = "certificates"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(250), nullable=False)
    issuer = Column(String(150))
    file_path = Column(String(400), nullable=False)
    issued_date = Column(String(50))
    notes = Column(Text)
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())


class SafetyDocument(Base):
    __tablename__ = "safety_documents"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    file_path = Column(String(400), nullable=False)
    file_type = Column(String(20))
    uploaded_by = Column(Integer, ForeignKey("users.id"))
    created_date = Column(DateTime, default=func.now())
    keywords = Column(Text)


class SafetyMeeting(Base):
    __tablename__ = "safety_meetings"
    id = Column(Integer, primary_key=True)
    title = Column(String(250), nullable=False)
    meeting_date = Column(String(50))
    file_path = Column(String(400))
    notes = Column(Text)
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
    """Work-order based diagnostic session — resume anytime, story at end."""
    __tablename__ = "diagnostic_jobs"
    id = Column(Integer, primary_key=True)
    wo_number = Column(String(80), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_name = Column(String(150), nullable=False)
    model_text = Column(String(250))
    concern = Column(Text, nullable=False)
    plan_text = Column(Text)
    findings = Column(Text)
    step_log = Column(Text)  # JSON list of {step, result, notes, at}
    sources_text = Column(Text)
    final_story = Column(Text)
    status = Column(String(30), default="in_progress")  # in_progress | complete
    created_date = Column(DateTime, default=func.now())
    updated_date = Column(DateTime, default=func.now(), onupdate=func.now())


Base.metadata.create_all(engine)
session = Session()


def _ensure_schema_upgrades():
    try:
        with engine.connect() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(documents)").fetchall()]
            if "indexed" not in cols:
                conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN indexed BOOLEAN DEFAULT 0")
                conn.commit()
            if "index_note" not in cols:
                conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN index_note VARCHAR(250)")
                conn.commit()
    except Exception:
        pass


_ensure_schema_upgrades()


# ---------------- AUTH HELPERS ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${pwd_hash}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, pwd_hash = stored.split("$", 1)
        return hashlib.sha256((salt + password).encode()).hexdigest() == pwd_hash
    except Exception:
        return False


def get_safety_progress(user_id: int) -> float:
    total = session.query(SafetyMeeting).count()
    if total == 0:
        return 100.0
    signed = session.query(SafetyAcknowledgement.meeting_id).filter_by(user_id=user_id).distinct().count()
    return round((signed / total) * 100, 1)


# ---------------- STORY + DIAGNOSTICS AI ----------------
def improve_tech_story(concern: str, tech_notes: str) -> str:
    concern = (concern or "").strip()
    tech_notes = (tech_notes or "").strip()
    if not concern and not tech_notes:
        return ""

    if not GROQ_AVAILABLE or "GROQ_API_KEY" not in st.secrets:
        return (
            "**CONCERN**\n"
            f"{concern or 'Customer reported an issue requiring diagnosis and repair.'}\n\n"
            "**CAUSE**\n"
            f"The root cause was identified during diagnostic testing. Technician notes: {tech_notes}\n\n"
            "**CORRECTION**\n"
            f"Corrective action performed based on findings: {tech_notes}\n\n"
            "All related systems were inspected and tested. Unit returned to service in fully functional condition."
        )

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        system_prompt = """You are an expert RV service writer who creates strong, professional warranty claim narratives for RV manufacturers (Lippert, Dometic, etc.).

You will be given two pieces of information:
1. CUSTOMER CONCERN – what the customer reported
2. TECHNICIAN NOTES – what the tech observed and did

Your job is to write a clear warranty story using this EXACT structure and order:

CONCERN
(Clearly restate and slightly expand the customer's reported problem)

CAUSE
(Explain the root cause that was found. Base this on the technician notes. You may add logical diagnostic reasoning that would normally be performed.)

CORRECTION
(Detail the repair steps performed. You may add commonly performed related steps such as system recovery, evacuation, leak check, recharge, operational testing under load, verification of related systems, etc., when they would reasonably be part of this repair.)

Rules:
- Always start with CONCERN, then CAUSE, then CORRECTION. Never change this order.
- Stay faithful to the facts the technician provided. Do not invent a completely different failure or repair.
- It is acceptable and encouraged to expand short notes into complete professional sentences.
- Add logical missing steps that a competent RV technician would normally perform for this type of job.
- Use professional but plain language that warranty reviewers expect.
- Make the story complete enough to support the labor time claimed.
- Write in short paragraphs under each heading. Do not use bullet points.
- Output ONLY the three sections (CONCERN, CAUSE, CORRECTION). No introduction or extra commentary."""

        user_prompt = f"""CUSTOMER CONCERN:
{concern or "(not provided)"}

TECHNICIAN NOTES:
{tech_notes or "(not provided)"}

Write the warranty story now following the rules above."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.35,
            max_tokens=900
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error contacting AI: {e}\n\nConcern: {concern}\nNotes: {tech_notes}"


def story_from_diagnostic_job(job: "DiagnosticJob") -> str:
    """Merge concern + diagnostic plan context + findings into warranty story."""
    notes_parts = []
    if job.model_text:
        notes_parts.append(f"System/model: {job.model_text}")
    if job.category_name:
        notes_parts.append(f"Category: {job.category_name}")
    if job.findings:
        notes_parts.append(f"Technician findings and work performed:\n{job.findings}")
    if job.step_log:
        try:
            steps = json.loads(job.step_log)
            if steps:
                lines = []
                for s in steps:
                    lines.append(
                        f"- {s.get('step', 'Step')}: {s.get('result', '')} "
                        f"{('— ' + s['notes']) if s.get('notes') else ''}".strip()
                    )
                notes_parts.append("Diagnostic step log:\n" + "\n".join(lines))
        except Exception:
            notes_parts.append(f"Step log:\n{job.step_log}")
    if job.plan_text:
        # Light context only — story should favor actual findings
        notes_parts.append(
            "Reference (guided test plan used during diagnosis — use only where it matches actual work):\n"
            + job.plan_text[:1500]
        )
    tech_notes = "\n\n".join(notes_parts)
    return improve_tech_story(job.concern, tech_notes)


# ---------------- DOCUMENT INDEX + SEARCH ----------------
def extract_pdf_pages(file_bytes: bytes):
    if not PYPDF_AVAILABLE:
        return []
    pages = []
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                pages.append((i + 1, text))
    except Exception:
        return []
    return pages


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
                keywords=doc.keywords
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


def tokenize(text: str):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2]


def search_manual_chunks(category_id, model_text: str, symptom: str, limit: int = 8):
    q = session.query(DocChunk)
    if category_id:
        q = q.filter(DocChunk.category_id == category_id)
    chunks = q.all()
    if not chunks:
        return []
    query_terms = set(tokenize(f"{model_text} {symptom}"))
    if not query_terms:
        return chunks[:limit]
    scored = []
    for ch in chunks:
        hay = f"{ch.title or ''} {ch.keywords or ''} {ch.chunk_text or ''}".lower()
        score = 0
        for term in query_terms:
            if term in hay:
                title_kw = f"{ch.title or ''} {ch.keywords or ''}".lower()
                score += 4 if term in title_kw else 1
                score += min(hay.count(term), 3)
        if model_text.strip() and model_text.strip().lower() in hay:
            score += 6
        if score > 0:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def run_guided_diagnostics(category_name: str, model_text: str, symptom: str, chunks) -> tuple[str, str]:
    """Returns (plan_text, sources_text)."""
    if not chunks:
        msg = (
            "No matching manual text was found in TechTrack.\n\n"
            "- Check category selection\n"
            "- Try different keywords / model number\n"
            "- Ask a manager to upload/index the service manual\n"
            "- Scanned PDFs with no text cannot be searched until OCR is added"
        )
        return msg, ""

    sources = []
    context_parts = []
    for i, ch in enumerate(chunks, 1):
        sources.append(f"- {ch.title} (page {ch.page})")
        context_parts.append(
            f"[EXCERPT {i}] Manual: {ch.title} | Page: {ch.page}\n{ch.chunk_text}"
        )
    context = "\n\n".join(context_parts)
    sources_text = "\n".join(sources)

    if not GROQ_AVAILABLE or "GROQ_API_KEY" not in st.secrets:
        body = [
            "**Guided Diagnostics (AI offline — matching manual excerpts)**",
            "",
            f"**Category:** {category_name}",
            f"**Model/System:** {model_text or '—'}",
            f"**Symptom:** {symptom}",
            "",
            "**Sources:**",
            sources_text,
            ""
        ]
        for i, ch in enumerate(chunks[:5], 1):
            body.append(f"**Excerpt {i} — {ch.title} p.{ch.page}**")
            body.append(ch.chunk_text[:700] + ("..." if len(ch.chunk_text) > 700 else ""))
            body.append("")
        return "\n".join(body), sources_text

    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        system_prompt = """You are an expert RV technician coach helping shop techs diagnose and repair units.

You will receive:
- Category, optional model/system, and the reported symptom
- EXCERPTS from the shop's uploaded service manuals only

Rules:
1. Use ONLY the provided manual excerpts for procedures, specs, LED codes, and test steps.
2. If the excerpts do not cover the issue, say clearly what is missing. Do NOT invent OEM procedures.
3. Start with SAFETY notes when relevant (power, propane, crushing hazards, high voltage, hydraulic pressure).
4. Give a numbered GUIDED TEST sequence a tech can follow on the shop floor.
5. For each test: what to do, what result means, and what to do next (pass/fail branching when possible).
6. End with SOURCES listing the manual titles and page numbers you used.
7. Keep language plain and practical. Short sentences. No fluff.
8. Prefer manufacturer troubleshooting order when the excerpts show one."""

        user_prompt = f"""CATEGORY: {category_name}
MODEL / SYSTEM: {model_text or "(not provided)"}
SYMPTOM: {symptom}

MANUAL EXCERPTS:
{context}

Write the guided diagnostic plan now."""

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
            max_tokens=1400
        )
        answer = response.choices[0].message.content.strip()
        if "source" not in answer.lower():
            answer += "\n\n**Sources used**\n" + sources_text
        return answer, sources_text
    except Exception as e:
        return f"Error contacting AI: {e}", sources_text


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


# ---------------- SEED ----------------
def seed_data():
    if session.query(User).count() == 0:
        session.add(User(username="manager", password_hash=hash_password("manager123"), full_name="Shop Manager", role="Manager"))
        session.add(User(username="alex", password_hash=hash_password("tech123"), full_name="Alex Rivera", role="Technician"))
        session.add(User(username="jordan", password_hash=hash_password("tech123"), full_name="Jordan Hale", role="Technician"))
        session.commit()
    if session.query(Category).count() == 0:
        for name in [
            "Air Conditioner", "Furnace", "Water Heater", "Electrical Systems",
            "Refrigeration Systems", "Slide-Outs & Leveling", "Plumbing",
            "Generators", "Converters & Power Centers", "Solar"
        ]:
            session.add(Category(name=name))
        session.commit()


seed_data()

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "active_job_id" not in st.session_state:
    st.session_state.active_job_id = None

if st.session_state.user is None:
    st.title("🔧 RV TechTrack")
    st.subheader("Sign In")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In", type="primary")
        if submitted:
            u = session.query(User).filter_by(username=username, is_active=True).first()
            if u and verify_password(password, u.password_hash):
                st.session_state.user = {
                    "id": u.id,
                    "username": u.username,
                    "full_name": u.full_name,
                    "role": u.role
                }
                st.rerun()
            else:
                st.error("Invalid username or password")
    st.info("Default accounts (change after first login):\n- Manager: `manager` / `manager123`\n- Tech: `alex` or `jordan` / `tech123`")
    st.stop()

# ---------------- LOGGED IN ----------------
user = st.session_state.user
is_manager = user["role"] == "Manager"

st.sidebar.title("🔧 TechTrack")
st.sidebar.write(f"**{user['full_name']}**")
st.sidebar.caption(f"Role: {user['role']}")
if st.sidebar.button("Sign Out"):
    st.session_state.user = None
    st.session_state.active_job_id = None
    st.rerun()

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

nav_cols = st.columns(3 if is_manager else 2)
with nav_cols[0]:
    if st.button("📱 My Dashboard", use_container_width=True, type="primary" if st.session_state.page == "Dashboard" else "secondary"):
        st.session_state.page = "Dashboard"
        st.rerun()
with nav_cols[1]:
    if st.button("👥 Team Overview", use_container_width=True, type="primary" if st.session_state.page == "Overview" else "secondary"):
        st.session_state.page = "Overview"
        st.rerun()
if is_manager:
    with nav_cols[2]:
        if st.button("🛠️ Manager Tools", use_container_width=True, type="primary" if st.session_state.page == "Manager" else "secondary"):
            st.session_state.page = "Manager"
            st.rerun()

st.divider()

# =========================================================
# PAGE: MY DASHBOARD
# =========================================================
if st.session_state.page == "Dashboard":
    st.header(f"Welcome, {user['full_name']}")

    # -------- DIAGNOSTIC JOBS (WO-based) --------
    st.subheader("🔍 Diagnostic Jobs (Work Order)")
    st.caption(
        "Start or resume a job by work order number. TechTrack searches your manuals, "
        "guides testing, saves progress, and can write the warranty story when you're done."
    )

    categories = session.query(Category).order_by(Category.name).all()
    cat_names = [c.name for c in categories] if categories else []

    tab_active, tab_new, tab_list = st.tabs(["Active Job", "Start / Resume", "My Jobs"])

    # --- Start / Resume ---
    with tab_new:
        st.markdown("#### Start a new job or resume by WO #")
        wo_in = st.text_input("Work Order Number", key="wo_start", placeholder="e.g. 4521 or WO-4521")
        c_resume, c_new = st.columns(2)
        with c_resume:
            if st.button("Resume this WO", use_container_width=True):
                if not wo_in.strip():
                    st.warning("Enter a work order number.")
                else:
                    job = (
                        session.query(DiagnosticJob)
                        .filter(DiagnosticJob.wo_number == wo_in.strip())
                        .order_by(DiagnosticJob.updated_date.desc())
                        .first()
                    )
                    if not job:
                        st.error("No job found for that WO #. Start a new one below.")
                    else:
                        st.session_state.active_job_id = job.id
                        st.success(f"Resumed WO {job.wo_number}")
                        st.rerun()
        with c_new:
            pass

        st.markdown("---")
        st.markdown("#### New diagnostic job")
        if not cat_names:
            st.warning("No categories yet. Ask a manager to create categories and upload manuals.")
        else:
            nj_wo = st.text_input("Work Order #", key="nj_wo")
            nj_cat = st.selectbox("Category", cat_names, key="nj_cat")
            nj_model = st.text_input("Model / System (optional)", key="nj_model", placeholder="Schwintek, RM2652, Hydro-Sync…")
            nj_concern = st.text_area(
                "Customer concern / symptom",
                key="nj_concern",
                height=100,
                placeholder="Customer states slide only moves ~2 inches then one side stops."
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
                    if existing:
                        st.warning(
                            f"Open job already exists for WO {nj_wo.strip()} "
                            f"(id {existing.id}). Use Resume, or complete that job first."
                        )
                    else:
                        cat_obj = session.query(Category).filter_by(name=nj_cat).first()
                        with st.spinner("Searching manuals and building guided tests..."):
                            hits = search_manual_chunks(
                                cat_obj.id if cat_obj else None,
                                nj_model,
                                nj_concern,
                                limit=8
                            )
                            plan, sources = run_guided_diagnostics(nj_cat, nj_model, nj_concern, hits)
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
                            status="in_progress"
                        )
                        session.add(job)
                        session.commit()
                        st.session_state.active_job_id = job.id
                        st.success(f"Job started for WO {job.wo_number}")
                        st.rerun()

    # --- My Jobs list ---
    with tab_list:
        my_jobs = (
            session.query(DiagnosticJob)
            .filter_by(user_id=user["id"])
            .order_by(DiagnosticJob.updated_date.desc())
            .limit(40)
            .all()
        )
        if is_manager:
            st.caption("Showing your jobs. Managers can open any WO via Resume.")
        if not my_jobs:
            st.info("No diagnostic jobs yet.")
        else:
            for j in my_jobs:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"**WO {j.wo_number}** — {j.category_name}")
                        st.caption((j.concern or "")[:120] + ("…" if j.concern and len(j.concern) > 120 else ""))
                    with c2:
                        st.caption(f"Status: **{j.status}**")
                        st.caption(f"Updated: {j.updated_date.strftime('%Y-%m-%d %H:%M') if j.updated_date else '—'}")
                    with c3:
                        if st.button("Open", key=f"open_job_{j.id}"):
                            st.session_state.active_job_id = j.id
                            st.rerun()

    # --- Active Job workspace ---
    with tab_active:
        job = None
        if st.session_state.active_job_id:
            job = session.query(DiagnosticJob).get(st.session_state.active_job_id)

        if not job:
            st.info("No active job. Use **Start / Resume** to open a work order.")
        else:
            st.markdown(f"### WO **{job.wo_number}** · {job.status}")
            st.caption(
                f"{job.category_name}"
                + (f" · {job.model_text}" if job.model_text else "")
                + f" · Tech user id {job.user_id}"
            )

            st.markdown("**Customer concern**")
            st.write(job.concern)

            with st.expander("📋 Guided test plan (from manuals)", expanded=True):
                st.markdown(job.plan_text or "_No plan saved._")
                if job.sources_text:
                    st.caption("Sources")
                    st.text(job.sources_text)

            st.markdown("#### Log tests as you go")
            st.caption("Record each test result so you can stop and resume later. This also feeds the warranty story.")

            steps = load_step_log(job)
            if steps:
                st.markdown("**Progress so far**")
                for i, s in enumerate(steps):
                    st.write(
                        f"{i+1}. **{s.get('step', 'Step')}** — {s.get('result', '')}"
                        + (f" — {s.get('notes')}" if s.get('notes') else "")
                    )

            with st.form(f"add_step_{job.id}", clear_on_submit=True):
                step_name = st.text_input("What test / step did you do?", placeholder="e.g. Checked 30A fuse / battery voltage")
                step_result = st.selectbox("Result", ["Pass", "Fail", "Inconclusive", "Info"])
                step_notes = st.text_input("Notes (readings, LED codes, etc.)", placeholder="e.g. 12.4V, motor LED red")
                if st.form_submit_button("Add to job log", type="primary"):
                    if step_name.strip():
                        steps.append({
                            "step": step_name.strip(),
                            "result": step_result,
                            "notes": step_notes.strip(),
                            "at": datetime.now().isoformat(timespec="minutes")
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
                placeholder="Found left Schwintek motor open circuit. Replaced motor, synced system, cycled room 3x OK."
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
                        hits = search_manual_chunks(
                            cat_obj.id if cat_obj else None,
                            job.model_text or "",
                            job.concern,
                            limit=8
                        )
                        plan, sources = run_guided_diagnostics(
                            job.category_name, job.model_text or "", job.concern, hits
                        )
                    job.plan_text = plan
                    job.sources_text = sources
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
                if job.status != "complete":
                    if st.button("✅ Mark complete", key=f"done_{job.id}", use_container_width=True):
                        job.findings = findings_val
                        job.status = "complete"
                        job.updated_date = datetime.now()
                        session.commit()
                        st.success("Job marked complete.")
                        st.rerun()
                else:
                    if st.button("Reopen job", key=f"reopen_{job.id}", use_container_width=True):
                        job.status = "in_progress"
                        job.updated_date = datetime.now()
                        session.commit()
                        st.rerun()

            if job.final_story:
                st.markdown("### Warranty story (saved on this WO)")
                st.text_area(
                    "Copy into the warranty claim",
                    value=job.final_story,
                    height=320,
                    key=f"final_story_{job.id}"
                )
                st.info("This story is stored on the work order. Resume the same WO later and it will still be here.")

            if st.button("Close active job view", key="clear_active"):
                st.session_state.active_job_id = None
                st.rerun()

    st.divider()

    # CERTIFICATES
    st.subheader("📜 My Certificates")
    my_certs = session.query(Certificate).filter_by(user_id=user["id"]).order_by(Certificate.created_date.desc()).all()
    if my_certs:
        for cert in my_certs:
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.markdown(f"**{cert.title}**")
                    st.caption(f"Issuer: {cert.issuer or '—'} • Issued: {cert.issued_date or '—'}")
                with c2:
                    r2_download_button("⬇️", cert.file_path, Path(cert.file_path).name, f"dlc_{cert.id}")
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
            if st.button("Save Certificate", type="primary"):
                if ct and cf:
                    key = f"certificates/{user['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{cf.name}"
                    if r2_upload(io.BytesIO(cf.getvalue()), key, "application/pdf"):
                        session.add(Certificate(
                            user_id=user["id"], title=ct, issuer=ci or None,
                            file_path=key, issued_date=cd or None, notes=cn or None,
                            uploaded_by=user["id"]
                        ))
                        session.commit()
                        st.success("Certificate saved permanently!")
                        st.rerun()
                else:
                    st.error("Title and PDF are required.")

    st.divider()

    # DOCUMENT LIBRARY
    st.subheader("📚 Document Library (Manuals & Troubleshooting)")
    categories = session.query(Category).order_by(Category.name).all()
    if not categories:
        st.warning("No categories yet. Ask a manager to create some.")
    else:
        cat_name = st.selectbox("Select Category", [c.name for c in categories], key="doc_cat")
        cat = session.query(Category).filter_by(name=cat_name).first()
        search_term = st.text_input("Search documents by title or keyword", key="doc_search")
        if st.button("Search", type="primary") or search_term:
            q = session.query(Document).filter_by(category_id=cat.id)
            if search_term.strip():
                term = f"%{search_term.strip()}%"
                q = q.filter((Document.title.ilike(term)) | (Document.keywords.ilike(term)))
            results = q.order_by(Document.title).all()
            if results:
                st.write(f"**{len(results)} document(s) found**")
                for doc in results:
                    with st.container(border=True):
                        c1, c2 = st.columns([5, 1])
                        with c1:
                            st.markdown(f"**{doc.title}**")
                            idx = "✅ indexed" if doc.indexed else "⚠️ not indexed"
                            st.caption(f"Type: {doc.file_type or 'file'} • {idx}")
                        with c2:
                            r2_download_button("⬇️", doc.file_path, Path(doc.file_path).name, f"dld_{doc.id}")
            else:
                st.info("No documents matched your search.")

    st.divider()

    # SAFETY
    st.subheader("🛡️ Safety / Compliance")
    with st.expander("Safety Documents", expanded=False):
        safety_docs = session.query(SafetyDocument).order_by(SafetyDocument.title).all()
        s_search = st.text_input("Search safety documents", key="safety_doc_search")
        if s_search:
            safety_docs = [
                d for d in safety_docs
                if s_search.lower() in d.title.lower()
                or (d.keywords and s_search.lower() in (d.keywords or "").lower())
            ]
        if safety_docs:
            for doc in safety_docs:
                c1, c2 = st.columns([5, 1])
                with c1:
                    st.write(f"📄 **{doc.title}**")
                with c2:
                    r2_download_button("⬇️", doc.file_path, Path(doc.file_path).name, f"sdoc_{doc.id}")
        else:
            st.info("No safety documents available.")

    st.markdown("#### Safety Meetings – Acknowledgement Required")
    meetings = session.query(SafetyMeeting).order_by(SafetyMeeting.created_date.desc()).all()
    if not meetings:
        st.info("No safety meetings have been created yet.")
    else:
        for m in meetings:
            already = session.query(SafetyAcknowledgement).filter_by(meeting_id=m.id, user_id=user["id"]).first()
            with st.container(border=True):
                st.markdown(f"**{m.title}**")
                st.caption(
                    f"Meeting Date: {m.meeting_date or '—'} • Created: "
                    f"{m.created_date.strftime('%Y-%m-%d') if m.created_date else ''}"
                )
                if m.notes:
                    st.caption(m.notes)
                if m.file_path:
                    r2_download_button(
                        "Download Presentation", m.file_path,
                        Path(m.file_path).name, f"meet_{m.id}"
                    )
                if already:
                    st.success(
                        f"✅ You acknowledged this meeting on {already.signed_at.strftime('%Y-%m-%d %H:%M')}"
                    )
                else:
                    if st.checkbox(
                        "I attended this safety meeting, received the training, and understand the material.",
                        key=f"ack_{m.id}"
                    ):
                        if st.button("Sign Acknowledgement", key=f"sign_{m.id}", type="primary"):
                            session.add(SafetyAcknowledgement(
                                meeting_id=m.id, user_id=user["id"], understood=True
                            ))
                            session.commit()
                            st.success("Acknowledgement recorded. Thank you.")
                            st.rerun()

    st.divider()

    # STANDALONE STORY IMPROVER (quick claims without full job)
    st.subheader("✍️ Quick Story Improver (no WO)")
    st.caption("For one-off claims. For full jobs with saved progress, use Diagnostic Jobs above.")
    concern = st.text_area(
        "1. Customer Concern",
        height=90,
        key="story_concern",
        placeholder="Customer states the air conditioner is not cooling…"
    )
    tech_notes = st.text_area(
        "2. What you found and did",
        height=120,
        key="story_notes",
        placeholder="Found bad compressor. Recovered, replaced, evacuated, recharged, tested."
    )
    if st.button("Improve Story", type="primary"):
        if concern.strip() or tech_notes.strip():
            with st.spinner("Writing improved warranty story..."):
                improved = improve_tech_story(concern, tech_notes)
            st.markdown("### Improved Version")
            st.text_area("Copy this improved story", value=improved, height=320, key="story_improved")
        else:
            st.warning("Please enter at least the customer concern or your notes.")

# =========================================================
# PAGE: TEAM OVERVIEW
# =========================================================
elif st.session_state.page == "Overview":
    st.header("👥 Team Overview")
    users = session.query(User).filter_by(is_active=True).order_by(User.full_name).all()
    st.subheader("Certificate & Safety Summary")
    for u in users:
        certs = session.query(Certificate).filter_by(user_id=u.id).all()
        safety_pct = get_safety_progress(u.id)
        open_jobs = session.query(DiagnosticJob).filter_by(user_id=u.id, status="in_progress").count()
        issuers = list(set([c.issuer for c in certs if c.issuer]))
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
            with c1:
                st.markdown(f"**{u.full_name}**")
                st.caption(f"{u.role} • @{u.username}")
            with c2:
                st.metric("Certificates", len(certs))
                if issuers:
                    st.caption(", ".join(issuers[:4]) + ("..." if len(issuers) > 4 else ""))
            with c3:
                st.metric("Safety Progress", f"{safety_pct}%")
                if safety_pct < 100:
                    st.caption("⚠️ Missing acknowledgements")
            with c4:
                st.metric("Open WO Jobs", open_jobs)
            if certs:
                with st.expander(f"View {u.full_name}'s certificates"):
                    for c in certs:
                        st.write(f"• **{c.title}** ({c.issuer or 'No issuer'}) – {c.issued_date or 'no date'}")

    if is_manager:
        st.subheader("Recent Diagnostic Jobs (all techs)")
        recent = session.query(DiagnosticJob).order_by(DiagnosticJob.updated_date.desc()).limit(25).all()
        if not recent:
            st.info("No diagnostic jobs yet.")
        else:
            for j in recent:
                tech = session.query(User).get(j.user_id)
                st.write(
                    f"**WO {j.wo_number}** — {j.category_name} — {j.status} — "
                    f"{tech.full_name if tech else '—'} — "
                    f"{j.updated_date.strftime('%Y-%m-%d %H:%M') if j.updated_date else ''}"
                )

# =========================================================
# PAGE: MANAGER TOOLS
# =========================================================
elif st.session_state.page == "Manager" and is_manager:
    st.header("🛠️ Manager Tools")

    with st.expander("👤 User Management", expanded=True):
        st.subheader("Add New User")
        nu_user = st.text_input("Username", key="new_username")
        nu_name = st.text_input("Full Name", key="new_fullname")
        nu_pass = st.text_input("Temporary Password", type="password", key="new_pass")
        nu_role = st.selectbox("Role", ["Technician", "Manager"], key="new_role")
        if st.button("Create User", type="primary"):
            if nu_user and nu_name and nu_pass:
                if session.query(User).filter_by(username=nu_user).first():
                    st.error("Username already exists.")
                else:
                    session.add(User(
                        username=nu_user,
                        password_hash=hash_password(nu_pass),
                        full_name=nu_name,
                        role=nu_role
                    ))
                    session.commit()
                    st.success(f"User {nu_user} created.")
                    st.rerun()
            else:
                st.error("All fields required.")
        st.markdown("---")
        st.subheader("Existing Users")
        for u in session.query(User).order_by(User.full_name).all():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.write(f"**{u.full_name}** (@{u.username})")
                    st.caption(f"Role: {u.role} • Active: {u.is_active}")
                with c2:
                    new_role = st.selectbox(
                        "Role", ["Technician", "Manager"],
                        index=0 if u.role == "Technician" else 1,
                        key=f"role_{u.id}"
                    )
                    if new_role != u.role and st.button("Update Role", key=f"updrole_{u.id}"):
                        u.role = new_role
                        session.commit()
                        st.rerun()
                with c3:
                    if st.button("Reset Password", key=f"rp_{u.id}"):
                        u.password_hash = hash_password("temp123")
                        session.commit()
                        st.success(f"Password for {u.username} reset to: temp123")
                    if u.id != user["id"] and st.button("Deactivate", key=f"deact_{u.id}"):
                        u.is_active = False
                        session.commit()
                        st.rerun()

    with st.expander("📁 Manage Categories"):
        st.subheader("Add Category")
        new_cat = st.text_input("Category Name", key="add_cat")
        if st.button("Create Category"):
            if new_cat and not session.query(Category).filter_by(name=new_cat).first():
                session.add(Category(name=new_cat))
                session.commit()
                st.success("Category created.")
                st.rerun()
            else:
                st.error("Name required or already exists.")
        st.markdown("---")
        for cat in session.query(Category).order_by(Category.name).all():
            c1, c2, c3 = st.columns([4, 2, 1])
            with c1:
                new_name = st.text_input("Name", value=cat.name, key=f"catname_{cat.id}")
            with c2:
                if st.button("Rename", key=f"rencat_{cat.id}"):
                    cat.name = new_name
                    session.commit()
                    st.rerun()
            with c3:
                if st.button("🗑️", key=f"delcat_{cat.id}"):
                    docs = session.query(Document).filter_by(category_id=cat.id).all()
                    for d in docs:
                        clear_document_chunks(d.id)
                        session.delete(d)
                    session.delete(cat)
                    session.commit()
                    st.rerun()

    with st.expander("📤 Upload Documents to Categories"):
        if not r2_available():
            st.warning("R2 storage is not configured. Check Streamlit Secrets.")
        else:
            cats = session.query(Category).order_by(Category.name).all()
            if cats:
                sel_cat = st.selectbox("Category", [c.name for c in cats], key="up_cat")
                cat_obj = session.query(Category).filter_by(name=sel_cat).first()
                doc_title = st.text_input("Document Title", key="up_title")
                doc_keywords = st.text_input(
                    "Keywords (models, brand names — helps search)",
                    key="up_keys",
                    placeholder="Schwintek, In-Wall, Lippert, error codes"
                )
                doc_file = st.file_uploader(
                    "PDF / PPTX / Image",
                    type=["pdf", "pptx", "png", "jpg", "jpeg"],
                    key="up_file"
                )
                if st.button("Upload Document", type="primary"):
                    if doc_title and doc_file:
                        key = f"documents/{cat_obj.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{doc_file.name}"
                        content_type = doc_file.type or "application/octet-stream"
                        raw = doc_file.getvalue()
                        if r2_upload(io.BytesIO(raw), key, content_type):
                            ftype = doc_file.name.split(".")[-1].lower()
                            doc = Document(
                                category_id=cat_obj.id,
                                title=doc_title,
                                file_path=key,
                                file_type=ftype,
                                uploaded_by=user["id"],
                                keywords=doc_keywords or None
                            )
                            session.add(doc)
                            session.commit()
                            if ftype == "pdf":
                                ok, note = index_document_from_bytes(doc, raw)
                                if ok:
                                    st.success(f"Document uploaded and indexed. {note}")
                                else:
                                    st.warning(f"Uploaded, but not indexed: {note}")
                            else:
                                st.success("Document uploaded (non-PDF — not indexed for guided diagnostics).")
                            st.rerun()
                    else:
                        st.error("Title and file required.")

    with st.expander("🧠 Re-index Manuals for Guided Diagnostics"):
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
            docs = session.query(Document).order_by(Document.id).all()
            ok_n = fail_n = 0
            prog = st.progress(0.0)
            status = st.empty()
            for i, doc in enumerate(docs):
                status.write(f"Indexing: {doc.title}")
                if (doc.file_type or "").lower() != "pdf":
                    doc.indexed = False
                    doc.index_note = "Not a PDF"
                    session.commit()
                    fail_n += 1
                else:
                    success, note = index_document_from_r2(doc)
                    if success:
                        ok_n += 1
                    else:
                        fail_n += 1
                prog.progress((i + 1) / max(len(docs), 1))
            status.write("Done.")
            st.success(f"Indexed OK: {ok_n} • Skipped/failed: {fail_n}")
            st.rerun()
        st.markdown("---")
        st.subheader("Index status by document")
        for doc in session.query(Document).order_by(Document.title).all():
            flag = "✅" if doc.indexed else "⚠️"
            st.write(f"{flag} **{doc.title}** — {doc.index_note or ('indexed' if doc.indexed else 'not indexed')}")

    with st.expander("✏️ Manage Documents (Rename / Edit / Delete)"):
        cats = session.query(Category).order_by(Category.name).all()
        if not cats:
            st.info("No categories yet.")
        else:
            manage_cat_name = st.selectbox("Select Category", [c.name for c in cats], key="manage_doc_cat")
            manage_cat = session.query(Category).filter_by(name=manage_cat_name).first()
            docs = session.query(Document).filter_by(category_id=manage_cat.id).order_by(Document.title).all()
            if not docs:
                st.info("No documents in this category.")
            else:
                st.write(f"**{len(docs)} document(s) in {manage_cat_name}**")
                for doc in docs:
                    with st.container(border=True):
                        st.markdown(f"**Current title:** {doc.title}")
                        st.caption(
                            f"File: {Path(doc.file_path).name} • Type: {doc.file_type or '—'} • "
                            f"{'Indexed' if doc.indexed else 'Not indexed'}"
                        )
                        new_title = st.text_input("New Title", value=doc.title, key=f"edit_title_{doc.id}")
                        new_keywords = st.text_input(
                            "Keywords", value=doc.keywords or "", key=f"edit_keys_{doc.id}"
                        )
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            if st.button("💾 Save Changes", key=f"save_doc_{doc.id}"):
                                doc.title = new_title.strip() or doc.title
                                doc.keywords = new_keywords.strip() or None
                                session.query(DocChunk).filter_by(document_id=doc.id).update({
                                    "title": doc.title,
                                    "keywords": doc.keywords
                                })
                                session.commit()
                                st.success("Updated.")
                                st.rerun()
                        with c2:
                            r2_download_button(
                                "⬇️ Download", doc.file_path,
                                Path(doc.file_path).name, f"mgr_dl_{doc.id}"
                            )
                        with c3:
                            if st.button("🧠 Re-index", key=f"reidx_{doc.id}"):
                                success, note = index_document_from_r2(doc)
                                if success:
                                    st.success(note)
                                else:
                                    st.warning(note)
                                st.rerun()
                        with c4:
                            if st.button("🗑️ Delete", key=f"del_doc_{doc.id}"):
                                clear_document_chunks(doc.id)
                                session.delete(doc)
                                session.commit()
                                st.success("Document deleted from library.")
                                st.rerun()

    with st.expander("🛡️ Safety Documents & Meetings"):
        if not r2_available():
            st.warning("R2 storage is not configured. Check Streamlit Secrets.")
        else:
            st.subheader("Upload Safety Document")
            sd_title = st.text_input("Safety Document Title", key="sd_title")
            sd_keys = st.text_input("Keywords", key="sd_keys")
            sd_file = st.file_uploader("File", type=["pdf", "pptx", "docx"], key="sd_file")
            if st.button("Upload Safety Document"):
                if sd_title and sd_file:
                    key = f"safety/docs/{datetime.now().strftime('%Y%m%d%H%M%S')}_{sd_file.name}"
                    if r2_upload(io.BytesIO(sd_file.getvalue()), key, sd_file.type or "application/octet-stream"):
                        session.add(SafetyDocument(
                            title=sd_title, file_path=key,
                            file_type=sd_file.name.split(".")[-1].lower(),
                            uploaded_by=user["id"], keywords=sd_keys or None
                        ))
                        session.commit()
                        st.success("Safety document uploaded permanently!")
                        st.rerun()
            st.markdown("---")
            st.subheader("Create Safety Meeting")
            sm_title = st.text_input("Meeting Title", key="sm_title")
            sm_date = st.text_input("Meeting Date", key="sm_date")
            sm_notes = st.text_area("Notes / Agenda", key="sm_notes")
            sm_file = st.file_uploader(
                "PowerPoint or PDF of the training", type=["pdf", "pptx"], key="sm_file"
            )
            if st.button("Create Safety Meeting", type="primary"):
                if sm_title:
                    key = None
                    if sm_file:
                        key = f"safety/meetings/{datetime.now().strftime('%Y%m%d%H%M%S')}_{sm_file.name}"
                        if not r2_upload(
                            io.BytesIO(sm_file.getvalue()), key,
                            sm_file.type or "application/octet-stream"
                        ):
                            st.error("Failed to upload the presentation file.")
                            st.stop()
                    session.add(SafetyMeeting(
                        title=sm_title, meeting_date=sm_date or None,
                        file_path=key, notes=sm_notes or None, created_by=user["id"]
                    ))
                    session.commit()
                    st.success("Safety meeting created. Technicians can now acknowledge it.")
                    st.rerun()
                else:
                    st.error("Title is required.")

    with st.expander("💾 Database Backup & Restore"):
        st.warning("Streamlit Cloud resets data on restart. Download backups regularly.")
        c1, c2 = st.columns(2)
        with c1:
            if Path(DB_PATH).exists():
                with open(DB_PATH, "rb") as f:
                    st.download_button(
                        "⬇️ Download Current Database", f,
                        file_name=f"techtrack_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                        mime="application/octet-stream", type="primary"
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
            st.write(f"**{cert.title}** — {u.full_name if u else 'Unknown'} ({cert.issuer or '—'})")

st.sidebar.caption("v4.4 • WO Jobs • Guided Diagnostics • Story • R2 • Groq")
