"""The one manual page to show when the tech asks for a picture (v4.20.6, Chase go pt1664u, test7b).

Until v4.20.5 the picture step read page references out of the reply text in the old coach format ("📖 Source: TITLE -
page N") and found nothing in Grok's replies, so the tech got the old "could not load" note. Now the page comes from the
library pages Grok opened this turn: the page Grok names for that item in its reply (or lists in its cited pages) first,
then the page whose picture label or text best matches the tech's words. Exactly one page; None when nothing was opened.
"""
import re

MODULE_REVISION = "v4.20.6"
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
_PAGE_REF = re.compile(r"\b(?:page|pg|p)\.?\s*(\d{1,4})\b", re.I)
PICTURE_WORDS = ("diagram", "wiring", "figure", "fig", "photo", "drawing", "illustration", "schematic", "exploded", "view",
                 "layout", "connector", "location")


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


def _reply_scores(reply, subject):
    """{printed page label: (best number of subject words in a reply line that names that page, first line naming it)}."""
    out = {}
    for n_line, line in enumerate(re.split(r"[\n\r]+|(?<=[.!?])\s+(?=[A-Z])", reply or "")):
        refs = _PAGE_REF.findall(line)
        if not refs:
            continue
        hit = len(subject & words(line))
        for n in refs:
            best, first = out.get(n, (0, n_line))
            out[n] = (max(best, hit), min(first, n_line))
    return out


def pick_picture_page(tech_msg, reply, pages, cited=()):
    """The opened page (an item of pages) that best shows what the tech asked a picture of, or None.

    pages: this turn's opened library pages (gd_pages.Page or dicts with doc_id, page, sheet, title, topics, text).
    cited: Grok's cited [{doc_id, page}] this turn."""
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
    by_reply = _reply_scores(reply, subject)
    cited_keys = {(str(c.get("doc_id")), str(c.get("page"))) for c in cited or [] if isinstance(c, dict)}
    best, best_score = None, None
    for i, p in enumerate(cands):
        page = str(_get(p, "page") or "")
        named = page in by_reply
        reply_hit, first = by_reply.get(page, (0, 10 ** 6))
        label_hit = len(subject & words(_get(p, "topics")))
        text_hit = len(subject & words(_get(p, "text")))
        is_cited = (str(_get(p, "doc_id")), page) in cited_keys
        has_picture = any(w in (_get(p, "topics") or "").lower() for w in PICTURE_WORDS)
        # Grok naming the page for that item counts most, then the page's picture label, then Grok's cited list; the page
        # text and where Grok named it first break ties.
        score = (reply_hit * 4 + label_hit * 3 + (2 if named else 0) + (1 if is_cited else 0) + (1 if has_picture else 0),
                 text_hit, -first, -i)
        if best_score is None or score > best_score:
            best, best_score = p, score
    return best
