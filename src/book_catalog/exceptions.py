"""Domain errors distinguish validation, configuration and external failures."""


class CatalogError(Exception):
    """Base expected application error."""


class ValidationError(CatalogError, ValueError):
    """Invalid book value or selection."""


class ImportError(CatalogError):
    """CSV cannot be converted into a valid catalog."""


class ConfigurationError(CatalogError):
    """Invalid or missing configuration."""


class ExportError(CatalogError):
    """Output was not committed."""


class ExternalCatalogError(CatalogError):
    """External repository is unavailable or returned invalid data."""
