"""Ranking metrics for recommendation quality evaluation.

All functions take `ranked` (recommended IDs, best first) and `relevant`
(the ground-truth set) and return a float in [0, 1].
"""

import math


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k recommendations that are relevant."""
    if k <= 0:
        return 0.0
    top = ranked[:k]
    if not top:
        return 0.0
    hits = sum(1 for r in top if r in relevant)
    return hits / k


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant items that appear in the top-k recommendations."""
    if not relevant:
        return 0.0
    hits = sum(1 for r in ranked[:k] if r in relevant)
    return hits / len(relevant)


def hit_rate_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """1.0 if any relevant item appears in the top-k, else 0.0."""
    return 1.0 if any(r in relevant for r in ranked[:k]) else 0.0


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    """1 / rank of the first relevant item (0 if none appear)."""
    for i, r in enumerate(ranked, start=1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    """Normalized discounted cumulative gain with binary relevance."""
    if not relevant or k <= 0:
        return 0.0
    dcg = sum(
        1.0 / math.log2(i + 1)
        for i, r in enumerate(ranked[:k], start=1)
        if r in relevant
    )
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_ranking(ranked: list[str], relevant: set[str], k_values: list[int]) -> dict:
    """Compute the full metric suite for one ranked list."""
    result = {"mrr": reciprocal_rank(ranked, relevant)}
    for k in k_values:
        result[f"precision@{k}"] = precision_at_k(ranked, relevant, k)
        result[f"recall@{k}"] = recall_at_k(ranked, relevant, k)
        result[f"hit_rate@{k}"] = hit_rate_at_k(ranked, relevant, k)
        result[f"ndcg@{k}"] = ndcg_at_k(ranked, relevant, k)
    return result


def aggregate(per_case: list[dict]) -> dict:
    """Mean of each metric across cases."""
    if not per_case:
        return {}
    keys = per_case[0].keys()
    return {key: sum(c[key] for c in per_case) / len(per_case) for key in keys}
