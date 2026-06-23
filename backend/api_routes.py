"""REST API routes for DA-Fabric."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.service_layer import DAFabricService
from core.models import (
    DemandMetadata,
    FabricNode,
    FeedbackAction,
    FeedbackEvent,
    NodeStatus,
    NodeType,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
service = DAFabricService(PROJECT_ROOT)

router = APIRouter()


class NodeRegisterRequest(BaseModel):
    node_id: str
    node_type: NodeType
    name: str
    organization: str = ""
    description: str = ""
    supported_tasks: list[str] = Field(default_factory=list)
    supported_services: list[str] = Field(default_factory=list)
    status: NodeStatus = NodeStatus.ACTIVE


class MatchRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)


class ProactiveSimulateRequest(BaseModel):
    num_updates: int = Field(default=1, ge=1, le=100)


class FeedbackRequest(BaseModel):
    demand_id: str
    view_id: str = ""
    user_id: str = ""
    resource_id: str = ""
    action: FeedbackAction = FeedbackAction.VIEWED
    rating: float = Field(default=3.0, ge=0.0, le=5.0)
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    comment: str = ""


@router.get("/")
def root():
    """API root — service metadata and live counts."""
    status = service.get_status()
    return {
        "service": "DA-Fabric API",
        "version": "0.1.0",
        "description": "Demand-Aware Data Fabric research prototype",
        "status": status,
        "endpoints": [
            "GET /nodes",
            "POST /nodes/register",
            "GET /resources",
            "GET /demands",
            "POST /demands",
            "POST /match/{demand_id}",
            "POST /views/{demand_id}",
            "POST /execute/{view_id}",
            "POST /proactive/simulate",
            "POST /feedback",
        ],
    }


@router.get("/nodes")
def list_nodes(
    node_type: Optional[NodeType] = None,
    status: Optional[NodeStatus] = None,
):
    nodes = service.registry.list_nodes(node_type=node_type, status=status)
    return [n.model_dump(mode="json") for n in nodes]


@router.post("/nodes/register")
def register_node(body: NodeRegisterRequest):
    node = FabricNode(**body.model_dump())
    registered = service.register_node(node)
    return registered.model_dump(mode="json")


@router.get("/resources")
def list_resources(
    node_type: Optional[str] = Query(None, description="Filter by node/platform type"),
    business_domain: Optional[str] = Query(None, description="Filter by business domain"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    domain: Optional[str] = Query(None, description="Legacy alias for business_domain"),
    platform: Optional[str] = Query(None, description="Legacy alias for node_type"),
):
    resources = service.metadata.list_resources(
        node_type=node_type or platform,
        business_domain=business_domain or domain,
        entity_type=entity_type,
    )
    return [r.model_dump(mode="json") for r in resources]


@router.get("/demands")
def list_demands():
    return [d.model_dump(mode="json") for d in service.demands.list_demands()]


@router.post("/demands")
def create_demand(body: DemandMetadata):
    saved = service.submit_demand(body)
    return saved.model_dump(mode="json")


@router.post("/match/{demand_id}")
def match_demand(demand_id: str, body: MatchRequest | None = None):
    if not service.demands.get(demand_id):
        raise HTTPException(status_code=404, detail=f"Demand not found: {demand_id}")
    top_k = body.top_k if body else 5
    matches = service.match_demand(demand_id, top_k=top_k)
    return {
        "demand_id": demand_id,
        "top_k": top_k,
        "match_count": len(matches),
        "matches": [m.model_dump(mode="json") for m in matches],
    }


@router.post("/views/{demand_id}")
def build_view(demand_id: str, body: MatchRequest | None = None):
    if not service.demands.get(demand_id):
        raise HTTPException(status_code=404, detail=f"Demand not found: {demand_id}")
    top_k = body.top_k if body else 8
    view = service.build_view(demand_id, top_k=top_k)
    if not view:
        raise HTTPException(
            status_code=422,
            detail=f"No virtual view could be built for demand: {demand_id}",
        )
    return view.model_dump(mode="json")


@router.post("/execute/{view_id}")
def execute_view(view_id: str):
    if not service.get_view(view_id):
        raise HTTPException(status_code=404, detail=f"View not found: {view_id}")
    result = service.execute_view(view_id)
    if not result:
        raise HTTPException(status_code=422, detail=f"Execution failed for view: {view_id}")
    return result.model_dump(mode="json")


@router.post("/proactive/simulate")
def simulate_proactive(body: ProactiveSimulateRequest | None = None):
    num_updates = body.num_updates if body else 1
    return service.simulate_proactive(num_updates=num_updates)


@router.post("/feedback")
def submit_feedback(body: FeedbackRequest):
    if not service.demands.get(body.demand_id):
        raise HTTPException(status_code=404, detail=f"Demand not found: {body.demand_id}")
    feedback = FeedbackEvent(**body.model_dump())
    recorded = service.record_feedback(feedback)
    return recorded.model_dump(mode="json")
