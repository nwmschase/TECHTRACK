"""Brand and model filters for library search, GD retrieval, and the Bay PDF.

Does not import rv_techtrack. Empty metadata must keep the previous brand match.
"""
import unittest
from pathlib import Path

import library_bulk_import as bulk
from gd_library_coach import (
    chunk_matches_asked_brand,
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


class TestModelList(unittest.TestCase):
    pass


