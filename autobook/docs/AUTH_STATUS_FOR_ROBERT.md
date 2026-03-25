# Auth Status Update — March 25, 2026

## What I did

1. **DB schema created** — I created the full schema (all 18 tables including `users` with `cognito_sub`, `last_authenticated_at`, and the `auth_sessions` table). Migrations 001 and 002 are no longer needed — the schema was created fresh from the current models.

2. **Backend deployed** — All your auth commits are deployed and running. `curl /api/v1/auth/me` returns `401` (not `500`). The DB issue is resolved.

3. **Cognito wiring fixed** — `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, and `COGNITO_DOMAIN` are all set correctly on the ECS API task. The `/auth/login-url` endpoint returns a valid Cognito hosted UI URL.

4. **Callback URLs registered** — Added `https://autobook.tech/auth/callback`, `https://www.autobook.tech/auth/callback`, `https://ai-accountant490.netlify.app/auth/callback`, and `http://localhost:5173/auth/callback` to the Cognito app client.

**Backend endpoints confirmed working**
```
GET  /api/v1/health         → 200 {"status": "ok"}
GET  /api/v1/auth/me        → 401 {"detail": "Missing bearer token."}
GET  /api/v1/auth/login-url → 200 {"hosted_ui_url": "https://autobook-dev.auth.ca-central-1.amazoncognito.com/login?..."}
```

## Decision: real Cognito, not demo mode

I did not set `AUTH_DEMO_MODE=true`. 
We're going with real Cognito auth instead of the demo bypass. I believe the backend is ready — `/auth/me` returns 401, `/auth/login-url` returns the correct Cognito URL, and the DB has all required tables.


## What I did not do

1. **Did not deploy the frontend** — The live frontend at `autobook.tech` is an old build. It either has mock mode on or doesn't have your latest `auth.ts` changes. I can't deploy this from my side.

2. **Did not set Netlify env vars** — `VITE_USE_MOCK_API`, `VITE_API_BASE_URL`, etc. need to be set in the Netlify build environment.


## What you need to do

To get real Cognito login working end-to-end:

1. **Deploy the frontend to Netlify** with these env vars:
   ```
   VITE_USE_MOCK_API=false
   VITE_USE_MOCK_AUTH=false
   VITE_API_BASE_URL=https://api-dev.autobook.tech/api/v1
   ```
   `VITE_USE_MOCK_AUTH` must be `false` (not `true`) — we're using real Cognito, not demo mode.

2. **Verify** — After deploy, go to `autobook.tech`, click "Continue with Cognito", create an account on the Cognito hosted page, and confirm you land back authenticated.

3. **If testing locally first** — Run `npm run dev` with the env vars above. The backend is ready at `https://api-dev.autobook.tech/api/v1`.


