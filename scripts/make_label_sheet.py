"""Build data/out/label_sheet.html for the REAL holdout set.

You type the CORRECT answers yourself while looking at each PDF (fields are empty on purpose: no AI answer is shown,
so you are not biased). Press 'Download ground_truth.jsonl' and move that file to data/real/ground_truth.jsonl.

  1. put 5-10 PDFs into data/real/invoices/
  2. python scripts/make_label_sheet.py
  3. open data/out/label_sheet.html, fill, download, move the file
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
FIELDS = [("vendor_name", "Vendor (who issued it)"), ("invoice_number", "Invoice number"), ("po_number", "PO number"),
          ("invoice_date", "Invoice date YYYY-MM-DD"), ("due_date", "Due date YYYY-MM-DD"), ("currency", "Currency (USD, EUR...)"),
          ("subtotal", "Subtotal"), ("discount", "Discount (positive)"), ("tax_rate", "Tax rate % (e.g. 20)"),
          ("tax_amount", "Tax amount"), ("total", "Invoice TOTAL (not balance due)")]

JS = r"""
const NUM = ["subtotal","discount","tax_rate","tax_amount","total"];
function rowFromValues(id, file, v) {
  const clean = s => { s = (s || "").trim(); return s === "" ? null : s; };
  const exp = {};
  for (const k of ["vendor_name","invoice_number","po_number","invoice_date","due_date","currency"]) exp[k] = clean(v[k]);
  if (exp.currency) exp.currency = exp.currency.toUpperCase();
  for (const k of NUM) {
    const c = clean(v[k]);
    if (c === null) { exp[k] = null; continue; }
    const n = Number(c.replace(/,/g, ""));
    if (Number.isNaN(n)) throw new Error(id + ": '" + c + "' is not a number in " + k);
    exp[k] = n;
  }
  exp.tax_amount = exp.tax_amount === null ? 0 : exp.tax_amount;
  const amts = (clean(v.lines) || "").split(/[;\s]+/).filter(x => x !== "").map(x => {
    const n = Number(x.replace(/,/g, ""));
    if (Number.isNaN(n)) throw new Error(id + ": line amount '" + x + "' is not a number");
    return n;
  });
  exp.line_items = amts.map(a => ({description: null, quantity: null, unit_price: null, amount: a}));
  return {id: id, file: file, layout: "real", traps: [], expect_scanned: !!v.scan, expected: exp};
}
function download() {
  const rows = [];
  try {
    document.querySelectorAll(".card").forEach(card => {
      const v = {};
      card.querySelectorAll("[data-f]").forEach(el => { v[el.dataset.f] = el.type === "checkbox" ? el.checked : el.value; });
      rows.push(rowFromValues(card.dataset.id, card.dataset.file, v));
    });
  } catch (e) { alert(e.message); return; }
  const blob = new Blob([rows.map(r => JSON.stringify(r)).join("\n") + "\n"], {type: "application/jsonl"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "ground_truth.jsonl"; a.click();
}
"""

CSS = """body{font:14px system-ui,sans-serif;margin:20px;background:#111;color:#ddd}h1{color:#fff}
.card{border:1px solid #333;border-radius:8px;margin:14px 0;padding:10px;background:#181818;display:grid;grid-template-columns:1.3fr 1fr;gap:14px}
img{max-width:100%;background:#fff;margin-bottom:6px;border-radius:4px}label{display:block;font-size:12px;margin-top:6px;color:#aaa}
input[type=text]{width:100%;box-sizing:border-box;background:#0b0b0b;color:#eee;border:1px solid #444;padding:5px;border-radius:4px}
button{background:#10b981;color:#000;border:0;padding:10px 16px;border-radius:6px;font-weight:700;cursor:pointer;font-size:14px}
.note{background:#1d2433;padding:10px 14px;border-radius:8px;margin-bottom:10px}"""


def page_images(path: Path, max_pages: int = 2) -> str:
    out = []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages[:max_pages]:
            buf = io.BytesIO()
            pg.to_image(resolution=90).original.save(buf, "PNG")
            out.append(f'<img src="data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"/>')
        extra = len(pdf.pages) - max_pages
    return "".join(out) + (f"<p>(+{extra} more page(s), open the PDF to read them)</p>" if extra > 0 else "")


def main() -> None:
    folder = ROOT / "data" / "real" / "invoices"
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"no PDFs in {folder}")
    cards = []
    for i, p in enumerate(pdfs, 1):
        inputs = "".join(f'<label>{lab}<input type="text" data-f="{k}"></label>' for k, lab in FIELDS)
        inputs += ('<label>Line item AMOUNTS in order, separated by space (e.g. 120.00 45.50 300). '
                   'If you leave this empty, the expected result becomes "needs review"<input type="text" data-f="lines"></label>'
                   '<label><input type="checkbox" data-f="scan"> this PDF is only an image (no selectable text)</label>')
        cards.append(f'<div class="card" data-id="real_{i:02d}" data-file="{html.escape(p.name)}"><div><b>real_{i:02d}: {html.escape(p.name)}</b><br>'
                     f'{page_images(p)}</div><div>{inputs}</div></div>')
    page = (f"<!doctype html><meta charset=utf-8><title>Label sheet</title><style>{CSS}</style><h1>Label the real invoices</h1>"
            '<div class="note">Type what is PRINTED (not what it should be). Leave a box empty if it is not printed. '
            "Numbers without currency symbols; dates as YYYY-MM-DD. Total = invoice grand total, not the balance due. "
            "When done: <button onclick='download()'>Download ground_truth.jsonl</button> "
            "then move it to <code>data\\real\\ground_truth.jsonl</code>.</div>" + "".join(cards) + f"<script>{JS}</script>")
    out = ROOT / "data" / "out" / "label_sheet.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    (ROOT / "data" / "out" / "label_sheet.js").write_text(JS, encoding="utf-8")
    print(f"wrote {out} for {len(pdfs)} PDFs")


if __name__ == "__main__":
    main()
