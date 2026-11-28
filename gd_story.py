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
- 11/25 (Chase): "A STORY IS A WELL WRITTEN CONCERN CAUSE AND CORRECTION ... NOT A ... BULLETPOINT LIST"; "REWRITE THE
  WORDS INTO THE BEST POSSIBLE STORY IT CAN"; reasonably inferred findings are fine. Supersedes the numbered test log:
  CONCERN / CAUSE / CORRECTION as paragraphs, references named inside the cause, for Grok and the fallback alike.
  Later 11/25: "It needs to be first person. its the technicians story not a narration by a third party."

write_warranty_story(): a story Grok already wrote into the state block (repair verified) when it passes the check, else
Grok writes it with STORY_SYSTEM from the whole chat (checked by check_story; one retry naming what was missing), else
warranty_story(), the three-paragraph story rewritten from the tech's own messages. No regex here (core guard): plain string work.
"""
from __future__ import annotations

import json
import os

PHOTO_NOTE = "The file did not count."
PHOTO_NOTE_LINE = "(The file did not count as a finding.)"
LABEL_LINE = "Label/photo shows:"
_HEAD_WORDS = (("CONCERN", "CONCERN"), ("COMPLAINT", "CONCERN"), ("CAUSE", "CAUSE"), ("DIAGNOSTIC TEST LOG", "CAUSE"),
               ("MANUFACTURER REFERENCE", "REFERENCES"), ("REFERENCES", "REFERENCES"), ("CORRECTION", "CORRECTION"),
               ("WORK PERFORMED", "CORRECTION"), ("REQUEST", "REQUEST"))
_UNITS = ("vdc", "vac", "µf", "μf", "uf", "mfd", "v", "a", "amps", "amp", "°f", "f", "°c", "c", "ohms", "ohm", "kohm", "k", "psi", "hz", "w",
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
        if low.startswith(("once replaced", "once repaired", "after replacement", "after the repair", "after installation",
                           "once installed")):
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
            for lead in ("once replaced, ", "once repaired, ", "after replacement, ", "after the repair, ", "after installation, ",
                         "once installed, "):
                if v.startswith(lead):
                    v = v[len(lead):]
            return f"{rec}, then {v.rstrip('.')}."
        return f"{rec}, then re-test and verify proper operation."
    if (st.get("cause") or found.get("cause") or "").strip():
        return "Recommend repairing or replacing the failed component identified above, then re-test and verify proper operation."
    return "Recommend further diagnosis to confirm the cause before repair."


# ---------------------------------------------------------------- the tech's own recommendation (11/24, WO 156231)
_REC_LEADS = ("recommend a replacement of ", "recommend replacement of ", "recommend replacing ", "recommend a new ",
              "recommend new ", "recommend to replace ", "recommend replace ", "recommend repairing ", "recommend repair of ",
              "recommend a repair of ", "recommend ")


def tech_recommendation(history) -> str:
    """The repair the tech said he recommends ('I will recommend a new thermostat'), newest first, as
    'Replace the thermostat' / 'Repair the ...' / the tech's words; '' when he did not state one. v4.20.9: only a plain
    statement in which the tech recommends counts; a question ('what do you recommend I check next?') never does."""
    for t in reversed(_tech_msgs(history)):
        for clause in reversed(_statements(t)):
            i = _rec_at(clause)
            if i < 0:
                continue
            tail = clause[i:]
            tl = tail.lower()
            for lead in _REC_LEADS:
                if tl.startswith(lead):
                    rest = _sentences(tail[len(lead):])[0].rstrip(".!?, ").strip() if tail[len(lead):].strip() else ""
                    for art in ("the ", "a new ", "a ", "an ", "new "):
                        if rest.lower().startswith(art):
                            rest = rest[len(art):]
                    if not rest:
                        break
                    if lead.startswith(("recommend repair", "recommend a repair")):
                        return "Repair the " + rest
                    if lead == "recommend " and not tl.startswith(("recommend the ", "recommend a ", "recommend an ")):
                        return rest[0].upper() + rest[1:]
                    return "Replace the " + rest
    return ""


def _rec_verb_and_part(rec: str):
    """('replacing', 'thermostat') from 'Replace the thermostat'."""
    low = (rec or "").strip().lower()
    for verb, ing in (("replace ", "replacing"), ("repair ", "repairing"), ("install ", "installing")):
        if low.startswith(verb):
            part = low[len(verb):].strip()
            if part.startswith("the "):
                part = part[4:]
            return ing, part
    return "", low


def record_tech_findings(case: dict, tech_msg: str) -> dict:
    """App side, after the tech sends: a recommendation he states goes into the job record (state.tech_recommendation)."""
    if not case:
        return case
    rec = tech_recommendation([{"role": "user", "content": tech_msg or ""}])
    if rec:
        case.setdefault("state", {})["tech_recommendation"] = rec
    return case


# ---------------------------------------------------------------- end-of-job access / teardown question (11/24, Chase)
# v4.20.9 (audit H2, Chase t1727u): the wrap-up starts only on a real end-of-job signal. In order:
#   1. the tech's close button (Diagnosis complete / Repair complete), passed in as close_action;
#   2. the job record from Grok's state block: repair.verified or closed (repair.done alone is NOT enough: Grok can call a
#      repair done before the tech verifies it);
#   3. the tech TYPING that the diag / repair is complete, or that he recommends a repair, as a plain statement.
# The old substring phrase lists (the done / repair phrase tuples: "working now" matched "not working now") and the
# any-"recommend" trigger ("what do you recommend I check next?") are deleted; questions and negated phrases never trigger.
WRAPUP_DIAG = "diag"
WRAPUP_REPAIR = "repair"
CLOSE_ACTIONS = (WRAPUP_DIAG, WRAPUP_REPAIR)
_CLOSE_DIAG = ("diagnostic complete", "diagnostics complete", "diagnosis complete", "diag complete", "diag is complete",
               "diagnosis is complete", "diagnostic is complete", "diag done", "diagnosis done", "done diagnosing")
_CLOSE_REPAIR = ("repair complete", "repair is complete", "repair done", "repair is done", "job complete", "job is complete",
                 "repair verified", "fixed and verified", "all fixed", "all working", "working now", "working as designed",
                 "operating as designed", "verified working", "verified operation")
_QUESTION_LEADS = ("what ", "what's ", "whats ", "how ", "why ", "where ", "which ", "when ", "who ", "do ", "does ", "did ",
                   "can ", "could ", "should ", "would ", "will ", "is ", "are ", "was ", "were ", "any ", "anything ")
_NEGATIONS = ("not", "no", "never", "isn't", "isnt", "wasn't", "wasnt", "aren't", "arent", "doesn't", "doesnt", "didn't",
              "didnt", "won't", "wont", "still", "nothing", "without", "if", "until", "once", "when", "before")
_REC_STATEMENT = ("recommend a replacement of ", "recommend replacement of ", "recommend replacing ", "recommend a new ",
                  "recommend new ", "recommend to replace ", "recommend replace ", "recommend repairing ", "recommend repair of ",
                  "recommend a repair of ")
_REC_SUBJECTS = ("", "i ", "we ", "i will ", "i'll ", "ill ", "i would ", "i'd ", "id ", "i want to ", "i wanna ", "we will ",
                 "i am going to ", "i'm going to ", "im going to ", "i do ", "so i ", "ok i ", "ok so i ", "then i ", "and i ",
                 "i'm gonna ", "im gonna ", "i am gonna ")


def _statements(text: str) -> list:
    """The tech's message as plain-statement clauses (original case); a sentence that is a question is dropped."""
    t = (text or "").replace("\n", ". ").replace("!", ". ").replace(";", ". ")
    parts, cur = [], ""
    for ch in t:
        cur += ch
        if ch in ".?":
            parts.append(cur)
            cur = ""
    if cur.strip():
        parts.append(cur)
    out = []
    for p in parts:
        p = p.strip()
        low = p.lower().rstrip(".").strip()
        if not low or p.endswith("?") or low.startswith(_QUESTION_LEADS):
            continue
        out += [c.strip(" .") for c in p.rstrip(".").replace(" then ", ", ").replace(" Then ", ", ").split(",") if c.strip(" .")]
    return out


def _says(clause: str, phrases) -> bool:
    """A phrase in the clause as whole words, with no negation or condition in the three words before it."""
    words = [w.strip(".,!:") for w in clause.lower().split()]
    for ph in phrases:
        pw = ph.split()
        for i in range(len(words) - len(pw) + 1):
            if words[i:i + len(pw)] == pw:
                if not any(w in _NEGATIONS or w.endswith("n't") for w in words[max(0, i - 3):i]):
                    return True
    return False


def _rec_at(clause: str) -> int:
    """Where 'recommend' starts in a clause in which the TECH is the one recommending ('I will recommend ...',
    'recommend replacing ...'), else -1."""
    low = clause.lower()
    i = low.find("recommend")
    if i < 0:
        return -1
    head = low[:i]
    if head in _REC_SUBJECTS or any(head.endswith(" " + x) for x in _REC_SUBJECTS if x):
        return i
    return -1


def _stated_recommendation(clauses) -> str:
    """The clause tail from 'recommend replacing / a new / a repair of ...' when the tech states a repair recommendation."""
    for c in clauses:
        i = _rec_at(c)
        if i < 0:
            continue
        tail = c[i:]
        for lead in _REC_STATEMENT:
            if tail.lower().startswith(lead) and tail[len(lead):].strip(" .,"):
                return tail
    return ""


def tech_close_statement(tech_msg: str) -> str:
    """'repair' / 'diag' when the tech's message STATES the repair or the diagnosis is complete, or states the repair he
    recommends ('I will recommend a new thermostat'); '' for a question ('what do you recommend I check next?'), a negated
    phrase ('the fan is not working now') or anything else."""
    clauses = _statements(tech_msg)
    if any(_says(c, _CLOSE_REPAIR) for c in clauses):
        return WRAPUP_REPAIR
    if any(_says(c, _CLOSE_DIAG) for c in clauses) or _stated_recommendation(clauses):
        return WRAPUP_DIAG
    return ""


