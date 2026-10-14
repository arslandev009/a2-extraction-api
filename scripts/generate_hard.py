"""Generate the HARD set (16 PDFs) into data/hard/.  python scripts/generate_hard.py"""
from pathlib import Path

from extractor.synth_hard import generate_hard

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "hard" / "invoices"
    rows = generate_hard(out)
    print(f"wrote {len(rows)} PDFs to {out}; expected needs_review: {sum(r['needs_review'] for r in rows)}")
