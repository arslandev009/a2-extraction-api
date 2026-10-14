"""FastAPI router (mountable in the shared demo-api as /a2) + standalone app in main.py."""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile

from .pipeline import Result, process_pdf

router = APIRouter()

_llm_cache: dict[str, Any] = {}


def get_llm_dep() -> Any:
    if "llm" not in _llm_cache:
        from .llm_extract import get_llm

        _llm_cache["llm"] = get_llm()
    return _llm_cache["llm"]


def check_gateway(x_gateway_secret: str | None = Header(default=None)) -> None:
    secret = os.getenv("GATEWAY_SECRET", "")
    if secret and x_gateway_secret != secret:
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/health")
def health() -> dict:
    return {"ok": True, "module": "a2-extraction"}


@router.post("/extract", response_model=Result, dependencies=[Depends(check_gateway)])
def extract_endpoint(file: UploadFile = File(...), llm: Any = Depends(get_llm_dep)) -> Result:
    max_bytes = int(float(os.getenv("MAX_UPLOAD_MB", "3")) * 1024 * 1024)
    max_pages = int(os.getenv("MAX_PAGES", "5"))
    data = file.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="file too large")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="only PDF files are accepted")
    result = process_pdf(data, llm, max_pages=max_pages, default_currency=os.getenv("DEFAULT_CURRENCY") or None)
    if result.error and result.extraction is None and result.pages > 0 and not result.issues:
        raise HTTPException(status_code=502, detail=result.error)
    return result
