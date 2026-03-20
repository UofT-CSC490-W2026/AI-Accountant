# API Gateway

Creates the WebSocket API for real-time push notifications to the frontend.

## What it creates

- **WebSocket API** — persistent bidirectional connection between frontend and backend
- **MOCK integration** — placeholder backend (returns 200) until real integration is wired
- **3 routes** — `$connect`, `$disconnect`, `$default`
- **Stage** — deployment with auto-deploy and throttling

## How real-time updates work

```
1. Frontend connects:
   Browser → wss://abc123.execute-api.ca-central-1.amazonaws.com/dev
     → API Gateway assigns connectionId, returns 200

2. Backend pushes update:
   Posting Service → Redis pub/sub ("entry posted")
     → API Service receives notification
       → API Service calls Management API: POST /@connections/{connectionId}
         → API Gateway pushes message to the client's WebSocket

3. Frontend receives:
   Browser gets {"event": "entry_posted", "entry_id": 123} instantly
```

The client never polls. Updates arrive over the open WebSocket connection.

## Current state: MOCK integration

Routes currently use a MOCK integration (static 200 response). To enable real functionality, replace the integration with:

- **Lambda** (`AWS_PROXY`): handles $connect/$disconnect (store/remove connection IDs in Redis)
- **HTTP** (`HTTP_PROXY`): forwards WebSocket events to the API Service via ALB

This is the same pattern as the compute module — infrastructure exists before the application is ready.

## Usage

```hcl
# Dev
module "api_gateway" {
  source = "../../modules/api-gateway"

  project     = "autobook"
  environment = "dev"
}

# Prod — higher throttle limits
module "api_gateway" {
  source = "../../modules/api-gateway"

  project                = "autobook"
  environment            = "prod"
  throttling_rate_limit  = 500
  throttling_burst_limit = 200
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment (also used as stage name) |
| route_selection_expression | string | "$request.body.action" | How to select routes from messages |
| throttling_rate_limit | number | 100 | Max requests/sec |
| throttling_burst_limit | number | 50 | Max concurrent burst |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| websocket_url | WebSocket URL (wss://...) | frontend (connect to WebSocket) |
| api_id | API ID | API Service (Management API calls) |
| api_endpoint | Execution endpoint base URL | API Service (construct Management API URL) |
