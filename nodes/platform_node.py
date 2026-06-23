"""
Platform-side Fabric Node — mediates cross-platform metadata federation
and virtual view materialization.
"""

from __future__ import annotations

from typing import Any

from core.models import FabricNode
from nodes.base_node import BaseFabricNode


class PlatformNode(BaseFabricNode):
    """Platform-side node for metadata federation and view hosting."""

    def __init__(self, config: FabricNode) -> None:
        super().__init__(config)

    def execute_task(self, task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "metadata_discovery": self._metadata_discovery,
            "schema_alignment": self._schema_alignment,
            "view_materialization": self._view_materialization,
        }
        handler = handlers.get(task_type, self._default_handler)
        return handler(payload)

    def _metadata_discovery(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "platform": self.config.platform,
            "discovered_resources": payload.get("resource_ids", []),
            "status": "completed",
        }

    def _schema_alignment(self, payload: dict[str, Any]) -> dict[str, Any]:
        fields = payload.get("fields", [])
        return {
            "node_id": self.node_id,
            "aligned_fields": fields,
            "mapping_rules": len(fields),
            "status": "completed",
        }

    def _view_materialization(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "view_id": payload.get("view_id"),
            "materialized": True,
            "platform": self.config.platform,
            "status": "completed",
        }

    def _default_handler(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"node_id": self.node_id, "task": "noop", "status": "completed"}

    def federate_metadata(self, resource_ids: list[str]) -> dict[str, Any]:
        return self._metadata_discovery({"resource_ids": resource_ids})
