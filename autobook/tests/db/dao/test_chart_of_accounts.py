from __future__ import annotations

from db.dao.chart_of_accounts import ChartOfAccountsDAO, DEFAULT_COA
from db.dao.users import UserDAO


def _make_user(db):
    return UserDAO.create(db, email=f"coa-{id(db)}@example.com")


def test_coa_list_by_user(db_session):
    user = _make_user(db_session)
    accounts = ChartOfAccountsDAO.list_by_user(db_session, user.id)
    assert len(accounts) == len(DEFAULT_COA)


def test_coa_get_by_code_found(db_session):
    user = _make_user(db_session)
    result = ChartOfAccountsDAO.get_by_code(db_session, user.id, "1000")
    assert result is not None
    assert result.account_name == "Cash"


def test_coa_get_by_code_not_found(db_session):
    user = _make_user(db_session)
    result = ChartOfAccountsDAO.get_by_code(db_session, user.id, "ZZZZ")
    assert result is None


def test_coa_get_or_create_existing(db_session):
    user = _make_user(db_session)
    existing = ChartOfAccountsDAO.get_by_code(db_session, user.id, "1000")
    result = ChartOfAccountsDAO.get_or_create(db_session, user.id, "1000", "Cash", "asset")
    assert result.id == existing.id


def test_coa_get_or_create_new(db_session):
    user = _make_user(db_session)
    result = ChartOfAccountsDAO.get_or_create(db_session, user.id, "7000", "New Account", "expense")
    assert result.account_code == "7000"
    assert result.auto_created is True


def test_coa_seed_defaults(db_session):
    user = _make_user(db_session)
    seeded = ChartOfAccountsDAO.seed_defaults(db_session, user.id)
    assert len(seeded) == len(DEFAULT_COA)
