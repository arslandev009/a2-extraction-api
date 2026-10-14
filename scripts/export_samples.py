"""Copy a curated set of sample PDFs for the demo UI (sample files ONLY: never accept real client documents in a free-tier demo).

  python scripts/export_samples.py [--out web/public/samples]

Needs the sets generated first:  generate_data.py, generate_hard.py, generate_world.py --name world5 --seed 31337 --kit new
Writes the PDFs and samples.json (title, file, what the demo should show) for the UI.
"""
import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETS = {"easy": ROOT / "data", "hard": ROOT / "data" / "hard", "world5": ROOT / "data" / "world5"}
# (set, document id or layout name, title, what the demo should show)
PICKS = [
    ("easy", "inv_00", "Clean invoice", "extracted and validated, no review needed"),
    ("easy", "inv_07", "Printed total does not add up", "extracted exactly as printed, FLAGGED for review (total mismatch)"),
    ("easy", "inv_05", "Prompt injection hidden in the footer", "the instruction is ignored; real total and vendor are extracted"),
    ("hard", "hard_02", "French invoice (1 234,56 number format)", "extracted, dates and numbers normalised"),
    ("hard", "hard_12", "Scanned image, no text layer", "FLAGGED: no text layer, a human must look"),
    ("world5", "repair", "Repair shop invoice (parts and labor tables)", "two tables, shop supplies and tax on parts only"),
    ("world5", "pharmacy", "Pharmacy receipt (insurance savings)", "savings captured as a discount, total is what you paid"),
    ("world5", "insurance", "Insurance premium notice", "fees summed, minimum payment ignored"),
]

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=str(ROOT / "web" / "public" / "samples"))
out = Path(ap.parse_args().out)
out.mkdir(parents=True, exist_ok=True)
manifest = []
for name, key, title, shows in PICKS:
    base = SETS[name]
    gt = base / "ground_truth.jsonl"
    if not gt.exists():
        raise SystemExit(f"missing {gt}: generate the {name} set first")
    rows = [json.loads(x) for x in open(gt, encoding="utf-8")]
    row = next((r for r in rows if r["id"] == key or r["layout"] == key), None)
    if row is None:
        raise SystemExit(f"{name}: no document '{key}'")
    dest = f"{name}_{row['id']}.pdf"
    shutil.copy(base / "invoices" / row["file"], out / dest)
    manifest.append({"file": dest, "title": title, "shows": shows, "expected_review": row["needs_review"]})
(out / "samples.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"wrote {len(manifest)} samples to {out}")
