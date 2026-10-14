"""Standalone app for local/docker use:  uvicorn extractor.main:app --reload --port 8002"""
from fastapi import FastAPI

from .api import router

app = FastAPI(title="A2 Invoice Extraction")
app.include_router(router)
