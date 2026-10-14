from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel

from .llm_extract import extract
from .pdftext import PdfError, extract_text
from .repairs import apply_repairs
from .schema import InvoiceExtraction
from .validators import Issue, check_deductions, check_grounding, check_numbers, needs_review, validate


class Result(BaseModel):
    extraction: InvoiceExtraction | None = None
    issues: list[Issue] = []
    needs_review: bool = True
    pages: int = 0
    text_chars: int = 0
    latency_ms: int = 0
    error: str | None = None
    attempts: int = 1


RETRY_CODES = {"missing_required", "line_missing_amount", "tax_missing"}
# Retry ONLY for structural omissions (items / tax). Never for vendor, dates, numbers: if those are really not printed,
# a retry just pressures the model into inventing something (seen on the hard set: an address became the vendor name).
RETRY_FIELDS = {"line_items", "tax_amount"}
ID_CODES = {"not_in_document", "reader_mismatch"}
ID_FIELDS = {"invoice_number", "po_number"}


def _errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def process_pdf(data: bytes, llm: Any, max_pages: int = 5, retry: bool = True, default_currency: str | None = None) -> Result:
    t0 = time.perf_counter()

    def ms() -> int:
        return int((time.perf_counter() - t0) * 1000)

    try:
        pdf = extract_text(data, max_pages=max_pages)
    except PdfError as e:
        return Result(error=str(e), issues=[Issue(code="bad_pdf", severity="error", message=str(e))], latency_ms=ms())

    base = dict(pages=pdf.pages, text_chars=pdf.chars)
    if pdf.scanned:
        msg = "no text layer (scanned PDF); vision fallback not implemented yet"
        return Result(**base, issues=[Issue(code="scanned_pdf", severity="error", message=msg)], latency_ms=ms())
    extra: list[Issue] = []
    if pdf.pages > pdf.pages_read:
        extra.append(Issue(code="truncated", severity="warning", message=f"only first {pdf.pages_read} of {pdf.pages} pages read"))

    def evaluate(ext: InvoiceExtraction) -> tuple[InvoiceExtraction, list[Issue]]:
        ext, notes = apply_repairs(ext, pdf.text, default_currency)
        return ext, validate(ext) + check_grounding(ext, pdf.text, pdf.alt_text) + check_numbers(ext, pdf.text, pdf.alt_text) + check_deductions(ext, pdf.text) + notes

    try:
        ext, issues = evaluate(extract(pdf.text, llm))
    except Exception as e:
        return Result(**base, error=f"LLM extraction failed: {type(e).__name__}: {e}", latency_ms=ms())
    attempts = 1
    gaps = [i for i in issues if i.code in RETRY_CODES and i.field in RETRY_FIELDS]
    if retry and gaps:
        # Only gaps (missing values) trigger a retry. Arithmetic errors are NOT retried: they are usually
        # real errors printed on the document and must reach a human.
        problems = sorted({i.message for i in gaps})[:6]
        try:
            ext2, issues2 = evaluate(extract(pdf.text, llm, previous=ext, problems=problems))
            attempts = 2
            if len(_errors(issues2)) <= len(_errors(issues)):
                ext, issues = ext2, issues2
        except Exception:
            attempts = 2  # keep the first answer
    # Identifier repair: if an ID is invented or the two PDF engines disagree about it, read the document again
    # from the OTHER engine's text and keep that answer only if it has fewer errors.
    ident = [i for i in issues if i.code in ID_CODES and i.field in ID_FIELDS]
    if retry and ident and pdf.alt_text:
        try:
            ext3, issues3 = evaluate(extract(pdf.alt_text, llm))
            attempts += 1
            if len(_errors(issues3)) < len(_errors(issues)):
                ext, issues = ext3, issues3
        except Exception:
            attempts += 1
    issues = issues + extra
    return Result(**base, extraction=ext, issues=issues, needs_review=needs_review(issues), latency_ms=ms(), attempts=attempts)
