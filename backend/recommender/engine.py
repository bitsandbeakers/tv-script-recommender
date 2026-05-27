"""Recommendation engine: vector similarity with preference blending and re-ranking."""

import logging

from backend.db.show_store import get_show
from backend.db.vector_store import get_collection, query_similar
from backend.pipeline.embed import embed_text, features_to_text

logger = logging.getLogger(__name__)


def recommend_by_text(query: str, top_k: int = 10, exclude_ids: list[str] | None = None) -> dict:
    """Get recommendations from a natural language query."""
    embedding = embed_text(query)
    results = query_similar(embedding, top_k=top_k + len(exclude_ids or []))
    if exclude_ids:
        results = _filter_results(results, exclude_ids)
    return _trim_results(results, top_k)


def recommend_by_show(
    show_id: str,
    top_k: int = 10,
    exclude_ids: list[str] | None = None,
) -> dict:
    """Get recommendations based on a show already in the database."""
    show = get_show(show_id)
    if not show or not show.features:
        # Fall back to text search using the show title
        return recommend_by_text(show.title if show else show_id, top_k=top_k, exclude_ids=exclude_ids)

    features_dict = show.features.model_dump(exclude={"show_title", "season", "episode"})
    text = features_to_text(features_dict)
    embedding = embed_text(text)

    # Exclude the query show itself
    all_exclude = list(set((exclude_ids or []) + [show_id]))
    results = query_similar(embedding, top_k=top_k + len(all_exclude))
    results = _filter_results(results, all_exclude)
    return _trim_results(results, top_k)


def recommend_blended(
    liked_ids: list[str],
    disliked_ids: list[str] | None = None,
    query: str = "",
    top_k: int = 10,
) -> dict:
    """Blend multiple signals: liked shows, disliked shows, and free-text query.

    Strategy:
    1. Compute an average embedding from liked shows' features
    2. If a text query is provided, blend it in (weighted average)
    3. Retrieve candidates
    4. Penalize candidates similar to disliked shows
    """
    import numpy as np

    embeddings = []
    weights = []

    # Embed liked shows
    for show_id in liked_ids:
        show = get_show(show_id)
        if show and show.features:
            features_dict = show.features.model_dump(exclude={"show_title", "season", "episode"})
            text = features_to_text(features_dict)
        elif show:
            text = f"TV show: {show.title}"
        else:
            text = f"TV show: {show_id}"
        embeddings.append(embed_text(text))
        weights.append(1.0)

    # Embed free-text query if provided
    if query:
        embeddings.append(embed_text(query))
        weights.append(1.5)  # give user's explicit query slightly more weight

    if not embeddings:
        return {"ids": [[]], "distances": [[]], "metadatas": [[]]}

    # Weighted average embedding
    arr = np.array(embeddings)
    w = np.array(weights).reshape(-1, 1)
    blended = (arr * w).sum(axis=0) / w.sum()
    blended = (blended / np.linalg.norm(blended)).tolist()

    # Exclude liked + disliked from results
    exclude = list(set(liked_ids + (disliked_ids or [])))
    results = query_similar(blended, top_k=top_k + len(exclude) + 10)
    results = _filter_results(results, exclude)

    # Penalize results close to disliked shows
    if disliked_ids:
        results = _penalize_disliked(results, disliked_ids)

    return _trim_results(results, top_k)


def _penalize_disliked(results: dict, disliked_ids: list[str]) -> dict:
    """Re-rank results by penalizing similarity to disliked shows."""
    import numpy as np

    if not results.get("ids") or not results["ids"][0]:
        return results

    # Get embeddings for disliked shows
    disliked_embeddings = []
    for show_id in disliked_ids:
        show = get_show(show_id)
        if show and show.features:
            features_dict = show.features.model_dump(exclude={"show_title", "season", "episode"})
            text = features_to_text(features_dict)
            disliked_embeddings.append(embed_text(text))

    if not disliked_embeddings:
        return results

    # For each result, compute max similarity to any disliked show
    # and apply a penalty
    collection = get_collection()
    result_ids = results["ids"][0]
    stored = collection.get(ids=result_ids, include=["embeddings"])

    if not stored.get("embeddings"):
        return results

    result_embs = np.array(stored["embeddings"])
    disliked_embs = np.array(disliked_embeddings)

    # Cosine similarity matrix (result x disliked)
    norms_r = np.linalg.norm(result_embs, axis=1, keepdims=True)
    norms_d = np.linalg.norm(disliked_embs, axis=1, keepdims=True)
    sim_matrix = (result_embs / norms_r) @ (disliked_embs / norms_d).T
    max_disliked_sim = sim_matrix.max(axis=1)  # worst-case similarity per result

    # Adjust distances: increase distance for results similar to disliked
    penalty_weight = 0.3
    distances = list(results["distances"][0])
    for i in range(len(distances)):
        distances[i] += penalty_weight * max_disliked_sim[i]

    # Re-sort by adjusted distance
    indices = sorted(range(len(distances)), key=lambda i: distances[i])
    results["ids"][0] = [results["ids"][0][i] for i in indices]
    results["distances"][0] = [distances[i] for i in indices]
    if results.get("metadatas"):
        results["metadatas"][0] = [results["metadatas"][0][i] for i in indices]

    return results


def _filter_results(results: dict, exclude_ids: list[str]) -> dict:
    """Remove specific show IDs from results."""
    if not results.get("ids") or not results["ids"][0]:
        return results

    filtered = {"ids": [[]], "distances": [[]], "metadatas": [[]]}
    for i, show_id in enumerate(results["ids"][0]):
        if show_id not in exclude_ids:
            filtered["ids"][0].append(show_id)
            filtered["distances"][0].append(results["distances"][0][i])
            if results.get("metadatas"):
                filtered["metadatas"][0].append(results["metadatas"][0][i])

    return filtered


def _trim_results(results: dict, top_k: int) -> dict:
    """Trim results to top_k."""
    if not results.get("ids") or not results["ids"][0]:
        return results

    results["ids"][0] = results["ids"][0][:top_k]
    results["distances"][0] = results["distances"][0][:top_k]
    if results.get("metadatas"):
        results["metadatas"][0] = results["metadatas"][0][:top_k]
    return results
