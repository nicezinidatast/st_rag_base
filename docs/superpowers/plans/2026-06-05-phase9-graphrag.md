# Phase 9 — GraphRAG 파이프라인 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 엔티티/관계 지식그래프 기반 검색(graph_local/graph_global)을 기존 Vector RAG *옆에* 추가한다.

**Architecture:** 인덱싱(추출→Leiden 군집→커뮤니티 요약)은 Neo4j 에 적재하고, 검색은 Retriever 전략 패턴으로 `retrieve` 노드에서 rag_mode 분기. Leiden 은 Python(igraph+leidenalg)에서 실행해 Neo4j 를 순수 저장소로 유지. 승인된 설계: `docs/superpowers/specs/2026-06-05-phase9-graphrag-design.md`

**Tech Stack:** Neo4j 5(bolt, 풀텍스트 인덱스), python-igraph + leidenalg, LangChain `with_structured_output`, 기존 LangGraph 워크플로

**규칙:** 각 태스크는 TDD(실패 테스트 → 최소 구현 → 통과 → 커밋). pytest 는 외부 인프라 없이 통과해야 한다(가짜 드라이버/LLM). 전체 `make test`/`make lint`/`make type` 는 Task 11(페이즈 경계)에서 1회. 커밋 메시지 끝에 트레일러를 붙인다:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

---

## 파일 구조 (이 계획이 만들고/고치는 것)

```
[신규] app/utils/prompts.py                    YAML 프롬프트 로더
[신규] tests/test_utils/{__init__,test_prompts}.py
[신규] tests/test_core/test_graph_db.py
[신규] tests/test_ir/test_graph_extractor.py
[신규] tests/test_ir/test_graph_cluster.py
[신규] tests/test_ir/test_graph_summarizer.py
[신규] tests/test_ir/test_graph_ingest.py
[신규] tests/test_ir/test_graph_search.py
[신규] docs/phases/phase-9.md
[수정] config/prompts/graphrag/{entity_extraction,community_report,global_search}.yaml
       (local_search.yaml 은 현재 미사용 — generate 노드가 범용 프롬프트 담당. 건드리지 않음)
[수정] app/core/graph_db.py                    드라이버 + 스키마 보장
[수정] app/services/ir/graph/ingest/__init__.py  ingest() 오케스트레이션 + 서브그래프 upsert
[수정] app/services/ir/graph/ingest/extractor.py
[수정] app/services/ir/graph/ingest/cluster.py
[수정] app/services/ir/graph/ingest/summarizer.py
[수정] app/services/ir/graph/search/local.py
[수정] app/services/ir/graph/search/global_.py
[수정] app/services/workflow/nodes/retrieve.py   rag_mode 분기
[수정] app/api/v1/endpoints/document.py         IngestTarget.GRAPH 연결
[수정] pyproject.toml + uv.lock                  igraph, leidenalg
[수정] README.md / CHANGELOG.md                  phase 9 기록
```

---

### Task 1: 의존성 추가 (igraph + leidenalg)

**Files:**
- Modify: `pyproject.toml`, `uv.lock`

- [ ] **Step 1: 패키지 추가**

```bash
uv add igraph leidenalg
```

- [ ] **Step 2: import 확인**

```bash
uv run python -c "import igraph, leidenalg; print(igraph.__version__, leidenalg.version)"
```

