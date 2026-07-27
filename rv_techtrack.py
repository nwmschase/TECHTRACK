"""
RV TechTrack v4.2
- Login + Roles (Technician / Manager)
- Certificate Hub
- Searchable Document Library by Category
- Safety / Compliance + Meeting Acknowledgements
- Team Overview (Certificates + Safety Progress)
- AI Tech Story Improver (Groq)
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
import base64
import hashlib
import secrets
import io

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

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="RV TechTrack v4.2",
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

# ---------------- R2 (Cloudflare) HELPERS ----------------
def get_r2_client():
    """Create an S3-compatible client for Cloudflare R2."""
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
    """Upload a file-like object to R2. Returns True on success."""
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

def r2_download_button(label: str, key: str, filename: str, button_key: str):
    """Create a Streamlit download button that pulls the file from R2."""
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

Base.metadata.create_all(engine)
session = Session()

# ---------------- HELPERS ----------------
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

def improve_tech_story(concern: str, tech_notes: str) -> str:
    """Improve a technician's warranty story using Groq AI.
    Structure is always: CONCERN → CAUSE → CORRECTION
    """
    concern = (concern or "").strip()
    tech_notes = (tech_notes or "").strip()
    if not concern and not tech_notes:
        return ""

    # Fallback if Groq is not available or key is missing
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

def get_safety_progress(user_id: int) -> float:
    total = session.query(SafetyMeeting).count()
    if total == 0:
        return 100.0
    signed = session.query(SafetyAcknowledgement.meeting_id).filter_by(user_id=user_id).distinct().count()
    return round((signed / total) * 100, 1)

# ---------------- SEED DATA ----------------
def seed_data():
    if session.query(User).count() == 0:
        session.add(User(username="manager", password_hash=hash_password("manager123"), full_name="Shop Manager", role="Manager"))
        session.add(User(username="alex", password_hash=hash_password("tech123"), full_name="Alex Rivera", role="Technician"))
        session.add(User(username="jordan", password_hash=hash_password("tech123"), full_name="Jordan Hale", role="Technician"))
        session.commit()
    if session.query(Category).count() == 0:
        for name in ["Air Conditioner", "Furnace", "Water Heater", "Electrical Systems", "Refrigeration Systems", "Slide-Outs & Leveling", "Plumbing"]:
            session.add(Category(name=name))
        session.commit()

seed_data()

# ---------------- LOGIN ----------------
if "user" not in st.session_state:
    st.session_state.user = None

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
                st.session_state.user = {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role}
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
    st.rerun()

# Top navigation buttons (clear and always visible)
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
                        session.add(Certificate(user_id=user["id"], title=ct, issuer=ci or None, file_path=key, issued_date=cd or None, notes=cn or None, uploaded_by=user["id"]))
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
                            st.caption(f"Type: {doc.file_type or 'file'}")
                        with c2:
                            r2_download_button("⬇️", doc.file_path, Path(doc.file_path).name, f"dld_{doc.id}")
            else:
                st.info("No documents matched your search.")

    st.divider()

    # SAFETY / COMPLIANCE
    st.subheader("🛡️ Safety / Compliance")
    with st.expander("Safety Documents", expanded=False):
        safety_docs = session.query(SafetyDocument).order_by(SafetyDocument.title).all()
        s_search = st.text_input("Search safety documents", key="safety_doc_search")
        if s_search:
            safety_docs = [d for d in safety_docs if s_search.lower() in d.title.lower() or (d.keywords and s_search.lower() in (d.keywords or "").lower())]
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
                st.caption(f"Meeting Date: {m.meeting_date or '—'} • Created: {m.created_date.strftime('%Y-%m-%d') if m.created_date else ''}")
                if m.notes:
                    st.caption(m.notes)
                if m.file_path:
                    r2_download_button("Download Presentation", m.file_path, Path(m.file_path).name, f"meet_{m.id}")
                if already:
                    st.success(f"✅ You acknowledged this meeting on {already.signed_at.strftime('%Y-%m-%d %H:%M')}")
                else:
                    if st.checkbox("I attended this safety meeting, received the training, and understand the material.", key=f"ack_{m.id}"):
                        if st.button("Sign Acknowledgement", key=f"sign_{m.id}", type="primary"):
                            session.add(SafetyAcknowledgement(meeting_id=m.id, user_id=user["id"], understood=True))
                            session.commit()
                            st.success("Acknowledgement recorded. Thank you.")
                            st.rerun()

    st.divider()

    # AI TECH STORY IMPROVER
    st.subheader("✍️ AI Tech Story Improver")
    st.caption("Enter the customer concern and what you found/did. The AI will write a professional CONCERN → CAUSE → CORRECTION story to help maximize warranty time.")

    concern = st.text_area(
        "1. Customer Concern (what the customer reported)",
        height=100,
        key="story_concern",
        placeholder="Example: Customer states the air conditioner is not cooling and the unit is making a loud rattling noise."
    )
    tech_notes = st.text_area(
        "2. What you found and what you did",
        height=150,
        key="story_notes",
        placeholder="Example: Found bad compressor. Recovered refrigerant, replaced compressor, evacuated system, recharged, tested under load."
    )

    if st.button("Improve Story", type="primary"):
        if concern.strip() or tech_notes.strip():
            with st.spinner("Writing improved warranty story..."):
                improved = improve_tech_story(concern, tech_notes)
            st.markdown("### Improved Version")
            st.text_area("Copy this improved story", value=improved, height=350, key="story_improved")
            st.info("Copy the text above and paste it into the warranty claim.")
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
        issuers = list(set([c.issuer for c in certs if c.issuer]))
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 2, 2])
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
            if certs:
                with st.expander(f"View {u.full_name}'s certificates"):
                    for c in certs:
                        st.write(f"• **{c.title}** ({c.issuer or 'No issuer'}) – {c.issued_date or 'no date'}")

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
                    session.add(User(username=nu_user, password_hash=hash_password(nu_pass), full_name=nu_name, role=nu_role))
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
                    new_role = st.selectbox("Role", ["Technician", "Manager"], index=0 if u.role == "Technician" else 1, key=f"role_{u.id}")
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
                        # Note: files remain in R2; only DB records are removed
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
                doc_keywords = st.text_input("Keywords (optional, helps search)", key="up_keys")
                doc_file = st.file_uploader("PDF / PPTX / Image", type=["pdf", "pptx", "png", "jpg", "jpeg"], key="up_file")
                if st.button("Upload Document", type="primary"):
                    if doc_title and doc_file:
                        key = f"documents/{cat_obj.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{doc_file.name}"
                        content_type = doc_file.type or "application/octet-stream"
                        if r2_upload(io.BytesIO(doc_file.getvalue()), key, content_type):
                            session.add(Document(category_id=cat_obj.id, title=doc_title, file_path=key, file_type=doc_file.name.split(".")[-1].lower(), uploaded_by=user["id"], keywords=doc_keywords or None))
                            session.commit()
                            st.success("Document uploaded permanently to storage!")
                            st.rerun()
                    else:
                        st.error("Title and file required.")

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
                        st.caption(f"File: {Path(doc.file_path).name} • Type: {doc.file_type or '—'}")

                        new_title = st.text_input("New Title", value=doc.title, key=f"edit_title_{doc.id}")
                        new_keywords = st.text_input("Keywords", value=doc.keywords or "", key=f"edit_keys_{doc.id}")

                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("💾 Save Changes", key=f"save_doc_{doc.id}"):
                                doc.title = new_title.strip() or doc.title
                                doc.keywords = new_keywords.strip() or None
                                session.commit()
                                st.success("Updated.")
                                st.rerun()
                        with c2:
                            r2_download_button("⬇️ Download", doc.file_path, Path(doc.file_path).name, f"mgr_dl_{doc.id}")
                        with c3:
                            if st.button("🗑️ Delete", key=f"del_doc_{doc.id}"):
                                # Remove DB record (file remains in R2)
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
                        session.add(SafetyDocument(title=sd_title, file_path=key, file_type=sd_file.name.split(".")[-1].lower(), uploaded_by=user["id"], keywords=sd_keys or None))
                        session.commit()
                        st.success("Safety document uploaded permanently!")
                        st.rerun()

            st.markdown("---")
            st.subheader("Create Safety Meeting")
            sm_title = st.text_input("Meeting Title", key="sm_title")
            sm_date = st.text_input("Meeting Date", key="sm_date")
            sm_notes = st.text_area("Notes / Agenda", key="sm_notes")
            sm_file = st.file_uploader("PowerPoint or PDF of the training", type=["pdf", "pptx"], key="sm_file")
            if st.button("Create Safety Meeting", type="primary"):
                if sm_title:
                    key = None
                    if sm_file:
                        key = f"safety/meetings/{datetime.now().strftime('%Y%m%d%H%M%S')}_{sm_file.name}"
                        if not r2_upload(io.BytesIO(sm_file.getvalue()), key, sm_file.type or "application/octet-stream"):
                            st.error("Failed to upload the presentation file.")
                            st.stop()
                    session.add(SafetyMeeting(title=sm_title, meeting_date=sm_date or None, file_path=key, notes=sm_notes or None, created_by=user["id"]))
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
                    st.download_button("⬇️ Download Current Database", f, file_name=f"techtrack_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db", mime="application/octet-stream", type="primary")
        with c2:
            up_db = st.file_uploader("Upload .db backup to restore", type=["db"], key="restore_db")
            if up_db and st.button("Restore Database"):
                if Path(DB_PATH).exists():
                    shutil.copy(DB_PATH, DB_PATH + ".bak")
                with open(DB_PATH, "wb") as f:
                    f.write(up_db.getbuffer())
                st.success("Database restored. Refresh the page.")
                st.rerun()

    with st.expander("📜 All Team Certificates"):
        all_certs = session.query(Certificate).order_by(Certificate.created_date.desc()).all()
        for cert in all_certs:
            u = session.query(User).get(cert.user_id)
            st.write(f"**{cert.title}** — {u.full_name if u else 'Unknown'} ({cert.issuer or '—'})")

st.sidebar.caption("v4.2 • R2 Storage • Groq • Safety")
