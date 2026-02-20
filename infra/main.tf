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
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "autobook"
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

# --- Global resources: look up, don't create ---
data "aws_route53_zone" "main" {
  name = var.domain_name
}

data "aws_acm_certificate" "main" {
  domain      = "*.${var.domain_name}"
  statuses    = ["ISSUED"]
  most_recent = true
}

# --- Module wiring ---

module "networking" {
  source = "./modules/networking"
  env    = var.env
  region = var.aws_region
}

module "iam" {
  source               = "./modules/iam"
  account_id           = data.aws_caller_identity.current.account_id
  env                  = var.env
  region               = var.aws_region
  bucket_name_prefix   = var.bucket_name_prefix
  secret_name_prefix   = var.secret_name_prefix
  service_name_prefix  = var.service_name_prefix
  github_repo          = var.github_repo
}

module "auth" {
  source = "./modules/auth"
  env    = var.env
}

module "storage" {
  source             = "./modules/storage"
  env                = var.env
  account_id         = data.aws_caller_identity.current.account_id
  bucket_name_prefix = var.bucket_name_prefix
}

module "database" {
  source              = "./modules/database"
  env                 = var.env
  db_password         = var.db_password
  db_instance_class   = var.db_instance_class
  private_subnet_ids  = module.networking.private_subnet_ids
  db_sg_id            = module.networking.db_sg_id
  restore_snapshot_id = var.restore_snapshot_id
}

module "secrets" {
  source             = "./modules/secrets"
  env                = var.env
  db_password        = var.db_password
  db_address         = module.database.address
  secret_name_prefix = var.secret_name_prefix
}

module "compute" {
  source                    = "./modules/compute"
  env                       = var.env
  aws_region                = var.aws_region
  vpc_id                    = module.networking.vpc_id
  public_subnet_ids         = module.networking.public_subnet_ids
  alb_sg_id                 = module.networking.alb_sg_id
  app_sg_id                 = module.networking.app_sg_id
  ecs_execution_role_arn    = module.iam.ecs_execution_role_arn
  ecs_task_role_arn         = module.iam.ecs_task_role_arn
  cert_arn                  = data.aws_acm_certificate.main.arn
  zone_id                   = data.aws_route53_zone.main.zone_id
  api_subdomain             = var.api_subdomain
  domain_name               = var.domain_name
  cluster_name_prefix       = var.cluster_name_prefix
  service_name_prefix       = var.service_name_prefix
  db_credentials_secret_arn = module.secrets.db_credentials_secret_arn
  cognito_pool_id           = module.auth.user_pool_id
  cognito_client_id         = module.auth.client_id
  s3_bucket                 = module.storage.bucket_id
}

module "monitoring" {
  source         = "./modules/monitoring"
  env            = var.env
  cluster_name   = module.compute.cluster_name
  service_name   = module.compute.service_name
  alb_arn_suffix = module.compute.alb_arn_suffix
  db_instance_id = module.database.instance_id
  alert_email    = var.alert_email
}

module "backup" {
  source          = "./modules/backup"
  env             = var.env
  db_instance_arn = module.database.instance_arn
}
