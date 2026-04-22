from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    model_name: str = "claude-sonnet-4-6"

    # Cost/emissions constants
    cost_per_km_usd: float = 2.15
    co2_per_km_kg: float = 0.89
    annual_bus_operating_cost_usd: float = 85_000.0
    daily_trips: int = 2          # morning + afternoon
    school_days_per_year: int = 180

    # LLM loop guard
    max_tool_turns: int = 8

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Dataset path (relative to this file's directory)
    dataset_dir: Path = Path(__file__).parent / "data" / "datasets"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "protected_namespaces": ()}


settings = Settings()
