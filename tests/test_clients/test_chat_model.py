"""ChatModel 팩토리 단위 테스트 — provider:model → LangChain BaseChatModel.

실제 LLM 호출은 하지 않는다(생성만 검증, 키는 더미 주입).
"""
from __future__ import annotations

import pytest
from langchain_core.language_models import BaseChatModel

from app.clients.chat_model import get_chat_model
from app.core.config import settings


def test_get_chat_model_builds_anthropic(monkeypatch):
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    model = get_chat_model("anthropic:claude-haiku-4-5-20251001")
    assert isinstance(model, BaseChatModel)


def test_get_chat_model_builds_openai(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    model = get_chat_model("openai:gpt-4o-mini")
    assert isinstance(model, BaseChatModel)


def test_get_chat_model_defaults_to_settings(monkeypatch):
    """spec 미지정 시 settings.DEFAULT_CHAT_MODEL(anthropic) 로 빌드."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    assert isinstance(get_chat_model(), BaseChatModel)


def test_get_chat_model_unknown_provider_raises():
    with pytest.raises(ValueError, match="등록되지 않은 chat provider"):
        get_chat_model("nope:some-model")
