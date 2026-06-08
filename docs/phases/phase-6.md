# Phase 6 — 대화 메모리 + 응답 캐시 (Redis)

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** 멀티턴 맥락 유지(이전 대화를 generate 에 주입) + 반복 질문 캐싱으로 LLM 비용 절감.
- **검증:** `pytest` 45 passed (신규 11: memory 4 / cache 5 / 통합 2). Redis 미기동에도 채팅 정상(빠름).

Phase 5 까지는 매 질문이 독립적이었다. Phase 6 은 `session_id` 로 대화 이력을 기억하고,
같은 질문은 캐시에서 즉시 답한다. **둘 다 Redis 가 없거나 죽어도 채팅을 막지 않는다.**

---

## A. 대화 이력 (`app/services/memory.py`)

`NotImplementedError` → Redis 리스트 기반 구현:
- 키 `chat:history:{session_id}`, 원소 = JSON `{"role","content"}`.
- `append_message`: RPUSH → LTRIM(최근 `HISTORY_MAX_MESSAGES`) → EXPIRE(`HISTORY_TTL_SECONDS`).
- `get_history`: LRANGE 최근 N개 → dict 리스트(오래된→최신).
- 빈 session_id / Redis 불가 시 no-op·`[]`(비치명).

## B. 응답 캐시 (`app/services/cache.py`)

`NotImplementedError` → **완전일치 캐시**(MVP):
- 키 `chat:cache:{sha256(정규화 질문)}`(공백·소문자 정규화), 값 = 답변, TTL `CACHE_TTL_SECONDS`.
- `get_cached`/`set_cached`. 히트 시 LLM 호출을 통째로 건너뛴다.
- **후속:** 진짜 "시맨틱"(임베딩 유사도) 캐시는 RediSearch 벡터 인덱스 필요 → 미룸. 지금은 같은 질문만 히트.
- **주의:** 질문 텍스트만으로 캐시 → 멀티턴 맥락 미반영(히트 시 citations 비움).

## C. 그래프/노드 주입 (`state.py`, `nodes/generate.py`)

- `AgentState` 에 `history: list[dict]` 추가.
- `_build_messages(question, context, history)`: **system(컨텍스트) → 이전 대화 턴 → 현재 질문** 순서로 조립.
- generate 가 `state["history"]` 를 프롬프트에 포함.

## D. 오케스트레이션 (`utils/streaming.py`, `endpoints/chat.py`)

`endpoints/chat.py`: `session_id` 를 **1회 확정**(없으면 발급) 후 메모리/캐시·응답이 같은 id 사용.

`run_chat_sync` / `stream_chat` 양쪽에:
1. **진입 시 캐시 조회** → 히트면 LLM·검색 없이 답변 반환(스트림은 통째로 1토큰). 이력엔 그대로 적재.
2. 미스면 `get_history` → state 에 주입 → 그래프 실행.
3. 응답 후 user/assistant 메시지 `append` + 답변 `set_cached`.

## E. Graceful degradation (`core/redis.py`, `main.py`)

Redis 미기동/다운에도 채팅이 **느려지지 않게** 한다:
- `redis_client` 에 `socket_connect_timeout/socket_timeout=1.0`(빠른 실패).
- 가용성 플래그(`is_available`/`set_available`): `main.py` lifespan 의 `ping` 으로 1회 확정.
  미기동이면 `False` → memory/cache 가 매 요청 연결 재시도 없이 **즉시 스킵**(요청 지연 0).
- 효과: Redis 다운 시 요청 20초 → **0.35초**(시작 시 ping 만 ~1초 1회). Redis 띄운 뒤 재시작하면 반영.

## F. 설정 / 테스트

- `config.py` + `.env.example`: `MEMORY_ENABLED`, `HISTORY_MAX_MESSAGES`, `HISTORY_TTL_SECONDS`,
  `CACHE_ENABLED`, `CACHE_TTL_SECONDS`.
- 의존성(dev): `fakeredis` 추가. `tests/conftest.py` autouse 픽스처가 모든 테스트에서
  Redis 를 in-memory fakeredis 로 대체(라이브 Redis 불필요).
- 테스트: `test_services/test_memory.py`, `test_cache.py`, `test_api/test_chat.py`
  (캐시 히트 시 2번째 LLM 미호출 / 후속 질문에 이전 이력 주입).
