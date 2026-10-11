"""The headless gate reads a SQLite library and an R2 cache, not the Streamlit app."""
import json
import sqlite3
import unittest
from pathlib import Path

from scripts.thetford_live_gate import main

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "thetford_live_retrieval.json"
OM = "Thetford Style II OM Permanent RV Toilet 42088"


def _build(db: Path, cache: Path) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            category_id INTEGER,
            title TEXT,
            file_path TEXT,
            keywords TEXT,
            brand TEXT,
            product_line TEXT,
            models TEXT,
            clean_title TEXT,
            doc_number TEXT
        );
        CREATE TABLE doc_chunks (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            category_id INTEGER,
            title TEXT,
            page INTEGER,
            chunk_text TEXT,
            keywords TEXT
        );
        CREATE TABLE doc_assets (
            id INTEGER PRIMARY KEY,
            document_id INTEGER,
            page INTEGER,
            kind TEXT,
            label TEXT,
            image_path TEXT,
            width INTEGER,
            height INTEGER,
            caption TEXT,
            bbox TEXT,
            chunk_id INTEGER
        );
        """
    )
    conn.execute("INSERT INTO categories (id, name) VALUES (1, 'Plumbing / Toilets')")
    docs = {}
    for chunk in payload["chunks"]:
        docs[int(chunk["document_id"])] = (chunk["title"], chunk.get("file_path") or "", chunk.get("brand") or "")
    for doc_id, (title, file_path, brand) in docs.items():
        conn.execute(
            """
            INSERT INTO documents (
                id, category_id, title, file_path, keywords, brand, product_line,
                models, clean_title, doc_number
            ) VALUES (?, 1, ?, ?, '', ?, '', '', ?, '')
            """,
            (doc_id, title, file_path, brand, title),
        )
    for index, chunk in enumerate(payload["chunks"], 1):
        conn.execute(
            """
            INSERT INTO doc_chunks (
                id, document_id, category_id, title, page, chunk_text, keywords
            ) VALUES (?, ?, 1, ?, ?, ?, '')
            """,
            (index, chunk["document_id"], chunk["title"], chunk["page"], chunk["excerpt"]),
        )
    assets = list(payload["figures"])
    assets.append(
        {
            "document_id": 3,
            "title": OM,
            "page": 3,
            "kind": "page",
            "label": "page",
            "brand": "Thetford",
            "file_path": "library/42088.pdf",
        }
    )
    assets.append(
        {
            "document_id": 3,
            "title": OM,
            "page": 7,
            "kind": "figure",
            "label": "Step 1",
            "brand": "Thetford",
            "file_path": "library/42088.pdf",
        }
    )
    cache.mkdir(parents=True, exist_ok=True)
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    for index, fig in enumerate(assets, 1):
        key = f"library/doc{fig['document_id']}-p{fig['page']}-{index}.png"
        dest = cache / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(png)
        conn.execute(
            """
            INSERT INTO doc_assets (
                id, document_id, page, kind, label, image_path, width, height,
                caption, bbox, chunk_id
            ) VALUES (?, ?, ?, ?, ?, ?, 10, 10, ?, '', NULL)
            """,
            (
                index,
                fig["document_id"],
                fig["page"],
                fig.get("kind") or "figure",
                fig.get("label") or "",
                key,
                fig.get("label") or "",
            ),
        )
    conn.commit()
    conn.close()


class TestThetfordLiveGateCli(unittest.TestCase):
    def test_db_and_cache_build_the_pdf_and_transcript(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "library.db"
            cache = root / "cache"
            out = root / "out"
            _build(db, cache)
            code = main(["--db", str(db), "--cache", str(cache), "--out", str(out)])
            report = (out / "report.txt").read_text(encoding="utf-8")
            transcript = (out / "transcript.txt").read_text(encoding="utf-8")
            self.assertEqual(code, 0, report)
            self.assertIn("PASS", report)
            self.assertTrue((out / "thetford-bay.pdf").stat().st_size > 1000)
            self.assertIn("T2 Tech: Show me where that connection is", transcript)
            self.assertIn("back of the toilet", transcript.lower())
            self.assertIn("water valve", transcript.lower())
            self.assertNotIn("not stated", transcript.lower())
            self.assertNotIn("How (", transcript)
            self.assertNotIn("page 7", transcript.lower())
            self.assertNotRegex(transcript, r"Step 1")
