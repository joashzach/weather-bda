"""Application configuration and environment settings with strict Pydantic validation."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.enums import EnvironmentType

DEFAULT_JWT_EXAMPLE = "change_this_to_a_secure_random_32_character_string_at_least"
DEFAULT_IP_HASH_EXAMPLE = "change_this_to_a_random_secret_for_hmac_ip_hashing"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: EnvironmentType = EnvironmentType.DEVELOPMENT

    # Database
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/weather_dev"
    TEST_DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/weather_test"

    # JWT Authentication
    JWT_SECRET: str = DEFAULT_JWT_EXAMPLE
    JWT_ISSUER: str = "weather-bda"
    JWT_AUDIENCE: str = "weather-bda-api"
    ACCESS_TOKEN_TTL_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    # Security & Abuse Prevention
    IP_HASH_SECRET: str = DEFAULT_IP_HASH_EXAMPLE
    API_DOCS_ENABLED: bool = True
    TRUSTED_PROXY_IPS: str = ""
    ALLOWED_SOURCE_HOSTS: str = "api.open-meteo.com,api.data.gov.in,mausam.imd.gov.in"

    # Ingestion Engine & Worker
    INGESTION_ENABLED: bool = False
    INGESTION_RUN_TIMEOUT_SECONDS: int = 900
    HTTP_CONNECT_TIMEOUT: float = 5.0
    HTTP_READ_TIMEOUT: float = 15.0
    HTTP_MAX_RETRIES: int = 3
    HTTP_MAX_RESPONSE_BYTES: int = 5_242_880  # 5 MB

    # Provider Defaults
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"
    OPEN_METEO_FORECAST_DAYS: int = 7
    OPEN_METEO_PAST_DAYS: int = 2
    DATA_GOV_IN_API_KEY: str = ""

    # Rate Limiting
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REPORT_SUBMIT: str = "5/hour"
    RATE_LIMIT_PUBLIC_READ: str = "120/minute"
    RATE_LIMIT_TRACKING: str = "20/minute"

    # Account Lockout
    LOGIN_LOCKOUT_THRESHOLD: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Citizen Reports
    REPORT_LOCATION_RADIUS_KM: float = 50.0
    REPORT_MAX_AGE_DAYS: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("TEST_DATABASE_URL")
    @classmethod
    def validate_test_database_url(cls, v: str) -> str:
        # Rule: test database name must end in _test
        db_name = v.split("/")[-1].split("?")[0]
        if not db_name.endswith("_test"):
            raise ValueError(f"TEST_DATABASE_URL database name '{db_name}' must end in '_test'")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        origins = [origin.strip() for origin in v.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS cannot be empty")
        for origin in origins:
            if origin == "*":
                raise ValueError("CORS_ORIGINS wildcard '*' is strictly forbidden")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == EnvironmentType.PRODUCTION:
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if self.JWT_SECRET == DEFAULT_JWT_EXAMPLE:
                raise ValueError("JWT_SECRET cannot use the example value in production")
            if len(self.IP_HASH_SECRET) < 16 or self.IP_HASH_SECRET == DEFAULT_IP_HASH_EXAMPLE:
                raise ValueError("IP_HASH_SECRET must be set to a secure secret in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [ip.strip() for ip in self.TRUSTED_PROXY_IPS.split(",") if ip.strip()]

    @property
    def allowed_source_host_list(self) -> list[str]:
        return [
            host.strip().lower() for host in self.ALLOWED_SOURCE_HOSTS.split(",") if host.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
