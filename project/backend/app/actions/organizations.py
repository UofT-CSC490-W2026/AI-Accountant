from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.actions.errors import NotFoundError
from app.models.organization import Organization


def create_organization(
    db: Session,
    *,
    name: str,
    fiscal_year_end: date,
    jurisdiction: str,
    incorporation_date: date | None = None,
    hst_registration_number: str | None = None,
    business_number: str | None = None,
) -> Organization:
    org = Organization(
        name=name,
        incorporation_date=incorporation_date,
        fiscal_year_end=fiscal_year_end,
        jurisdiction=jurisdiction,
        hst_registration_number=hst_registration_number,
        business_number=business_number,
    )
    db.add(org)
    db.flush()
    return org


def get_organization(db: Session, org_id: uuid.UUID) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise NotFoundError(f"organization {org_id} not found")
    return org
