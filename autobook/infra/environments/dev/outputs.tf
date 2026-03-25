# =============================================================================
# DEV ENVIRONMENT OUTPUTS — key values for development and CI/CD
# =============================================================================
# These outputs are displayed after `terraform apply` and can be read by
# other tools (CI/CD pipelines, frontend config, developer setup scripts).

# --- API access ---

# The full API domain name — what the frontend uses to make API calls
# Example: "api-dev.autobook.tech"
output "api_url" {
  description = "API domain name (HTTPS) — frontend calls this"
  value       = "https://${module.dns.api_fqdn}"
}

# WebSocket URL for real-time push notifications to the frontend
# Example: "wss://abc123.execute-api.ca-central-1.amazonaws.com/dev"
output "websocket_url" {
  description = "WebSocket URL — frontend connects for real-time updates"
  value       = module.api_gateway.websocket_url
}

# --- Auth ---

# Cognito user pool ID — frontend needs this to configure Amplify/SDK
output "cognito_user_pool_id" {
  description = "Cognito user pool ID — frontend auth configuration"
  value       = module.auth.user_pool_id
}

# Cognito app client ID — frontend uses this to initiate login flows
output "cognito_client_id" {
  description = "Cognito app client ID — frontend auth configuration"
  value       = module.auth.client_id
}

output "cognito_role_claim_source" {
  description = "Canonical Cognito claim the backend uses for authorization"
  value       = module.auth.role_claim_source
}

output "cognito_role_groups" {
  description = "Cognito groups and precedence values expected by backend authorization"
  value       = module.auth.role_group_names
}

# --- CI/CD ---

# ECR repository URLs — CI/CD pushes Docker images here
# Map: {"api" = "609092547371.dkr.ecr.ca-central-1.amazonaws.com/autobook-dev-api", ...}
output "ecr_urls" {
  description = "Map of service name → ECR repository URL — CI/CD pushes images here"
  value       = module.compute.ecr_urls
}

# GitHub Actions deploy role — CI/CD assumes this via OIDC to deploy
output "deploy_role_arn" {
  description = "IAM role ARN for GitHub Actions OIDC deployment"
  value       = module.iam.github_actions_role_arn
}

# ECS cluster name — CI/CD needs this to update services after pushing images
output "ecs_cluster_name" {
  description = "ECS cluster name — CI/CD uses to deploy new task definitions"
  value       = module.compute.cluster_name
}

# --- Vector search ---

# Qdrant cluster URL — application code connects here for RAG operations
output "qdrant_url" {
  description = "Qdrant cluster URL — LLM and Flywheel workers connect here"
  value       = module.vector_search.qdrant_url
}

# Qdrant API key — sensitive, only shown when explicitly requested
output "qdrant_api_key" {
  description = "Qdrant database API key (sensitive)"
  value       = module.vector_search.qdrant_api_key
  sensitive   = true
}

# --- ML ---

# SageMaker endpoint name — null until model_image is provided
output "sagemaker_endpoint_name" {
  description = "SageMaker endpoint name (null if no model deployed yet)"
  value       = module.ml.endpoint_name
}

# --- Bastion ---

output "bastion_instance_id" {
  description = "SSM bastion EC2 instance ID — use with aws ssm start-session"
  value       = module.bastion.instance_id
}

# --- Monitoring ---

# Direct link to the CloudWatch dashboard
output "dashboard_url" {
  description = "CloudWatch dashboard URL — system health at a glance"
  value       = module.monitoring.dashboard_url
}
