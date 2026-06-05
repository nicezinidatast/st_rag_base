# Phase 9 — GraphRAG 파이프라인 설계 (2026-06-05)

> 학습 목적을 겸한 설계 문서. 각 결정의 "왜"를 함께 기록한다.
> 관련 로드맵: `README.md` Phase 9 · 스켈레톤: `app/services/ir/graph/`

## 0. 배경 — GraphRAG 란

Vector RAG(Phase 3)는 "질문과 의미가 비슷한 청크"를 찾는다. 그래서 두 유형의 질문에 약하다:

1. **관계형 질문** — "A 회사의 CEO 가 투자한 스타트업은?"
   답이 여러 문서에 흩어진 *관계의 연쇄*라서 유사도 검색으로 못 찾음.
2. **거시적 질문** — "이 문서 전체의 핵심 주제는?"
   답이 특정 청크에 *없음*. 전체를 조망해야 함.

GraphRAG(Microsoft, 2024)는 문서를 미리 **지식그래프**로 변환해 두고,
질문 유형에 따라 그래프를 다르게 탐색한다:

- **Local Search** → 관계형 질문: 엔티티 이웃 확장
- **Global Search** → 거시 질문: 커뮤니티 요약 Map-Reduce

## 1. 확정된 설계 결정 (Q&A 결과)

| 결정 | 선택 | 이유 |
|---|---|---|
| 추출용 LLM | `DEFAULT_CHAT_MODEL` 재사용 (haiku) | 설정 추가 없이 단순, 학습/MVP 충분 |
| Leiden 군집화 | **Python igraph + leidenalg** | 로직이 우리 코드에 보여 학습에 유리, Neo4j 를 순수 저장소로 유지(교체 가능성 원칙). 단일 레벨부터 시작, 계층화는 후속. (대안: Neo4j GDS — 블랙박스+종속성↑ / graspologic — 의존성 무거움) |
| 앵커 엔티티 식별 | **Neo4j 풀텍스트 인덱스** | 검색 경로 LLM 0회 → 빠르고 저렴. (대안: LLM 추출 선행 — Phase 10 analyze 고도화 때 업그레이드 가능) |
| Global Reduce | **기존 generate 노드에 위임** | Map(리포트별 부분답변)은 retriever 안에서, Reduce(통합)는 generate 노드가 자연 수행 → Retriever 인터페이스 유지 |

## 2. 아키텍처 (변경 파일)

```
core/graph_db.py              드라이버 싱글톤 + 제약/인덱스 보장          [구현]
ir/graph/ingest/__init__.py   ingest() 오케스트레이션 (추출→군집→요약)    [신규 함수]
ir/graph/ingest/extractor.py  LLM 추출 → Subgraph                        [구현]
ir/graph/ingest/cluster.py    Neo4j→igraph→leidenalg→Community           [구현]
ir/graph/ingest/summarizer.py 커뮤니티 → LLM 요약 리포트                 [구현]
ir/graph/search/local.py      앵커 풀텍스트 매칭 → 1-hop 확장            [구현]
ir/graph/search/global_.py    리포트 Map-Reduce                          [구현]
utils/prompts.py              YAML 프롬프트 로더 (신규 — graphrag 4종)
workflow/nodes/retrieve.py    rag_mode 분기 (graph_local/graph_global)
endpoints/document.py         IngestTarget.GRAPH 연결
pyproject.toml                igraph, leidenalg 추가
```

- 새 설정 0개 (`GRAPH_DB_URI/USER/PASSWORD` 이미 존재)
- 새 스키마 0개 (`schemas/graph.py` 의 Entity/Relation/Subgraph/Community 그대로)

## 3. Neo4j 스키마

```cypher
(:Entity {name*, type, description, source_ids: []})
(:Entity)-[:RELATED {type, description, weight, source_ids: []}]->(:Entity)
(:Community {id*, level, report})
(:Entity)-[:IN_COMMUNITY]->(:Community)

* 유니크 제약
+ 풀텍스트 인덱스 entity_fulltext ON (Entity.name, Entity.description)
```

**설계 이유 3가지 (학습 포인트):**

1. **관계 타입을 엣지 속성으로** (`[:RELATED {type: "CEO_OF"}]`)
   Cypher 는 엣지 라벨을 파라미터화할 수 없다. LLM 이 만들어내는 무한한
   관계 타입을 라벨로 쓰면 쿼리가 불가능 → 단일 라벨 + `type` 속성이 실무 표준 절충안.
