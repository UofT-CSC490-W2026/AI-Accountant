# --- Values other modules need from DNS ---

# The full API URL that the frontend and external clients use
# Example: "api.autobook.tech" (prod) or "api-dev.autobook.tech" (dev)
output "api_fqdn" {
  description = "Fully qualified domain name for the API endpoint"
  value       = aws_route53_record.api.fqdn
}
