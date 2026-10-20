"""Page text and page tags for the page-finder index (no network, no API).
Extracted from the fresh-library build (library/build/02_pages.py, 03_build_db.py, taxonomy.DOC_TYPES) so the app can
build and extend its own index from the app library. Document KIND (manual / tech sheet / troubleshooting ...) is read from
the title; brand and category are NOT guessed here: they come from the app library's own fields."""
import json, os, re, subprocess, tempfile, hashlib, collections
import pymupdf
pymupdf.TOOLS.mupdf_display_errors(False)

NUM = re.compile(r'^(?:page|pg\.?|p\.)?\s*[-–(]?\s*(\d{1,3})\s*[-–)]?(?:\s*(?:of|/)\s*\d{1,3})?$', re.I)
SECNUM = re.compile(r'^(\d{1,2})\s*[-–.]\s*(\d{1,3})$')   # "3-12" section-page style: recorded, not used for offset

def hf_candidates(lines_top, lines_bot):
    out = []
    for zone, lines in (('top', lines_top), ('bot', lines_bot)):
        for ln in lines:
            ln = ln.strip()
            m = NUM.match(ln)
            if m and 0 < int(m.group(1)) < 1000: out.append([zone, int(m.group(1))])
            else:
                # trailing / leading number in a footer line like "Rev B 05/2021   23" or "23  Girard ..."
                m2 = re.search(r'(?:^|\s{2,}|\|\s*)(\d{1,3})$', ln) or re.match(r'^(\d{1,3})(?:\s{2,}|\s*\|)', ln)
                if m2 and 0 < int(m2.group(1)) < 1000 and not re.search(r'\d{1,2}/\d{1,2}/?$', ln[:m2.start(1)] if m2 else ''):
                    out.append([zone + '-line', int(m2.group(1))])
    return out

def ocr_page(path, i):
    d = pymupdf.open(path); pg = d[i]
    long_in = max(pg.rect.width, pg.rect.height) / 72.0
    dpi = int(min(300, 3600 / max(long_in, 1)))  # cap the image at ~3600 px on the long side (big sheets time out)
    pix = pg.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    with tempfile.TemporaryDirectory() as td:
        img = f'{td}/p.png'; pix.save(img)
        r = subprocess.run(['tesseract', img, 'stdout', '--psm', '3', '-l', 'eng'], capture_output=True, text=True, timeout=900)
    return r.stdout

def do_pdf_path(doc_id, path):

    out = []
    try: d = pymupdf.open(path)
    except Exception as e: return [dict(doc_id=doc_id, sheet=0, error=str(e))]
    for i, pg in enumerate(d):
        h = pg.rect.height or 792
        words = pg.get_text('words')  # x0,y0,x1,y1,word,block,line,wno
        text = pg.get_text()
        method = 'text'
        lines = {}
        for w in words:
            lines.setdefault((w[5], w[6]), []).append(w)
        top, bot = [], []
        for ws in lines.values():
            y0 = min(w[1] for w in ws); y1 = max(w[3] for w in ws)
            s = '   '.join(w[4] for w in sorted(ws, key=lambda w: w[0]))
            if y1 < 0.10 * h: top.append(s)
            elif y0 > 0.90 * h: bot.append(s)
        if len(text.strip()) < 20:
            ocr = ocr_page(path, i).strip()
            if ocr:
                text, method = ocr, 'ocr'
                ls = [l for l in text.splitlines() if l.strip()]
                top, bot = ls[:2], ls[-2:]
            else:
                method = 'blank'
        out.append(dict(doc_id=doc_id, sheet=i + 1, text=text, method=method, hf=hf_candidates(top, bot),
                        n_images=len(pg.get_images()), n_drawings=len(pg.get_drawings()) if len(text) < 4000 else -1,
                        width=pg.rect.width, height=h))
    return out

def merge_chunks(chunks):
    txt = ''
    for ch in chunks:
        k = 0
        for n in range(min(250, len(ch), len(txt)), 15, -1):
            if txt.endswith(ch[:n]): k = n; break
        txt += ('' if k or not txt else '\n') + ch[k:]
    return txt

DOC_TYPES = [
    ('warranty-form',   [r'warranty\s*(?:request|diagnostic)?\s*form', r'diagnostic\s*form', r'check\s*(?:sheet|list)', r'performance\s*check', r'diag\s*sheet']),
    ('recall-bulletin', [r'recall', r'bulletin', r'\bTSB\b', r'service\s*campaign']),
    ('troubleshooting', [r'troubleshoot', r'diagnos', r'error\s*code', r'fault\s*code', r'service\s*hints']),
    ('service-manual',  [r'service', r'repair', r'training', r'technical\s*manual']),
    ('tech-sheet',      [r'\bTI\s*-?\s*\d', r'\bT\.?I\.?P\b', r'\bQR\s*-?\s*\d', r'tip\s*sheet', r'quick\s*ref', r'procedure', r'replacement', r'\bhow\s*to', r'instructions\b(?!\s*manual)']),
    ('parts-list',      [r'parts?\s*(?:list|breakdown|catalog|identification|manual)', r'part-?id', r'exploded']),
    ('wiring-diagram',  [r'wiring\s*diagram', r'schematic', r'pin\s*map', r'diagram', r'cable\s*routing']),
    ('install-manual',  [r'install']),
    ('owners-manual',   [r'owner', r'operat', r'user\s*(?:manual|guide)', r'instruction\s*manual', r'\bmanual\b', r'guide']),
    ('reference',       [r'flat\s*rate', r'standard', r'spec', r'brochure', r'comparison', r'faq', r'chart']),
]

