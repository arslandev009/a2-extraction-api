# A2 results: world set, gemini (2026-10-11 07:43)

Provider: `gemini` | model: `gemini-3.5-flash-lite` | docs: 24 | retry: on | synthetic invoices only

## Headline

- Docs fully right (fields + review decision), adjusted scoring: **16/24 (67%)**; STRICT scoring: **12/24 (50%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **79%**
- Review flag: precision 0%, recall n/a (TP 0, FP 5, FN 0, TN 19)
- Per document: auto-processed correctly **16**, sent to a human rightly **5** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 3** (wrong fields and NOT flagged), of which **1 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/24 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1541 ms, max 5223 ms; run total 92 s
- Tokens per document: 2187 (in 1538, out 649)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 24/24 (100%) |
| invoice_number | 24/24 (100%) |
| po_number | 24/24 (100%) |
| invoice_date | 24/24 (100%) |
| due_date | 23/24 (96%) |
| currency | 24/24 (100%) |
| subtotal | 24/24 (100%) |
| discount | 23/24 (96%) |
| tax_rate | 21/24 (88%) |
| tax_amount | 24/24 (100%) |
| other_charges | 24/24 (100%) |
| total | 19/24 (79%) |
| line_count | 24/24 (100%) |
| line_amounts | 24/24 (100%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| agency | 2/2 |
| electricity | 0/2 |
| freelancer | 2/2 |
| hotel | 1/2 |
| marketplace | 2/2 |
| medical | 0/2 |
| pk_tax | 1/2 |
| restaurant | 2/2 |
| retail | 2/2 |
| saas | 1/2 |
| telecom | 1/2 |
| wholesale | 2/2 |

## Failures

- world_02 (electricity): wrong=['tax_rate', 'total'], review=True (expected False), issues=['tax_math', 'total_mismatch', 'vendor_name_joined']
- world_06 (medical): wrong=['discount', 'total'], review=False (expected False), issues=[]
- world_09 (hotel): wrong=['tax_rate'], review=False (expected False), issues=['tax_math']
- world_10 (pk_tax): wrong=['tax_rate'], review=False (expected False), issues=['tax_math']
- world_12 (saas): wrong=['due_date'], review=True (expected False), issues=['date_not_in_document']
- world_14 (electricity): wrong=['total'], review=True (expected False), issues=['total_mismatch']
- world_15 (telecom): wrong=['total'], review=True (expected False), issues=['total_mismatch']
- world_18 (medical): wrong=['total'], review=True (expected False), issues=['total_mismatch']

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
