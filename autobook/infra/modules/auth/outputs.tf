# --- Values other modules need from auth ---

# Compute module needs this so the API Service can verify user tokens
# API Gateway uses this to validate JWT tokens on incoming requests
output "user_pool_id" {
  description = "Cognito user pool ID — used by API Gateway to validate auth tokens"
  value       = aws_cognito_user_pool.main.id
}

# Compute module needs this so the frontend knows which app client to use
# The frontend includes this client ID when sending auth requests to Cognito
output "client_id" {
  description = "Cognito app client ID — used by frontend to authenticate users"
  value       = aws_cognito_user_pool_client.main.id
}

output "role_claim_source" {
  description = "Canonical Cognito claim the backend uses for app authorization"
  value       = "cognito:groups"
}

output "role_group_names" {
  description = "Map of Cognito role group names -> precedence expected by backend authorization"
  value       = { for name, group in aws_cognito_user_group.roles : name => group.precedence }
}
