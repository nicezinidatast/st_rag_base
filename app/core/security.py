"""인증 프리미티브: 비밀번호 해싱(bcrypt), JWT 발급/검증(pyjwt).

- deps.py 의 get_current_user 가 decode_access_token 을 호출해 사용자 주체를 복원.
- passlib 대신 bcrypt 를 직접 사용(passlib 은 bcrypt 4.x 와 호환이 깨진 채 미유지).
- API 키 방식이 필요해지면 별도 검증 함수를 여기에 추가.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:  # 손상된/형식이 다른 해시
        return False


def create_access_token(subject: str) -> str:
    """subject(사용자 식별자, 여기서는 email)로 서명된 JWT 를 발급."""
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """토큰 검증 + payload 반환. 무효/만료 시 jwt.InvalidTokenError 를 던진다."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
