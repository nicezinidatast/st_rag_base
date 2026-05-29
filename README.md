# NICECHAT_BASE

> **RAG AI 챗봇의 공통 백엔드 (common backend)**
> 여러 AI 챗봇 프로젝트가 *그대로 가져다 쓰는* 하이브리드 RAG(Vector + Graph) 기반 엔진.

NICECHAT_BASE 는 "챗봇마다 RAG 백엔드를 처음부터 다시 만들지 말자"는 정신으로 만든
**재사용 가능한 토대**입니다. 프로젝트는 이 repo 를 베이스로 두고, 비즈니스 로직만
각자 채워 넣습니다. 모델·벡터DB·그래프DB·프로바이더는 **코드 수정 없이 `.env`로 교체**됩니다.

## 핵심 원칙

- **교체 가능성(Pluggable)** — LLM/임베딩/리랭커는 `clients/`의 팩토리로 `provider:model`
  문자열만 바꿔 교체. 벡터DB(Qdrant)·그래프DB(Neo4j)도 인터페이스 뒤에 숨겨 둠.
- **스트리밍 우선(Streaming-first)** — 기본 응답은 **SSE 토큰 스트리밍**. 단,
  `stream=false`로 **동기(JSON) 응답**도 항상 가능. (LangGraph `astream_events` ↔ `ainvoke`)
- **관측 가능(Observable)** — **Langfuse** LLM 트레이싱 + 구조화 JSON 로그 + 요청별 trace id.
- **현재는 "틀"** — FastAPI 부팅만 실제 동작하고, 나머지는 전부 **한글 주석 구현 가이드 +
  `NotImplementedError`** 상태. 각자 하나씩 채워 넣는 것을 전제로 함.

## 아키텍처

```
API (FastAPI / SSE)               app/api
  └─ orchestrator                 app/services/orchestrator   # 모드 라우팅 + LangGraph 지휘
       └─ workflow (LangGraph)    app/services/workflow       # analyze→retrieve→grade→generate
            └─ ir (검색 엔진)      app/services/ir
                 ├─ vector        # dense + BM25 하이브리드 + rerank
                 └─ graph         # GraphRAG: 추출→Leiden 군집→요약, local/global 검색

clients   app/clients    # ChatModel / Embedder / Reranker 팩토리 (+ openai/anthropic 래퍼)
core      app/core       # config, db, redis, vector_db, graph_db, security, observability(Langfuse)
workers   app/workers    # 무거운 적재·GraphRAG 인덱싱 (요청 경로 밖 비동기)
middleware app/middleware # trace id, 접근 로그 (양파 구조 — __init__.py 에 개념 설명)
```

> **네이밍 주의:** `services/workflow`(LangGraph 노드), `services/ir/graph`(GraphRAG),
> `core/graph_db`(Neo4j)는 모두 다른 "graph"입니다. 원안의 `services/graph/`를 충돌 방지를
> 위해 `workflow/`로 개명했습니다.

## 응답 모델: 스트리밍 vs 동기

| 구분 | 클라이언트 요청 | LangGraph 실행 | HTTP 반환 |
|------|----------------|----------------|-----------|
| **스트리밍(기본)** | `stream=true` | `graph.astream_events(...)` (토큰 단위) | `EventSourceResponse(generator)` |
| **동기** | `stream=false` | `graph.ainvoke(...)` (한 번에) | `JSONResponse(ChatResponse)` |

- `generator`(내용물) ↔ `StreamingResponse/EventSourceResponse`(포장지)의 구분은
  `app/utils/streaming.py` 상단 주석에 상세히 정리되어 있습니다.
- 토큰 스트리밍이 동작하려면 `generate` 노드의 LLM 호출이 streaming 이어야 하고,
  그래서 `ChatModel.astream()`(clients/chat_model.py)이 필수입니다.

## 빠른 시작

