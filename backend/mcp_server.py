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


if __name__ == "__main__":
    mcp.run()
