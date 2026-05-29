"""[IR: 정보검색 도메인] base.py 의 Retriever 인터페이스를 모두가 구현한다.
- vector/ : 일반 Vector RAG (dense + BM25 하이브리드 + rerank)
- graph/  : GraphRAG (엔티티 추출 → Leiden 군집 → 커뮤니티 요약 → local/global 검색)
"""
