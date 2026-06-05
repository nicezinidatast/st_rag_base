"""Dense 벡터 저장소 클라이언트 (기본 Qdrant, 배포별 교체 가능).

[구현 가이드]
- get_vector_client() 가 설정된 백엔드 클라이언트를 반환하도록 구현.
- 컬렉션 차원(dim)은 반드시 embedding.py 의 Embedder.dim 과 일치시킬 것.
- ir/vector/ingest.py(upsert), ir/vector/search.py(검색)에서 이 클라이언트를 쓴다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from qdrant_client import AsyncQdrantClient


@lru_cache
def get_vector_client() -> AsyncQdrantClient:
    """프로세스당 1회 생성되는 Qdrant 비동기 클라이언트(지연 연결).

    VECTOR_DB_URL 값으로 모드를 자동 선택한다:
      - "http://..." / "https://..."  → 원격/도커 서버 모드(운영 권장).
      - ":memory:"                    → 인메모리(테스트/임시, 비영속).
      - 그 외(경로)                    → 로컬 임베디드(파일 경로, 도커 불필요/영속).

    서버 모드는 생성만으로는 붙지 않고 실제 호출 시점에 연결한다(앱 부팅을 막지 않음).
    로컬/인메모리 모드는 단일 프로세스에서만 열 수 있다(서버 실행 중 별도 적재 X).
    """
    from qdrant_client import AsyncQdrantClient

    url = settings.VECTOR_DB_URL
    if url.startswith(("http://", "https://")):
        return AsyncQdrantClient(url=url, api_key=settings.VECTOR_DB_API_KEY)
    if url == ":memory:":
        return AsyncQdrantClient(location=":memory:")
    return AsyncQdrantClient(path=url)
