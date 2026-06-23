#!/usr/bin/env python3
"""Shared utilities for experiment scripts."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

RELEVANCE_THRESHOLD = 0.6
TOP_K = 5


def setup_paths() -> Path:
    sys.path.insert(0, str(PROJECT_ROOT))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECT_ROOT


def load_ground_truth() -> tuple[dict[str, dict[str, float]], dict[str, set[str]]]:
    """Return relevance maps and relevant-id sets per demand."""
    path = DATA_DIR / "ground_truth.json"
    with open(path, encoding="utf-8") as f:
        ground_truth = json.load(f)

    rel_map: dict[str, dict[str, float]] = {}
    relevant: dict[str, set[str]] = {}
    for entry in ground_truth:
        did = entry["demand_id"]
        rid = entry["resource_id"]
        rel_map.setdefault(did, {})[rid] = float(entry["relevance"])
        if float(entry["relevance"]) >= RELEVANCE_THRESHOLD:
            relevant.setdefault(did, set()).add(rid)
    return rel_map, relevant


def precision_at_k(predicted: list[str], relevant: set[str], k: int = TOP_K) -> float:
    top_k = predicted[:k]
    if not top_k:
        return 0.0
    return len(set(top_k) & relevant) / k


def recall_at_k(predicted: list[str], relevant: set[str], k: int = TOP_K) -> float:
    if not relevant:
        return 0.0
    top_k = predicted[:k]
    return len(set(top_k) & relevant) / len(relevant)


def ndcg_at_k(predicted: list[str], relevance_map: dict[str, float], k: int = TOP_K) -> float:
    dcg = 0.0
    for i, rid in enumerate(predicted[:k]):
        rel = relevance_map.get(rid, 0.0)
        dcg += rel / np.log2(i + 2)
    ideal = sorted(relevance_map.values(), reverse=True)[:k]
    idcg = sum(r / np.log2(i + 2) for i, r in enumerate(ideal))
    return float(dcg / idcg) if idcg > 0 else 0.0


def mrr(predicted: list[str], relevant: set[str]) -> float:
    for i, rid in enumerate(predicted):
        if rid in relevant:
            return 1.0 / (i + 1)
    return 0.0


def compute_ranking_metrics(
    predicted: list[str],
    rel_map: dict[str, float],
    relevant: set[str],
    k: int = TOP_K,
) -> dict[str, float]:
    return {
        "precision_at_5": round(precision_at_k(predicted, relevant, k), 4),
        "recall_at_5": round(recall_at_k(predicted, relevant, k), 4),
        "ndcg_at_5": round(ndcg_at_k(predicted, rel_map, k), 4),
        "mrr": round(mrr(predicted, relevant), 4),
    }


def aggregate_metrics(rows: list[dict], group_col: str = "method") -> pd.DataFrame:
    df = pd.DataFrame(rows)
    metric_cols = [c for c in df.columns if c not in (group_col, "demand_id")]
    numeric = [c for c in metric_cols if pd.api.types.is_numeric_dtype(df[c])]
    summary = df.groupby(group_col)[numeric].mean().reset_index()
    return summary.round(4)


def print_table(df: pd.DataFrame, title: str = "") -> None:
    if title:
        print(f"\n{title}")
        print("=" * len(title))
    print(df.to_string(index=False))


def load_service():
    from backend.service_layer import DAFabricService

    service = DAFabricService(PROJECT_ROOT)
    service.initialize()
    return service


def load_demands_resources_mappings():
    from core.models import DemandMetadata, ResourceMetadata, SemanticMapping, load_json

    demands = load_json(DATA_DIR / "demands.json", DemandMetadata, many=True)
    resources = load_json(DATA_DIR / "resources.json", ResourceMetadata, many=True)
    mappings = load_json(DATA_DIR / "semantic_mappings.json", SemanticMapping, many=True)
    return demands, resources, mappings


def scale_resources(resources, target_count: int):
    """Expand or truncate resource list to target_count for scaling experiments."""
    from core.models import ResourceMetadata

    if target_count <= len(resources):
        return resources[:target_count]

    scaled: list[ResourceMetadata] = list(resources)
    idx = 0
    while len(scaled) < target_count:
        base = resources[idx % len(resources)]
        copy = base.model_copy(
            update={
                "resource_id": f"{base.resource_id}-s{len(scaled):05d}",
                "name": f"{base.name} (scale copy {len(scaled)})",
            }
        )
        scaled.append(copy)
        idx += 1
    return scaled[:target_count]


def timed(fn, *args, **kwargs) -> tuple[float, object]:
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return elapsed_ms, result
