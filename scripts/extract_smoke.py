"""Run the REAL pipeline on a few sample PDFs and compare with ground truth.

  python scripts/extract_smoke.py --n 3            # first 3 docs
  python scripts/extract_smoke.py --ids inv_05 inv_07
  python scripts/extract_smoke.py --dry            # no LLM call: pipeline wiring check with ground truth as the 'model'
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from extractor.compare import compare
from extractor.pipeline import process_pdf

ROOT = Path(__file__).resolve().parents[1]


class DryLLM:
    def __init__(self, rows):
        self.rows, self.cur = rows, None

    def chat_json(self, messages, schema):
        return self.cur


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--ids", nargs="*")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    rows = [json.loads(x) for x in open(ROOT / "data" / "ground_truth.jsonl", encoding="utf-8")]
    if a.ids:
        rows = [r for r in rows if r["id"] in a.ids]
    else:
        # a mix: first doc, then planted traps, so 3 docs already say something useful
        pick = [rows[0]] + [r for r in rows if r["traps"]]
        rows = pick[: a.n]

    if a.dry:
        llm = DryLLM(rows)
    else:
        from extractor.llm_extract import get_llm

        llm = get_llm()
        print("LLM object:", type(llm).__name__)

    ok_all = True
    for r in rows:
        if a.dry:
            llm.cur = r["expected"]
        data = (ROOT / "data" / "invoices" / r["file"]).read_bytes()
        res = process_pdf(data, llm, max_pages=10)
        print(f"\n=== {r['id']} layout={r['layout']} traps={r['traps']} pages={res.pages} {res.latency_ms} ms")
        if res.error:
            print("ERROR:", res.error)
            ok_all = False
            continue
        cmp = compare(res.extraction.model_dump(), r["expected"])
        bad = [k for k, v in cmp.items() if not v]
        print(f"fields correct: {sum(cmp.values())}/{len(cmp)}   wrong: {bad or '-'}")
        pred = res.extraction.model_dump()
        for k in bad[:4]:
            if k.startswith("line_"):
                print(f"   lines: got {len(pred['line_items'])} rows, expected {len(r['expected']['line_items'])}")
            else:
                print(f"   {k}: got={pred.get(k)!r} expected={r['expected'].get(k)!r}")
        print(f"attempts={res.attempts}  needs_review: got={res.needs_review} expected={r['needs_review']}   issues: {[i.code for i in res.issues] or '-'}")
        ok_all &= not bad and res.needs_review == r["needs_review"]
    print("\nRESULT:", "ALL MATCH" if ok_all else "SOME MISMATCH (expected on a first real run, paste this output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
