"""HARD set: 16 invoices with real-world messiness (other languages, odd number/date formats, wrapped lines,
noisy labels, missing vendor/date, credit note, swapped parties, image-only scans). Deterministic truth.

Ground truth = what is printed. Image-only scans carry expect_scanned=True: today the correct behaviour is to
FLAG them for review (no text layer); a vision fallback would be scored on fields later.
"""
from __future__ import annotations

import io
import json
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pdfplumber
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .schema import InvoiceExtraction
from .synth import Inv, fmt_rate, make_invoice, q, truth
from .validators import needs_review, validate

# (kind, index passed to make_invoice: decides currency via i % 5 -> 0 USD, 1 EUR, 2 GBP, 3 USD, 4 PKR)
KINDS = [
    ("german", 1001), ("german", 1006), ("french", 1011),
    ("us_date", 1000), ("us_date", 1003),
    ("wrapped_lines", 1002), ("wrapped_lines", 1005),
    ("ocr_noise", 1010), ("ocr_noise", 1015),
    ("missing_vendor", 1020), ("missing_date", 1025), ("credit_note", 1030),
    ("scanned", 1035), ("scanned", 1040),
    ("parties_swapped", 1045), ("parties_swapped", 1048),
]
LABELS = {
    "en": dict(inv_no="Invoice No", date="Invoice date", due="Due date", po="Your PO", sub="Subtotal", disc="Discount",
               tax="Tax", total="Total", bill="Bill to", desc="Description", qty="Qty", unit="Unit price", amt="Amount"),
    "de": dict(inv_no="Rechnungsnummer", date="Rechnungsdatum", due="Fällig am", po="Ihre Bestellnr.", sub="Zwischensumme",
               disc="Rabatt", tax="MwSt", total="Gesamtbetrag", bill="Rechnung an", desc="Beschreibung", qty="Menge",
               unit="Einzelpreis", amt="Betrag"),
    "fr": dict(inv_no="Facture n°", date="Date de facture", due="Échéance", po="Votre commande", sub="Sous-total",
               disc="Remise", tax="TVA", total="Total TTC", bill="Facturé à", desc="Désignation", qty="Qté",
               unit="Prix unitaire", amt="Montant"),
}
LONG = [" - extended service agreement covering onsite visits, remote support and a quarterly review as per annex B",
        " (includes setup, configuration, user training and two follow-up calls within the first thirty days of delivery)",
        " - bespoke delivery to multiple sites, signed proof of delivery required, see special handling instructions"]
NOISE = [("Subtotal", "Subtota1"), ("Invoice", "lnvoice"), ("Total", "Tota1"), ("Date", "Dale"), ("Due", "Duc"),
         ("Bill to", "Bi11 to"), ("Description", "Descrlption"), ("No", "N0")]


def num(x: Decimal, style: str) -> str:
    s = f"{x:,.2f}"
    if style == "eu":
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    elif style == "fr":
        s = s.replace(",", " ").replace(".", ",")
    return s


def money(x: Decimal, cur: str, style: str) -> str:
    return f"{num(x, style)} €" if cur == "EUR" else f"{cur} {num(x, style)}"


def fix_day(d):  # make the date unambiguous between DD/MM and MM/DD
    return d if d.day > 12 else d + timedelta(days=13 - d.day)


