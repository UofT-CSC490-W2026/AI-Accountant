"""Tests for services/ml_inference/providers/base.py — abstract classes and error."""
import pytest

from services.ml_inference.providers.base import (
    EntityExtractor,
    MLInferenceProvider,
    ModelNotReadyError,
    SequenceClassifier,
)


class TestModelNotReadyError:
    def test_can_be_raised(self):
        with pytest.raises(ModelNotReadyError, match="not configured"):
            raise ModelNotReadyError("Model not configured")

    def test_is_runtime_error(self):
        assert issubclass(ModelNotReadyError, RuntimeError)

    def test_message_preserved(self):
        err = ModelNotReadyError("test message")
        assert str(err) == "test message"


class TestMLInferenceProviderAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            MLInferenceProvider()

    def test_subclass_must_implement_enrich(self):
        class Incomplete(MLInferenceProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_with_enrich_can_instantiate(self):
        class Complete(MLInferenceProvider):
            def enrich(self, message: dict) -> dict:
                return message

        instance = Complete()
        assert instance.enrich({"key": "val"}) == {"key": "val"}


class TestSequenceClassifierAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            SequenceClassifier()

    def test_subclass_must_implement_all_methods(self):
        class Partial(SequenceClassifier):
            @property
            def is_ready(self) -> bool:
                return True

        with pytest.raises(TypeError):
            Partial()


class TestEntityExtractorAbstract:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            EntityExtractor()

    def test_subclass_must_implement_all_methods(self):
        class Partial(EntityExtractor):
            @property
            def is_ready(self) -> bool:
                return True

        with pytest.raises(TypeError):
            Partial()
