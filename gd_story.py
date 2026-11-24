"""Warranty / technician story for a Guided Diagnostics job.

Source of truth (Chase's decisions, not invented here):
- 10/23 story spec (primer "Grok's part in the job"): Grok writes the story itself from the whole chat; loose three C's
  (concern, cause, correction); ALL testing and every action described in full detail, in full professional sentences, so
  the work and the time on the job are justified; official sources cited by manual title or document number, unofficial
  sources left uncited while the steps they informed stay; one standard for warranty and customer work.
- 10/24 R5: no page numbers in the story.
- 11/4 Brinkley furnace story (approved format): Concern paragraph; Cause as a numbered diagnostic test log of every step
  in order with readings, results and what each ruled in or out; Manufacturer references; Correction (completed) in full
  sentences; optional Request.
- 11/24 (Chase, M1066): the complaint is the job's real complaint (never the photo note); a job not repaired gets the
  correction as a general recommendation ("Recommend replacing the evaporator fan assembly, then re-test ...");
  no OPEN tag; nothing invented; every reading the tech reported is carried into the story.

write_warranty_story(): a story Grok already wrote into the state block (repair verified) when it passes the check, else
Grok writes it with STORY_SYSTEM from the whole chat (checked by check_story; one retry naming what was missing), else
warranty_story(), the numbered narrative built from the tech's own messages. No regex here (core guard): plain string work.
"""
from __future__ import annotations

import json

PHOTO_NOTE = "The file did not count."
PHOTO_NOTE_LINE = "(The file did not count as a finding.)"
LABEL_LINE = "Label/photo shows:"
SECTIONS = ("CONCERN", "CAUSE", "REFERENCES", "CORRECTION", "REQUEST")
_HEAD_WORDS = (("CONCERN", "CONCERN"), ("COMPLAINT", "CONCERN"), ("CAUSE", "CAUSE"), ("DIAGNOSTIC TEST LOG", "CAUSE"),
               ("MANUFACTURER REFERENCE", "REFERENCES"), ("REFERENCES", "REFERENCES"), ("CORRECTION", "CORRECTION"),
               ("WORK PERFORMED", "CORRECTION"), ("REQUEST", "REQUEST"))
_UNITS = ("vdc", "vac", "v", "a", "amps", "amp", "°f", "f", "°c", "c", "ohms", "ohm", "kohm", "k", "psi", "hz", "w",
          "degrees", "degree", "deg", "%", "in", "wc")
_CAUSE_LABELS = ("cause confirmed", "confirmed cause", "root cause confirmed", "root cause", "cause")
_REC_LABELS = ("recommendation", "recommended repair", "recommended correction", "recommend")


# ---------------------------------------------------------------- reading the chat (plain string work)
def _clean_user(text: str) -> str:
    """The tech's words: the photo notes and the photo-reading line the app added are taken out."""
    keep = []
    for line in (text or "").replace("\r", "").split("\n"):
        s = line.strip()
        if s in (PHOTO_NOTE, PHOTO_NOTE_LINE) or s.startswith(LABEL_LINE):
            continue
        keep.append(line.rstrip())
    return "\n".join(keep).strip()


def _tech_msgs(history) -> list:
    return [t for t in (_clean_user(m.get("content")) for m in history or [] if m.get("role") == "user") if t]


def _gd_msgs(history) -> list:
    return [(m.get("content") or "").strip() for m in history or [] if m.get("role") == "assistant" and (m.get("content") or "").strip()]


def complaint_of(case: dict, history: list = None) -> str:
    """The job's complaint: the first thing the tech typed (photo notes removed), else the case's stored complaint."""
    first = next(((m.get("content") or "") for m in history or [] if m.get("role") == "user" and (m.get("content") or "").strip()), "")
    return _clean_user(first) or _clean_user((case or {}).get("complaint", "")) or ""


def repair_done(case: dict, history: list = None) -> bool:
    """Done when the record says so (Grok's state block repair.done); the chat is not guessed at."""
    return bool((((case or {}).get("state") or {}).get("repair") or {}).get("done"))


