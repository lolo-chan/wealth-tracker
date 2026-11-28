from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = os.environ.get('DATABASE_URL')
    voo_units: float = 0.430844

settings = Settings()