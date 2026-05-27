"""API route handlers."""

from fastapi import APIRouter, HTTPException

from backend.db import show_store
from backend.metadata.enrich import enrich_show
from backend.models.schemas import RecommendationRequest, RecommendationResponse, RecommendationResult, ShowInfo
from backend.recommender.engine import recommend_blended, recommend_by_show, recommend_by_text

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "shows_indexed": show_store.get_show_count()}


# --- Show catalog ---


@router.get("/shows", response_model=list[ShowInfo])
def list_shows():
    """List all shows in the catalog."""
    return show_store.list_shows()


@router.get("/shows/search", response_model=list[ShowInfo])
def search_shows(q: str):
    """Search shows by title."""
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    return show_store.search_shows(q)


@router.get("/shows/{show_id}", response_model=ShowInfo)
def get_show(show_id: str):
    """Get a show by ID."""
    show = show_store.get_show(show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")
    return show


@router.delete("/shows/{show_id}")
def delete_show(show_id: str):
    """Delete a show from the catalog."""
    if not show_store.delete_show(show_id):
        raise HTTPException(status_code=404, detail="Show not found")
    return {"status": "deleted", "id": show_id}


@router.get("/shows/{show_id}/enrich", response_model=ShowInfo)
def enrich_show_metadata(show_id: str):
    """Enrich an existing show with metadata from TMDB/TVDB."""
    show = show_store.get_show(show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    metadata = enrich_show(show.title, year=show.year, imdb_id=show.imdb_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="No metadata found from external sources")

    enriched = show.model_copy(update={
        "network": metadata.get("network") or show.network,
        "genres": metadata.get("genres") or show.genres,
        "overview": metadata.get("overview") or show.overview,
        "poster_url": metadata.get("poster_url") or show.poster_url,
        "imdb_id": metadata.get("imdb_id") or show.imdb_id,
        "tmdb_id": metadata.get("tmdb_id") or show.tmdb_id,
        "tvdb_id": metadata.get("tvdb_id") or show.tvdb_id,
        "status": metadata.get("status") or show.status,
        "num_seasons": metadata.get("num_seasons") or show.num_seasons,
        "num_episodes": metadata.get("num_episodes") or show.num_episodes,
    })
    show_store.upsert_show(enriched)
    return enriched


@router.get("/lookup")
def lookup_show(q: str):
    """Look up show metadata from TMDB/TVDB without adding to catalog."""
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")
    metadata = enrich_show(q)
    if not metadata:
        raise HTTPException(status_code=404, detail="No results found")
    return metadata


# --- Recommendations ---


@router.post("/recommend", response_model=RecommendationResponse)
def get_recommendations(request: RecommendationRequest):
    """Get TV show recommendations.

    Supports three modes:
    - Free-text query: "dark comedy with sharp dialogue"
    - Similar to show: provide liked_shows list
    - Blended: combine query + liked/disliked shows
    """
    if not request.query and not request.liked_shows:
        raise HTTPException(status_code=400, detail="Provide a query or liked shows")

    # Choose recommendation strategy
    if request.liked_shows and (request.query or request.disliked_shows):
        # Blended mode
        raw_results = recommend_blended(
            liked_ids=request.liked_shows,
            disliked_ids=request.disliked_shows or None,
            query=request.query,
            top_k=request.top_k,
        )
        query_interpretation = f"Blended: query='{request.query}', liked={request.liked_shows}"
    elif request.liked_shows and len(request.liked_shows) == 1:
        # Single show similarity
        raw_results = recommend_by_show(request.liked_shows[0], top_k=request.top_k)
        query_interpretation = f"Shows similar to {request.liked_shows[0]}"
    elif request.liked_shows:
        # Multiple liked shows, no query
        raw_results = recommend_blended(
            liked_ids=request.liked_shows,
            top_k=request.top_k,
        )
        query_interpretation = f"Shows similar to {', '.join(request.liked_shows)}"
    else:
        # Pure text query
        raw_results = recommend_by_text(request.query, top_k=request.top_k)
        query_interpretation = request.query

    results = _format_results(raw_results)

    return RecommendationResponse(results=results, query_interpretation=query_interpretation)


@router.get("/recommend/{show_id}", response_model=RecommendationResponse)
def get_similar_shows(show_id: str, top_k: int = 10):
    """Get shows similar to a specific show (convenience endpoint)."""
    show = show_store.get_show(show_id)
    if not show:
        raise HTTPException(status_code=404, detail="Show not found")

    raw_results = recommend_by_show(show_id, top_k=top_k)
    results = _format_results(raw_results)

    return RecommendationResponse(
        results=results,
        query_interpretation=f"Shows similar to {show.title}",
    )


def _format_results(raw_results: dict) -> list[RecommendationResult]:
    """Convert raw ChromaDB results to API response format."""
    results = []
    if not raw_results.get("ids") or not raw_results["ids"][0]:
        return results

    for i, show_id in enumerate(raw_results["ids"][0]):
        metadata = raw_results["metadatas"][0][i] if raw_results.get("metadatas") else {}
        distance = raw_results["distances"][0][i] if raw_results.get("distances") else 0.0

        # Try to enrich from SQLite store
        stored_show = show_store.get_show(show_id)
        if stored_show:
            show_info = stored_show
        else:
            show_info = ShowInfo(
                id=show_id,
                title=metadata.get("title", show_id),
                year=metadata.get("year"),
                network=metadata.get("network", ""),
            )

        results.append(
            RecommendationResult(
                show=show_info,
                similarity_score=round(max(0.0, 1 - distance), 4),
                explanation=metadata.get("style_summary", ""),
            )
        )

    return results
