"""
Node Registry — Fabric Control Plane component for node registration
and capability management (Section III-A in paper architecture).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Optional

from core.models import FabricNode, NodeCapability, NodeStatus, NodeType, load_json, save_json


class NodeRegistry:
    """Manages registration and lookup of fabric nodes."""

    DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "nodes.json"

    def __init__(self, data_path: Optional[Path | str] = None) -> None:
        self._nodes: dict[str, FabricNode] = {}
        self._data_path = Path(data_path) if data_path else self.DEFAULT_DATA_PATH

    def load(self, path: Optional[Path | str] = None) -> int:
        """Load nodes from JSON seed data (default: data/nodes.json)."""
        file_path = Path(path) if path else self._data_path
        if not file_path.exists():
            return 0
        nodes = load_json(file_path, FabricNode, many=True)
        self._nodes.clear()
        for node in nodes:
            self.register_node(node)
        return len(nodes)

    def register_node(self, node: FabricNode) -> FabricNode:
        """Register or update a fabric node."""
        self._nodes[node.node_id] = node
        return node

    def list_nodes(
        self,
        node_type: Optional[NodeType] = None,
        status: Optional[NodeStatus] = None,
    ) -> list[FabricNode]:
        """List registered nodes with optional type and status filters."""
        nodes = list(self._nodes.values())
        if node_type:
            nodes = [n for n in nodes if n.node_type == node_type]
        if status:
            nodes = [n for n in nodes if n.status == status]
        return sorted(nodes, key=lambda n: n.name)

    def get_node(self, node_id: str) -> Optional[FabricNode]:
        """Retrieve a node by identifier."""
        return self._nodes.get(node_id)

    def list_by_type(self, node_type: NodeType | str) -> list[FabricNode]:
        """List all nodes of a given type."""
        if isinstance(node_type, str):
            node_type = NodeType(node_type)
        return self.list_nodes(node_type=node_type)

    def build_capability_directory(self) -> dict[str, dict[str, list[str]]]:
        """
        Build an index of supported tasks and services across all nodes.

        Returns
        -------
        dict with keys ``tasks``, ``services``, and ``nodes`` mapping
        capability names / node ids to participating node ids or profiles.
        """
        task_index: dict[str, list[str]] = defaultdict(list)
        service_index: dict[str, list[str]] = defaultdict(list)
        node_profiles: dict[str, dict] = {}

        for node in self._nodes.values():
            profile = NodeCapability(
                node_id=node.node_id,
                executable_tasks=node.supported_tasks,
                service_types=node.supported_services,
                metadata_types=[node.node_type.value],
            )
            node_profiles[node.node_id] = profile.model_dump(mode="json")

            for task in node.supported_tasks:
                task_index[task].append(node.node_id)
            for service in node.supported_services:
                service_index[service].append(node.node_id)

        return {
            "tasks": dict(sorted(task_index.items())),
            "services": dict(sorted(service_index.items())),
            "nodes": node_profiles,
        }

    def save(self, path: Optional[Path | str] = None) -> None:
        """Persist registered nodes to JSON."""
        file_path = Path(path) if path else self._data_path
        payload = [n.model_dump(mode="json") for n in self._nodes.values()]
        save_json(file_path, payload)

    def count_by_type(self) -> dict[str, int]:
        """Count nodes grouped by node type."""
        counts: dict[str, int] = {}
        for node in self._nodes.values():
            key = node.node_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    @property
    def size(self) -> int:
        return len(self._nodes)

    # Legacy aliases
    register = register_node
    get = get_node
    load_from_file = load
    save_to_file = save

    def unregister(self, node_id: str) -> bool:
        if node_id in self._nodes:
            del self._nodes[node_id]
            return True
        return False

    def add_capability(self, node_id: str, capability: NodeCapability) -> Optional[FabricNode]:
        node = self._nodes.get(node_id)
        if not node:
            return None
        tasks = list(node.supported_tasks)
        if capability.name and capability.name not in tasks:
            tasks.append(capability.name)
        services = list(dict.fromkeys(node.supported_services + capability.service_types))
        updated = node.model_copy(update={"supported_tasks": tasks, "supported_services": services})
        self._nodes[node_id] = updated
        return updated

    def find_by_capability(self, capability_name: str) -> list[FabricNode]:
        return [n for n in self._nodes.values() if capability_name in n.supported_tasks]
