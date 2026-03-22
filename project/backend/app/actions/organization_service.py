"""
Organization Service

Handles organization CRUD and setup operations.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.services.coa_manager import create_default_chart_of_accounts


def create_organization(
    db: Session,
    name: str,
    fiscal_year_end: date,
    jurisdiction: str = "federal",
    incorporation_date: date | None = None,
    hst_registration_number: str | None = None,
    business_number: str | None = None,
    setup_default_coa: bool = True,
) -> Organization:
    """
    Create a new organization with optional default Chart of Accounts.

    Args:
        db: Database session.
        name: Organization name.
        fiscal_year_end: Fiscal year-end date.
        jurisdiction: Jurisdiction (federal, ON, BC, etc.).
        incorporation_date: Date of incorporation.
        hst_registration_number: HST registration number.
        business_number: CRA business number.
        setup_default_coa: If True, create the default Chart of Accounts.

    Returns:
        The created Organization.
    """
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

    if setup_default_coa:
        create_default_chart_of_accounts(db, org.id)

    db.flush()
    return org


def get_organization(db: Session, org_id: uuid.UUID) -> Organization | None:
    """Get an organization by ID."""
    return db.get(Organization, org_id)


def list_organizations(db: Session) -> list[Organization]:
    """List all organizations."""
    stmt = select(Organization).order_by(Organization.name)
    return list(db.scalars(stmt).all())


def update_organization(
    db: Session,
    org_id: uuid.UUID,
    name: str | None = None,
    fiscal_year_end: date | None = None,
    jurisdiction: str | None = None,
    hst_registration_number: str | None = None,
    business_number: str | None = None,
) -> Organization:
    """
    Update an organization's details.

    Args:
        db: Database session.
        org_id: Organization ID.
        name: New name (optional).
        fiscal_year_end: New fiscal year-end (optional).
        jurisdiction: New jurisdiction (optional).
        hst_registration_number: New HST number (optional).
        business_number: New business number (optional).

    Returns:
        The updated Organization.
    """
    org = db.get(Organization, org_id)
    if org is None:
        raise ValueError(f"Organization {org_id} not found")

    if name is not None:
        org.name = name
    if fiscal_year_end is not None:
        org.fiscal_year_end = fiscal_year_end
    if jurisdiction is not None:
        org.jurisdiction = jurisdiction
    if hst_registration_number is not None:
        org.hst_registration_number = hst_registration_number
    if business_number is not None:
        org.business_number = business_number

    db.flush()
    return org
