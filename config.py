import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Загружаем переменные из .env файла
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class Settings(BaseSettings):
        telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        yandex_api_key: str = os.getenv("YANDEX_API_KEY", "")
        yandex_folder_id: str = os.getenv("YANDEX_FOLDER_ID", "b1g2co248mbe7rhlk2ir")
        openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        model_config = SettingsConfigDict(
            env_file=os.path.join(BASE_DIR, ".env"),
            env_file_encoding="utf-8",
            extra="ignore"
        )
    settings = Settings()

except ImportError:
    # Запасной вариант на встроенном os.getenv
    class SettingsFallback:
        @property
        def telegram_bot_token(self) -> str:
            return os.getenv("TELEGRAM_BOT_TOKEN", "")

        @property
        def yandex_api_key(self) -> str:
            return os.getenv("YANDEX_API_KEY", "")

        @property
        def yandex_folder_id(self) -> str:
            return os.getenv("YANDEX_FOLDER_ID", "b1g2co248mbe7rhlk2ir")

        @property
        def openai_api_key(self) -> str:
            return os.getenv("OPENAI_API_KEY", "")

        @property
        def openai_model(self) -> str:
            return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    settings = SettingsFallback()
