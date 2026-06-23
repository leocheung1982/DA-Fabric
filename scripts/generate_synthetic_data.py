#!/usr/bin/env python3
"""
Generate synthetic multi-platform enterprise regulation dataset for DA-Fabric.

Creates fabric nodes, resource metadata, demand scenarios, semantic mappings,
and ground-truth relevance labels under data/.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

random.seed(42)

# ---------------------------------------------------------------------------
# Domain and entity configuration
# ---------------------------------------------------------------------------

BUSINESS_DOMAINS = [
    "enterprise_profile",
    "license_management",
    "penalty_record",
    "inspection_result",
    "risk_monitoring",
    "complaint_report",
    "regional_statistics",
    "industry_analysis",
    "dashboard_summary",
]

ENTITY_TYPES = [
    "enterprise",
    "license",
    "penalty",
    "inspection",
    "risk",
    "complaint",
    "region",
    "industry",
    "dashboard",
]

DOMAIN_TO_ENTITY = dict(zip(BUSINESS_DOMAINS, ENTITY_TYPES))

PLATFORMS = [
    "provincial_supervision_cloud",
    "municipal_regulation_platform",
    "industry_regulator_hub",
    "cross_region_data_exchange",
    "national_credit_info_platform",
    "unified_regulatory_catalog",
]

REGIONS = ["CN-110000", "CN-310000", "CN-440000", "CN-330000", "CN-510000", "CN-420000"]
INDUSTRIES = ["I64", "C33", "F52", "A01", "D44", "M73"]

FIELD_VOCABULARY = [
    "enterprise_id",
    "enterprise_name",
    "credit_code",
    "market_entity_name",
    "license_id",
    "license_status",
    "penalty_amount",
    "penalty_reason",
    "inspection_date",
    "inspection_result",
    "risk_score",
    "risk_level",
    "risk_index",
    "complaint_count",
    "region_code",
    "industry_code",
    "permit_status",
    "administrative_penalty",
    "sampling_result",
    "handling_status",
    "violation_type",
    "record_date",
    "update_time",
]

ENTITY_FIELD_PROFILES: dict[str, list[str]] = {
    "enterprise": [
        "enterprise_id",
        "enterprise_name",
        "credit_code",
        "market_entity_name",
        "region_code",
        "industry_code",
    ],
    "license": [
        "enterprise_id",
        "license_id",
        "license_status",
        "permit_status",
        "region_code",
        "record_date",
    ],
    "penalty": [
        "enterprise_id",
        "penalty_amount",
        "penalty_reason",
        "administrative_penalty",
        "handling_status",
        "record_date",
    ],
    "inspection": [
        "enterprise_id",
        "inspection_date",
        "inspection_result",
        "sampling_result",
        "violation_type",
        "region_code",
    ],
    "risk": [
        "enterprise_id",
        "risk_score",
        "risk_level",
        "risk_index",
        "region_code",
        "industry_code",
        "update_time",
    ],
    "complaint": [
        "enterprise_id",
        "complaint_count",
        "handling_status",
        "region_code",
        "record_date",
    ],
    "region": [
        "region_code",
        "enterprise_id",
        "risk_score",
        "complaint_count",
        "industry_code",
    ],
    "industry": [
        "industry_code",
        "region_code",
        "enterprise_id",
        "risk_score",
        "complaint_count",
    ],
    "dashboard": [
        "region_code",
        "industry_code",
        "risk_score",
        "risk_level",
        "complaint_count",
        "penalty_amount",
    ],
}

SEMANTIC_TERM_PAIRS: list[tuple[str, str, str, str]] = [
    # Required heterogeneous naming groups
    ("license", "permit", "equivalent", "License/permit equivalence"),
    ("license", "approval", "equivalent", "License/approval equivalence"),
    ("permit", "approval", "equivalent", "Permit/approval equivalence"),
    ("enterprise", "market_entity", "equivalent", "Enterprise/market entity equivalence"),
    ("enterprise", "business_subject", "equivalent", "Enterprise/business subject equivalence"),
    ("market_entity", "business_subject", "equivalent", "Market entity/business subject equivalence"),
    ("penalty", "administrative_sanction", "equivalent", "Penalty/administrative sanction equivalence"),
    ("penalty", "violation_record", "related", "Penalty/violation record relation"),
    ("administrative_sanction", "violation_record", "similar", "Sanction/violation terminology"),
    ("inspection", "sampling_check", "equivalent", "Inspection/sampling check equivalence"),
    ("inspection", "audit_result", "related", "Inspection/audit result relation"),
    ("sampling_check", "audit_result", "similar", "Sampling/audit terminology"),
    ("risk_score", "risk_index", "equivalent", "Risk score/index equivalence"),
    ("risk_score", "warning_level", "related", "Risk score/warning level relation"),
    ("risk_index", "warning_level", "equivalent", "Risk index/warning level equivalence"),
    # Field-level mappings required for ground truth
    ("enterprise_name", "market_entity_name", "equivalent", "Enterprise legal and market naming alignment"),
    ("enterprise_id", "business_subject_id", "equivalent", "Unified enterprise identifier mapping"),
    ("enterprise_id", "credit_code", "related", "Enterprise identifier crosswalk"),
    ("license_status", "permit_status", "equivalent", "License/permit status equivalence"),
    ("license_status", "approval_status", "equivalent", "License/approval status equivalence"),
    ("penalty_amount", "administrative_sanction_amount", "equivalent", "Penalty amount mapping"),
    ("penalty_reason", "administrative_sanction_reason", "similar", "Penalty reason mapping"),
    ("inspection_result", "sampling_check_result", "equivalent", "Inspection outcome mapping"),
    ("inspection_date", "sampling_check_date", "similar", "Inspection date mapping"),
    ("risk_level", "warning_level", "equivalent", "Risk level/warning level mapping"),
    ("enterprise_profile", "enterprise_name", "related", "Profile domain to attribute"),
    ("license_management", "license_status", "related", "License domain to attribute"),
    ("penalty_record", "administrative_penalty", "similar", "Penalty record domain terminology"),
    ("inspection_result", "sampling_result", "similar", "Inspection outcome terminology"),
    ("high_risk", "risk_level", "related", "High-risk monitoring vocabulary"),
    ("abnormal_operation", "violation_type", "similar", "Abnormal operation detection"),
    ("regulatory_handling", "handling_status", "related", "Regulatory workflow status"),
    ("region_code", "regional_statistics", "hierarchical", "Regional aggregation hierarchy"),
    ("industry_code", "industry_analysis", "hierarchical", "Industry taxonomy hierarchy"),
]
DEMAND_SCENARIOS: list[dict] = [
    {
        "scenario_type": "enterprise_profile_query",
        "object_type": "enterprise",
        "domains": ["enterprise_profile"],
        "indicators": ["enterprise_id", "enterprise_name", "credit_code", "market_entity_name"],
        "roles": ["enforcement_officer", "analyst"],
        "task_prefix": "Query enterprise profile",
    },
    {
        "scenario_type": "license_penalty_query",
        "object_type": "license",
        "domains": ["license_management", "penalty_record"],
        "indicators": ["license_id", "license_status", "penalty_amount", "penalty_reason"],
        "roles": ["enforcement_officer", "compliance_manager"],
        "task_prefix": "Cross-check license and penalty records",
    },
    {
        "scenario_type": "inspection_tracking",
        "object_type": "inspection",
        "domains": ["inspection_result", "enterprise_profile"],
        "indicators": ["inspection_date", "inspection_result", "enterprise_id", "violation_type"],
        "roles": ["inspector", "supervisor"],
        "task_prefix": "Track inspection outcomes",
    },
    {
        "scenario_type": "high_risk_monitoring",
        "object_type": "risk",
        "domains": ["risk_monitoring", "enterprise_profile"],
        "indicators": ["risk_score", "risk_level", "risk_index", "enterprise_id"],
        "roles": ["risk_analyst", "supervisor"],
        "task_prefix": "Monitor high-risk enterprises",
    },
    {
        "scenario_type": "regional_risk_dashboard",
        "object_type": "region",
        "domains": ["regional_statistics", "risk_monitoring", "dashboard_summary"],
        "indicators": ["region_code", "risk_score", "complaint_count", "penalty_amount"],
        "roles": ["regional_admin", "analyst"],
        "task_prefix": "Build regional risk dashboard",
    },
    {
        "scenario_type": "industry_trend_analysis",
        "object_type": "industry",
        "domains": ["industry_analysis", "regional_statistics"],
        "indicators": ["industry_code", "risk_score", "complaint_count", "enterprise_id"],
        "roles": ["policy_analyst", "researcher"],
        "task_prefix": "Analyze industry regulatory trends",
    },
    {
        "scenario_type": "complaint_related_query",
        "object_type": "complaint",
        "domains": ["complaint_report", "enterprise_profile"],
        "indicators": ["complaint_count", "enterprise_id", "handling_status", "region_code"],
        "roles": ["complaint_handler", "enforcement_officer"],
        "task_prefix": "Investigate complaint-related records",
    },
    {
        "scenario_type": "abnormal_operation_query",
        "object_type": "enterprise",
        "domains": ["enterprise_profile", "risk_monitoring", "penalty_record"],
        "indicators": ["enterprise_id", "violation_type", "risk_level", "penalty_reason"],
        "roles": ["enforcement_officer", "risk_analyst"],
        "task_prefix": "Detect abnormal enterprise operations",
    },
    {
        "scenario_type": "regulatory_handling_task",
        "object_type": "penalty",
        "domains": ["penalty_record", "inspection_result", "license_management"],
        "indicators": ["penalty_amount", "handling_status", "inspection_result", "license_status"],
        "roles": ["compliance_manager", "supervisor"],
        "task_prefix": "Execute regulatory handling workflow",
    },
    {
        "scenario_type": "proactive_risk_change_subscription",
        "object_type": "risk",
        "domains": ["risk_monitoring", "dashboard_summary"],
        "indicators": ["risk_score", "risk_index", "enterprise_id", "update_time"],
        "roles": ["risk_analyst", "regional_admin"],
        "task_prefix": "Subscribe to proactive risk change alerts",
    },
]

APPLICATION_NODES = [
    ("app-001", "Regulatory Enforcement Portal", "provincial_supervision_bureau"),
    ("app-002", "Risk Monitoring Dashboard", "municipal_regulation_office"),
    ("app-003", "Industry Analysis Workbench", "industry_regulator_hub"),
    ("app-004", "Proactive Compliance Assistant", "unified_regulatory_catalog"),
]

UPDATE_FREQUENCIES = ["realtime", "hourly", "daily", "weekly", "monthly"]
SERVICE_TYPES = ["query", "batch", "streaming", "subscription", "dashboard"]
PRIORITIES = ["low", "medium", "medium", "high", "critical"]
MAPPING_TYPES = ["equivalent", "similar", "hierarchical", "related", "composite"]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def generate_platform_nodes() -> list[dict]:
    nodes = []
    for platform in PLATFORMS:
        nodes.append(
            {
                "node_id": f"plat-{platform[:8]}",
                "node_type": "platform",
                "name": platform.replace("_", " ").title(),
                "organization": platform,
                "description": f"Platform-side fabric node for {platform.replace('_', ' ')} metadata federation",
                "supported_tasks": [
                    "metadata_federation",
                    "schema_alignment",
                    "view_materialization",
                    "catalog_sync",
                ],
                "supported_services": [
                    "virtual_view_hosting",
                    "cross_platform_query",
                    "metadata_discovery",
                ],
                "status": "active",
            }
        )
    return nodes


def generate_source_nodes() -> list[dict]:
    nodes = []
    for i in range(12):
        platform = PLATFORMS[i % len(PLATFORMS)]
        domain = BUSINESS_DOMAINS[i % len(BUSINESS_DOMAINS)]
        entity = DOMAIN_TO_ENTITY[domain]
        nodes.append(
            {
                "node_id": f"src-{i + 1:03d}",
                "node_type": "source",
                "name": f"{domain.replace('_', ' ').title()} Source Node",
                "organization": platform,
                "description": f"Source-side node exposing {entity} metadata from {platform}",
                "supported_tasks": [
                    "data_extraction",
                    "schema_discovery",
                    "quality_validation",
                    "incremental_sync",
                ],
                "supported_services": [
                    "metadata_publish",
                    "batch_export",
                    "event_stream",
                ],
                "status": random.choice(["active", "active", "active", "degraded"]),
            }
        )
    return nodes


def generate_application_nodes() -> list[dict]:
    nodes = []
    for node_id, name, org in APPLICATION_NODES:
        nodes.append(
            {
                "node_id": node_id,
                "node_type": "application",
                "name": name,
                "organization": org,
                "description": f"Application-side node for {name.lower()} demand submission",
                "supported_tasks": [
                    "demand_submission",
                    "view_consumption",
                    "feedback_reporting",
                ],
                "supported_services": [
                    "interactive_query",
                    "proactive_subscription",
                    "dashboard_render",
                ],
                "status": "active",
            }
        )
    return nodes


def generate_nodes() -> list[dict]:
    return (
        generate_platform_nodes()
        + generate_source_nodes()
        + generate_application_nodes()
    )


def _apply_field_aliases(fields: list[str], alias_prob: float = 0.48) -> list[str]:
    """Replace canonical indicator names with synonyms so KW-Catalog cannot match exactly."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))
    from core.semantic_matcher import FIELD_SYNONYMS

    aliased: list[str] = []
    for field in fields:
        synonyms = FIELD_SYNONYMS.get(field, [])
        if synonyms and random.random() < alias_prob:
            aliased.append(random.choice(synonyms))
        else:
            aliased.append(field)
    return list(dict.fromkeys(aliased))


