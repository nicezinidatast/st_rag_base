"""ir/graph/extractor: LLM 구조화 추출(가짜 모델) + 정규화 테스트."""
from __future__ import annotations

import app.clients.chat_model as chat_model_module
from app.schemas.graph import Entity, Relation, Subgraph
from app.services.ir.graph.ingest.extractor import _normalize, extract


class _FakeStructuredModel:
    """get_chat_model() 대역 — with_structured_output 체인을 흉내낸다."""

    def __init__(self, result):
        self._result = result

    def with_structured_output(self, schema):
        assert schema is Subgraph
        return self

    async def ainvoke(self, messages):
        assert len(messages) == 2  # system + user
        return self._result


def _sample():
    return Subgraph(
        entities=[Entity(id="x", name="  서울 ", type="LOCATION", description="대한민국의 수도")],
        relations=[Relation(source=" 서울 ", target="대한민국", type="CAPITAL_OF")],
    )


async def test_extract_returns_normalized_subgraph(monkeypatch):
    monkeypatch.setattr(
        chat_model_module, "get_chat_model", lambda spec=None: _FakeStructuredModel(_sample())
    )
    sub = await extract("서울은 대한민국의 수도이다.")
    assert sub.entities[0].name == "서울"
    assert sub.entities[0].id == "서울"  # 그래프 키 = name
    assert sub.relations[0].source == "서울"


def test_normalize_drops_blank_entities_and_relations():
    sub = _normalize(
        Subgraph(
            entities=[Entity(id="", name="  ", type="X")],
            relations=[Relation(source=" ", target="대한민국", type="R")],
        )
    )
    assert sub.entities == []
    assert sub.relations == []
