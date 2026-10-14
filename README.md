# A2: Invoice Extraction API

Upload a PDF invoice, bill or receipt and get **validated JSON** back, plus a flag that says **"a human should look at this"** whenever the system is not sure. Built to be *measured*, not just demoed: 8 evaluation sets, 79 tests, and a failure analysis of every mistake found along the way.

> Status (2026-10-12): extraction, validators, repairs, eval harness, tests and the cost estimate are done. A valid second-provider comparison, deployment (`/a2` in the shared demo-api) and the demo page are **TODO**.

## What it does

```
PDF upload
  -> pdftext.py       text layer from TWO engines (pdfplumber = main, pdfium = second opinion); image-only scans are detected and flagged
  -> llm_extract.py   LLM structured output (Pydantic schema, provider chosen by env). Rules: copy what is printed, never calculate, null if absent
  -> repairs.py       deterministic fixes, applied ONLY when the document itself confirms them (exact arithmetic, or a number printed on a labelled line)
  -> validators.py    arithmetic (lines, subtotal, discount, fees, tax, total), dates, currency, required fields,
                      grounding (every value must appear in the PDF as a whole token), number grounding, deduction completeness
  -> pipeline.py      Result { extraction, issues[], needs_review, attempts, latency_ms }
  -> api.py           POST /extract, GET /health   (APIRouter, mounted as /a2 in the shared demo-api)
```

Design principle: **the model reads, Python checks.** A wrong answer must never leave the system silently. Anything the checks cannot confirm goes to `needs_review`.

## How safe is it? (read this before the accuracy numbers)

Two numbers matter more than "accuracy":

* **Silent errors**: wrong field(s) and *not* flagged. Of these, the **critical** ones (vendor, invoice number, dates, currency, total) are the dangerous kind.
* **Straight-through rate**: documents that were correct and needed no human.

Everything else is flagged for review, which is the intended behaviour for what the system does not understand.

## Evaluation ladder (all data is synthetic or public sample data; no client data)

| Set | Docs | What it is |
|---|---|---|
| easy | 36 | generated invoices, 6 layouts, 4 currencies, planted errors (wrong printed total, wrong line, prompt injection in the footer, multi-page...) |
| hard | 16 | other languages (DE/FR), US dates, wrapped lines, noisy labels, missing vendor/date, credit note, swapped parties, 2 image-only scans |
| real | 8 | public sample invoices downloaded from the web (dummy data): 5 from one template, a university statement, 2 invoice-plugin samples |
| world2 | 24 | realistic documents: SaaS, freelancer, electricity bill (PKR), mobile bill, receipts, clinic bill, wholesale, marketplace, hotel, Pakistani sales-tax invoice, multi-page agency invoice |
| world3/4/5 | 24 each | 12 further kinds (water bill, car rental, airline receipt, ride, repair shop, school fees, rent, courier, tickets, pharmacy, usage-based SaaS, insurance) with new layout features |

Latest results (model `gemini-3.5-flash-lite` on the free tier; adjusted scoring = an omitted subtotal is not an error, and a discount returned as a negative line counts as equal money; strict scoring is shown beside it). **LLM answers vary from run to run, so sets with several runs show a range**:

| Set | Runs | Fully right (adjusted / strict) | Silent errors (critical) | Critical fields all right |
|---|---|---|---|---|
| easy (36) | 1 | 33 / 33 | 0 (0) | 36/36 |
| hard (16) | 1 | 15 / 15 | 0 (0) | 15/16 |
| real (8) | 1 | 6 / 6 | 1 (0) | 8/8 |
| world2 (24) | 2 | 18 and 21 / 18 and 21 | 5 (1) and 1 (0) | 23/24 and 24/24 |
| world4 (24) | 1 | 21 / 19 | 1 (0) | 24/24 |
| **world5 (24, fresh seed)** | **4** | **21 to 23 (mean 22, 92%) / 21 in every run** | **0 to 2 per run; critical: 0 in all 4 runs** | 23 to 24 |

How to read this honestly:

