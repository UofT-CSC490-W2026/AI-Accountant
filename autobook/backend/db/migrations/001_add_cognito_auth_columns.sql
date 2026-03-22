BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS cognito_sub VARCHAR(255);

UPDATE users
SET cognito_sub = email
WHERE cognito_sub IS NULL;

ALTER TABLE users
  ALTER COLUMN cognito_sub SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_cognito_sub
  ON users (cognito_sub);

ALTER TABLE users
  ALTER COLUMN password_hash DROP NOT NULL;

COMMIT;
