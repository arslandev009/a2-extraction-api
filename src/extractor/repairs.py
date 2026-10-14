"""Deterministic repairs applied to the model's answer BEFORE validation.

Principle: a repair is allowed only when the DOCUMENT ITSELF confirms it (exact arithmetic reconciliation, or a number that is
printed on a labelled line). Every repair returns a warning so nothing changes silently.
"""
from __future__ import annotations

import re
from collections import Counter
from decimal import Decimal
from itertools import combinations

from .schema import InvoiceExtraction
from .validators import _STRONG, CENT, SUPPORTED_CURRENCIES, Issue, _d, _fee_candidates

D0 = Decimal(0)
_CARRY = re.compile(r"\b(carried|brought)\s+forward\b|\b(b/f|c/f)\b|page\s+(sub)?total", re.I)
_PAYMENT = re.compile(r"\b(deposit|payment|paid|prepaid|credit applied|balance due|amount due|insurance)\b", re.I)
_PO = re.compile(r"(?im)\b(?:your\s+|customer\s+)?(?:p\.?\s?o\.?|purchase\s+order|bestellnr\.?|bestellnummer|ihre\s+bestellung|votre\s+commande)(?![A-Za-z])"
                 r"\s*(?:no\.?|number|#|nr\.?)?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/]{3,})")
_SYMBOL = {"$": "USD", "\u00a3": "GBP", "\u20ac": "EUR"}


def _warn(code: str, msg: str, field: str | None = None) -> Issue:
    return Issue(code=code, severity="warning", message=msg, field=field)


def infer_currency(inv: InvoiceExtraction, text: str, default: str | None) -> tuple[InvoiceExtraction, list[Issue]]:
    if inv.currency:
        return inv, []
    codes = {c for c in re.findall(r"\b([A-Z]{3})\b", text) if c in SUPPORTED_CURRENCIES}
    syms = {_SYMBOL[s] for s in _SYMBOL if s in text}
    if len(codes) == 1:
        cur, why = next(iter(codes)), "the only ISO currency code printed"
    elif not codes and len(syms) == 1:
        cur, why = next(iter(syms)), "the only currency symbol printed"
    elif default:
        cur, why = default.upper(), "configured default currency (nothing unambiguous is printed)"
    else:
        return inv, []
    return inv.model_copy(update={"currency": cur}), [_warn("currency_inferred", f"currency set to {cur}: {why}", "currency")]


def rescue_po(inv: InvoiceExtraction, text: str) -> tuple[InvoiceExtraction, list[Issue]]:
    if inv.po_number:
        return inv, []
    cands = {m.group(1) for m in _PO.finditer(text) if any(ch.isdigit() for ch in m.group(1))}
    if len(cands) != 1:
        return inv, []
    po = next(iter(cands))
    return inv.model_copy(update={"po_number": po}), [_warn("po_from_label", f"po_number {po!r} taken from a printed PO label", "po_number")]


def reconcile_lines(inv: InvoiceExtraction) -> tuple[InvoiceExtraction, list[Issue]]:
    """If line amounts do not add up to the printed subtotal, drop suspicious rows (negative, duplicated, 'carried forward',
    payments/deposits) when - and only when - the remaining rows then add up EXACTLY and the solution is unique."""
    sub, items = _d(inv.subtotal), inv.line_items
    if sub is None or len(items) < 2 or any(li.amount is None for li in items):
        return inv, []
    amts = [_d(li.amount) for li in items]
    if abs(sum(amts) - sub) <= CENT:
        return inv, []
    cnt, total = Counter(amts), _d(inv.total)
    sus = [i for i, (li, a) in enumerate(zip(items, amts))
           if a < 0 or cnt[a] > 1 or a == sub or a == total or _CARRY.search(li.description or "") or _PAYMENT.search(li.description or "")][:12]
    for k in range(1, min(6, len(sus)) + 1):
        sols = [c for c in combinations(sus, k) if abs(sum(a for i, a in enumerate(amts) if i not in c) - sub) <= CENT]
        if len(sols) == 1:
            drop = set(sols[0])
            kept = [li for i, li in enumerate(items) if i not in drop]
            # a dropped NEGATIVE row that is really a discount (promo, savings, scholarship...) is not thrown away: it moves to `discount`
            moved = sum((-amts[i] for i in drop if amts[i] < 0 and _STRONG.search(items[i].description or "")), D0)
            update: dict = {"line_items": kept}
            notes: list[Issue] = []
            if moved > 0 and not _d(inv.discount):
                update["discount"] = float(moved)
                notes.append(_warn("row_moved_to_discount", f"negative discount row(s) totalling {moved} moved from line items to discount", "discount"))
            gone = [f"{items[i].description or '?'} ({amts[i]})" for i in sorted(drop)]
            return (inv.model_copy(update=update),
                    [_warn("rows_dropped_to_reconcile", f"removed {len(drop)} non-item row(s) so items add up to the printed subtotal: {'; '.join(gone)[:200]}", "line_items")] + notes)
        if sols:
            return inv, []  # ambiguous -> leave it to the review flag
    return inv, []


