# A2 results: easy set, groq (2026-10-12 14:05)

Provider: `groq` | model: `openai/gpt-oss-120b` | docs: 36 | retry: on | synthetic invoices only

## Headline

- **Critical fields all right (vendor, invoice number, dates, currency, total): 36/36 (100%)**
- Docs fully right (fields + review decision), adjusted scoring: **1/36 (3%)**; STRICT scoring: **1/36 (3%)**
  (adjusted = an omitted subtotal is not an error, and a discount returned as a negative line item counts as equal money)
- Total amount exact match (scored docs): **100%**
- Review flag: precision 17%, recall 100% (TP 6, FP 29, FN 0, TN 1)
- Per document: auto-processed correctly **1**, sent to a human rightly **35** (real problem in the PDF or caught an extraction error), sent needlessly **0**, **SILENT ERRORS 0** (wrong fields and NOT flagged), of which **0 in critical fields** (vendor, invoice number, dates, currency, total)
- Retries used: 0/36 docs; hard errors (API/PDF): 35
- Latency per doc (incl. retry): median 9432 ms, max 52234 ms; run total 451 s
- Tokens per document: 97 (in 66, out 30)
- Cost per document: $0.00000 (free tiers report 0)

## Field accuracy (scored docs)

| field | correct |
|---|---|
| vendor_name | 1/1 (100%) |
| invoice_number | 1/1 (100%) |
| po_number | 1/1 (100%) |
| invoice_date | 1/1 (100%) |
| due_date | 1/1 (100%) |
| currency | 1/1 (100%) |
| subtotal | 1/1 (100%) |
| discount | 1/1 (100%) |
| tax_rate | 1/1 (100%) |
| tax_amount | 1/1 (100%) |
| other_charges | 1/1 (100%) |
| total | 1/1 (100%) |
| line_count | 1/1 (100%) |
| line_amounts | 1/1 (100%) |

## By trap / kind (docs fully right)

| trap | ok/total |
|---|---|
| (none) | 1/10 |
| bad_arithmetic | 0/4 |
| discount | 0/5 |
| eu_number_format | 0/7 |
| line_mismatch | 0/2 |
| multi_page | 0/4 |
| no_due_date | 0/5 |
| no_tax | 0/4 |
| partial_payment | 0/3 |
| prompt_injection | 0/2 |

## Failures

- inv_00 (classic): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_01 (minimal): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_02 (twocol): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_03 (lines): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_04 (footer_heavy): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_05 (mono): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_06 (classic): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_07 (minimal): wrong=['ERROR'], review=True (expected True), issues=[]
- inv_08 (twocol): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_09 (lines): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_10 (footer_heavy): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_11 (mono): wrong=['ERROR'], review=True (expected True), issues=[]
- inv_12 (classic): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_13 (minimal): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_14 (twocol): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_15 (lines): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_16 (footer_heavy): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_17 (mono): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_18 (classic): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_19 (minimal): wrong=['ERROR'], review=True (expected True), issues=[]
- inv_20 (twocol): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_21 (lines): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_22 (footer_heavy): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_23 (mono): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_24 (classic): wrong=['ERROR'], review=True (expected True), issues=[]
- inv_25 (minimal): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_26 (twocol): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_28 (footer_heavy): wrong=['ERROR'], review=True (expected True), issues=[]
- inv_29 (mono): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_30 (classic): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_31 (minimal): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_32 (twocol): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_33 (lines): wrong=['ERROR'], review=True (expected True), issues=[]
- inv_34 (footer_heavy): wrong=['ERROR'], review=True (expected False), issues=[]
- inv_35 (mono): wrong=['ERROR'], review=True (expected False), issues=[]

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
