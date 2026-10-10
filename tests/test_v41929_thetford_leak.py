"""v4.19.29: a Thetford flush-lever leak uses the English leak rows only.

The page text is the pypdf extract of OM Permanent RV Toilet 42088 (the same
extractor the shop library uses). Kits 42109 and 34122/34123 are the lines the
live sheet cited.
"""
import json
import unittest
from pathlib import Path

from bay_procedure import (
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    layout_problems,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
    sheet_standard_violations,
)
from gd_library_coach import PLUMBING_TOILETS_CATEGORY

CONCERN = "toilet leaks under the flush lever when flushing"
MODEL = "Style II 42070"
OM_TITLE = "Thetford Style II OM Permanent RV Toilet 42088"
FRAME = (36.0, 50.0, 540.0, 612.0)
FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "om42088_pypdf_pages.json"

JUNK = (
    "scarico",
    "opzioni",
    "preparazione",
    "inverno",
    "????",
    "poor flush",
    "flow rate",
    "blade",
    "frozen",
    "riser",
    "winteriz",
    "did the first",
    "next cited",
    "en/it/kr",
)


def _chunks():
    pages = json.loads(FIXTURE.read_text(encoding="utf-8"))
    chunks = []
    for page in pages:
        text = page["text"]
        # Same 900/120 windows as chunk_page_text in the library indexer.
        if len(text) <= 900:
            pieces = [text]
        else:
            pieces = []
            start = 0
            while start < len(text):
                pieces.append(text[start : start + 900].strip())
                if start + 900 >= len(text):
                    break
                start += 780
        for piece in pieces:
            if piece:
                chunks.append({"title": OM_TITLE, "page": page["page"], "excerpt": piece})
    chunks.append(
        {
            "title": "Thetford Water Valve Service Kit 42109",
            "page": 1,
            "excerpt": "Disconnect RV water supply from toilet.",
        }
    )
    chunks.append(
        {
            "title": "Thetford Vacuum Breaker Kit 34123/34122",
            "page": 2,
            "excerpt": "Connect RV water supply line to Toilet.",
        }
    )
    return chunks


def _pdf_text(pdf: bytes) -> str:
    import pymupdf

    doc = pymupdf.open(stream=pdf, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


class TestThetfordFlushLeakSheet(unittest.TestCase):
    def setUp(self):
        self.proc = compile_bay_procedure(
            concern=CONCERN,
            brand="Thetford",
            model=MODEL,
            category=PLUMBING_TOILETS_CATEGORY,
            chunks=_chunks(),
        )

    def test_bay_order_is_the_four_leak_checks(self):
        text = procedure_plain_text(self.proc).lower()
        self.assertIn("water supply line connection at the water valve", text)
        self.assertIn("weeps at the pedal", text)
        self.assertIn("vacuum breaker leaks while flushing", text)
        self.assertIn("flange", text)
        for junk in JUNK:
            self.assertNotIn(junk, text, junk)
        self.assertEqual(sheet_standard_violations(procedure_body_text(self.proc)), [])

    def test_flowchart_follows_the_leak_checks(self):
        decisions = [node.text.lower() for node in self.proc.flowchart.nodes if node.kind == "decision"]
        self.assertEqual(len(decisions), 4)
        joined = " | ".join(decisions)
        self.assertLess(joined.find("supply connection"), joined.find("weeping"))
        self.assertLess(joined.find("weeping"), joined.find("vacuum breaker"))
        self.assertLess(joined.find("vacuum breaker"), joined.find("flange"))
        labels = {}
        for edge in self.proc.flowchart.edges:
            if edge.label:
                labels.setdefault(edge.from_id, set()).add(edge.label.upper())
        for node in self.proc.flowchart.nodes:
            if node.kind == "decision":
                self.assertEqual(labels.get(node.id), {"YES", "NO"}, node.text)
        self.assertNotIn("did the first", " ".join(node.text.lower() for node in self.proc.flowchart.nodes))

    def test_sources_are_the_troubleshooting_page_and_the_two_kits(self):
        titles = " ".join((src.get("title") or "") for src in self.proc.sources).lower()
        self.assertIn("42088", titles)
        self.assertIn("42109", titles)
        self.assertIn("34122", titles)
        self.assertIn("34123", titles)
        self.assertTrue(
            any("42088" in (src.get("title") or "") and src.get("page") == 3 for src in self.proc.sources)
        )
        self.assertTrue(
            any("42109" in (src.get("title") or "") and src.get("page") == 1 for src in self.proc.sources)
        )
        quotes = " ".join((src.get("excerpt") or "") for src in self.proc.sources).lower()
        for junk in JUNK:
            self.assertNotIn(junk, quotes, junk)
        self.assertTrue(
            any(
                "water valve" in (src.get("excerpt") or "").lower()
                or "vacuum breaker" in (src.get("excerpt") or "").lower()
                or "flange" in (src.get("excerpt") or "").lower()
                for src in self.proc.sources
                if src.get("page") == 3
            )
        )
        pages = {src.get("page") for src in self.proc.sources if "42088" in (src.get("title") or "")}
        self.assertEqual(pages, {3})
        for src in self.proc.sources:
            excerpt = src.get("excerpt") or ""
            self.assertNotRegex(excerpt, r"disconnect rv water supply", excerpt)
            self.assertNotRegex(excerpt, r"connect rv water supply line to toilet", excerpt)

    def test_pdf_drops_the_junk_and_keeps_the_checks(self):
        trace = []
        pdf = render_bay_procedure_pdf(self.proc, trace=trace)
        problems = layout_problems(trace)
        self.assertEqual(problems, [], problems[:8])
        rects = flowchart_node_rects(self.proc.flowchart, *FRAME)
        self.assertEqual(flowchart_boxes_overlap(rects, gap=6.0), [])
        low = _pdf_text(pdf).lower()
        self.assertIn("supply connection", low)
        self.assertIn("weeping", low)
        self.assertIn("vacuum breaker", low)
        self.assertIn("flange", low)
        self.assertIn("42109", low)
        self.assertIn("34122", low)
        self.assertIn("42088", low)
        for junk in ("scarico", "opzioni", "preparazione", "????", "poor flush", "did the first"):
            self.assertNotIn(junk, low, junk)
        self.assertNotIn("disconnect rv water supply", low)
        self.assertNotIn("connect rv water supply line to toilet", low)


if __name__ == "__main__":
    unittest.main()
