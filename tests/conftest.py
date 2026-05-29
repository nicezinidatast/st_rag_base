"""Shared test fixtures: mock DB, mock Redis, fake LLM clients."""
from __future__ import annotations

import pytest


@pytest.fixture
def fake_llm():
    """Return a deterministic fake LLM client for unit tests."""
    class _FakeLLM:
        async def chat(self, *a, **k):
            return "fake-answer"

        async def embed(self, texts):
            return [[0.0] * 8 for _ in texts]

    return _FakeLLM()
