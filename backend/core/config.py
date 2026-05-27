from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TV Script Recommender"
    debug: bool = False

    # Database
    database_url: str = "sqlite:///./tvscripts.db"

    # ChromaDB
    chroma_collection: str = "tv_scripts"
    chroma_persist_dir: str = "./chroma_data"

    # Embedding model (runs locally, no API key needed)
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # LLM for feature extraction — configured via LiteLLM model strings.
    # Examples:
    #   ollama/mistral          (local Ollama, free)
    #   ollama/llama3.2
    #   groq/llama-3.1-8b-instant   (Groq free tier, needs TVR_LLM_API_KEY)
    #   openai/gpt-4o-mini          (OpenAI, needs TVR_LLM_API_KEY)
    #   gemini/gemini-1.5-flash     (Google, free tier, needs TVR_LLM_API_KEY)
    #   anthropic/claude-haiku-4-5  (Anthropic, needs TVR_LLM_API_KEY)
    llm_model: str = "ollama/mistral"
    llm_api_base: str = ""   # e.g. "http://localhost:11434" for local Ollama
    llm_api_key: str = ""    # API key for the chosen provider

    # OpenSubtitles
    opensubtitles_api_key: str = ""
    opensubtitles_username: str = ""
    opensubtitles_password: str = ""

    # TMDB
    tmdb_api_key: str = ""
    tmdb_read_token: str = ""

    # TVDB
    tvdb_api_key: str = ""

    model_config = {"env_file": ".env", "env_prefix": "TVR_"}


settings = Settings()
