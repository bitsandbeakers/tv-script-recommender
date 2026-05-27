"""Generate embeddings from extracted script features."""

from sentence_transformers import SentenceTransformer

from backend.core.config import settings

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load the embedding model."""
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def features_to_text(features: dict) -> str:
    """Convert extracted features dict into a text representation for embedding."""
    parts = []
    if features.get("themes"):
        parts.append(f"Themes: {', '.join(features['themes'])}")
    if features.get("tone"):
        parts.append(f"Tone: {', '.join(features['tone'])}")
    if features.get("humor_type"):
        parts.append(f"Humor: {', '.join(features['humor_type'])}")
    if features.get("dialogue_style"):
        parts.append(f"Dialogue: {', '.join(features['dialogue_style'])}")
    if features.get("emotional_register"):
        parts.append(f"Emotional register: {', '.join(features['emotional_register'])}")
    if features.get("pacing"):
        parts.append(f"Pacing: {features['pacing']}")
    if features.get("genre_blend"):
        parts.append(f"Genre: {', '.join(features['genre_blend'])}")
    if features.get("style_summary"):
        parts.append(features["style_summary"])
    return ". ".join(parts)


def embed_text(text: str) -> list[float]:
    """Generate embedding vector for a text string."""
    model = get_embedding_model()
    embedding = model.encode(text)
    return embedding.tolist()
