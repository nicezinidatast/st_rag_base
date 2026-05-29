# ---------- builder ----------
FROM python:3.11-slim AS builder

# uv 바이너리를 공식 이미지에서 복사 (별도 설치 불필요)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 바이트코드 컴파일 + 복사 모드(레이어 캐시 친화적)
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 1) 의존성만 먼저 설치 (소스 변경 시에도 이 레이어는 캐시됨)
#    *** uv.lock 이 있어야 --frozen 이 동작한다. 최초 1회 `uv lock` 후 커밋할 것. ***
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 2) 앱 소스 복사 후 프로젝트까지 설치
COPY app ./app
COPY config ./config
RUN uv sync --frozen --no-dev

# ---------- runtime ----------
FROM python:3.11-slim AS runtime

# 빌더에서 만든 가상환경을 그대로 사용
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/config /app/config

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
