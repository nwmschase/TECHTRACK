"""LOCKED selector root-fix tests (Leader GO 2026-10-16 4:02 PM; RCA standard). One test per prior incident of the class
'weak-evidence document match accepted as confident and suppressing fallback', plus the F1 property test, F2 tie/threshold,
F3 needs-confirmation, B13 series/keyword/page-text evidence, file-availability fallback, and the R1 library audit."""
import itertools
import json
import os
import sqlite3
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import gd_official as go  # noqa: E402
import library_category_audit as audit  # noqa: E402


class Lib:
    def __init__(self, rows, text=None):
        self.rows, self.text = rows, text or {}

    def documents(self):
        return [dict(r) for r in self.rows]

    def docs_with_text(self, key, doc_ids):
        return {d: t for d, t in self.text.items() if d in doc_ids and key in t.lower().replace("-", "").replace(".", "")}

    def chunks(self, doc_id):
        return [{"page": 1, "text": self.text.get(doc_id, "Troubleshooting. Check the fuse.")}]


def sel(rows, model, cat, text=None, available=None, msg="not working"):
    return go.select_manual(Lib(rows, text), go.identify_unit([], msg, cat, model), available=available)


# ---------------- F1: unit values are never model tokens (property test) ----------------
NUMBERS = ["1", "12", "120", "240", "13500", "13,500", "6,000", "2.5", "0.5", "1500", "100"]
UNITS = ["V", "v", "VAC", "VDC", "volt", "volts", "A", "amp", "amps", "Ah", "AH", "mAh", "amp-hours", "W", "watt", "watts", "kW",
         "BTU", "btu", "BTUs", "BTUH", "lb", "lbs", "LB", "pound", "pounds"]
SEPS = ["", " ", "-"]
CONTEXTS = ["{v}", "Dometic Brisk II {v} air conditioner", "Furrion FCR08DCGTA {v} refrigerator", "jack rated {v}, model unknown"]


class TestF1UnitTokens(unittest.TestCase):
    def test_no_unit_value_is_ever_a_model_token(self):
        n = 0
        for num, unit, sep, ctx in itertools.product(NUMBERS, UNITS, SEPS, CONTEXTS):
            text = ctx.format(v=f"{num}{sep}{unit}")
            toks = go.model_tokens(text)
            keys = go.model_keys({"tokens": toks})
            digits = num.replace(",", "").replace(".", "")
            for k in keys:
                self.assertNotEqual(k, digits, (text, keys))
                self.assertFalse(go.is_unit_token(k), (text, keys))
                self.assertFalse(k.startswith(digits) and k[len(digits):] in {u.lower().replace("-", "") for u in UNITS}, (text, keys))
            unit_ = go.identify_unit([], text, "Refrigerators", text)
            self.assertFalse([t for t in unit_["tokens"] if go.is_unit_token(t)], (text, unit_["tokens"]))
            n += 1
        self.assertGreater(n, 3000)

    def test_thousand_btu_k_is_a_rating_but_4500k_is_a_model(self):
        for r in ["8K", "13.5K", "15 K", "13.5K/15K"]:
            self.assertEqual(go.model_keys({"tokens": go.model_tokens(f"Chill {r} R32")}), [], r)
        self.assertIn("4500k", go.model_keys({"tokens": go.model_tokens("MaxxFan 4500K")}))

    def test_real_model_survives_next_to_ratings(self):
        keys = go.model_keys({"tokens": go.model_tokens("Furrion FCR08DCGTA 12 V DC 13,500 BTU 50Ah")})
        self.assertEqual(keys, ["fcr08dcgta", "fcr08"])


# ---------------- F2: specificity, threshold, ties ----------------
A = {"id": 10, "title": "Acme 2000X Water Heater Troubleshooting Manual", "brand": "Acme", "models": "2000X", "doc_number": "AC-1"}
B = {"id": 11, "title": "Acme 2000X Water Heater Troubleshooting Guide", "brand": "Acme", "models": "2000X", "doc_number": "AC-2"}
A_DUP = dict(A, id=12)


