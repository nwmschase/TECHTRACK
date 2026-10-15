"""PF-06 rewrite pass: long manual / OCR / WARNING lines -> short imperative lines.

Deterministic and offline (same input, same output), so batch runs are
reproducible with no model call. Rules follow ASD-STE100 section 5: one
instruction per sentence, imperative not passive, a condition first then the
command, safety text kept as safety text.

Every rewrite passes ``fidelity_ok`` before use: each number, unit, ID, part
or model name, quoted text, parenthetical, warning word and content word of the
source must survive. On any loss (or any line still over the word target) the
original line comes back unchanged and the caller's old path runs.

An LLM rewriter could sit behind BAY_REWRITE_LLM later; it is not wired here,
so nothing in this module calls a model.
"""
from __future__ import annotations

import json
import os
import re

TARGET_WORDS = 12

# Function words a rewrite may remove (modal/passive/hedge glue, articles, OCR 'T o').
_DROPPABLE = {
    "a", "an", "the", "is", "are", "be", "been", "should", "it", "that", "to", "you", "make", "sure",
    "have", "has", "advisable", "will", "and", "of", "this", "by", "o", "t", "then", "kept",
}
_WARN_WORDS = ("warning", "caution", "danger", "note", "notice", "important", "safety", "not", "never", "do not", "only")
_VERBS = (
    "check|test|bench|measure|replace|repair|reset|confirm|seat|set|leave|turn|press|open|close|remove|install|"
    "clean|tighten|retest|go|stop|write|look|run|disconnect|reconnect|verify|inspect|plug|unplug|drain|fill|"
    "flush|move|record|ensure|return|proceed|apply|attach|connect|insert|lift|lower|pull|push|hold|use|keep|"
    "release|loosen|slide|secure|mount|wait|clear|operate|perform|engage|crank|start"
)
_PARTICIPLE = {
    "cleaned": "Clean", "checked": "Check", "replaced": "Replace", "inspected": "Inspect", "tightened": "Tighten",
    "removed": "Remove", "installed": "Install", "tested": "Test", "lubricated": "Lubricate", "drained": "Drain",
    "flushed": "Flush", "reset": "Reset", "adjusted": "Adjust", "secured": "Secure", "serviced": "Service",
}


def _words(text: str) -> list[str]:
    return [w for w in re.split(r"\s+", (text or "").strip()) if w]


def _norm(word: str) -> str:
    w = re.sub(r"[^a-z0-9#+/.\-]", "", word.lower()).strip(".-/")
    for suf in ("ing", "ed", "es", "s"):
        if len(w) > 4 and w.endswith(suf) and not re.search(r"\d", w):
            return w[: -len(suf)]
    return w


def _key_tokens(text: str) -> dict[str, set[str]]:
    t = text or ""
    return {
        "numbers": set(re.findall(r"[+\-]?\d+(?:[./\-]\d+)*\s*(?:%|°\s*[CF]|[a-zA-Z]{1,4}\b)?", t)),
        "ids": {w.strip(".,;:()") for w in _words(t) if re.search(r"\d", w) and re.search(r"[A-Za-z#]", w)},
        "caps": {w.strip(".,;:()\"'") for w in _words(t) if re.match(r"^[\"'(]?[A-Z]{2,}", w)},
        "quoted": set(re.findall(r"\"[^\"]+\"", t)),
        "paren": {re.sub(r"\s+", " ", p).strip().lower() for p in re.findall(r"\(([^)]*)\)", t)},
        "warn": {w for w in _WARN_WORDS if re.search(rf"\b{w}\b", t, re.I)},
        "content": {_norm(w) for w in _words(t) if _norm(w) and _norm(w) not in _DROPPABLE},
    }


