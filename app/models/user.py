"""사용자 및 접근권한(RBAC) 엔티티.

[구현 가이드] hashed_password 는 core.security.hash_password 결과만 저장.
role 로 RBAC 분기. 필요 시 ApiKey 테이블을 별도 모델로 추가.
"""
from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str]
    role: Mapped[str] = mapped_column(default="user")  # RBAC 역할
    is_active: Mapped[bool] = mapped_column(default=True)
