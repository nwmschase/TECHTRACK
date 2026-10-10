"""Brand and model filters for library search, GD retrieval, and the Bay PDF.

Does not import rv_techtrack. Empty metadata must keep the previous brand match.
"""
import unittest
from pathlib import Path

import library_bulk_import as bulk
from bay_procedure import bay_brand_retrieval
from gd_library_coach import (
    chunk_matches_asked_brand,
    filter_chunks_for_unit,
    identity_from_page,
    model_list_allows,
    page_identity_blob,
    page_is_ground_control_family,
)

ROOT = Path(__file__).resolve().parents[1]


class TestLibraryRecordMatch(unittest.TestCase):
    def test_query_hits_models_keywords_and_clean_title(self):
        doc = {
            "title": "CCD-0001750",
            "clean_title": "Schwintek In-Wall Service",
            "keywords": "slide motor; E2; 1234567",
            "models": "PSX1",
            "brand": "Lippert",
        }
        self.assertTrue(bulk.library_record_matches(doc, query="psx1"))
        self.assertTrue(bulk.library_record_matches(doc, query="e2"))
        self.assertTrue(bulk.library_record_matches(doc, query="1234567"))
        self.assertTrue(bulk.library_record_matches(doc, query="schwintek"))
        self.assertFalse(bulk.library_record_matches(doc, query="awning missing"))

    def test_brand_column_is_authoritative_and_null_brand_still_matches_text(self):
        stored = {
            "title": "CCD-0001750",
            "keywords": "Dometic compressor mentioned",
            "brand": "Lippert",
        }
        self.assertFalse(bulk.library_record_matches(stored, brand="Dometic"))
        self.assertTrue(bulk.library_record_matches(stored, brand="Lippert"))
        older = {"title": "Dometic fridge", "keywords": "no cool", "brand": None}
        self.assertTrue(bulk.library_record_matches(older, brand="Dometic"))
        self.assertTrue(bulk.library_record_matches(older, query="no cool"))
        self.assertFalse(bulk.library_record_matches(older, query="awning"))
        self.assertTrue(bulk.library_record_matches(older, brand="(any)", query="fridge"))

    def test_model_box_uses_the_list_and_falls_back_to_the_blob(self):
        listed = {"title": "CCD", "keywords": "", "models": "FCR10DCGTA-BL"}
        self.assertTrue(bulk.library_record_matches(listed, model="FCR10"))
        self.assertFalse(bulk.library_record_matches(listed, model="FACR13"))
        older = {"title": "FCR10 service manual", "keywords": "fridge", "models": ""}
        self.assertTrue(bulk.library_record_matches(older, model="FCR10"))
        self.assertFalse(bulk.library_record_matches(older, model="FACR13"))


class TestBrandMatchDoesNotRegress(unittest.TestCase):
    def test_title_brand_without_new_arguments(self):
        self.assertTrue(
            chunk_matches_asked_brand("Furrion FCR10 service", "", "compressor", {"furrion"})
        )
        self.assertFalse(
            chunk_matches_asked_brand("Furrion FCR10 service", "", "compressor", {"lippert"})
        )

    def test_stored_brand_overrides_the_title(self):
        self.assertTrue(
            chunk_matches_asked_brand(
                "CCD-0001750", "", "", {"lippert"}, brand="Lippert"
            )
        )
        self.assertFalse(
            chunk_matches_asked_brand(
                "CCD-0001750", "", "", {"furrion"}, brand="Lippert"
            )
        )
        self.assertFalse(
            chunk_matches_asked_brand(
                "Furrion FCR10 service",
                "furrion",
                "compressor",
                {"furrion"},
                brand="Dometic",
            )
        )

    def test_empty_metadata_keeps_the_same_page_identity(self):
        bare = page_identity_blob("Ground Control", "level", "zero point", "gc.pdf")
        same = page_identity_blob(
            "Ground Control",
            "level",
            "zero point",
            "gc.pdf",
            brand="",
            models="",
            product_line="",
            doc_number="",
            clean_title="",
        )
        self.assertEqual(bare, same)


