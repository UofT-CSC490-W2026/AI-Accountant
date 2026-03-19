# Auth Backend Design

## Scope

This document replaces the original authorization PDF with a repo-specific design for
`autobook/src/backend`. The system uses bearer-token API auth with short-lived JWT access
tokens. It does not assume server-side sessions unless a later refresh-token flow is added.

The main goal is to keep the module split from the original design while making the security
rules explicit enough to implement safely.

## Design Principles

1. Routes stay thin and contain HTTP concerns only.
2. Services contain business logic and orchestration.
3. JWTs identify the user, but the database is the source of truth for role and account state.
4. Sensitive auth flows are single-use, short-lived, rate limited, and auditable.
5. Application roles do not imply direct database privileges.

## Package Layout

Use the existing backend structure:

```text
autobook/src/backend/
  routes/
    auth.py
  services/user/
    auth_service.py
    token_service.py
    password_service.py
    user_service.py
  schema/
    auth.py
    user.py
  models/
    user_model.py
  deps/
    auth.py
  db/
    session.py
    base.py
  config.py
  main.py
```

Responsibilities:

- `routes/auth.py`: FastAPI endpoints, request validation, HTTP status codes, response shaping.
- `services/user/auth_service.py`: login, password change, forgot/reset password, account-state checks.
- `services/user/token_service.py`: JWT create/decode/expiry handling only.
- `services/user/password_service.py`: password hashing, verification, and password policy helpers.
- `services/user/user_service.py`: user lookups, updates, role changes, verification, and audit event creation hooks.
- `schema/auth.py`: auth request and response models.
- `schema/user.py`: user-facing models, role enum, account-state enum.
- `models/user_model.py`: SQLAlchemy user model and persisted auth-related fields.
- `deps/auth.py`: `get_current_user`, `require_role`, and active-account enforcement.
- `config.py`: JWT settings, password-reset settings, and security-related config values.

## Roles

Use these exact role strings:

- `regular`
- `manager`
- `superuser`

Role meanings:

- `regular`: authenticated end user with access to their own account and accounting data.
- `manager`: can perform operational actions such as verifying users and clearing suspicious flags.
- `superuser`: can promote or demote roles and perform all application-level admin actions.

Do not encode "full system/database privileges" into the application role model. The application
database user must remain least-privilege regardless of the caller's app role.

## Account State Model

Authorization decisions depend on both role and account state. Add explicit account-state fields to
the user model instead of scattering booleans without defined semantics.

Required persisted fields:

- `role`
- `is_verified`
- `is_suspicious`
- `is_disabled`
- `password_hash`
- `password_changed_at`
- `token_version`
- `last_login_at`
- `last_failed_login_at`
- `failed_login_count`
- `reset_token_hash`
- `reset_token_expires_at`
- `reset_token_created_at`
- `reset_requested_at`

State semantics:

- unverified users may exist in the system but cannot access protected business endpoints until verified.
- suspicious users may authenticate only if the product explicitly allows it; otherwise reject login and protected requests until cleared by a manager.
- disabled users cannot log in and any previously issued token must stop working.

Enforcement rules:

1. Login must reject disabled accounts.
2. Login must reject accounts whose current state should block access.
3. `get_current_user` must reject deleted, disabled, or otherwise blocked accounts on every request.
4. Role checks must run against the live user record, not a JWT role claim.

## Authentication Model

### Login

`POST /auth/login` accepts email and password.

Flow:

1. Look up the user by normalized email.
2. If the user does not exist, return the same generic failure used for wrong passwords.
3. Check whether the account state allows login.
4. Verify the password hash.
5. On success, reset failed-login counters, update `last_login_at`, and issue a short-lived access token.
6. On failure, increment failure counters and apply lockout or backoff rules.

### Access Tokens

Access tokens are bearer JWTs with short expiry, for example 15 minutes. Required claims:

- `sub`: user id
- `exp`
- `iat`
- `jti`
- `token_version`

Optional informational claims such as `role` may be included for client display or logging, but they
must never be treated as the final authorization source.

### Logout

Because this design is bearer-token API auth without refresh tokens, `POST /auth/logout` is a client-side
logout acknowledgement only. The server can return success, but it does not revoke an already-issued
access token by itself.

The API contract must say this explicitly to avoid a false security guarantee.

If true revocation is required later, choose one of these designs and document it separately:

- short-lived access tokens plus refresh tokens stored server-side
- token-version invalidation checked on every request
- JWT denylist keyed by `jti`

## Authorization Model

### Current User Dependency

`deps/auth.py:get_current_user` must:

1. Read the bearer token.
2. Decode and validate the JWT signature and expiry.
3. Extract `sub` and `token_version`.
4. Load the user from the database.
5. Reject the request if the user does not exist, is disabled, is blocked by account state, or if
   the token version no longer matches.
6. Return the live user record.

This dependency is the central enforcement point for account-state checks.

### Role Enforcement

Implement:

- `require_role("manager")`
- `require_role("superuser")`

Use a simple hierarchy:

```python
ROLE_LEVEL = {
    "regular": 1,
    "manager": 2,
    "superuser": 3,
}
```

The dependency must compare the required role against `current_user.role` from the database-backed
user object returned by `get_current_user`.

