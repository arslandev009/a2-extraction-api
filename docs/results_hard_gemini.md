# A2 results: hard set, gemini (2026-10-11 13:50)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 16 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 15/16 (94%)**
- Docs fully right (fields + review decision), adjusted scoring: **15/16 (94%)**; STRICT scoring: **15/16 (94%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **100%**
- Review flag: precision 80%, recall 100% (TP 4, FP 1, FN 0, TN 11)
- Per document: auto-processed correctly **11**, sent to a human rightly **5** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 0** (wrong fields and NOT flagged), of which **0 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/16 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1602 ms, max 2235 ms; run total 57 s
- Tokens per document: 1741 (in 1293, out 447)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 14/14 (100%) |
| invoice_number | 14/14 (100%) |
| po_number | 14/14 (100%) |
| invoice_date | 14/14 (100%) |
| due_date | 13/14 (93%) |
| currency | 14/14 (100%) |
| subtotal | 14/14 (100%) |
| discount | 14/14 (100%) |
| tax_rate | 14/14 (100%) |
| tax_amount | 14/14 (100%) |
| other_charges | 14/14 (100%) |
| total | 14/14 (100%) |
| line_count | 14/14 (100%) |
| line_amounts | 14/14 (100%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| credit_note | 1/1 |
| french | 1/1 |
| german | 1/2 |
| missing_date | 1/1 |
| missing_vendor | 1/1 |
| ocr_noise | 2/2 |
| parties_swapped | 2/2 |
| scanned | 2/2 |
| us_date | 2/2 |
| wrapped_lines | 2/2 |

## Failures

- hard_01 (german): wrong=['due_date'], review=True (expected False), issues=['date_not_in_document']

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
