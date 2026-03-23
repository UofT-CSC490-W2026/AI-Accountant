"""
Asset Service

Handles capital asset recording, CCA class assignment, and disposition.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.asset import Asset
from db.models.enums import AssetStatus
from services.actions.exceptions import AssetAlreadyDisposedError


CCA_CLASSES: dict[str, dict] = {
    "1": {"rate": Decimal("0.04"), "description": "Buildings acquired after 1987"},
    "8": {"rate": Decimal("0.20"), "description": "Furniture, equipment, machinery"},
    "10": {"rate": Decimal("0.30"), "description": "Vehicles, automotive equipment"},
    "10.1": {"rate": Decimal("0.30"), "description": "Passenger vehicles > $37,000"},
    "12": {"rate": Decimal("1.00"), "description": "Tools, medical instruments < $500"},
    "14": {"rate": None, "description": "Patents, franchises, licences (straight-line)"},
    "14.1": {"rate": Decimal("0.05"), "description": "Goodwill and other eligible capital property"},
    "50": {"rate": Decimal("0.55"), "description": "Computer hardware & software"},
    "53": {"rate": Decimal("0.50"), "description": "Manufacturing & processing machinery"},
}


def get_cca_rate(cca_class: str) -> Decimal | None:
    """Get the CCA rate for a given class."""
    info = CCA_CLASSES.get(cca_class)
    return info["rate"] if info else None


def record_asset(
    db: Session,
    user_id: uuid.UUID,
    name: str,
    acquisition_date: date,
    acquisition_cost: Decimal,
    cca_class: str | None = None,
    description: str | None = None,
    book_depreciation_method: str | None = None,
    book_useful_life: int | None = None,
) -> Asset:
    """
    Record a new capital asset.

    Args:
        db: Database session.
        user_id: User ID who owns this asset.
        name: Asset name/description.
        acquisition_date: Date the asset was acquired.
        acquisition_cost: Purchase price of the asset.
        cca_class: CCA class for tax depreciation (e.g., "50" for computers).
        description: Optional detailed description.
        book_depreciation_method: Optional book depreciation method.
        book_useful_life: Optional useful life in years for book depreciation.

    Returns:
        The created Asset.
    """
    asset = Asset(
        user_id=user_id,
        name=name,
        description=description,
        acquisition_date=acquisition_date,
        acquisition_cost=float(acquisition_cost),
        cca_class=cca_class,
        status=AssetStatus.ACTIVE.value,
    )
    db.add(asset)
    db.flush()
    return asset


def dispose_asset(
    db: Session,
    user_id: uuid.UUID,
    asset_id: uuid.UUID,
    disposition_date: date,
    disposition_proceeds: Decimal,
) -> Asset:
    """
    Record the disposition (sale/disposal) of an asset.

    Args:
        db: Database session.
        user_id: User ID who owns this asset.
        asset_id: ID of the asset to dispose.
        disposition_date: Date of disposition.
        disposition_proceeds: Amount received from disposition.

    Returns:
        The updated Asset.

    Raises:
        AssetAlreadyDisposedError: If asset is already disposed.
    """
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise AssetAlreadyDisposedError(f"Asset {asset_id} not found")

    if asset.user_id != user_id:
        raise AssetAlreadyDisposedError(f"Asset {asset_id} not owned by user")

    if asset.status == AssetStatus.DISPOSED:
        raise AssetAlreadyDisposedError(f"Asset {asset_id} is already disposed")

    asset.disposition_date = disposition_date
    asset.disposition_proceeds = disposition_proceeds
    asset.status = AssetStatus.DISPOSED

    db.flush()
    return asset


def list_assets(
    db: Session,
    user_id: uuid.UUID,
    status: AssetStatus | None = None,
    cca_class: str | None = None,
) -> list[Asset]:
    """
    List assets for a user with optional filters.

    Args:
        db: Database session.
        user_id: User ID.
        status: Filter by asset status (ACTIVE, DISPOSED).
        cca_class: Filter by CCA class.

    Returns:
        List of matching assets.
    """
    stmt = select(Asset).where(Asset.user_id == user_id)

    if status is not None:
        stmt = stmt.where(Asset.status == status)

    if cca_class is not None:
        stmt = stmt.where(Asset.cca_class == cca_class)

    stmt = stmt.order_by(Asset.acquisition_date.desc())
    return list(db.execute(stmt).scalars().all())


def get_asset(db: Session, asset_id: uuid.UUID) -> Asset | None:
    """Get an asset by ID."""
    return db.get(Asset, asset_id)
