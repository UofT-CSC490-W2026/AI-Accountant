"""Custom exceptions for the service layer."""


class AccountingError(Exception):
    """Base exception for accounting-related errors."""

    pass


class UnbalancedEntryError(AccountingError):
    """Raised when a journal entry does not balance (debits != credits)."""

    pass


class InvalidEntryStateError(AccountingError):
    """Raised when an operation is invalid for the entry's current state."""

    pass


class AccountNotFoundError(AccountingError):
    """Raised when a referenced account does not exist."""

    pass


class DuplicateAccountError(AccountingError):
    """Raised when attempting to create an account that already exists."""

    pass


class AssetError(Exception):
    """Base exception for asset-related errors."""

    pass


class AssetAlreadyDisposedError(AssetError):
    """Raised when attempting to dispose an already-disposed asset."""

    pass


class ShareholderLoanWarning(Exception):
    """Warning for shareholder loan issues (e.g., s.15(2) deadline approaching)."""

    pass
