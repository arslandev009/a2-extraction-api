# A2 results: world4 set, gemini (2026-10-11 13:54)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 24 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 24/24 (100%)**
- Docs fully right (fields + review decision), adjusted scoring: **21/24 (88%)**; STRICT scoring: **19/24 (79%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **100%**
- Review flag: precision 0%, recall n/a (TP 0, FP 2, FN 0, TN 22)
- Per document: auto-processed correctly **21**, sent to a human rightly **2** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 1** (wrong fields and NOT flagged), of which **0 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/24 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1493 ms, max 2456 ms; run total 86 s
- Tokens per document: 1894 (in 1456, out 438)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 24/24 (100%) |
| invoice_number | 24/24 (100%) |
| po_number | 24/24 (100%) |
| invoice_date | 24/24 (100%) |
| due_date | 24/24 (100%) |
| currency | 24/24 (100%) |
| subtotal | 23/24 (96%) |
| discount | 24/24 (100%) |
| tax_rate | 24/24 (100%) |
| tax_amount | 23/24 (96%) |
| other_charges | 22/24 (92%) |
| total | 24/24 (100%) |
| line_count | 23/24 (96%) |
| line_amounts | 23/24 (96%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| airline | 2/2 |
| car_rental | 2/2 |
| courier | 1/2 |
| event | 2/2 |
| insurance | 0/2 |
| pharmacy | 2/2 |
| rent | 2/2 |
| repair | 2/2 |
| ride | 2/2 |
| tuition | 2/2 |
| usage | 2/2 |
| water | 2/2 |

## Failures

- world_11 (insurance): wrong=['tax_amount', 'other_charges'], review=False (expected False), issues=[]
- world_19 (courier): wrong=['other_charges', 'line_count', 'line_amounts'], review=True (expected False), issues=['tax_math', 'total_mismatch']
- world_23 (insurance): wrong=['subtotal'], review=True (expected False), issues=['subtotal_mismatch', 'tax_math', 'total_mismatch', 'number_not_in_document']

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
