"""Past work orders in Guided Diagnostics (Chase 2026-10-24 2:51 PM; retention 30 days). Offline: an in-memory SQLite copy
of the diagnostic_jobs table, scripted GD turns, and one AppTest walk of the GD area. No network, no API calls."""
import json
import os
import re
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine, func  # noqa: E402
from sqlalchemy.orm import declarative_base, sessionmaker  # noqa: E402

import gd_turn  # noqa: E402
import gd_work_orders as wo  # noqa: E402
from test_fresh_core import FakeRespond, block, finder  # noqa: E402

Base = declarative_base()


class Job(Base):   # the app's DiagnosticJob columns (rv_techtrack.py), checked against the app source below
    __tablename__ = "diagnostic_jobs"
    id = Column(Integer, primary_key=True)
    wo_number = Column(String(80), nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
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
    ask_chat_id = Column(Integer, nullable=True, index=True)


def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


def gd_job(closed=False):
    """One scripted GD turn on the stub library: Grok reads p.29, records a reading, cites the page and a web source."""
    store = {}
    st = dict(facts=[{"item": "fan volts", "value": "10.4 V", "quote": "10.4 at the fan"}], fault_code="E2",
              cause="freezer fan" if closed else "", cited=[{"doc_id": "L1", "page": "29"}], summary="E2; fan at 10.4 V.",
              repair={"done": closed, "verified": closed, "what": "replaced freezer fan" if closed else "", "quote": "cools now" if closed else ""},
              closed=closed, story="Verified E2. Fan read 10.4 V. Replaced the freezer fan." if closed else "")
    chat = FakeRespond([[("read_pages", {"doc_id": "L1", "pages": ["29"]})], "Test the fan at F+ F- [Acme p.29].\n" + block(**st)])
    r = gd_turn.run_turn("Fridge freezes food, E2 blinking", "Refrigerators", "Acme X1", [], finder=finder(), respond_fn=chat,
                         store=store, log_path="")
    store["gd_case"]["web_sources"].append({"url": "https://acme.example/bulletin.pdf", "title": "Acme bulletin"})
    history = [{"role": "user", "content": "Fridge freezes food, E2 blinking"}, {"role": "assistant", "content": r["reply"]}]
    return history, store["gd_case"]


class TestRetention(unittest.TestCase):
    def test_retention_is_30_days(self):
        self.assertEqual(wo.WORK_ORDER_RETENTION_DAYS, 30)

    def test_old_gd_work_orders_purged_on_load_legacy_rows_kept(self):
        s, now = db(), datetime(2026, 10, 24, 14, 0)
        s.add_all([Job(wo_number="OLD", user_id=1, ask_chat_id=1, updated_date=now - timedelta(days=31)),
                   Job(wo_number="EDGE", user_id=1, ask_chat_id=2, updated_date=now - timedelta(days=29, hours=23)),
                   Job(wo_number="LEGACY", user_id=1, ask_chat_id=None, updated_date=now - timedelta(days=200))])
        s.commit()
        self.assertEqual(wo.purge_old(s, Job, now=now), 1)
        self.assertEqual(sorted(j.wo_number for j in s.query(Job)), ["EDGE", "LEGACY"])

    def test_app_purges_on_load_with_the_constant(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("_gd_wo.purge_old(session, DiagnosticJob)", src)
        self.assertIn("ask_chat_id = Column(Integer", src)
        self.assertIn('ALTER TABLE diagnostic_jobs ADD COLUMN ask_chat_id INTEGER', src)
        app_cols = re.findall(r"^    (\w+) = Column\(", src[src.index("class DiagnosticJob("):src.index("class AskChat(")], re.M)
        self.assertEqual(app_cols, [c.name for c in Job.__table__.columns])


class TestSnapshotAndSave(unittest.TestCase):
    def test_snapshot_has_everything_the_file_needs(self):
        history, case = gd_job(closed=True)
        snap = wo.snapshot(history=history, case=case, wo_number="4471", chat_id=9)
        self.assertEqual((snap["wo_number"], snap["status"], snap["category_name"], snap["model_text"]),
                         ("4471", "closed", "Refrigerators", "Acme X1"))
        self.assertEqual(snap["concern"], "Fridge freezes food, E2 blinking")
        self.assertEqual(len(json.loads(snap["step_log"])), 2)
        f = json.loads(snap["findings"])
        self.assertEqual(f["facts"][0]["value"], "10.4 V")
        self.assertEqual(f["fault_code"], "E2")
        src = json.loads(snap["sources_json"])
        self.assertEqual([(p["doc_id"], p["page"]) for p in src["pages"]], [("L1", "29")])
        self.assertEqual(src["pages"][0]["title"], "Acme Fridge Service Manual")
        self.assertEqual(src["web"][0]["url"], "https://acme.example/bulletin.pdf")
        self.assertIn("Replaced the freezer fan", snap["final_story"])

    def test_status_and_default_number(self):
        history, case = gd_job(closed=False)
        self.assertEqual(wo.snapshot(history=history, case=case, chat_id=5)["status"], "saved")
        self.assertEqual(wo.snapshot(history=history, case=case, chat_id=5)["wo_number"], "GD-5")
        self.assertEqual(wo.snapshot(history=history, case=case, chat_id=5, story="My story")["status"], "story written")

    def test_one_row_per_chat_number_kept_closed_sticks_reopen_keeps_findings(self):
        s = db()
        history, case = gd_job(closed=True)
        r1 = wo.save(s, Job, 7, 3, wo.snapshot(history=history, case=case, wo_number="4471", chat_id=3))
        self.assertEqual(r1.status, "closed")
        # a later save of the reopened chat (its case is gone) with no WO # typed
        r2 = wo.save(s, Job, 7, 3, wo.snapshot(history=history + [{"role": "user", "content": "thanks"}], case=None, chat_id=3))
        self.assertEqual(s.query(Job).count(), 1)
        self.assertEqual((r2.wo_number, r2.status), ("4471", "closed"))
        self.assertEqual(json.loads(r2.findings)["fault_code"], "E2")
        self.assertEqual(len(json.loads(r2.step_log)), 3)
        self.assertIn("freezer fan", r2.final_story)

    def test_nothing_saved_without_a_chat(self):
        s = db()
        self.assertIsNone(wo.save(s, Job, 7, None, wo.snapshot(history=[{"role": "user", "content": "x"}])))
        self.assertIsNone(wo.save(s, Job, 7, 4, wo.snapshot(history=[], chat_id=4)))
        self.assertEqual(s.query(Job).count(), 0)


class TestListAndDownload(unittest.TestCase):
    def test_own_jobs_newest_first_inside_window(self):
        s, now = db(), datetime(2026, 10, 24, 14, 0)
        for n, (user, days) in enumerate([(1, 3), (1, 1), (2, 0), (1, 40)]):
            s.add(Job(wo_number=f"W{n}", user_id=user, ask_chat_id=n + 1, updated_date=now - timedelta(days=days),
                      status="saved", category_name="Furnaces", model_text="NT-20", concern="no heat " * 30))
        s.commit()
        jobs = wo.list_jobs(s, Job, 1, now=now)
        self.assertEqual([j.wo_number for j in jobs], ["W1", "W0"])
        label = wo.list_label(jobs[0])
        self.assertTrue(label.startswith("WO W1 · saved · Furnaces · NT-20 · no heat"))
        self.assertTrue(label.endswith("2026-10-23 02:00 PM"))
        self.assertLess(len(label), 160)

    def test_html_file_has_every_section_and_is_escaped(self):
        s = db()
        history, case = gd_job(closed=True)
        history[0]["content"] += " <script>alert(1)</script>"
        row = wo.save(s, Job, 7, 3, wo.snapshot(history=history, case=case, wo_number="44/71", chat_id=3),
                      now=datetime(2026, 10, 24, 14, 5))
        page = wo.render_html(row)
        for want in ("Work order 44/71", "Complaint", "Fridge freezes food, E2 blinking", "Refrigerators", "Acme X1",
                     "Readings and findings", "fan volts", "10.4 V", "Fault code", "E2", "Cause", "replaced freezer fan",
                     "Pages and sources cited", "Acme Fridge Service Manual — page 29", "https://acme.example/bulletin.pdf",
                     "Technician story", "Replaced the freezer fan", "Full chat", "Test the fan at F+ F-", "Guided Diagnostics"):
            self.assertIn(want, page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<state>", page)
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertEqual(wo.file_name(row), "work-order-44-71-20261024.html")

    def test_old_flow_row_renders(self):
        r = Job(wo_number="88", user_id=1, status="in_progress", concern="AC dead", findings="compressor hums",
                sources_json='[{"title": "Coleman manual", "page": 4}]', step_log="[]", created_date=datetime(2026, 9, 1),
                updated_date=datetime(2026, 9, 2))
        page = wo.render_html(r)
        self.assertIn("compressor hums", page)
        self.assertIn("Coleman manual — page 4", page)
        self.assertIn("No chat saved.", page)


OFFLINE_ENV_KEYS = ("XAI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")


class TestGdAreaAppWalk(unittest.TestCase):
    """The GD area lists the signed-in tech's work orders with a Download button (AppTest, offline)."""

    def setUp(self):
        env = {k: v for k, v in os.environ.items() if k not in OFFLINE_ENV_KEYS}
        patcher = mock.patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_then_listed_with_download(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "rv_techtrack.py"), default_timeout=60)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        gd = "💬 Guided Diagnostics"
        at.radio[0].set_value(gd).run()
        at.selectbox(key="ask_cat").set_value("Furnaces")
        at.text_input(key="ask_model").set_value("Suburban NT-20SEQT")
        tag = datetime.now().strftime("WT%H%M%S%f")
        at.text_area(key="ask_input").set_value(f"Blower runs, no heat {tag}")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()
        self.assertFalse(list(at.exception))
        at.text_input(key="ask_wo_number").set_value(tag)
        at.button(key="ask_save_wo").click().run()
        self.assertFalse(list(at.exception))
        self.assertTrue(any(f"Saved WO {tag}" in (x.value or "") for x in at.success))
        labels = [m.value or "" for m in at.markdown]
        mine = [l for l in labels if l.startswith(f"WO {tag} · saved · Furnaces · Suburban NT-20SEQT · Blower runs, no heat")]
        self.assertEqual(len(mine), 1)
        dl = [e for e in at.get("download_button")]
        self.assertTrue(dl, "no Download button in the GD area")
        self.assertTrue(any("Past work orders (kept 30 days)" in (e.label or "") for e in at.expander))


class TestAppSavesFinishedJobs(unittest.TestCase):
    def test_closed_turn_and_story_save_the_work_order(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        send = src[src.index('st.session_state["gd_case_chat_id"] = st.session_state["ask_chat_id"]'):][:400]
        self.assertIn("save_gd_work_order(user[\"id\"], only_if_closed_or_saved=True", send)
        story = src[src.index("chat_row.final_story = story"):][:400]
        self.assertIn("save_gd_work_order(user[\"id\"]", story)
        fn = src[src.index("def save_gd_work_order("):src.index("def _render_past_work_orders(")]
        self.assertIn('st.session_state.get("gd_case_chat_id") != chat_id', fn)   # another job's case is never mixed in
        lst = src[src.index("def _render_past_work_orders("):src.index("def load_ask_chat(")]
        self.assertIn("wo.list_jobs(session, DiagnosticJob, user_id)", lst)          # the signed-in tech's own jobs
        self.assertIn('mime="text/html"', lst)
