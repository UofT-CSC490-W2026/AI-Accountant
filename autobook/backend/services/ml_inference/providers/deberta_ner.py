from __future__ import annotations

from services.ml_inference.providers.base import EntityExtractor, ModelNotReadyError
from services.ml_inference.schemas import EntityExtractionResult


class DebertaEntityExtractor(EntityExtractor):
    """
    Scaffold for the future trained token-classification / span-extraction stack.

    This is intentionally separate from sequence classification so intent labels
    and entity extraction can be trained and shipped independently.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self.model_path = model_path

    @property
    def is_ready(self) -> bool:
        return bool(self.model_path)

    def extract_entities(self, message: dict, text: str) -> EntityExtractionResult:
        raise ModelNotReadyError(
            "DeBERTa entity-extraction scaffold is configured, but trained-model inference is not implemented yet."
        )
