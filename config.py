"""Application configuration via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API keys
    anthropic_api_key: str = ""
    tomtom_api_key: str = ""
    zillow_api_key: str = ""
    attom_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://dev:dev@localhost:5432/realestate"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MiroFish
    mirofish_api_url: str = "http://localhost:5001"
    mirofish_webhook_secret: str = ""
    mirofish_mode: str = "mock"  # "mock" for local simulation, "live" for external service

    # App
    environment: str = "development"
    log_level: str = "INFO"
    max_deal_value_auto: int = 2_000_000
    min_offer_percent: float = 0.50
    max_counter_rounds: int = 10

    # Market data provider: "mock" or "zillow"
    market_data_provider: str = "mock"

    # Monte Carlo simulation
    monte_carlo_scenarios: int = 300

    # Negotiation simulation
    max_simulation_rounds: int = 30
    max_batch_scenarios: int = 6

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
