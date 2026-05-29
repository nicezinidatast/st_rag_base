# Phase 1 — 가장 단순한 동기 챗 (RAG 없음)

- **커밋:** `568ded1` (Feat) openAPI 키 없을 시 하드코딩 답변 반환
- **목표:** LLM 한 개만 연결해 "질문 → 답변". 검색 없음.
- **검증:** `POST /api/v1/chat` `{"stream": false}` → `answer` 필드.

> 참고: 동기 챗의 본체(`achat` / `run_chat_sync` / 엔드포인트 분기)는 이미 Phase 0
> 스캐폴드(`c8bbc4d`)에 동작 상태로 있었다. 그래서 Phase 1 의 **유일한 코드 변경은
> "개발 편의 가드" 추가**다.

## 코드별 변경

### `app/utils/streaming.py` — `run_chat_sync` 에 키 없음 가드
키가 없으면 OpenAI 가 난해한 인증 에러를 던지므로, 대신 안내 답변을 그대로 반환한다.
```python
async def run_chat_sync(request):
    from app.clients.chat_model import get_chat_model
    from app.core.config import settings           # ← 추가

    # [개발 편의 가드] 키가 없으면 안내 답변을 그대로 돌려준다. (키 채우면 자동 해제)
    if not settings.OPENAI_API_KEY:                # ← 추가
        return {
            "answer": "OpenAI API key 가 설정되지 않았습니다. .env 의 OPENAI_API_KEY 를 입력하세요.",
            "citations": [],
        }

    chat_model = get_chat_model()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    answer = await chat_model.achat(messages)
    return {"answer": answer, "citations": []}
```

### `tests/test_api/test_chat.py` — 테스트 2건
- `test_chat_sync_returns_chat_response`: 가드 통과용으로 `OPENAI_API_KEY="test-key"` 주입 +
  `get_chat_model` 을 가짜로 교체 → 직렬화 검증
- `test_chat_sync_without_key_returns_guard_message`: 키 없을 때 안내 답변이 나오는지

## 의미
이 가드 패턴(키 없으면 친절한 안내값을 result 로)이 이후 Phase 2(스트리밍),
Phase 3(Anthropic 키 기준)으로 이어진다.
