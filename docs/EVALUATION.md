# How the evaluation works

**Ground truth** is what is *printed* on the page. A model must copy it, not fix it. Documents whose printed numbers are inconsistent are labelled `needs_review = true`.

**Per document, the outcome is one of:**

| Outcome | Meaning |
|---|---|
| auto-processed correctly | no review flag, no wrong field |
| sent to a human rightly | flagged, and there was a real problem (in the PDF, or a model mistake that was caught) |
| sent needlessly | flagged although everything was right (costs human time) |
| **silent error** | wrong field(s) and **not** flagged. *Critical* = vendor, invoice number, dates, currency or total |

**Scoring:** *strict* compares every field with the label. *Adjusted* additionally treats (1) an omitted subtotal as acceptable (derivable from the lines) and (2) a discount returned as a negative line item as equal money. Both are always printed.

**Honest-test rules used here:** a set is run once when it is fresh; fixes are made from what the failures show; the fix is then confirmed on a new seed. After a fix, a set is "seen" and no longer a test of generalisation. The checks (not only the prompt) are also run on the *correct* answers of every set (dry run) to find false alarms before releasing.

**Repeat runs:** the model answers differ from run to run. Run a set several times with `--tag _r1`, `--tag _r2`, ... (the tag keeps result files apart) and report the range, not one number. A provider run that has API errors (for example `429`) is marked INVALID in `docs/PROVIDERS.md` and must not be compared.

**Reproduce:**

```powershell
python scripts/run_eval.py --set <easy|hard|real|world|world2|world3|world4|world5> [--provider groq] [--default-currency USD] [--sleep 2]
python scripts/show_diffs.py        # AI answer vs correct answer for every document with a mistake or a needless alarm
python scripts/make_report.py       # side-by-side HTML (PDF picture, extracted text, AI answer, checks)
python scripts/compare_providers.py # docs/PROVIDERS.md from all runs
```

`--default-currency` is a client-style setting: used only when a document prints no currency at all.
