"""create user-scoped pipeline foundation

Revision ID: 20260321_0001
Revises:
Create Date: 2026-03-21 15:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260321_0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


USER_TABLES = (
    "chart_of_accounts",
    "transactions",
    "journal_entries",
    "clarification_tasks",
    "assets",
    "scheduled_entries",
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "chart_of_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_code", sa.String(length=20), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "auto_created", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_type IN ('asset', 'liability', 'equity', 'revenue', 'expense')",
            name="ck_chart_of_accounts_account_type",
        ),
        sa.UniqueConstraint("user_id", "account_code", name="uq_chart_of_accounts_user_code"),
    )
    op.create_index("ix_chart_of_accounts_user_id", "chart_of_accounts", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("normalized_description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="CAD", nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("counterparty", sa.String(length=255), nullable=True),
        sa.Column("intent_label", sa.String(length=100), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("bank_category", sa.String(length=100), nullable=True),
        sa.Column("cca_class_match", sa.String(length=50), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("origin_tier", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('draft', 'posted')", name="ck_journal_entries_status"),
        sa.CheckConstraint(
            "origin_tier IS NULL OR origin_tier BETWEEN 1 AND 4",
            name="ck_journal_entries_origin_tier",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.000 AND confidence <= 1.000)",
            name="ck_journal_entries_confidence",
        ),
    )
    op.create_index("ix_journal_entries_user_id", "journal_entries", ["user_id"])
    op.create_index("ix_journal_entries_transaction_id", "journal_entries", ["transaction_id"])

    op.create_table(
        "journal_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_code", sa.String(length=20), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("line_order", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint("type IN ('debit', 'credit')", name="ck_journal_lines_type"),
        sa.CheckConstraint("amount > 0", name="ck_journal_lines_amount_positive"),
    )
    op.create_index("ix_journal_lines_journal_entry_id", "journal_lines", ["journal_entry_id"])

    op.create_table(
        "clarification_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("proposed_entry", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evaluator_verdict", sa.String(length=20), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'resolved', 'rejected')",
            name="ck_clarification_tasks_status",
        ),
        sa.CheckConstraint(
            "evaluator_verdict IN ('confident', 'fixable', 'stuck')",
            name="ck_clarification_tasks_verdict",
        ),
        sa.CheckConstraint(
            "confidence >= 0.000 AND confidence <= 1.000",
            name="ck_clarification_tasks_confidence",
        ),
    )
    op.create_index("ix_clarification_tasks_user_id", "clarification_tasks", ["user_id"])
    op.create_index(
        "ix_clarification_tasks_transaction_id", "clarification_tasks", ["transaction_id"]
    )

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acquisition_date", sa.Date(), nullable=False),
        sa.Column("acquisition_cost", sa.Numeric(15, 2), nullable=False),
        sa.Column("cca_class", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('active', 'disposed')", name="ck_assets_status"),
    )
    op.create_index("ix_assets_user_id", "assets", ["user_id"])

    op.create_table(
        "cca_schedule_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("ucc_opening", sa.Numeric(15, 2), nullable=False),
        sa.Column("additions", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("dispositions", sa.Numeric(15, 2), server_default="0", nullable=False),
        sa.Column("cca_claimed", sa.Numeric(15, 2), nullable=False),
        sa.Column("ucc_closing", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "half_year_rule_applied",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "journal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_cca_schedule_entries_asset_id", "cca_schedule_entries", ["asset_id"])

    op.create_table(
        "scheduled_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("next_run_date", sa.Date(), nullable=False),
        sa.Column("template_journal_entry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_scheduled_entries_user_id", "scheduled_entries", ["user_id"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_posted_journal_entry_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' AND OLD.status = 'posted' THEN
                RAISE EXCEPTION 'posted journal entries are immutable';
            END IF;

            IF TG_OP = 'UPDATE' AND OLD.status = 'posted' THEN
                RAISE EXCEPTION 'posted journal entries are immutable';
            END IF;

            RETURN COALESCE(NEW, OLD);
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_posted_journal_entry_mutation
        BEFORE UPDATE OR DELETE ON journal_entries
        FOR EACH ROW
        EXECUTE FUNCTION prevent_posted_journal_entry_mutation();
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION check_journal_entry_balance()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_journal_entry_id uuid;
            debit_total numeric(15, 2);
            credit_total numeric(15, 2);
        BEGIN
            target_journal_entry_id := COALESCE(NEW.journal_entry_id, OLD.journal_entry_id);

            SELECT
                COALESCE(SUM(CASE WHEN type = 'debit' THEN amount ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END), 0)
            INTO debit_total, credit_total
            FROM journal_lines
            WHERE journal_entry_id = target_journal_entry_id;

            IF debit_total <> credit_total THEN
                RAISE EXCEPTION
                    'journal entry % is unbalanced: debits %, credits %',
                    target_journal_entry_id,
                    debit_total,
                    credit_total;
            END IF;

            RETURN NULL;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_check_journal_entry_balance
        AFTER INSERT OR UPDATE OR DELETE ON journal_lines
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION check_journal_entry_balance();
        """
    )

    for table_name in USER_TABLES:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY {table_name}_user_isolation
            ON {table_name}
            USING (user_id = current_setting('app.current_user_id', true)::uuid)
            WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
            """
        )

    op.execute("ALTER TABLE journal_lines ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY journal_lines_user_isolation
        ON journal_lines
        USING (
            EXISTS (
                SELECT 1
                FROM journal_entries
                WHERE journal_entries.id = journal_lines.journal_entry_id
                  AND journal_entries.user_id = current_setting('app.current_user_id', true)::uuid
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM journal_entries
                WHERE journal_entries.id = journal_lines.journal_entry_id
                  AND journal_entries.user_id = current_setting('app.current_user_id', true)::uuid
            )
        );
        """
    )

    op.execute("ALTER TABLE cca_schedule_entries ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY cca_schedule_entries_user_isolation
        ON cca_schedule_entries
        USING (
            EXISTS (
                SELECT 1
                FROM assets
                WHERE assets.id = cca_schedule_entries.asset_id
                  AND assets.user_id = current_setting('app.current_user_id', true)::uuid
            )
        )
        WITH CHECK (
            EXISTS (
                SELECT 1
                FROM assets
                WHERE assets.id = cca_schedule_entries.asset_id
                  AND assets.user_id = current_setting('app.current_user_id', true)::uuid
            )
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS cca_schedule_entries_user_isolation ON cca_schedule_entries;")
    op.execute("DROP POLICY IF EXISTS journal_lines_user_isolation ON journal_lines;")
    for table_name in reversed(USER_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table_name}_user_isolation ON {table_name};")

    op.execute("DROP TRIGGER IF EXISTS trg_check_journal_entry_balance ON journal_lines;")
    op.execute("DROP FUNCTION IF EXISTS check_journal_entry_balance();")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_prevent_posted_journal_entry_mutation ON journal_entries;"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_posted_journal_entry_mutation();")

    op.drop_index("ix_scheduled_entries_user_id", table_name="scheduled_entries")
    op.drop_table("scheduled_entries")
    op.drop_index("ix_cca_schedule_entries_asset_id", table_name="cca_schedule_entries")
    op.drop_table("cca_schedule_entries")
    op.drop_index("ix_assets_user_id", table_name="assets")
    op.drop_table("assets")
    op.drop_index(
        "ix_clarification_tasks_transaction_id", table_name="clarification_tasks"
    )
    op.drop_index("ix_clarification_tasks_user_id", table_name="clarification_tasks")
    op.drop_table("clarification_tasks")
    op.drop_index("ix_journal_lines_journal_entry_id", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_journal_entries_transaction_id", table_name="journal_entries")
    op.drop_index("ix_journal_entries_user_id", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_table("transactions")
    op.drop_index("ix_chart_of_accounts_user_id", table_name="chart_of_accounts")
    op.drop_table("chart_of_accounts")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
