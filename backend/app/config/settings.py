from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cors_origins: list[str] = ["http://localhost:3000"]
    max_upload_size_mb: int = 20
    debug: bool = False
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    llm_total_timeout_s: float = 30.0
    llm_max_enriched: int = 100
    database_url: str = "sqlite:///./statements.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
