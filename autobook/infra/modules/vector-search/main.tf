# Naming convention
locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"
}

# =============================================================================
# BOOKING PACKAGES — query available Qdrant Cloud resource configurations
# =============================================================================
# Qdrant Cloud uses "packages" to define node sizes (CPU, RAM, disk).
# This data source fetches all available packages for our cloud provider
# and region, then we filter to find the one matching our desired specs.
#
# This is similar to how AWS has instance types (t3.micro, m5.large) —
# Qdrant Cloud has packages that bundle CPU, RAM, and disk together.
data "qdrant-cloud_booking_packages" "available" {
  cloud_provider = "aws"            # We run on AWS (matches our ECS/RDS/Redis)
  cloud_region   = var.cloud_region # Same region as our other infrastructure
}

# Filter packages to find the one matching our desired CPU and RAM
# The data source returns all packages — we pick the right one here
locals {
  # Find the package that matches our requested CPU and RAM allocation
  # Returns a list (should be exactly 1 match) — we take the first
  desired_package = [
    for pkg in data.qdrant-cloud_booking_packages.available.packages : pkg
    if pkg.resource_configuration[0].cpu == var.node_cpu
    && pkg.resource_configuration[0].ram == var.node_ram
  ]
}

# Guard against no matching package — give a clear error instead of cryptic index crash
check "package_exists" {
  assert {
    condition     = length(local.desired_package) > 0
    error_message = "No Qdrant Cloud package found for cpu=${var.node_cpu}, ram=${var.node_ram}. Check available packages in your region."
  }
}

# =============================================================================
# QDRANT CLUSTER — managed vector database for RAG retrieval
# =============================================================================
# Qdrant stores vector embeddings of journal entries and corrections.
# Two collections serve the LLM pipeline:
#   1. Generator RAG: positive examples (correctly resolved entries)
#   2. Evaluator RAG: correction examples (human-overridden entries)
#
# How it fits in the system:
#   - Flywheel Worker embeds new entries (Cohere Embed v4 on Bedrock)
#     and inserts vectors into Qdrant
#   - LLM Worker queries Qdrant for similar examples to include in
#     Generator/Evaluator prompts (few-shot learning)
#   - As more entries are processed, RAG quality improves (learning flywheel)
#
# This is a managed cluster on Qdrant Cloud — no VPC, no EC2, no Kubernetes.
# ECS services connect over HTTPS using the URL and API key.
resource "qdrant-cloud_accounts_cluster" "main" {
  name           = "${local.name}-qdrant"                                      # e.g. "autobook-dev-qdrant"
  cloud_provider = data.qdrant-cloud_booking_packages.available.cloud_provider # "aws"
  cloud_region   = data.qdrant-cloud_booking_packages.available.cloud_region   # e.g. "ca-central-1"

  # Cluster configuration — node count, database settings, and package selection
  configuration {
    number_of_nodes = var.number_of_nodes # 1 for dev, 3+ for prod (HA with replication)

    # Database engine settings
    database_configuration {
      service {
        jwt_rbac = var.jwt_rbac # Enable JWT-based access control (recommended)
      }
    }

    # Node size — selected from the filtered booking package
    node_configuration {
      package_id = local.desired_package[0].id # Package matching our CPU/RAM requirements
    }
  }
}

# =============================================================================
# DATABASE API KEY — authentication for ECS services to access Qdrant
# =============================================================================
# This creates an API key scoped to this specific cluster.
# ECS containers use this key in the QDRANT_API_KEY environment variable
# to authenticate when inserting/querying vectors.
#
# IMPORTANT: The key value is only available at creation time.
# Terraform stores it in state (encrypted via S3 backend).
# If the key is lost, create a new one and rotate in ECS task definitions.
resource "qdrant-cloud_accounts_database_api_key_v2" "main" {
  cluster_id = qdrant-cloud_accounts_cluster.main.id # Scoped to our cluster
  name       = "${local.name}-api-key"               # Descriptive name for the key
}
