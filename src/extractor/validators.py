"""Business-rule validators. Money uses Decimal; tolerances absorb cent rounding only."""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from .schema import InvoiceExtraction

SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "PKR", "AED", "CAD", "AUD", "INR", "CHF", "SAR", "JPY"}
CENT = Decimal("0.01")
_STREET = re.compile(r"\b(street|st|lane|road|rd|avenue|ave|boulevard|blvd|strasse|stra\u00dfe|via|suite|plot|block|court|square|yard|park|row|unit)\b", re.I)


class Issue(BaseModel):
    code: str
    severity: str  # "error" -> needs human review, "warning" -> informational
    message: str
    field: str | None = None


def _d(x: float | None) -> Decimal | None:
    return None if x is None else Decimal(str(x))


def _iso(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def validate(inv: InvoiceExtraction) -> list[Issue]:
    out: list[Issue] = []

    def err(code: str, msg: str, field: str | None = None) -> None:
        out.append(Issue(code=code, severity="error", message=msg, field=field))

    def warn(code: str, msg: str, field: str | None = None) -> None:
        out.append(Issue(code=code, severity="warning", message=msg, field=field))

    for f in ("vendor_name", "invoice_number", "invoice_date", "currency", "total"):
        v = getattr(inv, f)
        if v is None or (isinstance(v, str) and not v.strip()):
            err("missing_required", f"{f} is missing", f)
    if not inv.line_items:
        err("missing_required", "no line items found", "line_items")

    # the issuer name must be a name, not an address/phone line (a model may grab one when no name is printed)
    vn = (inv.vendor_name or "").strip()
    if vn and ((vn[0].isdigit() and _STREET.search(vn)) or re.search(r"\b(tel|phone|fax)\b|@", vn, re.I)):
        err("vendor_is_address", f"vendor_name looks like an address/contact line: {vn!r}", "vendor_name")

    # dates
    idate, ddate = _iso(inv.invoice_date), _iso(inv.due_date)
    if inv.invoice_date and idate is None:
        err("bad_date", f"invoice_date is not ISO: {inv.invoice_date!r}", "invoice_date")
    if inv.due_date and ddate is None:
        err("bad_date", f"due_date is not ISO: {inv.due_date!r}", "due_date")
    if idate and not (2000 <= idate.year <= 2100):
        warn("date_range", f"invoice_date year looks wrong: {idate.year}", "invoice_date")
    if idate and ddate and ddate < idate:
        err("due_before_invoice", "due_date is before invoice_date", "due_date")

    # currency
    if inv.currency and inv.currency.upper() not in SUPPORTED_CURRENCIES:
        err("currency_unsupported", f"currency {inv.currency!r} not in supported list", "currency")

    # lines
    line_sum = Decimal("0")
    lines_complete = bool(inv.line_items)
    for i, li in enumerate(inv.line_items, 1):
        q, u, a = _d(li.quantity), _d(li.unit_price), _d(li.amount)
        if a is None:
            lines_complete = False
            err("line_missing_amount", f"line {i} has no amount", "line_items")
            continue
        line_sum += a
        # unit prices are printed rounded to cents, so q x u can legitimately differ by up to q/2 cents
        if q is not None and u is not None:
            tol = CENT + abs(q) * Decimal("0.005")
            dp = _d(li.discount_percent)
            ok = abs(q * u - a) <= tol or (a < 0 and abs(abs(q * u) - abs(a)) <= tol) or (dp is not None and abs(q * u * (Decimal(100) - dp) / Decimal(100) - a) <= tol)
            if not ok:
                err("line_math", f"line {i}: {q} x {u} = {q * u:.2f} but amount is {a}", "line_items")

    sub = _d(inv.subtotal)
    disc = _d(inv.discount) or Decimal("0")
    tax = _d(inv.tax_amount)
    other = _d(inv.other_charges) or Decimal("0")
    total = _d(inv.total)
    if sub is not None and lines_complete and abs(line_sum - sub) > CENT:
        err("subtotal_mismatch", f"line amounts sum to {line_sum} but subtotal is {sub}", "subtotal")
    base = sub if sub is not None else (line_sum if lines_complete else None)

    rate = _d(inv.tax_rate)
    if rate is not None and tax is None:
        err("tax_missing", "tax_rate given but tax_amount missing", "tax_amount")
    if rate is not None and tax is not None and base is not None:
        expect = ((base - disc) * rate / Decimal(100)).quantize(CENT)
        if abs(expect - tax) > Decimal("0.02"):
            # only a warning: tax is often charged on a subset (taxable items, excluding shipping...). The total check
            # below still catches a wrong tax amount.
            warn("tax_math", f"{rate}% of {base - disc} = {expect} but tax_amount is {tax}", "tax_amount")

    if base is not None and total is not None:
        expect_total = base - disc + other + (tax or Decimal("0"))
        if abs(expect_total - total) > CENT:
            err("total_mismatch", f"subtotal - discount + other charges + tax = {expect_total} but total is {total}", "total")

    return out


def needs_review(issues: list[Issue]) -> bool:
    return any(i.severity == "error" for i in issues)


def _norm(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip().lower()


_EN = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
_DE = ["januar", "februar", "m\u00e4rz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember"]
_FR = ["janvier", "f\u00e9vrier", "mars", "avril", "mai", "juin", "juillet", "ao\u00fbt", "septembre", "octobre", "novembre", "d\u00e9cembre"]


def _date_variants(d: date) -> set[str]:
    """Every common way this date can be PRINTED (numeric, month names EN/DE/FR, padded or not, 2/4-digit year)."""
    names = {_EN[d.month - 1], _DE[d.month - 1], _FR[d.month - 1]}
    names |= {n[:3] for n in names}
    if d.month == 9:
        names.add("sept")
    days = {str(d.day), f"{d.day:02d}"}
    months = {str(d.month), f"{d.month:02d}"}
    years = {str(d.year), str(d.year)[-2:]}
    out: set[str] = set()
    for dd in days:
        for yy in years:
            for mm in months:
                for sep in ("/", ".", "-", " "):
                    out |= {f"{dd}{sep}{mm}{sep}{yy}", f"{mm}{sep}{dd}{sep}{yy}", f"{yy}{sep}{mm}{sep}{dd}"}
            for nm in names:
                out |= {f"{dd} {nm} {yy}", f"{nm} {dd} {yy}", f"{dd}. {nm} {yy}", f"{dd}-{nm}-{yy}", f"{nm}-{dd}-{yy}"}
    return out


def _norm_dates(x: str) -> str:
    x = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", x.lower())
    return re.sub(r"\s+", " ", x.replace(",", "")).strip()


def _has_token(t: str, v: str) -> bool:
    """Whole-token match: '135' must NOT match inside '13594027'. Boundaries only where the edge char is alphanumeric."""
    v = _norm(v)
    if not v:
        return False
    pat = re.escape(v)
    if v[0].isalnum():
        pat = r"(?<![a-z0-9])" + pat
    if v[-1].isalnum():
        pat += r"(?![a-z0-9])"
    return re.search(pat, t) is not None


def check_grounding(inv: InvoiceExtraction, text: str, alt_text: str | None = None) -> list[Issue]:
    """Values must appear in the PDF text as whole tokens (dates: in any common printed form).
    If an identifier looks whole to the main engine but not to the second one, it may be cut short (reader_mismatch)."""
    t = _norm(text)
    ta = _norm(alt_text) if alt_text else None
    out = []
    for f in ("vendor_name", "invoice_number", "po_number"):
        v = getattr(inv, f)
        if not v:
            continue
        a = _has_token(t, v)
        b = _has_token(ta, v) if ta is not None else a
        if not a and not b:
            out.append(Issue(code="not_in_document", severity="error", field=f,
                             message=f"{f} {v!r} does not appear in the PDF text (possibly invented)"))
        elif f != "vendor_name" and a and not b:
            out.append(Issue(code="reader_mismatch", severity="error", field=f,
                             message=f"{f} {v!r} is a whole token in the main PDF reader but not in the second one (the value may be cut short)"))
    td = _norm_dates(text + " " + (alt_text or ""))
    for f in ("invoice_date", "due_date"):
        v = getattr(inv, f)
        d = _iso(v)
        if d and not any(_norm_dates(var) in td for var in _date_variants(d)):
            out.append(Issue(code="date_not_in_document", severity="error", field=f,
                             message=f"{f} {v} does not appear in the PDF in any common date format (possibly misread or invented)"))
    return out


def _num_variants(x: Decimal) -> set[str]:
    x = abs(x)
    s2 = f"{x:,.2f}"
    plain = f"{x:.2f}"
    vs = {s2, plain, s2.replace(",", "X").replace(".", ",").replace("X", "."), s2.replace(",", " ").replace(".", ","),
          plain.replace(".", ",")}
    for v in list(vs):
        if v[-2:] == "00":
            vs.add(v[:-3])
        elif v[-1] == "0":
            vs.add(v[:-1])
    return vs


def _number_in_text(t: str, x: float) -> bool:
    for v in _num_variants(Decimal(str(x))):
        if re.search(r"(?<!\d)(?<!\d[.,])" + re.escape(v) + r"(?!\d)(?![.,]\d)", t):
            return True
    return False


_TAX_WORD = re.compile(r"\b(tax|taxes|vat|gst|duty|levy|assessment|mwst|ust|tva|iva|imposto)\b", re.I)
_AMOUNT = re.compile(r"(?<!\d)(?<!\d[.,])\d{1,3}(?:[., ]\d{3})*[.,]\d{2}(?!\d)|(?<!\d)(?<!\d[.,])\d+[.,]\d{2}(?!\d)")


def _parse_amount(s: str) -> Decimal | None:
    m = re.search(r"[.,](\d{2})$", s)
    if not m:
        return None
    whole = re.sub(r"[., ]", "", s[: m.start()])
    return Decimal(f"{whole}.{m.group(1)}") if whole.isdigit() else None


def _tax_sum_in_text(text: str, x: float) -> bool:
    """tax_amount may be the SUM of several printed tax lines (e.g. GST + duty). Accepted only when it equals a sum
    of up to 3 amounts that are printed on lines containing a tax word, so a made-up number cannot hide behind it."""
    cands: list[Decimal] = []
    for line in text.splitlines():
        if _TAX_WORD.search(line):
            for a in _AMOUNT.findall(line):
                v = _parse_amount(a)
                if v is not None:
                    cands.append(v)
    cands = sorted(set(cands))[:12]
    target = Decimal(str(x)).quantize(Decimal("0.01"))
    from itertools import combinations
    return any(abs(sum(c, Decimal(0)) - target) <= Decimal("0.01") for k in (2, 3) for c in combinations(cands, k))


_FEE_WORD = re.compile(r"\b(fee|fees|charge|charges|surcharge|shipping|freight|delivery|handling|postage|carriage|courier|fracht|versand|service|"
                       r"facility|recovery|processing|booking|fuel|licence|license|admin|administration|remote|inselzuschlag)\b", re.I)


def _fee_candidates(text: str) -> list[Decimal]:
    out: list[Decimal] = []
    for line in text.splitlines():
        if _FEE_WORD.search(line) and not _TAX_WORD.search(line):
            for a in _AMOUNT.findall(line):
                v = _parse_amount(a)
                if v is not None:
                    out.append(v)
    return sorted(set(out))[:12]


def _fee_sum_in_text(text: str, x: float) -> bool:
    """other_charges may be the SUM of several printed fee lines (facility + service + processing). Same safety rule as for
    taxes: only amounts from lines that carry a fee word (and no tax word), at most 4 of them."""
    from itertools import combinations
    cands, target = _fee_candidates(text), Decimal(str(x)).quantize(Decimal("0.01"))
    return any(abs(sum(c, Decimal(0)) - target) <= Decimal("0.01") for k in (2, 3, 4) for c in combinations(cands, k))


def check_numbers(inv: InvoiceExtraction, text: str, alt_text: str | None = None) -> list[Issue]:
    """Every extracted amount must literally appear in the document. Catches numbers the model calculated or invented
    (e.g. a shipping charge made up to make a wrong printed total add up). Line amounts/subtotal only warn, because
    some documents legitimately omit them."""
    t = (text + "\n" + (alt_text or "")).replace("\u00a0", " ")
    out = []
    for f, sev in (("other_charges", "error"), ("discount", "error"), ("tax_amount", "error"), ("total", "error"), ("subtotal", "warning"), ("amount_due", "warning")):
        v = getattr(inv, f)
        if v and not _number_in_text(t, v) and not (f == "tax_amount" and _tax_sum_in_text(text, v)) and not (f == "other_charges" and _fee_sum_in_text(text, v)):
            out.append(Issue(code="number_not_in_document", severity=sev, field=f,
                             message=f"{f} {v} does not appear in the PDF text (calculated or invented?)"))
    bad = [li.amount for li in inv.line_items if li.amount and not _number_in_text(t, li.amount)]
    if bad:
        out.append(Issue(code="number_not_in_document", severity="warning", field="line_items",
                         message=f"line amounts not found in the PDF text: {bad[:4]}"))
    return out


_STRONG = re.compile(r"\b(discounts?|savings?|coupons?|promo(?:tion)?s?|scholarships?|rebates?|reductions?)\b", re.I)
_WEAK = re.compile(r"\badjustments?\b", re.I)          # 'Fuel price adjustment' is a charge, 'Insurance adjustment -68.40' a deduction
_NOT_DEDUCTION = re.compile(r"\b(payments?|paid|received|deposits?|balance|if paid|within|terms)\b", re.I)
# amounts for this check: no space-grouping (so '1 105.00' = qty 1 and rate 105.00), and never a percentage ('25.00%')
_AMOUNT_STRICT = re.compile(r"(?<!\d)(?<!\d[.,])(?:\d{1,3}(?:,\d{3})+\.\d{2}|\d{1,3}(?:\.\d{3})+,\d{2}|\d+[.,]\d{2})(?!\d)(?!\s?%)")
_NEG_BEFORE = re.compile(r"(?:-|\u2212|\()\s*(?:[A-Za-z]{0,3}\.?\s*[$\u00a3\u20ac]?\s*)$")


def check_deductions(inv: InvoiceExtraction, text: str) -> list[Issue]:
    """Completeness (the mirror image of check_numbers): every deduction printed WITH an amount (discount, savings, coupon, promo,
    scholarship, rebate, or an adjustment shown with a minus/brackets) must be accounted for: either as `discount` or as a negative
    line item. Otherwise the model silently used the gross figure as the total (seen on pharmacy and medical statements)."""
    disc = _d(inv.discount) or Decimal(0)
    negs = [abs(_d(li.amount)) for li in inv.line_items if li.amount is not None and _d(li.amount) < 0]
    out, seen = [], set()
    for line in text.splitlines():
        strong, weak = _STRONG.search(line), _WEAK.search(line)
        if not (strong or weak) or _NOT_DEDUCTION.search(line):
            continue
        for m in _AMOUNT_STRICT.finditer(line):
            v = _parse_amount(m.group(0))
            if v is None or v == 0 or v in seen:
                continue
            if not strong and not _NEG_BEFORE.search(line[:m.start()]):
                continue          # an 'adjustment' only counts as a deduction when it is shown as negative
            seen.add(v)
            if abs(v - disc) <= CENT or any(abs(v - n) <= CENT for n in negs):
                continue
            out.append(Issue(code="deduction_not_captured", severity="error", field="discount",
                             message=f"the document prints a deduction of {v} ({line.strip()[:60]!r}) that is neither in discount nor a negative line item; total may be the gross figure"))
    return out
