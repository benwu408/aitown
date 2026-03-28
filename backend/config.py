from pydantic_settings import BaseSettings

# Simulation timing — HARDCODED, not overridable by .env
# (The .env file may contain old values from a previous version)
TICK_DURATION_MS = 100      # Real-time ms between ticks (before speed multiplier)
TICKS_PER_DAY = 480         # 1 tick = 3 sim-minutes. Full day = 480 ticks.
REFLECTION_INTERVAL = 60    # Ticks between reflection cycles


class Settings(BaseSettings):
    # LLM
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model_name: str = "gpt-4o-mini"
    llm_max_concurrent_requests: int = 5
    llm_call_timeout_seconds: int = 30

    # Embeddings
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_base_url: str = ""

    # Server
    backend_port: int = 8000

    # Database
    db_path: str = "data/agentica.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