def fidelity_ok(source: str, lines: list[str]) -> tuple[bool, str]:
    """True when every value, unit, ID, name, quote, warning and content word of source survives."""
    out = " ".join(lines)
    src, dst = _key_tokens(source), _key_tokens(out)
    low = out.lower()
    for n in src["numbers"]:
        if n.strip() not in out:
            return False, f"number/unit lost: {n.strip()}"
    for kind in ("ids", "caps", "quoted"):
        for tok in src[kind]:
            if tok and tok not in out:
                return False, f"{kind} lost: {tok}"
    for p in src["paren"]:
        if p and p not in low and not all(_norm(w) in dst["content"] or _norm(w) in _DROPPABLE for w in _words(p)):
            return False, f"parenthetical lost: {p}"
    for w in src["warn"]:
        if not re.search(rf"\b{w}\b", out, re.I):
            return False, f"warning word lost: {w}"
    missing = sorted(src["content"] - dst["content"])
    if missing:
        return False, "word lost: " + " ".join(missing)
    return True, ""


def _cap(s: str) -> str:
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s


def _sent(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip().rstrip(",;")
    if not s:
        return s
    if not re.search(r"[.!?:]$", s):
        s += "."
    return _cap(s)


def _rules_one(line: str) -> list[str]:
    s = re.sub(r"\s+", " ", line or "").strip()
    s = re.sub(r"^T o\b", "To", s)
    # Hedge lead-ins.
    s = re.sub(r"\bit is (?:advisable|recommended) to\s+", "", s, flags=re.I)
    s = re.sub(r"^Make sure you have (all .+?) included\b", r"Check that \1 are included", s, flags=re.I)
    # Passive modal -> imperative: '(To V) the X should be Ved R' -> 'V the X R'.
    m = re.match(r"^(?:To\s+\w+\s+)?(?:the\s+)?(.+?)\s+should be\s+(\w+)\b\s*(.*)$", s, re.I)
    if m and m.group(2).lower() in _PARTICIPLE:
        s = f"{_PARTICIPLE[m.group(2).lower()]} the {m.group(1)} {m.group(3)}".strip()
    # 'X will V if Y is kept Z' -> 'Keep the Y Z.' + 'The X will V.'
    m = re.match(r"^(.+?) will (.+?) if (.+?) is kept (.+?)\.?$", s, re.I)
    if m:
        return [_sent(f"Keep the {m.group(3)} {m.group(4)}"), _sent(f"If kept so, the {m.group(1).lower()} will {m.group(2)}")]
    # Boilerplate safety: 'X is a sign that Y has Z and may cause W if not performed P'.
    m = re.match(r"^(Safety\s+)?(.+?) is a sign that (?:an? )?(.+?) has (.+?) and may cause (.+?) if not performed (.+?)\.?$", s, re.I)
    if m:
        lead = "Safety: " if m.group(1) else ""
        return [
            _sent(f"{lead}{m.group(2)} is a sign of this risk"),
            _sent(f"This {m.group(3)} has {m.group(4)}"),
            *_perform_lines(m.group(5), m.group(6)),
        ]
    # Trailing parenthetical '(not ...)' -> its own sentence about the last named part.
    tail = []
    m = re.match(r"^(.+?\bthe ([a-z][\w\- ]{1,30}?))\s*\((not [^)]+)\)\.?$", s, re.I)
    if m:
        s, tail = m.group(1), [_sent(f"Note that the {m.group(2).split()[-1]} is {m.group(3)}")]
    out = []
    # Leading condition with a comma: 'If C, A1, A2, and A3' -> 'If C:' + actions.
    m = re.match(r"^((?:[A-Z]{2,}(?: [A-Z]{2,})*:?\s+)?(?:If|When|Before|After|Once)\b[^,]{3,}),\s+(.+)$", s)
    if m and len(_words(s)) > TARGET_WORDS:
        cond, rest = m.group(1), m.group(2)
        acts = re.split(rf",\s+(?:and\s+)?(?=(?:{_VERBS})\b)", rest, flags=re.I)
        if len(acts) == 1:
            acts = _split_and(acts[0])
            acts = [a.rstrip(".") for a in acts]
        if len(_words(cond)) <= TARGET_WORDS and (len(acts) == 1 or all(re.match(rf"(?:{_VERBS})\b", a, re.I) for a in acts)):
            # Keep a short condition on the first action when it fits.
            a0 = acts[0] if re.match(r"^[A-Z]{2,}", acts[0]) else acts[0][:1].lower() + acts[0][1:]
            first = f"{cond}, {a0}"
            if len(acts) == 1 or len(_words(first)) > TARGET_WORDS:
                out.append(_sent(cond).rstrip(".") + ":")
                out.extend(_sent(a) for a in acts)
            else:
                out.append(_sent(first))
                out.extend(_sent(a) for a in acts[1:])
            s = ""
    if s:
        # ', if ...' clause starts its own sentence.
        parts = re.split(r",\s+(?=if\b)", s, flags=re.I)
        for p in parts:
            out.extend(_split_and(p))
    return [x for x in (*out, *tail) if x]


def _perform_lines(harm: str, how: str) -> list[str]:
    how = how.strip().rstrip(".")
    first, _, more = how.partition(" and ")
    out = [_sent(f"It may cause {harm} if not performed {first}")]
    if more:
        out.append(_sent(f"Stay {more}" if not re.match(rf"(?:{_VERBS})\b", more, re.I) else more))
    return out


def _split_and(s: str) -> list[str]:
    s = s.strip().rstrip(".")
    if len(_words(s)) <= TARGET_WORDS:
        return [_sent(s)]
    # 'use the X to V R' -> 'use the X.' + 'V R.'
    m = re.match(r"^(.*\buse (?:the |a )?[\w\- ]{2,30}?) to ((?:%s)\b.+)$" % _VERBS, s, re.I)
    if m and len(_words(m.group(1))) >= 3:
        return [_sent(m.group(1)), *_split_and(m.group(2))]
    m = re.search(rf"\s+(?:and|or)\s+(?=(?:{_VERBS})\b)", s, re.I)
    if m and len(_words(s[: m.start()])) >= 3 and len(_words(s[m.end():])) >= 3:
        joiner = m.group(0).strip().lower()
        right = s[m.end():]
        right = f"or {right}" if joiner == "or" else right
        return [_sent(s[: m.start()]), *_split_and(right)]
    return [_sent(s)]


def _log(source: str, result: str, reason: str = "") -> None:
    path = os.environ.get("BAY_REWRITE_LOG")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"result": result, "reason": reason, "source": source}) + "\n")
    except OSError:
        pass


