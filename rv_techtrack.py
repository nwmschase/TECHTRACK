"""
RV TechTrack v4.0
- Login + Roles (Technician / Manager)
- Certificate Hub
- Searchable Document Library by Category
- Safety / Compliance + Meeting Acknowledgements
- Team Overview (Certificates + Safety Progress)
- AI Tech Story Improver (Placeholder - upgradeable later)
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

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="RV TechTrack v4.0",
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
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }
    button[data-baseweb="tab"] {
        font-size: 1.05rem !important;
        padding: 0.6rem 0.9rem !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------- CONFIG ----------------
DB_PATH = "rv_techtrack_v4.db"
DOC_DIR = Path("documents")
CERT_DIR = Path("certificates")
SAFETY_DIR = Path("safety")
DOC_DIR.mkdir(exist_ok=True)
CERT_DIR.mkdir(exist_ok=True)
SAFETY_DIR.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

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

def improve_tech_story(raw: str) -> str:
    """Placeholder AI Story Improver - easy to upgrade later to real AI."""
    raw = raw.strip()
    if not raw:
        return ""
    lower = raw.lower()
    has_cause = any(w in lower for w in ["cause", "caused by", "due to", "because", "root"])
    has_correction = any(w in lower for w in ["repair", "replaced", "adjusted", "corrected", "fixed", "installed"])

    parts = []
    parts.append("**CAUSE**")
    if has_cause:
        parts.append(raw)
    else:
        parts.append(f"The root cause of the issue was identified during diagnostic testing. Original notes: {raw}")

    parts.append("\n**CONCERN**")
    parts.append("Customer reported the symptom which required thorough diagnosis to determine the failed component and prevent recurrence. Proper diagnosis ensures the correct repair is performed the first time.")

    parts.append("\n**CORRECTION**")
    if has_correction:
        parts.append(f"The following corrective action was performed: {raw}\n\nAll related systems were inspected, tested, and verified for proper operation after the repair. Unit was returned to service in fully functional condition.")
    else:
        parts.append(f"Corrective action performed based on diagnostic findings: {raw}\n\nComponents were replaced/repaired as required. System was thoroughly tested under load conditions to confirm the repair resolved the reported concern. Unit is now operating within manufacturer specifications.")

    parts.append("\n\nAdditional notes: All work was performed in accordance with manufacturer service guidelines. Diagnostic time and repair procedures were documented for warranty purposes.")
    return "\n".join(parts)

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
                    if Path(cert.file_path).exists():
                        with open(cert.file_path, "rb") as f:
                            st.download_button("⬇️", f, file_name=Path(cert.file_path).name, key=f"dlc_{cert.id}")
    else:
        st.info("No certificates uploaded yet.")

    with st.expander("⬆️ Upload Certificate", expanded=False):
        ct = st.text_input("Certificate Title", key="cert_title")
        ci = st.text_input("Issuer (Lippert, RVTI, Airexcel, etc.)", key="cert_issuer")
        cd = st.text_input("Issued Date (optional)", key="cert_date")
        cn = st.text_area("Notes (optional)", key="cert_notes")
        cf = st.file_uploader("PDF Certificate", type=["pdf"], key="cert_file")
        if st.button("Save Certificate", type="primary"):
            if ct and cf:
                fname = f"{user['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{cf.name}"
                fpath = CERT_DIR / fname
                with open(fpath, "wb") as f:
                    f.write(cf.getbuffer())
                session.add(Certificate(user_id=user["id"], title=ct, issuer=ci or None, file_path=str(fpath), issued_date=cd or None, notes=cn or None, uploaded_by=user["id"]))
                session.commit()
                st.success("Certificate saved!")
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
                            if Path(doc.file_path).exists():
                                with open(doc.file_path, "rb") as f:
                                    st.download_button("⬇️", f, file_name=Path(doc.file_path).name, key=f"dld_{doc.id}")
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
                    if Path(doc.file_path).exists():
                        with open(doc.file_path, "rb") as f:
                            st.download_button("⬇️", f, file_name=Path(doc.file_path).name, key=f"sdoc_{doc.id}")
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
                if m.file_path and Path(m.file_path).exists():
                    with open(m.file_path, "rb") as f:
                        st.download_button("Download Presentation", f, file_name=Path(m.file_path).name, key=f"meet_{m.id}")
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
    st.subheader("✍️ AI Tech Story Improver (Placeholder)")
    st.caption("Paste your original tech story. The system restructures it into Cause → Concern → Correction format and expands the language to help maximize warranty time. Real AI can be added later.")
    original = st.text_area("Paste your original tech story here", height=150, key="story_raw")
    if st.button("Improve Story", type="primary"):
        if original.strip():
            improved = improve_tech_story(original)
            st.markdown("### Improved Version")
            st.text_area("Copy this improved story", value=improved, height=300, key="story_improved")
            st.info("Copy the improved text above and paste it into the warranty claim.")
        else:
            st.warning("Please paste a story first.")

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
                        if Path(d.file_path).exists():
                            os.remove(d.file_path)
                        session.delete(d)
                    session.delete(cat)
                    session.commit()
                    st.rerun()

    with st.expander("📤 Upload Documents to Categories"):
        cats = session.query(Category).order_by(Category.name).all()
        if cats:
            sel_cat = st.selectbox("Category", [c.name for c in cats], key="up_cat")
            cat_obj = session.query(Category).filter_by(name=sel_cat).first()
            doc_title = st.text_input("Document Title", key="up_title")
            doc_keywords = st.text_input("Keywords (optional, helps search)", key="up_keys")
            doc_file = st.file_uploader("PDF / PPTX / Image", type=["pdf", "pptx", "png", "jpg", "jpeg"], key="up_file")
            if st.button("Upload Document", type="primary"):
                if doc_title and doc_file:
                    fname = f"{cat_obj.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{doc_file.name}"
                    fpath = DOC_DIR / fname
                    with open(fpath, "wb") as f:
                        f.write(doc_file.getbuffer())
                    session.add(Document(category_id=cat_obj.id, title=doc_title, file_path=str(fpath), file_type=doc_file.name.split(".")[-1].lower(), uploaded_by=user["id"], keywords=doc_keywords or None))
                    session.commit()
                    st.success("Document uploaded.")
                    st.rerun()
                else:
                    st.error("Title and file required.")

    with st.expander("🛡️ Safety Documents & Meetings"):
        st.subheader("Upload Safety Document")
        sd_title = st.text_input("Safety Document Title", key="sd_title")
        sd_keys = st.text_input("Keywords", key="sd_keys")
        sd_file = st.file_uploader("File", type=["pdf", "pptx", "docx"], key="sd_file")
        if st.button("Upload Safety Document"):
            if sd_title and sd_file:
                fname = f"safety_{datetime.now().strftime('%Y%m%d%H%M%S')}_{sd_file.name}"
                fpath = SAFETY_DIR / fname
                with open(fpath, "wb") as f:
                    f.write(sd_file.getbuffer())
                session.add(SafetyDocument(title=sd_title, file_path=str(fpath), file_type=sd_file.name.split(".")[-1].lower(), uploaded_by=user["id"], keywords=sd_keys or None))
                session.commit()
                st.success("Safety document uploaded.")
                st.rerun()

        st.markdown("---")
        st.subheader("Create Safety Meeting")
        sm_title = st.text_input("Meeting Title", key="sm_title")
        sm_date = st.text_input("Meeting Date", key="sm_date")
        sm_notes = st.text_area("Notes / Agenda", key="sm_notes")
        sm_file = st.file_uploader("PowerPoint or PDF of the training", type=["pdf", "pptx"], key="sm_file")
        if st.button("Create Safety Meeting", type="primary"):
            if sm_title:
                fpath = None
                if sm_file:
                    fname = f"meeting_{datetime.now().strftime('%Y%m%d%H%M%S')}_{sm_file.name}"
                    fpath = str(SAFETY_DIR / fname)
                    with open(fpath, "wb") as f:
                        f.write(sm_file.getbuffer())
                session.add(SafetyMeeting(title=sm_title, meeting_date=sm_date or None, file_path=fpath, notes=sm_notes or None, created_by=user["id"]))
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

st.sidebar.caption("v4.0 • Login • Categories • Safety • Story Improver")
