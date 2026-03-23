# Deployed Auth And Browser Test Guide

## Scope
This guide summarizes the auth-related and P1-adjacent code that has been implemented, what infra/config must exist in the deployed environment, and how to validate the app in a real browser against deployed Cognito and deployed backend services.

This is intended for the teammate handling deployed infra validation, not local mock-mode testing.

## What Has Been Implemented

### Frontend
- Login page
- Cognito hosted-login start flow
- Auth callback handling
- Protected route gating
- Logout flow
- API bearer-token wiring
- Realtime token wiring

Relevant files:
- `frontend/src/api/auth.ts`
- `frontend/src/auth/AuthProvider.tsx`
- `frontend/src/auth/ProtectedRoute.tsx`
- `frontend/src/pages/LoginPage.tsx`
- `frontend/src/pages/AuthCallbackPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/layout/AppLayout.tsx`

### Backend
- Cognito JWT verification
- Local user sync from Cognito claims
- Auth context and role enforcement
- Protected auth endpoints
- Manager-only clarification resolution
- Auth session persistence
- DB-level journal balance trigger

Relevant files:
- `backend/api/routes/auth.py`
- `backend/auth/deps.py`
- `backend/db/models/auth_session.py`
- `backend/db/dao/auth_sessions.py`
- `backend/db/migrations/001_add_cognito_auth_columns.sql`
- `backend/db/migrations/002_add_auth_sessions_and_balance_trigger.sql`
- `backend/services/shared/transaction_persistence.py`

### Pipeline / Data Contract
These were preserved through the auth merge:
- parse -> normalizer -> precedent -> ml_inference -> downstream services
- transaction schema with normalization mention fields
- auth-derived identity instead of client-supplied `user_id`

Relevant files:
- `backend/db/models/transaction.py`
- `backend/services/normalizer/process.py`
- `backend/services/precedent/process.py`
- `backend/services/ml_inference/process.py`
- `backend/api/routes/parse.py`
- `backend/api/routes/ledger.py`
- `backend/api/routes/clarifications.py`
- `backend/api/routes/statements.py`

## Required Deployed Environment Variables

### Backend
These must be set correctly in deployed backend compute:

```env
DATABASE_URL=<postgres connection string>
REDIS_URL=<redis connection string>
AWS_REGION=ca-central-1
AWS_DEFAULT_REGION=ca-central-1
COGNITO_POOL_ID=<real cognito pool id>
COGNITO_CLIENT_ID=<real cognito app client id>
COGNITO_DOMAIN=autobook-dev.auth.ca-central-1.amazoncognito.com
COGNITO_SCOPES=openid email profile
SQS_QUEUE_NORMALIZER=<real queue url>
SQS_QUEUE_PRECEDENT=<real queue url>
SQS_QUEUE_ML_INFERENCE=<real queue url>
SQS_QUEUE_AGENT=<real queue url>
SQS_QUEUE_RESOLUTION=<real queue url>
SQS_QUEUE_POSTING=<real queue url>
SQS_QUEUE_FLYWHEEL=<real queue url>
```

### Frontend
These must be set in deployed frontend config:

```env
VITE_USE_MOCK_API=false
VITE_API_BASE_URL=https://<api-domain>/api/v1
VITE_WS_URL=wss://<api-domain>/ws
VITE_APP_NAME=AI Accountant
```

## Required One-Time Database Setup
Before deployed auth testing, make sure these have been applied to the deployed database:

1. `backend/db/migrations/001_add_cognito_auth_columns.sql`
2. `backend/db/migrations/002_add_auth_sessions_and_balance_trigger.sql`
3. `scripts/migrate_transaction_schema.py` if the deployed `transactions` table does not already have:
   - `amount_mentions`
   - `date_mentions`
   - `party_mentions`
   - `quantity_mentions`
   - nullable `amount`

## Cognito Configuration Requirements
The deployed Cognito app client must allow:
- Authorization code flow with PKCE
- Redirect URI for frontend callback
- Logout URI for frontend logout return

Expected callback URI pattern:
- `https://<frontend-domain>/auth/callback`

Expected logout return URI pattern:
- `https://<frontend-domain>/login`

If these are misconfigured, typical failures are:
- `Invalid client id`
- Cognito hosted UI redirect errors
- successful login followed by callback failure

## API Validation Checklist
Use a real Cognito access token.

### 1. Validate identity bootstrap
Request:
- `GET /api/v1/auth/me`

Expectation:
- HTTP 200
- response includes:
  - local user id
  - `cognito_sub`
  - `email`
  - `role`
  - `token_use`

### 2. Validate authenticated token acceptance
Request:
- `GET /api/v1/auth/validate`

Expectation:
- HTTP 200
- `authenticated: true`

### 3. Validate protected parse route
Request:
- `POST /api/v1/parse`

Expectation:
- HTTP 200
- parse request accepted
- no client-supplied `user_id` needed

