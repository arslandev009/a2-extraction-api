"""Ground-truth text values must be found in the PDF text of every readable doc (else grounding would false-alarm)."""
from pathlib import Path

from extractor.pdftext import extract_text
from extractor.schema import InvoiceExtraction
from extractor.synth_hard import generate_hard
from extractor.validators import check_grounding, check_numbers

ROOT = Path(__file__).resolve().parents[1]


def _check(rows, folder):
    for r in rows:
        if r.get("expect_scanned"):
            continue
        t = extract_text((folder / r["file"]).read_bytes(), max_pages=10)
        inv = InvoiceExtraction.model_validate(r["expected"])
        assert check_grounding(inv, t.text, t.alt_text) == [], r["id"]
        assert [i for i in check_numbers(inv, t.text, t.alt_text) if i.severity == "error"] == [], r["id"]


def test_easy_set_grounded(truth_rows):
    _check(truth_rows, ROOT / "data" / "invoices")


def test_hard_set_grounded(tmp_path):
    rows = generate_hard(tmp_path / "invoices")
    _check(rows, tmp_path / "invoices")
