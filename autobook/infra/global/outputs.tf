# Values that environment stacks (dev, prod) read via terraform_remote_state

output "zone_id" {
  description = "Route53 zone ID — environments use this to add API subdomain records"
  value       = aws_route53_zone.main.zone_id
}

output "cert_arn" {
  description = "ACM wildcard certificate ARN — environments attach this to their ALB for HTTPS"
  value       = aws_acm_certificate.main.arn
}

output "oidc_provider_arn" {
  description = "GitHub OIDC provider ARN — environments use this for CI/CD deploy roles"
  value       = aws_iam_openid_connect_provider.github.arn
}
