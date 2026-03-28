# Autobook Development Guide

## Local Dev

### Prerequisites
- Docker Desktop running
- Node.js 18+ (for frontend)

### Start backend
```bash
cd autobook
docker compose up
```

Services available:
| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| CloudBeaver (DB UI) | http://localhost:8978 |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

### Start frontend
```bash
cd autobook/frontend
npm install
npm run dev
```
Frontend runs at http://localhost:5173.

### Stop everything
```bash
docker compose down       # stop containers, keep data
docker compose down -v    # stop containers, delete data
```

---

## Deploy to Dev

Automatic. Push to `autobook` branch:
```bash
git push origin autobook
```

Only changed services are rebuilt and deployed. Shared code changes (config, schemas, queues, etc.) trigger all 8 services.

### Check dev deployment
1. Go to GitHub Actions — see workflow run status
2. API health: `https://dev-api.autobook.ca/health` (once DNS is configured)
3. AWS Console — ECS → autobook-dev cluster → check service status

---

## Deploy to Prod

Manual trigger:
1. Go to GitHub → Actions → "Deploy Autobook" workflow
2. Click "Run workflow" → select `autobook` branch
3. Environment defaults to `prod`

### Check prod deployment
1. Go to GitHub Actions — see workflow run status
2. API health: `https://api.autobook.ca/health` (once DNS is configured)
3. AWS Console — ECS → autobook-prod cluster → check service status

---

## Environment Differences

Same code, same Docker images. Only env vars change:

| Variable | Local | Dev | Prod |
|---|---|---|---|
| DATABASE_URL | db:5432 (container) | RDS endpoint | RDS endpoint |
| REDIS_URL | redis:6379 (container) | ElastiCache | ElastiCache |
| ENV | local | dev | prod |
| AUTH_ENABLED | false | true | true |
