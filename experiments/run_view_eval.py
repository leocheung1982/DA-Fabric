#!/usr/bin/env python3
"""
Virtual view construction evaluation at multiple resource scales.

Maps to paper Section IV-B.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from core.semantic_matcher import SemanticMatcher
from core.view_builder import VirtualViewBuilder
from experiments._utils import (
    RESULTS_DIR,
    load_demands_resources_mappings,
    print_table,
    scale_resources,
    setup_paths,
    timed,
)

setup_paths()

SCALES = [100, 300, 500, 1000, 3000, 5000]
SAMPLE_DEMANDS = 20  # keep large-scale runs tractable


def main() -> None:
    print("Running view construction evaluation...")
    demands, base_resources, mappings = load_demands_resources_mappings()
    eval_demands = demands[:SAMPLE_DEMANDS]

    matcher = SemanticMatcher(auto_load=False)
    builder = VirtualViewBuilder()
    rows: list[dict] = []

    for scale in SCALES:
        resources = scale_resources(base_resources, scale)
        match_times: list[float] = []
        view_times: list[float] = []
        selected_counts: list[int] = []

        for demand in eval_demands:
            match_ms, matches = timed(matcher.match, demand, resources, top_k=10)
            view_ms, view = timed(
                builder.build_view, demand, matches, resources, mappings
            )
            match_times.append(match_ms)
            view_times.append(view_ms)
            selected_counts.append(len(view.selected_resources))

        rows.append(
            {
                "resource_scale": scale,
                "num_demands_evaluated": len(eval_demands),
                "avg_matching_time_ms": round(sum(match_times) / len(match_times), 2),
                "avg_view_construction_time_ms": round(sum(view_times) / len(view_times), 2),
                "avg_selected_resource_count": round(sum(selected_counts) / len(selected_counts), 2),
            }
        )
        print(f"  scale={scale}: match={rows[-1]['avg_matching_time_ms']:.1f}ms view={rows[-1]['avg_view_construction_time_ms']:.1f}ms")

    df = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "view_results.csv"
    df.to_csv(out_path, index=False)

    print_table(df, "View Construction Evaluation Summary")
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
