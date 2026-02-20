terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    # bucket provided via: terraform init -backend-config="bucket=autobook-tfstate-<ACCOUNT_ID>"
    region         = "ca-central-1"
    encrypt        = true
    dynamodb_table = "autobook-terraform-locks"
  }
}

provider "aws" {
  region = "ca-central-1"
  default_tags {
    tags = { Project = "autobook", ManagedBy = "terraform-global" }
  }
}

# --- Route 53 zone (one per account) ---
resource "aws_route53_zone" "main" {
  name = "autobook.app"
}

# --- ACM wildcard cert (ca-central-1) ---
resource "aws_acm_certificate" "main" {
  domain_name               = "autobook.app"
  subject_alternative_names = ["*.autobook.app"]
  validation_method         = "DNS"
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.main.domain_validation_options : dvo.domain_name => dvo
  }
  zone_id = aws_route53_zone.main.zone_id
  name    = each.value.resource_record_name
  type    = each.value.resource_record_type
  ttl     = 300
  records = [each.value.resource_record_value]
}

resource "aws_acm_certificate_validation" "main" {
  certificate_arn         = aws_acm_certificate.main.arn
  validation_record_fqdns = [for r in aws_route53_record.cert_validation : r.fqdn]
}

# --- Vercel frontend DNS ---
resource "aws_route53_record" "frontend" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "autobook.app"
  type    = "A"
  ttl     = 300
  records = ["76.76.21.21"]
}

resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = "www.autobook.app"
  type    = "CNAME"
  ttl     = 300
  records = ["cname.vercel-dns.com"]
}

# --- GitHub Actions OIDC provider (one per account per issuer) ---
resource "aws_iam_openid_connect_provider" "github" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["ffffffffffffffffffffffffffffffffffffffff"]
  # Placeholder — AWS validates GitHub tokens directly since July 2023.
  # Field required by API but value ignored for GitHub.
}
