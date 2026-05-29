# CHANGELOG — 페이즈별 작업 기록

> 각 Phase 에서 **무엇을 바꿨는지** 한눈에 추적하는 문서. 로드맵 자체는 `README.md` 참고.
> 형식: Phase 제목 — 목표 / 주요 변경(파일) / 커밋 / 검증.

---

## [x] Phase 0 — 그대로 부팅 (구현 0줄)

- **목표:** 받자마자 서버가 뜨는지 확인하고 출발선을 잡는다.
- **주요 변경:** 초기 스캐폴드 전체(앱 구조, 미들웨어 trace id/로그, `GET /api/v1/health`).
- **커밋:** `c8bbc4d` (Feat) st RAG 기본 init
- **검증:** `make dev` → `/docs` 확인, `make test` 통과.

## [x] Phase 1 — 가장 단순한 동기 챗 (RAG 없음)

- **목표:** LLM 한 개만 연결해 "질문 → 답변". 검색 없음.
- **주요 변경:**
  - `app/utils/streaming.py` — `run_chat_sync` 에 OpenAI 키 없음 가드 추가
    (키 미설정 시 인증 에러 대신 안내 답변을 `answer` 로 반환).
  - `tests/test_api/test_chat.py` — 동기 경로 + 키 없음 가드 테스트.
  - (참고: `OpenAIChatModel.achat`, `chat_model` 팩토리는 Phase 0 스캐폴드에 포함.)
- **커밋:** `568ded1` openAPI 키 없을 시 하드코딩 답변 반환
- **검증:** `POST /api/v1/chat` `{"stream": false}` → `answer` 필드 확인.

## [x] Phase 2 — SSE 토큰 스트리밍 추가

- **목표:** 같은 챗을 토큰 단위로 흘려보낸다. 동기 경로는 그대로(둘 다 지원).
- **주요 변경:**
  - `app/clients/openai_client.py` — `OpenAIChatModel.astream` 구현
    (OpenAI `stream=True` 응답에서 `delta.content` 있는 조각만 yield).
  - `app/utils/streaming.py` — `stream_chat` 구현 (`astream` → SSE `token`/`done`/`error`).
    키 없음 안내값을 `NO_API_KEY_MESSAGE` 상수로 통일 → 동기/스트리밍 양쪽이 동일 result.
  - `tests/test_clients/test_chat_model.py` — `astream` 토큰 yield 단위 테스트.
  - `tests/test_api/test_chat.py` — SSE 프레임(`event: token`/`done`) + 키 없음 스트리밍 테스트.
  - `tests/conftest.py` — 안 쓰던 `fake_llm` 픽스처 제거.
  - `README.md` — Phase 0/2 `[x]` 표기.
- **커밋:** `6f28409` feat(streaming): add SSE token streaming for chat (phase 2)
- **검증:** `pytest` 11 passed. `curl -N` 로 SSE 프레임 확인.

## [x] Phase 3 — Vector RAG 최소 동작 (Qdrant + dense 검색)

- **목표:** 문서를 적재하고, 검색된 컨텍스트를 프롬프트에 넣어 답한다(citations 포함).
- **주요 변경:**
  - `app/clients/embedding.py` — `SentenceTransformerEmbedder`(로컬 bge-m3, 무료/키 불필요,
    지연 로드+스레드풀 인코딩, 정규화) **기본** + `OpenAIEmbedder`(선택) 구현. `@register("st")`.
  - `app/core/vector_db.py` — `get_vector_client` (지연 연결 Qdrant `AsyncQdrantClient`, lru_cache).
  - `app/services/ir/vector/ingest.py` — 청킹(고정 800/overlap 100) → 임베딩 → 컬렉션 보장 →
    upsert(payload: content/source_id/metadata). point id 는 `uuid5(source_id:idx)` 로 멱등.
  - `app/services/ir/vector/search.py` — `VectorRetriever` dense 검색(`query_points`).
    컬렉션 없으면 `[]`.
  - `app/api/v1/endpoints/document.py` — `/documents/ingest` 가 vector ingest 직접 호출
    (인라인 content 만, 워커는 Phase 8). content 없으면 400.
  - `app/utils/streaming.py` — `_retrieve_context`/`_augment` 추가 → 동기/스트리밍 양쪽에
    "검색 → system 컨텍스트 주입 → citations" 끼움. 검색 실패는 비치명(컨텍스트 없이 진행).
