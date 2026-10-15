# A2: Invoice Extraction API

Upload a PDF invoice, bill or receipt and get **validated JSON** back, plus a flag that says **"a human should look at this"** whenever the system is not sure.

The point of the project is not "an LLM reads invoices" (that is easy to demo). The point is that it is **measured**: 8 evaluation sets, 79 tests, every failure analysed, and a pipeline designed so that **a wrong answer never leaves the system silently**.

* Repository: `github.com/arslandev009/a2-extraction-api` (CI: ruff + pytest on every push)
* Companion docs: [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) (how it was built, step by step), [`docs/EVALUATION.md`](docs/EVALUATION.md) (how the numbers are produced), [`docs/DEPLOY.md`](docs/DEPLOY.md) (mounting, settings, Docker)

**Contents:** [What it does](#what-it-does) · [Quick start](#quick-start) · [Pipeline](#pipeline) · [Checks and repairs](#checks-and-repairs) · [API](#api) · [Evaluation ladder and results](#evaluation-ladder-and-results) · [Failure analysis](#failure-analysis) · [Tech and why](#tech-and-why) · [Known limitations](#known-limitations) · [What is left](#what-is-left) · [Repository layout](#repository-layout)

---

## What it does

Input: a PDF with a text layer. Output (`Result`):

```json
{
  "extraction": { "vendor_name": "...", "invoice_number": "...", "po_number": null, "invoice_date": "2025-04-25",
                  "due_date": "2025-06-09", "currency": "USD", "line_items": [ {"description": "...", "quantity": 12, "unit_price": 172, "amount": 2064, "discount_percent": null} ],
                  "subtotal": 2247.0, "discount": null, "tax_rate": null, "tax_amount": 0.0, "other_charges": null, "total": 2247.0, "amount_due": null },
  "issues": [ {"code": "total_mismatch", "severity": "error", "field": "total", "message": "..."} ],
  "needs_review": false, "pages": 1, "latency_ms": 2216, "attempts": 1, "error": null
}
```

Design principle: **the model reads, Python checks.** The model copies what is printed (it is told never to calculate or "fix" numbers). Deterministic code then verifies the arithmetic, verifies that every value really appears in the PDF, and either repairs obvious slips (only when the document itself confirms the repair) or flags the document for a human.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest -q                                   # 79 tests
python scripts/generate_data.py             # easy set (already committed)
python scripts/generate_hard.py
python scripts/generate_world.py --name world5 --seed 31337 --kit new
python scripts/run_eval.py --set world5 --default-currency USD --sleep 2
python scripts/show_diffs.py                # AI answer vs correct answer for every mistake
uvicorn extractor.main:app --reload --port 8002
```

Provider, model and API keys come from the workspace `.env` through `packages/llm-client` (never committed). `.env.example` lists the A2 settings. Example call:

```powershell
curl.exe -F "file=@web/public/samples/easy_inv_00.pdf" http://127.0.0.1:8002/extract
```

Docker (build from the `ai-studio` root; verified 2026-10-13: builds in about 50 s, `/health` and `/extract` work with a real LLM, 40 MiB at start and 72.5 MiB after one real call):

```powershell
docker build -f projects/a2-extraction-api/Dockerfile -t a2-extraction .
docker run --rm -d --name a2 -p 8002:8002 --env-file .env a2-extraction
```

## Pipeline

```
PDF upload
  pdftext.py     text from TWO engines: pdfplumber (main; keeps label and value on one line) and pdfium (second opinion);
                 image-only scans are detected and flagged, never guessed
  llm_extract.py LLM structured output into the Pydantic schema (provider chosen by env). All fields optional: the model must answer null instead of guessing
  repairs.py     deterministic fixes, applied ONLY when the document confirms them (exact arithmetic or a number printed on a labelled line)
  validators.py  arithmetic + grounding + completeness checks (below)
  pipeline.py    gap retry (items/tax only), identifier repair from the second PDF engine, Result with issues and needs_review
  api.py         POST /extract, GET /health  (APIRouter, mounted as /a2 in the shared demo-api)
```

Failure behaviour: bad PDF, scan, LLM error, rate limit (429) all end in `needs_review = true` with an explanation, never in a guess.

## Checks and repairs

Each check has a code that appears in `issues`. `error` means review; `warning` is informational.

**Validators**

| Group | Codes | What it protects against |
|---|---|---|
| Required / format | `missing_required`, `bad_date`, `due_before_invoice`, `currency_unsupported`, `date_range` (warn), `vendor_is_address` | gaps, non-ISO dates, an address used as the vendor |
| Arithmetic | `line_math` (qty x price, tolerance scales with quantity because unit prices are printed rounded; per-line discount % and credit-line sign accepted), `subtotal_mismatch`, `tax_missing`, `total_mismatch` (subtotal - discount + other charges + tax), `tax_math` (warn only: tax is often charged on a subset) | wrong numbers anywhere |
| Grounding (soundness) | `not_in_document` (whole-token match, so `135` is not found inside `13594027`), `reader_mismatch` (value whole in the main reader but not in the second one), `date_not_in_document` (any common printed form, EN/DE/FR month names), `number_not_in_document` (calculated or invented amounts; a tax total may be the sum of printed tax lines, other charges the sum of up to 4 printed fee lines) | invented or mis-read values |
| Completeness | `deduction_not_captured` (every printed discount/savings/coupon/scholarship/negative adjustment must be a `discount` or a negative line) | the model silently using the gross figure as total |
| Pipeline | `scanned_pdf`, `bad_pdf`, `truncated` (warn) | documents the text path cannot read |

**Repairs** (each writes a warning so nothing changes silently)

| Code | Repair | Allowed only when |
|---|---|---|
| `rows_dropped_to_reconcile` / `row_moved_to_discount` | drop deposit, payment, "carried forward" rows read as items; a negative discount row moves to `discount` | the remaining rows add up exactly to the printed subtotal and the solution is unique |
| `other_charges_from_label` | fill shipping/fees | the missing amount equals the sum of 1 to 3 printed fee/shipping line amounts, unique |
| `po_from_label` / `invoice_number_from_label` | fill from a printed label ("Your PO", "Trip ID", "Repair order #"...) | exactly one labelled value on the same line; account/policy numbers never count |
| `currency_inferred` | single ISO code, single symbol, or the configured default | nothing ambiguous is printed |
| `vendor_name_joined` | join a vendor name that wraps onto the next header line | the next line is a short legal-suffix line ("Distribution Co.") |

**Retries**: only for structural gaps (items, tax). Never for vendor, dates or numbers: a retry pressures the model to invent (an address once became a vendor). An identifier that is invented or that the two PDF engines disagree about triggers one re-read from the other engine's text.

## API

* `POST /extract` (multipart field `file`, PDF only), `GET /health`.
* Status codes: 403 wrong `X-Gateway-Secret`, 413 over the size cap, 415 not a PDF, 502 LLM call failed. Scans return 200 with `needs_review=true`.
* Settings: `LLM_PROVIDER`, `MAX_UPLOAD_MB` (3), `MAX_PAGES` (5), `GATEWAY_SECRET`, `DEFAULT_CURRENCY` (used only when a document prints no currency at all).
* Mounting in the shared demo-api, memory, UI rules: see `docs/DEPLOY.md`.

Schema fields: `vendor_name`, `invoice_number`, `po_number`, `invoice_date`, `due_date`, `currency`, `line_items[description, quantity, unit_price, amount, discount_percent]`, `subtotal`, `discount`, `tax_rate`, `tax_amount` (sum of all tax lines), `other_charges` (shipping/fees), `total` (this document's own final charges after discounts, before payments), `amount_due` (what is payable now).

## Evaluation ladder and results

All data is synthetic or public sample data; no client data. Fictional businesses only (the demo uses free LLM tiers that may log inputs).

| Set | Docs | What it is | In the repo? |
|---|---|---|---|
| easy | 36 | generated invoices: 6 layouts, 4 currencies, planted errors (wrong printed total, wrong line, prompt injection in the footer, multi-page...) | yes |
| hard | 16 | German/French, US dates, wrapped lines, noisy labels, missing vendor/date, credit note, swapped parties, 2 image-only scans | regenerate |
| real | 8 | public sample invoices from the web (5 from one template, a university statement, 2 plugin samples) | no (third-party) |
| world, world2 | 24 each | realistic documents: SaaS, freelancer, electricity bill (PKR), mobile bill, receipts, clinic bill, wholesale, marketplace, hotel, Pakistani sales-tax invoice, multi-page agency invoice | regenerate |
| world3, world4, world5 | 24 each | 12 further kinds: water bill, car rental, airline receipt, ride, repair shop (two tables), school fees, rent, courier, tickets, pharmacy, usage-based SaaS, insurance | regenerate |

Latest results (Gemini `gemini-3.5-flash-lite`, free tier; **adjusted** scoring = an omitted subtotal is not an error and a discount returned as a negative line counts as equal money; strict scoring is also recorded). Sets with several runs show a range because **LLM answers vary from run to run**:

| Set | Runs | Fully right (adjusted / strict) | Silent errors (critical) | Critical fields all right |
|---|---|---|---|---|
| easy (36) | 1 | 33 / 33 | 0 (0) | 36/36 |
| hard (16) | 1 | 15 / 15 | 0 (0) | 15/16 |
| real (8) | 1 | 6 / 6 | 1 (0) | 8/8 |
| world2 (24) | 2 | 18 and 21 / 18 and 21 | 5 (1) and 1 (0) | 23/24 and 24/24 |
| world4 (24) | 1 | 21 / 19 | 1 (0) | 24/24 |
| **world5 (24, fresh seed)** | **4** | **21 to 23 (mean 22, 92%) / 21 each** | **0 to 2; critical 0 in all 4** | 23 to 24 |

How to read it honestly:

* world3/4/5 are the **same 12 document kinds** with new numbers, dates and items. They show the fixes generalise across data, not across designs I have never seen.
* **First contact** with those 12 kinds, before any tuning (world3, first run): **7/24 strict (29%)**, about 54% adjusted, 1 critical silent error. That is the realistic expectation for a new document type; one tuning round on the client's own samples is what lifts it.
* The documents, labels and checks were written by the same person (an LLM assistant working with me). The "real" set labels were written from the PDFs by the assistant and checked by arithmetic, not by a second human. Treat the numbers as an engineering signal, not as proof about your invoices. **The real test is your own 20 invoices.**
* Same code on the same data: world2 18/24 and 21/24, world5 21 to 23/24. Differences of about 3 documents on a 24-document set are noise.
* **Cost**: about 1.45k input and 0.4k output tokens per document on world5 (1.6k / 0.8k on easy). At $0.30 / $2.50 per million tokens (third-party aggregators quoting Google's list price, Oct 2026: verify before quoting) that is **about $0.0015 to $0.0025 per document, $1.5 to $2.5 per 1,000 documents**. The free tier reports $0.
* **Latency**: about 1.5 s per single-page document, about 5 s for multi-page ones. Free-tier outliers of 60 s or more were observed.
* **Provider comparison**: Groq `openai/gpt-oss-120b` returned `429` on 35 of 36 documents (easy) and 8 of 24 (world5); that comparison is invalid until rerun slowly or on a paid tier. A fallback provider on 429 belongs in the demo-api.

## Failure analysis

| # | What I observed | Root cause | Fix |
|---|---|---|---|
| 1 | PO number empty on every document | my prompt said "ignore PO numbers" | rewrote the rule; label-based rescue |
| 2 | missing vendor: the model returned the street address | a "fill the gaps" retry pressured it to invent | retry only for structural gaps; address-as-vendor check |
| 3 | 10 documents lost their invoice date | labels "Date"/"Issued"; an earlier retry had been hiding it | explicit label list in the prompt |
| 4 | invoice number `13594027` came out as `135` | the PDF library split digits printed on slightly different baselines | second PDF engine as cross-check; whole-token grounding |
| 5 | shipping, per-line discounts, two taxes, deposits flagged as errors | the schema had no field for them | `other_charges`, `discount_percent`, summed tax lines, `amount_due`, rounding tolerance |
| 6 | the model invented a shipping charge so a wrong printed total added up | my prompt said "total equals subtotal - discount + ..." | removed that sentence; every amount must appear in the PDF |
| 7 | deposits, payments, "carried forward" rows read as items | everything near the table looks like an item | prompt rule + exact reconciliation against the printed subtotal |
| 8 | gross total used when the document shows insurance savings / scholarship | the deduction was never extracted, so the arithmetic still looked fine | completeness check for printed deductions |
| 9 | my own checks gave false alarms on correct answers (`Rs.` prefix, `POL-` read as `PO`, `25.00%` read as an amount, `1 105.00` read as 1105) | regex edge cases | found by running the pipeline on the correct answers (dry run) before every release |
| 10 | 100% on synthetic data, 5/8 on real sample PDFs | synthetic data is easier than reality | added the real and realistic sets; strict and adjusted scoring both reported |

The reader (PDF text) was the cause of only one failure out of all of them. Everything else was definitions, schema, prompts and checks, which is why a premium OCR engine would not have fixed these; vision/OCR matters for scans (coverage), not for these accuracy failures.

## Tech and why

| Piece | Used | Why |
|---|---|---|
| Language / API | Python 3.12, FastAPI, uvicorn, Pydantic v2, python-multipart | typed schema shared by the LLM output, validators and API |
| PDF text | pdfplumber (pdfminer.six) + pypdfium2 | pdfplumber keeps labels with values; pdfium groups characters differently and exposed split digits |
| LLM access | own `packages/llm-client` (OpenAI-format client for OpenAI, Groq, Gemini, local llama.cpp) | provider switch by env, call log with tokens |
| Model used | Gemini `gemini-3.5-flash-lite`, free tier | cheap, fast; Groq `gpt-oss-120b` tried (rate-limited) |
| Test data | reportlab (synthetic PDFs, deterministic by seed), Pillow (scan simulation) | ground truth known exactly |
| Quality | pytest (79 tests), httpx, ruff, GitHub Actions | the repairs are tested by re-creating real model mistakes |
| Packaging | Docker (python:3.12-slim, non-root, health check) | same image can sit behind the shared demo-api |
| Environment | Windows, PowerShell, VS Code | |

No torch, no OCR engine, no local model: the extractor itself uses about 76 MB peak (about 73 MiB measured inside the container with the LLM client), small enough for a 512 MB free host.

## Known limitations

* **Scanned or photographed invoices** (no text layer) are detected and flagged. A vision/OCR fallback is not built.
* Some layouts still read totals-block rows (freight, fuel, duties) as line items; these are flagged, not fixed.
* Statements with gross vs net totals, previous balances and insurance payments depend on definitions: `total` is the document's own final charges, `amount_due` is what is payable now (`amount_due` is extracted but not yet scored).
* `po_number` is only filled from PO-style labels; "Order number" fields are treated as ambiguous.
* A single `tax_rate` is only filled when one rate is printed.
* One document per PDF; documents over 5 pages are truncated with a warning.
* Languages tested: English, German, French. Right-to-left scripts and Urdu are not tested.
* Free LLM tiers: fictional or public data only; latency and rate limits are unpredictable.

## What is left

1. Provider comparison that is valid (rerun Groq slowly or on a paid tier) and a **fallback provider on 429**.
2. Mount `extractor.api:router` in the shared demo-api at `/a2`; demo page on Cloudflare Pages using `scripts/export_samples.py` (8 curated sample files only) and a 90-second video.
3. Vision/OCR fallback for scanned PDFs (coverage).
4. Score `amount_due`; more languages; multiple tax rates; the courier-style totals rows.
5. Run it on a client's own 20 invoices (the only real proof).

## Repository layout

```
src/extractor/   schema, pdftext, llm_extract, repairs, validators, pipeline, api, main, compare; synth*.py generate the test documents
scripts/         generate_data/hard/world, run_eval, show_diffs, make_report, make_label_sheet, compare_providers, export_samples, extract_smoke
tests/           79 tests (unit, pipeline with a fake LLM, API, generators, repairs re-creating real model mistakes)
data/            easy set + ground truth (other sets are regenerated by the scripts and not committed)
docs/            BUILD_LOG.md, EVALUATION.md, DEPLOY.md, results_<set>_<provider>.md written by run_eval
web/public/samples/   8 curated sample PDFs for the demo UI
Dockerfile, Dockerfile.dockerignore, .github/workflows/ci.yml, pyproject.toml (ruff config), .env.example, .gitattributes (PDFs are binary)
```