# General fix (a): scanned table rows and long prose. Every word is kept in order;
# only the line breaks (and a 'Read the table row:' lead for table rows) change.
_CODE_TOK = re.compile(r"^(?:[A-Z]{1,4}-?\d[\w/\-]*|\d+[A-Z][\w/\-]*|[A-Z]\d+[A-Z]?)$")
_VERBISH = re.compile(
    r"\b(?:is|are|was|were|be|will|can|could|should|must|may|does|do|did|has|have|"
    + _VERBS + r"|read|jumper|bypass|allow|attempt|undergo|preceded|wish|see|cause|light|run|heat|cool|blow|flash|display|show)\w*\b",
    re.I,
)
_TABLE_LEAD = "Read:"


def _is_table_line(s: str) -> bool:
    toks = _words(s)
    codes = sum(1 for t in toks if _CODE_TOK.match(t.strip(",.;:*")))
    caps = sum(1 for t in toks if re.match(r"^[A-Z][A-Za-z]*$", t))
    return codes >= 3 or (codes >= 2 and caps >= len(toks) * 0.5)


def _pack(pieces: list[str], limit: int) -> list[str]:
    out, cur = [], ""
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        cand = f"{cur} {p}".strip()
        if cur and len(_words(cand)) > limit:
            out.append(cur)
            cur = p
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def _table_rows(s: str) -> list[str]:
    toks = _words(s)
    rows, cur = [], []
    for t in toks:
        if _CODE_TOK.match(t.strip(",.;:*")) and cur and any(not _CODE_TOK.match(x.strip(",.;:*")) for x in cur):
            rows.append(" ".join(cur))
            cur = []
        cur.append(t)
    if cur:
        rows.append(" ".join(cur))
    limit = TARGET_WORDS - len(_words(_TABLE_LEAD))
    out = []
    for r in rows:
        for chunk in _pack(_words(r), limit):
            out.append(f"{_TABLE_LEAD} {chunk.rstrip('.;,')}.")
    return out