class TestF2Specificity(unittest.TestCase):
    def test_tie_between_different_manuals_is_no_pick_in_any_order(self):
        for rows in ([A, B], [B, A]):
            r = sel(rows, "Acme 2000X", "Water Heaters")
            self.assertIsNone(r["doc"])
            self.assertEqual(r["how"], "ambiguous")
            self.assertIn("not guessing", r["miss_line"])

    def test_duplicate_uploads_of_one_manual_are_one_pick_in_any_order(self):
        self.assertEqual(sel([A, A_DUP], "Acme 2000X", "Water Heaters")["doc"]["id"], 10)
        self.assertEqual(sel([A_DUP, A], "Acme 2000X", "Water Heaters")["doc"]["id"], 10)

    def test_brand_only_match_is_not_found(self):
        r = sel([A], "Acme water heater, tag missing", "Water Heaters")
        self.assertIsNone(r["doc"])
        self.assertEqual(r["how"], "none")

    def test_exact_model_beats_series(self):
        series = {"id": 20, "title": "Acme 2000 Series Water Heater Manual", "brand": "Acme", "models": "2000", "doc_number": "S"}
        exact = {"id": 21, "title": "Acme Water Heater Service Manual", "brand": "Acme", "models": "", "doc_number": "E"}
        r = sel([series, exact], "Acme AX2000DE", "Water Heaters", text={21: "Model AX2000DE wiring"})
        self.assertEqual(r["doc"]["id"], 21)

    def test_ambiguous_or_weak_pick_runs_the_web_lookup(self):
        calls = []

        def web(unit):
            calls.append(unit)
            return {}

        go.official_turn("No hot water.", "Water Heaters", "Acme 2000X", [], library=Lib([A, B]),
                         chat_fn=lambda m, t, e: "Verify the complaint first.", pin_store={}, web_fetch_fn=web)
        self.assertEqual(len(calls), 1)


# ---------------- F3: every category maps; unknown type -> needs confirmation ----------------
LIBRARY_CATEGORIES = json.load(open(os.path.join(ROOT, "tests", "fixtures", "library_category_snapshot_2026-10-16.json")))["categories"]


class TestF3TypeConfirmation(unittest.TestCase):
    def test_every_library_category_maps_to_types(self):
        missing = [c for c in LIBRARY_CATEGORIES if c.strip().lower() not in go.CATEGORY_TYPES]
        self.assertEqual(missing, [])

    def test_unmapped_category_asks_the_tech(self):
        r = sel([A], "Acme 2000X", "Misc New Category")
        self.assertIsNone(r["doc"])
        self.assertEqual(r["how"], "needs_confirmation")
        out = go.official_turn("Not working.", "Misc New Category", "Acme 2000X", [], library=Lib([A]),
                               chat_fn=lambda m, t, e: "x", pin_store={})
        self.assertEqual(out["mode"], "confirm_type")
        self.assertIn("what kind of unit", out["reply"])

    def test_tech_answer_confirms_the_type(self):
        hist = [{"role": "user", "content": "Not working."}, {"role": "assistant", "content": "what kind of unit is it?"}]
        r = go.select_manual(Lib([A]), go.identify_unit(hist, "It's the water heater.", "Misc New Category", "Acme 2000X"))
        self.assertEqual(r["doc"]["id"], 10)

    def test_model_only_under_another_type_asks_instead_of_pinning(self):
        r = sel([A], "Acme 2000X", "Refrigerators")
        self.assertIsNone(r["doc"])
        self.assertEqual(r["how"], "needs_confirmation")
        self.assertIn("water heater", r["miss_line"])


# ---------------- B13: series key from one digit; keywords + page text are evidence ----------------
SUB124 = {"id": 124, "title": "Suburban Water Heater Master Service and Training Manual", "brand": "Suburban", "models": "",
          "doc_number": "", "keywords": "Suburban, water heater, service, training, SW6, SW10, no hot water"}
SUB_FURN = {"id": 125, "title": "Suburban SF-35 Furnace Service Manual", "brand": "Suburban", "models": "SF-35", "doc_number": "SF"}


class TestB13(unittest.TestCase):
    def test_sw6de_series_key(self):
        self.assertEqual(go.model_keys({"tokens": go.model_tokens("Suburban SW6DE")}), ["sw6de", "sw6"])

    def test_b13_pins_doc_124_from_page_text(self):
        r = sel([SUB_FURN, SUB124], "Suburban SW6DE", "Water Heaters", text={124: "Models SW6DE, SW6DEL, SW10DE"})
        self.assertEqual(r["doc"]["id"], 124)
        self.assertEqual(r["how"], "exact")

    def test_b13_pins_doc_124_from_keywords_series(self):
        r = sel([SUB_FURN, SUB124], "Suburban SW6DE", "Water Heaters")
        self.assertEqual(r["doc"]["id"], 124)
        self.assertEqual(r["how"], "series")

    def test_series_never_matches_a_longer_number(self):
        other = dict(SUB124, id=126, keywords="SW60 only", title="Suburban Water Heater SW60 Manual")
        self.assertIsNone(sel([other], "Suburban SW6DE", "Water Heaters")["doc"])


