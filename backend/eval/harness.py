"""Evaluation harness: runs the recommender against curated ground truth.

Two evaluation modes:
- Similar-show retrieval: for each show in a ground-truth group, recommend
  similar shows and check the rest of the group ranks highly.
- Text-query retrieval: run natural-language style queries and check the
  expected shows rank highly.

Cases referencing shows missing from the catalog are skipped (and reported),
so the harness can run meaningfully against a partial catalog.
"""

import json
import logging
from pathlib import Path

from backend.db import show_store
from backend.eval.metrics import aggregate, evaluate_ranking

logger = logging.getLogger(__name__)

DEFAULT_GROUND_TRUTH = Path(__file__).parent / "data" / "ground_truth.json"
DEFAULT_K_VALUES = [5, 10]


def load_ground_truth(path: str | Path = DEFAULT_GROUND_TRUTH) -> dict:
    with open(path) as f:
        return json.load(f)


def _result_ids(raw_results: dict) -> list[str]:
    if not raw_results.get("ids") or not raw_results["ids"][0]:
        return []
    return list(raw_results["ids"][0])


def evaluate_similar_shows(
    ground_truth: dict,
    k_values: list[int] | None = None,
    recommend_fn=None,
) -> dict:
    """Evaluate similar-show retrieval over ground-truth groups.

    For each show in each group that exists in the catalog, the other group
    members (also in the catalog) are the relevant set.
    `recommend_fn(show_id, top_k)` defaults to the engine's recommend_by_show.
    """
    if recommend_fn is None:
        from backend.recommender.engine import recommend_by_show

        def recommend_fn(show_id, top_k):
            return recommend_by_show(show_id, top_k=top_k)

    k_values = k_values or DEFAULT_K_VALUES
    max_k = max(k_values)
    catalog_ids = {s.id for s in show_store.list_shows()}

    cases = []
    skipped = []
    for group in ground_truth.get("similar_groups", []):
        present = [s for s in group["shows"] if s in catalog_ids]
        missing = [s for s in group["shows"] if s not in catalog_ids]
        if len(present) < 2:
            skipped.append({"group": group["name"], "reason": f"needs >=2 shows in catalog, missing: {missing}"})
            continue

        for query_show in present:
            relevant = set(present) - {query_show}
            ranked = _result_ids(recommend_fn(query_show, max_k))
            case_metrics = evaluate_ranking(ranked, relevant, k_values)
            cases.append({
                "group": group["name"],
                "query_show": query_show,
                "relevant": sorted(relevant),
                "missing_from_catalog": missing,
                "metrics": case_metrics,
            })

    return {
        "cases": cases,
        "skipped": skipped,
        "aggregate": aggregate([c["metrics"] for c in cases]),
    }


def evaluate_text_queries(
    ground_truth: dict,
    k_values: list[int] | None = None,
    recommend_fn=None,
) -> dict:
    """Evaluate natural-language query retrieval.

    `recommend_fn(query, top_k)` defaults to the engine's recommend_by_text.
    """
    if recommend_fn is None:
        from backend.recommender.engine import recommend_by_text

        def recommend_fn(query, top_k):
            return recommend_by_text(query, top_k=top_k)

    k_values = k_values or DEFAULT_K_VALUES
    max_k = max(k_values)
    catalog_ids = {s.id for s in show_store.list_shows()}

    cases = []
    skipped = []
    for case in ground_truth.get("query_cases", []):
        relevant = {s for s in case["expected"] if s in catalog_ids}
        missing = [s for s in case["expected"] if s not in catalog_ids]
        if not relevant:
            skipped.append({"case": case["name"], "reason": f"no expected shows in catalog: {missing}"})
            continue

        ranked = _result_ids(recommend_fn(case["query"], max_k))
        case_metrics = evaluate_ranking(ranked, relevant, k_values)
        cases.append({
            "case": case["name"],
            "query": case["query"],
            "relevant": sorted(relevant),
            "missing_from_catalog": missing,
            "metrics": case_metrics,
        })

    return {
        "cases": cases,
        "skipped": skipped,
        "aggregate": aggregate([c["metrics"] for c in cases]),
    }


def run_full_eval(
    ground_truth_path: str | Path = DEFAULT_GROUND_TRUTH,
    k_values: list[int] | None = None,
) -> dict:
    """Run both evaluation modes and return a combined report."""
    ground_truth = load_ground_truth(ground_truth_path)
    k_values = k_values or DEFAULT_K_VALUES

    return {
        "catalog_size": show_store.get_show_count(),
        "k_values": k_values,
        "similar_shows": evaluate_similar_shows(ground_truth, k_values),
        "text_queries": evaluate_text_queries(ground_truth, k_values),
    }
