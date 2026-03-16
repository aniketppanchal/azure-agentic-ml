from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_endpoint: AnyHttpUrl
    model_deployment_name: str

    mcp_url: AnyHttpUrl

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AZURE_AGENTICML_AGENT_",
        case_sensitive=False,
    )


settings = Settings()
