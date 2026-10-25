"""Exception hierarchy for the package.

Context: Shared by every module that can fail at a boundary. |
Input: None. |
Output: Exception classes.
"""


class IdpError(Exception):
    """Base class for all errors raised by this package."""


class ConfigError(IdpError):
    """A required setting is missing or invalid."""


class ProviderError(IdpError):
    """A model provider returned an error or could not be reached."""


class TransientProviderError(ProviderError):
    """A provider error that is worth retrying (rate limit, timeout, 5xx)."""


class ResponseFormatError(ProviderError):
    """A provider answered, but the answer does not match the expected structure."""
