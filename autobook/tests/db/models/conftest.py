import pytest


@pytest.fixture(autouse=True)
def _load_all_models():
    """Import all models so SQLAlchemy relationships resolve."""
    import db.models.user  # noqa: F401
    import db.models.account  # noqa: F401
    import db.models.transaction  # noqa: F401
    import db.models.journal  # noqa: F401
    import db.models.clarification  # noqa: F401
    import db.models.auth_session  # noqa: F401
    import db.models.asset  # noqa: F401
    import db.models.schedule  # noqa: F401
    import db.models.document  # noqa: F401
    import db.models.organization  # noqa: F401
    import db.models.reconciliation  # noqa: F401
    import db.models.tax  # noqa: F401
    import db.models.integration  # noqa: F401
    import db.models.shareholder_loan  # noqa: F401
