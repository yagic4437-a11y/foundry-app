from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.com/v1"
    siliconflow_model: str = "Qwen/Qwen3-8B"
    siliconflow_embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    siliconflow_embedding_fallbacks: str = "BAAI/bge-large-en-v1.5,BAAI/bge-m3"
    database_path: Path = Path("data/assessments.sqlite")
    chroma_path: Path = Path("data/chroma")
    legal_docs_path: Path = Path("data/legal")

    @property
    def embedding_fallback_models(self) -> list[str]:
        return [item.strip() for item in self.siliconflow_embedding_fallbacks.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
