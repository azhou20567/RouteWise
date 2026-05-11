"""
Direct HTTP access to the three data-gathering tools. The MCP server and the
LLM agentic loop call the same underlying functions. The final RouteRecommendation
is produced exclusively through POST /analysis/{id}/recommend — there is no
HTTP entry point for the LLM exit sentinel `generate_route_recommendation`.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.tool_outputs import DemandEstimate, RouteSummary, TrafficSnapshot
from app.tools.route_summary import get_route_summary
from app.tools.traffic_snapshot import get_traffic_snapshot
from app.tools.demand_estimate import get_demand_estimate

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
