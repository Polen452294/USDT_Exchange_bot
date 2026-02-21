from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    BOT_TOKEN: str

    DB_AUTO_CREATE: bool = True

    nudge1_delay_seconds: int = 10      # 20 минут
    nudge2_delay_seconds: int = 10       # 15 минут
    nudge3_delay_seconds: int = 10      # 100 минут
    nudge_worker_interval_seconds: int = 5 # обновление дожимов
    nudge4_delay_seconds: int = 86400     # 24 часа

    nudge5_test_mode: bool = True
    nudge5_test_delay_seconds: int = 10

    nudge6_test_mode: bool = True
    nudge6_test_delay_seconds: int = 20

    nudge7_test_mode: bool = True
    nudge7_test_delay_seconds: int = 30

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

    VK_GROUP_TOKEN: str | None = None
    VK_GROUP_ID: int | None = None

    ADMIN_IDS: str = ""

    @property
    def admin_ids(self) -> set[int]:
        raw = (self.ADMIN_IDS or "").strip()
        if not raw:
            return set()
        parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
        ids: set[int] = set()
        for p in parts:
            try:
                ids.add(int(p))
            except Exception:
                continue
        return ids

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()