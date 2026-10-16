import os, sqlite3, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import library_category_fix as f


def _db():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT, category_id INTEGER);
    CREATE TABLE doc_chunks(id INTEGER PRIMARY KEY, document_id INTEGER, category_id INTEGER);
    INSERT INTO categories VALUES (6,'Leveling'),(12,'Range & Cooktops'),(18,'awnings'),(20,'slide-outs');
    INSERT INTO documents VALUES (309,'Girard 17 inch All Glass Gas Range Troubleshooting and Service Manual',18),
                                 (631,'Power Gear T.I.P. - AUTOMATIC LEVEL CONTROLLER SET-UP',20);
    INSERT INTO doc_chunks VALUES (1,309,18),(2,631,20);""")
    return c


class TestCategoryFix(unittest.TestCase):
    def test_dry_run_apply_idempotent_rollback(self):
        c = _db()
        p = f.plan(c)
        self.assertEqual([r["status"] for r in p], ["will change", "will change"])
        self.assertEqual(c.execute("select category_id from documents where id=309").fetchone()[0], 18)  # dry run changed nothing
        undo = f.apply(c, p)
        self.assertEqual(c.execute("select category_id from documents where id=309").fetchone()[0], 12)
        self.assertEqual(c.execute("select category_id from doc_chunks where document_id=631").fetchone()[0], 6)
        self.assertEqual([r["status"] for r in f.plan(c)], ["already correct", "already correct"])
        self.assertEqual(f.rollback(c, undo), 2)
        self.assertEqual(c.execute("select category_id from documents where id=631").fetchone()[0], 20)

    def test_title_mismatch_is_skipped(self):
        c = _db()
        c.execute("update documents set title='Something else' where id=309")
        self.assertTrue(f.plan(c)[0]["status"].startswith("skip"))
