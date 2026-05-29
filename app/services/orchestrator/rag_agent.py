"""LangGraph 기반 워크플로 제어 — Vector/Graph 모드 동적 분기.

[구현 가이드]
- build_graph(): StateGraph(AgentState) 에 workflow/nodes 의 노드를 add_node,
  routing.py 의 판단에 따라 add_conditional_edges 로 분기 구성 후 compile().
- 실행은 utils/streaming.py 가이드대로:
    · 동기   → graph.ainvoke(state)
    · 스트림 → graph.astream_events(state, version="v2")  (토큰 단위)
- Langfuse 연동: observability.get_langgraph_callback() 을 config={"callbacks":[cb]} 로 전달.
"""
from __future__ import annotations


def build_graph():
    # TODO: StateGraph 구성 + compile
    raise NotImplementedError("LangGraph 빌드 미구현")
