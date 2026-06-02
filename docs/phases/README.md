# Phase 작업 기록 (코드 상세)

각 Phase 에서 **무슨 코드를 어떻게 바꿨는지** 커밋 기준으로 정리한다.
한 줄 요약/체크리스트는 루트 `CHANGELOG.md`, 로드맵은 `README.md` 참고.

| Phase | 한 줄 | 커밋 | 문서 |
|---|---|---|---|
| 0 | 스캐폴드 그대로 부팅 (+ 동기 챗 코드 이미 포함) | `c8bbc4d` | [phase-0.md](phase-0.md) |
| 1 | 동기 챗 + 키 없음 개발 가드 | `568ded1` | [phase-1.md](phase-1.md) |
| 2 | SSE 토큰 스트리밍 | `6f28409` | [phase-2.md](phase-2.md) |
| 3 | Vector RAG(검색→출처) + Anthropic 챗 + 로컬 bge-m3 | _(미커밋)_ | [phase-3.md](phase-3.md) |
| 4 | 하이브리드 검색(BM25)+리랭커 — **스켈레톤만** | `9cf9784` | _(스텁, 본체 미구현)_ |
| 5 | LangGraph 워크플로 구조화(analyze→retrieve→grade→generate) | _(미커밋)_ | [phase-5.md](phase-5.md) |

## 큰 그림 (계층)

```
요청(question) ─▶ endpoints/chat.py ─┬─ stream=false ─▶ run_chat_sync ─▶ graph.ainvoke
                                     └─ stream=true  ─▶ stream_chat  ─▶ graph.astream
                                                                          (updates+custom)
                                                                       ▼
   build_graph():  analyze ─▶ retrieve ─▶ grade ─▶ generate          (Phase 5, LangGraph)
                              │                       │
              VectorRetriever/MockRetriever      ChatModel.astream + get_stream_writer
              (embedding→vector_db query)        (토큰 → custom 스트림 → SSE)
   적재: /documents/ingest → ir/vector/ingest → embedding+upsert
```
