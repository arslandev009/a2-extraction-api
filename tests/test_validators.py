import copy

from extractor.schema import InvoiceExtraction
from extractor.validators import needs_review, validate

GOOD = {
    "vendor_name": "Acme", "invoice_number": "INV-1", "invoice_date": "2026-03-01", "due_date": "2026-03-31",
    "currency": "USD",
    "line_items": [{"description": "a", "quantity": 2, "unit_price": 10.0, "amount": 20.0},
                   {"description": "b", "quantity": 1, "unit_price": 5.5, "amount": 5.5}],
    "subtotal": 25.5, "discount": None, "tax_rate": 10, "tax_amount": 2.55, "total": 28.05,
}


def codes(d):
    return {i.code for i in validate(InvoiceExtraction.model_validate(d)) if i.severity == "error"}


def mut(**kw):
    d = copy.deepcopy(GOOD)
    d.update(kw)
    return d


def test_good_invoice_clean():
    assert validate(InvoiceExtraction.model_validate(GOOD)) == []


def test_total_mismatch():
    assert "total_mismatch" in codes(mut(total=30.0))


def test_subtotal_mismatch():
    assert "subtotal_mismatch" in codes(mut(subtotal=26.0, total=28.6, tax_amount=2.6))


def test_line_math():
    d = mut()
    d["line_items"][0]["amount"] = 25.0
    assert "line_math" in codes(d)


def test_tax_math_is_only_a_warning_but_total_check_still_catches_it():
    issues = validate(InvoiceExtraction.model_validate(mut(tax_amount=5.0, total=30.5)))
    assert any(i.code == "tax_math" and i.severity == "warning" for i in issues)
    assert "total_mismatch" not in codes(mut(tax_amount=5.0, total=30.5))   # consistent total: allowed (taxable subset)
    assert "total_mismatch" in codes(mut(tax_amount=5.0, total=28.05))      # tax changed but total not: caught


def test_discount_flow():
    d = mut(discount=2.5, tax_rate=10, tax_amount=2.3, total=25.3)
    assert codes(d) == set()


def test_missing_required_and_empty_lines():
    d = mut(vendor_name=None, line_items=[])
    assert "missing_required" in codes(d)


def test_bad_and_reversed_dates():
    assert "bad_date" in codes(mut(invoice_date="05/03/2026"))
    assert "due_before_invoice" in codes(mut(due_date="2026-02-01"))


def test_unsupported_currency():
    assert "currency_unsupported" in codes(mut(currency="XYZ"))


def test_needs_review_flag():
    assert needs_review(validate(InvoiceExtraction.model_validate(mut(total=1.0))))
    assert not needs_review(validate(InvoiceExtraction.model_validate(GOOD)))


def test_address_as_vendor_is_flagged():
    assert "vendor_is_address" in codes(mut(vendor_name="14 Mill Lane"))
    assert "vendor_is_address" in codes(mut(vendor_name="Tel +44 20 7946 0000"))
    assert "vendor_is_address" not in codes(mut(vendor_name="3M Company"))


def test_grounding_catches_invented_values():
    from extractor.validators import check_grounding
    inv = InvoiceExtraction.model_validate(mut(vendor_name="ACME PAYMENTS"))
    issues = check_grounding(inv, "Brightline Print Works\nInvoice No INV-1\n2026-03-01 2026-03-31")
    assert [i.field for i in issues] == ["vendor_name"]
    ok = InvoiceExtraction.model_validate(mut(vendor_name="Brightline  Print Works"))
    assert check_grounding(ok, "brightline print\nworks\nINV-1 2026-03-01 2026-03-31") == []


def test_date_grounding_accepts_common_printed_forms():
    from extractor.validators import check_grounding
    inv = InvoiceExtraction.model_validate(mut(due_date="2025-04-29", invoice_date="2025-04-05"))
    forms = ["Due 29 Apr 2025", "Due April 29, 2025", "Due 29/04/2025", "Due 04/29/2025", "Due 29.04.2025",
             "Due 29. April 2025", "Due 2025-04-29", "Due Apr 29th, 2025", "Due 29 avril 2025", "Due 29-Apr-2025", "Due 29.04.25"]
    for f in forms:
        text = f"Invoice date 5 April 2025\n{f}"
        issues = [i for i in check_grounding(inv, text) if i.field == "due_date"]
        assert issues == [], f


