# Database

Creates the RDS PostgreSQL instance that stores all application data.

## What it creates

- **DB subnet group** — places the database in private subnets (no internet access)
- **RDS PostgreSQL 16 instance** — single instance, handles all 9 tables

## Usage

```hcl
# Dev — small, no redundancy
module "database" {
  source = "../../modules/database"

  project            = "autobook"
  environment        = "dev"
  private_subnet_ids = module.networking.private_subnet_ids
  db_sg_id           = module.networking.db_sg_id
  db_instance_class  = "db.t4g.micro"
  db_password        = var.db_password
}

# Prod — larger, with failover and deletion protection
module "database" {
  source = "../../modules/database"

  project                 = "autobook"
  environment             = "prod"
  private_subnet_ids      = module.networking.private_subnet_ids
  db_sg_id                = module.networking.db_sg_id
  db_instance_class       = "db.t4g.medium"
  db_password             = var.db_password
  multi_az                = true
  backup_retention_period = 30
  deletion_protection     = true
  skip_final_snapshot     = false
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| private_subnet_ids | list(string) | — | Subnets for the database |
| db_sg_id | string | — | Security group allowing ECS access |
| db_instance_class | string | — | Machine size |
| db_password | string | — | Master password (sensitive) |
| allocated_storage | number | 20 | Disk space in GB |
| multi_az | bool | false | Standby replica in second AZ |
| backup_retention_period | number | 7 | Days to keep backups |
| deletion_protection | bool | false | Block accidental deletion |
| skip_final_snapshot | bool | true | Skip snapshot on delete |
| restore_snapshot_id | string | null | Snapshot to restore from |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| address | Database hostname | secrets (connection string) |
| instance_id | RDS identifier | monitoring (CloudWatch alarms) |
| instance_arn | RDS ARN | backup (backup plans) |
