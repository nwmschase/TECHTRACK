"""Rebuild shop sheets with the rule-11 builder (offline library copy + OEM site).
Usage: python scripts/rule11_rebuild.py CASE [CASE...]  (writes to --out/<case>/)"""
import argparse, json, os, re, subprocess, sys, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gd_official as go
import pdf_rule11 as r11

V = "/workspace/techtrack-validation"
CASES = {
    "B11": ("Refrigerators", "Dometic RM1350", "Dometic RM1350 cools on 120V AC but will not cool on LP gas; no flame, check light comes on."),
    "B13": ("Water Heaters", "Suburban SW6DE", "Suburban SW6DE water heater will not light on gas; spark for a few seconds then locks out. Electric element works."),
    "B24": ("Furnaces", "Dometic DFS", "Dometic DFS furnace lights then shuts off after a few seconds, then retries."),
    "S04": ("Refrigerators", "Furrion FCR10DCGTA-BL", "Dial is at OFF, but the compressor keeps running. The fridge is ice-cold after weeks parked and plugged in."),
}
SEARCH = ["/workspace/tt-incoming", "/workspace/lippert-docs", "/workspace/techtrack-uploads", "/workspace/lci-docs", "/workspace/furnace"]


def pdf_for_doc(doc):
    base = os.path.basename(doc.get("file_path") or "") if "file_path" in doc else ""
    if not base:
        return None
    name = re.sub(r"^\d+_\d{14}_", "", base)
    if re.fullmatch(r"[0-9a-f]{6}\.pdf", name):
        return None
    for root in SEARCH:
        for p in glob.glob(f"{root}/**/{name}", recursive=True):
            return open(p, "rb").read()
    return None


class Lib(go.SqliteLibrary):
    def documents(self):
        docs = super().documents()
        fp = dict(self.c.execute("select id, coalesce(file_path,'') from documents").fetchall())
        for d in docs:
            d["file_path"] = fp.get(d["id"], "")
        return docs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="+")
    ap.add_argument("--db", default=f"{V}/live-data-copy/out-2026-10-13/rv_techtrack_v4.db")
    ap.add_argument("--out", default=f"{V}/rule11-rebuild-2026-10-16")
    a = ap.parse_args()
    lib = Lib(a.db)
    key = os.environ.get("XAI_API_KEY", "")
    for case in a.cases:
        cat, model, concern = CASES[case]
        out = os.path.join(a.out, case)
        os.makedirs(out, exist_ok=True)
        ref = ""
        if case == "S04":
            ref = (open(f"{V}/newstd/S04/S04-shop-sheet.md").read() +
                   "\nFIXES REQUIRED: put this manual's figures on Branches B, C and D too (e.g. Fig. 59/60 probe seat, Fig. 66 probe, Fig. 67 wires, "
                   "Fig. 68-70 C/T, Fig. 72 locking tab, Fig. 77 board screw, Fig. 79 compressor plug). Lines that are remarks, not actions "
                   "(\"Shop check: no jumper...\", \"Housing already down...? Go to step 2\", \"Wires already off...\", \"10 min is a shop wait...\") are kind note.")
        res = {"case": case, "model": model, "concern": concern}
        try:
            stats, sheet, plan = r11.build(case, model, concern, cat, lib, pdf_for_doc=pdf_for_doc, api_key=key,
                                           out_pdf=f"{out}/{case}-rule11-shop-sheet.pdf", out_md=f"{out}/{case}-rule11-shop-sheet.md", reference=ref)
            json.dump(plan, open(f"{out}/{case}-plan.json", "w"), indent=1)
            os.makedirs(f"{out}/pages", exist_ok=True)
            subprocess.run(["pdftoppm", "-r", "90", "-png", f"{out}/{case}-rule11-shop-sheet.pdf", f"{out}/pages/p"], check=True)
            res.update(status="BUILT", **stats)
        except (r11.NoManual, r11.NoFigures, r11.StepRuleError) as exc:
            res.update(status=f"STOPPED: {type(exc).__name__}", reason=str(exc))
        json.dump(res, open(f"{out}/{case}-result.json", "w"), indent=1, default=str)
        print(json.dumps({k: v for k, v in res.items() if k != "usage"}, default=str))


if __name__ == "__main__":
    main()
