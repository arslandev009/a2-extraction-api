"""Generate a WORLD set (24 realistic invoices/bills/receipts) into data/<name>/.
  python scripts/generate_world.py                                    # data/world   classic kit, seed 2026
  python scripts/generate_world.py --name world2 --seed 777           # same 24 designs, new numbers/dates/items
  python scripts/generate_world.py --name world3 --seed 4242 --kit new   # 12 NEW kinds/designs (water, car rental, airline, ...)
"""
import argparse
from pathlib import Path

from extractor.synth_world import generate_world

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="world")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--kit", choices=["classic", "new"], default="classic")
    a = ap.parse_args()
    out = Path(__file__).resolve().parents[1] / "data" / a.name / "invoices"
    rows = generate_world(out, seed=a.seed, kit=a.kit)
    print(f"wrote {len(rows)} PDFs to {out}; expected needs_review: {sum(r['needs_review'] for r in rows)}")
