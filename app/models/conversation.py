"""대화방(Conversation) 메타데이터."""
from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Redis 대화 메모리(Phase 6)의 session_id 와 1:1 매핑 — 채팅 요청이 이 키로 대화방을 찾는다.
    session_id: Mapped[str] = mapped_column(unique=True, index=True)
    title: Mapped[str | None]
