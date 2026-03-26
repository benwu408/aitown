from pydantic_settings import BaseSettings


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

    # Simulation
    tick_duration_ms: int = 200
    ticks_per_day: int = 288
    reflection_interval: int = 80
    max_memories_per_retrieval: int = 15

    # Server
    backend_port: int = 8000

    # Database
    db_path: str = "data/agentica.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
