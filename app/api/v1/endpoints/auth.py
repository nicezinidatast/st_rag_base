"""사용자 인증 및 API 키 관리 엔드포인트.

[구현 가이드]
- POST /token: 자격증명 검증 후 core.security.create_access_token 으로 토큰 발급.
- GET /me: Depends(get_current_user) 로 현재 주체 반환.
- API 키 발급/회수 엔드포인트도 여기에 추가.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

router = APIRouter()


@router.post("/token")
async def login() -> dict:
    # TODO: 자격증명 검증 → 토큰 발급
    raise NotImplementedError


@router.get("/me")
async def me(user=Depends(get_current_user)) -> dict:
    return {"user": user}
