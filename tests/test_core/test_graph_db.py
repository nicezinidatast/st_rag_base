"""core/graph_db: 드라이버 싱글톤 + 스키마 보장(가짜 드라이버) 테스트."""
from __future__ import annotations

import app.core.graph_db as graph_db


class _FakeSession:
    def __init__(self, log):
        self._log = log

    async def run(self, query, **params):
        self._log.append(query)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeDriver:
    def __init__(self, log):
        self._log = log

    def session(self):
        return _FakeSession(self._log)


def test_get_graph_driver_is_singleton():
    graph_db.get_graph_driver.cache_clear()
    assert graph_db.get_graph_driver() is graph_db.get_graph_driver()
    graph_db.get_graph_driver.cache_clear()


async def test_ensure_schema_runs_all_statements(monkeypatch):
    log = []
    monkeypatch.setattr(graph_db, "get_graph_driver", lambda: _FakeDriver(log))
    await graph_db.ensure_schema()
    assert log == graph_db.SCHEMA_STATEMENTS
    assert any("FULLTEXT" in s for s in log)
