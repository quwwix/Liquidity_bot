from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    telegram_bot_token: str = ""
    my_chat_id: int = 0
    webapp_url: str = "http://localhost:8000"
    database_path: str = "/data/liquidity.db"
    scrape_enabled: bool = True

    price_min: int = 4000
    price_max: int = 20000

    @property
    def price_ranges(self) -> list[tuple[int, int, str]]:
        return [
            (4000, 8000, "4000–8000"),
            (8000, 12000, "8000–12000"),
            (12000, 16000, "12000–16000"),
            (16000, 20000, "16000–20000"),
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
