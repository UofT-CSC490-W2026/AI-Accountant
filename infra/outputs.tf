output "ecr_url"                 { value = module.compute.ecr_url }
output "alb_dns_name"            { value = module.compute.alb_dns_name }
output "github_actions_role_arn" { value = module.iam.github_actions_role_arn }
output "cognito_pool_id"         { value = module.auth.user_pool_id }
output "cognito_client_id"       { value = module.auth.client_id }
