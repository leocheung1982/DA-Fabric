"""
Pydantic data models for DA-Fabric.

Maps to paper architecture:
- FabricNode / NodeCapability: fabric node registration and capabilities
- ResourceMetadata: resource-layer synthetic metadata catalog
- DemandMetadata: application demand metadata
- SemanticMapping / MatchResult: semantic supply-demand matching
- VirtualView / TaskPlan / ExecutionResult: view construction and orchestration
- FeedbackEvent / ProactiveDeliveryEvent: optimization and proactive delivery loop
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Literal, TypeVar, Union
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class NodeType(str, Enum):
    """Fabric node role in the multi-platform data environment."""

    PLATFORM = "platform"
    SOURCE = "source"
    APPLICATION = "application"


class NodeStatus(str, Enum):
    """Operational status of a fabric node."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEGRADED = "degraded"


class MappingType(str, Enum):
    """Semantic relationship type between source and target terms."""

    EQUIVALENT = "equivalent"
    SIMILAR = "similar"
    HIERARCHICAL = "hierarchical"
    RELATED = "related"
    COMPOSITE = "composite"


class FeedbackAction(str, Enum):
    """User interaction action on a delivered view or match."""

    VIEWED = "viewed"
    CLICKED = "clicked"
    ADOPTED = "adopted"
    IGNORED = "ignored"
    EXPORTED = "exported"
    REJECTED = "rejected"


