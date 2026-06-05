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
- **부가(요청 5):** **MockRetriever** 추가 — Qdrant/임베딩 인프라 없이 RAG 흐름을 점검.
  - `app/services/ir/mock.py` — `Retriever` 구현. 쿼리와 무관하게 포켓몬 가상 문서 5건
    (피카츄·리자몽·꼬부기·뮤츠·이상해씨)을 `RetrievedChunk` 로 고정 반환.
  - `app/core/config.py` — `MOCK_RETRIEVER: bool = False` 토글.
  - `app/utils/streaming.py` → (Phase 5 에서 `retrieve` 노드로 이동) `MOCK_RETRIEVER` true 면
    `MockRetriever`, 아니면 `VectorRetriever` 선택.
  - `.env` — `MOCK_RETRIEVER=false` 기본.
- **테스트(갱신):** `pytest` 30 passed (커버리지 옵션 제외 시).
- **커밋:** `ce14e28` feat(clients): pass HF_TOKEN / `7cfc9b2` feat(ir): MockRetriever
  / `9cf9784` feat(ir/vector): Phase 4 hybrid 스텁

## [x] Phase 4 — 하이브리드 검색(BM25) + 리랭커 *(스켈레톤만)*

- **결정:** 하이브리드/rerank 는 정확도 최적화 단계라 MVP 에는 본체 구현을 미룬다.
  **함수 슬롯(스텁)만** 만들어 Phase 5 가 인터페이스를 참조할 수 있게 자리만 잡았다.
- **주요 변경:** `app/services/ir/vector/search.py` — `reciprocal_rank_fusion`(RRF 융합),
  `HybridRetriever`(dense+BM25→RRF→rerank) `NotImplementedError` 스텁 추가.
  (기존 스텁: `rerank.py`, `clients/reranker.py` 팩토리, `utils/text.tokenize_ko` placeholder.)
- **커밋:** `9cf9784` feat(ir/vector): scaffold Phase 4 hybrid search stubs

## [x] Phase 5 — LangGraph 워크플로로 구조화

- **목표:** 함수로 엮던 흐름을 상태머신으로 정식화. **외부 동작은 Phase 3/4 와 동일**, 내부만 그래프.
  `analyze → retrieve → grade → generate` (선형).
- **주요 변경:**
  - `app/services/workflow/nodes/*` — 4개 노드 구현(`NotImplementedError` 졸업).
    analyze(경량 정규화) / retrieve(Phase 3 검색 로직 이식) / grade(검색 최고점, LLM 無) /
    generate(`astream`+`get_stream_writer` 토큰 송출 & 누적).
  - `app/services/orchestrator/rag_agent.py` — `build_graph()`(`StateGraph` 구성+compile, lru_cache).
  - `app/utils/streaming.py` — 로직 제거 후 **얇은 어댑터**로. sync=`ainvoke`,
    stream=`astream(stream_mode=["updates","custom"])` (retrieve→meta, generate→token).
  - `app/services/workflow/state.py` — `top_k`/`model`/`context` 필드 추가.
  - `workflow/nodes/__init__.py` — 노드 re-export.
- **스트리밍 메모:** 커스텀 `ChatModel` 은 LangChain Runnable 이 아니라 `astream_events` 로 토큰이
  안 잡힌다 → `get_stream_writer()`(custom 스트림) 사용. `ainvoke` 일 땐 writer 가 no-op 이라
  generate 한 벌로 동기/스트리밍 양쪽 커버.
- **테스트:** `tests/test_graph/test_workflow.py` 신설(노드 단위 + 그래프 e2e).
- **커밋:** `c456461` feat(workflow) / `a57e101` docs(phases)

## [x] Phase 6 — 대화 메모리 + 응답 캐시 (Redis)

- **목표:** 멀티턴 맥락 유지(이전 대화 generate 주입) + 반복 질문 캐싱으로 LLM 절감.
- **주요 변경:**
  - `services/memory.py` — Redis 리스트 세션 이력(`append_message`/`get_history`, LTRIM+TTL).
  - `services/cache.py` — 정규화 질문 **완전일치** 캐시(시맨틱은 후속). 히트 시 LLM 스킵.
  - `workflow/state.py`·`nodes/generate.py` — `history` 추가, `_build_messages` 가 이전 턴 주입.
  - `utils/streaming.py` — 진입 시 캐시 조회 → 이력 로드/주입 → 응답 후 적재+캐시.
    `endpoints/chat.py` — `session_id` 1회 확정.
  - `core/redis.py`·`main.py` — 빠른 타임아웃 + 가용성 플래그(lifespan ping). **Redis 미기동에도
    채팅 정상·빠름**(요청당 즉시 스킵, 20s→0.35s).
  - `config.py`/`.env.example` — `MEMORY_ENABLED`/`HISTORY_*`/`CACHE_*`.
- **테스트:** `fakeredis`(dev) + conftest autouse 픽스처. `test_services/test_{memory,cache}.py`,
  `test_chat.py`(캐시 히트·이력 주입). `pytest` 45 passed.
- **커밋:** _(미커밋)_

## [x] Phase 5+ — 채팅 모델 LangChain `BaseChatModel` 전환 + 정리

- **목표:** 자체 `ChatModel` Protocol/래퍼 → LangChain 통합 모델. LangGraph `astream_events(v2)`
  로 토큰 자동 포착(스트리밍 배관 제거) + 콜백 트레이싱(Phase 11) 기반 마련.
- **주요 변경:**
  - 의존성 추가: `langchain-anthropic`, `langchain-openai` (`pyproject.toml`/`uv.lock`).
  - `clients/chat_model.py` — 빌더 레지스트리 유지, 반환을 `BaseChatModel`(`ChatAnthropic`/`ChatOpenAI`)로.
    키는 settings 에서 명시 주입.
  - **삭제:** `clients/openai_client.py`, `clients/anthropic_client.py`(통합 모델이 대체),
    `services/orchestrator/base.py`(`BaseOrchestrator` 미사용 — 오케스트레이션은 graph 담당).
  - `workflow/nodes/generate.py` — `get_stream_writer`+`astream` → `ainvoke` 한 줄.
  - `utils/streaming.py` — `astream(stream_mode=custom)` → `astream_events(v2)`
    (`on_chat_model_stream`→token, `on_chain_end`(retrieve)→meta citations).
  - 테스트: `test_anthropic_client.py` 삭제, `test_chat_model.py` 재작성(생성 검증),
    fake 는 `GenericFakeChatModel` 통일.
- **트레이드오프:** SDK 직접 종속 → `langchain-*` 버전 종속으로 이동.
- **테스트:** `pytest` 34 passed. ruff/mypy 통과. 서버 부팅 + 실제 모델 빌드 확인.
- **커밋:** _(미커밋)_
