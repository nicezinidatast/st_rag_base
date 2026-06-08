# Phase 3 — Vector RAG (검색→출처) + Anthropic 챗 + 로컬 bge-m3

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** 문서를 적재하고, 검색된 컨텍스트를 프롬프트에 넣어 답한다(citations 포함). **여기서부터 진짜 RAG.**
- **실동작 검증(e2e):** `data/` PDF 6개 → 311 chunks 적재(`.qdrant_local`).
  "모형 검증 방법론은 무엇인가?" → 관련 청크 citations 반환(score 0.68/0.62/0.62). `pytest` 30 passed.

Phase 2 는 *LLM 한 개에 질문 전달*까지였다. Phase 3 는 그 앞단에 **임베딩→적재→검색→
컨텍스트 주입→출처** 전체 RAG 파이프라인을 붙이고, 챗 LLM 을 Anthropic·임베딩을 로컬
bge-m3 로 바꾼 뒤 도커 없이 실제로 검색이 되게 했다.

---

## A. 검색 파이프라인 — Phase 2엔 없던 4개 파일 구현

전부 Phase 0~2 까지 `NotImplementedError` 껍데기였다.

### `app/clients/embedding.py` — 텍스트 → 벡터
- `OpenAIEmbedder`(선택) + `SentenceTransformerEmbedder`(**기본**, 로컬 bge-m3) 구현
- 인터페이스: `aembed_documents`(적재 다건) / `aembed_query`(검색 단건) / `dim`(bge-m3=1024)
- bge-m3 는 무겁기에 **지연 로드** + 인코딩은 `anyio.to_thread` 로 이벤트 루프 비차단 + 정규화

### `app/core/vector_db.py` — Qdrant 클라이언트
```python
@lru_cache
def get_vector_client():
    url = settings.VECTOR_DB_URL
    if url.startswith(("http://","https://")): return AsyncQdrantClient(url=url, api_key=...)  # 서버
    if url == ":memory:":                       return AsyncQdrantClient(location=":memory:")  # 임시
    return AsyncQdrantClient(path=url)                                                          # 로컬 임베디드
```
도커 유무에 따라 `VECTOR_DB_URL` 만 바꾸면 됨.

### `app/services/ir/vector/ingest.py` — 적재
`clean_text` → 고정길이 청킹(800/overlap 100) → `aembed_documents` → 컬렉션 보장(dim/COSINE)
→ `upsert`. point id 는 `uuid5(source_id:idx)` 라 **같은 문서를 다시 적재해도 중복 없이 덮어쓰기**. payload: content/source_id/metadata.

### `app/services/ir/vector/search.py` — 검색
`VectorRetriever.retrieve(query, top_k)`: `aembed_query` → `query_points` → `RetrievedChunk[]`.
컬렉션 없으면 `[]`(적재 전이면 검색 건너뜀).

---

## B. `app/utils/streaming.py` — 챗에 검색을 끼움 (Phase 2 직계 진화)

**Phase 2:** `citations` 항상 `[]`. **Phase 3:** 헬퍼 2개 신설 후 양쪽 경로에 주입.
```python
async def _retrieve_context(question, top_k):     # 질문으로 검색 → (context, citations)
    try:
        chunks = await VectorRetriever().retrieve(question, top_k)
    except Exception:                              # 검색 인프라 죽어도 챗은 막지 않음
        return "", []
    context = "\n\n".join(f"[{i+1}] {c.content}" ...)
    citations = [{"source_id":.., "snippet":c.content[:200], "score":c.score} for c in chunks]
    return context, citations

def _build_messages(question, context):           # question 을 user 메시지로 변환
    msgs = []
    if context: msgs.append({"role":"system","content": f"...컨텍스트...\n\n{context}"})
    msgs.append({"role":"user","content": question})
    return msgs
```
- `run_chat_sync`: `citations` 를 실제로 채워 반환. `model`(사용 모델) 도 함께 반환.
- `stream_chat`: 시작 시 `meta` 이벤트로 `{model, citations}` 송출 후 토큰 스트리밍.

---

## C. 챗 LLM: OpenAI → Anthropic 전환

- `app/clients/anthropic_client.py`: `placeholder` → `AnthropicChatModel`(achat/astream).
  Anthropic 특수처리: **system 메시지를 별도 `system=` 인자로 분리**(`_split_system`), `max_tokens` 필수.
- `app/clients/chat_model.py`: `_build_anthropic` 를 실제 래퍼 반환으로 연결 + import 정리.
- **가드 변경**(streaming.py): `OPENAI_API_KEY` → `ANTHROPIC_API_KEY`,
  `NO_API_KEY_MESSAGE = "Anthropic API key 가 없습니다."`

---

## D. 기본 임베딩: 무료 로컬 bge-m3

`app/core/config.py`:
```diff
- DEFAULT_CHAT_MODEL = "openai:gpt-4o-mini"
+ DEFAULT_CHAT_MODEL = "anthropic:claude-haiku-4-5-20251001"
- DEFAULT_EMBEDDING_MODEL = "openai:text-embedding-3-small"
+ DEFAULT_EMBEDDING_MODEL = "st:BAAI/bge-m3"     # 로컬, 키 불필요
```
런타임은 `.env` 가 우선이라 `.env`/`.env.example` 도 동일하게 갱신.

---

## E. API 스키마 재설계 (`app/schemas/chat.py`)

**Phase 2:** LLM 직접 호출형 `messages: [{role, content}]` 배열.
**Phase 3:** 애플리케이션형 — 클라이언트는 질문 하나만.
- 요청: `question`(필수, 서버가 user 메시지로 변환) + `session_id` + `user_meta` + `model`(오버라이드)
- 응답: `session_id` + `model`(사용 모델 에코) 추가
- `(str, Enum)` → `StrEnum`, Swagger 에서 바로 Execute 되는 example 내장
- `endpoints/chat.py`: `conversation_id` → `session_id` 발급/유지 + 응답 `model` 포함

---

## F. 적재 엔드포인트 (`app/api/v1/endpoints/document.py`)

`return {"status":"queued"}`(가짜) → `IngestTarget.VECTOR` 면 **실제 `vector_ingest()` 직접 호출**,
`content` 없으면 400. (워커 분리는 Phase 8)

---

## G. 도커 없이 실동작 (mock 졸업)

- `vector_db.py` 로컬 임베디드 모드(`./.qdrant_local`) → 도커 불필요·영속
- **`scripts/ingest_data.py`**(신규): `data/*.pdf` → pypdf 텍스트 추출 → 청킹 → bge-m3 → 적재 → 샘플 검색.
  Windows 콘솔 대응 위해 stdout utf-8 강제.
- 의존성: `sentence-transformers`(+torch), `pypdf` 추가 / 미사용 `fastembed` 제거 (`pyproject.toml`, `uv.lock`)
- `.gitignore`: `.qdrant_local/` 제외

### 운영 메모
로컬 임베디드 Qdrant 는 **단일 프로세스만 점유**. 적재 스크립트 실행 시 API 서버는 꺼둘 것.
동시 사용/운영은 도커 서버 모드(`VECTOR_DB_URL=http://localhost:6333`)로 전환.

---

## H. 테스트 (신규 4 + 갱신)
- 신규: `test_clients/test_embedding.py`, `test_clients/test_anthropic_client.py`,
  `test_ir/test_vector.py`, `test_api/test_document.py`
- 갱신: `test_api/test_chat.py` (messages→question, 가드 ANTHROPIC, citations/session_id/model 검증)
- 단위 테스트는 모델/Qdrant 를 모킹. 실제 검색은 `scripts/ingest_data.py` 로 e2e 확인.
