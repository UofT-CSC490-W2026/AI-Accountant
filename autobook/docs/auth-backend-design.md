# Auth Backend Design

This backend treats Amazon Cognito as the identity provider. FastAPI does not own
primary login, password reset, or JWT issuance. Its auth responsibilities are:

- verify Cognito-issued JWTs
- extract user identity and role claims
- protect routes with claim-based authorization
- sync a local user record only for app-specific profile and account-state fields

## Request Flow

1. The client authenticates with Cognito and sends a Cognito bearer token to the API.
2. `deps/auth.py` verifies the JWT signature against the Cognito JWKS.
3. The dependency validates issuer, token use, expiry, and app client id.
4. The dependency derives the effective app role from Cognito claims.
5. The backend loads or syncs a local `UserModel` keyed by the Cognito `sub`.
6. Route handlers use the verified auth context for identity and authorization.

## Token Verification

`services/user/token_service.py` is responsible for Cognito JWT verification.

- expected issuer: `https://cognito-idp.<region>.amazonaws.com/<user_pool_id>`
- expected algorithm: `RS256`
- supported token types: Cognito `access` and `id` tokens
- signing keys: Cognito JWKS, loaded from the issuer JWKS endpoint or from
  `AUTOBOOK_COGNITO_JWKS_JSON` for tests

Validation rules:

- reject missing or malformed bearer tokens with `401`
- reject unknown `kid` values with `401`
- reject invalid signatures with `401`
- reject expired tokens with `401`
- reject tokens whose issuer does not match the configured user pool with `401`
- reject tokens whose client id or audience does not match the configured Cognito app client with `401`

## Claim Contract

Frontend and infra need to guarantee a consistent Cognito claim shape for the API.

Required claims for every token accepted by the backend:

- `sub`: stable Cognito user identifier; this is the backend user id
- `iss`: must match the configured Cognito user pool issuer
- `exp`: token expiry
- `iat`: token issued-at time
- `token_use`: must be either `access` or `id`

Required claim by token type:

- access token: `client_id`
- id token: `aud`

Recommended profile claims:

- `email`: primary user email for local profile sync
- `name`: display name for local profile sync
- `cognito:username`: fallback identifier if email is missing

Role source contract:

- preferred role source: `custom:role`
- accepted fallback role source: `cognito:groups`
- accepted role values: `regular`, `manager`, `superuser`

Role resolution policy:

1. If `custom:role` is present and recognized, use it.
2. Otherwise inspect `cognito:groups` and pick the highest recognized role.
3. If neither claim provides a recognized role, default to `regular`.

Infra should ensure either `custom:role` or `cognito:groups` is populated for any user
that needs manager or superuser access. Frontend should send the Cognito bearer token as
issued and should not transform or strip claims.

## Identity And Roles

The backend uses Cognito claims as the auth source of truth.

- identity key: `sub`
- optional profile claims: `email`, `name`, `cognito:username`
- role claims:
  - preferred: `custom:role`
  - fallback: `cognito:groups`

Mapped application roles:

- `regular`
- `manager`
- `superuser`

If no recognized role claim is present, the backend falls back to `regular`.

## Local User Record

The local user record is not the identity provider. It stores application state that
does not belong in Cognito.

Current local fields:

- `id`: Cognito `sub`
- `email`
- `full_name`
- `role`: last synced effective Cognito role
- `identity_provider`
- `is_verified`
- `is_suspicious`
- `is_disabled`
- `last_authenticated_at`

`services/user/user_service.py:sync_cognito_user(...)` performs the sync.

Local account-state flags are still enforced after token verification:

- disabled users are rejected with `403`
- unverified users are rejected with `403`
- suspicious users are rejected with `403`

## Routes

The backend auth router now exposes only Cognito-compatible API endpoints:

- `GET /auth/me`
- `PATCH /auth/me`
- `POST /auth/logout`
- `POST /auth/users/{user_id}/verify`
- `POST /auth/users/{user_id}/clear-suspicious`

Removed from the API:

- `POST /auth/login`
- `PATCH /auth/me/password`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- local role-management endpoints that implied backend-owned auth authority

`POST /auth/logout` is informational only. Sign-out must happen through the Cognito
client flow or Cognito Hosted UI flow used by the frontend.

## Configuration

Required runtime configuration:

- `AWS_REGION`
- `COGNITO_POOL_ID`
- `COGNITO_CLIENT_ID`

Optional test override:

- `AUTOBOOK_COGNITO_JWKS_JSON`

## Testing

`tests/test_auth.py` uses Cognito-shaped RS256 tokens and an injected JWKS to cover:

- valid token access to `/auth/me`
- local user sync for a new Cognito identity
- `custom:role` precedence over `cognito:groups`
- regular-role fallback when role claims are unrecognized
- manager-only route protection
- malformed token rejection
- signature rejection
- expiry rejection
- issuer rejection
- client id rejection
