from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassificationResult:
    label: str | None
    confidence: float | None


@dataclass(frozen=True)
class EntityExtractionResult:
    amount: float | None
    vendor: str | None
    asset_name: str | None
    entities: dict
