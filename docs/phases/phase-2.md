# Phase 2 — SSE 토큰 스트리밍 추가

- **커밋:** `6f28409` feat(streaming): add SSE token streaming for chat (phase 2)
- **목표:** 같은 챗을 토큰 단위로 흘려보낸다. 동기 경로는 그대로(둘 다 지원).
- **검증:** `{"stream": true}` → `curl -N` 로 SSE 프레임 확인. `pytest` 11 passed.

데이터 흐름: `openai_client.astream`(토큰 생산) → `streaming.stream_chat`(SSE 포장) → 엔드포인트.

## 1. `app/clients/openai_client.py` — `astream` 구현 (토큰의 출처)

`NotImplementedError` → OpenAI `stream=True` 응답을 토큰 조각으로 yield 하는 async generator.
```python
async def astream(self, messages, **kwargs) -> AsyncIterator[str]:
    stream = await self._client.chat.completions.create(
        model=self.model, messages=..., stream=True, **kwargs,
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:                 # 내용 있는 조각만
            yield delta
```
- `def`→`async def`+`yield` 로 진짜 async generator. HTTP/SSE 는 모름(포장은 streaming.py).

## 2. `app/utils/streaming.py`

### 2-a. 공용 상수
```python
NO_API_KEY_MESSAGE = "OpenAI API key 가 없습니다."   # 동기/스트리밍 공용 안내값
```

### 2-b. `stream_chat` 구현 (가이드 주석 → 실제 generator)
```python
async def stream_chat(request):
    if not settings.OPENAI_API_KEY:                  # 가드: 안내 토큰 + done
        yield sse(NO_API_KEY_MESSAGE, EVENT_TOKEN)
        yield sse("[DONE]", EVENT_DONE)
        return
    chat_model = get_chat_model()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        async for token in chat_model.astream(messages):
            yield sse(token, EVENT_TOKEN)            # 토큰마다 token 이벤트
        yield sse("[DONE]", EVENT_DONE)              # 끝나면 done
    except Exception as e:
        yield sse(str(e), EVENT_ERROR)               # 스트림 중 에러는 event 로만 알림
```

### 2-c. `run_chat_sync` 가드 단순화
긴 안내 문구를 `NO_API_KEY_MESSAGE` 상수로 교체 → 동기/스트리밍 동일 result.

### 2-d. import 정리
`from typing import AsyncIterator` → `from collections.abc import AsyncIterator`.

## 3. 테스트
- `test_clients/test_chat_model.py`: 가짜 청크(`["안","녕",None,"!"]`)로 `astream` 이 `None` 스킵하는지
- `test_api/test_chat.py`: `_FakeChatModel.astream` 추가 + SSE 프레임(`event: token`/`done`) 검증, 키 없음 스트리밍 검증
- `tests/conftest.py`: 안 쓰던 `fake_llm` 픽스처 제거

## 4. 문서
- `README.md`: Phase 0/2 `[x]` 표기