ACCESS_ASK = ("Before I write the warranty story: what did you have to remove or move to get access (for example the fridge "
              "pulled out, battery box covers off, panels, ducts, counters, drawers)? And anything else that took extra time, "
              "or that the repair itself will need removed? Just list it out, a run-on sentence is fine. If nothing was "
              "removed, say \"nothing removed\".")


def access_question(kind: str) -> str:
    head = ("Got it, logging this as repair complete." if kind == WRAPUP_REPAIR
            else "Got it, logging this as diag complete for now.")
    return head + " " + ACCESS_ASK


REPAIR_SWITCH_LINE = ("Logged as repair complete (it was diag complete). The access question was already asked for this job, "
                      "so I am not asking it again.")


def repair_switch_due(case: dict, tech_msg: str = "", close_action: str = "") -> bool:
    """v4.20.13 (Chase t1741u, 2026-11-28): a job logged as diag complete (waiting on approval or a part) is switched to
    repair complete when the repair then really ends: the Repair complete button, Grok's state saying the repair was
    verified or the job closed, or the tech plainly stating it. Only diag -> repair; a repair complete record is never
    taken back to diag, and the access question is not asked a second time."""
    st = (case or {}).get("state") or {}
    if st.get("wrapup") != WRAPUP_DIAG:
        return False
    if close_action == WRAPUP_REPAIR:
        return True
    rep = st.get("repair") or {}
    if rep.get("verified") or st.get("closed"):
        return True
    return tech_close_statement(tech_msg) == WRAPUP_REPAIR


def wrapup_due(case: dict, tech_msg: str = "", close_action: str = "") -> str:
    """'repair' / 'diag' when the job really reached its end and the access question has not been asked, else ''.
    close_action is the tech's close button; the record counts when Grok's state block says the repair was verified or
    the job closed; the tech's message counts only as a plain statement (tech_close_statement)."""
    st = (case or {}).get("state") or {}
    if st.get("access_asked") or st.get("access_answer"):
        return ""
    if close_action in CLOSE_ACTIONS:
        return close_action
    rep = st.get("repair") or {}
    if rep.get("verified") or st.get("closed"):
        return WRAPUP_REPAIR
    return tech_close_statement(tech_msg)


def asked_access_last(history) -> bool:
    """The app's own access question is in the last GD reply of the chat (the app really asked it)."""
    for m in reversed(history or []):
        if (m.get("role") or "") == "assistant":
            return ACCESS_ASK in (m.get("content") or "")
    return False


_NOTHING = ("nothing", "nothing removed", "none", "nothing was removed", "didn't remove anything", "did not remove anything",
            "nothing to remove", "n/a")             # only an explicit none counts as none (GD-4: 'no i cited ...' is not)
_UNCLEAR = ("idk", "i don't know", "i dont know", "dunno", "not sure", "?", "huh", "what", "same", "see above", "yes", "no",
            "ok", "k")
_POINT_BACK = ("already", "cited", "told you", "i said", "said it", "said that", "mentioned", "above", "earlier", "in the chat",
               "like i said", "see chat", "same as before", "i listed", "listed it")
_ACCESS_WORDS = ("to gain access", "for access", "to get access", "to access", "removing", "removed", "remove ", "pulled",
                 "pulling", "took off", "taking off", "took out", "taking out", "dropped", "unscrewed", "opened up")
_GERUNDS = {"going": "went", "removing": "removed", "pulling": "pulled", "taking": "took", "dropping": "dropped",
            "opening": "opened", "moving": "moved", "lifting": "lifted", "disconnecting": "disconnected",
            "unscrewing": "unscrewed", "getting": "got", "accessing": "accessed"}
_ACCESS_LEADS = ("i am ", "i'm ", "im ", "i was ", "i had to ", "we had to ", "had to ", "i have ", "i ", "we ", "so ", "ok ",
                 "and ", "then ")
_NEED_MARKS = ("will need", "will have to", "would need", "would have to", "need to", "needs to", "needs ", "have to be",
               "has to be", "for the repair", "for repair", "to do the repair", "for replacement", "when replacing",
               "repair will", "replacement will", "required for")
_SPLITS = (";", ", and then ", ", then ", " and then ", " then ", ", plus ", " plus ", " also ", ", and ", " and ", ", ", "\n", ". ")
_FILLERS = ("for the repair ", "for repair ", "the repair will need ", "repair will need ", "it will need ", "they will need ",
            "we will need ", "will need to ", "will need ", "will have to ", "would need to ", "would need ", "would have to ",
            "need to ", "needs to ", "needs ", "i had to ", "we had to ", "had to ", "i have to ", "have to ", "i ", "we ",
            "they ", "then ", "also ", "so ", "and ", "plus ", "to be ", "be ", "to ")
_PAST = {"pull": "pulled", "take": "took", "remove": "removed", "move": "moved", "open": "opened", "drop": "dropped",
         "lift": "lifted", "disconnect": "disconnected", "unscrew": "unscrewed", "unbolt": "unbolted", "slide": "slid",
         "cut": "cut", "lower": "lowered", "raise": "raised", "unplug": "unplugged", "detach": "detached"}
_PAST_FORMS = set(_PAST.values()) | {"taken", "pulled", "removed"}
_TAIL_WORDS = (" removed", " pulled", " off", " out", " moved", " taken", " opened", " dropped", " lowered", " disconnected",
               " for access", " to access it", " all the way", " first")
_STATEMENT = (" is ", " are ", " was ", " were ", " seems ", " looks ")


def _split_items(text: str) -> list:
    t = " " + (text or "") + " "
    for joined in (" remove and reinstall ", " remove and replace ", " pull and reinstall ", " r&r ", " r and r "):
        t = t.replace(joined, " remove ").replace(joined.title(), " remove ")
    parts = [t]
    for sep in _SPLITS:
        nxt = []
        for p in parts:
            nxt += p.split(sep)
        parts = nxt
    return [p.strip(" .,;:-") for p in parts if p.strip(" .,;:-")]


def _strip_fillers(chunk: str) -> str:
    out = chunk.strip(" .,;:-")
    changed = True
    while changed:
        changed = False
        for f in _FILLERS:
            if out.lower().startswith(f):
                out = out[len(f):].strip(" .,;:-")
                changed = True
    return out


def _item_noun(item: str) -> str:
    """'Pulled the fridge out' -> 'fridge'; 'all the drawers removed to replace the floor' -> 'drawers'."""
    low = _strip_fillers(item)
    i = low.lower().find(" to ")
    if i > 0:
        low = low[:i]
    first = low.split(" ", 1)
    if first and (first[0].lower() in _PAST or first[0].lower() in _PAST_FORMS) and len(first) > 1:
        low = first[1]
        if low.lower().startswith(("off ", "out ")):
            low = low[4:]
    changed = True
    while changed:
        changed = False
        for t in _TAIL_WORDS:
            if low.lower().endswith(t):
                low = low[: -len(t)]
                changed = True
    for art in ("all of the ", "all the ", "the ", "a ", "an ", "all "):
        if low.lower().startswith(art):
            low = low[len(art):]
            break
    return low.strip(" .,")


def _done_step(chunk: str, last_verb: str) -> tuple:
    """An access step already done, in the past tense ('take the battery box covers off' -> 'Took the battery box covers
    off'). A bare item after one with a verb takes that verb ('removed 2 panels and the water heater door'). Statements
    ('the floor is rotted') are not access items. Returns (step or '', verb)."""
    c = _strip_fillers(chunk)
    if not c or any(w in " " + c.lower() + " " for w in _STATEMENT):
        return "", last_verb
    head, _, rest = c.partition(" ")
    h = head.lower()
    if h in _PAST:
        return (_PAST[h] + (" " + rest if rest else "")).capitalize(), _PAST[h]
    if h in _PAST_FORMS:
        return c[0].upper() + c[1:], h
    return ((last_verb or "removed") + " " + c).capitalize(), last_verb


def parse_access_answer(text: str) -> dict:
    """The tech's answer to the access question as {'done': [...], 'needed': [...], 'raw': text, 'nothing': bool}. 'done'
    is access work already done during the diagnosis (past-tense steps); 'needed' is what the recommended repair will need
    removed (item names). Once the tech's words turn to what the repair will need ('for the repair it will need the
    furnace pulled ...'), the items after that are 'needed'. Only the tech's own words; nothing is added."""
    raw = (text or "").strip()
    if raw.lower().strip(" .!") in _NOTHING:
        return {"done": [], "needed": [], "raw": raw, "nothing": True}
    done, needed, future, verb = [], [], False, ""
    for chunk in _split_items(raw):
        if any(m in " " + chunk.lower() + " " for m in _NEED_MARKS):
            future = True
        if future:
            noun = _item_noun(chunk)
            if noun and not any(w in " " + chunk.lower() + " " for w in _STATEMENT) and noun.lower() not in ("repair", "it", "them"):
                if noun.lower() not in [n.lower() for n in needed]:
                    needed.append(noun)
        else:
            step, verb = _done_step(chunk, verb)
            if step:
                done.append(step)
    return {"done": done, "needed": needed, "raw": raw, "nothing": False}


def _access_clause(part: str) -> str:
    """'ok ..., so to be clear, I am going to the control box cieling assembly and removing trim to gain access' ->
    'Went to the control box cieling assembly and removed trim to gain access.' (the tech's words, past tense)."""
    clauses = [c.strip() for c in part.split(", ") if c.strip()]
    first = next((k for k, c in enumerate(clauses) if any(w in " " + c.lower() + " " for w in _ACCESS_WORDS)), 0)
    out = ", ".join(clauses[first:]).strip(" .,;")
    changed = True
    while changed:
        changed = False
        for lead in _ACCESS_LEADS:
            if out.lower().startswith(lead):
                out = out[len(lead):].strip()
                changed = True
    words = [_GERUNDS.get(w.lower(), w) for w in out.split()]
    out = " ".join(words)
    return _sentence(out[0].upper() + out[1:]) if out else ""