def _pick_fields(entity_type: str, alias_prob: float = 0.48) -> list[str]:
    base = list(ENTITY_FIELD_PROFILES[entity_type])
    extras = random.sample(
        [f for f in FIELD_VOCABULARY if f not in base],
        k=random.randint(0, min(3, len(FIELD_VOCABULARY) - len(base))),
    )
    fields = list(dict.fromkeys(base + extras))
    random.shuffle(fields)
    return _apply_field_aliases(fields, alias_prob=alias_prob)


def generate_resources(nodes: list[dict], count: int = 500) -> list[dict]:
    source_nodes = [n for n in nodes if n["node_type"] == "source"]
    resources: list[dict] = []

    for i in range(count):
        domain = BUSINESS_DOMAINS[i % len(BUSINESS_DOMAINS)]
        entity_type = DOMAIN_TO_ENTITY[domain]
        src = source_nodes[i % len(source_nodes)]
        platform = src["organization"]
        alias_prob = 0.55 if i % 3 == 0 else 0.42
        fields = _pick_fields(entity_type, alias_prob=alias_prob)
        seq = i + 1

        resources.append(
            {
                "resource_id": f"res-{seq:05d}",
                "node_id": src["node_id"],
                "node_type": platform,
                "name": f"{entity_type.title()} Resource {seq:05d}",
                "description": (
                    f"{domain.replace('_', ' ')} metadata for {entity_type} entities "
                    f"published via {platform.replace('_', ' ')}"
                ),
                "business_domain": domain,
                "entity_type": entity_type,
                "resource_type": random.choice(["table", "view", "api", "stream"]),
                "fields": fields,
                "indicators": random.sample(fields, k=min(len(fields), random.randint(2, 5))),
                "keywords": list(
                    dict.fromkeys(
                        [domain, entity_type, platform.split("_")[0], random.choice(REGIONS)]
                    )
                ),
                "update_frequency": random.choice(UPDATE_FREQUENCIES),
                "service_type": random.choice(SERVICE_TYPES),
                "quality_score": round(random.uniform(0.65, 0.99), 3),
            }
        )
    return resources


