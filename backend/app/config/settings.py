from typing import List, Set
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration for MarketPulse AI.
    Strictly validates supported instruments and forbids any prohibited symbols.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_ENV: str = "development"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    DATABASE_PATH: str = "marketpulse.db"

    # Upstox API credentials
    UPSTOX_API_KEY: str = Field(default="", description="Upstox API Key / Client ID")
    UPSTOX_API_SECRET: str = Field(default="", description="Upstox API Secret")
    UPSTOX_REDIRECT_URI: str = Field(default="http://localhost:8000/api/auth/callback")
    UPSTOX_ACCESS_TOKEN: str = Field(default="", description="Manual daily access token")

    # Strict instruments policy
    SUPPORTED_INSTRUMENTS: str = "HDFCBANK,ICICIBANK"
    ALLOWED_INSTRUMENTS_SET: Set[str] = {"HDFCBANK", "ICICIBANK"}
    FORBIDDEN_INSTRUMENTS_SET: Set[str] = {"RELIANCE"}

    # Timezone & market hours
    MARKET_TIMEZONE: str = "Asia/Kolkata"
    STALE_DATA_THRESHOLD_SECONDS: int = 15  # Mark ticks stale if no update in 15 seconds during active market

    @field_validator("SUPPORTED_INSTRUMENTS")
    @classmethod
    def validate_instruments(cls, v: str) -> str:
        symbols = [s.strip().upper() for s in v.split(",") if s.strip()]
        
        # Check forbidden symbols
        for forbidden in ["RELIANCE"]:
            if forbidden in symbols:
                raise ValueError(
                    f"CRITICAL VIOLATION: Instrument '{forbidden}' is strictly FORBIDDEN in MarketPulse AI."
                )

        # Ensure only allowed symbols exist
        allowed = {"HDFCBANK", "ICICIBANK"}
        for s in symbols:
            if s not in allowed:
                raise ValueError(
                    f"Unsupported instrument '{s}'. MarketPulse AI only permits HDFCBANK and ICICIBANK."
                )
        
        if not symbols:
            raise ValueError("SUPPORTED_INSTRUMENTS cannot be empty.")
            
        return ",".join(symbols)

    @property
    def instruments_list(self) -> List[str]:
        return [s.strip().upper() for s in self.SUPPORTED_INSTRUMENTS.split(",") if s.strip()]


settings = Settings()

