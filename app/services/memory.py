"""Redis 기반 대화 히스토리 관리.

[구현 가이드] conversation_id 별 메시지 목록 저장/조회. generate 노드가 이전
맥락을 프롬프트에 포함할 때 사용. 윈도우/요약 압축 전략 고려.
"""
from __future__ import annotations


async def append_message(conversation_id: str, role: str, content: str) -> None:
    raise NotImplementedError


async def get_history(conversation_id: str, limit: int = 20) -> list[dict]:
    raise NotImplementedError
