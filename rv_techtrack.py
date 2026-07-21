"""
RV TechTrack v3.0
Technician Competency Tracking System
+ Quiz System (Sub-Module quizzes required for "Demonstrated")
Built with Streamlit + SQLAlchemy
"""

import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
from pathlib import Path
import os
import json

st.set_page_config(page_title="RV TechTrack v3.0", page_icon="🔧", layout="wide")

# ---------------- CONFIG ----------------
DB_PATH = "rv_techtrack.db"
TRAINING_DIR = Path("training_materials")
TRAINING_DIR.mkdir(exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# ---------------- DATABASE MODELS ----------------
class Technician(Base):
    __tablename__ = "technicians"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    role = Column(String(50), default="Technician")

class SkillModule(Base):
    __tablename__ = "skill_modules"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, unique=True)

class SubModule(Base):
    __tablename__ = "sub_modules"
    id = Column(Integer, primary_key=True)
    skill_module_id = Column(Integer, ForeignKey("skill_modules.id"))
    name = Column(String(150), nullable=False)

class Competency(Base):
    __tablename__ = "competencies"
    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("skill_modules.id"))
    submodule_id = Column(Integer, ForeignKey("sub_modules.id"), nullable=True)
    code = Column(String(20))
    title = Column(String(250), nullable=False)
    description = Column(Text)

class TechnicianCompetency(Base):
    __tablename__ = "technician_competencies"
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"))
    competency_id = Column(Integer, ForeignKey("competencies.id"))
    status = Column(String(20), default="not_started")
    demonstrated_date = Column(DateTime)
    work_order_ref = Column(String(100))
    notes = Column(Text)

class TrainingMaterial(Base):
    __tablename__ = "training_materials"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    file_path = Column(String(300), nullable=False)
    file_type = Column(String(20))
    module_id = Column(Integer, ForeignKey("skill_modules.id"), nullable=True)
    submodule_id = Column(Integer, ForeignKey("sub_modules.id"), nullable=True)
    uploaded_by = Column(Integer, ForeignKey("technicians.id"))
    created_date = Column(DateTime, default=func.now())

# -------- QUIZ MODELS --------
class Quiz(Base):
    __tablename__ = "quizzes"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    submodule_id = Column(Integer, ForeignKey("sub_modules.id"), nullable=False)
    pass_score = Column(Float, default=80.0)  # percent
    created_by = Column(Integer, ForeignKey("technicians.id"))
    created_date = Column(DateTime, default=func.now())

class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    id = Column(Integer, primary_key=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    order = Column(Integer, default=0)

class QuizChoice(Base):
    __tablename__ = "quiz_choices"
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("quiz_questions.id"), nullable=False)
    choice_text = Column(String(500), nullable=False)
    is_correct = Column(Boolean, default=False)

class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=False)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False)
    score = Column(Float)          # percentage
    passed = Column(Boolean, default=False)
    completed_date = Column(DateTime, default=func.now())
    answers_json = Column(Text)    # store selected choice ids for review

Base.metadata.create_all(engine)
session = Session()

# ---------------- SEED DATA ----------------
def seed_data():
    if session.query(Technician).count() == 0:
        session.add_all([
            Technician(name="Alex Rivera", role="Technician"),
            Technician(name="Jordan Hale", role="Technician"),
            Technician(name="Sam Patel", role="Manager"),
        ])
        for m in ["Air Conditioner", "Furnace", "Water Heater", "Electrical Systems", "Refrigeration Systems"]:
            session.add(SkillModule(name=m))
        session.commit()

        # Create example sub-modules for Water Heater so quizzes can attach
        wh = session.query(SkillModule).filter_by(name="Water Heater").first()
        if wh:
            for s in ["General", "Atwood/Dometic", "Suburban", "Girard (Tankless)"]:
                if not session.query(SubModule).filter_by(name=s, skill_module_id=wh.id).first():
                    session.add(SubModule(skill_module_id=wh.id, name=s))
            session.commit()

        # Create example sub-modules for Air Conditioner
        ac = session.query(SkillModule).filter_by(name="Air Conditioner").first()
        if ac:
            for s in ["General", "Coleman", "Dometic/Furrion", "Installation & Commissioning"]:
                if not session.query(SubModule).filter_by(name=s, skill_module_id=ac.id).first():
                    session.add(SubModule(skill_module_id=ac.id, name=s))
            session.commit()

        # Create example sub-modules for Furnace
        fur = session.query(SkillModule).filter_by(name="Furnace").first()
        if fur:
            for s in ["General", "Atwood/Dometic", "Suburban"]:
                if not session.query(SubModule).filter_by(name=s, skill_module_id=fur.id).first():
                    session.add(SubModule(skill_module_id=fur.id, name=s))
            session.commit()

