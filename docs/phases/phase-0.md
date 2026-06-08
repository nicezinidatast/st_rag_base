# Phase 0 — 그대로 부팅 (스캐폴드)

- **커밋:** `c8bbc4d` (Feat) st RAG 기본 init
- **목표:** 받자마자 서버가 뜨는지 확인하고 출발선을 잡는다. (구현은 대부분 stub)
- **검증:** `make dev` → `http://localhost:8000/docs`, `GET /api/v1/health` 200, `make test` 통과.

## 무엇이 들어왔나

전체 백엔드 스캐폴드 한 번에. 디렉터리 골격 + 동작하는 "틀" + 단계별 stub.

### 바로 동작하는 것
- **앱 부팅**: `app/main.py`(FastAPI + lifespan), `app/api/v1/router.py`(라우터 묶음)
- **엔드포인트**: `health`(200), `chat`(stream 분기), `document`(가짜 202), `auth`(틀)
- **미들웨어**: `middleware/request_context.py`(trace_id), `middleware/logging.py` + `utils/logger.py`(structlog JSON)
- **설정**: `core/config.py`(Pydantic Settings, `.env` 로딩, 프로바이더 키/기본모델 필드)
- **팩토리 틀**: `clients/chat_model.py`(provider:model 레지스트리), `clients/embedding.py`, `clients/reranker.py`
- **인터페이스**: `services/ir/base.py`(`Retriever`/`RetrievedChunk`), `schemas/*`

### 이미 "동작 상태"로 포함된 챗 코드 (중요)
init 시점에 아래가 **이미 구현돼 있었다** → 사실상 동기 챗의 뼈대는 Phase 0 스캐폴드에 포함:
- `clients/openai_client.OpenAIChatModel.achat` — Chat Completions 동기 호출 (`stream=False`)
- `utils/streaming.run_chat_sync` — `get_chat_model().achat(...)` 직접 호출로 답변 생성
- `endpoints/chat.py` — `request.stream` 으로 동기/스트리밍 분기

### stub (이후 Phase 에서 채움)
- `openai_client.astream` → `NotImplementedError` (Phase 2)
- `streaming.stream_chat` → `NotImplementedError` (Phase 2)
- `clients/embedding`, `core/vector_db`, `ir/vector/{ingest,search}` → `NotImplementedError` (Phase 3)
- `clients/anthropic_client` → `placeholder` (Phase 3)
- graph/workflow/workers 전반 (Phase 5/8/9)

## 기타
- 인프라 파일: `Dockerfile`, `docker-compose.yml`(qdrant/redis/postgres/neo4j), `Makefile`, `.github/workflows/ci.yml`(ruff/mypy/pytest), `.pre-commit-config.yaml`, `alembic.ini`
- 테스트 골격: `tests/test_api/test_health.py`, `tests/test_api/test_chat.py`(동기), `tests/test_clients/test_chat_model.py`