def render_pdf(inv: Inv, target, lang="en", style="us", date_fmt="%Y-%m-%d", noise=False, hide_vendor=False,
               hide_dates=False, credit=False, swapped=False) -> None:
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.grey)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=18)
    L = dict(LABELS[lang])
    if lang == "en":
        L["tax"] = inv.labels["tax"]
    if credit:
        L["inv_no"] = "Credit note no"
    if noise:
        for k, v in L.items():
            for a, b in NOISE:
                v = v.replace(a, b)
            L[k] = v
    cur = inv.currency
    story: list = []
    if noise:
        story.append(Paragraph("~ ' . ,  |  _ -  . ' ~", small))
    addr = f"{inv.vendor[1]}<br/>{inv.vendor[2]}<br/>Tel {inv.phone}"
    if swapped:
        left = Paragraph(f"<b>Customer</b><br/>{inv.customer}<br/>Account 4471", body)
        right = Paragraph(f"<font size=16><b>{inv.vendor[0]}</b></font><br/>{addr}", body)
        story += [Table([[left, right]], colWidths=[80 * mm, 95 * mm]), Spacer(1, 10)]
    elif hide_vendor:
        story += [Paragraph(addr, body), Spacer(1, 8)]
    else:
        story += [Paragraph(inv.vendor[0], h1), Paragraph(addr, body), Spacer(1, 8)]
    if credit:
        story.append(Paragraph("<b>CREDIT NOTE</b>", body))
    meta = [(L["inv_no"], inv.invoice_number)]
    if not hide_dates:
        meta.append((L["date"], inv.invoice_date.strftime(date_fmt)))
        if inv.due_date:
            meta.append((L["due"], inv.due_date.strftime(date_fmt)))
    if inv.po_number:
        meta.append((L["po"], inv.po_number))
    m = Table(meta, colWidths=[40 * mm, 50 * mm], hAlign="LEFT")
    m.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [m, Spacer(1, 8)]
    if not swapped:
        story.append(Paragraph(f"<b>{L['bill']}:</b> {inv.customer}", body))
    story.append(Spacer(1, 8))
    head = [L["desc"], L["qty"], L["unit"], f"{L['amt']} ({cur})"]
    rows = [[Paragraph(d, body), f"{qt.normalize():f}", num(u, style), num(a, style)] for d, qt, u, a in inv.items]
    t = Table([head] + rows, colWidths=[85 * mm, 18 * mm, 30 * mm, 35 * mm], repeatRows=1)
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    tot = [(L["sub"], money(inv.subtotal, cur, style))]
    if inv.discount:
        tot.append((L["disc"], "-" + money(inv.discount, cur, style)))
    if inv.tax_rate:
        tot.append((f"{L['tax']} ({fmt_rate(inv.tax_rate)}%)", money(inv.tax_amount, cur, style)))
    tot.append((L["total"], money(inv.total, cur, style)))
    tt = Table(tot, colWidths=[45 * mm, 38 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    story += [t, Spacer(1, 10), tt]
    if noise:
        story += [Spacer(1, 10), Paragraph(". ' ~ | , _ ' .  -  ~ ,", small)]
    SimpleDocTemplate(target if isinstance(target, str) else target, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                      topMargin=15 * mm, bottomMargin=15 * mm, invariant=1).build(story)


def render_scanned(inv: Inv, path: Path, rng: random.Random) -> None:
    buf = io.BytesIO()
    render_pdf(inv, buf, style=inv.locale)
    with pdfplumber.open(io.BytesIO(buf.getvalue())) as pdf:
        im = pdf.pages[0].to_image(resolution=110).original.convert("L")
    im = im.rotate(rng.uniform(-1.5, 1.5), resample=Image.BICUBIC, fillcolor=255)
    im = Image.blend(im, Image.effect_noise(im.size, 25), 0.10)
    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(ImageReader(im), 0, 0, width=A4[0], height=A4[1])
    c.save()


def generate_hard(out_dir: Path, seed: int = 7) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    rows = []
    for n, (kind, i) in enumerate(KINDS):
        inv = make_invoice(i, rng)
        inv.traps, inv.notes, inv.amount_paid = [kind], None, None
        kw: dict = dict(style=inv.locale, date_fmt="%Y-%m-%d")
        if kind in ("german", "french", "us_date"):
            inv.invoice_date = fix_day(inv.invoice_date)
            if inv.due_date:
                inv.due_date = fix_day(inv.invoice_date + timedelta(days=rng.choice([14, 30, 45])))
        if kind == "german":
            kw.update(lang="de", style="eu", date_fmt="%d.%m.%Y")
        elif kind == "french":
            kw.update(lang="fr", style="fr", date_fmt="%d/%m/%Y")
        elif kind == "us_date":
            kw.update(date_fmt="%m/%d/%Y")
        elif kind == "wrapped_lines":
            inv.items = [(d + LONG[(k + n) % 3], qt, u, a) for k, (d, qt, u, a) in enumerate(inv.items)]
        elif kind == "ocr_noise":
            kw.update(noise=True)
        elif kind == "missing_vendor":
            kw.update(hide_vendor=True)
        elif kind == "missing_date":
            kw.update(hide_dates=True)
        elif kind == "credit_note":
            inv.items = [(d, qt, -u, -a) for d, qt, u, a in inv.items]
            inv.subtotal = sum((it[3] for it in inv.items), Decimal("0"))
            inv.discount = Decimal("0")
            inv.tax_amount = q(inv.subtotal * inv.tax_rate / 100) if inv.tax_rate else Decimal("0.00")
            inv.total = inv.subtotal + inv.tax_amount
            kw.update(credit=True)
        elif kind == "parties_swapped":
            kw.update(swapped=True)
        file = f"hard_{n:02d}.pdf"
        if kind == "scanned":
            render_scanned(inv, out_dir / file, rng)
        else:
            render_pdf(inv, str(out_dir / file), **kw)
        exp = truth(inv)
        if kind == "missing_vendor":
            exp["vendor_name"] = None
        if kind == "missing_date":
            exp["invoice_date"], exp["due_date"] = None, None
        review = True if kind == "scanned" else needs_review(validate(InvoiceExtraction.model_validate(exp)))
        rows.append({"id": f"hard_{n:02d}", "file": file, "layout": kind, "traps": [kind], "needs_review": review,
                     "expect_scanned": kind == "scanned", "expected": exp})
    with open(out_dir.parent / "ground_truth.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows
