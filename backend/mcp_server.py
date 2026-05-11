"""
RouteWise MCP Server

Exposes the three data-gathering tools via the MCP stdio transport so any
MCP-compatible client (Claude Desktop, Claude Code, etc.) can call them
directly. The final RouteRecommendation is generated only through the
LLM agentic loop at POST /analysis/{id}/recommend — there is no MCP tool
for it, because outside the loop a "recommendation" tool would just be
a duplicate trigger for that same endpoint.

Run from the backend/ directory:
    python mcp_server.py
"""

import sys
from pathlib import Path

# Ensure the backend/ directory is on the path when running directly
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

from app.config import settings
from app.data.loader import get_dataset
from app.tools.route_summary import get_route_summary as _get_route_summary
from app.tools.traffic_snapshot import get_traffic_snapshot as _get_traffic_snapshot
from app.tools.demand_estimate import get_demand_estimate as _get_demand_estimate

mcp = FastMCP("RouteWise")


@mcp.tool()
async def get_route_summary(dataset_id: str, route_id: str) -> dict:
    """
    Returns a detailed summary of a single bus route including stops,
    distance, duration, bus capacity, and estimated ridership load factor.
    Call this for each route you want to analyze.
    """
    result = await _get_route_summary(dataset_id, route_id)
    return result.model_dump()


@mcp.tool()
async def get_traffic_snapshot(dataset_id: str) -> dict:
    """
    Returns simulated morning peak traffic conditions for all zones in the
    dataset, including congestion level and estimated delay minutes.
    """
    result = await _get_traffic_snapshot(dataset_id)
    return result.model_dump()


@mcp.tool()
async def get_demand_estimate(dataset_id: str) -> dict:
    """
    Returns ridership demand estimates per zone based on proxy enrollment
    data, current bus capacity allocation, and utilization rates.
    """
    result = await _get_demand_estimate(dataset_id)
    return result.model_dump()


# ---------------------------------------------------------------------------
# Map-quality tools — require GOOGLE_MAPS_BACKEND_API_KEY. Lazy-imported
# so the MCP server still starts when the build-time deps aren't installed.
# ---------------------------------------------------------------------------

def _require_maps():
    if not settings.google_maps_backend_api_key:
        raise RuntimeError(
            "GOOGLE_MAPS_BACKEND_API_KEY is not configured. Set it in .env "
            "to use geocode_address or validate_route_geometry."
        )
    from app.services.google_maps_service import GoogleMapsService
    return GoogleMapsService()


@mcp.tool()
async def geocode_address(address: str) -> dict:
    """
    Resolve a postal address or place name to lat/lng + a formatted address.
    Backed by Google's Geocoding API; responses are cached on disk so repeat
    lookups are free.
    """
    maps = _require_maps()
    result = maps.geocode(address)
    return {
        "lat": result.lat,
        "lng": result.lng,
        "formatted_address": result.formatted_address,
    }


@mcp.tool()
async def validate_route_geometry(dataset_id: str, route_id: str) -> dict:
    """
    Sample a route's polyline every 50 m and check each sample's distance
    to the nearest real road via Google's Roads API. Returns
    {valid, sampled_points, on_road_points, pass_rate, offending_points}.
    Use after edits to confirm a route still follows actual streets.
    """
    from app.services.google_maps_service import LatLng
    from app.services.route_validator import validate_polyline_on_road

    dataset = get_dataset(dataset_id)
    route = next(
        (r for r in [*dataset.routes, *dataset.optimized_scenario.routes] if r.route_id == route_id),
        None,
    )
    if route is None:
        raise ValueError(f"Route '{route_id}' not in dataset '{dataset_id}'")
    if not route.path:
        raise ValueError(f"Route '{route_id}' has no path geometry to validate")

    maps = _require_maps()
    path = [LatLng(lat=p.lat, lng=p.lng) for p in route.path]
    result = validate_polyline_on_road(path, maps)

    return {
        "valid": result.valid,
        "sampled_points": result.sampled_points,
        "on_road_points": result.on_road_points,
        "pass_rate": round(result.pass_rate, 4),
        "tolerance_m": result.tolerance_m,
        "pass_threshold": result.pass_threshold,
        "offending_points": [
            {"lat": p.lat, "lng": p.lng} for p in result.offending_points
        ],
    }


if __name__ == "__main__":
    mcp.run()
