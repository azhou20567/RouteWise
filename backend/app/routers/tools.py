"""
Direct HTTP access to the 4 tools — used for testing and MCP inspection.
The MCP server imports these same underlying functions directly.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.models.tool_outputs import DemandEstimate, RouteSummary, TrafficSnapshot
from app.models.recommendation import RouteRecommendation
from app.tools.route_summary import get_route_summary
from app.tools.traffic_snapshot import get_traffic_snapshot
from app.tools.demand_estimate import get_demand_estimate
from app.tools.route_recommendation import generate_route_recommendation

router = APIRouter(prefix="/tools", tags=["tools"])


class RouteSummaryRequest(BaseModel):
    dataset_id: str
    route_id: str


class DatasetRequest(BaseModel):
    dataset_id: str


@router.post("/get_route_summary", response_model=RouteSummary)
async def tool_route_summary(req: RouteSummaryRequest):
    try:
        return await get_route_summary(req.dataset_id, req.route_id)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/get_traffic_snapshot", response_model=TrafficSnapshot)
async def tool_traffic_snapshot(req: DatasetRequest):
    try:
        return await get_traffic_snapshot(req.dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/get_demand_estimate", response_model=DemandEstimate)
async def tool_demand_estimate(req: DatasetRequest):
    try:
        return await get_demand_estimate(req.dataset_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/generate_route_recommendation", response_model=RouteRecommendation)
async def tool_generate_recommendation(req: DatasetRequest):
    try:
        return await generate_route_recommendation(req.dataset_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
