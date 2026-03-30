# AI-Accountant (Autobook)

![Test & Coverage](https://github.com/UofT-CSC490-W2026/AI-Accountant/actions/workflows/test.yml/badge.svg)
![Coverage](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/UofT-CSC490-W2026/AI-Accountant/autobook/.github/badges/coverage.json)

AI-powered automated bookkeeping for Canadian small businesses. Transactions are classified and converted into double-entry journal entries through a 4-tier cascade, from cheap pattern matching to LLM-based reasoning, with human review for ambiguous cases.

## Architecture

8 backend services connected by 7 SQS queues, deployed on AWS (ECS + Lambda):

```
Transaction → Normalizer → Precedent Matcher → ML Inference → LLM Agent → Resolution → Posting → Flywheel
                (extract)     (Tier 1: match)   (Tier 2: ML)   (Tier 3: LLM)  (Tier 4: human)  (write DB)  (learn)
```

| Tier | Service | Method | Latency |
|------|---------|--------|---------|
| 1 | Precedent Matcher | Token overlap + amount/counterparty scoring against posted entries | < 50ms |
| 2 | ML Inference | DeBERTa intent classifier + NER on SageMaker, heuristic fallback for bank category + CCA class | ~300ms |
| 3 | LLM Agent | 8-agent LangGraph pipeline on AWS Bedrock (Claude Sonnet 4.5) with fix loop | ~2s |
| 4 | Human | Clarification queue — user approves, edits, or rejects proposed entries | — |

Each tier only runs if the previous tier didn't auto-post (confidence < 0.95).

**Other services**: Normalizer (regex NLP extraction), Resolution (clarification routing), Posting (DB writer), Flywheel (learning — stub).

**Infrastructure**: PostgreSQL (RDS), Redis (ElastiCache), SQS (7 queues), Qdrant (vector search), Cognito (auth), Bedrock (LLM), SageMaker (ML inference). Terraform IaC in `autobook/infra/`.

## Live (Dev Environment)

The dev environment is deployed on AWS and accessible without any local setup:

| Service | URL |
|---------|-----|
| Frontend | https://ai-accountant490.netlify.app |
| Backend API | https://api-dev.autobook.tech |
| Health check | https://api-dev.autobook.tech/health |

The frontend connects to the backend API automatically. Auth is via AWS Cognito (sign up on the login page).

## Running Locally

### Prerequisites
- Docker Desktop running
- Node.js 18+ (for frontend)
- Python 3.12 + [uv](https://docs.astral.sh/uv/) (for tests)

### 1. Start backend (Terminal 1)
```bash
cd autobook
docker compose up
```
Wait until all services are healthy (API, workers, Postgres, Redis, queues all start).

### 2. Start frontend (Terminal 2)
```bash
cd autobook/frontend
npm install
npm run dev
```

### 3. Open the app

Go to **http://localhost:5173** in your browser. The frontend connects to the backend API at `localhost:8000`.

You can also use the API directly:
- **Swagger UI**: http://localhost:8000/docs — interactive API explorer
- **Health check**: http://localhost:8000/health

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| pgAdmin (DB UI) | http://localhost:5050 |

### Stop
```bash
docker compose down       # stop containers, keep data
docker compose down -v    # stop containers, delete volumes
```

## Running Tests

```bash
cd autobook
uv sync --dev
DATABASE_URL=sqlite:///:memory: uv run pytest
```

- **761 tests**, **96% line+branch coverage**
- HTML coverage report: `autobook/htmlcov/index.html`
- Coverage posted automatically on PRs targeting `main` via GitHub Actions

## Deployment

### How it works

The project uses a single multi-target `Dockerfile` that produces 8 images (1 API + 7 workers) from shared base layers. The CI/CD pipeline (`.github/workflows/deploy.yml`) does the following:

1. **Change detection** — diffs against the last successful deploy tag (`deployed/dev` or `deployed/prod`). Only changed services are rebuilt. Shared code changes (config, schemas, queues, DB, auth) trigger all 8 services.
2. **Build & push** — Docker builds the relevant target(s) and pushes to ECR (one repo per service).
3. **Deploy API** — registers a new ECS task definition revision with the new image, updates the Fargate service, waits for stability, verifies the deployment wasn't rolled back.
4. **Deploy workers** — updates each Lambda function's image URI directly (no ECS for workers).
5. **Tag** — force-pushes a `deployed/{env}` git tag so the next run knows what changed.

### Dev (automatic)
```bash
git push origin autobook
```

### Prod (manual)
GitHub Actions → "Deploy Autobook" → Run workflow → select `autobook` branch, environment `prod`.

### Infrastructure as Code

All AWS infrastructure is managed by Terraform in `autobook/infra/`:

| Module | Resources |
|--------|-----------|
| `networking` | VPC, public/private subnets, NAT gateway, security groups |
| `database` | RDS PostgreSQL with RLS |
| `cache` | ElastiCache Redis |
| `compute` | ECS cluster, API service, ALB, ECR repos |
| `lambda-workers` | 7 Lambda functions + SQS event source mappings |
| `ml` | SageMaker endpoint (HuggingFace DLC + S3 model artifacts) |
| `auth` | Cognito user pool + app client |
| `storage` | S3 bucket |
| `secrets` | Secrets Manager for DB credentials |
| `queuing` | 7 SQS queues + dead-letter queues |
| `dns` | Route53 A record for API subdomain |
| `monitoring` | CloudWatch alarms, dashboard, SNS, budget |
| `vector-search` | Qdrant Cloud cluster |

Environments: `infra/environments/dev/` (serverless SageMaker, 1 Redis node, $100 budget) and `infra/environments/prod/` (GPU SageMaker, 3 Redis nodes, deletion protection).

### CI/CD Workflows
- `.github/workflows/deploy.yml` — build, push, deploy (triggered on push to `autobook`)
- `.github/workflows/test.yml` — pytest + coverage (triggered on PRs to `main`)

## Benchmarking

The `autobook/llm-experiment/` directory contains an ablation study benchmarking the LLM agent pipeline (Tier 3).

### What it measures

For each test case, the harness records:
- **Accuracy** — debit/credit tuple exact match + slot accuracy, entry validity (balanced debits = credits), decision correctness (APPROVED vs INCOMPLETE_INFORMATION vs STUCK)
- **Cost** — actual (with prompt cache pricing) and raw (no cache) per run, broken down per agent
- **Latency** — wall-clock milliseconds end-to-end
- **Token usage** — input, output, cache read, cache write per agent node

### Ablation variants

6 pipeline configurations tested against the same test cases:

| Variant | Components active |
|---------|-------------------|
| `single_agent` | 1 LLM call does everything (baseline to beat) |
| `baseline` | Classifiers + entry builder only |
| `with_correction` | + debit/credit correctors (cross-validation) |
| `with_evaluation` | + approver + diagnostician (quality gate + fix loop) |
| `with_disambiguation` | + disambiguator (ambiguity detection) |
| `full_pipeline` | All 8 agents active |

### Test cases

61 test cases across 3 difficulty tiers:
- **Basic** (15) — deterministic transactions (inventory purchase, stock issuance, loan payment)
- **Intermediate** (20) — compound entries, tax lines, multi-step transactions
- **Hard** (26) — ambiguous transactions with multiple valid interpretations requiring clarification

Each test case has expected debit/credit 6-tuples and expected journal entries. Hard cases include `expected_cases` mapping each interpretation to its correct answer.

### How to run

```bash
cd autobook/llm-experiment
./run_experiment.sh --warmup                          # prime prompt caches
./run_experiment.sh --variant full_pipeline           # run one variant
./run_experiment.sh --all                             # run all 6 variants
./run_experiment.sh --variant baseline --test-case basic_01_inventory_cash  # single test case
```

Results are saved to `results/<variant>/<timestamp>/` as JSON per test case. Analysis and LaTeX report generation:

```bash
cd code/analysis && python main.py --all-recent       # aggregate metrics
cd code/present && python main.py --analysis <path>    # generate LaTeX tables
```

### ML Model Evaluation (Tier 2)

The `ml_workspace/` directory contains training and evaluation code for the DeBERTa models used in Tier 2 (ML Inference).

**Models trained**:
- Intent classifier (`intent_label`) — classifies transaction intent (asset_purchase, rent_expense, transfer, etc.)
- Entity extractor (NER) — extracts vendor, asset_name, transfer_destination, mentioned_date from transaction text

**Evaluation metrics** (from `ml_workspace/eval/metrics_plan.md`):

| Task | Metrics |
|------|---------|
| Intent classification | Accuracy, macro F1 |
| Bank category classification | Macro F1 |
| CCA class matching | Accuracy |
| Entity extraction | Per-field precision, recall, F1 |
| Routing quality | % auto-posted, % clarified, wrong auto-post count |

**How to evaluate**:
```bash
cd ml_workspace
python training/evaluate_saved_models.py \
  --classifier-dir artifacts/autobook_deberta_v3_share \
  --entity-dir artifacts/autobook_deberta_v3_share/entity_extractor \
  --test-path data/processed/train.jsonl \
  --output-dir eval/results
```

The evaluation script computes accuracy and macro-F1 on a held-out test split, and per-entity precision/recall/F1 for the NER model. Results are saved as JSON.

### Why custom benchmarks

No public benchmark exists for accounting transaction → journal entry classification. Available financial datasets (HuggingFace `transaction-categorization`, GoMask.ai) classify into consumer spending categories, not chart-of-accounts codes with balanced double-entry journal entries. Both the LLM ablation harness and the ML evaluation suite use domain-specific labeled data designed by accounting knowledge.

## Project Structure

```
AI-Accountant/
  autobook/
    backend/                  # Python backend (FastAPI + 7 Lambda workers)
      api/                    #   API routes (parse, ledger, clarifications, auth, statements, events)
      auth/                   #   Cognito JWT validation, role-based access
      db/                     #   SQLAlchemy models + DAOs (PostgreSQL)
      queues/                 #   SQS (pipeline) + Redis pub/sub (real-time events)
      services/               #   8 pipeline services
        normalizer/           #     Regex NLP: extract amounts, dates, parties, quantities
        precedent/            #     Tier 1: pattern matching against posted entries
        ml_inference/         #     Tier 2: SageMaker DeBERTa + heuristic fallback
        agent/                #     Tier 3: 8-agent LangGraph pipeline (Bedrock Claude)
        resolution/           #     Tier 4: clarification routing
        posting/              #     DB writer (journal entries + lines)
        flywheel/             #     Learning worker (stub)
        shared/               #     Pipeline routing, parse status, transaction persistence
      accounting_engine/      #   Rule-based entry builder + validators
      schemas/                #   Pydantic request/response/queue message schemas
      vectordb/               #   Qdrant client, embeddings (Cohere v4), collections
      reporting/              #   Balance sheet, income statement, trial balance
    tests/                    # 761 pytest tests (96% coverage)
    infra/                    # Terraform IaC
      modules/                #   Reusable: networking, database, cache, compute, lambda-workers, ml, etc.
      environments/           #   dev/ and prod/ configurations
    frontend/                 # React frontend (Vite)
    Dockerfile                # Multi-target: 1 API + 7 worker images
    docker-compose.yml        # Local dev: Postgres, Redis, ElasticMQ, Qdrant, MinIO, LocalStack
    pyproject.toml            # Dependencies, pytest config, coverage config
  ml_workspace/               # DeBERTa model training (Modal GPU)
  llm-experiment/             # LLM pipeline ablation study (6 variants, 61 test cases)
```

## Environment Variables

| Variable | Local | Dev/Prod | Description |
|----------|-------|----------|-------------|
| `DATABASE_URL` | `db:5432` | RDS endpoint | PostgreSQL connection |
| `REDIS_URL` | `redis:6379` | ElastiCache | Redis for cache + pub/sub |
| `ENV` | `local` | `dev` / `prod` | Environment name |
| `AUTH_DEMO_MODE` | `true` | `false` | Skip Cognito auth locally |
| `ML_INFERENCE_PROVIDER` | `heuristic` | `sagemaker` | ML tier: heuristic or SageMaker |
| `SAGEMAKER_ENDPOINT_NAME` | — | `autobook-dev-classifier` | SageMaker endpoint for Tier 2 |
| `BEDROCK_MODEL_ROUTING` | — | per-agent model IDs | Claude model per agent node |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/parse` | Submit transaction text for processing |
| `POST` | `/api/v1/parse/upload` | Upload CSV/PDF for processing |
| `GET` | `/api/v1/parse/{id}` | Poll parse status |
| `GET` | `/api/v1/ledger` | Get journal entries + account balances |
| `GET` | `/api/v1/clarifications` | List pending clarification tasks |
| `POST` | `/api/v1/clarifications/{id}/resolve` | Approve/reject/edit clarification |
| `GET` | `/api/v1/statements?type=balance_sheet` | Financial statements |
| `GET` | `/api/v1/events` | SSE stream for real-time pipeline updates |
| `GET` | `/health` | Health check |
