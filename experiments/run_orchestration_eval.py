#!/usr/bin/env python3
"""
Orchestration evaluation — Supply-Fabric vs DA-Fabric.

Maps to paper Section IV-C.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from backend.service_layer import DAFabricService
from core.orchestrator import TaskOrchestrator
from core.semantic_matcher import SemanticMatcher
from core.view_builder import VirtualViewBuilder
from experiments._utils import (
    PROJECT_ROOT,
    RESULTS_DIR,
    load_demands_resources_mappings,
    load_ground_truth,
    print_table,
    setup_paths,
)

setup_paths()

METHODS = ["Supply-Fabric", "DA-Fabric"]


def main() -> None:
    print("Running orchestration evaluation...")
    service = DAFabricService(PROJECT_ROOT)
    service.initialize()

    demands, resources, mappings = load_demands_resources_mappings()
    _, relevant_sets = load_ground_truth()

    matcher = SemanticMatcher(auto_load=False)
    matcher.load()
    builder = VirtualViewBuilder(service.registry)
    orchestrator = TaskOrchestrator(service.registry)

    rows: list[dict] = []
    for method in METHODS:
        for demand in demands:
            if method == "Supply-Fabric":
                matches = matcher.supply_fabric_baseline(demand, resources, top_k=20)
            else:
                matches = matcher.da_fabric_match(demand, resources, top_k=15)

            view = builder.build_view_for_method(method, demand, matches, resources, mappings)
            gt_resources = relevant_sets.get(demand.demand_id, set())
            result = orchestrator.execute_view(view, ground_truth=gt_resources)

            summary = result.result_summary
            rows.append(
                {
                    "method": method,
                    "demand_id": demand.demand_id,
                    "view_id": view.view_id,
                    "selected_resources": len(view.selected_resources),
                    "invoked_nodes": summary.get("invoked_node_count", len(result.invoked_nodes)),
                    "invoked_resources": summary.get(
                        "invoked_resource_count", len(result.invoked_resources)
                    ),
                    "redundant_invocation_ratio": summary.get("redundant_invocation_ratio"),
                    "end_to_end_latency_ms": result.latency_ms,
                }
            )

    df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "orchestration_results.csv"
    df.to_csv(out_path, index=False)

    summary = df.groupby("method").agg(
        avg_selected_resources=("selected_resources", "mean"),
        avg_invoked_nodes=("invoked_nodes", "mean"),
        avg_invoked_resources=("invoked_resources", "mean"),
        avg_redundant_ratio=("redundant_invocation_ratio", "mean"),
        avg_latency_ms=("end_to_end_latency_ms", "mean"),
    ).reset_index().round(4)

    summary_path = RESULTS_DIR / "orchestration_results_summary.csv"
    summary.to_csv(summary_path, index=False)

    print_table(summary, "Orchestration Evaluation Summary")
    print(f"\nSaved to {out_path}")
    print(f"Saved summary to {summary_path}")


if __name__ == "__main__":
    main()
