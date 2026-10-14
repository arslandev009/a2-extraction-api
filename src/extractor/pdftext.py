"""PDF -> text (pdfplumber). Scanned PDFs (no text layer) are detected; vision fallback comes later."""
from __future__ import annotations

import io
from dataclasses import dataclass

import pdfplumber


class PdfError(ValueError):
    pass


@dataclass
class PdfText:
    text: str
    pages: int
    pages_read: int
    chars: int
    scanned: bool
    alt_text: str | None = None  # second opinion from a different PDF engine (pdfium)


def _alt_text(data: bytes, max_pages: int) -> str | None:
    """Same PDF read by Chrome's engine (pdfium). Reading order differs, but characters are grouped differently, which
    exposes values the primary reader split (e.g. an invoice number printed on slightly different baselines)."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        parts = [pdf[i].get_textpage().get_text_range().replace("\r\n", "\n") for i in range(min(len(pdf), max_pages))]
        return "\n\n--- page break ---\n\n".join(parts).strip()
    except Exception:
        return None


def extract_text(data: bytes, max_pages: int = 5) -> PdfText:
    if not data.startswith(b"%PDF"):
        raise PdfError("not a PDF file")
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            n = len(pdf.pages)
            parts = [(p.extract_text() or "") for p in pdf.pages[:max_pages]]
    except Exception as e:  # corrupt/encrypted
        raise PdfError(f"cannot read PDF: {e}") from e
    text = "\n\n--- page break ---\n\n".join(parts).strip()
    read = min(n, max_pages)
    scanned = len(text) < 40 * max(read, 1)
    return PdfText(text=text, pages=n, pages_read=read, chars=len(text), scanned=scanned, alt_text=_alt_text(data, max_pages))
