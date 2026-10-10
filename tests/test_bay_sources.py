"""SOURCES cite a human title, a whole sentence, and this procedure only."""
import re
import unittest

from bay_procedure import (
    clean_source_excerpt,
    compile_bay_procedure,
    human_source_title,
    polish_bay_sources,
)

_FRAGMENT_WORDS = {"er", "anel", "s", "tion", "ing", "ed"}
_SHORT_OK = {"a", "i", "if", "do", "no", "ok", "be"}


def _title_is_raw_filename(title: str) -> bool:
    text = (title or "").strip()
    if not text or re.search(r"\s", text):
        return False
    return bool(re.search(r"[-_]", text) or re.search(r"\.(pdf|docx?|txt)$", text, re.I))


def _snippet_is_partial(excerpt: str) -> bool:
    words = (excerpt or "").strip().split()
    if not words:
        return False
    first = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.]+$", "", words[0])
    if not first:
        return True
    if first.lower() in _FRAGMENT_WORDS:
        return True
    letters = re.sub(r"[^A-Za-z]", "", first)
    if letters and len(letters) <= 2 and letters.lower() not in _SHORT_OK:
        return True
    if first[0].islower():
        return True
    return False


def _assert_source_quality(testcase, proc, *, required, forbidden):
    blob_titles = []
    for src in proc.sources:
        title = src.get("title") or ""
        excerpt = (src.get("excerpt") or "").strip()
        blob_titles.append(title)
        testcase.assertFalse(_title_is_raw_filename(title), title)
        testcase.assertNotRegex(title, r"(?<!\S)[A-Za-z0-9]+(?:-[A-Za-z0-9.]+){2,}(?!\S)")
        if excerpt:
            testcase.assertFalse(_snippet_is_partial(excerpt), excerpt)
            testcase.assertTrue(excerpt[-1] in ".!?", excerpt)
            testcase.assertNotIn("...", excerpt)
    hay = "\n".join(
        f"{src.get('title') or ''} {src.get('excerpt') or ''}" for src in proc.sources
    ).lower()
    for needle in required:
        testcase.assertIn(needle.lower(), hay, hay)
    for banned in forbidden:
        testcase.assertNotIn(banned.lower(), hay, hay)


FLAT_RATE = {
    "title": "Flat-Rate-Guide",
    "page": 1,
    "excerpt": "TOR 20300000 REAR LEVELING JACK MOTOR. Replace the rear leveling jack motor.",
}
RAW_FUSE = {
    "title": "Furrion-Fridge-Fuse-Location",
    "page": 3,
    "excerpt": (
        "er is the 15A fuse in the front vent. Locate the fuse location before any other check."
    ),
}

BAL_CONCERN = (
    "BAL Soft-Touch SS 5.1 electric tongue jack dead. "
    "Other stabilizers and panel lights work. Motor OK on direct 12V. Coupler OK."
)
BAL_NOISE = [
    {
        "title": "BAL-5.1-SS-Troubleshooting-Guide",
        "page": 1,
        "excerpt": (
            "anel in place before the test. Prove 12V at the soft-touch panel "
            "before you condemn the jack."
        ),
    },
    FLAT_RATE,
    {
        "title": "BAL-Power-C-Jack-Troubleshooting-Check-List",
        "page": 1,
        "excerpt": (
            "Make sure the motor turns in both directions. If the motors will not "
            "turn in both directions with an alternative power source, repair the motor leads."
        ),
    },
    {
        "title": "20300605-SS-5.1-User-Manual-2nd-Gen",
        "page": 1,
        "excerpt": "s illuminate when the switch is pressed.",
    },
    {
        "title": "BAL tongue jack coupler",
        "page": 2,
        "excerpt": "Replace the coupler 21700072. Shear pin. Coupler replacement is the repair.",
    },
]


