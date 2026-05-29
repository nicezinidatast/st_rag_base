"""메시지 로그: 유저 질문 및 LLM 최종 답변.

[구현 가이드] 실시간 대화 맥락은 Redis(memory.py)에서, 영구 로그/감사는 여기 RDBMS 에.
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str]  # "user" | "assistant" | "system"
    content: Mapped[str] = mapped_column(Text)
