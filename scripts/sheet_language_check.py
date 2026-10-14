"""Sheet-language checks for Bay PDFs (v4.19.63 rev2, Leader page review 10/14).

  SL-1  garbled fragment: a PRIMARY sentence that names no manual, page or figure,
        a node sentence of 4+ words with no verb, or a flowchart
        end node that points back with 'after that/this ... prove|check|test'.
  SL-2  a step heading that is not an action (starts with a condition or a
        statement), or a plain step whose line 1 repeats its heading.
  SL-3  a split If/then: a numbered line that is only a condition ending in ':'.

Usage: python scripts/sheet_language_check.py SHEET.pdf [...]   (exit 1 on any FAIL)
"""
from __future__ import annotations

import re
import subprocess
import sys

_CONDITION = r"(?:If|When|Once|After|Before|Until|Unless|On a|On an|On the|With)\b"
_STATEMENT = r"(?:The|This|That|It|A|An|Both|Each|Every|No|Did|Does|Is|Are|Shaft)\b"
# Verbs and verb forms the sheets use. A sentence with none of them is a fragment.
_VERB = re.compile(
    r"\b(?:is|are|was|were|be|been|has|have|had|do|does|did|can|will|must|should|may|"
    r"shows?|reads?|runs?|works?|holds?|stops?|leaks?|leaves?|returns?|remains?|cools?|"
    r"stays?|passes|fails?|starts?|turns?|lights?|comes?|goes|means|calls?|"
    r"[a-z]+(?:ed|ing)|check|test|measure|replace|repair|reset|confirm|seat|set|leave|"
    r"turn|press|open|close|remove|install|clean|tighten|retest|go|stop|write|look|let|"
    r"run|disconnect|reconnect|verify|inspect|clear|correct|watch|find|match|use|note|"
    r"recheck|re[a-z]+|record|reseat|prove|keep|hold|cite|see|follow|dry|wait|jump|bypass|want|try|r&r)\b",
    re.I,
)
_IMPERATIVE = (
    r"(?:check|test|measure|replace|repair|reset|confirm|seat|set|leave|turn|press|open|close|remove|"
    r"install|clean|tighten|retest|go|stop|write|look|let|run|disconnect|reconnect|verify|inspect|"
    r"clear|correct|watch|find|match|use|note|record|reseat|bypass|keep|stay|move|level|add|apply|fit|attach|"
    r"connect|escalate|straighten|swap|pull|push|lift|lower|drain|fill|flush|plug|unplug|hold|wait|seal|tape|unscrew|loosen)"
)
_LABEL = re.compile(r"^(?:Where|Tools|Safety|Good looks like|Bad looks like|Next|If it fails|Do this|Figure)\s*:")
_DANGLING = re.compile(r"\bafter (?:that|this)(?: [\w-]+){0,3} (?:prove|check|test)\.?$", re.I)


_MORE_VERBS = (
    "pour|wash|drop|center|clamp|hoist|make|point|unplug|apply|push|pull|lift|lower|power|light|relight|"
    "back-probe|probe|trace|label|mark|swap|add|bring|fit|attach|connect|jumper|level|read|compare|listen|"
    "feel|smell|spin|rotate|wait|take|towel-dry|shut|cycle|ask|call|observe|count|time|loosen|unscrew|"
    "screw|tape|seal|plug|drain|fill|flush|lock|unlock|slide|lay|raise|retract|extend|store|enter|hold"
)


