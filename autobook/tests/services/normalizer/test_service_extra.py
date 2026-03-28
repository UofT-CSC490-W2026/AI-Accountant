from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
import services.normalizer.service as normalizer_svc


def test_execute_rollback_on_error(monkeypatch):
    db = SimpleNamespace(committed=False, rolled_back=False, closed=False)
    db.commit = lambda: None
    db.rollback = lambda: setattr(db, "rolled_back", True)
    db.close = lambda: setattr(db, "closed", True)

    monkeypatch.setattr(normalizer_svc, "SessionLocal", lambda: db)
    monkeypatch.setattr(normalizer_svc, "resolve_local_user", lambda _db, _ext: (_ for _ in ()).throw(RuntimeError("fail")))

    with pytest.raises(RuntimeError):
        normalizer_svc.execute({"parse_id": "p1", "input_text": "test", "source": "manual", "currency": "CAD", "user_id": "u1"})

    assert db.rolled_back
    assert db.closed
