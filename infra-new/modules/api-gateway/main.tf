# Naming convention
locals {
  name = "${var.project}-${var.environment}-ws" # e.g. "autobook-dev-ws"

  # The three WebSocket routes that API Gateway must handle
  # $connect:    fired when a client opens a WebSocket connection
  # $disconnect: fired when a client closes the connection
  # $default:    fired for any message that doesn't match a custom route
  routes = ["$connect", "$disconnect", "$default"]
}

# =============================================================================
# WEBSOCKET API — persistent bidirectional connection for real-time updates
# =============================================================================
# API Gateway manages WebSocket connections for us:
#   - Handles connection lifecycle (open, close, keep-alive)
#   - Scales automatically (thousands of concurrent connections)
#   - Assigns each connection a unique ID
#
# Our app uses this to push real-time updates to the frontend:
#   1. Client connects via wss://xxx.execute-api.region.amazonaws.com/dev
#   2. Backend subscribes to Redis pub/sub ("entry posted", "transactions ready")
#   3. When an update arrives, backend calls the Management API to push to connected clients
#
# The client never polls — updates arrive instantly over the open WebSocket.
resource "aws_apigatewayv2_api" "websocket" {
  name                       = local.name                     # e.g. "autobook-dev-ws"
  protocol_type              = "WEBSOCKET"                    # WebSocket (not HTTP)
  route_selection_expression = var.route_selection_expression # How to pick a route from incoming messages

  tags = { Name = local.name }
}

# =============================================================================
# MOCK INTEGRATION — placeholder backend for all routes
# =============================================================================
# A MOCK integration returns a static response without calling any backend.
# We use this as scaffolding — the real integration (Lambda or HTTP to the API
# Service) is wired when the application is built.
#
# For $connect, the MOCK must return 200 or the connection is rejected.
# For $disconnect and $default, the response doesn't matter (informational).
#
# To switch to a real backend later, replace integration_type with:
#   - "AWS_PROXY" for Lambda
#   - "HTTP_PROXY" for an HTTP endpoint (e.g. ALB)
resource "aws_apigatewayv2_integration" "mock" {
  api_id           = aws_apigatewayv2_api.websocket.id
  integration_type = "MOCK" # Static response, no backend

  # Template that returns a 200 status — required for $connect to succeed
  template_selection_expression = "200"
  request_templates = {
    "200" = jsonencode({ statusCode = 200 })
  }
}

# Integration response — maps the MOCK response back to the route
resource "aws_apigatewayv2_integration_response" "mock" {
  api_id                   = aws_apigatewayv2_api.websocket.id
  integration_id           = aws_apigatewayv2_integration.mock.id
  integration_response_key = "/200/" # Regex matching the 200 status code
}

# =============================================================================
# ROUTES — $connect, $disconnect, $default
# =============================================================================
# Each route handles a specific WebSocket event:
#   $connect:    client opens connection → store connection ID for later pushes
#   $disconnect: client closes connection → remove connection ID
#   $default:    client sends a message → process it (or ignore for push-only)

resource "aws_apigatewayv2_route" "main" {
  for_each = toset(local.routes)

  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = each.key                                               # "$connect", "$disconnect", or "$default"
  target    = "integrations/${aws_apigatewayv2_integration.mock.id}" # Points to the MOCK integration
}

# Route response — required for bidirectional communication on $connect
# Without this, the client doesn't receive the connection confirmation
resource "aws_apigatewayv2_route_response" "connect" {
  api_id             = aws_apigatewayv2_api.websocket.id
  route_id           = aws_apigatewayv2_route.main["$connect"].id
  route_response_key = "$default" # Default response for the $connect route
}

# =============================================================================
# STAGE — deployment environment (dev, prod)
# =============================================================================
# A stage is a named deployment of the API. The stage name appears in the URL:
#   wss://abc123.execute-api.ca-central-1.amazonaws.com/dev
#
# auto_deploy = true means any route/integration changes are deployed immediately
# without needing a separate deployment resource.
resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.websocket.id
  name        = var.environment # e.g. "dev" or "prod"
  auto_deploy = true            # Deploy changes automatically (no manual deployment step)

  # Throttling — protect backend from message floods
  default_route_settings {
    throttling_rate_limit  = var.throttling_rate_limit  # Max requests/sec (default: 100)
    throttling_burst_limit = var.throttling_burst_limit # Max burst (default: 50)
  }

  # Access logging — record every WebSocket connection and message for debugging
  # and audit. Logs go to a CloudWatch log group dedicated to this API stage.
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.websocket.arn
    format = jsonencode({
      requestId    = "$context.requestId"
      ip           = "$context.identity.sourceIp"
      routeKey     = "$context.routeKey"
      status       = "$context.status"
      connectionId = "$context.connectionId"
      requestTime  = "$context.requestTime"
      eventType    = "$context.eventType"
      error        = "$context.error.message"
    })
  }

  tags = { Name = local.name }
}

# =============================================================================
# CLOUDWATCH LOG GROUP — access logs for WebSocket API
# =============================================================================
# Stores connection events, message routing, and errors for debugging.
# Retained for 30 days — enough for troubleshooting without unbounded cost.
resource "aws_cloudwatch_log_group" "websocket" {
  name              = "/aws/apigateway/${local.name}" # e.g. "/aws/apigateway/autobook-dev-ws"
  retention_in_days = 30                              # Auto-delete after 30 days
  # Hardcoded (not a variable) because there is only one WebSocket log group.
  # The compute module uses a variable because it applies to 8 service log groups.

  tags = { Name = local.name }
}