def _has_verb(text: str) -> bool:
    if _VERB.search(text):
        return True
    # 'Shim the unit', 'Torque the bolts': an imperative opens with its verb and an object.
    if re.match(r"^(?:\d+\.\s+)?[A-Z][a-z-]+\s+(?:the|a|an|both|each|it|them|all|every)\b", text):
        return True
    return bool(re.search(r"\b(?:" + _IMPERATIVE + "|" + _MORE_VERBS + r"|is|are)\b", text, re.I))


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][\w'/-]*", text))


def _sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<!\bFig\.)(?<!\bFigs\.)(?<!\bNo\.)(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [s.strip() for s in parts if s.strip()]


def check_lines(lines: list[str], *, primary: str = "", nodes: list[str] | None = None) -> list[str]:
    """Return problem strings. ``lines`` are the sheet's text lines in order."""
    problems: list[str] = []
    for sent in _sentences(primary or ""):
        # The PRIMARY line is a citation: each sentence names a manual, a page, or a figure.
        if (
            _words(sent) >= 5
            and not re.search(r"manual|guide|instruction|\bSM\b|\bIM\b|CCD-|\bpages?\s+\d|\bFigs?\.|section|\d", sent, re.I)
            and not _VERB.search(sent)
        ):
            problems.append(f"SL-1 garbled fragment (PRIMARY names no manual): {sent}")
    for value in list(nodes or []):
        for sent in _sentences(value or ""):
            if _words(sent) >= 4 and not _has_verb(sent):
                problems.append(f"SL-1 garbled fragment (no verb): {sent}")
            if _DANGLING.search(sent):
                problems.append(f"SL-1 garbled fragment (dangling 'after that'): {sent}")
    for i, line in enumerate(lines):
        line = line.strip()
        head = re.match(r"^Step\s+\d+\s*:\s*(.+)$", line)
        if head:
            title = head.group(1).strip().rstrip(".")
            acts_after_condition = re.match(_CONDITION, title) and re.search(r",\s+(?:then\s+)?" + _IMPERATIVE + r"\b", title)
            if (re.match(_CONDITION, title) and not acts_after_condition) or re.match(_STATEMENT, title) or title.endswith("?"):
                problems.append(f"SL-2 heading is not an action: {line}")
            # A plain step (heading, then 'Do this:' straight away) must not open
            # with its own heading. A labeled profile step (Where/Safety/Tools first)
            # keeps the locked profile layout, where line 1 restates the action.
            nxt = [l.strip() for l in lines[i + 1 : i + 3]]
            first = nxt[1][3:] if len(nxt) == 2 and nxt[0] == "Do this:" and nxt[1].startswith("1. ") else ""
            if first and first.rstrip(".:").lower() == title.lower():
                problems.append(f"SL-2 heading repeats line 1: {line}")
        num = re.match(r"^\d+\.\s+(.+)$", line)
        if num and _words(num.group(1)) >= 4 and not _has_verb(num.group(1)) and not num.group(1).startswith("("):
            problems.append(f"SL-1 garbled fragment (no verb): {line}")
        if num and re.match(_CONDITION, num.group(1)) and num.group(1).rstrip().endswith(":"):
            problems.append(f"SL-3 split If/then: {line}")
    return problems


def check_pdf(path: str) -> list[str]:
    text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
    lines = [l for l in text.splitlines() if l.strip()]
    layout = subprocess.run(["pdftotext", "-layout", "-l", "1", path, "-"], capture_output=True, text=True).stdout
    prim = ""
    rows = layout.splitlines()
    for i, l in enumerate(rows):
        m = re.match(r"^PRIMARY\s{2,}(.+)$", l.strip())
        if m:
            prim = m.group(1).strip()
            for more in rows[i + 1 : i + 3]:
                if more.startswith(" " * 8) and more.strip() and not more.strip().isupper():
                    prim += " " + more.strip()
                else:
                    break
            break
    # Flowchart node text: page 1 between VISUAL FLOWCHART and the end of the page,
    # joined so a node broken over lines reads whole.
    flow = re.sub(r"\s+", " ", layout.split("VISUAL FLOWCHART", 1)[-1]) if "VISUAL FLOWCHART" in layout else ""
    nodes = [m.group(0) for m in re.finditer(r"[A-Z][^.?!]{3,160}\bafter (?:that|this)(?: [\w-]+){0,3} (?:prove|check|test)\.", flow)]
    return check_lines(lines, primary=prim, nodes=nodes)


def main(argv: list[str]) -> int:
    bad = 0
    for path in argv:
        problems = check_pdf(path)
        print(f"{path}: {'PASS' if not problems else 'FAIL'}")
        for p in problems:
            print("  " + p)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
