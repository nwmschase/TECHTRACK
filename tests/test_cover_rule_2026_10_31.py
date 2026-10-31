"""Cover-page rule (2026-10-31): page 1 is a cover only when it holds nothing but a title, logo, model / document numbers,
an address or legal text. A page 1 with a diagram, a parts table, steps, specs or slide text is content and is not scored
0.3x. Offline: no network, no API, no real library needed."""
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pagefinder import pagetext as PT
from pagefinder import build_index as B
from pagefinder import search as S

OWNERS_COVER = "Ground Control\n®\nTT Leveling System\nwith LCD Touch Pad\nOWNER'S MANUAL\nScan for Product Support\n"
DOMETIC_COVER = ("1\nDIAGNOSTIC SERVICE MANUAL\nROOF TOP AC/HP SYSTEMS\nTROUBLESHOOTING\nUSA\nService Office\nDometic Corporation\n"
                 "2320 Industrial Parkway\nElkhart, IN 46516\nCANADA\nDometic Corporation\n46 Zatonski Unit 3\nBrantford, Ontario\n"
                 "CANADA N3T 5L8\nForm No. 3311071.017  01/12\n©2007 Dometic Corporation\nLaGrange, IN 46761\n")
FURRION_TSM_COVER = ("RV FURNACES\nMODEL (LIPPERT PN)\nFFG20FA (2023033712)\nFFG30FA (2022121947)\nFFG35FA (2022121948)\n"
                     "FFG20RA (2023033713)\nTROUBLESHOOTING AND SERVICE MANUAL\n* Picture shown here is for reference only.\n"
                     "This manual contains the product's basic information, safety, maintenance, replaceable parts and troubleshooting.\n")
WARNING_COVER = ("Improper installation,\nadjustment, alteration,\nservice or maintenance\ncan cause personal\ninjury or property\n"
                 "damage. Refer to this\nmanual. For assistance or additional\ninformation consult a qualified installer, service\n"
                 "agency, or the gas\nsupplier.\nWARNING\nN10DCX\n")
PARTS_TABLE = ("Rev: 08.23.18\nPage 1\nCCD-0001933\nELECTRIC STABILIZERS - AUTO SHUT OFF\nTI-070\nA\nB\nC\nCallout\nDescription\n"
               "Quantity\nA\nMounting Bracket\n2\nB\n12V DC Motor - 138445\n1\nC\nSwitch Assembly 162307\n1\n")
LABELED_ASSEMBLY = ("Web: - https://support.lci1.com/documentation/ - Ph: 432-LIPPERT (432-547-7378) - Email: customerservice@lci1.com\n"
                    "SLIDE-OUTS\nSLIMRACK® SLIDE-OUT\nASSEMBLY\nRev: 11.09.23\nCCD-0002113\nMotor\nEnd Brackets\nGear Rack\nDrive Shaft\n"
                    "Spur Gear\nIdler Shaft\nBearing Block\nColumn Assembly\n")
LETTER_CALLOUTS = ("Rev: 08.29.18\nPage 1\nCCD-0002092\nGROUND CONTROL® 2.0 6 POINT WIRING DIAGRAM\nTI-192\nFront of Coach\n"
                   "G\nI\nH\nK\nC\nE\nN\nJ\nF\nD\nB\nA\nM\n")
STEPS = ("REED SWITCH\nLIMIT SWITCH\nFULLY RETRACT THE JACK\nDISCONNECT THE TWO PRONG\nAUTOMOTIVE CONNECTOR FROM\nTHE SWITCH.\n"
         "REMOVE THE ALLEN HEAD SCREWS\n(#1) FROM THE TOP OF THE JACK\nREMOVE THE SWITCH AND ROD\nTIGHTEN THE NUTS (#2)\n")
NUMBERED = ("Lubrication Instructions\n1. Fully extend the slide-out room.\n2. Wipe the TOP of the slide-out arms free of any dirt.\n"
            "3. Apply the lube directly to the top of the slide-out arms.\n")
ABS_DECK = ("12/15/2022\n1\nANTI-LOCK BRAKE SYSTEM (ABS)\nOVERVIEW\nAnti-Lock Braking systems are designed to prevent wheel lock and\n"
            "enhance the steerability of the vehicle in emergency situations\n•\nHarsh braking\n•\nLoss of traction\n•\nEvasive maneuvers\n"
            "Designed for electromagnetic drum brakes\nIntegrates into OneControl\nQR Code Stickers\nMounting Orientation\n1\n2\n")
BED_TILT_DECK = "12/15/2022\n1\nSCHWINTEK BED TILT\nHead Assembly Support Frame\nBearing Block\nGear Rack\n1\n2\n"
MODEL_BULLETS_COVER = "• Classic\n• Americana\n• RM1350\n• RM3762 & RM3962\n• DMR702\n• 8-Series\nDOMETIC\nRefrigerators\n"
FURRION_FEATURES = ("Main Features\nHIGH EFFICIENCY\nDC COMPRESSOR\nPOWERFUL\nCOOLING\nBIG STORAGE\nVOLUME\nBUILT-IN\nQUIET OPERATION\n"
                    "VIBRATIONSMART™\nCLIMATESMART™\nFCR10DCGTA\n")
TOC = ("Owner's\nManual\n#888\nTable of Contents\n3\nIdentification Information\n4\nIntroduction\n5\nOperating the Step\n6\n"
       "Maintenance\n7\nTroubleshooting\n8\n")


def cover(text, n_pages=12, sheet=1):
    m, _ = PT.page_marks(dict(text=text, sheet=sheet), n_pages)
    return m['is_cover']


