"""Bay procedure PDF layout: text stays inside its shape, and nothing overlaps.

The drawing pass records a bounding box for every shape, bar, and glyph run.
layout_problems fails when text leaves its owner (ellipse and diamond use the
real curve) or when two drawn elements occupy the same spot.
"""
import unittest

from bay_procedure import (
    BayProcedure,
    FlowEdge,
    FlowNode,
    Flowchart,
    compile_bay_procedure,
    flowchart_boxes_overlap,
    flowchart_node_rects,
    layout_problems,
    render_bay_procedure_pdf,
)

FRAME = (36.0, 50.0, 540.0, 612.0)

# Locked shop cases plus the generic sheets that have no locked path.
CASES = (
    ("facr", "FACR08 freeze up interior leak condensate", "Furrion", "FACR08", "Air Conditioning"),
    (
        "ice",
        "icing up on rear wall — only about half from the top down",
        "Furrion",
        "FCR10DCGTA-BL",
        "Refrigerators",
    ),
    (
        "dial",
        "temperature dial OFF but compressor still running, freezer frozen solid, overcooling",
        "Furrion",
        "Furrion FCR10DCGTA-BG-PWH",
        "Refrigerators",
    ),
    (
        "bal",
        "BAL Soft-Touch SS 5.1 electric tongue jack dead. Other stabilizers and panel lights work. "
        "Motor OK on direct 12V. Coupler OK.",
        "BAL",
        "Soft-Touch SS 5.1",
        "Leveling",
    ),
    (
        "firefly",
        "Manual Mode dump works. Auto works. Touch pad flashes then returns to the home screen.",
        "",
        "Level Up Advantage 807662",
        "Leveling",
    ),
    (
        "coleman",
        "Coleman-Mach 2111-0001 ran then went dead. Fan High is dead.",
        "Coleman-Mach",
        "2111-0001",
        "Air Conditioning",
    ),
    (
        "e2",
        "FCR10 E2 fan fault current on the freezer evaporator fan",
        "Furrion",
        "FCR10",
        "Refrigerators",
    ),
    (
        "furnace",
        "Suburban NT-20SEQT furnace will not light. Blower runs.",
        "Suburban",
        "NT-20SEQT",
        "Furnaces",
    ),
)

_LONG = (
    "The rooftop assembly must be proved through a full cool cycle before you "
    "condemn the sealed system or the rooftop assembly. "
)


def _stress_procedure() -> BayProcedure:
    """Long wrapped lines, plus a cross-column branch that must stay in the gutter."""
    return BayProcedure(
        concern=_LONG * 3,
        brand="Furrion",
        model="FACR08",
        category="Air Conditioning",
        pattern_means=_LONG * 4,
        flowchart=Flowchart(
            readable=True,
            nodes=[
                FlowNode("s", "start", _LONG, 0.50, 0.08, w=420, h=80),
                FlowNode(
                    "d1",
                    "decision",
                    "Is the drain restricted or the pan iced after a full cool cycle?",
                    0.22,
                    0.28,
                    w=240,
                    h=110,
                ),
                FlowNode("n1", "end", _LONG, 0.78, 0.28, w=220, h=80),
                FlowNode("p2", "process", _LONG, 0.22, 0.52, w=280, h=90),
                FlowNode(
                    "d2",
                    "decision",
                    "Does cooling hold through a full cool cycle before you condemn the sealed system?",
                    0.50,
                    0.52,
                    w=220,
                    h=110,
                ),
                FlowNode(
                    "y2",
                    "end",
                    "Drain is clear and cooling holds. That is the confirmed correction.",
                    0.22,
                    0.82,
                    w=260,
                    h=80,
                ),
                FlowNode("n2", "end", _LONG, 0.78, 0.82, w=220, h=80),
            ],
            edges=[
                FlowEdge("s", "d1"),
                FlowEdge("d1", "p2", "YES", "bottom", "top"),
                FlowEdge("d1", "n1", "NO", "right", "left"),
                FlowEdge("p2", "y2", "YES", "bottom", "top"),
                FlowEdge("p2", "d2", "NO", "right", "left"),
                FlowEdge("d2", "n2", "YES", "right", "left"),
                FlowEdge("d2", "y2", "NO", "bottom", "right"),
            ],
        ),
        bay_order=[_LONG * 2] * 10,
        do_not=[_LONG] * 4,
        sources=[
            {"title": "Rooftop assembly manual", "page": i, "excerpt": _LONG * 2}
            for i in range(1, 6)
        ],
        flow_tall=True,
    )


def _assert_clean(testcase, proc, label):
    trace = []
    pdf = render_bay_procedure_pdf(proc, trace=trace)
    testcase.assertTrue(pdf.startswith(b"%PDF"), label)
    testcase.assertGreater(len(trace), 8, label)
    problems = layout_problems(trace)
    testcase.assertEqual(problems, [], (label, problems[:12]))
    if proc.flowchart.nodes:
        rects = flowchart_node_rects(proc.flowchart, *FRAME)
        hits = flowchart_boxes_overlap(rects, gap=14.0)
        testcase.assertEqual(hits, [], (label, hits))


class TestBayPdfLayout(unittest.TestCase):
    def test_known_cases_have_no_overlap_or_overflow(self):
        for label, concern, brand, model, category in CASES:
            proc = compile_bay_procedure(
                concern=concern, brand=brand, model=model, category=category
            )
            _assert_clean(self, proc, label)

    def test_long_text_stress_has_no_overlap_or_overflow(self):
        _assert_clean(self, _stress_procedure(), "stress")
