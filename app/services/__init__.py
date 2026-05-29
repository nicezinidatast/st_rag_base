"""[서비스 레이어] 도메인 핵심 로직. API 와 인프라 사이의 '두뇌'.

- orchestrator/ : 검색 모드 제어 + LangGraph 워크플로 지휘
- workflow/     : LangGraph 상태머신 노드 집합 (analyze/retrieve/grade/generate)
- ir/           : 정보검색 엔진 (vector / graph[=GraphRAG])
- cache.py      : 시맨틱 캐시 (Redis)
- memory.py     : 대화 이력 (Redis)

※ 네이밍 주의: 'workflow'(LangGraph 노드)와 'ir/graph'(GraphRAG)와
  core/graph_db(Neo4j)는 서로 다른 'graph'다. 혼동 금지.
"""
