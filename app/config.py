from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    secret_key: str
    log_level: str = "INFO"

    db_user: str
    db_password: str
    db_host: str
    db_port: int = 5432
    db_name: str

    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    # sesje server-side
    session_redis_url: str = "redis://redis:6379/2"
    session_ttl_seconds: int = 604800  # 7 dni
    session_cookie_name: str = "session_id"

    playwright_timeout_ms: int = 30000

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def alembic_database_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cookie_secure(self) -> bool:
        return self.app_env == "prod"


settings = Settings()
