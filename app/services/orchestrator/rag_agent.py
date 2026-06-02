"""LangGraph 기반 워크플로 제어.

[Phase 5] 함수로 엮던 흐름을 상태머신으로 정식화한다(외부 동작은 Phase 3/4 와 동일).
  analyze → retrieve → grade → generate  (선형)

- build_graph(): StateGraph(AgentState) 구성 후 compile(). 컴파일된 그래프는
  무상태라 프로세스당 1회만 만들면 된다(lru_cache). 노드들은 실행 시점에
  get_chat_model / VectorRetriever 를 해석하므로 캐시해도 테스트 패치가 먹는다.
- 실행은 utils/streaming.py 가 담당:
    · 동기   → graph.ainvoke(state)
    · 스트림 → graph.astream(state, stream_mode=["updates","custom"])
      (generate 노드가 get_stream_writer 로 토큰을 흘리면 custom 모드로 받는다.)

[추후] grade 점수로 재검색/모드전환 conditional edge(품질 게이트), routing.py 로
rag_mode 자동 분기(Phase 10), Langfuse CallbackHandler 연결(observability.py).
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.services.workflow.nodes import analyze, generate, grade, retrieve
from app.services.workflow.state import AgentState


@lru_cache(maxsize=1)
def build_graph():
    g = StateGraph(AgentState)
    g.add_node("analyze", analyze)
    g.add_node("retrieve", retrieve)
    g.add_node("grade", grade)
    g.add_node("generate", generate)

    g.add_edge(START, "analyze")
    g.add_edge("analyze", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_edge("grade", "generate")
    g.add_edge("generate", END)

    return g.compile()
