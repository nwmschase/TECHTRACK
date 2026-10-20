"""scripts/migrate_to_fresh.py on small synthetic DBs: people data kept row-for-row, library replaced, live never written,
library drift since the base stops the migration (exit 3)."""
import hashlib
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import migrate_to_fresh as mig  # noqa: E402

SCHEMA = """
create table users (id integer primary key, username text, full_name text);
create table ask_chats (id integer primary key, user_id integer references users(id), title text);
create table ask_messages (id integer primary key, chat_id integer references ask_chats(id), content text);
create table categories (id integer primary key, name text, slug text);
create table documents (id integer primary key, category_id integer references categories(id), brand text, clean_title text, file_path text, content_sha256 text);
create table doc_chunks (id integer primary key, document_id integer references documents(id), category_id integer, page integer, chunk_text text);
create table doc_assets (id integer primary key, document_id integer references documents(id), page integer);
create table bulk_import_jobs (id integer primary key, status text);
create table bulk_import_items (id integer primary key, job_id integer references bulk_import_jobs(id), document_id integer);
create table figure_backfill_jobs (id integer primary key, status text);
create table figure_backfill_items (id integer primary key, job_id integer, document_id integer);
"""


def make(path, extra=""):
    c = sqlite3.connect(path)
    c.executescript(SCHEMA + """
insert into users values (1,'chase','Chase'),(2,'tech1','Tech One');
insert into categories values (1,'Refrigerators','refrigerators'),(2,'slide-outs','slide-outs');
insert into documents values (1,1,'Furrion','Fridge SM','documents/1.pdf','aa');
insert into doc_chunks values (1,1,1,1,'page one');
""" + extra)
    c.commit()
    c.close()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


class TestMigration(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.base, self.lib, self.live, self.out = (os.path.join(self.d, n) for n in ("base.db", "lib.db", "live.db", "out.db"))
        make(self.base)
        make(self.lib, "insert into documents values (2,1,'Dometic','New Fridge SM','documents/2.pdf','bb');"
                       "insert into doc_chunks values (2,2,1,1,'new page');")
        make(self.live, "insert into users values (3,'tech2','Tech Two');"
                        "insert into ask_chats values (1,3,'fridge E2');insert into ask_messages values (1,1,'hello');")

    def run_mig(self):
        try:
            return mig.main(["--live", self.live, "--library", self.lib, "--base", self.base, "--out", self.out,
                             "--report", os.path.join(self.d, "r.json")])
        except SystemExit as e:
            return e.code

    def test_people_kept_library_replaced_live_untouched(self):
        before = sha(self.live)
        self.assertEqual(self.run_mig(), 0)
        self.assertEqual(sha(self.live), before)
        c = sqlite3.connect(self.out)
        self.assertEqual(c.execute("select count(*) from users").fetchone()[0], 3)
        self.assertEqual(c.execute("select content from ask_messages").fetchall(), [("hello",)])
        self.assertEqual(sorted(r[0] for r in c.execute("select id from documents")), [1, 2])
        self.assertEqual(c.execute("select count(*) from doc_chunks").fetchone()[0], 2)
        # the empty load-plan category is dropped, the used one stays
        self.assertEqual([r[0] for r in c.execute("select slug from categories")], ["refrigerators"])

    def test_live_library_drift_stops_with_exit_3_and_writes_nothing_usable(self):
        c = sqlite3.connect(self.live)
        c.execute("update documents set clean_title='Edited on live' where id=1")
        c.commit()
        c.close()
        before = sha(self.live)
        self.assertEqual(self.run_mig(), 3)
        self.assertEqual(sha(self.live), before)


if __name__ == "__main__":
    unittest.main()