def repair_other_charges(inv: InvoiceExtraction, text: str) -> tuple[InvoiceExtraction, list[Issue]]:
    """If subtotal - discount + tax + other_charges does not reach the total, but the missing amount is printed on a
    shipping/freight/handling line (alone or as two lines), take it as other_charges."""
    sub, total = _d(inv.subtotal), _d(inv.total)
    if sub is None or total is None:
        return inv, []
    disc, tax, other = _d(inv.discount) or Decimal(0), _d(inv.tax_amount) or Decimal(0), _d(inv.other_charges) or Decimal(0)
    gap = total - (sub - disc + tax + other)
    if abs(gap) <= CENT or gap < 0:
        return inv, []
    cands = _fee_candidates(text)[:10]
    sols = [c for k in (1, 2, 3) for c in combinations(cands, k) if abs(sum(c, Decimal(0)) - gap) <= CENT]
    if len(sols) != 1:
        return inv, []
    new = other + gap
    return (inv.model_copy(update={"other_charges": float(new)}),
            [_warn("other_charges_from_label", f"other_charges set to {new}: the missing amount equals the sum of printed fee/shipping/handling line(s)", "other_charges")])


_LEGAL_TAIL = re.compile(r"^(?:[A-Z][\w&.\-]*\s+){0,2}(?:Co\.?|Company|Ltd\.?|Limited|Inc\.?|LLC|LLP|GmbH|Corp\.?|Corporation|PLC|Pvt\.?|AG|SRL|S\.A\.)$")


def extend_vendor(inv: InvoiceExtraction, text: str) -> tuple[InvoiceExtraction, list[Issue]]:
    """A long company name can wrap onto a second header line ('Punjab Valley Power' / 'Distribution Co.'). If the next line is
    a short line ending in a legal suffix and the vendor name stops right before it, join them."""
    v = (inv.vendor_name or "").strip()
    if not v:
        return inv, []
    lines = [ln.strip() for ln in text.splitlines()]
    for i, ln in enumerate(lines[:-1]):
        if ln != v:
            continue
        # in two-column headers the continuation can be interleaved with the right-hand column: look a few lines ahead
        for nxt in lines[i + 1:i + 4]:
            if _LEGAL_TAIL.match(nxt) and not v.lower().endswith(nxt.lower()):
                full = f"{v} {nxt}"
                return (inv.model_copy(update={"vendor_name": full}),
                        [_warn("vendor_name_joined", f"vendor_name extended to {full!r}: the name continues on a following line", "vendor_name")])
    return inv, []


_INV_TIERS = [r"invoice\s*(?:no\.?|number|#|nr\.?|num\.?)",
              r"(?:receipt|bill|statement|challan|folio(?:\s*/\s*invoice)?|agreement|order|trip|repair\s+order)\s*(?:no\.?|number|#|id|nr\.?)"]


def rescue_invoice_number(inv: InvoiceExtraction, text: str) -> tuple[InvoiceExtraction, list[Issue]]:
    """Many documents (receipts, trips, repair orders...) label their own number differently. If the model returned null but exactly
    one such labelled identifier is printed on the same line, use it. Account/policy/customer numbers are never labels here."""
    if inv.invoice_number:
        return inv, []
    for tier in _INV_TIERS:
        found = {m.group(1) for m in re.finditer(r"(?i)\b(?:" + tier + r")[ \t]*[:#]?[ \t]*([A-Z0-9][A-Z0-9\-/_]{2,})", text) if any(ch.isdigit() for ch in m.group(1))}
        if len(found) == 1:
            num = next(iter(found))
            return inv.model_copy(update={"invoice_number": num}), [_warn("invoice_number_from_label", f"invoice_number {num!r} taken from the document's own labelled identifier", "invoice_number")]
        if found:
            return inv, []
    return inv, []


def apply_repairs(inv: InvoiceExtraction, text: str, default_currency: str | None = None) -> tuple[InvoiceExtraction, list[Issue]]:
    notes: list[Issue] = []
    for fn in (lambda i: infer_currency(i, text, default_currency), lambda i: rescue_po(i, text), lambda i: rescue_invoice_number(i, text), lambda i: extend_vendor(i, text), reconcile_lines,
               lambda i: repair_other_charges(i, text)):
        inv, n = fn(inv)
        notes += n
    return inv, notes