def generate_demands(nodes: list[dict], count: int = 100) -> list[dict]:
    app_nodes = [n for n in nodes if n["node_type"] == "application"]
    demands: list[dict] = []

    for i in range(count):
        scenario = DEMAND_SCENARIOS[i % len(DEMAND_SCENARIOS)]
        app = app_nodes[i % len(app_nodes)]
        seq = i + 1
        region = REGIONS[i % len(REGIONS)]
        industry = INDUSTRIES[i % len(INDUSTRIES)]

        demands.append(
            {
                "demand_id": f"dem-{seq:05d}",
                "user_id": f"user-{(i % 20) + 1:03d}",
                "role": random.choice(scenario["roles"]),
                "application": app["name"],
                "task": f"{scenario['task_prefix']} #{seq}",
                "object_type": scenario["object_type"],
                "object_id": f"{scenario['object_type']}-{seq:05d}",
                "indicators": scenario["indicators"],
                "conditions": {
                    "scenario_type": scenario["scenario_type"],
                    "business_domains": scenario["domains"],
                    "region_code": region,
                    "industry_code": industry,
                    "description": (
                        f"Synthetic {scenario['scenario_type']} scenario for "
                        f"{scenario['object_type']} analysis in {region}"
                    ),
                    "tags": scenario["domains"] + [scenario["scenario_type"]],
                },
                "time_range": {
                    "start": (datetime.now(timezone.utc) - timedelta(days=90)).date().isoformat(),
                    "end": datetime.now(timezone.utc).date().isoformat(),
                },
                "output_format": random.choice(["json", "csv", "parquet", "dashboard"]),
                "priority": random.choice(PRIORITIES),
                "subscription": {
                    "enabled": (
                        scenario["scenario_type"] == "proactive_risk_change_subscription"
                        or i % 3 == 0
                    ),
                    "channel": random.choice(["push", "email", "webhook"]),
                    "frequency": random.choice(["daily", "hourly", "realtime"]),
                },
                "feedback": {},
                "submitted_at": (
                    datetime.now(timezone.utc) - timedelta(days=random.randint(0, 60))
                ).isoformat(),
            }
        )
    return demands