class DemandPriority(str, Enum):
    """Demand urgency level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Status of an orchestration sub-task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Supporting structures
# ---------------------------------------------------------------------------


class FieldMapping(BaseModel):
    """Maps a source resource field into a virtual view column."""

    source_resource_id: str = ""
    source_field: str = ""
    view_field: str = ""
    transform: str = "identity"


class PlanTask(BaseModel):
    """Single task within a cross-node orchestration plan."""

    task_id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:8]}")
    task_type: str = ""
    target_node_id: str = ""
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    estimated_duration_ms: float = 100.0
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] = Field(default_factory=dict)


class OptimizationSnapshot(BaseModel):
    """Snapshot of matcher weights after feedback optimization."""

    iteration: int
    matcher_method: str
    avg_rating: float
    avg_relevance: float
    weight_adjustments: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class FabricNode(BaseModel):
    """Registered fabric node in the control and orchestration plane."""

    node_id: str
    node_type: NodeType
    name: str
    organization: str = ""
    description: str = ""
    supported_tasks: list[str] = Field(default_factory=list)
    supported_services: list[str] = Field(default_factory=list)
    status: NodeStatus = NodeStatus.ACTIVE

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "organization" not in data and data.get("platform"):
            data["organization"] = data["platform"]
        if "supported_tasks" not in data and data.get("capabilities"):
            data["supported_tasks"] = [
                c.get("name", "") for c in data["capabilities"] if isinstance(c, dict)
            ]
        if "supported_services" not in data and data.get("capabilities"):
            data["supported_services"] = [
                t for c in data["capabilities"] if isinstance(c, dict) for t in c.get("tags", [])
            ]
        return data

    @property
    def platform(self) -> str:
        """Legacy alias used by platform routing logic."""
        return self.organization

    @property
    def capabilities(self) -> list[NodeCapability]:
        """Legacy capability list derived from supported tasks and services."""
        return [
            NodeCapability(
                node_id=self.node_id,
                executable_tasks=[task],
                service_types=self.supported_services,
            )
            for task in self.supported_tasks
        ]


class NodeCapability(BaseModel):
    """Capability profile advertised by a fabric node."""

    node_id: str
    metadata_types: list[str] = Field(default_factory=list)
    service_types: list[str] = Field(default_factory=list)
    executable_tasks: list[str] = Field(default_factory=list)
    return_formats: list[str] = Field(default_factory=list)
    update_modes: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "executable_tasks" not in data and data.get("name"):
            data.setdefault("executable_tasks", [data["name"]])
        if "service_types" not in data and data.get("tags"):
            data.setdefault("service_types", data["tags"])
        return data

    @property
    def name(self) -> str:
        """Legacy alias for the primary executable task."""
        return self.executable_tasks[0] if self.executable_tasks else ""


class ResourceMetadata(BaseModel):
    """Synthetic resource metadata entry in the catalog."""

    resource_id: str
    node_id: str = ""
    node_type: str = ""
    name: str
    description: str = ""
    business_domain: str = ""
    entity_type: str = ""
    resource_type: str = "dataset"
    fields: list[str] = Field(default_factory=list)
    indicators: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    update_frequency: str = "daily"
    service_type: str = "batch"
    quality_score: float = Field(default=0.8, ge=0.0, le=1.0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not data.get("node_id") and data.get("source_node_id"):
            data["node_id"] = data["source_node_id"]
        if not data.get("business_domain") and data.get("domain"):
            data["business_domain"] = data["domain"]
        if not data.get("fields") and data.get("schema_fields"):
            data["fields"] = data["schema_fields"]
        if not data.get("keywords") and data.get("tags"):
            data["keywords"] = data["tags"]
        if not data.get("node_type") and data.get("platform"):
            data["node_type"] = data["platform"]
        if not data.get("update_frequency") and data.get("freshness_hours") is not None:
            hours = float(data["freshness_hours"])
            data["update_frequency"] = "hourly" if hours <= 1 else "daily" if hours <= 24 else "weekly"
        return data

    @property
    def domain(self) -> str:
        return self.business_domain

    @property
    def schema_fields(self) -> list[str]:
        return self.fields

    @property
    def tags(self) -> list[str]:
        return self.keywords

    @property
    def source_node_id(self) -> str:
        return self.node_id

    @property
    def platform(self) -> str:
        return self.node_type


class DemandMetadata(BaseModel):
    """Demand metadata submitted by application-side consumers."""

    demand_id: str = Field(default_factory=lambda: f"dem-{uuid4().hex[:8]}")
    user_id: str = ""
    role: str = ""
    application: str = ""
    task: str = ""
    object_type: str = ""
    object_id: str = ""
    indicators: list[str] = Field(default_factory=list)
    conditions: dict[str, Any] = Field(default_factory=dict)
    time_range: dict[str, Any] = Field(default_factory=dict)
    output_format: str = "json"
    priority: DemandPriority = DemandPriority.MEDIUM
    subscription: dict[str, Any] = Field(default_factory=dict)
    feedback: dict[str, Any] = Field(default_factory=dict)
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not data.get("task") and data.get("title"):
            data["task"] = data["title"]
        if data.get("description"):
            data.setdefault("conditions", {})["description"] = data["description"]
        if not data.get("indicators") and data.get("required_fields"):
            data["indicators"] = data["required_fields"]
        if not data.get("object_type") and data.get("domain"):
            data["object_type"] = data["domain"]
        if not data.get("user_id") and data.get("application_node_id"):
            data["user_id"] = data["application_node_id"]
        if not data.get("application") and data.get("title"):
            data["application"] = data["title"]
        if data.get("tags") and not data.get("conditions"):
            data["conditions"] = {"tags": data["tags"]}
        elif data.get("tags"):
            data.setdefault("conditions", {})["tags"] = data["tags"]
        if data.get("constraints"):
            data.setdefault("conditions", {}).update(data["constraints"])
        return data

    @property
    def title(self) -> str:
        return self.task

    @property
    def description(self) -> str:
        return self.conditions.get("description", "")

    @property
    def required_fields(self) -> list[str]:
        return self.indicators

    @property
    def domain(self) -> str:
        return self.object_type

    @property
    def tags(self) -> list[str]:
        tags = self.conditions.get("tags", [])
        return tags if isinstance(tags, list) else []

    @property
    def application_node_id(self) -> str:
        return self.user_id


class SemanticMapping(BaseModel):
    """Auxiliary semantic mapping between vocabulary terms."""

    mapping_id: str = Field(default_factory=lambda: f"map-{uuid4().hex[:8]}")
    source_term: str
    target_term: str
    mapping_type: MappingType = MappingType.RELATED
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    description: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not data.get("mapping_id"):
            data["mapping_id"] = data.get("demand_id", f"map-{uuid4().hex[:8]}")
        if not data.get("source_term") and data.get("resource_id"):
            data["source_term"] = str(data["resource_id"])
        if not data.get("target_term") and data.get("label"):
            data["target_term"] = str(data["label"])
        if data.get("relevance") is not None and "confidence" not in data:
            data["confidence"] = float(data["relevance"])
        return data


class MatchResult(BaseModel):
    """Scored result of semantic supply-demand matching."""

    demand_id: str
    resource_id: str
    score: float = Field(ge=0.0, le=1.0)
    keyword_score: float = Field(default=0.0, ge=0.0, le=1.0)
    indicator_score: float = Field(default=0.0, ge=0.0, le=1.0)
    entity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    semantic_score: float = Field(default=0.0, ge=0.0, le=1.0)
    context_score: float = Field(default=0.0, ge=0.0, le=1.0)
    mapping_score: float = Field(default=0.0, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    rank: int = 0
    matcher_method: str = "tfidf"
    matched_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "score" not in data and data.get("similarity_score") is not None:
            data["score"] = data["similarity_score"]
        if not data.get("semantic_score") and data.get("similarity_score") is not None:
            data["semantic_score"] = data["similarity_score"]
        if not data.get("reason") and data.get("explanation"):
            data["reason"] = data["explanation"]
        if not data.get("indicator_score") and data.get("keyword_score") is not None:
            data["indicator_score"] = data["keyword_score"]
        return data

    @property
    def similarity_score(self) -> float:
        return self.score

    @property
    def explanation(self) -> str:
        return self.reason


class VirtualView(BaseModel):
    """Demand-driven virtual view federated across fabric nodes."""

    view_id: str = Field(default_factory=lambda: f"view-{uuid4().hex[:8]}")
    demand_id: str
    view_name: str = ""
    view_type: str = "federated"
    selected_resources: list[str] = Field(default_factory=list)
    field_mappings: list[FieldMapping] = Field(default_factory=list)
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    construction_time_ms: float = 0.0

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not data.get("view_name") and data.get("name"):
            data["view_name"] = data["name"]
        if not data.get("selected_resources") and data.get("source_resources"):
            data["selected_resources"] = data["source_resources"]
        if not data.get("field_mappings") and data.get("fields"):
            data["field_mappings"] = data["fields"]
        return data

    @property
    def name(self) -> str:
        return self.view_name

    @property
    def description(self) -> str:
        return self.execution_plan.get("description", "")

    @property
    def fields(self) -> list[FieldMapping]:
        return self.field_mappings

    @property
    def source_resources(self) -> list[str]:
        return self.selected_resources

    @property
    def platform_node_id(self) -> str:
        return self.execution_plan.get("platform_node_id", "")

    @property
    def status(self) -> str:
        return self.execution_plan.get("status", "ready")


class TaskPlan(BaseModel):
    """Cross-node orchestration plan for materializing a virtual view."""

    plan_id: str = Field(default_factory=lambda: f"plan-{uuid4().hex[:8]}")
    view_id: str = ""
    tasks: list[PlanTask] = Field(default_factory=list)
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    execution_mode: str = "sequential"
    demand_id: str = ""
    total_estimated_ms: float = 0.0
    actual_duration_ms: float = 0.0
    efficiency_score: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _derive_totals(self) -> TaskPlan:
        if self.tasks and self.total_estimated_ms == 0.0:
            self.total_estimated_ms = sum(t.estimated_duration_ms for t in self.tasks)
        return self


class ExecutionResult(BaseModel):
    """Outcome of executing a virtual view orchestration plan."""

    execution_id: str = Field(default_factory=lambda: f"exec-{uuid4().hex[:8]}")
    view_id: str
    demand_id: str
    invoked_nodes: list[str] = Field(default_factory=list)
    invoked_resources: list[str] = Field(default_factory=list)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    status: str = "completed"


class FeedbackEvent(BaseModel):
    """User or system feedback on matching, views, or delivery."""

    feedback_id: str = Field(default_factory=lambda: f"fb-{uuid4().hex[:8]}")
    demand_id: str
    view_id: str = ""
    user_id: str = ""
    action: FeedbackAction = FeedbackAction.VIEWED
    rating: float = Field(default=3.0, ge=0.0, le=5.0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resource_id: str = ""
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    comment: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "action" not in data:
            data["action"] = FeedbackAction.VIEWED.value
        return data


class ProactiveDeliveryEvent(BaseModel):
    """Proactive data service delivery event."""

    event_id: str = Field(default_factory=lambda: f"pe-{uuid4().hex[:8]}")
    trigger_type: str = "pattern_prediction"
    demand_id: str
    target_user: str = ""
    target_application: str = ""
    delivered_view_id: str = ""
    delivery_channel: str = "push"
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    user_action: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if not data.get("trigger_type") and data.get("trigger_reason"):
            data["trigger_type"] = data["trigger_reason"]
        if not data.get("delivered_view_id") and data.get("view_id"):
            data["delivered_view_id"] = data["view_id"]
        if data.get("effectiveness_score") is not None and "relevance_score" not in data:
            data["relevance_score"] = data["effectiveness_score"]
        if data.get("accepted") is True:
            data.setdefault("user_action", "adopted")
        elif data.get("accepted") is False:
            data.setdefault("user_action", "ignored")
        return data

    @property
    def view_id(self) -> str:
        return self.delivered_view_id

    @property
    def trigger_reason(self) -> str:
        return self.trigger_type

    @property
    def delivery_latency_ms(self) -> float:
        return float(self.delivery_channel.split(":")[-1]) if ":" in self.delivery_channel else 0.0

    @property
    def accepted(self) -> bool:
        return self.user_action in ("adopted", "clicked", "exported", "viewed")

    @property
    def effectiveness_score(self) -> float:
        return self.relevance_score


# ---------------------------------------------------------------------------
# Legacy aliases (prototype modules may import these names)
# ---------------------------------------------------------------------------

ApplicationDemand = DemandMetadata
ProactiveEvent = ProactiveDeliveryEvent
TaskOrchestrationPlan = TaskPlan
OrchestrationTask = PlanTask
VirtualViewField = FieldMapping


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def model_to_dict(model: BaseModel, *, exclude_none: bool = False) -> dict[str, Any]:
    """Convert a Pydantic model to a JSON-serializable dictionary."""
    return model.model_dump(mode="json", exclude_none=exclude_none)


def save_json(
    path: Union[str, Path],
    data: Union[BaseModel, list[BaseModel], dict[str, Any], list[dict[str, Any]]],
    *,
    indent: int = 2,
    exclude_none: bool = False,
) -> None:
    """Persist a model, list of models, or dict to a JSON file."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, BaseModel):
        payload: Any = model_to_dict(data, exclude_none=exclude_none)
    elif isinstance(data, list) and data and isinstance(data[0], BaseModel):
        payload = [model_to_dict(item, exclude_none=exclude_none) for item in data]
    else:
        payload = data

    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=indent, default=str)


