output "user_pool_id" { value = aws_cognito_user_pool.main.id }
output "client_id"    { value = aws_cognito_user_pool_client.main.id }
output "endpoint"     { value = aws_cognito_user_pool.main.endpoint }
