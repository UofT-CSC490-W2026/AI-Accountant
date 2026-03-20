# Naming convention
locals {
  # Subdomain: "api" for prod, "api-dev" for dev (unless overridden)
  api_subdomain = coalesce(var.api_subdomain, var.environment == "prod" ? "api" : "api-${var.environment}")
}

# =============================================================================
# ROUTE53 A RECORD (ALIAS) — api.autobook.tech → ALB
# =============================================================================
# This DNS record maps a human-readable domain (api.autobook.tech) to the ALB.
# When someone visits https://api.autobook.tech, DNS resolves to the ALB's IP,
# the ALB forwards the request to an ECS container running the API service.
#
# We use an ALIAS A record (not a CNAME) because:
#   1. Free — Route53 doesn't charge for alias queries to AWS resources
#   2. Faster — returns the ALB's IP directly (no second DNS lookup)
#   3. Health-aware — Route53 checks ALB health automatically
#   4. Works at zone apex — CNAMEs can't be used for root domains (DNS spec)
resource "aws_route53_record" "api" {
  zone_id = var.zone_id                                 # DNS zone for autobook.tech
  name    = "${local.api_subdomain}.${var.domain_name}" # e.g. "api.autobook.tech" or "api-dev.autobook.tech"
  type    = "A"                                         # A record (returns IP addresses)

  # Alias block — tells Route53 "resolve this to the ALB's current IPs"
  # Unlike a regular A record (static IP), alias automatically updates when ALB IPs change
  alias {
    name                   = var.alb_dns_name # ALB's AWS-assigned DNS name
    zone_id                = var.alb_zone_id  # ALB's AWS-managed hosted zone (not our Route53 zone)
    evaluate_target_health = true             # If ALB is unhealthy, Route53 stops returning this record
  }
}
