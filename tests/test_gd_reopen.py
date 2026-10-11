"""GD session reopen: history, a neutral follow-up, a review flag, and a new Bay PDF."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fitz
import profile_check
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import gd_reopen
import gd_session_store as store

APP = ROOT / "rv_techtrack.py"
BLAME = ("your fault", "you did it wrong", "our mistake", "program")


def _session():
    tmp = tempfile.TemporaryDirectory()
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'gd.db'}")
    store.ensure_schema(engine)
    db = sessionmaker(bind=engine)()
    return tmp, db


def _words(sentence: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", sentence))


def _thetford_history():
    return [
        {"role": "user", "content": "Thetford 42070 leaks under the flush lever."},
        {
            "role": "assistant",
            "content": "The supply connection is the first check.\nWhat do you see?",
        },
        {"role": "user", "content": "The supply connection is tight and dry."},
        {
            "role": "assistant",
            "content": "The vacuum breaker is the next check.\nWhat do you see?",
        },
        {"role": "user", "content": "The vacuum breaker leaks while flushing."},
    ]


class TestReopenPhrases(unittest.TestCase):
    def test_natural_phrases_reopen_and_a_normal_turn_does_not(self):
        self.assertTrue(gd_reopen.is_reopen_phrase("This wasn't the actual fix."))
        self.assertTrue(gd_reopen.is_reopen_phrase("It came back."))
        self.assertTrue(
            gd_reopen.is_reopen_phrase(
                "The lever leak came back after the vacuum breaker. It wasn't the fix."
            )
        )
        self.assertTrue(gd_reopen.is_reopen_phrase("not fixed"))
        self.assertFalse(gd_reopen.is_reopen_phrase("still not cooling"))
        self.assertFalse(gd_reopen.is_reopen_phrase("FCR10 not cooling, cavity light is on"))


class TestThetfordReopen(unittest.TestCase):
    def test_lever_leak_came_back_after_the_vacuum_breaker(self):
        history = _thetford_history()
        latest = "The lever leak came back after the vacuum breaker. It wasn't the fix."
        reply = gd_reopen.neutral_reopen_reply(
            history, latest, "Plumbing / Toilets", "Thetford 42070"
        )
        low = reply.lower()
        self.assertIn("supply connection was dry", low)
        self.assertNotIn("check the water supply line connection", low)
        self.assertIn("flush once and watch the vacuum breaker", low)
        self.assertIn("42109", reply)
        self.assertIn("What do you see?", reply)
        self.assertIn("Send a photo of what you see.", reply)
        self.assertNotRegex(reply, r"Step\s+\d+\s+of\s+\d+")
        self.assertNotRegex(reply, r"(?m)^(Where|Tools|Do this|Good looks like|Next):")
        for phrase in BLAME:
            self.assertNotIn(phrase, low)
        for line in reply.splitlines():
            if line.startswith("📖"):
                continue
            self.assertLessEqual(_words(line), 15, line)
        transcript = "\n\n".join(
            [
                "USER: The supply connection is tight and dry.\n"
                "ASSISTANT:\nThe supply connection is dry.\nWhat do you see?",
                f"USER: {latest}\nASSISTANT:\n{reply}",
            ]
        )
        rules = profile_check.check_transcript(transcript)
        failed = [f"{rule.name}: {rule.detail}" for rule in rules if not rule.ok]
        self.assertEqual(failed, [])

    def test_another_brand_does_not_inherit_the_thetford_reply(self):
        reply = gd_reopen.neutral_reopen_reply(
            [{"role": "user", "content": "Freeze sensor reads 2k at 25C."}],
            "It came back.",
            "Air Conditioning",
            "FACR",
        )
        self.assertNotIn("42109", reply)
        self.assertNotIn("vacuum breaker", reply.lower())
        self.assertIn("?", reply)
        for phrase in BLAME:
            self.assertNotIn(phrase, reply.lower())


class TestSessionStore(unittest.TestCase):
    def test_completed_session_stays_listed_and_context_round_trips(self):
        tmp, db = _session()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(db.close)
        chat_id = store.start_chat(
            db,
            7,
            category_name="Plumbing / Toilets",
            model_text="Thetford 42070",
            title="Lever leak",
            status="complete",
        )
        store.append_message(db, chat_id, "user", "Thetford 42070 leaks under the flush lever.")
        store.append_message(
            db,
            chat_id,
            "assistant",
            "📖 Source: Thetford Style II OM Permanent RV Toilet 42088, page 3",
        )
        store.append_message(db, chat_id, "user", "The vacuum breaker leaks while flushing.")
        synced = store.sync_context(db, chat_id)
        loaded = store.load_session(db, chat_id)
        self.assertEqual(loaded["status"], "complete")
        self.assertIn("vacuum breaker", " ".join(loaded["facts"]).lower())
        self.assertEqual(loaded["case"]["model"], "Thetford 42070")
        self.assertEqual(loaded["case"]["category"], "Plumbing / Toilets")
        self.assertEqual(synced["cited"][0]["page"], 3)
        self.assertIn("42088", loaded["cited"][0]["title"])
        listed = store.list_sessions(db)
        self.assertIn(chat_id, [row["id"] for row in listed])
        self.assertEqual(listed[0]["status"], "complete")

    def test_old_ask_table_gains_the_context_columns(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        engine = create_engine(f"sqlite:///{Path(tmp.name) / 'old.db'}")
        with engine.connect() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE ask_chats (id INTEGER PRIMARY KEY, user_id INTEGER, title VARCHAR(250))"
            )
            conn.commit()
        store.ensure_schema(engine)
        with engine.connect() as conn:
            cols = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(ask_chats)").fetchall()]
        for name in ("status", "concern", "facts_json", "cited_json", "case_json"):
            self.assertIn(name, cols)

    def test_cross_session_facts_do_not_leak(self):
        tmp, db = _session()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(db.close)
        thetford = store.start_chat(
            db, 1, "Plumbing / Toilets", "Thetford 42070", "Lever leak", status="complete"
        )
        store.append_message(db, thetford, "user", "The vacuum breaker leaks while flushing.")
        store.append_message(
            db,
            thetford,
            "assistant",
            "📖 Source: Thetford Water Valve Kit 42109, page 1",
        )
        store.sync_context(db, thetford)
        facr = store.start_chat(db, 2, "Air Conditioning", "FACR", "No cool", status="complete")
        store.append_message(db, facr, "user", "Freeze sensor reads 2k at 25C.")
        store.append_message(db, facr, "assistant", "📖 Source: CCD-0007990, page 12")
        store.sync_context(db, facr)

        loaded_t = store.load_session(db, thetford)
        loaded_f = store.load_session(db, facr)
        thetford_blob = json.dumps(loaded_t).lower()
        facr_blob = json.dumps(loaded_f).lower()
        self.assertIn("vacuum breaker", thetford_blob)
        self.assertIn("42109", thetford_blob)
        self.assertNotIn("freeze sensor", thetford_blob)
        self.assertNotIn("7990", thetford_blob)
        self.assertIn("freeze sensor", facr_blob)
        self.assertNotIn("42109", facr_blob)
        self.assertNotIn("vacuum breaker", facr_blob)
        ids = {row["id"] for row in store.list_sessions(db)}
        self.assertEqual(ids, {thetford, facr})

    def test_reopen_log_is_flagged_for_review(self):
        tmp, db = _session()
        self.addCleanup(tmp.cleanup)
        self.addCleanup(db.close)
        chat_id = store.start_chat(
            db, 4, "Plumbing / Toilets", "Thetford 42070", "Lever leak", status="complete"
        )
        reason = "The lever leak came back after the vacuum breaker. It wasn't the fix."
        store.append_message(db, chat_id, "user", "Thetford 42070 leaks under the flush lever.")
        store.append_message(db, chat_id, "user", "The supply connection is tight and dry.")
        store.append_message(db, chat_id, "user", "The vacuum breaker leaks while flushing.")
        store.append_message(db, chat_id, "user", reason)
        reply = gd_reopen.neutral_reopen_reply(
            store.load_session(db, chat_id)["messages"][:-1],
            reason,
            "Plumbing / Toilets",
            "Thetford 42070",
        )
        store.append_message(db, chat_id, "assistant", reply)
        store.sync_context(db, chat_id)
        log_id = store.record_reopen(db, chat_id, 4, "Chase", reason)
        self.assertIsNotNone(log_id)
        flags = store.list_flags(db)
        self.assertEqual(len(flags), 1)
        flag = flags[0]
        self.assertEqual(flag["who_name"], "Chase")
        self.assertEqual(flag["reason"], reason)
        self.assertEqual(flag["session_id"], chat_id)
        self.assertEqual(flag["status"], "flagged_for_review")
        self.assertTrue(flag["opened_at"])
        self.assertEqual(store.load_session(db, chat_id)["status"], "in_progress")
        self.assertIn("42109", json.dumps(store.load_session(db, chat_id)["cited"]))


class TestRegeneratePdf(unittest.TestCase):
    def test_reopen_finding_and_thetford_branches_are_on_the_sheet(self):
        case = {
            "category": "Plumbing / Toilets",
            "brand": "Thetford",
            "model": "42070",
            "concern": "Thetford 42070 leaks under the flush lever.",
        }
        reason = "The lever leak came back after the vacuum breaker. It wasn't the fix."
        history = _thetford_history() + [{"role": "user", "content": reason}]
        pdf = gd_reopen.regenerate_bay_pdf(case, history, reason)
        self.assertTrue(pdf.startswith(b"%PDF"))
        doc = fitz.open(stream=pdf, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        low = text.lower()
        self.assertIn("came back", low)
        self.assertIn("vacuum breaker", low)
        self.assertIn("42109", text)
        self.assertIn("BEFORE YOU START", text)
        self.assertNotIn("facr", low)
        self.assertNotIn("freeze sensor", low)
        rules = profile_check.check_pdf_bytes(pdf)
        failed = [f"{rule.name}: {rule.detail}" for rule in rules if not rule.ok]
        self.assertEqual(failed, [])


class TestReopenUi(unittest.TestCase):
    def test_app_exposes_reopen_complete_pdf_and_the_manager_flags(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn('st.button("Not fixed / reopen", key="ask_reopen"', src)
        self.assertIn('st.button("Mark session complete", key="ask_complete"', src)
        self.assertIn('st.button("Regenerate Bay PDF", key="ask_regen_pdf"', src)
        self.assertIn("Reopened sessions flagged for review", src)
        self.assertIn("flagged for review", src)
        self.assertIn('key="ask_new"', src)
        self.assertIn('st.form("gd_send_form"', src)


if __name__ == "__main__":
    unittest.main()
