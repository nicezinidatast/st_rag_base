# Phase 9 — GraphRAG 파이프라인 추가

- **커밋:** _(미커밋, 작업 트리)_
- **목표:** 엔티티/관계 그래프 기반 검색(`graph_local` / `graph_global`)을 Vector RAG 옆에 추가한다.
  Vector 모드는 그대로 둔 채 *옆에* 쌓는다. Phase 8 워커 이관 전이므로 Phase 3 와 같이 엔드포인트에서 직접 실행.
- **검증:** `pytest` 83 passed (신규 17: graph_db 2 / extractor 2 / cluster 2 / summarizer 1 /
  ingest 3 / search 7 / prompts 3). ruff / mypy 통과.
  수동 E2E: Neo4j 기동 → 문서 GRAPH 적재 → `graph_local` 관계형 질의 / `graph_global` 요지 질의 응답 확인.

> **설계 문서:** `docs/superpowers/specs/2026-06-05-phase9-graphrag-design.md`

---

## 파이프라인 5단계

| 단계 | 모듈 | 역할 |
|------|------|------|
| ① graph_db | `core/graph_db.py` | Neo4j AsyncDriver + 스키마 부트스트랩(인덱스/제약) |
| ② extractor | `ir/graph/ingest/extractor.py` | LLM 구조화 추출(엔티티 목록, 관계 삼중항) |
| ③ cluster | `ir/graph/ingest/cluster.py` | igraph + leidenalg Leiden 알고리즘으로 커뮤니티 탐지 |
| ④ summarizer | `ir/graph/ingest/summarizer.py` | 커뮤니티 멤버 목록 → LLM 커뮤니티 리포트 생성 |
| ⑤ search | `ir/graph/search/local.py`, `global_.py` | 앵커 기반 서브그래프(local) / Map-Reduce 요약(global) |

---

## A. Neo4j 드라이버 + 스키마 (`core/graph_db.py`)

`get_graph_driver()`: `NEO4J_URI` 기반 `AsyncGraphDatabase.driver` lru_cache 반환. `NEO4J_URI` 미설정 시 `None`(graceful).

`bootstrap_schema(driver)`: 서버 기동 시 1회 실행. 생성 대상:
- **노드 제약:** `Entity.id` UNIQUE, `Community.id` UNIQUE
- **관계 타입:** `:RELATED{type, weight}`, `:IN_COMMUNITY`
- **풀텍스트 인덱스 2종:**
  - `entity_name_idx` — `Entity.name`
  - `entity_desc_idx` — `Entity.description`

MERGE 기반 멱등 적재: 동일 `id` 재실행 시 `description` 은 긴 쪽을 유지, `source_ids` 는 누적.

---

## B. 엔티티/관계 추출기 (`ir/graph/ingest/extractor.py`)

`extract_entities_and_relations(chunks, llm)`: 청크 배치 → LLM JSON 추출.

반환 스키마:
```python
entities: list[{id, name, type, description}]
relations: list[{source_id, target_id, type, weight}]
```

`weight` 기본값 1.0 — 재적재 시 덮어쓰기(백로그: 누적 += 이 첫 튜닝 노브).

---

## C. Leiden 군집화 (`ir/graph/ingest/cluster.py`)

`cluster_entities(driver)`: Neo4j 에서 (entity_id, neighbor_id, weight) 엣지 전체 적재 →
`igraph.Graph` 구성 → `leidenalg.find_partition(ModularityVertexPartition)` 실행.

**설계 결정 1 — Leiden 을 Python(igraph+leidenalg)에서 실행:**
- Neo4j GDS 플러그인·graspologic 에 비해 의존성이 가볍고 로직이 코드 안에서 보인다.
- 학습·디버깅·커스터마이징이 쉽고, Neo4j 는 순수 저장소 역할만 유지.
- GDS 커뮤니티 에디션은 기능 제약 있음.

결과 커뮤니티 id → Neo4j `Community` 노드 + `:IN_COMMUNITY` 관계로 MERGE 적재.

---

## D. 커뮤니티 요약 (`ir/graph/ingest/summarizer.py`)

`summarize_communities(driver, llm)`: 커뮤니티별 멤버 엔티티 목록 조회 → LLM 리포트 생성 →
`Community.report` 프로퍼티 갱신.

비용 특성: 커뮤니티 수만큼 LLM 호출. 인덱싱 전체 비용 = 청크 수(추출) + 커뮤니티 수(요약).

---

## E. Local Search (`ir/graph/search/local.py`)

`LocalSearchRetriever.retrieve(query)`:

1. Neo4j 풀텍스트 인덱스(`entity_name_idx`) 로 앵커 엔티티 탐색 — LLM 0회.
2. 앵커에서 1-hop 이웃 서브그래프 추출.
3. 엔티티+관계 텍스트를 컨텍스트로 반환.

**설계 결정 2 — 앵커 식별 = Neo4j 풀텍스트 인덱스:**
- LLM 추출·임베딩 유사도 없이 쿼리 → Neo4j 인덱스 직접 조회 → 검색 경로 LLM 0회.
- 빠르고 결정론적. Lucene 파서 특이사항: 질의에 대문자 `AND`/`OR` 잔존 시 연산자로 해석 가능(백로그).

