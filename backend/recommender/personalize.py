"""Personalized recommendations: taste vectors from feedback + collaborative signal.

Blends two signals for a user:
1. Semantic: a "taste vector" built from the embeddings of shows the user liked
   (pushed away from disliked shows), optionally blended with a free-text query.
2. Collaborative: item-item co-preference — shows liked by users whose liked
   sets overlap with this user's rank higher.

final_score = semantic_weight * semantic_sim + cf_weight * cf_score,
with an additional penalty for candidates embedding-close to disliked shows.
"""

import logging

import numpy as np

from backend.db import user_store
from backend.db.show_store import get_show
from backend.db.vector_store import get_collection, query_similar
from backend.pipeline.embed import embed_text, features_to_text

logger = logging.getLogger(__name__)

SEMANTIC_WEIGHT = 0.7
CF_WEIGHT = 0.3
QUERY_WEIGHT = 1.5  # user's explicit query counts more than each liked show
DISLIKE_PUSH = 0.3  # how far the taste vector is pushed away from dislikes
DISLIKE_PENALTY = 0.3  # score penalty scale for candidates similar to dislikes


def get_show_embedding(show_id: str) -> list[float] | None:
    """Get a show's embedding: stored vector if indexed, else re-embed its features."""
    collection = get_collection()
    stored = collection.get(ids=[show_id], include=["embeddings"])
    embeddings = stored.get("embeddings")
    if embeddings is not None and len(embeddings) > 0:
        emb = embeddings[0]
        return list(emb) if not isinstance(emb, list) else emb

    show = get_show(show_id)
    if show and show.features:
        features_dict = show.features.model_dump(exclude={"show_title", "season", "episode"})
        return embed_text(features_to_text(features_dict))
    if show:
        return embed_text(f"TV show: {show.title}")
    return None


def build_taste_vector(user_id: str) -> list[float] | None:
    """Build a normalized taste embedding from the user's liked/disliked shows.

    Mean of liked embeddings, pushed away from the mean of disliked embeddings.
    Returns None if the user has no usable liked shows.
    """
    liked = user_store.get_liked_ids(user_id)
    disliked = user_store.get_disliked_ids(user_id)

    liked_embs = [e for e in (get_show_embedding(s) for s in liked) if e is not None]
    if not liked_embs:
        return None

    taste = np.array(liked_embs).mean(axis=0)

    disliked_embs = [e for e in (get_show_embedding(s) for s in disliked) if e is not None]
    if disliked_embs:
        taste = taste - DISLIKE_PUSH * np.array(disliked_embs).mean(axis=0)

    norm = np.linalg.norm(taste)
    if norm == 0:
        return None
    return (taste / norm).tolist()


def collaborative_scores(user_id: str, candidate_ids: list[str]) -> dict[str, float]:
    """Item-item collaborative score for each candidate, normalized to [0, 1].

    For candidate c: sum over other users v who liked c of
    |likes(v) ∩ likes(u)| / sqrt(|likes(v)| * |likes(u)|)  (cosine on like-sets).
    """
    all_likes = user_store.get_all_likes()
    my_likes = all_likes.pop(user_id, set())
    if not my_likes or not all_likes:
        return {c: 0.0 for c in candidate_ids}

    scores: dict[str, float] = {c: 0.0 for c in candidate_ids}
    for other_likes in all_likes.values():
        overlap = len(my_likes & other_likes)
        if overlap == 0:
            continue
        affinity = overlap / np.sqrt(len(my_likes) * len(other_likes))
        for c in candidate_ids:
            if c in other_likes:
                scores[c] += affinity

    max_score = max(scores.values())
    if max_score > 0:
        scores = {c: s / max_score for c, s in scores.items()}
    return scores


def recommend_personalized(
    user_id: str,
    query: str = "",
    top_k: int = 10,
    semantic_weight: float = SEMANTIC_WEIGHT,
    cf_weight: float = CF_WEIGHT,
) -> dict:
    """Personalized recommendations for a user, in ChromaDB-style result format.

    Returned distances encode the blended score (distance = 1 - final_score) so
    downstream formatting can derive similarity_score uniformly.
    """
    taste = build_taste_vector(user_id)

    # Blend taste vector with an optional explicit query
    vectors = []
    weights = []
    if taste is not None:
        vectors.append(taste)
        weights.append(1.0)
    if query:
        vectors.append(embed_text(query))
        weights.append(QUERY_WEIGHT)
    if not vectors:
        return {"ids": [[]], "distances": [[]], "metadatas": [[]]}

    arr = np.array(vectors)
    w = np.array(weights).reshape(-1, 1)
    blended = (arr * w).sum(axis=0) / w.sum()
    blended = (blended / np.linalg.norm(blended)).tolist()

    # Retrieve extra candidates: rated shows get filtered out below
    rated = set(user_store.get_liked_ids(user_id)) | set(user_store.get_disliked_ids(user_id))
    raw = query_similar(blended, top_k=top_k + len(rated) + 20)
    if not raw.get("ids") or not raw["ids"][0]:
        return {"ids": [[]], "distances": [[]], "metadatas": [[]]}

    candidates = []
    for i, show_id in enumerate(raw["ids"][0]):
        if show_id in rated:
            continue
        metadata = raw["metadatas"][0][i] if raw.get("metadatas") else {}
        semantic_sim = max(0.0, 1 - raw["distances"][0][i])
        candidates.append({"id": show_id, "semantic": semantic_sim, "metadata": metadata})

    candidate_ids = [c["id"] for c in candidates]
    cf = collaborative_scores(user_id, candidate_ids)
    dislike_sim = _dislike_similarity(user_id, candidate_ids)

    for c in candidates:
        c["score"] = (
            semantic_weight * c["semantic"]
            + cf_weight * cf.get(c["id"], 0.0)
            - DISLIKE_PENALTY * dislike_sim.get(c["id"], 0.0)
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    candidates = candidates[:top_k]

    return {
        "ids": [[c["id"] for c in candidates]],
        "distances": [[round(1 - max(0.0, min(1.0, c["score"])), 6) for c in candidates]],
        "metadatas": [[c["metadata"] for c in candidates]],
    }


def _dislike_similarity(user_id: str, candidate_ids: list[str]) -> dict[str, float]:
    """Max cosine similarity of each candidate to any of the user's disliked shows."""
    disliked = user_store.get_disliked_ids(user_id)
    if not disliked or not candidate_ids:
        return {}

    disliked_embs = [e for e in (get_show_embedding(s) for s in disliked) if e is not None]
    if not disliked_embs:
        return {}

    collection = get_collection()
    stored = collection.get(ids=candidate_ids, include=["embeddings"])
    stored_embs = stored.get("embeddings")
    if stored_embs is None or len(stored_embs) == 0:
        return {}

    cand_arr = np.array(stored_embs)
    dis_arr = np.array(disliked_embs)
    cand_norm = cand_arr / np.linalg.norm(cand_arr, axis=1, keepdims=True)
    dis_norm = dis_arr / np.linalg.norm(dis_arr, axis=1, keepdims=True)
    sim = (cand_norm @ dis_norm.T).max(axis=1)

    # collection.get does not guarantee input order — map by returned ids
    returned_ids = stored.get("ids", candidate_ids)
    return {show_id: max(0.0, float(s)) for show_id, s in zip(returned_ids, sim)}
