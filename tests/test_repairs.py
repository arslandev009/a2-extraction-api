"""Repairs are tested by re-creating the AI mistakes seen in the real Gemini run of the world set, then checking the pipeline
turns them into the correct answer - or still flags them when the document cannot confirm a fix."""
import copy
from pathlib import Path

import pytest

from extractor.compare import compare
from extractor.pipeline import process_pdf
from extractor.synth_world import generate_world

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("w") / "invoices"
    rows = {r["layout"] + str(i // 12): r for i, r in enumerate(generate_world(d))}   # e.g. 'saas0', 'saas1'
    return d, rows


def run(world, key, mutate, **kw):
    d, rows = world
    r = rows[key]
    wrong = copy.deepcopy(r["expected"])
    mutate(wrong)

    class L:
        def chat_json(self, m, s):
            return wrong

    res = process_pdf((d / r["file"]).read_bytes(), L(), max_pages=10, **kw)
    return res, r


def all_fields_ok(res, r):
    c = compare(res.extraction.model_dump(), r["expected"])
    return [k for k, v in c.items() if not v]


def codes(res):
    return {i.code for i in res.issues}


def test_deposit_row_taken_as_item_is_removed(world):          # world_01
    res, r = run(world, "freelancer0", lambda e: e["line_items"].append({"description": "Less deposit received", "quantity": None, "unit_price": None, "amount": -1500.0}))
    assert all_fields_ok(res, r) == [] and "rows_dropped_to_reconcile" in codes(res) and not res.needs_review


def test_carried_forward_rows_are_removed_on_multipage(world):  # world_11 / 23
    def m(e):
        li = e["line_items"]
        li.insert(12, {"description": "Carried forward", "quantity": None, "unit_price": None, "amount": 6062.5})
        li.insert(13, {"description": "Brought forward", "quantity": None, "unit_price": None, "amount": 6062.5})
    res, r = run(world, "agency0", m)
    assert all_fields_ok(res, r) == [] and not res.needs_review


def test_missing_shipping_is_recovered_from_the_labelled_line(world):  # world_08 / 19
    for key in ("marketplace0", "wholesale1"):
        res, r = run(world, key, lambda e: e.update(other_charges=None))
        assert all_fields_ok(res, r) == [] and "other_charges_from_label" in codes(res) and not res.needs_review, key


def test_wrong_total_is_still_flagged_even_after_row_repair(world):   # world_06: AI used balance due as total
    def m(e):
        e["line_items"] += [{"description": "Insurance adjustment", "quantity": None, "unit_price": None, "amount": -68.4},
                            {"description": "Insurance payment", "quantity": None, "unit_price": None, "amount": -120.0}]
        e["discount"], e["total"] = None, 36.6
    res, r = run(world, "medical0", m)
    assert res.needs_review      # the rows get cleaned up, but a wrong total must never pass


def test_invented_gap_is_not_hidden(world):    # the easy-set failure: AI makes up other_charges to balance a wrong printed total
    res, r = run(world, "saas0", lambda e: e.update(other_charges=55.0, total=e["total"] + 55.0))
    assert res.needs_review


def test_currency_inference_and_default(world):                 # world_05 / 17: receipt prints no currency
    res, r = run(world, "retail0", lambda e: e.update(currency=None))
    assert res.needs_review and res.extraction.currency is None  # nothing printed, no default -> human
    res2, r = run(world, "retail0", lambda e: e.update(currency=None), default_currency="USD")
    assert res2.extraction.currency == "USD" and "currency_inferred" in codes(res2) and not res2.needs_review
    res3, r = run(world, "medical0", lambda e: e.update(currency=None))     # '$' is printed -> inferred without a default
    assert res3.extraction.currency == "USD" and "currency_inferred" in codes(res3)


def test_po_rescued_from_printed_label():
    import json
    rows = [json.loads(x) for x in open(ROOT / "data" / "ground_truth.jsonl", encoding="utf-8")]
    r = next(x for x in rows if x["expected"]["po_number"])
    wrong = {**r["expected"], "po_number": None}

    class L:
        def chat_json(self, m, s):
            return wrong

    res = process_pdf((ROOT / "data" / "invoices" / r["file"]).read_bytes(), L(), max_pages=10)
    assert res.extraction.po_number == r["expected"]["po_number"] and "po_from_label" in codes(res)


def test_repairs_do_nothing_to_correct_answers(world):
    d, rows = world
    for r in rows.values():
        class L:
            def __init__(self, answer):
                self.answer = answer

            def chat_json(self, m, s):
                return self.answer
        res = process_pdf((d / r["file"]).read_bytes(), L(r["expected"]), max_pages=10)
        assert not ({"rows_dropped_to_reconcile", "other_charges_from_label", "po_from_label"} & codes(res)), r["id"]
        assert not res.needs_review, r["id"]


def test_ambiguous_reconciliation_is_left_alone():
    from extractor.repairs import reconcile_lines
    from extractor.schema import InvoiceExtraction
    inv = InvoiceExtraction.model_validate({"subtotal": 100.0, "line_items": [{"amount": 50.0}, {"amount": 50.0}, {"amount": 50.0}]})
    new, notes = reconcile_lines(inv)
    assert notes == [] and len(new.line_items) == 3     # any one of the three 50s could go: not unique -> unchanged


def test_vendor_name_wrapped_onto_next_line_is_joined(world):      # world2 / world_02
    res, r = run(world, "electricity0", lambda e: e.update(vendor_name="Punjab Valley Power"))
    assert res.extraction.vendor_name == r["expected"]["vendor_name"] and "vendor_name_joined" in codes(res)


def test_vendor_join_is_not_applied_to_complete_names():
    from extractor.repairs import extend_vendor
    from extractor.schema import InvoiceExtraction
    inv = InvoiceExtraction.model_validate({"vendor_name": "Acme Supplies"})
    assert extend_vendor(inv, "Acme Supplies\nInc.\n")[1] != []          # a bare legal suffix on the next line IS a continuation
    assert extend_vendor(inv, "Acme Supplies\n14 Mill Lane\n")[1] == []  # an address line is not


def test_po_label_must_be_a_whole_word():
    """Regression: 'POL-51210392' (a policy number) must not be read as 'PO' + 'L-51210392'."""
    from extractor.repairs import rescue_po
    from extractor.schema import InvoiceExtraction
    inv = InvoiceExtraction.model_validate({})
    assert rescue_po(inv, "Policy number POL-51210392\nPO Box 3602")[1] == []
    assert rescue_po(inv, "Your PO: PO-87139")[0].po_number == "PO-87139"
    assert rescue_po(inv, "Ihre Bestellnr. PO-84115")[0].po_number == "PO-84115"


def test_medical_gross_total_with_ignored_adjustment_is_flagged(world):   # world2 world_06: total=225 (gross), adjustment ignored
    def m(e):
        e["total"], e["discount"] = e["total"] + e["discount"], None
    res, r = run(world, "medical0", m)
    assert res.needs_review