> 패키지 관리는 **[uv](https://docs.astral.sh/uv/)** 를 사용합니다.
> **앱은 도커가 아니라 로컬 `.venv`에서 실행**합니다. 도커는 *백킹 인프라
> (Postgres/Redis/Qdrant/Neo4j)* 를 띄우는 용도일 뿐, 앱 실행에 필수가 아닙니다.

### 1) 최소 실행 — 도커 없이 바로 (현재 Phase 0)

지금 상태(Phase 0)는 DB에 연결하지 않으므로 인프라 없이 서버가 뜹니다.

```bash
cp .env.example .env                    # API 키 채우기 (안 쓰는 건 비워둬도 됨)
uv sync                                 # .venv 생성 + 의존성 설치 (최초 실행 시 uv.lock 생성)
uv run uvicorn app.main:app --reload    # = make dev → http://localhost:8000/docs
```

Windows PowerShell 도 동일합니다 (`cp` 대신 `Copy-Item`):

```powershell
Copy-Item .env.example .env
uv sync
uv run uvicorn app.main:app --reload    # http://localhost:8000/docs
```

> 이 시점에서 `GET /api/v1/health` 가 200 으로 응답합니다.
> 채팅 등 나머지 엔드포인트는 가이드 주석을 따라 구현하면 됩니다.

### 2) 인프라가 필요해지면 (Phase 3+)

Vector/메모리/DB/그래프 단계부터 백킹 서비스가 필요합니다. **필요한 것만** 골라 올리면 됩니다.

```bash
docker compose up -d qdrant             # Phase 3: Vector RAG
docker compose up -d redis              # Phase 6: 메모리/캐시
docker compose up -d postgres           # Phase 7: 인증/영속화
uv run alembic upgrade head             # = make migrate (Postgres 올린 뒤)
docker compose up -d neo4j              # Phase 9: GraphRAG
# 전부 한 번에: docker compose up -d postgres redis qdrant neo4j
```

> 도커가 싫으면 각 DB 를 로컬에 직접 설치해도 됩니다. `.env` 의 접속 주소만 맞추면 코드 수정 없이 동작합니다.

### uv 사용 메모

- `uv sync` 가 가상환경(`.venv`)과 잠금파일(`uv.lock`)을 만든다. **`uv.lock` 은 커밋**해서
  팀/CI/Docker가 동일 버전을 재현하도록 한다.
- 의존성을 바꾼 뒤(`pyproject.toml` 수정)에는 `uv lock` 으로 잠금파일을 갱신한다.
- 단발 명령은 `uv run <cmd>`, 패키지 추가는 `uv add <pkg>` (개발용은 `uv add --dev <pkg>`).

## 자주 쓰는 명령어

| 명령 | 용도 |
|------|------|
| `make dev`  | 오토리로드로 API 실행 |
| `make test` | pytest |
| `make lint` | Ruff 린트 |
| `make type` | mypy 타입 체크 |
| `make up` / `make down` | 로컬 인프라 스택 |

## 단계별 구현 로드맵 (Incremental Roadmap)

> **이 로드맵의 철학 — "항상 동작하는 상태를 유지하며 한 단계씩 쌓는다."**
>
> 이 백엔드는 한 번에 다 구현하는 게 아닙니다. **각 단계(Phase)가 끝나면 그 자체로
> 실행되고 검증 가능한 완결된 기능**이 됩니다. 다음 단계는 그 위에 *기능만 더하는*
> 방식이라, 중간에 멈춰도 "지금까지 만든 만큼은 정상 동작"합니다.
>
> 규칙 3가지:
> 1. **한 번에 한 Phase만.** 다음으로 넘어가기 전, 현재 Phase의 "검증"을 반드시 통과시킨다.
> 2. **항상 초록불 유지.** 각 Phase 끝에서 서버가 뜨고 `pytest`가 통과해야 한다.
> 3. **각 파일 상단의 `[구현 가이드]` 주석을 따른다.** "여기서 뭘 해야 하는지"가 적혀 있다.

> 표기: 🎯 목표 · 🛠 작업 파일 · ✅ 완료 시 동작하는 것(working state) · 🔍 검증

---

### [x] Phase 0 — 그대로 부팅 (현재 상태, 구현 0줄)
- 🎯 받자마자 서버가 뜨는지 확인하고 출발선을 잡는다.
- 🛠 (없음 — 그대로)
- ✅ `GET /api/v1/health` 가 200. 미들웨어(trace id/로그)가 이미 동작.
- 🔍 `make dev` → `http://localhost:8000/docs` 확인, `make test` 통과.

### [x] Phase 1 — 가장 단순한 동기 챗 (RAG 없음)
- 🎯 LLM 한 개만 연결해 "질문 → 답변"이 되게 한다. *검색은 아직 없다.*
- 🛠 `clients/openai_client.py`(ChatModel 구현) → `clients/chat_model.py` 빌더 연결
  → `utils/streaming.run_chat_sync`(graph 없이 chat_model 직접 호출로 임시 구현)
- ✅ `POST /api/v1/chat` 에 `{"stream": false}` 로 호출 → 동기 JSON 답변.
- 🔍 curl 로 `stream=false` 요청 → `answer` 필드 확인. **이 시점에서 이미 "동작하는 챗봇".**

### [x] Phase 2 — SSE 토큰 스트리밍 추가
- 🎯 같은 챗을 토큰 단위로 흘려보낸다. (동기 경로는 그대로 둔다 — 둘 다 지원)
- 🛠 `clients/openai_client.ChatModel.astream` 구현 → `utils/streaming.stream_chat`(generator)
- ✅ `{"stream": true}` → SSE 로 토큰이 한 조각씩. Phase 1 의 동기 경로도 여전히 동작.
- 🔍 `curl -N` 로 SSE 프레임이 끊겨 들어오는지 확인.
  > `generator` vs `EventSourceResponse` 구분이 헷갈리면 `utils/streaming.py` 상단 주석 참고.

### [x] Phase 3 — Vector RAG 최소 동작 (Qdrant + dense 검색)
- 🎯 문서를 적재하고, 검색된 컨텍스트를 프롬프트에 넣어 답한다. **여기서부터 진짜 RAG.**
- 🛠 `clients/embedding.py`(openai Embedder) → `core/vector_db.py`(Qdrant 연결)
  → `ir/vector/ingest.py`(청킹+임베딩+upsert) → `ir/vector/search.py`(dense만)
  → `endpoints/document.py` 에서 ingest 직접 호출(임시, 워커는 Phase 8)
  → `stream_chat`/`run_chat_sync` 에 "검색 → 컨텍스트 주입" 끼우기
- ✅ `POST /documents/ingest` 로 문서 적재 후, 그 내용을 근거로 답변(citations 포함).
- 🔍 적재한 문서에만 있는 사실을 물어보고 정답+출처가 나오는지 확인.

### Phase 4 — 하이브리드 검색(BM25) + 리랭커
- 🎯 검색 품질을 끌어올린다. (dense 단독 → dense+BM25 융합 → rerank)
- 🛠 `utils/text.tokenize_ko`(형태소 분석) → `ir/vector/search.py`(BM25 추가 + RRF 융합)
  → `clients/reranker.py`(cohere) → `ir/vector/rerank.py`
- ✅ Phase 3 와 동일 API, **검색 정확도만 향상**. 기능 추가지 동작 변화 없음.
- 🔍 동일 질문에서 더 관련도 높은 청크가 상위로 오는지(점수/순서) 비교.

### Phase 5 — LangGraph 워크플로로 구조화
- 🎯 그동안 함수로 엮던 흐름을 상태머신으로 정식화한다. (analyze→retrieve→grade→generate)
- 🛠 `workflow/state.py` → `workflow/nodes/*` 채우기 → `orchestrator/rag_agent.build_graph`
  → `utils/streaming` 을 graph 의 `ainvoke`/`astream_events` 호출로 교체
- ✅ 외부 동작은 Phase 4 와 같되, 내부가 노드 그래프로 정리됨. grade 노드로 품질 게이트 추가 가능.
- 🔍 기존 테스트 그대로 통과 + 각 노드 단위 테스트(`tests/test_graph/`) 추가.

### Phase 6 — 대화 메모리 + 시맨틱 캐시 (Redis)
- 🎯 멀티턴 맥락 유지 + 동일/유사 질문 캐싱으로 비용 절감.
- 🛠 `core/redis.py` 연결 → `services/memory.py`(이력) → `services/cache.py`(시맨틱 캐시)
  → generate 노드에 이전 맥락 주입, 진입부에 캐시 조회
- ✅ 이어지는 질문이 맥락을 기억. 반복 질문은 캐시 히트.
- 🔍 멀티턴 대화 + 같은 질문 2회 호출 시 두 번째가 빠른지 확인.

### Phase 7 — 인증/RBAC + 영속화 (Postgres + Alembic)
- 🎯 사용자/대화/메시지를 DB에 남기고 접근을 보호한다.
- 🛠 `core/security.py`(JWT/해싱) → `api/deps.get_current_user` → `models/*` 마이그레이션
  (`migration/env.py` 에 `Base.metadata` 연결 후 `make migrate`) → 엔드포인트에 `Depends` 부착
- ✅ 토큰 없이는 차단, 대화/메시지가 DB에 저장됨.
- 🔍 `make migrate` 성공 + 토큰 유무에 따른 401/200 + 메시지 row 적재 확인.

### Phase 8 — 무거운 적재를 워커로 분리 (ARQ/Celery)
- 🎯 대형문서 적재가 요청을 막지 않게 한다.
- 🛠 `workers/tasks.ingest_document` 구현 → `endpoints/document.py` 를 "enqueue 후 202" 로 변경
- ✅ 적재 API 가 즉시 202 반환, 실제 인덱싱은 백그라운드. 검색 기능은 그대로.
- 🔍 큰 문서 적재 시 API 응답이 즉시 오고, 잠시 후 검색에 반영되는지 확인.

### Phase 9 — GraphRAG 파이프라인 추가
- 🎯 엔티티/관계 그래프 기반 검색을 더한다. (Vector RAG 는 그대로 둔 채 *옆에* 추가)
- 🛠 `core/graph_db.py`(Neo4j) → `ir/graph/ingest/{extractor,cluster,summarizer}`
  (Phase 8 워커에서 실행) → `ir/graph/search/{local,global_}` → `config/prompts/graphrag/*`
- ✅ `rag_mode="graph_local"`/`"graph_global"` 로 호출하면 그래프 기반 답변. vector 모드도 그대로.
- 🔍 관계형 질문(local) / 광범위 요지 질문(global) 각각 테스트.

### Phase 10 — 자동 라우팅 + 하이브리드 모드
- 🎯 `rag_mode="auto"` 에서 시스템이 알아서 엔진을 고르고, 필요 시 융합한다.
- 🛠 `orchestrator/routing.route` → `rag_agent` 의 conditional edge 분기 → `hybrid` 융합 로직
- ✅ 사용자가 모드를 안 정해도 질문 성격에 맞는 엔진이 선택됨.
- 🔍 여러 유형 질문을 `auto` 로 던져 적절한 엔진이 선택되는지(로그/trace) 확인.

### Phase 11 — 관측성: Langfuse 실연동
- 🎯 검색→프롬프트→토큰→비용을 한 trace 로 묶어 품질을 추적한다.
- 🛠 `core/observability.py` 의 `init/get_langgraph_callback/shutdown` 실구현
  → `rag_agent` 실행 config 에 콜백 주입 → `.env` 에 `LANGFUSE_ENABLED=true`
- ✅ 모든 요청이 Langfuse 대시보드에 trace 로 남음(요청 미들웨어 trace_id 와 연계).
- 🔍 한 요청 후 Langfuse 에 span 트리(retrieve/generate 등)가 보이는지 확인.

### Phase 12 — 프로덕션 하드닝
- 🎯 운영에 안전한 형태로 마감.
- 🛠 `core/exceptions.py` 핸들러 등록(+SSE 는 `EVENT_ERROR` 로 전달) →
  `endpoints/health.ready` 에 실제 의존성 핑 → rate limit 미들웨어 추가 →
  `Dockerfile`/`docker-compose`/CI 점검 → 부하·보안 테스트
- ✅ 장애 시 일관된 에러 응답, readiness 정확, 배포 파이프라인 가동.
- 🔍 의존성 하나 내렸을 때 `/ready` 가 503, 전역 예외가 일관 포맷으로 나오는지 확인.

---

#### 의존 관계 한눈에

```
P0 부팅
 └ P1 동기챗 ── P2 스트리밍            (LLM 계층 완성)
        └ P3 VectorRAG ── P4 하이브리드+리랭크   (검색 품질)
               └ P5 LangGraph ── P6 메모리/캐시
                      └ P7 인증/DB ── P8 워커
                             └ P9 GraphRAG ── P10 라우팅/하이브리드
                                    └ P11 Langfuse ── P12 하드닝
```

- **최소 동작 데모**까지: P0→P3 (단순 Vector RAG 챗봇)
- **실서비스 기본기**까지: ~P8 (품질·메모리·인증·확장성)
- **풀 기능**: ~P12 (GraphRAG·자동라우팅·관측성·운영)
