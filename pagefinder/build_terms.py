"""Generate the page-finder's word-form, compound-word and acronym tables FROM THE LIBRARY'S OWN PAGE TEXT.

    python -m pagefinder.build_terms [--index pagefinder/index/index.sqlite] [--out pagefinder/terms]

Writes three reviewable TSV files (one row per mapping, with the counts that justify it):
  word_forms.tsv  cooling -> cool, wired -> wire, ignition -> ignite, calibration -> calibrate ...
                  A word ending in -ing / -ed / -ion / -ation maps to its base form only when that base form is itself
                  a word of the library (>= MIN_BASE pages-worth of uses) and a real English word (bay_words.txt, the
                  shop word list already in the repo). No -er / -or rule: heater/heat,
                  freezer/freeze and controller/control stay apart.
  compounds.tsv   touchscreen -> touch screen, touchpad -> touch pad, setpoint -> set point ...
                  Only when the library itself writes BOTH forms (the joined word, and the two words side by side in at least 5%
                  of the uses), and both halves are real words (bay_words.txt). Rules out line-break splits like 'bat tery'.
  acronyms.tsv    DSI = direct spark ignition, PCB = printed circuit board ...
                  Only acronyms the manuals define themselves ("Direct Spark Ignition (DSI)"), seen >= 2 times, with a
                  single meaning in the whole library, and not an ordinary word (e.g. NO, CAN, PIN are skipped).
Words listed under kind 'keep' in rv_term_families.tsv are never changed by these tables.
search.py reads the files at import; nothing here runs in the app. No network, no API calls."""
import argparse, collections, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from pagefinder import terms as T

MIN_BASE = 3        # a base form must be used at least this often in the library
MIN_COMPOUND = 2    # the joined word and the split pair must each appear at least this often
MIN_ACRONYM = 2
# prefixes and suffixes are not words of a compound: antifreeze is not 'anti freeze', tankless is not 'tank less'
PREFIX_HALVES = set('anti sub pro inter multi pre non mis micro semi uni tri bi re de un super per over under counter'.split())
SUFFIX_HALVES = set('ing ed er less ful ness able ible ment wise ward'.split())
COMPOUND_SHARE = 0.05   # split pair seen at least 5% as often as the joined word


def library_words(db):
    raw = collections.Counter(); bigrams = collections.Counter(); acr = collections.defaultdict(collections.Counter)
    ex = {}
    for d, s, text in db.execute('select doc_id, pdf_sheet, text from pages'):
        t = re.sub(r'\s+', ' ', text or '')
        words = re.findall(r'[a-z]+', t.lower())
        raw.update(words)
        bigrams.update(zip(words, words[1:]))
        for m in re.finditer(r'((?:[A-Za-z][A-Za-z\-]*\s+){1,6})\(([A-Z][A-Z0-9/&]{1,6})\)', t):
            a = re.sub(r'[^A-Z]', '', m.group(2)); ws = m.group(1).split()[-len(a):]
            if len(a) >= 2 and len(ws) == len(a) and ''.join(w[0].upper() for w in ws) == a:
                k = ' '.join(ws).lower(); acr[a.lower()][k] += 1; ex.setdefault((a.lower(), k), f'{d} sheet {s}')
        for m in re.finditer(r'\b([A-Z][A-Z0-9]{1,6})\s*\(((?:[A-Za-z][A-Za-z\-]*\s*){2,6})\)', t):
            a = re.sub(r'[^A-Z]', '', m.group(1)); ws = m.group(2).split()
            if len(a) >= 2 and len(ws) == len(a) and ''.join(w[0].upper() for w in ws) == a:
                k = ' '.join(ws).lower(); acr[a.lower()][k] += 1; ex.setdefault((a.lower(), k), f'{d} sheet {s}')
    return raw, bigrams, acr, ex


def dictionary_words():
    p = os.path.join(os.path.dirname(HERE), 'bay_words.txt')
    return {w.strip().lower() for w in open(p, encoding='utf-8') if w.strip()}


