from pydantic import BaseModel


class ScriptFeatures(BaseModel):
    """Extracted features from a TV script."""

    show_title: str
    season: int | None = None
    episode: int | None = None

    # Core dimensions
    themes: list[str] = []
    tone: list[str] = []  # e.g. ["dark", "satirical", "melancholic"]
    humor_type: list[str] = []  # e.g. ["dry wit", "slapstick", "absurdist"]
    dialogue_style: list[str] = []  # e.g. ["rapid-fire", "monologue-heavy", "naturalistic"]
    emotional_register: list[str] = []  # e.g. ["restrained", "explosive", "vulnerable"]
    pacing: str = ""  # e.g. "fast", "slow-burn", "variable"
    genre_blend: list[str] = []  # e.g. ["drama", "comedy", "thriller"]
    narrative_structure: str = ""  # e.g. "episodic", "serialized", "anthology"
    vocabulary_complexity: str = ""  # e.g. "simple", "moderate", "dense"

    # Summary for display
    style_summary: str = ""


class ShowInfo(BaseModel):
    """Show metadata from catalog + external sources."""

    id: str
    title: str
    year: int | None = None
    network: str = ""
    genres: list[str] = []
    overview: str = ""
    poster_url: str = ""
    imdb_id: str = ""
    tmdb_id: int | None = None
    tvdb_id: int | None = None
    status: str = ""
    num_seasons: int = 0
    num_episodes: int = 0
    num_episodes_analyzed: int = 0
    features: ScriptFeatures | None = None


class RecommendationRequest(BaseModel):
    """User request for recommendations."""

    # Either a show title to find similar shows, or a natural language query
    query: str
    liked_shows: list[str] = []
    disliked_shows: list[str] = []
    top_k: int = 10


class RecommendationResult(BaseModel):
    """A single recommendation."""

    show: ShowInfo
    similarity_score: float
    explanation: str = ""


class RecommendationResponse(BaseModel):
    """Response with recommendations."""

    results: list[RecommendationResult]
    query_interpretation: str = ""
