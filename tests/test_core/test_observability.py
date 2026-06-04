"""core/observability.py 테스트: 비활성화 no-op / 키 누락 가드 / 활성화 시 config 생성."""
from __future__ import annotations

import pytest

import app.core.observability as obs
from app.core.config import settings


@pytest.fixture(autouse=True)
def reset_client(monkeypatch):
    """테스트 간 전역 클라이언트 격리."""
    monkeypatch.setattr(obs, "_langfuse_client", None)


def test_disabled_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "LANGFUSE_ENABLED", False)
    obs.init_langfuse()
    assert obs.get_langfuse() is None
    assert obs.get_langgraph_callback() is None
    assert obs.build_graph_config("sess-1") == {}


def test_enabled_without_keys_is_noop(monkeypatch):
    monkeypatch.setattr(settings, "LANGFUSE_ENABLED", True)
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", None)
    obs.init_langfuse()
    assert obs.get_langfuse() is None


def test_enabled_with_keys_builds_client_and_config(monkeypatch):
    monkeypatch.setattr(settings, "LANGFUSE_ENABLED", True)
    monkeypatch.setattr(settings, "LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setattr(settings, "LANGFUSE_SECRET_KEY", "sk-test")

    import langfuse

    created: dict = {}

    class FakeLangfuse:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def flush(self):
            created["flushed"] = True

    monkeypatch.setattr(langfuse, "Langfuse", FakeLangfuse)

    obs.init_langfuse()
    assert isinstance(obs.get_langfuse(), FakeLangfuse)
    assert created["public_key"] == "pk-test"
    assert created["base_url"] == settings.LANGFUSE_HOST

    config = obs.build_graph_config("sess-1", user_id=7)
    assert len(config["callbacks"]) == 1
    assert config["metadata"] == {
        "langfuse_session_id": "sess-1",
        "langfuse_user_id": "7",
    }

    obs.shutdown_langfuse()
    assert created.get("flushed") is True
