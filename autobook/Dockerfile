# syntax=docker/dockerfile:1

# ── autobook-base ──────────────────────────────────────────────
# Shared by all 8 services: pydantic, redis, boto3, awslambdaric
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
COPY backend/local_identity.py backend/local_identity.py
COPY backend/auth/ backend/auth/
COPY backend/db/ backend/db/
COPY backend/queues/ backend/queues/
COPY backend/cache/ backend/cache/
COPY backend/utils/ backend/utils/
COPY backend/schemas/ backend/schemas/
COPY backend/reporting/ backend/reporting/
COPY backend/services/__init__.py backend/services/__init__.py
COPY backend/services/shared/ backend/services/shared/
COPY backend/vectordb/ backend/vectordb/

RUN groupadd -g 1001 app && useradd -u 1001 -g app -s /bin/false app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/backend"

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
# Lambda: ENTRYPOINT runs the RIC, CMD is the handler (overridden by Terraform image_config)
# Local: docker-compose overrides with ["python", "-m", "services.normalizer"]
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.normalizer.aws.handler"]

# ── Precedent Matcher (Tier 1) ─────────────────────────────────
FROM autobook-accounting AS autobook-precedent

COPY backend/services/precedent/ backend/services/precedent/
COPY backend/services/precedent_v2/ backend/services/precedent_v2/
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.precedent.aws.handler"]

# ── ML Inference (Tier 2) ──────────────────────────────────────
FROM autobook-accounting AS autobook-ml-inference

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra ml-inference

COPY backend/services/ml_inference/ backend/services/ml_inference/
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.ml_inference.aws.handler"]

# ── Agent / LLM Worker (Tier 3) ────────────────────────────────
FROM autobook-accounting AS autobook-agent

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra agent

COPY backend/services/agent/ backend/services/agent/
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.agent.aws.handler"]

# ── Resolution Worker (Tier 4) ─────────────────────────────────
FROM autobook-accounting AS autobook-resolution

COPY backend/services/resolution/ backend/services/resolution/
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.resolution.aws.handler"]

# ── Posting Service ────────────────────────────────────────────
FROM autobook-base AS autobook-posting

COPY backend/services/posting/ backend/services/posting/
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.posting.aws.handler"]

# ── Flywheel Worker ────────────────────────────────────────────
FROM autobook-base AS autobook-flywheel

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra flywheel

COPY backend/services/flywheel/ backend/services/flywheel/
ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["services.flywheel.aws.handler"]
