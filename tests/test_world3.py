"""Batch-5 fixes, tested with the mistakes seen in the first real Gemini run of the world3 set."""
import copy

import pytest

from extractor.compare import compare
from extractor.pdftext import extract_text
from extractor.pipeline import process_pdf
from extractor.schema import InvoiceExtraction
from extractor.synth_world import generate_world
from extractor.validators import check_grounding, check_numbers, validate


@pytest.fixture(scope="module")
def w3(tmp_path_factory):
    d = tmp_path_factory.mktemp("w3") / "invoices"
    rows = generate_world(d, seed=4242, kit="new")
    return d, {r["layout"] + str(i // 12): r for i, r in enumerate(rows)}


def run(w3, key, mutate, **kw):
    d, rows = w3
    r = rows[key]
    ans = copy.deepcopy(r["expected"])
    mutate(ans)

    class L:
        def chat_json(self, m, s):
            return ans

    return process_pdf((d / r["file"]).read_bytes(), L(), max_pages=10, **kw), r


def codes(res):
    return {i.code for i in res.issues}


def test_correct_answers_of_all_new_kinds_pass_every_check(w3):
    d, rows = w3
    for r in rows.values():
        t = extract_text((d / r["file"]).read_bytes(), max_pages=10)
        inv = InvoiceExtraction.model_validate(r["expected"])
        errs = [i for i in validate(inv) + check_grounding(inv, t.text, t.alt_text) + check_numbers(inv, t.text, t.alt_text) if i.severity == "error"]
        assert errs == [], (r["id"], r["layout"], [(e.code, e.field) for e in errs])


def test_sum_of_several_fee_lines_is_accepted(w3):
    for key in ("car_rental0", "event0", "courier0", "insurance0"):
        res, r = run(w3, key, lambda e: None)
        assert not res.needs_review, key


def test_wrong_fee_sum_is_still_flagged(w3):                      # world_20: AI said 31.95, printed lines add to 27.95
    res, r = run(w3, "event1", lambda e: e.update(other_charges=e["other_charges"] + 4.0, total=e["total"] + 4.0))
    assert res.needs_review


def test_missing_fees_are_recovered_from_up_to_three_fee_lines(w3):
    for key in ("event0", "car_rental0"):
        res, r = run(w3, key, lambda e: e.update(other_charges=None))
        assert res.extraction.other_charges == pytest.approx(r["expected"]["other_charges"]) and not res.needs_review, key


def test_document_number_rescued_from_its_own_label(w3):          # world_01/03/04/13/15
    for key in ("car_rental0", "ride0", "repair0", "car_rental1", "ride1"):
        res, r = run(w3, key, lambda e: e.update(invoice_number=None))
        assert res.extraction.invoice_number == r["expected"]["invoice_number"] and "invoice_number_from_label" in codes(res), key


def test_invoice_number_rescue_does_not_jump_lines_or_use_account_numbers():
    from extractor.repairs import rescue_invoice_number
    inv = InvoiceExtraction.model_validate({})
    assert rescue_invoice_number(inv, "Invoice Number:\n31 JUL 2012\nAccount number 998877")[1] == []   # redacted number: stay null
    assert rescue_invoice_number(inv, "Account number 998877  Policy number POL-5551")[1] == []
    assert rescue_invoice_number(inv, "Invoice no. INV-9912")[0].invoice_number == "INV-9912"


def test_credit_line_with_positive_unit_price_is_not_an_error():  # world_03 / 11: unit_price 105, amount -105
    inv = InvoiceExtraction.model_validate({"vendor_name": "A", "invoice_number": "1", "invoice_date": "2026-03-01", "currency": "USD", "total": 100.0,
                                            "line_items": [{"description": "Plan", "quantity": 1, "unit_price": 205.0, "amount": 205.0},
                                                           {"description": "Discount", "quantity": 1, "unit_price": 105.0, "amount": -105.0}]})
    assert [i for i in validate(inv) if i.code == "line_math"] == []


def test_adjusted_and_strict_scoring():
    truth = {"vendor_name": "A", "invoice_number": "1", "po_number": None, "invoice_date": "2026-01-01", "due_date": None, "currency": "USD",
             "subtotal": 100.0, "discount": 10.0, "tax_rate": None, "tax_amount": 0, "other_charges": None, "total": 90.0,
             "line_items": [{"amount": 60.0}, {"amount": 40.0}]}
    pred = {**truth, "subtotal": None, "discount": None, "line_items": [{"amount": 60.0}, {"amount": 40.0}, {"amount": -10.0}]}
    assert all(compare(pred, truth).values())
    strict = compare(pred, truth, strict=True)
    assert not strict["subtotal"] and not strict["discount"] and not strict["line_count"]
    # a WRONG discount is still an error in adjusted scoring
    pred2 = {**pred, "line_items": [{"amount": 60.0}, {"amount": 40.0}, {"amount": -25.0}]}
    assert not compare(pred2, truth)["discount"]


def test_previous_balance_and_amount_due_are_separate_fields(w3):  # world_12: total must stay 152.65, amount due 206.85
    res, r = run(w3, "water1", lambda e: e.update(amount_due=206.85))
    assert res.extraction.total == r["expected"]["total"] and res.extraction.amount_due == 206.85 and not res.needs_review


def test_gross_total_with_ignored_savings_is_flagged(w3):          # world4 world_09 / 21 (pharmacy): total=retail price, savings ignored
    def m(e):
        e["total"], e["discount"] = e["total"] + e["discount"], None
    res, r = run(w3, "pharmacy0", m)
    assert res.needs_review and "deduction_not_captured" in codes(res)
    res2, r = run(w3, "pharmacy1", m)
    assert res2.needs_review


def test_deduction_as_negative_line_or_as_discount_both_pass(w3):
    res, r = run(w3, "pharmacy0", lambda e: None)
    assert not res.needs_review
    def as_line(e):
        e["line_items"].append({"description": "Insurance savings", "quantity": None, "unit_price": None, "amount": -e["discount"]})
        e["discount"] = None
    res2, r = run(w3, "pharmacy0", as_line)     # AI returns the savings as a negative row: the repair moves it to `discount`
    assert not res2.needs_review and res2.extraction.discount == r["expected"]["discount"] and "row_moved_to_discount" in codes(res2)


def test_deduction_check_ignores_percentages_charges_and_qty_rate_pairs():
    from extractor.validators import check_deductions
    inv = InvoiceExtraction.model_validate({"line_items": [{"amount": 50.0}, {"amount": -12.5}]})
    assert check_deductions(inv, "Promotional Code: 25OFF - 25.00% Recurring Discount USD $-12.50") == []      # '25.00%' is a percent
    assert check_deductions(inv, "Fuel price adjustment (516 units) 1.85 954.60") == []                          # a positive charge
    inv2 = InvoiceExtraction.model_validate({"line_items": [{"amount": 105.0}, {"amount": -105.0}]})
    assert check_deductions(inv2, "Multi-policy discount 1 105.00 -105.00") == []                                # '1 105.00' is qty and rate
    inv3 = InvoiceExtraction.model_validate({"line_items": [{"amount": 225.0}]})
    assert check_deductions(inv3, "Insurance adjustment -$68.40")[0].code == "deduction_not_captured"            # a negative adjustment IS a deduction