# ---------------- file availability (rule 11 CONTAINMENT moved into the selector) ----------------
class TestAvailability(unittest.TestCase):
    def test_unreachable_top_doc_falls_to_next_eligible(self):
        series = {"id": 30, "title": "Acme 2000 Water Heater Owner Manual", "brand": "Acme", "models": "", "doc_number": "O", "keywords": "AX2000"}
        r = sel([A, series], "Acme 2000X", "Water Heaters", available=lambda d: d["id"] != 10)
        self.assertNotEqual((r["doc"] or {}).get("id"), 10)
        self.assertIn((10, "file unreachable"), r["rejected"])

    def test_all_unreachable_is_not_found(self):
        r = sel([A], "Acme 2000X", "Water Heaters", available=lambda d: False)
        self.assertIsNone(r["doc"])
        self.assertEqual(r["how"], "none")


# ---------------- prior incidents of the class ----------------
class TestPriorIncidents(unittest.TestCase):
    def test_girard_fridge_never_for_a_water_heater(self):
        fridge = {"id": 40, "title": "Girard Refrigerator GRF-100 Service Manual", "brand": "Girard", "models": "GRF-100", "doc_number": "G1"}
        self.assertIsNone(sel([fridge], "Girard GSWH-2", "Water Heaters")["doc"])

    def test_thetford_never_assumed_for_an_unbranded_toilet(self):
        import bay_procedure as bp

        self.assertFalse(bp.is_thetford_flush_leak_context("Plumbing / Toilets", "RV toilet", "leaks at the pedal"))
        self.assertTrue(bp.is_thetford_flush_leak_context("Plumbing / Toilets", "Thetford Aqua-Magic Style II", "leaks at the pedal"))
        pages = [{"title": "Thetford Style II Manual", "page": 3, "excerpt": "Leak"}]
        kept, _miss = bp.bay_brand_retrieval(pages, "Plumbing / Toilets", "RV toilet", "leaks")
        self.assertEqual(len(kept), 1)  # no brand named -> nothing assumed, nothing filtered by an invented brand

    def test_maxxfan_remote_page_rises_by_evidence_not_page_number(self):
        import bay_procedure as bp

        pages = [{"title": "MaxxAir MaxxFan 11F90000K", "page": 2, "excerpt": "Installation of the ceiling unit"},
                 {"title": "MaxxAir MaxxFan 11F90000K", "page": 9, "excerpt": "Remote: low battery bars, transmit symbol; aim remote at the fan; 4500K"},
                 {"title": "Furrion vent fan", "page": 1, "excerpt": "remote not working low battery"}]
        top = bp.rank_pages_for_concern(pages, "MaxxFan 4500K", "remote not working, low battery", limit=3)
        self.assertEqual(top[0]["page"], 9)
        self.assertEqual(top[-1]["title"], "Furrion vent fan")

    def test_unknown_brand_never_borrows(self):
        lippert = {"id": 50, "title": "Lippert 3100 Leveling Troubleshooting", "brand": "Lippert", "models": "3100", "doc_number": "L"}
        self.assertIsNone(sel([lippert], "Brinkley Z 3100", "Leveling")["doc"])

    def test_rc30_rating_never_matches_and_exact_wins(self):
        fan = {"id": 283, "title": 'Furrion 14" 12V Vent Fan Troubleshooting and Service Manual', "brand": "Furrion",
               "models": "FVF14D90A2", "doc_number": "CCD-0010491"}
        fridge = {"id": 298, "title": "Furrion Arctic 8 & 10 cu.ft. Refrigerator Troubleshooting and Service Manual", "brand": "Furrion",
                  "models": "FCR08DCGTA;FCR10DCGTA", "doc_number": "CCD-0008122"}
        for rows in ([fan, fridge], [fridge, fan]):
            self.assertEqual(sel(rows, "Furrion FCR08DCGTA 12V DC refrigerator", "Refrigerators")["doc"]["id"], 298)
        self.assertIsNone(sel([fan], "Furrion FCR08DCGTA 12V DC refrigerator", "Refrigerators")["doc"])


