# A2 results: world5 set, groq (2026-10-12 13:57)

Provider: `groq` | model: `openai/gpt-oss-120b` | docs: 24 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 19/24 (79%)**
- Docs fully right (fields + review decision), adjusted scoring: **9/24 (38%)**; STRICT scoring: **7/24 (29%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **94%**
- Review flag: precision 0%, recall n/a (TP 0, FP 11, FN 0, TN 13)
- Per document: auto-processed correctly **9**, sent to a human rightly **10** (real problem in the PDF or caught an extraction error), sent needlessly **1**, **SILENT ERRORS 4** (wrong fields and NOT flagged), of which **3 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/24 docs; hard errors (API/PDF): 8
- Latency per doc (incl. retry): median 9125 ms, max 29941 ms; run total 378 s
- Tokens per document: 2411 (in 1601, out 810)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 16/16 (100%) |
| invoice_number | 16/16 (100%) |
| po_number | 16/16 (100%) |
| invoice_date | 15/16 (94%) |
| due_date | 14/16 (88%) |
| currency | 15/16 (94%) |
| subtotal | 15/16 (94%) |
| discount | 15/16 (94%) |
| tax_rate | 16/16 (100%) |
| tax_amount | 16/16 (100%) |
| other_charges | 16/16 (100%) |
| total | 15/16 (94%) |
| line_count | 15/16 (94%) |
| line_amounts | 15/16 (94%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| airline | 2/2 |
| car_rental | 2/2 |
| courier | 0/2 |
| event | 1/2 |
| insurance | 0/2 |
| pharmacy | 0/2 |
| rent | 1/2 |
| repair | 0/2 |
| ride | 2/2 |
| tuition | 0/2 |
| usage | 1/2 |
| water | 0/2 |

## Failures

- world_00 (water): wrong=['due_date'], review=False (expected False), issues=[]
- world_04 (repair): wrong=['invoice_date'], review=True (expected False), issues=['missing_required', 'tax_math']
- world_05 (tuition): wrong=['currency'], review=False (expected False), issues=[]
- world_07 (courier): wrong=[], review=True (expected False), issues=['line_math', 'tax_math']
- world_09 (pharmacy): wrong=['total'], review=True (expected False), issues=['missing_required']
- world_11 (insurance): wrong=['subtotal', 'discount', 'line_count', 'line_amounts'], review=False (expected False), issues=['number_not_in_document', 'rows_dropped_to_reconcile', 'row_moved_to_discount']
- world_12 (water): wrong=['due_date'], review=False (expected False), issues=[]
- world_16 (repair): wrong=['ERROR'], review=True (expected False), issues=[]
- world_17 (tuition): wrong=['ERROR'], review=True (expected False), issues=[]
- world_18 (rent): wrong=['ERROR'], review=True (expected False), issues=[]
- world_19 (courier): wrong=['ERROR'], review=True (expected False), issues=[]
- world_20 (event): wrong=['ERROR'], review=True (expected False), issues=[]
- world_21 (pharmacy): wrong=['ERROR'], review=True (expected False), issues=[]
- world_22 (usage): wrong=['ERROR'], review=True (expected False), issues=[]
- world_23 (insurance): wrong=['ERROR'], review=True (expected False), issues=[]

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
