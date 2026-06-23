"""
Source-side Fabric Node — exposes data source metadata and
executes extraction tasks at the data origin.
"""

from __future__ import annotations

from typing import Any

from core.models import FabricNode, ResourceMetadata
from nodes.base_node import BaseFabricNode


class SourceNode(BaseFabricNode):
    """Source-side node attached to origin data systems."""

    def __init__(self, config: FabricNode) -> None:
        super().__init__(config)
        self._local_resources: dict[str, ResourceMetadata] = {}

    def register_resource(self, resource: ResourceMetadata) -> None:
        bound = resource.model_copy(update={"node_id": self.node_id})
        self._local_resources[bound.resource_id] = bound

    def list_local_resources(self) -> list[ResourceMetadata]:
        return list(self._local_resources.values())

    def execute_task(self, task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "data_extraction": self._data_extraction,
            "quality_validation": self._quality_validation,
        }
        handler = handlers.get(task_type, self._default_handler)
        return handler(payload)

    def _data_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        resource_id = payload.get("resource_id", "")
        return {
            "node_id": self.node_id,
            "resource_id": resource_id,
            "rows_extracted": payload.get("limit", 1000),
            "format": payload.get("format", "parquet"),
            "status": "completed",
        }

    def _quality_validation(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "quality_score": payload.get("quality_score", 0.85),
            "checks_passed": ["completeness", "schema_conformance"],
            "status": "completed",
        }

    def _default_handler(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"node_id": self.node_id, "status": "completed"}
