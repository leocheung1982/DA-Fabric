"""Core DA-Fabric components — Fabric Control and Orchestration Plane."""

from core.models import (
    DemandMetadata,
    ExecutionResult,
    FabricNode,
    FeedbackEvent,
    MatchResult,
    ProactiveDeliveryEvent,
    ResourceMetadata,
    TaskPlan,
    VirtualView,
    load_json,
    model_to_dict,
    save_json,
)
from core.registry import NodeRegistry
from core.metadata_store import MetadataStore
from core.demand_manager import DemandManager
from core.semantic_matcher import SemanticMatcher
from core.view_builder import ViewBuilder, VirtualViewBuilder
from core.orchestrator import Orchestrator, TaskOrchestrator
from core.proactive_service import ProactiveService
from core.feedback_optimizer import FeedbackOptimizer

# Legacy aliases
ApplicationDemand = DemandMetadata
ProactiveEvent = ProactiveDeliveryEvent
TaskOrchestrationPlan = TaskPlan

__all__ = [
    "ApplicationDemand",
    "DemandMetadata",
    "ExecutionResult",
    "FabricNode",
    "FeedbackEvent",
    "MatchResult",
    "ProactiveDeliveryEvent",
    "ProactiveEvent",
    "ResourceMetadata",
    "TaskOrchestrationPlan",
    "TaskPlan",
    "VirtualView",
    "NodeRegistry",
    "MetadataStore",
    "DemandManager",
    "SemanticMatcher",
    "ViewBuilder",
    "VirtualViewBuilder",
    "Orchestrator",
    "TaskOrchestrator",
    "ProactiveService",
    "FeedbackOptimizer",
    "model_to_dict",
    "save_json",
    "load_json",
]
