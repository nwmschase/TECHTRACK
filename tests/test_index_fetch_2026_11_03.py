"""v4.20.0 index download-at-start (index_fetch.py; INDEX-DOWNLOAD-PLAN.md section 8). A fake R2 client serves files from
a dict; no network, no keys."""
import ast, hashlib, io, json, logging, os, sqlite3, threading, time
from pathlib import Path

import pytest

import index_fetch as IF

ROOT = Path(__file__).resolve().parents[1]


def make_index(folder, build_id="b1", fp="fp1", n=5):
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(folder / "index.sqlite")
    con.execute("create table meta(key text primary key, value text)"); con.execute("create table pages(doc_id, pdf_sheet)")
    con.executemany("insert into meta values(?,?)", [("build_id", build_id), ("library_fingerprint", fp), ("n_docs", "1"), ("built_at", "now")])
    con.executemany("insert into pages values(?,?)", [("L1", i) for i in range(1, n + 1)])
    con.commit(); con.close()
    return folder


def manifest_for(folder, build_id="b1", fp="fp1", n=5):
    files = {}
    for f in IF.FILES:
        p = Path(folder) / f
        files[f] = dict(key=f"pagefinder-index/{build_id}/{f}", size=p.stat().st_size, sha256=IF.sha256_file(p))
    return dict(build_id=build_id, built_at="now", library_fingerprint=fp, n_docs=1, n_pages=n, files=files)


class FakeBody:
    def __init__(self, data, cut=None):
        self.buf = io.BytesIO(data if cut is None else data[:cut])

    def read(self, n=-1):
        return self.buf.read(n)