seed_data()

# ---------------- HELPER FUNCTIONS ----------------
def get_progress(tech_id, module_id=None, sub_id=None):
    q = session.query(TechnicianCompetency).filter_by(technician_id=tech_id)
    if module_id:
        ids = [c.id for c in session.query(Competency.id).filter_by(module_id=module_id)]
        if not ids:
            return 0.0
        q = q.filter(TechnicianCompetency.competency_id.in_(ids))
    if sub_id:
        ids = [c.id for c in session.query(Competency.id).filter_by(submodule_id=sub_id)]
        if not ids:
            return 0.0
        q = q.filter(TechnicianCompetency.competency_id.in_(ids))
    total = q.count()
    if total == 0:
        return 0.0
    approved = q.filter_by(status="approved").count()
    return round(approved / total * 100, 1)

def has_passed_quiz(tech_id, submodule_id):
    """Return True if the technician has at least one passing attempt on any quiz for this sub-module."""
    quizzes = session.query(Quiz).filter_by(submodule_id=submodule_id).all()
    if not quizzes:
        return True  # no quiz required
    for quiz in quizzes:
        attempt = session.query(QuizAttempt).filter_by(
            technician_id=tech_id, quiz_id=quiz.id, passed=True
        ).first()
        if attempt:
            return True
    return False

def get_quiz_for_submodule(submodule_id):
    return session.query(Quiz).filter_by(submodule_id=submodule_id).first()

# ---------------- SIDEBAR ----------------
st.title("RV TechTrack v3.0")
st.sidebar.header("Current User")
role = st.sidebar.selectbox("Role", ["Technician", "Manager"], key="role")
name = st.sidebar.selectbox("Name", ["Alex Rivera", "Jordan Hale", "Sam Patel"], key="name")
tech = session.query(Technician).filter_by(name=name).first()

tab1, tab2, tab3 = st.tabs(["My Dashboard", "Manager Tools", "Team Overview"])

