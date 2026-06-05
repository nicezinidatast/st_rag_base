"""POST /api/v1/chat 동기(stream=false)/스트리밍(stream=true) 경로 테스트.

ChatModel 과 vector 검색을 가짜로 끼워 실제 LLM/Qdrant 호출 없이
엔드포인트 직렬화 + RAG 컨텍스트/출처 흐름을 검증한다.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.clients.chat_model as chat_model_module
import app.services.ir.vector.search as search_module
from app.core.config import settings
from app.main import app
from app.services.ir.base import RetrievedChunk
from app.utils.streaming import NO_API_KEY_MESSAGE


def _fake_chat_model(content="fake answer"):
    """LangChain BaseChatModel 대역. ainvoke=전체 메시지, astream_events=토큰 이벤트.

    공백 기준으로 청크가 쪼개진다("fake answer" → "fake"/" "/"answer").
    매 호출마다 새 인스턴스를 줘야 메시지 이터레이터가 소진되지 않는다.
    """
    return GenericFakeChatModel(messages=iter([AIMessage(content=content)]))


class _FakeRetriever:
    """VectorRetriever 대역. 주어진 청크를 그대로 반환."""

    def __init__(self, chunks=None):
        self._chunks = chunks or []

    async def retrieve(self, query, top_k=5, **kwargs):
        return self._chunks


def _patch_no_retrieval(monkeypatch):
    monkeypatch.setattr(search_module, "VectorRetriever", lambda: _FakeRetriever([]))


def test_chat_sync_returns_chat_response(monkeypatch):
    # 챗 LLM(Anthropic) 키가 있어야 가드를 통과해 (가짜) 모델 경로로 간다.
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model()
    )
    _patch_no_retrieval(monkeypatch)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"question": "안녕?", "stream": False},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "fake answer"
    assert body["citations"] == []
    assert body["rag_mode"] == "auto"
    assert body["session_id"]  # 자동 생성된 uuid
    assert body["model"]  # 사용된 provider:model 이 응답에 실린다


def test_chat_sync_echoes_given_session_id(monkeypatch):
    """요청에 session_id 를 주면 응답에 그대로 유지된다."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model()
    )
    _patch_no_retrieval(monkeypatch)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"question": "안녕?", "session_id": "sess-42", "stream": False},
    )

    assert resp.status_code == 200
    assert resp.json()["session_id"] == "sess-42"


def test_chat_sync_with_retrieval_includes_citations(monkeypatch):
    """검색 결과가 있으면 citations 가 응답에 실린다."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model()
    )
    chunk = RetrievedChunk(
        content="서울은 대한민국의 수도이다.",
        score=0.9,
        source_id="doc-1",
        metadata={},
    )
    monkeypatch.setattr(
        search_module, "VectorRetriever", lambda: _FakeRetriever([chunk])
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"question": "수도가 어디야?", "stream": False},
    )

    assert resp.status_code == 200
    citations = resp.json()["citations"]
    assert len(citations) == 1
    assert citations[0]["source_id"] == "doc-1"
    assert citations[0]["score"] == 0.9


def test_chat_sync_model_override_is_echoed(monkeypatch):
    """요청의 model 오버라이드가 응답 model 에 그대로 반영된다."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    captured = {}

    def _fake_get(spec=None):
        captured["spec"] = spec
        return _fake_chat_model()

    monkeypatch.setattr(chat_model_module, "get_chat_model", _fake_get)
    _patch_no_retrieval(monkeypatch)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={
            "question": "안녕?",
            "model": "anthropic:claude-haiku-4-5-20251001",
            "stream": False,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["model"] == "anthropic:claude-haiku-4-5-20251001"
    assert captured["spec"] == "anthropic:claude-haiku-4-5-20251001"


def test_chat_question_is_required():
    """question 은 필수 — 없으면 422."""
    client = TestClient(app)
    resp = client.post("/api/v1/chat", json={"stream": False})
    assert resp.status_code == 422


def test_chat_sync_without_key_returns_guard_message(monkeypatch):
    """챗 LLM 키가 없으면 인증 에러 대신 안내 답변을 돌려준다(개발 편의 가드)."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")

    client = TestClient(app)
    resp = client.post("/api/v1/chat", json={"question": "안녕?", "stream": False})

    assert resp.status_code == 200
    assert resp.json()["answer"] == NO_API_KEY_MESSAGE


def test_chat_stream_returns_sse_token_events(monkeypatch):
    """stream=True 면 토큰이 SSE 프레임(event: token)으로 흘러오고 done 으로 끝난다."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model()
    )
    _patch_no_retrieval(monkeypatch)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/chat",
        json={"question": "안녕?", "stream": True},
    )

    assert resp.status_code == 200
    body = resp.text
    assert "event: token" in body
    assert "data: fake" in body
    assert "data: answer" in body
    assert "event: done" in body


def test_chat_stream_without_key_streams_guard_message(monkeypatch):
    """키가 없으면 스트리밍에서도 안내 메시지를 토큰으로 흘리고 정상 종료."""
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")

    client = TestClient(app)
    resp = client.post("/api/v1/chat", json={"question": "안녕?", "stream": True})

    assert resp.status_code == 200
    assert NO_API_KEY_MESSAGE in resp.text
    assert "event: done" in resp.text
