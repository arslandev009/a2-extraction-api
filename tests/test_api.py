from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from extractor.api import get_llm_dep, router

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client_factory(fake_llm_cls):
    def make(payload=None, exc=None):
        app = FastAPI()
        app.include_router(router, prefix="/a2")  # same way demo-api will mount it
        app.dependency_overrides[get_llm_dep] = lambda: fake_llm_cls(payload, exc)
        return TestClient(app)
    return make


def _file(row):
    return {"file": (row["file"], (ROOT / "data" / "invoices" / row["file"]).read_bytes(), "application/pdf")}


def test_health(client_factory):
    assert client_factory().get("/a2/health").json()["ok"] is True


def test_extract_ok(client_factory, truth_rows):
    row = truth_rows[0]
    r = client_factory(row["expected"]).post("/a2/extract", files=_file(row))
    assert r.status_code == 200
    body = r.json()
    assert body["extraction"]["total"] == row["expected"]["total"] and body["needs_review"] is False


def test_rejects_non_pdf(client_factory):
    r = client_factory({}).post("/a2/extract", files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 415


def test_rejects_big_file(client_factory, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "0.001")
    r = client_factory({}).post("/a2/extract", files={"file": ("x.pdf", b"%PDF" + b"0" * 5000, "application/pdf")})
    assert r.status_code == 413


def test_gateway_secret(client_factory, truth_rows, monkeypatch):
    monkeypatch.setenv("GATEWAY_SECRET", "s3cret")
    row = truth_rows[0]
    c = client_factory(row["expected"])
    assert c.post("/a2/extract", files=_file(row)).status_code == 403
    assert c.post("/a2/extract", files=_file(row), headers={"X-Gateway-Secret": "s3cret"}).status_code == 200


def test_llm_failure_gives_502(client_factory, truth_rows):
    row = truth_rows[0]
    r = client_factory(exc=RuntimeError("boom")).post("/a2/extract", files=_file(row))
    assert r.status_code == 502