# ---------------- R1: category audit (309 / 631 / 629 moved by the rule; 565 flagged) ----------------
def _audit_db(rows, cats):
    c = sqlite3.connect(":memory:")
    c.executescript("CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT);"
                    "CREATE TABLE documents(id INTEGER PRIMARY KEY, title TEXT, clean_title TEXT, product_line TEXT, keywords TEXT, category_id INTEGER);"
                    "CREATE TABLE doc_chunks(id INTEGER PRIMARY KEY, document_id INTEGER, category_id INTEGER, chunk_text TEXT);")
    ids = {n: i + 1 for i, n in enumerate(cats)}
    c.executemany("INSERT INTO categories VALUES (?,?)", [(i, n) for n, i in ids.items()])
    for r in rows:
        c.execute("INSERT INTO documents VALUES (?,?,?,?,?,?)", (r["id"], r["title"], r.get("clean_title", ""), r.get("product_line", ""),
                                                                 r.get("keywords", ""), ids[r["category"]]))
        c.execute("INSERT INTO doc_chunks(document_id, category_id, chunk_text) VALUES (?,?,?)", (r["id"], ids[r["category"]], r.get("text", "")))
    return c


INCIDENT_ROWS = [
    {"id": 309, "title": "Girard 17 inch All Glass Gas Range Troubleshooting and Service Manual", "category": "awnings",
     "text": "range burner oven cooktop " * 10},
    {"id": 631, "title": "Power Gear T.I.P. - AUTOMATIC LEVEL CONTROLLER SET-UP", "category": "slide-outs", "keywords": "slide-",
     "text": "jack leveling controller " * 5},
    {"id": 629, "title": "Power Gear T.I.P. - DMI LEVELING PUMP TEST PROCEDURE", "category": "slide-outs", "text": "pump"},
    {"id": 565, "title": "ï Follow the coach manufacturer instructions regarding the leveling of the coach", "product_line": "Leveling",
     "category": "slide-outs", "text": "room slide-out extension retraction slide " * 3},
    {"id": 1, "title": "Lippert Leveling Jack Manual", "category": "Leveling", "text": "jack " * 9},
]
AUDIT_CATS = ["awnings", "slide-outs", "Leveling", "Range & Cooktops"]


class TestR1Audit(unittest.TestCase):
    def test_rule_moves_309_631_629_and_flags_565(self):
        c = _audit_db(INCIDENT_ROWS, AUDIT_CATS)
        p = audit.plan(c)
        self.assertEqual({(m["doc_id"], m["to"]) for m in p["moves"]}, {(309, "Range & Cooktops"), (631, "Leveling"), (629, "Leveling")})
        self.assertEqual([r["doc_id"] for r in p["metadata_review"]], [565])

    def test_apply_is_idempotent_and_rolls_back(self):
        c = _audit_db(INCIDENT_ROWS, AUDIT_CATS)
        undo = audit.apply(c, audit.plan(c)["moves"])
        self.assertEqual(len(undo["rows"]), 3)
        self.assertEqual(audit.plan(c)["moves"], [])
        self.assertEqual(c.execute("select count(*) from doc_chunks d join categories k on k.id=d.category_id where k.name='Leveling'").fetchone()[0], 3)
        self.assertEqual(audit.rollback(c, undo), 3)
        self.assertEqual(len(audit.plan(c)["moves"]), 3)

    def test_library_snapshot_has_no_misfiled_documents(self):
        snap = json.load(open(os.path.join(ROOT, "tests", "fixtures", "library_category_snapshot_2026-10-16.json")))
        c = _audit_db([dict(d, text="") for d in snap["documents"]], snap["categories"])
        body = {d["id"]: d["body"] for d in snap["documents"]}
        p = audit.plan(c, body_types=lambda did: body.get(did, {}))
        self.assertEqual(p["moves"], [], p["moves"][:5])
        self.assertEqual(p["unmapped_categories"], [])

    def test_upload_warning(self):
        self.assertIn("cooktop", audit.upload_category_warning("Girard 17 inch All Glass Gas Range Manual", "awnings"))
        self.assertEqual(audit.upload_category_warning("Lippert Awning Manual", "awnings"), "")
        self.assertIn("no product-type map", audit.upload_category_warning("Anything", "Brand New Category"))


if __name__ == "__main__":
    unittest.main()
