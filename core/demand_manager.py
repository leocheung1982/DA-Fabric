"""
Demand Manager — handles demand metadata submission from
application-side fabric nodes (Section III-C).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.models import DemandMetadata, DemandPriority, load_json, save_json

# Legacy alias
ApplicationDemand = DemandMetadata


class DemandManager:
    """Manages application demand lifecycle."""

    DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "demands.json"

    def __init__(self, data_path: Optional[Path | str] = None) -> None:
        self._demands: dict[str, DemandMetadata] = {}
        self._data_path = Path(data_path) if data_path else self.DEFAULT_DATA_PATH

    def load(self, path: Optional[Path | str] = None) -> int:
        """Load demands from JSON seed data (default: data/demands.json)."""
        file_path = Path(path) if path else self._data_path
        if not file_path.exists():
            return 0
        demands = load_json(file_path, DemandMetadata, many=True)
        self._demands.clear()
        for demand in demands:
            self.submit_demand(demand)
        return len(demands)

    def submit_demand(self, demand: DemandMetadata) -> DemandMetadata:
        """Submit or update a demand in the manager."""
        self._demands[demand.demand_id] = demand
        return demand

    def list_demands(
        self,
        priority: Optional[DemandPriority] = None,
        domain: Optional[str] = None,
        object_type: Optional[str] = None,
    ) -> list[DemandMetadata]:
        """List demands with optional priority, domain, or object_type filters."""
        demands = list(self._demands.values())
        if priority:
            demands = [d for d in demands if d.priority == priority]
        if domain:
            demands = [
                d
                for d in demands
                if d.object_type == domain
                or d.domain == domain
                or domain in d.conditions.get("business_domains", [])
            ]
        if object_type:
            demands = [d for d in demands if d.object_type == object_type]
        return sorted(demands, key=lambda d: d.submitted_at, reverse=True)

    def get_demand(self, demand_id: str) -> Optional[DemandMetadata]:
        """Retrieve a demand by identifier."""
        return self._demands.get(demand_id)

    def list_subscriptions(self) -> list[DemandMetadata]:
        """List demands with proactive subscription enabled."""
        return [
            d
            for d in self._demands.values()
            if isinstance(d.subscription, dict) and d.subscription.get("enabled") is True
        ]

    def save_demands(self, path: Optional[Path | str] = None) -> None:
        """Persist demands to JSON."""
        file_path = Path(path) if path else self._data_path
        payload = [d.model_dump(mode="json") for d in self._demands.values()]
        save_json(file_path, payload)

    @property
    def size(self) -> int:
        return len(self._demands)

    # Legacy aliases
    submit = submit_demand
    get = get_demand
    load_from_file = load
    save_to_file = save_demands

    def update(self, demand_id: str, **kwargs) -> Optional[DemandMetadata]:
        demand = self._demands.get(demand_id)
        if not demand:
            return None
        updated = demand.model_copy(update=kwargs)
        self._demands[demand_id] = updated
        return updated

    def delete(self, demand_id: str) -> bool:
        if demand_id in self._demands:
            del self._demands[demand_id]
            return True
        return False
