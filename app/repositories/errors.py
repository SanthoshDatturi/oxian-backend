class RepositoryError(Exception):
    """Base exception for all repository-related errors."""


class EntityNotFoundError(RepositoryError):
    """Raised when an expected entity cannot be found."""


class InvalidEntityError(RepositoryError):
    """Raised when an entity or its attributes are invalid for an operation."""


class InvalidFileStateError(RepositoryError):
    """Raised when a file's state prevents an operation."""
