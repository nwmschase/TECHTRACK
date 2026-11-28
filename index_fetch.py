"""Download-at-start of the page-finder index from R2 (INDEX-DOWNLOAD-PLAN.md, 2026-10-31; built 2026-11-03, v4.20.0).

The index file (index.sqlite) is too big to rebuild on every start. The build that the code expects is PINNED in git:
pagefinder/INDEX_MANIFEST.json lists build_id, built_at, library_fingerprint, n_docs, n_pages and the file's R2 key, size
and sha256. Rollback = revert that file. (v4.20.13: the passage-vector files passages.npy / passages.json went with the
deleted meaning search; they are no longer fetched or checked.)

At app start a background thread makes ~/.cache/techtrack-index/<build_id>/ hold the index file:
  1. a cached folder whose file matches the manifest is used as is (0 downloads);
  2. else the in-git pagefinder/index is used only if its file matches the SAME manifest sha (never an older build);
  3. else the file streams to <file>.part (1 MB chunks), its size and sha256 are checked, then it is renamed in place.
     Each file is tried 4 times (waits 2 s / 5 s / 15 s) on top of boto3's own retries.
Then the folder is gated: meta.build_id and meta.library_fingerprint equal the manifest. Only a folder that passes is handed to the page-finder. A failure leaves a clear
"manual library could not load" state (never an empty, half or silent keyword-only library) and is retried every 10 min.

TT_PAGEFINDER_DIR set (tests, dev, offline tools) = use that folder; no fetch. No secret value is read or logged here:
the caller passes a ready client factory (the app's get_r2_client) and the bucket name.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "pagefinder" / "INDEX_MANIFEST.json"
IN_GIT_DIR = HERE / "pagefinder" / "index"
CACHE_ROOT = Path(os.environ.get("TT_INDEX_CACHE", Path.home() / ".cache" / "techtrack-index"))
FILES = ("index.sqlite",)
BACKOFF = (2, 5, 15)
RETRY_SEC = 600
CHUNK = 1024 * 1024
LOG = logging.getLogger("techtrack.index_fetch")

LOADING_LINE = ("The manual library is still loading (this takes up to a minute after the app wakes up). "
                "Nothing was guessed. Send the same message again in a moment.")
UNAVAILABLE_LINE = "The manual library could not load. Nothing was guessed. Try again in a minute."


class IndexLoading(RuntimeError):
    """The index is being fetched; ask the tech to resend shortly."""


class IndexUnavailable(RuntimeError):
    """No verified copy of the pinned build could be made ready."""


class ManifestError(ValueError):
    pass


def load_manifest(path=MANIFEST) -> dict:
    with open(path, encoding="utf-8") as fh:
        man = json.load(fh)
    need = ("build_id", "built_at", "library_fingerprint", "n_docs", "n_pages", "files")
    miss = [k for k in need if k not in man]
    if miss:
        raise ManifestError(f"manifest missing {', '.join(miss)}")
    if not isinstance(man["build_id"], str) or not man["build_id"] or "/" in man["build_id"] or ".." in man["build_id"]:
        raise ManifestError("manifest build_id is not a plain name")
    for f in FILES:
        e = man["files"].get(f)
        if not isinstance(e, dict) or not all(k in e for k in ("key", "size", "sha256")):
            raise ManifestError(f"manifest entry for {f} is incomplete")
        if not e["key"].startswith(f"pagefinder-index/{man['build_id']}/"):
            raise ManifestError(f"manifest key for {f} is not under pagefinder-index/{man['build_id']}/")
    return man


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def file_ok(path: Path, entry: dict) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"{path.name} missing"
    if path.stat().st_size != int(entry["size"]):
        return False, f"{path.name} size {path.stat().st_size} != {entry['size']}"
    got = sha256_file(path)
    if got != entry["sha256"]:
        return False, f"{path.name} sha256 {got[:12]} != {entry['sha256'][:12]}"
    return True, ""


def gate(folder: Path, man: dict) -> tuple[bool, str]:
    """The index file present with the manifest's size+sha256, and its content agrees with the manifest."""
    folder = Path(folder)
    for f in FILES:
        ok, why = file_ok(folder / f, man["files"][f])
        if not ok:
            return False, why
    try:
        con = sqlite3.connect(f"file:{folder / 'index.sqlite'}?mode=ro", uri=True)
        meta = dict(con.execute("select key, value from meta").fetchall())
        con.close()
    except Exception as exc:
        return False, f"index.sqlite unreadable ({type(exc).__name__})"
    if meta.get("build_id") != man["build_id"]:
        return False, f"index.sqlite build_id {meta.get('build_id')} != manifest {man['build_id']}"
    if meta.get("library_fingerprint") != man["library_fingerprint"]:
        return False, "index.sqlite library_fingerprint differs from the manifest"
    return True, ""


