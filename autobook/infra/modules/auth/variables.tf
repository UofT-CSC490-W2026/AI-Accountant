# --- Required inputs (no defaults — caller must provide) ---

# Used in resource names like "autobook-dev-users"
variable "project" {
  type        = string
  description = "Project name, used in resource naming"
}

# Used in resource names like "autobook-dev-users"
variable "environment" {
  type        = string
  description = "Deployment environment, used in resource naming"
}

# --- Optional inputs (safe defaults provided) ---

# Password policy — how strong user passwords must be
# These defaults follow AWS recommended minimums

# Minimum password length — 8 is the AWS default, NIST recommends 8+
variable "password_min_length" {
  type        = number
  description = "Minimum password length"
  default     = 8
}

# Whether passwords must contain uppercase, lowercase, numbers, symbols
variable "password_require_uppercase" {
  type        = bool
  description = "Require at least one uppercase letter in passwords"
  default     = true
}

variable "password_require_lowercase" {
  type        = bool
  description = "Require at least one lowercase letter in passwords"
  default     = true
}

variable "password_require_numbers" {
  type        = bool
  description = "Require at least one number in passwords"
  default     = true
}

variable "password_require_symbols" {
  type        = bool
  description = "Require at least one special character in passwords"
  default     = true
}

# MFA (multi-factor authentication) — adds a second verification step at login
# "OFF" = no MFA, "OPTIONAL" = users can enable it, "ON" = all users must use it
variable "mfa_configuration" {
  type        = string
  description = "MFA mode: OFF, OPTIONAL, or ON"
  default     = "OPTIONAL"

  validation {
    condition     = contains(["OFF", "OPTIONAL", "ON"], var.mfa_configuration)
    error_message = "mfa_configuration must be OFF, OPTIONAL, or ON."
  }
}

# OAuth callback URLs — where Cognito redirects after login/logout
# The frontend app must be listed here or Cognito will reject the redirect
variable "callback_urls" {
  type        = list(string)
  description = "Allowed OAuth callback URLs after login (frontend app URLs)"
  default     = ["http://localhost:3000/callback"]
}

variable "logout_urls" {
  type        = list(string)
  description = "Allowed URLs to redirect to after logout"
  default     = ["http://localhost:3000"]
}

# Access token validity — how long a user stays logged in before needing to re-authenticate
variable "access_token_validity_hours" {
  type        = number
  description = "Hours before access tokens expire (user must re-authenticate)"
  default     = 1
}

# Refresh token validity — how long before a user must fully re-login (not just refresh)
variable "refresh_token_validity_days" {
  type        = number
  description = "Days before refresh tokens expire (user must re-login)"
  default     = 30
}

# Backend authorization uses Cognito groups as the canonical app role source.
# The group names are intentionally the same as the backend's role values.
variable "role_group_names" {
  type        = map(number)
  description = "Map of Cognito role group name -> precedence for backend authorization"
  default = {
    regular   = 0
    manager   = 10
    superuser = 20
  }
}
