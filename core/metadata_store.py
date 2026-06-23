"""
Metadata Store — resource metadata catalog for the simulated
resource and application layer (Section III-B).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.models import ResourceMetadata, load_json, save_json


class MetadataStore:
    """Catalog of synthetic resource metadata across platforms."""

    DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "resources.json"

    def __init__(self, data_path: Optional[Path | str] = None) -> None:
        self._resources: dict[str, ResourceMetadata] = {}
        self._data_path = Path(data_path) if data_path else self.DEFAULT_DATA_PATH

    def load(self, path: Optional[Path | str] = None) -> int:
        """Load resources from JSON seed data (default: data/resources.json)."""
        file_path = Path(path) if path else self._data_path
        if not file_path.exists():
            return 0
        resources = load_json(file_path, ResourceMetadata, many=True)
        self._resources.clear()
        for resource in resources:
            self.add_resource(resource)
        return len(resources)

    def list_resources(
        self,
        domain: Optional[str] = None,
        platform: Optional[str] = None,
        source_node_id: Optional[str] = None,
        *,
        node_type: Optional[str] = None,
        business_domain: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> list[ResourceMetadata]:
        """
        List resources with optional filters.

        Supports legacy parameters (domain, platform, source_node_id) and
        canonical filters (node_type, business_domain, entity_type).
        """
        bd = business_domain or domain
        nt = node_type or platform
        resources = self.list_resources_unfiltered()
        if nt:
            resources = [r for r in resources if r.node_type == nt or r.platform == nt]
        if bd:
            resources = [r for r in resources if r.business_domain == bd or r.domain == bd]
        if entity_type:
            resources = [r for r in resources if r.entity_type == entity_type]
        if source_node_id:
            resources = [
                r for r in resources
                if r.node_id == source_node_id or r.source_node_id == source_node_id
            ]
        return resources

    def list_resources_unfiltered(self) -> list[ResourceMetadata]:
        """List all resources sorted by name."""
        return sorted(self._resources.values(), key=lambda r: r.name)

    def get_resource(self, resource_id: str) -> Optional[ResourceMetadata]:
        """Retrieve a resource by identifier."""
        return self._resources.get(resource_id)

    def filter_resources(
        self,
        *,
        node_type: Optional[str] = None,
        business_domain: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> list[ResourceMetadata]:
        """Filter resources by platform node type, business domain, and/or entity type."""
        return self.list_resources(
            node_type=node_type,
            business_domain=business_domain,
            entity_type=entity_type,
        )

    def add_resource(self, resource: ResourceMetadata) -> ResourceMetadata:
        """Add or update a resource in the catalog."""
        self._resources[resource.resource_id] = resource
        return resource

    def save_resources(self, path: Optional[Path | str] = None) -> None:
        """Persist catalog to JSON."""
        file_path = Path(path) if path else self._data_path
        payload = [r.model_dump(mode="json") for r in self._resources.values()]
        save_json(file_path, payload)

    def search_text(self, query: str) -> list[ResourceMetadata]:
        """Search resources by name, description, or keywords."""
        q = query.lower()
        return [
            r
            for r in self._resources.values()
            if q in r.name.lower()
            or q in r.description.lower()
            or any(q in kw.lower() for kw in r.keywords)
        ]

    def domains(self) -> list[str]:
        """List distinct business domains in the catalog."""
        return sorted({r.business_domain for r in self._resources.values() if r.business_domain})

    def platforms(self) -> list[str]:
        """List distinct platform/node_type values in the catalog."""
        return sorted({r.node_type for r in self._resources.values() if r.node_type})

    def entity_types(self) -> list[str]:
        """List distinct entity types in the catalog."""
        return sorted({r.entity_type for r in self._resources.values() if r.entity_type})

    @property
    def size(self) -> int:
        return len(self._resources)

    # Legacy aliases
    add = add_resource
    get = get_resource
    load_from_file = load
    save_to_file = save_resources
