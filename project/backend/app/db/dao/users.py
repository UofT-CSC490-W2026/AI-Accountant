from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.dao.chart_of_accounts import ChartOfAccountsDAO
from app.models.user import User


class UserDAO:
    @staticmethod
    def create(db: Session, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        db.flush()
        ChartOfAccountsDAO.seed_defaults(db, user.id)
        db.flush()
        return user

    @staticmethod
    def get_by_id(db: Session, user_id) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return db.execute(stmt).scalar_one_or_none()