def test_date_grounding_catches_wrong_year():
    from extractor.validators import check_grounding
    inv = InvoiceExtraction.model_validate(mut(invoice_date="2025-03-15", due_date="2029-04-29"))
    issues = [i for i in check_grounding(inv, "Acme INV-1\nInvoice date 2025-03-15\nDue date 2025-04-29")]
    assert [(i.code, i.field) for i in issues] == [("date_not_in_document", "due_date")]


def test_other_charges_included_in_total():
    d = mut(subtotal=100.0, discount=10.0, tax_rate=None, tax_amount=0.0, other_charges=5.0, total=95.0,
            line_items=[{"description": "a", "quantity": 1, "unit_price": 100.0, "amount": 100.0}])
    assert codes(d) == set()
    d["other_charges"] = None   # shipping not extracted -> total no longer adds up -> review
    assert "total_mismatch" in codes(d)


def test_rounded_unit_price_tolerance_scales_with_quantity():
    d = mut()
    d["line_items"] = [{"description": "a", "quantity": 7, "unit_price": 1630.13, "amount": 11410.88}]  # 0.03 off
    d.update(subtotal=11410.88, tax_rate=None, tax_amount=0.0, total=11410.88)
    assert codes(d) == set()
    d["line_items"][0]["amount"] = 11411.50  # 0.59 off: a real error
    d.update(subtotal=11411.50, total=11411.50)
    assert "line_math" in codes(d)


def test_whole_token_and_reader_mismatch():
    from extractor.validators import check_grounding
    inv = InvoiceExtraction.model_validate(mut(invoice_number="135", invoice_date="2026-03-01", due_date="2026-03-31"))
    dates = " 2026-03-01 2026-03-31 Acme"
    # "135" inside "13594027" is NOT a match
    assert [i.code for i in check_grounding(inv, "Invoice #13594027" + dates)] == ["not_in_document"]
    # whole token in one engine but not the other
    issues = check_grounding(inv, "Invoice #135\n94027" + dates, "Invoice #13594027" + dates)
    assert [i.code for i in issues] == ["reader_mismatch"]
    assert check_grounding(inv, "Invoice #135" + dates, "Invoice #135" + dates) == []


def test_per_line_discount_percent_is_accepted():
    d = mut()
    d["line_items"] = [{"description": "a", "quantity": 10, "unit_price": 20.0, "discount_percent": 15, "amount": 170.0}]
    d.update(subtotal=170.0, tax_rate=None, tax_amount=0.0, total=170.0)
    assert codes(d) == set()
    d["line_items"][0]["amount"] = 175.0
    d.update(subtotal=175.0, total=175.0)
    assert "line_math" in codes(d)


def test_invented_numbers_are_caught():
    from extractor.validators import check_numbers
    inv = InvoiceExtraction.model_validate(mut(other_charges=55.0, discount=None, tax_amount=2.55, total=28.05, subtotal=25.5))
    text = "Subtotal 25.50\nTax 2.55\nTotal USD 28.05\nItem 20.00 5.50"
    issues = check_numbers(inv, text)
    assert [(i.field, i.severity) for i in issues if i.severity == "error"] == [("other_charges", "error")]
    inv2 = InvoiceExtraction.model_validate(mut(tax_amount=2.55, total=28.05, subtotal=25.5))
    assert [i for i in check_numbers(inv2, text) if i.severity == "error"] == []
    # '50' must not be found inside '12.50' or '1,500.00'
    inv3 = InvoiceExtraction.model_validate(mut(discount=50.0, tax_amount=2.55, total=28.05))
    assert any(i.field == "discount" for i in check_numbers(inv3, text + "\nx 12.50 and 1,500.00"))


def test_tax_sum_of_printed_tax_lines_is_accepted_but_not_an_arbitrary_number():
    from extractor.validators import check_numbers
    text = "Subtotal 1,000.00\nGST 17% 170.00\nElectricity duty 1.5% 15.00\nTotal 1,185.00\nShipping 20.00"
    ok = InvoiceExtraction.model_validate(mut(subtotal=1000.0, tax_amount=185.0, total=1185.0))
    assert [i for i in check_numbers(ok, text) if i.field == "tax_amount"] == []
    # 190 = 170 + 20 only if the non-tax 'Shipping 20.00' line were allowed: it is not
    bad = InvoiceExtraction.model_validate(mut(subtotal=1000.0, tax_amount=190.0, total=1185.0))
    assert [i.field for i in check_numbers(bad, text) if i.severity == "error"] == ["tax_amount"]
