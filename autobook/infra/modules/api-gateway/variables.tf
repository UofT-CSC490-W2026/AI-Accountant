# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-ws"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used as the stage name — e.g. "dev" → wss://xxx.execute-api.region.amazonaws.com/dev
variable "environment" {
  type        = string
  description = "Deployment environment, used as stage name"
}

# --- Optional inputs (safe defaults provided) ---

# How API Gateway decides which route to use for incoming messages
# Default: looks at the "action" field in the JSON message body
# Example: client sends {"action": "subscribe", ...} → routes to $default
variable "route_selection_expression" {
  type        = string
  description = "JSONPath expression to select the route from incoming messages"
  default     = "$request.body.action"
}

# Throttling — maximum requests per second across all connected clients
# Protects your backend from being overwhelmed by WebSocket messages
variable "throttling_rate_limit" {
  type        = number
  description = "Max requests per second (across all clients)"
  default     = 100
}

# Throttling — maximum burst of concurrent requests
variable "throttling_burst_limit" {
  type        = number
  description = "Max concurrent burst requests"
  default     = 50
}
