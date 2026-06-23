"""
Application-side Fabric Node — submits demands and receives
proactive data services.
"""

from __future__ import annotations

from typing import Any

from core.models import ApplicationDemand, FabricNode, ProactiveEvent, VirtualView
from nodes.base_node import BaseFabricNode


class ApplicationNode(BaseFabricNode):
    """Application-side node representing consumer applications."""

    def __init__(self, config: FabricNode) -> None:
        super().__init__(config)
        self._pending_demands: list[ApplicationDemand] = []
        self._delivered_views: list[VirtualView] = []
        self._proactive_events: list[ProactiveEvent] = []

    def submit_demand(self, demand: ApplicationDemand) -> ApplicationDemand:
        demand.application_node_id = self.node_id
        self._pending_demands.append(demand)
        return demand

    def receive_view(self, view: VirtualView) -> VirtualView:
        self._delivered_views.append(view)
        return view

    def receive_proactive_delivery(self, event: ProactiveEvent, view: VirtualView) -> bool:
        self._proactive_events.append(event)
        if event.accepted:
            self._delivered_views.append(view)
            return True
        return False

    def execute_task(self, task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task_type == "delivery_notification":
            return {
                "node_id": self.node_id,
                "view_id": payload.get("view_id"),
                "notified": True,
                "status": "completed",
            }
        return {"node_id": self.node_id, "status": "completed"}

    @property
    def pending_demands(self) -> list[ApplicationDemand]:
        return list(self._pending_demands)

    @property
    def delivered_views(self) -> list[VirtualView]:
        return list(self._delivered_views)
