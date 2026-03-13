from importlib.metadata import version
from typing import Any

from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """Application settings with layered loading.

    Priority (highest wins):
      1. Environment variables (OPENCASE_ prefix)
      2. .env file
      3. config.json file
      4. Hard-coded defaults
    """

    app_name: str = "OpenCase"
    app_version: str = version("opencase")
    debug: bool = False
    deployment_mode: str = "airgapped"

    model_config = SettingsConfigDict(
        env_prefix="OPENCASE_",
        env_file=".env",
        env_file_encoding="utf-8",
        json_file="config.json",
        json_file_encoding="utf-8",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003 — no secrets dir used
        **kwargs: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            env_settings,
            dotenv_settings,
            JsonConfigSettingsSource(settings_cls),
            init_settings,  # allows Settings(field=val) for testing
        )


settings = Settings()
