# A2 results: real set, gemini (2026-10-11 13:51)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 8 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 8/8 (100%)**
- Docs fully right (fields + review decision), adjusted scoring: **6/8 (75%)**; STRICT scoring: **6/8 (75%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **100%**
- Review flag: precision 100%, recall 100% (TP 1, FP 0, FN 0, TN 7)
- Per document: auto-processed correctly **6**, sent to a human rightly **1** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 1** (wrong fields and NOT flagged), of which **0 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/8 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1501 ms, max 3850 ms; run total 31 s
- Tokens per document: 2194 (in 1683, out 512)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 8/8 (100%) |
| invoice_number | 8/8 (100%) |
| po_number | 7/8 (88%) |
| invoice_date | 8/8 (100%) |
| due_date | 8/8 (100%) |
| currency | 8/8 (100%) |
| subtotal | 8/8 (100%) |
| discount | 8/8 (100%) |
| tax_rate | 8/8 (100%) |
| tax_amount | 8/8 (100%) |
| other_charges | 8/8 (100%) |
| total | 8/8 (100%) |
| line_count | 7/8 (88%) |
| line_amounts | 7/8 (88%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| 4_pages_same_invoice | 1/1 |
| currency_ambiguous | 0/1 |
| shipping_line | 5/5 |
| statement_redacted | 0/1 |

## Failures

- real_07 (real): wrong=['line_count', 'line_amounts'], review=True (expected True), issues=['missing_required', 'missing_required']
- real_08 (real): wrong=['po_number'], review=False (expected False), issues=[]

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