def hits(patterns, text):
    pos = [m.start() for p in patterns for m in [re.search(p, text, re.I)] if m]
    return min(pos) if pos else None

def infer_doctype(title, fn):
    tf = f'{title} || {fn}'
    for d, pats in DOC_TYPES:
        if hits(pats, tf) is not None: return d
    return 'other'

MODEL = re.compile(r'(?<![A-Za-z0-9])([A-Z]{1,6}[- ]?\d{1,5}(?:[A-Z0-9]*(?:-[A-Z0-9]+)*)|\d{3,5}[A-Z]{1,4}\d*[A-Z0-9-]*)(?![A-Za-z0-9])')
NOT_MODEL = re.compile(r'^(CCD|TI|QR|S|REV|R|PG|P|PN|NO|FIG|FORM|ITEM|STEP|PAGE|SEC|LCI|TSB|RV|AC|DC|VAC|VDC|V|A|AMP|BTU|HZ|LB|LBS|MM|IN|FT|PSI|OZ|W|KW|WO|USB|ISO|UL|CSA|SAE|ANSI|NFPA|SKU|ID|EN|FR|ES|AWG|GA|Q|M|X|T|NC|NO|IP|CAN|LED|LCD|E|ER|F|H|L)$', re.I)
def norm_model(m): return re.sub(r'[^A-Z0-9]', '', m.upper())
STATES = set('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
WORDS = re.compile(r'^(THE|FOR|AND|TO|OF|ON|AT|BY|OR|IS|IT|AS|BE|IF|NO|UP|ALL|WITH|FROM|INTO|MOVE|BOTTOM|ROOM|USING|WITHIN|BEFORE|AFTER|FREEZE|VALVE|SERIES|SERIE|RIES|RIE|STEP|PAGE|PART|TYPE|MODEL|SIZE|JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|ARCTIC|ELITE|MACH|LB|LBS)$', re.I)
def models_from(text, title=False):
    out = []
    for m in MODEL.findall(text):
        m = m.strip(' -')
        if ' ' in m:
            pre, num = m.split(' ', 1)
            if not title or WORDS.match(pre) or pre.upper() in STATES or len(pre) > 3: continue
        pre = re.match(r'[A-Z]+', m)
        if pre and NOT_MODEL.match(pre.group(0)) and len(norm_model(m)) <= len(pre.group(0)) + 4: continue
        if re.fullmatch(r'\d+[A-Z]{1,3}', m) and re.search(r'(V|A|K|W|MM|IN|FT|LB|GPM|PSI|HZ|VA|AH|MAH|CC|OZ)$', m): continue  # 12V, 30A, 13K
        if re.fullmatch(r'R\d{2,3}[A-Z]?', m): continue  # refrigerants
        if re.match(r'(CCD|TI|QR|TSB|FORM|REV|PG|PTS|INS|ART|WO|SN|LOT)\b', m, re.I) or re.match(r'82-[SL]', m): continue
        if len(norm_model(m)) < 3 or not re.search(r'\d', m) or not re.search(r'[A-Z]', m): continue
        out.append(m)
    if title:  # bare part numbers in a title (e.g. 803280, 3311071) are model/part identifiers
        out += [n for n in re.findall(r'(?<![\d.-])(\d{6,10})(?![\d.])', text) if not re.fullmatch(r'20\d{6}', n)]
        out += re.findall(r'(?<![\d.-])(\d{4,5})\s*series', text, re.I) + re.findall(r'(?<![\d.-])(\d{4}-\d{3,4})(?![\d.])', text)
    return out

# ---------- printed page numbers ----------
def page_numbers(pgs):
    """Find the offset between PDF sheet and printed page from header/footer numbers.
    Returns {sheet: (printed, how)}, offset, confidence, note."""
    votes = collections.Counter(); per = {}
    for p in pgs:
        cands = [n for z, n in p.get('hf', []) if n <= p['sheet'] + 5]
        per[p['sheet']] = cands
        for n in set(cands): votes[p['sheet'] - n] += 1
    numbered = [p for p in pgs if p.get('method') != 'blank']
    if not votes or len(pgs) < 2:
        return {p['sheet']: (p['sheet'], 'assumed') for p in pgs}, 0, 'none', 'no page numbers found; printed page assumed = sheet'
    # up to two offsets (e.g. front matter, then body)
    top = votes.most_common(3)
    off, sup = top[0]
    n_det = sum(1 for s, c in per.items() if c)
    agree = sum(1 for s, c in per.items() if (s - off) in c)
    frac = agree / max(1, len(numbered))
    conf = 'high' if agree >= 3 and frac >= 0.5 else 'medium' if agree >= 2 and frac >= 0.25 else 'low'
    offsets = [o for o, v in top if v >= max(2, 0.15 * len(numbered))] or [off]
    res = {}
    det_sheets = sorted(s for s, c in per.items() if any((s - o) in c for o in offsets))
    for p in pgs:
        s = p['sheet']; c = per.get(s, [])
        hit = [o for o in offsets if (s - o) in c]
        if hit: res[s] = (s - hit[0], 'printed'); continue
        if conf == 'low': res[s] = (s - off if s - off >= 1 else None, 'guess'); continue
        # take the offset of the nearest sheet that has a detected number
        if det_sheets:
            near = min(det_sheets, key=lambda d: abs(d - s))
            o = next(o for o in offsets if (near - o) in per[near])
            res[s] = ((s - o) if s - o >= 1 else None, 'inferred')
        else: res[s] = (None, 'none')
    note = f'offset {off:+d} (sheet - printed) on {agree}/{len(numbered)} text pages'
    if len(offsets) > 1: note += f'; second offset {offsets[1]:+d} also seen'
    return res, off, conf, note

# ---------- special pages ----------
CODE = re.compile(r'(?<![A-Za-z0-9])((?:E|ER|Er|F|EE|P|LO|HI|DTC)\s?-?\s?\d{1,3})(?![0-9.,]|\s?(?:mm|in|ft|V|A)\b)')
def page_marks(p, n_pages):
    t = p['text']; tl = t.lower(); lines = [l.strip() for l in t.splitlines() if l.strip()]
    head = ' '.join(lines[:6]).lower()
    m = {}
    dot_lines = sum(1 for l in lines if re.search(r'(\.{4,}|…{2,}|\s\.\s\.\s\.)\s*\d{1,3}$', l))
    num_end = sum(1 for l in lines if re.search(r'[A-Za-z].{3,}\s{1,}\d{1,3}$', l))
    m['is_toc'] = int(bool(re.search(r'table of contents|\bcontents\b|\bindex\b', head) and (dot_lines >= 3 or num_end >= 6)) or dot_lines >= 8)
    m['is_cover'] = int(p['sheet'] == 1 and (len(t) < 900 or len(lines) < 18))
    sw = len(re.findall(r'\b(warning|caution|danger)\b', tl))
    m['is_safety'] = int(bool(re.search(r'safety (information|instructions|precautions|alert|warnings|guidelines)|important safety|for your safety|safety first|general safety', head)) or (sw >= 6 and sw * 40 > len(lines)))
    pn = len(re.findall(r'\b(?:\d{5,}|[A-Z]{1,3}-?\d{5,}[A-Z]?)\b', t))
    m['is_parts'] = int(bool(re.search(r'parts? list|replacement parts|parts breakdown|repair parts|parts catalog|exploded view|item\s+(?:no\.?|#)?\s*(?:part|description)', tl)) and pn >= 6 or pn >= 25 and 'part' in tl)
    codes = sorted({re.sub(r'[\s-]', '', c).upper() for c in CODE.findall(t)})
    codes = [c for c in codes if not re.fullmatch(r'P\d', c)]
    # blink / flash codes ("2 flashes: Fan Fault", "blinks 3 times") are indexed as FLASH<n>
    codes += sorted({f'FLASH{n}' for n in re.findall(r'(?<![\d.])(\d{1,2})\s*(?:flash|blink)(?:es|s)?\b', t, re.I)} |
                    {f'FLASH{n}' for n in re.findall(r'(?:flash|blink)(?:es|s)?\s+(\d{1,2})\s*times', t, re.I)})
    # a fault-code TABLE: many distinct codes, or a code-list heading with 3+ codes
    m['is_fault_codes'] = int(len(codes) >= 4 and bool(re.search(r'code|error|fault', tl)) or len(codes) >= 3 and bool(re.search(r'(error|fault|diagnostic|flash|blink|trouble|display)\s+codes?|codes?\s+(table|list|chart)', tl)))
    ts = len(re.findall(r'troubleshoot|symptom|possible cause|probable cause|\bremedy\b|corrective action|\bsolution\b|\bcause\b|check for|replace the|if (?:the|no|not)', tl))
    m['is_troubleshooting'] = int('troubleshoot' in head and ts >= 2 or ts >= 5)
    colors = len(re.findall(r'\b(BLK|RED|WHT|GRN|YEL|BLU|ORG|BRN|black|white|red|green|yellow|blue|orange|brown)\b', t))
    m['is_wiring'] = int(bool(re.search(r'wiring diagram|schematic|ladder diagram|wire diagram|pin ?out|pin map|wiring schematic', tl)) or colors >= 12 and len(t) < 3000)
    return m, codes