def load_json(
    path: Union[str, Path],
    model: type[T] | None = None,
    *,
    many: bool = False,
) -> Union[T, list[T], Any]:
    """
    Load JSON from disk and optionally validate into a Pydantic model.

    Parameters
    ----------
    path:
        File path to read.
    model:
        Optional model class for validation.
    many:
        When True, validate a JSON array into a list of models.
    """
    target = Path(path)
    with open(target, encoding="utf-8") as handle:
        raw = json.load(handle)

    if model is None:
        return raw
    if many:
        if not isinstance(raw, list):
            raise ValueError(f"Expected JSON array in {target}")
        return [model.model_validate(item) for item in raw]
    return model.model_validate(raw)


__all__ = [
    "ApplicationDemand",
    "DemandMetadata",
    "DemandPriority",
    "ExecutionResult",
    "FabricNode",
    "FeedbackAction",
    "FeedbackEvent",
    "FieldMapping",
    "MappingType",
    "MatchResult",
    "NodeCapability",
    "NodeStatus",
    "NodeType",
    "OptimizationSnapshot",
    "OrchestrationTask",
    "PlanTask",
    "ProactiveDeliveryEvent",
    "ProactiveEvent",
    "ResourceMetadata",
    "SemanticMapping",
    "TaskOrchestrationPlan",
    "TaskPlan",
    "TaskStatus",
    "VirtualView",
    "VirtualViewField",
    "load_json",
    "model_to_dict",
    "save_json",
]
