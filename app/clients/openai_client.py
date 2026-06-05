"""OpenAI 구체 래퍼 (GPT 챗 + 임베딩).

[구현 가이드]
- chat_model.py 의 ChatModel 인터페이스(achat/astream)를 만족하는 클래스를 만든다.
- astream 은 OpenAI 의 stream=True 응답을 async 로 yield (토큰 단위 SSE 의 원천).
- 임베딩 클래스는 embedding.py 의 Embedder(dim/aembed_documents/aembed_query) 구현.
- 키는 settings.OPENAI_API_KEY 사용. Azure 면 AZURE_OPENAI_* 분기.

[현재 구현 범위 — Phase 1]
- OpenAIChatModel.achat (동기형) 만 구현. astream 은 Phase 2 에서 구현.
- 임베딩(OpenAIEmbedder) 은 Phase 3 에서 구현.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, cast

from openai import AsyncOpenAI

from app.core.config import settings

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletion, ChatCompletionMessageParam


class OpenAIChatModel:
    """OpenAI Chat Completions 를 ChatModel 인터페이스로 감싼 래퍼.

    achat: 전체 답변을 한 번에 반환(동기형). 동기 JSON 응답 경로에서 사용.
    astream: 토큰 조각을 yield(스트리밍형). → Phase 2 에서 구현.
    """

    def __init__(self, model: str) -> None:
        self.model = model
        # api_key 가 비어 있으면 실제 호출 시점에 OpenAI 가 에러를 던진다(생성은 OK).
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def achat(self, messages: list[dict], **kwargs) -> str:
        """동기형: 전체 답변을 한 번에 반환."""
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=cast("list[ChatCompletionMessageParam]", messages),
            stream=False,
            **kwargs,
        )
        return cast("ChatCompletion", resp).choices[0].message.content or ""

    async def astream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """스트리밍형: OpenAI stream=True 응답을 토큰 조각씩 yield.

        OpenAI 는 청크마다 delta.content 에 토큰 조각을 담아 보낸다(없는 청크도 있다).
        내용이 있는 조각만 흘려보낸다. HTTP/SSE 는 모른다(streaming.py 가 포장).
        """
        stream = await self._client.chat.completions.create(
            model=self.model,
            messages=cast("list[ChatCompletionMessageParam]", messages),
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# TODO(Phase 3): class OpenAIEmbedder (dim / aembed_documents / aembed_query 구현)