# =========================================================
# TAB 1 - MY DASHBOARD
# =========================================================
with tab1:
    st.header(f"My Dashboard - {name}")

    mains = session.query(SkillModule).all()
    if not mains:
        st.warning("No Main Modules yet. Ask a Manager to create some.")
    else:
        main = st.selectbox("Main Module", [m.name for m in mains], key="main")
        mod = session.query(SkillModule).filter_by(name=main).first()

        subs = session.query(SubModule).filter_by(skill_module_id=mod.id).all()
        sub_names = ["All"] + [s.name for s in subs]
        sub_choice = st.selectbox("Sub-Module", sub_names, key="sub")

        active_sub = None
        if sub_choice != "All":
            active_sub = session.query(SubModule).filter_by(name=sub_choice, skill_module_id=mod.id).first()

        # ---------- QUIZ SECTION ----------
        if active_sub:
            quiz = get_quiz_for_submodule(active_sub.id)
            if quiz:
                st.subheader("📝 Required Quiz")
                passed = has_passed_quiz(tech.id, active_sub.id)
                if passed:
                    st.success(f"✅ You have passed: **{quiz.title}**")
                else:
                    st.warning(f"⚠️ You must pass **{quiz.title}** before you can mark competencies as Demonstrated.")

                if st.button(f"Take Quiz: {quiz.title}", key=f"take_quiz_{quiz.id}"):
                    st.session_state["active_quiz_id"] = quiz.id
                    st.session_state["quiz_mode"] = True
                    st.rerun()

        # ---------- TAKE QUIZ MODE ----------
        if st.session_state.get("quiz_mode") and st.session_state.get("active_quiz_id"):
            quiz_id = st.session_state["active_quiz_id"]
            quiz = session.query(Quiz).get(quiz_id)
            if quiz:
                st.markdown("---")
                st.subheader(f"Taking Quiz: {quiz.title}")
                st.caption(f"Pass score required: {quiz.pass_score}%")

                questions = session.query(QuizQuestion).filter_by(quiz_id=quiz.id).order_by(QuizQuestion.order).all()
                if not questions:
                    st.error("This quiz has no questions yet.")
                else:
                    answers = {}
                    for q in questions:
                        choices = session.query(QuizChoice).filter_by(question_id=q.id).all()
                        options = [c.choice_text for c in choices]
                        selected = st.radio(q.question_text, options, key=f"q_{q.id}")
                        # store the choice object
                        for c in choices:
                            if c.choice_text == selected:
                                answers[q.id] = c.id

                    if st.button("Submit Quiz", type="primary"):
                        correct = 0
                        total = len(questions)
                        for qid, choice_id in answers.items():
                            choice = session.query(QuizChoice).get(choice_id)
                            if choice and choice.is_correct:
                                correct += 1
                        score = round((correct / total) * 100, 1) if total > 0 else 0
                        passed = score >= quiz.pass_score

                        attempt = QuizAttempt(
                            technician_id=tech.id,
                            quiz_id=quiz.id,
                            score=score,
                            passed=passed,
                            answers_json=json.dumps(answers)
                        )
                        session.add(attempt)
                        session.commit()

                        if passed:
                            st.success(f"🎉 PASSED! Score: {score}%")
                            st.balloons()
                        else:
                            st.error(f"❌ Not passed. Score: {score}% (Need {quiz.pass_score}%)")
                        
                        # clear quiz mode
                        del st.session_state["quiz_mode"]
                        del st.session_state["active_quiz_id"]
                        st.rerun()

                if st.button("Cancel Quiz"):
                    del st.session_state["quiz_mode"]
                    del st.session_state["active_quiz_id"]
                    st.rerun()

        # ---------- TRAINING MATERIALS ----------
        if active_sub:
            materials = session.query(TrainingMaterial).filter(
                (TrainingMaterial.submodule_id == active_sub.id) | (TrainingMaterial.module_id == mod.id)
            ).all()
            if materials:
                st.subheader("📚 Training Materials")
                for mat in materials:
                    if st.button(f"📄 {mat.title}", key=f"view_{mat.id}"):
                        file_path = Path(mat.file_path)
                        if file_path.exists():
                            with open(file_path, "rb") as f:
                                st.download_button(label=f"Download {mat.title}", data=f, file_name=file_path.name)

        # ---------- PROGRESS ----------
        st.subheader("Progress by Sub-Module")
        for s in subs:
            pct = get_progress(tech.id, sub_id=s.id)
            st.progress(pct / 100, text=f"{s.name} — {pct}%")

        # ---------- COMPETENCY CHECKLISTS ----------
        st.subheader("Competency Checklists")
        if active_sub:
            comps = session.query(Competency).filter_by(module_id=mod.id, submodule_id=active_sub.id).all()
        else:
            comps = session.query(Competency).filter_by(module_id=mod.id).all()

        if not comps:
            st.info("No competencies yet for this selection. Manager can add them via Bulk Import or Add Competency.")
        else:
            quiz_passed = True
            if active_sub:
                quiz_passed = has_passed_quiz(tech.id, active_sub.id)

            for comp in comps:
                tc = session.query(TechnicianCompetency).filter_by(
                    technician_id=tech.id, competency_id=comp.id
                ).first()
                if not tc:
                    tc = TechnicianCompetency(
                        technician_id=tech.id, competency_id=comp.id, status="not_started"
                    )
                    session.add(tc)
                    session.commit()

                with st.container(border=True):
                    st.markdown(f"**{comp.code} — {comp.title}**")
                    if comp.description:
                        st.caption(comp.description)

                    # Build status options - remove "demonstrated" if quiz not passed
                    status_options = ["not_started", "practicing", "demonstrated", "approved"]
                    if not quiz_passed and active_sub:
                        # Remove demonstrated if they haven't passed the quiz
                        if "demonstrated" in status_options:
                            status_options.remove("demonstrated")
                        st.caption("🔒 Pass the Sub-Module quiz to unlock **Demonstrated**")

                    current_idx = 0
                    if tc.status in status_options:
                        current_idx = status_options.index(tc.status)

                    new_status = st.selectbox(
                        "Status", status_options, index=current_idx, key=f"status_{comp.id}"
                    )

                    if new_status != tc.status:
                        if new_status == "demonstrated":
                            # Extra safety check
                            if not quiz_passed:
                                st.error("You must pass the Sub-Module quiz first.")
                            else:
                                wo = st.text_input(
                                    "Work Order # (required)",
                                    value=tc.work_order_ref or "",
                                    key=f"wo_{comp.id}"
                                )
                                if st.button("Confirm as Demonstrated", key=f"confirm_{comp.id}"):
                                    if wo.strip():
                                        tc.status = "demonstrated"
                                        tc.work_order_ref = wo.strip()
                                        tc.demonstrated_date = datetime.now()
                                        session.commit()
                                        st.success("✅ Marked as Demonstrated")
                                        st.rerun()
                                    else:
                                        st.error("Work Order # is required")
                        else:
                            tc.status = new_status
                            session.commit()
                            st.rerun()

