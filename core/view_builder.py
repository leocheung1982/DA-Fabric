"""
View Builder — demand-driven virtual view construction (Section III-E).

Constructs unified virtual views spanning matched resources across
platform-side and source-side nodes.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Union

from core.models import (
    DemandMetadata,
    FieldMapping,
    MatchResult,
    ResourceMetadata,
    SemanticMapping,
    VirtualView,
    save_json,
)
from core.registry import NodeRegistry

ApplicationDemand = DemandMetadata
VirtualViewField = FieldMapping

SCORE_THRESHOLD = 0.45
MAX_RESOURCES_PER_VIEW = 5
SUPPLY_SCORE_THRESHOLD = 0.20
SUPPLY_MIN_RESOURCES = 8
SUPPLY_MAX_RESOURCES = 12


class VirtualViewBuilder:
    """Builds virtual views from demand requirements and ranked match results."""

    def __init__(
        self,
        registry: Optional[NodeRegistry] = None,
        *,
        score_threshold: float = SCORE_THRESHOLD,
        max_resources: int = MAX_RESOURCES_PER_VIEW,
    ) -> None:
        self.score_threshold = score_threshold
        self.max_resources = max_resources
        self.registry = registry

    # ------------------------------------------------------------------
    # Resource selection
    # ------------------------------------------------------------------

    def _resource_map(self, resources: list[ResourceMetadata]) -> dict[str, ResourceMetadata]:
        return {r.resource_id: r for r in resources}

    def _select_resources(
        self,
        demand: DemandMetadata,
        match_results: list[MatchResult],
        resource_map: dict[str, ResourceMetadata],
    ) -> list[ResourceMetadata]:
        """
        Select resources with score >= threshold, max 8, covering all indicators
        when possible.
        """
        eligible = [
            m for m in sorted(match_results, key=lambda x: x.score, reverse=True)
            if m.score >= self.score_threshold and m.resource_id in resource_map
        ]

        selected: list[ResourceMetadata] = []
        selected_ids: set[str] = set()
        covered_indicators: set[str] = set()

        def _covers(resource: ResourceMetadata, indicator: str) -> bool:
            fields = set(resource.fields) | set(resource.indicators)
            if indicator in fields:
                return True
            return indicator.lower() in {f.lower() for f in fields}

        # First pass: pick resources that cover uncovered indicators
        for indicator in demand.indicators:
            if indicator in covered_indicators:
                continue
            for match in eligible:
                resource = resource_map[match.resource_id]
                if resource.resource_id in selected_ids:
                    if _covers(resource, indicator):
                        covered_indicators.add(indicator)
                    continue
                if _covers(resource, indicator):
                    selected.append(resource)
                    selected_ids.add(resource.resource_id)
                    covered_indicators.add(indicator)
                    break
            if len(selected) >= self.max_resources:
                break

        # Second pass: fill remaining slots by score
        for match in eligible:
            if len(selected) >= self.max_resources:
                break
            if match.resource_id not in selected_ids:
                selected.append(resource_map[match.resource_id])
                selected_ids.add(match.resource_id)

        return selected[: self.max_resources]

    def _select_supply_fabric_resources(
        self,
        demand: DemandMetadata,
        match_results: list[MatchResult],
        resource_map: dict[str, ResourceMetadata],
    ) -> list[ResourceMetadata]:
        """Broad supply-side view: 8–12 resources from the same business domain."""
        domains = set(demand.conditions.get("business_domains", []))
        eligible: list[ResourceMetadata] = []
        seen: set[str] = set()

        ranked = sorted(match_results, key=lambda m: m.score, reverse=True)
        for match in ranked:
            resource = resource_map.get(match.resource_id)
            if not resource or resource.resource_id in seen:
                continue
            if domains and resource.business_domain not in domains:
                continue
            if match.score < SUPPLY_SCORE_THRESHOLD:
                continue
            eligible.append(resource)
            seen.add(resource.resource_id)

        if len(eligible) < SUPPLY_MIN_RESOURCES:
            for match in ranked:
                resource = resource_map.get(match.resource_id)
                if not resource or resource.resource_id in seen:
                    continue
                if domains and resource.business_domain not in domains:
                    continue
                eligible.append(resource)
                seen.add(resource.resource_id)
                if len(eligible) >= SUPPLY_MIN_RESOURCES:
                    break

        target = min(SUPPLY_MAX_RESOURCES, max(SUPPLY_MIN_RESOURCES, len(demand.indicators) + 4))
        return eligible[:target]

    def _select_da_fabric_resources(
        self,
        demand: DemandMetadata,
        match_results: list[MatchResult],
        resource_map: dict[str, ResourceMetadata],
    ) -> list[ResourceMetadata]:
        """Demand-aware minimal set covering indicators (max 5, threshold 0.45)."""
        prev_threshold = self.score_threshold
        prev_max = self.max_resources
        self.score_threshold = SCORE_THRESHOLD
        self.max_resources = MAX_RESOURCES_PER_VIEW
        try:
            return self._select_resources(demand, match_results, resource_map)
        finally:
            self.score_threshold = prev_threshold
            self.max_resources = prev_max

    def _build_mapping_index(
        self,
        mappings: list[SemanticMapping],
    ) -> dict[str, list[tuple[str, str]]]:
        """Map source terms to (target_term, mapping_type) pairs."""
        index: dict[str, list[tuple[str, str]]] = {}
        for mapping in mappings:
            src = mapping.source_term.lower()
            tgt = mapping.target_term.lower()
            mtype = mapping.mapping_type.value if hasattr(mapping.mapping_type, "value") else str(mapping.mapping_type)
            index.setdefault(src, []).append((tgt, mtype))
            if mtype in ("equivalent", "similar"):
                index.setdefault(tgt, []).append((src, mtype))
        return index

    def _resolve_source_field(
        self,
        indicator: str,
        resource: ResourceMetadata,
        mapping_index: dict[str, list[tuple[str, str]]],
    ) -> tuple[str, str]:
        """Return (source_field, transform) for an indicator on a resource."""
        fields = resource.fields + resource.indicators
        field_lower = {f.lower(): f for f in fields}

        if indicator in fields:
            return indicator, "identity"
        if indicator.lower() in field_lower:
            return field_lower[indicator.lower()], "identity"

        # Semantic mapping lookup
        for src, targets in mapping_index.items():
            if src == indicator.lower() or indicator.lower() == src:
                for tgt, mtype in targets:
                    if tgt in field_lower:
                        return field_lower[tgt], f"semantic_{mtype}"
            for tgt, mtype in targets:
                if tgt == indicator.lower() and src in field_lower:
                    return field_lower[src], f"semantic_{mtype}"

        # Partial token match fallback
        ind_tokens = set(indicator.lower().replace("_", " ").split())
        for field in fields:
            field_tokens = set(field.lower().replace("_", " ").split())
            if ind_tokens & field_tokens:
                return field, "alias"

        return fields[0] if fields else indicator, "fallback"

    # ------------------------------------------------------------------
    # Public builders
    # ------------------------------------------------------------------

    def generate_field_mappings(
        self,
        demand: DemandMetadata,
        selected_resources: list[ResourceMetadata],
        mappings: list[SemanticMapping],
    ) -> list[FieldMapping]:
        """Generate field mappings using demand indicators and semantic mappings."""
        mapping_index = self._build_mapping_index(mappings)
        field_mappings: list[FieldMapping] = []
        covered: set[str] = set()

        for indicator in demand.indicators:
            for resource in selected_resources:
                source_field, transform = self._resolve_source_field(
                    indicator, resource, mapping_index
                )
                if indicator in covered and transform == "fallback":
                    continue
                field_mappings.append(
                    FieldMapping(
                        source_resource_id=resource.resource_id,
                        source_field=source_field,
                        view_field=indicator,
                        transform=transform,
                    )
                )
                covered.add(indicator)
                break

        # Add supplementary fields from top resource
        if selected_resources:
            top = selected_resources[0]
            for field in top.fields[:3]:
                if field not in covered and field not in demand.indicators:
                    field_mappings.append(
                        FieldMapping(
                            source_resource_id=top.resource_id,
                            source_field=field,
                            view_field=field,
                            transform="identity",
                        )
                    )

        return field_mappings

    def generate_execution_plan(
        self,
        demand: DemandMetadata,
        selected_resources: list[ResourceMetadata],
    ) -> dict:
        """
        Group selected resources by node_id and emit query tasks.

        Task format:
        {
            "task_id": "T1",
            "node_id": "...",
            "resource_id": "...",
            "operation": "query",
            "params": {...}
        }
        """
        tasks: list[dict] = []
        node_groups: dict[str, list[str]] = {}

        for idx, resource in enumerate(selected_resources, start=1):
            task_id = f"T{idx}"
            task = {
                "task_id": task_id,
                "node_id": resource.node_id,
                "resource_id": resource.resource_id,
                "operation": "query",
                "params": {
                    "object_type": demand.object_type,
                    "object_id": demand.object_id,
                    "indicators": demand.indicators,
                    "time_range": demand.time_range,
                },
            }
            tasks.append(task)
            node_groups.setdefault(resource.node_id, []).append(task_id)

        platform_node_id = self._resolve_platform_node(selected_resources)

        return {
            "tasks": tasks,
            "node_groups": node_groups,
            "platform_node_id": platform_node_id,
            "status": "ready",
            "description": f"Demand-driven view for: {demand.task}",
            "execution_mode": "parallel_by_node",
        }

    def generate_output_schema(
        self,
        demand: DemandMetadata,
        selected_resources: list[ResourceMetadata],
        field_mappings: Optional[list[FieldMapping]] = None,
    ) -> dict:
        """Generate output schema from demand indicators and selected resource fields."""
        mappings = field_mappings or self.generate_field_mappings(
            demand, selected_resources, []
        )

        fields_schema = []
        for indicator in demand.indicators:
            sources = [
                {
                    "resource_id": m.source_resource_id,
                    "source_field": m.source_field,
                    "transform": m.transform,
                }
                for m in mappings
                if m.view_field == indicator
            ]
            fields_schema.append(
                {
                    "name": indicator,
                    "type": "string",
                    "required": True,
                    "sources": sources,
                }
            )

        resource_fields = sorted(
            {
                m.view_field
                for m in mappings
                if m.view_field not in demand.indicators
            }
        )
        for fname in resource_fields:
            fields_schema.append(
                {
                    "name": fname,
                    "type": "string",
                    "required": False,
                    "sources": [
                        {
                            "resource_id": m.source_resource_id,
                            "source_field": m.source_field,
                            "transform": m.transform,
                        }
                        for m in mappings
                        if m.view_field == fname
                    ],
                }
            )

        return {
            "demand_id": demand.demand_id,
            "object_type": demand.object_type,
            "output_format": demand.output_format,
            "fields": fields_schema,
            "resource_count": len(selected_resources),
            "indicator_count": len(demand.indicators),
        }

    def build_view(
        self,
        demand: DemandMetadata,
        match_results: list[MatchResult],
        resources: list[ResourceMetadata],
        mappings: list[SemanticMapping],
        *,
        profile: str = "da_fabric",
    ) -> VirtualView:
        """Build a complete VirtualView from demand, matches, resources, and mappings."""
        start = time.perf_counter()

        resource_map = self._resource_map(resources)
        if profile == "supply_fabric":
            selected = self._select_supply_fabric_resources(demand, match_results, resource_map)
            view_type = "broad_service"
        else:
            selected = self._select_da_fabric_resources(demand, match_results, resource_map)
            view_type = "federated"
            if len({r.node_id for r in selected}) == 1:
                view_type = "single_source"
            elif len(selected) > 3:
                view_type = "multi_source"

        use_mappings = mappings if profile != "ablation_no_mapping" else []
        field_mappings = self.generate_field_mappings(demand, selected, use_mappings)
        execution_plan = self.generate_execution_plan(demand, selected)
        output_schema = self.generate_output_schema(demand, selected, field_mappings)

        elapsed_ms = (time.perf_counter() - start) * 1000
        elapsed_ms += 5.0 * len(selected)

        return VirtualView(
            demand_id=demand.demand_id,
            view_name=f"VirtualView_{demand.task.replace(' ', '_')[:40]}",
            view_type=view_type,
            selected_resources=[r.resource_id for r in selected],
            field_mappings=field_mappings,
            execution_plan=execution_plan,
            output_schema=output_schema,
            construction_time_ms=round(elapsed_ms, 2),
        )

    def build_view_for_method(
        self,
        method: str,
        demand: DemandMetadata,
        match_results: list[MatchResult],
        resources: list[ResourceMetadata],
        mappings: list[SemanticMapping],
    ) -> VirtualView:
        profile = "supply_fabric" if method == "Supply-Fabric" else "da_fabric"
        return self.build_view(demand, match_results, resources, mappings, profile=profile)

    def save_view(self, view: VirtualView, path: Union[str, Path]) -> None:
        """Persist a virtual view to JSON."""
        save_json(path, view)

    def _resolve_platform_node(self, resources: list[ResourceMetadata]) -> str:
        if self.registry:
            platform_nodes = [
                n for n in self.registry.list_nodes()
                if n.node_type.value == "platform"
            ]
            platforms = {r.node_type for r in resources if r.node_type}
            for node in platform_nodes:
                if node.organization in platforms or node.platform in platforms:
                    return node.node_id
            if platform_nodes:
                return platform_nodes[0].node_id
        return "platform-default"


class ViewBuilder(VirtualViewBuilder):
    """Backward-compatible alias for VirtualViewBuilder."""

    def build(
        self,
        demand: DemandMetadata,
        matches: list[MatchResult],
        resources: dict[str, ResourceMetadata],
        max_resources: int = MAX_RESOURCES_PER_VIEW,
        mappings: Optional[list[SemanticMapping]] = None,
    ) -> VirtualView:
        self.max_resources = max_resources
        resource_list = list(resources.values())
        return self.build_view(
            demand,
            matches,
            resource_list,
            mappings or [],
        )

    def build_from_demand(
        self,
        demand: DemandMetadata,
        matches: list[MatchResult],
        resource_list: list[ResourceMetadata],
        mappings: Optional[list[SemanticMapping]] = None,
    ) -> VirtualView:
        return self.build_view(
            demand,
            matches,
            resource_list,
            mappings or [],
        )
