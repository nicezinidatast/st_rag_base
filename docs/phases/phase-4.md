# Phase 4 — 하이브리드 검색(BM25) + 리랭커

- **커밋:** _(미커밋, 작업 트리 — 스텁은 `9cf9784`)_
- **목표:** dense(의미) 검색 단독에 BM25(키워드) 검색을 더해 검색 품질을 끌어올린다.
  한국어는 형태소 단위 BM25 가 dense 가 놓치는 정확매칭(고유명사·드문 용어)을 잡아준다.
- **검증:** 전체 `pytest` 99 passed(신규 7: hybrid 4 / rerank 3). ruff / mypy 통과.
  수동: 문서 적재 후 같은 질문을 dense 단독과 비교 — 키워드가 정확히 겹치는 문서가 더 위로.

---

## A. RRF 융합 (`ir/vector/search.py`)

`reciprocal_rank_fusion(rankings, k=60)`: 여러 랭킹(dense / BM25)을 하나로 합치는 순수 함수.

- 각 청크 점수 = Σ 1/(k + 순위). 두 방식이 다 찾은 청크가 위로 올라온다.
- 합치는 기준은 **(source_id, 내용) 청크 단위** — 같은 문서의 다른 청크를 뭉개지 않는다.
- `k=60` 은 관행값(순위 차이를 부드럽게 반영). 비율을 바꾸려면 이 값만 손본다.

## B. HybridRetriever (`ir/vector/search.py`)

`HybridRetriever.retrieve(query, top_k)`:

1. dense 후보 = 기존 `VectorRetriever` 재사용.
2. BM25 후보 = `_bm25_search` — Qdrant 전체 청크를 `scroll` 로 읽어 그때그때 BM25 를 만들고,
   `tokenize_ko` 로 토큰화해 점수를 매긴다. 겹치는 단어가 없으면(점수 0) 버린다.
3. 둘을 `reciprocal_rank_fusion` 으로 합쳐 상위 top_k 반환.

> **대형 코퍼스 주의:** 질의마다 전체 청크를 읽어 BM25 를 새로 만든다(작은~중간 코퍼스 기준).
> 코퍼스가 아주 커지면 영구 BM25 색인이나 Qdrant 스파스벡터로 옮긴다 — 배포마다 다른 부분이라
> 이 base 에는 단순한 방식만 둔다.

## C. 재정렬 (`ir/vector/rerank.py`)

`rerank(query, chunks, top_n)`: 리랭커로 재정렬해 상위 top_n 만 남긴다.

- 리랭커가 없거나(프로바이더 미구현/키 없음) 호출이 실패하면 입력을 그대로 돌려준다(우아한 강등).
- 비용·키 때문에 **기본 검색 파이프라인엔 끼우지 않았다.** 쓰려면 retrieve 결과에 한 줄 덧대면 된다.
- 프로바이더 본체(cohere/BGE 등)는 `clients/reranker.py` 빌더에서 고른다 — 배포마다 다른 선택.

## D. 연결 (`workflow/nodes/retrieve.py`)

`rag_mode="vector"`(자동 라우팅 기본값이기도 함)가 이제 `HybridRetriever` 를 쓴다
(enum 의 "VECTOR = dense+BM25 혼합" 의도대로). 순수 dense 가 필요하면 `VectorRetriever` 를 직접 쓴다.

## E. 남겨둔 것 (배포별 선택)

- `tokenize_ko` 는 아직 공백 분리 placeholder — 형태소 분석기(kiwipiepy 등) 교체는 후속(새 의존성).
- 재정렬 프로바이더 본체(cohere/BGE), 대형 코퍼스용 영구 BM25 색인.