* world3/4/5 are the *same 12 document kinds* with new numbers, dates and items. They show the fixes generalise across data, not across designs I have never seen.
* First contact with those 12 kinds, before any tuning (world3, first run): **7/24 strict (29%)**, about 54% under adjusted scoring, 1 critical silent error. That is the realistic expectation for a new document type; a tuning round on a client's own sample invoices is what lifts it.
* The documents and the checks were written by the same person (me). Treat the numbers as an engineering signal, not as proof about your invoices. **The real test is your own 20 invoices.**
* Cost per document: about 1.9k tokens (input ~1.45k, output ~0.4k on world5; ~1.6k in / 0.8k out on easy). At the list price of $0.30 per 1M input and $2.50 per 1M output tokens (third-party aggregators quoting Google's pricing page, Oct 2026: **verify on ai.google.dev before quoting**) that is about **$0.0015 to $0.0025 per document, i.e. $1.5 to $2.5 per 1,000 documents**. The free tier reports $0.
* Run-to-run variation: the same code on the same data scored 18/24 and 21/24 on world2 and 21 to 23/24 on world5. Differences of up to about 3 documents on a 24-document set are noise.
* Latency: about 1.5 s per single-page document, about 5 s for multi-page ones. Free-tier outliers of 60 s or more were observed.

## Provider comparison

| Provider / model | Status |
|---|---|
| Gemini `gemini-3.5-flash-lite` | all results above |
| Groq `openai/gpt-oss-120b` | **not comparable yet**: the free tier answered `429 RateLimitError` on 35 of 36 documents (easy) and 8 of 24 (world5). On the 16 world5 documents that completed it scored 9 perfect with 4 silent errors (3 critical), which is too small and too polluted by the errors to conclude anything. The system's behaviour on an API error is to flag the document for review (safe), not to guess. **TODO: rerun slowly or on a paid tier, and add a fallback provider on 429 in the demo-api.** |

## Failure analysis: what went wrong and what fixed it

| # | What I observed | Root cause | Fix |
|---|---|---|---|
| 1 | PO number empty on every document | my own prompt said "ignore PO numbers" | rewrote the rule; added label-based rescue |
| 2 | Missing vendor: model returned the street address as the vendor | a "fill the gaps" retry pressured the model into inventing | retry only for structural gaps (items, tax); address-as-vendor check; value must appear in the PDF |
| 3 | 10 documents lost their invoice date | labels "Date"/"Issued"; an earlier retry had been hiding it | explicit label list in the prompt |
| 4 | invoice number `13594027` came out as `135` | the PDF library split digits printed on slightly different baselines | second PDF engine as cross-check; whole-token grounding |
| 5 | shipping, per-line discounts, two taxes, deposits flagged as errors | the schema had no field for them | `other_charges`, `discount_percent`, summed tax lines, `amount_due`, tolerance for rounded unit prices |
| 6 | the model invented a shipping charge to make a wrong printed total add up | my prompt said "total equals subtotal - discount + ..." | removed that sentence; every extracted amount must appear in the PDF |
| 7 | deposits, payments and "carried forward" rows read as line items | model treats everything near the table as an item | prompt rule + reconciliation against the printed subtotal (exact, unique solution only) |
| 8 | gross total used when the document shows insurance savings / scholarship | the model never extracted the deduction, so the arithmetic still looked fine | completeness check: every printed deduction must be accounted for |
| 9 | my own checks gave false alarms on correct answers (`Rs.` prefix, `POL-` read as `PO`, `25.00%` read as an amount) | regex edge cases | found by running the pipeline on the *correct* answers (dry run) before every release |
| 10 | 100% on synthetic data, 5/8 on real sample PDFs | synthetic data is easier than reality | added the real and realistic ladders; adjusted and strict scoring both reported |

## Known limitations

* **Scanned or photographed invoices** (no text layer) are detected and flagged for review. A vision/OCR fallback is **TODO** (it would widen coverage; it would not have fixed any of the accuracy failures above, all of which were definition/schema issues on clean text).
* Several layouts still read totals-block rows (freight, fuel, duties) as line items; these are flagged, not fixed.
* Statements with gross vs net totals, previous balances and insurance payments depend on definitions: `total` is the document's own final charges, `amount_due` is what is payable now.
* `po_number` is only filled from PO-style labels; "Order number" fields are treated as ambiguous.
* A single `tax_rate` is only filled when one rate is printed.
* One document per PDF. Documents longer than 5 pages are truncated with a warning.
* Languages tested: English, German, French. Right-to-left scripts and Urdu are **not tested**.
* Runs on free LLM tiers: fictional or public data only; latency is unpredictable.

## Run it

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q
python scripts/generate_data.py
python scripts/generate_hard.py
python scripts/generate_world.py --name world5 --seed 31337 --kit new
python scripts/run_eval.py --set world5 --default-currency USD --sleep 2
python scripts/show_diffs.py
uvicorn extractor.main:app --reload --port 8002
```

Provider, model and API keys come from the workspace `.env` through `packages/llm-client` (never committed). `.env.example` lists the A2 knobs (`MAX_UPLOAD_MB`, `MAX_PAGES`, `GATEWAY_SECRET`, `DEFAULT_CURRENCY`).

Example:

```powershell
curl.exe -F "file=@data/world5/invoices/world_00.pdf" http://127.0.0.1:8002/extract
```

## Deploy

See `docs/DEPLOY.md` (mount in the shared demo-api, settings, memory, container, UI rules). CI: `.github/workflows/ci.yml` runs ruff and pytest.

## Layout

`src/extractor/` the package, `scripts/` data generators, eval runner, report and diff tools, `tests/` 79 tests (the repairs are tested by re-creating real model mistakes), `docs/` results per set (`results_<set>_<provider>.md`) and `EVALUATION.md`.

> Note: the 8 public sample PDFs of the 'real' set are third-party files and are not included in this repository.
