"""[ORM 모델] RDBMS 영구 저장 엔티티(SQLAlchemy).

- base.py         : DeclarativeBase + 공통 타임스탬프 믹스인
- user.py         : 사용자/RBAC
- conversation.py : 대화방 메타
- message.py      : 메시지 로그

주의: Alembic 마이그레이션(migration/)이 이 모델들을 스캔하도록 env.py 에서 import.
"""
