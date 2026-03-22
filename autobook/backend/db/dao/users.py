from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.dao.chart_of_accounts import ChartOfAccountsDAO
from db.models.user import User


class UserDAO:
    @staticmethod
    def create(db: Session, email: str, password_hash: str | None = None, cognito_sub: str | None = None) -> User:
        user = User(email=email, password_hash=password_hash, cognito_sub=cognito_sub or email)
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

    @staticmethod
    def get_by_cognito_sub(db: Session, cognito_sub: str) -> User | None:
        stmt = select(User).where(User.cognito_sub == cognito_sub)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_or_create_from_cognito_claims(db: Session, cognito_sub: str, email: str | None) -> User:
        user = UserDAO.get_by_cognito_sub(db, cognito_sub)
        if user:
            if email and user.email != email:
                user.email = email
                db.add(user)
                db.flush()
            return user

        resolved_email = email or f"{cognito_sub}@autobook.local"
        return UserDAO.create(db, email=resolved_email, cognito_sub=cognito_sub)
