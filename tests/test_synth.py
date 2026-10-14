"""The generator + validators must agree: printed-consistent docs pass, planted errors are caught."""
from pathlib import Path

from extractor.compare import compare
from extractor.pdftext import extract_text
from extractor.schema import InvoiceExtraction
from extractor.synth import generate
from extractor.validators import needs_review, validate

ROOT = Path(__file__).resolve().parents[1]


def test_count_and_variety(truth_rows):
    assert len(truth_rows) == 36
    assert len({r["layout"] for r in truth_rows}) == 6
    assert {r["expected"]["currency"] for r in truth_rows} == {"USD", "EUR", "GBP", "PKR"}
    traps = {t for r in truth_rows for t in r["traps"]}
    assert {"bad_arithmetic", "line_mismatch", "prompt_injection", "multi_page", "partial_payment",
            "discount", "eu_number_format", "no_tax", "no_due_date"} <= traps


def test_validators_agree_with_ground_truth(truth_rows):
    for r in truth_rows:
        issues = validate(InvoiceExtraction.model_validate(r["expected"]))
        assert needs_review(issues) == r["needs_review"], (r["id"], r["traps"], issues)


def test_pdfs_have_text_layer_with_key_fields(truth_rows):
    for r in truth_rows:
        t = extract_text((ROOT / "data" / "invoices" / r["file"]).read_bytes(), max_pages=10)
        assert not t.scanned, r["id"]
        assert r["expected"]["invoice_number"] in t.text, r["id"]
        assert r["expected"]["vendor_name"].split()[0].lower() in t.text.lower(), r["id"]


def test_multi_page_docs_really_have_multiple_pages(truth_rows):
    for r in truth_rows:
        if "multi_page" in r["traps"]:
            t = extract_text((ROOT / "data" / "invoices" / r["file"]).read_bytes(), max_pages=10)
            assert t.pages >= 2, r["id"]


def test_compare_truth_with_itself_is_all_true(truth_rows):
    for r in truth_rows:
        assert all(compare(r["expected"], r["expected"]).values())


def test_generation_is_deterministic(tmp_path, truth_rows):
    rows = generate(tmp_path / "invoices", seed=42)
    assert [x["expected"] for x in rows] == [x["expected"] for x in truth_rows]
