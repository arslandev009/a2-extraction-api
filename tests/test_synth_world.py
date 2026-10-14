
import pytest

from extractor.pdftext import extract_text
from extractor.schema import InvoiceExtraction
from extractor.synth_world import BUILDERS, generate_world
from extractor.validators import check_grounding, check_numbers, validate


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    d = tmp_path_factory.mktemp("world") / "invoices"
    return d, generate_world(d)


def test_count_and_kinds(world):
    _, rows = world
    assert len(rows) == 24 and {r["layout"] for r in rows} == {k for k, _ in BUILDERS}


def test_correct_answers_pass_every_check(world):
    """The checks must not raise false alarms on the correct answer of any realistic document."""
    d, rows = world
    for r in rows:
        t = extract_text((d / r["file"]).read_bytes(), max_pages=10)
        inv = InvoiceExtraction.model_validate(r["expected"])
        errs = [i for i in validate(inv) + check_grounding(inv, t.text, t.alt_text) + check_numbers(inv, t.text, t.alt_text) if i.severity == "error"]
        assert not t.scanned and errs == [], (r["id"], r["layout"], [(e.code, e.field) for e in errs])


def test_multipage_and_receipt_shapes(world):
    d, rows = world
    agency = [r for r in rows if r["layout"] == "agency"]
    assert all(extract_text((d / r["file"]).read_bytes(), max_pages=10).pages >= 2 for r in agency)
    assert all(len(r["expected"]["line_items"]) >= 28 for r in agency)
    assert all(r["expected"]["other_charges"] for r in agency)


def test_new_kit_world3_shapes(tmp_path):
    from extractor.synth_world import BUILDERS3
    rows = generate_world(tmp_path / "invoices", seed=4242, kit="new")
    assert len(rows) == 24 and {r["layout"] for r in rows} == {k for k, _ in BUILDERS3}
    for r in rows:
        t = extract_text((tmp_path / "invoices" / r["file"]).read_bytes(), max_pages=10)
        assert not t.scanned, r["id"]
        inv = InvoiceExtraction.model_validate(r["expected"])
        assert not [i for i in validate(inv) if i.severity == "error"], (r["id"], r["layout"])   # the printed numbers add up
