"""Reviewed OCR copies of scanned library PDFs (Chase 2026-10-31 3:05 PM PT: force-OCR the low-text scans).

A scanned PDF often carries a thin text layer (a 'CCD-0009642 Rev. 1-17-2025' stamp, a header), so its sheets are not empty
and pagetext.do_pdf_path, which OCRs only sheets with under 20 characters, keeps the stamp as the whole page text. The
app's own import (library_bulk_import.inspect_pdf_bytes) reads the same text layer and files the doc as 'text'. The fix is
an OCR copy of the PDF (ocrmypdf --redo-ocr: the PDF's own text is kept exactly and the image parts get an OCR text
layer; --force-ocr only when redo fails), made offline and checked, and then used in place of the original.

Manifest (CSV, staging/OCR-COPIES-MANIFEST.csv): original_sha256, copy, copy_sha256, method (+ any other columns).
build_index --ocr-copies <manifest> reads the copy for every app doc whose PDF sha256 is an original_sha256 in it. The
copy's sha256 is checked before use and the build stops on a mismatch or a missing copy (a wrong file is never indexed).
When the copy itself is loaded into the library (the 10/20 FILE_REPLACE_OCR way), no manifest is needed: its own text
layer already holds the OCR text."""
from __future__ import annotations

import csv
import hashlib
import os


class OcrCopyError(ValueError):
    pass


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def load(path):
    """{original sha256: {'copy': path, 'copy_sha256': sha, 'method': ...}} from the manifest; rows without a copy are skipped."""
    out = {}
    for n, r in enumerate(csv.DictReader(open(path, encoding='utf-8')), 2):
        o, c, cs = (r.get('original_sha256') or '').strip(), (r.get('copy') or '').strip(), (r.get('copy_sha256') or '').strip()
        if not o or not c:
            continue
        if not cs:
            raise OcrCopyError(f'{path}:{n}: copy without its sha256')
        if o in out and out[o]['copy_sha256'] != cs:
            raise OcrCopyError(f'{path}:{n}: two different copies for one original {o[:12]}')
        out[o] = dict(copy=c, copy_sha256=cs, method=(r.get('method') or '').strip())
    return out


def resolve(original_sha, copies):
    """(path, note) of the checked OCR copy for a PDF sha256, or (None, '') when there is none."""
    e = copies.get(original_sha or '')
    if not e:
        return None, ''
    if not os.path.exists(e['copy']):
        raise OcrCopyError(f'OCR copy missing: {e["copy"]}')
    got = sha256_file(e['copy'])
    if got != e['copy_sha256']:
        raise OcrCopyError(f'OCR copy changed since review: {e["copy"]} sha256 {got[:12]} != {e["copy_sha256"][:12]}')
    return e['copy'], f'pdf (OCR copy, {e["method"] or "ocrmypdf"}, sha256 {got[:12]})'