2. **MERGE 기반 멱등 적재**
   vector 의 uuid5 와 같은 철학 — 같은 문서를 재적재해도 중복 노드가 안 생긴다.
   엔티티 키는 정규화된 `name`. 재등장 시 description 은 더 긴(정보 많은) 쪽 유지.
3. **커뮤니티도 그래프 안에**
   별도 저장소 없이 `IN_COMMUNITY` 엣지로 연결 → "이 엔티티가 속한 커뮤니티의
   리포트" 같은 질의가 Cypher 한 번에 가능.

## 4. 인덱싱 플로 (`POST /documents/ingest`, targets=["graph"])

```
content
 → ① 청킹: 그래프용 1200자/100 오버랩 (추출엔 넓은 문맥이 유리, vector 의 800과 독립)
 → ② 청크별 extractor.extract():
      chat_model.with_structured_output(Subgraph) 로 LLM 이 곧장
      검증된 Pydantic 객체 반환 (JSON 파싱 코드 불필요 — LangChain 기능)
 → ③ MERGE 로 Neo4j 적재 (엔티티/관계, source_ids 누적)
 → ④ cluster(): 전체 그래프를 igraph 로 로드 → leidenalg → Community 노드 갱신
 → ⑤ summarizer: 커뮤니티마다 LLM 요약 → report 저장
응답: {"graph_entities": N, "graph_relations": M, "graph_communities": K}
```

- 비용 주의: 인덱싱은 청크 수 + 커뮤니티 수만큼 LLM 호출 (10페이지 ≈ 30~50회).
- ④⑤는 문서 하나가 아니라 **전체 그래프 대상 재실행** (커뮤니티는 전역 개념).
  소규모 코퍼스에선 문제없음. 느려지면 Phase 8 워커로 이관 (README 계획 그대로).

## 5. 검색 플로

### Local Search (관계형 질문) — 검색 경로 LLM 0회

```
질문 → 풀텍스트 인덱스로 앵커 엔티티 top-3
     → 1-hop 이웃 + 관계 Cypher 조회
     → "엔티티/관계 설명 텍스트"를 RetrievedChunk 로 조립
       (score = 풀텍스트 점수 정규화, source_id = 원문 문서 id)
```

### Global Search (거시 질문) — Map-Reduce

```
질문 → 관련 커뮤니티 리포트 top-k 선택 (리포트 풀텍스트 매칭)
     → Map: 리포트별 LLM 부분답변 (asyncio.gather 동시 실행, ≤ top_k 회 호출)
     → 부분답변들을 RetrievedChunk 로 반환
     → Reduce: 기존 generate 노드가 컨텍스트 통합 답변으로 자연 수행
```

### 워크플로 연결

`workflow/nodes/retrieve.py` 에 분기 추가:
- `rag_mode == "graph_local"` → `LocalGraphRetriever`
- `rag_mode == "graph_global"` → `GlobalGraphRetriever`
- 그 외(vector/auto/hybrid) → 기존 vector 경로 (auto/hybrid 분기는 Phase 10)

## 6. 에러 처리

- **검색 시 Neo4j 다운**: retrieve 노드의 기존 try/except 가 비치명 처리 →
  컨텍스트 없이 채팅 생존 (Phase 6 Redis 우아한 강등과 동일 철학).
- **적재 시 Neo4j 다운**: 503 명시 에러 (적재는 그래프 없이는 무의미).
- **추출 실패 청크**: 해당 청크만 스킵하고 계속 (부분 성공 허용), 로그 경고.

## 7. 테스트 전략

- **pytest (외부 의존 없이 통과 — 기존 철학 유지)**
  - extractor: fake LLM 으로 Subgraph 반환 검증
  - cluster: 합성 그래프(두 무리 + 약한 다리)로 군집 결과 검증
  - local/global retriever: fake driver 로 컨텍스트 조립 검증
  - retrieve 노드: rag_mode 분기 동작
- **수동 통합 검증 (README 🔍)**: 실 Neo4j(docker) + 실 LLM
  - 관계형 질문 → `rag_mode="graph_local"` 로 정답+출처 확인
  - 요지 질문 → `rag_mode="graph_global"` 로 종합 답변 확인
  - vector 모드 회귀 없음 확인

## 8. 명시적 비범위 (후속으로 미룸)

- 계층형(다단계) 커뮤니티 — 단일 레벨(level=0)로 시작
- 엔티티 임베딩 유사도 앵커 매칭 (MS 원본 방식)
- auto/hybrid 라우팅 → Phase 10
- 워커 이관 → Phase 8
- gleaning(추출 다회 반복), 엔티티 설명 LLM 병합 요약
