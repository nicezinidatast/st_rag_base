# Phase 5 — LangGraph 워크플로로 구조화

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** 그동안 함수로 엮던 흐름(검색→컨텍스트→생성)을 **상태머신(LangGraph)** 으로 정식화한다.
  **외부 동작은 Phase 3/4 와 동일** — 응답/SSE 포맷 그대로, 내부만 노드 그래프로 정리.
- **검증:** `pytest` 36 passed (기존 30 + 그래프 6). 서버 부팅 OK, `/api/v1/chat` 라우트 + 4개 노드 확인.

Phase 3/4 는 `streaming.py` 안의 `_retrieve_context` / `_build_messages` + ChatModel 직접 호출이
실질 파이프라인이었다. Phase 5 는 이 로직을 노드로 옮기고 그래프로 엮어, 이후 품질 게이트·
자동 라우팅·Langfuse 트레이싱을 끼울 자리를 만든다.

```
analyze ─▶ retrieve ─▶ grade ─▶ generate     (선형, START→…→END)
```

---

## A. 노드 4개 구현 (`app/services/workflow/nodes/*`)

전부 `NotImplementedError` 껍데기였다 → 각자 AgentState 일부를 갱신해 반환하는 async 함수로.

### `analyze.py` — 경량 정규화
동작을 바꾸지 않는다. `query` 만 strip, `rag_mode` 는 요청값 통과. LLM 의도분류/엔티티 추출과
`AUTO` 라우팅은 Phase 10(routing.py)로 미룸.

### `retrieve.py` — 검색 (Phase 3 `_retrieve_context` 이식)
`settings.MOCK_RETRIEVER` 면 `MockRetriever`, 아니면 `VectorRetriever`. 결과로
`documents`(원청크) / `context`(LLM 입력 문자열) / `citations`(응답 출처)를 채운다.
검색 실패·빈 결과는 비치명 → 빈 값 반환(컨텍스트 없이 진행).

### `grade.py` — 신뢰도 점수 (추가 LLM 호출 없음)
`documents` 의 **최고 검색 점수**를 `grade` 로 둔다(없으면 0.0). 지연/동작 변화 없는 관측용 값.
LLM 관련성 채점 + 저점수 시 재검색 분기(conditional edge)는 추후 품질 게이트로.

### `generate.py` — 답변 생성 (Phase 3 `_build_messages` + LLM 이식)
`await get_chat_model(spec).ainvoke(messages)` → `resp.content` 를 `answer` 로 반환.
system 프롬프트(컨텍스트 근거 강제)는 Phase 3 그대로 보존.

> **스트리밍 핵심:** 토큰 스트리밍은 generate 가 신경 쓰지 않는다. streaming.py 가
> `astream_events(v2)` 로 그래프를 돌리면 **LangChain 챗 모델 호출이 `on_chat_model_stream`
> 이벤트로 토큰을 자동으로 흘린다**(노드가 `ainvoke` 든 `astream` 이든 무관).
> ※ 초기 구현은 커스텀 `ChatModel`+`get_stream_writer`(custom 스트림)였으나, 같은 세션에서
> 모델 레이어를 LangChain `BaseChatModel` 로 전환하며 위 방식으로 단순화했다(아래 F 참고).

---

## B. 그래프 빌드 (`app/services/orchestrator/rag_agent.py`)

`NotImplementedError` → `build_graph()`:
```python
@lru_cache(maxsize=1)            # 컴파일 그래프는 무상태 → 프로세스당 1회
def build_graph():
    g = StateGraph(AgentState)
    for name, fn in [("analyze",analyze),("retrieve",retrieve),("grade",grade),("generate",generate)]:
        g.add_node(name, fn)
    g.add_edge(START,"analyze"); g.add_edge("analyze","retrieve")
    g.add_edge("retrieve","grade"); g.add_edge("grade","generate"); g.add_edge("generate",END)
    return g.compile()
```
노드는 실행 시점에 `get_chat_model`/`VectorRetriever` 를 해석하므로 캐시해도 테스트 패치가 먹는다.

---

## C. `streaming.py` — 두꺼운 로직 → 얇은 그래프 어댑터

`_retrieve_context`/`_build_messages` 제거(노드로 이동). 키 없음 개발 가드는 그대로 유지.

- **`run_chat_sync`**: `await build_graph().ainvoke(state)` → 최종 state 에서 `answer/citations/model`.
- **`stream_chat`**: `graph.astream_events(state, version="v2")` *(F 전환 후)*
  - `on_chain_end`(name=`retrieve`) → 그 출력의 `citations` 를 **EVENT_META 로 먼저** 송출.
  - `on_chat_model_stream` → generate 의 LLM 토큰을 **EVENT_TOKEN** 으로 중계. 끝에 `[DONE]`.

`AgentState` 에 `top_k` / `model` / `context` 필드 추가.

---

## D. 상태/패키지

- `workflow/state.py`: `top_k`, `model`, `context` 추가.
- `workflow/nodes/__init__.py`: 4개 노드 re-export(`build_graph` 가 한 곳에서 import).

---

## E. 테스트 (`tests/test_graph/test_workflow.py`)

placeholder 제거 후 신설:
- **노드 단위**: retrieve(컨텍스트/citations 채움 · 빈 결과 · 공백 쿼리 스킵), grade(최고점/0.0).
- **그래프 e2e**: `ainvoke` 동기(answer/citations/grade), `astream_events`(토큰 누적 + meta citations).
- 노드 단위: retrieve/grade/generate 직접 호출 검증.
- 기존 `test_api/test_chat.py`(동기/스트리밍/가드)는 외부 동작 불변. (F 전환으로 fake 만 LangChain
  모델로 교체, 단언은 동일 — `GenericFakeChatModel`.)

---

## F. (후속) 채팅 모델 → LangChain `BaseChatModel` 전환

같은 세션에서 자체 `ChatModel` Protocol/래퍼를 **LangChain 통합 모델**로 갈아끼웠다. 이유: LangGraph
`astream_events(v2)` 가 토큰을 자동 포착(스트리밍 배관 제거) + 콜백 트레이싱(Phase 11) + 생태계 기능.

- 의존성: `langchain-anthropic`, `langchain-openai` 추가(`pyproject`/`uv.lock`).
- `clients/chat_model.py`: 빌더 레지스트리 유지하되 반환을 `BaseChatModel` 로
  (`ChatAnthropic`/`ChatOpenAI`). 키는 settings 에서 골라 명시 주입(.env 는 환경변수가 아니므로).
- `clients/openai_client.py`, `anthropic_client.py` **삭제**(통합 모델이 대체).
- `generate.py`: `get_stream_writer`+`astream` 루프 → `ainvoke` 한 줄.
- `streaming.py`: `astream(stream_mode=custom)` → `astream_events(v2)`.
- `orchestrator/base.py`(`BaseOrchestrator` ABC) **삭제** — 아무도 안 씀(오케스트레이션은 graph 가 함).
- 테스트: `test_anthropic_client.py` 삭제, `test_chat_model.py` 재작성(생성만 검증),
  fake 는 `GenericFakeChatModel` 로 통일.
- **트레이드오프:** SDK 직접 종속 → `langchain-*` 버전 종속으로 이동.
