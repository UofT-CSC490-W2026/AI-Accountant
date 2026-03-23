BEGIN;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS last_authenticated_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS auth_sessions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  cognito_sub VARCHAR(255) NOT NULL,
  token_fingerprint VARCHAR(64) NOT NULL UNIQUE,
  token_use VARCHAR(20) NOT NULL,
  issued_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions(user_id);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_cognito_sub ON auth_sessions(cognito_sub);
CREATE INDEX IF NOT EXISTS ix_auth_sessions_token_fingerprint ON auth_sessions(token_fingerprint);

CREATE OR REPLACE FUNCTION enforce_balanced_journal_entry()
RETURNS TRIGGER AS $$
DECLARE
  target_entry_id UUID;
  debit_total NUMERIC(19, 4);
  credit_total NUMERIC(19, 4);
  line_count INTEGER;
BEGIN
  target_entry_id := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);

  SELECT
    COALESCE(SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 0),
    COUNT(*)
  INTO debit_total, credit_total, line_count
  FROM journal_lines
  WHERE journal_entry_id = target_entry_id;

  IF line_count > 0 AND debit_total <> credit_total THEN
    RAISE EXCEPTION
      'journal entry % is unbalanced: debits=% credits=%',
      target_entry_id,
      debit_total,
      credit_total;
  END IF;

  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_balanced_journal_entry ON journal_lines;

CREATE CONSTRAINT TRIGGER trg_enforce_balanced_journal_entry
AFTER INSERT OR UPDATE OR DELETE ON journal_lines
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION enforce_balanced_journal_entry();

COMMIT;