### 4. Validate realtime auth
Connect to SSE / realtime using the same access token.

Expectation:
- connection succeeds
- protected realtime does not reject the token

## Browser Test Guide

### 1. Login page
What to do:
- Open the deployed frontend `/login`

What to expect:
- Login page renders
- `Continue with Cognito` button is visible
- no 404 from `/auth/login-url`

### 2. Hosted Cognito login
What to do:
- Click `Continue with Cognito`
- Sign in with a valid Cognito user

What to expect:
- redirect to Cognito hosted UI
- successful sign-in
- redirect back to `/auth/callback`
- final navigation into the app

### 3. Protected app bootstrap
What to do:
- land on dashboard after login
- refresh the page

What to expect:
- dashboard remains accessible
- no redirect loop
- no immediate logout
- protected routes still work after refresh

### 4. Logout
What to do:
- click `Logout`

What to expect:
- user session clears
- browser returns to `/login`
- protected pages are no longer accessible without login

### 5. Dashboard
What to do:
- open `/`

What to expect:
- dashboard loads
- no auth error
- no blank state due to missing token

### 6. Manual transaction parse
What to do:
- open `/transactions`
- submit: `Bought a laptop for $2400 from Apple`

What to expect:
- request accepted
- clear transaction should flow toward posting
- check ledger/statements afterward

### 7. Ambiguous transaction
What to do:
- submit: `Transferred money`

What to expect:
- request accepted
- ambiguous transaction should go to clarification flow rather than immediate clean posting

### 8. Clarifications page
What to do:
- open `/clarifications`

What to expect:
- pending ambiguous item is visible
- regular user can view
- resolve action should require manager privileges

### 9. Manager-only clarification resolution
What to do:
- test resolve as a regular user
- test resolve as a manager user

What to expect:
- regular user should be rejected
- manager should be allowed to resolve

### 10. Ledger page
What to do:
- open `/ledger`

What to expect:
- posted entries render
- no user-id query parameter is required
- no auth failure
- debit/credit lines appear balanced

### 11. Statements page
What to do:
- open `/statements`

What to expect:
- statement data loads from backend
- no auth failure
- no 500 on report generation

### 12. CSV upload
What to do:
- upload a CSV with realistic transaction content

What to expect:
- request accepted
- upload is processed through the same protected backend
- resulting behavior should reflect actual content, not mock fixture behavior

### 13. Text-based PDF upload
What to do:
- upload a text-based PDF

What to expect:
- request accepted
- backend receives `pdf_upload`
- result should depend on extracted content

### 14. Realtime updates
What to do:
- keep one app page open
- submit transactions from the UI

What to expect:
- clarification creation or entry posting shows up without full refresh
- same access token should work for both API and realtime

## What Should Not Be Relied On
- Local mock-mode browser behavior is not evidence of deployed Cognito correctness.
- Mock upload behavior is intentionally simplified and not evidence of deployed CSV/PDF parsing correctness.
- Placeholder local Cognito defaults like `local-test-client` or `local-test-pool` are not valid for deployed testing.

## Common Failure Modes

### `Invalid client id`
Cause:
- backend is using wrong `COGNITO_CLIENT_ID`

Check:
- deployed backend env
- Cognito app client existence

### 404 on login start
Cause:
- frontend points to wrong API base URL
- deployed backend does not expose `/api/v1/auth/login-url`

Check:
- `VITE_API_BASE_URL`
- deployed API routing

### Login succeeds but callback fails
Cause:
- callback URI mismatch
- PKCE/callback flow mismatch

Check:
- Cognito allowed callback URLs
- frontend callback route `/auth/callback`

### Logout does not return to login
Cause:
- Cognito logout URI mismatch

Check:
- allowed logout URLs in Cognito
- frontend logout return path

### API works but realtime fails
Cause:
- token not passed to realtime correctly
- websocket/SSE auth mismatch

Check:
- frontend realtime connection logic
- deployed realtime auth configuration

### Parse/ledger/statements fail after login
Cause:
- missing DB migrations
- missing queue env vars
- token-derived identity not wired correctly in deployment

Check:
- DB migrations applied
- queue URLs present
- protected route env wired correctly

## Suggested Test Order
1. Confirm backend env vars
2. Confirm DB migrations applied
3. Confirm frontend env vars
4. Test `/api/v1/auth/me`
5. Test hosted login in browser
6. Test dashboard access after login
7. Test logout
8. Test manual transaction
9. Test clarification path
10. Test manager-only resolution
11. Test ledger/statements
12. Test CSV upload
13. Test PDF upload
14. Test realtime updates

## Final Expected Outcome
If deployment is correct, the tester should be able to:
- sign in through Cognito hosted UI
- access the protected app
- call protected API routes with the same token
- receive realtime updates with the same token
- submit manual and uploaded transaction inputs
- see clear items post and ambiguous items move to clarification
- resolve clarifications only with appropriate role permissions
