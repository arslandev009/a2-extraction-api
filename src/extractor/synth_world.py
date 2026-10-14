"""WORLD set: 24 documents modelled on invoices/bills/receipts people really get (12 kinds x 2 variants).

SaaS subscription, freelancer, electricity bill, mobile/internet bill, restaurant receipt, grocery/electronics receipt,
medical/dental bill, wholesale invoice (per-line discounts), marketplace order, hotel folio, Pakistani sales-tax invoice,
multi-page agency/law invoice (page subtotals). Fictional businesses; amounts, taxes and layouts follow real conventions
including the awkward parts (taxes on a subset, two taxes, deposits, balance vs total, 'payable after due date', ...).
Ground truth = what is printed. Deterministic per seed.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP
from decimal import Decimal as D
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .schema import InvoiceExtraction
from .validators import needs_review, validate

SYM = {"USD": "$", "GBP": "£", "EUR": "€", "PKR": "Rs.", "AED": "AED "}


def q(x) -> D:
    return D(x).quantize(D("0.01"), ROUND_HALF_UP)


def n2(x: D, style: str = "us") -> str:
    s = f"{abs(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if style == "eu" else s


def m(x: D, cur: str, style: str = "us", code: bool = False) -> str:
    sign = "-" if x < 0 else ""
    if cur == "EUR":
        return f"{sign}{n2(x, style)} €"
    return f"{sign}{cur} {n2(x, style)}" if code else f"{sign}{SYM[cur]}{n2(x, style)}"


def dt(d: date, fmt: str) -> str:
    return d.strftime(fmt)


def rdate(rng: random.Random, lo=(2025, 6, 1), span=420, min_day=13) -> date:
    d = date(*lo) + timedelta(days=rng.randint(0, span))
    return d if d.day >= min_day else d + timedelta(days=min_day - d.day)


def item(desc, qty, unit, amount=None, dp=None) -> dict:
    qty, unit = D(str(qty)), D(str(unit))
    amt = q(qty * unit * (D(100) - D(str(dp))) / 100) if dp else q(qty * unit)
    return {"description": desc, "quantity": float(qty), "unit_price": float(unit), "amount": float(amt if amount is None else amount),
            "discount_percent": float(dp) if dp else None}


def expected(vendor, number, po, idate, ddate, cur, items, sub, disc, rate, tax, other, total) -> dict:
    f = lambda x: None if x is None else float(x)  # noqa: E731
    return {"vendor_name": vendor, "invoice_number": number, "po_number": po,
            "invoice_date": idate.isoformat() if idate else None, "due_date": ddate.isoformat() if ddate else None,
            "currency": cur, "line_items": items, "subtotal": f(sub), "discount": f(disc) if disc else None,
            "tax_rate": f(rate), "tax_amount": float(tax or 0), "other_charges": f(other) if other else None, "total": f(total)}


def S(**kw) -> dict:  # spec with defaults
    base = dict(render="doc", font="Helvetica", accent="#1f3a5f", layout="left", grid=True, zebra=False, page=A4, title="INVOICE",
                addr=[], meta=[], parties=[], columns=[], aligns=[], widths=None, rows=[], pages=None, totals=[], before=[],
                after=[], footer="", lines=[], total_bold=True, top_box=[], sections=[], totals_pos="right", banner=False)
    base.update(kw)
    return base


# ---------------------------------------------------------------- builders (each returns spec + expected)
def b_saas(v, rng):
    cur, style = ("USD", "us") if v == 0 else ("GBP", "us")
    d = rdate(rng)
    if v == 0:
        name, seats = "Kestrel Analytics, Inc.", rng.choice([8, 12, 15])
        items = [item(f"Team plan - {seats} seats x $29.00 / month (Mar 5 - Apr 5, 2026)", seats, 29), item("Extra storage 500 GB", 1, 20),
                 item("Priority support", 1, 49)]
        rate = D("8.625")
        fmt, labels = "%B %d, %Y", ("Invoice number", "Date of issue", "Date due")
        num = f"KA-{d.year}-{rng.randint(10000, 99999)}"
    else:
        name = "Lumen Cloud Ltd"
        items = [item("Unused time on Basic after 12 Mar 2026", 1, "-18.40"), item("Remaining time on Pro after 12 Mar 2026", 1, "61.20"),
                 item("Pro plan - April 2026", 1, 79)]
        rate = D("20")
        fmt, labels = "%d %b %Y", ("Invoice number", "Issue date", "Due date")
        num = f"LC{rng.randint(100000, 999999)}"
    sub = sum((D(str(i["amount"])) for i in items), D(0))
    tax = q(sub * rate / 100)
    total = sub + tax
    tl = [("Subtotal", m(sub, cur)), ((f"Sales tax (CA {rate}%)" if v == 0 else f"VAT ({rate}%)"), m(tax, cur)), ("Total", m(total, cur))]
    if v == 0:
        tl += [("Amount paid", "-" + m(total, cur)), ("Amount due", m(D(0), cur))]
    spec = S(vendor=name, addr=["548 Market St, Suite 4120", "San Francisco, CA 94104"] if v == 0 else ["Unit 9, Cedar Works", "Manchester M4 5AA"],
             title="Invoice", layout="split" if v == 0 else "left", accent="#4f46e5" if v == 0 else "#0d9488", grid=False, zebra=v == 1,
             meta=[(labels[0], num), (labels[1], dt(d, fmt)), (labels[2], dt(d, fmt) if v == 0 else dt(d + timedelta(days=14), fmt))],
             parties=[("Bill to", ["Acme Test Clinic", "12 Example Road"])], columns=["Description", "Qty", "Unit price", "Amount"],
             aligns=["L", "R", "R", "R"], rows=[[i["description"], f"{i['quantity']:g}", m(D(str(i["unit_price"])), cur), m(D(str(i["amount"])), cur)] for i in items],
             totals=tl, after=["Paid by card ending 4242 on " + dt(d, fmt) + "."] if v == 0 else ["Prorated charges reflect your plan change on 12 Mar 2026."],
             footer=f"{name} - questions? billing@example.com")
    due = d if v == 0 else d + timedelta(days=14)
    return spec, expected(name, num, None, d, due, cur, items, sub, None, rate, tax, None, total)


def b_freelancer(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, po, rate_h = "USD", "Mira Okafor Design Studio", "PO-2026-118", 95
        items = [item("UX audit and report - 18.5 hrs @ $95.00", "18.5", rate_h), item("Prototype (Figma) - 24 hrs @ $95.00", 24, rate_h),
                 item("Icon set license", 1, 150)]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        tax, rate, total, deposit = D(0), None, sub, D("1500.00")
        tl = [("Subtotal", m(sub, cur)), ("Total", m(total, cur)), ("Less deposit received (Jan 20)", "-" + m(deposit, cur)), ("Balance due", m(total - deposit, cur))]
        after = ["Payment terms: Net 15. Bank: First Example Bank, Acct 00123456, Routing 021000021.", "Late payments accrue interest at 1.5% per month."]
        due, fmt, num = d + timedelta(days=15), "%b %d, %Y", f"MO-{d.year}-0{rng.randint(10, 99)}"
    else:
        cur, name, po = "GBP", "Arjun Patel Consulting", None
        items = [item("Data platform advisory - 6 days @ £450.00", 6, 450), item("Travel expenses (rail, receipts attached)", 1, "86.40")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        rate = D("20")
        tax = q(sub * rate / 100)
        total = sub + tax
        tl = [("Net total", m(sub, cur)), ("VAT @ 20%", m(tax, cur)), ("Total due", m(total, cur))]
        after = ["VAT reg. no. GB 123 4567 89 | Company no. 12345678", "Pay by bank transfer within 14 days: Sort code 20-00-00, Account 55779911."]
        due, fmt, num = d + timedelta(days=14), "%d %B %Y", f"{d.year}-{rng.randint(10, 40):03d}"
    meta = [("Invoice no.", num), ("Invoice date", dt(d, fmt)), ("Due date", dt(due, fmt))] + ([("Your PO", po)] if po else [])
    spec = S(vendor=name, addr=["Independent contractor"], title="INVOICE", layout="right", accent="#b45309" if v == 0 else "#1d4ed8", grid=False,
             meta=meta, parties=[("Invoice to", ["Fictional Startup Inc", "Attn: Accounts payable"])], columns=["Description", "Qty", "Rate", "Amount"],
             aligns=["L", "R", "R", "R"], rows=[[i["description"], f"{i['quantity']:g}", m(D(str(i["unit_price"])), cur), m(D(str(i["amount"])), cur)] for i in items],
             totals=tl, after=after, footer="Thank you for your business!")
    return spec, expected(name, num, po, d, due, cur, items, sub, None, rate, tax, None, total)


def b_electricity(v, rng):
    cur = "PKR"
    d = rdate(rng)
    units = rng.randint(290, 520)
    if v == 0:
        name, t1, t2, fpa, addr = "Punjab Valley Power Distribution Co.", D("22.44"), D("28.91"), D("1.85"), ["Customer service: 118", "Lahore Region"]
    else:
        name, t1, t2, fpa, addr = "Capital Electric Supply Co.", D("21.95"), D("27.50"), D("2.10"), ["Helpline 118", "Islamabad Circle"]
    items = [item("Energy charges - first 200 units", 200, t1), item(f"Energy charges - next {units - 200} units", units - 200, t2),
             item("Fixed charges", 1, 200), item(f"Fuel price adjustment ({units} units)", units, fpa), item("TV licence fee", 1, 35)]
    sub = sum((D(str(i["amount"])) for i in items), D(0))
    gst, ed = q(sub * D("0.17")), q(sub * D("0.015"))
    tax = gst + ed
    total = sub + tax
    late = q(total * D("1.05"))
    due = d + timedelta(days=12)
    num = f"{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
    fmt = "%d %b %Y"
    spec = S(vendor=name, addr=addr, title="ELECTRICITY BILL", layout="split", accent="#0f766e", grid=True,
             meta=[("Bill No", num), ("Issue date", dt(d, fmt)), ("Due date", dt(due, fmt)), ("Units consumed", str(units)), ("Consumer ID", f"{rng.randint(10, 99)} {rng.randint(10000, 99999)} {rng.randint(1000000, 9999999)}")],
             parties=[("Consumer", ["Sample Home Services Ltd", "House 14, Block C"])], columns=["Description", "Units", "Rate", "Amount (Rs.)"],
             aligns=["L", "R", "R", "R"], rows=[[i["description"], f"{i['quantity']:g}", n2(D(str(i["unit_price"]))), n2(D(str(i["amount"])))] for i in items],
             totals=[("Total charges", m(sub, cur)), ("GST 17%", m(gst, cur)), ("Electricity duty 1.5%", m(ed, cur)),
                     ("Payable within due date", m(total, cur)), ("Payable after due date", m(late, cur))],
             after=["Late payment surcharge of 5% applies after the due date."], footer="Computer generated bill - no signature required")
    return spec, expected(name, num, None, d, due, cur, items, sub, None, None, tax, None, total)


def b_telecom(v, rng):
    cur = "USD"
    d = rdate(rng)
    fmt = "%b %d, %Y"
    if v == 0:
        name = "Northline Wireless"
        items = [item("Unlimited Plus plan (2 lines)", 1, "65.00"), item("Device payment 12 of 24", 1, "33.33"), item("Regulatory & admin fee", 1, "3.49")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        t1, t2 = q(sub * D("0.032")), q(sub * D("0.0725"))
        tax, rate = t1 + t2, None
        tl = [("Monthly charges", m(sub, cur)), ("Federal tax (universal service)", m(t1, cur)), ("State & local taxes", m(t2, cur)), ("Total amount due", m(sub + tax, cur))]
        prev = ("Previous balance", D("101.82"), "Payment received - thank you", D("-101.82"))
    else:
        name = "Fibernet Communications"
        items = [item("Fibre 500 Mbps broadband", 1, "59.99"), item("Wi-Fi router rental", 1, "10.00"), item("Static IP address", 1, "15.00"), item("Loyalty credit", 1, "-10.00")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        rate = D("6")
        tax = q(sub * rate / 100)
        tl = [("Subtotal", m(sub, cur)), ("Sales tax (6%)", m(tax, cur)), ("Total amount due", m(sub + tax, cur))]
        prev = ("Previous balance", D("74.99"), "Payment received", D("-74.99"))
    total = sub + tax
    due = d + timedelta(days=21)
    num = f"{rng.randint(100000000, 999999999)}"
    spec = S(vendor=name, addr=["Customer care 1-800-555-0143"], title="Your bill", layout="split", accent="#be123c" if v == 0 else "#0369a1", grid=False, zebra=True,
             meta=[("Statement number", num), ("Account number", f"{rng.randint(10**9, 10**10 - 1)}"), ("Statement date", dt(d, fmt)), ("Payment due", dt(due, fmt))],
             parties=[("Account holder", ["Demo Home Services Ltd"])], columns=["Charges this month", "Qty", "Amount"], aligns=["L", "R", "R"],
             rows=[[i["description"], f"{i['quantity']:g}", m(D(str(i["amount"])), cur)] for i in items],
             before=[f"Account summary: {prev[0]} {m(prev[1], cur)} | {prev[2]} {m(prev[3], cur)} | Balance forward {m(D(0), cur)}"],
             totals=tl, after=["Autopay is on. Your card ending 0099 will be charged on the due date."], footer="Download the app to manage your plan")
    return spec, expected(name, num, None, d, due, cur, items, sub, None, rate, tax, None, total)


def _receipt_lines(vendor, addr, head, items_lines, totals, tail, w=40):
    L = [vendor.upper().center(w)] + [a.center(w) for a in addr] + ["-" * w] + head + ["-" * w] + items_lines + ["-" * w]
    L += [f"{a:<{w - 14}}{b:>14}" for a, b in totals] + ["-" * w] + [t.center(w) if len(t) < w else t for t in tail]
    return L


def b_restaurant(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name = "PKR", "Savour Kitchen & Grill"
        menu = [("Chicken karahi (half)", 1450), ("Garlic naan", 70), ("Seekh kabab platter", 1190), ("Mint margarita", 390), ("Raita", 120), ("Gulab jamun", 280)]
        picks = rng.sample(menu, 5)
        items = [item(n, rng.choice([1, 2, 3]), p) for n, p in picks]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        svc, rate = q(sub * D("0.10")), D("16")
        tax = q(sub * rate / 100)
        total = sub + svc + tax
        tl = [("Subtotal", n2(sub)), ("Service charge 10%", n2(svc)), ("GST 16%", n2(tax)), ("TOTAL Rs.", n2(total))]
        stamp, num, other = dt(d, "%d-%m-%Y") + " 21:14", f"{rng.randint(10000, 99999)}", svc
        head = [f"Bill No: {num}", f"Date: {stamp}", "Table: 12   Waiter: Imran", "Covers: 3"]
        tail = ["GST NTN 1234567-8", "Thank you! Visit again"]
        addr = ["DHA Phase 5, Lahore", "Tel 042-111-000-111"]
    else:
        cur, name = "USD", "Maple Street Diner"
        menu = [("Classic burger", "13.50"), ("Fries", "4.75"), ("Chicken Caesar", "12.25"), ("Milkshake", "6.50"), ("Pancake stack", "10.95"), ("Coffee", "3.25")]
        picks = rng.sample(menu, 5)
        items = [item(n, rng.choice([1, 2]), p) for n, p in picks]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        rate, svc = D("8.875"), D(0)
        tax = q(sub * rate / 100)
        total = sub + tax
        tl = [("Subtotal", n2(sub)), ("Tax 8.875%", n2(tax)), ("TOTAL", "$" + n2(total))]
        stamp, num, other = dt(d, "%m/%d/%Y") + " 12:41", f"{rng.randint(1000, 9999)}", None
        head = [f"Check #: {num}", f"Date: {stamp}", "Server: Dana   Table 7", "Guests: 2"]
        tail = [f"Suggested tip: 18% ${n2(q(total * D('0.18')))}  20% ${n2(q(total * D('0.20')))}  22% ${n2(q(total * D('0.22')))}", "Thank you!"]
        addr = ["214 Maple Street", "Springfield"]
    il = [f"{i['description'][:22]:<22}{i['quantity']:g} x {n2(D(str(i['unit_price']))):>8}{n2(D(str(i['amount']))):>8}"[:44] for i in items]
    spec = S(render="receipt", vendor=name, lines=_receipt_lines(name, addr, head, il, tl, tail, 44))
    return spec, expected(name, num, None, d, None, cur, items, sub, None, rate, tax, other, total)


def b_retail(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, rate = "USD", "FreshMart Grocery #214", D("8.25")
        pool = [("Bananas (lb)", "0.59", True, False), ("Whole milk 1 gal", "3.89", False, False), ("Sourdough loaf", "4.49", False, False), ("Paper towels 6pk", "8.99", True, False),
                ("Chicken breast (lb)", "3.49", False, False), ("Orange juice", "4.29", False, False), ("Dish soap", "2.79", True, False), ("Eggs dozen", "3.19", False, False),
                ("Tomatoes (lb)", "1.99", False, False), ("Cereal", "4.59", False, False), ("Sparkling water 12pk", "5.49", True, False), ("Greek yogurt", "1.29", False, False)]
        picks = rng.sample(pool, 10)
        items, taxable = [], D(0)
        for n, p, t, _ in picks:
            qty = D(str(rng.choice([1, 1, 2, "1.34", "2.10"]))) if "(lb)" in n else D(rng.choice([1, 1, 2, 3]))
            it = item(n + (" T" if t else ""), qty, p)
            items.append(it)
            taxable += D(str(it["amount"])) if t else D(0)
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        tax, disc, other = q(taxable * rate / 100), D(0), None
        total = sub + tax
        tl = [("SUBTOTAL", n2(sub)), (f"TAX {rate}% on {n2(taxable)}", n2(tax)), ("TOTAL", n2(total))]
        num, stamp = f"{rng.randint(100000, 999999)}", dt(d, "%m/%d/%Y") + " 14:32"
        head = [f"Receipt #: {num}  Reg 03", f"Date: {stamp}", "Cashier: 0417"]
        tail = [f"VISA ****4417 AUTH {rng.randint(100000, 999999)}", "Items sold: 10   Change due: 0.00", "T = taxable item"]
        addr = ["88 Grove Avenue", "Tel 555-0172"]
        rate_out = rate
    else:
        cur, name, rate = "USD", "Volt & Co. Electronics", D("7")
        items = [item("USB-C dock 8-in-1 SKU 55102", 1, "89.99"), item("27in monitor SKU 70311", 1, "249.00"), item("Care plan 2 years SKU W-2Y", 1, "39.00")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        disc, other = D("20.00"), None
        tax = q((sub - disc) * rate / 100)
        total = sub - disc + tax
        tl = [("SUBTOTAL", n2(sub)), ("COUPON SAVE20", "-" + n2(disc)), (f"TAX {rate}%", n2(tax)), ("TOTAL", n2(total))]
        num, stamp = f"TR{rng.randint(10000, 99999)}", dt(d, "%m/%d/%Y") + " 17:05"
        head = [f"Trans #: {num}", f"Date: {stamp}", "Store 0062  Reg 2"]
        tail = ["MASTERCARD ****8821", "Returns within 30 days with receipt"]
        addr = ["Riverside Mall, Unit 14"]
        rate_out = rate
    il = [f"{i['description'][:24]:<24}{i['quantity']:g} x {n2(D(str(i['unit_price']))):>7}{n2(D(str(i['amount']))):>7}"[:44] for i in items]
    spec = S(render="receipt", vendor=name, lines=_receipt_lines(name, addr, head, il, tl, tail, 44))
    return spec, expected(name, num, None, d, None, cur, items, sub, disc if disc else None, rate_out, tax, other, total)


def b_medical(v, rng):
    cur = "USD"
    d = rdate(rng)
    fmt = "%m/%d/%Y"
    if v == 0:
        name, addr = "Riverside Family Clinic", ["400 Riverside Dr", "Suite 2"]
        items = [item("99213 Office visit, established patient", 1, "165.00"), item("85025 Complete blood count", 1, "42.00"), item("81002 Urinalysis", 1, "18.00")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        adj = D("68.40")
        ins_paid = D("120.00")
        tl = [("Total charges", m(sub, cur)), ("Insurance adjustment", "-" + m(adj, cur)), ("Net charges", m(sub - adj, cur)),
              ("Insurance payment", "-" + m(ins_paid, cur)), ("Patient balance due", m(sub - adj - ins_paid, cur))]
    else:
        name, addr = "BrightSmile Dental Group", ["19 Orchard Lane"]
        items = [item("D1110 Adult prophylaxis (cleaning)", 1, "120.00"), item("D0274 Bitewing X-rays (4)", 1, "75.00"), item("D2391 Resin filling, 1 surface", 1, "185.00")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        adj = D("95.00")
        ins_paid = D("190.00")
        tl = [("Total charges", m(sub, cur)), ("Plan discount", "-" + m(adj, cur)), ("Net charges", m(sub - adj, cur)),
              ("Insurance payment", "-" + m(ins_paid, cur)), ("Patient balance due", m(sub - adj - ins_paid, cur))]
    total = sub - adj
    num = f"ST-{rng.randint(100000, 999999)}"
    dos = d - timedelta(days=9)
    spec = S(vendor=name, addr=addr, title="PATIENT STATEMENT", layout="split", accent="#047857", grid=True,
             meta=[("Statement no.", num), ("Statement date", dt(d, fmt)), ("Date of service", dt(dos, fmt)), ("Patient ID", f"P{rng.randint(10000, 99999)}")],
             parties=[("Patient", ["J. Sample"]), ("Insurance", ["Sample Health Plan"])], columns=["Service", "Qty", "Charge"], aligns=["L", "R", "R"],
             rows=[[i["description"], "1", m(D(str(i["amount"])), cur)] for i in items], totals=tl,
             after=["Please pay the patient balance within 30 days of the statement date."], footer="Billing questions: 555-0100")
    return spec, expected(name, num, None, d, None, cur, items, sub, adj, None, D(0), None, total)


def b_wholesale(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, style, name, rate, fmt = "USD", "us", "Allied Janitorial Wholesale", D("6"), "%m/%d/%Y"
        cat = [("Trash liners 33gal (case 100)", "cs", "28.40"), ("Floor cleaner 1gal", "ea", "9.75"), ("Microfibre cloths (12)", "pk", "11.20"), ("Hand soap refill 1L", "ea", "6.30")]
        taxl, freightl = "Sales tax 6%", "Freight"
    else:
        cur, style, name, rate, fmt = "EUR", "eu", "Meier & Soehne Grosshandel", D("19"), "%d.%m.%Y"
        cat = [("Verpackungskarton 40x30 (VE 50)", "VE", "34.90"), ("Klebeband 66m (VE 36)", "VE", "27.60"), ("Stretchfolie 500mm", "Rl", "8.45"), ("Etiketten 100x150 (Rl 500)", "Rl", "12.30")]
        taxl, freightl = "MwSt 19%", "Fracht"
    items = []
    for desc, _, price in cat:
        items.append(item(desc, rng.choice([4, 6, 10, 12, 20]), price, dp=rng.choice([5, 10, 15])))
    sub = sum((D(str(i["amount"])) for i in items), D(0))
    freight = q(D(rng.choice([18, 24.5, 32])))
    tax = q(sub * rate / 100)
    total = sub + freight + tax
    due = d + timedelta(days=30)
    po = f"PO-{rng.randint(10000, 99999)}"
    num = f"INV{rng.randint(100000, 999999)}"
    spec = S(vendor=name, addr=["Distribution Centre 3", "Tel 555-0199"], title="INVOICE", layout="split", accent="#7c2d12", grid=True,
             meta=[("Invoice #", num), ("Invoice date", dt(d, fmt)), ("Customer PO", po), ("Terms", "2/10 net 30"), ("Due date", dt(due, fmt))],
             parties=[("Sold to", ["Demo Home Services Ltd", "Receiving dock B"])], columns=["Item", "Qty", "Unit price", "Disc %", "Amount"], aligns=["L", "R", "R", "R", "R"],
             rows=[[i["description"], f"{i['quantity']:g}", n2(D(str(i["unit_price"])), style), f"{i['discount_percent']:g}%", n2(D(str(i["amount"])), style)] for i in items],
             totals=[("Subtotal", m(sub, cur, style)), (freightl, m(freight, cur, style)), (taxl, m(tax, cur, style)), ("Invoice total", m(total, cur, style))],
             after=["Terms 2/10 net 30: 2% discount if paid within 10 days, otherwise net 30."], footer="Goods remain our property until paid in full")
    return spec, expected(name, num, po, d, due, cur, items, sub, None, rate, tax, freight, total)


def b_marketplace(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, fmt, rate = "USD", "ShopSphere Marketplace", "%B %d, %Y", None
        items = [item("Wireless mouse (Sold by: TechNest)", 1, "24.99"), item("Desk lamp LED (Sold by: HomeLite)", 2, "18.50"), item("HDMI cable 2m (Sold by: TechNest)", 1, "9.99")]
    else:
        cur, name, fmt, rate = "GBP", "BuyBridge UK", "%d %B %Y", D("20")
        items = [item("Running shoes UK 9 (Sold by: StrideCo)", 1, "64.00"), item("Sports socks 3pk (Sold by: StrideCo)", 2, "7.50")]
    sub = sum((D(str(i["amount"])) for i in items), D(0))
    ship, promo = D("5.99") if v == 0 else D("3.95"), D("10.00") if v == 0 else D("6.00")
    before_tax = sub - promo + ship
    tax = q(before_tax * D("0.0725")) if rate is None else q((sub - promo + ship) * rate / 100)
    if rate is not None:
        pass
    total = before_tax + tax
    order = f"{rng.randint(100, 999)}-{rng.randint(1000000, 9999999)}-{rng.randint(1000000, 9999999)}"
    num = f"INV-{rng.randint(10**9, 10**10 - 1)}"
    tl = [("Item(s) subtotal", m(sub, cur)), ("Shipping & handling", m(ship, cur)), ("Promotion applied", "-" + m(promo, cur)), ("Total before tax", m(before_tax, cur)),
          ("Estimated tax" if rate is None else "VAT (20%)", m(tax, cur)), ("Grand total", m(total, cur))]
    rows = [["Shipment 1 of 2 - arriving soon", "", "", ""]] + [[i["description"], f"{i['quantity']:g}", m(D(str(i["unit_price"])), cur), m(D(str(i["amount"])), cur)] for i in items[:-1]]
    rows += [["Shipment 2 of 2", "", "", ""]] + [[items[-1]["description"], f"{items[-1]['quantity']:g}", m(D(str(items[-1]["unit_price"])), cur), m(D(str(items[-1]["amount"])), cur)]]
    spec = S(vendor=name, addr=["Order invoice"], title="Final order invoice", layout="left", accent="#c2410c", grid=False, zebra=True,
             meta=[("Invoice number", num), ("Order #", order), ("Order date", dt(d - timedelta(days=3), fmt)), ("Invoice date", dt(d, fmt))],
             parties=[("Ship to", ["Fictional Startup Inc", "12 Example Road"])], columns=["Item", "Qty", "Price", "Item total"], aligns=["L", "R", "R", "R"], rows=rows,
             totals=tl, after=["Payment method: card ending 7788."], footer="This is not a payment receipt for the seller's own records")
    other = ship
    return spec, expected(name, num, None, d, None, cur, items, sub, promo, rate, tax, other, total)


def b_hotel(v, rng):
    d = rdate(rng)
    nights = 3
    if v == 0:
        cur, style, name, fmt = "EUR", "eu", "Hotel Alpenblick", "%d.%m.%Y"
        rate_n = D("142.00")
        items = [item(f"Room 412 Deluxe - night of {dt(d - timedelta(days=nights - k), '%d.%m.%Y')}", 1, rate_n) for k in range(nights)]
        items += [item("Breakfast buffet (2 pers.)", 3, "38.00"), item("Parking garage", 3, "18.00")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        svc = q(sub * D("0.05"))
        vat, city = q((sub + svc) * D("0.10")), D("6.00") * nights
        tax = vat + city
        tl = [("Net amount", m(sub, cur, style)), ("Service charge 5%", m(svc, cur, style)), ("VAT 10%", m(vat, cur, style)), ("City tax (2 guests x 3 nights)", m(city, cur, style)), ("Gross total", m(sub + svc + tax, cur, style))]
        other, rate, total = svc, None, sub + svc + tax
    else:
        cur, style, name, fmt = "USD", "us", "Harborview Suites", "%m/%d/%Y"
        items = [item(f"Suite 8F - night of {dt(d - timedelta(days=nights - k), '%m/%d/%Y')}", 1, "219.00") for k in range(nights)] + [item("Resort fee", 3, "28.00")]
        sub = sum((D(str(i["amount"])) for i in items), D(0))
        occ, tour = q(sub * D("0.12")), q(sub * D("0.015"))
        tax = occ + tour
        tl = [("Room & fees", m(sub, cur)), ("Occupancy tax 12%", m(occ, cur)), ("Tourism assessment 1.5%", m(tour, cur)), ("Total charges", m(sub + tax, cur))]
        other, rate, total = None, None, sub + tax
    tl += [("Paid by Visa", "-" + m(total, cur, style)), ("Balance", m(D(0), cur, style))]
    num = f"F{rng.randint(100000, 999999)}"
    spec = S(vendor=name, addr=["Guest folio"], title="Guest Invoice", layout="split", accent="#6d28d9", grid=False, zebra=True,
             meta=[("Folio / Invoice No", num), ("Invoice date", dt(d, fmt)), ("Arrival", dt(d - timedelta(days=nights), fmt)), ("Departure", dt(d, fmt)), ("Room", "412" if v == 0 else "8F")],
             parties=[("Guest", ["Sample Traveller"])], columns=["Description", "Qty", "Rate", "Amount"], aligns=["L", "R", "R", "R"],
             rows=[[i["description"], f"{i['quantity']:g}", n2(D(str(i["unit_price"])), style), n2(D(str(i["amount"])), style)] for i in items], totals=tl,
             after=["Check-out time 11:00."], footer="We hope to welcome you again")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, rate, tax, other, total)


def b_pk_tax(v, rng):
    cur, d = "PKR", rdate(rng)
    if v == 0:
        name, rows_in, further = "Zafar Trading Co.", [("Cotton fabric 60in (m)", 400, "850.00"), ("Polyester lining (m)", 250, "420.00"), ("Packing & labels", 1, "12500.00")], True
    else:
        name, rows_in, further = "Metro Packaging Industries", [("Corrugated cartons 5-ply", 1200, "145.00"), ("Shrink wrap rolls", 40, "1850.00")], False
    items = [item(n, qn, p) for n, qn, p in rows_in]
    sub = sum((D(str(i["amount"])) for i in items), D(0))
    st = q(sub * D("0.18"))
    ft = q(sub * D("0.03")) if further else D(0)
    tax = st + ft
    total = sub + tax
    num = f"ZT/{d.year}/{rng.randint(100, 999):04d}" if v == 0 else f"MP-{rng.randint(1000, 9999)}"
    rate = None if further else D("18")
    rows = [[str(k + 1), i["description"], f"{i['quantity']:g}", n2(D(str(i["unit_price"]))), n2(D(str(i["amount"]))), "18%", n2(q(D(str(i["amount"])) * D("0.18"))),
             n2(q(D(str(i["amount"])) * D("1.18")))] for k, i in enumerate(items)]
    tl = [("Total value excl. sales tax", m(sub, cur)), ("Sales tax 18%", m(st, cur))] + ([("Further tax 3%", m(ft, cur))] if further else []) + [("Total invoice value", m(total, cur))]
    spec = S(vendor=name, addr=["Industrial Estate, Lahore", f"NTN {rng.randint(1000000, 9999999)}-{rng.randint(1, 9)} | STRN {rng.randint(10, 99)}-00-{rng.randint(1000, 9999)}-{rng.randint(100, 999)}-{rng.randint(10, 99)}"],
             title="SALES TAX INVOICE", layout="split", accent="#14532d", grid=True,
             meta=[("Invoice No", num), ("Date", dt(d, "%d-%m-%Y")), ("Buyer NTN", f"{rng.randint(1000000, 9999999)}-{rng.randint(1, 9)}")],
             parties=[("Buyer", ["Demo Home Services Ltd", "Karachi"])], columns=["#", "Description", "Qty", "Rate", "Value excl. ST", "ST %", "Sales tax", "Value incl. ST"],
             aligns=["R", "L", "R", "R", "R", "R", "R", "R"], widths=[8, 52, 14, 20, 26, 12, 22, 26], rows=rows, totals=tl,
             after=["Goods once sold will not be taken back."], footer="Computer generated invoice")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, rate, tax, None, total)


def b_agency(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, fmt, n, rate_h, vat = "USD", "Calloway & Reed LLP", "%m/%d/%Y", 34, [(" Partner", 520), ("Associate", 310), ("Paralegal", 140)], None
    else:
        cur, name, fmt, n, rate_h, vat = "GBP", "Northgate Creative Agency", "%d %b %Y", 28, [("Creative director", 180), ("Designer", 95), ("Producer", 85)], D("20")
    tasks = ["Review contract draft", "Client call", "Prepare brief", "Concept development", "Revisions round", "Research", "Filing and correspondence", "Workshop", "Asset production"]
    items, rows, start = [], [], d - timedelta(days=60)
    for k in range(n):
        who, rt = rate_h[k % 3]
        hrs = D(str(rng.choice(["0.5", "1.0", "1.5", "2.0", "3.0", "0.75"])))
        it = item(f"{rng.choice(tasks)} ({who.strip()})", hrs, rt)
        items.append(it)
        rows.append([dt(start + timedelta(days=k + rng.randint(0, 1)), fmt), it["description"], f"{hrs:g}", n2(D(rt)), n2(D(str(it["amount"])))])
    sub = sum((D(str(i["amount"])) for i in items), D(0))
    disb = q(D(rng.choice([212.40, 385.00, 96.75])))
    tax = q(sub * vat / 100) if vat else D(0)
    total = sub + disb + tax
    per = 12
    chunks, run = [], D(0)
    for p in range(0, n, per):
        part = rows[p:p + per]
        page_sum = sum((D(r[4].replace(",", "")) for r in part), D(0))
        run += page_sum
        extra = []
        if p > 0:
            extra.append(["", "Brought forward", "", "", n2(run - page_sum)])
        chunks.append(extra + part + ([["", "Carried forward", "", "", n2(run)]] if p + per < n else []))
    tl = [("Total fees", m(sub, cur)), ("Disbursements", m(disb, cur))] + ([("VAT 20%", m(tax, cur))] if vat else []) + [("Total due", m(total, cur))]
    num = f"{d.year}-{rng.randint(1000, 9999)}"
    spec = S(vendor=name, addr=["Professional services"], title="INVOICE", layout="split", accent="#374151", grid=False, zebra=True,
             meta=[("Invoice no.", num), ("Date", dt(d, fmt)), ("Matter", f"M-{rng.randint(100, 999)}"), ("Payment terms", "30 days")],
             parties=[("Client", ["Fictional Startup Inc"])], columns=["Date", "Description", "Hours", "Rate", "Amount"], aligns=["L", "L", "R", "R", "R"],
             widths=[24, 80, 16, 20, 26], pages=chunks, totals=tl, footer="Page of pages shown in footer of each page")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, vat, tax, disb, total)  # terms say "30 days", no date printed


BUILDERS = [("saas", b_saas), ("freelancer", b_freelancer), ("electricity", b_electricity), ("telecom", b_telecom), ("restaurant", b_restaurant),
            ("retail", b_retail), ("medical", b_medical), ("wholesale", b_wholesale), ("marketplace", b_marketplace), ("hotel", b_hotel),
            ("pk_tax", b_pk_tax), ("agency", b_agency)]


# ---------------------------------------------------------------- rendering
def render(spec: dict, path: Path) -> None:
    if spec["render"] == "receipt":
        ps = ParagraphStyle("r", fontName="Courier", fontSize=8, leading=9.6)
        story = [Paragraph(l.replace(" ", "&nbsp;") or "&nbsp;", ps) for l in spec["lines"]]
        h = (len(spec["lines"]) * 9.6 + 40)
        SimpleDocTemplate(str(path), pagesize=(88 * mm, max(h, 120 * mm / 2)), leftMargin=4 * mm, rightMargin=4 * mm, topMargin=8, bottomMargin=8, invariant=1).build(story)
        return
    f, acc = spec["font"], colors.HexColor(spec["accent"])
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontName=f, fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, textColor=colors.grey)
    big = ParagraphStyle("h", parent=body, fontName=f + "-Bold" if f == "Helvetica" else f, fontSize=17, leading=21, textColor=acc)
    ttl = ParagraphStyle("t", parent=body, fontSize=14, leading=18, textColor=acc)
    vend = [Paragraph(spec["vendor"], big)] + [Paragraph(a, body) for a in spec["addr"]]
    meta_t = Table([[Paragraph(f"<b>{a}</b>", body), Paragraph(b, body)] for a, b in spec["meta"]], colWidths=[34 * mm, 48 * mm], hAlign="LEFT")
    story = []
    if spec["layout"] == "split":
        story.append(Table([[vend, [Paragraph(spec["title"], ttl), meta_t]]], colWidths=[88 * mm, 88 * mm]))
    elif spec["layout"] == "right":
        story += [Table([[vend, [Paragraph(spec["title"], ttl)]]], colWidths=[100 * mm, 76 * mm]), Spacer(1, 6), meta_t]
    else:
        if spec["banner"]:
            bt = Table([[Paragraph(f'<font color="white" size="16"><b>{spec["vendor"]}</b></font>', body)]], colWidths=[178 * mm])
            bt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), acc), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
            story += [bt, Spacer(1, 3)] + vend[1:] + [Spacer(1, 4), Paragraph(spec["title"], ttl), meta_t]
        else:
            story += vend + [Spacer(1, 4), Paragraph(spec["title"], ttl), meta_t]
    story.append(Spacer(1, 8))
    if spec["parties"]:
        story.append(Table([[[Paragraph(f"<b>{a}</b>", body)] + [Paragraph(x, body) for x in lines] for a, lines in spec["parties"]]]))
        story.append(Spacer(1, 8))
    if spec["top_box"]:
        cells = [[Paragraph(f'<font size="7.5" color="grey">{a}</font><br/><font size="15"><b>{b}</b></font>', body) for a, b in spec["top_box"]]]
        tb = Table(cells, colWidths=[178 / len(spec["top_box"]) * mm] * len(spec["top_box"]))
        tb.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, acc), ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                                ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [tb, Spacer(1, 8)]
    for b in spec["before"]:
        story += [Paragraph(b, body), Spacer(1, 6)]
    widths = [w * mm for w in spec["widths"]] if spec["widths"] else None
    al = {"L": "LEFT", "R": "RIGHT"}

    def table(rows, first, cols=None, aligns=None, wd=None):
        cols, aligns = cols or spec["columns"], aligns or spec["aligns"]
        wd = [w * mm for w in wd] if wd else widths
        data = [[Paragraph(f"<b>{c}</b>", body) for c in cols]] + \
               [[Paragraph(str(c), body) if k == 0 or aligns[k] == "L" else str(c) for k, c in enumerate(r)] for r in rows]
        t = Table(data, colWidths=wd, repeatRows=1)
        st = [("FONTNAME", (0, 0), (-1, -1), f), ("FONTSIZE", (0, 1), (-1, -1), 8.5), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.8, acc)]
        for k, a in enumerate(aligns):
            st.append(("ALIGN", (k, 0), (k, -1), al[a]))
        if spec["grid"]:
            st.append(("GRID", (0, 0), (-1, -1), 0.4, colors.grey))
        if spec["zebra"]:
            st += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")])]
        t.setStyle(TableStyle(st))
        return t

    if spec["pages"]:
        for pi, chunk in enumerate(spec["pages"]):
            story.append(table(chunk, pi == 0))
            if pi < len(spec["pages"]) - 1:
                story += [Spacer(1, 4), Paragraph(f"Page {pi + 1} of {len(spec['pages'])}", small), PageBreak()]
            else:
                story.append(Spacer(1, 6))
    elif spec["sections"]:
        for sec in spec["sections"]:
            story += [Paragraph(f"<b>{sec['title']}</b>", body), Spacer(1, 2), table(sec["rows"], True, sec["columns"], sec["aligns"], sec.get("widths")), Spacer(1, 8)]
    else:
        story += [table(spec["rows"], True), Spacer(1, 8)]
    tt = Table([[a, b] for a, b in spec["totals"]], colWidths=[62 * mm, 36 * mm], hAlign=spec["totals_pos"].upper())
    tst = [("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), f), ("FONTSIZE", (0, 0), (-1, -1), 9), ("LINEABOVE", (0, -1), (-1, -1), 0.5, colors.black)]
    tt.setStyle(TableStyle(tst))
    story += [tt, Spacer(1, 10)] + [Paragraph(a, body) for a in spec["after"]] + [Spacer(1, 12), Paragraph(spec["footer"], small)]
    if spec["pages"]:
        story.append(Paragraph(f"Page {len(spec['pages'])} of {len(spec['pages'])}", small))
    SimpleDocTemplate(str(path), pagesize=spec["page"], leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm, invariant=1).build(story)



# ================================================================= KIT 3: new kinds and new design features
def _rows(items, cur, style="us", decimals=2):
    return [[i["description"], f"{i['quantity']:g}", (f"{D(str(i['unit_price'])):f}" if decimals == 3 else n2(D(str(i["unit_price"])), style)),
             n2(D(str(i["amount"])), style) if D(str(i["amount"])) >= 0 else "-" + n2(D(str(i["amount"])), style)] for i in items]


def _sum(items):
    return sum((D(str(i["amount"])) for i in items), D(0))


def b3_water(v, rng):
    cur, d, fmt = "USD", rdate(rng), "%b %d, %Y"
    name = ["Riverton Water & Sewer Authority", "Lakeshore Municipal Utilities"][v]
    ccf = D(rng.choice(["14.2", "18.7", "11.4"]))
    items = [item("Base service charge (5/8 in meter)", 1, "12.50"), item("Water tier 1 (first 6 CCF)", 6, "3.85"), item(f"Water tier 2 ({ccf - 6} CCF)", ccf - 6, "4.62"),
             item(f"Sewer charge ({ccf} CCF)", ccf, "5.10"), item("Stormwater fee", 1, "6.75")]
    sub, prev = _sum(items), D(0) if v == 0 else D("54.20")
    due, acct, num = d + timedelta(days=21), f"{rng.randint(10, 99)}-{rng.randint(10000, 99999)}-{rng.randint(10, 99)}", f"WB-{rng.randint(100000, 999999)}"
    spec = S(vendor=name, addr=["Customer service 555-0150"], title="Water & Sewer Bill", layout="left", banner=True, accent="#0e7490", grid=False, zebra=True, font="Helvetica",
             top_box=[("Amount due", m(sub + prev, cur)), ("Pay by", dt(due, fmt)), ("Account", acct)],
             meta=[("Bill number", num), ("Bill date", dt(d, fmt)), ("Service period", f"{dt(d - timedelta(days=30), fmt)} - {dt(d, fmt)}")],
             parties=[("Service address", ["12 Example Road"])], columns=["Description", "Usage", "Rate", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur),
             totals=[("Previous balance", m(prev, cur)), ("Total current charges", m(sub, cur)), ("Total amount due", m(sub + prev, cur))], totals_pos="left",
             after=["A late fee of 1.5% applies to balances unpaid after the due date."], footer="Pay online at example.gov/water")
    return spec, expected(name, num, None, d, due, cur, items, sub, None, None, D(0), None, sub)


def b3_car(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, days, fmt = "USD", "Skyline Car Rental", 4, "%m/%d/%Y"
        items = [item("Compact car - 4 days @ $49.99", days, "49.99"), item("Collision damage waiver", days, "24.99"), item("GPS navigation", days, "8.00")]
        sub = _sum(items)
        fees = [("Concession recovery fee 11.1%", q(sub * D("0.111"))), ("Vehicle licence fee ($2.00/day)", D("2.00") * days), ("Customer facility charge ($6.00/day)", D("6.00") * days)]
        rate = D("7.5")
        note = "A pre-authorisation hold of $250.00 was placed on your card."
    else:
        cur, name, days, fmt = "GBP", "Cityline Car Hire", 3, "%d/%m/%Y"
        items = [item("Group B compact - 3 days @ £42.00", days, "42.00"), item("Additional driver", days, "6.00")]
        sub = _sum(items)
        fees = [("Premium location fee", D("25.00"))]
        rate = D("20")
        note = "Fuel policy: full to full. Deposit hold of £150.00 released within 7 days."
    other = sum((f[1] for f in fees), D(0))
    tax = q((sub + other) * rate / 100)
    total = sub + other + tax
    num = f"RA{rng.randint(1000000, 9999999)}"
    tl = [("Subtotal", m(sub, cur))] + [(a, m(b, cur)) for a, b in fees] + [(f"{'Sales tax' if v == 0 else 'VAT'} {rate}%", m(tax, cur)), ("Total charges", m(total, cur))]
    spec = S(vendor=name, addr=["Rental receipt"], title="RENTAL INVOICE", layout="split", accent="#b91c1c" if v == 0 else "#1e40af", grid=True, font="Times-Roman" if v == 1 else "Helvetica",
             meta=[("Agreement no.", num), ("Invoice date", dt(d, fmt)), ("Pick-up", dt(d - timedelta(days=days), fmt)), ("Return", dt(d, fmt)), ("Driver", "A. Sample")],
             columns=["Charge", "Days", "Rate", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur), totals=tl, after=[note], footer="Thank you for renting with us")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, rate, tax, other, total)


def b3_airline(v, rng):
    d = rdate(rng)
    cur, style, name, fmt = (("USD", "us", "SkyBridge Airways", "%d %b %Y") if v == 0 else ("EUR", "eu", "Nordlicht Air", "%d.%m.%Y"))
    fare = D(rng.choice(["412.00", "389.00", "455.00"]))
    parts = [D("12.30"), D("38.00"), D("5.60"), D("23.10")]
    taxes = sum(parts, D(0))
    items = [item("Air transportation - economy, one way", 1, fare)]
    total = fare + taxes
    num = f"{rng.randint(10, 99)}-{rng.randint(10000000, 99999999)}"
    spec = S(vendor=name, addr=["Electronic ticket receipt"], title="Receipt", layout="left", accent="#075985", grid=False, font="Helvetica",
             top_box=[("Total paid", m(total, cur, style)), ("Booking ref", "K7J2PQ"), ("Ticket", f"176-{rng.randint(1000000000, 9999999999)}")],
             meta=[("Receipt number", f"R-{num}"), ("Issue date", dt(d, fmt)), ("Passenger", "SAMPLE/TRAVELLER MR")],
             columns=["Description", "Qty", "Unit", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur, style),
             totals=[("Fare", m(fare, cur, style)), ("Taxes, fees and charges", m(taxes, cur, style)), ("Total", m(total, cur, style))],
             after=["Tax and fee breakdown: " + " | ".join(f"{c} {n2(a, style)}" for c, a in zip(["XX", "YQ", "ZZ", "AA"], parts)),
                    "Flight 214, seat 18C. Baggage: 1 piece, 23 kg."], footer="This receipt is not a boarding pass")
    return spec, expected(name, f"R-{num}", None, d, None, cur, items, fare, None, None, taxes, None, total)


def b3_ride(v, rng):
    d = rdate(rng)
    cur, name = (("USD", "Zippy Rides") if v == 0 else ("GBP", "Hopa Cabs"))
    items = [item("Trip fare (7.4 mi, 18 min)", 1, "18.40"), item("Booking fee", 1, "2.75"), item("Tolls", 1, "4.50"), item("Promo code SAVE5", 1, "-5.00"), item("Tip", 1, "3.00")]
    if v == 1:
        items = [item("Trip fare (9.1 mi, 26 min)", 1, "21.80"), item("Service fee", 1, "1.95"), item("Tip", 1, "2.50")]
    total = _sum(items)
    num = f"ZR-{rng.choice('ABCDEFGH')}{rng.randint(10000, 99999)}"
    spec = S(vendor=name, addr=["Your ride receipt"], title="Thanks for riding", layout="left", accent="#111827", grid=False, font="Helvetica", page=letter,
             top_box=[("Total", m(total, cur)), ("Date", dt(d, "%b %d, %Y"))],
             meta=[("Trip ID", num), ("Pickup", "14:05  Gulberg Main Blvd"), ("Drop-off", "14:23  DHA Phase 5"), ("Driver", "Imran")],
             columns=["Description", "Qty", "Rate", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur), totals=[("Total", m(total, cur))], totals_pos="left",
             after=["Paid with Visa ending 4242.", "Questions about this fare? Visit help.example.com"], footer="Rate your trip in the app")
    return spec, expected(name, num, None, d, None, cur, items, None, None, None, D(0), None, total)


def b3_repair(v, rng):
    d = rdate(rng)
    cur, name, rate = "USD", ["Hollis Auto Service", "Greenline Motors Workshop"][v], D("7")
    parts = [item("Oil filter", 1, "9.80"), item("Synthetic oil 5W-30 (qt)", 5, "8.25"), item("Brake pads, front set", 1, "74.90")]
    labor = [item("Oil and filter change", D("0.5"), "110.00"), item("Brake pad replacement", D("1.8"), "110.00")]
    if v == 1:
        parts = [item("Air filter", 1, "21.40"), item("Spark plugs (set of 4)", 1, "36.00"), item("Wiper blades (pair)", 1, "27.50")]
        labor = [item("Tune-up", D("1.5"), "95.00"), item("Diagnostics", D("1.0"), "95.00")]
    ps, ls = _sum(parts), _sum(labor)
    sub, shop = ps + ls, q(ls * D("0.05"))
    tax = q(ps * rate / 100)
    total = sub + shop + tax
    items = parts + labor
    num = f"RO-{rng.randint(10000, 99999)}"
    spec = S(vendor=name, addr=["Repair order"], title="REPAIR INVOICE", layout="split", accent="#9a3412", grid=True, font="Helvetica",
             meta=[("Repair order #", num), ("Date out", dt(d, "%m/%d/%Y")), ("Odometer", f"{rng.randint(41000, 98000)} mi"), ("VIN", "1HGCM82633A004352")],
             sections=[{"title": "Parts", "columns": ["Description", "Qty", "Price", "Amount"], "aligns": ["L", "R", "R", "R"], "rows": _rows(parts, cur)},
                       {"title": "Labor", "columns": ["Description", "Hours", "Rate", "Amount"], "aligns": ["L", "R", "R", "R"], "rows": _rows(labor, cur)}],
             totals=[("Parts", m(ps, cur)), ("Labor", m(ls, cur)), ("Subtotal", m(sub, cur)), ("Shop supplies (5% of labor)", m(shop, cur)),
                     ("Sales tax 7% (parts only)", m(tax, cur)), ("Total", m(total, cur))], after=["12 month / 12,000 mile warranty on parts and labor."], footer="Thank you")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, rate, tax, shop, total)


def b3_tuition(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, fmt = "PKR", "Crescent Grammar School", "%d/%m/%Y"
        items = [item("Tuition fee - Term 2", 1, "45000.00"), item("Laboratory fee", 1, "3000.00"), item("Transport fee", 1, "8000.00"), item("Annual charges", 1, "5000.00")]
        disc, dname = D("9000.00"), "Merit scholarship (20% of tuition)"
    else:
        cur, name, fmt = "USD", "Westbrook Academy", "%m/%d/%Y"
        items = [item("Tuition - Spring semester", 1, "6400.00"), item("Technology fee", 1, "180.00"), item("Activity fee", 1, "95.00")]
        disc, dname = D("640.00"), "Sibling discount (10% of tuition)"
    sub = _sum(items)
    total = sub - disc
    due = d + timedelta(days=15)
    num = f"CH-{rng.randint(100000, 999999)}"
    spec = S(vendor=name, addr=["Fee challan"], title="FEE INVOICE", layout="left", banner=True, accent="#166534", grid=True, font="Times-Roman",
             top_box=[("Net payable", m(total, cur)), ("Due date", dt(due, fmt))],
             meta=[("Challan no.", num), ("Issue date", dt(d, fmt)), ("Student ID", f"S{rng.randint(10000, 99999)}"), ("Class", "8-B")],
             columns=["Fee head", "Qty", "Rate", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur),
             totals=[("Total fees", m(sub, cur)), (dname, "-" + m(disc, cur)), ("Net payable", m(total, cur))],
             after=["Late fee of 500 applies after the due date." if v == 0 else "A $50 late fee applies after the due date."], footer="Bank copy / Student copy")
    return spec, expected(name, num, None, d, due, cur, items, sub, disc, None, D(0), None, total)


def b3_rent(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, fmt = "GBP", "Oakline Lettings", "%d %B %Y"
        items = [item("Rent - March 2026", 1, "1250.00"), item("Service charge", 1, "85.00"), item("Parking space 14", 1, "60.00")]
        rate, tax = None, D(0)
        vlab = None
    else:
        cur, name, fmt = "AED", "Marina Heights Property Mgmt", "%d-%b-%Y"
        items = [item("Monthly rent - Unit 2204", 1, "6500.00"), item("Service fee", 1, "350.00")]
        rate, tax = D("5"), q(D("350.00") * D("0.05"))
        vlab = "VAT 5% (service fee only)"
    sub = _sum(items)
    total = sub + tax
    due = d + timedelta(days=5)
    num = f"RENT-{rng.randint(1000, 9999)}"
    tl = [("Subtotal", m(sub, cur))] + ([(vlab, m(tax, cur))] if vlab else []) + [("Total due", m(total, cur))]
    spec = S(vendor=name, addr=["Tenancy invoice"], title="Rent Invoice", layout="right", accent="#4b5563", grid=False, zebra=True, font="Times-Roman",
             meta=[("Invoice no.", num), ("Invoice date", dt(d, fmt)), ("Due date", dt(due, fmt)), ("Tenancy ref", f"TN-{rng.randint(100, 999)}")],
             parties=[("Tenant", ["A. Sample"]), ("Property", ["Flat 14, Sample Court"])], columns=["Description", "Qty", "Rate", "Amount"], aligns=["L", "R", "R", "R"],
             rows=_rows(items, cur), totals=tl, after=["Please pay by standing order to the account on your tenancy agreement."], footer="Thank you for your prompt payment")
    return spec, expected(name, num, None, d, due, cur, items, sub, None, rate, tax, None, total)


def b3_courier(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, fmt, rate = "USD", "Swiftline Express", "%m/%d/%Y", D("20")
        items = [item("Express Worldwide 2.5 kg - zone 4", 1, "64.20")]
        fuel, remote, fl = q(D("64.20") * D("0.145")), D("18.00"), "Fuel surcharge 14.5%"
    else:
        cur, name, fmt, rate = "EUR", "Parcelo Logistik", "%d.%m.%Y", D("19")
        items = [item("Paket Europa 5 kg - Zone 2", 1, "31.90")]
        fuel, remote, fl = q(D("31.90") * D("0.12")), D("7.50"), "Fuel surcharge 12%"
    sub = _sum(items)
    other = fuel + remote
    tax = q((sub + other) * rate / 100)
    total = sub + other + tax
    style = "eu" if v == 1 else "us"
    num = f"SX-{rng.randint(10000000, 99999999)}"
    spec = S(vendor=name, addr=["Shipping invoice"], title="INVOICE", layout="split", accent="#c2410c", grid=True, font="Helvetica",
             meta=[("Invoice no.", num), ("Invoice date", dt(d, fmt)), ("Waybill (AWB)", f"{rng.randint(1000000000, 9999999999)}"), ("Shipper ref", f"REF-{rng.randint(1000, 9999)}")],
             columns=["Service", "Qty", "Rate", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur, style),
             totals=[("Freight charges", m(sub, cur, style)), (fl, m(fuel, cur, style)), ("Remote area delivery" if v == 0 else "Inselzuschlag", m(remote, cur, style)),
                     (f"Duties & taxes (VAT {rate}%)", m(tax, cur, style)), ("Total", m(total, cur, style))], after=["Duties and taxes were pre-paid by the shipper."], footer="Terms apply")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, rate, tax, other, total)


def b3_event(v, rng):
    d = rdate(rng)
    cur, name, qn = (("USD", "Ticketly", 3) if v == 0 else ("GBP", "SeatSmart", 2))
    price = D("45.00") if v == 0 else D("38.50")
    items = [item(f"General admission - Summer Fest ({dt(d + timedelta(days=30), '%b %d')})", qn, price)]
    sub = _sum(items)
    f1, f2, f3 = D("8.50") * qn, D("3.00") * qn, D("4.95")
    other = f1 + f2 + f3
    total = sub + other
    num = f"{rng.randint(10, 99)}-{rng.randint(10000, 99999)}/{rng.choice(['NY', 'MIA', 'LON'])}"
    tl = [("Tickets", m(sub, cur)), (f"Service fee ({qn} x 8.50)", m(f1, cur)), (f"Facility charge ({qn} x 3.00)", m(f2, cur)), ("Order processing fee", m(f3, cur)), ("Order total", m(total, cur))]
    spec = S(vendor=name, addr=["Order confirmation and receipt"], title="Order receipt", layout="left", banner=True, accent="#7e22ce", grid=False, zebra=True, font="Helvetica",
             meta=[("Order #", num), ("Order date", dt(d, "%B %d, %Y")), ("Delivery", "Mobile tickets")], columns=["Event", "Qty", "Price", "Amount"], aligns=["L", "R", "R", "R"],
             rows=_rows(items, cur), totals=tl, totals_pos="left", after=["All sales are final. Fees are non-refundable."], footer="Keep this receipt for your records")
    return spec, expected(name, num, None, d, None, cur, items, sub, None, None, D(0), other, total)


def b3_pharmacy(v, rng):
    d = rdate(rng)
    name, addr = (("CareFirst Pharmacy #88", ["210 Elm Street"]) if v == 0 else ("Wellspring Drugstore", ["Main Plaza, Shop 4"]))
    items = [item(f"Rx {rng.randint(1000000, 9999999)} Atorvastatin 20mg", 1, "42.60"), item(f"Rx {rng.randint(1000000, 9999999)} Metformin 500mg", 1, "18.40"), item("Vitamin D3 1000IU 90ct", 1, "9.99")]
    sub = _sum(items)
    cover = D("48.00") if v == 0 else D("39.50")
    total = sub - cover
    num = f"RX{rng.randint(100000, 999999)}"
    tl = [("TOTAL RETAIL PRICE", n2(sub)), ("INSURANCE SAVINGS", "-" + n2(cover)), ("YOU PAID", "$" + n2(total))]
    il = [f"{i['description'][:30]:<30}{n2(D(str(i['amount']))):>10}" for i in items]
    head = [f"Receipt #: {num}", f"Date: {dt(d, '%m/%d/%Y')} 10:12", "Pharmacist: R. Khan"]
    spec = S(render="receipt", vendor=name, lines=_receipt_lines(name, addr, head, il, tl, ["Plan: SAMPLE HEALTH  Member ID 99-1234", "Counselling is available on request"], 44))
    return spec, expected(name, num, None, d, None, "USD", items, sub, cover, None, D(0), None, total)


def b3_usage(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, style, rate, vat = "USD", "Nimbus API Inc.", "us", None, "Tax: reverse charge, no tax applied"
        items = [item("API requests - first 1,000 (thousands) @ $0.40 per 1k", 1000, "0.40"), item("API requests - next 2,300 (thousands) @ $0.30 per 1k", 2300, "0.30"),
                 item("Storage, GB-month", 840, "0.023"), item("Startup program credit", 1, "-250.00")]
        num = "in_1Q8w2eZvKYlo"
    else:
        cur, name, style, rate, vat = "EUR", "Stratus Data GmbH", "eu", D("19"), None
        items = [item("Compute hours (vCPU)", 1450, "0.045"), item("Object storage, GB-month", 2200, "0.018"), item("Support plan - Business", 1, "99.00")]
        num = "SD-2026-00417"
    sub = _sum(items)
    tax = q(sub * rate / 100) if rate else D(0)
    total = sub + tax
    po = "7781-A"
    tl = [("Subtotal", m(sub, cur, style))] + ([(f"VAT {rate}%", m(tax, cur, style))] if rate else [("Tax (reverse charge)", m(D(0), cur, style))]) + [("Total", m(total, cur, style))]
    spec = S(vendor=name, addr=["Usage-based billing"], title="Invoice", layout="split", accent="#0f172a", grid=False, zebra=True, font="Helvetica",
             meta=[("Invoice number", num), ("Invoice date", dt(d, "%Y-%m-%d")), ("PO number", po), ("Billing period", dt(d - timedelta(days=30), "%b %d") + " - " + dt(d, "%b %d, %Y"))],
             columns=["Description", "Quantity", "Unit price", "Amount"], aligns=["L", "R", "R", "R"], rows=_rows(items, cur, style, 3), totals=tl,
             after=[vat or "VAT ID DE123456789"], footer="Usage is metered hourly and billed monthly in arrears")
    return spec, expected(name, num, po, d, None, cur, items, sub, None, rate, tax, None, total)


def b3_insurance(v, rng):
    d = rdate(rng)
    if v == 0:
        cur, name, fmt = "USD", "Beacon Mutual Insurance", "%m/%d/%Y"
        items = [item("Auto liability coverage", 1, "612.00"), item("Collision coverage", 1, "310.00"), item("Comprehensive coverage", 1, "128.00"), item("Multi-policy discount", 1, "-105.00")]
        sub = _sum(items)
        fees = [("Policy fee", D("25.00")), ("State surcharge", D("18.50"))]
        rate, tax = None, D(0)
    else:
        cur, name, fmt = "GBP", "Harbour Home Insurance", "%d/%m/%Y"
        items = [item("Buildings cover", 1, "186.40"), item("Contents cover", 1, "94.10")]
        sub = _sum(items)
        fees = [("Administration fee", D("15.00"))]
        rate, tax = D("12"), q(_sum(items) * D("0.12"))
    other = sum((f[1] for f in fees), D(0))
    total = sub + other + tax
    minimum = q(total * D("0.25"))
    due = d + timedelta(days=14)
    num = f"INS-{rng.randint(100000, 999999)}"
    tl = [("Premium", m(sub, cur))] + [(a, m(b, cur)) for a, b in fees] + ([("Insurance premium tax 12%", m(tax, cur))] if rate else []) + [("Total premium for term", m(total, cur))]
    spec = S(vendor=name, addr=["Premium notice"], title="PREMIUM INVOICE", layout="left", banner=True, accent="#1e3a8a", grid=True, font="Helvetica",
             top_box=[("Minimum payment due", m(minimum, cur)), ("Due date", dt(due, fmt)), ("Policy number", f"POL-{rng.randint(10000000, 99999999)}")],
             meta=[("Invoice number", num), ("Invoice date", dt(d, fmt)), ("Policy term", "12 months")], columns=["Coverage", "Qty", "Rate", "Amount"], aligns=["L", "R", "R", "R"],
             rows=_rows(items, cur), totals=tl, after=[f"Pay in full or in 4 instalments of {m(minimum, cur)}."], footer="Cancellation rights apply")
    return spec, expected(name, num, None, d, due, cur, items, sub, None, rate, tax, other, total)


BUILDERS3 = [("water", b3_water), ("car_rental", b3_car), ("airline", b3_airline), ("ride", b3_ride), ("repair", b3_repair), ("tuition", b3_tuition),
             ("rent", b3_rent), ("courier", b3_courier), ("event", b3_event), ("pharmacy", b3_pharmacy), ("usage", b3_usage), ("insurance", b3_insurance)]


def generate_world(out_dir: Path, seed: int = 2026, kit: str = "classic") -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows = []
    n = 0
    for v in (0, 1):
        for kind, fn in (BUILDERS3 if kit == "new" else BUILDERS):
            spec, exp = fn(v, rng)
            file = f"world_{n:02d}.pdf"
            render(spec, out_dir / file)
            review = needs_review(validate(InvoiceExtraction.model_validate(exp)))
            rows.append({"id": f"world_{n:02d}", "file": file, "layout": kind, "traps": [kind], "needs_review": review, "expect_scanned": False, "expected": exp})
            n += 1
    with open(out_dir.parent / "ground_truth.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows
