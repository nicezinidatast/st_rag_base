"""ir/graph/summarizer: 커뮤니티 리포트 생성(가짜 드라이버 + 가짜 LLM) 테스트."""
from __future__ import annotations

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

import app.clients.chat_model as chat_model_module
import app.services.ir.graph.ingest.summarizer as summarizer_module
from app.schemas.graph import Community
from app.services.ir.graph.ingest.summarizer import summarize


class _FakeResult:
    def __init__(self, records):
        self._records = records

    def __aiter__(self):
        async def gen():
            for r in self._records:
                yield r

        return gen()


class _FakeSession:
    def __init__(self, records, log):
        self._records = records
        self._log = log

    async def run(self, query, **params):
        self._log.append(params)
        return _FakeResult(self._records)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeDriver:
    def __init__(self, records, log):
        self._records, self._log = records, log

    def session(self):
        return _FakeSession(self._records, self._log)


async def test_summarize_builds_report_and_saves(monkeypatch):
    records = [
        {
            "name": "서울",
            "type": "LOCATION",
            "description": "수도",
            "relations": ["서울 -[CAPITAL_OF]-> 대한민국"],
        },
        {"name": "대한민국", "type": "LOCATION", "description": None, "relations": []},
    ]
    log = []
    monkeypatch.setattr(summarizer_module, "get_graph_driver", lambda: _FakeDriver(records, log))
    fake_msg = AIMessage(content="커뮤니티 리포트")
    monkeypatch.setattr(
        chat_model_module,
        "get_chat_model",
        lambda spec=None: GenericFakeChatModel(messages=iter([fake_msg])),
    )

    report = await summarize(Community(id="c0", level=0))

    assert report == "커뮤니티 리포트"
    save_params = [p for p in log if "report" in p]
    assert save_params == [{"id": "c0", "report": "커뮤니티 리포트"}]
