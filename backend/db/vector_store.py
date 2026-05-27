"""ChromaDB vector store for script embeddings."""

import chromadb

from backend.core.config import settings

_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create ChromaDB persistent client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
    return _client


def get_collection() -> chromadb.Collection:
    """Get or create the TV scripts collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_show(show_id: str, embedding: list[float], metadata: dict) -> None:
    """Add or update a show's embedding in the vector store."""
    collection = get_collection()
    collection.upsert(
        ids=[show_id],
        embeddings=[embedding],
        metadatas=[metadata],
    )


def query_similar(embedding: list[float], top_k: int = 10) -> dict:
    """Find shows with similar embeddings."""
    collection = get_collection()
    return collection.query(
        query_embeddings=[embedding],
        n_results=top_k,
    )
