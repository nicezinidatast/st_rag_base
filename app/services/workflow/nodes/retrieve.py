"""노드: rag_mode 에 따라 ir/ 의 검색기를 골라 호출하고 컨텍스트를 채운다.

[Phase 5] Phase 3 의 _retrieve_context 로직을 그대로 노드로 옮겼다(동작 동일).
- settings.MOCK_RETRIEVER 면 MockRetriever, 아니면 VectorRetriever.
- 결과로 state["documents"](원청크) / state["context"](LLM 입력 문자열) /
  state["citations"](응답 출처) 를 채운다.
- 검색 실패는 비치명: 컨텍스트 없이 진행한다(채팅 자체는 막지 않음).

[추후] rag_mode 로 graph-local/global 분기, HybridRetriever(Phase 4) 연결.
"""
from __future__ import annotations

from app.services.workflow.state import AgentState


async def retrieve(state: AgentState) -> AgentState:
    from app.core.config import settings
    from app.services.ir.base import Retriever
    from app.services.ir.vector import search as vsearch
    from app.utils.logger import get_logger

    query = (state.get("query") or "").strip()
    if not query:
        return {"documents": [], "context": "", "citations": []}

    top_k = state.get("top_k", 5)
    retriever: Retriever
    if settings.MOCK_RETRIEVER:
        from app.services.ir.mock import MockRetriever

        retriever = MockRetriever()
    else:
        retriever = vsearch.VectorRetriever()

    try:
        chunks = await retriever.retrieve(query, top_k=top_k)
    except Exception as e:  # noqa: BLE001  검색 실패는 치명적이지 않다 → 컨텍스트 없이 진행
        get_logger(__name__).warning("vector retrieve skipped", error=str(e))
        return {"documents": [], "context": "", "citations": []}

    if not chunks:
        return {"documents": [], "context": "", "citations": []}

    documents = [
        {"content": c.content, "score": c.score, "source_id": c.source_id, "metadata": c.metadata}
        for c in chunks
    ]
    context = "\n\n".join(f"[{i + 1}] {c.content}" for i, c in enumerate(chunks))
    citations = [
        {"source_id": c.source_id, "snippet": c.content[:200], "score": c.score}
        for c in chunks
    ]
    return {"documents": documents, "context": context, "citations": citations}