def _download(client, bucket, key, dest: Path, entry: dict, sleep=time.sleep) -> None:
    part = dest.with_name(dest.name + ".part")
    last = ""
    for attempt in range(len(BACKOFF) + 1):
        try:
            obj = client.get_object(Bucket=bucket, Key=key)
            body = obj["Body"]
            with open(part, "wb") as out:
                while True:
                    chunk = body.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
            ok, why = file_ok(part, entry)
            if ok:
                os.replace(part, dest)
                return
            last = why
        except Exception as exc:  # the message names the class only (never request details that could hold a key)
            last = f"{type(exc).__name__}"
        part.unlink(missing_ok=True)
        LOG.warning("index fetch %s attempt %d failed: %s", dest.name, attempt + 1, last)
        if attempt < len(BACKOFF):
            sleep(BACKOFF[attempt])
    raise IndexUnavailable(f"{dest.name}: {last}")


def prepare(man: dict, client_factory, bucket: str | None, cache_root=None, in_git=IN_GIT_DIR, sleep=time.sleep) -> tuple[Path, str]:
    """Make a verified folder for the pinned build. Returns (folder, source) or raises IndexUnavailable."""
    cache_root = Path(cache_root or CACHE_ROOT)
    folder = cache_root / man["build_id"]
    folder.mkdir(parents=True, exist_ok=True)
    with open(cache_root / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)          # a second process waits here, then finds the cache ready
        try:
            ok, why = gate(folder, man)
            if ok:
                return folder, "cache"
            if in_git and Path(in_git).is_dir():
                ok_git, _ = gate(Path(in_git), man)
                if ok_git:
                    return Path(in_git), "git"
            if not bucket:
                raise IndexUnavailable("R2 settings are missing")
            client = client_factory()
            if client is None:
                raise IndexUnavailable("R2 client could not be built")
            for f in FILES:
                ok, _ = file_ok(folder / f, man["files"][f])
                if not ok:
                    _download(client, bucket, man["files"][f]["key"], folder / f, man["files"][f], sleep=sleep)
            ok, why = gate(folder, man)
            if not ok:
                for f in FILES:
                    (folder / f).unlink(missing_ok=True)
                raise IndexUnavailable(f"downloaded files failed the check: {why}")
            return folder, "r2"
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


class _State:
    def __init__(self):
        self.lock = threading.Lock()
        self.reset()

    def reset(self):
        self.status = "idle"        # idle | loading | ready | failed
        self.folder = None
        self.source = ""
        self.error = ""
        self.build_id = ""
        self.started = 0.0
        self.finished = 0.0
        self.thread = None


STATE = _State()


def _run(manifest_path, client_factory, bucket, cache_root, in_git, sleep):
    t0 = time.time()
    try:
        man = load_manifest(manifest_path)
        STATE.build_id = man["build_id"]
        folder, source = prepare(man, client_factory, bucket, cache_root=cache_root, in_git=in_git, sleep=sleep)
        with STATE.lock:
            STATE.folder, STATE.source, STATE.status, STATE.error = folder, source, "ready", ""
        LOG.warning("index ready: build %s from %s in %.1fs", man["build_id"], source, time.time() - t0)
    except Exception as exc:
        with STATE.lock:
            STATE.status, STATE.error = "failed", f"{type(exc).__name__}: {exc}"
        LOG.error("index could not load: %s", STATE.error)
    finally:
        STATE.finished = time.time()


def start(client_factory, bucket, manifest_path=MANIFEST, cache_root=None, in_git=IN_GIT_DIR, sleep=time.sleep,
          background=True):
    """Start (once per process) making the pinned index ready. Safe to call on every Streamlit rerun."""
    env = os.environ.get("TT_PAGEFINDER_DIR")
    with STATE.lock:
        if env:
            STATE.status, STATE.folder, STATE.source = "ready", Path(env), "env"
            return STATE.status
        if STATE.status in ("loading", "ready"):
            return STATE.status
        if STATE.status == "failed" and time.time() - STATE.finished < RETRY_SEC:
            return STATE.status
        STATE.status, STATE.started, STATE.error = "loading", time.time(), ""
        args = (manifest_path, client_factory, bucket, cache_root, in_git, sleep)
        if background:
            STATE.thread = threading.Thread(target=_run, args=args, name="techtrack-index-fetch", daemon=True)
            STATE.thread.start()
    if not background:
        _run(*args)
    return STATE.status


def ready_dir(client_factory=None, bucket=None, **kw) -> str:
    """The verified index folder, or IndexLoading / IndexUnavailable (a failed state retries after RETRY_SEC)."""
    if os.environ.get("TT_PAGEFINDER_DIR"):
        return os.environ["TT_PAGEFINDER_DIR"]
    if client_factory is not None:
        start(client_factory, bucket, **kw)
    with STATE.lock:
        if STATE.status == "ready":
            return str(STATE.folder)
        if STATE.status == "failed":
            raise IndexUnavailable(STATE.error)
    raise IndexLoading("index fetch in progress")


def status_note() -> str:
    """One line for managers (no secrets): what is loaded and from where, or why not."""
    s = STATE
    if s.status == "ready":
        where = {"cache": "disk cache", "r2": "R2 download", "git": "the copy in git", "env": "TT_PAGEFINDER_DIR"}.get(s.source, s.source)
        return f"Manual library index {s.build_id or ''} ready (from {where})."
    if s.status == "loading":
        return f"Manual library index {s.build_id or ''} is loading ({time.time() - s.started:.0f}s so far)."
    if s.status == "failed":
        return f"Manual library index could NOT load: {s.error}. TechTrack retries every 10 minutes."
    return "Manual library index not started."
