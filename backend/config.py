# backend/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache


import os
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"

class Settings(BaseSettings):
    moysklad_token: str
    moysklad_api_url: str = "https://api.moysklad.ru/api/remap/1.2"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    secret_key: str = "change_me"

    class Config:
        env_file = (str(ENV_PATH), ".env")


@lru_cache()
def get_settings() -> Settings:
    return Settings()