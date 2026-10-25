"""Runtime settings from environment variables or a .env file.

Context: Loaded once at the command-line entry point. |
Input: Environment. |
Output: Validated Settings.
"""

from __future__ import annotations

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from idp.errors import ConfigError


class Settings(BaseSettings):
    """Credentials and limits for the benchmark run."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    cloudflare_account_id: str | None = None
    cloudflare_api_token: SecretStr | None = None
    request_timeout_seconds: float = Field(default=120.0, gt=0)
    max_attempts: int = Field(default=4, ge=1, le=10)

    def require(self, name: str) -> str:
        """Return a setting that a selected provider needs.

        Args:
            name: Attribute name, e.g. "openai_api_key".

        Returns:
            The plain value.

        Raises:
            ConfigError: If the setting is missing or empty.
        """
        value = getattr(self, name)
        plain = value.get_secret_value() if isinstance(value, SecretStr) else value
        if not plain:
            raise ConfigError(f"{name.upper()} is not set; add it to .env")
        return str(plain)
