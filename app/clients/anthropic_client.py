"""Anthropic 구체 래퍼 (Claude).

[구현 가이드]
- ChatModel 인터페이스(achat/astream) 구현. astream 은 Anthropic messages 의
  스트리밍 이벤트를 텍스트 조각으로 변환해 yield.
- 키는 settings.ANTHROPIC_API_KEY.
"""
from __future__ import annotations

# TODO: from anthropic import AsyncAnthropic
# class AnthropicChatModel: ...  (achat / astream 구현)
placeholder = None
