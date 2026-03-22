# Local Mock Cognito

This branch includes a local Cognito mock for backend auth testing.

It generates:

- a mock RSA keypair
- a JWKS document the backend can trust
- Cognito-shaped `access` and `id` tokens
- role-bearing sample access tokens for `regular`, `manager`, and `superuser`
- shell exports for the env vars the backend auth layer expects

## Print Mock Env And Tokens

From the repo root:

```bash
python3 autobook/scripts/print_mock_cognito.py
```

To export them into your current shell:

```bash
eval "$(python3 autobook/scripts/print_mock_cognito.py)"
```

To print JSON instead:

```bash
python3 autobook/scripts/print_mock_cognito.py --format json
```

## Use The Mock Against The Backend

Start the API in the same shell after exporting the env vars, then call:

```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer $REGULAR_ACCESS_TOKEN"
```

Realtime endpoint example:

```bash
curl "http://127.0.0.1:8000/api/v1/events?access_token=$REGULAR_ACCESS_TOKEN"
```

## Shared Helper

The reusable helper lives in:

- `autobook/backend/auth/mock_cognito.py`

The auth tests and the print script both use it.
