"""Run the pipeline on a sample set and write docs/results_<set>_<provider>.md + data/out/*.

  python scripts/run_eval.py                              # easy set (36), provider from .env
  python scripts/run_eval.py --set hard                   # hard set (16)
  python scripts/run_eval.py --set hard --provider groq   # other provider (same names as llm-client)
  python scripts/run_eval.py --no-retry                   # without the repair retry
  python scripts/run_eval.py --dry                        # ground truth as the 'model' (wiring check, no API)
World set: python scripts/generate_world.py first (24 realistic invoices/bills/receipts).
Real set: put PDFs in data/real/invoices, label them with make_label_sheet.py first.
Options: --n N (first N docs), --sleep S (pause between docs, free-tier rate limits)
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median

from extractor.compare import compare
from extractor.pipeline import process_pdf
from extractor.schema import InvoiceExtraction
from extractor.validators import needs_review, validate

ROOT = Path(__file__).resolve().parents[1]
SETS = {"easy": ROOT / "data", "hard": ROOT / "data" / "hard", "real": ROOT / "data" / "real", "world": ROOT / "data" / "world", "world2": ROOT / "data" / "world2", "world3": ROOT / "data" / "world3", "world4": ROOT / "data" / "world4", "world5": ROOT / "data" / "world5"}


class DryLLM:
    cur = None

    def chat_json(self, messages, schema):
        return self.cur


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


def _candidates() -> list[Path]:
    c = {Path.cwd() / "llm_calls.jsonl", ROOT / "llm_calls.jsonl"} | {p / "llm_calls.jsonl" for p in ROOT.parents[:4]}
    if os.getenv("LLM_CALLS_FILE"):
        c.add(Path(os.environ["LLM_CALLS_FILE"]))
    return sorted(c)


def snapshot() -> dict[Path, int]:
    out = {}
    for p in _candidates():
        if p.exists():
            with open(p, "rb") as f:
                out[p] = sum(1 for _ in f)
    return out


def new_calls(before: dict[Path, int]) -> list[dict]:
    calls = []
    for p, n in snapshot().items():
        if n > before.get(p, 0):
            with open(p, encoding="utf-8") as f:
                for line in list(f)[before.get(p, 0):]:
                    try:
                        calls.append(json.loads(line))
                    except ValueError:
                        pass
    return calls


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=list(SETS), default="easy")
    ap.add_argument("--provider", default=None)
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.0)
    ap.add_argument("--no-retry", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--tag", default="", help="suffix for result/summary file names (e.g. _n12) so a partial run does not overwrite a full one")
    ap.add_argument("--default-currency", default=None, help="used only when a document prints no currency at all")
    a = ap.parse_args()

    base = SETS[a.set]
    gt = base / "ground_truth.jsonl"
    if not gt.exists():
        raise SystemExit(f"missing {gt} (for the real set: make the label sheet, fill it in, download and move the file here)")
    rows = [json.loads(x) for x in open(gt, encoding="utf-8") if x.strip()]
    for r in rows:  # hand-labelled rows (real set) only carry the expected fields
        r.setdefault("layout", "real")
        r.setdefault("traps", [])
        r.setdefault("expect_scanned", False)
        if "needs_review" not in r:
            r["needs_review"] = True if r["expect_scanned"] else needs_review(validate(InvoiceExtraction.model_validate(r["expected"])))
    if a.n:
        rows = rows[: a.n]
    if a.dry:
        llm, provider = DryLLM(), "dry-run"
    else:
        from extractor.llm_extract import get_llm

        llm = get_llm(a.provider)
        provider = a.provider or os.getenv("LLM_PROVIDER", "default")

    per_doc, field_ok, field_n = [], defaultdict(int), defaultdict(int)
    tokens_in = tokens_out = 0
    cost = 0.0
    models: set[str] = set()
    calls_seen = 0
    t_start = time.time()
    for r in rows:
        if a.dry:
            llm.cur = r["expected"]
        before = snapshot()
        res = process_pdf((base / "invoices" / r["file"]).read_bytes(), llm, max_pages=10, retry=not a.no_retry, default_currency=a.default_currency)
        calls = new_calls(before)
        calls_seen += len(calls)
        for c in calls:
            tokens_in += c.get("prompt_tokens") or 0
            tokens_out += c.get("completion_tokens") or 0
            cost += c.get("cost_usd") or 0.0
            if c.get("model"):
                models.add(c["model"])
        wrong_strict = None
        if r.get("expect_scanned"):  # image-only scan: correct behaviour = flag it, no fields scored
            ok = res.needs_review and any(i.code == "scanned_pdf" for i in res.issues)
            wrong = [] if ok else ["NOT_FLAGGED_AS_SCAN"]
        elif res.error:
            wrong = ["ERROR"]
        else:
            cmp = compare(res.extraction.model_dump(), r["expected"])
            wrong = [k for k, v in cmp.items() if not v]
            wrong_strict = [k for k, v in compare(res.extraction.model_dump(), r["expected"], strict=True).items() if not v]
            for k, v in cmp.items():
                field_n[k] += 1
                field_ok[k] += int(v)
        per_doc.append({"id": r["id"], "traps": r["traps"], "layout": r["layout"], "wrong": wrong, "wrong_strict": wrong if wrong_strict is None else wrong_strict, "error": res.error,
                        "pred_review": res.needs_review, "exp_review": r["needs_review"], "attempts": res.attempts,
                        "latency_ms": res.latency_ms, "issues": [i.code for i in res.issues],
                        "extraction": res.extraction.model_dump() if res.extraction else None,
                        "issues_full": [i.model_dump() for i in res.issues]})
        print(f"{r['id']} {r['layout']:<16} {'OK ' if not wrong and res.needs_review == r['needs_review'] else 'BAD'} "
              f"wrong={wrong or '-'} review={res.needs_review}/{r['needs_review']} tries={res.attempts} {res.latency_ms}ms")
        if a.sleep:
            time.sleep(a.sleep)

    n = len(per_doc)
    perfect = sum(1 for d in per_doc if not d["wrong"] and d["pred_review"] == d["exp_review"])
    perfect_strict = sum(not d["wrong_strict"] and d["pred_review"] == d["exp_review"] for d in per_doc)
    tp = sum(d["pred_review"] and d["exp_review"] for d in per_doc)
    fp = sum(d["pred_review"] and not d["exp_review"] for d in per_doc)
    fn = sum(not d["pred_review"] and d["exp_review"] for d in per_doc)
    tn = n - tp - fp - fn
    # what a client cares about: what happened to each document
    auto_ok = sum(not d["pred_review"] and not d["wrong"] for d in per_doc)
    sent_right = sum(d["pred_review"] and (d["exp_review"] or bool(d["wrong"])) for d in per_doc)
    sent_needless = sum(d["pred_review"] and not d["exp_review"] and not d["wrong"] for d in per_doc)
    silent = sum(not d["pred_review"] and bool(d["wrong"]) for d in per_doc)
    critical = {"vendor_name", "invoice_number", "invoice_date", "due_date", "currency", "total"}
    silent_crit = sum(not d["pred_review"] and bool(critical & set(d["wrong"])) for d in per_doc)
    crit_ok = sum(not (critical & set(d["wrong"])) for d in per_doc)
    retried = sum(d["attempts"] > 1 for d in per_doc)
    errs = sum(1 for d in per_doc if d["error"])
    lat = [d["latency_ms"] for d in per_doc]
    by_trap = defaultdict(lambda: [0, 0])
    for d in per_doc:
        for t in d["traps"] or ["(none)"]:
            by_trap[t][1] += 1
            by_trap[t][0] += int(not d["wrong"] and d["pred_review"] == d["exp_review"])
    have_log = calls_seen > 0
    tok = f"{(tokens_in + tokens_out) / n:.0f} (in {tokens_in / n:.0f}, out {tokens_out / n:.0f})" if have_log else "n/a (llm_calls.jsonl not found/updated)"
    cst = f"${cost / n:.5f}" if have_log else "n/a"
    total_ok = pct(field_ok["total"], field_n["total"])

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    model_s = ", ".join(sorted(models)) or "unknown"
    md = [f"# A2 results: {a.set} set, {provider} ({ts})", "",
          f"Provider: `{provider}` | model: `{model_s}` | docs: {n} | retry: {'off' if a.no_retry else 'on'} | synthetic invoices only", "",
          "## Headline", "",
          f"- **Critical fields all right (vendor, invoice number, dates, currency, total): {crit_ok}/{n} ({pct(crit_ok, n)})**",
          f"- Docs fully right (fields + review decision), adjusted scoring: **{perfect}/{n} ({pct(perfect, n)})**; STRICT scoring: **{perfect_strict}/{n} ({pct(perfect_strict, n)})**",
          "  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)",
          f"- Total amount exact match (scored docs): **{total_ok}**",
          f"- Review flag: precision {pct(tp, tp + fp)}, recall {pct(tp, tp + fn)} (TP {tp}, FP {fp}, FN {fn}, TN {tn})",
          f"- Per document: auto-processed correctly **{auto_ok}**, sent to a human rightly **{sent_right}** "
          f"(real problem in the PDF or caught an extraction error), sent needlessly **{sent_needless}**, "
          f"**SILENT ERRORS {silent}** (wrong fields and NOT flagged), of which **{silent_crit} in critical fields** "
          f"(vendor, invoice number, dates, currency, total)",
          f"- Retries used: {retried}/{n} docs; hard errors (API/PDF): {errs}",
          f"- Latency per doc (incl. retry): median {int(median(lat))} ms, max {max(lat)} ms; run total {time.time() - t_start:.0f} s",
          f"- Tokens per document: {tok}", f"- Cost per document: {cst} (free tiers report 0)", "",
          "## Field accuracy (scored docs)", "", "| field | correct |", "|---|---|"]
    md += [f"| {k} | {field_ok[k]}/{field_n[k]} ({pct(field_ok[k], field_n[k])}) |" for k in field_n]
    md += ["", "## By trap / kind (docs fully right)", "", "| trap | ok/total |", "|---|---|"]
    md += [f"| {t} | {v[0]}/{v[1]} |" for t, v in sorted(by_trap.items())]
    md += ["", "## Failures", ""]
    bad = [d for d in per_doc if d["wrong"] or d["pred_review"] != d["exp_review"]]
    md += [f"- {d['id']} ({d['layout']}): wrong={d['wrong']}, review={d['pred_review']} (expected {d['exp_review']}), issues={d['issues']}" for d in bad] or ["- none"]
    md += ["", "_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._"]
    out = Path(ROOT / "docs" / f"results_{a.set}_{provider}{a.tag}.md")
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")

    raw = ROOT / "data" / "out"
    raw.mkdir(parents=True, exist_ok=True)
    summary = {"set": a.set, "provider": provider, "model": model_s, "n": n, "perfect": perfect, "perfect_strict": perfect_strict, "total_exact": total_ok,
               "review_precision": pct(tp, tp + fp), "review_recall": pct(tp, tp + fn), "retried": retried, "errors": errs,
               "median_ms": int(median(lat)), "tokens_per_doc": round((tokens_in + tokens_out) / n) if have_log else None,
               "cost_per_doc": round(cost / n, 6) if have_log else None, "tokens_in_per_doc": round(tokens_in / n) if have_log else None, "tokens_out_per_doc": round(tokens_out / n) if have_log else None, "tag": a.tag, "retry": not a.no_retry, "ts": ts,
               "failures": [d["id"] for d in bad], "auto_ok": auto_ok, "sent_right": sent_right, "sent_needless": sent_needless, "silent_errors": silent, "silent_critical": silent_crit, "critical_ok": crit_ok}
    (raw / f"summary_{a.set}_{provider}{a.tag}.json").write_text(json.dumps(summary), encoding="utf-8")
    (raw / "last_run.json").write_text(json.dumps({"set": a.set, "provider": provider, "retry": not a.no_retry, "docs": per_doc}), encoding="utf-8")
    print(f"\nwrote {out}\n{a.set}/{provider}: perfect {perfect}/{n} (strict {perfect_strict}) | review P={pct(tp, tp + fp)} R={pct(tp, tp + fn)} | "
          f"retried {retried} | errors {errs} | tokens/doc {tok}\n"
          f"auto-correct {auto_ok} | to human rightly {sent_right} | to human needlessly {sent_needless} | SILENT ERRORS {silent} (critical fields: {silent_crit}) | critical-fields-all-right {crit_ok}/{n}")


if __name__ == "__main__":
    main()
