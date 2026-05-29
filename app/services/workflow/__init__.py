"""[LangGraph 상태머신 노드]

원래 트리의 services/graph/ 를 'workflow'로 개명함 — ir/graph(GraphRAG),
core/graph_db(Neo4j)와의 이름 충돌을 피하기 위해서다.

- state.py : 노드 간 공유 컨텍스트(AgentState)
- nodes/   : analyze → retrieve → grade → generate (순수 함수형 노드)
"""
