import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def truth_rows():
    with open(ROOT / "data" / "ground_truth.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


class FakeLLM:
    """Returns a preset dict for chat_json; records calls. Lets us test everything without network."""

    def __init__(self, payload=None, exc=None):
        self.payload, self.exc, self.calls = payload, exc, []

    def chat_json(self, messages, schema):
        self.calls.append(messages)
        if self.exc:
            raise self.exc
        return self.payload


@pytest.fixture
def fake_llm_cls():
    return FakeLLM
