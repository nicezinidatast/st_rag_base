"""모든 검색 엔진이 구현하는 표준 인터페이스 (Retrieval 인터페이스).

[설계 의도] vector / graph-local / graph-global 어느 엔진이든 동일한 retrieve()
시그니처를 갖게 해서, workflow/nodes/retrieve.py 가 rag_mode 에 따라 엔진만
바꿔 끼우면 되도록 한다(전략 패턴).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    content: str
    score: float
    source_id: str
    metadata: dict


class Retriever(ABC):
    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        """쿼리에 대한 상위 청크 반환. 모든 엔진이 이 시그니처를 따른다."""
        ...
