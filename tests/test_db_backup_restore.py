"""DB backup download (consistent snapshot, made only on click) and restore (checked, atomic, reopened).
The helper functions are lifted from rv_techtrack.py source and run against temp DBs; no Streamlit script run."""
import ast
import os
import pathlib
import re
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "rv_techtrack.py").read_text()
NAMES = ("db_snapshot_bytes", "check_db_backup_bytes", "restore_db_from_bytes")


def load(db_path):
    tree = ast.parse(SRC)
    code = "\n\n".join(ast.get_source_segment(SRC, n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in NAMES)
    calls = []

    class Closer:
        def close(self):
            calls.append("session.close")

        def dispose(self):
            calls.append("engine.dispose")

    ns = {"os": os, "shutil": shutil, "Path": Path, "DB_PATH": db_path, "session": Closer(), "engine": Closer(),
          "_reopen_db": lambda: calls.append("reopen")}
    exec(code, ns)
    return ns, calls


def make_db(path, users=1, docs=3):
    c = sqlite3.connect(path)
    c.executescript("create table users(id integer primary key, username text); create table documents(id integer primary key, t text);"
                    "create table doc_chunks(id integer primary key); create table categories(id integer primary key);")
    c.executemany("insert into users(username) values (?)", [(f"u{i}",) for i in range(users)])
    c.executemany("insert into documents(t) values (?)", [(f"d{i}",) for i in range(docs)])
    c.commit()
    c.close()


class TestBackupRestore(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.db = os.path.join(self.d, "rv_techtrack_v4.db")
        make_db(self.db, docs=3)

    def test_snapshot_is_a_full_sound_copy(self):
        ns, _ = load(self.db)
        data = ns["db_snapshot_bytes"]()
        self.assertTrue(data.startswith(b"SQLite format 3"))
        self.assertEqual(ns["check_db_backup_bytes"](data), "")

    def test_restore_swaps_keeps_bak_and_reopens(self):
        other = os.path.join(self.d, "other.db")
        make_db(other, docs=7)
        ns, calls = load(self.db)
        self.assertEqual(ns["restore_db_from_bytes"](open(other, "rb").read()), "")
        self.assertEqual(sqlite3.connect(self.db).execute("select count(*) from documents").fetchone()[0], 7)
        self.assertEqual(sqlite3.connect(self.db + ".bak").execute("select count(*) from documents").fetchone()[0], 3)
        self.assertEqual(calls[-1], "reopen")

    def test_bad_files_are_refused_and_nothing_changes(self):
        ns, calls = load(self.db)
        before = open(self.db, "rb").read()
        nouser = os.path.join(self.d, "nouser.db")
        make_db(nouser, users=0)
        notours = os.path.join(self.d, "x.db")
        sqlite3.connect(notours).execute("create table t(x)").connection.commit()
        for data, why in ((b"hello", "not a SQLite"), (open(nouser, "rb").read(), "no users"),
                          (open(notours, "rb").read(), "missing tables"), (before[:4096], "")):
            got = ns["restore_db_from_bytes"](data)
            self.assertTrue(got, why)
            if why:
                self.assertIn(why, got)
        self.assertEqual(open(self.db, "rb").read(), before)
        self.assertNotIn("reopen", calls)


class TestDownloadsAreLazy(unittest.TestCase):
    def test_no_download_button_reads_bytes_at_render(self):
        a = SRC.index('"⬇️ Download Current Database"')
        block = SRC[a - 200:a + 500]
        self.assertIn("data=db_snapshot_bytes", block)
        self.assertNotIn("open(DB_PATH", block)
        fn = SRC[SRC.index("def r2_download_button"):]
        fn = fn[:fn.index("\ndef ", 10)]
        self.assertIn("on_click=\"ignore\"", fn)
        self.assertNotRegex(fn.split("def _fetch")[0], r"r2_download_bytes\(")


if __name__ == "__main__":
    unittest.main()