def _plain(line: str) -> str:
    return line.replace("**", "").replace("__", "").strip().lstrip("-*•#> ").strip()


def _labeled(text: str, labels) -> str:
    """The text after a labeled line such as '**Cause confirmed:** ...' (first match), else ''."""
    for raw in (text or "").split("\n"):
        t = _plain(raw)
        low = t.lower()
        for lab in labels:
            if low.startswith(lab):
                rest = t[len(lab):].lstrip()
                if rest.startswith(":"):
                    return rest[1:].strip()
            elif " " in lab or lab == "recommendation":      # a clear label can follow a sentence on the same line
                i = low.find(lab + ":")
                if i > 0 and low[i - 1] == " ":
                    return t[i + len(lab) + 1:].strip()
    return ""


def _drop_parens(s: str) -> str:
    out, depth = [], 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")" and depth:
            depth -= 1
        elif not depth:
            out.append(ch)
    return " ".join("".join(out).split()).replace(" .", ".").replace(" ,", ",")


def _sentences(text: str) -> list:
    """Split prose into sentences at '. ', '? ', '! ' (decimals such as 0.84 stay whole)."""
    out, cur = [], ""
    t = " ".join((text or "").split())
    for i, ch in enumerate(t):
        cur += ch
        if ch in ".?!" and (i + 1 == len(t) or t[i + 1] == " "):
            if cur.strip():
                out.append(cur.strip())
            cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def _period(s: str) -> str:
    s = (s or "").strip()
    return s if not s or s.endswith((".", "!", "?")) else s + "."


