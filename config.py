"""Application configuration via pydantic-settings."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    _DEFAULT_MODEL_DUMP_EXCLUDE = frozenset({
        "supabase_url",
        "vite_supabase_url",
    })

    # API keys
    anthropic_api_key: str = ""
    tomtom_api_key: str = ""
    zillow_api_key: str = ""
    attom_api_key: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://dev:dev@localhost:5432/realestate"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Supabase Auth
    supabase_url: str = ""
    supabase_jwt_issuer: str = ""
    supabase_jwks_url: str = ""
    vite_supabase_url: str = Field(default="", validation_alias="VITE_SUPABASE_URL")
    vite_supabase_publishable_key: str = Field(
        default="",
        validation_alias="VITE_SUPABASE_PUBLISHABLE_KEY",
    )

    # Public frontend runtime config
    public_api_base_url: str = Field(default="/api", validation_alias="VITE_API_BASE_URL")
    public_ws_base_url: str = Field(default="/ws", validation_alias="VITE_WS_URL")
    public_map_style_url: str = Field(
        default="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        validation_alias="VITE_MAP_STYLE_URL",
    )
    cors_allowed_origins: str = "http://localhost:5173"

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

    # Jurisdiction / JP release ---------------------------------------------
    # "us" preserves the legacy code path. "jp_tokyo" activates
    # guardrails_jp, MoneyJPY formatting, and the JP provider stack.
    jurisdiction: str = "us"
    default_prefecture_code: str = "13"  # 東京都

    # Japan data providers (each: "mock" reads fixtures, "live" hits network)
    reins_mode: str = "mock"
    reinfolib_mode: str = "mock"

    # Japan API keys (empty in dev; populated from Secrets Manager in prod)
    reinfolib_api_key: str = ""
    estat_app_id: str = ""
    resas_api_key: str = ""
    google_maps_api_key: str = ""

    # RAG / embedder ---------------------------------------------------------
    # "hash" — deterministic, zero-dep, CI default.
    # "local_st" — sentence-transformers multilingual, for dev+integration.
    # "voyage" — production embeddings via Voyage AI.
    embedder_mode: str = "hash"
    embedding_dim: int = 64
    voyage_api_key: str = ""
    cohere_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # shared .env may include VITE_* keys for the frontend only
    )

    @field_validator("supabase_jwt_issuer", "supabase_jwks_url", mode="before")
    @classmethod
    def _normalize_optional_supabase_overrides(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized or normalized.startswith("#"):
                return ""
            return normalized
        return str(value)

    @property
    def public_supabase_url(self) -> str:
        return self.vite_supabase_url or self.supabase_url

    @property
    def public_supabase_publishable_key(self) -> str:
        return self.vite_supabase_publishable_key

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_allowed_origins.split(",")]
        return [origin for origin in origins if origin]

    def public_runtime_config(self) -> dict[str, str]:
        return {
            "environment": self.environment,
            "api_base_url": self.public_api_base_url,
            "ws_base_url": self.public_ws_base_url,
            "supabase_url": self.public_supabase_url,
            "supabase_publishable_key": self.public_supabase_publishable_key,
            "map_style_url": self.public_map_style_url,
        }

    def model_dump(self, *args, **kwargs):
        exclude = kwargs.pop("exclude", None)
        if exclude is None:
            exclude_set = set(self._DEFAULT_MODEL_DUMP_EXCLUDE)
        else:
            exclude_set = set(exclude)
            exclude_set.update(self._DEFAULT_MODEL_DUMP_EXCLUDE)
        return super().model_dump(*args, exclude=exclude_set, **kwargs)


settings = Settings()
