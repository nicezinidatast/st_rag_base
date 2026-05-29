"""Phase 1: POST /api/v1/chat 동기(stream=false) 경로 테스트.

ChatModel 을 가짜로 끼워 실제 LLM 호출 없이 엔드포인트 직렬화를 검증한다.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

import app.clients.chat_model as chat_model_module
from app.core.config import settings
from app.main import app
from app.utils.streaming import NO_API_KEY_MESSAGE


class _FakeChatModel:
    async def achat(self, messages, **kwargs):
        return "fake-answer"

    async def astream(self, messages, **kwargs):
        for tok in ["fake", "-", "answer"]:
            yield tok


def test_chat_sync_returns_chat_response(monkeypatch):
    # 키가 있어야 가드를 통과해 실제(가짜) 모델 경로로 간다.
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    # run_chat_sync 가 호출 시점에 import 하는 get_chat_model 을 가짜로 교체.
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _FakeChatModel()
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": False,
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "fake-answer"
    assert body["citations"] == []
    assert body["rag_mode"] == "auto"
    assert body["conversation_id"]  # 자동 생성된 uuid


def test_chat_sync_without_key_returns_guard_message(monkeypatch):
    """키가 없으면 인증 에러 대신 안내 답변을 돌려준다(개발 편의 가드)."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": False},
    )

    assert resp.status_code == 200
    assert resp.json()["answer"] == NO_API_KEY_MESSAGE


def test_chat_stream_returns_sse_token_events(monkeypatch):
    """stream=True 면 토큰이 SSE 프레임(event: token)으로 흘러오고 done 으로 끝난다."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _FakeChatModel()
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert resp.status_code == 200
    body = resp.text
    assert "event: token" in body
    assert "data: fake" in body
    assert "data: answer" in body
    assert "event: done" in body


def test_chat_stream_without_key_streams_guard_message(monkeypatch):
    """키가 없으면 스트리밍에서도 안내 메시지를 토큰으로 흘리고 정상 종료."""
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"messages": [{"role": "user", "content": "hi"}], "stream": True},
    )

    assert resp.status_code == 200
    assert NO_API_KEY_MESSAGE in resp.text
    assert "event: done" in resp.text
