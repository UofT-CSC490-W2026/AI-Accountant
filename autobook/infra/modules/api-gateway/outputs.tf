# --- Values other modules need from api-gateway ---

output "websocket_url" {
  description = "WebSocket URL for frontend clients to connect to"
  value       = aws_apigatewayv2_stage.main.invoke_url
}

output "api_id" {
  description = "WebSocket API ID"
  value       = aws_apigatewayv2_api.websocket.id
}

output "api_endpoint" {
  description = "WebSocket API execution endpoint — base URL for Management API calls"
  value       = aws_apigatewayv2_api.websocket.api_endpoint
}

output "connections_table_name" {
  description = "DynamoDB table name for WebSocket connections"
  value       = aws_dynamodb_table.connections.name
}

output "connections_table_arn" {
  description = "DynamoDB table ARN for WebSocket connections"
  value       = aws_dynamodb_table.connections.arn
}
