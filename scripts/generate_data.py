"""Regenerate the 36 synthetic invoices + data/ground_truth.jsonl (deterministic).  python scripts/generate_data.py"""
from pathlib import Path

from extractor.synth import generate

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "invoices"
    rows = generate(out)
    review = sum(r["needs_review"] for r in rows)
    print(f"wrote {len(rows)} PDFs to {out}; {review} expected needs_review")
