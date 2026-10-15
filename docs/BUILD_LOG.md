# Build log: how A2 was built

A chronological account of the work, written from the working sessions (October 2026, Windows + PowerShell, built with an LLM assistant; every step was run on my machine and the output pasted back before the next step). Numbers are from those runs.

## Working method

* One small batch at a time as a patch zip overlaid on the project (`Expand-Archive ... -Force`), each with: what it changes, what was verified, what was **not** verified.
* Run, paste the output, analyse, then fix. No fix without a failing example.
* Before each release the whole pipeline is run on the **correct answers** (a "dry run") to find false alarms in my own checks.
* Honest-test rules: a set is run once when it is fresh; after fixing from its failures it is "seen"; a fix is confirmed on a new seed. A stopping rule was fixed in advance (see phase 8).

## Phase 1: scaffold (A2.1)

Schema (all fields optional), pdfplumber text, validators (line math, subtotal, discount, tax, total, dates, currency), LLM extraction through `llm-client`, pipeline, FastAPI router. 36 synthetic invoices with ground truth: 6 layouts, USD/EUR (`1.234,56`)/GBP/PKR, planted traps (wrong printed total, wrong line amount, discount, partial payment, injection text in the footer, multi-page, PO/quote numbers beside the invoice number). 28 tests with a fake LLM.

First real Gemini run: 12 of 13 fields right on three documents; `po_number` empty everywhere. Cause: my own prompt said "ignore PO numbers".

## Phase 2: retry, eval runner, report

Added a repair retry (ask once more with the gaps listed), `run_eval.py` and an HTML side-by-side report (PDF picture, extracted text, AI answer, checks). Easy set: 35/36 then 36/36, review precision 100%, recall 100%.

## Phase 3: the hard set (16 documents)

German/French labels, US dates, wrapped lines, noisy labels, missing vendor, missing date, credit note, swapped parties, two image-only scans. 15/16 with one **silent error**: when the vendor name was not printed, the retry made the model return the address. Fix: retry only for structural gaps; address-as-vendor check; whole-value grounding. Hard: 16/16.

## Phase 4: easy set fell to 26/36

Cause: ten documents labelled the date "Date" or "Issued"; the earlier retry had been hiding it. Fix: explicit label list in the prompt: 36/36. Lesson: a repair can hide a weak prompt. Date grounding (a date must appear in any common printed form) was added after a `due_date` of 2029 slipped through.

## Phase 5: eight real public sample PDFs

Labelled from the PDFs by the assistant before running. First run: fields 94% right and total amount 8/8, but only 0/8 "perfect" and review precision 14%. Findings: (1) the PDF library split `13594027` into `135` and `94027`; (2) shipping had no field in the schema; (3) tiny rounding differences in `qty x price`; (4) a discount was both a line and a discount field. Fixes: second PDF engine (pdfium) as cross-check, whole-token grounding, `other_charges`, tolerance that scales with quantity, prompt rules. Real: 5/8, later 6/8.

## Phase 6: realistic sets (world, world2) and the "invented number" bug

24 documents modelled on real life (SaaS, freelancer, bills, receipts, clinic, wholesale, marketplace, hotel, Pakistani sales tax, multi-page agency). First run 12/24, all 11 mistakes flagged, 1 harmless silent error. Fixes: exact reconciliation of line items against the printed subtotal, fee/shipping recovery from a printed line, currency inference, PO rescue.

A regression exposed my own prompt: I had written "total equals subtotal - discount + other charges + tax", so on documents with a wrong printed total the model **invented a shipping charge to make it add up**. Fix: removed the sentence; every extracted amount must appear in the PDF (`number_not_in_document`); per-line discount percent; `tax_math` demoted to a warning.

## Phase 7: new designs (world3) and the protocol

12 new document kinds with new layout features (summary box on top, two tables, banner header, several fees). The code was frozen, the set generated, the checks run on the correct answers (findings reported, not fixed), then the AI run once: **7/24 strict**. Analysis of the 17 misses: omitted subtotal (my label flaw), document number not recognised (5), several fees summed (6), credit-line sign (2), totals rows read as items (2), previous balance + amount due (1 critical silent). The PDF reader caused none of them.

Batch 5 from that analysis: adjusted scoring (strict still printed), `amount_due` field, prompt rule for the document's own identifier, label-based invoice number rescue, fee-sum grounding and recovery, credit-line sign tolerance. World4 (new seed): 19/24.

## Phase 8: stopping rule and the last batch

Rule fixed in advance: on a fresh set, adjusted straight-through at least 60% and at most 1 critical silent error per 24, else one last small batch, then stop. World4 met the first and missed the second (two pharmacy receipts: the model used the gross "total retail price" and ignored "insurance savings"). Last batch: a **completeness** check (every printed deduction must be accounted for) and a net-total prompt rule. The dry runs caught three false alarms of the new check before release (`25.00%` read as an amount, `Fuel price adjustment` read as a deduction, `1 105.00` as an amount) and one collision with the reconcile repair (it dropped a negative discount row; it now moves it to `discount`).

Fresh seed (world5), first run: **22/24 adjusted (21 strict), 0 critical silent errors, 23/24 critical fields right.** Four runs of the same code: 21 to 23/24. Tuning stopped there.

## Phase 9: documentation, cost, variance, provider attempt

README, evaluation notes and deployment notes. Variance measured (world2 18 then 21 on the same code). Cost estimated from the call log tokens and the list price. Groq `gpt-oss-120b` returned 429 on 35 of 36 documents, so that comparison is marked invalid.

## Phase 10: packaging

ruff clean (10 small issues fixed, generated data unchanged), 79 tests, GitHub Actions workflow (ruff + pytest), Dockerfile (non-root, health check). Docker verified locally: image builds in about 50 s, `/health` 200, `/extract` correct with a real LLM, 40 MiB at start, 72.5 MiB after one call. First push: `.gitignore` initially let 1,114 files in, including a 1,000-PDF third-party dataset, a 12 MB zip and an LLM call log; caught at staging, fixed before the first commit (104 files). `.gitattributes` marks PDFs as binary so Git never rewrites their line endings. The commit on `main` shows a green CI check.

## Bugs found by my own dry runs (all fixed before release)

`Rs.` prefix not parsed as part of an amount; `POL-51210392` read as `PO` + `L-51210392`; `25.00%` read as an amount; `1 105.00` (qty 1, rate 105.00) read as 1105.00; `Fuel price adjustment` read as a deduction; reconcile dropping a legitimate negative discount row; a vendor tail line interleaved with a two-column header.

## Where this stands

Core done: extraction, checks, repairs, eval ladder, tests, docs, Docker, CI. Open: valid provider comparison and fallback on 429, mounting in the shared demo-api, demo page and video, vision/OCR fallback for scans, running on a client's own invoices. Next project in the plan: A1 (RAG), which is still at step A1.1.
