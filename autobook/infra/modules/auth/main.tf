# Naming convention
locals {
  name = "${var.project}-${var.environment}" # e.g. "autobook-dev"
}

# =============================================================================
# COGNITO USER POOL — the user directory
# =============================================================================
# A user pool is like a database of user accounts managed by AWS.
# Users sign up with email + password, Cognito handles:
#   - Account creation and verification
#   - Password hashing and storage
#   - Login and token issuance (JWT tokens)
#   - Password reset flows
#   - MFA (multi-factor authentication)
#
# Our app has two user types (free users, pro/accountant users) — both stored
# in the same pool, differentiated by a Cognito group or custom attribute.
resource "aws_cognito_user_pool" "main" {
  name = "${local.name}-users" # e.g. "autobook-dev-users"

  # --- Sign-up settings ---
  # Users sign in with their email address (not a separate username)
  username_attributes = ["email"]

  # Cognito automatically sends a verification email when a user signs up
  auto_verified_attributes = ["email"]

  # --- Password policy ---
  password_policy {
    minimum_length                   = var.password_min_length        # Default: 8
    require_uppercase                = var.password_require_uppercase # Default: true
    require_lowercase                = var.password_require_lowercase # Default: true
    require_numbers                  = var.password_require_numbers   # Default: true
    require_symbols                  = var.password_require_symbols   # Default: true
    temporary_password_validity_days = 7                              # Admin-created passwords expire in 7 days
  }

  # --- MFA (multi-factor authentication) ---
  # Adds a second verification step — even if password is stolen, attacker needs the code
  mfa_configuration = var.mfa_configuration # Default: "OPTIONAL"

  # Software token MFA = authenticator app (Google Authenticator, Authy, etc.)
  # Only configured when MFA is OPTIONAL or ON
  dynamic "software_token_mfa_configuration" {
    for_each = var.mfa_configuration != "OFF" ? [1] : []
    content {
      enabled = true # Allow authenticator app as MFA method
    }
  }

  # --- Account recovery ---
  # When a user forgets their password, send a reset code to their verified email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email" # Send recovery code to email
      priority = 1                # First (and only) recovery method
    }
  }

  # --- Security: require email re-verification on change ---
  # If a user changes their email, they must verify the new one before it takes effect.
  # Prevents account takeover via email change to an attacker-controlled address.
  user_attribute_update_settings {
    attributes_require_verification_before_update = ["email"]
  }

  # --- Schema: email is required ---
  schema {
    name                = "email"
    attribute_data_type = "String"
    required            = true # Users must provide an email
    mutable             = true # Email can be changed later

    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  tags = { Name = "${local.name}-users" }
}

# =============================================================================
# APP CLIENT — how the frontend application talks to Cognito
# =============================================================================
# An app client is a set of credentials that identifies your frontend app.
# Think of it as an API key for Cognito — the frontend uses this client ID
# when sending login/signup requests.
#
# This is a PUBLIC client (no secret) because the frontend is a single-page app
# running in the user's browser — a secret would be visible in the JavaScript source.
resource "aws_cognito_user_pool_client" "main" {
  name         = "${local.name}-app" # e.g. "autobook-dev-app"
  user_pool_id = aws_cognito_user_pool.main.id

  # --- No client secret (public client) ---
  # SPAs and mobile apps cannot securely store a secret — it would be in the JS bundle
  generate_secret = false

  # --- Auth flows: which login methods are allowed ---
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",     # Secure Remote Password — password never sent over the wire
    "ALLOW_REFRESH_TOKEN_AUTH" # Allow refreshing expired access tokens without re-login
  ]

  # --- OAuth settings ---
  allowed_oauth_flows                  = ["code"]                       # Authorization Code Grant (most secure)
  allowed_oauth_flows_user_pool_client = true                           # Enable OAuth for this client
  allowed_oauth_scopes                 = ["openid", "email", "profile"] # What user info the app can access
  callback_urls                        = var.callback_urls              # Where to redirect after login
  logout_urls                          = var.logout_urls                # Where to redirect after logout
  supported_identity_providers         = ["COGNITO"]                    # Only Cognito (no Google/Facebook login)

  # --- Token lifetimes ---
  access_token_validity  = var.access_token_validity_hours # Default: 1 hour
  refresh_token_validity = var.refresh_token_validity_days # Default: 30 days

  token_validity_units {
    access_token  = "hours" # Explicitly set units (not ambiguous)
    refresh_token = "days"
  }

  # --- Security: don't leak user existence ---
  # Returns the same error for "user not found" and "wrong password"
  prevent_user_existence_errors = "ENABLED"
}

# =============================================================================
# USER POOL DOMAIN — hosted login page URL
# =============================================================================
# Cognito provides a hosted login/signup page at:
#   https://{domain-prefix}.auth.{region}.amazoncognito.com
#
# This is useful for:
#   - Quick setup without building a custom login page
#   - OAuth redirect flows (Authorization Code Grant)
#   - The hosted UI handles email verification, password reset, MFA
#
# For production, you can replace this with a custom domain (e.g. auth.autobook.tech).
resource "aws_cognito_user_pool_domain" "main" {
  domain       = local.name # e.g. "autobook-dev" → autobook-dev.auth.ca-central-1.amazoncognito.com
  user_pool_id = aws_cognito_user_pool.main.id
}
