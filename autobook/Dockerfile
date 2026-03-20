# syntax=docker/dockerfile:1

# ── autobook-base ──────────────────────────────────────────────
# Shared by all 8 services: pydantic, redis, sqlalchemy, asyncpg, boto3
FROM python:3.12-slim AS autobook-base

COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# Deps layer (cached until pyproject.toml or uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Shared source
COPY backend/config.py backend/config.py
COPY backend/db/ backend/db/
COPY backend/queues/ backend/queues/
COPY backend/cache/ backend/cache/
COPY backend/utils/ backend/utils/
COPY backend/schemas/ backend/schemas/

RUN groupadd -g 1001 app && useradd -u 1001 -g app -s /bin/false app
ENV PATH="/app/.venv/bin:$PATH"

# ── autobook-accounting ────────────────────────────────────────
# Tier workers (precedent, ml_inference, agent, resolution) inherit from this
FROM autobook-base AS autobook-accounting

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra accounting

COPY backend/accounting_engine/ backend/accounting_engine/

# ── API Service ────────────────────────────────────────────────
FROM autobook-base AS autobook-api

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra api

COPY backend/api/ backend/api/
USER app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ── Normalizer (File Worker) ──────────────────────────────────
FROM autobook-base AS autobook-normalizer

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra normalizer

COPY backend/services/normalizer/ backend/services/normalizer/
USER app
CMD ["python", "-m", "services.normalizer"]

# ── Precedent Matcher (Tier 1) ─────────────────────────────────
FROM autobook-accounting AS autobook-precedent

COPY backend/services/precedent/ backend/services/precedent/
USER app
CMD ["python", "-m", "services.precedent"]

# ── ML Inference (Tier 2) ──────────────────────────────────────
FROM autobook-accounting AS autobook-ml-inference

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra ml-inference

COPY backend/services/ml_inference/ backend/services/ml_inference/
USER app
CMD ["python", "-m", "services.ml_inference"]

# ── Agent / LLM Worker (Tier 3) ────────────────────────────────
FROM autobook-accounting AS autobook-agent

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra agent

COPY backend/services/agent/ backend/services/agent/
USER app
CMD ["python", "-m", "services.agent"]

# ── Resolution Worker (Tier 4) ─────────────────────────────────
FROM autobook-accounting AS autobook-resolution

COPY backend/services/resolution/ backend/services/resolution/
USER app
CMD ["python", "-m", "services.resolution"]

# ── Posting Service ────────────────────────────────────────────
FROM autobook-base AS autobook-posting

COPY backend/services/posting/ backend/services/posting/
USER app
CMD ["python", "-m", "services.posting"]

# ── Flywheel Worker ────────────────────────────────────────────
FROM autobook-base AS autobook-flywheel

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra flywheel

COPY backend/services/flywheel/ backend/services/flywheel/
USER app
CMD ["python", "-m", "services.flywheel"]
