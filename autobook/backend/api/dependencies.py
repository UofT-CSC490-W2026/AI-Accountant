from __future__ import annotations

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from db.connection import get_db
from local_identity import resolve_local_user


def get_current_local_user(
    user_id: str | None = Query(default=None, alias="userId"),
    db: Session = Depends(get_db),
):
    return resolve_local_user(db, user_id)
