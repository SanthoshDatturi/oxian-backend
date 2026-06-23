class StorageError(Exception):
    """Base storage error."""


class StorageUploadError(StorageError):
    """Raised when an upload cannot be completed."""


class StorageDownloadError(StorageError):
    """Raised when a download cannot be completed."""


class StorageDeleteError(StorageError):
    """Raised when a delete cannot be completed."""


class StorageListError(StorageError):
    """Raised when listing blobs fails."""


class StorageNotFoundError(StorageError):
    """Raised when a requested blob does not exist."""


class StorageAuthError(StorageError):
    """Raised when authentication/authorization fails."""


class StorageBackendError(StorageError):
    """Raised when the storage service is unavailable."""
