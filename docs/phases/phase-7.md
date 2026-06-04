# Phase 7 — 인증/RBAC + 영속화 (Postgres + Alembic)

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** 사용자/대화/메시지를 DB에 남기고 접근을 보호한다. JWT 인증 + 대화 영속 로그.
- **검증:** `pytest` 56 passed (신규 11: security 4 / auth API 7). WSL Docker Postgres 에
  `make migrate` 성공(rev 0001) + E2E: 무토큰 채팅 401 → 가입 201 → 토큰 발급 → `/me` 200 →
  인증 채팅 → `conversations`/`messages` row 적재 확인. AUTH off 시 기존 채팅 그대로 동작.

원안("토큰 없이는 차단")을 **`AUTH_ENABLED` 토글**로 변형했다. 기본 `false` 면 기존
데모(/ui)·curl·테스트가 토큰/Postgres 없이 그대로 동작하고, `true` 면 chat/document 가
JWT 를 요구하며 대화가 DB에 영구 저장된다. Phase 6 의 "Redis 없어도 동작" 철학과 일관.

---

## A. 인증 프리미티브 (`core/security.py`)

`NotImplementedError` → bcrypt + pyjwt 구현:
- `hash_password`/`verify_password`: bcrypt 직접 사용(passlib 은 bcrypt 4.x 와 호환 깨진 채 미유지).
- `create_access_token(subject=email)`: HS256, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`.
- `decode_access_token`: 무효/만료 시 `jwt.InvalidTokenError`.

## B. 의존성 주입 (`api/deps.py`)

- `get_db`: `SessionLocal()` async 세션 yield (호출 시점 import → 테스트에서 모듈 속성 교체 가능).
- `get_current_user`: **항상 강제.** `Authorization: Bearer` → decode → DB 에서 활성 사용자 조회, 실패 시 401.
- `get_optional_user`: **토글형.** `AUTH_ENABLED=false` 면 None(검사 없음), true 면 위와 동일 강제.
  off 일 때도 세션 의존성이 걸리지만 SQLAlchemy 는 lazy 라 실제 쿼리 전엔 연결하지 않는다.

## C. 인증 API (`endpoints/auth.py`, `schemas/auth.py`)

- `POST /auth/register`: email+password 가입(201). 중복 email 409.
- `POST /auth/token`: 자격증명 검증 → JWT 발급. 실패/비활성 401.
- `GET /auth/me`: 토큰 주체 반환(토글과 무관하게 항상 토큰 필요).

## D. 모델 + 마이그레이션 (`models/`, `migration/`)

- `Conversation` 에 `session_id`(unique) 추가 — Redis 메모리(Phase 6)의 세션 키와 1:1 매핑.
- `models/__init__.py` 가 전 모델 export → `migration/env.py` 의 `Base.metadata` 에 전체 등록.
- `env.py`: async 엔진 + `.env` 의 `DATABASE_URL` 사용(alembic.ini 덮어씀). offline(`--sql`) 모드 지원.
- 초기 리비전 `0001`(users/conversations/messages)은 **수작성**(작성 시점에 Postgres 미기동이라
  autogenerate 불가). Postgres 띄운 뒤 `make migrate` 로 적용.

## E. 대화 영속화 (`services/persistence.py`, `utils/streaming.py`)

- `save_exchange(session_id, user_id, question, answer)`: session_id 로 Conversation
  get-or-create(첫 질문 80자를 title 로) 후 user/assistant 메시지 2건 적재.
- `stream_chat`/`run_chat_sync` 가 `user_id` 파라미터를 받아 Redis 메모리 적재와 같은 지점에서
  호출(캐시 히트 경로 포함). `user_id=None`(=AUTH off)이면 no-op.
- DB 장애는 **비치명**: 답변은 이미 나간 뒤이므로 경고 로그만 남기고 계속(memory.py 와 동일 정책).

## F. 설정 / 테스트

- `config.py` + `.env.example`: `AUTH_ENABLED`(기본 false).
- 의존성: `pyjwt`, `bcrypt` 추가. dev 에 `aiosqlite`.
- `tests/conftest.py` 에 `sqlite_db` 픽스처: 임시 파일 SQLite + `NullPool` 로 `SessionLocal`
  교체(fakeredis 와 같은 패턴, 라이브 Postgres 불필요).
- 테스트: `test_core/test_security.py`(해싱/JWT 왕복), `test_api/test_auth.py`
  (가입→로그인→me / 중복 409 / 무토큰·오토큰 401 / AUTH on 채팅 차단 / off 개방 /
  인증 채팅 후 Conversation+Message row 적재 확인).

## 수동 검증 절차 (Postgres 필요)

```bash
docker compose up -d postgres
uv run alembic upgrade head          # = make migrate
# .env: AUTH_ENABLED=true 로 변경 후 make dev
curl -X POST localhost:8000/api/v1/auth/register -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"password123"}'
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/token -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"password123"}' | jq -r .access_token)
curl localhost:8000/api/v1/chat -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"question":"안녕","stream":false}'
# → messages 테이블에 user/assistant row 2건 적재 확인
```
