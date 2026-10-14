# A2 results (2026-10-08 07:55)

Provider: `gemini` | docs: 36 | retry: on | synthetic invoices only

## Headline

- Docs with ALL fields correct: **36/36 (100%)**
- Total amount exact match: **100%**
- Review flag: precision 100%, recall 100% (TP 6, FP 0, FN 0, TN 30)
- Retries used: 6/36 docs; hard errors (API/PDF): 0
- Latency per doc (incl. retry): median 1652 ms, max 13253 ms; total 162 s
- Cost per document: TODO (parse llm_calls.jsonl)

## Field accuracy

| field | correct |
|---|---|
| vendor_name | 36/36 (100%) |
| invoice_number | 36/36 (100%) |
| po_number | 36/36 (100%) |
| invoice_date | 36/36 (100%) |
| due_date | 36/36 (100%) |
| currency | 36/36 (100%) |
| subtotal | 36/36 (100%) |
| discount | 36/36 (100%) |
| tax_rate | 36/36 (100%) |
| tax_amount | 36/36 (100%) |
| total | 36/36 (100%) |
| line_count | 36/36 (100%) |
| line_amounts | 36/36 (100%) |

## By trap (docs fully correct)

| trap | ok/total |
|---|---|
| (none) | 10/10 |
| bad_arithmetic | 4/4 |
| discount | 5/5 |
| eu_number_format | 7/7 |
| line_mismatch | 2/2 |
| multi_page | 4/4 |
| no_due_date | 5/5 |
| no_tax | 4/4 |
| partial_payment | 3/3 |
| prompt_injection | 2/2 |

## Failures

- none

_Failure analysis (why each failure happened, what was changed): TODO after reading the failures above._
