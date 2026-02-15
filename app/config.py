from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str

    nudge2_delay_seconds: int = 900
    nudge_worker_interval_seconds: int = 60
    nudge2_resend_after_seconds: int = 0

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "usdt_exchange"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    LOG_LEVEL: str = "INFO"

    crm_mode: str = "mock"
    crm_base_url: str = ""
    crm_token: str = ""
    crm_timeout: float = 10.0

    crm_offices_path: str = "/offices"
    crm_rates_path: str = "/rates"
    crm_create_request_path: str = "/requests"
    crm_event_path: str = "/events"
    crm_status_path: str = "/requests/status"

    crm_idempotency_header: str = "Idempotency-Key"
    crm_auth_header: str = "Authorization"
    crm_auth_prefix: str = "Bearer"

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()