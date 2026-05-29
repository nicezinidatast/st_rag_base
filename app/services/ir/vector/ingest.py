"""Vector 적재: 파싱 → 청킹 → 임베딩 → 벡터DB upsert.

[구현 가이드]
1. utils/text.clean_text 로 전처리, 청킹(고정/문장/시맨틱) 전략 결정.
2. clients/embedding.get_embedder() 로 임베딩 (dim 이 컬렉션과 일치해야 함).
3. core/vector_db.get_vector_client() 로 upsert. metadata(source_id 등) 함께 저장.
※ 무거우면 workers/tasks.py 에서 호출.
"""
from __future__ import annotations


async def ingest(source_id: str, content: str, metadata: dict | None = None) -> int:
    # 반환: 인덱싱된 청크 수
    raise NotImplementedError("vector ingest 미구현")
