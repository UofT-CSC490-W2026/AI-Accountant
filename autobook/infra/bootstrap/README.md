# Bootstrap

Creates the S3 bucket and DynamoDB table that all other stacks use for Terraform state storage and locking.

Run once. Uses local state (no backend.tf) because the remote backend doesn't exist yet — this is what creates it.

## Resources

- **S3 bucket** (`autobook-tfstate-<account_id>`) — stores .tfstate files, versioned, encrypted, no public access
- **DynamoDB table** (`autobook-terraform-locks`) — prevents concurrent `terraform apply`

## Usage

```bash
cd infra/bootstrap
terraform init
terraform plan
terraform apply
```

## Outputs

| Name | Description |
|------|-------------|
| state_bucket | S3 bucket name — goes into every other stack's backend.tf |
| lock_table | DynamoDB table name — goes into every other stack's backend.tf |

## Note

These resources already exist from the previous infra setup. No need to apply again — just reference the outputs in other stacks.
