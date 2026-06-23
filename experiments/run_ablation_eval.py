#!/usr/bin/env python3
"""
Ablation study — component removal analysis for DA-Fabric.

Maps to paper Section IV-E.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.service_layer import DAFabricService
from core.feedback_optimizer import FeedbackOptimizer
from core.orchestrator import TaskOrchestrator
from core.semantic_matcher import SemanticMatcher
from core.view_builder import VirtualViewBuilder
from experiments._utils import (
    PROJECT_ROOT,
    RESULTS_DIR,
    TOP_K,
    compute_ranking_metrics,
    load_demands_resources_mappings,
    load_ground_truth,
    print_table,
    setup_paths,
)

setup_paths()

CONFIGS = [
    "Full DA-Fabric",
    "w/o semantic mapping",
    "w/o context",
    "w/o feedback",
    "w/o application-side nodes",
]


def strip_application_metadata(demand):
    return demand.model_copy(
        update={
            "role": "",
            "application": "",
            "task": "",
            "subscription": {},
            "feedback": {},
        }
    )


def match_for_config(
    config: str,
    matcher: SemanticMatcher,
    feedback: FeedbackOptimizer,
    demand,
    resources,
):
    eval_demand = strip_application_metadata(demand) if config == "w/o application-side nodes" else demand

    if config == "w/o semantic mapping":
        matches = matcher.da_fabric_match(
            eval_demand, resources, top_k=TOP_K, use_mapping=False
        )
    elif config == "w/o context":
        matches = matcher.da_fabric_match(
            eval_demand, resources, top_k=TOP_K, use_context=False
        )
    elif config == "w/o application-side nodes":
        matches = matcher.da_fabric_match(
            eval_demand,
            resources,
            top_k=TOP_K,
            include_application_context=False,
        )
    else:
        matches = matcher.da_fabric_match(eval_demand, resources, top_k=TOP_K)

    if config == "Full DA-Fabric":
        return feedback.apply_feedback_boost(matches)
    return matches


def build_view_for_config(config, demand, matches, resources, mappings, builder):
    map_payload = [] if config == "w/o semantic mapping" else mappings
    eval_demand = strip_application_metadata(demand) if config == "w/o application-side nodes" else demand
    return builder.build_view(
        eval_demand,
        matches,
        resources,
        map_payload,
        profile="da_fabric",
    )


def main() -> None:
    print("Running ablation evaluation...")
    service = DAFabricService(PROJECT_ROOT)
    service.initialize()

    demands, resources, mappings = load_demands_resources_mappings()
    rel_maps, relevant_sets = load_ground_truth()

    matcher = SemanticMatcher(auto_load=False)
    matcher.load()
    feedback = FeedbackOptimizer(matcher=matcher)
    feedback.load_from_file()
    builder = VirtualViewBuilder(service.registry)
    orchestrator = TaskOrchestrator(service.registry)

    rows: list[dict] = []
    for config in CONFIGS:
        precisions: list[float] = []
        ndcgs: list[float] = []
        invoked_nodes: list[float] = []
        delivery_precisions: list[float] = []

        for demand in demands:
            matches = match_for_config(config, matcher, feedback, demand, resources)
            predicted = [m.resource_id for m in matches]
            rel_map = rel_maps.get(demand.demand_id, {})
            relevant = relevant_sets.get(demand.demand_id, set())
            metrics = compute_ranking_metrics(predicted, rel_map, relevant, k=TOP_K)
            precisions.append(metrics["precision_at_5"])
            ndcgs.append(metrics["ndcg_at_5"])

            view = build_view_for_config(config, demand, matches, resources, mappings, builder)
            result = orchestrator.execute_view(view, ground_truth=relevant)
            invoked_nodes.append(float(result.result_summary.get("invoked_node_count", 0)))
            if result.invoked_resources and relevant:
                hits = len(set(result.invoked_resources) & relevant)
                delivery_precisions.append(hits / len(set(result.invoked_resources)))
            else:
                delivery_precisions.append(0.0)

        rows.append(
            {
                "config": config,
                "precision_at_5": round(sum(precisions) / len(precisions), 4),
                "ndcg_at_5": round(sum(ndcgs) / len(ndcgs), 4),
                "invoked_nodes": round(sum(invoked_nodes) / len(invoked_nodes), 4),
                "delivery_precision": round(sum(delivery_precisions) / len(delivery_precisions), 4),
            }
        )

    df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "ablation_results.csv"
    df.to_csv(out_path, index=False)
    summary_path = RESULTS_DIR / "ablation_results_summary.csv"
    df.to_csv(summary_path, index=False)

    print_table(df, "Ablation Study Summary")
    print(f"\nSaved to {out_path}")
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()
