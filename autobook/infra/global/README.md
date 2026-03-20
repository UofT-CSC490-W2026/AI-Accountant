# Global

Resources that exist once per AWS account, shared by all environments.

## Resources

- **Route53 zone** (`autobook.tech`) — DNS lookup table for the domain
- **ACM wildcard cert** (`*.autobook.tech`) — TLS certificate for HTTPS on all subdomains
- **Cert validation records** — DNS records that prove domain ownership to AWS
- **Frontend DNS** — `autobook.tech` and `www.autobook.tech` → Netlify
- **GitHub OIDC provider** — lets GitHub Actions assume AWS roles without stored credentials

## Usage

```bash
cd infra/global
terraform init
terraform plan
terraform apply
```

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| zone_id | Route53 zone ID | environments — to add API subdomain records |
| cert_arn | ACM wildcard cert ARN | environments — to attach to ALB for HTTPS |
| oidc_provider_arn | GitHub OIDC provider ARN | environments — for CI/CD deploy roles |

## Prerequisites

- Bootstrap stack must be applied first (S3 state bucket + DynamoDB lock table)