- **부가(요청 1):** 챗 답변 생성 LLM 을 **Anthropic 으로 전환**.
  - `app/clients/anthropic_client.py` — `AnthropicChatModel`(achat/astream, system 분리, max_tokens).
  - `app/clients/chat_model.py` — `_build_anthropic` 연결.
  - 챗 키 가드를 `ANTHROPIC_API_KEY` 기준으로 변경(`NO_API_KEY_MESSAGE` 갱신).
- **부가(요청 2):** 기본 임베딩을 **무료 로컬 bge-m3** 로 전환, 나머지는 선택 가능.
  - `sentence-transformers`(+torch) 추가, 미사용 `fastembed` 제거 (`pyproject.toml`/`uv.lock`).
  - `app/core/config.py` — `DEFAULT_CHAT_MODEL=anthropic:claude-haiku-4-5-20251001`,
    `DEFAULT_EMBEDDING_MODEL=st:BAAI/bge-m3`.
  - `.env` / `.env.example` — 위 기본값으로 갱신(런타임은 .env 가 우선이므로 함께 수정).
- **부가(요청 3):** chat API 를 *애플리케이션* API 로 재설계 + Swagger 기본값.
  - `schemas/chat.py` — LLM 직접 호출형 `messages[]` 제거. 클라이언트는 **`question` 하나만**
    보내면 서버가 user 메시지로 변환. 운영 필드 `session_id`/`user_meta`/`model`(오버라이드) 추가.
    응답은 `{session_id, answer, citations[], rag_mode, model}`. StrEnum + Swagger example(stream=false).
  - `utils/streaming.py` — `_retrieve_context(question)` + `_build_messages(question, context)`,
    사용 모델 해석(request.model→기본값), 스트림 meta 로 `{model, citations}` 송출.
  - `endpoints/chat.py` — `session_id` 발급/유지 + 응답 `model` 포함.
  - `schemas/document.py` — `/ingest` example + StrEnum.
- **부가(요청 4):** 도커 없이 **실제 검색**까지 동작시킴(mock 졸업).
  - `app/core/vector_db.py` — `VECTOR_DB_URL` 로 모드 자동 선택: `http(s)://`(서버) /
    `:memory:`(임시) / 그 외 경로(**로컬 임베디드**, 도커 불필요·영속). `.env` 는 `./.qdrant_local`.
  - `pypdf` 추가 + `scripts/ingest_data.py` — `data/*.pdf` → 텍스트 추출 → 청킹 → bge-m3 임베딩
    → 로컬 Qdrant 적재 → 샘플 검색. stdout utf-8 강제(Windows cp949 대응).
  - `.gitignore` — `.qdrant_local/` 제외.
- **테스트:** `test_embedding.py`, `test_anthropic_client.py`, `test_ir/test_vector.py`,
  `test_api/test_document.py`, `test_api/test_chat.py` → `pytest` 30 passed (단위는 모킹).
- **실동작 검증(e2e):** `data/` PDF 6개 → **311 chunks** 적재(`.qdrant_local`).
  "모형 검증 방법론은 무엇인가?" 질의 → 관련 청크 citations 반환(score 0.68/0.62/0.62,
  출처 = CSS_모델링과정(Advanced)_2일차). **실제 검색 + 출처 동작 확인.**
- **운영 메모:** 로컬 임베디드 Qdrant 는 단일 프로세스만 점유 → 적재 스크립트 실행 시 API 서버는
  꺼둘 것. 동시 사용/운영은 도커 서버 모드(`VECTOR_DB_URL=http://localhost:6333`)로 전환.
- **커밋:** _(미커밋)_
