"""Extraction schema. Everything is optional on purpose: the model must answer null instead of
guessing, and validators.py turns missing/wrong values into review issues (never a crash)."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = Field(None, description="Line total exactly as printed (after any per-line discount)")
    discount_percent: float | None = Field(None, description="Per-line discount percent if the row has a discount column, else null")


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    vendor_name: str | None = Field(None, description="Company that ISSUED the invoice (not the customer)")
    invoice_number: str | None = Field(None, description="The invoice number, not PO/quote/customer/reference numbers")
    po_number: str | None = Field(None, description="Customer purchase order number if printed, else null")
    invoice_date: str | None = Field(None, description="ISO YYYY-MM-DD")
    due_date: str | None = Field(None, description="ISO YYYY-MM-DD, null if not printed")
    currency: str | None = Field(None, description="3-letter ISO code, e.g. USD")
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: float | None = Field(None, description="Sum of line amounts before discount and tax, as printed")
    discount: float | None = Field(None, description="Discount as a positive number, null/0 if none")
    tax_rate: float | None = Field(None, description="Tax percent as printed, e.g. 20 for 20%, null if none")
    tax_amount: float | None = Field(None, description="Sum of all tax lines as printed, 0 if no tax")
    other_charges: float | None = Field(None, description="Sum of shipping/delivery/handling/fee/rounding lines added to the total, as printed; null if none. Not taxes")
    total: float | None = Field(None, description="Grand total of THIS invoice's own charges as printed (not the balance due, not including any previous balance)")
    amount_due: float | None = Field(None, description="Amount still payable now as printed ('Amount due', 'Balance due', 'Total amount due'), after payments/deposits and including any previous balance; null if not printed")
