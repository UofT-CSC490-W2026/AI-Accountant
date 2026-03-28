# =============================================================================
# Dev environment values — non-secret configuration only
# =============================================================================
# Secrets are passed via environment variables (TF_VAR_*), never here:
#   export TF_VAR_db_password="..."
#   export TF_VAR_qdrant_cloud_api_key="..."
#   export TF_VAR_qdrant_cloud_account_id="..."

# --- Core ---
project     = "autobook"
environment = "dev"
region      = "ca-central-1"
account_id  = "609092547371"

# --- DNS ---
domain_name = "autobook.tech"

# --- Database ---
db_instance_class = "db.t4g.micro" # 2 vCPUs, 1 GB RAM — cheapest option, fine for dev

# --- CI/CD ---
github_repo = "UofT-CSC490-W2026/AI-Accountant"

# --- Monitoring ---
alert_email        = "autobook@pm.me"
monthly_budget_usd = "100.0"