def chat_access_steps(history, skip=()) -> list:
    """Access / removal work the tech described anywhere in his own chat messages (not the complaint, not questions, not
    the repair itself), each as a past-tense step in his words."""
    out = []
    for t in _tech_msgs(history)[1:]:
        if t.strip() in skip:
            continue
        for sent in _sentences(t):
            low = " " + sent.lower() + " "
            if sent.rstrip().endswith("?") or not any(w in low for w in _ACCESS_WORDS):
                continue
            if any(w in low for w in (" replac", "will need", "recommend", "need to")):     # the repair, not access work
                continue
            for part in sent.split(" then "):
                if any(w in " " + part.lower() + " " for w in _ACCESS_WORDS):
                    step = _access_clause(part)
                    if step and step not in out:
                        out.append(step)
                    break
    return out


def points_back(text: str) -> bool:
    """The access answer refers to what the tech already said in the chat ('no i cited what was removed already')."""
    low = " " + (text or "").lower() + " "
    return any(w in low for w in _POINT_BACK)


_ACCESS_PLAUSIBLE_UNCLEAR = ("idk", "i don't know", "i dont know", "dunno", "not sure", "same", "see above")


def answers_access(text: str, history=None) -> bool:
    """v4.20.9 (audit H2): the tech's message is taken as the access answer (no AI call) only when the app really asked
    the access question in the last GD reply AND the message plausibly answers it: an explicit none, a point back to the
    chat, removal / access wording, or a short list with no question in it. Anything else goes to Grok as usual."""
    if not asked_access_last(history):
        return False
    raw = (text or "").strip()
    low = raw.lower().strip(" .!")
    if not low or raw.endswith("?") or (low + " ").startswith(_QUESTION_LEADS):
        return False
    if low in _NOTHING or low in _ACCESS_PLAUSIBLE_UNCLEAR or points_back(raw):
        return True
    padded = " " + low + " "
    if any(w in padded for w in _ACCESS_WORDS) or any(f" {w} " in padded for w in list(_PAST) + list(_PAST_FORMS)):
        return True
    if any(f" {w} " in padded for w in ("off", "out", "panel", "panels", "cover", "covers", "drawer", "drawers", "door",
                                       "doors", "trim", "shroud", "duct", "ducts", "counter", "cabinet", "access")):
        return True
    return False


def record_access_answer(case: dict, text: str, history=None) -> dict:
    """The tech's access answer into the job record (state.access_answer / access_done / access_needed). Only an explicit
    none ('nothing removed', 'nothing', 'none') is none. An answer that points back to the chat ('I cited it already'),
    or one with no items in it, takes the access work from the tech's own earlier messages (state.access_from_chat)."""
    if case is None:
        return case
    st = case.setdefault("state", {})
    a = parse_access_answer(text)
    st["access_asked"] = True
    st["access_answer"] = a["raw"] or "nothing removed"
    done, needed, from_chat = a["done"], a["needed"], False
    unclear = a["raw"].lower().strip(" .!?") in _UNCLEAR
    if not a["nothing"] and (points_back(a["raw"]) or unclear or not (done or needed)):
        done, needed, from_chat = chat_access_steps(history, skip={a["raw"]}), [], True
    st["access_done"] = done
    st["access_needed"] = needed
    st["access_from_chat"] = from_chat
    return case


def access_logged_reply(case: dict) -> str:
    """What GD says after the tech answers the access question (no AI call)."""
    st = (case or {}).get("state") or {}
    done, needed = st.get("access_done") or [], st.get("access_needed") or []
    if st.get("access_from_chat"):
        if done:
            return ("Logged from what you told me earlier: " + " ".join(done)
                    + " Tap Write warranty story when you're ready.")
        return ("I couldn't find any removal work in the chat, so none is logged. If something came off, list it here; "
                "otherwise tap Write warranty story when you're ready.")
    if not (done or needed):
        return "Logged: nothing removed. Tap Write warranty story when you're ready."
    return "Logged. That goes into the warranty story. Tap Write warranty story when you're ready."


_STORY_MARKS = ("technician story", "warranty story", "tech story", "shop story")


def without_story_block(reply: str) -> str:
    """GD's reply with an in-chat technician story cut off (the story comes from the Write warranty story button, after
    the access question). The text before the story block (the confirmation) stays."""
    lines = (reply or "").split("\n")
    for i, ln in enumerate(lines):
        head = ln.strip().lstrip("#*_ ").rstrip("*_ :").strip().lower()
        if head in _STORY_MARKS or (head.startswith(_STORY_MARKS) and len(head) < 40 and ln.strip().startswith(("#", "*"))):
            return "\n".join(lines[:i]).rstrip()
    return (reply or "").rstrip()


def wrapup_reply(reply: str, kind: str) -> str:
    """At diag complete / repair complete: GD's confirmation, then the access question (an in-chat story is cut off)."""
    head = without_story_block(reply)
    return (head + "\n\n" if head.strip() else "") + access_question(kind)


# ---------------------------------------------------------------- where the test procedures came from (11/24, Chase)
_KEEP_CAPS = ("RV", "VDC", "VAC", "DC", "AC", "LP", "DSI", "GFCI", "OEM", "USB", "LED", "PCB", "BTU", "CO", "12V", "120V")


def _pretty_heading(line: str) -> str:
    words = []
    for w in line.split():
        words.append(w.capitalize() if (w.isupper() and w.isalpha() and len(w) > 2 and w not in _KEEP_CAPS) else w)
    return " ".join(words)


def page_heading(text: str) -> str:
    """The section / flowchart heading printed at the top of a manual page (the first capital-letter lines), as printed."""
    lines = [l.strip() for l in (text or "").replace("\r", "").split("\n") if l.strip()]
    out = []
    for l in lines[:8]:
        if l.isdigit() and not out:
            continue
        letters = [c for c in l if c.isalpha()]
        if not letters or len(l) > 80:
            break
        if sum(c.isupper() for c in letters) / len(letters) < 0.6 or l.endswith(":"):
            break
        out.append(_pretty_heading(l))
        if len(out) == 3:
            break
    return " - ".join(out)


def _page_numbers(seg: str) -> list:
    """Page numbers from words such as 'pages 26, 28, and 31', 'p.31', 'p.30–31', 'page 4'."""
    out = []
    t = seg.replace("–", "-").replace("—", "-")
    low = t.lower()
    i = 0
    while i < len(low):
        hit = None
        for w in ("pages ", "page ", "pp. ", "pp.", "p. ", "p."):
            if low.startswith(w, i) and (i == 0 or not low[i - 1].isalpha()):
                hit = w
                break
        if not hit:
            i += 1
            continue
        j = i + len(hit)
        while j < len(low) and (low[j].isdigit() or low[j] in " ,-&" or low.startswith("and ", j)):
            if low.startswith("and ", j):
                j += 4
                continue
            j += 1
        span = low[i + len(hit):j]
        for piece in span.replace("&", ",").replace(" and ", ",").split(","):
            piece = piece.strip()
            if "-" in piece:
                a, _, b = piece.partition("-")
                if a.strip().isdigit() and b.strip().isdigit() and 0 <= int(b) - int(a) <= 5:
                    out += [str(n) for n in range(int(a), int(b) + 1)]
                    continue
            if piece.isdigit():
                out.append(piece)
        i = j
    return out


def _library_ids(text: str) -> list:
    """Library doc ids such as L120 named in a line."""
    out = []
    for tok in text.replace("(", " ").replace(")", " ").replace(",", " ").replace("*", " ").split():
        tok = tok.strip(".:;")
        if len(tok) >= 2 and tok[0] == "L" and tok[1:].isdigit() and tok not in out:
            out.append(tok)
    return out


def source_mentions(history) -> list:
    """(doc_id, page) pairs from Guided Diagnostics' own 'Source:' lines and 'per L120 p.31' notes, in order."""
    out = []
    for text in _gd_msgs(history):
        for line in text.split("\n"):
            ids = _library_ids(line)
            if not ids:
                continue
            for pg in _page_numbers(line):
                pair = (ids[0], pg)
                if pair not in out:
                    out.append(pair)
    return out


def procedure_references(case: dict, history=None, cited=(), page_lookup=None) -> list:
    """Official documents the job's test steps came from, each as 'Title (doc number): section heading; ...', with no page
    numbers and no library ids. Pages are the ones Guided Diagnostics cited (state.cited, the app's cited log, its Source
    lines); the heading comes from the page's own text. page_lookup(doc_ref, page) -> {title, doc_number, text, source}
    reads a page the job did not keep. Web pages are not official and are left out."""
    case = case or {}
    read = case.get("read") or {}
    by_id, by_title = {}, {}
    for d in read.values():
        if (d.get("source") or "library") != "library":
            continue
        by_id[(str(d.get("doc_id")), str(d.get("page")))] = d
        by_title[((d.get("title") or "").strip().lower(), str(d.get("page")))] = d
    wanted = []
    for c in ((case.get("state") or {}).get("cited") or []):
        wanted.append((str(c.get("doc_id") or ""), "", str(c.get("page") or "")))
    for c in cited or []:
        wanted.append(("", (c.get("title") or "").strip(), str(c.get("page") or "")))
    for doc_id, pg in source_mentions(history):
        wanted.append((doc_id, "", pg))
    docs, order = {}, []
    for doc_id, title, pg in wanted:
        d = by_id.get((doc_id, pg)) if doc_id else by_title.get((title.lower(), pg))
        if d is None and page_lookup is not None:
            try:
                d = page_lookup(doc_id or title, pg)
            except Exception as e:
                import gd_errors
                gd_errors.fallback("story_references", "a cited page was not looked up for the story", exc=e,
                                   doc=str(doc_id or title), page=str(pg))
                d = None
        if not d or (d.get("source") or "library") != "library":
            continue
        name = (d.get("title") or title or "").strip()
        if not name or _library_ids(name) == [name]:
            continue
        if d.get("doc_number"):
            name = f"{name} ({d['doc_number']})"
        head = page_heading(d.get("text") or "")
        if name not in docs:
            docs[name] = []
            order.append(name)
        if head and head not in docs[name]:
            docs[name].append(head)
    return [f"{n}: {'; '.join(docs[n])}" if docs[n] else n for n in order]

