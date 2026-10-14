"""Collect data/out/summary_*.json from run_eval runs into docs/PROVIDERS.md (one row per set+provider+tag).
Rows with API errors are marked INVALID: a provider that failed calls was not compared fairly."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# USD per 1M tokens (input, output). 'verify' before quoting: prices change. Gemini figure: third-party aggregators citing Google's pricing page, Oct 2026.
PRICES = {"gemini-3.5-flash-lite": (0.30, 2.50)}

rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "data" / "out").glob("summary_*.json"))]
rows = [r for r in rows if r["provider"] != "dry-run"]


def est_cost(r):
    pr, ti, to = PRICES.get(r["model"]), r.get("tokens_in_per_doc"), r.get("tokens_out_per_doc")
    return f"${(ti * pr[0] + to * pr[1]) / 1e6:.4f}" if pr and ti is not None and to is not None else "n/a"


md = ["# Provider comparison (A2)", "", "Synthetic invoices; one run per row. LLM answers vary run to run (about +-3 documents on a 24-document set), so single rows are indicative only.", "",
      "| set | provider | model | fully right (adj/strict) | silent (critical) | critical fields ok | API errors | review P / R | median ms | tokens/doc | est. paid cost/doc | valid? | when |",
      "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in sorted(rows, key=lambda r: (r["set"], r["provider"], r.get("tag", ""))):
    bad = r["errors"] > 0
    md.append(f"| {r['set']}{r.get('tag', '')} | {r['provider']} | {r['model']} | {r['perfect']}/{r['n']} / {r.get('perfect_strict', '?')} | "
              f"{r.get('silent_errors', '?')} ({r.get('silent_critical', '?')}) | {r.get('critical_ok', '?')}/{r['n']} | {r['errors']} | "
              f"{r['review_precision']} / {r['review_recall']} | {r['median_ms']} | {r['tokens_per_doc'] if r['tokens_per_doc'] is not None else 'n/a'} | {est_cost(r)} | "
              f"{'**INVALID** (API errors)' if bad else 'yes'} | {r['ts']} |")
md += ["", "Free tiers report $0; the estimate column uses list prices (verify before quoting)."]
out = ROOT / "docs" / "PROVIDERS.md"
out.write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md))
