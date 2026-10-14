# A2 results: world2 set, gemini (2026-10-12 13:51)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 24 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 24/24 (100%)**
- Docs fully right (fields + review decision), adjusted scoring: **21/24 (88%)**; STRICT scoring: **21/24 (88%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **100%**
- Review flag: precision 0%, recall n/a (TP 0, FP 2, FN 0, TN 22)
- Per document: auto-processed correctly **21**, sent to a human rightly **2** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 1** (wrong fields and NOT flagged), of which **0 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/24 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1770 ms, max 5790 ms; run total 100 s
- Tokens per document: 2261 (in 1601, out 660)
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
| discount | 23/24 (96%) |
| tax_rate | 23/24 (96%) |
| tax_amount | 24/24 (100%) |
| other_charges | 24/24 (100%) |
| total | 24/24 (100%) |
| line_count | 24/24 (100%) |
| line_amounts | 24/24 (100%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| agency | 2/2 |
| electricity | 2/2 |
| freelancer | 1/2 |
| hotel | 0/2 |
| marketplace | 2/2 |
| medical | 2/2 |
| pk_tax | 2/2 |
| restaurant | 2/2 |
| retail | 2/2 |
| saas | 2/2 |
| telecom | 2/2 |
| wholesale | 2/2 |

## Failures

- world_01 (freelancer): wrong=['discount'], review=True (expected False), issues=['total_mismatch']
- world_09 (hotel): wrong=['tax_rate'], review=False (expected False), issues=['tax_math']
- world_21 (hotel): wrong=['subtotal'], review=True (expected False), issues=['subtotal_mismatch', 'total_mismatch']

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
