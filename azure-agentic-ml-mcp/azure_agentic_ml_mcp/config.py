from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    subscription_id: str
    resource_group: str
    location: str

    file_share_name: str
    storage_account_name: str
    storage_account_key: str

    container_registry_server: str
    container_registry_username: str
    container_registry_password: str

    container_app_environment_id: str

    model_trainer_image: str = "azure-agentic-ml-model-trainer:latest"
    model_server_image: str = "azure-agentic-ml-model-server:latest"

    trainer_memory_gb: float = 4
    trainer_cpu: float = 2

    server_memory_gb: float = 2
    server_cpu: float = 1

    csv_download_timeout_seconds: int = 300
    csv_upload_timeout_seconds: int = 300
    csv_profile_timeout_seconds: int = 600
    model_training_timeout_seconds: int = 600
    model_deployment_timeout_seconds: int = 600

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AZURE_AGENTICML_MCP_",
        case_sensitive=False,
    )


settings = Settings()
