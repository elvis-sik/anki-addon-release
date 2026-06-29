class ReleaseError(Exception):
    """Base error for user-facing release failures."""


class ConfigError(ReleaseError):
    """Raised when release configuration is missing or invalid."""


class ManifestError(ReleaseError):
    """Raised when an Anki add-on manifest is invalid."""


class PackageError(ReleaseError):
    """Raised when packaging cannot complete safely."""


class PublishError(ReleaseError):
    """Raised when an AnkiWeb publishing flow cannot complete safely."""
