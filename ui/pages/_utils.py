"""Shared UI utilities for DA-Fabric Streamlit pages."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"

PAPER_TITLE = (
    "From Passive Querying to Proactive Data Services: "
    "A Demand-Aware Data Fabric Framework for Multi-Platform Data Environments"
)


@st.cache_resource
def get_service():
    from backend.service_layer import DAFabricService

    svc = DAFabricService(PROJECT_ROOT)
    svc.initialize()
    svc.proactive.load_subscriptions()
    svc.proactive.load_resources()
    return svc


def load_json(name: str) -> list:
    path = DATA_DIR / name
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []


def load_semantic_mappings():
    from core.models import SemanticMapping, load_json as core_load_json

    path = DATA_DIR / "semantic_mappings.json"
    if not path.exists():
        return []
    return core_load_json(path, SemanticMapping, many=True)


def load_results_csv(name: str) -> pd.DataFrame | None:
    path = RESULTS_DIR / name
    if path.exists():
        return pd.read_csv(path)
    return None


def summarize_results_csv(detail_name: str, group_col: str = "method") -> pd.DataFrame | None:
    """Aggregate per-demand/per-run CSV into summary table."""
    df = load_results_csv(detail_name)
    if df is None or df.empty:
        return None
    numeric = df.select_dtypes(include="number").columns.tolist()
    if not numeric:
        return df
    return df.groupby(group_col)[numeric].mean().reset_index().round(4)


def run_experiment_script(script: str) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / script)],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def demand_to_row(demand) -> dict:
    return {
        "demand_id": demand.demand_id,
        "role": demand.role,
        "application": demand.application,
        "task": demand.task,
        "object_type": demand.object_type,
        "object_id": demand.object_id,
        "indicators": ", ".join(demand.indicators),
        "output_format": demand.output_format,
        "priority": demand.priority.value if hasattr(demand.priority, "value") else demand.priority,
        "submitted_at": str(demand.submitted_at),
    }


def resource_to_row(resource) -> dict:
    return {
        "resource_id": resource.resource_id,
        "name": resource.name,
        "node_type": resource.node_type,
        "business_domain": resource.business_domain,
        "entity_type": resource.entity_type,
        "node_id": resource.node_id,
        "quality_score": resource.quality_score,
        "fields": ", ".join(resource.fields[:5]) + ("..." if len(resource.fields) > 5 else ""),
    }


def proactive_event_to_row(event) -> dict:
    return {
        "event_id": event.event_id,
        "demand_id": event.demand_id,
        "trigger_type": event.trigger_type,
        "target_application": event.target_application,
        "relevance_score": event.relevance_score,
        "user_action": event.user_action or "pending",
        "delivery_latency_ms": event.delivery_latency_ms,
    }


def record_proactive_feedback(service, event_id: str, action: str) -> bool:
    """Update proactive event user_action and record feedback."""
    from core.models import FeedbackAction, FeedbackEvent

    updated = False
    for idx, event in enumerate(service.proactive.history):
        if event.event_id != event_id:
            continue
        service.proactive._delivery_history[idx] = event.model_copy(
            update={"user_action": action}
        )
        updated = True
        demand = service.demands.get(event.demand_id)
        feedback = FeedbackEvent(
            demand_id=event.demand_id,
            view_id=event.delivered_view_id,
            user_id=demand.user_id if demand else "",
            action=FeedbackAction(action),
            relevance_score=event.relevance_score,
        )
        service.record_feedback(feedback)
        service.proactive.save_events()
        break
    return updated