def generate_ground_truth(
    demands: list[dict],
    resources: list[dict],
    semantic_mappings: list[dict],
    min_relevant: int = 3,
    max_relevant: int = 8,
) -> list[dict]:
    """Ground truth from indicator coverage, entity/domain alignment, and semantic mappings."""
    import sys

    sys.path.insert(0, str(PROJECT_ROOT))
    from core.models import DemandMetadata, ResourceMetadata, SemanticMapping
    from core.semantic_matcher import SemanticMatcher

    matcher = SemanticMatcher(auto_load=False)
    matcher._mappings = [SemanticMapping.model_validate(m) for m in semantic_mappings]
    matcher._build_mapping_index()
    demand_models = [DemandMetadata.model_validate(d) for d in demands]
    resource_models = [ResourceMetadata.model_validate(r) for r in resources]
    resource_by_id = {r.resource_id: r for r in resource_models}

    ground_truth: list[dict] = []

    for demand_dict, demand in zip(demands, demand_models):
        scored = [
            (resource.resource_id, matcher.relevance_score_for_labeling(demand, resource))
            for resource in resource_models
        ]
        scored.sort(key=lambda item: item[1], reverse=True)

        target_count = random.randint(min_relevant, max_relevant)
        selected_ids: set[str] = set()
        selected_pairs: list[tuple[str, float]] = []

        for resource_id, relevance in scored:
            if len(selected_pairs) >= target_count:
                break
            if relevance < 0.42:
                continue
            selected_pairs.append((resource_id, relevance))
            selected_ids.add(resource_id)

        # Ensure mapping-dependent relevant resources are included
        mapping_required: list[tuple[str, float]] = []
        for resource in resource_models:
            exact = matcher.indicator_score(demand, resource, use_mapping=False, exact_only=True)
            mapped = matcher.indicator_score(demand, resource, use_mapping=True)
            if mapped > exact + 0.15 and mapped >= 0.45:
                bonus = matcher.mapping_score(demand, resource, use_mapping=True)
                mapping_required.append((resource.resource_id, max(mapped, bonus, 0.68)))

        mapping_required.sort(key=lambda x: x[1], reverse=True)
        for resource_id, relevance in mapping_required[:2]:
            if resource_id not in selected_ids:
                selected_pairs.append((resource_id, relevance))
                selected_ids.add(resource_id)

        if len(selected_pairs) < min_relevant:
            for resource_id, relevance in scored[:target_count]:
                if resource_id not in selected_ids:
                    selected_pairs.append((resource_id, max(relevance, 0.58)))
                    selected_ids.add(resource_id)
                if len(selected_pairs) >= min_relevant:
                    break

        for resource_id, relevance in selected_pairs[:max_relevant + 2]:
            rel = round(min(max(relevance, 0.55), 0.98), 3)
            ground_truth.append(
                {
                    "demand_id": demand_dict["demand_id"],
                    "resource_id": resource_id,
                    "relevance": rel,
                    "label": "relevant" if rel >= 0.7 else "partial",
                    "requires_mapping": matcher.indicator_score(
                        demand,
                        resource_by_id[resource_id],
                        use_mapping=False,
                        exact_only=True,
                    )
                    < matcher.indicator_score(
                        demand, resource_by_id[resource_id], use_mapping=True
                    ),
                }
            )

    return ground_truth


