# backend/app/config.py

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings.
    Reads from environment variables automatically.
    """

    # App info
    APP_NAME:        str = "Supply Chain Disruption Management Environment"
    APP_VERSION:     str = "1.0.0"
    APP_DESCRIPTION: str = (
        "An OpenEnv-compliant AI training environment where agents "
        "learn to manage real-world supply chain disruptions by rerouting "
        "orders, substituting suppliers, and minimizing revenue loss."
    )

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 7860   # HuggingFace Spaces default

    # LLM settings are optional here; inference.py reads them directly.
    API_BASE_URL: str = os.getenv("API_BASE_URL", "")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "")
    HF_TOKEN: str = os.getenv("HF_TOKEN", "")

    # Environment limits
    MAX_STEPS_EASY:   int = 10
    MAX_STEPS_MEDIUM: int = 20
    MAX_STEPS_HARD:   int = 30

    class Config:
        env_file = ".env"
        extra    = "allow"


# Single global settings instance
settings = Settings()
