"""Dense 벡터 저장소 클라이언트 (기본 Qdrant, 배포별 교체 가능).

[구현 가이드]
- get_vector_client() 가 설정된 백엔드 클라이언트를 반환하도록 구현.
- 컬렉션 차원(dim)은 반드시 embedding.py 의 Embedder.dim 과 일치시킬 것.
- ir/vector/ingest.py(upsert), ir/vector/search.py(검색)에서 이 클라이언트를 쓴다.
"""
from __future__ import annotations

from app.core.config import settings


def get_vector_client():
    # TODO: from qdrant_client import AsyncQdrantClient
    #       return AsyncQdrantClient(url=settings.VECTOR_DB_URL, api_key=settings.VECTOR_DB_API_KEY)
    raise NotImplementedError("vector_db 클라이언트 미구현")
