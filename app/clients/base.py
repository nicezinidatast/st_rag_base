"""모든 외부 API 래퍼가 공유하는 HTTPX 비동기 베이스.

[구현 가이드] 타임아웃/재시도/공통 헤더/로깅을 여기서 통일한다. 각 프로바이더
래퍼는 이 클래스를 상속하거나 self._client 를 받아 쓴다.
"""
from __future__ import annotations

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class BaseAsyncClient:
    """재사용 가능한 httpx.AsyncClient 를 들고 있는 베이스."""

    def __init__(self, base_url: str = "", headers: dict | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers or {}, timeout=DEFAULT_TIMEOUT
        )

    async def aclose(self) -> None:
        await self._client.aclose()
