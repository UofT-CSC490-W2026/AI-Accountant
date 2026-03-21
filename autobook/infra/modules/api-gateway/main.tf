# Naming convention
locals {
  name = "${var.project}-${var.environment}-ws" # e.g. "autobook-dev-ws"
}

# =============================================================================
# WEBSOCKET API
# =============================================================================
resource "aws_apigatewayv2_api" "websocket" {
  name                       = local.name
  protocol_type              = "WEBSOCKET"
  route_selection_expression = var.route_selection_expression

  tags = { Name = local.name }
}

# =============================================================================
# DYNAMODB — WebSocket connection tracking
# =============================================================================
resource "aws_dynamodb_table" "connections" {
  name         = "${local.name}-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connectionId"

  attribute {
    name = "connectionId"
    type = "S"
  }

  tags = { Name = "${local.name}-connections" }
}

# =============================================================================
# CONNECT / DISCONNECT LAMBDAS
# =============================================================================

# --- IAM role for connect/disconnect Lambdas ---
resource "aws_iam_role" "ws_lambda" {
  name = "${local.name}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Name = "${local.name}-lambda" }
}

resource "aws_iam_role_policy_attachment" "ws_lambda_basic" {
  role       = aws_iam_role.ws_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "ws_lambda_dynamodb" {
  name = "dynamodb-access"
  role = aws_iam_role.ws_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["dynamodb:PutItem", "dynamodb:DeleteItem"]
      Resource = aws_dynamodb_table.connections.arn
    }]
  })
}

# --- Connect Lambda ---
data "archive_file" "ws_connect" {
  type        = "zip"
  output_path = "${path.module}/ws_connect.zip"

  source {
    content  = <<-PYTHON
import logging
import os
import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["WS_CONNECTIONS_TABLE"])

def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    logger.info("WebSocket connect: %s", connection_id)
    table.put_item(Item={"connectionId": connection_id})
    return {"statusCode": 200}
    PYTHON
    filename = "handler.py"
  }
}

resource "aws_lambda_function" "ws_connect" {
  function_name = "${local.name}-connect"
  role          = aws_iam_role.ws_lambda.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 10
  memory_size   = 128

  filename         = data.archive_file.ws_connect.output_path
  source_code_hash = data.archive_file.ws_connect.output_base64sha256

  environment {
    variables = {
      WS_CONNECTIONS_TABLE = aws_dynamodb_table.connections.name
    }
  }

  tags = { Name = "${local.name}-connect" }
}

resource "aws_lambda_permission" "ws_connect" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_connect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/$connect"
}

# --- Disconnect Lambda ---
data "archive_file" "ws_disconnect" {
  type        = "zip"
  output_path = "${path.module}/ws_disconnect.zip"

  source {
    content  = <<-PYTHON
import logging
import os
import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["WS_CONNECTIONS_TABLE"])

def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    logger.info("WebSocket disconnect: %s", connection_id)
    table.delete_item(Key={"connectionId": connection_id})
    return {"statusCode": 200}
    PYTHON
    filename = "handler.py"
  }
}

resource "aws_lambda_function" "ws_disconnect" {
  function_name = "${local.name}-disconnect"
  role          = aws_iam_role.ws_lambda.arn
  handler       = "handler.handler"
  runtime       = "python3.12"
  timeout       = 10
  memory_size   = 128

  filename         = data.archive_file.ws_disconnect.output_path
  source_code_hash = data.archive_file.ws_disconnect.output_base64sha256

  environment {
    variables = {
      WS_CONNECTIONS_TABLE = aws_dynamodb_table.connections.name
    }
  }

  tags = { Name = "${local.name}-disconnect" }
}

resource "aws_lambda_permission" "ws_disconnect" {
  statement_id  = "AllowAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ws_disconnect.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.websocket.execution_arn}/*/$disconnect"
}

# =============================================================================
# INTEGRATIONS — Lambda (replaces mock)
# =============================================================================
resource "aws_apigatewayv2_integration" "connect" {
  api_id             = aws_apigatewayv2_api.websocket.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.ws_connect.invoke_arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_integration" "disconnect" {
  api_id             = aws_apigatewayv2_api.websocket.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.ws_disconnect.invoke_arn
  integration_method = "POST"
}

# Default route — no-op for push-only WebSocket (clients don't send messages)
resource "aws_apigatewayv2_integration" "default" {
  api_id           = aws_apigatewayv2_api.websocket.id
  integration_type = "MOCK"

  template_selection_expression = "200"
  request_templates = {
    "200" = jsonencode({ statusCode = 200 })
  }
}

resource "aws_apigatewayv2_integration_response" "default" {
  api_id                   = aws_apigatewayv2_api.websocket.id
  integration_id           = aws_apigatewayv2_integration.default.id
  integration_response_key = "/200/"
}

# =============================================================================
# ROUTES
# =============================================================================
resource "aws_apigatewayv2_route" "connect" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$connect"
  target    = "integrations/${aws_apigatewayv2_integration.connect.id}"
}

resource "aws_apigatewayv2_route" "disconnect" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$disconnect"
  target    = "integrations/${aws_apigatewayv2_integration.disconnect.id}"
}

resource "aws_apigatewayv2_route" "default" {
  api_id    = aws_apigatewayv2_api.websocket.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.default.id}"
}

resource "aws_apigatewayv2_route_response" "connect" {
  api_id             = aws_apigatewayv2_api.websocket.id
  route_id           = aws_apigatewayv2_route.connect.id
  route_response_key = "$default"
}

# =============================================================================
# CLOUDWATCH LOGGING
# =============================================================================
resource "aws_iam_role" "apigateway_cloudwatch" {
  name = "${local.name}-apigw-cloudwatch"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "apigateway.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apigateway_cloudwatch" {
  role       = aws_iam_role.apigateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "main" {
  cloudwatch_role_arn = aws_iam_role.apigateway_cloudwatch.arn
}

# =============================================================================
# STAGE
# =============================================================================
resource "aws_apigatewayv2_stage" "main" {
  api_id      = aws_apigatewayv2_api.websocket.id
  name        = var.environment
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = var.throttling_rate_limit
    throttling_burst_limit = var.throttling_burst_limit
  }

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

  depends_on = [aws_api_gateway_account.main]
}

# =============================================================================
# CLOUDWATCH LOG GROUP
# =============================================================================
resource "aws_cloudwatch_log_group" "websocket" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = 30

  tags = { Name = local.name }
}