Expected: 버전 두 개 출력 (예: `0.11.x 0.10.x`). Windows wheel 이 설치되어야 한다 — 빌드 에러가 나면 중단하고 보고.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): add igraph + leidenalg for graphrag clustering"
```

---

### Task 2: YAML 프롬프트 로더 + graphrag 프롬프트 보강

`config/prompts/*.yaml` 은 지금까지 로더가 없어 미사용이었다. 최소 로더(`{{ var }}` 치환만, Jinja2 는 YAGNI)를 만들고, 스텁 수준인 graphrag 프롬프트 3종을 실사용 품질로 보강한다.

**Files:**
- Create: `app/utils/prompts.py`
- Create: `tests/test_utils/__init__.py`, `tests/test_utils/test_prompts.py`
- Modify: `config/prompts/graphrag/entity_extraction.yaml`
- Modify: `config/prompts/graphrag/community_report.yaml`
- Modify: `config/prompts/graphrag/global_search.yaml`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_utils/test_prompts.py`

```python
"""utils/prompts: YAML 프롬프트 로더 테스트."""
from __future__ import annotations

from app.utils.prompts import load_prompt, render


def test_load_prompt_reads_graphrag_yaml():
    p = load_prompt("graphrag/entity_extraction")
    assert p["name"] == "entity_extraction"
    assert "{{ text }}" in p["user"]


def test_render_substitutes_both_spacings():
    assert render("질문: {{ query }} / {{query}}", query="수도?") == "질문: 수도? / 수도?"


def test_render_keeps_unknown_placeholders():
    assert render("{{ keep }}", other=1) == "{{ keep }}"
```

`tests/test_utils/__init__.py` 는 빈 파일로 생성.

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_utils/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.prompts'`

- [ ] **Step 3: 구현** — `app/utils/prompts.py`

```python
"""YAML 프롬프트 로더 (config/prompts/*).

[설계] 프롬프트를 코드 밖(YAML)에 두고 {{ var }} 치환만 지원하는 최소 로더.
Jinja2 같은 템플릿 엔진은 필요해질 때 도입한다(YAGNI).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

# app/utils/prompts.py → 리포 루트 /config/prompts
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "config" / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> dict:
    """'graphrag/entity_extraction' → 해당 YAML 을 dict 로 로드(프로세스당 1회)."""
    path = _PROMPTS_DIR / f"{name}.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def render(template: str, **variables: object) -> str:
    """'{{ var }}' / '{{var}}' 플레이스홀더 치환. 누락 변수는 그대로 둔다."""
    for key, value in variables.items():
        for token in (f"{{{{ {key} }}}}", f"{{{{{key}}}}}"):
            template = template.replace(token, str(value))
    return template
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_utils/test_prompts.py -v`
Expected: 3 passed

- [ ] **Step 5: 프롬프트 보강** — 3개 파일을 아래 내용으로 교체

`config/prompts/graphrag/entity_extraction.yaml`:

```yaml
name: entity_extraction
description: Extract entities and relations (knowledge triplets) from text.
system: |
  주어진 텍스트에서 지식그래프 재료를 추출한다.

  1. entities — 텍스트에 명시적으로 등장하는 핵심 엔티티만:
     - name: 고유한 정식 명칭 (약어보다 전체 이름 선호)
     - type: PERSON / ORGANIZATION / LOCATION / CONCEPT / EVENT / PRODUCT 등 대문자
     - description: 텍스트 근거 기반 한 문장 설명
  2. relations — 텍스트에 명시된 엔티티 간 관계(지식 트리플렛):
     - source / target: 위 entities 의 name 과 정확히 일치할 것
     - type: 대문자 영문 동사형 (예: CEO_OF, INVESTED_IN, PART_OF)
     - description: 관계의 근거 한 문장
     - weight: 1~10 (텍스트에서의 중요도)

  텍스트에 없는 내용을 추측하지 말 것. id 필드는 name 과 동일하게 채울 것.
user: |
  텍스트: {{ text }}
```

`config/prompts/graphrag/community_report.yaml`:

```yaml
name: community_report
description: Summarize a community of entities into a report.
system: |
  서로 밀접하게 연결된 엔티티 묶음(커뮤니티)의 요약 리포트를 작성한다.
  핵심 주제 한 줄 → 주요 엔티티와 역할 → 중요한 관계 순으로 5문장 내외의 한 단락.
  이 리포트는 거시 질문 답변의 재료(Global Search 의 Map 입력)로 쓰인다.
user: |
  엔티티:
  {{ entities }}

  관계:
  {{ relations }}
```

`config/prompts/graphrag/global_search.yaml` (역할 변경: Reduce 통합 → **Map 부분답변**. Reduce 는 generate 노드가 담당):

```yaml
name: global_search
description: Map step - answer partially from ONE community report.
system: |
  커뮤니티 리포트 하나를 보고 질문에 부분적으로 답하는 분석가다.
  리포트에 근거한 내용만 간결히 답하라.
  리포트가 질문과 무관하면 정확히 "관련 없음" 이라고만 답하라.
user: |
  질문: {{ query }}
  커뮤니티 리포트:
  {{ report }}
```

- [ ] **Step 6: 테스트 재실행(회귀 확인) 후 커밋**

Run: `uv run pytest tests/test_utils/test_prompts.py -v` → 3 passed

```bash
git add app/utils/prompts.py tests/test_utils config/prompts/graphrag
git commit -m "feat(utils): yaml prompt loader + enrich graphrag prompts"
```

---

### Task 3: Neo4j 드라이버 + 스키마 부트스트랩

**Files:**
- Modify: `app/core/graph_db.py`
- Create: `tests/test_core/test_graph_db.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_core/test_graph_db.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_core/test_graph_db.py -v`
Expected: FAIL — `NotImplementedError` / `AttributeError: ensure_schema`

- [ ] **Step 3: 구현** — `app/core/graph_db.py` 전체 교체

```python
"""그래프 저장소 드라이버 (기본 Neo4j, NebulaGraph 등으로 교체 가능).

[Phase 9]
- get_graph_driver(): 프로세스당 1회 생성되는 비동기 드라이버. 생성만으로는 접속하지
  않고 첫 쿼리에서 붙는다(지연 연결 — vector_db 의 Qdrant 클라이언트와 같은 철학).
- ensure_schema(): 유니크 제약 + 풀텍스트 인덱스를 멱등(IF NOT EXISTS) 생성.
  graph ingest 진입 시마다 호출해도 안전하다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from neo4j import AsyncDriver

# 스키마(제약/인덱스) — 전부 멱등(IF NOT EXISTS)
SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT entity_name IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
    "CREATE CONSTRAINT community_id IF NOT EXISTS FOR (c:Community) REQUIRE c.id IS UNIQUE",
    "CREATE FULLTEXT INDEX entity_fulltext IF NOT EXISTS "
    "FOR (e:Entity) ON EACH [e.name, e.description]",
    "CREATE FULLTEXT INDEX community_fulltext IF NOT EXISTS "
    "FOR (c:Community) ON EACH [c.report]",
]


@lru_cache
def get_graph_driver() -> AsyncDriver:
    from neo4j import AsyncGraphDatabase

    return AsyncGraphDatabase.driver(
        settings.GRAPH_DB_URI, auth=(settings.GRAPH_DB_USER, settings.GRAPH_DB_PASSWORD)
    )


async def ensure_schema() -> None:
    """엔티티/커뮤니티 제약과 풀텍스트 인덱스를 보장한다(멱등)."""
    driver = get_graph_driver()
    async with driver.session() as session:
        for stmt in SCHEMA_STATEMENTS:
            await session.run(stmt)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_core/test_graph_db.py -v` → 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/core/graph_db.py tests/test_core/test_graph_db.py
git commit -m "feat(core): neo4j async driver + graphrag schema bootstrap"
```

---

### Task 4: 엔티티/관계 추출기 (extractor)

학습 포인트: `with_structured_output(Subgraph)` 로 LLM 출력이 곧장 검증된 Pydantic 객체가 된다 — JSON 파싱/리트라이를 LangChain 이 처리.

**Files:**
- Modify: `app/services/ir/graph/ingest/extractor.py`
- Create: `tests/test_ir/test_graph_extractor.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_ir/test_graph_extractor.py`

```python
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
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ir/test_graph_extractor.py -v`
Expected: FAIL — `NotImplementedError("entity 추출 미구현")` / `ImportError: _normalize`

- [ ] **Step 3: 구현** — `app/services/ir/graph/ingest/extractor.py` 전체 교체

```python
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
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_ir/test_graph_extractor.py -v` → 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/ir/graph/ingest/extractor.py tests/test_ir/test_graph_extractor.py
git commit -m "feat(ir/graph): llm entity/relation extraction via structured output"
```

---

### Task 5: Leiden 커뮤니티 군집화 (cluster)

학습 포인트: 군집화 본체는 **순수 함수** `compute_communities(edges)` 로 분리 — Neo4j 없이 결정성(seed 고정)을 단위 테스트한다.

**Files:**
- Modify: `app/services/ir/graph/ingest/cluster.py`
- Create: `tests/test_ir/test_graph_cluster.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_ir/test_graph_cluster.py`

```python
"""ir/graph/cluster: Leiden 군집화 순수 함수 테스트 (Neo4j 불필요)."""
from __future__ import annotations

from app.services.ir.graph.ingest.cluster import compute_communities


def _clique(names):
    """완전그래프 엣지 목록 (서로 빽빽하게 연결된 무리)."""
    return [(a, b, 1.0) for i, a in enumerate(names) for b in names[i + 1 :]]


def test_two_cliques_with_weak_bridge_split_into_two_communities():
    edges = _clique(["a1", "a2", "a3"]) + _clique(["b1", "b2", "b3"]) + [("a1", "b1", 0.1)]
    comms = compute_communities(edges)
    groups = sorted(sorted(c.entity_ids) for c in comms)
    assert groups == [["a1", "a2", "a3"], ["b1", "b2", "b3"]]
    assert all(c.level == 0 for c in comms)
    assert sorted(c.id for c in comms) == ["c0", "c1"]


def test_empty_graph_returns_no_communities():
    assert compute_communities([]) == []
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ir/test_graph_cluster.py -v`
Expected: FAIL — `ImportError: compute_communities`

- [ ] **Step 3: 구현** — `app/services/ir/graph/ingest/cluster.py` 전체 교체

```python
"""Leiden 알고리즘 기반 커뮤니티 군집화 (단일 레벨 MVP).

[Phase 9 — 동작]
1. Neo4j 에서 (source, target, weight) 엣지 목록을 읽는다.
2. igraph 무방향 그래프 → leidenalg 모듈러리티 파티션 (seed 고정 → 결정적).
   계층형(level>0)은 후속 확장 — 지금은 전부 level=0.
3. 기존 Community 노드를 전부 지우고 새로 만든 뒤 IN_COMMUNITY 로 연결한다.
   (군집은 전역 개념이라 적재 때마다 전체 재계산 — 느려지면 Phase 8 워커로)
"""
from __future__ import annotations

from app.core.graph_db import get_graph_driver
from app.schemas.graph import Community

_LOAD_EDGES = (
    "MATCH (s:Entity)-[r:RELATED]->(t:Entity) "
    "RETURN s.name AS s, t.name AS t, r.weight AS w"
)
_DELETE_COMMUNITIES = "MATCH (c:Community) DETACH DELETE c"
_SAVE_COMMUNITIES = """
UNWIND $communities AS com
CREATE (c:Community {id: com.id, level: com.level})
WITH c, com
UNWIND com.entity_ids AS name
MATCH (e:Entity {name: name})
MERGE (e)-[:IN_COMMUNITY]->(c)
"""


def compute_communities(edges: list[tuple[str, str, float]]) -> list[Community]:
    """엣지 목록 → Leiden 파티션. (순수 함수 — 단위 테스트 대상)"""
    import igraph as ig
    import leidenalg

    if not edges:
        return []
    names = sorted({n for s, t, _ in edges for n in (s, t)})
    index = {n: i for i, n in enumerate(names)}
    g = ig.Graph(
        n=len(names), edges=[(index[s], index[t]) for s, t, _ in edges], directed=False
    )
    part = leidenalg.find_partition(
        g,
        leidenalg.ModularityVertexPartition,
        weights=[w or 1.0 for _, _, w in edges],
        seed=42,
    )
    return [
        Community(id=f"c{i}", level=0, entity_ids=[names[v] for v in members])
        for i, members in enumerate(part)
    ]


async def cluster() -> list[Community]:
    """Neo4j 그래프 전체를 군집화하고 Community 노드로 저장한다."""
    driver = get_graph_driver()
    async with driver.session() as session:
        result = await session.run(_LOAD_EDGES)
        edges = [(rec["s"], rec["t"], rec["w"]) async for rec in result]
    communities = compute_communities(edges)
    async with driver.session() as session:
        await session.run(_DELETE_COMMUNITIES)
        if communities:
            await session.run(
                _SAVE_COMMUNITIES,
                communities=[
                    c.model_dump(include={"id", "level", "entity_ids"}) for c in communities
                ],
            )
    return communities
```

주의: 기존 스텁 시그니처 `cluster(graph)` 의 `graph` 인자는 제거한다(데이터를 Neo4j 에서 직접 읽으므로 불필요).

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_ir/test_graph_cluster.py -v` → 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/ir/graph/ingest/cluster.py tests/test_ir/test_graph_cluster.py
git commit -m "feat(ir/graph): leiden community clustering via igraph"
```

---

### Task 6: 커뮤니티 요약 (summarizer)

**Files:**
- Modify: `app/services/ir/graph/ingest/summarizer.py`
- Create: `tests/test_ir/test_graph_summarizer.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_ir/test_graph_summarizer.py`

```python
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
    monkeypatch.setattr(
        chat_model_module,
        "get_chat_model",
        lambda spec=None: GenericFakeChatModel(messages=iter([AIMessage(content="커뮤니티 리포트")])),
    )

    report = await summarize(Community(id="c0", level=0))

    assert report == "커뮤니티 리포트"
    save_params = [p for p in log if "report" in p]
    assert save_params == [{"id": "c0", "report": "커뮤니티 리포트"}]
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ir/test_graph_summarizer.py -v`
Expected: FAIL — `NotImplementedError("community 요약 미구현")`

- [ ] **Step 3: 구현** — `app/services/ir/graph/ingest/summarizer.py` 전체 교체

```python
"""커뮤니티별 요약(Community Report) 생성.

[Phase 9]
- 커뮤니티 구성 엔티티/내부 관계를 Neo4j 에서 모아 텍스트로 펼친 뒤 LLM 요약.
- Global Search 가 이 리포트를 Map 입력으로 쓰므로 요약 품질 = 거시검색 품질.
- 생성된 리포트는 Community.report 에 저장된다.
"""
from __future__ import annotations

from app.core.graph_db import get_graph_driver
from app.schemas.graph import Community

_FETCH_MEMBERS = """
MATCH (e:Entity)-[:IN_COMMUNITY]->(c:Community {id: $id})
OPTIONAL MATCH (e)-[r:RELATED]-(o:Entity)-[:IN_COMMUNITY]->(c)
RETURN e.name AS name, e.type AS type, e.description AS description,
       collect(DISTINCT e.name + ' -[' + r.type + ']-> ' + o.name) AS relations
"""
_SAVE_REPORT = "MATCH (c:Community {id: $id}) SET c.report = $report"


async def summarize(community: Community) -> str:
    from app.clients.chat_model import get_chat_model
    from app.utils.prompts import load_prompt, render

    entities_text, relations_text = await _fetch_members(community.id)
    prompt = load_prompt("graphrag/community_report")
    resp = await get_chat_model().ainvoke(
        [
            ("system", prompt["system"]),
            ("user", render(prompt["user"], entities=entities_text, relations=relations_text)),
        ]
    )
    report = resp.content if isinstance(resp.content, str) else str(resp.content)
    async with get_graph_driver().session() as session:
        await session.run(_SAVE_REPORT, id=community.id, report=report)
    return report


async def _fetch_members(community_id: str) -> tuple[str, str]:
    """커뮤니티 구성원을 '엔티티 목록 텍스트'와 '관계 목록 텍스트'로 펼친다."""
    entity_lines: list[str] = []
    relation_lines: set[str] = set()
    async with get_graph_driver().session() as session:
        result = await session.run(_FETCH_MEMBERS, id=community_id)
        async for rec in result:
            entity_lines.append(f"- {rec['name']} ({rec['type']}): {rec['description'] or ''}")
            relation_lines.update(r for r in rec["relations"] if r)
    return "\n".join(entity_lines), "\n".join(sorted(relation_lines))
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_ir/test_graph_summarizer.py -v` → 1 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/ir/graph/ingest/summarizer.py tests/test_ir/test_graph_summarizer.py
git commit -m "feat(ir/graph): community report summarizer"
```

---

### Task 7: ingest 오케스트레이션 + 서브그래프 upsert

학습 포인트: MERGE 기반 멱등 적재 (vector 의 uuid5 와 같은 철학). description 은 더 긴 쪽 유지, source_ids 는 누적.

**Files:**
- Modify: `app/services/ir/graph/ingest/__init__.py`
- Create: `tests/test_ir/test_graph_ingest.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_ir/test_graph_ingest.py`

```python
"""ir/graph/ingest: 파이프라인 오케스트레이션(전부 가짜) 테스트."""
from __future__ import annotations

import app.services.ir.graph.ingest as ingest_module
import app.services.ir.graph.ingest.cluster as cluster_module
import app.services.ir.graph.ingest.extractor as extractor_module
import app.services.ir.graph.ingest.summarizer as summarizer_module
from app.schemas.graph import Community, Entity, Relation, Subgraph


async def _fake_ensure_schema():
    return None


def _patch_common(monkeypatch, communities):
    async def _fake_cluster():
        return communities

    monkeypatch.setattr(ingest_module, "ensure_schema", _fake_ensure_schema)
    monkeypatch.setattr(cluster_module, "cluster", _fake_cluster)


async def test_ingest_pipeline_counts_and_flow(monkeypatch):
    calls = {"upsert": 0, "summarize": []}

    async def _fake_extract(text, model=None):
        return Subgraph(
            entities=[Entity(id="서울", name="서울", type="LOCATION")],
            relations=[Relation(source="서울", target="대한민국", type="CAPITAL_OF")],
        )

    async def _fake_upsert(sub, source_id):
        calls["upsert"] += 1

    async def _fake_summarize(com):
        calls["summarize"].append(com.id)
        return "리포트"

    _patch_common(monkeypatch, [Community(id="c0", level=0, entity_ids=["서울", "대한민국"])])
    monkeypatch.setattr(extractor_module, "extract", _fake_extract)
    monkeypatch.setattr(ingest_module, "_upsert_subgraph", _fake_upsert)
    monkeypatch.setattr(summarizer_module, "summarize", _fake_summarize)

    out = await ingest_module.ingest("doc-1", "서울은 대한민국의 수도이다.")

    assert out == {"entities": 1, "relations": 1, "communities": 1}
    assert calls["upsert"] == 1
    assert calls["summarize"] == ["c0"]


async def test_ingest_skips_failed_chunk(monkeypatch):
    async def _boom(text, model=None):
        raise RuntimeError("llm down")

    _patch_common(monkeypatch, [])
    monkeypatch.setattr(extractor_module, "extract", _boom)

    out = await ingest_module.ingest("doc-1", "본문")
    assert out == {"entities": 0, "relations": 0, "communities": 0}


def test_chunk_uses_graph_sizes():
    text = "가" * 3000
    chunks = ingest_module._chunk(text)
    assert len(chunks[0]) == 1200
    assert chunks[1][:100] == chunks[0][-100:]  # 오버랩 100
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ir/test_graph_ingest.py -v`
Expected: FAIL — `AttributeError: ingest` (현재 `__init__.py` 는 docstring 뿐)

- [ ] **Step 3: 구현** — `app/services/ir/graph/ingest/__init__.py` 전체 교체

```python
"""[GraphRAG 컴포넌트] ingest 파이프라인: 청킹 → 추출 → 적재 → 군집 → 요약.

[Phase 9 — 비용 주의] 청크 수 + 커뮤니티 수만큼 LLM 호출이 발생한다.
무거우면 Phase 8 에서 workers/tasks.py 로 옮긴다(vector ingest 와 동일 계획).
"""
from __future__ import annotations

from app.core.graph_db import ensure_schema, get_graph_driver
from app.schemas.graph import Subgraph
from app.utils.logger import get_logger
from app.utils.text import clean_text

logger = get_logger(__name__)

# 추출엔 넓은 문맥이 유리해 vector(800)보다 큰 청크를 쓴다.
_CHUNK_SIZE = 1200
_CHUNK_OVERLAP = 100

_UPSERT_ENTITIES = """
UNWIND $entities AS ent
MERGE (e:Entity {name: ent.name})
SET e.type = ent.type,
    e.description = CASE
        WHEN size(coalesce(ent.description, '')) > size(coalesce(e.description, ''))
        THEN ent.description ELSE e.description END,
    e.source_ids = CASE
        WHEN $source_id IN coalesce(e.source_ids, []) THEN e.source_ids
        ELSE coalesce(e.source_ids, []) + $source_id END
"""

_UPSERT_RELATIONS = """
UNWIND $relations AS rel
MERGE (s:Entity {name: rel.source})
MERGE (t:Entity {name: rel.target})
MERGE (s)-[r:RELATED {type: rel.type}]->(t)
SET r.description = coalesce(rel.description, r.description),
    r.weight = coalesce(rel.weight, 1.0),
    r.source_ids = CASE
        WHEN $source_id IN coalesce(r.source_ids, []) THEN r.source_ids
        ELSE coalesce(r.source_ids, []) + $source_id END
"""


def _chunk(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """고정 길이 슬라이딩 윈도우 (vector/ingest 와 동일 방식, 크기만 다름)."""
    if not text:
        return []
    step = max(1, size - overlap)
    return [text[i : i + size] for i in range(0, len(text), step)]


async def _upsert_subgraph(sub: Subgraph, source_id: str) -> None:
    """추출 결과를 MERGE 로 멱등 적재. 관계의 미선언 엔티티도 MERGE 로 생성된다."""
    async with get_graph_driver().session() as session:
        if sub.entities:
            await session.run(
                _UPSERT_ENTITIES,
                entities=[
                    e.model_dump(include={"name", "type", "description"}) for e in sub.entities
                ],
                source_id=source_id,
            )
        if sub.relations:
            await session.run(
                _UPSERT_RELATIONS,
                relations=[r.model_dump() for r in sub.relations],
                source_id=source_id,
            )


async def ingest(source_id: str, content: str, metadata: dict | None = None) -> dict:
    """문서를 지식그래프로 적재. 반환: 엔티티/관계/커뮤니티 수."""
    from app.services.ir.graph.ingest import cluster as cluster_module
    from app.services.ir.graph.ingest import extractor, summarizer

    await ensure_schema()

    chunks = _chunk(clean_text(content))
    n_entities = n_relations = 0
    for i, chunk in enumerate(chunks):
        try:
            sub = await extractor.extract(chunk)
        except Exception as e:  # noqa: BLE001  한 청크 실패가 전체 적재를 막지 않는다
            logger.warning("graph_extract_skip", chunk_index=i, error=str(e))
            continue
        await _upsert_subgraph(sub, source_id)
        n_entities += len(sub.entities)
        n_relations += len(sub.relations)

    communities = await cluster_module.cluster()
    for com in communities:
        await summarizer.summarize(com)

    logger.info(
        "graph_ingest_done",
        source_id=source_id,
        chunks=len(chunks),
        entities=n_entities,
        relations=n_relations,
        communities=len(communities),
    )
    return {"entities": n_entities, "relations": n_relations, "communities": len(communities)}
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_ir/test_graph_ingest.py -v` → 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/ir/graph/ingest/__init__.py tests/test_ir/test_graph_ingest.py
git commit -m "feat(ir/graph): graph ingest pipeline with idempotent merge upsert"
```

---

### Task 8: Local Search (앵커 풀텍스트 → 1-hop 확장)

**Files:**
- Modify: `app/services/ir/graph/search/local.py`
- Create: `tests/test_ir/test_graph_search.py`

- [ ] **Step 1: 실패 테스트 작성** — `tests/test_ir/test_graph_search.py` (이 파일은 Task 9 에서 global 테스트가 추가된다)

```python
"""ir/graph/search: local(엔티티 카드 조립) + global(map-reduce) 테스트."""
from __future__ import annotations

from app.services.ir.graph.search.local import (
    LocalGraphRetriever,
    build_chunks,
    sanitize_fulltext_query,
)


def _row(name, score, neighbors=None, source_ids=None):
    return {
        "name": name,
        "type": "LOCATION",
        "description": f"{name} 설명",
        "source_ids": source_ids or ["doc-1"],
        "score": score,
        "neighbors": neighbors or [],
    }


def test_sanitize_strips_lucene_specials():
    assert sanitize_fulltext_query('서울+수도 AND "관계"?') == "서울 수도 AND  관계"


def test_build_chunks_normalizes_scores_and_formats_neighbors():
    rows = [
        _row(
            "서울",
            4.0,
            neighbors=[
                {"type": "CAPITAL_OF", "desc": "수도 관계", "other": "대한민국", "other_desc": None}
            ],
        ),
        _row("부산", 2.0),
    ]
    chunks = build_chunks(rows, top_k=5)
    assert chunks[0].score == 1.0 and chunks[1].score == 0.5
    assert "서울 -[CAPITAL_OF]- 대한민국" in chunks[0].content
    assert chunks[0].source_id == "doc-1"
    assert chunks[0].metadata["entity"] == "서울"


def test_build_chunks_respects_top_k():
    chunks = build_chunks([_row("a", 2.0), _row("b", 1.0)], top_k=1)
    assert len(chunks) == 1


async def test_local_retriever_blank_after_sanitize_returns_empty():
    # lucene 특수문자만 있는 질의 → 드라이버 접근 전에 빈 결과
    assert await LocalGraphRetriever().retrieve("?:!*") == []
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ir/test_graph_search.py -v`
Expected: FAIL — `ImportError: build_chunks`

- [ ] **Step 3: 구현** — `app/services/ir/graph/search/local.py` 전체 교체

```python
"""Local Search: 특정 엔티티 주변 이웃 노드 기반 미시적 검색.

[Phase 9 — 동작]
1. 질문을 풀텍스트 인덱스(entity_fulltext)에 던져 앵커 엔티티 top-N 매칭.
   검색 경로 LLM 0회 — 빠르고 저렴 (LLM 엔티티 인식은 Phase 10 analyze 고도화 때).
2. 앵커의 1-hop 이웃/관계를 모아 "엔티티 카드" 텍스트로 RetrievedChunk 조립.
3. score 는 lucene 점수를 최댓값으로 정규화(0~1), 출처는 엔티티 source_ids.
"""
from __future__ import annotations

import re

from app.core.graph_db import get_graph_driver
from app.services.ir.base import RetrievedChunk, Retriever

_ANCHORS = 3  # 질문당 앵커 엔티티 수

# lucene 쿼리 파싱 에러를 막기 위한 특수문자 제거
_LUCENE_SPECIALS = re.compile(r'[+\-&|!(){}\[\]^"~*?:\\/]')

_LOCAL_QUERY = """
CALL db.index.fulltext.queryNodes('entity_fulltext', $q) YIELD node, score
WITH node, score ORDER BY score DESC LIMIT $anchors
OPTIONAL MATCH (node)-[r:RELATED]-(nb:Entity)
RETURN node.name AS name, node.type AS type, node.description AS description,
       node.source_ids AS source_ids, score,
       collect({type: r.type, desc: r.description, other: nb.name,
                other_desc: nb.description}) AS neighbors
ORDER BY score DESC
"""


def sanitize_fulltext_query(query: str) -> str:
    """lucene 특수문자를 공백으로 치환 (global_ 도 같이 쓴다)."""
    return _LUCENE_SPECIALS.sub(" ", query).strip()


class LocalGraphRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        q = sanitize_fulltext_query(query)
        if not q:
            return []
        async with get_graph_driver().session() as session:
            result = await session.run(_LOCAL_QUERY, q=q, anchors=_ANCHORS)
            rows = [dict(rec) async for rec in result]
        return build_chunks(rows, top_k)


def build_chunks(rows: list[dict], top_k: int) -> list[RetrievedChunk]:
    """앵커별 '엔티티 카드' 텍스트 조립. (순수 함수 — 단위 테스트 대상)"""
    if not rows:
        return []
    max_score = max(r["score"] for r in rows) or 1.0
    chunks = []
    for row in rows[:top_k]:
        lines = [f"{row['name']} ({row['type']}): {row['description'] or ''}"]
        for nb in row["neighbors"]:
            if nb.get("other"):
                lines.append(
                    f"- {row['name']} -[{nb['type']}]- {nb['other']}: "
                    f"{nb.get('desc') or nb.get('other_desc') or ''}"
                )
        source_ids = row.get("source_ids") or []
        chunks.append(
            RetrievedChunk(
                content="\n".join(lines),
                score=row["score"] / max_score,
                source_id=source_ids[0] if source_ids else row["name"],
                metadata={"engine": "graph_local", "entity": row["name"]},
            )
        )
    return chunks
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_ir/test_graph_search.py -v` → 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/ir/graph/search/local.py tests/test_ir/test_graph_search.py
git commit -m "feat(ir/graph): local graph search via fulltext anchors + 1-hop expansion"
```

---

### Task 9: Global Search (커뮤니티 리포트 Map-Reduce)

학습 포인트: Map(리포트별 부분답변)은 retriever 안에서 `asyncio.gather` 동시 실행, Reduce(통합 답변)는 기존 generate 노드가 자연 수행 — Retriever 인터페이스를 유지하는 절충.

**Files:**
- Modify: `app/services/ir/graph/search/global_.py`
- Modify: `tests/test_ir/test_graph_search.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_ir/test_graph_search.py` 끝에 append

```python
# ── Global Search ────────────────────────────────────────────────────

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

import app.clients.chat_model as chat_model_module  # noqa: E402
import app.services.ir.graph.search.global_ as global_module  # noqa: E402
from app.services.ir.graph.search.global_ import GlobalGraphRetriever  # noqa: E402


async def test_global_retriever_maps_filters_and_normalizes(monkeypatch):
    reports = [
        {"id": "c0", "report": "리포트0", "score": 2.0},
        {"id": "c1", "report": "리포트1", "score": 1.0},
    ]
    answers = {"리포트0": "부분답변0", "리포트1": "관련 없음"}

    async def _fake_fetch(query, top_k):
        return reports

    async def _fake_map(query, report):
        return answers[report]

    monkeypatch.setattr(global_module, "_fetch_reports", _fake_fetch)
    monkeypatch.setattr(global_module, "_map_one", _fake_map)

    chunks = await GlobalGraphRetriever().retrieve("전체 주제는?")

    assert len(chunks) == 1  # "관련 없음" 은 버려진다
    assert chunks[0].content == "부분답변0"
    assert chunks[0].score == 1.0  # 최댓값 정규화
    assert chunks[0].source_id == "community:c0"
    assert chunks[0].metadata["engine"] == "graph_global"


async def test_global_retriever_empty_without_reports(monkeypatch):
    async def _fake_fetch(query, top_k):
        return []

    monkeypatch.setattr(global_module, "_fetch_reports", _fake_fetch)
    assert await GlobalGraphRetriever().retrieve("질문") == []


async def test_map_one_calls_llm_with_prompt(monkeypatch):
    monkeypatch.setattr(
        chat_model_module,
        "get_chat_model",
        lambda spec=None: GenericFakeChatModel(messages=iter([AIMessage(content="부분답변")])),
    )
    assert await global_module._map_one("질문", "리포트") == "부분답변"
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ir/test_graph_search.py -v`
Expected: 기존 4개 PASS + 신규 3개 FAIL (`NotImplementedError("graph global search 미구현")`)

- [ ] **Step 3: 구현** — `app/services/ir/graph/search/global_.py` 전체 교체

```python
"""Global Search: 커뮤니티 요약 Map-Reduce 기반 거시적 검색.

[Phase 9 — 동작]
1. 질문 관련 커뮤니티 리포트 top-k 선택 (community_fulltext 인덱스).
2. Map: 리포트별 LLM 부분답변 (asyncio.gather 동시 실행, "관련 없음" 은 버림).
3. 부분답변들을 RetrievedChunk 로 반환 → Reduce 는 generate 노드가 수행
   (컨텍스트 통합 답변 = reduce. Retriever 인터페이스를 유지하는 절충).
- 비용: 질문당 LLM ≤ top_k 회 (+generate 1회).
- 파일명이 global_.py 인 이유: 'global' 은 파이썬 예약어라 import 불가.
"""
from __future__ import annotations

import asyncio

from app.core.graph_db import get_graph_driver
from app.services.ir.base import RetrievedChunk, Retriever
from app.services.ir.graph.search.local import sanitize_fulltext_query

_NOT_RELEVANT = "관련 없음"

_REPORT_QUERY = """
CALL db.index.fulltext.queryNodes('community_fulltext', $q) YIELD node, score
RETURN node.id AS id, node.report AS report, score
ORDER BY score DESC LIMIT $top_k
"""


class GlobalGraphRetriever(Retriever):
    async def retrieve(self, query: str, top_k: int = 5, **kwargs) -> list[RetrievedChunk]:
        reports = await _fetch_reports(query, top_k)
        if not reports:
            return []
        partials = await asyncio.gather(*(_map_one(query, r["report"]) for r in reports))
        kept = [
            (r, p)
            for r, p in zip(reports, partials, strict=True)
            if p and p.strip() != _NOT_RELEVANT
        ]
        if not kept:
            return []
        max_score = max(r["score"] for r, _ in kept) or 1.0
        return [
            RetrievedChunk(
                content=partial,
                score=report["score"] / max_score,
                source_id=f"community:{report['id']}",
                metadata={"engine": "graph_global", "community_id": report["id"]},
            )
            for report, partial in kept
        ]


async def _fetch_reports(query: str, top_k: int) -> list[dict]:
    q = sanitize_fulltext_query(query)
    if not q:
        return []
    async with get_graph_driver().session() as session:
        result = await session.run(_REPORT_QUERY, q=q, top_k=top_k)
        return [dict(rec) async for rec in result if rec["report"]]


async def _map_one(query: str, report: str) -> str:
    """Map 단계: 리포트 1개 → 질문에 대한 부분답변 (무관하면 '관련 없음')."""
    from app.clients.chat_model import get_chat_model
    from app.utils.prompts import load_prompt, render

    prompt = load_prompt("graphrag/global_search")
    resp = await get_chat_model().ainvoke(
        [
            ("system", prompt["system"]),
            ("user", render(prompt["user"], query=query, report=report)),
        ]
    )
    return resp.content if isinstance(resp.content, str) else str(resp.content)
```

- [ ] **Step 4: 통과 확인**

Run: `uv run pytest tests/test_ir/test_graph_search.py -v` → 7 passed

- [ ] **Step 5: Commit**

```bash
git add app/services/ir/graph/search/global_.py tests/test_ir/test_graph_search.py
git commit -m "feat(ir/graph): global graph search with community report map-reduce"
```

---

### Task 10: 워크플로/엔드포인트 연결 (rag_mode 분기 + IngestTarget.GRAPH)

**Files:**
- Modify: `app/services/workflow/nodes/retrieve.py`
- Modify: `app/api/v1/endpoints/document.py`
- Modify: `tests/test_graph/test_workflow.py` (테스트 추가)
- Modify: `tests/test_api/test_document.py` (테스트 추가)

- [ ] **Step 1: 실패 테스트 추가** — `tests/test_graph/test_workflow.py` 의 "노드 단위" 섹션에 append

```python
async def test_retrieve_node_routes_graph_local(monkeypatch):
    import app.services.ir.graph.search.local as local_module

    monkeypatch.setattr(local_module, "LocalGraphRetriever", lambda: _FakeRetriever([_chunk()]))
    out = await retrieve({"query": "수도?", "top_k": 5, "rag_mode": "graph_local"})
    assert out["citations"][0]["source_id"] == "doc-1"


async def test_retrieve_node_routes_graph_global(monkeypatch):
    import app.services.ir.graph.search.global_ as global_module

    monkeypatch.setattr(global_module, "GlobalGraphRetriever", lambda: _FakeRetriever([_chunk()]))
    out = await retrieve({"query": "요지?", "top_k": 5, "rag_mode": "graph_global"})
    assert out["documents"][0]["score"] == 0.9
```

— `tests/test_api/test_document.py` 끝에 append:

```python
def test_ingest_calls_graph_ingest(monkeypatch):
    import app.services.ir.graph.ingest as graph_ingest_module

    async def _fake_graph_ingest(source_id, content, metadata=None):
        return {"entities": 4, "relations": 2, "communities": 1}

    monkeypatch.setattr(graph_ingest_module, "ingest", _fake_graph_ingest)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/ingest",
        json={"source_id": "doc-1", "content": "hello", "targets": ["graph"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["graph_entities"] == 4
    assert body["graph_relations"] == 2
    assert body["graph_communities"] == 1
    assert "vector_chunks" not in body  # graph 만 지정 시 vector 는 건너뜀


def test_graph_ingest_failure_returns_503(monkeypatch):
    import app.services.ir.graph.ingest as graph_ingest_module

    async def _boom(source_id, content, metadata=None):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(graph_ingest_module, "ingest", _boom)

    client = TestClient(app)
    resp = client.post(
        "/api/v1/documents/ingest",
        json={"source_id": "doc-1", "content": "hello", "targets": ["graph"]},
    )
    assert resp.status_code == 503
```

- [ ] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_graph/test_workflow.py tests/test_api/test_document.py -v`
Expected: 신규 4개 FAIL (retrieve 가 vector 로만 가고, endpoint 는 graph 키 미반환)

- [ ] **Step 3: retrieve 노드 분기 구현** — `app/services/workflow/nodes/retrieve.py` 의 retriever 선택부를 다음으로 교체 (docstring 의 `[추후]` 줄도 갱신)

docstring 9행을 다음으로 교체:

```python
[Phase 9] rag_mode 로 graph_local/graph_global 분기. auto/hybrid 라우팅은 Phase 10.
```

retriever 선택 블록(기존 `retriever: Retriever` ~ `retriever = vsearch.VectorRetriever()`)을 교체:

```python
    rag_mode = state.get("rag_mode", "auto")
    retriever: Retriever
    if settings.MOCK_RETRIEVER:
        from app.services.ir.mock import MockRetriever

        retriever = MockRetriever()
    elif rag_mode == "graph_local":
        from app.services.ir.graph.search.local import LocalGraphRetriever

        retriever = LocalGraphRetriever()
    elif rag_mode == "graph_global":
        from app.services.ir.graph.search.global_ import GlobalGraphRetriever

        retriever = GlobalGraphRetriever()
    else:  # vector / auto / hybrid → 기존 vector 경로 (auto·hybrid 분기는 Phase 10)
        retriever = vsearch.VectorRetriever()
```

같은 함수의 로그 한 줄도 rag_mode 가 보이게 교체:

```python
    logger.info("node_retrieve_start", top_k=top_k, rag_mode=rag_mode, mock=settings.MOCK_RETRIEVER)
```

> Neo4j 다운 시: 기존 `try/except` 가 검색 실패를 비치명 처리하므로 추가 코드 불필요 (채팅은 컨텍스트 없이 생존).

- [ ] **Step 4: 엔드포인트 연결** — `app/api/v1/endpoints/document.py` 의 `# IngestTarget.GRAPH → Phase 9` 주석을 다음으로 교체. 모듈 docstring 의 "graph target 은 Phase 9 에서 연결." 줄은 "graph target 은 ir/graph/ingest 파이프라인을 직접 await 한다(Phase 8 에서 워커 이관)." 로 갱신.

```python
    if IngestTarget.GRAPH in payload.targets:
        from app.services.ir.graph.ingest import ingest as graph_ingest

        try:
            g = await graph_ingest(payload.source_id, payload.content, payload.metadata)
        except Exception as e:  # noqa: BLE001  적재는 그래프 없이는 무의미 → 명시 에러
            raise HTTPException(status_code=503, detail=f"graph 적재 실패: {e}") from e
        result["graph_entities"] = g["entities"]
        result["graph_relations"] = g["relations"]
        result["graph_communities"] = g["communities"]
```

- [ ] **Step 5: 통과 확인**

Run: `uv run pytest tests/test_graph/test_workflow.py tests/test_api/test_document.py -v`
Expected: 전부 PASS (기존 + 신규 4개)

- [ ] **Step 6: Commit**

```bash
git add app/services/workflow/nodes/retrieve.py app/api/v1/endpoints/document.py tests/test_graph/test_workflow.py tests/test_api/test_document.py
git commit -m "feat(phase9): wire graph rag into retrieve node + ingest endpoint"
```

---

### Task 11: 페이즈 마감 — 전체 검증 + 문서화

**Files:**
- Create: `docs/phases/phase-9.md`
- Modify: `README.md` (Phase 9 항목 `[x]`, "*(다음 차례)*" 제거, 의존 다이어그램의 `← 다음` 을 P10 으로 이동)
- Modify: `CHANGELOG.md` (phase 9 섹션 추가 — 기존 phase 섹션 형식을 따른다)

- [ ] **Step 1: 전체 검증 (페이즈 경계 — 여기서만 풀 스위트)**

```bash
make lint   # ruff 통과
make type   # mypy 통과 (igraph/leidenalg/neo4j 는 ignore_missing_imports=true)
make test   # 전체 pytest 통과 — 외부 인프라(Neo4j/LLM) 없이
```

Expected: 모두 초록불. 실패 시 고치고 재실행 (이 단계를 통과해야 커밋).

- [ ] **Step 2: phase-9.md 작성** — `docs/phases/phase-7.md` 의 구조(목표/했던 일/검증/배운 점)를 그대로 따라, 이번 페이즈의 내용을 기록한다. 포함할 것: 5단계 파이프라인 표(①~⑤), 설계 결정 3가지(igraph+leidenalg / 풀텍스트 앵커 / Map-Reduce 절충)와 이유, 비용 특성(인덱싱 = 청크+커뮤니티 수만큼 LLM 호출), 비범위(계층 커뮤니티, auto 라우팅은 P10). 설계 문서(`docs/superpowers/specs/2026-06-05-phase9-graphrag-design.md`) 링크.

- [ ] **Step 3: README 로드맵 갱신**

`### Phase 9 — GraphRAG 파이프라인 추가 *(다음 차례)*` → `### [x] Phase 9 — GraphRAG 파이프라인 추가`
의존 다이어그램의 `└ P9 GraphRAG ── P10 라우팅/하이브리드   ← 다음` 줄에서 P9 를 완료로, `← 다음` 을 P10 쪽으로 옮긴다.

- [ ] **Step 4: Commit**

```bash
git add docs/phases/phase-9.md README.md CHANGELOG.md
git commit -m "docs(phases): record phase 9 graphrag pipeline"
```

---

### Task 12: 수동 통합 검증 (실 Neo4j + 실 LLM) — 커밋 없음

README 🔍 검증 항목. 자동화 대상이 아니므로 체크리스트만 수행한다.

- [ ] **Step 1: 인프라 기동**

```bash
docker compose up -d neo4j
uv run uvicorn app.main:app --reload
```

`.env` 확인: `GRAPH_DB_URI=bolt://localhost:7687`, `GRAPH_DB_USER/PASSWORD`, `ANTHROPIC_API_KEY` 채워져 있어야 함.

- [ ] **Step 2: 그래프 적재** (Swagger `/docs` 또는 curl)

```bash
curl -s -X POST http://localhost:8000/api/v1/documents/ingest -H "Content-Type: application/json" -d "{\"source_id\":\"graph-test-1\",\"content\":\"니체화학의 김철수 대표는 2020년 부산에 연구소를 세웠다. 연구소는 친환경 촉매를 개발했고, 박영희 박사가 개발을 이끌었다. 니체화학은 2023년 서울증권거래소에 상장했다.\",\"targets\":[\"graph\"]}"
```

Expected: `{"status":"ingested", ..., "graph_entities": N>0, "graph_relations": M>0, "graph_communities": K>0}`. Neo4j Browser(`http://localhost:7474`)에서 `MATCH (n) RETURN n LIMIT 50` 으로 그래프 확인.

- [ ] **Step 3: 관계형 질문 → graph_local**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"question\":\"박영희 박사는 어느 회사와 관련이 있나?\",\"rag_mode\":\"graph_local\",\"stream\":false}"
```

Expected: 니체화학/연구소 관계가 답변에 등장, `citations` 의 source 가 `graph-test-1` 또는 엔티티명, `rag_mode: "graph_local"`.

- [ ] **Step 4: 거시 질문 → graph_global**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"question\":\"이 문서들의 전체 내용을 요약해줘\",\"rag_mode\":\"graph_global\",\"stream\":false}"
```

Expected: 커뮤니티 리포트 기반 종합 답변, citations 의 source 가 `community:c*`.

- [ ] **Step 5: 회귀 확인** — `rag_mode:"vector"` 로 기존 vector 질문이 그대로 동작 + **Neo4j 컨테이너를 내리고** graph_local 질문 시 채팅이 죽지 않고 "모른다" 류 답변(우아한 강등) 확인.

```bash
docker compose stop neo4j
curl -s -X POST http://localhost:8000/api/v1/chat -H "Content-Type: application/json" -d "{\"question\":\"박영희 박사는?\",\"rag_mode\":\"graph_local\",\"stream\":false}"
```

Expected: HTTP 200 + 컨텍스트 없음 답변 (5xx 가 아님). 로그에 `node_retrieve_skip reason=error`.

---

## Self-Review 결과 (작성 시 수행)

- **스펙 커버리지**: 설계 §2(아키텍처 파일 전부) → Task 2~10 / §3(스키마) → Task 3·7 / §4(인덱싱) → Task 4~7 / §5(검색+노드 분기) → Task 8~10 / §6(에러) → Task 7(청크 스킵)·10(503, 비치명) / §7(테스트) → 각 태스크 + Task 11~12. 누락 없음.
- **플레이스홀더**: 없음 (모든 코드/명령 명시).
- **타입 일관성**: `ingest()` 반환 dict 키(entities/relations/communities) ↔ endpoint 매핑 일치, `sanitize_fulltext_query` 이름 local/global 공유 일치, `Community.id`/`compute_communities` 시그니처 일치 확인.
