"""
Service Layer — integrates core components into the Fabric Control
and Orchestration Plane (unified facade for UI and API).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.storage import StorageManager
from core.demand_manager import DemandManager
from core.feedback_optimizer import FeedbackOptimizer
from core.metadata_store import MetadataStore
from core.models import (
    ApplicationDemand,
    DemandMetadata,
    ExecutionResult,
    FabricNode,
    FeedbackEvent,
    MatchResult,
    ProactiveDeliveryEvent,
    ProactiveEvent,
    SemanticMapping,
    TaskOrchestrationPlan,
    VirtualView,
    load_json,
)
from core.orchestrator import Orchestrator
from core.proactive_service import ProactiveService
from core.registry import NodeRegistry
from core.semantic_matcher import SemanticMatcher
from core.view_builder import ViewBuilder
from nodes.application_node import ApplicationNode
from nodes.platform_node import PlatformNode
from nodes.source_node import SourceNode


class DAFabricService:
    """Unified service facade for the DA-Fabric prototype."""

    def __init__(self, project_root: Optional[Path] = None) -> None:
        self.root = Path(project_root or Path(__file__).resolve().parent.parent)
        self.data_dir = self.root / "data"
        self.results_dir = self.root / "results"
        self.storage = StorageManager(self.data_dir)

        self.registry = NodeRegistry(self.data_dir / "nodes.json")
        self.metadata = MetadataStore(self.data_dir / "resources.json")
        self.demands = DemandManager(self.data_dir / "demands.json")
        self.matcher = SemanticMatcher()
        self.view_builder = ViewBuilder(self.registry)
        self.orchestrator = Orchestrator(self.registry)
        self.proactive = ProactiveService(
            matcher=self.matcher,
            events_path=self.data_dir / "proactive_events.json",
            demands_path=self.data_dir / "demands.json",
            resources_path=self.data_dir / "resources.json",
        )
        self.feedback = FeedbackOptimizer(self.matcher, self.data_dir / "feedback_events.json")

        self._node_instances: dict = {}
        self._views: dict[str, VirtualView] = {}
        self._plans: dict[str, TaskOrchestrationPlan] = {}
        self._executions: dict[str, ExecutionResult] = {}

    def initialize(self) -> dict:
        """Load all seed data and instantiate node objects."""
        counts = {
            "nodes": self.registry.load_from_file(),
            "resources": self.metadata.load_from_file(),
            "demands": self.demands.load_from_file(),
            "feedback": self.feedback.load_from_file(),
        }
        self._instantiate_nodes()
        records = self.storage.read_json("proactive_events", default=[])
        if records:
            self.proactive.load_events_from_records(records)
        self.proactive.load_subscriptions()
        self.proactive.load_resources()
        return counts

    def _instantiate_nodes(self) -> None:
        self._node_instances.clear()
        for node in self.registry.list_nodes():
            if node.node_type.value == "platform":
                self._node_instances[node.node_id] = PlatformNode(node)
            elif node.node_type.value == "source":
                self._node_instances[node.node_id] = SourceNode(node)
            elif node.node_type.value == "application":
                self._node_instances[node.node_id] = ApplicationNode(node)

        for resource in self.metadata.list_resources():
            source_node = self._node_instances.get(resource.source_node_id)
            if isinstance(source_node, SourceNode):
                source_node.register_resource(resource)

    def _load_semantic_mappings(self) -> list[SemanticMapping]:
        path = self.data_dir / "semantic_mappings.json"
        if not path.exists():
            return []
        return load_json(path, SemanticMapping, many=True)

    def get_status(self) -> dict:
        return {
            "nodes": self.registry.size,
            "nodes_by_type": self.registry.count_by_type(),
            "resources": self.metadata.size,
            "demands": self.demands.size,
            "views": len(self._views),
            "executions": len(self._executions),
            "feedback_count": self.feedback.feedback_count,
            "proactive_events": len(self.proactive.history),
            "matcher_method": self.matcher.method,
            "transformer_available": SemanticMatcher.transformer_available(),
        }

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def register_node(self, node: FabricNode) -> FabricNode:
        registered = self.registry.register_node(node)
        self.registry.save_to_file()
        self._instantiate_nodes()
        return registered

    # ------------------------------------------------------------------
    # Demands & matching
    # ------------------------------------------------------------------

    def submit_demand(self, demand: ApplicationDemand | DemandMetadata) -> DemandMetadata:
        saved = self.demands.submit(demand)
        self.demands.save_to_file()
        self.proactive.load_subscriptions()
        return saved

    def match_demand(self, demand_id: str, top_k: int = 5) -> list[MatchResult]:
        demand = self.demands.get(demand_id)
        if not demand:
            return []
        resources = self.metadata.list_resources()
        return self.matcher.match(demand, resources, top_k=top_k)

    # ------------------------------------------------------------------
    # Virtual views & execution
    # ------------------------------------------------------------------

    def build_view(self, demand_id: str, top_k: int = 8) -> Optional[VirtualView]:
        demand = self.demands.get(demand_id)
        if not demand:
            return None
        matches = self.match_demand(demand_id, top_k=top_k)
        if not matches:
            return None
        mappings = self._load_semantic_mappings()
        view = self.view_builder.build_from_demand(
            demand,
            matches,
            self.metadata.list_resources(),
            mappings=mappings,
        )
        self._views[view.view_id] = view
        return view

    def get_view(self, view_id: str) -> Optional[VirtualView]:
        return self._views.get(view_id)

    def execute_view(self, view_id: str) -> Optional[ExecutionResult]:
        view = self._views.get(view_id)
        if not view:
            return None
        result = self.orchestrator.execute_view(view)
        self._executions[result.execution_id] = result
        return result

    def orchestrate(self, demand_id: str) -> Optional[TaskOrchestrationPlan]:
        demand = self.demands.get(demand_id)
        if not demand:
            return None
        view = next((v for v in self._views.values() if v.demand_id == demand_id), None)
        if not view:
            view = self.build_view(demand_id)
        if not view:
            return None
        plan = self.orchestrator.create_plan(demand, view)
        plan = self.orchestrator.execute_plan(plan, simulate=True)
        self._plans[plan.plan_id] = plan
        return plan

    # ------------------------------------------------------------------
    # Proactive delivery
    # ------------------------------------------------------------------

    def simulate_proactive(self, num_updates: int = 1) -> dict:
        """Simulate resource updates, evaluate triggers, and deliver events."""
        self.proactive.load_subscriptions()
        self.proactive.load_resources()
        updates: list[dict] = []
        deliveries: list[ProactiveDeliveryEvent] = []

        for _ in range(max(1, num_updates)):
            update = self.proactive.simulate_resource_update()
            updates.append(update)
            candidates = self.proactive.check_triggers(update)
            for candidate in candidates:
                deliveries.append(self.proactive.deliver(candidate))

        if deliveries:
            self.proactive.save_events()

        return {
            "updates": updates,
            "triggered_count": len(deliveries),
            "deliveries": [d.model_dump(mode="json") for d in deliveries],
        }

    def proactive_deliver(self, demand_id: str) -> Optional[ProactiveEvent]:
        demand = self.demands.get(demand_id)
        if not demand:
            return None
        view = self.build_view(demand_id)
        if not view:
            return None
        return self.proactive.deliver(demand, view)

    # ------------------------------------------------------------------
    # Feedback & optimization
    # ------------------------------------------------------------------

    def record_feedback(self, feedback: FeedbackEvent) -> FeedbackEvent:
        recorded = self.feedback.record_feedback(feedback)
        self.feedback.save_to_file()
        return recorded

    def optimize(self) -> dict:
        snapshot = self.feedback.optimize()
        return snapshot.model_dump()

    # ------------------------------------------------------------------
    # Reference data
    # ------------------------------------------------------------------

    def get_ground_truth(self) -> list[dict]:
        return self.storage.read_json("ground_truth", default=[])

    def get_semantic_mappings(self) -> list[dict]:
        return self.storage.read_json("semantic_mappings", default=[])