def generate_feedback_events(
    demands: list[dict],
    resources: list[dict],
    ground_truth: list[dict],
) -> list[dict]:
    """Historical adopted/ignored feedback to drive DA-Fabric+Feedback boosts."""
    import sys
    from collections import defaultdict
    from datetime import datetime, timezone

    sys.path.insert(0, str(PROJECT_ROOT))
    from core.models import FeedbackAction

    gt_by_demand: dict[str, list[dict]] = defaultdict(list)
    for entry in ground_truth:
        gt_by_demand[entry["demand_id"]].append(entry)

    all_resource_ids = [r["resource_id"] for r in resources]
    events: list[dict] = []

    for demand in demands:
        did = demand["demand_id"]
        ranked = sorted(gt_by_demand.get(did, []), key=lambda x: x["relevance"], reverse=True)

        for entry in ranked[:2]:
            events.append(
                {
                    "demand_id": did,
                    "resource_id": entry["resource_id"],
                    "view_id": f"view-fb-{did}",
                    "user_id": demand.get("user_id", ""),
                    "action": FeedbackAction.ADOPTED.value,
                    "rating": round(random.uniform(4.0, 5.0), 1),
                    "relevance_score": entry["relevance"],
                    "comment": "Synthetic adopted feedback for optimization",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        gt_ids = {e["resource_id"] for e in ranked}
        negative_pool = [rid for rid in all_resource_ids if rid not in gt_ids]
        for rid in random.sample(negative_pool, k=min(2, len(negative_pool))):
            events.append(
                {
                    "demand_id": did,
                    "resource_id": rid,
                    "view_id": "",
                    "user_id": demand.get("user_id", ""),
                    "action": random.choice([FeedbackAction.IGNORED.value, FeedbackAction.REJECTED.value]),
                    "rating": round(random.uniform(1.0, 2.5), 1),
                    "relevance_score": round(random.uniform(0.05, 0.35), 3),
                    "comment": "Synthetic negative feedback",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    return events

def generate_semantic_mappings(count: int = 1000) -> list[dict]:
    mappings: list[dict] = []
    seq = 1

    # Canonical pairs from specification and extended vocabulary
    for source, target, mapping_type, description in SEMANTIC_TERM_PAIRS:
        for variant in range(6):
            mappings.append(
                {
                    "mapping_id": f"map-{seq:05d}",
                    "source_term": source,
                    "target_term": target,
                    "mapping_type": mapping_type,
                    "confidence": round(random.uniform(0.75, 0.98), 3),
                    "description": description,
                }
            )
            seq += 1

    # Systematic field-level synonym expansions
    field_pairs = list(
        product(
            ["enterprise", "license", "penalty", "inspection", "risk", "complaint"],
            ["id", "name", "status", "score", "count", "date"],
        )
    )
    random.shuffle(field_pairs)

    while len(mappings) < count:
        if field_pairs:
            entity, suffix = field_pairs.pop()
            source = f"{entity}_{suffix}"
            target = f"{entity}_{suffix}_alt"
            mapping_type = random.choice(MAPPING_TYPES)
        else:
            source = random.choice(FIELD_VOCABULARY)
            target = random.choice(FIELD_VOCABULARY)
            while target == source:
                target = random.choice(FIELD_VOCABULARY)
            mapping_type = random.choice(MAPPING_TYPES)

        mappings.append(
            {
                "mapping_id": f"map-{seq:05d}",
                "source_term": source,
                "target_term": target,
                "mapping_type": mapping_type,
                "confidence": round(random.uniform(0.6, 0.99), 3),
                "description": f"Synthetic {mapping_type} mapping between {source} and {target}",
            }
        )
        seq += 1

    return mappings[:count]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, default=str)
    count = len(data) if isinstance(data, list) else 1
    print(f"  Wrote {path.name} ({count} records)")


def print_summary(
    nodes: list[dict],
    resources: list[dict],
    demands: list[dict],
    ground_truth: list[dict],
    semantic_mappings: list[dict],
) -> None:
    platform = sum(1 for n in nodes if n["node_type"] == "platform")
    source = sum(1 for n in nodes if n["node_type"] == "source")
    application = sum(1 for n in nodes if n["node_type"] == "application")
    gt_per_demand = len(ground_truth) / max(len(demands), 1)

    print("\n" + "=" * 60)
    print("DA-Fabric Synthetic Dataset Summary")
    print("=" * 60)
    print(f"  Platform nodes:      {platform}")
    print(f"  Source nodes:        {source}")
    print(f"  Application nodes:   {application}")
    print(f"  Resources:           {len(resources)}")
    print(f"  Demands:             {len(demands)}")
    print(f"  Semantic mappings:   {len(semantic_mappings)}")
    print(f"  Ground-truth pairs:  {len(ground_truth)}")
    print(f"  Avg relevant/demand: {gt_per_demand:.1f}")
    print(f"  Business domains:    {len(BUSINESS_DOMAINS)}")
    print(f"  Demand scenarios:    {len(DEMAND_SCENARIOS)}")
    print(f"  Output directory:    {DATA_DIR}")
    print("=" * 60)


def main() -> None:
    print("Generating DA-Fabric enterprise regulation synthetic dataset...")
    print(f"  Random seed: 42")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "results" / "figures").mkdir(parents=True, exist_ok=True)

    nodes = generate_nodes()
    resources = generate_resources(nodes, count=500)
    demands = generate_demands(nodes, count=100)
    semantic_mappings = generate_semantic_mappings(count=1000)
    ground_truth = generate_ground_truth(demands, resources, semantic_mappings, min_relevant=3, max_relevant=8)
    feedback_events = generate_feedback_events(demands, resources, ground_truth)

    write_json(DATA_DIR / "nodes.json", nodes)
    write_json(DATA_DIR / "resources.json", resources)
    write_json(DATA_DIR / "demands.json", demands)
    write_json(DATA_DIR / "ground_truth.json", ground_truth)
    write_json(DATA_DIR / "semantic_mappings.json", semantic_mappings)
    write_json(DATA_DIR / "feedback_events.json", feedback_events)
    write_json(DATA_DIR / "proactive_events.json", [])

    print_summary(nodes, resources, demands, ground_truth, semantic_mappings)
    print("\nDone.")


if __name__ == "__main__":
    main()
