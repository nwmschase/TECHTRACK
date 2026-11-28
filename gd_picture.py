"""The one manual page to show when the tech asks for a picture (v4.20.6, Chase go pt1664u, test7b).

The page comes from the library pages opened this turn (Grok's reads, or the picture page the app opened when Grok opened
none): the page whose picture labels and text best match the tech's words, Grok's cited pages breaking ties. Exactly one
page; None when nothing was opened. v4.20.7: no page numbers are read out of the reply text any more.
"""
import re

MODULE_REVISION = "v4.20.7"
FAIL_NOTE = "That page didn't load; tap Open PDF."

# Words of the request itself ("can you send me a picture of the ..."): not what the picture is of.
_ASK_WORDS = set("""
a an the of for to me my i you your we us our it its this that these those is are be can could would will please pls
send show give get see look let need want like pic pics picture pictures photo photos image images diagram diagrams drawing
drawings figure figures fig schematic schematics view page pages manual manuals library lippert from on in at with and or
what where which how do does did any some have has here there again also just one two up if available style kind type
sort possible maybe
""".split())
_WORD = re.compile(r"[a-z0-9]+")
# v4.20.7: the one check for "the tech asked to see a picture" on the GD path (it replaced coach wants_library_page_shown
# and manual_figures.tech_asked_for_manual_figure there). Plain words, the tech's own message only.
_PICTURE_ASK = re.compile(
    r"\b(?:photos?|photographs?|pics?|pictures?|images?|diagrams?|drawings?|schematics?|figures?|fig\.?|illustrations?|"
    r"pinouts?|layout|labell?ed|labels|exploded view)\b"
    r"|\bshow me\b|\blooks? like\b|\bwhere (?:is|are)\b", re.I)


def is_picture_request(msg) -> bool:
    return bool(_PICTURE_ASK.search(msg or ""))
# The picture labels people wrote on library pages ("diagram / drawing / ...: <kind>", "photo / photograph / ... of the actual
# component"). The one list for "this page has a picture" (gd_turn page-image order, the app's picture page, the pick).
PICTURE_LABEL_MARKS = ("diagram / drawing", "photo / photograph", "wiring diagram", "schematic", "figure")


def has_picture_label(topics) -> bool:
    t = (topics or "").lower()
    return any(w in t for w in PICTURE_LABEL_MARKS)


def _stem(w):
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("es") and w[-3] in "sxz":
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def words(text):
    return {_stem(w) for w in _WORD.findall((text or "").lower())}


def subject_words(tech_msg):
    """What the tech wants a picture of: the message words minus the words of asking."""
    return {w for w in words(tech_msg) if w not in _ASK_WORDS and len(w) > 1}


def _get(p, name, default=""):
    return p.get(name, default) if isinstance(p, dict) else getattr(p, name, default)


def pick_picture_page(tech_msg, pages, cited=()):
    """The opened page (an item of pages) that best shows what the tech asked a picture of, or None.

    pages: this turn's opened library pages (gd_pages.Page or dicts with doc_id, page, sheet, title, topics, text).
    cited: Grok's cited [{doc_id, page}] this turn (state block; v4.20.7: no reading of page numbers out of the reply text)."""
    seen, cands = set(), []
    for p in pages or []:
        if _get(p, "source", "library") == "web":
            continue
        key = (str(_get(p, "doc_id")), str(_get(p, "sheet")))
        if key in seen:
            continue
        seen.add(key)
        cands.append(p)
    if not cands:
        return None
    subject = subject_words(tech_msg)
    cited_keys = {(str(c.get("doc_id")), str(c.get("page"))) for c in cited or [] if isinstance(c, dict)}
    best, best_score = None, None
    for i, p in enumerate(cands):
        page = str(_get(p, "page") or "")
        label_hit = len(subject & words(_get(p, "topics")))
        text_hit = len(subject & words(_get(p, "text")))
        is_cited = (str(_get(p, "doc_id")), page) in cited_keys
        has_picture = has_picture_label(_get(p, "topics"))
        # the page's picture labels first, then the page text, then Grok's cited list and a picture label at all
        score = (label_hit * 3 + text_hit + (2 if is_cited else 0) + (2 if has_picture else 0), text_hit, -i)
        if best_score is None or score > best_score:
            best, best_score = p, score
    return best
