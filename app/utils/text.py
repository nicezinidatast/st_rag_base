"""텍스트 클리닝 + 한국어 토크나이저 가공.

[구현 가이드]
- clean_text: 공백 정규화/제어문자 제거/HTML 태그 제거 등 적재 전처리.
- tokenize_ko: BM25 키워드 검색 품질을 위해 한국어 형태소 분석기 연동
  (예: kiwipiepy, mecab-ko). ir/vector/search.py 의 BM25 단계에서 사용.
"""
from __future__ import annotations


def clean_text(text: str) -> str:
    # TODO: 적재 파이프라인에 맞춰 확장
    return " ".join(text.split())


def tokenize_ko(text: str) -> list[str]:
    # TODO: 한국어 형태소 분석기로 교체 (현재는 공백 분리 placeholder)
    return text.split()
