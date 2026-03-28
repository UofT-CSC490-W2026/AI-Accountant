from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def patch_set_user_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace PostgreSQL set_config calls with a no-op for SQLite tests."""
    noop = lambda db, uid: None  # noqa: E731

    import db.dao.chart_of_accounts as coa_mod
    import db.dao.journal_entries as je_mod
    import db.dao.transactions as tx_mod
    import db.dao.clarifications as cl_mod

    monkeypatch.setattr(coa_mod, "set_current_user_context", noop)
    monkeypatch.setattr(je_mod, "set_current_user_context", noop)
    monkeypatch.setattr(tx_mod, "set_current_user_context", noop)
    monkeypatch.setattr(cl_mod, "set_current_user_context", noop)
