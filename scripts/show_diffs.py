"""After run_eval: print, for every document with a mistake or an alarm, what the AI said vs the correct answer.
  python scripts/show_diffs.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
run = json.loads((ROOT / "data" / "out" / "last_run.json").read_text(encoding="utf-8"))
base = {"easy": ROOT / "data", "hard": ROOT / "data" / "hard", "real": ROOT / "data" / "real", "world": ROOT / "data" / "world", "world2": ROOT / "data" / "world2", "world3": ROOT / "data" / "world3", "world4": ROOT / "data" / "world4", "world5": ROOT / "data" / "world5"}[run["set"]]
truth = {}
for line in open(base / "ground_truth.jsonl", encoding="utf-8"):
    r = json.loads(line)
    truth[r["id"]] = r
shown = 0
for d in run["docs"]:
    t = truth[d["id"]]
    flagged_wrongly = d["pred_review"] and not d["exp_review"]
    missed = (not d["pred_review"]) and d["exp_review"]
    if not (d["wrong"] or flagged_wrongly or missed):
        continue
    shown += 1
    pred = d["extraction"] or {}
    print(f"\n=== {d['id']} [{d['layout']}] review: system={d['pred_review']} expected={d['exp_review']}"
          + ("  <-- MISSED REVIEW" if missed else "") + ("  <-- SILENT ERROR" + (" (CRITICAL FIELD)" if {"vendor_name", "invoice_number", "invoice_date", "due_date", "currency", "total"} & set(d["wrong"]) else "") if d["wrong"] and not d["pred_review"] else ""))
    for k in d["wrong"]:
        if k in ("line_count", "line_amounts"):
            pa = [x.get("amount") for x in pred.get("line_items", [])]
            ta = [x.get("amount") for x in t["expected"]["line_items"]]
            print(f"   {k}: AI amounts={pa}\n   {' ' * len(k)}  correct ={ta}")
        else:
            print(f"   {k}: AI={pred.get(k)!r}  correct={t['expected'].get(k)!r}")
    for i in d["issues_full"]:
        if i["severity"] == "error":
            print(f"   check fired: {i['code']} ({i['field']}): {i['message'][:140]}")
print(f"\n{shown} document(s) with a mistake or a needless/missed alarm out of {len(run['docs'])}  [{run['set']}/{run['provider']}]")
