from pathlib import Path
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # LLM
    google_api_key: str
    gemini_model: str
    llm_temperature: float 
    llm_max_output_tokens: int
    llm_timeout: float

    # Agent working memory
    agent_max_steps: int = 5
    agent_prompt_window_steps: int = 2
    agent_prompt_action_input_limit_chars: int = 700
    agent_prompt_default_observation_limit_chars: int = 1000
    agent_prompt_error_observation_limit_chars: int = 400
    chat_history_window_messages: int = 6

    # Per-tool observation limits (chars)
    agent_prompt_vector_search_limit_chars: int = 1500
    agent_prompt_attendance_query_limit_chars: int = 3000
    agent_prompt_employee_query_limit_chars: int = 700
    agent_prompt_shift_query_limit_chars: int = 700
    agent_prompt_ask_user_limit_chars: int = 500

    agent_tool_observation_limits: dict[str, int] = Field(
        default_factory=lambda: {
            "vector_search": 1500,
            "attendance_query": 3000,
            "employee_query": 700,
            "shift_query": 700,
            "ask_user": 500,
        }
    )

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_policy: str 
    qdrant_timeout: float = 5.0
    qdrant_upsert_batch_size: int

    redis_host: str
    redis_port: int
    redis_url: str = ""

    dense_vector_name: str
    sparse_vector_name: str
    bge_m3_dense_size: int

    # Embedding / reranking
    embedding_model: str 
    embedding_device: str

    reranker_model: str 
    reranker_device: str
    retrieval_top_k: int
    rerank_top_n: int
    retrieval_score_threshold: float

    # API server
    api_host: str
    api_port: int
    api_debug: bool

    api_server_base_url: str
    rag_api_key: str

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def default_qdrant_collection(self) -> str:
        return self.qdrant_collection_policy

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

    



if __name__ == "__main__":
    # Test load settings
    settings = get_settings()
    print("Gemini Model:", settings.gemini_model)
    print("Qdrant URL:", settings.qdrant_url)
    print("Policy Collection:", settings.qdrant_collection_policy)
    print("Embedding Model:", settings.embedding_model)
    print("API:", f"{settings.api_host}:{settings.api_port}")
