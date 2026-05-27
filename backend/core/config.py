from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TV Script Recommender"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./tvscripts.db"

    # ChromaDB
    chroma_collection: str = "tv_scripts"
    chroma_persist_dir: str = "./chroma_data"

    # Embedding model
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # LLM for feature extraction (configurable)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"

    # OpenSubtitles
    opensubtitles_api_key: str = ""
    opensubtitles_username: str = ""
    opensubtitles_password: str = ""

    # TMDB
    tmdb_api_key: str = ""
    tmdb_read_token: str = ""

    # TVDB
    tvdb_api_key: str = ""

    # API keys loaded from env
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env", "env_prefix": "TVR_"}


settings = Settings()
