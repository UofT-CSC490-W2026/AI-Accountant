# Auth

Creates the Cognito user pool that handles user authentication — sign up, login, password reset, MFA, and token issuance.

## What it creates

- **User pool** — the user directory (email-based sign up, password policy, MFA, account recovery)
- **App client** — public client for the frontend SPA (no secret, SRP auth, Authorization Code flow)
- **User pool domain** — hosted login page URL (`autobook-dev.auth.ca-central-1.amazoncognito.com`)

## Usage

```hcl
# Dev — defaults, localhost callbacks
module "auth" {
  source = "../../modules/auth"

  project     = "autobook"
  environment = "dev"
}

# Prod — MFA required, production callback URLs
module "auth" {
  source = "../../modules/auth"

  project           = "autobook"
  environment       = "prod"
  mfa_configuration = "ON"
  callback_urls     = ["https://autobook.tech/callback"]
  logout_urls       = ["https://autobook.tech"]
}
```

## Inputs

| Name | Type | Default | Description |
|------|------|---------|-------------|
| project | string | — | Project name |
| environment | string | — | Deployment environment |
| password_min_length | number | 8 | Minimum password length |
| password_require_uppercase | bool | true | Require uppercase letters |
| password_require_lowercase | bool | true | Require lowercase letters |
| password_require_numbers | bool | true | Require numbers |
| password_require_symbols | bool | true | Require special characters |
| mfa_configuration | string | "OPTIONAL" | MFA mode: OFF, OPTIONAL, or ON |
| callback_urls | list(string) | ["http://localhost:3000/callback"] | OAuth redirect URLs after login |
| logout_urls | list(string) | ["http://localhost:3000"] | Redirect URLs after logout |
| access_token_validity_hours | number | 1 | Hours before access token expires |
| refresh_token_validity_days | number | 30 | Days before refresh token expires |

## Outputs

| Name | Description | Used by |
|------|-------------|---------|
| user_pool_id | Cognito user pool ID | compute (API Gateway auth), api-gateway (WebSocket auth) |
| client_id | App client ID | compute (frontend config) |
