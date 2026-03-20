# DNS

Creates the Route53 alias record that maps the API subdomain to the ALB.

## What it creates

- **Route53 A record (alias)** — maps `api.autobook.tech` (prod) or `api-dev.autobook.tech` (dev) to the ALB

## How traffic flows

```
User visits https://api.autobook.tech
  → Route53 resolves alias to ALB IP addresses
    → ALB terminates TLS, forwards HTTP to API containers
```

## Why alias (not CNAME)?

| Feature | Alias A Record | CNAME |
|---------|---------------|-------|
| Cost | Free for AWS targets | $0.40/million queries |
| Speed | 1 DNS hop (returns IPs directly) | 2 hops (extra lookup) |
| Health check | Automatic (ALB health) | Manual |
| Zone apex | Works | Doesn't work (DNS spec) |

## Usage

```hcl
# Dev — api-dev.autobook.tech
module "dns" {
  source = "../../modules/dns"

  project      = "autobook"
  environment  = "dev"
  domain_name  = "autobook.tech"
  zone_id      = data.terraform_remote_state.global.outputs.zone_id
  alb_dns_name = module.compute.alb_dns_name
  alb_zone_id  = module.compute.alb_zone_id
}

# Prod — api.autobook.tech
module "dns" {
  source = "../../modules/dns"

  project      = "autobook"
  environment  = "prod"
  domain_name  = "autobook.tech"
  zone_id      = data.terraform_remote_state.global.outputs.zone_id
  alb_dns_name = module.compute.alb_dns_name
  alb_zone_id  = module.compute.alb_zone_id
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| domain_name | string | — | Root domain (e.g. "autobook.tech") |
| zone_id | string | — | Route53 zone ID (from global) |
| alb_dns_name | string | — | ALB DNS name (from compute) |
| alb_zone_id | string | — | ALB hosted zone ID (from compute) |
| api_subdomain | string | null | Custom subdomain (null = auto: "api" for prod, "api-dev" for dev) |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| api_fqdn | Full API domain name | frontend config, API Gateway |
