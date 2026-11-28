"""RV shop vocabulary for the page-finder's word half (BM25). Same rules at index time and query time.

Two layers, both read from reviewable data files in pagefinder/terms/ (no word lists in code):
1. Normalisation (every page and every query, weight 1.0 = treated as the same word):
   - plural:     sensors -> sensor (the old rule)
   - word forms: cooling / cooled -> cool, wiring -> wire, ignition -> ignite   (word_forms.tsv, generated)
   - compounds:  touchscreen -> touch screen, touchpad -> touch pad              (compounds.tsv, generated)
   - same:       temp -> temperature, ignitor -> igniter, fridge -> refrigerator (rv_term_families.tsv kind 'same')
2. Term families (query side only, weight FAMILY_WEIGHT < 1, so a page with the tech's exact words still ranks first):
   - 'family' rows of rv_term_families.tsv: freeze sensor | evaporator sensor | coil sensor ..., touch screen | touch
     pad | touch panel ..., not cold | not cooling | too warm | insufficient cooling ... Members are phrases; a member
     matches the query when its words appear in order (up to MAX_GAP other words between them). Negation words
     (not, no, never, won't, doesn't ...) count as 'not', so 'will not blow cold' matches 'not cold'.
   - acronyms the manuals define themselves (acronyms.tsv, generated): DSI | direct spark ignition.
A family adds the OTHER members to the query (a phrase member counts only on pages that carry all its words).
Nothing is per case: one table, one weight."""
import collections, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
TERMS_DIR = os.environ.get('TT_PAGEFINDER_TERMS', os.path.join(HERE, 'terms'))
FAMILY_WEIGHT = 0.5   # a family word counts half of the tech's own word
MAX_GAP = 2           # words allowed between the words of a family phrase ('not ... cold'); never across , ; . ! ? :

STOP = set('''a about above after again against all am an and any are aren't as at be because been before being below between both but by
can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he her here hers herself him himself his how i if in into is isn't it it's its itself just let's me more most mustn't my
myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she should shouldn't so some such than
that that's the their theirs them themselves then there there's these they this those through to too under until up very was wasn't we
were weren't what when where which while who whom why will with won't would wouldn't you your yours yourself yourselves also get gets
got getting one ones s t d ll m re ve y won wont dont doesnt didnt isnt cant'''.split())
# words that negate what follows ("won't" is split by the tokenizer into "won" + "t")
NEG = set('not no never nor cannot won wont doesn doesnt don dont didn didnt isn isnt aren arent wasn wasnt weren werent unable without'.split())
TOKEN = re.compile(r"[a-z0-9]+")


def stem(w):
    if len(w) > 3 and w.endswith('ies'): return w[:-3] + 'y'
    if len(w) > 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')): return w[:-1]
    return w


def _rows(name):
    p = os.path.join(TERMS_DIR, name)
    if not os.path.exists(p): return []
    out = []
    for line in open(p, encoding='utf-8'):
        if not line.strip() or line.lstrip().startswith('#'): continue
        out.append([c.strip() for c in line.rstrip('\n').split('\t')])
    return out


def keep_words():
    """Words that the generated tables must never change (kind 'keep' in rv_term_families.tsv)."""
    return {w.strip().lower() for r in _rows('rv_term_families.tsv') if r[0] == 'keep' for w in r[1].split('|') if w.strip()}


class Vocab:
    def __init__(self):
        keep = keep_words()
        self.forms = {r[0]: r[1] for r in _rows('word_forms.tsv') if len(r) >= 2 and r[0] not in keep}
        self.compounds = {r[0]: r[1].split() for r in _rows('compounds.tsv') if len(r) >= 2 and r[0] not in keep}
        self.same = {}
        fams = []
        for r in _rows('rv_term_families.tsv'):
            if len(r) < 2: continue
            members = [m.strip().lower() for m in r[1].split('|') if m.strip()]
            if r[0] == 'same':
                for m in members[1:]: self.same[m] = members[0]
            elif r[0] == 'family':
                fams.append(members)
        for r in _rows('acronyms.tsv'):
            if len(r) >= 2: fams.append([r[0].lower(), r[1].lower()])
        self.families = []   # [(member sequences (match stream), expansion tokens per member)]
        for members in fams:
            seqs = [tuple(w for w in self.stream(m) if w != '|') for m in members]
            toks = [tuple(self.tokens(m)) for m in members]
            seqs_toks = [(s, t) for s, t in zip(seqs, toks) if s and t]
            if len(seqs_toks) >= 2: self.families.append(seqs_toks)
        self.by_first = collections.defaultdict(list)   # first word of a member -> families (fast match)
        for i, fam in enumerate(self.families):
            for s, _ in fam: self.by_first[s[0]].append(i)

    def word(self, w):
        """one raw lowercase word -> normalised token(s)"""
        w = self.same.get(w, w)
        parts = self.compounds.get(w) or self.compounds.get(stem(w)) or [w]
        out = []
        for p in parts:
            p = self.same.get(p, p)
            s = stem(p)
            s = self.forms.get(s, s)
            out.append(self.same.get(s, s))
        return out

    def tokens(self, text):
        return [t for w in TOKEN.findall((text or '').lower()) if w not in STOP for t in self.word(w)]

    def stream(self, text):
        """all words in order (stop words kept, negations -> 'not'), for family phrase matching. A clause break
        (, ; . ! ? :) is kept as '|' so a phrase never spans two clauses ('not getting cold; freezer operating')."""
        out = []
        for clause in re.split(r'[,;.!?:\n]+', (text or '').lower()):
            for w in TOKEN.findall(clause):
                if w in NEG: out.append('not')
                elif w in STOP: out.append(w)
                else: out.extend(self.word(w))
            out.append('|')
        return out

    def query_terms(self, text, extra=()):
        """{token or (token, token, ...): weight}: the query's own words 1.0; matched family members FAMILY_WEIGHT
        (a phrase member is a tuple of its words: it scores only on pages that carry all of them)."""
        q = {}
        for t in list(self.tokens(text)) + list(extra): q[t] = 1.0
        s = self.stream(text)
        pos = collections.defaultdict(list)
        for i, w in enumerate(s): pos[w].append(i)
        seen = set()
        for w in set(s) - {'|'}:
            for fi in self.by_first.get(w, ()):
                if fi in seen: continue
                fam = self.families[fi]
                hit = [j for j, (seq, _) in enumerate(fam) if _matches(seq, pos)]
                if not hit: continue
                seen.add(fi)
                for j, (_, toks) in enumerate(fam):
                    if j in hit: continue
                    # a one-word member adds that word; a phrase member adds its words as ONE unit that counts only on
                    # pages carrying all of them ('freeze sensor' needs freeze AND sensor), so 'circuit' alone never scores
                    key = toks[0] if len(set(toks)) == 1 else tuple(sorted(set(toks)))
                    if isinstance(key, tuple) and all(q.get(t) == 1.0 for t in key): continue
                    if q.get(key, 0) < FAMILY_WEIGHT: q[key] = FAMILY_WEIGHT
        return q


def _matches(seq, pos):
    """seq's words appear in order in the stream, at most MAX_GAP words apart"""
    breaks = pos.get('|', ())
    for start in pos.get(seq[0], ()):
        i, ok = start, True
        for w in seq[1:]:
            nxt = next((p for p in pos.get(w, ()) if i < p <= i + MAX_GAP + 1 and not any(i < b < p for b in breaks)), None)
            if nxt is None: ok = False; break
            i = nxt
        if ok: return True
    return False


_V = None
def vocab():
    global _V
    if _V is None: _V = Vocab()
    return _V

