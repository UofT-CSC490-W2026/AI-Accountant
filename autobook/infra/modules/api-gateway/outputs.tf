# --- Values other modules need from api-gateway ---

# The URL the frontend connects to for real-time WebSocket updates
# Example: "wss://abc123.execute-api.ca-central-1.amazonaws.com/dev"
output "websocket_url" {
  description = "WebSocket URL for frontend clients to connect to"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

# The API Service needs this to call the Management API (push messages to connected clients)
# Management API endpoint: https://{api_id}.execute-api.{region}.amazonaws.com/{stage}
output "api_id" {
  description = "WebSocket API ID — needed by API Service to push messages via Management API"
  value       = aws_apigatewayv2_api.websocket.id
}

# The API Service uses this to construct the Management API URL
# Format: https://{api_id}.execute-api.{region}.amazonaws.com
output "api_endpoint" {
  description = "WebSocket API execution endpoint — base URL for Management API calls"
  value       = aws_apigatewayv2_api.websocket.api_endpoint
}