# ---------------------------------------------------------------- readings (for the check)
def _reading_pairs(text: str) -> list:
    """(number, unit) for each number the tech gave with a unit in one text (13.34V, 6.81A, 0.000 to 0.048 VAC ...)."""
    out = []
    t = text or ""
    low = t.lower()
    i, n = 0, len(low)
    while i < n:
        if low[i].isdigit() and (i == 0 or not (low[i - 1].isalnum() or low[i - 1] in "-/")):
            j = i
            while j < n and (low[j].isdigit() or (low[j] in ".-" and j + 1 < n and low[j + 1].isdigit())):
                j += 1
            nums = t[i:j].split("-")
            if low.startswith(" to ", j) and j + 4 < n and low[j + 4].isdigit():     # a range: 0.000 to 0.048 VAC
                j2 = j + 4
                while j2 < n and (low[j2].isdigit() or (low[j2] == "." and j2 + 1 < n and low[j2 + 1].isdigit())):
                    j2 += 1
                nums, j = nums + [t[j + 4:j2]], j2
            k = j + 1 if j < n and low[j] == " " else j
            unit = ""
            for u in _UNITS:
                if low.startswith(u, k) and (k + len(u) >= n or not low[k + len(u)].isalpha()):
                    unit = u
                    break
            if unit:
                out += [(part, unit) for part in nums if part]
            i = j
        else:
            i += 1
    return out


def readings(history) -> list:
    """Numbers the tech reported with a unit (13.34V, 6.81A, 48F, 7.28-12.50A ...), as the number strings."""
    out = []
    for t in _tech_msgs(history):
        for part, _unit in _reading_pairs(t):
            if part not in out:
                out.append(part)
    return out


def missing_readings(story: str, history) -> list:
    return [r for r in readings(history) if r not in (story or "")]


# ---------------------------------------------------------------- fallback narrative (no AI)
_QUESTION_WORDS = ("where ", "what ", "how ", "why ", "which ", "do ", "does ", "can ", "could ", "should ", "is ", "are ",
                   "will ", "would ", "did ", "any ")
_WORK_WORDS = ("measur", "check", "test", "found", "read", "remov", "replac", "bypass", "jump", "verif", "confirm", "pull",
               "took", "install", "inspect", "observ", "disconnect", "access", "meter", "applied", "ran ", "voltage", "power",
               "plug", "tool", "draw", "spin", "shaft", "light", "kick", "commanding", "getting")


def _concern_line(complaint: str) -> str:
    """The complaint as the job started, as 'Customer states ...' (stray quote marks off)."""
    c = complaint.strip().strip('"“”').strip()
    if c and not c.lower().startswith(("customer", "cust ", "owner")):
        c = "Customer states the unit " + c[0].lower() + c[1:] if c.lower().startswith(("ran ", "runs ", "will ", "won't ",
                                                                                      "wont ", "does ", "doesn't ", "is ",
                                                                                      "has ", "makes ", "keeps ", "stopped "))\
            else "Customer states: " + c
    return _period(c.rstrip('"'))


def _before_question(clauses) -> list:
    out = []
    for c in clauses:
        if c.strip().lower().startswith(_QUESTION_WORDS):
            break
        out.append(c)
    return out


def _has_reading(text: str) -> bool:
    return bool(readings([{"role": "user", "content": text}]))


def _is_work(text: str) -> bool:
    """A sentence that reports work or a reading (not a remark): a reading with a unit, or a test / access verb."""
    low = text.lower()
    return _has_reading(text) or any(w in low for w in _WORK_WORDS)


# The fallback log is the tech's own words, tidied (11/25, GD-4 'clean it up'): his misspellings are matched against the
# words the session itself spells (the assistant's replies), missing apostrophes go back in, 'I measured' reads
# 'Measured'. Nothing is added: a word the session never spells is left as he typed it.
_CONTRACTIONS = {"doesnt": "doesn't", "dont": "don't", "didnt": "didn't", "isnt": "isn't", "wasnt": "wasn't",
                 "arent": "aren't", "werent": "weren't", "cant": "can't", "couldnt": "couldn't", "wouldnt": "wouldn't",
                 "shouldnt": "shouldn't", "thats": "that's", "theres": "there's", "hasnt": "hasn't", "havent": "haven't",
                 "ive": "I've", "im": "I'm"}
_ITS_NEXT = ("the", "a", "an", "not", "been", "going", "running", "working", "good", "bad", "fine", "called", "getting",
             "still", "just", "only", "probably", "definitely", "now")
_I_PAST = {"found", "took", "ran", "read", "saw", "got", "put", "set", "had", "did", "made", "went", "left", "heard", "felt",
           "kept", "held", "cut", "slid"}
_SUFFIXES = ("s", "es", "ed", "d", "ing", "er", "ers", "ly")
_PARTICIPLE = {"plug": "plugged", "connect": "connected", "hook": "hooked", "clip": "clipped", "attach": "attached",
               "insert": "inserted"}


def _tokens(text: str) -> list:
    """[(token, is_word)] covering the text: letter runs (with inner apostrophes) and everything between them."""
    out, cur, word = [], "", None
    t = text or ""
    for k, ch in enumerate(t):
        w = ch.isalpha() or (ch in "'’" and cur and word and k + 1 < len(t) and t[k + 1].isalpha())
        if word is None or w == word:
            cur += ch
        else:
            out.append((cur, word))
            cur = ch
        word = w
    if cur:
        out.append((cur, bool(word)))
    return out


def _session_vocab(texts) -> tuple:
    """Words as the session spells them: {lower: count}, {lower: proper form} for words only ever written capitalized
    mid-sentence (Peacemaker), and the two-word pairs used (fan motor)."""
    count, caps, lower_seen, pairs = {}, {}, set(), set()
    for text in texts:
        prev_word, prev_gap = "", "."
        for tok, is_word in _tokens(text):
            if not is_word:
                prev_gap = tok
                if tok.strip():
                    prev_word = ""
                continue
            low = tok.lower()
            count[low] = count.get(low, 0) + 1
            mid = not any(ch in prev_gap for ch in ".!?:\n*-#") and prev_word != ""
            if tok[0].isupper() and not tok.isupper() and mid:
                caps.setdefault(low, tok)
            elif tok[0].islower():
                lower_seen.add(low)
            if prev_word and prev_gap == " ":
                pairs.add(prev_word + " " + low)
            prev_word, prev_gap = low, ""
    return count, {k: v for k, v in caps.items() if k not in lower_seen}, pairs


