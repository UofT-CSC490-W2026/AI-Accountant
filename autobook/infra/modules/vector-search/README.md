# Vector Search

Creates a Qdrant Cloud cluster for storing and retrieving vector embeddings used by the RAG pipeline.

## What it creates

- **Qdrant Cloud cluster** — managed vector database on AWS (no infrastructure to manage)
- **Database API key** — authentication credential for ECS services to connect

## How RAG uses Qdrant

```
1. Flywheel writes (learning):
   Flywheel Worker → embeds entry via Cohere Embed v4 (Bedrock)
     → inserts vector + metadata into Qdrant collection

2. Generator reads (few-shot examples):
   LLM Worker → embeds current transaction
     → queries Qdrant for similar positive examples (cosine similarity)
       → includes top-K results in Generator prompt

3. Evaluator reads (correction examples):
   LLM Worker → queries Qdrant for similar correction examples
     → includes in Evaluator prompt ("system produced X, correct was Y")
```

Two collections in Qdrant:
- **generator_examples** — positive examples (correctly resolved entries)
- **evaluator_corrections** — correction examples (human-overridden entries with error + fix)

Both use 1536-dimensional vectors (Cohere Embed v4) with cosine similarity.

## Provider requirement

This module uses the `qdrant-cloud` provider (not the AWS provider). The root module must configure it:

```hcl
# In environments/dev/versions.tf
terraform {
  required_providers {
    qdrant-cloud = {
      source  = "qdrant/qdrant-cloud"
      version = "~> 1.19"
    }
  }
}

# In environments/dev/providers.tf
provider "qdrant-cloud" {
  api_key    = var.qdrant_cloud_api_key  # From TF_VAR_qdrant_cloud_api_key
  account_id = var.qdrant_cloud_account_id
}
```

## Usage

```hcl
# Dev — smallest cluster, single node
module "vector_search" {
  source = "../../modules/vector-search"

  project     = "autobook"
  environment = "dev"
  node_cpu    = "500m"
  node_ram    = "1Gi"
}

# Prod — larger nodes, multi-node for HA
module "vector_search" {
  source = "../../modules/vector-search"

  project         = "autobook"
  environment     = "prod"
  number_of_nodes = 3
  node_cpu        = "1000m"
  node_ram        = "2Gi"
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| cloud_region | string | ca-central-1 | AWS region for the Qdrant cluster |
| number_of_nodes | number | 1 | Number of nodes (1 = dev, 3+ = prod HA) |
| node_cpu | string | 500m | CPU per node (Kubernetes notation) |
| node_ram | string | 1Gi | RAM per node (Kubernetes notation) |
| jwt_rbac | bool | true | Enable JWT RBAC on the database |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| qdrant_url | Cluster URL (https://...) | LLM Worker, Flywheel Worker (env var) |
| qdrant_api_key | Database API key (sensitive) | LLM Worker, Flywheel Worker (env var) |
| cluster_id | Qdrant Cloud cluster ID | reference only |
