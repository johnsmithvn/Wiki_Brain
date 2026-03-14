from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Second Brain"
    APP_VERSION: str = "0.8.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    KNOWLEDGE_DIR: Path = Path(__file__).resolve().parent.parent.parent / "knowledge"
    TEMPLATE_FOLDER: str = "template"
    DB_PATH: Path = Path(__file__).resolve().parent.parent.parent / "data" / "index.db"
    ALLOWED_EXTENSIONS: set[str] = {".md", ".markdown"}
    INDEX_EXCLUDED_FOLDERS: set[str] = {"_assets", "template", "inbox"}

    # Phase 4 — Ollama LLM
    OLLAMA_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b-instruct-q4_K_M"

    model_config = {"env_prefix": "SB_"}

    @property
    def TEMPLATE_DIR(self) -> Path:
        return self.KNOWLEDGE_DIR / self.TEMPLATE_FOLDER

    def is_excluded_from_index(self, rel_path: str) -> bool:
        normalized = rel_path.replace("\\", "/").strip("/")
        if not normalized:
            return False
        top_level = normalized.split("/", 1)[0]
        return top_level in self.INDEX_EXCLUDED_FOLDERS

    def ensure_dirs(self) -> None:
        self.KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
        (self.KNOWLEDGE_DIR / "inbox").mkdir(parents=True, exist_ok=True)
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
