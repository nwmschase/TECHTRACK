"""Case state for Guided Diagnostics (branch fresh-core).

The brain (the LLM) ends every reply with one small JSON block between <state> and </state>.
The code only cuts that block off the reply, checks the field types, and stores it.
The code never reads the tech's words or the brain's prose to decide anything: no regex on prose.

Fields (all optional in each update; missing = unchanged):
  facts               [{item, value, quote}]  readings / observations the tech gave (upsert by item)
  fault_code          str     a code the tech reported (the finder re-picks pages for it)
  pending_test        str     the test the brain is waiting on ("" when none)
  part_working        str     the part currently being tested or worked on
  next_part_to_fetch  str     text for a library search: a part, fault code, symptom or label words ("" when none)
  web_lookup          str     text for a web lookup: a URL, words, or both ("" when none)
  order_part          str     a part the brain tells the tech to order / replace this turn ("" when none)
  cause               str     the brain's current diagnosis, with its doc + page
  repair              {done: bool, verified: bool, what: str, quote: str}  quote = the tech's words
  cited               [{doc_id, page}]   pages the brain cited this turn
  summary             str     running summary of the job so far (replaces old turns in the prompt)
  closed              bool    the brain closed the job (repair verified, incl. adjustments)
"""
from __future__ import annotations

import copy
import json

OPEN, CLOSE = "<state>", "</state>"

SCHEMA = {
    "facts": list, "fault_code": str, "pending_test": str, "part_working": str,
    "next_part_to_fetch": str, "web_lookup": str, "order_part": str, "cause": str, "repair": dict,
    "cited": list, "summary": str, "closed": bool,
}


def new_state() -> dict:
    return {"facts": [],
            "fault_code": "", "pending_test": "", "part_working": "", "next_part_to_fetch": "", "web_lookup": "", "order_part": "",
            "cause": "", "repair": {"done": False, "verified": False, "what": "", "quote": ""}, "cited": [],
            "summary": "", "closed": False}


def split_reply(reply: str):
    """Cut the LAST <state>...</state> block off the reply. Returns (prose_for_tech, block_text or None)."""
    text = reply or ""
    end = text.rfind(CLOSE)
    start = text.rfind(OPEN, 0, end if end >= 0 else len(text))
    if start < 0 or end < 0 or end < start:
        return text.strip(), None
    block = text[start + len(OPEN):end].strip()
    if block.startswith("```"):
        block = block.strip("`")
        if block.lower().startswith("json"):
            block = block[4:]
    prose = (text[:start] + text[end + len(CLOSE):]).strip()
    return prose, block.strip()


def validate(update) -> tuple:
    """Keep only known fields with the right type. Returns (clean_update, problems)."""
    clean, problems = {}, []
    if not isinstance(update, dict):
        return {}, ["state block is not a JSON object"]
    for k, v in update.items():
        want = SCHEMA.get(k)
        if want is None:
            problems.append(f"unknown field {k!r} ignored")
            continue
        if not isinstance(v, want) or (want is not bool and isinstance(v, bool)):
            problems.append(f"field {k!r} has type {type(v).__name__}, expected {want.__name__}; ignored")
            continue
        if k == "facts":
            v = [f for f in v if isinstance(f, dict) and isinstance(f.get("item"), str) and f.get("item")]
        if k == "cited":
            v = [c for c in v if isinstance(c, dict) and c.get("doc_id")]
        if k == "repair":
            v = {"done": bool(v.get("done", False)), "verified": bool(v.get("verified", False)),
                 "what": str(v.get("what", "") or ""), "quote": str(v.get("quote", "") or "")}
        clean[k] = v
    return clean, problems


def parse(reply: str) -> tuple:
    """Returns (prose, clean_update, problems). A missing or broken block gives an empty update and a problem note."""
    prose, block = split_reply(reply)
    if block is None:
        return prose, {}, ["no <state> block in reply"]
    try:
        data = json.loads(block)
    except ValueError as e:
        return prose, {}, [f"state block is not valid JSON: {e}"]
    clean, problems = validate(data)
    return prose, clean, problems


def merge(state: dict, update: dict) -> dict:
    """Store an update. Scalars replace; facts upsert by item (newest value wins, nothing deleted);
    cited is per-turn (replaced)."""
    out = copy.deepcopy(state or new_state())
    for k, v in (update or {}).items():
        if k == "facts":
            by_item = {f["item"]: i for i, f in enumerate(out.get("facts") or [])}
            facts = list(out.get("facts") or [])
            for f in v:
                rec = {"item": f["item"], "value": str(f.get("value", "")), "quote": str(f.get("quote", ""))}
                if f["item"] in by_item:
                    facts[by_item[f["item"]]] = rec
                else:
                    by_item[f["item"]] = len(facts)
                    facts.append(rec)
            out["facts"] = facts
        else:
            out[k] = copy.deepcopy(v)
    return out


def dumps(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False, sort_keys=True)


def loads(text: str) -> dict:
    return merge(new_state(), validate(json.loads(text))[0])