class TestSourceTitleAndSnippet(unittest.TestCase):
    def test_filename_becomes_a_human_title_and_metadata_wins(self):
        self.assertEqual(
            human_source_title("BAL-Power-C-Jack-Troubleshooting-Check-List"),
            "BAL Power C-Jack Troubleshooting Check List",
        )
        self.assertEqual(
            human_source_title("20300605-SS-5.1-User-Manual-2nd-Gen.pdf"),
            "SS 5.1 User Manual 2nd Gen",
        )
        self.assertEqual(
            human_source_title("BAL-5.1-SS-Troubleshooting-Guide"),
            "BAL 5.1 SS Troubleshooting Guide",
        )
        self.assertEqual(
            human_source_title("BAL-Leveling-and-Stabilizing-System-Part-Identification"),
            "BAL Leveling and Stabilizing System Part Identification",
        )
        self.assertEqual(
            human_source_title("", "library/20300605-SS-5.1-User-Manual-2nd-Gen.pdf"),
            "SS 5.1 User Manual 2nd Gen",
        )
        kept = "BAL SS 5.1 Stabilizing System INS.STA.001"
        self.assertEqual(human_source_title(kept, "raw/BAL-Power-C-Jack.pdf"), kept)
        self.assertEqual(
            human_source_title("Furrion FCR08/FCR10 SM CCD-0008122"),
            "Furrion FCR08/FCR10 SM CCD-0008122",
        )

    def test_snippet_starts_on_a_whole_sentence(self):
        guide = clean_source_excerpt(
            "er is OEM installed on this coach. The tongue panel is the prove when only the tongue jack is dead."
        )
        self.assertNotIn("er is", guide.lower())
        self.assertTrue(guide.startswith("The tongue panel"))
        self.assertEqual(clean_source_excerpt("s illuminate when the switch is pressed."), "")
        self.assertEqual(
            clean_source_excerpt("anel in place before the test. Prove 12V at the soft-touch panel tongue channel."),
            "Prove 12V at the soft-touch panel tongue channel.",
        )
        kept = clean_source_excerpt(
            "Make sure the motor turns in both directions. If the motors will not turn, repair the leads."
        )
        self.assertTrue(kept.startswith("Make sure the motor turns in both directions."))

    def test_flat_rate_rear_jack_is_off_a_tongue_sheet(self):
        polished = polish_bay_sources(
            [
                {
                    "title": "BAL SS 5.1 Stabilizing System INS.STA.001",
                    "page": None,
                    "excerpt": (
                        "Tongue jack only dead, stabilizers and panel lights working: prove 12V "
                        "at the soft-touch panel tongue channel. No voltage there means panel 20300427."
                    ),
                },
                FLAT_RATE,
                BAL_NOISE[2],
                BAL_NOISE[3],
            ],
            locked_count=1,
            topic_text="tongue jack soft-touch panel 20300427 pigtail",
            path_kind="bal_tongue",
        )
        hay = " ".join(f"{s['title']} {s['excerpt']}" for s in polished).lower()
        self.assertNotIn("ins.sta.001", hay)
        self.assertIn("bal power c-jack troubleshooting check list", hay)
        self.assertNotIn("20300000", hay)
        self.assertNotIn("rear leveling", hay)
        self.assertNotIn("flat rate", hay)
        self.assertNotIn("s illuminate", hay)
        self.assertNotIn("20300605", hay)


