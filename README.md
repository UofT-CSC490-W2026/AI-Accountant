# AI-Accountant (Autobook)

![Test & Coverage](https://github.com/UofT-CSC490-W2026/AI-Accountant/actions/workflows/test.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/UofT-CSC490-W2026/AI-Accountant/autobook/.github/badges/coverage.json)

AI-powered automated bookkeeping for Canadian small businesses.

## Architecture

8-service pipeline processing transactions through a 4-tier cascade:

1. **Precedent Matcher** (Tier 1) — per-user pattern matching against posted journal entries
2. **ML Inference** (Tier 2) — DeBERTa intent classification + NER on SageMaker, heuristic fallback
3. **LLM Agent** (Tier 3) — 8-agent LangGraph pipeline on AWS Bedrock (Claude Sonnet 4.5)
4. **Human Clarification** (Tier 4) — resolution queue for ambiguous transactions

## Running Tests

```bash
cd autobook
uv sync --dev
DATABASE_URL=sqlite:///:memory: uv run pytest
```

Coverage reports are generated automatically on every push and PR. See the [latest workflow run](https://github.com/UofT-CSC490-W2026/AI-Accountant/actions/workflows/test.yml) for HTML coverage reports.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for local setup, deployment, and environment configuration.