class CoverRule(unittest.TestCase):
    def test_real_covers_stay_covers(self):
        for name, t in [('owner', OWNERS_COVER), ('address/legal', DOMETIC_COVER), ('model list', FURRION_TSM_COVER),
                        ('warning text', WARNING_COVER), ('model bullets', MODEL_BULLETS_COVER), ('contents list', TOC)]:
            with self.subTest(name):
                self.assertEqual(cover(t), 1, PT.cover_signals(t))

    def test_content_on_page_1_is_not_a_cover(self):
        for name, t, sig in [('parts table', PARTS_TABLE, 'parts table'), ('labeled assembly', LABELED_ASSEMBLY, 'labels'),
                             ('letter callouts', LETTER_CALLOUTS, 'callouts'), ('imperative steps', STEPS, 'steps'),
                             ('numbered steps', NUMBERED, 'steps'), ('ABS deck', ABS_DECK, 'bullets'), ('bed tilt deck', BED_TILT_DECK, 'slides')]:
            with self.subTest(name):
                self.assertEqual(cover(t, n_pages=2), 0)
                self.assertIn(sig, PT.cover_signals(t))

    def test_one_page_doc_has_no_cover(self):
        self.assertEqual(cover(OWNERS_COVER, n_pages=1), 0)   # the only page of a doc is its content
        self.assertEqual(cover(OWNERS_COVER, n_pages=0), 0)

    def test_only_sheet_1_and_only_short_pages(self):
        self.assertEqual(cover(OWNERS_COVER, sheet=2), 0)
        long_page = OWNERS_COVER + ''.join(f'Line {i} of a long first page with text\n' for i in range(40))
        self.assertEqual(cover(long_page), 0)

    def test_marketing_feature_icons_stay_a_cover(self):
        # Furrion spec sheet page 1: product photo + feature icons; the spec table is on page 2 (choice recorded in COVER-FIX.md)
        self.assertEqual(cover(FURRION_FEATURES, n_pages=2), 1)

    def test_strict_marks_count_as_content(self):
        self.assertIn('is_parts', PT.cover_signals(OWNERS_COVER, dict(is_parts=1)))
        self.assertNotIn('is_troubleshooting', PT.cover_signals(OWNERS_COVER, dict(is_troubleshooting=1)))

    def test_ocr_of_a_product_photo_is_not_drawing_labels(self):
        t = "VE.Bus BMS V2\nProduct manual\nRev 07\n[OCR]\nCharge Disconnect\nPre-alarm\nRemote panel\nBattery Plus\nAux Input\nLoad Disconnect\n"
        self.assertNotIn('labels', PT.cover_signals(t))


class RemarkIndex(unittest.TestCase):
    def _index(self, rows):
        d = tempfile.mkdtemp(); path = os.path.join(d, 'index.sqlite')
        db = sqlite3.connect(path); db.executescript(B.SCHEMA)
        for doc_id, n, text, old in rows:
            db.execute("insert into docs(doc_id, app_id, title, brand, models, unit_type, doc_type, file_path, n_pages, status)"
                       " values(?,?,?,?,?,?,?,?,?,'active')", (doc_id, int(doc_id[1:]), 'T ' + doc_id, 'Lippert', '[]', 'Slideouts', 'parts-list', doc_id + '.pdf', n))
            for s in range(1, n + 1):
                db.execute('insert into pages values(?,?,?,?,?,?,?,?,?,?,0,?,0,0,0,0,0)',
                           (doc_id, s, s, 'assumed', text if s == 1 else f'page {s} text body', 'text', '', len(text), '[]', '[]', old if s == 1 else 0))
        db.commit(); db.close()
        return path

    def test_remark_in_place_only_changes_wrong_covers(self):
        path = self._index([('L1', 2, LABELED_ASSEMBLY, 1), ('L2', 12, OWNERS_COVER, 1), ('L3', 1, BED_TILT_DECK, 1)])
        ch = B.remark_covers_in_place(path)
        self.assertEqual(ch, {'L1': (1, 0), 'L3': (1, 0)})
        db = sqlite3.connect(path)
        self.assertEqual(dict(db.execute('select doc_id, is_cover from pages where pdf_sheet=1')), {'L1': 0, 'L2': 1, 'L3': 0})
        self.assertEqual(B.remark_covers_in_place(path), {})   # idempotent

    def test_page1_diagram_no_longer_scored_down_in_search_pages(self):
        import gd_tools
        rows = [('L1', 2, LABELED_ASSEMBLY, 1), ('L2', 3, OWNERS_COVER, 1)]
        path = self._index(rows)
        with mock.patch.object(S, 'MEANING_ON', False):
            lib = S.Library(db=path, app_db='')
            before = gd_tools.LibraryTools(lib).search_pages('gear rack drive shaft')
            B.remark_covers_in_place(path)
            lib2 = S.Library(db=path, app_db='')
            after = gd_tools.LibraryTools(lib2).search_pages('gear rack drive shaft')
        top_b = next(h for h in before['hits'] if h['doc_id'] == 'L1' and h['sheet'] == 1)
        top_a = next(h for h in after['hits'] if h['doc_id'] == 'L1' and h['sheet'] == 1)
        self.assertIn('cover', top_b.get('marks', []))
        self.assertNotIn('cover', top_a.get('marks', []))
        self.assertAlmostEqual(top_a['score'], round(top_b['score'] / 0.3, 3), delta=0.002)


if __name__ == '__main__':
    unittest.main()