## Password Rules

`services/user/password_service.py` is the only place that should know the hashing algorithm.

Requirements:

- Use a modern password hashing algorithm already supported by the stack.
- Never store or log plaintext passwords.
- Enforce a minimum password policy in one place.
- On password change or reset, update `password_changed_at`.
- On password change or reset, increment `token_version` so older access tokens are rejected on the
  next authenticated request.

## Forgot/Reset Password

This flow needs explicit controls because it is one of the highest-risk auth paths.

### Forgot Password

`POST /auth/forgot-password`:

1. Accepts an email address.
2. Returns a generic success response whether or not the account exists.
3. Applies per-account and per-IP rate limits.
4. If the account exists and is eligible, generate a high-entropy random reset token.
5. Store only a hash of the reset token plus its expiry and creation time.
6. Send the raw token out-of-band by email.

### Reset Password

`POST /auth/reset-password`:

1. Accepts the reset token and a new password.
2. Hashes the presented token and compares it to the stored hash.
3. Rejects expired, missing, or already-used tokens.
4. Updates the password hash.
5. Clears all reset-token fields.
6. Increments `token_version` to invalidate previously issued access tokens.
7. Writes an audit event.

Recommended reset-token properties:

- one-time use
- short expiry, such as 15 to 30 minutes
- hash stored server-side
- regenerated on each new reset request

## Endpoints

### `routes/auth.py`

Recommended endpoints:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `PATCH /auth/me`
- `PATCH /auth/me/password`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`

Behavior notes:

- `GET /auth/me` returns data from the live user record.
- `PATCH /auth/me` may update only the caller's own permitted profile fields.
- `PATCH /auth/me/password` requires the current password unless the change is happening through the reset flow.
- Manager and superuser user-management endpoints can live in `routes/auth.py` for now or move to a future `routes/users.py`.

## Schemas

### `schema/auth.py`

Define:

- `LoginRequest`
- `TokenResponse`
- `MessageResponse`
- `ChangePasswordRequest`
- `ForgotPasswordRequest`
- `ResetPasswordRequest`
- `TokenPayload`

`TokenResponse` should include:

- `access_token`
- `token_type`
- `expires_in`

### `schema/user.py`

Define:

- `UserRole`
- `UserSummary`
- `MeResponse`
- `UserUpdateRequest`
- `UpdateUserRoleRequest`

If account state is exposed to clients or admins, add explicit fields instead of inferred booleans.

## Audit Logging

The system must produce durable audit events for:

- login success
- login failure after authentication checks
- password change
- forgot-password request issuance
- password reset completion
- role promotion and demotion
- account verification
- suspicious-flag clearing
- account disable and re-enable actions

Each event should record:

- actor user id if available
- target user id
- event type
- timestamp
- request metadata such as IP and user agent when available

## Rate Limiting And Abuse Controls

At minimum, protect:

- `POST /auth/login`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- any manager or superuser mutation endpoints

Controls may be implemented with middleware, gateway policies, or backing storage, but the design
must guarantee:

- repeated login failures trigger backoff or lockout
- forgot-password requests cannot be spammed for a single account
- reset-token verification cannot be brute-forced

## Config

`config.py` should centralize:

- `SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `PASSWORD_RESET_TOKEN_TTL_MINUTES`
- `PASSWORD_RESET_MAX_REQUESTS_PER_HOUR`
- `LOGIN_MAX_ATTEMPTS`
- `LOGIN_LOCKOUT_MINUTES`
- `DATABASE_URL`

## Request Flows

### `POST /auth/login`

1. `routes/auth.py` receives `LoginRequest`.
2. `auth_service.login(...)` orchestrates the flow.
3. `user_service.get_by_email(...)` loads the user.
4. `auth_service` checks account state.
5. `password_service.verify_password(...)` verifies the password.
6. `token_service.create_access_token(...)` issues a JWT with `sub`, `jti`, and `token_version`.
7. Route returns `TokenResponse`.

### `GET /auth/me`

1. Route depends on `deps/auth.py:get_current_user`.
2. Dependency validates the bearer token.
3. `token_service.decode_access_token(...)` extracts `sub` and `token_version`.
4. `user_service.get_by_id(...)` fetches the user from the database.
5. Dependency verifies account state and token version.
6. Route returns `MeResponse`.

### `POST /auth/reset-password`

1. Route receives `ResetPasswordRequest`.
2. `auth_service.reset_password(...)` hashes the submitted reset token.
3. `user_service` loads the matching reset record and checks expiry.
4. `password_service.hash_password(...)` creates the new password hash.
5. `user_service` clears reset fields and increments `token_version`.
6. Route returns `MessageResponse`.

## Implementation Order

Build in this order:

1. `schema/user.py` and `schema/auth.py`
2. `models/user_model.py`
3. `config.py`
4. `password_service.py`
5. `token_service.py`
6. `user_service.py`
7. `auth_service.py`
8. `deps/auth.py`
9. `routes/auth.py`
10. wire routes in `main.py`

## Non-Goals For This Version

The following are out of scope unless explicitly added in a later design revision:

- refresh tokens
- OAuth or social login
- multi-factor authentication
- device/session management UI
- self-service account deletion