class FakeR2:
    def __init__(self, objects, fail=None, flip=None, cut=None, secret="SECRET-VALUE-123"):
        self.objects, self.fail, self.flip, self.cut, self.calls, self.secret = objects, fail or {}, flip or set(), cut or set(), [], secret
        self.lock = threading.Lock()

    def get_object(self, Bucket, Key):
        with self.lock:
            self.calls.append(Key)
        if self.fail.get(Key):
            self.fail[Key] -= 1
            raise TimeoutError(f"connect timeout using key {self.secret}")
        if Key not in self.objects:
            raise KeyError(f"NoSuchKey {self.secret}")
        data = self.objects[Key]
        if Key in self.flip:
            data = bytes([data[0] ^ 1]) + data[1:]
        return {"Body": FakeBody(data, len(data) // 2 if Key in self.cut else None)}


@pytest.fixture
def built(tmp_path):
    src = make_index(tmp_path / "build")
    man = manifest_for(src)
    objs = {e["key"]: (src / f).read_bytes() for f, e in man["files"].items()}
    return src, man, objs


def no_sleep(_):
    pass


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    monkeypatch.delenv("TT_PAGEFINDER_DIR", raising=False)
    IF.STATE.reset()
    yield
    IF.STATE.reset()


def test_manifest_schema(tmp_path, built):
    _, man, _ = built
    p = tmp_path / "m.json"; json.dump(man, open(p, "w"))
    assert IF.load_manifest(p)["build_id"] == "b1"
    bad = dict(man); bad.pop("n_pages"); json.dump(bad, open(p, "w"))
    with pytest.raises(IF.ManifestError):
        IF.load_manifest(p)
    bad = json.loads(json.dumps(man)); bad["files"]["index.sqlite"]["key"] = "other/index.sqlite"; json.dump(bad, open(p, "w"))
    with pytest.raises(IF.ManifestError):
        IF.load_manifest(p)
    bad = dict(man, build_id="../x"); json.dump(bad, open(p, "w"))
    with pytest.raises(IF.ManifestError):
        IF.load_manifest(p)


def test_download_verifies_and_renames(tmp_path, built):
    _, man, objs = built
    r2 = FakeR2(objs)
    folder, source = IF.prepare(man, lambda: r2, "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    assert source == "r2" and len(r2.calls) == 1
    assert not list(folder.glob("*.part"))
    assert IF.gate(folder, man) == (True, "")


def test_cache_hit_downloads_nothing(tmp_path, built):
    _, man, objs = built
    r2 = FakeR2(objs)
    IF.prepare(man, lambda: r2, "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    r2.calls.clear()
    folder, source = IF.prepare(man, lambda: r2, "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    assert source == "cache" and r2.calls == []


def test_flipped_byte_retries_then_clear_error_and_no_part(tmp_path, built):
    _, man, objs = built
    key = man["files"]["index.sqlite"]["key"]
    r2 = FakeR2(objs, flip={key})
    waits = []
    with pytest.raises(IF.IndexUnavailable, match="index.sqlite: index.sqlite.part sha256"):
        IF.prepare(man, lambda: r2, "bucket", cache_root=tmp_path / "c", in_git=None, sleep=waits.append)
    assert waits == [2, 5, 15] and r2.calls.count(key) == 4
    assert not list((tmp_path / "c").rglob("*.part")) and not (tmp_path / "c" / "b1" / "index.sqlite").exists()


def test_truncated_body_is_a_size_mismatch(tmp_path, built):
    _, man, objs = built
    key = man["files"]["index.sqlite"]["key"]
    with pytest.raises(IF.IndexUnavailable, match="size"):
        IF.prepare(man, lambda: FakeR2(objs, cut={key}), "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)


def test_timeout_then_success(tmp_path, built):
    _, man, objs = built
    key = man["files"]["index.sqlite"]["key"]
    waits = []
    folder, source = IF.prepare(man, lambda: FakeR2(objs, fail={key: 2}), "bucket", cache_root=tmp_path / "c", in_git=None, sleep=waits.append)
    assert source == "r2" and waits == [2, 5]


def test_missing_key_404(tmp_path, built):
    _, man, objs = built
    objs.pop(man["files"]["index.sqlite"]["key"])
    with pytest.raises(IF.IndexUnavailable, match="index.sqlite: KeyError"):
        IF.prepare(man, lambda: FakeR2(objs), "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)


def test_no_secret_in_logs_or_errors(tmp_path, built, caplog):
    _, man, objs = built
    key = man["files"]["index.sqlite"]["key"]
    caplog.set_level(logging.DEBUG)
    with pytest.raises(IF.IndexUnavailable) as e:
        IF.prepare(man, lambda: FakeR2(objs, fail={key: 9}), "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    assert "SECRET-VALUE-123" not in str(e.value) and "SECRET-VALUE-123" not in caplog.text


def test_file_from_another_build_refused(tmp_path, built):
    src, man, objs = built
    other = make_index(tmp_path / "other", build_id="b0")
    man2 = manifest_for(src)
    # the other build's sqlite with its own (correct) sha: the content gate still refuses it
    man2["files"]["index.sqlite"] = dict(man2["files"]["index.sqlite"], size=(other / "index.sqlite").stat().st_size,
                                         sha256=IF.sha256_file(other / "index.sqlite"))
    objs[man2["files"]["index.sqlite"]["key"]] = (other / "index.sqlite").read_bytes()
    with pytest.raises(IF.IndexUnavailable, match="build_id b0 != manifest b1"):
        IF.prepare(man2, lambda: FakeR2(objs), "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    assert not (tmp_path / "c" / "b1" / "index.sqlite").exists()


def test_fingerprint_and_count_mismatch_refused(tmp_path):
    f = make_index(tmp_path / "a")
    man = manifest_for(f); man["library_fingerprint"] = "other"
    assert IF.gate(f, man)[0] is False and "fingerprint" in IF.gate(f, man)[1]


def test_manifest_pins_only_the_index_file_and_no_vectors():
    """v4.20.13: the smart-search vector files are gone from the pinned manifest, the fetch list and the repo."""
    assert IF.FILES == ("index.sqlite",)
    man = IF.load_manifest()
    assert list(man["files"]) == ["index.sqlite"] and "n_passages" not in man
    assert not (ROOT / "pagefinder" / "index" / "passages.npy").exists()
    assert not (ROOT / "pagefinder" / "index" / "passages.json").exists()


def test_in_git_copy_used_only_when_it_is_the_pinned_build(tmp_path, built):
    src, man, objs = built
    r2 = FakeR2(objs)
    folder, source = IF.prepare(man, lambda: r2, "bucket", cache_root=tmp_path / "c", in_git=src, sleep=no_sleep)
    assert source == "git" and r2.calls == []
    stale = make_index(tmp_path / "stale", build_id="old")
    folder, source = IF.prepare(man, lambda: r2, "bucket", cache_root=tmp_path / "c2", in_git=stale, sleep=no_sleep)
    assert source == "r2"


def test_r2_settings_missing(tmp_path, built):
    _, man, _ = built
    with pytest.raises(IF.IndexUnavailable, match="R2 settings are missing"):
        IF.prepare(man, lambda: None, None, cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    with pytest.raises(IF.IndexUnavailable, match="client could not be built"):
        IF.prepare(man, lambda: None, "bucket", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)


def test_two_starters_download_once(tmp_path, built):
    _, man, objs = built
    r2 = FakeR2(objs)
    out = []
    ts = [threading.Thread(target=lambda: out.append(IF.prepare(man, lambda: r2, "b", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)[1]))
          for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert sorted(out) == ["cache", "r2"] and len(r2.calls) == 1


def test_states_loading_ready_failed_and_retry_window(tmp_path, built, monkeypatch):
    _, man, objs = built
    mp = tmp_path / "INDEX_MANIFEST.json"; json.dump(man, open(mp, "w"))
    gate_open = threading.Event()

    class Slow(FakeR2):
        def get_object(self, Bucket, Key):
            gate_open.wait(5); return super().get_object(Bucket, Key)
    IF.start(lambda: Slow(objs), "b", manifest_path=mp, cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    with pytest.raises(IF.IndexLoading):
        IF.ready_dir()
    assert "loading" in IF.status_note()
    gate_open.set(); IF.STATE.thread.join(5)
    assert IF.ready_dir() == str(tmp_path / "c" / "b1") and "from R2 download" in IF.status_note()
    IF.STATE.reset()
    IF.start(lambda: None, None, manifest_path=mp, cache_root=tmp_path / "c3", in_git=None, background=False)
    with pytest.raises(IF.IndexUnavailable):
        IF.ready_dir()
    assert "could NOT load" in IF.status_note()
    assert IF.start(lambda: FakeR2(objs), "b", manifest_path=mp, cache_root=tmp_path / "c3", in_git=None, background=False) == "failed"
    IF.STATE.finished -= IF.RETRY_SEC + 1
    assert IF.start(lambda: FakeR2(objs), "b", manifest_path=mp, cache_root=tmp_path / "c3", in_git=None, sleep=no_sleep,
                    background=False) == "ready"
    assert IF.STATE.status == "ready"


def test_rollback_manifest_loads_previous_build(tmp_path):
    old, new = make_index(tmp_path / "old", "b-old", "fpo"), make_index(tmp_path / "new", "b-new", "fpn")
    m_old, m_new = manifest_for(old, "b-old", "fpo"), manifest_for(new, "b-new", "fpn")
    objs = {e["key"]: (d / f).read_bytes() for d, m in ((old, m_old), (new, m_new)) for f, e in m["files"].items()}
    assert IF.prepare(m_new, lambda: FakeR2(objs), "b", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)[0].name == "b-new"
    folder, _ = IF.prepare(m_old, lambda: FakeR2(objs), "b", cache_root=tmp_path / "c", in_git=None, sleep=no_sleep)
    assert folder.name == "b-old" and IF.gate(folder, m_old)[0]


def test_env_dir_skips_fetch(tmp_path, monkeypatch):
    monkeypatch.setenv("TT_PAGEFINDER_DIR", str(tmp_path))
    assert IF.start(lambda: 1 / 0, "b") == "ready" and IF.ready_dir() == str(tmp_path)


def test_pinned_manifest_in_git_is_valid():
    man = IF.load_manifest()
    assert man["n_docs"] > 0 and man["n_pages"] > 0


def test_app_hands_the_verified_folder_to_the_finder_and_names_the_library_state():
    src = (ROOT / "rv_techtrack.py").read_text()
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_gd_page_finder")
    body = ast.get_source_segment(src, fn)
    assert "index_fetch.ready_dir(get_r2_client" in body and "index_dir=index_dir" in body
    assert "index_fetch.LOADING_LINE" in src and "index_fetch.UNAVAILABLE_LINE" in src and "_start_index_fetch()" in src
    assert IF.LOADING_LINE != IF.UNAVAILABLE_LINE and "could not reach the AI" not in IF.UNAVAILABLE_LINE