# =========================================================
# TAB 2 - MANAGER TOOLS
# =========================================================
with tab2:
    st.header("Manager Tools")
    if role != "Manager":
        st.info("Switch to Manager role in the sidebar to access these tools.")
    else:
        # ---------- ADD MAIN MODULE ----------
        with st.expander("➕ Add New Main Module"):
            nm = st.text_input("Module Name", key="new_main_module")
            if st.button("Create Main Module", key="btn_create_main"):
                if nm:
                    if not session.query(SkillModule).filter_by(name=nm).first():
                        session.add(SkillModule(name=nm))
                        session.commit()
                        st.success(f"✅ Added Main Module: {nm}")
                        st.rerun()
                    else:
                        st.error("A Main Module with that name already exists.")

        # ---------- ADD / EDIT MAIN MODULE + TRAINING MATERIALS ----------
        with st.expander("➕ Add / Edit Main Module & Training Materials"):
            main_modules = session.query(SkillModule).all()
            if main_modules:
                selected_main = st.selectbox("Select Main Module", [m.name for m in main_modules], key="main_select")
                main_obj = session.query(SkillModule).filter_by(name=selected_main).first()

                if main_obj:
                    new_main_name = st.text_input("Main Module Name", value=main_obj.name, key="edit_main_name")
                    if st.button("Update Main Module Name", key="update_main"):
                        main_obj.name = new_main_name
                        session.commit()
                        st.success("Main Module updated!")
                        st.rerun()

                    st.write("**Training Materials attached to this Main Module:**")
                    main_materials = session.query(TrainingMaterial).filter_by(module_id=main_obj.id).all()
                    for mat in main_materials:
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.write(f"• {mat.title}")
                        with col2:
                            if st.button("Remove", key=f"remove_main_{mat.id}"):
                                if os.path.exists(mat.file_path):
                                    os.remove(mat.file_path)
                                session.delete(mat)
                                session.commit()
                                st.rerun()

                    st.write("**Upload Training Material to this Main Module:**")
                    uploaded = st.file_uploader("Upload PDF or PPTX", type=["pdf", "pptx"], key="main_upload")
                    mat_title = st.text_input("Material Title", key="main_mat_title")
                    if st.button("Upload to Main Module", key="upload_main_mat"):
                        if uploaded and mat_title:
                            file_path = TRAINING_DIR / uploaded.name
                            with open(file_path, "wb") as f:
                                f.write(uploaded.getbuffer())
                            new_mat = TrainingMaterial(
                                title=mat_title,
                                file_path=str(file_path),
                                file_type=uploaded.name.split(".")[-1].lower(),
                                module_id=main_obj.id,
                                uploaded_by=tech.id
                            )
                            session.add(new_mat)
                            session.commit()
                            st.success("Training material added!")
                            st.rerun()

        # ---------- ADD SUB-MODULE ----------
        with st.expander("➕ Add New Sub-Module"):
            pm = st.selectbox("Parent Main Module", [m.name for m in session.query(SkillModule).all()], key="parent_main")
            ns = st.text_input("Sub-Module Name", key="new_sub_name")
            if st.button("Create Sub-Module", key="btn_add_sub"):
                if ns and pm:
                    p = session.query(SkillModule).filter_by(name=pm).first()
                    if not session.query(SubModule).filter_by(name=ns, skill_module_id=p.id).first():
                        session.add(SubModule(skill_module_id=p.id, name=ns))
                        session.commit()
                        st.success(f"Added '{ns}' under {pm}")
                        st.rerun()
                    else:
                        st.error("Already exists under this module")

        # ---------- EDIT / DELETE SUB-MODULE ----------
        with st.expander("✏️ Edit / Delete Sub-Module"):
            sub_list = session.query(SubModule).all()
            if sub_list:
                sub_to_edit = st.selectbox("Select Sub-Module", [f"{s.name} (ID:{s.id})" for s in sub_list], key="sub_edit")
                sub_id = int(sub_to_edit.split("ID:")[1].replace(")", ""))
                sub = session.query(SubModule).get(sub_id)

                if sub:
                    new_name = st.text_input("New Name", value=sub.name, key="edit_sub_name")
                    if st.button("Update Name", key="update_sub"):
                        sub.name = new_name
                        session.commit()
                        st.success("Updated!")
                        st.rerun()

                    if st.button("🗑️ Delete Sub-Module + All Data Under It", key="delete_sub"):
                        # cascade delete
                        session.query(Competency).filter_by(submodule_id=sub.id).delete()
                        session.query(TrainingMaterial).filter_by(submodule_id=sub.id).delete()
                        # also delete quizzes for this sub
                        quizzes = session.query(Quiz).filter_by(submodule_id=sub.id).all()
                        for qz in quizzes:
                            qs = session.query(QuizQuestion).filter_by(quiz_id=qz.id).all()
                            for q in qs:
                                session.query(QuizChoice).filter_by(question_id=q.id).delete()
                            session.query(QuizQuestion).filter_by(quiz_id=qz.id).delete()
                            session.query(QuizAttempt).filter_by(quiz_id=qz.id).delete()
                            session.delete(qz)
                        session.delete(sub)
                        session.commit()
                        st.success("Deleted Sub-Module and all related data.")
                        st.rerun()

        # ---------- ADD COMPETENCY ----------
        with st.expander("➕ Add New Competency"):
            cm = st.selectbox("Main Module", [m.name for m in session.query(SkillModule).all()], key="cmod")
            cmod = session.query(SkillModule).filter_by(name=cm).first()
            subs_for_mod = ["None"] + [s.name for s in session.query(SubModule).filter_by(skill_module_id=cmod.id).all()]
            cs = st.selectbox("Sub-Module (optional)", subs_for_mod, key="csub")
            cc = st.text_input("Code", key="ccode")
            ct = st.text_input("Title", key="ctitle")
            cd = st.text_area("Description (optional)", key="cdesc")
            if st.button("Create Competency", key="btn_comp"):
                if cc and ct:
                    subid = None
                    if cs != "None":
                        subobj = session.query(SubModule).filter_by(name=cs, skill_module_id=cmod.id).first()
                        if subobj:
                            subid = subobj.id
                    session.add(Competency(
                        module_id=cmod.id, submodule_id=subid,
                        code=cc, title=ct, description=cd or None
                    ))
                    session.commit()
                    st.success(f"Added: {cc} — {ct}")
                    st.rerun()
                else:
                    st.error("Code and Title required")

        # ---------- BULK IMPORT COMPETENCIES ----------
        with st.expander("🚀 Bulk Import Competencies"):
            st.write("**Paste competencies (one per line)**  \nFormat: `CODE | Title | Description` (description optional)")
            bulk_text = st.text_area("Competencies", height=180, key="bulk_text")

            col1, col2 = st.columns(2)
            with col1:
                bulk_main = st.selectbox("Main Module", [m.name for m in session.query(SkillModule).all()], key="bulk_main")
            with col2:
                bulk_mod = session.query(SkillModule).filter_by(name=bulk_main).first()
                bulk_sub_opts = ["None"] + [s.name for s in session.query(SubModule).filter_by(skill_module_id=bulk_mod.id).all()]
                bulk_sub_name = st.selectbox("Sub-Module (optional)", bulk_sub_opts, key="bulk_sub")

            if st.button("Import Competencies", key="bulk_import_btn"):
                if bulk_text.strip():
                    lines = [line.strip() for line in bulk_text.strip().split("\n") if line.strip()]
                    imported = 0
                    for line in lines:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 2:
                            code, title = parts[0], parts[1]
                            desc = parts[2] if len(parts) > 2 else None
                            sub_id = None
                            if bulk_sub_name != "None":
                                sub = session.query(SubModule).filter_by(
                                    name=bulk_sub_name, skill_module_id=bulk_mod.id
                                ).first()
                                if sub:
                                    sub_id = sub.id
                            existing = session.query(Competency).filter_by(
                                module_id=bulk_mod.id, code=code
                            ).first()
                            if not existing:
                                session.add(Competency(
                                    module_id=bulk_mod.id, submodule_id=sub_id,
                                    code=code, title=title, description=desc
                                ))
                                imported += 1
                    session.commit()
                    st.success(f"✅ Imported {imported} competencies")
                    st.rerun()

