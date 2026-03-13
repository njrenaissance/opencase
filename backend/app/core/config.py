from importlib.metadata import version

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "OpenCase"
    app_version: str = version("opencase")
    debug: bool = False
    deployment_mode: str = "airgapped"

    model_config = {"env_prefix": "OPENCASE_"}


settings = Settings()
