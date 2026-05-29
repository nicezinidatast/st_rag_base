"""[백그라운드 워커] 무거운 작업(대형문서 임베딩, GraphRAG 인덱싱)을 요청 경로 밖에서 실행.
ARQ/Celery 등으로 큐잉. document 엔드포인트는 여기로 작업을 enqueue 만 한다."""
