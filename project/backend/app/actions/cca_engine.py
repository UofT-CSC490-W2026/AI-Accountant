"""
CCA (Capital Cost Allowance) Calculation Engine

Handles Canadian tax depreciation calculations including:
- Half-year rule (50% of net additions in acquisition year)
- Accelerated Investment Incentive Property (AIIP)
- Annual CCA calculation per asset and class
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, CCAScheduleEntry
from app.models.enums import AssetStatus
from app.services.asset_service import CCA_CLASSES


def calculate_annual_cca(
    db: Session,
    asset: Asset,
    fiscal_year: int,
    fiscal_year_end: date,
) -> CCAScheduleEntry:
    """
    Calculate the CCA for an asset for a given fiscal year.

    Implements:
    - Half-year rule: In acquisition year, CCA base = 50% of cost
    - Standard declining balance calculation

    Args:
        db: Database session.
        asset: The asset to calculate CCA for.
        fiscal_year: The fiscal year (e.g., 2024).
        fiscal_year_end: The fiscal year-end date.

    Returns:
        A CCAScheduleEntry (not yet persisted).
    """
    if asset.cca_class is None or asset.cca_rate is None:
        raise ValueError(f"Asset {asset.id} has no CCA class/rate assigned")

    ucc_opening = _get_ucc_opening(db, asset, fiscal_year)
    is_acquisition_year = asset.acquisition_date.year == fiscal_year

    additions = asset.acquisition_cost if is_acquisition_year else Decimal("0")

    dispositions = Decimal("0")
    if (
        asset.disposition_date is not None
        and asset.disposition_date.year == fiscal_year
    ):
        dispositions = min(
            asset.disposition_proceeds or Decimal("0"),
            ucc_opening + additions,
        )

    if is_acquisition_year:
        cca_base = additions * Decimal("0.5")
        half_year_applied = True
    else:
        cca_base = ucc_opening + additions - dispositions
        half_year_applied = False

    cca_base = max(cca_base, Decimal("0"))

    cca_amount = (cca_base * asset.cca_rate).quantize(Decimal("0.01"))

    ucc_closing = ucc_opening + additions - dispositions - cca_amount
    ucc_closing = max(ucc_closing, Decimal("0"))

    entry = CCAScheduleEntry(
        asset_id=asset.id,
        fiscal_year=fiscal_year,
        ucc_opening=ucc_opening,
        additions=additions,
        dispositions=dispositions,
        cca_claimed=cca_amount,
        ucc_closing=ucc_closing,
        half_year_rule_applied=half_year_applied,
        aiip_applied=False,
    )

    return entry


def create_cca_entries_for_year(
    db: Session,
    org_id: uuid.UUID,
    fiscal_year: int,
    fiscal_year_end: date,
) -> list[CCAScheduleEntry]:
    """
    Calculate and persist CCA entries for all active assets in an organization.

    Args:
        db: Database session.
        org_id: Organization ID.
        fiscal_year: The fiscal year to calculate.
        fiscal_year_end: The fiscal year-end date.

    Returns:
        List of created CCAScheduleEntry records.
    """
    stmt = select(Asset).where(
        Asset.org_id == org_id,
        Asset.cca_class.isnot(None),
        Asset.status == AssetStatus.ACTIVE,
    )
    assets = db.scalars(stmt).all()

    entries = []
    for asset in assets:
        existing = _get_cca_entry(db, asset.id, fiscal_year)
        if existing is not None:
            entries.append(existing)
            continue

        entry = calculate_annual_cca(db, asset, fiscal_year, fiscal_year_end)
        db.add(entry)
        entries.append(entry)

    db.flush()
    return entries


def get_cca_schedule(
    db: Session,
    org_id: uuid.UUID,
    fiscal_year: int | None = None,
) -> list[CCAScheduleEntry]:
    """
    Get CCA schedule entries for an organization.

    Args:
        db: Database session.
        org_id: Organization ID.
        fiscal_year: Optional filter by fiscal year.

    Returns:
        List of CCAScheduleEntry records.
    """
    stmt = (
        select(CCAScheduleEntry)
        .join(Asset)
        .where(Asset.org_id == org_id)
    )

    if fiscal_year is not None:
        stmt = stmt.where(CCAScheduleEntry.fiscal_year == fiscal_year)

    stmt = stmt.order_by(CCAScheduleEntry.fiscal_year, Asset.name)
    return list(db.scalars(stmt).all())


def get_total_cca_by_class(
    db: Session,
    org_id: uuid.UUID,
    fiscal_year: int,
) -> dict[str, Decimal]:
    """
    Get total CCA claimed by CCA class for a fiscal year.

    Returns:
        Dict mapping CCA class to total CCA amount.
    """
    stmt = (
        select(CCAScheduleEntry)
        .join(Asset)
        .where(
            Asset.org_id == org_id,
            CCAScheduleEntry.fiscal_year == fiscal_year,
        )
    )
    entries = db.scalars(stmt).all()

    totals: dict[str, Decimal] = {}
    for entry in entries:
        asset = db.get(Asset, entry.asset_id)
        if asset and asset.cca_class:
            cca_class = asset.cca_class
            totals[cca_class] = totals.get(cca_class, Decimal("0")) + entry.cca_claimed

    return totals


def _get_ucc_opening(db: Session, asset: Asset, fiscal_year: int) -> Decimal:
    """Get the opening UCC balance for an asset in a given fiscal year."""
    stmt = select(CCAScheduleEntry).where(
        CCAScheduleEntry.asset_id == asset.id,
        CCAScheduleEntry.fiscal_year == fiscal_year - 1,
    )
    prior_entry = db.scalars(stmt).first()

    if prior_entry is not None:
        return prior_entry.ucc_closing

    if asset.acquisition_date.year < fiscal_year:
        return asset.acquisition_cost

    return Decimal("0")


def _get_cca_entry(
    db: Session, asset_id: uuid.UUID, fiscal_year: int
) -> CCAScheduleEntry | None:
    """Get existing CCA entry for an asset and fiscal year."""
    stmt = select(CCAScheduleEntry).where(
        CCAScheduleEntry.asset_id == asset_id,
        CCAScheduleEntry.fiscal_year == fiscal_year,
    )
    return db.scalars(stmt).first()
