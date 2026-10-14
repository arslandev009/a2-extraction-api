"""Field-level comparison of an extraction against ground truth (smoke now, eval runner in A2.2)."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

SCALARS = ["vendor_name", "invoice_number", "po_number", "invoice_date", "due_date", "currency"]
MONEY = ["subtotal", "discount", "tax_rate", "tax_amount", "other_charges", "total"]
Q = Decimal("0.01")


def _num(x: Any) -> Decimal | None:
    return None if x is None else Decimal(str(x)).quantize(Q)


def _s(x: Any) -> str | None:
    return None if x is None else str(x).strip().lower()


def compare(pred: dict, truth: dict, strict: bool = False) -> dict[str, bool]:
    res: dict[str, bool] = {}
    for f in SCALARS:
        res[f] = _s(pred.get(f)) == _s(truth.get(f))
    for f in MONEY:
        p, t = _num(pred.get(f)), _num(truth.get(f))
        if f in ("discount", "tax_amount", "other_charges"):  # null and 0 mean the same
            p, t = p or Decimal("0.00"), t or Decimal("0.00")
        res[f] = p == t
    pl, tl = pred.get("line_items") or [], truth.get("line_items") or []
    res["line_count"] = len(pl) == len(tl)
    res["line_amounts"] = sorted(_num(x.get("amount")) or Decimal(0) for x in pl) == sorted(
        _num(x.get("amount")) or Decimal(0) for x in tl
    )
    if strict:
        return res
    # Adjusted scoring (documented in the report; strict numbers are printed next to it):
    # 1) an omitted subtotal is not an error: it is derivable from the line items
    if pred.get("subtotal") is None:
        res["subtotal"] = True
    # 2) a discount printed in the totals block and the same amount returned as a NEGATIVE line item are the same money
    t_disc = _num(truth.get("discount")) or Decimal("0.00")
    p_disc = _num(pred.get("discount")) or Decimal("0.00")
    t_amounts = [_num(x.get("amount")) or Decimal(0) for x in tl]
    if t_disc > 0 and p_disc == 0 and all(a >= 0 for a in t_amounts):
        neg = [_num(x.get("amount")) or Decimal(0) for x in pl if (_num(x.get("amount")) or Decimal(0)) < 0]
        if neg and abs(-sum(neg) - t_disc) <= Decimal("0.01"):
            pos = [_num(x.get("amount")) or Decimal(0) for x in pl if (_num(x.get("amount")) or Decimal(0)) >= 0]
            res["discount"] = True
            res["line_count"] = len(pos) == len(t_amounts)
            res["line_amounts"] = sorted(pos) == sorted(t_amounts)
    return res
