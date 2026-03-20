# Storage

Creates the S3 bucket that stores file uploads, processed data, and ML training artifacts.

## What it creates

- **S3 bucket** — named `{project}-{env}-data-{account_id}` for global uniqueness
- **Versioning** — keeps every version of every file (recover from accidental overwrites/deletes)
- **Encryption** — AES-256 at rest on all objects (automatic, free)
- **Public access block** — blocks all four ways a bucket can be made public
- **Lifecycle rules**:
  - `processed/` objects move to Infrequent Access after 90 days (saves ~45% per GB)
  - Incomplete multipart uploads cleaned up after 7 days

## Usage

```hcl
# Dev — defaults are fine
module "storage" {
  source = "../../modules/storage"

  project    = "autobook"
  environment = "dev"
  account_id = "609092547371"
}

# Prod — keep processed files in Standard longer, protect against accidental deletion
module "storage" {
  source = "../../modules/storage"

  project           = "autobook"
  environment       = "prod"
  account_id        = "609092547371"
  ia_transition_days = 180
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| account_id | string | — | AWS account ID (for globally unique bucket name) |
| ia_transition_days | number | 90 | Days before processed/ objects move to IA (0 = disabled) |
| abort_incomplete_multipart_days | number | 7 | Days before incomplete uploads are cleaned up |
| force_destroy | bool | false | Allow destroying bucket with objects inside |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| bucket_arn | S3 bucket ARN | iam (scoped S3 policies) |
| bucket_id | S3 bucket name | compute (ECS container env vars) |
