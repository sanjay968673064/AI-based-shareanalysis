from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    allow_dev_user_header: bool = False
    database_url: str = "postgresql+asyncpg://portfolio:portfolio@postgres:5432/portfolio"
    redis_url: str = "redis://redis:6379/0"
    encryption_key: str = "development-only-replace-me"
    zerodha_kite_mcp_url: str = "http://kite-mcp:8080"
    zerodha_kite_mcp_read_only: bool = True
    zerodha_integration_mode: str = "mcp"
    zerodha_hosted_mcp_url: str = "https://mcp.kite.trade/mcp"
    zerodha_mcp_login_tool: str = "login"
    zerodha_mcp_holdings_tool: str = "get_holdings"
    zerodha_kite_api_key: str = ""
    zerodha_kite_api_secret: str = ""
    zerodha_redirect_url: str = "http://localhost:8000/api/v1/zerodha/callback"
    market_data_provider: str = "yahoo"
    market_data_timeout_seconds: float = 6.0
    market_data_max_concurrency: int = 8
    analytics_daily_refresh_enabled: bool = True
    analytics_daily_refresh_check_seconds: int = 21600
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = 75.0
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://0.0.0.0:3000",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