def word_forms(raw, dict_words, keep):
    stemmed = collections.Counter()
    for w, n in raw.items(): stemmed[T.stem(w)] += n
    def ok(b): return len(b) >= 3 and b not in T.STOP and stemmed[b] >= MIN_BASE and b in dict_words
    def cvc(b): return len(b) >= 3 and b[-1] not in 'aeiouwxy' and b[-2] in 'aeiou' and b[-3] not in 'aeiou'
    out = []
    for w, n in sorted(stemmed.items()):
        if w in keep or len(w) < 5 or w in T.STOP: continue
        cands = []
        if w.endswith('ing'):
            b = w[:-3]; cands = [b, b + 'e'] + ([b[:-1]] if len(b) > 2 and b[-1] == b[-2] and b[-1] not in 'lsz' else [])
        elif w.endswith('ied'):
            cands = [w[:-3] + 'y']
        elif w.endswith('ed'):
            b = w[:-2]; cands = [b, b + 'e'] + ([b[:-1]] if len(b) > 2 and b[-1] == b[-2] and b[-1] not in 'lsz' else [])
        elif w.endswith('ation') and len(w) - 5 >= 5:
            cands = [w[:-3] + 'e', w[:-5]]
        elif w.endswith('ion') and len(w) - 3 >= 5:
            cands = [w[:-3], w[:-3] + 'e']
        cands = [c for c in cands if c != w and c not in keep and ok(c)]
        if not cands: continue
        # 'united' -> unite (not unit), 'rated' -> rate: after consonant-vowel-consonant the base keeps its final e
        b = next((c for c in cands if c.endswith('e') and cvc(c[:-1])), None) or max(cands, key=lambda c: (stemmed[c], c))
        out.append((w, b, n, stemmed[b]))
    return out


def compounds(raw, bigrams, keep, dict_words):
    out = []
    for w, n in sorted(raw.items()):
        if n < MIN_COMPOUND or len(w) < 7 or w in keep or w in T.STOP: continue
        best = None
        for i in range(3, len(w) - 2):
            a, b = w[:i], w[i:]
            if a in T.STOP or b in T.STOP or raw[a] < MIN_BASE or raw[b] < MIN_BASE: continue
            if a not in dict_words or b not in dict_words or a in PREFIX_HALVES or b in SUFFIX_HALVES: continue   # 'bat tery', 'con trol' are line breaks, not words
            c = bigrams[(a, b)]
            # the split spelling must be a real habit of the manuals, not a rare hyphenation ('volt age' 13 vs 7,633)
            if c >= MIN_COMPOUND and c >= COMPOUND_SHARE * n and (best is None or c > best[2]): best = (a, b, c)
        if best: out.append((w, f'{best[0]} {best[1]}', n, best[2]))
    return out


def acronyms(acr, ex, dict_words, raw):
    out = []
    for a, kinds in sorted(acr.items()):
        # one meaning only (plural spellings of the same words count as one meaning)
        means = collections.Counter()
        for k, n in kinds.items(): means[' '.join(T.stem(x) for x in k.split())] += n
        if len(means) != 1: continue
        k, n = kinds.most_common(1)[0]
        if sum(kinds.values()) < MIN_ACRONYM or a in dict_words or a in T.STOP or len(a) < 2: continue
        out.append((a, k, sum(kinds.values()), ex[(a, k)]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--index', default=os.path.join(HERE, 'index', 'index.sqlite'))
    ap.add_argument('--out', default=T.TERMS_DIR)
    a = ap.parse_args(argv)
    db = sqlite3.connect(f'file:{a.index}?mode=ro', uri=True)
    keep = T.keep_words()
    raw, bigrams, acr, ex = library_words(db)
    dw = dictionary_words()
    os.makedirs(a.out, exist_ok=True)
    head = '# GENERATED by pagefinder/build_terms.py from the library page text (do not hand-edit; add exceptions as kind "keep" in rv_term_families.tsv)\n'
    with open(os.path.join(a.out, 'word_forms.tsv'), 'w', encoding='utf-8') as f:
        f.write(head + '# word\tbase\tuses_of_word\tuses_of_base\n')
        rows = word_forms(raw, dw, keep)
        for r in rows: f.write('\t'.join(map(str, r)) + '\n')
    print('word_forms', len(rows))
    with open(os.path.join(a.out, 'compounds.tsv'), 'w', encoding='utf-8') as f:
        f.write(head + '# joined_word\tsplit_words\tuses_joined\tuses_split\n')
        rows = compounds(raw, bigrams, keep, dw)
        for r in rows: f.write('\t'.join(map(str, r)) + '\n')
    print('compounds', len(rows))
    with open(os.path.join(a.out, 'acronyms.tsv'), 'w', encoding='utf-8') as f:
        f.write(head + '# acronym\tmeaning\ttimes_defined\tfirst_seen\n')
        rows = acronyms(acr, ex, dw, raw)
        for r in rows: f.write('\t'.join(map(str, r)) + '\n')
    print('acronyms', len(rows))


if __name__ == '__main__':
    main()
