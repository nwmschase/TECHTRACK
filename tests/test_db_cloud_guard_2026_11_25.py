"""2026-11-25: the 11/24 library label fix on R2 was overwritten at 2:06 PM PT by the running app's older local DB.

Covers the two fixes: the label corrections ship with the code and apply once to whatever DB the app has
(apply_label_fixes), and the cloud backup never uploads over a cloud copy that changed after this server loaded or
last saved its library (sidecar ETag + IfMatch), nor on every new browser session when nothing changed.
Functions are lifted from rv_techtrack.py source and run against temp DBs and a fake R2 client; no Streamlit run."""
import ast
import csv
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
FIX_DIR = ROOT / "data" / "label_fixes"
NAMES = ("_db_cloud_state", "_db_cloud_state_save", "_r2_db_etag", "cloud_db_conflict", "apply_label_fixes",
         "maybe_backup_db_to_r2", "maybe_restore_db_from_r2")


class ClientError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeR2:
    def __init__(self, etag="", body=b""):
        self.etag, self.body, self.puts, self.copies = etag, body, [], []
        self.fail_put = None

    def head_object(self, Bucket, Key):
        if not self.etag:
            raise ClientError("404")
        return {"ETag": f'"{self.etag}"'}

    def copy_object(self, **kw):
        self.copies.append(kw)

    def put_object(self, **kw):
        if self.fail_put:
            raise ClientError(self.fail_put)
        want = kw.get("IfMatch")
        if want and want.strip('"') != self.etag:
            raise ClientError("PreconditionFailed")
        self.body = kw["Body"].read()
        self.puts.append({k: v for k, v in kw.items() if k != "Body"})
        self.etag = f"new{len(self.puts)}"
        return {"ETag": f'"{self.etag}"'}

    def get_object(self, Bucket, Key):
        import io
        return {"Body": io.BytesIO(self.body), "ETag": f'"{self.etag}"'}


class FakeSt:
    def __init__(self):
        self.secrets = {"R2_BUCKET_NAME": "b"}
        self.session_state = {}


def load(db_path, client, st=None, docs=50):
    tree = ast.parse(SRC)
    code = "\n\n".join(ast.get_source_segment(SRC, n) for n in tree.body
                       if isinstance(n, ast.FunctionDef) and n.name in NAMES)
    st = st or FakeSt()
    ns = {"json": json, "os": os, "shutil": shutil, "time": time, "Path": Path, "datetime": datetime, "st": st,
          "DB_PATH": db_path, "DB_CLOUD_STATE": db_path + ".cloud.json", "R2_DB_KEY": "backups/rv_techtrack_v4.db",
          "R2_DB_PREV_KEY": "backups/rv_techtrack_v4.prev.db", "MIN_DOCS_TO_BACKUP": 10, "BACKUP_DEBOUNCE_SEC": 90,
          "LABEL_FIX_DIR": FIX_DIR, "LABEL_FIX_FIELDS": ("title", "clean_title", "brand", "models", "product_line"),
          "r2_available": lambda: True, "get_r2_client": lambda: client, "_reopen_db": lambda: None}
    ns["_local_doc_count"] = lambda: sqlite3.connect(db_path).execute("select count(*) from documents").fetchone()[0] \
        if Path(db_path).exists() else 0
    exec(code, ns)
    return ns, st


def make_lib(path, docs=12):
    c = sqlite3.connect(path)
    c.executescript(
        "create table categories(id integer primary key, name varchar(150) not null unique);"
        "create table documents(id integer primary key, category_id integer, title text, clean_title text, brand text,"
        " models text, product_line text);"
        "create table doc_chunks(id integer primary key, document_id integer, category_id integer);"
        "create table users(id integer primary key);"
        "insert into categories(id, name) values (4, 'Air Conditioning'), (25, 'Vent Fans'), (27, 'Lippert Unsorted');")
    for i in range(1, docs + 1):
        c.execute("insert into documents(id, category_id, title, brand, models) values (?, 27, ?, '', null)", (i, f"doc {i}"))
        c.execute("insert into doc_chunks(document_id, category_id) values (?, 27)", (i,))
    c.commit()
    c.close()


def write_fix(d, name, rows, cats=None):
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{name}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "field", "before", "after", "evidence"])
        w.writeheader()
        for r in rows:
            w.writerow(dict(zip(["id", "field", "before", "after"], r), evidence="test"))
    if cats:
        (d / f"{name}.categories.txt").write_text("\n".join(cats) + "\n", encoding="utf-8")