def _sentence(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    s = s[0].upper() + s[1:]
    return s if s.endswith((".", "!", "?")) else s + "."


def reply_findings(text: str) -> dict:
    """{'cause', 'recommendation'} from labeled lines in one Guided Diagnostics reply ('Cause confirmed: ...',
    'Recommendation: ...'), plus the reply's 'Once replaced, ...' verify sentence. Empty strings when absent."""
    cause = _labeled(text, _CAUSE_LABELS)
    rec = _labeled(text, _REC_LABELS)
    verify = ""
    for s in _sentences(" ".join(_plain(x) for x in (text or "").split("\n"))):
        low = s.lower()
        if low.startswith(("once replaced", "once repaired", "after replacement", "after the repair")):
            verify = s
            break
    return {"cause": cause, "recommendation": rec, "verify": verify}


def chat_findings(history) -> dict:
    """The latest confirmed cause / recommendation said in the chat (newest reply first); the tech's own
    'recommend a replacement of ...' words count for the recommendation when no reply labeled one."""
    out = {"cause": "", "recommendation": "", "verify": ""}
    for text in reversed(_gd_msgs(history)):
        f = reply_findings(text)
        for k in out:
            out[k] = out[k] or f[k]
    if not out["recommendation"]:
        for t in reversed(_tech_msgs(history)):
            low = t.lower()
            for lead in ("recommend a replacement of ", "recommend replacing ", "recommend replacement of "):
                i = low.find(lead)
                if i >= 0:
                    out["recommendation"] = "Replace " + _sentences(t[i + len(lead):])[0].rstrip(".")
                    break
            if out["recommendation"]:
                break
    return out


def record_reply_findings(case: dict, reply: str) -> dict:
    """App side, after a turn: when a reply confirms a cause or a recommendation that the state block did not carry, the
    job record gets it (state.cause when empty; state.recommendation, which later turns do not clear)."""
    if not case:
        return case
    st = case.setdefault("state", {})
    f = reply_findings(reply)
    if f["cause"] and not (st.get("cause") or "").strip():
        st["cause"] = f["cause"]
    rec = f["recommendation"] or (st.get("order_part") and f"Replace the {st['order_part']}") or ""
    if rec:
        st["recommendation"] = rec
    if f["verify"]:
        st["recommendation_verify"] = f["verify"]
    return case


def _recommendation(st: dict, found: dict) -> str:
    """Diagnosis-only correction, in general terms, from what was recommended in the chat / record."""
    raw = (st.get("recommendation") or found.get("recommendation") or "").strip()
    if not raw and (st.get("order_part") or "").strip():
        raw = "Replace the " + st["order_part"].strip()
    verify = (st.get("recommendation_verify") or found.get("verify") or "").strip()
    if raw:
        first = _sentences(_drop_parens(raw))[0].rstrip(".;: ")
        low = first.lower()
        if low.startswith("recommend"):
            rec = first
        elif low.startswith("replace "):
            rec = "Recommend replacing " + first[len("replace "):]
        elif low.startswith("repair "):
            rec = "Recommend repairing " + first[len("repair "):]
        else:
            rec = "Recommend " + first[0].lower() + first[1:]
        if verify:
            v = verify[0].lower() + verify[1:]
            for lead in ("once replaced, ", "once repaired, ", "after replacement, ", "after the repair, "):
                if v.startswith(lead):
                    v = v[len(lead):]
            return f"{rec}, then {v.rstrip('.')}."
        return f"{rec}, then re-test and verify proper operation."
    if (st.get("cause") or found.get("cause") or "").strip():
        return "Recommend repairing or replacing the failed component identified above, then re-test and verify proper operation."
    return "Recommend further diagnosis to confirm the cause before repair."


# ---------------------------------------------------------------- readings (for the check)
def readings(history) -> list:
    """Numbers the tech reported with a unit (13.34V, 6.81A, 48F, 7.28-12.50A ...), as the number strings."""
    out = []
    for t in _tech_msgs(history):
        low = t.lower()
        i, n = 0, len(low)
        while i < n:
            if low[i].isdigit() and (i == 0 or not (low[i - 1].isalnum() or low[i - 1] in "-/")):
                j = i
                while j < n and (low[j].isdigit() or (low[j] in ".-" and j + 1 < n and low[j + 1].isdigit())):
                    j += 1
                k = j + 1 if j < n and low[j] == " " else j
                unit = ""
                for u in _UNITS:
                    if low.startswith(u, k) and (k + len(u) >= n or not low[k + len(u)].isalpha()):
                        unit = u
                        break
                if unit:
                    for part in t[i:j].split("-"):
                        if part and part not in out:
                            out.append(part)
                i = j
            else:
                i += 1
    return out


def missing_readings(story: str, history) -> list:
    return [r for r in readings(history) if r not in (story or "")]


# ---------------------------------------------------------------- fallback narrative (no AI)
def _cause_steps(history) -> list:
    """Every test / action the tech reported, in order, as full sentences; bullet readings become one sentence each group."""
    steps = []
    users = [m for m in history or [] if m.get("role") == "user" and (m.get("content") or "").strip()]
    for m in users[1:]:                       # the first message is the complaint (CONCERN)
        t = _clean_user(m.get("content"))
        lines = [ln.rstrip() for ln in t.split("\n") if ln.strip()]
        prose, i = [], 0
        while i < len(lines):
            s = lines[i].strip()
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if s.endswith(":") and nxt.startswith(("* ", "- ", "• ")):
                label = s[:-1].strip()
                items, i = [], i + 1
                while i < len(lines) and lines[i].strip().startswith(("* ", "- ", "• ")):
                    item = lines[i].strip()[2:].strip().rstrip(".")
                    if ":" in item:
                        a, b = item.split(":", 1)
                        item = f"{a.strip()} {b.strip()}"
                    if len(item) > 1 and item[1].islower():
                        item = item[0].lower() + item[1:]
                    items.append(item)
                    i += 1
                if prose:
                    steps += [_sentence(x) for x in _sentences(" ".join(prose))]
                    prose = []
                steps.append(_sentence(f"Recorded the following readings ({label[0].lower() + label[1:]}): " + ", ".join(items)))
                continue
            if s:
                prose.append(s.lstrip("*-• ").strip())
            i += 1
        for x in _sentences(" ".join(prose)):
            x = x.strip()
            low = x.lower()
            if low.startswith("cause:"):
                x = x[6:].strip()
                low = x.lower()
            if low.startswith(("i ", "i'm ", "im ")):      # remarks to the assistant, not work performed
                continue
            if " you " in f" {low} ":                       # drop a clause spoken to the assistant ("everything you asked ...")
                x = ", ".join(c for c in x.rstrip(".").split(", ") if " you " not in f" {c.lower()} ")
            if x:
                steps.append(_sentence(x))
    return steps


def noted_findings(history) -> list:
    """Out-of-spec readings named in the replies ('... exceeds the manual limit ...'), kept as noted findings."""
    out = []
    for text in _gd_msgs(history):
        for x in [y for l in text.split("\n") for y in _sentences(_plain(l))]:
            low = x.lower()
            if ("exceeds" in low or "out of spec" in low or "outside the spec" in low) and x not in out:
                out.append(x)
    return out


def _doc_numbers(texts) -> list:
    """Document numbers such as CCD-0009616 named in the chat (letters, a dash, then mostly digits)."""
    out = []
    for t in texts:
        for tok in t.replace("(", " ").replace(")", " ").replace(",", " ").replace(";", " ").replace("/", " ").split():
            tok = tok.strip(".:*").upper()
            if "-" not in tok:
                continue
            a, _, b = tok.partition("-")
            if a.isalpha() and 2 <= len(a) <= 4 and sum(ch.isdigit() for ch in b) >= 5 and b[-1:].isdigit() and tok not in out:
                out.append(tok)
    return out


def warranty_story(case: dict, history: list = None, model_text: str = "", references=()) -> str:
    """The Brinkley-format story built from the tech's own messages and the record (used when Grok is not available or
    its text fails the check). Nothing is added that the chat or record does not hold."""
    case = case or {}
    st = case.get("state") or {}
    if (st.get("story") or "").strip():
        return st["story"].strip()          # the story Grok wrote itself at repair verified (10/23) beats a built one
    complaint = complaint_of(case, history)
    if not complaint and not st and not history:
        return "No session recorded."
    unit = (case.get("unit") or {}).get("model_text") or model_text or ""
    found = chat_findings(history)
    steps = _cause_steps(history)
    if not steps:
        for f in st.get("facts") or []:
            item, value = (f.get("item") or "").strip(), (f.get("value") or "").strip()
            if item or value:
                steps.append(f"Recorded {item}: {value}." if item and value else _sentence(item or value))
    cause = (st.get("cause") or "").strip() or found["cause"]
    out = []
    if unit:
        out += [f"UNIT: {unit}", ""]
    out += ["1. CONCERN", _period(complaint) if complaint else "Not recorded.", "",
            "2. CAUSE - DIAGNOSTIC TEST LOG", "Every test and action is listed in the order performed, as the technician reported it."]
    out += [f"{n}. {s}" for n, s in enumerate(steps, 1)] or ["1. No testing was recorded in this job."]
    for x in noted_findings(history):
        out.append(f"Noted finding: {_sentence(x)}")
    out += ["", "Confirmed cause: " + (_period(_drop_parens(cause) if found["cause"] == cause else cause) if cause
                                       else "Not confirmed during diagnosis.")]
    refs = [r for r in references if r] + [d for d in _doc_numbers(_gd_msgs(history)) if d not in references]
    if refs:
        out += ["", "3. MANUFACTURER REFERENCES"] + [f"- {r}" for r in refs]
    rep = st.get("repair") or {}
    out += ["", "4. CORRECTION" if refs else "3. CORRECTION"]
    if rep.get("done"):
        corr = _sentence(rep.get("what") or "Repair performed")
        out.append(corr + (" Repair verified working." if rep.get("verified") else " Recommend verifying proper operation."))
    else:
        out.append(_recommendation(st, found))
    return "\n".join(out)


# ---------------------------------------------------------------- Grok writes it
STORY_SYSTEM = """You write the technician / warranty story for an RV repair job from a Guided Diagnostics session. The shop sends it to the maker or the coach builder (Furrion, Dometic, Lippert, Brinkley and others) to justify the diagnosis and the time on the job, and the same story goes on customer-pay work. It reads like an experienced warranty technician wrote it: full professional sentences, past tense, shop language, plain text with no markdown.

The story follows the shop's approved format:

1. CONCERN
A short paragraph with the customer's complaint as the job started ("Customer states ..."), and the conditions or pattern the tech observed when verifying it.

2. CAUSE - DIAGNOSTIC TEST LOG
A numbered list of every test, inspection and action the tech reported, in the order performed. Each step says what was done, the readings and results exactly as the tech gave them (every voltage, amperage, temperature, resistance and pressure, with its units), and what the step ruled in or out. Disassembly and access work (removing the unit, panels, ducts, covers) is listed as its own step, because it is labor on the job. Steps the assistant only suggested belong here when the tech reported doing them. A reading out of the maker's specification that the tech chose not to pursue is listed as a noted finding, and is not the cause. After the list, a short paragraph names the confirmed cause and why the tests point to it.

3. MANUFACTURER REFERENCES
The official documents used in the job: library documents and the maker's own manuals and bulletins, named by title or document number, with no page numbers. Web pages, forum posts and other unofficial sources are left out of this list, and the steps they informed stay in the test log.

4. CORRECTION
When the job's repair status says the repair was performed: the repair and how it was verified, in full sentences (numbered when there were several actions). When it says the repair was not performed (diagnosis only): the recommended repair in general terms, starting with "Recommend", for example "Recommend replacing the evaporator fan assembly, then re-test airflow and compartment temperatures to verify repair." A secondary issue the tech left can be a separate recommendation.

5. REQUEST (optional)
One or two sentences asking for authorization of the repair and the diagnostic time, when that fits the job.

Everything in the story comes from the session: readings, part names, results and document names as they appear there. Part numbers, labor times and operation codes appear when the tech gave them. Words about the software (OPEN, state, session, assistant, GD, TechTrack) stay out of the story."""


def story_messages(case: dict, history: list = None, model_text: str = "", references=(), missing=()) -> list:
    case = case or {}
    st = case.get("state") or {}
    unit = (case.get("unit") or {}).get("model_text") or model_text or "not recorded"
    category = (case.get("unit") or {}).get("category") or ""
    lines = []
    for m in history or []:
        role, text = m.get("role"), (m.get("content") or "").strip()
        if role == "user":
            text = _clean_user(text)
            if text:
                lines.append("TECH: " + text)
        elif role == "assistant" and text:
            lines.append("ASSISTANT (suggestions and analysis; work counts as done when the tech reported it): " + text)
    keep = {k: st.get(k) for k in ("facts", "cause", "repair", "order_part", "recommendation") if st.get(k)}
    status = ("REPAIR STATUS: performed (the CORRECTION is the repair done and its verification)."
              if repair_done(case, history) else
              "REPAIR STATUS: not performed - diagnosis only (the CORRECTION is a general recommendation starting with \"Recommend\").")
    parts = [f"UNIT: {category + ' / ' if category else ''}{unit}",
             "CUSTOMER COMPLAINT (job start): " + (complaint_of(case, history) or "not recorded"),
             status,
             "READINGS THE TECH REPORTED (each one belongs in the test log): " + (", ".join(readings(history)) or "none"),
             "OFFICIAL DOCUMENTS CITED IN THE JOB: " + ("; ".join(r for r in references if r) or "see the session"),
             "CASE RECORD: " + json.dumps(keep, ensure_ascii=False),
             "SESSION:\n" + "\n\n".join(lines)]
    if missing:
        parts.append("The last draft left out these readings the tech reported: " + ", ".join(missing) + ". They go in the test log.")
    parts.append("Write the story now.")
    return [{"role": "system", "content": STORY_SYSTEM}, {"role": "user", "content": "\n\n".join(parts)}]


def _header(line: str):
    """(SECTION, rest of line) when the line opens a section, else None. A header is short and is in capitals,
    starts with '#', or ends its heading words with ':'."""
    raw = line.strip()
    if not raw:
        return None
    t = raw.lstrip("#*_ ").strip()
    k = 0
    while k < len(t) and t[k].isdigit():
        k += 1
    if 0 < k < 3 and k < len(t) and t[k] in ".)":
        t = t[k + 1:].strip()
    head, sep, rest = t.partition(":")
    head = head.strip(" *_")
    if not head or len(head) > 60:
        return None
    if not (raw.startswith("#") or sep or head == head.upper()):
        return None
    up = head.upper()
    for word, sec in _HEAD_WORDS:
        if up.startswith(word):
            return sec, rest.strip(" *_")
    return None


def parse_story(text: str) -> dict:
    sec, cur = {}, None
    for raw in (text or "").replace("\r", "").split("\n"):
        hd = _header(raw)
        if hd and hd[0] not in sec:
            cur = hd[0]
            sec[cur] = [hd[1]] if hd[1] else []
            continue
        if cur:
            sec[cur].append(raw.replace("**", "").rstrip())
    return {k: "\n".join(v).strip() for k, v in sec.items()}


def _numbered_lines(text: str) -> int:
    n = 0
    for ln in (text or "").split("\n"):
        s = ln.strip()
        k = 0
        while k < len(s) and s[k].isdigit():
            k += 1
        if k and k < len(s) and s[k] in ".)":
            n += 1
    return n


def _scrub(t: str) -> str:
    for tag in ("OPEN - ", "OPEN – ", "OPEN: "):
        t = t.replace(tag, "")
    for note in ("not yet performed", "not performed"):
        while True:
            i = t.lower().find(f"({note})")
            if i < 0:
                break
            t = t[:i].rstrip() + t[i + len(note) + 2:]
    return t.strip()


def _long_numbers(t: str, n: int = 6) -> list:
    out, run = [], ""
    for ch in t + " ":
        if ch.isdigit():
            run += ch
        else:
            if len(run) >= n:
                out.append(run)
            run = ""
    return out


def story_problems(text: str, case: dict, history: list = None) -> list:
    """What keeps a story from being used ([] = good): a missing concern / cause / correction, a cause that is not a
    numbered test log, a correction that is not a recommendation on a diagnosis-only job, a long number (part number)
    nowhere in the session, or a reading the tech reported that is not in the story."""
    sec = parse_story(text)
    probs = [f"no {s} section" for s in ("CONCERN", "CAUSE", "CORRECTION") if not sec.get(s)]
    if probs:
        return probs
    if _numbered_lines(sec["CAUSE"]) < 2:
        probs.append("cause is not a numbered test log")
    if not repair_done(case, history) and "recommend" not in sec["CORRECTION"].lower():
        probs.append("diagnosis-only correction is not a recommendation")
    source = json.dumps(case or {}, ensure_ascii=False) + " ".join(m.get("content") or "" for m in history or [])
    for num in _long_numbers(text):
        if num not in source:
            probs.append(f"number {num} is not in the session")
    miss = missing_readings(text, history)
    if miss:
        probs.append("missing readings: " + ", ".join(miss))
    return probs


def check_story(text: str, case: dict, history: list = None) -> str | None:
    """The story with any OPEN tag removed when it passes story_problems, else None."""
    if story_problems(text, case, history):
        return None
    return _scrub((text or "").replace("**", "").strip())


def write_warranty_story(case: dict, history: list = None, model_text: str = "", chat_fn=None, references=()) -> str:
    """The Write-warranty-story button. chat_fn(messages) -> text calls Grok; None = Grok not available."""
    case = case or {}
    st = case.get("state") or {}
    stored = (st.get("story") or "").strip()
    if stored and check_story(stored, case, history):
        return check_story(stored, case, history)
    if chat_fn is not None and (history or complaint_of(case, history)):
        missing = ()
        for _ in range(2):
            try:
                text = chat_fn(story_messages(case, history, model_text, references, missing)) or ""
            except Exception:
                break
            ok = check_story(text, case, history)
            if ok:
                return ok
            missing = tuple(missing_readings(text, history))
    return warranty_story(case, history, model_text, references)
