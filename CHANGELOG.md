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
