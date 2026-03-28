# Secrets

Creates the Secrets Manager secret that stores database credentials as a JSON blob, injected into ECS containers at startup.

## What it creates

- **Secret** — named container in Secrets Manager (encrypted, access-controlled, audited)
- **Secret version** — the actual JSON value with DB connection details

## How it works

```
Terraform creates secret with DB credentials (JSON)
    ↓
ECS task definition references secret ARN with JSON key selectors
    ↓
At container startup, ECS agent reads secret and sets env vars:
    DB_HOST=autobook-dev-db.abc123.rds.amazonaws.com
    DB_PORT=5432
    DB_NAME=autobook
    DB_USER=autobook
    DB_PASSWORD=***
    ↓
Application code reads env vars — never touches Secrets Manager directly
```

## Usage

```hcl
# Dev — immediate deletion, no recovery window
module "secrets" {
  source = "../../modules/secrets"

  project     = "autobook"
  environment = "dev"
  db_address  = module.database.db_address
  db_password = var.db_password  # From TF_VAR_db_password
}

# Prod — 30-day recovery window for accidental deletion protection
module "secrets" {
  source = "../../modules/secrets"

  project                 = "autobook"
  environment             = "prod"
  db_address              = module.database.db_address
  db_password             = var.db_password
  recovery_window_in_days = 30
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| db_address | string | — | RDS hostname (from database module) |
| db_password | string | — | Database password (sensitive, via TF_VAR) |
| db_port | number | 5432 | Database port |
| db_name | string | null | Database name (null = project name) |
| db_username | string | null | Database username (null = project name) |
| recovery_window_in_days | number | 0 | Days before permanent deletion (0 = immediate) |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| db_credentials_secret_arn | Secret ARN | compute (ECS task definition secrets block) |

## Security notes

- Secret value is in Terraform state — state is encrypted in S3 with AES-256
- Only the ECS execution role can read the secret (scoped by naming pattern in IAM module)
- CloudTrail logs every secret access (who, when, which secret)
- Password is never in code or tfvars — injected via `TF_VAR_db_password` at runtime
