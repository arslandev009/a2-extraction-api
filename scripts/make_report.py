"""Build data/out/side_by_side.html from the LAST run_eval run (no API calls).

For every invoice: PDF picture | what Python read (text) | what the AI returned vs the correct answer | math checks.
  python scripts/run_eval.py --sleep 2
  python scripts/make_report.py
"""
from __future__ import annotations

import base64
import html
import io
import json
from pathlib import Path

import pdfplumber

from extractor.compare import MONEY, SCALARS, compare
from extractor.pdftext import extract_text

ROOT = Path(__file__).resolve().parents[1]


def esc(x) -> str:
    return '<i class="null">null</i>' if x is None else html.escape(str(x))


def picture(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        im = pdf.pages[0].to_image(resolution=75).original
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def fields_table(pred: dict, exp: dict, cmp: dict) -> str:
    rows = []
    for f in SCALARS + MONEY:
        ok = cmp[f]
        rows.append(f'<tr class="{"ok" if ok else "bad"}"><td>{f}</td><td>{esc(pred.get(f))}</td><td>{esc(exp.get(f))}</td>'
                    f'<td>{"✓" if ok else "✗"}</td></tr>')
    return ('<table><tr><th>field</th><th>AI said</th><th>correct answer</th><th></th></tr>' + "".join(rows) + "</table>")


def lines_table(pred: dict, exp: dict) -> str:
    pl, tl = pred.get("line_items") or [], exp.get("line_items") or []
    rows = []
    for i in range(max(len(pl), len(tl))):
        p = pl[i] if i < len(pl) else {}
        t = tl[i] if i < len(tl) else {}
        ok = p.get("amount") is not None and t.get("amount") is not None and abs(p["amount"] - t["amount"]) < 0.005
        rows.append(f'<tr class="{"ok" if ok else "bad"}"><td>{i + 1}</td><td>{esc(p.get("description"))}</td>'
                    f'<td>{esc(p.get("quantity"))} x {esc(p.get("unit_price"))}</td><td>{esc(p.get("amount"))}</td>'
                    f'<td>{esc(t.get("amount"))}</td><td>{"✓" if ok else "✗"}</td></tr>')
    return ('<table><tr><th>#</th><th>AI: item</th><th>AI: qty x price</th><th>AI: amount</th><th>correct amount</th><th></th></tr>'
            + "".join(rows) + "</table>")


CSS = """body{font:14px system-ui,sans-serif;margin:24px;background:#111;color:#ddd}h1,h2{color:#fff}
table{border-collapse:collapse;margin:6px 0;width:100%}td,th{border:1px solid #333;padding:3px 6px;text-align:left;font-size:12px}
tr.ok td{background:#10241a}tr.bad td{background:#3a1515}th{background:#222}.null{color:#888}
details{border:1px solid #333;border-radius:8px;margin:10px 0;padding:6px 10px;background:#181818}summary{cursor:pointer;font-weight:600}
.grid{display:grid;grid-template-columns:minmax(320px,1fr) minmax(420px,1.3fr);gap:14px;margin-top:8px}
img{max-width:100%;background:#fff;border-radius:4px}pre{white-space:pre-wrap;background:#0b0b0b;padding:8px;border-radius:6px;font-size:11px;max-height:340px;overflow:auto}
.tag{display:inline-block;background:#2a2a2a;border-radius:10px;padding:1px 8px;margin-left:4px;font-size:11px;font-weight:400}
.good{color:#4ade80}.badc{color:#f87171}.box{background:#1d2433;padding:10px 14px;border-radius:8px}"""


def main() -> None:
    run = json.loads((ROOT / "data" / "out" / "last_run.json").read_text(encoding="utf-8"))
    which = run.get("set", "easy")
    base = {"easy": ROOT / "data", "hard": ROOT / "data" / "hard", "real": ROOT / "data" / "real", "world": ROOT / "data" / "world", "world2": ROOT / "data" / "world2", "world3": ROOT / "data" / "world3", "world4": ROOT / "data" / "world4", "world5": ROOT / "data" / "world5"}[which]
    truth = {json.loads(x)["id"]: json.loads(x) for x in open(base / "ground_truth.jsonl", encoding="utf-8")}
    docs = run["docs"]
    over, details = [], []
    for d in docs:
        t = truth[d["id"]]
        pdf_path = base / "invoices" / t["file"]
        pred = d["extraction"] or {}
        cmp = compare(pred, t["expected"]) if d["extraction"] else {k: False for k in SCALARS + MONEY + ["line_count", "line_amounts"]}
        n_ok = sum(cmp.values())
        scan = t.get("expect_scanned", False)
        perfect = (not d["wrong"]) and d["pred_review"] == d["exp_review"] if scan else (n_ok == len(cmp) and d["pred_review"] == d["exp_review"])
        over.append(f'<tr class="{"ok" if perfect else "bad"}"><td><a href="#{d["id"]}">{d["id"]}</a></td><td>{d["layout"]}</td>'
                    f'<td>{html.escape(", ".join(d["traps"]) or "-")}</td><td>{n_ok}/{len(cmp)}</td>'
                    f'<td>{d["pred_review"]} / {d["exp_review"]}</td><td>{d["attempts"]}</td><td>{d["latency_ms"]} ms</td></tr>')
        text = extract_text(pdf_path.read_bytes(), max_pages=10)
        issues = "".join(f'<li class="{"badc" if i["severity"] == "error" else ""}">[{i["severity"]}] {html.escape(i["message"])}</li>'
                         for i in d["issues_full"]) or '<li class="good">no problems found by the math checks</li>'
        verdict = ('<b class="badc">needs human review</b>' if d["pred_review"] else '<b class="good">looks fine, no review needed</b>')
        exp_v = "review expected" if d["exp_review"] else "no review expected"
        right = ('<h3>3. Image-only scan (no text layer)</h3><p>Python found <b>no text</b> in this PDF, so it did not call the AI. '
                 'Correct behaviour today: flag for a human. (A vision/OCR fallback would be the next step.)</p>'
                 if scan else f'<h3>3. AI result vs correct answer</h3>{fields_table(pred, t["expected"], cmp)}{lines_table(pred, t["expected"])}')
        body = (f'<div class="grid"><div><h3>1. PDF (page 1 picture)</h3><img src="{picture(pdf_path)}"/>'
                f'<h3>2. What Python read from the PDF (plain text, {text.pages} page(s))</h3><pre>{html.escape(text.text)}</pre></div>'
                f'<div>{right}'
                f'<h3>4. Python math checks</h3><ul>{issues}</ul><p>Decision: {verdict} ({exp_v}); AI attempts: {d["attempts"]}</p></div></div>')
        details.append(f'<details id="{d["id"]}" {"" if perfect else "open"}><summary>{d["id"]} - {d["layout"]}'
                       + "".join(f'<span class="tag">{html.escape(x)}</span>' for x in d["traps"])
                       + f' <span class="{"good" if perfect else "badc"}">{"all correct" if perfect else "has a mistake"}</span></summary>{body}</details>')
    perfect_n = sum(1 for r in over if 'class="ok"' in r)
    page = (f"<!doctype html><meta charset=utf-8><title>A2 side by side</title><style>{CSS}</style>"
            f"<h1>A2 invoice extraction: side by side</h1>"
            f'<div class="box">Provider: <b>{html.escape(str(run["provider"]))}</b> | retry: {run["retry"]} | all correct: <b>{perfect_n}/{len(docs)}</b><br>'
            "Flow: <b>PDF</b> → Python reads the text → AI turns text into fields → Python checks the math → "
            "flag for a human if anything looks wrong. Red rows = wrong or missing. Wrong ones are open, correct ones are collapsed.<br>"
            "Review column: <i>decided by system / should have been</i>.</div>"
            f"<h2>Overview</h2><table><tr><th>doc</th><th>layout</th><th>traps</th><th>fields ok</th><th>review (system / expected)</th>"
            f"<th>AI tries</th><th>time</th></tr>{''.join(over)}</table><h2>Every invoice</h2>{''.join(details)}")
    out = ROOT / "data" / "out" / f"side_by_side_{which}_{run['provider']}.html"
    out.write_text(page, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
