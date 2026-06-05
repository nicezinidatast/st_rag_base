"""[외부 API 클라이언트/팩토리]

- base.py        : HTTPX 비동기 공통 베이스
- chat_model.py  : ChatModel 팩토리 (provider:model → LangChain BaseChatModel)
- embedding.py   : Embedder 팩토리
- reranker.py    : Reranker 팩토리

핵심: 호출부는 팩토리(get_chat_model 등)만 알면 되고, 어떤 프로바이더인지는 몰라도 된다.
채팅 모델은 LangChain 통합(langchain-anthropic/openai)을 쓴다 — LangGraph 스트리밍/콜백 연동 때문.
"""
