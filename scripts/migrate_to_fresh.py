"""Build the DB the new TechTrack starts with: the LIVE DB's people data + the CLEAN library (no network, no R2).

    python scripts/migrate_to_fresh.py --live <downloaded live .db> --library <clean library .db> --base <library base .db> \
        --out <new .db> [--report <report.json>] [--sources <sources.json> --r2-plan <r2-upload-plan.csv>]

- live    : today's live DB (Database Backup & Restore -> Download). Opened READ-ONLY, never changed.
- library : the clean 811-doc library (library-dialin dry run: 10/16 live library + approved cleanup + 61 new manuals + 23 OCR copies).
- base    : the live library snapshot the clean library was built from (live-2026-10-16.db). Used only to prove the live
            library has not changed since; if it has, the script stops and lists what changed (nothing is guessed).

Library tables (taken from --library): documents, doc_chunks, doc_assets, categories, bulk_import_jobs, bulk_import_items,
figure_backfill_jobs, figure_backfill_items. EVERY other table (users, diagnostic_jobs, ask_chats, ask_messages,
certificates, safety_*, and any table added later) is copied from --live unchanged and verified row-for-row.
The 4 categories the load plan deletes (empty after the cleanup) are removed only if they hold no document.
Exit code 0 only when every check passes."""
import argparse, csv, hashlib, json, os, shutil, sqlite3, sys, time

LIBRARY_TABLES = ['documents', 'doc_chunks', 'doc_assets', 'categories', 'bulk_import_jobs', 'bulk_import_items',
                  'figure_backfill_jobs', 'figure_backfill_items']
DROP_IF_EMPTY_CATEGORIES = ['furrion-appliances', 'slide-outs', 'plumbing-sewer-water', 'recalls-bulletins']  # READY-TO-LOAD step 6


def ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def tables(c):
    return sorted(r[0] for r in c.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'"))


def cols(c, t):
    return [r[1] for r in c.execute(f'pragma table_info("{t}")')]


def table_hash(c, t):
    h = hashlib.sha256(); n = 0
    cl = ','.join(f'"{x}"' for x in cols(c, t))
    for row in c.execute(f'select {cl} from "{t}" order by 1'):
        h.update(repr(row).encode()); n += 1
    return h.hexdigest(), n


def diff_ids(a, b, t):
    cl = ','.join(f'"{x}"' for x in cols(a, t))
    ra = {r[0]: r for r in a.execute(f'select {cl} from "{t}"')}
    rb = {r[0]: r for r in b.execute(f'select {cl} from "{t}"')}
    return dict(only_live=sorted(set(ra) - set(rb))[:50], only_base=sorted(set(rb) - set(ra))[:50],
                changed=sorted(k for k in set(ra) & set(rb) if ra[k] != rb[k])[:50])


def accept_covered(live, base, accepted, drift):
    """Drop drift that comes only from ACCEPTED live documents (added after the base, already covered by the clean library):
    rows that are new in live and belong to those docs, plus the bulk-import jobs/items that imported them.
    Anything deleted from live (only_base) or any other change stays as drift, so the script still stops on it."""
    jobs = {r[0] for r in live.execute(f"select distinct job_id from bulk_import_items where document_id in ({','.join(map(str, accepted))})")}
    def owned(t, rid):
        if t == 'documents': return rid in accepted
        if t in ('doc_chunks', 'doc_assets'):
            r = live.execute(f'select document_id from "{t}" where id=?', (rid,)).fetchone(); return bool(r) and r[0] in accepted
        if t == 'bulk_import_jobs': return rid in jobs
        if t == 'bulk_import_items':
            r = live.execute('select job_id from bulk_import_items where id=?', (rid,)).fetchone(); return bool(r) and r[0] in jobs
        return False
    left = {}
    for t, d in drift.items():
        full = diff_ids_all(live, base, t)
        if full['only_base'] or t not in ('documents', 'doc_chunks', 'doc_assets', 'bulk_import_jobs', 'bulk_import_items'):
            left[t] = d; continue
        if t in ('documents', 'doc_chunks', 'doc_assets') and full['changed']:
            left[t] = d; continue
        bad = [i for i in full['only_live'] + full['changed'] if not owned(t, i)]
        if bad: left[t] = dict(d, not_accepted=bad[:50])
    return left


def diff_ids_all(a, b, t):
    cl = ','.join(f'"{x}"' for x in cols(a, t))
    ra = {r[0]: r for r in a.execute(f'select {cl} from "{t}"')}
    rb = {r[0]: r for r in b.execute(f'select {cl} from "{t}"')}
    return dict(only_live=sorted(set(ra) - set(rb)), only_base=sorted(set(rb) - set(ra)),
                changed=sorted(k for k in set(ra) & set(rb) if ra[k] != rb[k]))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', required=True); ap.add_argument('--library', required=True); ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True); ap.add_argument('--report'); ap.add_argument('--sources'); ap.add_argument('--r2-plan')
    ap.add_argument('--accept-live-docs', default='', help='comma list of live document ids added after the base that the clean library already covers '
                    '(checked by content); their rows and the bulk-import jobs that made them are allowed to differ from the base')
    a = ap.parse_args(argv)
    rep = dict(started=time.strftime('%Y-%m-%d %H:%M:%S %Z'), live=os.path.abspath(a.live), library=os.path.abspath(a.library),
               base=os.path.abspath(a.base), checks={}, ok=False)
    def check(name, ok, detail=None):
        rep['checks'][name] = dict(ok=bool(ok), detail=detail)
        print(('PASS ' if ok else 'FAIL ') + name + (f'  {detail}' if detail is not None else ''), flush=True)
        return ok
    def finish(code):
        rep['ok'] = code == 0
        if a.report: json.dump(rep, open(a.report, 'w'), indent=1, default=str)
        return code
    sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    rep['live_sha256_before'] = sha(a.live)
    live, lib, base = ro(a.live), ro(a.library), ro(a.base)
    for name, c in (('live', live), ('library', lib), ('base', base)):
        if not check(f'{name} integrity_check', c.execute('pragma integrity_check').fetchone()[0] == 'ok'): return finish(2)
    # same schema for every library table
    for t in LIBRARY_TABLES:
        if not check(f'schema {t} live == library', cols(live, t) == cols(lib, t), None if cols(live, t) == cols(lib, t) else (cols(live, t), cols(lib, t))):
            return finish(2)
    # live library unchanged since the base the clean library was built from
    drift = {}
    for t in LIBRARY_TABLES:
        if table_hash(live, t)[0] != table_hash(base, t)[0]:
            drift[t] = diff_ids(live, base, t)
    accepted = {int(x) for x in a.accept_live_docs.split(',') if x.strip()}
    if drift and accepted:
        rep['accepted_live_docs'] = sorted(accepted)
        drift = accept_covered(live, base, accepted, drift)
    if not check('live library == base library (no uploads/edits since the clean library was built)', not drift, drift or None):
        print('STOP: the live library changed since the base. Re-run the library dial-in on this live DB first.', flush=True)
        return finish(3)
    # build: copy live (all people data), then replace library tables
    if os.path.exists(a.out): os.remove(a.out)
    dst = sqlite3.connect(a.out)
    live.backup(dst); dst.commit()
    dst.close()
    dst = sqlite3.connect(a.out)
    dst.execute(f"attach database '{os.path.abspath(a.library)}' as lib")
    dst.execute('pragma foreign_keys=OFF')
    with dst:
        for t in LIBRARY_TABLES:
            cl = ','.join(f'"{x}"' for x in cols(lib, t))
            dst.execute(f'delete from main."{t}"')
            dst.execute(f'insert into main."{t}"({cl}) select {cl} from lib."{t}"')
        dropped = []
        for name in DROP_IF_EMPTY_CATEGORIES:
            r = dst.execute('select id from main.categories where name=?', (name,)).fetchone()
            if r and not dst.execute('select 1 from main.documents where category_id=? union select 1 from main.doc_chunks where category_id=?', (r[0], r[0])).fetchone():
                dst.execute('delete from main.categories where id=?', (r[0],)); dropped.append(name)
    dst.execute('detach database lib')
    dst.execute('vacuum')
    dst.commit(); dst.close()
    rep['categories_dropped_empty'] = dropped
    out = ro(a.out)
    ok = True
    ok &= check('out integrity_check', out.execute('pragma integrity_check').fetchone()[0] == 'ok')
    # nothing real lost: every non-library table is identical to live
    people = [t for t in tables(live) if t not in LIBRARY_TABLES]
    rep['people_tables'] = {}
    for t in people:
        hl, nl = table_hash(live, t); ho, no = table_hash(out, t)
        rep['people_tables'][t] = dict(rows_live=nl, rows_out=no, identical=hl == ho)
        ok &= check(f'{t}: identical to live ({nl} rows)', hl == ho, None if hl == ho else (nl, no))
    ok &= check('no table lost', set(tables(live)) <= set(tables(out)), sorted(set(tables(live)) - set(tables(out))))
    rep['library_tables'] = {}
    for t in LIBRARY_TABLES:
        hb, nb = table_hash(lib, t)
        if t == 'categories':
            nb -= len(dropped)
            no = out.execute('select count(*) from categories').fetchone()[0]
            same = no == nb and not out.execute(f"select 1 from categories where name in ({','.join('?' * len(dropped)) or 'null'})", dropped).fetchone()
        else:
            ho, no = table_hash(out, t); same = ho == hb
        rep['library_tables'][t] = dict(rows_library=nb, rows_out=no, identical=same)
        ok &= check(f'{t}: equals clean library ({nb} rows)', same, None if same else (nb, no))
    # references hold
    fk = {
        'documents.category_id -> categories': 'select count(*) from documents d where not exists(select 1 from categories c where c.id=d.category_id)',
        'doc_chunks.document_id -> documents': 'select count(*) from doc_chunks x where not exists(select 1 from documents d where d.id=x.document_id)',
        'doc_chunks.category_id -> categories': 'select count(*) from doc_chunks x where not exists(select 1 from categories c where c.id=x.category_id)',
        'doc_assets.document_id -> documents': 'select count(*) from doc_assets x where not exists(select 1 from documents d where d.id=x.document_id)',
        'documents.uploaded_by -> users': 'select count(*) from documents d where d.uploaded_by is not null and not exists(select 1 from users u where u.id=d.uploaded_by)',
        'ask_messages.chat_id -> ask_chats': 'select count(*) from ask_messages m where not exists(select 1 from ask_chats c where c.id=m.chat_id)',
        'ask_chats.user_id -> users': 'select count(*) from ask_chats c where not exists(select 1 from users u where u.id=c.user_id)',
        'diagnostic_jobs.user_id -> users': 'select count(*) from diagnostic_jobs j where not exists(select 1 from users u where u.id=j.user_id)',
    }
    for name, q in fk.items():
        src_t, src_c = name.split(' ->')[0].split('.')
        if src_t not in tables(out) or src_c not in cols(out, src_t):
            rep['checks'][f'reference {name}'] = dict(ok=True, detail='skipped: no such column in this schema')
            continue
        n = out.execute(q).fetchone()[0]
        ok &= check(f'reference {name}', n == 0, n or None)
    rep['counts'] = {t: out.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables(out)}
    rep['live_sha256_after'] = sha(a.live)
    ok &= check('live DB file unchanged', rep['live_sha256_after'] == rep['live_sha256_before'])
    # R2 plan: library files the new DB points at that the live library never had (they must be uploaded before go-live)
    if a.r2_plan:
        live_keys = {r[0] for r in live.execute('select file_path from documents')}
        src = {int(k): v for k, v in json.load(open(a.sources)).items()} if a.sources else {}
        rows = []
        for i, fp, s in out.execute('select id, file_path, content_sha256 from documents order by id'):
            if fp not in live_keys:
                rows.append(dict(document_id=i, r2_key=fp, local_pdf=(src.get(i) or {}).get('src', ''), sha256=(src.get(i) or {}).get('sha') or s or ''))
        with open(a.r2_plan, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['document_id', 'r2_key', 'local_pdf', 'sha256']); w.writeheader(); w.writerows(rows)
        missing = [r['document_id'] for r in rows if not r['local_pdf'] or not os.path.exists(r['local_pdf'])]
        rep['r2_new_files'] = len(rows)
        ok &= check(f'R2 plan: {len(rows)} new library files, each has a local PDF', not missing, missing or None)
    rep['out_sha256'] = sha(a.out)
    print(json.dumps(rep['counts']), flush=True)
    return finish(0 if ok else 1)


if __name__ == '__main__':
    sys.exit(main())
