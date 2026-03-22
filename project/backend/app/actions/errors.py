class ActionError(Exception):
    """Base exception for all action-layer errors."""


class NotFoundError(ActionError):
    """Raised when a requested entity does not exist."""


class ValidationError(ActionError):
    """Raised when input data fails a business rule."""


class ConflictError(ActionError):
    """Raised when an operation conflicts with the current state."""
