# A2 results: easy set, gemini (2026-10-11 13:49)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 36 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 36/36 (100%)**
- Docs fully right (fields + review decision), adjusted scoring: **33/36 (92%)**; STRICT scoring: **33/36 (92%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **100%**
- Review flag: precision 75%, recall 100% (TP 6, FP 2, FN 0, TN 28)
- Per document: auto-processed correctly **28**, sent to a human rightly **8** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 0** (wrong fields and NOT flagged), of which **0 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/36 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1714 ms, max 6050 ms; run total 150 s
- Tokens per document: 2364 (in 1568, out 796)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 36/36 (100%) |
| invoice_number | 36/36 (100%) |
| po_number | 36/36 (100%) |
| invoice_date | 36/36 (100%) |
| due_date | 36/36 (100%) |
| currency | 36/36 (100%) |
| subtotal | 36/36 (100%) |
| discount | 34/36 (94%) |
| tax_rate | 36/36 (100%) |
| tax_amount | 36/36 (100%) |
| other_charges | 35/36 (97%) |
| total | 36/36 (100%) |
| line_count | 36/36 (100%) |
| line_amounts | 36/36 (100%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| (none) | 10/10 |
| bad_arithmetic | 3/4 |
| discount | 5/5 |
| eu_number_format | 7/7 |
| line_mismatch | 2/2 |
| multi_page | 4/4 |
| no_due_date | 5/5 |
| no_tax | 4/4 |
| partial_payment | 1/3 |
| prompt_injection | 2/2 |

## Failures

- inv_07 (minimal): wrong=['other_charges'], review=True (expected True), issues=['number_not_in_document']
- inv_20 (twocol): wrong=['discount'], review=True (expected False), issues=['total_mismatch']
- inv_30 (classic): wrong=['discount'], review=True (expected False), issues=['total_mismatch']

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
