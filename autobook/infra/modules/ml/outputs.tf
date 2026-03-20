# --- Values other modules need from ml ---

# The endpoint name is what ECS services use to call sagemaker:InvokeEndpoint
# Passed as an environment variable to model and flywheel containers
# Example: "autobook-dev-classifier"
output "endpoint_name" {
  description = "SageMaker endpoint name — passed to ECS services as env var for inference calls"
  value       = var.model_image != null ? aws_sagemaker_endpoint.main[0].name : null
}

# The SageMaker execution role ARN — needed by flywheel worker when creating
# training jobs (iam:PassRole to SageMaker)
output "sagemaker_role_arn" {
  description = "SageMaker execution role ARN — used by training jobs and endpoint"
  value       = aws_iam_role.sagemaker.arn
}
