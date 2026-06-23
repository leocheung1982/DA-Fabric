"""
Base Fabric Node — abstract node behavior shared across node types.

Each node type maps to a fabric node role in the multi-platform
data environment (Section II-B).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from core.models import FabricNode, NodeCapability, NodeStatus


class BaseFabricNode(ABC):
    """Base class for platform, source, and application fabric nodes."""

    def __init__(self, config: FabricNode) -> None:
        self.config = config

    @property
    def node_id(self) -> str:
        return self.config.node_id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def status(self) -> NodeStatus:
        return self.config.status

    def heartbeat(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "capabilities": [c.name for c in self.config.capabilities],
        }

    @abstractmethod
    def execute_task(self, task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute a delegated orchestration task."""

    def has_capability(self, name: str) -> bool:
        return any(c.name == name for c in self.config.capabilities)

    def get_capability(self, name: str) -> Optional[NodeCapability]:
        for cap in self.config.capabilities:
            if cap.name == name:
                return cap
        return None
