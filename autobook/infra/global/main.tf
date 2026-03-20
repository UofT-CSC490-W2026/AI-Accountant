# --- Route53: DNS zone for the domain ---
resource "aws_route53_zone" "main" {
  name = var.domain_name # "autobook.tech" — one zone, all envs share it

  tags = { Name = "${var.project}-dns" }
}

# --- ACM: TLS certificate for HTTPS ---
resource "aws_acm_certificate" "main" {
  domain_name               = var.domain_name          # "autobook.tech"
  subject_alternative_names = ["*.${var.domain_name}"] # Wildcard covers all subdomains
  validation_method         = "DNS"                    # Prove ownership via DNS record

  tags = { Name = "${var.project}-wildcard-cert" }
}

# DNS records that prove we own the domain (ACM checks these)
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id         = aws_route53_zone.main.zone_id
  name            = each.value.name
  type            = each.value.type
  ttl             = 300 # 5 minutes
  records         = [each.value.record]
  allow_overwrite = true # Safe to overwrite if record already exists
}

# Wait until ACM verifies the DNS records and issues the cert
resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# --- Frontend DNS: root domain → Netlify ---
resource "aws_route53_record" "frontend" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name # "autobook.tech"
  type    = "A"
  ttl     = 300
  records = [var.frontend_ip] # Netlify IP
}

# www subdomain → Netlify
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.${var.domain_name}" # "www.autobook.tech"
  type    = "CNAME"
  ttl     = 300
  records = [var.frontend_cname] # Netlify CNAME target
}

# --- GitHub OIDC: lets GitHub Actions assume AWS roles without storing credentials ---
# Import block: this OIDC provider already exists in the account.
# Run `terraform apply` once, then remove this import block.
import {
  to = aws_iam_openid_connect_provider.github
  id = "arn:aws:iam::609092547371:oidc-provider/token.actions.githubusercontent.com"
}

resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]                        # Required audience
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"] # Placeholder — AWS ignores this for GitHub since July 2023
}
