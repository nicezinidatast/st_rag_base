"""Mock 검색기 — 실제 Vector DB/임베딩 없이 RAG 흐름을 점검하는 개발용 대역.

settings.MOCK_RETRIEVER 가 true 일 때 _retrieve_context 가 VectorRetriever 대신
이걸 쓴다. 쿼리와 무관하게 포켓몬에 대한 가상 문서 5건을 고정 반환한다.
"""
from __future__ import annotations

from app.services.ir.base import RetrievedChunk, Retriever

# 쿼리와 무관하게 항상 돌려주는 고정 포켓몬 가상 문서 5건.
_MOCK_DOCS: list[RetrievedChunk] = [
    RetrievedChunk(
        content="피카츄는 전기 타입 포켓몬으로, 볼에 있는 전기 주머니에 전기를 저장한다. "
        "진화 전 단계는 피츄, 천둥의돌로 라이츄로 진화한다.",
        score=0.98,
        source_id="mock-pokemon-pikachu",
        metadata={"name": "피카츄", "type": "전기", "no": 25},
    ),
    RetrievedChunk(
        content="charizard(리자몽)은 불꽃/비행 타입 포켓몬이다. 파이리 → 리자드 → 리자몽으로 "
        "진화하며, 강한 상대와 싸울 때 꼬리의 불꽃이 더욱 거세게 타오른다.",
        score=0.95,
        source_id="mock-pokemon-charizard",
        metadata={"name": "리자몽", "type": "불꽃/비행", "no": 6},
    ),
    RetrievedChunk(
        content="꼬부기는 물 타입 포켓몬으로, 등껍질에 몸을 숨겨 몸을 보호한다. "
        "어니부기를 거쳐 거북왕으로 진화하며 등의 대포로 고압 물줄기를 발사한다.",
        score=0.92,
        source_id="mock-pokemon-squirtle",
        metadata={"name": "꼬부기", "type": "물", "no": 7},
    ),
    RetrievedChunk(
        content="뮤츠는 초능력 타입의 전설의 포켓몬이다. 뮤의 유전자를 바탕으로 인공적으로 "
        "만들어졌으며, 사납고 강력한 사이코 키네시스 능력을 지녔다.",
        score=0.90,
        source_id="mock-pokemon-mewtwo",
        metadata={"name": "뮤츠", "type": "에스퍼", "no": 150},
    ),
    RetrievedChunk(
        content="이상해씨는 풀/독 타입 포켓몬으로, 등에 식물의 씨앗을 짊어지고 태어난다. "
        "햇빛을 받아 씨앗이 자라며 이상해풀, 이상해꽃으로 진화한다.",
        score=0.88,
        source_id="mock-pokemon-bulbasaur",
        metadata={"name": "이상해씨", "type": "풀/독", "no": 1},
    ),
]


class MockRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        return _MOCK_DOCS[:top_k]
