"""LLM 기반 엔티티 & 관계(지식 트리플렛) 추출.

[Phase 9]
- with_structured_output(Subgraph): LLM 출력이 곧장 검증된 Pydantic 객체로 온다
  (JSON 파싱/리트라이를 LangChain 이 처리). 프롬프트: config/prompts/graphrag/.
- 후처리(_normalize): 이름 trim, 빈 항목 제거, id=name 통일(그래프 키 = name).
  관계가 미선언 엔티티를 가리켜도 버리지 않는다 — 적재 MERGE 가 엔티티를 만들어 준다.
"""
from __future__ import annotations

from app.schemas.graph import Subgraph


async def extract(text: str, model: str | None = None) -> Subgraph:
    from app.clients.chat_model import get_chat_model
    from app.utils.prompts import load_prompt, render

    prompt = load_prompt("graphrag/entity_extraction")
    llm = get_chat_model(model).with_structured_output(Subgraph)
    raw = await llm.ainvoke(
        [("system", prompt["system"]), ("user", render(prompt["user"], text=text))]
    )
    return _normalize(raw)


def _normalize(sub: Subgraph) -> Subgraph:
    """이름 trim + 빈 항목 제거 + id 를 name 으로 통일."""
    entities = []
    for e in sub.entities:
        name = e.name.strip()
        if not name:
            continue
        entities.append(e.model_copy(update={"id": name, "name": name}))
    relations = [
        r.model_copy(update={"source": r.source.strip(), "target": r.target.strip()})
        for r in sub.relations
        if r.source.strip() and r.target.strip()
    ]
    return Subgraph(entities=entities, relations=relations)
