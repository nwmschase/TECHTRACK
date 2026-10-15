"""Brand-cite check for Bay PDFs (batch fix 1, Leader 2026-10-14 8:57 PM).

  BR-1  a cited manual's maker differs from the case brand
        (maker = documents.brand, else the maker named in the title).
  BR-2  a cited title is not a document in the shop DB.

Usage: python scripts/brand_cite_check.py SHEET.pdf --brand BRAND --db DB   (exit 1 on any FAIL)
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gd_library_coach import canonical_shop_brands  # noqa: E402


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def find_docs(title: str, docs: list[tuple]) -> list[tuple]:
    t = _norm(title)
    hits = [d for d in docs if _norm(d[1]) == t]
    hits = hits or [d for d in docs if t and len(t) > 8 and (t in _norm(d[1]) or _norm(d[1]) in t and len(_norm(d[1])) > 8)]
    if not hits:
        code = re.search(r"(CCD-\d+|TI-\s?\d+)", title or "", re.I)
        if code:
            key = _norm(code.group(1))
            hits = [d for d in docs if key in _norm(f"{d[1]} {d[3] or ''}")]
    return hits


def check_titles(titles: list[str], brand: str, docs: list[tuple]) -> list[str]:
    """docs rows are (id, title, brand, file_path)."""
    asked = canonical_shop_brands(brand)
    problems: list[str] = []
    for title in dict.fromkeys(titles):
        hits = find_docs(title, docs)
        if not hits:
            problems.append(f"BR-2 cited title not in DB: {title}")
            makers = [canonical_shop_brands(title)]
        else:
            makers = [canonical_shop_brands(d[2] or "") or canonical_shop_brands(d[1]) for d in hits]
        makers = [m for m in makers if m]
        if asked and makers and not any(m & asked for m in makers):
            problems.append(f"BR-1 cited maker {sorted(set().union(*makers))} is not case brand {sorted(asked)}: {title}")
    return problems


def pdf_titles(path: str) -> list[str]:
    text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
    src = text.split("SOURCES (SHOP DOCUMENT LIBRARY)", 1)[-1] if "SOURCES (SHOP" in text else ""
    return [m.group(1).strip() for m in re.finditer(r"^- (.+?) page \d+\s*$", src, re.M)]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="+")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--db", required=True)
    a = ap.parse_args(argv)
    docs = list(sqlite3.connect(a.db).execute("select id, title, brand, file_path from documents"))
    bad = 0
    for path in a.pdf:
        problems = check_titles(pdf_titles(path), a.brand, docs)
        print(f"{path}: {'PASS' if not problems else 'FAIL'}")
        for p in problems:
            print("  " + p)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