class TestModelList(unittest.TestCase):
    def test_compact_model_numbers_and_non_matches(self):
        self.assertTrue(bulk.listed_models_match("FCR10", "Furrion FCR10DCGTA-BL"))
        self.assertTrue(bulk.listed_models_match("FCR10DCGTA-BL", "FCR10"))
        self.assertFalse(bulk.listed_models_match("FACR13", "Furrion FCR10DCGTA-BL"))
        self.assertTrue(bulk.listed_models_match("2111-0001", "Coleman-Mach 2111-0001"))
        self.assertTrue(model_list_allows("", "Lippert PSX1"))
        self.assertTrue(model_list_allows("PSX1", "Lippert"))
        self.assertFalse(model_list_allows("PSX1", "Lippert Schwintek"))
        self.assertTrue(model_list_allows("Schwintek; In-Wall", "Lippert Schwintek"))
        self.assertFalse(model_list_allows("Schwintek", "Lippert PSX1"))
        self.assertTrue(model_list_allows("PSX1", "Lippert PSX1"))

    def test_models_column_counts_for_ground_control_identity(self):
        page = {"title": "CCD", "excerpt": "manual level", "file_path": "ccd.pdf", "models": "343633"}
        self.assertTrue(page_is_ground_control_family(identity_from_page(page)))
        kept = filter_chunks_for_unit(
            [
                {"title": "Level Up", "excerpt": "807662 hydraulic", "file_path": "level.pdf"},
                page,
            ],
            "",
            "343633",
            "",
        )
        self.assertEqual(kept, [page])


class TestBayBrandAndModel(unittest.TestCase):
    def test_stored_brand_keeps_a_title_that_does_not_say_the_brand(self):
        page = {"title": "CCD-0001750", "excerpt": "slide motor", "brand": "Lippert", "page": 1}
        kept, miss = bay_brand_retrieval([page], "", "Lippert PSX1", "slide will not move")
        self.assertFalse(miss)
        self.assertEqual([p["title"] for p in kept], ["CCD-0001750"])
        dropped, dropped_miss = bay_brand_retrieval([page], "", "Furrion FCR10", "no cool")
        self.assertTrue(dropped_miss)
        self.assertEqual(dropped, [])

    def test_page_without_a_brand_column_follows_the_title(self):
        page = {"title": "Furrion FCR10 service", "excerpt": "compressor", "page": 1}
        kept, miss = bay_brand_retrieval([page], "", "Furrion FCR10", "no cool")
        self.assertFalse(miss)
        self.assertEqual(kept[0]["title"], page["title"])
        other, other_miss = bay_brand_retrieval([page], "", "Lippert", "slide")
        self.assertTrue(other_miss)
        self.assertEqual(other, [])

    def test_keywords_match_a_lippert_ask(self):
        page = {
            "title": "CCD-0001750",
            "keywords": "Lippert slide motor",
            "excerpt": "motor",
            "page": 2,
        }
        kept, miss = bay_brand_retrieval([page], "", "Lippert", "slide")
        self.assertFalse(miss)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["keywords"], "Lippert slide motor")

    def test_model_list_drops_a_different_lippert_manual(self):
        pages = [
            {"title": "CCD-A", "excerpt": "jack", "brand": "Lippert", "models": "PSX1", "page": 1},
            {
                "title": "CCD-B",
                "excerpt": "slide",
                "brand": "Lippert",
                "models": "Schwintek; In-Wall",
                "page": 2,
            },
        ]
        kept, miss = bay_brand_retrieval(pages, "", "Lippert Schwintek", "in wall")
        self.assertFalse(miss)
        self.assertEqual([p["title"] for p in kept], ["CCD-B"])


class TestSearchWiring(unittest.TestCase):
    def test_library_and_gd_search_use_the_new_filters(self):
        src = (ROOT / "rv_techtrack.py").read_text(encoding="utf-8")
        search = src.split("def search_manual_chunks(", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("model_list_allows", search)
        self.assertIn("_lookup_brand", search)
        self.assertIn("_lookup_models", search)
        self.assertIn("WATER_HEATERS_CATEGORY", search)
        library = src.split("# DOCUMENT LIBRARY", 1)[1].split("# SAFETY", 1)[0]
        self.assertIn("library_record_matches", library)
        self.assertIn("title, keyword, or model", library)
        self.assertNotIn("process_next_batch", src)
