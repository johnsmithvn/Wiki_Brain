from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Second Brain"
    APP_VERSION: str = "0.2.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    KNOWLEDGE_DIR: Path = Path(__file__).resolve().parent.parent / "knowledge"
    DB_PATH: Path = Path(__file__).resolve().parent.parent / "data" / "index.db"
    ALLOWED_EXTENSIONS: set[str] = {".md", ".markdown"}

    model_config = {"env_prefix": "SB_"}

    def ensure_dirs(self) -> None:
        self.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