class TestLockedSourceRegression(unittest.TestCase):
    def test_locked_sheets_keep_known_cites_and_drop_bad_sources(self):
        cases = [
            {
                "concern": "FACR08 freeze up interior leak condensate",
                "brand": "Furrion",
                "model": "FACR08",
                "category": "Air Conditioning",
                "chunks": [
                    FLAT_RATE,
                    RAW_FUSE,
                    {
                        "title": "Coleman-Mach-12VDC-wall-thermostat",
                        "page": 2,
                        "excerpt": "Pin 5 is Fan High on the wall thermostat.",
                    },
                    {
                        "title": "Furrion-Rooftop-HVAC-Troubleshooting-Service-Manual",
                        "page": 4,
                        "excerpt": (
                            "anel is iced over. Clear the condensate drain and confirm "
                            "water leaves the pan."
                        ),
                    },
                ],
                "required": ["ccd-0007990", "ccd-0008666", "rooftop hvac"],
                "forbidden": [
                    "flat-rate-guide",
                    "flat rate",
                    "20300000",
                    "rear leveling",
                    "coleman",
                    "peacemaker",
                    "anel is",
                    "er is",
                    "s illuminate",
                    "15a",
                ],
            },
            {
                "concern": BAL_CONCERN,
                "brand": "BAL",
                "model": "Soft-Touch SS 5.1",
                "category": "Leveling",
                "chunks": BAL_NOISE,
                "required": [
                    "bal 5.1 ss troubleshooting guide",
                    "bal power c-jack troubleshooting check list",
                    "both directions",
                    "prove 12v at the soft-touch panel",
                ],
                "forbidden": [
                    "flat-rate-guide",
                    "flat rate",
                    "20300000",
                    "rear leveling",
                    "20300605",
                    "bal-power-c-jack",
                    "anel in",
                    "er is",
                    "s illuminate",
                    "21700072",
                    "replace the coupler",
                ],
            },
            {
                "concern": (
                    "temperature dial OFF but compressor still running, "
                    "freezer frozen solid, overcooling"
                ),
                "brand": "Furrion",
                "model": "Furrion FCR10DCGTA-BG-PWH",
                "category": "Refrigerators",
                "chunks": [
                    FLAT_RATE,
                    RAW_FUSE,
                    {
                        "title": "Furrion-FCR-Thermostat-CT",
                        "page": 31,
                        "excerpt": (
                            "s illuminate on the board. Open flag terminals C (blue) and "
                            "T (black) and leave them open with no jumper."
                        ),
                    },
                ],
                "required": ["ccd-0008122", "no jumper"],
                "pages": [31, 43],
                "forbidden": [
                    "flat rate",
                    "20300000",
                    "rear leveling",
                    "fuse location",
                    "15a",
                    "s illuminate",
                    "er is",
                ],
            },
            {
                "concern": "icing up on rear wall — only about half from the top down",
                "brand": "Furrion",
                "model": "Furrion FCR10DCGTA-BG-PWH",
                "category": "Refrigerators",
                "chunks": [
                    FLAT_RATE,
                    RAW_FUSE,
                    {
                        "title": "Furrion-FCR-Ice-and-Moisture",
                        "page": 36,
                        "excerpt": (
                            "er is frost on the rear wall. Ice and Moisture on the back "
                            "wall is the moisture path for this fridge."
                        ),
                    },
                ],
                "required": ["ccd-0008122", "ice and moisture"],
                "pages": [36],
                "forbidden": [
                    "flat rate",
                    "20300000",
                    "rear leveling",
                    "fuse location",
                    "15a",
                    "er is",
                    "s illuminate",
                ],
            },
            {
                "concern": (
                    "Manual Mode dump works. Auto works. "
                    "Touch pad flashes then returns to the home screen."
                ),
                "brand": "",
                "model": "Level Up Advantage 807662",
                "category": "Leveling",
                "chunks": [
                    FLAT_RATE,
                    {
                        "title": "Level-Up-Advantage-Manual-Mode",
                        "page": 2,
                        "excerpt": (
                            "s illuminate on the panel. Leave the rubber-boot terminator "
                            "in and unplug the Firefly CAN cable only."
                        ),
                    },
                ],
                "required": ["ti-005", "qr-092"],
                "forbidden": [
                    "flat rate",
                    "20300000",
                    "rear leveling",
                    "s illuminate",
                    "level-up-advantage",
                ],
            },
        ]
        for case in cases:
            proc = compile_bay_procedure(
                concern=case["concern"],
                brand=case["brand"],
                model=case["model"],
                category=case["category"],
                chunks=case["chunks"],
            )
            _assert_source_quality(
                self,
                proc,
                required=case["required"],
                forbidden=case["forbidden"],
            )
            got_pages = {src.get("page") for src in proc.sources}
            for page in case.get("pages") or []:
                self.assertIn(page, got_pages, proc.sources)


if __name__ == "__main__":
    unittest.main()