# ---------- CREATE / MANAGE QUIZZES (Manager) ----------
with st.expander("📝 Create / Manage Quizzes", expanded=True):
    
    # === CREATE NEW QUIZ ===
    st.subheader("Create New Quiz")
    q_title = st.text_input("Quiz Title", key="q_title")
    q_main = st.selectbox("Main Module", [m.name for m in session.query(SkillModule).all()], key="q_main")
    q_mod = session.query(SkillModule).filter_by(name=q_main).first()
    
    if q_mod:
        q_subs = session.query(SubModule).filter_by(skill_module_id=q_mod.id).all()
        if q_subs:
            q_sub_name = st.selectbox("Sub-Module (required)", [s.name for s in q_subs], key="q_sub")
            q_sub = session.query(SubModule).filter_by(name=q_sub_name, skill_module_id=q_mod.id).first()
            q_pass = st.number_input("Pass Score (%)", min_value=50.0, max_value=100.0, value=80.0, step=5.0, key="q_pass")
            
            if st.button("Create Quiz", key="create_quiz_btn"):
                if q_title and q_sub:
                    existing = session.query(Quiz).filter_by(submodule_id=q_sub.id).first()
                    if existing:
                        st.error("A quiz already exists for this Sub-Module. Delete it first.")
                    else:
                        new_quiz = Quiz(
                            title=q_title,
                            submodule_id=q_sub.id,
                            pass_score=q_pass,
                            created_by=tech.id
                        )
                        session.add(new_quiz)
                        session.commit()
                        st.success(f"Quiz created: {q_title}")
                        st.rerun()
        else:
            st.info("Create Sub-Modules first.")

    st.markdown("---")

    # === ADD QUESTIONS TO EXISTING QUIZ ===
    st.subheader("Add Questions to a Quiz")
    all_quizzes = session.query(Quiz).all()
    if all_quizzes:
        quiz_options = {f"{q.title} (ID:{q.id})": q.id for q in all_quizzes}
        selected_q = st.selectbox("Select Quiz", list(quiz_options.keys()), key="select_quiz_for_q")
        selected_quiz_id = quiz_options[selected_q]

        st.write("**Add a new question:**")
        q_text = st.text_area("Question Text", key="new_q_text")
        c1 = st.text_input("Choice A", key="cA")
        c2 = st.text_input("Choice B", key="cB")
        c3 = st.text_input("Choice C", key="cC")
        c4 = st.text_input("Choice D", key="cD")
        correct = st.selectbox("Correct Answer", ["A", "B", "C", "D"], key="correct_choice")

        if st.button("Add Question", key="add_question_btn"):
            if q_text and c1 and c2 and c3 and c4:
                new_question = QuizQuestion(
                    quiz_id=selected_quiz_id,
                    question_text=q_text
                )
                session.add(new_question)
                session.commit()

                choices = [
                    QuizChoice(question_id=new_question.id, choice_text=c1, is_correct=(correct == "A")),
                    QuizChoice(question_id=new_question.id, choice_text=c2, is_correct=(correct == "B")),
                    QuizChoice(question_id=new_question.id, choice_text=c3, is_correct=(correct == "C")),
                    QuizChoice(question_id=new_question.id, choice_text=c4, is_correct=(correct == "D")),
                ]
                session.add_all(choices)
                session.commit()
                st.success("Question added successfully!")
                st.rerun()
            else:
                st.error("Please fill in all fields.")
    else:
        st.info("Create a quiz first before adding questions.")

    st.markdown("---")

    # ========== NEW: DELETE QUIZ ==========
    st.subheader("🗑️ Delete a Quiz")
    quizzes = session.query(Quiz).order_by(Quiz.title).all()
    if quizzes:
        quiz_options = {f"{q.title} (ID:{q.id})": q for q in quizzes}
        selected_title = st.selectbox(
            "Select quiz to delete",
            list(quiz_options.keys()),
            key="delete_quiz_select"
        )
        quiz_to_delete = quiz_options[selected_title]

        st.warning(f"⚠️ This will permanently delete **{quiz_to_delete.title}** and all its questions + attempts.")

        if st.button("Delete Quiz", type="primary", key="delete_quiz_btn"):
            try:
                # Delete attempts first
                session.query(QuizAttempt).filter_by(quiz_id=quiz_to_delete.id).delete()
                # Delete choices
                session.query(QuizChoice).filter(
                    QuizChoice.question_id.in_(
                        session.query(QuizQuestion.id).filter_by(quiz_id=quiz_to_delete.id)
                    )
                ).delete(synchronize_session=False)
                # Delete questions
                session.query(QuizQuestion).filter_by(quiz_id=quiz_to_delete.id).delete()
                # Delete quiz
                session.delete(quiz_to_delete)
                session.commit()
                st.success(f"✅ Quiz '{quiz_to_delete.title}' deleted.")
                st.rerun()
            except Exception as e:
                session.rollback()
                st.error(f"Error deleting quiz: {e}")
    else:
        st.info("No quizzes to delete.")
# =========================================================
# TAB 3 - TEAM OVERVIEW
# =========================================================
with tab3:
    st.header("Team Skills Matrix")
    data = []
    for t in session.query(Technician).all():
        row = {"Name": t.name, "Role": t.role}
        for m in session.query(SkillModule).all():
            row[m.name[:16]] = f"{get_progress(t.id, module_id=m.id)}%"
        data.append(row)
    st.dataframe(data, use_container_width=True)

    st.subheader("Recent Quiz Results")
    attempts = session.query(QuizAttempt).order_by(QuizAttempt.completed_date.desc()).limit(20).all()
    if attempts:
        for att in attempts:
            tech_name = session.query(Technician).get(att.technician_id).name
            quiz = session.query(Quiz).get(att.quiz_id)
            status = "✅ PASS" if att.passed else "❌ FAIL"
            st.write(f"{status}  {tech_name}  —  {quiz.title}  ({att.score}%)")
    else:
        st.info("No quiz attempts recorded yet.")

st.sidebar.caption("v3.0 • Quizzes + Demonstrated Gate + Full Manager Quiz Builder")
