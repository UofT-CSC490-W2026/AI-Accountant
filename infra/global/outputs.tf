output "zone_id"                  { value = aws_route53_zone.main.zone_id }
output "zone_name_servers"        { value = aws_route53_zone.main.name_servers }
output "certificate_arn"          { value = aws_acm_certificate.main.arn }
output "github_oidc_provider_arn" { value = aws_iam_openid_connect_provider.github.arn }
