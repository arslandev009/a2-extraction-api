# A2 results: world3 set, gemini (2026-10-11 07:46)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 24 | retry: on | synthetic invoices only

## Headline

- Docs fully right (fields + review decision), adjusted scoring: **19/24 (79%)**; STRICT scoring: **9/24 (38%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **83%**
- Review flag: precision 0%, recall n/a (TP 0, FP 3, FN 0, TN 21)
- Per document: auto-processed correctly **19**, sent to a human rightly **3** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 2** (wrong fields and NOT flagged), of which **2 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/24 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1414 ms, max 3922 ms; run total 85 s
- Tokens per document: 1817 (in 1392, out 425)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 24/24 (100%) |
| invoice_number | 24/24 (100%) |
| po_number | 24/24 (100%) |
| invoice_date | 23/24 (96%) |
| due_date | 24/24 (100%) |
| currency | 24/24 (100%) |
| subtotal | 24/24 (100%) |
| discount | 22/24 (92%) |
| tax_rate | 24/24 (100%) |
| tax_amount | 24/24 (100%) |
| other_charges | 24/24 (100%) |
| total | 20/24 (83%) |
| line_count | 24/24 (100%) |
| line_amounts | 24/24 (100%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| airline | 2/2 |
| car_rental | 2/2 |
| courier | 2/2 |
| event | 2/2 |
| insurance | 2/2 |
| pharmacy | 0/2 |
| rent | 2/2 |
| repair | 1/2 |
| ride | 2/2 |
| tuition | 0/2 |
| usage | 2/2 |
| water | 2/2 |

## Failures

- world_05 (tuition): wrong=['discount', 'total'], review=False (expected False), issues=['rows_dropped_to_reconcile']
- world_09 (pharmacy): wrong=['total'], review=True (expected False), issues=['total_mismatch']
- world_16 (repair): wrong=['invoice_date'], review=True (expected False), issues=['missing_required', 'tax_math']
- world_17 (tuition): wrong=['total'], review=True (expected False), issues=['total_mismatch']
- world_21 (pharmacy): wrong=['discount', 'total'], review=False (expected False), issues=[]

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
