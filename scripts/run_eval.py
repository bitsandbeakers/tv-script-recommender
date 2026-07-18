#!/usr/bin/env python
"""Run the recommendation quality evaluation and print a report.

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --ground-truth path/to/gt.json --k 5 10 20 --json report.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.eval.harness import DEFAULT_GROUND_TRUTH, run_full_eval  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _fmt_metrics(metrics: dict) -> str:
    return "  ".join(f"{k}={v:.3f}" for k, v in metrics.items())


def _print_section(title: str, section: dict) -> None:
    print(f"\n=== {title} ===")
    if not section["cases"]:
        print("  (no cases could run — is the catalog populated?)")
    for case in section["cases"]:
        label = case.get("query_show") or case.get("case")
        print(f"  {label:<28} {_fmt_metrics(case['metrics'])}")
    if section["skipped"]:
        print(f"  Skipped {len(section['skipped'])} case(s):")
        for s in section["skipped"]:
            label = s.get("group") or s.get("case")
            print(f"    - {label}: {s['reason']}")
    if section["aggregate"]:
        print(f"  {'MEAN':<28} {_fmt_metrics(section['aggregate'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate recommendation quality against ground truth")
    parser.add_argument("--ground-truth", default=str(DEFAULT_GROUND_TRUTH), help="Path to ground truth JSON")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10], help="k values for ranking metrics")
    parser.add_argument("--json", dest="json_out", default="", help="Also write the full report to this JSON file")
    args = parser.parse_args()

    report = run_full_eval(ground_truth_path=args.ground_truth, k_values=args.k)

    print(f"Catalog size: {report['catalog_size']} shows")
    _print_section("Similar-show retrieval", report["similar_shows"])
    _print_section("Text-query retrieval", report["text_queries"])

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull report written to {args.json_out}")

    ran_any = bool(report["similar_shows"]["cases"] or report["text_queries"]["cases"])
    if not ran_any:
        print("\nNo evaluation cases could run. Ingest shows from the ground-truth set first.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
