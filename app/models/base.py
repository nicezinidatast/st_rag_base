"""ORM 공통 베이스 + 타임스탬프 믹스인.

[구현 가이드] 모든 모델은 Base 를 상속. Alembic 이 Base.metadata 를 스캔하도록
migration/env.py 에서 이 Base 를 import 할 것.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
