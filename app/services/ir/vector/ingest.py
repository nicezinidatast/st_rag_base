"""Vector 적재: 전처리 → 청킹 → 임베딩 → 벡터DB upsert.

[Phase 3 구현 — dense 적재]
1. utils/text.clean_text 로 전처리 후 고정 길이로 청킹(overlap 포함).
2. clients/embedding.get_embedder() 로 임베딩 (dim 이 컬렉션과 일치해야 함).
3. core/vector_db.get_vector_client() 로 컬렉션 보장 후 upsert.
   payload 에 content/source_id/metadata 를 함께 저장(검색 시 그대로 복원).
※ 무거우면 Phase 8 에서 workers/tasks.py 로 옮긴다(지금은 엔드포인트에서 직접 호출).
"""

from __future__ import annotations

import uuid

from app.clients.embedding import get_embedder
from app.core.config import settings
from app.core.vector_db import get_vector_client
from app.utils.text import clean_text

# source_id+chunk_index 로 항상 같은(uuid5) point id 를 만든다 →
# 같은 문서를 다시 적재해도 중복 없이 같은 자리에 덮어쓴다.
_ID_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100


def _chunk(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """고정 길이 슬라이딩 윈도우 청킹. (문장/시맨틱 청킹은 추후)"""
    if not text:
        return []
    step = max(1, size - overlap)
    return [text[i : i + size] for i in range(0, len(text), step)]


async def _ensure_collection(client, name: str, dim: int) -> None:
    from qdrant_client.models import Distance, VectorParams

    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


async def ingest(source_id: str, content: str, metadata: dict | None = None) -> int:
    """문서를 청킹·임베딩해 벡터DB 에 upsert. 반환: 인덱싱된 청크 수."""
    from qdrant_client.models import PointStruct

    chunks = _chunk(clean_text(content))
    if not chunks:
        return 0

    embedder = get_embedder()
    vectors = await embedder.aembed_documents(chunks)

    client = get_vector_client()
    await _ensure_collection(client, settings.VECTOR_COLLECTION, embedder.dim)

    points = [
        PointStruct(
            id=str(uuid.uuid5(_ID_NAMESPACE, f"{source_id}:{i}")),
            vector=vector,
            payload={
                "content": chunk,
                "source_id": source_id,
                "metadata": metadata or {},
            },
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
    ]
    await client.upsert(collection_name=settings.VECTOR_COLLECTION, points=points)
    return len(chunks)
