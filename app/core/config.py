"""애플리케이션 전역 설정 (Pydantic Settings).

[역할]
- 모든 환경변수(.env)를 한 곳에서 검증/로딩한다.
- 소비처(consumer) 프로젝트는 코드를 건드리지 않고 .env 값만 바꿔서 동작을 제어한다.

[구현 가이드]
- 새 외부 서비스/모델을 붙일 때마다 여기에 *_API_KEY / *_URL 필드를 추가한다.
- 비밀값(키)은 절대 기본값에 실제 값을 넣지 말 것. 기본값은 빈 문자열/None.
- 검증이 필요한 값은 pydantic Field(validator)로 강제한다.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── 앱 기본 ───────────────────────────────────────────────
    APP_NAME: str = "nicechat-base"
    ENV: Literal["local", "dev", "staging", "prod"] = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["*"]

    # ── 보안 / 인증 ───────────────────────────────────────────
    # SECRET_KEY: JWT 서명 키. prod에서는 반드시 강한 랜덤값으로 교체.
    SECRET_KEY: str = Field(default="change-me", min_length=8)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # ── RDBMS (PostgreSQL / SQLAlchemy async) ─────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nicechat"

    # ── Redis (세션/대화이력/시맨틱 캐시) ─────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Vector DB (기본 Qdrant, 배포별 교체 가능) ─────────────
    VECTOR_DB_URL: str = "http://localhost:6333"
    VECTOR_DB_API_KEY: str | None = None
    VECTOR_COLLECTION: str = "documents"

    # ── Graph DB (기본 Neo4j) ─────────────────────────────────
    GRAPH_DB_URI: str = "bolt://localhost:7687"
    GRAPH_DB_USER: str = "neo4j"
    GRAPH_DB_PASSWORD: str = "password"

    # ── LLM / 임베딩 / 리랭커 프로바이더 키 ───────────────────
    # 여기 있는 키들은 clients/ 의 팩토리(chat_model / embedding / reranker)가
    # 런타임에 어떤 프로바이더를 쓸지 결정할 때 참조한다. 안 쓰는 건 비워두면 됨.
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None          # Gemini
    COHERE_API_KEY: str | None = None          # Command / Rerank
    MISTRAL_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    VOYAGE_API_KEY: str | None = None          # Voyage 임베딩
    HUGGINGFACE_API_KEY: str | None = None
    # HF Hub 토큰. sentence-transformers 모델 다운로드 시 인증에 사용
    # (없으면 익명 요청 → rate limit 낮음 + 다운로드 느림 경고).
    HF_TOKEN: str | None = None
    UPSTAGE_API_KEY: str | None = None         # Solar (한국어 특화)

    # Azure OpenAI (엔드포인트/배포명 별도 필요)
    AZURE_OPENAI_API_KEY: str | None = None
    AZURE_OPENAI_ENDPOINT: str | None = None
    AZURE_OPENAI_API_VERSION: str = "2024-06-01"

    # ── 기본 모델 선택 (팩토리의 default) ─────────────────────
    # "provider:model" 또는 단순 모델명. 팩토리 구현 시 파싱 규칙을 정할 것.
    DEFAULT_CHAT_MODEL: str = "anthropic:claude-haiku-4-5-20251001"
    # 기본은 무료 로컬 임베딩(bge-m3, API 키 불필요). 다른 프로바이더로 바꾸려면
    # .env 에서 "openai:text-embedding-3-small" 처럼 지정한다.
    DEFAULT_EMBEDDING_MODEL: str = "st:BAAI/bge-m3"
    DEFAULT_RERANK_MODEL: str = "cohere:rerank-multilingual-v3.0"

    # ── 관측성 (Langfuse LLM 트레이싱) ────────────────────────
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENABLED: bool = False  # 키가 있어도 명시적으로 켜야 동작


@lru_cache
def get_settings() -> Settings:
    """프로세스당 1회만 파싱되는 싱글톤."""
    return Settings()


settings = get_settings()
