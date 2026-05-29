"""인증 프리미티브: 비밀번호 해싱, JWT 발급/검증, API 키 확인.

[구현 가이드]
- 해싱은 passlib(bcrypt) 권장. JWT 는 python-jose 또는 pyjwt.
- deps.py 의 get_current_user 가 decode_access_token 을 호출해 사용자 주체를 복원.
- API 키 방식도 지원하려면 별도 검증 함수 추가.
"""
from __future__ import annotations


def hash_password(password: str) -> str:
    raise NotImplementedError


def verify_password(plain: str, hashed: str) -> bool:
    raise NotImplementedError


def create_access_token(subject: str) -> str:
    raise NotImplementedError


def decode_access_token(token: str) -> dict:
    raise NotImplementedError
