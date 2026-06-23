#!/usr/bin/env python3
"""
Matching evaluation — compare KW-Catalog, Semantic-Only, Supply-Fabric,
DA-Fabric, and DA-Fabric+Feedback.

Maps to paper Section IV-A.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from core.feedback_optimizer import FeedbackOptimizer
from core.semantic_matcher import SemanticMatcher
from experiments._utils import (
    RESULTS_DIR,
    TOP_K,
    compute_ranking_metrics,
    load_demands_resources_mappings,
    load_ground_truth,
    print_table,
    setup_paths,
)

setup_paths()

METHODS = [
    "KW-Catalog",
    "Semantic-Only",
    "Supply-Fabric",
    "DA-Fabric",
    "DA-Fabric+Feedback",
]


def match_for_method(
    method: str,
    matcher: SemanticMatcher,
    feedback: FeedbackOptimizer,
    demand,
    resources,
):
    if method == "KW-Catalog":
        return matcher.keyword_baseline(demand, resources, top_k=TOP_K)
    if method == "Semantic-Only":
        return matcher.semantic_only_baseline(demand, resources, top_k=TOP_K)
    if method == "Supply-Fabric":
        return matcher.supply_fabric_baseline(demand, resources, top_k=TOP_K)
    matches = matcher.da_fabric_match(demand, resources, top_k=TOP_K)
    if method == "DA-Fabric+Feedback":
        boosted = feedback.apply_feedback_boost(matches)
        return boosted[:TOP_K]
    return matches


def main() -> None:
    print("Running matching evaluation...")
    demands, resources, _ = load_demands_resources_mappings()
    rel_maps, relevant_sets = load_ground_truth()

    matcher = SemanticMatcher(auto_load=False)
    matcher.load()
    feedback = FeedbackOptimizer(matcher=matcher)
    feedback.load_from_file()

    rows: list[dict] = []
    for method in METHODS:
        for demand in demands:
            matches = match_for_method(method, matcher, feedback, demand, resources)
            predicted = [m.resource_id for m in matches]
            rel_map = rel_maps.get(demand.demand_id, {})
            relevant = relevant_sets.get(demand.demand_id, set())
            metrics = compute_ranking_metrics(predicted, rel_map, relevant, k=TOP_K)
            rows.append({"method": method, "demand_id": demand.demand_id, **metrics})

    df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "matching_results.csv"
    df.to_csv(out_path, index=False)

    summary = df.groupby("method")[
        ["precision_at_5", "recall_at_5", "ndcg_at_5", "mrr"]
    ].mean().reset_index().round(4)
    summary = summary.set_index("method").loc[METHODS].reset_index()

    summary_path = RESULTS_DIR / "matching_results_summary.csv"
    summary.to_csv(summary_path, index=False)

    print_table(summary, "Matching Evaluation Summary (mean @5)")
    print(f"\nSaved to {out_path}")
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()