비용: 인덱스 조회 + 그래프 순회만, LLM 호출 없음.

---

## F. Global Search (`ir/graph/search/global_.py`)

`GlobalSearchRetriever.retrieve(query)`:

1. 상위 커뮤니티 리포트 top_k 개 조회.
2. `asyncio.gather` 로 각 리포트에 대해 Map 단계: 질의와 관련 있는지 + 관련 요약 생성.
   - 반환값이 "관련 없음" 센티넬이면 제외(백로그: 구두점 변형 강건화 여지).
3. 관련 리포트 필터링 후 Reduce 단계: `generate` 노드에 위임해 최종 답변 합성.

**설계 결정 3 — Global = Map(retriever 내 gather)-Reduce(generate 노드 위임):**
- Retriever 인터페이스를 깨지 않고 Map 까지 흡수, Reduce 는 기존 generate 노드 재사용.
- `asyncio.gather` 는 fail-fast(백로그: `return_exceptions=True` 로 부분 실패 허용 가능).

비용: `graph_global` 검색 = ≤ top_k+1 회 LLM 호출.

---

## G. Ingest 오케스트레이션 (`ir/graph/ingest/__init__.py`)

`ingest_graph(source_id, content, llm, driver)`:

```
extract → cluster → summarize
```

MERGE 멱등: 동일 문서 재적재 안전. `source_ids` 누적 누락 없음.

`document.py` 의 `target=GRAPH` 분기에서 직접 호출(Phase 3 와 같은 패턴, 워커 이관은 Phase 8).

---

## H. retrieve 노드 분기 + 엔드포인트 연결

`workflow/nodes/retrieve.py`: `rag_mode` 기반 분기.
- `"vector"` → `VectorRetriever`
- `"graph_local"` → `LocalSearchRetriever`
- `"graph_global"` → `GlobalSearchRetriever`
- `"auto"` / `"hybrid"` → Phase 10 에서 구현(현재는 vector 로 동작, rag_mode 는 요청값 에코 — Phase 10 백로그).

`document.py`: `target` 필드 추가(`VECTOR` | `GRAPH`). `GRAPH` 이면 `ingest_graph` 호출.

---

## I. 프롬프트 로더 + GraphRAG 프롬프트 (`utils/prompts.py`, `config/prompts/graphrag/`)

`load_prompt(name)`: YAML 파일에서 `system`/`user` 로드, `str.format_map()` 변수 치환. LRU 캐시.

프롬프트 파일 3종:
- `extract.yaml` — 엔티티/관계 JSON 추출
- `summarize.yaml` — 커뮤니티 멤버 → 리포트
- `map_community.yaml` — 커뮤니티 관련성 판단 + 요약

---

## J. 우아한 강등 (Graceful Degradation)

- **채팅 검색:** Neo4j 다운 시 빈 컨텍스트로 채팅 생존(`retrieve` 노드 기존 `try/except`).
- **문서 적재:** Neo4j 미연결 시 503 명시 에러 반환(빈 응답 대신 원인 노출).

Phase 6 Redis · Phase 7 Postgres 의 graceful 강등 철학 일관.

---

## K. 의존성 추가

- `igraph` — 그래프 자료구조 + 알고리즘
- `leidenalg` — Leiden 커뮤니티 탐지

---

## L. 비범위 (Out of Scope)

- 계층형 커뮤니티(level > 0)
- 엔티티 임베딩 앵커 (풀텍스트 인덱스로 충분)
- `auto` / `hybrid` 라우팅 (Phase 10)
- 워커 이관 (Phase 8)

---

## 백로그 (리뷰 후속 개선 후보)

1. **`r.weight` 재적재 시 1.0 덮어쓰기** — 군집 품질 아쉬우면 누적(`+=`) 이 첫 튜닝 노브.
2. **`global` 의 `asyncio.gather` fail-fast** — 부분 실패 허용하려면 `return_exceptions=True`.
3. **"관련 없음" 센티넬 완전일치** — 구두점 변형("관련 없음.") 강건화 여지.
4. **질의 Lucene 파서 충돌** — 대문자 `AND`/`OR` 잔존 시 풀텍스트 인덱스 파스 에러 가능성.
5. **`hybrid` 요청 시 vector 로 동작** — `rag_mode` 는 요청값 에코. Phase 10 에서 해소.

---

## 수동 검증 절차 (Neo4j 필요)

```bash
docker compose up -d neo4j
# .env: NEO4J_URI=bolt://localhost:7687 로 설정 후 make dev

# 문서 적재 (GRAPH 타겟)
curl -X POST localhost:8000/api/v1/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_id":"doc1","content":"Alice 와 Bob 은 협력 관계다. Bob 은 Acme 소속이다.","target":"GRAPH"}'

# local search: 관계형 질문
curl -X POST localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"Alice 와 Bob 의 관계는?","rag_mode":"graph_local","stream":false}'

# global search: 요지 질문
curl -X POST localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"question":"문서의 주요 관계를 요약해줘","rag_mode":"graph_global","stream":false}'
```
