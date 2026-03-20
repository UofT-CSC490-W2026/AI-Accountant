# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-qdrant"
variable "project" {
  type        = string
  description = "Project name, used in cluster naming"
}

# Used in cluster name to distinguish dev vs prod clusters
variable "environment" {
  type        = string
  description = "Deployment environment (dev, prod)"
}

# --- Optional inputs (safe defaults provided) ---

# AWS region where the Qdrant Cloud cluster runs
# Qdrant Cloud is not available in all AWS regions. Verified available regions:
#   us-east-1, us-west-2, eu-west-1, ap-northeast-1
# ca-central-1 is NOT supported — use us-east-1 for lowest latency from ca-central-1
variable "cloud_region" {
  type        = string
  description = "AWS region for the Qdrant Cloud cluster"
  default     = "us-east-1"
}

# Number of Qdrant nodes in the cluster
# 1 for dev (cheapest), 3+ for prod (high availability with replication)
variable "number_of_nodes" {
  type        = number
  description = "Number of nodes in the Qdrant cluster"
  default     = 1
}

# CPU allocation per node — Qdrant uses Kubernetes-style notation
# "500m" = 0.5 vCPU (enough for dev), "1000m" = 1 vCPU (prod)
variable "node_cpu" {
  type        = string
  description = "CPU per node in Kubernetes notation (e.g. 500m, 1000m)"
  default     = "500m"
}

# RAM allocation per node — determines how many vectors fit in memory
# "1Gi" for dev (~100K vectors), "2Gi"+ for prod
# Our embedding model (Cohere Embed v4) produces 1536-dim vectors
# Each vector ≈ 6KB → 1GB RAM ≈ 150K vectors
# Available packages: free2 (500m/1Gi), gpx1 (500m/2Gi), mx1 (500m/4Gi), ...
variable "node_ram" {
  type        = string
  description = "RAM per node in Kubernetes notation (e.g. 1Gi, 2Gi)"
  default     = "1Gi"
}

# Enable JWT-based Role-Based Access Control on the Qdrant database
# Recommended for production — controls read/write access per collection
variable "jwt_rbac" {
  type        = bool
  description = "Enable JWT RBAC on the Qdrant database"
  default     = true
}
