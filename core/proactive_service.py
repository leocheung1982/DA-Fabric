"""
Proactive Service — simulates proactive data service delivery based on
resource update events and subscription demands (Section III-G).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from core.models import (
    DemandMetadata,
    ProactiveDeliveryEvent,
    ResourceMetadata,
    VirtualView,
    load_json,
    save_json,
)
from core.semantic_matcher import MatchOptions, SemanticMatcher

ApplicationDemand = DemandMetadata
ProactiveEvent = ProactiveDeliveryEvent

RELEVANCE_THRESHOLD = 0.58
DEFAULT_EVENTS_PATH = Path(__file__).resolve().parent.parent / "data" / "proactive_events.json"
DEFAULT_DEMANDS_PATH = Path(__file__).resolve().parent.parent / "data" / "demands.json"
DEFAULT_RESOURCES_PATH = Path(__file__).resolve().parent.parent / "data" / "resources.json"


class ProactiveService:
    """Simulates proactive delivery triggered by resource update events."""

    def __init__(
        self,
        matcher: Optional[SemanticMatcher] = None,
        events_path: Optional[Path | str] = None,
        demands_path: Optional[Path | str] = None,
        resources_path: Optional[Path | str] = None,
        base_latency_ms: float = 50.0,
        seed: int = 42,
    ) -> None:
        self.matcher = matcher or SemanticMatcher(auto_load=True)
        self.events_path = Path(events_path) if events_path else DEFAULT_EVENTS_PATH
        self.demands_path = Path(demands_path) if demands_path else DEFAULT_DEMANDS_PATH
        self.resources_path = Path(resources_path) if resources_path else DEFAULT_RESOURCES_PATH
        self.base_latency_ms = base_latency_ms
        self.seed = seed
        self._sim_counter = 0

        self._subscription_demands: list[DemandMetadata] = []
        self._resources: list[ResourceMetadata] = []
        self._resource_map: dict[str, ResourceMetadata] = {}
        self._delivery_history: list[ProactiveDeliveryEvent] = []

        self.load_subscriptions()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_subscriptions(self) -> int:
        """Load subscription-enabled demands from demands.json."""
        if not self.demands_path.exists():
            self._subscription_demands = []
            return 0
        demands = load_json(self.demands_path, DemandMetadata, many=True)
        self._subscription_demands = [
            d for d in demands
            if isinstance(d.subscription, dict) and d.subscription.get("enabled") is True
        ]
        return len(self._subscription_demands)

    def load_resources(self) -> int:
        """Load resource catalog for update simulation."""
        if not self.resources_path.exists():
            return 0
        self._resources = load_json(self.resources_path, ResourceMetadata, many=True)
        self._resource_map = {r.resource_id: r for r in self._resources}
        return len(self._resources)

    def load_events_from_records(self, records: list[dict]) -> list[ProactiveDeliveryEvent]:
        """Load historical proactive events into memory."""
        events = [ProactiveDeliveryEvent.model_validate(r) for r in records]
        self._delivery_history.extend(events)
        return events

    def save_events(self, path: Optional[Path | str] = None) -> None:
        """Persist delivery history to data/proactive_events.json."""
        target = Path(path) if path else self.events_path
        payload = [e.model_dump(mode="json") for e in self._delivery_history]
        save_json(target, payload)

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    def _stable_pick(self, key: str, items: list) -> int:
        if not items:
            return 0
        digest = hashlib.md5(f"{self.seed}:{key}".encode()).hexdigest()
        return int(digest[:8], 16) % len(items)

    def _compute_relevance(
        self,
        demand: DemandMetadata,
        resource: ResourceMetadata,
    ) -> float:
        """Compute relevance using the full DA-Fabric scoring function."""
        result = self.matcher.score_pair(
            demand,
            resource,
            options=MatchOptions(profile="da_fabric"),
        )
        return result.score

    def _indicator_overlap(
        self,
        demand: DemandMetadata,
        updated_fields: list[str],
    ) -> bool:
        if not demand.indicators:
            return True
        updated = {f.lower() for f in updated_fields}
        return any(ind.lower() in updated for ind in demand.indicators)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def simulate_resource_update(
        self,
        resource: Optional[ResourceMetadata] = None,
    ) -> dict:
        """Simulate a synthetic resource metadata update event."""
        if not self._resources:
            self.load_resources()
        if not self._resources:
            return {"event_id": "update-empty", "resource_id": "", "object_type": "", "updated_fields": []}

        self._sim_counter += 1
        if resource is None:
            resource = self._resources[self._stable_pick(f"res-{self._sim_counter}", self._resources)]

        n_fields = max(1, min(3, len(resource.fields)))
        start = self._stable_pick(f"fld-{self._sim_counter}", resource.fields)
        updated_fields = [
            resource.fields[(start + i) % len(resource.fields)] for i in range(n_fields)
        ]

        return {
            "event_id": f"upd-{self._sim_counter:05d}",
            "resource_id": resource.resource_id,
            "object_type": resource.entity_type,
            "node_id": resource.node_id,
            "business_domain": resource.business_domain,
            "updated_fields": updated_fields,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def check_triggers(
        self,
        update_event: dict,
        subscription_demands: Optional[list[DemandMetadata]] = None,
    ) -> list[ProactiveDeliveryEvent]:
        """
        Check which subscription demands are triggered by a resource update.

        Matches on object_type and indicator overlap; computes relevance via matcher.
        """
        demands = subscription_demands if subscription_demands is not None else self._subscription_demands
        if not self._resource_map:
            self.load_resources()

        resource = self._resource_map.get(update_event.get("resource_id", ""))
        if not resource:
            return []

        updated_fields = update_event.get("updated_fields", [])
        triggered: list[ProactiveDeliveryEvent] = []

        for demand in demands:
            if demand.object_type and demand.object_type != update_event.get("object_type"):
                continue
            if not self._indicator_overlap(demand, updated_fields):
                continue

            relevance = self._compute_relevance(demand, resource)
            if relevance < RELEVANCE_THRESHOLD:
                continue

            ind_cov = self.matcher.indicator_score(demand, resource, use_mapping=True)
            if ind_cov < 0.20:
                continue

            channel = demand.subscription.get("channel", "push") if demand.subscription else "push"
            triggered.append(
                ProactiveDeliveryEvent(
                    trigger_type="resource_update",
                    demand_id=demand.demand_id,
                    target_user=demand.user_id,
                    target_application=demand.application,
                    delivered_view_id=f"view-proactive-{demand.demand_id}",
                    delivery_channel=f"{channel}:{self.base_latency_ms}",
                    relevance_score=round(relevance, 4),
                    user_action="",
                )
            )

        return triggered

    def deliver(
        self,
        event_or_demand: Union[ProactiveDeliveryEvent, DemandMetadata],
        view: Optional[VirtualView] = None,
        trigger_reason: str = "pattern_prediction",
    ) -> ProactiveDeliveryEvent:
        """
        Record a proactive delivery event.

        Accepts a ProactiveDeliveryEvent (subscription trigger path) or
        legacy (demand, view) pair from explicit delivery simulation.
        """
        if isinstance(event_or_demand, ProactiveDeliveryEvent):
            event = event_or_demand
            if not event.user_action:
                event = event.model_copy(update={"user_action": "delivered"})
        else:
            demand = event_or_demand
            if view is None:
                raise ValueError("view is required when delivering from demand metadata")
            latency = self.base_latency_ms + view.construction_time_ms * 0.1
            field_coverage = len(view.fields) / max(len(demand.indicators), 1)
            relevance = min(1.0, 0.5 + 0.3 * field_coverage)
            accepted_action = "adopted" if relevance >= 0.6 else "ignored"

            event = ProactiveDeliveryEvent(
                demand_id=demand.demand_id,
                delivered_view_id=view.view_id,
                trigger_type=trigger_reason,
                delivery_channel=f"push:{round(latency, 2)}",
                relevance_score=round(relevance, 4),
                user_action=accepted_action,
                target_user=demand.user_id,
                target_application=demand.application,
            )

        self._delivery_history.append(event)
        return event

    def run_simulation(self, num_events: int = 100) -> list[ProactiveDeliveryEvent]:
        """
        Run proactive delivery simulation over synthetic resource updates.

        Saves triggered events (relevance >= 0.50) to proactive_events.json.
        """
        self.load_subscriptions()
        self.load_resources()
        new_deliveries: list[ProactiveDeliveryEvent] = []

        for _ in range(num_events):
            update = self.simulate_resource_update()
            candidates = self.check_triggers(update)
            for candidate in candidates:
                delivered = self.deliver(candidate)
                new_deliveries.append(delivered)

        self.save_events()
        return new_deliveries

    # ------------------------------------------------------------------
    # Legacy / utility API
    # ------------------------------------------------------------------

    @property
    def history(self) -> list[ProactiveDeliveryEvent]:
        return list(self._delivery_history)

    @property
    def subscription_demands(self) -> list[DemandMetadata]:
        return list(self._subscription_demands)

    def predict_proactive_candidates(
        self,
        demands: list[DemandMetadata],
        historical_events: Optional[list[ProactiveDeliveryEvent]] = None,
    ) -> list[DemandMetadata]:
        """Identify demands with proactive subscriptions enabled."""
        return [
            d for d in demands
            if isinstance(d.subscription, dict) and d.subscription.get("enabled")
        ]

    def batch_deliver(
        self,
        demand_view_pairs: list[tuple[DemandMetadata, VirtualView]],
    ) -> list[ProactiveDeliveryEvent]:
        return [self.deliver(d, v) for d, v in demand_view_pairs]

    def compute_metrics(self, events: Optional[list[ProactiveDeliveryEvent]] = None) -> dict:
        events = events or self._delivery_history
        if not events:
            return {
                "total_deliveries": 0,
                "acceptance_rate": 0.0,
                "avg_latency_ms": 0.0,
                "avg_effectiveness": 0.0,
            }
        accepted = [e for e in events if e.accepted]
        return {
            "total_deliveries": len(events),
            "acceptance_rate": round(len(accepted) / len(events), 4),
            "avg_latency_ms": round(
                sum(e.delivery_latency_ms for e in events) / len(events), 2
            ),
            "avg_effectiveness": round(
                sum(e.effectiveness_score for e in accepted) / max(len(accepted), 1), 4
            ),
        }
