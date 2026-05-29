"""오케스트레이터 레이어 공통 타입."""
from __future__ import annotations

from abc import ABC, abstractmethod


class BaseOrchestrator(ABC):
    @abstractmethod
    async def run(self, request) -> object:
        ...
