"""core/security.py 단위 테스트: 해싱/JWT 왕복 + 무효 입력."""
from __future__ import annotations

import jwt
import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong", hashed)


def test_verify_password_malformed_hash():
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_token_roundtrip():
    token = create_access_token("user@example.com")
    payload = decode_access_token(token)
    assert payload["sub"] == "user@example.com"
    assert "exp" in payload


def test_decode_invalid_token_raises():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-jwt")