def _prose_chunks(s: str) -> list[str]:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+\*\s+", ". ", s)
    s = re.sub(r"\s+(?=(?:action|problem|step)\s+\d+\b)", ". ", s, flags=re.I)
    pieces = re.split(r"(?<=[.;])\s+", s)
    lines = []
    for p in pieces:
        if len(_words(p)) <= TARGET_WORDS:
            lines.append(p)
            continue
        sub = re.split(r"(?<=,)\s+|\s+(?=(?:so|that|which|so that|where|while|during|upon|into|before|after|until|unless)\b)", p)
        lines.extend(_pack(sub, TARGET_WORDS))
    return [_sent(x.rstrip(",;")) for x in lines if x.strip(" .,;")]


def chunk_long_line(src: str) -> list[str]:
    """General fix (a): table rows or prose clauses, every word kept, <=12 words a line."""
    out = []
    for seg in re.split(r"\s+\*\s+|(?<=[.;])\s+(?=[A-Z])", src):
        if not seg.strip():
            continue
        if len(_words(seg)) <= TARGET_WORDS:
            out.append(_sent(seg))
        else:
            out.extend(_table_rows(seg) if _is_table_line(seg) else _prose_chunks(seg))
    return out


def _same_words(src: str, out: list[str]) -> bool:
    a = [w.lower().strip(".,;:*\"'") for w in _words(src)]
    b = [w.lower().strip(".,;:*\"'") for w in _words(" ".join(out).replace(_TABLE_LEAD, " "))]
    return [w for w in a if w] == [w for w in b if w]


def _segment_ok(seg: str, out: list[str]) -> bool:
    if any(len(_words(x)) > TARGET_WORDS for x in out):
        return False
    if any(len(_words(x)) >= 4 and not _VERBISH.search(x) for x in out):
        return False
    # A condition never stands alone, cut from the command it governs.
    if len(out) > 1 and any(re.match(r"^(?:If|When|Unless|Until|Once)\b", x) and "," not in x for x in out):
        return False
    return _same_words(seg, out) and fidelity_ok(seg, out)[0]


def _chunk_or_none(src: str) -> list[str] | None:
    """Each segment (table row block or prose sentence) is chunked and gated on its own;
    a segment that fails stays exactly as written."""
    out, changed = [], False
    for seg in re.split(r"\s+\*\s+|(?<=[.;])\s+(?=[A-Z])", src):
        if not seg.strip():
            continue
        if len(_words(seg)) <= TARGET_WORDS:
            out.append(seg.strip())
            continue
        lines = _table_rows(seg) if _is_table_line(seg) else _prose_chunks(seg)
        if len(lines) > 1 and _segment_ok(seg, lines):
            out.extend(lines)
            changed = True
        else:
            out.append(seg.strip())
    if not changed or not fidelity_ok(src, out)[0]:
        return None
    return out


def rewrite_line(line: str) -> list[str]:
    """Short action lines for one long line, or [line] unchanged when the rewrite is not faithful."""
    src = (line or "").strip()
    if len(_words(src)) <= TARGET_WORDS:
        return [line]
    try:
        out = _rules_one(src)
    except re.error:
        out = []
    if not out or out == [_sent(src)] or any(len(_words(x)) > TARGET_WORDS for x in out):
        chunks = _chunk_or_none(src)
        if chunks:
            _log(src, "chunked")
            return chunks
        _log(src, "fallback" if out and out != [_sent(src)] else "nochange", "rules and chunker could not keep it faithful")
        return [line]
    ok, why = fidelity_ok(src, out)
    if not ok:
        _log(src, "fallback", why)
        return [line]
    _log(src, "rewritten")
    return out
