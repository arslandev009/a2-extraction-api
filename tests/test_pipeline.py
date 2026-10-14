from pathlib import Path

from extractor.pipeline import process_pdf

ROOT = Path(__file__).resolve().parents[1]


def _pdf(row):
    return (ROOT / "data" / "invoices" / row["file"]).read_bytes()


def test_clean_doc_no_review(truth_rows, fake_llm_cls):
    row = next(r for r in truth_rows if not r["needs_review"])
    llm = fake_llm_cls(row["expected"])
    res = process_pdf(_pdf(row), llm, max_pages=10)
    assert res.error is None and res.needs_review is False and res.extraction.invoice_number == row["expected"]["invoice_number"]
    assert "Invoice text:" in llm.calls[0][1]["content"]  # PDF text reached the prompt


def test_bad_arithmetic_doc_is_flagged(truth_rows, fake_llm_cls):
    row = next(r for r in truth_rows if "bad_arithmetic" in r["traps"])
    res = process_pdf(_pdf(row), fake_llm_cls(row["expected"]), max_pages=10)
    assert res.needs_review and any(i.code == "total_mismatch" for i in res.issues)


def test_llm_failure_is_reported_not_raised(truth_rows, fake_llm_cls):
    res = process_pdf(_pdf(truth_rows[0]), fake_llm_cls(exc=RuntimeError("429")), max_pages=10)
    assert res.extraction is None and "RuntimeError" in res.error and res.needs_review


def test_garbage_bytes(fake_llm_cls):
    res = process_pdf(b"hello", fake_llm_cls({}))
    assert res.needs_review and res.issues[0].code == "bad_pdf"


def test_truncation_warning(truth_rows, fake_llm_cls):
    row = next(r for r in truth_rows if "multi_page" in r["traps"])
    res = process_pdf(_pdf(row), fake_llm_cls(row["expected"]), max_pages=1)
    assert any(i.code == "truncated" for i in res.issues)


def test_llm_returns_string_or_model(truth_rows, fake_llm_cls):
    import json
    row = truth_rows[0]
    res = process_pdf(_pdf(row), fake_llm_cls(json.dumps(row["expected"])), max_pages=10)
    assert res.extraction.currency == row["expected"]["currency"]


def test_gap_triggers_one_repair_retry(truth_rows, fake_llm_cls):
    """First answer misses line items -> pipeline asks once more with feedback and keeps the better answer."""
    row = next(r for r in truth_rows if not r["needs_review"])

    class Flaky(fake_llm_cls):
        def chat_json(self, messages, schema):
            self.calls.append(messages)
            if len(self.calls) == 1:
                return {**row["expected"], "line_items": []}
            return row["expected"]

    llm = Flaky()
    res = process_pdf(_pdf(row), llm, max_pages=10)
    assert res.attempts == 2 and res.needs_review is False and len(res.extraction.line_items) == len(row["expected"]["line_items"])
    assert "gaps" in llm.calls[1][-1]["content"]  # feedback was sent


def test_arithmetic_errors_are_not_retried(truth_rows, fake_llm_cls):
    row = next(r for r in truth_rows if "bad_arithmetic" in r["traps"])
    llm = fake_llm_cls(row["expected"])
    res = process_pdf(_pdf(row), llm, max_pages=10)
    assert res.attempts == 1 and len(llm.calls) == 1 and res.needs_review


def test_retry_can_be_disabled(truth_rows, fake_llm_cls):
    row = next(r for r in truth_rows if not r["needs_review"])
    llm = fake_llm_cls({**row["expected"], "line_items": []})
    res = process_pdf(_pdf(row), llm, max_pages=10, retry=False)
    assert res.attempts == 1 and len(llm.calls) == 1 and res.needs_review


def test_missing_vendor_is_not_retried_and_invention_is_flagged(truth_rows, fake_llm_cls):
    """Regression for the hard-set failure: no retry for vendor gaps; an address used as vendor must be caught."""
    row = next(r for r in truth_rows if not r["needs_review"])
    llm = fake_llm_cls({**row["expected"], "vendor_name": None})
    res = process_pdf(_pdf(row), llm, max_pages=10)
    assert res.attempts == 1 and len(llm.calls) == 1 and res.needs_review

    llm2 = fake_llm_cls({**row["expected"], "vendor_name": "14 Mill Lane"})
    res2 = process_pdf(_pdf(row), llm2, max_pages=10)
    assert res2.needs_review and {"vendor_is_address", "not_in_document"} & {i.code for i in res2.issues}


def _split_baseline_pdf() -> bytes:
    """Invoice number '13594027' printed with a slightly lower baseline for the last digits (seen in a real sample):
    pdfplumber reads '#135' + '94027' on two lines, pdfium reads '#13594027'."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 760, "Acme Supplies")
    c.drawString(60, 700, "Invoice #135")
    c.drawString(60 + c.stringWidth("Invoice #135", "Helvetica-Bold", 16), 696.8, "94027")
    c.setFont("Helvetica", 10)
    c.drawString(60, 670, "Date: 2026-03-01")
    c.drawString(60, 640, "Widget   1 x 37.50   37.50")
    c.drawString(60, 620, "Subtotal 37.50")
    c.drawString(60, 600, "Total USD 37.50")
    c.save()
    return buf.getvalue()


def test_split_identifier_is_caught_and_repaired_with_second_reader(fake_llm_cls):
    base = {"vendor_name": "Acme Supplies", "invoice_date": "2026-03-01", "currency": "USD", "subtotal": 37.5, "total": 37.5,
            "line_items": [{"description": "Widget", "quantity": 1, "unit_price": 37.5, "amount": 37.5}]}

    class ReadsWhatItSees(fake_llm_cls):
        def chat_json(self, messages, schema):
            self.calls.append(messages)
            txt = messages[1]["content"]
            return {**base, "invoice_number": "13594027" if "#13594027" in txt else "135"}

    llm = ReadsWhatItSees()
    res = process_pdf(_split_baseline_pdf(), llm, max_pages=5)
    assert res.extraction.invoice_number == "13594027" and res.needs_review is False and res.attempts == 2

    # with retry disabled the wrong value is still NOT silent: it is flagged for review
    res2 = process_pdf(_split_baseline_pdf(), ReadsWhatItSees(), max_pages=5, retry=False)
    assert res2.needs_review and any(i.code == "reader_mismatch" for i in res2.issues)
