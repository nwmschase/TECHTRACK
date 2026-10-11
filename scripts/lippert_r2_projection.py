#!/usr/bin/env python3
"""Project R2 storage for the Lippert library.

Counts pages in the PDFs named by LOAD-MANIFEST.csv, then prices the PDFs,
the 150 dpi page images, and the figure crops. Figure crops use the kit-sheet
rate unless --sample renders a few PDFs and measures a rate.

  python3 scripts/lippert_r2_projection.py
  python3 scripts/lippert_r2_projection.py /workspace/lippert-docs/LOAD-MANIFEST.csv
  python3 scripts/lippert_r2_projection.py --root /workspace/lippert-docs --sample 20

The manifest is not required to be in git. A missing file exits 2 and prints
the command to run once the PDFs are on disk.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import library_figure_backfill as fb

DEFAULT_MANIFEST = Path("/workspace/lippert-docs/LOAD-MANIFEST.csv")
_NAME_KEYS = ("filename", "file", "path", "pdf", "name", "relative_path")
_BYTE_KEYS = ("bytes", "byte_size", "size", "pdf_bytes")
_PAGE_KEYS = ("pages", "page_count", "page")


def _header_key(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_")


def _cell(row: dict, canon: dict, key: str) -> str:
    header = canon.get(key)
    if not header:
        return ""
    value = row.get(header)
    return "" if value is None else str(value).strip()


def read_manifest_rows(csv_path: Path) -> list[dict]:
    """Rows with a filename. Optional byte and page columns are kept."""
    text = csv_path.read_text(encoding="utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ValueError(f"{csv_path} has no header row.")
    canon = {_header_key(header): header for header in reader.fieldnames}
    name_key = next((key for key in _NAME_KEYS if key in canon), "")
    if not name_key:
        raise ValueError(f"{csv_path} needs a filename column.")
    byte_key = next((key for key in _BYTE_KEYS if key in canon), "")
    page_key = next((key for key in _PAGE_KEYS if key in canon), "")
    rows = []
    for row in reader:
        filename = _cell(row, canon, name_key).replace("\\", "/")
        if not filename:
            continue
        rows.append(
            {
                "filename": filename,
                "bytes": _int_cell(_cell(row, canon, byte_key)) if byte_key else None,
                "pages": _int_cell(_cell(row, canon, page_key)) if page_key else None,
            }
        )
    if not rows:
        raise ValueError(f"{csv_path} has no file rows.")
    return rows


def _int_cell(value: str):
    raw = (value or "").replace(",", "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def resolve_pdf(filename: str, manifest_dir: Path, root: Path | None) -> Path | None:
    name = (filename or "").replace("\\", "/").strip()
    if not name:
        return None
    path = Path(name)
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    candidates.append(manifest_dir / name)
    if root is not None:
        candidates.append(root / name)
        candidates.append(root / path.name)
    candidates.append(manifest_dir / path.name)
    for item in candidates:
        if item.is_file():
            return item
    return None


def count_pdf_pages(path: Path) -> int:
    """Page count from the PDF catalog. This does not render the page."""
    from pypdf import PdfReader

    reader = PdfReader(str(path), strict=False)
    if getattr(reader, "is_encrypted", False):
        try:
            if reader.decrypt("") == 0:
                return 0
        except Exception:
            return 0
    return len(reader.pages)


def tally_manifest(rows: list[dict], manifest_dir: Path, root: Path | None) -> dict:
    """Sum PDF bytes and pages. A missing file uses a pages cell when one exists."""
    files = 0
    opened = 0
    missing = 0
    failed = 0
    pdf_bytes = 0
    pages = 0
    used_page_cell = 0
    for row in rows:
        files += 1
        path = resolve_pdf(row["filename"], manifest_dir, root)
        if path is None:
            missing += 1
            if row.get("bytes"):
                pdf_bytes += int(row["bytes"])
            if row.get("pages"):
                pages += int(row["pages"])
                used_page_cell += 1
            continue
        pdf_bytes += path.stat().st_size
        try:
            pages += count_pdf_pages(path)
            opened += 1
        except Exception:
            failed += 1
            if row.get("pages"):
                pages += int(row["pages"])
                used_page_cell += 1
    return {
        "files": files,
        "opened": opened,
        "missing": missing,
        "failed": failed,
        "pdf_bytes": pdf_bytes,
        "pages": pages,
        "used_page_cell": used_page_cell,
    }


def sample_crop_rate(rows: list[dict], manifest_dir: Path, root: Path | None, sample: int) -> dict:
    """Render a spread of PDFs and return crops per page. Empty when nothing opens."""
    import manual_figures as mf

    paths = []
    for row in rows:
        path = resolve_pdf(row["filename"], manifest_dir, root)
        if path is not None:
            paths.append(path)
    if not paths or sample <= 0:
        return {"pages": 0, "figures": 0, "files": 0}
    step = max(1, len(paths) // sample)
    chosen = paths[::step][:sample]
    pages = 0
    figures = 0
    opened = 0
    for path in chosen:
        try:
            indexed = mf.index_pdf_bytes(path.read_bytes())
        except Exception:
            continue
        opened += 1
        pages += len(indexed.get("pages") or [])
        figures += len(indexed.get("figures") or [])
    return {"pages": pages, "figures": figures, "files": opened}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Project Lippert library R2 storage.")
    parser.add_argument("manifest", nargs="?", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--root", default="", help="Directory that holds the PDFs.")
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Render this many PDFs and use their crop rate instead of the kit-sheet rate.",
    )
    args = parser.parse_args(argv)
    csv_path = Path(args.manifest)
    if not csv_path.is_file():
        print(
            f"Cannot read {csv_path}. Put LOAD-MANIFEST.csv and the PDFs on disk, then run:\n"
            f"  python3 scripts/lippert_r2_projection.py {csv_path}",
            file=sys.stderr,
        )
        return 2
    root = Path(args.root) if args.root else csv_path.parent
    rows = read_manifest_rows(csv_path)
    tally = tally_manifest(rows, csv_path.parent, root)
    figures = None
    sample_note = ""
    if args.sample:
        sample = sample_crop_rate(rows, csv_path.parent, root, args.sample)
        if sample["pages"]:
            rate = sample["figures"] / sample["pages"]
            figures = int(round(tally["pages"] * rate))
            sample_note = (
                f"Crop rate {rate:.2f} per page from {sample['files']} rendered PDFs "
                f"({sample['figures']} crops on {sample['pages']} pages)."
            )
    est = fb.project_r2_storage(tally["pdf_bytes"], tally["pages"], figures)
    print(f"Files in manifest: {tally['files']}")
    print(f"PDFs opened: {tally['opened']}")
    if tally["missing"] or tally["failed"]:
        print(f"Missing: {tally['missing']}  Failed to open: {tally['failed']}")
    if tally["used_page_cell"]:
        print(f"Page cells used when a PDF could not be opened: {tally['used_page_cell']}")
    print(fb.format_r2_projection(est))
    if sample_note:
        print(sample_note)
    elif est["figures_estimated"]:
        print(
            "Figure crops use the kit-sheet rate "
            f"({fb.SAMPLE_CROPS} crops on {fb.SAMPLE_PAGES} pages). "
            "A text manual has fewer. Re-run with --sample 20 to measure a rate."
        )
    print("Class A and Class B request charges are not included.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