class TestLabelFixes(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.db = str(self.d / "rv_techtrack_v4.db")
        make_lib(self.db)
        self.fixes = self.d / "fixes"
        write_fix(self.fixes, "2026-11-24", [
            (1, "category", "Lippert Unsorted", "Air Conditioning"),
            (1, "models", "", "2111-0001"),
            (2, "category", "Lippert Unsorted", "Ladders"),
            (3, "brand", "", "Coleman-Mach"),
            (4, "title", "doc 4", "Fixed title"),
            (999, "models", "", "X1"),
        ], cats=["Dishwashers", "Ladders"])

    def run_fix(self):
        ns, _ = load(self.db, FakeR2())
        return ns["apply_label_fixes"](self.db, self.fixes)

    def test_applies_once_and_updates_chunks(self):
        got = self.run_fix()
        self.assertEqual((got["changed"], got["missing"]), (5, 1))
        c = sqlite3.connect(self.db)
        cats = dict(c.execute("select name, id from categories"))
        self.assertEqual([cats["Dishwashers"], cats["Ladders"]], [28, 29])       # order file keeps ids stable
        self.assertEqual(c.execute("select category_id, models from documents where id=1").fetchone(), (4, "2111-0001"))
        self.assertEqual(c.execute("select category_id from doc_chunks where document_id=2").fetchone()[0], cats["Ladders"])
        self.assertEqual(c.execute("select brand from documents where id=3").fetchone()[0], "Coleman-Mach")
        self.assertEqual(c.execute("select title from documents where id=4").fetchone()[0], "Fixed title")
        again = self.run_fix()
        self.assertEqual((again["applied"], again["changed"]), ([], 0))

    def test_stale_copy_after_a_clobber_is_fixed_again(self):
        """Today's failure: an older DB (fix not in it, no marker) comes back. The shipped fix re-applies."""
        self.run_fix()
        stale = str(self.d / "stale.db")
        make_lib(stale)
        ns, _ = load(stale, FakeR2())
        self.assertEqual(ns["apply_label_fixes"](stale, self.fixes)["changed"], 5)

    def test_value_edited_since_is_kept_and_already_fixed_is_counted(self):
        c = sqlite3.connect(self.db)
        c.execute("update documents set brand='Dometic' where id=3")
        c.execute("update documents set models='2111-0001' where id=1")
        c.commit()
        got = self.run_fix()
        self.assertEqual((got["changed"], got["already"], got["kept"]), (3, 1, 1))
        self.assertEqual(sqlite3.connect(self.db).execute("select brand from documents where id=3").fetchone()[0], "Dometic")

    def test_empty_library_waits_for_the_restore(self):
        empty = str(self.d / "empty.db")
        make_lib(empty, docs=0)
        ns, _ = load(empty, FakeR2())
        self.assertEqual(ns["apply_label_fixes"](empty, self.fixes)["applied"], [])
        self.assertFalse(sqlite3.connect(empty).execute(
            "select count(*) from sqlite_master where name='app_data_migrations'").fetchone()[0])

    def test_shipped_fix_file_is_the_11_24_change_log(self):
        rows = list(csv.DictReader((FIX_DIR / "2026-11-24.csv").open(encoding="utf-8", newline="")))
        self.assertEqual(len(rows), 941)
        self.assertEqual(len({r["id"] for r in rows}), 665)
        self.assertLessEqual({r["field"] for r in rows}, {"category", "title", "clean_title", "brand", "models"})
        self.assertIn({"id": "236", "field": "models", "before": "", "after": "2111-0001"},
                      [{k: r[k] for k in ("id", "field", "before", "after")} for r in rows])
        order = (FIX_DIR / "2026-11-24.categories.txt").read_text(encoding="utf-8").split("\n")
        self.assertEqual(order[:7], ["Dishwashers", "Fireplaces", "Laundry", "Pop-Tops", "Storage & Convenience",
                                     "Ladders", "Needs Category Review"])

    def test_app_runs_label_fixes_after_restore_and_seed(self):
        i_restore = SRC.index("\nmaybe_restore_db_from_r2()\n")
        i_seed = SRC.index("\nseed_data()\n", i_restore)
        i_fix = SRC.index("apply_label_fixes()", i_seed)
        self.assertLess(i_fix - i_seed, 200)


class TestCloudGuard(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.db = str(self.d / "rv_techtrack_v4.db")
        make_lib(self.db)

    def test_conflict_rules(self):
        ns, _ = load(self.db, FakeR2())
        f = ns["cloud_db_conflict"]
        self.assertEqual(f("abc", "abc"), "")
        self.assertEqual(f('"abc"', "abc"), "")
        self.assertEqual(f("", "abc"), "")          # not recorded yet (server from before this check): adopt
        self.assertEqual(f("abc", ""), "")          # no cloud copy at all
        self.assertIn("changed after this app loaded", f("abc", "xyz"))
        self.assertIn("Could not check", f("abc", None))

    def test_newer_cloud_copy_is_not_overwritten(self):
        """The 2:06 PM clobber: this server loaded cloud copy A; a fix wrote B; the server must not upload over B."""
        r2 = FakeR2(etag="B")
        ns, st = load(self.db, r2)
        ns["_db_cloud_state_save"]("A", 1.0)
        for force in (False, True):
            ok, why = ns["maybe_backup_db_to_r2"](force=force)
            self.assertFalse(ok)
            self.assertIn("changed after this app loaded", why)
        self.assertEqual(r2.puts, [])
        self.assertEqual(r2.copies, [])
        self.assertIn("_db_cloud_conflict", st.session_state)

    def test_new_session_with_no_changes_does_not_upload(self):
        """Before: _db_backup_mtime lived in session_state, so every new browser session's first run uploaded."""
        r2 = FakeR2(etag="A")
        ns, _ = load(self.db, r2)
        ns["_db_cloud_state_save"]("A", Path(self.db).stat().st_mtime)
        ok, why = ns["maybe_backup_db_to_r2"](force=False)
        self.assertEqual((ok, why), (False, "No database changes"))
        self.assertEqual(r2.puts, [])

    def test_matching_copy_uploads_with_if_match_and_records_new_etag(self):
        r2 = FakeR2(etag="A")
        ns, st = load(self.db, r2)
        ns["_db_cloud_state_save"]("A", 1.0)
        ok, note = ns["maybe_backup_db_to_r2"](force=False)
        self.assertTrue(ok, note)
        self.assertEqual(r2.puts[0]["IfMatch"], '"A"')
        self.assertEqual(ns["_db_cloud_state"]()["etag"], "new1")
        self.assertTrue(r2.body.startswith(b"SQLite format 3"))
        # the next new session sees the sidecar: nothing changed, nothing uploaded
        ns2, _ = load(self.db, r2)
        self.assertEqual(ns2["maybe_backup_db_to_r2"](force=False), (False, "No database changes"))

    def test_no_sidecar_adopts_then_guards(self):
        r2 = FakeR2(etag="A")
        ns, _ = load(self.db, r2)
        self.assertTrue(ns["maybe_backup_db_to_r2"](force=True)[0])
        r2.etag = "someone-else"
        ok, why = ns["maybe_backup_db_to_r2"](force=True)
        self.assertFalse(ok)
        self.assertEqual(len(r2.puts), 1)

    def test_save_racing_another_save_is_refused(self):
        r2 = FakeR2(etag="A")
        r2.fail_put = "PreconditionFailed"
        ns, _ = load(self.db, r2)
        ns["_db_cloud_state_save"]("A", 1.0)
        ok, why = ns["maybe_backup_db_to_r2"](force=True)
        self.assertFalse(ok)
        self.assertIn("changed after this app loaded", why)
        self.assertEqual(ns["_db_cloud_state"]()["etag"], "A")

    def test_head_failure_does_not_upload(self):
        r2 = FakeR2(etag="A")
        r2.head_object = lambda **kw: (_ for _ in ()).throw(ClientError("500"))
        ns, _ = load(self.db, r2)
        ok, why = ns["maybe_backup_db_to_r2"](force=True)
        self.assertFalse(ok)
        self.assertIn("Could not check", why)
        self.assertEqual(r2.puts, [])

    def test_restore_records_which_cloud_copy_it_loaded(self):
        src = str(self.d / "cloud.db")
        make_lib(src, docs=40)
        body = open(src, "rb").read() + b"\0" * 60000
        r2 = FakeR2(etag="C", body=body)
        empty = str(self.d / "fresh" / "rv_techtrack_v4.db")
        os.makedirs(os.path.dirname(empty))
        make_lib(empty, docs=0)
        ns, _ = load(empty, r2)
        self.assertTrue(ns["maybe_restore_db_from_r2"]())
        state = ns["_db_cloud_state"]()
        self.assertEqual(state["etag"], "C")
        self.assertEqual(state["mtime"], Path(empty).stat().st_mtime)
        self.assertEqual(ns["maybe_backup_db_to_r2"](force=False), (False, "No database changes"))


if __name__ == "__main__":
    unittest.main()
