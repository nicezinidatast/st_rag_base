"""Phase 7 인증/영속화 테스트: 가입→로그인→/me, 토큰 차단, 메시지 DB 적재.

라이브 Postgres 없이 sqlite_db 픽스처(conftest)로 SessionLocal 을 교체해 검증한다.
"""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.clients.chat_model as chat_model_module
import app.core.database as database_module
from app.core.config import settings
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message
from tests.test_api.test_chat import _fake_chat_model, _patch_no_retrieval

client = TestClient(app)

CREDS = {"email": "user@example.com", "password": "password123"}


def _register_and_login() -> str:
    assert client.post("/api/v1/auth/register", json=CREDS).status_code == 201
    res = client.post("/api/v1/auth/token", json=CREDS)
    assert res.status_code == 200
    return res.json()["access_token"]


def test_register_login_me_flow(sqlite_db):
    token = _register_and_login()

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["email"] == CREDS["email"]
    assert body["role"] == "user"
    assert "hashed_password" not in body


def test_register_duplicate_email_409(sqlite_db):
    assert client.post("/api/v1/auth/register", json=CREDS).status_code == 201
    assert client.post("/api/v1/auth/register", json=CREDS).status_code == 409


def test_login_wrong_password_401(sqlite_db):
    client.post("/api/v1/auth/register", json=CREDS)
    res = client.post(
        "/api/v1/auth/token", json={"email": CREDS["email"], "password": "wrong-password"}
    )
    assert res.status_code == 401


def test_me_without_token_401(sqlite_db):
    assert client.get("/api/v1/auth/me").status_code == 401
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert res.status_code == 401


def test_chat_blocked_without_token_when_auth_enabled(sqlite_db, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    res = client.post("/api/v1/chat", json={"question": "hi", "stream": False})
    assert res.status_code == 401


def test_chat_open_when_auth_disabled():
    """AUTH_ENABLED=false(기본)면 기존처럼 토큰·Postgres 없이 동작한다."""
    res = client.post("/api/v1/chat", json={"question": "hi", "stream": False})
    assert res.status_code == 200


def test_chat_persists_messages_when_authenticated(sqlite_db, monkeypatch):
    monkeypatch.setattr(settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _fake_chat_model()
    )
    _patch_no_retrieval(monkeypatch)

    token = _register_and_login()
    res = client.post(
        "/api/v1/chat",
        json={"question": "포켓몬 마스터가 되려면?", "stream": False, "session_id": "sess-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200

    async def _fetch():
        async with database_module.SessionLocal() as db:
            conv = (
                await db.execute(select(Conversation).where(Conversation.session_id == "sess-1"))
            ).scalar_one()
            msgs = (
                await db.execute(select(Message).where(Message.conversation_id == conv.id))
            ).scalars().all()
            return conv, msgs

    conv, msgs = asyncio.run(_fetch())
    assert conv.title.startswith("포켓몬")
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "fake answer"
