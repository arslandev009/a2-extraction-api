
import pytest

from extractor.pdftext import extract_text
from extractor.schema import InvoiceExtraction
from extractor.synth_hard import KINDS, generate_hard
from extractor.validators import needs_review, validate


@pytest.fixture(scope="module")
def hard(tmp_path_factory):
    d = tmp_path_factory.mktemp("hard") / "invoices"
    rows = generate_hard(d)
    return d, rows


def text_of(hard, row):
    d, _ = hard
    return extract_text((d / row["file"]).read_bytes(), max_pages=5)


def test_count_and_kinds(hard):
    _, rows = hard
    assert len(rows) == len(KINDS) == 16
    assert {r["layout"] for r in rows} == {k for k, _ in KINDS}


def test_scans_have_no_text_others_do(hard):
    _, rows = hard
    for r in rows:
        t = text_of(hard, r)
        assert t.scanned == r["expect_scanned"], r["id"]


def test_validators_agree_with_truth(hard):
    _, rows = hard
    for r in rows:
        if r["expect_scanned"]:
            assert r["needs_review"]
            continue
        assert needs_review(validate(InvoiceExtraction.model_validate(r["expected"]))) == r["needs_review"], r["id"]


def test_kind_specific_content(hard):
    _, rows = hard
    for r in rows:
        e, k = r["expected"], r["layout"]
        if k == "scanned":
            continue
        txt = text_of(hard, r).text
        if k == "german":
            assert "Rechnungsnummer" in txt and e["invoice_number"] in txt
        elif k == "french":
            assert "Facture" in txt and "TVA" in txt
        elif k == "us_date":
            y, m, d = e["invoice_date"].split("-")
            assert f"{m}/{d}/{y}" in txt and int(d) > 12
        elif k == "wrapped_lines":
            assert "annex B" in txt or "thirty days" in txt or "handling instructions" in txt
        elif k == "ocr_noise":
            assert "lnvoice" in txt
        elif k == "missing_vendor":
            assert e["vendor_name"] is None and "Brightline" not in txt and r["needs_review"]
        elif k == "missing_date":
            assert e["invoice_date"] is None and "Invoice date" not in txt and r["needs_review"]
        elif k == "credit_note":
            assert e["total"] < 0 and "CREDIT NOTE" in txt
        elif k == "parties_swapped":
            assert "Customer" in txt and e["vendor_name"] in txt


def test_deterministic(tmp_path, hard):
    _, rows = hard
    again = generate_hard(tmp_path / "invoices")
    assert [r["expected"] for r in again] == [r["expected"] for r in rows]
