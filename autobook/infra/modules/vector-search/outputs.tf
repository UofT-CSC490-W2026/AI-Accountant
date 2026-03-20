# --- Values other modules need from vector-search ---

# The URL that ECS services use to connect to Qdrant
# Passed as QDRANT_URL environment variable to LLM Worker and Flywheel Worker
# Example: "https://abc123.us-east-1-0.aws.cloud.qdrant.io:6333"
output "qdrant_url" {
  description = "Qdrant cluster URL — passed to ECS services as env var for vector operations"
  value       = qdrant-cloud_accounts_cluster.main.url
}

# API key for authenticating with the Qdrant database
# Passed as QDRANT_API_KEY environment variable to ECS services
# This key is only available once at creation time — Terraform stores it in state
output "qdrant_api_key" {
  description = "Qdrant database API key — sensitive, passed to ECS services for authentication"
  value       = qdrant-cloud_accounts_database_api_key_v2.main.key
  sensitive   = true # Prevents accidental exposure in logs/console output
}

# The cluster ID — useful for referencing in other Qdrant Cloud resources
output "cluster_id" {
  description = "Qdrant Cloud cluster ID"
  value       = qdrant-cloud_accounts_cluster.main.id
}

