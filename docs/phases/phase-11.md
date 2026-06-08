# Phase 11 — 관측성: Langfuse 실연동

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** 검색→프롬프트→토큰→비용을 한 trace 로 묶어 품질을 추적한다.
- **검증:** `pytest` 59 passed (신규 3). Langfuse Cloud E2E: 채팅 1회 →
  trace 적재(`LangGraph` > analyze/retrieve/grade/generate span + LLM GENERATION,
  tokens 33/96, cost $0.000513) + `X-Request-ID` == Langfuse trace id 일치 확인.

> **진행 순서 변경:** Phase 7 다음을 8 이 아니라 11 로 진행 (README 로드맵 참고).
> 11 은 독립적이고, 이후 9(GraphRAG)/10(라우팅) 디버깅 때 trace 가 있으면 이득.

---

## A. Langfuse 클라이언트 (`core/observability.py`)

placeholder → 실구현. **langfuse v3+(OTel 기반) API** 사용 — 파일에 있던 v2 가이드
(`langfuse.callback.CallbackHandler`)는 v4.7 에서 동작하지 않아 폐기.
- `init_langfuse()`: `Langfuse(public_key, secret_key, base_url, environment=ENV)`.
  `LANGFUSE_ENABLED=false` 거나 키 없으면 no-op(운영 안전) — 기존 가드 유지.
- `get_langgraph_callback()`: `langfuse.langchain.CallbackHandler` 반환.
  **미들웨어 trace_id(uuid4().hex)가 W3C trace id 형식(32 hex)과 동일**하므로
  `trace_context={"trace_id": ...}` 로 그대로 사용 → `X-Request-ID` ↔ Langfuse trace 1:1.
  (클라이언트가 임의 형식 X-Request-ID 를 보내면 Langfuse 자체 발급으로 폴백.)
- `build_graph_config(session_id, user_id)`: graph 실행 config 생성.
  metadata 의 `langfuse_session_id`/`langfuse_user_id` 를 CallbackHandler 가 trace
  속성으로 승격 → 대시보드에서 세션/사용자 단위 묶음.
- `shutdown_langfuse()`: `flush()` (main.py shutdown 에서 호출, 연결은 기존 그대로).

## B. 그래프 실행에 주입 (`utils/streaming.py`)

`stream_chat`/`run_chat_sync` 양쪽에서 `config = build_graph_config(session_id, user_id)`
→ `graph.astream_events(..., config=config)` / `graph.ainvoke(state, config=config)`.
트레이싱이 꺼져 있으면 `{}` 라 동작 변화 없음.

## C. 의존성 / 테스트

- `langchain` 추가 — `langfuse.langchain` 통합이 langchain 본체를 요구
  (langchain-core 만으로는 ImportError). langgraph 1.2.4 로 함께 patch bump.
- `tests/test_core/test_observability.py`(3): disabled no-op / 키 누락 가드 /
  활성화 시 클라이언트 생성 + callbacks/metadata config 검증(가짜 Langfuse 주입).
- `tests/conftest.py` 에 `auth_disabled_by_default` autouse 픽스처 추가:
  개발자 `.env` 의 `AUTH_ENABLED=true` 가 테스트를 깨지 않도록 항상 off 에서 시작
  (인증 테스트는 각자 monkeypatch 로 켬). **테스트가 .env 상태에 의존하던 갭 수정.**

## 확인 방법

```
.env: LANGFUSE_ENABLED=true + pk/sk 키 → make dev → 채팅 1회
→ https://cloud.langfuse.com 프로젝트 Traces 에서:
   · trace 1건 (이름 LangGraph, 응답 헤더 X-Request-ID 와 같은 id)
   · span 트리: analyze → retrieve → grade → generate → ChatAnthropic(GENERATION)
   · 토큰 수/비용/지연 자동 집계, Sessions 탭에 session_id 별 묶음
```