def _distance(a: str, b: str) -> int:
    """Edits between two words (insert, delete, change, swap of two neighbours)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


_ENGLISH = None


def _english() -> set:
    """The English word list the page finder already uses (bay_words.txt); empty when the file is missing."""
    global _ENGLISH
    if _ENGLISH is None:
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bay_words.txt"), encoding="utf-8") as f:
                _ENGLISH = {w.strip().lower() for w in f if w.strip()}
        except OSError as e:
            import gd_errors
            gd_errors.fallback("story_words", "bay_words.txt not readable; story spelling check has no word list", exc=e)
            _ENGLISH = set()
    return _ENGLISH


def _session_spelling(low: str, vocab: tuple) -> str:
    """The session's spelling of a word the tech misspelled ('cieling' -> 'ceiling', 'fanmotor' -> 'fan motor'), else ''.
    A real English word is never changed, and nothing changes without the word list."""
    count, _caps, pairs = vocab
    words = _english()
    if len(low) < 5 or low in count or not words or low in words:
        return ""
    if any(low.endswith(x) and low[:-len(x)] in count for x in _SUFFIXES) or any(low + x in count for x in _SUFFIXES):
        return ""                                         # another form of a word the session uses: his word stands
    for k in range(3, len(low) - 2):
        if f"{low[:k]} {low[k:]}" in pairs:
            return f"{low[:k]} {low[k:]}"
    best, hits = 9, []
    for w in count:
        if w[0] != low[0] or w[-1] != low[-1] or abs(len(w) - len(low)) > 2 or len(w) < 4:
            continue
        dist = _distance(low, w)
        if dist < best:
            best, hits = dist, [w]
        elif dist == best:
            hits.append(w)
    return hits[0] if len(hits) == 1 and best <= (1 if len(low) < 6 else 2) else ""


def _tidy(text: str, vocab: tuple) -> str:
    """The tech's sentence with his spelling tidied against the session's words (see above)."""
    toks = _tokens(text)
    out = []
    for n, (tok, is_word) in enumerate(toks):
        if not is_word:
            out.append(tok)
            continue
        low = tok.lower()
        nxt = toks[n + 2][0].lower() if n + 2 < len(toks) and toks[n + 1][0] == " " else ""
        new = tok
        if low == "i":
            new = "I"
        elif low in _CONTRACTIONS:
            new = _CONTRACTIONS[low]
        elif low == "its" and nxt in _ITS_NEXT:
            new = "it's"
        elif tok.isupper() and len(tok) > 1:
            new = tok
        elif low in ("v", "vac", "vdc") and n and toks[n - 1][0].strip(" ")[-1:].isdigit():
            new = tok.upper()                                  # '12 v' -> '12 V' (a unit after a number)
        elif low in vocab[1] and tok.islower():
            new = vocab[1][low]
        else:
            fix = _session_spelling(low, vocab)
            if fix:
                new = vocab[1].get(fix, fix)
        if new != tok and tok[0].isupper() and not new[0].isupper():
            new = new[0].upper() + new[1:]
        out.append(new)
    t = "".join(out)
    words = t.split(" ", 2)
    if len(words) > 2 and words[0] == "I" and (words[1].lower().endswith("ed") or words[1].lower() in _I_PAST):
        t = words[1][0].upper() + words[1][1:] + " " + words[2]       # 'I measured 122 VAC input.' -> 'Measured ...'
    return t


def _setup_sentence(x: str) -> str:
    """'I have peacemaker tool its called that I can plug into the control board' (the tool he set up, said before the
    result) -> 'With the peacemaker tool plugged into the control board', else ''."""
    t = x.strip().rstrip(".").strip()
    low = t.lower()
    lead = next((ld for ld in ("i have ", "i've got ", "ive got ", "i got ") if low.startswith(ld)), "")
    if not lead or _has_reading(t):
        return ""
    rest, rl = t[len(lead):], low[len(lead):]
    sep = " that i can " if " that i can " in rl else (" i can " if " i can " in rl else "")
    if not sep:
        return ""
    k = rl.index(sep)
    obj, vp = rest[:k].strip(), rest[k + len(sep):].strip()
    for tail in (" its called", " it's called", " called"):
        if obj.lower().endswith(tail):
            obj = obj[:-len(tail)].strip(" ,")
    for art in ("a ", "an ", "the ", "my ", "this "):
        if obj.lower().startswith(art):
            obj = obj[len(art):]
    verb, _, more = vp.partition(" ")
    past = _PARTICIPLE.get(verb.lower()) or _PAST.get(verb.lower())
    return f"With the {obj} {past} {more}".strip() if obj and past else ""


def _join_setups(sentences: list) -> list:
    """A setup sentence and the result that follows it in the same message are one step."""
    out, i = [], 0
    while i < len(sentences):
        x = sentences[i]
        bare = x
        for lead in ("ok so ", "ok, ", "ok ", "so ", "and "):
            if bare.lower().startswith(lead):
                bare = bare[len(lead):].strip()
        pre = _setup_sentence(bare)
        if pre and i + 1 < len(sentences):
            nxt = sentences[i + 1].strip()
            for lead in ("ok so ", "ok, ", "ok ", "so ", "and ", "then "):
                if nxt.lower().startswith(lead):
                    nxt = nxt[len(lead):].strip()
            out.append(pre + ", " + nxt[:1].lower() + nxt[1:])
            i += 2
            continue
        out.append(x)
        i += 1
    return out


def _drop_repeated_readings(steps: list) -> list:
    """A step repeating readings already logged (the tech's recap of the same test) is logged once, at the place the test
    was first reported: the recap's wording when it holds more readings or carries the first sentence further (adds 'and
    the shaft is locked'), else the first wording. Every reading is kept."""
    out, sets = [], []
    for x in steps:
        p = set(_reading_pairs(x))
        if p:
            hit = next((k for k, q in enumerate(sets) if q and q <= p), None)
            if hit is not None:                  # more readings, or the same sentence carried further: this wording
                if p != sets[hit] or out[hit].rstrip(".").lower() in x.lower():
                    out[hit], sets[hit] = x, p
                elif x[:1].isdigit() and " at the " in x:     # '122 VAC at the control box' -> where the first one was read
                    where = x[x.index(" at the "):].rstrip(".")
                    if where.lower() not in out[hit].lower():
                        out[hit] = out[hit].rstrip(".") + where + "."
                continue
            if any(q and p <= q for q in sets):
                continue
        out.append(x)
        sets.append(p)
    return out


def _cause_steps(history, skip=()) -> list:
    """Every test / action the tech reported, in order, as full sentences; bullet readings become one sentence each group.
    skip: messages that are not test work (the tech's access answer)."""
    steps = []
    users = [m for m in history or [] if m.get("role") == "user" and (m.get("content") or "").strip()]
    for m in users[1:]:                       # the first message is the complaint (CONCERN)
        t = _clean_user(m.get("content"))
        if t.strip() in skip:
            continue
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
        for x in _join_setups(_sentences(" ".join(prose))):
            x = x.rstrip(".").strip(" \\/,;")
            for lead in ("ok so ", "ok, ", "ok ", "so ", "and "):
                if x.lower().startswith(lead):
                    x = x[len(lead):].strip()
            low = x.lower()
            if any(w in " " + low + " " for w in _ACCESS_WORDS) and not any(
                    w in " " + low + " " for w in (" replac", "will need", "recommend", "need to")) and not x.endswith("?"):
                acc = next((_access_clause(p) for p in x.split(" then ")
                            if any(w in " " + p.lower() + " " for w in _ACCESS_WORDS)), "")
                if acc:                                   # access work: the clean step in the tech's words
                    steps.append(acc)
                    continue
            if low.startswith("cause:"):
                x = x[6:].strip()
                low = x.lower()
            if x.endswith("?"):                            # a question to the assistant: keep only the work before it
                x = ", ".join(_before_question(x.rstrip("?").split(", ")))
                low = x.lower()
            if low.startswith(("i ", "i'm ", "im ")) and not _is_work(x):   # remarks to the assistant, not work performed
                continue
            if "recommend" in low or any(ph in low for ph in _CLOSE_DIAG):   # the wrap-up, not a test (goes to CORRECTION)
                continue
            if " you " in f" {low} ":                       # drop a clause spoken to the assistant ("everything you asked ...")
                x = ", ".join(c[4:] if (c.lower().startswith("you ") and _is_work(c)) else c
                              for c in x.rstrip(".").split(", ")
                              if " you " not in f" {c.lower()} " or (c.lower().startswith("you ") and _is_work(c)))
            x = x.strip(" \\/,;")
            if x:
                x = x[0].upper() + x[1:]
                steps.append(_sentence(x.rstrip(" ,;/")))
    count, caps, pairs = _session_vocab(_gd_msgs(history))
    tech_caps = {tok.lower() for t in _tech_msgs(history) for line in t.split("\n") for tok in line.split()[1:]
                 if tok[:1].isupper() and not tok.isupper()}
    tech_caps = {w.strip(".,;:!?()\"'") for w in tech_caps}
    vocab = (count, {k: v for k, v in caps.items() if k in tech_caps}, pairs)   # a name as the tech also wrote it (Peacemaker)
    return _drop_repeated_readings([_tidy(x, vocab) for x in steps])


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




# ---------------------------------------------------------------- the story in prose (11/25, Chase: "A STORY IS A WELL
# WRITTEN CONCERN CAUSE AND CORRECTION ... NOT A ... BULLETPOINT LIST"; "REWRITE THE WORDS INTO THE BEST POSSIBLE STORY";
# reasonably inferred findings are fine). The tech's steps are rewritten into professional past tense with no first
# person, restated steps merged, his casual conclusion folded into the cause, the repair told once (CORRECTION), and the
# whole told as three paragraphs. Every reading and finding he gave stays.
_VERBS = {"start": "started", "kick": "kicked", "run": "ran", "come": "came", "go": "went", "turn": "turned", "light": "lit",
          "blow": "blew", "draw": "drew", "read": "read", "show": "showed", "get": "got", "spin": "spun", "hum": "hummed",
          "click": "clicked", "trip": "tripped", "stop": "stopped", "shut": "shut", "fire": "fired", "ignite": "ignited",
          "cycle": "cycled", "work": "worked", "operate": "operated", "have": "had", "do": "did", "make": "made",
          "see": "saw", "find": "found", "take": "took", "hold": "held", "keep": "kept", "prevent": "prevented",
          "function": "functioned", "measure": "measured", "test": "tested", "engage": "engaged", "respond": "responded",
          "power": "powered", "heat": "heated", "cool": "cooled", "leak": "leaked", "need": "needed", "seem": "seemed",
          "look": "looked", "sound": "sounded", "smell": "smelled", "pull": "pulled", "drop": "dropped", "open": "opened",
          "close": "closed", "flash": "flashed", "blink": "blinked", "beep": "beeped", "buzz": "buzzed", "move": "moved",
          "exceed": "exceeded", "indicate": "indicated", "remain": "remained", "stay": "stayed", "fail": "failed"}
_S_FORMS = {}
for _v, _p in _VERBS.items():
    _S_FORMS[_v + ("es" if _v.endswith(("sh", "ch", "x", "ss", "o")) else "s")] = _p
_AUX = (("doesn't", "did not"), ("does not", "did not"), ("don't", "did not"), ("do not", "did not"), ("won't", "would not"),
        ("will not", "would not"), ("can't", "could not"), ("cannot", "could not"), ("can not", "could not"),
        ("isn't", "was not"), ("aren't", "were not"), ("it's", "it was"), ("that's", "that was"), ("there's", "there was"))
_DETERMINERS = {"the", "a", "an", "his", "its", "their", "of", "and", "or", "no", "all", "both", "my", "your", "our", "each",
                "every", "some", "any", "to", "did", "not", "would", "could", "will", "can"}
_PAST_IRREGULAR = {"found", "took", "ran", "read", "saw", "got", "put", "set", "had", "did", "made", "went", "left", "heard",
                   "felt", "kept", "held", "cut", "slid", "drew", "lit", "spun", "blew", "shut"}
_THE_AFTER = {"bypassed", "removed", "replaced", "inspected", "verified", "checked", "tested", "disconnected",
              "reinstalled", "installed", "jumped", "unplugged", "reconnected", "cleaned", "reset"}
_NO_THE = {"the", "a", "an", "all", "both", "each", "every", "further", "additional", "proper", "any", "no", "power",
           "voltage", "that", "this", "it", "its", "his", "their", "electrical", "visual", "operation", "continuity"}
_NO_LEAD_THE = {"during", "further", "with", "on", "when", "no", "after", "before", "while", "all", "both", "each", "power",
                "voltage", "it", "there", "then", "once", "this", "that", "these", "those", "the", "a", "an", "at", "in",
                "from", "per", "using", "following", "following", "if", "since", "because", "also", "both", "every",
                "nothing", "none", "not", "initial", "preliminary", "additional", "another", "one", "two", "three",
                "battery", "shore", "customer", "unit"}
_STOP = {"the", "a", "an", "and", "or", "but", "with", "on", "at", "to", "of", "in", "for", "from", "was", "were", "is", "are",
         "it", "that", "this", "when", "not", "did", "would", "could", "had", "has", "have", "be", "been", "then", "so",
         "found", "technician", "about", "into", "high", "low", "turn", "turned"}
_FAIL_WORDS = {"failed": "had failed", "seized": "was seized", "shorted": "was shorted", "open": "was open",
               "burnt": "was burnt", "burned": "was burned", "cracked": "was cracked", "leaking": "was leaking",
               "bad": "was bad", "defective": "was defective", "faulty": "was faulty", "corroded": "was corroded",
               "broken": "was broken", "stuck": "was stuck", "loose": "was loose", "worn": "was worn",
               "damaged": "was damaged", "locked": "was locked", "inoperative": "was inoperative"}
_CONCLUSION_LEADS = ("it was the ", "it's the ", "its the ", "it is the ", "the problem is ", "problem is ", "the issue is ",
                     "issue is ", "the problem was ", "the issue was ")
_CONNECTORS = ("Next, I", "I then", "From there, I", "After that, I", "I also")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _low1(s: str) -> str:
    """First letter lowered unless the first word is an acronym or a name (VAC, Peacemaker kept)."""
    w = s.split(" ", 1)[0]
    if not s or (len(w) > 1 and w.isupper()) or (len(w) > 1 and w[1:].lower() != w[1:]):
        return s
    return s[:1].lower() + s[1:]


def _is_past(word: str) -> bool:
    w = word.lower().strip(",.;")
    return (w.endswith("ed") and len(w) > 3) or w in _PAST_IRREGULAR


def _past_tense(s: str) -> str:
    """Present / future tech talk to past tense ('the compressor will kick on' -> 'kicked on', 'doesn't' -> 'did not',
    'reads' -> 'read', 'is' -> 'was'). Only verbs it knows are changed."""
    t = " " + s + " "
    for a, b in _AUX:
        for form in (a, _cap(a)):
            t = t.replace(" " + form + " ", " " + (b if form == a else _cap(b)) + " ")
    words = t.split(" ")
    out = []
    i = 0
    while i < len(words):
        w = words[i]
        core = w.rstrip(",.;:")
        tail = w[len(core):]
        low = core.lower()
        prev = out[-1].lower().strip(",.;:") if out else ""
        if low == "will" and i + 1 < len(words) and words[i + 1].rstrip(",.;:").lower() in _VERBS:
            nxt = words[i + 1].rstrip(",.;:")
            out.append(_VERBS[nxt.lower()] + words[i + 1][len(nxt):])
            i += 2
            continue
        if low in ("is", "am"):
            out.append(("Was" if core[:1].isupper() else "was") + tail)
        elif low == "are":
            out.append(("Were" if core[:1].isupper() else "were") + tail)
        elif low in _S_FORMS and prev not in _DETERMINERS and prev:
            out.append(_S_FORMS[low] + tail)
        elif low in _VERBS and prev and prev not in _DETERMINERS and i + 1 < len(words) \
                and words[i + 1].rstrip(",.;:").lower().endswith("ly"):
            out.append(_VERBS[low] + tail)
        else:
            out.append(w)
        i += 1
    return " ".join(out).strip()


def _join_list(items: list) -> str:
    items = [x for x in items if x]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _professional(s: str) -> str:
    """One tech step as a professional past-tense sentence with no first person."""
    t = s.strip().rstrip(".").strip()
    low = t.lower()
    if low.startswith("recorded the following readings (") and "): " in t:          # bullet readings -> one sentence
        label, items = t[len("recorded the following readings ("):].split("): ", 1)
        lead = "With" if "connected" in label.lower() or label.lower().startswith(("shore", "generator")) else "On"
        return f"{lead} {label}, I recorded " + _join_list([x.strip() for x in items.split(", ")]) + "."
    if low.startswith("when i ") and " i found " in low:                                 # 'When I checked X I found Y'
        k = low.index(" i found ")
        t = _cap(t[len("when i "):k].strip(" ,")) + " and found " + t[k + len(" i found "):]
    elif low.startswith("when i ") and ", " in t:
        a, b = t[len("when i "):].split(", ", 1)
        t = _cap(a) + " and " + b
    for lead in ("i am getting ", "i'm getting ", "im getting ", "i was getting ", "getting "):  # 'I am getting power to the board'
        if t.lower().startswith(lead):
            rest = t[len(lead):]
            for prep in (" to the ", " at the "):
                if prep in rest:
                    a, b = rest.split(prep, 1)
                    place = b.split(" but ", 1)[0].split(",", 1)[0].strip()
                    t = f"I had {_low1(a)} at the {b}".replace(f"{place} but it ", f"{place}, but the {place} ", 1)
                    break
            else:
                t = "I had " + _low1(rest)
            break
    words = t.split(" ")
    if len(words) > 2 and words[0] in ("I", "i") and _is_past(words[1]):
        t = _cap(" ".join(words[1:]))
    for x in (" voltage not coming", " power not coming", " signal not coming", " output not coming"):
        if x in t:
            noun = x.split()[0]
            t = t.replace("," + x, " and no " + noun + " was coming out").replace(x, " and no " + noun + " was coming out")
    t = t.replace(" on that ", " on the ").replace(" from thermostat", " from the thermostat")
    for a, b in ((", so it's good)", "), within specification"), (", so it was good)", "), within specification"),
                 (", so its good)", "), within specification"), (" and it works", " and the unit operated"),
                 (" and it worked", " and the unit operated"), (" but did not ignite", " but the burner did not ignite"), (", not in ", ", the unit was not in ")):
        t = t.replace(a, b)
    if t.lower().startswith("no ") and t.endswith((" observed", " found", " noted")) and " was " not in t:
        t = f"I {t.rsplit(' ', 1)[1]} no {t[3:].rsplit(' ', 1)[0]}"                     # 'No damage observed' -> 'I observed no damage'
    parts = t.split(", ")
    if len(parts) >= 3 and any(w in (" " + parts[-1] + " ") for w in (" was ", " were ", " are ", " is ")) \
            and not parts[-1].lower().startswith(("and ", "but ", "however")):
        t = ", ".join(parts[:-1]) + ", and " + parts[-1]                                # 'A, B, C were good' -> ', and C'
    if t.startswith(("It ", "it ")) and _CTX.get("cause_parts"):                        # 'It drew 1.91 A' -> the part named
        nums = [n for n, _u in _reading_pairs(t)]
        for noun, text in _CTX["cause_parts"]:
            if any(n in text for n in nums) or any(w in text for w in ("shaft",) if w in t):
                t = "The " + noun + t[2:]
                t = t.replace(", and the shaft is locked", ", and its shaft was locked").replace(
                    ", and the shaft was locked", ", and its shaft was locked")
                break
    low = t.lower()
    if low.startswith("no ") and _has_reading(t):                                       # 'No 12 V on the wire'
        t = "Found no " + t[3:]
    if low.startswith("went to the ") and " and " in t:                                 # 'Went to the X and removed Y to gain access'
        place, act = t[len("went to the "):].split(" and ", 1)
        verb, _, obj = act.partition(" ")
        purpose = next((p for p in (" to gain access", " for access", " to get access", " to access") if p in obj), "")
        if _is_past(verb) and purpose:
            thing, rest = obj.split(purpose, 1)
            art = "" if thing.split(" ", 1)[0].lower() in ("the", "a", "an") else "the "
            t = f"{_cap(verb)} {art}{thing.strip()} at the {place.strip()}{purpose}{rest}"
    words = t.split(" ")
    if len(words) >= 3 and words[-1].lower() in ("confirmed", "verified", "checked") and _has_reading(t):
        body = " ".join(words[:-1])                                                     # 'Thermostat 12 V confirmed'
        k = next((n for n, w in enumerate(body.split(" ")) if w[:1].isdigit()), 0)
        np_, reading = " ".join(body.split(" ")[:k]), " ".join(body.split(" ")[k:])
        t = f"{_cap(words[-1].lower())} {reading} at the {_low1(np_)}" if np_ else f"{_cap(words[-1].lower())} {reading}"
    t = _past_tense(t).replace(" but did not ignite", " but the burner did not ignite")
    if " and found " in t:                                                              # 'and found evaporator fan ...'
        a, b = t.split(" and found ", 1)
        w0 = b.split(" ", 1)[0]
        if w0.isalpha() and w0.islower() and w0 not in _NO_THE and w0 not in ("no", "nothing", "that"):
            t = f"{a} and found the {b}"
    words = t.split(" ")
    if len(words) > 1 and words[0].lower() in _THE_AFTER and words[1].lower() not in _NO_THE and words[1][:1].isalpha() \
            and not words[1][:1].isupper():
        words.insert(1, "the")
    first = words[0].lower().strip(",")
    if words and first.isalpha() and not _is_past(first) and not first.endswith(("ing", "ly")) and first not in _NO_LEAD_THE \
            and first not in _VERBS and not words[0].isupper() and len(words) > 2:
        words = ["The", _low1(words[0])] + words[1:]                                     # 'Blower started' -> 'The blower ...'
    t = " ".join(words)
    return _sentence(_cap(t))


def _content(s: str) -> set:
    words = set()
    for raw in s.lower().replace("/", " ").split():
        tok = "".join(ch for ch in raw if ch.isalpha() or ch == "-").strip("-")
        if len(tok) >= 3 and tok not in _STOP:
            w = tok
            for suf in ("ing", "ed", "es", "s"):
                if w.endswith(suf) and len(w) - len(suf) >= 3:
                    w = w[:-len(suf)]
                    break
            words.add(w)
    for _num, unit in _reading_pairs(s):
        words.add("voltage" if unit in ("v", "vac", "vdc") else ("amp" if unit in ("a", "amp", "amps") else unit))
    return words


def _merge_restated(steps: list) -> list:
    """A later step that restates an earlier one (the tech's recap of the same test: half or more of its words in common,
    and readings that do not disagree) is told once, at the earlier place, in the wording that carries more readings
    (else the fuller one)."""
    out = []
    for x in steps:
        cx, rx = _content(x), set(_reading_pairs(x))
        hit = None
        for k, y in enumerate(out):
            cy, ry = _content(y), set(_reading_pairs(y))
            if min(len(cx), len(cy)) < 3 or (rx and ry and not (rx <= ry or ry <= rx)):
                continue
            if len(cx & cy) / min(len(cx), len(cy)) >= 0.5:
                hit = k
                break
        if hit is None:
            out.append(x)
            continue
        y = out[hit]
        ry = set(_reading_pairs(y))
        keep, drop = (x, y) if len(rx) > len(ry) or (len(rx) == len(ry) and len(x) > len(y)) else (y, x)
        for tok in drop.split():                       # 'high fan black/white' -> the kept wording says which wires
            if "/" in tok and tok.strip(".,") in keep:
                before = drop.split(tok, 1)[0].split()[-2:]
                lead = [w for w in before if w.lower() not in ("the", "on", "at", "checked", "of")]
                if lead and " ".join(lead).lower() not in keep.lower():
                    t = tok.strip(".,")
                    keep = keep.replace(f"on {t}", f"on the {' '.join(lead)} {t}", 1).replace(
                        f"at {t}", f"at the {' '.join(lead)} {t}", 1)
                break
        out[hit] = keep
    return out


def _cause_clause(cause: str) -> str:
    """'Failed ceiling control/relay board (not commanding fans) + seized fan motor (locked shaft, 1.91 A draw)' ->
    'the ceiling control/relay board had failed and was not commanding the fans, and the fan motor was seized (locked
    shaft, 1.91 A draw)'."""
    parts, out = [], []
    for chunk in cause.replace(" + ", "|").replace("; ", "|").split("|"):
        if chunk.strip():
            parts.append(chunk.strip().rstrip("."))
    for p in parts:
        inner = ""
        if p.endswith(")") and "(" in p:
            p, inner = p[:p.rindex("(")].strip(), p[p.rindex("(") + 1:-1].strip()
        first, _, rest = p.partition(" ")
        if first.lower() in _FAIL_WORDS and rest:
            noun = rest if rest.split(" ", 1)[0].lower() in ("the", "a", "an") else "the " + rest
            s = f"{noun} {_FAIL_WORDS[first.lower()]}"
        else:
            s = p[0].lower() + p[1:] if p[:2] != p[:2].upper() else p
            ws = s.split(" ")
            if " not " in f" {s} " and not any(w in ("is", "was", "are", "were") for w in ws):
                s = s.replace(" not ", " was not ", 1)
            if ws[0] not in ("the", "a", "an") and ws[0].isalpha() and ws[0].islower():
                s = "the " + s
        if inner:
            if inner.lower().startswith("not "):
                obj = inner[4:]
                w = obj.split(" ")
                if len(w) == 2 and w[1][:1].isalpha():
                    obj = f"{w[0]} the {w[1]}"
                s += f" and was not {obj}"
            else:
                s += f" ({inner})"
        out.append(s)
    return out[0] if len(out) == 1 else ", ".join(out[:-1]) + ", and " + out[-1]


def _front_place(rest: str) -> str:
    """'read 0.000 to 0.048 VAC on the high fan black/white at the 9-pin connector.' -> 'At the 9-pin connector, I read
    0.000 to 0.048 VAC on the high fan black/white.' ('' when the step does not end on where it was read)."""
    body = rest.rstrip(".")
    k = body.rfind(" at the ")
    if k < 0 or " to gain access" in body or " for access" in body:
        return ""
    place, head = body[k + 1:], body[:k]
    if "," in place or " and " in place or len(place.split()) > 6 or not head.strip():
        return ""
    return f"{_cap(place)}, I {head}."


def _narrate(steps: list) -> str:
    """The steps as one paragraph in the tech's own voice (Chase 11/25: "It needs to be first person. its the
    technicians story"): a step that starts with what was done gets 'I', and the openings vary (connectors, or where a
    reading was taken put first) so the order of the job reads through without I / I / I."""
    out, n, last_i = [], 0, False
    for s in steps:
        w = s.split(" ", 1)
        if len(w) == 2 and _is_past(w[0]) and w[0][:1].isupper():
            rest = f"{w[0].lower()} {w[1]}"
            fronted = _front_place(rest) if last_i and _has_reading(rest) else ""
            if not out:
                s = f"I first {rest}"
            elif fronted:
                s = fronted
            else:
                s = f"{_CONNECTORS[n % len(_CONNECTORS)]} {rest}"
                n += 1
            last_i = s.startswith("I ") or s.split(", ", 1)[-1].startswith("I ") and not fronted
        else:
            last_i = False
        out.append(s)
    return " ".join(out)


def _is_conclusion(s: str) -> str:
    low = s.lower()
    for lead in _CONCLUSION_LEADS:
        if low.startswith(lead):
            return s[len(lead) - len("the "):].rstrip(".") if lead.endswith("the ") else s[len(lead):].rstrip(".")
    return ""


_CTX = {}


def _cause_parts(cause: str) -> list:
    """[(part noun, its text)] from a record cause such as 'Failed ceiling control/relay board (...) + seized fan motor
    (locked shaft, 1.91 A draw)'."""
    out = []
    for chunk in cause.replace(" + ", "|").replace("; ", "|").split("|"):
        c = chunk.strip()
        head = c.split("(", 1)[0].strip()
        first, _, rest = head.partition(" ")
        if first.lower() in _FAIL_WORDS and rest:
            out.append((rest.strip(), c))
    return out


_VERIFY_WORDS = ("as designed", "working properly", "works properly", "operating properly", "operates properly",
                 "working normally", "works now", "working now", "all working", "now works", "now working")


def warranty_story(case: dict, history: list = None, model_text: str = "", references=()) -> str:
    """The story written from the tech's own messages and the record when Grok is not available or its text fails the
    check: CONCERN, CAUSE and CORRECTION as paragraphs (see above). Readings and findings come only from the session."""
    case = case or {}
    st = case.get("state") or {}
    complaint = complaint_of(case, history)
    if not complaint and not st and not history:
        return "No session recorded."
    unit = (case.get("unit") or {}).get("model_text") or model_text or ""
    found = chat_findings(history)
    rep = st.get("repair") or {}
    access_done = [] if st.get("access_from_chat") else [_sentence(x) for x in st.get("access_done") or []]
    raw = _cause_steps(history, skip={(st.get("access_answer") or "").strip()} - {""})
    if not raw:
        for f in st.get("facts") or []:
            item, value = (f.get("item") or "").strip(), (f.get("value") or "").strip()
            if item or value:
                raw.append(f"Recorded {item} of {value}." if item and value else _sentence(item or value))
    _CTX["cause_parts"] = _cause_parts((st.get("cause") or "").strip() or found["cause"])
    steps, verified_concern, tech_cause, verify_words = [], False, "", ""
    for x in access_done + raw:                       # access work comes before the tests it opened up
        low = x.lower()
        if low.startswith(("verified customer concern", "verified the customer concern", "verified concern",
                           "customer concern verified", "concern verified")):
            verified_concern = True
            continue
        concl = _is_conclusion(x)
        if concl:                                    # his own call on the cause: folded into the cause sentence
            tech_cause = tech_cause or concl
            continue
        if rep.get("done") and low.startswith(("replaced ", "installed ", "repaired ")):
            verify_words = next((v for v in _VERIFY_WORDS if v in low), verify_words)
            continue                                 # the repair is told once, in CORRECTION
        steps.append(_professional(x))
    steps = _merge_restated(steps)
    cause = (st.get("cause") or "").strip() or found["cause"]
    cause = (_drop_parens(cause) if cause and found["cause"] == cause and "(" in cause and " + " not in cause else cause)
    concern = _concern_line(complaint) if complaint else "Customer concern not recorded."
    for a, b in ((" ran about ", " ran for about "), (" then dead ", " and then went dead "), (" then dead.", " and then went dead."),
                 (" / no ", " with no "), (" / ", " and ")):
        concern = concern.replace(a, b)
    letters = [ch for ch in concern if ch.isalpha()]
    if letters and sum(ch.isupper() for ch in letters) > 0.8 * len(letters):    # a complaint typed in capitals
        sents = []
        for x in _sentences(concern):
            x = " ".join(w if w.strip(".,") in _KEEP_CAPS else w.lower() for w in x.split())
            sents.append(_cap(x))
        concern = " ".join(_cap(x[len("customer states that "):]) if k and x.lower().startswith("customer states that ")
                           else x for k, x in enumerate(sents))
    if verified_concern:
        concern += " I verified the concern."
    para = _narrate(steps) if steps else "No testing was recorded in this job."
    if cause:
        first, _, more = cause.partition(". ")
        clause = _cause_clause(first)
        verb = any(f" {w} " in f" {clause} " for w in ("was", "were", "had", "is", "are", "has", "did")) or \
            any(w.endswith("ed") for w in clause.split()[1:])
        if verb:
            para += " These results confirmed that " + clause.rstrip(".") + "."
        else:
            c = _low1(clause[4:] if clause.startswith("the ") else clause).rstrip(".")
            last = c.split("[", 1)[0].split()[-1].lower() if c.split("[", 1)[0].split() else ""
            art = (("an " if c[:1].lower() in "aeiou" else "a ") if last in ("failure", "fault", "leak", "short", "restriction",
                                                                             "malfunction", "problem", "issue", "blockage")
                   else "the ")
            para += " These results identified the cause as " + art + c + "."
        if more:
            para += " " + _past_tense(_sentence(more))
    elif tech_cause:
        para += " My testing pointed to " + _low1(_past_tense(tech_cause)) + " as the cause."
    else:
        para += " I was not able to confirm the cause during diagnosis."
    for x in noted_findings(history):
        nf = _low1(_professional(x))
        if nf.split(" ", 1)[0] not in ("the", "a", "an") and nf[:1].islower():
            nf = "the " + nf
        para += " I also noted that " + nf.rstrip(".") + "; I recorded it as a finding, and it was not the cause."
    refs = [r for r in references or [] if r]
    docs = [d for d in _doc_numbers(_gd_msgs(history)) if not any(d in r for r in refs)]   # maker doc numbers GD named
    for r in refs:
        if ": " in r:
            title, secs = r.split(": ", 1)
            para += f" My testing followed the {title} ({secs})."
        else:
            para += f" My testing followed the {r}."
    if docs:
        para += " I referenced manufacturer documents " + _join_list(docs) + "."
    if rep.get("done"):
        corr = _sentence(_professional(rep.get("what") or "Performed the repair"))
        if _is_past(corr.split(" ", 1)[0]):
            corr = "I " + _low1(corr)
        if rep.get("verified"):
            corr += (" After the repair, I operated the unit and verified it was working as designed." if "designed" in verify_words
                     else " After the repair, I operated the unit and verified it was working properly.")
        else:
            corr += " I recommend verifying proper operation."
    else:
        st2 = dict(st)
        rec_tech = (st.get("tech_recommendation") or "") or tech_recommendation(history)
        if rec_tech:                   # the tech's own call wins over the assistant's wording (11/24, WO 156231)
            st2["recommendation"] = rec_tech
        corr = _recommendation(st2, found)
        if corr.startswith("Recommend "):
            corr = "I recommend " + corr[len("Recommend "):]
            for a, b in ((", then re-test ", ", then re-testing "), (", then verify ", ", then verifying "),
                         (", then test ", ", then testing "), (", then check ", ", then checking "),
                         (", then confirm ", ", then confirming "), (" and verify ", " and verifying ")):
                corr = corr.replace(a, b)
        needed = st.get("access_needed") or []
        if needed:
            corr += (" The repair will also require removing and reinstalling "
                     + _join_list(["the " + _item_noun(x) for x in needed]) + ".")
    out = [f"UNIT: {unit}", ""] if unit else []
    out += ["CONCERN", concern, "", "CAUSE", para, "", "CORRECTION", corr]
    return "\n".join(out)


# ---------------------------------------------------------------- Grok writes it
STORY_SYSTEM = """You write the technician / warranty story for an RV repair job from a Guided Diagnostics session. The shop sends it to the maker or the coach builder (Furrion, Dometic, Lippert, Keystone, Brinkley and others) to justify the diagnosis and the time on the job, and the same story goes on customer-pay work. A story is a well-written Concern, Cause and Correction, and it is the technician's own story: written in the first person as the tech ("I confirmed 12 V at the thermostat. Next, I removed the trim ..."; "I replaced ..."), never "the technician" or a third-party narration, in well-written professional paragraphs, past tense, shop language, plain text with no markdown, and no bullet points or numbered lists. Sentence openings vary ("Next, ...", "With the ...", "At the 9-pin connector, I read ...") so it does not read I, I, I. The tech's notes are rewritten into the best story they can make: his spelling and shorthand cleaned up, restated steps told once, his remarks to the assistant turned into what he did and found, and conclusions a good technician would reasonably draw from the results stated plainly.

The story has three parts, each headed by its name on its own line:

CONCERN
A short paragraph with the customer's complaint as the job started ("Customer states ..."), and the conditions or pattern the tech observed when verifying it ("I verified the concern ...").

CAUSE
A paragraph (two when the job is long) telling the diagnosis in the order it was done: every test, inspection and action the tech reported, with the readings and results exactly as the tech gave them (every voltage, amperage, temperature, resistance and pressure, with its units), and what each result ruled in or out. Disassembly and access work (removing the unit, panels, trim, ducts, covers, battery box covers) is told where it happened, before the tests it opened up, because it is labor on the job; the access work the tech described anywhere in the session and his answer to the access question are given below. When the tech corrected the assistant during the session, the tech's version is what happened. A test that followed a manual procedure says so (for example "following the Suburban fan control module board troubleshooting flowchart"), and the official documents the procedures came from, listed below under OFFICIAL PROCEDURE SOURCES, are named in the paragraph by title or maker document number with the procedure or section used, with no page numbers and no library codes; web pages, forum posts and other unofficial sources are not named, and the steps they informed stay. Steps the assistant only suggested are told when the tech reported doing them. A reading out of the maker's specification that the tech chose not to pursue is mentioned as a noted finding, and is not the cause. The paragraph ends by naming the confirmed cause and why the tests point to it.

CORRECTION
When the job's repair status says the repair was performed: the repair and how it was verified, in full sentences. When it says the repair was not performed (diagnosis only): the recommended repair in general terms, as "I recommend ..."; when the tech stated his own recommendation, the correction is that recommendation, for example "I recommend replacing the wall thermostat, then re-test the full heating sequence to verify repair." When the tech listed items the repair will need removed, the removal and reinstallation work is named in the paragraph. A secondary issue the tech left can be a separate recommendation. A sentence asking for authorization of the repair and the diagnostic time can close it when that fits the job.

Readings, part names, results and document names come from the session as they appear there. Part numbers, labor times and operation codes appear when the tech gave them. Words about the software (OPEN, state, session, assistant, GD, TechTrack) stay out of the story."""


def story_messages(case: dict, history: list = None, model_text: str = "", references=(), problems=()) -> list:
    case = case or {}
    st = case.get("state") or {}
    unit = (case.get("unit") or {}).get("model_text") or model_text or "not recorded"
    category = (case.get("unit") or {}).get("category") or ""
    skip = (st.get("access_answer") or "").strip()
    lines = []
    for m in history or []:
        role, text = m.get("role"), (m.get("content") or "").strip()
        if role == "user":
            text = _clean_user(text)
            if text and text != skip:
                lines.append("TECH: " + text)
        elif role == "assistant" and text:
            text = without_story_block(text)   # GD's own in-chat story summary is not the source; the session is
            if text:
                lines.append("ASSISTANT (suggestions and analysis; work counts as done when the tech reported it): " + text)
    keep = {k: st.get(k) for k in ("facts", "cause", "repair", "order_part", "recommendation") if st.get(k)}
    rec_tech = (st.get("tech_recommendation") or "") or tech_recommendation(history)
    status = ("REPAIR STATUS: performed (the CORRECTION is the repair done and its verification)."
              if repair_done(case, history) else
              "REPAIR STATUS: not performed - diagnosis only (the CORRECTION is a general recommendation starting with \"Recommend\").")
    parts = [f"UNIT: {category + ' / ' if category else ''}{unit}",
             "CUSTOMER COMPLAINT (job start): " + (complaint_of(case, history) or "not recorded"),
             status,
             "TECH'S STATED RECOMMENDATION: " + (rec_tech or "none stated"),
             "READINGS THE TECH REPORTED (each one belongs in the test log): " + (", ".join(readings(history)) or "none"),
             "ACCESS WORK DONE DURING THE DIAGNOSIS (the tech's answer to the access question): "
             + ("; ".join([] if st.get("access_from_chat") else (st.get("access_done") or [])) or "see the session"),
             "ACCESS WORK THE TECH DESCRIBED IN THE SESSION: " + ("; ".join(chat_access_steps(history, skip={skip} - {""}))
                                                               or "none found"),
             "REMOVAL THE RECOMMENDED REPAIR WILL NEED (the tech's words): " + ("; ".join(st.get("access_needed") or []) or "none reported"),
             "OFFICIAL PROCEDURE SOURCES: " + ("; ".join(r for r in references if r) or "none recorded"),
             "CASE RECORD: " + json.dumps(keep, ensure_ascii=False),
             "SESSION:\n" + "\n\n".join(lines)]
    if problems:
        parts.append("The last draft needs these fixed: " + "; ".join(problems) + ".")
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
    """What keeps a story from being used ([] = good): a missing concern / cause / correction, a correction that is not a recommendation on a diagnosis-only job or does not follow the tech's own
    recommendation, a long number (part number) nowhere in the session, a reading the tech reported that is not in the
    story, a library code or page number, or an access item the tech listed that is not in the story."""
    sec = parse_story(text)
    probs = [f"no {s} section" for s in ("CONCERN", "CAUSE", "CORRECTION") if not sec.get(s)]
    if probs:
        return probs
    st = (case or {}).get("state") or {}
    corr = sec["CORRECTION"].lower()
    if not repair_done(case, history):
        if "recommend" not in corr:
            probs.append("diagnosis-only correction is not a recommendation")
        verb, part = _rec_verb_and_part((st.get("tech_recommendation") or "") or tech_recommendation(history))
        if verb:
            after = corr[corr.find("recommend"):]
            word = part.split()[-1] if part else ""
            if not after.startswith(f"recommend {verb}") or (word and word not in after.split(".")[0]):
                probs.append(f"correction does not follow the tech's recommendation (recommend {verb} the {part})")
    source = json.dumps(case or {}, ensure_ascii=False) + " ".join(m.get("content") or "" for m in history or [])
    for num in _long_numbers(text):
        if num not in source:
            probs.append(f"number {num} is not in the session")
    miss = missing_readings(text, history)
    if miss:
        probs.append("missing readings: " + ", ".join(miss))
    ids = _library_ids(text)
    if ids:
        probs.append("library codes in the story: " + ", ".join(ids))
    if _page_numbers(text):
        probs.append("page numbers in the story")
    low = text.lower()
    for x in ([] if st.get("access_from_chat") else (st.get("access_done") or [])) + (st.get("access_needed") or []):
        noun = _item_noun(x).lower()
        key = noun.split()[-1] if noun else ""
        if key and key not in low:
            probs.append(f"access item left out: {x}")
    return probs


def check_story(text: str, case: dict, history: list = None) -> str | None:
    """The story with any OPEN tag removed when it passes story_problems, else None."""
    if story_problems(text, case, history):
        return None
    return _drop_empty_sections(_scrub((text or "").replace("**", "").strip()))


def _drop_empty_sections(text: str) -> str:
    """A section header with nothing under it (GD-4: 'MANUFACTURER REFERENCES' when no maker document was used) is left
    out, and the numbered headers after it close up."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        hd = _header(lines[i])
        if hd and not hd[1]:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j >= len(lines) or _header(lines[j]):
                while out and not out[-1].strip():
                    out.pop()
                i = j
                if out and j < len(lines):
                    out.append("")
                continue
        out.append(lines[i])
        i += 1
    out = "\n".join(out).strip()
    n, fixed = 0, []
    numbered = [ln for ln in out.split("\n") if _header(ln) and ln.strip()[:1].isdigit()]
    for ln in out.split("\n"):
        if numbered and _header(ln) and ln.strip()[:1].isdigit():
            n += 1
            k = 0
            t = ln.strip()
            while k < len(t) and t[k].isdigit():
                k += 1
            ln = f"{n}{t[k:]}"
        fixed.append(ln)
    return "\n".join(fixed)


def write_warranty_story(case: dict, history: list = None, model_text: str = "", chat_fn=None, references=()) -> str:
    """The Write-warranty-story button. chat_fn(messages) -> text calls Grok; None = Grok not available."""
    case = case or {}
    # GD-4 (11/24): the story is written here, from the whole chat, after the access question; a story GD put in its own
    # state block mid-chat is not used.
    if chat_fn is not None and (history or complaint_of(case, history)):
        problems = ()
        for _ in range(2):
            try:
                text = chat_fn(story_messages(case, history, model_text, references, problems)) or ""
            except Exception as e:
                import gd_errors
                gd_errors.fallback("story", "Grok's story call failed; the template story is used", exc=e)
                break
            ok = check_story(text, case, history)
            if ok:
                return ok
            problems = tuple(story_problems(text, case, history))
        else:
            import gd_errors
            gd_errors.fallback("story", "Grok's story failed the checks twice; the template story is used",
                               problems=list(problems)[:6])
    return warranty_story(case, history, model_text, references)
