"""대화/메시지 RDBMS 영속화 (Phase 7).

실시간 멀티턴 맥락은 Redis(memory.py, 휘발·TTL)에, 영구 로그/감사는 여기 Postgres 에.
- session_id 로 Conversation 을 get-or-create 한 뒤 user/assistant 메시지 2건을 적재.
- AUTH_ENABLED + 인증 사용자일 때만 호출된다(user_id 없으면 no-op).
- DB 장애는 비치명: 답변은 이미 사용자에게 나간 뒤이므로 경고 로그만 남기고 넘어간다.
"""
from __future__ import annotations

from sqlalchemy import select

from app.models.conversation import Conversation
from app.models.message import Message
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def save_exchange(session_id: str, user_id: int | None, question: str, answer: str) -> None:
    """질문/답변 한 쌍을 session_id 의 대화방에 영구 저장."""
    if not session_id or user_id is None:
        return
    from app.core.database import SessionLocal

    try:
        async with SessionLocal() as db:
            conv = (
                await db.execute(select(Conversation).where(Conversation.session_id == session_id))
            ).scalar_one_or_none()
            if conv is None:
                # 첫 메시지 → 대화방 생성. 질문 앞부분을 제목으로.
                conv = Conversation(user_id=user_id, session_id=session_id, title=question[:80])
                db.add(conv)
                await db.flush()  # conv.id 확보
            db.add(Message(conversation_id=conv.id, role="user", content=question))
            db.add(Message(conversation_id=conv.id, role="assistant", content=answer))
            await db.commit()
    except Exception as e:  # noqa: BLE001  영속화 실패는 비치명 → 채팅 계속
        logger.warning("persistence_skipped", session_id=session_id, error=str(e))
