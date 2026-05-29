"""[코어/인프라] 앱 전역 설정과 외부 인프라 커넥션.

- config.py        : 환경변수 검증(Pydantic Settings)
- database.py      : PostgreSQL 세션
- redis.py         : Redis 클라이언트
- vector_db.py     : 벡터 저장소 클라이언트
- graph_db.py      : 그래프 저장소 드라이버
- security.py      : 인증 프리미티브(JWT/해싱)
- exceptions.py    : 도메인 예외
- observability.py : Langfuse LLM 트레이싱
"""
